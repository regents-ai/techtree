"""The run state machine and its projection. Spec sections 18.2, 7.6.

Everything in this module is a pure function of the event log. Nothing here
touches the filesystem, the clock, or the process table, which is what makes
"the state rebuilds from the events alone" a property that can be tested rather
than a claim.

The normal path is a straight line::

    created → validating_taskset → running_baseline → running_candidate
    → building_receipts → verifying_comparison → building_report → completed

``running_variants`` is the one branch off it: a run whose two variants execute
side by side leaves ``validating_taskset`` for it instead of for
``running_baseline``, and rejoins the line at ``building_receipts``. The
sequential pair stays for the fake executor.

Two escapes leave it. Any phase that is still working may fail, and any phase
that is still working may have cancellation requested of it; a run that has been
asked to stop then reaches ``cancelled`` when the worker winds down, or
``failed`` if it breaks while doing so. ``completed``, ``failed``, and
``cancelled`` have no outgoing edges at all: once a run has ended, its log is
closed.

No phase has an edge to itself. A run does still have things to report while it
stays where it is — the worker's process id, its progress through a phase, the
digest of the report it just wrote, and how each variant of a concurrent
comparison is getting on — but those are a closed set of events, named
in :data:`techtree.runs.events.SAME_PHASE_EVENT_KINDS`, and
:func:`validate_same_phase_event` rather than the transition table is what
admits them. Recording them as events is what keeps the projection derivable
from the log; recording them anywhere else would make ``state.json`` hold facts
the log cannot rebuild.

Twelve phases is more vocabulary than anything outside Techtree should have to
learn, so :func:`public_state` projects them onto the five public states the
v0.2 machine contract speaks in. It is a projection and not a replacement: no
phase is retired, the log is unchanged, and the detailed phase remains the
answer to "what is this run doing".

One fact deliberately does not come from events: ``heartbeat_at``. A liveness
signal refreshed every couple of seconds would bury a run's actual history under
thousands of lines that mean nothing after the fact, so the heartbeat is a
single overwritten file and :func:`reduce_events` always leaves the field unset.
:class:`techtree.runs.store.RunStore` merges it in.
"""

from __future__ import annotations

from typing import Final

from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import validate_digest
from techtree.errors import RunError, ValidationError
from techtree.models.base import Digest, JsonValue
from techtree.models.cli import CliError
from techtree.models.run import (
    PublicRunState,
    RunEvent,
    RunPhase,
    RunProgress,
    RunState,
    VariantProgress,
)
from techtree.runs.events import (
    CANCEL_REQUESTED,
    DETAIL_COMPLETED,
    DETAIL_CURRENT,
    DETAIL_ERROR,
    DETAIL_ERRORED,
    DETAIL_LABEL,
    DETAIL_RESULT_DIGEST,
    DETAIL_RUNNING,
    DETAIL_STATE,
    DETAIL_TOTAL,
    DETAIL_VARIANT,
    DETAIL_WORKER_PID,
    PROGRESS_UPDATED,
    RESULT_WRITTEN,
    RUN_COMPLETED,
    RUN_CREATED,
    RUN_FAILED,
    SAME_PHASE_EVENT_KINDS,
    VARIANT_EVENT_KINDS,
    WORKER_STARTED,
    validate_event_kind,
)

__all__ = [
    "ALLOWED_TRANSITIONS",
    "NORMAL_PATH",
    "PUBLIC_STATE_BY_PHASE",
    "apply_event",
    "can_cancel",
    "initial_state",
    "is_terminal",
    "phase_progress_allowed",
    "public_state",
    "reduce_events",
    "validate_same_phase_event",
    "validate_transition",
]


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

#: The concurrent alternative to ``running_baseline → running_candidate``, as
#: the phase it leaves, the phase it is, and the phase it rejoins at. Spec
#: section 3.3 adds it beside the sequential pair rather than in place of it, so
#: ``validating_taskset`` has two successors and both routes meet again at
#: ``building_receipts``.
_VARIANT_BRANCH: Final[tuple[RunPhase, RunPhase, RunPhase]] = (
    RunPhase.VALIDATING_TASKSET,
    RunPhase.RUNNING_VARIANTS,
    RunPhase.BUILDING_RECEIPTS,
)


def _build_allowed_transitions() -> dict[RunPhase, frozenset[RunPhase]]:
    """Derive the transition table from the normal path and the two escapes."""
    allowed: dict[RunPhase, frozenset[RunPhase]] = {}

    working = [phase for phase in NORMAL_PATH if phase not in _TERMINAL_PHASES]
    for position, phase in enumerate(working):
        allowed[phase] = frozenset(
            {
                NORMAL_PATH[position + 1],
                RunPhase.FAILED,
                RunPhase.CANCEL_REQUESTED,
            }
        )

    entered_from, branch, rejoins_at = _VARIANT_BRANCH
    allowed[entered_from] = allowed[entered_from] | {branch}
    allowed[branch] = frozenset(
        {rejoins_at, RunPhase.FAILED, RunPhase.CANCEL_REQUESTED}
    )

    allowed[RunPhase.CANCEL_REQUESTED] = frozenset(
        {
            RunPhase.CANCELLED,
            RunPhase.FAILED,
        }
    )

    for phase in _TERMINAL_PHASES:
        allowed[phase] = frozenset()

    return allowed


#: Every phase a run may move to from each phase it can be in. A phase mapped to
#: the empty set is terminal. No phase maps to itself: an event that leaves the
#: run where it is passes :func:`validate_same_phase_event` instead.
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
            code="run_transition_invalid",
            details={"phase": current.value, "target_phase": target.value},
        )

    if current is target:
        raise RunError(
            f"a run in {current.value} does not move to itself; only "
            f"{_named(SAME_PHASE_EVENT_KINDS)} report without leaving a phase",
            code="run_transition_invalid",
            details={"phase": current.value, "target_phase": target.value},
        )

    allowed: list[JsonValue] = [
        phase.value for phase in sorted(ALLOWED_TRANSITIONS[current])
    ]
    raise RunError(
        f"a run in {current.value} cannot move to {target.value}",
        code="run_transition_invalid",
        details={
            "phase": current.value,
            "target_phase": target.value,
            "allowed": allowed,
        },
    )


def validate_same_phase_event(state: RunState, event: RunEvent) -> None:
    """Raise unless this event may leave the run in the phase it is in."""
    if is_terminal(state.phase):
        raise RunError(
            f"run has already ended in {state.phase.value}; it records no "
            "further events",
            code="run_transition_invalid",
            details={"run_id": state.run_id, "phase": state.phase.value},
        )
    if event.kind not in SAME_PHASE_EVENT_KINDS:
        raise RunError(
            f"a run records nothing without leaving {state.phase.value} except "
            f"{_named(SAME_PHASE_EVENT_KINDS)}",
            code="run_transition_invalid",
            details={
                "run_id": state.run_id,
                "phase": state.phase.value,
                "kind": event.kind,
            },
        )
    if event.kind == PROGRESS_UPDATED and not phase_progress_allowed(state.phase):
        raise RunError(
            f"a run in {state.phase.value} has no progress to report",
            code="run_transition_invalid",
            details={"run_id": state.run_id, "phase": state.phase.value},
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
    return RunPhase.CANCEL_REQUESTED in ALLOWED_TRANSITIONS[phase]


def phase_progress_allowed(phase: RunPhase) -> bool:
    """Return whether a phase measures work a run can be part-way through.

    A run that has ended is not part-way through anything, and ``created`` is a
    run that exists rather than a run doing something.
    """
    return not is_terminal(phase) and phase is not RunPhase.CREATED


def _named(kinds: frozenset[str]) -> str:
    """Return a list of event kinds as English, for a message a human reads."""
    return ", ".join(sorted(kinds))


# ---------------------------------------------------------------------------
# The public projection
# ---------------------------------------------------------------------------


#: What each phase is called outside Techtree. One row per phase, written out
#: rather than derived from a rule.
#:
#: A rule would answer for a phase nobody had thought about, and the answer it
#: happened to give would be the difference between telling a caller a run is
#: still going and telling them it has stopped. Written out, a phase added
#: without an answer here fails the build instead.
#:
#: ``docs/v0.2/MACHINE_CONTRACT.md`` carries the same table, and
#: ``tests/contract/test_v02_machine_contract.py`` holds the two to each other.
PUBLIC_STATE_BY_PHASE: Final[dict[RunPhase, PublicRunState]] = {
    RunPhase.CREATED: PublicRunState.PREPARED,
    RunPhase.VALIDATING_TASKSET: PublicRunState.RUNNING,
    RunPhase.RUNNING_BASELINE: PublicRunState.RUNNING,
    RunPhase.RUNNING_CANDIDATE: PublicRunState.RUNNING,
    RunPhase.RUNNING_VARIANTS: PublicRunState.RUNNING,
    RunPhase.BUILDING_RECEIPTS: PublicRunState.RUNNING,
    RunPhase.VERIFYING_COMPARISON: PublicRunState.RUNNING,
    RunPhase.BUILDING_REPORT: PublicRunState.RUNNING,
    RunPhase.CANCEL_REQUESTED: PublicRunState.RUNNING,
    RunPhase.COMPLETED: PublicRunState.COMPLETED,
    RunPhase.FAILED: PublicRunState.FAILED,
    RunPhase.CANCELLED: PublicRunState.CANCELLED,
}


def public_state(phase: RunPhase) -> PublicRunState:
    """Return the public state a phase projects onto.

    ``cancel_requested`` projects to ``running``, not to ``cancelled``.
    Cancellation is cooperative and takes effect at a phase boundary: a run
    that has been asked to stop has not stopped, may still be working, and may
    still end in ``failed``. Calling it ``cancelled`` would report an outcome
    that has not happened. That the request was made is a fact the run carries
    — the moment it was first made — rather than a state.
    """
    return PUBLIC_STATE_BY_PHASE[phase]


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------


def reduce_events(events: list[RunEvent]) -> RunState:
    """Project complete state."""
    if not events:
        raise ValidationError(
            "a run event log cannot be empty; every run opens with its created event",
            code="run_event_log_corrupt",
        )

    state = initial_state(events[0])
    for event in events[1:]:
        state = apply_event(state, event)
    return state


def initial_state(created_event: RunEvent) -> RunState:
    """Project the event every run opens with."""
    if created_event.kind != RUN_CREATED:
        raise ValidationError(
            f"a run event log opens with {RUN_CREATED}, not {created_event.kind}",
            code="run_event_kind_invalid",
            details={"run_id": created_event.run_id, "kind": created_event.kind},
        )
    validate_event_kind(created_event)
    return _project(_opening_state(created_event), created_event)


def apply_event(state: RunState, event: RunEvent) -> RunState:
    """Apply one event."""
    if event.run_id != state.run_id:
        raise ValidationError(
            f"run event belongs to {event.run_id}, not to {state.run_id}",
            code="run_event_log_corrupt",
            details={"run_id": state.run_id, "event_run_id": event.run_id},
        )
    if event.sequence != state.sequence + 1:
        raise ValidationError(
            f"run event {event.sequence} does not follow {state.sequence}",
            code="run_event_sequence_invalid",
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
            code="run_event_log_corrupt",
            details={
                "run_id": state.run_id,
                "phase": state.phase.value,
                "event_previous_phase": recorded,
            },
        )

    validate_event_kind(event)
    if event.phase is state.phase:
        validate_same_phase_event(state, event)
    else:
        validate_transition(state.phase, event.phase)
    return _project(state, event)


def _project(previous: RunState, event: RunEvent) -> RunState:
    """Return the state that results from applying one validated event.

    Which fields an event touches follows from its kind, which is why the kind
    is a closed set: a reader never has to guess whether a detail was meant to
    be interpreted.
    """
    worker_pid = _worker_pid(event) if event.kind == WORKER_STARTED else None
    progress = _progress(event) if event.kind == PROGRESS_UPDATED else None
    carries_result = event.kind in (RESULT_WRITTEN, RUN_COMPLETED)
    entered_new_phase = previous.phase is not event.phase

    # Variant progress belongs to the phase that reported it, exactly as
    # ``progress`` does, so entering a new phase discards it. Each variant keeps
    # its own entry, replaced whole by the most recent event that named it.
    variant_progress = {} if entered_new_phase else dict(previous.variant_progress)
    if event.kind in VARIANT_EVENT_KINDS:
        reported = _variant_progress(event)
        variant_progress[reported.variant] = reported

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
        cancel_requested_at=(
            event.timestamp
            if event.kind == CANCEL_REQUESTED
            else previous.cancel_requested_at
        ),
        error=(_error(event) if event.kind == RUN_FAILED else previous.error),
        # Progress measures a position inside one phase, so entering a new phase
        # discards it.
        progress=(
            progress
            if progress is not None
            else (None if entered_new_phase else previous.progress)
        ),
        variant_progress=variant_progress,
        result_digest=(
            _result_digest(event) if carries_result else previous.result_digest
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
        variant_progress={},
        result_digest=None,
    )


def _worker_pid(event: RunEvent) -> int:
    """Return the worker process id this event announces."""
    raw = event.details[DETAIL_WORKER_PID]
    if not isinstance(raw, int) or isinstance(raw, bool) or raw <= 0:
        raise _detail_invalid(event, f"{DETAIL_WORKER_PID} must be a positive integer")
    return raw


def _progress(event: RunEvent) -> RunProgress:
    """Return the progress this event reports."""
    try:
        return RunProgress.model_validate(
            {
                "current": event.details[DETAIL_CURRENT],
                "total": event.details[DETAIL_TOTAL],
                "label": event.details[DETAIL_LABEL],
            }
        )
    except PydanticValidationError as error:
        raise _detail_invalid(
            event,
            f"progress is not valid ({error.errors()[0]['msg']})",
        ) from error


def _variant_progress(event: RunEvent) -> VariantProgress:
    """Return the one variant's position this event reports."""
    try:
        return VariantProgress.model_validate(
            {
                "variant": event.details[DETAIL_VARIANT],
                "completed": event.details[DETAIL_COMPLETED],
                "total": event.details[DETAIL_TOTAL],
                "running": event.details[DETAIL_RUNNING],
                "errored": event.details[DETAIL_ERRORED],
                "state": event.details[DETAIL_STATE],
            }
        )
    except PydanticValidationError as error:
        raise _detail_invalid(
            event,
            f"variant progress is not valid ({error.errors()[0]['msg']})",
        ) from error


def _result_digest(event: RunEvent) -> Digest:
    """Return the report digest this event records."""
    raw = event.details[DETAIL_RESULT_DIGEST]
    if not isinstance(raw, str):
        raise _detail_invalid(event, f"{DETAIL_RESULT_DIGEST} must be a digest string")
    try:
        return validate_digest(raw)
    except ValidationError as error:
        raise _detail_invalid(
            event, f"{DETAIL_RESULT_DIGEST} is not a digest"
        ) from error


def _error(event: RunEvent) -> CliError:
    """Return the failure this event carries.

    A run that failed without saying why leaves the caller nothing to act on, so
    the error is part of the transition rather than an optional annotation.
    """
    try:
        return CliError.model_validate(event.details[DETAIL_ERROR])
    except PydanticValidationError as error:
        raise _detail_invalid(
            event,
            f"{DETAIL_ERROR} is not a CLI error ({error.errors()[0]['msg']})",
        ) from error


def _detail_invalid(event: RunEvent, reason: str) -> ValidationError:
    """Return the failure a detail that its kind cannot interpret raises."""
    return ValidationError(
        f"run event {reason}",
        code="run_event_kind_invalid",
        details={
            "run_id": event.run_id,
            "sequence": event.sequence,
            "kind": event.kind,
        },
    )
