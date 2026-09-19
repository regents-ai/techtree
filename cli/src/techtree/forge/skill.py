"""The Skill a forge run or revision owns: taken once, read back verified.

A candidate run measures the Skill it was declared with, and the directory
that Skill was declared from is somebody's working copy, free to move on the
moment the run ends. So the run takes its own copy of the files before the
first attempt, under ``skill/`` beside its evidence, and every attempt's
profile is filled from that copy rather than from the working directory. A
revision keeps its candidate Skill the same way, under its own directory.

Reading the copy back is a verification, not a load: every file the
specification lists is read and hashed against the size and digest the
specification committed to, and the entrypoint's text is the buffer that was
hashed. A mismatch is a refusal; nothing here repairs a digest or returns text
it could not vouch for. Decisions document 0007 R2 asks exactly this of the
Skill a Climb run owns, and the read here is the same read for a forge run.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Final

from techtree.canonical import sha256_digest_bytes
from techtree.errors import VerificationError
from techtree.forge.models import ForgeSkillSpec
from techtree.manifests.builder import skill_content_digest
from techtree.models.skill import SKILL_ENTRY_FILE, SkillFile
from techtree.skills.policy import default_instruction_skill_policy
from techtree.skills.scanner import scan_skill
from techtree.uplift.source import (
    SOURCE_SKILL_UNREADABLE,
    SOURCE_SKILL_UNVERIFIED,
    VerifiedSourceSkill,
)

__all__ = [
    "SKILL_DIRNAME",
    "read_owned_skill",
    "scan_skill_spec",
    "snapshot_skill",
]

#: Where a run or a revision keeps its own copy of the Skill.
SKILL_DIRNAME: Final = "skill"


def scan_skill_spec(
    skill_root: Path, *, name: str | None = None
) -> tuple[ForgeSkillSpec, list[tuple[Path, str]]]:
    """Scan a Skill directory and return its specification and its files.

    The files come back as ``(source, relative path)`` pairs in the scan's
    order, which is what a snapshot copies. The name is the directory's
    unless one is given, and it is checked as the name Hermes will accept.
    """
    scan = scan_skill(skill_root, default_instruction_skill_policy())
    files = [
        SkillFile(
            path=item.relative_path.as_posix(),
            media_type=item.media_type,
            size=item.size,
            digest=item.digest,
        )
        for item in scan.files
    ]
    spec = ForgeSkillSpec(
        name=scan.root.name if name is None else name,
        root_digest=skill_content_digest(files),
        files=files,
        exposure="preloaded",
    )
    return spec, [
        (item.source_path, item.relative_path.as_posix()) for item in scan.files
    ]


def snapshot_skill(files: list[tuple[Path, str]], destination: Path) -> None:
    """Copy the scanned files under ``destination``, keeping their paths."""
    for source, relative in files:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copyfile(source, target)


def read_owned_skill(
    spec: ForgeSkillSpec, directory: Path, *, owner_id: str
) -> VerifiedSourceSkill:
    """Read the owned copy's entrypoint, proving every listed file as it is read."""
    recomputed = skill_content_digest(spec.files)
    _require(
        recomputed == spec.root_digest,
        "this copy of the Skill lists files that do not describe the Skill "
        "it says it is",
        owner_id=owner_id,
        expected=spec.root_digest,
        computed=recomputed,
    )

    entry: SkillFile | None = None
    entrypoint_bytes = b""
    for file in spec.files:
        data = _read(directory / file.path, owner_id=owner_id, path=file.path)
        computed = sha256_digest_bytes(data)
        _require(
            len(data) == file.size and computed == file.digest,
            f"this copy of {file.path} is not the file that was measured",
            owner_id=owner_id,
            path=file.path,
            expected=file.digest,
            computed=computed,
        )
        if file.path == SKILL_ENTRY_FILE:
            entry, entrypoint_bytes = file, data

    if entry is None:
        raise VerificationError(
            f"this copy of the Skill lists no {SKILL_ENTRY_FILE}, so it has no "
            "text to read",
            code=SOURCE_SKILL_UNVERIFIED,
            details={"owner_id": owner_id, "skill": spec.root_digest},
        )
    try:
        text = entrypoint_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise VerificationError(
            f"this copy of {entry.path} is not UTF-8 text, so it cannot be "
            "read as a Skill",
            code=SOURCE_SKILL_UNREADABLE,
            details={"owner_id": owner_id, "path": entry.path},
        ) from error

    return VerifiedSourceSkill(
        run_id=owner_id,
        name=spec.name,
        root_digest=spec.root_digest,
        entrypoint_path=entry.path,
        entrypoint_digest=entry.digest,
        entrypoint_size=entry.size,
        entrypoint_text=text,
        file_count=len(spec.files),
    )


def _read(location: Path, *, owner_id: str, path: str) -> bytes:
    try:
        return location.read_bytes()
    except OSError as error:
        raise VerificationError(
            f"this copy of {path} could not be read: {error.strerror or error}",
            code=SOURCE_SKILL_UNREADABLE,
            details={"owner_id": owner_id, "path": path},
        ) from error


def _require(condition: bool, message: str, **details: str | int) -> None:
    if condition:
        return
    raise VerificationError(
        message,
        code=SOURCE_SKILL_UNVERIFIED,
        details={key: str(value) for key, value in details.items()},
    )
