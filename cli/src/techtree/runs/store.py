"""Everything one run keeps on disk. Spec section 18.3.

A run directory holds three kinds of file and treats each differently.

*Written once.* ``request.json`` is what was asked for and ``report/uplift.json``
is what came back. Both are created with ``O_EXCL`` in canonical bytes, so a
second attempt is reported as a conflict rather than quietly replacing evidence,
and the file's digest is the object's digest.

*Appended to.* ``events.jsonl`` is the run's history and the only authority on
what has happened.

*Overwritten.* ``state.json`` is a projection of the log, ``heartbeat.json`` is
the worker's most recent sign of life, and ``pid`` names the process executing
the run. Each is replaced atomically, and none of them is ever the source of a
fact the log could not rebuild — except the heartbeat, which is deliberately not
event-sourced because a signal refreshed every two seconds would drown the
history it was appended to.

Every writer passes through ``runs/<run-id>/.lock``. The lock matters because
the writers are genuinely concurrent: a detached worker advances the run while
the CLI, in another process entirely, requests cancellation. Appending an event
and rewriting the projection happen inside one lock hold, so the two files can
never disagree about which event was last.

The projection is always recomputed from the log rather than patched in place.
It costs one small read and it means a stale or corrupted ``state.json`` heals
itself at the next append, heartbeat, or explicit rebuild instead of persisting
a wrong answer.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from filelock import FileLock, Timeout
from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import canonical_json_bytes, digest_object
from techtree.errors import ConflictError, NotFoundError, RunError, ValidationError
from techtree.fs import (
    atomic_write_json,
    atomic_write_text,
    ensure_private_directory,
    fsync_directory,
    open_exclusive,
    read_json,
)
from techtree.models.base import JsonValue
from techtree.models.run import RunEvent, RunPhase, RunRequest, RunState
from techtree.models.uplift_report import UpliftReport
from techtree.paths import TechtreePaths
from techtree.runs.events import (
    CANCEL_REQUESTED,
    DETAIL_REQUEST_DIGEST,
    DETAIL_REQUESTED_BY,
    DETAIL_RESULT_DIGEST,
    DETAIL_WORKER_PID,
    PHASE_ENTERED,
    RESULT_WRITTEN,
    RUN_CREATED,
    WORKER_STARTED,
    append_event,
    next_sequence,
    read_events,
)
from techtree.runs.machine import apply_event, is_terminal, reduce_events

__all__ = [
    "LOCK_TIMEOUT_SECONDS",
    "RunStore",
]

#: A lock hold is a few file operations, so waiting this long means the holder
#: died with the lock or something is badly wrong. Failing beats hanging.
LOCK_TIMEOUT_SECONDS: Final = 30.0

_LOCK_FILE_NAME: Final = ".lock"
_REQUEST_FILE_NAME: Final = "request.json"
_EVENTS_FILE_NAME: Final = "events.jsonl"
_STATE_FILE_NAME: Final = "state.json"
_HEARTBEAT_FILE_NAME: Final = "heartbeat.json"
_PID_FILE_NAME: Final = "pid"
_WORKER_LOG_FILE_NAME: Final = "worker.log"
_REPORT_DIRECTORY_NAME: Final = "report"
_RESULT_FILE_NAME: Final = "uplift.json"

_HEARTBEAT_PHASE_KEY: Final = "phase"
_HEARTBEAT_AT_KEY: Final = "at"

_FILE_MODE: Final = 0o600


def _now() -> datetime:
    return datetime.now(UTC)


class RunStore:
    """The run directory, and the only way anything writes to it."""

    def __init__(self, paths: TechtreePaths) -> None:
        self._paths = paths

    # -- immutable request --------------------------------------------------

    def create(self, request: RunRequest) -> RunState:
        """Create run tree and initial event."""
        run_id = request.run_id
        run_dir = self._run_dir(run_id)
        ensure_private_directory(self._paths.runs_dir)
        ensure_private_directory(run_dir)

        with self._lock(run_id):
            try:
                self._write_immutable(self._request_path(run_id), request)
            except ConflictError as error:
                raise ConflictError(
                    f"run {run_id} already exists",
                    code="run_already_exists",
                    details={"run_id": run_id},
                ) from error
            append_event(
                self._events_path(run_id),
                RunEvent(
                    sequence=0,
                    timestamp=_now(),
                    run_id=run_id,
                    previous_phase=None,
                    phase=RunPhase.CREATED,
                    kind=RUN_CREATED,
                    # Naming the request here ties the log to the document it
                    # executes, so a recovered run directory can be checked
                    # rather than assumed.
                    details={DETAIL_REQUEST_DIGEST: digest_object(request)},
                ),
            )
            return self._write_projection(run_id)

    def get_request(self, run_id: str) -> RunRequest:
        """Load immutable request."""
        path = self._request_path(run_id)
        try:
            raw = path.read_bytes()
        except FileNotFoundError as error:
            raise NotFoundError(
                f"no such run: {run_id}",
                code="run_not_found",
                details={"run_id": run_id},
            ) from error

        try:
            return RunRequest.model_validate_json(raw)
        except PydanticValidationError as error:
            # Nothing here inspects *why* validation failed, and nothing here
            # tries to read the document another way. A stored request that
            # this build cannot read is a run this build cannot operate on,
            # and that is the whole of what the message says: it does not
            # accuse the participant's files of being damaged, because they
            # are not — they are exactly the bytes that were written, and the
            # run's signed proof still checks against them.
            raise ValidationError(
                f"this run's records do not match what this version of techtree "
                f"writes, so this build cannot operate on the run: {path}. Runs "
                f"recorded by an earlier version of techtree read this way. "
                f"Techtree has not changed the run's files — it never rewrites a "
                f"run's records — and `techtree proof verify {run_id}` still "
                f"checks the run's proof.",
                code="run_request_unreadable",
                details={"run_id": run_id, "path": str(path)},
            ) from error

    # -- events and projection ---------------------------------------------

    def append(
        self,
        run_id: str,
        *,
        phase: RunPhase | None,
        kind: str = PHASE_ENTERED,
        details: dict[str, JsonValue] | None = None,
    ) -> RunState:
        """Validate event, append, and project.

        ``phase=None`` records the event against whatever phase the run is in
        at append time, under the lock. A caller reporting on work in progress
        must use it rather than naming a phase, because between its last look
        and this append the run may have been asked to cancel — and an event
        that claims a phase the run has left is corruption, not progress.
        """
        self._require_run(run_id)
        with self._lock(run_id):
            return self._append_locked(run_id, phase=phase, kind=kind, details=details)

    def request_cancel(self, run_id: str, *, requested_by: str) -> RunState:
        """Ask a run to stop, idempotently.

        A second request changes nothing: the log records when a run was first
        asked to stop, not how many times. Asking is therefore safe to retry,
        which matters because the CLI process that asked may not survive long
        enough to learn whether it succeeded.
        """
        self._require_run(run_id)
        with self._lock(run_id):
            current = reduce_events(read_events(self._events_path(run_id)))
            if current.phase is RunPhase.CANCEL_REQUESTED:
                return self._with_heartbeat(run_id, current)
            if is_terminal(current.phase):
                raise RunError(
                    f"run has already ended in {current.phase.value}; it cannot "
                    "be cancelled",
                    code="run_not_cancellable",
                    details={"run_id": run_id, "phase": current.phase.value},
                )
            return self._append_locked(
                run_id,
                phase=RunPhase.CANCEL_REQUESTED,
                kind=CANCEL_REQUESTED,
                details={DETAIL_REQUESTED_BY: requested_by},
            )

    def state(self, run_id: str) -> RunState:
        """Load projection or rebuild."""
        try:
            raw = self._state_path(run_id).read_bytes()
        except FileNotFoundError:
            return self.rebuild_state(run_id)

        try:
            cached = RunState.model_validate_json(raw)
        except PydanticValidationError:
            # The projection is a cache. A cache that will not parse is simply
            # a cache miss.
            return self.rebuild_state(run_id)

        # The journal is the truth; the cache is only trusted when it matches
        # the journal's head. A cache that lags (a crash between event append
        # and projection write) rebuilds. A cache that is AHEAD of the journal
        # claims events that never durably happened, which is corruption, not
        # a cache miss.
        journal = reduce_events(read_events(self._events_path(run_id)))
        if cached.run_id != journal.run_id or cached.sequence > journal.sequence:
            raise ConflictError(
                "the cached run state is ahead of the run's event journal",
                code="run_state_ahead_of_journal",
                details={
                    "run_id": run_id,
                    "cached_sequence": cached.sequence,
                    "journal_sequence": journal.sequence,
                },
            )
        if cached.sequence < journal.sequence:
            return self.rebuild_state(run_id)
        return cached

    def rebuild_state(self, run_id: str) -> RunState:
        """Recompute from events."""
        self._require_run(run_id)
        with self._lock(run_id):
            return self._write_projection(run_id)

    # -- worker process -----------------------------------------------------

    def write_pid(self, run_id: str, pid: int) -> None:
        """Persist worker PID."""
        self._require_run(run_id)
        if pid <= 0:
            raise ValidationError(
                f"a worker process id is positive, not {pid}",
                details={"run_id": run_id, "pid": pid},
            )

        with self._lock(run_id):
            self._require_open_locked(run_id, "take on a worker")
            # The pid file is what a signal-sender reads; the event is what
            # makes the worker's start part of the run's rebuildable history.
            # The event is settled first so that a run which cannot record a
            # worker does not end up with a pid file naming one.
            event = self._prepare_event(
                run_id,
                phase=None,
                kind=WORKER_STARTED,
                details={DETAIL_WORKER_PID: pid},
            )
            atomic_write_text(self._pid_path(run_id), f"{pid}\n")
            self._commit_event(run_id, event)

    def read_pid(self, run_id: str) -> int | None:
        """Read PID."""
        self._require_run(run_id)
        path = self._pid_path(run_id)
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

        try:
            return int(raw.strip())
        except ValueError as error:
            raise ValidationError(
                f"run pid file does not hold a process id: {path}",
                details={"run_id": run_id, "path": str(path)},
            ) from error

    def write_heartbeat(self, run_id: str, phase: RunPhase) -> None:
        """Refresh heartbeat."""
        self._require_run(run_id)
        with self._lock(run_id):
            atomic_write_json(
                self._heartbeat_path(run_id),
                {_HEARTBEAT_PHASE_KEY: phase, _HEARTBEAT_AT_KEY: _now()},
            )
            self._write_projection(run_id)

    # -- result -------------------------------------------------------------

    def result_path(self, run_id: str) -> Path:
        """Return UpliftReport path."""
        return self._run_dir(run_id) / _REPORT_DIRECTORY_NAME / _RESULT_FILE_NAME

    def write_result(self, run_id: str, report: UpliftReport) -> None:
        """Write immutable result."""
        self._require_run(run_id)
        if report.run_id != run_id:
            raise ValidationError(
                f"report belongs to run {report.run_id}, not to {run_id}",
                details={"run_id": run_id, "report_run_id": report.run_id},
            )

        path = self.result_path(run_id)
        with self._lock(run_id):
            self._require_open_locked(run_id, "record a result")
            # A report the log cannot announce would sit in the run directory
            # unmentioned and block the write that could be announced, so the
            # event is settled before the file exists.
            event = self._prepare_event(
                run_id,
                phase=None,
                kind=RESULT_WRITTEN,
                details={DETAIL_RESULT_DIGEST: digest_object(report)},
            )
            ensure_private_directory(path.parent)
            self._write_immutable(path, report)
            self._commit_event(run_id, event)

    def get_result(self, run_id: str) -> UpliftReport:
        """Load result."""
        self._require_run(run_id)
        path = self.result_path(run_id)
        try:
            raw = path.read_bytes()
        except FileNotFoundError as error:
            raise NotFoundError(
                f"run {run_id} has not produced a result",
                details={"run_id": run_id},
            ) from error

        try:
            return UpliftReport.model_validate_json(raw)
        except PydanticValidationError as error:
            raise ValidationError(
                f"run result is not a valid report: {path} "
                f"({error.errors()[0]['msg']})",
                details={"run_id": run_id, "path": str(path)},
            ) from error

    def worker_log_path(self, run_id: str) -> Path:
        """Return log path."""
        return self._run_dir(run_id) / _WORKER_LOG_FILE_NAME

    # -- internals ----------------------------------------------------------

    def _append_locked(
        self,
        run_id: str,
        *,
        phase: RunPhase | None,
        kind: str,
        details: dict[str, JsonValue] | None = None,
    ) -> RunState:
        """Append one event and refresh the projection. The lock is held."""
        event = self._prepare_event(run_id, phase=phase, kind=kind, details=details)
        return self._commit_event(run_id, event)

    def _prepare_event(
        self,
        run_id: str,
        *,
        phase: RunPhase | None,
        kind: str,
        details: dict[str, JsonValue] | None = None,
    ) -> RunEvent:
        """Build the next event, or raise if the machine would refuse it.

        Separate from committing it so that a method which also writes a file —
        the pid, the report — can find out that the run cannot record what it is
        about to do before it does it, and leave nothing behind.

        ``phase`` of ``None`` means "whatever phase the run is already in",
        which is how a store-level fact such as the worker's process id is
        recorded without pretending to advance the run. The lock is held.
        """
        events = read_events(self._events_path(run_id))
        current = reduce_events(events)

        try:
            event = RunEvent(
                sequence=next_sequence(events),
                timestamp=_now(),
                run_id=run_id,
                previous_phase=current.phase,
                phase=current.phase if phase is None else phase,
                kind=kind,
                details=dict(details or {}),
            )
        except PydanticValidationError as error:
            raise ValidationError(
                f"run event is not valid ({error.errors()[0]['msg']})",
                code="run_event_kind_invalid",
                details={"run_id": run_id, "kind": kind},
            ) from error

        # Projected against the current state here rather than trusted later, so
        # an event the machine would refuse never reaches the log.
        apply_event(current, event)
        return event

    def _commit_event(self, run_id: str, event: RunEvent) -> RunState:
        """Append a prepared event and recompute the projection.

        The projection comes from the log rather than from the event in hand,
        because the log is what a later reader will have. The lock is held.
        """
        append_event(self._events_path(run_id), event)
        return self._write_projection(run_id)

    def _write_projection(self, run_id: str) -> RunState:
        """Recompute the projection from the log and replace ``state.json``."""
        state = self._with_heartbeat(
            run_id, reduce_events(read_events(self._events_path(run_id)))
        )
        atomic_write_json(self._state_path(run_id), state)
        return state

    def _with_heartbeat(self, run_id: str, state: RunState) -> RunState:
        """Merge in the one fact the log cannot rebuild."""
        state.heartbeat_at = self._read_heartbeat(run_id)
        return state

    def _read_heartbeat(self, run_id: str) -> datetime | None:
        """Return the worker's last sign of life, if it has given one."""
        path = self._heartbeat_path(run_id)
        if not path.exists():
            return None

        document = read_json(path)
        raw = document.get(_HEARTBEAT_AT_KEY) if isinstance(document, dict) else None
        if not isinstance(raw, str):
            raise ValidationError(
                f"run heartbeat does not record when it was written: {path}",
                details={"run_id": run_id, "path": str(path)},
            )

        try:
            moment = datetime.fromisoformat(raw)
        except ValueError as error:
            raise ValidationError(
                f"run heartbeat time is not a timestamp: {path}",
                details={"run_id": run_id, "path": str(path)},
            ) from error
        if moment.tzinfo is None:
            raise ValidationError(
                f"run heartbeat time names no time zone: {path}",
                details={"run_id": run_id, "path": str(path)},
            )
        return moment

    def _write_immutable(self, path: Path, value: object) -> None:
        """Create a write-once file holding one object's canonical bytes."""
        # Serialized before the file is created: a value that cannot be
        # canonicalized must not leave an empty file that blocks the retry.
        data = canonical_json_bytes(value)
        with open_exclusive(path, _FILE_MODE) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        fsync_directory(path.parent)

    def _require_open_locked(self, run_id: str, doing: str) -> RunState:
        """Return the current state, refusing a run that has already ended.

        Checked before anything is written, so a run that cannot record what
        happened is not left holding a file it never announced. The lock is
        held.
        """
        state = reduce_events(read_events(self._events_path(run_id)))
        if is_terminal(state.phase):
            raise RunError(
                f"run has already ended in {state.phase.value}; it cannot {doing}",
                code="run_transition_invalid",
                details={"run_id": run_id, "phase": state.phase.value},
            )
        return state

    def _require_run(self, run_id: str) -> None:
        """Raise unless the run exists, which its request is the proof of."""
        if not self._request_path(run_id).exists():
            raise NotFoundError(
                f"no such run: {run_id}",
                code="run_not_found",
                details={"run_id": run_id},
            )

    @contextmanager
    def _lock(self, run_id: str) -> Iterator[None]:
        """Hold the per-run lock, or report the wait as a conflict."""
        lock = FileLock(
            self._run_dir(run_id) / _LOCK_FILE_NAME,
            timeout=LOCK_TIMEOUT_SECONDS,
            mode=_FILE_MODE,
        )
        try:
            lock.acquire()
        except Timeout as error:
            raise ConflictError(
                f"another process is holding the lock on run {run_id}",
                code="run_lock_timeout",
                details={"run_id": run_id, "waited_seconds": LOCK_TIMEOUT_SECONDS},
            ) from error
        try:
            yield
        finally:
            lock.release()

    def _run_dir(self, run_id: str) -> Path:
        return self._paths.run_dir(run_id)

    def _request_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / _REQUEST_FILE_NAME

    def _events_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / _EVENTS_FILE_NAME

    def _state_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / _STATE_FILE_NAME

    def _heartbeat_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / _HEARTBEAT_FILE_NAME

    def _pid_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / _PID_FILE_NAME
