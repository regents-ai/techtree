"""Where Techtree keeps its state. Spec sections 10.10 and 28.

The layout is derived from one root and nothing is created at import time, so
the tests check both: that every path hangs off the root a caller named, and
that resolving the layout touches no disk until asked.

``identities_dir`` gets its own test. Resolving the layout must not create it:
the local signing identity is made by ``techtree setup`` or by a run that needs
to sign, and :class:`~techtree.identity.store.IdentityStore` creates the
directory then. A layout that made it in advance would leave every machine
looking as though it held a key.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from techtree.canonical import sha256_digest_bytes
from techtree.errors import ValidationError
from techtree.paths import (
    APPLICATION_NAME,
    default_paths,
    ensure_path_layout,
    paths_from_root,
)

DIGEST = sha256_digest_bytes(b"engine")
DRAFT_ID = f"draft_{'a' * 32}"
RUN_ID = f"run_{'b' * 32}"


def test_every_path_hangs_off_the_root(tmp_path: Path) -> None:
    paths = paths_from_root(tmp_path)

    assert paths.root == tmp_path
    assert paths.config_file == tmp_path / "config.toml"
    assert paths.cache_dir == tmp_path / "cache"
    assert paths.drafts_dir == tmp_path / "drafts"
    assert paths.runs_dir == tmp_path / "runs"
    assert paths.engines_dir == tmp_path / "engines"
    assert paths.identities_dir == tmp_path / "identities"


def test_resolving_paths_creates_nothing(tmp_path: Path) -> None:
    root = tmp_path / "techtree"

    paths_from_root(root)

    assert not root.exists()


def test_default_paths_are_platform_resolved() -> None:
    paths = default_paths()

    assert APPLICATION_NAME in paths.root.parts
    assert paths.config_file.name == "config.toml"


def test_the_layout_is_created_privately(tmp_path: Path) -> None:
    paths = paths_from_root(tmp_path / "techtree")

    ensure_path_layout(paths)

    for directory in (
        paths.root,
        paths.cache_dir,
        paths.drafts_dir,
        paths.runs_dir,
        paths.engines_dir,
    ):
        assert directory.is_dir()
        assert directory.stat().st_mode & 0o777 == 0o700


def test_creating_the_layout_twice_is_harmless(tmp_path: Path) -> None:
    paths = paths_from_root(tmp_path / "techtree")
    ensure_path_layout(paths)

    ensure_path_layout(paths)

    assert paths.runs_dir.is_dir()


def test_the_identities_directory_is_not_part_of_the_layout(tmp_path: Path) -> None:
    """Spec section 7.5: the identity store creates it, when a key is made."""
    paths = paths_from_root(tmp_path / "techtree")

    ensure_path_layout(paths)

    assert not paths.identities_dir.exists()


def test_draft_and_run_directories_validate_their_identifiers(tmp_path: Path) -> None:
    paths = paths_from_root(tmp_path)

    assert paths.draft_dir(DRAFT_ID) == paths.drafts_dir / DRAFT_ID
    assert paths.run_dir(RUN_ID) == paths.runs_dir / RUN_ID


@pytest.mark.parametrize("value", ["draft_short", "../escape", RUN_ID])
def test_draft_directory_rejects_anything_but_a_draft_id(
    tmp_path: Path, value: str
) -> None:
    with pytest.raises(ValidationError):
        paths_from_root(tmp_path).draft_dir(value)


@pytest.mark.parametrize("value", ["run_short", "/absolute", DRAFT_ID])
def test_run_directory_rejects_anything_but_a_run_id(
    tmp_path: Path, value: str
) -> None:
    with pytest.raises(ValidationError):
        paths_from_root(tmp_path).run_dir(value)


def test_engine_directory_is_content_addressed_without_a_colon(
    tmp_path: Path,
) -> None:
    """A colon is legal on POSIX and not on Windows; the layout uses neither."""
    directory = paths_from_root(tmp_path).engine_dir(DIGEST)

    assert directory.name == DIGEST.replace(":", "-")
    assert ":" not in directory.name


def test_engine_directory_rejects_a_malformed_digest(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        paths_from_root(tmp_path).engine_dir("sha256:not-hex")


def test_paths_are_frozen(tmp_path: Path) -> None:
    paths = paths_from_root(tmp_path)

    with pytest.raises(AttributeError):
        paths.root = tmp_path / "elsewhere"  # type: ignore[misc]
