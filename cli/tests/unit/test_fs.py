"""Atomic writes, exclusive creation, and containment. Spec section 10.9.

Two properties are worth testing here, and both are about what somebody else
can observe.

A reader must never see a partly written file, so the atomic helpers are tested
by proving that a failure mid-write leaves the previous contents intact and no
temporary file behind.

An immutable artifact must never be silently replaced, so the exclusive helper
is tested by proving that the second write is refused as a conflict rather than
overwriting evidence.
"""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from techtree.errors import ConflictError, NotFoundError, ValidationError
from techtree.fs import (
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_text,
    ensure_private_directory,
    fsync_directory,
    open_exclusive,
    read_json,
    realpath_within,
    remove_tree,
)


def test_atomic_write_creates_missing_parents(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "nested" / "file.txt"

    atomic_write_text(target, "hello")

    assert target.read_text(encoding="utf-8") == "hello"


def test_atomic_write_replaces_existing_content(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    atomic_write_text(target, "first")

    atomic_write_text(target, "second")

    assert target.read_text(encoding="utf-8") == "second"


def test_atomic_write_leaves_no_temporary_file(tmp_path: Path) -> None:
    atomic_write_bytes(tmp_path / "file.bin", b"\x00\x01")

    assert [entry.name for entry in tmp_path.iterdir()] == ["file.bin"]


def test_a_failed_write_leaves_the_previous_contents(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    atomic_write_text(target, "original")

    class Unwritable:
        def __str__(self) -> str:
            raise RuntimeError("serialization failed")

    with pytest.raises(ValidationError):
        atomic_write_json(target, {"value": Unwritable()})

    assert target.read_text(encoding="utf-8") == "original"
    assert [entry.name for entry in tmp_path.iterdir()] == ["file.txt"]


def test_atomic_write_applies_owner_only_permissions(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"

    atomic_write_text(target, "secret-free but private")

    assert target.stat().st_mode & 0o777 == 0o600


def test_atomic_write_json_is_readable_and_terminated(tmp_path: Path) -> None:
    target = tmp_path / "file.json"

    atomic_write_json(target, {"b": 1, "a": 2})

    text = target.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert text.index('"a"') < text.index('"b"')
    assert json.loads(text) == {"a": 2, "b": 1}


def test_read_json_round_trips(tmp_path: Path) -> None:
    target = tmp_path / "file.json"
    payload: dict[str, Any] = {"nested": {"list": [1, 2, 3]}}
    atomic_write_json(target, payload)

    assert read_json(target) == payload


def test_read_json_reports_a_missing_file_as_not_found(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError, match="no such file"):
        read_json(tmp_path / "absent.json")


def test_read_json_reports_malformed_json_with_a_line_number(tmp_path: Path) -> None:
    target = tmp_path / "file.json"
    target.write_text("{\n  broken\n}\n", encoding="utf-8")

    with pytest.raises(ValidationError) as caught:
        read_json(target)

    assert caught.value.details["line"] == 2


def test_read_json_reports_invalid_utf8(tmp_path: Path) -> None:
    target = tmp_path / "file.json"
    target.write_bytes(b"\xff\xfe not utf-8")

    with pytest.raises(ValidationError, match="not valid UTF-8"):
        read_json(target)


# ---------------------------------------------------------------------------
# Exclusive creation
# ---------------------------------------------------------------------------


def test_open_exclusive_creates_a_private_file(tmp_path: Path) -> None:
    target = tmp_path / "receipt.json"

    with open_exclusive(target) as stream:
        stream.write(b"{}")

    assert target.read_bytes() == b"{}"
    assert target.stat().st_mode & 0o777 == 0o600


def test_open_exclusive_refuses_to_replace_an_artifact(tmp_path: Path) -> None:
    target = tmp_path / "receipt.json"
    with open_exclusive(target) as stream:
        stream.write(b"{}")

    with pytest.raises(ConflictError, match="immutable artifact"):
        open_exclusive(target)

    assert target.read_bytes() == b"{}"


def test_open_exclusive_does_not_follow_a_symlink(tmp_path: Path) -> None:
    victim = tmp_path / "victim.json"
    victim.write_text("original", encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(victim)

    # ``O_CREAT | O_EXCL`` fails on a symlink itself, so the link is reported
    # as an existing artifact and the file it points at is never touched.
    with pytest.raises(ConflictError):
        open_exclusive(link)

    assert victim.read_text(encoding="utf-8") == "original"


# ---------------------------------------------------------------------------
# Directories and containment
# ---------------------------------------------------------------------------


def test_ensure_private_directory_is_owner_only(tmp_path: Path) -> None:
    target = tmp_path / "runs"

    ensure_private_directory(target)

    assert target.is_dir()
    assert target.stat().st_mode & 0o777 == 0o700


def test_ensure_private_directory_is_repeatable(tmp_path: Path) -> None:
    target = tmp_path / "runs"
    ensure_private_directory(target)

    ensure_private_directory(target)

    assert target.is_dir()


def test_ensure_private_directory_refuses_a_symlink(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    link = tmp_path / "runs"
    link.symlink_to(elsewhere)

    with pytest.raises(ValidationError, match="symlinked directory"):
        ensure_private_directory(link)


def test_fsync_directory_tolerates_a_missing_directory(tmp_path: Path) -> None:
    fsync_directory(tmp_path / "absent")


def test_realpath_within_accepts_a_contained_path(tmp_path: Path) -> None:
    inner = tmp_path / "runs" / "one"
    inner.mkdir(parents=True)

    assert realpath_within(inner, tmp_path) is True


def test_realpath_within_rejects_an_escaping_symlink(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "escape"
    link.symlink_to(outside)

    assert realpath_within(link, root) is False


def test_remove_tree_removes_a_directory(tmp_path: Path) -> None:
    target = tmp_path / "run"
    (target / "nested").mkdir(parents=True)
    (target / "nested" / "file.txt").write_text("data", encoding="utf-8")

    remove_tree(target)

    assert not target.exists()


def test_remove_tree_unlinks_a_symlink_without_following_it(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    link = tmp_path / "link"
    link.symlink_to(outside)

    remove_tree(link)

    assert not link.exists()
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_remove_tree_tolerates_an_absent_path(tmp_path: Path) -> None:
    remove_tree(tmp_path / "absent")


def test_remove_tree_removes_a_file(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("data", encoding="utf-8")

    remove_tree(target)

    assert not target.exists()


def test_written_files_are_flushed_to_disk(tmp_path: Path) -> None:
    """A reopened descriptor sees the bytes, not a buffered promise of them."""
    target = tmp_path / "file.bin"

    atomic_write_bytes(target, b"durable")

    descriptor = os.open(target, os.O_RDONLY)
    try:
        assert os.read(descriptor, 16) == b"durable"
    finally:
        os.close(descriptor)


# ---------------------------------------------------------------------------
# Nobody but the owner. WP11g S6.
# ---------------------------------------------------------------------------
#
# Techtree state is single-user, and it was single-user at the leaf only: the
# helpers chmod the directory the caller named and left every parent they had
# to invent at the process umask. Inside a Techtree home that was invisible,
# because `ensure_path_layout` had already made the ancestors 0700. It stopped
# being invisible the moment a caller passed a deeper path first.


def _modes_below(root: Path) -> dict[str, int]:
    """Return every path under a root and the permission bits it carries."""
    return {
        str(path.relative_to(root)): stat.S_IMODE(path.stat().st_mode)
        for path in sorted(root.rglob("*"))
    }


def _group_or_other_readable(root: Path) -> list[str]:
    """Return every path under a root that somebody else can see into."""
    return [
        name
        for name, mode in _modes_below(root).items()
        if mode & (stat.S_IRWXG | stat.S_IRWXO)
    ]


@pytest.fixture
def permissive_umask() -> Iterator[None]:
    """Run with the umask of somebody who has never thought about umasks.

    0o000 grants everything the mode asks for, which is what makes this a test
    of the modes Techtree chooses rather than a test of the umask that happened
    to be set when the suite ran.
    """
    previous = os.umask(0o000)
    try:
        yield
    finally:
        os.umask(previous)


@pytest.mark.usefixtures("permissive_umask")
def test_every_directory_a_private_tree_needs_is_private(tmp_path: Path) -> None:
    """Not just the leaf. The whole path to it."""
    root = tmp_path / "home"

    ensure_private_directory(root / "runs" / "run_x" / "taskset" / "validation")

    assert _modes_below(root) == {
        "runs": 0o700,
        "runs/run_x": 0o700,
        "runs/run_x/taskset": 0o700,
        "runs/run_x/taskset/validation": 0o700,
    }
    assert stat.S_IMODE(root.stat().st_mode) == 0o700


@pytest.mark.usefixtures("permissive_umask")
def test_an_atomic_write_does_not_leave_a_readable_path_behind_it(
    tmp_path: Path,
) -> None:
    """The write helper invents directories too, and they are nobody else's."""
    root = tmp_path / "home"

    atomic_write_bytes(root / "runs" / "run_x" / "proof" / "bundle.json", b"{}\n")

    assert _group_or_other_readable(root) == []
    assert _modes_below(root)["runs/run_x/proof/bundle.json"] == 0o600


@pytest.mark.usefixtures("permissive_umask")
def test_a_whole_created_tree_is_closed_to_everyone_else(tmp_path: Path) -> None:
    """The walking assertion: one tree, every node, no group or other bits."""
    root = tmp_path / "home"
    ensure_private_directory(root / "drafts" / "draft_x" / "skill" / "files")
    atomic_write_json(root / "config.toml", {"output_mode": "rich"})
    atomic_write_text(root / "runs" / "run_x" / "worker.log", "started\n")
    atomic_write_bytes(root / "identities" / "executor-private-key.bin", b"\x00" * 32)

    assert _group_or_other_readable(root) == []


@pytest.mark.usefixtures("permissive_umask")
def test_an_existing_directory_is_re_hardened_rather_than_accepted(
    tmp_path: Path,
) -> None:
    """A home somebody loosened by hand is tightened the next time it is used."""
    loosened = tmp_path / "home" / "runs"
    loosened.mkdir(parents=True)
    loosened.chmod(0o755)

    ensure_private_directory(loosened)

    assert stat.S_IMODE(loosened.stat().st_mode) == 0o700


def test_a_directory_that_already_exists_outside_is_left_at_its_own_mode(
    tmp_path: Path,
) -> None:
    """Only what the helper creates is hardened.

    The alternative — walking up and tightening whatever is above — would mean
    that writing one file into a directory somebody handed us could take away
    their own access to the directory containing it.
    """
    outer = tmp_path / "shared"
    outer.mkdir()
    outer.chmod(0o755)

    atomic_write_bytes(outer / "inner" / "file.bin", b"data")

    assert stat.S_IMODE(outer.stat().st_mode) == 0o755
    assert stat.S_IMODE((outer / "inner").stat().st_mode) == 0o700


def test_a_file_where_a_directory_should_be_is_still_an_error(
    tmp_path: Path,
) -> None:
    """The creation walk must not swallow the collision it used to report."""
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")

    with pytest.raises((FileExistsError, NotADirectoryError, ValidationError)):
        ensure_private_directory(blocker / "below")
