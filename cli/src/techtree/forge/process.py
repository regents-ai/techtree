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

#: ``(argv, timeout_seconds) -> completed process``, output captured as text.
type CommandRunner = Callable[[Sequence[str], float], subprocess.CompletedProcess[str]]


def run_command(
    argv: Sequence[str], timeout: float
) -> subprocess.CompletedProcess[str]:
    """Run one command with the caller's environment and captured output.

    The caller's environment is passed through on purpose: docker needs its
    context and credentials store, uv its index and proxy settings, git its
    identity. None of the commands run here is the subject under evaluation.
    """
    try:
        return subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as error:
        raise RunError(
            f"{argv[0]} did not finish within {timeout:.0f}s",
            code="forge_command_timeout",
            details={"argv0": str(argv[0]), "timeout_seconds": timeout},
        ) from error
    except OSError as error:
        raise RunError(
            f"{argv[0]} could not be started: {error.strerror or error}",
            code="forge_command_unusable",
            details={"argv0": str(argv[0])},
        ) from error
