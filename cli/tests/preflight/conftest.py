"""One pinned Verifiers environment, shared by every preflight module.

Building the engine environment is the slow part of the preflight, and there
are now two suites that need it: PI0's ``validate`` contract and WP6a's ``eval``
contract. A session-scoped fixture means the pin is installed once per run and
both suites answer against the same interpreter, which is also the only way the
two sets of findings can be said to describe one engine.

Each suite installs its own fixture package on top, because a fixture package
is part of what that suite is proving.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from engine_environment import (
    ENGINE_PYTHON_ENV,
    VERIFIERS_PIN,
    VERIFIERS_REPO,
    check_engine_command,
    installed_pin,
)


@pytest.fixture(scope="session")
def pinned_engine_python(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """An interpreter holding exactly the pinned Verifiers commit.

    The pin is read back from the installed distribution's own VCS metadata, so
    a stale or wrong environment fails loudly rather than silently proving the
    wrong thing.
    """
    supplied = os.environ.get(ENGINE_PYTHON_ENV)
    if supplied:
        # Not resolve(): a venv's bin/python is a symlink to the base
        # interpreter, and following it would drop the venv's site-packages.
        python = Path(supplied).expanduser().absolute()
        if not python.exists():
            pytest.fail(f"{ENGINE_PYTHON_ENV}={supplied} does not exist")
    else:
        venv = tmp_path_factory.mktemp("verifiers-engine") / ".venv"
        check_engine_command("uv", "venv", "--python", "3.12", venv)
        python = venv / "bin" / "python"
        check_engine_command(
            "uv",
            "pip",
            "install",
            "--python",
            python,
            f"verifiers @ git+{VERIFIERS_REPO}@{VERIFIERS_PIN}",
        )

    recorded = installed_pin(python)
    vcs = recorded.get("vcs_info")
    commit = vcs.get("commit_id") if isinstance(vcs, dict) else None
    assert commit == VERIFIERS_PIN, (
        f"engine venv does not hold the pin {VERIFIERS_PIN}: {recorded}"
    )
    return python
