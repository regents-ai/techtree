"""What the plugin remembers between tool calls. Specification section 7.9.

Almost nothing, on purpose. The scientific truth of a comparison lives in
Techtree's own artifacts; what the plugin keeps is a handful of identifiers so
that a later turn in the same conversation knows which run is being talked
about.

So this holds identifiers, digests, labels, and local proof paths — never a
key, never a used confirmation token, never Skill text, never Episode data,
never hidden task content.

It is held in memory for the life of the Hermes session. Hermes 0.20.0 gives
plugins no profile-scoped store, and the reasoning that settled installation
offers settles this too: a conversation's working state is the conversation's.
Nothing is lost by that, because every identifier here also exists in Techtree,
and :func:`reconcile_session_with_cli` rebuilds the stage from the run itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from .constants import DEMO_SESSION_TTL_SECONDS
from .errors import PluginError, PluginStateError
from .models import DemoSessionState, DemoStage

#: Phases the CLI reports that mean a run is over, and how it ended.
_TERMINAL_PHASES = {
    "completed": DemoStage.FIRST_RESULT_READY,
    "failed": DemoStage.FAILED,
    "cancelled": DemoStage.CANCELLED,
}


@dataclass
class SessionStore:
    """The demo sessions this Hermes session knows about."""

    _sessions: dict[str, DemoSessionState] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)

    def save(self, session: DemoSessionState) -> None:
        """Record a session, keeping the order they were last touched in."""
        if session.demo_id in self._sessions:
            self._order.remove(session.demo_id)
        self._sessions[session.demo_id] = session
        self._order.append(session.demo_id)

    def get(self, demo_id: str) -> DemoSessionState | None:
        """Return one session by identifier."""
        return self._sessions.get(demo_id)

    def all(self) -> dict[str, DemoSessionState]:
        """Return every session, oldest touch first."""
        return {demo_id: self._sessions[demo_id] for demo_id in self._order}

    def latest(self) -> DemoSessionState | None:
        """Return the most recently touched session, deterministically."""
        return self._sessions[self._order[-1]] if self._order else None

    def discard(self, demo_id: str) -> None:
        """Forget one session."""
        if self._sessions.pop(demo_id, None) is not None:
            self._order.remove(demo_id)

    def prune_expired(self, now: datetime | None = None) -> int:
        """Drop sessions nobody has touched for a long time."""
        moment = now or datetime.now(UTC)
        cutoff = moment - timedelta(seconds=DEMO_SESSION_TTL_SECONDS)
        stale = [
            demo_id
            for demo_id, session in self._sessions.items()
            if _updated_at(session) < cutoff
        ]
        for demo_id in stale:
            self.discard(demo_id)
        return len(stale)


def load_sessions(services: Any) -> dict[str, DemoSessionState]:
    """Return every demo session this Hermes session knows about."""
    store: SessionStore = services.sessions
    return store.all()


def save_session(services: Any, session: DemoSessionState) -> None:
    """Record a demo session."""
    services.sessions.save(session)


def latest_session(services: Any) -> DemoSessionState | None:
    """Return the session a bare "how is it going?" refers to."""
    store: SessionStore = services.sessions
    return store.latest()


def active_run_ids(services: Any) -> list[str]:
    """Return the run identifiers this session started and has not finished."""
    running = {
        DemoStage.FIRST_RUN_ACTIVE: "first_run_id",
        DemoStage.SECOND_RUN_ACTIVE: "second_run_id",
    }
    found: list[str] = []
    for session in load_sessions(services).values():
        attribute = running.get(session.stage)
        if attribute is None:
            continue
        run_id = getattr(session, attribute)
        if isinstance(run_id, str) and run_id:
            found.append(run_id)
    return found


def prune_expired_plans(services: Any, now: datetime | None = None) -> int:
    """Drop installation offers that have run out."""
    count: int = services.plans.prune_expired(now)
    return count


def prune_expired_sessions(services: Any, now: datetime | None = None) -> int:
    """Drop demo sessions nobody has touched in a long time."""
    count: int = services.sessions.prune_expired(now)
    return count


def reconcile_session_with_cli(
    services: Any, session: DemoSessionState
) -> DemoSessionState:
    """Advance convenience state from what Techtree says about the run.

    Only Techtree can move a run to finished. This reads one bounded status
    and believes it: a run counts as complete when the CLI reports a terminal
    phase, the completed phase specifically, and a result that exists. Nothing
    short of that is allowed to look like a finished comparison, because a
    conversation that believes a run finished will go looking for a result
    that is not there.
    """
    run_id = _active_run_id(session)
    if run_id is None:
        return session

    try:
        envelope = services.bridge.invoke(["run", "status", run_id])
    except PluginError:
        return session

    data = envelope.get("data")
    if not isinstance(data, dict) or not envelope.get("ok"):
        return session

    phase = data.get("phase")
    if not data.get("terminal") or not isinstance(phase, str):
        return session

    stage = _TERMINAL_PHASES.get(phase)
    if stage is None:
        return session
    if stage is DemoStage.FIRST_RESULT_READY and not data.get("result_available"):
        return session
    if stage is DemoStage.FIRST_RESULT_READY and session.second_run_id == run_id:
        stage = DemoStage.COMPLETE

    return _touch(session, stage=stage)


def read_session_document(document: Any) -> DemoSessionState:
    """Rebuild a session from stored data, refusing anything malformed.

    Malformed state is reported rather than repaired, and the caller is
    expected to keep the original for debugging instead of deleting it.
    """
    if not isinstance(document, dict):
        raise PluginStateError("stored plugin state is not a session")
    try:
        stage = DemoStage(document["stage"])
        return DemoSessionState(
            demo_id=str(document["demo_id"]),
            release_core_digest=str(document["release_core_digest"]),
            climb_reference=str(document["climb_reference"]),
            stage=stage,
            first_draft_id=document.get("first_draft_id"),
            first_run_id=document.get("first_run_id"),
            first_proof_path=document.get("first_proof_path"),
            source_skill_v1_digest=document.get("source_skill_v1_digest"),
            proposal_id=document.get("proposal_id"),
            second_draft_id=document.get("second_draft_id"),
            second_run_id=document.get("second_run_id"),
            second_proof_path=document.get("second_proof_path"),
            revision_attempts=int(document.get("revision_attempts", 0)),
            updated_at=str(document["updated_at"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise PluginStateError(
            f"stored plugin state could not be read: {error}"
        ) from error


def session_payload(session: DemoSessionState) -> dict[str, Any]:
    """Return a session in the shape a tool result carries it."""
    return {
        "demo_id": session.demo_id,
        "stage": session.stage.value,
        "climb_reference": session.climb_reference,
        "first_draft_id": session.first_draft_id,
        "first_run_id": session.first_run_id,
        "first_proof_path": session.first_proof_path,
        "source_skill_v1_digest": session.source_skill_v1_digest,
        "second_draft_id": session.second_draft_id,
        "second_run_id": session.second_run_id,
        "second_proof_path": session.second_proof_path,
        "revision_attempts": session.revision_attempts,
        "updated_at": session.updated_at,
    }


def _active_run_id(session: DemoSessionState) -> str | None:
    if session.stage is DemoStage.FIRST_RUN_ACTIVE:
        return session.first_run_id
    if session.stage is DemoStage.SECOND_RUN_ACTIVE:
        return session.second_run_id
    return None


def _touch(session: DemoSessionState, **changes: Any) -> DemoSessionState:
    from dataclasses import replace

    return replace(session, updated_at=datetime.now(UTC).isoformat(), **changes)


def _updated_at(session: DemoSessionState) -> datetime:
    try:
        return datetime.fromisoformat(session.updated_at)
    except ValueError:
        return datetime.now(UTC)
