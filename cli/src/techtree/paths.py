"""Where Techtree keeps its local state. Spec sections 10.10 and 28.

One root directory holds everything: the settings file, the download cache,
submission drafts, runs, and installed managed engines. Resolving that root
through ``platformdirs`` means the location follows each platform's own
convention instead of hard-coding a Unix dotfile path.

Nothing here touches the filesystem at import time. Directories are created
only when :func:`ensure_path_layout` is called, which keeps ``import techtree``
free of side effects.

``identities_dir`` is resolved but never created. Decisions document 0001
forbids device keys and identity storage through WP5, so the path exists as a
settled location and the directory does not exist at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_path

from techtree.canonical import validate_digest
from techtree.fs import ensure_private_directory
from techtree.ids import validate_id
from techtree.models.base import Digest

__all__ = [
    "APPLICATION_NAME",
    "TechtreePaths",
    "default_paths",
    "ensure_path_layout",
    "paths_from_root",
]

APPLICATION_NAME = "techtree"


@dataclass(frozen=True)
class TechtreePaths:
    """Every directory and file Techtree owns, derived from one root."""

    root: Path
    config_file: Path
    cache_dir: Path
    drafts_dir: Path
    runs_dir: Path
    engines_dir: Path
    identities_dir: Path

    def draft_dir(self, draft_id: str) -> Path:
        """Return the directory holding one submission draft."""
        return self.drafts_dir / validate_id(draft_id, "draft")

    def run_dir(self, run_id: str) -> Path:
        """Return the directory holding one run."""
        return self.runs_dir / validate_id(run_id, "run")

    def engine_dir(self, digest: Digest) -> Path:
        """Return the install directory for one managed engine bundle.

        The digest's colon becomes a dash: ``sha256-<hex>``. A colon is legal
        on POSIX but not on Windows, and an engine install is content-addressed
        on every platform.
        """
        return self.engines_dir / validate_digest(digest).replace(":", "-", 1)


def paths_from_root(root: Path) -> TechtreePaths:
    """Construct deterministic test paths."""
    resolved = Path(root)
    return TechtreePaths(
        root=resolved,
        config_file=resolved / "config.toml",
        cache_dir=resolved / "cache",
        drafts_dir=resolved / "drafts",
        runs_dir=resolved / "runs",
        engines_dir=resolved / "engines",
        identities_dir=resolved / "identities",
    )


def default_paths() -> TechtreePaths:
    """Resolve platform paths through platformdirs."""
    return paths_from_root(
        user_data_path(appname=APPLICATION_NAME, appauthor=False, roaming=False)
    )


def ensure_path_layout(paths: TechtreePaths) -> None:
    """Create top-level private directories."""
    for directory in (
        paths.root,
        paths.cache_dir,
        paths.drafts_dir,
        paths.runs_dir,
        paths.engines_dir,
    ):
        ensure_private_directory(directory)
