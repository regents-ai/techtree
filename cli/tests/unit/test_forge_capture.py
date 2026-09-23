"""What a subject left, recorded before grading (U4b, AE6, R38).

The tests hold what the manifest promises: a binary the subject added, a
structured text it changed and a file it deleted are all recorded, each with
its type, size and digest, and the bytes of every regular file it left are
kept beside the manifest; a link out of the working directory, however many
links it passes through, one of the image's own turned outward by what the
subject changed, one whose way runs through a name not recorded
there exactly (a disk that ignores case would match it to something else),
and one too long to follow, an entry that is not a file, folder or link, an
output too large to keep, a required output the subject did not leave and a
read or a copy left incomplete are each an explicit failure, and none of them
stops the capture or makes an entry it could not read look deleted. Real
files on disk; no Docker.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from techtree.canonical import sha256_digest_bytes
from techtree.forge.capture import (
    MANIFEST_FILENAME,
    OUTPUT_LIMITS,
    capture_outputs,
    take_snapshot,
)
from techtree.forge.models import ForgeOutputLimits, ForgeOutputManifest

WORK_DIR = "/app"
BINARY = bytes(range(256)) * 4


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A working directory as its image left it."""
    root = tmp_path / "app"
    root.mkdir()
    (root / "ledger.json").write_text('{"total": 3}\n', encoding="utf-8")
    (root / "obsolete.txt").write_text("old\n", encoding="utf-8")
    (root / "notes.md").write_text("untouched\n", encoding="utf-8")
    return root


def manifest(destination: Path) -> ForgeOutputManifest:
    return ForgeOutputManifest.model_validate_json(
        (destination / MANIFEST_FILENAME).read_bytes()
    )


def test_a_binary_added_a_text_changed_and_a_file_deleted_are_all_recorded(
    root: Path, tmp_path: Path
) -> None:
    before = take_snapshot(root, OUTPUT_LIMITS)
    (root / "out").mkdir()
    (root / "out" / "chart.bin").write_bytes(BINARY)
    (root / "ledger.json").write_text('{"total": 5}\n', encoding="utf-8")
    (root / "obsolete.txt").unlink()
    destination = tmp_path / "outputs"

    outputs = capture_outputs(
        root,
        before,
        work_dir=WORK_DIR,
        artifacts=["/app/out/chart.bin"],
        limits=OUTPUT_LIMITS,
        destination=destination,
    )

    written = manifest(destination)
    changes = {change.path: change for change in written.changes}
    assert sorted(changes) == ["ledger.json", "obsolete.txt", "out", "out/chart.bin"]
    added = changes["out/chart.bin"]
    assert added.change == "added" and added.before is None and added.kept
    assert added.after is not None and added.after.kind == "file"
    assert added.after.size == len(BINARY)
    assert added.after.digest == sha256_digest_bytes(BINARY)
    assert changes["out"].change == "added"
    assert changes["out"].after is not None
    assert changes["out"].after.kind == "directory"
    changed = changes["ledger.json"]
    assert changed.change == "modified" and changed.kept
    assert changed.before is not None and changed.after is not None
    assert changed.before.digest == sha256_digest_bytes(b'{"total": 3}\n')
    assert changed.after.digest == sha256_digest_bytes(b'{"total": 5}\n')
    deleted = changes["obsolete.txt"]
    assert deleted.change == "deleted" and deleted.after is None
    assert not deleted.kept
    assert (destination / "files" / "out" / "chart.bin").read_bytes() == BINARY
    assert (destination / "files" / "ledger.json").read_bytes() == b'{"total": 5}\n'
    assert not (destination / "files" / "notes.md").exists()
    assert written.failures == [] and written.limits == OUTPUT_LIMITS
    assert written.work_dir == WORK_DIR
    assert (outputs.added, outputs.modified, outputs.deleted) == (2, 1, 1)
    assert outputs.kept_bytes == len(BINARY) + len(b'{"total": 5}\n')
    assert outputs.manifest_digest == sha256_digest_bytes(
        (destination / MANIFEST_FILENAME).read_bytes()
    )


def test_a_link_out_of_the_directory_and_an_oversized_output_are_failures(
    root: Path, tmp_path: Path
) -> None:
    limits = ForgeOutputLimits(entries=100, checked_bytes=1_000_000, kept_bytes=64)
    before = take_snapshot(root, OUTPUT_LIMITS)
    (root / "result.txt").write_text("5\n", encoding="utf-8")
    (root / "large.bin").write_bytes(b"x" * 100)
    (root / "passwd").symlink_to("/etc/passwd")
    (root / "up").symlink_to("../secret")
    (root / "same").symlink_to("result.txt")
    (root / "sub").mkdir()
    (root / "sub" / "back").symlink_to("../ledger.json")
    destination = tmp_path / "outputs"

    outputs = capture_outputs(
        root,
        before,
        work_dir=WORK_DIR,
        artifacts=["/app/result.txt"],
        limits=limits,
        destination=destination,
    )

    failures = {(failure.kind, failure.path) for failure in outputs.failures}
    assert failures == {
        ("escaping_link", "passwd"),
        ("escaping_link", "up"),
        ("output_too_large", "large.bin"),
    }
    written = manifest(destination)
    assert written.failures == outputs.failures
    changes = {change.path: change for change in written.changes}
    assert changes["large.bin"].change == "added" and not changes["large.bin"].kept
    assert changes["passwd"].after is not None
    assert changes["passwd"].after.target == "/etc/passwd"
    assert not (destination / "files" / "large.bin").exists()
    assert (destination / "files" / "result.txt").read_bytes() == b"5\n"


def test_a_missing_required_output_and_an_incomplete_read_are_failures(
    root: Path, tmp_path: Path
) -> None:
    before = take_snapshot(root, OUTPUT_LIMITS)
    (root / "sealed.txt").write_text("private\n", encoding="utf-8")
    (root / "sealed.txt").chmod(0)
    if os.access(root / "sealed.txt", os.R_OK):
        pytest.skip("this user reads files whatever their mode")

    outputs = capture_outputs(
        root,
        before,
        work_dir=WORK_DIR,
        artifacts=["/app/result.txt"],
        limits=OUTPUT_LIMITS,
        destination=tmp_path / "outputs",
    )

    assert {(failure.kind, failure.path) for failure in outputs.failures} == {
        ("artifact_missing", "result.txt"),
        ("capture_incomplete", "sealed.txt"),
    }

    (root / "sealed.txt").chmod(0o600)
    bounded = capture_outputs(
        root,
        before,
        work_dir=WORK_DIR,
        artifacts=[],
        limits=ForgeOutputLimits(entries=2, checked_bytes=1_000_000, kept_bytes=1_000),
        destination=tmp_path / "bounded",
    )

    [incomplete] = [
        failure
        for failure in bounded.failures
        if failure.kind == "capture_incomplete" and failure.path is None
    ]
    assert "more than 2 entries" in incomplete.detail
    stored = json.loads((tmp_path / "bounded" / MANIFEST_FILENAME).read_bytes())
    assert stored["limits"]["entries"] == 2
    assert not any(change["change"] == "deleted" for change in stored["changes"])


def test_a_link_that_may_leave_through_other_links_is_a_failure(
    root: Path, tmp_path: Path
) -> None:
    # The image's own link out of the directory is the image's; the subject's
    # links are followed through it, and through each other, as the kernel
    # would follow them.
    (root / "python").symlink_to("/usr/bin/python3")
    (root / "sub").mkdir()
    (root / "a").mkdir()
    (root / "shipped").symlink_to("a/../notes.md")
    before = take_snapshot(root, OUTPUT_LIMITS)
    # The image's link through a/.. stays inside until a, itself a link that
    # stays inside, makes a/.. the folder above.
    (root / "a").rmdir()
    (root / "a").symlink_to(".")
    (root / "d").symlink_to("/app")
    (root / "result.txt").symlink_to("d/../tests/expected.json")
    (root / "up").symlink_to("..")
    (root / "e").symlink_to("up/etc")
    (root / "run").symlink_to("python")
    (root / "loop").symlink_to("loop")
    (root / "home").symlink_to("../app/ledger.json")
    (root / "inside").symlink_to("d/notes.md")
    (root / "absolute").symlink_to("/app/ledger.json")
    (root / "b").symlink_to(".")
    (root / "folded").symlink_to("B/B/B/../../../etc/passwd")
    (root / "ghost").symlink_to("missing.txt")
    (root / "sub" / "near").symlink_to("../notes.md")
    # Twenty links, each walking into sub and back 140 times: only the last
    # few can be followed within the bound on steps.
    for hop in range(20):
        onward = f"hop{hop + 1}" if hop < 19 else "notes.md"
        (root / f"hop{hop}").symlink_to("sub/../" * 140 + onward)

    outputs = capture_outputs(
        root,
        before,
        work_dir=WORK_DIR,
        artifacts=["/app/result.txt"],
        limits=OUTPUT_LIMITS,
        destination=tmp_path / "outputs",
    )

    refused = {failure.path for failure in outputs.failures}
    assert {failure.kind for failure in outputs.failures} == {"escaping_link"}
    assert refused - {f"hop{hop}" for hop in range(20)} == {
        "result.txt",
        "up",
        "e",
        "run",
        "loop",
        "folded",
        "ghost",
        "shipped",
    }
    assert "hop0" in refused and "hop19" not in refused


def test_what_cannot_be_taken_is_a_failure_and_the_capture_still_ends(
    root: Path, tmp_path: Path
) -> None:
    (root / "data").mkdir()
    (root / "data" / "kept.txt").write_text("kept\n", encoding="utf-8")
    before = take_snapshot(root, OUTPUT_LIMITS)
    long_name = "n" * 250
    (root / long_name).write_text("a long name\n", encoding="utf-8")
    (root / " ").write_text("a blank name\n", encoding="utf-8")
    os.mkfifo(root / "result.txt")
    (root / "extra.txt").write_text("extra\n", encoding="utf-8")
    (root / "data").chmod(0)
    destination = tmp_path / "outputs"
    (destination / "files").mkdir(parents=True)
    (destination / "files" / "extra.txt").write_text("in the way\n", encoding="utf-8")
    try:
        if os.access(root / "data", os.R_OK):
            pytest.skip("this user reads folders whatever their mode")
        outputs = capture_outputs(
            root,
            before,
            work_dir=WORK_DIR,
            artifacts=["/app/result.txt"],
            limits=OUTPUT_LIMITS,
            destination=destination,
        )
    finally:
        (root / "data").chmod(0o700)

    assert {(failure.kind, failure.path) for failure in outputs.failures} == {
        ("special_entry", "result.txt"),
        ("capture_incomplete", "data"),
        ("capture_incomplete", "extra.txt"),
    }
    written = manifest(destination)
    assert "data/kept.txt" not in {change.path for change in written.changes}
    assert (destination / "files" / long_name).read_text() == "a long name\n"
    assert (destination / "files" / " ").read_text() == "a blank name\n"
