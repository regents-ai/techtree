"""The managed Repo2RLEnv environment. ``docs/plan/repo2rlenv-local-lane.md``.

Repo2RLEnv is not a dependency of Techtree. It is a pinned project shipped
under ``techtree/resources/forge`` — a ``pyproject.toml``, its ``uv.lock``, and
the driver script — that is copied into the Techtree home and built with
``uv sync --frozen`` the first time a forge build needs it. The lock is the
whole resolution; nothing is resolved on the person's machine.

The install is content-addressed the way an engine install is: ``installed.json``
records the digest of the shipped files, and a home whose recorded digest
matches the files this build ships reuses the environment. A different digest
means a different Repo2RLEnv pin, and the environment is built again.
"""

from __future__ import annotations

from importlib.resources import files as resource_files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Final

from techtree.canonical import digest_object
from techtree.engines.bundle import content_manifest, enumerate_bundle_files
from techtree.errors import EngineError, PrerequisiteError
from techtree.forge.process import CommandRunner
from techtree.fs import (
    atomic_write_json,
    ensure_private_directory,
    read_json,
    remove_tree,
)
from techtree.models.base import Digest
from techtree.paths import TechtreePaths

__all__ = [
    "FORGE_PYTHON_VERSION",
    "REPO2RLENV_VERSION",
    "SYNC_TIMEOUT_SECONDS",
    "ForgeEnvironment",
    "embedded_forge_root",
    "ensure_forge_environment",
    "forge_bundle_digest",
]

#: The pin the shipped lock resolves. Stated here so a build record can name it
#: without importing the environment it describes.
REPO2RLENV_VERSION: Final = "0.8.8"
FORGE_PYTHON_VERSION: Final = "3.12"
SYNC_TIMEOUT_SECONDS: Final = 1800.0

_MANIFEST_SCHEMA: Final = "techtree.forge-bundle-manifest.v1"
_INSTALLED_SCHEMA: Final = "techtree.forge-installed.v1"
_INSTALLED_FILENAME: Final = "installed.json"
_DRIVER: Final = "tools/generate_commit_runtime.py"


class ForgeEnvironment:
    """A built Repo2RLEnv environment and the driver inside it."""

    def __init__(self, root: Path) -> None:
        self.root = root

    @property
    def python(self) -> Path:
        return self.root / ".venv" / "bin" / "python"

    @property
    def driver(self) -> Path:
        return self.root / _DRIVER


def embedded_forge_root() -> Traversable:
    """Return the shipped forge project."""
    return resource_files("techtree") / "resources" / "forge"


def forge_bundle_digest(root: Traversable) -> Digest:
    """Return the digest of the shipped forge project's files."""
    return digest_object(
        content_manifest(_MANIFEST_SCHEMA, enumerate_bundle_files(root))
    )


def ensure_forge_environment(
    paths: TechtreePaths, run: CommandRunner, uv_executable: Path
) -> ForgeEnvironment:
    """Return the built environment, building it when the home has none."""
    root = embedded_forge_root()
    digest = forge_bundle_digest(root)
    destination = paths.forge_env_dir
    environment = ForgeEnvironment(destination)

    if _installed_digest(destination) == digest and environment.python.is_file():
        return environment

    remove_tree(destination)
    ensure_private_directory(destination)
    for entry in enumerate_bundle_files(root):
        target = destination / entry.relative_path
        ensure_private_directory(target.parent)
        source: Traversable = root
        for segment in entry.relative_path.split("/"):
            source = source / segment
        target.write_bytes(source.read_bytes())

    completed = run(
        [
            str(uv_executable),
            "sync",
            "--frozen",
            "--project",
            str(destination),
            "--python",
            FORGE_PYTHON_VERSION,
        ],
        SYNC_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        remove_tree(destination)
        raise EngineError(
            "building the Repo2RLEnv environment failed: "
            f"{completed.stderr.strip()[-2000:]}",
            code="forge_environment_sync_failed",
            details={"exit_code": completed.returncode},
        )
    if not environment.python.is_file():
        remove_tree(destination)
        raise PrerequisiteError(
            f"uv sync finished but left no interpreter at {environment.python}",
            code="forge_environment_incomplete",
            details={"path": str(destination)},
        )

    atomic_write_json(
        destination / _INSTALLED_FILENAME,
        {
            "schema_version": _INSTALLED_SCHEMA,
            "bundle_digest": digest,
            "repo2rlenv_version": REPO2RLENV_VERSION,
        },
    )
    return environment


def _installed_digest(destination: Path) -> Digest | None:
    """Return the digest a home's environment was built from, if it says."""
    marker = destination / _INSTALLED_FILENAME
    if not marker.is_file():
        return None
    document = read_json(marker)
    if not isinstance(document, dict):
        return None
    recorded = document.get("bundle_digest")
    return recorded if isinstance(recorded, str) else None
