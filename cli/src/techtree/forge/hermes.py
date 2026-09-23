"""The person's own Hermes, run once and read back.

Every forge step that calls a model does it through the person's Hermes: the
planner, the creator and each run attempt. This is what they share: the
version Hermes prints for itself, one supervised Hermes process that is
interrupted at its deadline so it can still write its usage report, and that
usage report read exactly as Hermes wrote it.
"""

from __future__ import annotations

import json
import re
import signal
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Final

from pydantic import ValidationError as ModelValidationError

from techtree.errors import PrerequisiteError, RunError
from techtree.forge.models import ForgeUsage
from techtree.forge.process import run_command

__all__ = [
    "AgentLauncher",
    "AgentOutcome",
    "hermes_version",
    "launch_agent",
    "read_usage",
    "supervise_hermes",
]

#: The Hermes version banner: ``Hermes Agent v0.21.3 (2026.9.14) · upstream 6d712cf8``.
#: All of it is the version: Hermes updates from its upstream without changing
#: the number, and only the build date and upstream commit tell two apart.
_VERSION_BANNER: Final = re.compile(r"^Hermes Agent v(?P<version>\S.*?)\s*$")
_VERSION_TIMEOUT_SECONDS: Final = 30.0
#: After an interrupt Hermes writes its usage report and exits; then it is killed.
_INTERRUPT_GRACE_SECONDS: Final = 30.0
_USAGE_KEYS: Final = (
    "model",
    "provider",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "api_calls",
    "estimated_cost_usd",
    "cost_status",
    "cost_source",
    "completed",
    "failed",
    "failure",
)


@dataclass(frozen=True)
class AgentOutcome:
    """What one Hermes process did."""

    exit_code: int | None
    timed_out: bool
    seconds: float


type AgentLauncher = Callable[
    [list[str], dict[str, str], Path, Path, float], AgentOutcome
]


def launch_agent(
    argv: list[str], env: dict[str, str], cwd: Path, log: Path, timeout: float
) -> AgentOutcome:
    """Run Hermes once, its output to ``log``, and stop it at ``timeout``."""
    with log.open("wb") as output:
        return supervise_hermes(
            argv, env, cwd, stdout=output, stderr=subprocess.STDOUT, timeout=timeout
        )


def supervise_hermes(
    argv: list[str],
    env: dict[str, str],
    cwd: Path,
    *,
    stdout: IO[bytes],
    stderr: IO[bytes] | int,
    timeout: float,
) -> AgentOutcome:
    """Start Hermes and wait for it, stopping it at ``timeout`` or on Ctrl-C.

    Hermes is interrupted first so it can write its usage report, and killed
    only if it does not exit in time. A Ctrl-C is passed on and raised again
    once Hermes has gone.
    """
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
        )
    except OSError as error:
        raise RunError(
            f"{argv[0]} could not be started: {error.strerror or error}",
            code="hermes_unusable",
            details={"executable": argv[0]},
        ) from error
    try:
        exit_code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _stop(process)
        return AgentOutcome(
            exit_code=None, timed_out=True, seconds=time.monotonic() - started
        )
    except KeyboardInterrupt:
        _stop(process)
        raise
    return AgentOutcome(
        exit_code=exit_code, timed_out=False, seconds=time.monotonic() - started
    )


def _stop(process: subprocess.Popen[bytes]) -> None:
    process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=_INTERRUPT_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def read_usage(usage_file: Path) -> ForgeUsage | None:
    """Read Hermes' usage report as it reported it, or nothing."""
    try:
        loaded = json.loads(usage_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(loaded, dict):
        return None
    try:
        return ForgeUsage.model_validate({key: loaded.get(key) for key in _USAGE_KEYS})
    except ModelValidationError:
        return None


def hermes_version(executable: Path) -> str:
    """Return the version the Hermes at ``executable`` prints for itself."""
    completed = run_command([str(executable), "--version"], _VERSION_TIMEOUT_SECONDS)
    first_line = completed.stdout.splitlines()[0] if completed.stdout else ""
    match = _VERSION_BANNER.match(first_line)
    if completed.returncode != 0 or match is None:
        raise PrerequisiteError(
            f"{executable} did not report a Hermes Agent version",
            code="hermes_version_unreadable",
            details={
                "executable": str(executable),
                "exit_code": completed.returncode,
                "first_line": first_line,
            },
        )
    return match.group("version")
