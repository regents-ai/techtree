"""The run's own verified Skill text. Decisions document 0007 R2.

A host agent that is asked to revise a Skill has to read the Skill first, and
R2 says which copy it reads: the one the run owns, re-verified against the
run's own artifact at the moment it is read. This module is that read.

Three things are deliberate.

*Verification happens on the bytes that are returned.* The run's inputs are
checked file by file when they are loaded, but a check performed on one read
says nothing about a later one. The entrypoint is read once, hashed, and
compared with the artifact's own entry for it, and it is that same buffer that
becomes the returned text. There is no window between proving and using.

*The whole tree is proved, not just the file.* The artifact's file list is
re-digested against its root digest before any file is opened, and then every
file it lists is read and hashed — not only the entrypoint. A caller who is
handed text is being told two things at once: this is the entrypoint of a
Skill, and that Skill is the one the run measured. The second half would be
false if a reference file could be edited without anyone noticing, and a
Skill is a handful of small text files, so proving all of it costs nothing.

*A mismatch is a refusal, never a repair.* Nothing here rewrites a digest,
falls back to the archive, or returns text it could not vouch for. The only
outcomes are verified text and a typed error, because the consumer of this
text sends it to a model and binds a proposal to the digests beside it.

Composing the internal path to a run's staged Skill is what this exists to
prevent: the layout under a run directory is Techtree's, and a second
implementation of it somewhere else would be a second thing to keep true.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from techtree.canonical import sha256_digest_bytes
from techtree.drafts.source import StagedSkill
from techtree.errors import VerificationError
from techtree.manifests.builder import skill_content_digest
from techtree.models.base import Digest
from techtree.models.skill import SKILL_ENTRY_FILE, SkillFile

__all__ = [
    "SOURCE_SKILL_UNREADABLE",
    "SOURCE_SKILL_UNVERIFIED",
    "VerifiedSourceSkill",
    "read_verified_source_skill",
]

#: The Skill this run owns does not hash to what the run says it is. Stable,
#: because a consumer branches on it: this is the one condition under which a
#: revision must not be proposed at all.
SOURCE_SKILL_UNVERIFIED: Final = "source_skill_unverified"

#: The bytes are there and correct but cannot be handed over as text — an
#: unreadable file, or an entrypoint that is not UTF-8. Different from a
#: mismatch, because nothing is claiming to be something it is not.
SOURCE_SKILL_UNREADABLE: Final = "source_skill_unreadable"


@dataclass(frozen=True)
class VerifiedSourceSkill:
    """One run-owned Skill's entrypoint text, and what it was verified against."""

    run_id: str
    name: str
    root_digest: Digest
    entrypoint_path: str
    entrypoint_digest: Digest
    entrypoint_size: int
    entrypoint_text: str
    file_count: int


def read_verified_source_skill(
    staged: StagedSkill, *, run_id: str
) -> VerifiedSourceSkill:
    """Read one run-owned Skill's entrypoint, proving it as it is read."""
    skill = staged.artifact

    recomputed_root = skill_content_digest(skill.files)
    _require(
        recomputed_root == skill.root_digest,
        "this run's copy of the Skill lists files that do not describe the "
        "Skill it says it is",
        run_id=run_id,
        expected=skill.root_digest,
        computed=recomputed_root,
    )

    entry: SkillFile | None = None
    entrypoint_bytes = b""
    for file in skill.files:
        data = _read(staged.files / file.path, run_id=run_id, path=file.path)
        computed = sha256_digest_bytes(data)
        _require(
            len(data) == file.size and computed == file.digest,
            f"this run's copy of {file.path} is not the file the run measured",
            run_id=run_id,
            path=file.path,
            expected=file.digest,
            computed=computed,
        )
        if file.path == SKILL_ENTRY_FILE:
            entry, entrypoint_bytes = file, data

    if entry is None:
        raise VerificationError(
            f"this run's copy of the Skill lists no {SKILL_ENTRY_FILE}, so it "
            "has no text to read",
            code=SOURCE_SKILL_UNVERIFIED,
            details={"run_id": run_id, "skill": skill.root_digest},
        )

    try:
        text = entrypoint_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise VerificationError(
            f"this run's copy of {entry.path} is not UTF-8 text, so it cannot "
            "be read as a Skill",
            code=SOURCE_SKILL_UNREADABLE,
            details={"run_id": run_id, "path": entry.path},
        ) from error

    return VerifiedSourceSkill(
        run_id=run_id,
        name=skill.name,
        root_digest=skill.root_digest,
        entrypoint_path=entry.path,
        entrypoint_digest=entry.digest,
        entrypoint_size=entry.size,
        entrypoint_text=text,
        file_count=len(skill.files),
    )


def _read(location: Path, *, run_id: str, path: str) -> bytes:
    """Return one staged file's bytes, or refuse because it cannot be read."""
    try:
        return location.read_bytes()
    except OSError as error:
        raise VerificationError(
            f"this run's copy of {path} could not be read: {error.strerror or error}",
            code=SOURCE_SKILL_UNREADABLE,
            details={"run_id": run_id, "path": path},
        ) from error


def _require(condition: bool, message: str, **details: str | int) -> None:
    """Refuse, with the two digests that disagree, unless they agree."""
    if condition:
        return
    raise VerificationError(
        message,
        code=SOURCE_SKILL_UNVERIFIED,
        details={key: str(value) for key, value in details.items()},
    )
