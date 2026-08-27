"""Starting and signalling the detached worker. Spec PR8 §8.7.

The point of the whole slice is here: the process that runs a Climb must
outlive the process that started it. A host agent invokes ``techtree climb
start``, gets a run identifier back in well under a second, and exits. The
work continues.

That is what ``start_new_session=True`` buys. The worker becomes a session
leader in its own process group, so it does not receive the terminal's
``SIGHUP`` when the shell that launched it goes away, and a ``Ctrl-C`` in that
shell interrupts the CLI rather than the run. The same fact makes cancellation
precise: the run's process group contains the worker and nothing else, so
signalling the group cannot reach anything the run did not start.

Three rules apply to every launch.

*No shell.* The command is an argument array handed to ``execvp``. Spec §10.1
allows nothing else, and there is no string anywhere in this module that a run
identifier could be interpolated into.

*No inherited environment.* The child is given a small, named set of
variables, built by the injected ``environment_builder``. The fake executor
needs no model credential, and spec §10.7 says it must not be handed one; the
way to guarantee that is to pass a constructed environment rather than to
filter the ambient one.

*The log is the run's, and private.* ``worker.log`` is opened ``0600`` in
append mode and given to the child as both stdout and stderr, so anything the
worker prints — including anything a library prints — lands in one file the
run owns instead of on the caller's terminal.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Final

from techtree.errors import PrerequisiteError, RunError
from techtree.fs import ensure_private_directory
from techtree.paths import TechtreePaths
from techtree.runs.store import RunStore

__all__ = [
    "WORKER_COMMAND",
    "WORKER_EXECUTABLE_NAME",
    "WORKER_EXECUTABLE_NOT_FOUND",
    "WORKER_LAUNCH_FAILED",
    "WORKER_SIGNAL_FAILED",
    "WorkerLauncher",
    "default_worker_executable",
    "scrubbed_worker_environment",
    "worker_visible_environment",
]

#: Stable error codes. Spec PR8 §8.16.
WORKER_EXECUTABLE_NOT_FOUND: Final = "worker_executable_not_found"
WORKER_LAUNCH_FAILED: Final = "worker_launch_failed"
WORKER_SIGNAL_FAILED: Final = "worker_signal_failed"

#: The console script the package installs for the detached worker.
WORKER_EXECUTABLE_NAME: Final = "techtree-worker"

#: The subcommand a launch always invokes.
WORKER_COMMAND: Final = "execute"

_LOG_FILE_MODE: Final = 0o600

#: Everything the worker is given. ``TECHTREE_HOME`` is how it finds the run
#: directory; ``PYTHONUNBUFFERED`` is how its log is readable while it runs
#: rather than only after it exits.
_INHERITED_VARIABLES: Final[tuple[str, ...]] = (
    "PATH",
    "HOME",
    "TMPDIR",
    "TECHTREE_LOG_LEVEL",
)
_TECHTREE_HOME: Final = "TECHTREE_HOME"


def default_worker_executable() -> Path:
    """Return where the ``techtree-worker`` console script should be.

    The interpreter's own directory is consulted first. Inside a virtual
    environment that is where the console script lives, and it is the right
    answer even when the environment has not been activated on ``PATH`` —
    which is exactly the situation a launched subprocess is in.

    Resolution does not assert that the program is there. Only a launch needs
    it to exist, and a command that merely reads a run's status should not
    fail because this machine could not start a new one.
    """
    beside_interpreter = Path(sys.executable).resolve().parent / WORKER_EXECUTABLE_NAME
    if beside_interpreter.is_file():
        return beside_interpreter

    on_path = shutil.which(WORKER_EXECUTABLE_NAME)
    return beside_interpreter if on_path is None else Path(on_path)


def worker_visible_environment(
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return the part of an environment a worker would actually be given.

    Variables are copied in by name from a fixed list. Nothing that is not on
    that list reaches the worker, so a model-provider credential in the
    operator's shell cannot be inherited by a run that has no business seeing
    one.

    This is separate from :func:`scrubbed_worker_environment` because a
    readiness check has to answer "what would a run be able to see" without
    inventing a run to ask about. Both go through this one function so that the
    answer a check gives and the environment a launch builds cannot drift
    apart.
    """
    source = os.environ if environ is None else environ
    return {name: source[name] for name in _INHERITED_VARIABLES if name in source}


def scrubbed_worker_environment(
    paths: TechtreePaths,
    *,
    environ: Mapping[str, str] | None = None,
) -> Callable[[str], Mapping[str, str]]:
    """Return the builder that constructs a worker's whole environment.

    What the worker inherits is :func:`worker_visible_environment`; what it is
    told on top of that is where this installation lives and that its output
    must not be buffered.
    """

    def build(run_id: str) -> Mapping[str, str]:
        environment = worker_visible_environment(environ)
        environment[_TECHTREE_HOME] = str(paths.root)
        environment["PYTHONUNBUFFERED"] = "1"
        return environment

    return build


class WorkerLauncher:
    """Launches and signals one detached local worker per run."""

    def __init__(
        self,
        *,
        worker_executable: Path,
        run_store: RunStore,
        environment_builder: Callable[[str], Mapping[str, str]],
    ) -> None:
        self._executable = worker_executable
        self._runs = run_store
        self._environment = environment_builder

    def command(self, run_id: str) -> Sequence[str]:
        """Return the argument array a launch executes."""
        return [str(self._executable), WORKER_COMMAND, "--run-id", run_id]

    def launch(self, run_id: str) -> int:
        """Start the detached worker for one run and return its process id."""
        if not self._executable.is_file() or not os.access(self._executable, os.X_OK):
            raise PrerequisiteError(
                f"there is no runnable worker program at {self._executable}, so "
                "no run can be started on this machine",
                code=WORKER_EXECUTABLE_NOT_FOUND,
                details={"run_id": run_id, "executable": str(self._executable)},
            )

        log_path = self._runs.worker_log_path(run_id)
        run_dir = log_path.parent
        ensure_private_directory(run_dir)
        descriptor = os.open(
            log_path,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND,
            _LOG_FILE_MODE,
        )
        try:
            # An argument array, never a command string: there is nothing here
            # for a shell to reinterpret. The working directory is the run's
            # own, so a worker outliving the directory it was started from is
            # not holding one open.
            process = subprocess.Popen(
                self.command(run_id),
                stdin=subprocess.DEVNULL,
                stdout=descriptor,
                stderr=subprocess.STDOUT,
                env=dict(self._environment(run_id)),
                cwd=str(run_dir),
                start_new_session=True,
                close_fds=True,
                shell=False,
            )
        except OSError as error:
            raise RunError(
                f"the worker for run {run_id} could not be started: "
                f"{error.strerror or error}",
                code=WORKER_LAUNCH_FAILED,
                details={"run_id": run_id},
            ) from error
        finally:
            os.close(descriptor)

        return process.pid

    def is_alive(self, run_id: str) -> bool:
        """Return whether this run's worker process still exists."""
        pid = self._runs.read_pid(run_id)
        if pid is None:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            # The process exists; it simply is not ours to signal. That is
            # still an answer to the question asked.
            return True
        return True

    def request_termination(self, run_id: str) -> None:
        """Ask this run's process group to stop, and do not wait."""
        self._signal(run_id, signal.SIGTERM)

    def force_kill(self, run_id: str) -> None:
        """Stop this run's process group without asking."""
        self._signal(run_id, signal.SIGKILL)

    def _signal(self, run_id: str, number: signal.Signals) -> None:
        """Signal the worker's process group, tolerating a worker that ended."""
        pid = self._runs.read_pid(run_id)
        if pid is None:
            return
        try:
            # The worker was started with ``start_new_session``, so its process
            # group identifier is its own process id and the group holds only
            # the run.
            os.killpg(os.getpgid(pid), number)
        except ProcessLookupError:
            # The worker already exited. Being asked to stop something that
            # has stopped is not a failure.
            return
        except OSError as error:
            raise RunError(
                f"run {run_id} could not be signalled: {error.strerror or error}",
                code=WORKER_SIGNAL_FAILED,
                details={"run_id": run_id, "signal": number.name},
            ) from error
