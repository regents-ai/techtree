"""The complete first-run tool sequence, through real processes.

Specification section 7.15, integration rows. Everything here goes through the
actual bridge and an actual executable named ``techtree`` on a temporary PATH,
so the argv, the envelopes, the bounded output, and the session progression are
all exercised the way a host would exercise them.

No Docker, no model, no money: the fake CLI answers from a script.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest
from support import envelope, install_fake_cli
from techtree_hermes.approvals import DisclosureStore, InstallPlanStore, ReviewStore
from techtree_hermes.models import DemoStage
from techtree_hermes.release import load_embedded_release_core, release_core_digest
from techtree_hermes.services.container import PluginServices
from techtree_hermes.state import SessionStore, latest_session
from techtree_hermes.tools import TOOL_HANDLERS

CORE = load_embedded_release_core()
PUBLISHED = dataclasses.replace(
    CORE,
    placeholder_release=False,
    placeholder_fields=(),
    release_id="0.1.0",
    cli_version="0.1.0",
    cli_source_commit="a" * 40,
    starter_skill_digest="sha256:" + "7" * 64,
)
RUN_ID = "run_" + "0" * 32
DRAFT_ID = "draft_" + "0" * 32
TOKEN = "confirmation-token-value"
POLICY = "sha256:" + "b" * 64


class StarterSkillDouble:
    """Stands in for a release whose starter Skill exists."""

    def materialize(self, services: Any) -> dict[str, Any]:
        return {"path": "/tmp/starter-skill", "digest": PUBLISHED.starter_skill_digest}


def _answers() -> dict[str, dict[str, Any]]:
    return {
        "release info": envelope(
            command="release info",
            data={
                "release_id": PUBLISHED.release_id,
                "cli_version": PUBLISHED.cli_version,
                "package_version": PUBLISHED.cli_version,
                "cli_source_commit": PUBLISHED.cli_source_commit,
                "protocol_version": PUBLISHED.protocol_version,
                "release_core_digest": release_core_digest(PUBLISHED),
                "engine_digest": PUBLISHED.engine_digest,
                "catalog_digest": PUBLISHED.catalog_digest,
                "intro_climb_reference": PUBLISHED.intro_climb_reference,
                "placeholder_release": False,
                "placeholder_fields": [],
            },
        ),
        "doctor": envelope(command="doctor", data={"checks": []}),
        "climb list": envelope(
            command="climb list",
            data=[{"reference": PUBLISHED.intro_climb_reference}],
        ),
        "climb show": envelope(
            command="climb show",
            data={"reference": PUBLISHED.intro_climb_reference, "proof_grade": "P1"},
        ),
        "climb prepare": envelope(
            command="climb prepare",
            data={
                "draft_id": DRAFT_ID,
                "confirmation_token": TOKEN,
                "data_policy_digest": POLICY,
                "skill_root_digest": PUBLISHED.starter_skill_digest,
                "estimated_episodes": 72,
            },
        ),
        "climb start": envelope(
            command="climb start", data={"run_id": RUN_ID, "phase": "created"}
        ),
        "run status": envelope(
            command="run status",
            data={
                "run_id": RUN_ID,
                "phase": "completed",
                "terminal": True,
                "result_available": True,
                "worker_alive": False,
            },
        ),
        "run result": envelope(
            command="run result",
            data={"presentation": {"run_id": RUN_ID, "decision": "improved"}},
        ),
    }


@pytest.fixture
def services(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PluginServices:
    """A container wired to a fake Techtree executable on PATH."""
    answers = _answers()
    body = (
        f"answers = {answers!r}\n"
        "key = ' '.join(a for a in argv if not a.startswith('--'))\n"
        "for name in sorted(answers, key=len, reverse=True):\n"
        "    if key.startswith(name):\n"
        "        print(json.dumps(answers[name]))\n"
        "        break\n"
        "else:\n"
        "    sys.exit(2)\n"
    )
    install_fake_cli(tmp_path / "bin", body=body, monkeypatch=monkeypatch)

    from techtree_hermes.bridge import CliBridge

    return PluginServices(
        ctx=None,
        root=tmp_path,
        release_core=PUBLISHED,
        release_core_digest=release_core_digest(PUBLISHED),
        bridge=CliBridge(),
        plans=InstallPlanStore(),
        reviews=ReviewStore(),
        disclosures=DisclosureStore(),
        sessions=SessionStore(),
        assets=StarterSkillDouble(),
    )


def _call(name: str, services: PluginServices, args: dict[str, Any]) -> dict[str, Any]:
    parsed = json.loads(TOOL_HANDLERS[name](services, args))
    assert isinstance(parsed, dict)
    return parsed


def _current(services: Any) -> Any:
    """Return the session there must be one of."""
    session = latest_session(services)
    assert session is not None
    return session


def test_the_whole_first_run_sequence(services: PluginServices) -> None:
    readiness = _call("techtree_system_check", services, {})
    assert readiness["ok"] is True

    catalogue = _call("techtree_climbs_list", services, {})
    assert catalogue["ok"] is True

    prepared = _call("techtree_demo_prepare", services, {})
    assert prepared["draft_id"] == DRAFT_ID
    assert prepared["confirmation_token"] == TOKEN
    assert _current(services).stage is DemoStage.FIRST_DRAFT_PREPARED

    started = _call(
        "techtree_climb_start",
        services,
        {
            "draft_id": DRAFT_ID,
            "confirmation_token": TOKEN,
            "data_policy_digest": POLICY,
        },
    )
    assert started["data"]["run_id"] == RUN_ID
    assert _current(services).stage is DemoStage.FIRST_RUN_ACTIVE

    status = _call("techtree_run_status", services, {"run_id": RUN_ID})
    assert status["summary"]["finished"] is True
    assert _current(services).stage is DemoStage.FIRST_RESULT_READY

    result = _call("techtree_run_result", services, {"run_id": RUN_ID})
    assert result["ok"] is True
    assert "not been independently reproduced" in result["reproduction"]
    assert result["demo"]["stage"] == DemoStage.FIRST_RESULT_READY.value


def test_nothing_in_the_sequence_starts_a_run_by_itself(
    services: PluginServices,
) -> None:
    """Preparation is free and inert; only an explicit start starts anything."""
    _call("techtree_system_check", services, {})
    _call("techtree_demo_prepare", services, {})

    session = _current(services)
    assert session.first_run_id is None
    assert session.stage is DemoStage.FIRST_DRAFT_PREPARED


def test_a_session_that_lost_its_memory_recovers_from_the_run(
    services: PluginServices,
) -> None:
    """A new Hermes session knows nothing; Techtree still knows the run."""
    _call("techtree_demo_prepare", services, {})
    _call(
        "techtree_climb_start",
        services,
        {
            "draft_id": DRAFT_ID,
            "confirmation_token": TOKEN,
            "data_policy_digest": POLICY,
        },
    )
    run_id = _current(services).first_run_id
    assert run_id is not None

    restarted = dataclasses.replace(services, sessions=SessionStore())
    assert latest_session(restarted) is None

    status = _call("techtree_run_status", restarted, {"run_id": run_id})

    assert status["summary"]["finished"] is True
    assert status["summary"]["result_available"] is True
