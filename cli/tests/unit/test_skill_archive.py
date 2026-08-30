"""The deterministic snapshot archive. Spec sections 15.3 and 26 WP2.

An archive digest is a promise: the same files produce the same bytes, on any
machine, in any order, whatever the source directory's timestamps and
permissions happen to be. Most of this file is that promise, tested by building
the same skill twice and comparing bytes rather than by inspecting the code
that is supposed to make it true.

The rest is extraction, which is where an archive stops being ours and becomes
untrusted input: links, devices, absolute names, and traversal are all built
here by hand and refused.
"""

from __future__ import annotations

import io
import os
import random
import tarfile
from pathlib import Path, PurePosixPath

import pytest

from techtree.canonical import sha256_digest_bytes
from techtree.errors import NotFoundError, ValidationError, VerificationError
from techtree.models.skill import SkillArtifact, SkillFile
from techtree.skills.archive import (
    build_deterministic_tar,
    normalized_tar_info,
    safe_extract_archive,
    verify_archive,
)
from techtree.skills.policy import default_instruction_skill_policy
from techtree.skills.scanner import ScannedFile, scan_skill

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "skills"
VALID = FIXTURES / "valid-procedure"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def scanned(root: Path) -> list[ScannedFile]:
    return scan_skill(root, default_instruction_skill_policy()).files


def copy_skill(source: Path, destination: Path) -> Path:
    """Copy a skill tree, deliberately not preserving metadata."""
    for item in sorted(source.rglob("*")):
        if item.is_dir():
            continue
        target = destination / item.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(item.read_bytes())
    return destination


def artifact_for(files: list[ScannedFile], archive_digest: str) -> SkillArtifact:
    """Build the SkillArtifact a snapshot of these files would carry."""
    entries = [
        SkillFile(
            path=item.relative_path.as_posix(),
            media_type=item.media_type,
            size=item.size,
            digest=item.digest,
        )
        for item in sorted(files, key=lambda item: item.relative_path.as_posix())
    ]
    return SkillArtifact(
        schema_version="techtree.skill.v1alpha1",
        name="valid-procedure",
        root_digest=sha256_digest_bytes(
            "\n".join(f"{entry.path} {entry.digest}" for entry in entries).encode()
        ),
        archive_digest=archive_digest,
        files=entries,
        source_kind="manual",
        parent_skill_digest=None,
    )


def snapshot(tmp_path: Path, source: Path = VALID) -> tuple[Path, SkillArtifact]:
    """Archive a skill and return the archive path with its artifact."""
    files = scanned(source)
    archive_path = tmp_path / "skill.tar"
    digest = build_deterministic_tar(files, archive_path)
    return archive_path, artifact_for(files, digest)


def tar_with(members: list[tuple[tarfile.TarInfo, bytes | None]], path: Path) -> Path:
    """Write a hand-built tar, including shapes our builder never produces."""
    with tarfile.open(path, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for info, payload in members:
            archive.addfile(info, io.BytesIO(payload) if payload is not None else None)
    return path


# ---------------------------------------------------------------------------
# Member normalization
# ---------------------------------------------------------------------------


def test_member_metadata_is_normalized() -> None:
    info = normalized_tar_info(PurePosixPath("reference/notes.md"), 12)

    assert info.name == "reference/notes.md"
    assert info.size == 12
    assert info.mtime == 0
    assert info.mode == 0o644
    assert info.uid == 0
    assert info.gid == 0
    assert info.uname == ""
    assert info.gname == ""
    assert info.isreg()


@pytest.mark.parametrize(
    "name",
    ["/etc/passwd", "../escape.md", "reference/../../escape.md", "", ".."],
)
def test_member_names_that_escape_are_refused(name: str) -> None:
    with pytest.raises(ValidationError):
        normalized_tar_info(PurePosixPath(name), 1)


def test_negative_member_size_is_refused() -> None:
    with pytest.raises(ValidationError):
        normalized_tar_info(PurePosixPath("SKILL.md"), -1)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_the_same_skill_produces_the_same_bytes_twice(tmp_path: Path) -> None:
    files = scanned(VALID)
    first = tmp_path / "first.tar"
    second = tmp_path / "second.tar"

    first_digest = build_deterministic_tar(files, first)
    second_digest = build_deterministic_tar(files, second)

    assert first.read_bytes() == second.read_bytes()
    assert first_digest == second_digest == sha256_digest_bytes(first.read_bytes())


def test_input_order_does_not_change_the_archive(tmp_path: Path) -> None:
    files = scanned(VALID)
    ordered = tmp_path / "ordered.tar"
    build_deterministic_tar(files, ordered)
    expected = ordered.read_bytes()

    generator = random.Random(20260812)
    for attempt in range(5):
        shuffled = list(files)
        generator.shuffle(shuffled)
        candidate = tmp_path / f"shuffled-{attempt}.tar"

        build_deterministic_tar(shuffled, candidate)

        assert candidate.read_bytes() == expected


def test_source_timestamps_and_permissions_do_not_change_the_archive(
    tmp_path: Path,
) -> None:
    first = copy_skill(VALID, tmp_path / "first")
    second = copy_skill(VALID, tmp_path / "second")
    for item in sorted(second.rglob("*")):
        if item.is_file():
            item.chmod(0o600)
            os.utime(item, (1_000_000, 1_000_000))

    first_digest = build_deterministic_tar(scanned(first), tmp_path / "first.tar")
    second_digest = build_deterministic_tar(scanned(second), tmp_path / "second.tar")

    assert first_digest == second_digest


def test_changing_one_byte_changes_the_archive_digest(tmp_path: Path) -> None:
    directory = copy_skill(VALID, tmp_path / "skill")
    before = build_deterministic_tar(scanned(directory), tmp_path / "before.tar")

    entrypoint = directory / "SKILL.md"
    entrypoint.write_text(entrypoint.read_text() + "\n", encoding="utf-8")
    after = build_deterministic_tar(scanned(directory), tmp_path / "after.tar")

    assert before != after


def test_members_are_written_in_lexicographic_order(tmp_path: Path) -> None:
    archive_path, _ = snapshot(tmp_path)

    with tarfile.open(archive_path, mode="r:") as archive:
        names = archive.getnames()

    assert names == sorted(names)
    assert names == [
        "SKILL.md",
        "config.yaml",
        "data/examples.json",
        "glossary.txt",
        "reference/notes.md",
    ]


def test_written_members_carry_no_local_metadata(tmp_path: Path) -> None:
    archive_path, _ = snapshot(tmp_path)

    with tarfile.open(archive_path, mode="r:") as archive:
        for member in archive.getmembers():
            assert member.mtime == 0
            assert member.mode == 0o644
            assert (member.uid, member.gid) == (0, 0)
            assert (member.uname, member.gname) == ("", "")


def test_the_archive_is_uncompressed(tmp_path: Path) -> None:
    archive_path, _ = snapshot(tmp_path)

    assert b"# Branch code procedure" in archive_path.read_bytes()


def test_duplicate_paths_are_refused(tmp_path: Path) -> None:
    files = scanned(VALID)

    with pytest.raises(ValidationError) as caught:
        build_deterministic_tar([files[0], files[0]], tmp_path / "skill.tar")

    assert caught.value.details["path"] == "SKILL.md"


# ---------------------------------------------------------------------------
# The source changing underneath the snapshot
# ---------------------------------------------------------------------------


def test_a_file_edited_after_the_scan_is_refused(tmp_path: Path) -> None:
    directory = copy_skill(VALID, tmp_path / "skill")
    files = scanned(directory)
    (directory / "SKILL.md").write_text("# Swapped\n", encoding="utf-8")

    with pytest.raises(VerificationError) as caught:
        build_deterministic_tar(files, tmp_path / "skill.tar")

    assert caught.value.details["path"] == "SKILL.md"


def test_a_file_deleted_after_the_scan_is_refused(tmp_path: Path) -> None:
    directory = copy_skill(VALID, tmp_path / "skill")
    files = scanned(directory)
    (directory / "glossary.txt").unlink()

    with pytest.raises(VerificationError) as caught:
        build_deterministic_tar(files, tmp_path / "skill.tar")

    assert caught.value.details["path"] == "glossary.txt"


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def test_a_matching_artifact_verifies(tmp_path: Path) -> None:
    archive_path, artifact = snapshot(tmp_path)

    assert verify_archive(archive_path, artifact) is True


def test_a_different_archive_digest_does_not_verify(tmp_path: Path) -> None:
    archive_path, artifact = snapshot(tmp_path)
    claimed = artifact.model_copy(update={"archive_digest": sha256_digest_bytes(b"")})

    assert verify_archive(archive_path, claimed) is False


def test_a_changed_member_digest_does_not_verify(tmp_path: Path) -> None:
    archive_path, artifact = snapshot(tmp_path)
    files = list(artifact.files)
    files[0] = files[0].model_copy(update={"digest": sha256_digest_bytes(b"other")})
    claimed = artifact.model_copy(update={"files": files})

    assert verify_archive(archive_path, claimed) is False


def test_a_changed_member_size_does_not_verify(tmp_path: Path) -> None:
    archive_path, artifact = snapshot(tmp_path)
    files = list(artifact.files)
    files[0] = files[0].model_copy(update={"size": files[0].size + 1})
    claimed = artifact.model_copy(update={"files": files})

    assert verify_archive(archive_path, claimed) is False


def test_a_missing_member_does_not_verify(tmp_path: Path) -> None:
    archive_path, artifact = snapshot(tmp_path)
    claimed = artifact.model_copy(update={"files": list(artifact.files)[:-1]})

    assert verify_archive(archive_path, claimed) is False


def test_an_archive_with_an_extra_member_does_not_verify(tmp_path: Path) -> None:
    _, artifact = snapshot(tmp_path)
    files = scanned(VALID)
    extra = tmp_path / "extra"
    extra.mkdir()
    smuggled = extra / "smuggled.md"
    smuggled.write_text("# Not in the manifest\n", encoding="utf-8")
    data = smuggled.read_bytes()
    files.append(
        ScannedFile(
            source_path=smuggled,
            relative_path=PurePosixPath("smuggled.md"),
            size=len(data),
            media_type="text/markdown",
            digest=sha256_digest_bytes(data),
        )
    )
    tampered = tmp_path / "tampered.tar"
    build_deterministic_tar(files, tampered)

    assert verify_archive(tampered, artifact) is False


def test_restamped_member_metadata_does_not_verify(tmp_path: Path) -> None:
    archive_path, artifact = snapshot(tmp_path)
    members: list[tuple[tarfile.TarInfo, bytes | None]] = []
    with tarfile.open(archive_path, mode="r:") as archive:
        for member in archive.getmembers():
            stream = archive.extractfile(member)
            assert stream is not None
            payload = stream.read()
            member.mtime = 1_700_000_000
            members.append((member, payload))
    restamped = tar_with(members, tmp_path / "restamped.tar")
    claimed = artifact.model_copy(
        update={"archive_digest": sha256_digest_bytes(restamped.read_bytes())}
    )

    assert verify_archive(restamped, claimed) is False


def test_verification_reports_a_missing_archive_as_not_found(tmp_path: Path) -> None:
    _, artifact = snapshot(tmp_path)

    with pytest.raises(NotFoundError):
        verify_archive(tmp_path / "absent.tar", artifact)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def test_extraction_restores_every_file_byte_for_byte(tmp_path: Path) -> None:
    archive_path, _ = snapshot(tmp_path)
    destination = tmp_path / "extracted"

    safe_extract_archive(archive_path, destination)

    for item in scanned(VALID):
        restored = destination / item.relative_path
        assert restored.read_bytes() == item.source_path.read_bytes()


def test_extraction_round_trips_to_the_same_archive(tmp_path: Path) -> None:
    archive_path, _ = snapshot(tmp_path)
    destination = tmp_path / "extracted"
    safe_extract_archive(archive_path, destination)

    rebuilt = build_deterministic_tar(scanned(destination), tmp_path / "rebuilt.tar")

    assert rebuilt == sha256_digest_bytes(archive_path.read_bytes())


def test_extraction_refuses_a_traversing_member(tmp_path: Path) -> None:
    info = tarfile.TarInfo(name="../escape.md")
    info.size = 3
    archive_path = tar_with([(info, b"bad")], tmp_path / "traversal.tar")

    with pytest.raises(ValidationError) as caught:
        safe_extract_archive(archive_path, tmp_path / "extracted")

    assert "escape" in caught.value.message
    assert not (tmp_path / "escape.md").exists()


def test_extraction_refuses_a_nested_traversing_member(tmp_path: Path) -> None:
    info = tarfile.TarInfo(name="reference/../../escape.md")
    info.size = 3
    archive_path = tar_with([(info, b"bad")], tmp_path / "nested.tar")

    with pytest.raises(ValidationError):
        safe_extract_archive(archive_path, tmp_path / "extracted")


def test_extraction_refuses_an_absolute_member(tmp_path: Path) -> None:
    victim = tmp_path / "victim.md"
    victim.write_text("# Untouched\n", encoding="utf-8")
    info = tarfile.TarInfo(name=str(victim))
    info.size = 3
    archive_path = tar_with([(info, b"bad")], tmp_path / "absolute.tar")

    with pytest.raises(ValidationError) as caught:
        safe_extract_archive(archive_path, tmp_path / "extracted")

    assert "absolute" in caught.value.message
    assert victim.read_text(encoding="utf-8") == "# Untouched\n"


def test_extraction_refuses_a_symlink_member(tmp_path: Path) -> None:
    info = tarfile.TarInfo(name="notes.md")
    info.type = tarfile.SYMTYPE
    info.linkname = "/etc/passwd"
    archive_path = tar_with([(info, None)], tmp_path / "symlink.tar")

    with pytest.raises(ValidationError) as caught:
        safe_extract_archive(archive_path, tmp_path / "extracted")

    assert caught.value.details["kind"] == "link"


def test_extraction_refuses_a_hard_link_member(tmp_path: Path) -> None:
    info = tarfile.TarInfo(name="notes.md")
    info.type = tarfile.LNKTYPE
    info.linkname = "SKILL.md"
    archive_path = tar_with([(info, None)], tmp_path / "hardlink.tar")

    with pytest.raises(ValidationError) as caught:
        safe_extract_archive(archive_path, tmp_path / "extracted")

    assert caught.value.details["kind"] == "link"


@pytest.mark.parametrize(
    "member_type", [tarfile.FIFOTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE]
)
def test_extraction_refuses_devices_and_fifos(
    tmp_path: Path, member_type: bytes
) -> None:
    info = tarfile.TarInfo(name="device")
    info.type = member_type
    archive_path = tar_with([(info, None)], tmp_path / "device.tar")

    with pytest.raises(ValidationError) as caught:
        safe_extract_archive(archive_path, tmp_path / "extracted")

    assert caught.value.details["kind"] == "device"


def test_extraction_refuses_a_directory_member(tmp_path: Path) -> None:
    info = tarfile.TarInfo(name="reference")
    info.type = tarfile.DIRTYPE
    archive_path = tar_with([(info, None)], tmp_path / "directory.tar")

    with pytest.raises(ValidationError) as caught:
        safe_extract_archive(archive_path, tmp_path / "extracted")

    assert caught.value.details["kind"] == "not_regular"


def test_extraction_refuses_a_backslash_member(tmp_path: Path) -> None:
    info = tarfile.TarInfo(name="reference\\notes.md")
    info.size = 3
    archive_path = tar_with([(info, b"bad")], tmp_path / "backslash.tar")

    with pytest.raises(ValidationError):
        safe_extract_archive(archive_path, tmp_path / "extracted")


def test_extraction_reports_a_missing_archive_as_not_found(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError):
        safe_extract_archive(tmp_path / "absent.tar", tmp_path / "extracted")
