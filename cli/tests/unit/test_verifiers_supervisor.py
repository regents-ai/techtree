"""The process that outlives the worker. Decisions document 0029, layer B.

Every test here starts real processes, because the whole claim is about what
happens to real processes when something dies. A mock cannot be hard-killed and
a stub has no process group, so the two questions that matter — does the
evaluation stop when its worker is killed outright, and does the stop reach the
grandchildren the engine actually runs its containers from — have no answer
that does not involve ``fork``.

The evaluations here are Python one-liners. What the pinned engine does with a
signal belongs to the preflight suite and the real-model run; what the
supervisor does with one belongs here.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Final

import pytest

from techtree.verifiers.child import (
    DEFAULT_GRACE_SECONDS,
    SUPERVISOR_GRACE_SECONDS,
    VARIANT_HARD_DEADLINE_SECONDS,
    VerifiersChild,
)
from techtree.verifiers.models import VariantName
from techtree.verifiers.supervisor import (
    DEADLINE_EXIT_CODE,
    RECORD_SCHEMA_VERSION,
    STOPPED_EXIT_CODE,
    SupervisionReason,
)

#: Long enough that nothing here ends by finishing.
_FOREVER: Final = 300

#: How long a test waits for something a supervisor was going to do anyway.
_PATIENCE_SECONDS = 30.0


def _eval_with_a_grandchild(marker: Path) -> list[str]:
    """Return an evaluation that spawns a child of its own and then waits.

    The engine's containers are torn down inside a rollout, and rollouts are
    grandchildren of the process the supervisor started. A signal that reached
    only the direct child would leave them running, so every test that stops an
    evaluation checks the grandchild too.
    """
    program = (
        "import pathlib, subprocess, sys, time\n"
        "kid = subprocess.Popen(\n"
        f"    [sys.executable, '-c', 'import time; time.sleep({_FOREVER})']\n"
        ")\n"
        "pathlib.Path(sys.argv[1]).write_text(str(kid.pid))\n"
        f"time.sleep({_FOREVER})\n"
    )
    return [sys.executable, "-c", program, str(marker)]


def _child(
    tmp_path: Path,
    argv: list[str],
    *,
    env: dict[str, str] | None = None,
    hard_deadline_seconds: float = VARIANT_HARD_DEADLINE_SECONDS,
    supervisor_grace_seconds: float = 2.0,
) -> VerifiersChild:
    """Build one supervised evaluation that captures into ``tmp_path``."""
    return VerifiersChild(
        variant=VariantName.BASELINE,
        argv=argv,
        cwd=tmp_path / "cwd",
        env={"PATH": os.environ.get("PATH", "")} if env is None else env,
        stdout_path=tmp_path / "run" / "stdout.log",
        stderr_path=tmp_path / "run" / "stderr.log",
        supervision_record_path=tmp_path / "supervision.json",
        hard_deadline_seconds=hard_deadline_seconds,
        supervisor_grace_seconds=supervisor_grace_seconds,
    )


def _record(tmp_path: Path) -> dict[str, object]:
    """Read the supervision record, waiting for the supervisor to write it."""
    path = tmp_path / "supervision.json"
    deadline = time.monotonic() + _PATIENCE_SECONDS
    while time.monotonic() < deadline:
        if path.is_file():
            document: dict[str, object] = json.loads(path.read_text())
            return document
        time.sleep(0.05)
    raise AssertionError("the supervisor left no record behind")


def _wait_for(path: Path) -> None:
    """Wait for a process to announce itself by writing a file."""
    deadline = time.monotonic() + _PATIENCE_SECONDS
    while time.monotonic() < deadline:
        if path.is_file() and path.read_text().strip():
            return
        time.sleep(0.05)
    raise AssertionError(f"nothing ever wrote {path}")


def _is_gone(pid: int) -> bool:
    """Whether one process has stopped existing, allowing time to be reaped."""
    deadline = time.monotonic() + _PATIENCE_SECONDS
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError):
            return True
        if _is_zombie(pid):
            return True
        time.sleep(0.05)
    return False


def _is_zombie(pid: int) -> bool:
    """Whether a pid names a process that has exited but not been reaped."""
    completed = subprocess.run(
        ["ps", "-o", "state=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip().startswith("Z")


# ---------------------------------------------------------------------------
# An evaluation that is left alone
# ---------------------------------------------------------------------------


def test_an_evaluation_that_finishes_reports_its_own_exit_code(
    tmp_path: Path,
) -> None:
    # The supervisor is not allowed to be a second opinion about how a run
    # went: an evaluation that ended by itself is reported exactly as it ended.
    started = _child(tmp_path, [sys.executable, "-c", "raise SystemExit(7)"])
    started.start()

    assert started.wait(timeout=_PATIENCE_SECONDS) == 7
    record = _record(tmp_path)
    assert record["schema_version"] == RECORD_SCHEMA_VERSION
    assert record["reason"] == SupervisionReason.COMPLETED
    assert record["eval_exit_code"] == 7
    assert record["escalated_to_sigkill"] is False


# ---------------------------------------------------------------------------
# The three ways an evaluation is stopped
# ---------------------------------------------------------------------------


def test_the_hard_deadline_stops_the_whole_evaluation_group(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "grandchild.pid"
    started = _child(
        tmp_path,
        _eval_with_a_grandchild(marker),
        hard_deadline_seconds=1.0,
    )
    started.start()
    _wait_for(marker)
    grandchild = int(marker.read_text())

    assert started.wait(timeout=_PATIENCE_SECONDS) == DEADLINE_EXIT_CODE
    assert _is_gone(grandchild)
    record = _record(tmp_path)
    assert record["reason"] == SupervisionReason.DEADLINE_EXCEEDED
    assert record["deadline_seconds"] == 1.0


def test_a_signalled_supervisor_forwards_the_signal_to_the_evaluation(
    tmp_path: Path,
) -> None:
    # The evaluation is in a process group of its own, so the worker's SIGTERM
    # reaches the supervisor and nothing else. The engine's own teardown only
    # ever runs because the supervisor passes the signal on.
    #
    # The evaluation says when it is ready and the test waits for that, because
    # a signal sent any earlier would be answered by a default disposition
    # rather than by a handler, and the forwarding this test is about would
    # never happen. The announcement cannot arrive too early: the supervisor
    # installs its own handlers before it launches anything, and the evaluation
    # installs its handler before it writes the file, so a readable marker
    # means every handler between here and there is already in place.
    marker = tmp_path / "signalled"
    ready = tmp_path / "handler-installed"
    program = (
        "import pathlib, signal, sys, time\n"
        "signal.signal(\n"
        "    signal.SIGTERM,\n"
        "    lambda *_: (pathlib.Path(sys.argv[1]).write_text('term'), sys.exit(0)),\n"
        ")\n"
        "pathlib.Path(sys.argv[2]).write_text('ready')\n"
        f"time.sleep({_FOREVER})\n"
    )
    started = _child(tmp_path, [sys.executable, "-c", program, str(marker), str(ready)])
    started.start()
    _wait_for(ready)

    started.terminate(grace_seconds=DEFAULT_GRACE_SECONDS)

    assert marker.read_text() == "term"
    assert started.outcome().exit_code == STOPPED_EXIT_CODE
    record = _record(tmp_path)
    assert record["reason"] == SupervisionReason.CANCELLED
    assert record["escalated_to_sigkill"] is False


def test_end_of_file_on_the_liveness_pipe_stops_the_evaluation(
    tmp_path: Path,
) -> None:
    # The same event a dead worker produces, produced deliberately: the worker
    # lets go of the pipe, and the supervisor treats the end-of-file as the
    # worker being gone.
    marker = tmp_path / "grandchild.pid"
    started = _child(tmp_path, _eval_with_a_grandchild(marker))
    started.start()
    _wait_for(marker)
    grandchild = int(marker.read_text())

    started._close_parent_liveness()

    assert started.wait(timeout=_PATIENCE_SECONDS) == STOPPED_EXIT_CODE
    assert _is_gone(grandchild)
    assert _record(tmp_path)["reason"] == SupervisionReason.PARENT_LOST


# ---------------------------------------------------------------------------
# The worker is killed outright
# ---------------------------------------------------------------------------


_WORKER_SOURCE = """
import os
import pathlib
import sys
import time

from techtree.verifiers.child import VerifiersChild
from techtree.verifiers.models import VariantName

root = pathlib.Path(sys.argv[1])
grandchild_marker = root / "grandchild.pid"
program = (
    "import pathlib, subprocess, sys, time\\n"
    "kid = subprocess.Popen(\\n"
    "    [sys.executable, '-c', 'import time; time.sleep(300)']\\n"
    ")\\n"
    "pathlib.Path(sys.argv[1]).write_text(str(kid.pid))\\n"
    "time.sleep(300)\\n"
)
child = VerifiersChild(
    variant=VariantName.BASELINE,
    argv=[sys.executable, "-c", program, str(grandchild_marker)],
    cwd=root / "cwd",
    env={"PATH": os.environ.get("PATH", "")},
    stdout_path=root / "run" / "stdout.log",
    stderr_path=root / "run" / "stderr.log",
    supervision_record_path=root / "supervision.json",
    supervisor_grace_seconds=2.0,
)
(root / "supervisor.pid").write_text(str(child.start()))
time.sleep(300)
"""


def test_a_hard_killed_worker_leaves_no_evaluation_running(tmp_path: Path) -> None:
    """The stop condition decision 0029 was written for.

    A worker that is ``SIGKILL``ed runs no cleanup, no signal handler and no
    ``finally``. The only thing left is the kernel closing its descriptors,
    which is why the liveness pipe is a pipe and not a heartbeat: the
    end-of-file arrives whether or not the worker was in a position to say
    anything. Nothing is terminated politely here — that would prove the wrong
    thing — and the supervision record is what says the evaluation was stopped
    because its worker died rather than for any other reason.
    """
    worker_source = tmp_path / "worker.py"
    worker_source.write_text(_WORKER_SOURCE, encoding="utf-8")
    worker = subprocess.Popen([sys.executable, str(worker_source), str(tmp_path)])
    try:
        _wait_for(tmp_path / "supervisor.pid")
        _wait_for(tmp_path / "grandchild.pid")
        supervisor = int((tmp_path / "supervisor.pid").read_text())
        grandchild = int((tmp_path / "grandchild.pid").read_text())

        os.kill(worker.pid, signal.SIGKILL)
        worker.wait(timeout=_PATIENCE_SECONDS)

        record = _record(tmp_path)
    finally:
        if worker.poll() is None:  # pragma: no cover - the kill above is the test
            worker.kill()
            worker.wait(timeout=_PATIENCE_SECONDS)

    assert record["reason"] == SupervisionReason.PARENT_LOST
    assert record["supervisor_pid"] == supervisor
    assert _is_gone(grandchild)
    assert _is_gone(supervisor)


# ---------------------------------------------------------------------------
# What the record may and may not say
# ---------------------------------------------------------------------------


def test_the_supervision_record_is_private_to_the_operator(tmp_path: Path) -> None:
    started = _child(tmp_path, [sys.executable, "-c", "pass"])
    started.start()
    started.wait(timeout=_PATIENCE_SECONDS)

    _record(tmp_path)
    assert (tmp_path / "supervision.json").stat().st_mode & 0o777 == 0o600


def test_the_record_carries_neither_the_invocation_nor_a_credential(
    tmp_path: Path,
) -> None:
    # The supervisor runs with the provider credential in its environment and
    # the whole evaluation on its argv. A record of a run is not a place for
    # either of them.
    secret = "sk-supervisor-unit-test-secret"
    argument = "a-marker-only-the-invocation-carries"
    started = _child(
        tmp_path,
        [sys.executable, "-c", "import sys; sys.exit(0)", argument],
        env={"PATH": os.environ.get("PATH", ""), "PRIME_API_KEY": secret},
    )
    started.start()
    started.wait(timeout=_PATIENCE_SECONDS)

    written = (tmp_path / "supervision.json").read_text()
    _record(tmp_path)
    assert secret not in written
    assert argument not in written
    assert sys.executable not in written


# ---------------------------------------------------------------------------
# The invariant that keeps the two graces in the right order
# ---------------------------------------------------------------------------


def test_the_supervisors_grace_is_shorter_than_the_workers() -> None:
    """Both are running during a cancellation, and the inner one must finish.

    A worker that escalated first would ``SIGKILL`` a supervisor in the middle
    of a clean teardown, which is exactly the state that leaves containers
    behind.
    """
    assert SUPERVISOR_GRACE_SECONDS < DEFAULT_GRACE_SECONDS


if sys.platform == "win32":  # pragma: no cover - process groups here are POSIX
    pytestmark = pytest.mark.skip(reason="the supervisor's guarantees are POSIX")
