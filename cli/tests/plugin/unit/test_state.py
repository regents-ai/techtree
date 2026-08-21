"""What the plugin remembers, and what it refuses to conclude.

Specification sections 6.3, 7.9, 7.15 (state rows).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from techtree_hermes.errors import PluginError, PluginStateError
from techtree_hermes.models import DemoStage
from techtree_hermes.services.session import (
    create_demo_session,
    update_after_first_prepare,
    update_after_first_result,
    update_after_first_start,
    update_after_second_start,
)
from techtree_hermes.state import (
    SessionStore,
    active_run_ids,
    latest_session,
    prune_expired_plans,
    prune_expired_sessions,
    read_session_document,
    reconcile_session_with_cli,
    save_session,
    session_payload,
)

RUN_ID = "run_" + "0" * 32
SECOND_RUN_ID = "run_" + "1" * 32
DRAFT_ID = "draft_" + "0" * 32
DIGEST = "sha256:" + "a" * 64


class FakeBridge:
    """A bridge that answers with whatever the test wants, or refuses."""

    def __init__(
        self, envelope: dict[str, Any] | None = None, error: Exception | None = None
    ) -> None:
        self.envelope = envelope
        self.error = error
        self.calls: list[list[str]] = []

    def invoke(self, arguments: list[str]) -> dict[str, Any]:
        self.calls.append(list(arguments))
        if self.error is not None:
            raise self.error
        return self.envelope or {}


class FakeServices:
    """Just enough container for the state layer."""

    def __init__(self, bridge: Any = None) -> None:
        self.sessions = SessionStore()
        self.plans = _PlanStore()
        self.bridge = bridge or FakeBridge()
        self.release_core_digest = DIGEST


class _PlanStore:
    def __init__(self) -> None:
        self.pruned = 0

    def prune_expired(self, now: Any = None) -> int:
        self.pruned += 1
        return 2


def _status(**data: Any) -> dict[str, Any]:
    return {
        "schema_version": "techtree.cli.v1",
        "command": "run status",
        "ok": True,
        "data": {"run_id": RUN_ID, **data},
        "error": None,
        "messages": [],
        "warnings": [],
        "next_actions": [],
    }


def _session_at(stage: DemoStage, **changes: Any) -> Any:
    from dataclasses import replace

    from techtree_hermes.release import load_embedded_release_core

    session = create_demo_session(
        release=load_embedded_release_core(),
        climb_reference="procedure-transfer-dev@1",
        release_core_digest=DIGEST,
    )
    return replace(session, stage=stage, **changes)


def _current(services: Any) -> Any:
    """Return the session there must be one of."""
    session = latest_session(services)
    assert session is not None
    return session


# What is kept ---------------------------------------------------------------


def test_state_holds_identifiers_and_nothing_else() -> None:
    """No keys, no tokens, no Skill text, no Episode data."""
    session = update_after_first_prepare(
        _session_at(DemoStage.CLI_READY),
        {
            "ok": True,
            "data": {
                "draft_id": DRAFT_ID,
                "skill_root_digest": DIGEST,
                "confirmation_token": "token-that-must-not-be-kept",
                "included_files": ["SKILL.md"],
            },
        },
    )

    stored = json.dumps(session_payload(session))
    assert "token-that-must-not-be-kept" not in stored
    assert "SKILL.md" not in stored
    assert session.first_draft_id == DRAFT_ID
    assert session.source_skill_v1_digest == DIGEST


def test_a_session_payload_carries_only_declared_fields() -> None:
    payload = session_payload(_session_at(DemoStage.CLI_READY))

    assert set(payload) == {
        "demo_id",
        "stage",
        "climb_reference",
        "first_draft_id",
        "first_run_id",
        "first_proof_path",
        "source_skill_v1_digest",
        "second_draft_id",
        "second_run_id",
        "second_proof_path",
        "revision_attempts",
        "updated_at",
    }


# Malformed state --------------------------------------------------------------


@pytest.mark.parametrize(
    "document",
    [
        "not a session",
        {"demo_id": "demo_1"},
        {
            "demo_id": "demo_1",
            "stage": "inventing",
            "release_core_digest": DIGEST,
            "climb_reference": "c@1",
            "updated_at": "now",
        },
    ],
)
def test_malformed_state_fails_safely(document: Any) -> None:
    with pytest.raises(PluginStateError):
        read_session_document(document)


def test_a_well_formed_document_reads_back() -> None:
    session = _session_at(DemoStage.FIRST_RUN_ACTIVE, first_run_id=RUN_ID)
    document = {
        **session_payload(session),
        "release_core_digest": DIGEST,
        "proposal_id": None,
    }

    assert read_session_document(document).first_run_id == RUN_ID


# Selection and pruning ----------------------------------------------------------


def test_the_latest_session_is_the_one_last_touched() -> None:
    services = FakeServices()
    first = _session_at(DemoStage.CLI_READY)
    second = _session_at(DemoStage.CLI_READY)
    save_session(services, first)
    save_session(services, second)
    save_session(services, first)

    assert _current(services).demo_id == first.demo_id


def test_active_runs_are_the_ones_still_going() -> None:
    services = FakeServices()
    save_session(services, _session_at(DemoStage.FIRST_RUN_ACTIVE, first_run_id=RUN_ID))
    save_session(
        services,
        _session_at(DemoStage.SECOND_RUN_ACTIVE, second_run_id=SECOND_RUN_ID),
    )
    save_session(services, _session_at(DemoStage.COMPLETE, first_run_id="run_ignored"))

    assert sorted(active_run_ids(services)) == sorted([RUN_ID, SECOND_RUN_ID])


def test_stale_sessions_and_expired_plans_are_pruned() -> None:
    services = FakeServices()
    old = _session_at(
        DemoStage.CLI_READY,
        updated_at=(datetime.now(UTC) - timedelta(days=30)).isoformat(),
    )
    save_session(services, old)
    save_session(services, _session_at(DemoStage.CLI_READY))

    assert prune_expired_sessions(services) == 1
    assert prune_expired_plans(services) == 2


# Reconciliation ------------------------------------------------------------------


def test_a_running_run_stays_running() -> None:
    services = FakeServices(
        FakeBridge(_status(phase="running_variants", terminal=False))
    )
    session = _session_at(DemoStage.FIRST_RUN_ACTIVE, first_run_id=RUN_ID)

    assert reconcile_session_with_cli(services, session).stage is (
        DemoStage.FIRST_RUN_ACTIVE
    )


def test_reconciliation_cannot_invent_a_completed_run() -> None:
    """Terminal is not enough: a result has to exist."""
    services = FakeServices(
        FakeBridge(_status(phase="completed", terminal=True, result_available=False))
    )
    session = _session_at(DemoStage.FIRST_RUN_ACTIVE, first_run_id=RUN_ID)

    assert reconcile_session_with_cli(services, session).stage is (
        DemoStage.FIRST_RUN_ACTIVE
    )


def test_a_completed_run_with_a_result_advances() -> None:
    services = FakeServices(
        FakeBridge(_status(phase="completed", terminal=True, result_available=True))
    )
    session = _session_at(DemoStage.FIRST_RUN_ACTIVE, first_run_id=RUN_ID)

    assert reconcile_session_with_cli(services, session).stage is (
        DemoStage.FIRST_RESULT_READY
    )


@pytest.mark.parametrize(
    ("phase", "expected"),
    [("failed", DemoStage.FAILED), ("cancelled", DemoStage.CANCELLED)],
)
def test_a_run_that_ended_badly_is_recorded_as_it_ended(
    phase: str, expected: DemoStage
) -> None:
    services = FakeServices(FakeBridge(_status(phase=phase, terminal=True)))
    session = _session_at(DemoStage.FIRST_RUN_ACTIVE, first_run_id=RUN_ID)

    assert reconcile_session_with_cli(services, session).stage is expected


def test_an_unreachable_cli_changes_nothing() -> None:
    services = FakeServices(FakeBridge(error=PluginError("no CLI here")))
    session = _session_at(DemoStage.FIRST_RUN_ACTIVE, first_run_id=RUN_ID)

    assert reconcile_session_with_cli(services, session) == session


def test_a_session_with_no_active_run_asks_nothing() -> None:
    bridge = FakeBridge(_status(phase="completed", terminal=True))
    services = FakeServices(bridge)

    reconcile_session_with_cli(services, _session_at(DemoStage.FIRST_DRAFT_PREPARED))

    assert bridge.calls == []


def test_the_state_is_rebuildable_from_techtree_after_a_restart() -> None:
    """A fresh session knows nothing; the run itself still knows everything."""
    services = FakeServices(
        FakeBridge(_status(phase="completed", terminal=True, result_available=True))
    )

    assert latest_session(services) is None

    recovered = reconcile_session_with_cli(
        services, _session_at(DemoStage.FIRST_RUN_ACTIVE, first_run_id=RUN_ID)
    )

    assert recovered.stage is DemoStage.FIRST_RESULT_READY
    assert services.bridge.calls == [["run", "status", RUN_ID]]


# Stage transitions -------------------------------------------------------------------


def test_the_first_run_advances_through_its_stages() -> None:
    session = _session_at(DemoStage.CLI_READY)

    session = update_after_first_prepare(
        session,
        {"ok": True, "data": {"draft_id": DRAFT_ID, "skill_root_digest": DIGEST}},
    )
    assert session.stage is DemoStage.FIRST_DRAFT_PREPARED

    session = update_after_first_start(
        session, {"ok": True, "data": {"run_id": RUN_ID}}
    )
    assert session.stage is DemoStage.FIRST_RUN_ACTIVE
    assert session.first_run_id == RUN_ID

    session = update_after_first_result(session, {"ok": True, "data": {}})
    assert session.stage is DemoStage.FIRST_RESULT_READY


def test_a_start_that_returned_no_run_changes_nothing() -> None:
    session = _session_at(DemoStage.FIRST_DRAFT_PREPARED)

    assert update_after_first_start(session, {"ok": True, "data": {}}) == session


def test_a_failed_result_call_does_not_mark_a_result_ready() -> None:
    session = _session_at(DemoStage.FIRST_RUN_ACTIVE, first_run_id=RUN_ID)

    assert update_after_first_result(session, {"ok": False, "data": None}) == session


def test_the_second_run_counts_the_revision() -> None:
    session = _session_at(DemoStage.SECOND_DRAFT_PREPARED, first_run_id=RUN_ID)

    session = update_after_second_start(
        session, {"ok": True, "data": {"run_id": SECOND_RUN_ID, "draft_id": DRAFT_ID}}
    )

    assert session.stage is DemoStage.SECOND_RUN_ACTIVE
    assert session.second_run_id == SECOND_RUN_ID
    assert session.revision_attempts == 1
