"""The one place forge work runs a command. ``docs/plan/repo2rlenv-local-lane.md``.

Everything the forge does outside the Techtree process — git, docker, uv, and
the Repo2RLEnv driver — goes through one callable with one shape, so a unit
test can hand the forge a stand-in that answers at the command boundary and
never starts a daemon, a clone, or a sync.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence

from techtree.errors import RunError

__all__ = ["CommandRunner", "run_command"]

#: How much of a timed-out command's last output its error keeps.
_OUTPUT_TAIL_CHARS = 8000

#: ``(argv, timeout_seconds) -> completed process``, output captured as text.
type CommandRunner = Callable[[Sequence[str], float], subprocess.CompletedProcess[str]]


def run_command(
    argv: Sequence[str], timeout: float
) -> subprocess.CompletedProcess[str]:
    """Run one command with the caller's environment and captured output.

    The caller's environment is passed through on purpose: docker needs its
    context and credentials store, uv its index and proxy settings, git its
    identity. None of the commands run here is the subject under evaluation.
    Output is read as UTF-8 and a byte that is not is replaced, since a
    container prints whatever its task makes it print. A command that runs
    out of time keeps the end of what it printed in the error.
    """
    try:
        return subprocess.run(
            list(argv),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as error:
        raise RunError(
            f"{argv[0]} did not finish within {timeout:.0f}s",
            code="forge_command_timeout",
            details={
                "argv0": str(argv[0]),
                "timeout_seconds": timeout,
                "stdout": _tail(error.stdout),
                "stderr": _tail(error.stderr),
            },
        ) from error
    except OSError as error:
        raise RunError(
            f"{argv[0]} could not be started: {error.strerror or error}",
            code="forge_command_unusable",
            details={"argv0": str(argv[0])},
        ) from error


def _tail(output: bytes | str | None) -> str:
    """The end of what a stopped command printed, as text."""
    if output is None:
        return ""
    text = output.decode("utf-8", "replace") if isinstance(output, bytes) else output
    return text[-_OUTPUT_TAIL_CHARS:]
