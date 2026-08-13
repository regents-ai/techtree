"""The append-only run event log and its vocabulary. Spec sections 18.1, 7.4.

One run event is one line of canonical JSON. The log is only ever appended to,
never rewritten, which is what lets a reader that arrives halfway through a run
reconstruct everything that has happened without coordinating with the writer.

Three properties are deliberate.

*Canonical bytes.* Lines are serialized with
:func:`techtree.canonical.canonical_json_bytes`, so the same events always
produce the same file and :func:`event_digest` is a meaningful identity for a
run's history rather than an accident of dictionary ordering.

*Durability.* Each append is a single write to a file opened with ``O_APPEND``
followed by an ``fsync``. A crash can therefore lose a whole trailing event, but
it cannot interleave one event's bytes with another's.

*Discontinuity is fatal.* Sequence numbers start at zero and increase by exactly
one. A log that skips is a log that lost something, and a state projected from
it would be quietly wrong; :func:`read_events` refuses it instead. That check is
also what catches a truncated final line, because a partly written event fails
to parse before its sequence is ever considered.

The kinds a run may record are a closed set. ``RunEvent.kind`` is a string in
the frozen protocol model, but nine names exhaust what a local run can say about
itself, and each name fixes the phases it may appear between and the details it
carries. :func:`validate_event_kind` holds every reader to that, so a log cannot
contain an event whose name and position disagree.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import canonical_json_bytes, sha256_digest_bytes
from techtree.errors import NotFoundError, ValidationError
from techtree.fs import fsync_directory
from techtree.models.base import Digest, JsonValue
from techtree.models.run import RunEvent, RunPhase

__all__ = [
    "CANCEL_REQUESTED",
    "DETAIL_CURRENT",
    "DETAIL_ERROR",
    "DETAIL_LABEL",
    "DETAIL_REQUESTED_BY",
    "DETAIL_REQUEST_DIGEST",
    "DETAIL_RESULT_DIGEST",
    "DETAIL_TOTAL",
    "DETAIL_WORKER_PID",
    "EVENT_KINDS",
    "PHASE_ENTERED",
    "PROGRESS_UPDATED",
    "RESULT_WRITTEN",
    "RUN_CANCELLED",
    "RUN_COMPLETED",
    "RUN_CREATED",
    "RUN_FAILED",
    "SAME_PHASE_EVENT_KINDS",
    "WORKER_STARTED",
    "append_event",
    "event_digest",
    "next_sequence",
    "read_events",
    "validate_event_kind",
]

_LINE_SEPARATOR: Final = b"\n"
#: Owner read and write only, matching every other file Techtree writes.
_FILE_MODE: Final = 0o600


# ---------------------------------------------------------------------------
# Event kinds
#
# Nine names, and no tenth. A kind is not a free-text annotation: it fixes what
# the event means, which phases it may sit between, and which details it must
# carry, so a reader can interpret an event without guessing.
# ---------------------------------------------------------------------------

#: The run exists and its request is fixed. Always sequence zero.
RUN_CREATED: Final = "run.created"
#: A detached worker took the run on and announced its process id.
WORKER_STARTED: Final = "worker.started"
#: The run moved from one phase to another.
PHASE_ENTERED: Final = "phase.entered"
#: How far through the current phase the worker is.
PROGRESS_UPDATED: Final = "progress.updated"
#: Someone asked the run to stop.
CANCEL_REQUESTED: Final = "cancel.requested"
#: The run stopped because something went wrong.
RUN_FAILED: Final = "run.failed"
#: The run stopped because it was asked to.
RUN_CANCELLED: Final = "run.cancelled"
#: The report was persisted and its digest recorded.
RESULT_WRITTEN: Final = "result.written"
#: The run finished the normal path.
RUN_COMPLETED: Final = "run.completed"

#: Every kind a run may record. Anything else is a corrupt log.
EVENT_KINDS: Final[frozenset[str]] = frozenset(
    {
        RUN_CREATED,
        WORKER_STARTED,
        PHASE_ENTERED,
        PROGRESS_UPDATED,
        CANCEL_REQUESTED,
        RUN_FAILED,
        RUN_CANCELLED,
        RESULT_WRITTEN,
        RUN_COMPLETED,
    }
)

#: The three kinds that report something true of a run without moving it on.
#: Every other kind changes the phase. Spec section 7.6.
SAME_PHASE_EVENT_KINDS: Final[frozenset[str]] = frozenset(
    {WORKER_STARTED, PROGRESS_UPDATED, RESULT_WRITTEN}
)


# ---------------------------------------------------------------------------
# Detail keys
#
# ``RunEvent.details`` is free-form JSON so that a worker can record whatever a
# human will want to read later. These keys are the exception: each is part of
# the definition of the kind that carries it, and the projection interprets it.
# ---------------------------------------------------------------------------

#: The digest of the ``RunRequest`` this run executes.
DETAIL_REQUEST_DIGEST: Final = "request_digest"
#: The process id of the detached worker executing this run.
DETAIL_WORKER_PID: Final = "worker_pid"
#: Position within the work the current phase describes.
DETAIL_CURRENT: Final = "current"
#: How much work the current phase amounts to.
DETAIL_TOTAL: Final = "total"
#: What the current phase is working through.
DETAIL_LABEL: Final = "label"
#: Who asked the run to stop.
DETAIL_REQUESTED_BY: Final = "requested_by"
#: A ``CliError`` object saying why the run failed.
DETAIL_ERROR: Final = "error"
#: The digest of the ``UpliftReport`` this run produced.
DETAIL_RESULT_DIGEST: Final = "result_digest"

#: What each kind is defined to carry. A kind missing one of its own details
#: cannot be interpreted, so it is refused rather than projected as a blank.
_REQUIRED_DETAILS: Final[dict[str, tuple[str, ...]]] = {
    RUN_CREATED: (DETAIL_REQUEST_DIGEST,),
    WORKER_STARTED: (DETAIL_WORKER_PID,),
    PROGRESS_UPDATED: (DETAIL_CURRENT, DETAIL_TOTAL, DETAIL_LABEL),
    CANCEL_REQUESTED: (DETAIL_REQUESTED_BY,),
    RUN_FAILED: (DETAIL_ERROR,),
    RESULT_WRITTEN: (DETAIL_RESULT_DIGEST,),
    RUN_COMPLETED: (DETAIL_RESULT_DIGEST,),
}


# ---------------------------------------------------------------------------
# Kind and phase agreement
# ---------------------------------------------------------------------------

#: Four phases each belong to exactly one kind, in both directions: no other
#: kind may enter the phase, and the kind may enter no other phase. Ending a run
#: is too consequential to be recorded by a generic phase change.
_EXCLUSIVE_PHASE_KINDS: Final[dict[RunPhase, str]] = {
    RunPhase.CANCEL_REQUESTED: CANCEL_REQUESTED,
    RunPhase.FAILED: RUN_FAILED,
    RunPhase.CANCELLED: RUN_CANCELLED,
    RunPhase.COMPLETED: RUN_COMPLETED,
}

#: The one phase each of these kinds may appear in. A worker announces itself
#: before the run starts working; a result exists only while the report is
#: being built.
_ONLY_IN_PHASE: Final[dict[str, RunPhase]] = {
    WORKER_STARTED: RunPhase.CREATED,
    RESULT_WRITTEN: RunPhase.BUILDING_REPORT,
}

#: The phase each of these kinds must have been reached from. Both are the last
#: step of a path, and the step before it is not optional.
_REQUIRED_PREVIOUS_PHASE: Final[dict[str, RunPhase]] = {
    RUN_CANCELLED: RunPhase.CANCEL_REQUESTED,
    RUN_COMPLETED: RunPhase.BUILDING_REPORT,
}


def validate_event_kind(event: RunEvent) -> None:
    """Reject unknown kinds, kind and phase mismatches, and missing details."""
    if event.kind not in EVENT_KINDS:
        known: list[JsonValue] = [kind for kind in sorted(EVENT_KINDS)]
        raise ValidationError(
            f"{event.kind!r} is not a run event kind",
            code="run_event_kind_invalid",
            details={
                "run_id": event.run_id,
                "sequence": event.sequence,
                "kind": event.kind,
                "known": known,
            },
        )

    _check_phases(event)
    _check_required_details(event)


def _check_phases(event: RunEvent) -> None:
    """Refuse an event whose kind and phases describe different things."""
    if event.kind == RUN_CREATED:
        _check_created_event(event)
    elif event.previous_phase is None:
        raise _kind_mismatch(
            event,
            f"only {RUN_CREATED} comes from no earlier phase",
        )

    for phase, kind in _EXCLUSIVE_PHASE_KINDS.items():
        if event.phase is phase and event.kind != kind:
            raise _kind_mismatch(event, f"only {kind} enters {phase.value}")
        if event.kind == kind and event.phase is not phase:
            raise _kind_mismatch(event, f"{kind} enters {phase.value}")

    required_phase = _ONLY_IN_PHASE.get(event.kind)
    if required_phase is not None and event.phase is not required_phase:
        raise _kind_mismatch(
            event,
            f"{event.kind} belongs to {required_phase.value}, "
            f"not to {event.phase.value}",
        )

    required_previous = _REQUIRED_PREVIOUS_PHASE.get(event.kind)
    if required_previous is not None and event.previous_phase is not required_previous:
        raise _kind_mismatch(
            event,
            f"{event.kind} follows {required_previous.value}",
        )

    # The same-phase kinds report something true of a run while it stays where
    # it is; every other kind exists to move it. Neither may pretend to be the
    # other, so the two are checked as one equivalence.
    same_phase = event.phase is event.previous_phase
    if same_phase and event.kind not in SAME_PHASE_EVENT_KINDS:
        raise _kind_mismatch(
            event,
            f"{event.kind} moves a run on, but this one stays in {event.phase.value}",
        )
    if not same_phase and event.kind in SAME_PHASE_EVENT_KINDS:
        raise _kind_mismatch(
            event,
            f"{event.kind} does not move a run out of {event.phase.value}",
        )


def _check_created_event(event: RunEvent) -> None:
    """Refuse a created event anywhere but at the opening of a log."""
    if event.sequence != 0:
        raise _kind_mismatch(
            event,
            f"{RUN_CREATED} opens a log at sequence 0, not {event.sequence}",
        )
    if event.previous_phase is not None:
        raise _kind_mismatch(
            event,
            "a run's first event comes from no earlier phase, but this one "
            f"claims to leave {event.previous_phase.value}",
        )
    if event.phase is not RunPhase.CREATED:
        raise _kind_mismatch(
            event,
            f"{RUN_CREATED} opens a run in {RunPhase.CREATED.value}",
        )


def _check_required_details(event: RunEvent) -> None:
    """Refuse an event that omits a detail its kind is defined to carry."""
    for key in _REQUIRED_DETAILS.get(event.kind, ()):
        if key not in event.details:
            raise _kind_mismatch(
                event,
                f"a {event.kind} event carries details.{key}",
            )


def _kind_mismatch(event: RunEvent, reason: str) -> ValidationError:
    """Return the one failure every kind and phase disagreement raises."""
    previous = None if event.previous_phase is None else event.previous_phase.value
    return ValidationError(
        reason,
        code="run_event_kind_invalid",
        details={
            "run_id": event.run_id,
            "sequence": event.sequence,
            "kind": event.kind,
            "phase": event.phase.value,
            "event_previous_phase": previous,
        },
    )


# ---------------------------------------------------------------------------
# Bytes
# ---------------------------------------------------------------------------


def append_event(path: Path, event: RunEvent) -> None:
    """Append compact JSONL and fsync."""
    line = canonical_json_bytes(event) + _LINE_SEPARATOR

    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    descriptor = os.open(path, flags, _FILE_MODE)
    try:
        written = 0
        while written < len(line):
            written += os.write(descriptor, line[written:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)

    # The first append also creates the directory entry, and a durable file
    # whose name is not durable is not much use after a crash.
    fsync_directory(path.parent)


def read_events(path: Path) -> list[RunEvent]:
    """Read events and reject sequence discontinuity."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError as error:
        raise NotFoundError(
            f"no run event log at {path}",
            details={"path": str(path)},
        ) from error

    lines = raw.split(_LINE_SEPARATOR)
    # A well-formed log ends with a separator, which leaves one empty trailing
    # element. Any other empty line is damage.
    if lines and lines[-1] == b"":
        lines.pop()

    events: list[RunEvent] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            raise ValidationError(
                f"run event log line {number} is empty: {path}",
                code="run_event_log_corrupt",
                details={"path": str(path), "line": number},
            )
        try:
            event = RunEvent.model_validate_json(line)
        except PydanticValidationError as error:
            raise ValidationError(
                f"run event log line {number} is not a run event: {path} "
                f"({error.errors()[0]['msg']})",
                code="run_event_log_corrupt",
                details={"path": str(path), "line": number},
            ) from error

        expected = len(events)
        if event.sequence != expected:
            raise ValidationError(
                f"run event log skips from sequence {expected - 1} to "
                f"{event.sequence}: {path}",
                code="run_event_sequence_invalid",
                details={
                    "path": str(path),
                    "line": number,
                    "expected_sequence": expected,
                    "sequence": event.sequence,
                },
            )
        events.append(event)

    return events


def next_sequence(events: list[RunEvent]) -> int:
    """Return next sequence number."""
    if not events:
        return 0
    return events[-1].sequence + 1


def event_digest(path: Path) -> Digest:
    """Digest exact event-log bytes."""
    try:
        return sha256_digest_bytes(path.read_bytes())
    except FileNotFoundError as error:
        raise NotFoundError(
            f"no run event log at {path}",
            details={"path": str(path)},
        ) from error
