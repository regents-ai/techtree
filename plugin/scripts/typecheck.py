"""Type-check the plugin package, the tests, and this repository's tooling.

mypy identifies a package by its directory name, and `techtree-hermes` is not
a Python identifier. The package is therefore given an importable name through
a temporary symbolic link, checked under that name, and the link is discarded.
Nothing in the checkout is touched.

The tests and the scripts are checked from their own directories, where they
are ordinary top-level modules, exactly as pytest and the shell run them.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

PACKAGE_NAME = "techtree_hermes"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"
TESTS_ROOT = REPOSITORY_ROOT / "tests"


def main() -> int:
    """Run every mypy pass and return the first failing exit code."""
    with tempfile.TemporaryDirectory() as directory:
        link_root = Path(directory)
        (link_root / PACKAGE_NAME).symlink_to(REPOSITORY_ROOT, target_is_directory=True)

        results = [
            _mypy(
                ["-p", PACKAGE_NAME],
                cwd=REPOSITORY_ROOT,
                mypy_path=[link_root],
            ),
            _mypy(
                ["--explicit-package-bases", "."],
                cwd=SCRIPTS_ROOT,
                mypy_path=[SCRIPTS_ROOT],
            ),
            _mypy(
                ["--explicit-package-bases", "."],
                cwd=TESTS_ROOT,
                mypy_path=[link_root, TESTS_ROOT, SCRIPTS_ROOT],
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
