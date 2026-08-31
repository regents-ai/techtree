"""Building and addressing the pinned Verifiers environment.

The preflight suites run commands against a real installation of the pinned
commit, so they all need the same three things: a way to run a command and read
everything it produced, a way to install a fixture package into the
environment, and a way to prove afterwards that the environment really holds
the pin rather than whatever happened to be lying around.

``conftest.py`` turns these into the session fixture both suites share.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

VERIFIERS_REPO = "https://github.com/PrimeIntellect-ai/verifiers"
VERIFIERS_PIN = "b2e4e8157783b2c0dffc7821044c87f29f1c3ccf"
"""Binding (docs/decisions/0001). Never bump this here; a bump is its own ticket."""

ENGINE_PYTHON_ENV = "TECHTREE_PREFLIGHT_ENGINE_PYTHON"


def run_engine_command(
    *argv: str | Path,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one command and return its complete result, failure included."""
    return subprocess.run(
        [str(argument) for argument in argv],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def check_engine_command(
    *argv: str | Path,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> str:
    """Run one command that must succeed and return its standard output."""
    result = run_engine_command(*argv, cwd=cwd, env=env)
    if result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): "
            f"{' '.join(str(argument) for argument in argv)}\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        )
    return result.stdout


def install_fixture_package(python: Path, distribution: str, source: Path) -> None:
    """Install one fixture package into the engine environment.

    Always a reinstall: a supplied environment may hold a stale build, and a
    preflight that proved something about last week's fixture has proved
    nothing at all.
    """
    check_engine_command(
        "uv",
        "pip",
        "install",
        "--python",
        python,
        "--reinstall-package",
        distribution,
        source,
    )


def installed_pin(python: Path) -> dict[str, object]:
    """The VCS metadata pip or uv recorded for the installed git build."""
    source = (
        "import json;"
        "from importlib.metadata import distribution;"
        "print(distribution('verifiers').read_text('direct_url.json') or '{}')"
    )
    document = json.loads(check_engine_command(python, "-c", source).strip())
    assert isinstance(document, dict)
    return document
