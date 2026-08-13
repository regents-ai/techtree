"""The run state machine and its projection. Spec section 18.2.

Everything in this module is a pure function of the event log. Nothing here
touches the filesystem, the clock, or the process table, which is what makes
"the state rebuilds from the events alone" a property that can be tested rather
than a claim.

The normal path is a straight line::

    created → validating_taskset → running_baseline → running_candidate
    → building_receipts → verifying_comparison → building_report → completed

Two escapes leave it. Any phase that is still working may fail, and any phase
that is still working may have cancellation requested of it; a run that has been
asked to stop then reaches ``cancelled`` when the worker winds down, or
``failed`` if it breaks while doing so. ``completed``, ``failed``, and
``cancelled`` have no outgoing edges at all: once a run has ended, its log is
closed.

Every non-terminal phase also permits an event that does not change the phase.
That is not a loop in the state machine so much as the recognition that a run
has things to report while it stays where it is — the worker's process id, its
progress through a phase, the digest of the report it just wrote. Recording
those as events is what keeps the projection derivable from the log; recording
them anywhere else would make ``state.json`` hold facts the log cannot rebuild.

One fact deliberately does not come from events: ``heartbeat_at``. A liveness
signal refreshed every couple of seconds would bury a run's actual history under
thousands of lines that mean nothing after the fact, so the heartbeat is a
single overwritten file and :func:`reduce_events` always leaves the field unset.
:class:`techtree.runs.store.RunStore` merges it in.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import validate_digest
from techtree.errors import RunError, ValidationError
from techtree.models.base import Digest, JsonValue
from techtree.models.cli import CliError
from techtree.models.run import RunEvent, RunPhase, RunProgress, RunState

__all__ = [
    "ALLOWED_TRANSITIONS",
    "DETAIL_ERROR",
    "DETAIL_PROGRESS",
    "DETAIL_RESULT_DIGEST",
    "DETAIL_WORKER_PID",
    "NORMAL_PATH",
    "apply_event",
    "can_cancel",
    "is_terminal",
    "reduce_events",
    "validate_transition",
]


# ---------------------------------------------------------------------------
# Event detail keys
#
# ``RunEvent.details`` is free-form JSON so that a worker can record whatever a
# human will want to read later. These four keys are the exception: the
# projection interprets them, so they are named here and nowhere else.
# ---------------------------------------------------------------------------

#: A ``CliError`` object. Required on every event entering ``failed``.
DETAIL_ERROR: Final = "error"
#: A ``RunProgress`` object describing position within the current phase.
DETAIL_PROGRESS: Final = "progress"
#: The digest of the ``UpliftReport`` this run produced.
DETAIL_RESULT_DIGEST: Final = "result_digest"
#: The process id of the detached worker executing this run.
DETAIL_WORKER_PID: Final = "worker_pid"


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------

#: The successful sequence, in order. Each phase's successor is the next entry.
NORMAL_PATH: Final[tuple[RunPhase, ...]] = (
    RunPhase.CREATED,
    RunPhase.VALIDATING_TASKSET,
    RunPhase.RUNNING_BASELINE,
    RunPhase.RUNNING_CANDIDATE,
    RunPhase.BUILDING_RECEIPTS,
    RunPhase.VERIFYING_COMPARISON,
    RunPhase.BUILDING_REPORT,
    RunPhase.COMPLETED,
)

_TERMINAL_PHASES: Final[frozenset[RunPhase]] = frozenset(
    {RunPhase.COMPLETED, RunPhase.FAILED, RunPhase.CANCELLED}
)


def _build_allowed_transitions() -> dict[RunPhase, frozenset[RunPhase]]:
    """Derive the transition table from the normal path and the two escapes."""
    allowed: dict[RunPhase, frozenset[RunPhase]] = {}

    working = [phase for phase in NORMAL_PATH if phase not in _TERMINAL_PHASES]
    for position, phase in enumerate(working):
        allowed[phase] = frozenset(
            {
                # An event that reports something without moving the run on.
                phase,
                NORMAL_PATH[position + 1],
                RunPhase.FAILED,
                RunPhase.CANCEL_REQUESTED,
            }
        )

    allowed[RunPhase.CANCEL_REQUESTED] = frozenset(
        {
            RunPhase.CANCEL_REQUESTED,
            RunPhase.CANCELLED,
            RunPhase.FAILED,
        }
    )

    for phase in _TERMINAL_PHASES:
        allowed[phase] = frozenset()

    return allowed


#: Every phase a run may move to from each phase it can be in. A phase mapped to
#: the empty set is terminal. A phase that includes itself accepts events that
#: report progress without advancing the run.
ALLOWED_TRANSITIONS: Final[dict[RunPhase, frozenset[RunPhase]]] = (
    _build_allowed_transitions()
)


def validate_transition(current: RunPhase, target: RunPhase) -> None:
    """Raise on invalid transition."""
    if target in ALLOWED_TRANSITIONS[current]:
        return

    if is_terminal(current):
        raise RunError(
            f"run has already ended in {current.value}; it records no further "
            f"events, so it cannot move to {target.value}",
            details={"phase": current.value, "target_phase": target.value},
        )

    allowed: list[JsonValue] = [
        phase.value for phase in sorted(ALLOWED_TRANSITIONS[current])
    ]
    raise RunError(
        f"a run in {current.value} cannot move to {target.value}",
        details={
            "phase": current.value,
            "target_phase": target.value,
            "allowed": allowed,
        },
    )


def is_terminal(phase: RunPhase) -> bool:
    """Return terminal state."""
    return not ALLOWED_TRANSITIONS[phase]


def can_cancel(phase: RunPhase) -> bool:
    """Return cancellation eligibility.

    A run that has ended cannot be stopped, and a run that has already been
    asked to stop is not asked twice — the second request would change nothing
    and the caller deserves to be told so rather than given a second receipt.
    """
    if phase is RunPhase.CANCEL_REQUESTED:
        return False
    return RunPhase.CANCEL_REQUESTED in ALLOWED_TRANSITIONS[phase]


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------


def reduce_events(events: list[RunEvent]) -> RunState:
    """Project complete state."""
    if not events:
        raise ValidationError(
            "a run event log cannot be empty; every run opens with its created event",
        )

    state = _project(None, events[0])
    for event in events[1:]:
        state = apply_event(state, event)
    return state


def apply_event(state: RunState, event: RunEvent) -> RunState:
    """Apply one event."""
    if event.run_id != state.run_id:
        raise ValidationError(
            f"run event belongs to {event.run_id}, not to {state.run_id}",
            details={"run_id": state.run_id, "event_run_id": event.run_id},
        )
    if event.sequence != state.sequence + 1:
        raise ValidationError(
            f"run event {event.sequence} does not follow {state.sequence}",
            details={
                "run_id": state.run_id,
                "sequence": event.sequence,
                "expected_sequence": state.sequence + 1,
            },
        )
    if event.previous_phase is not state.phase:
        recorded = None if event.previous_phase is None else event.previous_phase.value
        raise ValidationError(
            f"run event claims to leave {recorded}, but the run is in "
            f"{state.phase.value}",
            details={
                "run_id": state.run_id,
                "phase": state.phase.value,
                "event_previous_phase": recorded,
            },
        )

    validate_transition(state.phase, event.phase)
    return _project(state, event)


def _project(previous: RunState | None, event: RunEvent) -> RunState:
    """Return the state that results from applying one validated event.

    ``previous`` is ``None`` only for a run's created event, which has nothing
    behind it to carry forward.
    """
    if previous is None:
        _check_created_event(event)
        previous = _opening_state(event)

    worker_pid = _worker_pid(event)
    progress = _progress(event)
    result_digest = _result_digest(event)
    entered_new_phase = previous.phase is not event.phase

    return RunState(
        run_id=event.run_id,
        phase=event.phase,
        sequence=event.sequence,
        updated_at=event.timestamp,
        worker_pid=worker_pid if worker_pid is not None else previous.worker_pid,
        # The worker's start time is the moment it announced its process id.
        worker_started_at=(
            event.timestamp if worker_pid is not None else previous.worker_started_at
        ),
        # Liveness is not an event-sourced fact. See the module docstring.
        heartbeat_at=None,
        cancel_requested_at=_cancel_requested_at(previous, event),
        error=(
            _required_error(event) if event.phase is RunPhase.FAILED else previous.error
        ),
        # Progress measures a position inside one phase, so entering a new phase
        # discards it unless the event that moved the run supplies a new one.
        progress=(
            progress
            if progress is not None
            else (None if entered_new_phase else previous.progress)
        ),
        result_digest=(
            result_digest if result_digest is not None else previous.result_digest
        ),
    )


def _opening_state(event: RunEvent) -> RunState:
    """Return the empty state a run's created event is applied to.

    A run starts with nothing known about it. Spelling that as a state rather
    than as a special case in every field keeps the projection one shape.
    """
    return RunState(
        run_id=event.run_id,
        phase=RunPhase.CREATED,
        sequence=0,
        updated_at=event.timestamp,
        worker_pid=None,
        worker_started_at=None,
        heartbeat_at=None,
        cancel_requested_at=None,
        error=None,
        progress=None,
        result_digest=None,
    )


def _check_created_event(event: RunEvent) -> None:
    if event.sequence != 0:
        raise ValidationError(
            f"a run event log opens at sequence 0, not {event.sequence}",
            details={"sequence": event.sequence},
        )
    if event.phase is not RunPhase.CREATED:
        raise ValidationError(
            f"a run event log opens in {RunPhase.CREATED.value}, not "
            f"{event.phase.value}",
            details={"phase": event.phase.value},
        )
    if event.previous_phase is not None:
        raise ValidationError(
            "a run's first event comes from no earlier phase, but this one "
            f"claims to leave {event.previous_phase.value}",
            details={"event_previous_phase": event.previous_phase.value},
        )


def _cancel_requested_at(previous: RunState, event: RunEvent) -> datetime | None:
    """Return when cancellation was first asked for.

    The first request is the one that counts. A second cancel event, or the
    later move to ``cancelled``, does not move the timestamp.
    """
    if (
        event.phase is RunPhase.CANCEL_REQUESTED
        and previous.cancel_requested_at is None
    ):
        return event.timestamp
    return previous.cancel_requested_at


def _worker_pid(event: RunEvent) -> int | None:
    """Return the worker process id this event announces, if any."""
    raw = event.details.get(DETAIL_WORKER_PID)
    if raw is None:
        return None
    if not isinstance(raw, int) or isinstance(raw, bool) or raw <= 0:
        raise ValidationError(
            f"run event {DETAIL_WORKER_PID} must be a positive integer",
            details={"run_id": event.run_id, "sequence": event.sequence},
        )
    return raw


def _progress(event: RunEvent) -> RunProgress | None:
    """Return the progress this event reports, if any."""
    raw = event.details.get(DETAIL_PROGRESS)
    if raw is None:
        return None
    try:
        return RunProgress.model_validate(raw)
    except PydanticValidationError as error:
        raise ValidationError(
            f"run event {DETAIL_PROGRESS} is not run progress "
            f"({error.errors()[0]['msg']})",
            details={"run_id": event.run_id, "sequence": event.sequence},
        ) from error


def _result_digest(event: RunEvent) -> Digest | None:
    """Return the report digest this event records, if any."""
    raw = event.details.get(DETAIL_RESULT_DIGEST)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValidationError(
            f"run event {DETAIL_RESULT_DIGEST} must be a digest string",
            details={"run_id": event.run_id, "sequence": event.sequence},
        )
    return validate_digest(raw)


def _required_error(event: RunEvent) -> CliError:
    """Return the failure this event carries.

    A run that failed without saying why leaves the caller nothing to act on, so
    the error is part of the transition rather than an optional annotation.
    """
    raw: JsonValue | None = event.details.get(DETAIL_ERROR)
    if raw is None:
        raise ValidationError(
            f"a failed run event carries the failure in details.{DETAIL_ERROR}",
            details={"run_id": event.run_id, "sequence": event.sequence},
        )
    try:
        return CliError.model_validate(raw)
    except PydanticValidationError as error:
        raise ValidationError(
            f"run event {DETAIL_ERROR} is not a CLI error ({error.errors()[0]['msg']})",
            details={"run_id": event.run_id, "sequence": event.sequence},
        ) from error
