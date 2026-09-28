"""Type-check the Hermes plugin's tests and the scripts that run them.

Both import the plugin package, and mypy identifies a package by its directory
name, which is not the Python package name the tests use. The plugin directory
is given that name through a temporary symbolic link, the passes run against
that name, and the link is discarded. Nothing in the plugin is touched.

The plugin package itself is checked by `make typecheck`. What is checked here
is the tests and the scripts, each from its own directory, where they are
ordinary top-level modules, exactly as pytest and the Makefile run them.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from _plugin_package import PACKAGE_NAME, PLUGIN_ROOT

TOOLING_ROOT = PLUGIN_ROOT / "scripts"
TESTS_ROOT = PLUGIN_ROOT / "tests"


def main() -> int:
    """Run every mypy pass and return the first failing exit code."""
    with tempfile.TemporaryDirectory() as directory:
        link_root = Path(directory)
        (link_root / PACKAGE_NAME).symlink_to(PLUGIN_ROOT, target_is_directory=True)

        results = [
            _mypy(
                ["--explicit-package-bases", "."],
                cwd=TOOLING_ROOT,
                mypy_path=[link_root, TOOLING_ROOT],
            ),
            _mypy(
                ["--explicit-package-bases", "."],
                cwd=TESTS_ROOT,
                mypy_path=[link_root, TESTS_ROOT, TOOLING_ROOT],
            ),
        ]
    return next((result for result in results if result != 0), 0)


def _mypy(arguments: list[str], *, cwd: Path, mypy_path: list[Path]) -> int:
    completed = subprocess.run(
        [sys.executable, "-m", "mypy", "--namespace-packages", *arguments],
        cwd=cwd,
        env={
            **os.environ,
            "MYPYPATH": os.pathsep.join(str(path) for path in mypy_path),
        },
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
