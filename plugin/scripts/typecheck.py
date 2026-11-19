"""Type-check the Hermes plugin's scripts.

They import the plugin package, and mypy identifies a package by its directory
name, which is not the Python package name the scripts use. The plugin directory
is given that name through a temporary symbolic link, the pass runs against
that name, and the link is discarded. Nothing in the plugin is touched.

The plugin package itself is checked by `make typecheck`. What is checked here
is the scripts, from their own directory, where they are ordinary top-level
modules, exactly as the Makefile runs them.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from _plugin_package import PACKAGE_NAME, PLUGIN_ROOT

TOOLING_ROOT = PLUGIN_ROOT / "scripts"


def main() -> int:
    """Run the mypy pass and return its exit code."""
    with tempfile.TemporaryDirectory() as directory:
        link_root = Path(directory)
        (link_root / PACKAGE_NAME).symlink_to(PLUGIN_ROOT, target_is_directory=True)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "mypy",
                "--namespace-packages",
                "--explicit-package-bases",
                ".",
            ],
            cwd=TOOLING_ROOT,
            env={
                **os.environ,
                "MYPYPATH": os.pathsep.join([str(link_root), str(TOOLING_ROOT)]),
            },
            check=False,
        )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
