"""One evaluation, supervised by a process that outlives its worker.

Decisions document 0029, layer B. The problem this solves has one sentence: a
Techtree worker that is hard-killed cannot stop anything, so without something
else watching, the evaluation it started keeps running containers and keeps
spending until it finishes on its own. Nothing in the pinned engine bounds
that, and a signal handler in the worker cannot run when the worker is gone.

So each variant is launched under a supervisor of its own — one small process,
in its own session, holding three things and nothing else:

*The read end of a pipe the worker holds open.* Nobody ever writes to it. Its
only message is end-of-file, and the kernel sends that when the last writer
closes, which includes the worker being killed outright. That is the fast path:
the eval is stopped within a poll interval of the worker's death rather than
within the deadline.

*A monotonic deadline.* The backstop for everything the pipe cannot see — a
worker that is alive but wedged, an evaluation that hangs with the pipe still
open. Measured on the monotonic clock so a system clock change cannot extend
it.

*The eval's process group.* The engine tears its containers down inside the
rollout it was interrupted in, so it is signalled gently first and the whole
group is signalled, because the rollouts are grandchildren. Only after the
grace period does the group get ``SIGKILL``. The grace here is deliberately
shorter than the worker's own, so that when both are running the inner
escalation happens first and the worker never kills a supervisor that was
halfway through a clean stop.

This is not a daemon. It has no registry, no socket, no state directory, and no
life beyond the one evaluation it was started for. What it leaves behind is one
private record saying what happened, which is the only way anybody can tell an
orphan-stop from an ordinary finish after the fact. The record carries no argv,
no environment and no credentials: it is written by a process that had a
credential in its environment, and a record of a run is not a place for one.

Run as ``python -m techtree.verifiers.supervisor``; the worker builds the
invocation in :mod:`techtree.verifiers.child`.
"""

from __future__ import annotations

import argparse
import contextlib
import errno
import os
import selectors
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Final

from techtree.fs import atomic_write_json, ensure_private_directory
from techtree.models.base import JsonValue

__all__ = [
    "DEADLINE_EXIT_CODE",
    "RECORD_SCHEMA_VERSION",
    "STOPPED_EXIT_CODE",
    "SUPERVISION_RECORD_MODE",
    "SUPERVISOR_FAILURE_EXIT_CODE",
    "SupervisionReason",
    "main",
]

#: The schema of the record this process leaves behind.
RECORD_SCHEMA_VERSION: Final = "techtree.eval-supervision.v1"

#: The deadline was reached and the evaluation was stopped.
DEADLINE_EXIT_CODE: Final = 124

#: The supervisor itself could not do its job — most often, the evaluation
#: could not be launched at all.
SUPERVISOR_FAILURE_EXIT_CODE: Final = 125

#: The evaluation was stopped rather than allowed to finish, either because the
#: supervisor was signalled or because its worker died. The conventional Ctrl-C
#: code, which is what the pinned engine exits with after its own teardown.
STOPPED_EXIT_CODE: Final = 130

#: Owner read and write only, matching every other file Techtree writes.
SUPERVISION_RECORD_MODE: Final = 0o600

#: How often the loop re-checks the eval, the clock, and a pending signal.
_POLL_INTERVAL_SECONDS: Final = 0.1

#: How often a dying process group is re-checked during the grace period.
_REAP_INTERVAL_SECONDS: Final = 0.05


class SupervisionReason(StrEnum):
    """Why one supervised evaluation ended. The record's ``reason`` field."""

    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DEADLINE_EXCEEDED = "deadline_exceeded"
    PARENT_LOST = "parent_lost"
    LAUNCH_FAILED = "launch_failed"


def _parse_arguments(argv: list[str]) -> argparse.Namespace:
    """Read the supervisor's own arguments; everything after ``--`` is the eval."""
    parser = argparse.ArgumentParser(
        prog="techtree-eval-supervisor",
        description="Bound one Verifiers evaluation to its worker's lifetime.",
    )
    parser.add_argument("--variant", required=True)
    parser.add_argument("--parent-fd", required=True, type=int)
    parser.add_argument("--record", required=True, type=Path)
    parser.add_argument("--deadline-seconds", required=True, type=float)
    parser.add_argument("--grace-seconds", required=True, type=float)
    parser.add_argument("eval_argv", nargs=argparse.REMAINDER)
    parsed = parser.parse_args(argv)
    if parsed.eval_argv[:1] == ["--"]:
        parsed.eval_argv = parsed.eval_argv[1:]
    if not parsed.eval_argv:
        parser.error("the evaluation to supervise follows --")
    return parsed


class _Supervisor:
    """The one evaluation this process was started for."""

    def __init__(
        self,
        *,
        variant: str,
        parent_fd: int,
        record_path: Path,
        deadline_seconds: float,
        grace_seconds: float,
        eval_argv: list[str],
    ) -> None:
        self._variant = variant
        self._parent_fd = parent_fd
        self._record_path = record_path
        self._deadline_seconds = deadline_seconds
        self._grace_seconds = grace_seconds
        self._eval_argv = eval_argv

        self._process: subprocess.Popen[bytes] | None = None
        self._group: int | None = None
        self._started_at = datetime.now(UTC)
        self._started_monotonic = time.monotonic()
        self._signalled = False
        self._escalated = False
        self._shutdown_seconds: float | None = None

    # -- the loop ---------------------------------------------------------

    def run(self) -> int:
        """Supervise the evaluation and return the code this process exits with."""
        signal.signal(signal.SIGTERM, self._on_signal)
        signal.signal(signal.SIGINT, self._on_signal)

        reason = SupervisionReason.LAUNCH_FAILED
        exit_code = SUPERVISOR_FAILURE_EXIT_CODE
        try:
            self._launch()
        except OSError:
            self._finish(reason=reason, exit_code=exit_code)
            return exit_code

        try:
            reason = self._watch()
            exit_code = self._stop_if_running(reason)
        except Exception:
            # Whatever went wrong in here, an evaluation must not outlive the
            # process that was supposed to bound it. Stop it, then report the
            # supervisor's own failure rather than the eval's.
            reason = SupervisionReason.CANCELLED
            exit_code = SUPERVISOR_FAILURE_EXIT_CODE
            with contextlib.suppress(Exception):
                self._stop_if_running(reason)
        finally:
            self._finish(reason=reason, exit_code=exit_code)
        return exit_code

    def _finish(self, *, reason: SupervisionReason, exit_code: int) -> None:
        """Leave the record behind and let go of the worker's pipe."""
        self._write_record(reason=reason, exit_code=exit_code)
        self._close_parent_fd()

    def _launch(self) -> None:
        """Start the evaluation in a process group of its own."""
        self._process = subprocess.Popen(
            self._eval_argv,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
        with contextlib.suppress(OSError):
            self._group = os.getpgid(self._process.pid)

    def _watch(self) -> SupervisionReason:
        """Wait for the first of: the eval finishing, EOF, the deadline, a signal."""
        process = self._process
        assert process is not None
        deadline = self._started_monotonic + self._deadline_seconds

        with selectors.DefaultSelector() as selector:
            selector.register(self._parent_fd, selectors.EVENT_READ)
            while True:
                if process.poll() is not None:
                    return SupervisionReason.COMPLETED
                if self._signalled:
                    return SupervisionReason.CANCELLED
                if time.monotonic() >= deadline:
                    return SupervisionReason.DEADLINE_EXCEEDED
                if selector.select(timeout=_POLL_INTERVAL_SECONDS) and self._at_eof():
                    return SupervisionReason.PARENT_LOST

    def _at_eof(self) -> bool:
        """Whether the worker's end of the liveness pipe has closed.

        Nothing is ever written to this pipe, so anything readable is either
        end-of-file or a byte nobody sent. A byte is not a reason to stop an
        evaluation, so only the empty read counts.
        """
        try:
            return os.read(self._parent_fd, 1) == b""
        except OSError as error:
            # Nothing to read yet is not a death; anything else means the pipe
            # can no longer answer the question, which is treated as one.
            return error.errno != errno.EAGAIN

    # -- stopping ---------------------------------------------------------

    def _stop_if_running(self, reason: SupervisionReason) -> int:
        """Return the exit code for ``reason``, stopping the eval if it still runs."""
        process = self._process
        assert process is not None
        if reason == SupervisionReason.COMPLETED:
            return _exit_code_of(process.returncode)

        started = time.monotonic()
        self._signal_group(signal.SIGTERM)
        grace_until = started + max(self._grace_seconds, 0.0)
        while time.monotonic() < grace_until:
            if process.poll() is not None:
                break
            time.sleep(_REAP_INTERVAL_SECONDS)
        else:
            if process.poll() is None:
                self._escalated = True
                self._signal_group(signal.SIGKILL)
                process.wait()
        self._shutdown_seconds = time.monotonic() - started

        if reason == SupervisionReason.DEADLINE_EXCEEDED:
            return DEADLINE_EXIT_CODE
        return STOPPED_EXIT_CODE

    def _signal_group(self, number: int) -> None:
        """Signal the evaluation's whole group, tolerating a race with its exit."""
        process = self._process
        assert process is not None
        if self._group is not None:
            try:
                os.killpg(self._group, number)
                return
            except ProcessLookupError:
                return
            except PermissionError:
                pass
        with contextlib.suppress(ProcessLookupError):
            process.send_signal(number)

    def _on_signal(self, _number: int, _frame: object) -> None:
        """Record that a stop was asked for; the loop does the stopping."""
        self._signalled = True

    # -- what it leaves behind --------------------------------------------

    def _write_record(self, *, reason: SupervisionReason, exit_code: int) -> None:
        """Write the private supervision record.

        Deliberately last and deliberately unconditional: the record is the
        only evidence that a hard-killed worker's evaluation was stopped, and a
        record that is only written on the happy path proves the wrong half.
        """
        process = self._process
        finished = datetime.now(UTC)
        document: dict[str, JsonValue] = {
            "schema_version": RECORD_SCHEMA_VERSION,
            "variant": self._variant,
            "reason": reason.value,
            "started_at": self._started_at.isoformat(),
            "finished_at": finished.isoformat(),
            "elapsed_seconds": round(time.monotonic() - self._started_monotonic, 3),
            "deadline_seconds": self._deadline_seconds,
            "grace_seconds": self._grace_seconds,
            "supervisor_pid": os.getpid(),
            "eval_pid": None if process is None else process.pid,
            "eval_process_group": self._group,
            # As the operating system reported it: negative means the
            # evaluation was killed by that signal rather than exiting.
            "eval_exit_code": None if process is None else process.returncode,
            "supervisor_exit_code": exit_code,
            "escalated_to_sigkill": self._escalated,
            "shutdown_seconds": (
                None
                if self._shutdown_seconds is None
                else round(self._shutdown_seconds, 3)
            ),
        }
        with contextlib.suppress(OSError):
            ensure_private_directory(self._record_path.parent)
            atomic_write_json(self._record_path, document, mode=SUPERVISION_RECORD_MODE)

    def _close_parent_fd(self) -> None:
        """Release the worker's liveness pipe."""
        with contextlib.suppress(OSError):
            os.close(self._parent_fd)


def _exit_code_of(returncode: int) -> int:
    """Return one process's exit status as a shell would report it."""
    return 128 + (-returncode) if returncode < 0 else returncode


def main(argv: list[str] | None = None) -> int:
    """Supervise one evaluation and return this process's exit code."""
    parsed = _parse_arguments(sys.argv[1:] if argv is None else argv)
    return _Supervisor(
        variant=parsed.variant,
        parent_fd=parsed.parent_fd,
        record_path=parsed.record,
        deadline_seconds=parsed.deadline_seconds,
        grace_seconds=parsed.grace_seconds,
        eval_argv=list(parsed.eval_argv),
    ).run()


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    raise SystemExit(main())
