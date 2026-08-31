"""The run-owned verified Skill text. Decisions document 0007 R2.

One question is asked here, in both directions: does the text handed to a
caller come with a proof that it is the Skill the run measured, and is
anything less than that refused?

The proof has to hold at the moment of the read, so every refusal below is
arranged by changing the bytes *after* an artifact describing them exists —
which is exactly the shape of the failure this guards against. A snapshot that
was correct when a run staged it and is not correct now must not be readable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from techtree.canonical import sha256_digest_bytes
from techtree.cli.commands.uplift import UpliftSkillSourcePayload
from techtree.drafts.source import StagedSkill
from techtree.errors import VerificationError
from techtree.manifests.builder import skill_content_digest
from techtree.models.skill import SkillArtifact, SkillFile
from techtree.uplift.source import (
    SOURCE_SKILL_UNREADABLE,
    SOURCE_SKILL_UNVERIFIED,
    read_verified_source_skill,
)

RUN_ID = "run_01J8ZQ3KAAAAAAAAAAAAAAAAAA"

SKILL_TEXT = """# BranchCode v1

Follow every step in order.

5. Add 7 times the total number of characters.
"""

REFERENCE_TEXT = "Worked examples live here.\n"


def staged_skill(root: Path, *, text: str = SKILL_TEXT) -> StagedSkill:
    """Write a two-file Skill and the artifact that describes it exactly."""
    files = root / "files"
    files.mkdir(parents=True)
    contents = {"REFERENCE.md": REFERENCE_TEXT, "SKILL.md": text}
    entries = []
    for path, body in sorted(contents.items()):
        data = body.encode("utf-8")
        (files / path).write_bytes(data)
        entries.append(
            SkillFile(
                path=path,
                media_type="text/markdown",
                size=len(data),
                digest=sha256_digest_bytes(data),
            )
        )

    return StagedSkill(
        artifact=SkillArtifact(
            schema_version="techtree.skill.v1alpha1",
            name="branch-code-v1",
            root_digest=skill_content_digest(entries),
            archive_digest=f"sha256:{'b' * 64}",
            files=entries,
            source_kind="manual",
            parent_skill_digest=None,
        ),
        archive=root / "bundle.tar",
        files=files,
    )


# ---------------------------------------------------------------------------
# What a caller is handed
# ---------------------------------------------------------------------------


def test_the_entrypoint_text_comes_back_with_what_it_was_verified_against(
    tmp_path: Path,
) -> None:
    """R2: the text, the tree digest, and the entrypoint digest, together."""
    staged = staged_skill(tmp_path)

    read = read_verified_source_skill(staged, run_id=RUN_ID)

    assert read.run_id == RUN_ID
    assert read.name == "branch-code-v1"
    assert read.entrypoint_path == "SKILL.md"
    assert read.entrypoint_text == SKILL_TEXT
    assert read.entrypoint_digest == sha256_digest_bytes(SKILL_TEXT.encode("utf-8"))
    assert read.entrypoint_size == len(SKILL_TEXT.encode("utf-8"))
    assert read.root_digest == staged.artifact.root_digest
    assert read.file_count == 2


def test_the_entrypoint_is_the_entry_file_and_not_the_first_one(
    tmp_path: Path,
) -> None:
    """A Skill whose files sort before SKILL.md still reads SKILL.md."""
    staged = staged_skill(tmp_path)
    assert staged.artifact.files[0].path == "REFERENCE.md"

    read = read_verified_source_skill(staged, run_id=RUN_ID)

    assert read.entrypoint_text == SKILL_TEXT
    assert REFERENCE_TEXT not in read.entrypoint_text


def test_two_reads_of_one_snapshot_agree(tmp_path: Path) -> None:
    """Nothing here is derived from when it was read."""
    staged = staged_skill(tmp_path)

    assert read_verified_source_skill(staged, run_id=RUN_ID) == (
        read_verified_source_skill(staged, run_id=RUN_ID)
    )


# ---------------------------------------------------------------------------
# What is refused
# ---------------------------------------------------------------------------


def test_an_edited_entrypoint_is_refused(tmp_path: Path) -> None:
    """One added character is enough: the digest is the whole claim."""
    staged = staged_skill(tmp_path)
    (staged.files / "SKILL.md").write_text(f"{SKILL_TEXT} ", encoding="utf-8")

    with pytest.raises(VerificationError) as raised:
        read_verified_source_skill(staged, run_id=RUN_ID)

    assert raised.value.code == SOURCE_SKILL_UNVERIFIED
    assert raised.value.details["expected"] == staged.artifact.files[1].digest


def test_an_edited_sibling_file_is_refused_too(tmp_path: Path) -> None:
    """The claim is about the Skill, not only about the file being read.

    A reviser told "this is the Skill that was measured" would be told
    something false if a Skill with an altered reference file read as clean
    because its entrypoint happened to be untouched.
    """
    staged = staged_skill(tmp_path)
    (staged.files / "REFERENCE.md").write_text("something else\n", encoding="utf-8")

    with pytest.raises(VerificationError) as raised:
        read_verified_source_skill(staged, run_id=RUN_ID)

    assert raised.value.code == SOURCE_SKILL_UNVERIFIED


def test_a_file_list_that_no_longer_describes_the_tree_is_refused(
    tmp_path: Path,
) -> None:
    """A root digest is checked against the list before anything is opened."""
    staged = staged_skill(tmp_path)
    tampered = StagedSkill(
        artifact=staged.artifact.model_copy(
            update={"root_digest": f"sha256:{'a' * 64}"}
        ),
        archive=staged.archive,
        files=staged.files,
    )

    with pytest.raises(VerificationError) as raised:
        read_verified_source_skill(tampered, run_id=RUN_ID)

    assert raised.value.code == SOURCE_SKILL_UNVERIFIED
    assert raised.value.details["expected"] == f"sha256:{'a' * 64}"


def test_a_missing_entrypoint_is_refused(tmp_path: Path) -> None:
    """A snapshot that lost the file it is read through has nothing to give."""
    staged = staged_skill(tmp_path)
    (staged.files / "SKILL.md").unlink()

    with pytest.raises(VerificationError) as raised:
        read_verified_source_skill(staged, run_id=RUN_ID)

    assert raised.value.code == SOURCE_SKILL_UNREADABLE
    assert raised.value.details["path"] == "SKILL.md"


def test_a_verified_skill_is_answerable_however_thin_its_text_is(
    tmp_path: Path,
) -> None:
    """A Skill that really ran comes back, even if its SKILL.md says nothing.

    Nothing stops a participant preparing a Skill whose entry file is one
    newline, and a run that measured one is a real run. The response shape
    must carry what was verified rather than re-judging it, or the honest
    answer to "show me the Skill this result came from" would be a crash.
    """
    staged = staged_skill(tmp_path, text="\n")

    read = read_verified_source_skill(staged, run_id=RUN_ID)
    payload = UpliftSkillSourcePayload(
        source_run_id=read.run_id,
        skill_name=read.name,
        skill_root_digest=read.root_digest,
        entrypoint_path=read.entrypoint_path,
        entrypoint_digest=read.entrypoint_digest,
        entrypoint_size=read.entrypoint_size,
        entrypoint_text=read.entrypoint_text,
        file_count=read.file_count,
    )

    assert payload.entrypoint_text == "\n"
    assert payload.entrypoint_digest == sha256_digest_bytes(b"\n")


def test_an_entrypoint_that_is_not_text_is_refused(tmp_path: Path) -> None:
    """Bytes that hash correctly are still not a Skill if they are not text."""
    root = tmp_path / "skill"
    files = root / "files"
    files.mkdir(parents=True)
    data = b"\xff\xfe\x00binary"
    (files / "SKILL.md").write_bytes(data)
    entries = [
        SkillFile(
            path="SKILL.md",
            media_type="text/markdown",
            size=len(data),
            digest=sha256_digest_bytes(data),
        )
    ]
    staged = StagedSkill(
        artifact=SkillArtifact(
            schema_version="techtree.skill.v1alpha1",
            name="branch-code-v1",
            root_digest=skill_content_digest(entries),
            archive_digest=f"sha256:{'b' * 64}",
            files=entries,
            source_kind="manual",
            parent_skill_digest=None,
        ),
        archive=root / "bundle.tar",
        files=files,
    )

    with pytest.raises(VerificationError) as raised:
        read_verified_source_skill(staged, run_id=RUN_ID)

    assert raised.value.code == SOURCE_SKILL_UNREADABLE
