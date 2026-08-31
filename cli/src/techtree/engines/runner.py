"""Running one command inside the managed engine. Spec section 20.5.

Two rules shape every invocation.

*Absolute paths, never ``PATH``.* The pinned Verifiers build installs console
scripts under names as generic as ``validate`` and ``eval``
(``docs/verifiers-pin.md``, finding C3). Resolving those through the caller's
``PATH`` would let anything on the machine answer for the engine, so the engine
addresses its own executables by absolute path and the environment it runs them
in carries a ``PATH`` for the operating system's benefit, not for lookup.

*A minimal environment.* Model-free validation needs no provider credential,
and a subprocess that never receives one cannot leak one. The child gets
``PATH``, ``HOME``, and ``TMPDIR``, plus whatever the caller passes explicitly.
Everything else in the parent environment — API keys, tokens, cloud
credentials, the caller's Python configuration — is dropped.

The result of a run is data, not a decision. ``validate`` exits ``0`` even when
every task fails (``docs/verifiers-pin.md``, finding C2), so nothing here maps
an exit code onto a verdict; callers read the summary the engine wrote.
"""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from techtree.engines.registry import EngineRegistry
from techtree.errors import EngineError
from techtree.models.base import Digest

__all__ = ["INHERITED_ENVIRONMENT", "EngineProcessResult", "EngineRunner"]

#: The only variables an engine process inherits from its parent. ``PATH`` so
#: the child can find ordinary system tools, ``HOME`` because caches and
#: configuration hang off it, ``TMPDIR`` so scratch files land where the host
#: expects them.
INHERITED_ENVIRONMENT: Final[tuple[str, ...]] = ("PATH", "HOME", "TMPDIR")

#: Prefix of the variables a caller may add. Anything else has to be passed
#: deliberately by name, which keeps "just forward the environment" from being
#: the easy option.
_TECHTREE_PREFIX: Final = "TECHTREE_"


@dataclass(frozen=True)
class EngineProcessResult:
    """What one engine command did."""

    argv: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float


class EngineRunner:
    """Runs commands inside one installed engine."""

    def __init__(self, registry: EngineRegistry, digest: Digest) -> None:
        self._registry = registry
        self._digest = digest

    def run(
        self,
        executable: str,
        args: Sequence[str],
        *,
        timeout: float,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
    ) -> EngineProcessResult:
        """Run one console script from the engine environment."""
        return self._execute(
            [str(self._registry.executable(self._digest, executable)), *args],
            timeout=timeout,
            env=env,
            cwd=cwd,
        )

    def run_python_script(
        self,
        script: Path,
        args: Sequence[str],
        *,
        timeout: float,
        env: Mapping[str, str] | None = None,
    ) -> EngineProcessResult:
        """Run one Python file with the engine's own interpreter."""
        return self._execute(
            [str(self._registry.python(self._digest)), str(script), *args],
            timeout=timeout,
            env=env,
        )

    def _execute(
        self,
        argv: Sequence[str],
        *,
        timeout: float,
        env: Mapping[str, str] | None,
        cwd: Path | None = None,
    ) -> EngineProcessResult:
        program = Path(argv[0])
        if not program.is_file():
            raise EngineError(
                f"engine {self._digest} has no executable at {program}; "
                "install the engine again",
                code="engine_executable_missing",
                details={"digest": self._digest, "path": str(program)},
            )

        started = time.monotonic()
        try:
            completed = subprocess.run(
                list(argv),
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
                stdin=subprocess.DEVNULL,
                env=engine_environment(env),
                cwd=None if cwd is None else str(cwd),
            )
        except subprocess.TimeoutExpired as error:
            raise EngineError(
                f"engine command did not finish within {timeout:.0f}s: {program.name}",
                code="engine_command_timeout",
                details={"digest": self._digest, "timeout_seconds": timeout},
                retryable=True,
            ) from error
        except OSError as error:
            raise EngineError(
                f"engine command could not be started: {error.strerror or error}",
                code="engine_command_unusable",
                details={"digest": self._digest, "path": str(program)},
            ) from error

        return EngineProcessResult(
            argv=tuple(argv),
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_seconds=time.monotonic() - started,
        )


def engine_environment(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Build the minimal environment an engine process runs in."""
    environment = {
        name: os.environ[name] for name in INHERITED_ENVIRONMENT if name in os.environ
    }

    for name, value in (extra or {}).items():
        if not name.startswith(_TECHTREE_PREFIX) and name not in INHERITED_ENVIRONMENT:
            raise EngineError(
                f"{name} cannot be passed to an engine process; only "
                f"{_TECHTREE_PREFIX}* variables and "
                f"{', '.join(INHERITED_ENVIRONMENT)} are allowed",
                code="engine_environment_rejected",
                details={"variable": name},
            )
        environment[name] = value

    return environment
