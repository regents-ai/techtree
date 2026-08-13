"""One live evaluation child process. Spec section 6.10.

Three rules shape this module, and each of them is a finding rather than a
preference.

*The engine's ``eval`` is addressed by absolute path.* The pinned build installs
its console script under the bare, generic name ``eval``
(``docs/verifiers-pin.md``, finding C3). Resolving that through ``PATH`` would
let the shell's builtin, or anything else on the machine called ``eval``, answer
for the managed engine. :class:`~techtree.engines.registry.EngineRegistry`
resolves it inside the engine's own virtual environment and the resolved path is
what is executed.

*Standard output is redirected to a file and never streamed.* With ``rich``
disabled the pinned CLI prints every trace to stdout as indented JSON once the
run finishes (``docs/verifiers-eval.md``). Those are the subject's full
transcripts. A host agent that saw them would be reading the participant's
private evidence out of its own terminal, so the child's descriptors point at
run-owned files from the moment it starts and nothing here ever returns their
contents.

*Cancellation goes to the process group, gently first.* The pinned CLI installs
an interrupt handler so the first signal raises ``KeyboardInterrupt`` inside
each rollout, letting its ``finally`` tear down the Docker container before the
process exits ``130``. Killing outright would leave containers running. So
:meth:`VerifiersChild.terminate` sends ``SIGTERM`` to the whole group, waits out
a grace period, and only then escalates.

The capture files open with a single provenance line naming the variant, the
start time and the digest of the invocation. It costs one line and buys two
things: an ``ArtifactRef`` is well formed even when a stream stayed silent, and
a log copied out of a run directory for diagnosis still says which variant of
which invocation produced it.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Final, Self

from techtree.canonical import sha256_digest_bytes
from techtree.errors import RunError
from techtree.fs import ensure_private_directory, fsync_directory
from techtree.models.base import ArtifactRef, Digest
from techtree.verifiers.models import ChildProcessOutcome, VariantName

__all__ = [
    "CANCELLATION_EXIT_CODE",
    "CAPTURE_MEDIA_TYPE",
    "CHILD_NOT_STARTED",
    "CHILD_START_FAILED",
    "CHILD_STILL_RUNNING",
    "CONFIG_ARGUMENT_MARKER",
    "DEFAULT_GRACE_SECONDS",
    "DRY_RUN_FLAG",
    "EVAL_EXECUTABLE",
    "OUTPUT_DIR_FLAG",
    "PUSH_DISABLED_FLAG",
    "VerifiersChild",
    "argv_digest",
    "capture_artifact",
    "dry_run_argv",
    "eval_argv",
    "write_command_log",
]

#: The pinned engine's evaluation console script. A bare, generic name
#: (``docs/verifiers-pin.md``, finding C3), so it is only ever handed to
#: :class:`~techtree.engines.registry.EngineRegistry` or resolved to an absolute
#: path before being executed — never looked up on ``PATH``.
EVAL_EXECUTABLE: Final = "eval"

#: ``eval`` takes its configuration as ``@`` followed by the path, as two
#: separate argv entries (``docs/verifiers-eval.md``).
CONFIG_ARGUMENT_MARKER: Final = "@"
DRY_RUN_FLAG: Final = "--dry-run"
OUTPUT_DIR_FLAG: Final = "--output-dir"

#: Belt and braces alongside ``push = false`` in the compiled document. Upstream
#: defaults to uploading the participant's episodes (``docs/verifiers-eval.md``,
#: finding E1), and a flag on argv overrides whatever the file says.
PUSH_DISABLED_FLAG: Final = "--no-push"

#: The conventional Ctrl-C code the pinned CLI exits on after it has torn its
#: containers down (``docs/verifiers-eval.md``). A stopped run is cancelled,
#: not invalid.
CANCELLATION_EXIT_CODE: Final = 130

#: How long a terminated child is given to tear its containers down before the
#: signal is escalated.
DEFAULT_GRACE_SECONDS: Final = 30.0

CAPTURE_MEDIA_TYPE: Final = "text/plain"

CHILD_NOT_STARTED: Final = "eval_child_not_started"
CHILD_START_FAILED: Final = "eval_child_start_failed"
CHILD_STILL_RUNNING: Final = "eval_child_still_running"

#: How often :meth:`VerifiersChild.terminate` re-checks a dying child.
_REAP_INTERVAL_SECONDS: Final = 0.05


def eval_argv(*, eval_executable: Path, input_config_path: Path) -> list[str]:
    """Return the full-path invocation for one variant's real evaluation.

    The output directory is deliberately absent: the compiled configuration
    already names an absolute one, and repeating it on argv would create a
    second place the two documents could disagree. No credential appears here
    and none can — the configuration names an environment variable, and the
    engine reads it from the child's environment (spec section 6.9).
    """
    return [
        str(eval_executable),
        CONFIG_ARGUMENT_MARKER,
        str(input_config_path),
        PUSH_DISABLED_FLAG,
    ]


def dry_run_argv(*, input_config_path: Path, dry_run_dir: Path) -> list[str]:
    """Return the arguments the engine's ``eval`` script is given for a dry run.

    ``--output-dir`` redirects the resolved document away from the real run
    directory, so a validation cannot be mistaken later for a truncated run
    (``docs/verifiers-eval.md``, finding E2). The executable itself is prepended
    by :class:`~techtree.engines.runner.EngineRunner`.
    """
    return [
        CONFIG_ARGUMENT_MARKER,
        str(input_config_path),
        DRY_RUN_FLAG,
        PUSH_DISABLED_FLAG,
        OUTPUT_DIR_FLAG,
        str(dry_run_dir),
    ]


def argv_digest(argv: Sequence[str]) -> Digest:
    """Digest one invocation so it can be cited without being reprinted."""
    return sha256_digest_bytes("\0".join(argv).encode("utf-8"))


def capture_artifact(path: Path) -> ArtifactRef:
    """Hash one capture file and describe it."""
    data = path.read_bytes()
    return ArtifactRef(
        digest=sha256_digest_bytes(data),
        media_type=CAPTURE_MEDIA_TYPE,
        size=len(data),
        relative_path=None,
    )


def write_command_log(
    path: Path,
    *,
    variant: VariantName,
    argv: Sequence[str],
    exit_code: int,
    stdout: str,
    stderr: str,
) -> Path:
    """Record what a short captured engine command did. Spec section 6.19.

    This is the dry run's counterpart to a live child's capture files. A dry run
    is short and its output is model-free, so it is captured in memory and
    written here in one piece rather than streamed.
    """
    ensure_private_directory(path.parent)
    document = "\n".join(
        [
            f"variant: {variant.value}",
            f"argv-digest: {argv_digest(argv)}",
            f"argv: {' '.join(argv)}",
            f"exit-code: {exit_code}",
            "--- stdout ---",
            stdout.rstrip("\n"),
            "--- stderr ---",
            stderr.rstrip("\n"),
            "",
        ]
    )
    _write_private(path, document.encode("utf-8"))
    return path


class VerifiersChild:
    """One ``eval`` process, its capture files, and its outcome.

    The object is single-use and strictly ordered: construct, :meth:`start`,
    observe through :meth:`poll` or :meth:`wait`, then :meth:`outcome`. Asking
    for an outcome before the process has exited raises rather than guessing,
    because a half-finished child has no finishing time and no final bytes to
    hash.
    """

    def __init__(
        self,
        *,
        variant: VariantName,
        argv: Sequence[str],
        cwd: Path,
        env: Mapping[str, str],
        stdout_path: Path,
        stderr_path: Path,
    ) -> None:
        self._variant = variant
        self._argv = tuple(argv)
        self._cwd = cwd
        self._env = dict(env)
        self._stdout_path = stdout_path
        self._stderr_path = stderr_path

        self._process: subprocess.Popen[bytes] | None = None
        self._streams: list[IO[bytes]] = []
        self._started_at: datetime | None = None
        self._started_monotonic: float | None = None
        self._finished_at: datetime | None = None
        self._elapsed_seconds: float | None = None
        self._cancelled = False

    # -- identity ---------------------------------------------------------

    @property
    def variant(self) -> VariantName:
        """Which side of the comparison this child is running."""
        return self._variant

    @property
    def argv_digest(self) -> Digest:
        """The digest of this child's invocation."""
        return argv_digest(self._argv)

    @property
    def pid(self) -> int | None:
        """The child's process id once it has started."""
        return None if self._process is None else self._process.pid

    @property
    def cancelled(self) -> bool:
        """Whether this child was asked to stop rather than allowed to finish."""
        return self._cancelled

    @property
    def elapsed_seconds(self) -> float | None:
        """How long the child ran, measured on the monotonic clock."""
        return self._elapsed_seconds

    # -- lifecycle --------------------------------------------------------

    def start(self) -> int:
        """Start the child in its own process group and return its pid.

        A new session means the whole subprocess tree — the engine, its Docker
        client, anything either spawns — can be signalled as one group, and
        that the operator's own Ctrl-C in the foreground terminal does not reach
        an evaluation mid-rollout and orphan its containers.
        """
        if self._process is not None:
            raise RunError(
                f"the {self._variant.value} evaluation child has already started",
                code=CHILD_START_FAILED,
                details={"variant": self._variant.value},
            )

        ensure_private_directory(self._cwd)
        stdout = self._open_capture(self._stdout_path, stream="stdout")
        stderr = self._open_capture(self._stderr_path, stream="stderr")

        self._started_at = datetime.now(UTC)
        self._started_monotonic = time.monotonic()
        try:
            self._process = subprocess.Popen(
                list(self._argv),
                cwd=str(self._cwd),
                env=self._env,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
                close_fds=True,
            )
        except OSError as error:
            self._close_streams()
            raise RunError(
                f"the evaluation child could not be started: {error.strerror or error}",
                code=CHILD_START_FAILED,
                details={"variant": self._variant.value, "program": self._argv[0]},
            ) from error
        return self._process.pid

    def poll(self) -> int | None:
        """Return the exit code, or ``None`` while the child is still running."""
        process = self._require_started()
        code = process.poll()
        if code is not None:
            self._record_exit()
        return code

    def wait(self, timeout: float | None = None) -> int:
        """Wait for the child and return its exit code."""
        process = self._require_started()
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise RunError(
                f"the {self._variant.value} evaluation did not finish within "
                f"{timeout:.0f}s",
                code=CHILD_STILL_RUNNING,
                details={"variant": self._variant.value, "timeout_seconds": timeout},
                retryable=True,
            ) from error
        self._record_exit()
        return code

    def terminate(self, grace_seconds: float = DEFAULT_GRACE_SECONDS) -> None:
        """Stop the child's process group, allowing Docker teardown first.

        ``SIGTERM`` reaches every process in the group, which is what lets the
        pinned CLI's interrupt handler run each rollout's cleanup. Only after
        the grace period does the group get ``SIGKILL``; escalating sooner would
        buy a faster exit at the price of containers nobody owns any more.
        """
        process = self._require_started()
        self._cancelled = True
        if process.poll() is not None:
            self._record_exit()
            return

        self._signal_group(signal.SIGTERM)
        deadline = time.monotonic() + max(grace_seconds, 0.0)
        while time.monotonic() < deadline:
            if process.poll() is not None:
                self._record_exit()
                return
            time.sleep(_REAP_INTERVAL_SECONDS)

        self._signal_group(signal.SIGKILL)
        process.wait()
        self._record_exit()

    def outcome(self) -> ChildProcessOutcome:
        """Describe the finished child, with both capture files hashed."""
        process = self._require_started()
        code = process.poll()
        if code is None:
            raise RunError(
                f"the {self._variant.value} evaluation child is still running",
                code=CHILD_STILL_RUNNING,
                details={"variant": self._variant.value},
            )
        self._record_exit()
        assert self._started_at is not None
        assert self._finished_at is not None

        return ChildProcessOutcome(
            variant=self._variant,
            argv_digest=self.argv_digest,
            exit_code=code,
            started_at=self._started_at,
            finished_at=self._finished_at,
            stdout_artifact=capture_artifact(self._stdout_path),
            stderr_artifact=capture_artifact(self._stderr_path),
            cancelled=self._cancelled,
        )

    # -- context management ----------------------------------------------

    def __enter__(self) -> Self:
        """Start the child and return it."""
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        """Stop a child that is still running, then release its descriptors."""
        if self._process is not None and self._process.poll() is None:
            self.terminate()
        self._close_streams()

    # -- internals ---------------------------------------------------------

    def _require_started(self) -> subprocess.Popen[bytes]:
        """Return the running process, or refuse."""
        if self._process is None:
            raise RunError(
                f"the {self._variant.value} evaluation child has not been started",
                code=CHILD_NOT_STARTED,
                details={"variant": self._variant.value},
            )
        return self._process

    def _open_capture(self, path: Path, *, stream: str) -> IO[bytes]:
        """Create one capture file, seeded with its provenance line."""
        ensure_private_directory(path.parent)
        header = (
            f"# techtree {self._variant.value} {stream}; "
            f"argv-digest {self.argv_digest}; "
            f"started {datetime.now(UTC).isoformat()}\n"
        )
        handle = _open_private(path)
        handle.write(header.encode("utf-8"))
        handle.flush()
        self._streams.append(handle)
        return handle

    def _close_streams(self) -> None:
        """Flush and release the capture descriptors this child opened."""
        while self._streams:
            handle = self._streams.pop()
            try:
                handle.flush()
                os.fsync(handle.fileno())
            except (OSError, ValueError):
                pass
            handle.close()

    def _record_exit(self) -> None:
        """Fix the finishing time once, and let go of the capture files."""
        if self._finished_at is not None:
            return
        self._finished_at = datetime.now(UTC)
        if self._started_monotonic is not None:
            self._elapsed_seconds = time.monotonic() - self._started_monotonic
        self._close_streams()

    def _signal_group(self, number: int) -> None:
        """Signal the child's whole process group, tolerating a race with exit."""
        process = self._require_started()
        try:
            os.killpg(os.getpgid(process.pid), number)
        except ProcessLookupError:
            # The child exited between the poll and the signal. Nothing to stop.
            return
        except PermissionError:
            # Not ours to signal as a group; fall back to the child itself.
            with contextlib.suppress(ProcessLookupError):
                process.send_signal(number)


def _open_private(path: Path) -> IO[bytes]:
    """Open a capture file for writing with private permissions."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    return os.fdopen(descriptor, "wb")


def _write_private(path: Path, data: bytes) -> None:
    """Write one whole private file and flush it to disk."""
    with _open_private(path) as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    fsync_directory(path.parent)
