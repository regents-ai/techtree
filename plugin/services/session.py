"""How a guided introduction moves forward. Specification sections 6.2, 7.10.

Each function takes what Techtree just said and returns the next session
state. They are the only place a stage changes, so "what happened so far" can
be read in one screen — and so nothing can quietly mark a comparison finished
that Techtree has not finished.
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, Final

from ..errors import PluginError
from ..models import DemoSessionState, DemoStage, ReleaseCore

#: Which stage may follow which. Specification section 8.18.
#:
#: The table is here rather than in the callers because section 10.4 forbids
#: particular jumps outright — an install plan never becomes an installation,
#: a prepared draft never becomes a started run, a first result never becomes
#: a proposal, a proposal never becomes a second run — and every one of those
#: is a person's decision. A transition that is not in this table cannot
#: happen by accident, because it cannot happen at all.
ALLOWED_TRANSITIONS: Mapping[DemoStage, frozenset[DemoStage]] = {
    DemoStage.PLUGIN_READY: frozenset(
        {DemoStage.CLI_INSTALL_REQUIRED, DemoStage.CLI_READY}
    ),
    DemoStage.CLI_INSTALL_REQUIRED: frozenset({DemoStage.CLI_READY}),
    DemoStage.CLI_READY: frozenset({DemoStage.FIRST_DRAFT_PREPARED}),
    DemoStage.FIRST_DRAFT_PREPARED: frozenset({DemoStage.FIRST_RUN_ACTIVE}),
    DemoStage.FIRST_RUN_ACTIVE: frozenset(
        {DemoStage.FIRST_RESULT_READY, DemoStage.FAILED, DemoStage.CANCELLED}
    ),
    DemoStage.FIRST_RESULT_READY: frozenset({DemoStage.REVISION_PROPOSAL_READY}),
    DemoStage.REVISION_PROPOSAL_READY: frozenset({DemoStage.SECOND_DRAFT_PREPARED}),
    DemoStage.SECOND_DRAFT_PREPARED: frozenset({DemoStage.SECOND_RUN_ACTIVE}),
    DemoStage.SECOND_RUN_ACTIVE: frozenset(
        {DemoStage.COMPLETE, DemoStage.FAILED, DemoStage.CANCELLED}
    ),
    DemoStage.COMPLETE: frozenset(),
    DemoStage.FAILED: frozenset(),
    DemoStage.CANCELLED: frozenset(),
}

CODE_STAGE_INVALID: Final = "demo_stage_invalid"


def require_transition(current: DemoStage, target: DemoStage) -> None:
    """Refuse a stage change the guided introduction does not allow.

    Raises:
        PluginError: when nothing in the journey goes from here to there.
    """
    if target is current:
        return
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise PluginError(
            f"a guided comparison does not go from {current.value} to {target.value}",
            code=CODE_STAGE_INVALID,
        )


def create_demo_session(
    *, release: ReleaseCore, climb_reference: str, release_core_digest: str
) -> DemoSessionState:
    """Start a new guided introduction."""
    return DemoSessionState(
        demo_id=f"demo_{secrets.token_hex(16)}",
        release_core_digest=release_core_digest,
        climb_reference=climb_reference or release.intro_climb_reference,
        stage=DemoStage.CLI_READY,
        first_draft_id=None,
        first_run_id=None,
        first_proof_path=None,
        source_skill_v1_digest=None,
        proposal_id=None,
        second_draft_id=None,
        second_run_id=None,
        second_proof_path=None,
        revision_attempts=0,
        updated_at=_now(),
    )


def update_after_first_prepare(
    session: DemoSessionState, envelope: Mapping[str, Any]
) -> DemoSessionState:
    """Record the prepared draft. No token is kept: it is used once, elsewhere."""
    data = _data(envelope)
    return _advance(
        session,
        DemoStage.FIRST_DRAFT_PREPARED,
        first_draft_id=_identifier(data, "draft_id"),
        source_skill_v1_digest=_identifier(data, "skill_root_digest"),
    )


def update_after_first_start(
    session: DemoSessionState, envelope: Mapping[str, Any]
) -> DemoSessionState:
    """Record the detached run this session started."""
    data = _data(envelope)
    run_id = _identifier(data, "run_id")
    if run_id is None:
        return session
    return _advance(session, DemoStage.FIRST_RUN_ACTIVE, first_run_id=run_id)


def update_after_first_result(
    session: DemoSessionState, envelope: Mapping[str, Any]
) -> DemoSessionState:
    """Record that a first result exists, and where its proof is."""
    if not envelope.get("ok"):
        return session
    data = _data(envelope)
    return _advance(
        session,
        DemoStage.FIRST_RESULT_READY,
        first_proof_path=_identifier(data, "proof_path"),
    )


def update_after_second_start(
    session: DemoSessionState, envelope: Mapping[str, Any]
) -> DemoSessionState:
    """Record the second comparison, and that a revision was spent on it."""
    data = _data(envelope)
    run_id = _identifier(data, "run_id")
    if run_id is None:
        return session
    return _advance(
        session,
        DemoStage.SECOND_RUN_ACTIVE,
        second_run_id=run_id,
        second_draft_id=_identifier(data, "draft_id"),
        revision_attempts=session.revision_attempts + 1,
    )


def update_after_proposal(
    session: DemoSessionState, *, proposal_id: str | None = None
) -> DemoSessionState:
    """Record that one revision has been proposed, before it is prepared."""
    return _advance(session, DemoStage.REVISION_PROPOSAL_READY, proposal_id=proposal_id)


def update_after_second_prepare(
    session: DemoSessionState, envelope: Mapping[str, Any]
) -> DemoSessionState:
    """Record the prepared replacement comparison."""
    data = _data(envelope)
    return _advance(
        session,
        DemoStage.SECOND_DRAFT_PREPARED,
        second_draft_id=_identifier(data, "draft_id"),
    )


def _advance(
    session: DemoSessionState, stage: DemoStage, **changes: Any
) -> DemoSessionState:
    require_transition(session.stage, stage)
    return replace(session, stage=stage, updated_at=_now(), **changes)


def _data(envelope: Mapping[str, Any]) -> Mapping[str, Any]:
    data = envelope.get("data")
    return data if isinstance(data, dict) else {}


def _identifier(data: Mapping[str, Any], name: str) -> str | None:
    value = data.get(name)
    return value if isinstance(value, str) and value else None


def _now() -> str:
    return datetime.now(UTC).isoformat()
