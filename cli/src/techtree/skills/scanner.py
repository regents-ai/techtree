"""Validate and scan a candidate skill directory. Spec section 15.2.

This module answers one question completely: given a path a participant typed,
what exactly is going to be snapshotted, and is any of it something we must
refuse to copy?

It refuses rather than repairs. A symlink is not resolved, a hidden file is not
skipped, and an oversized file is not truncated. Every one of those would
produce a snapshot that differs from what the participant believes they
submitted, and the snapshot is the scientific input to an experiment.

Every refusal here is about a file's *shape*: how big it is, how many there
are, whether it is a regular file, whether it decodes as text. None of them
reads the words. Decision 0036 removed the rules that did — a Skill is prose
about a procedure, a procedure about security is prose about credentials, and
refusing one on a regex blocked legitimate work in a product whose premise is
that people bring their own Skills. What a Skill says is now the participant's
business.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

from techtree.canonical import sha256_digest_bytes
from techtree.errors import NotFoundError, ValidationError
from techtree.fs import realpath_within
from techtree.models.base import Digest
from techtree.models.skill import SKILL_ENTRY_FILE
from techtree.skills.policy import SkillPolicy

__all__ = [
    "MEDIA_TYPES",
    "ScannedFile",
    "SkillScanResult",
    "enumerate_files",
    "media_type_for",
    "resolve_skill_root",
    "scan_skill",
    "validate_file",
]


# ---------------------------------------------------------------------------
# Structures
# ---------------------------------------------------------------------------


@dataclass
class ScannedFile:
    """A validated file, and everything the snapshot needs to know about it."""

    source_path: Path
    relative_path: PurePosixPath
    size: int
    media_type: str
    digest: Digest


@dataclass
class SkillScanResult:
    """The complete, ordered description of what would be snapshotted."""

    root: Path
    files: list[ScannedFile]


# ---------------------------------------------------------------------------
# Media types
# ---------------------------------------------------------------------------

#: Suffix to media type. Fixed strings: they travel into the SkillArtifact and
#: therefore into a digest, so they may never be derived from the host's
#: ``mimetypes`` database, which differs between machines.
MEDIA_TYPES: Final[dict[str, str]] = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".json": "application/json",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
}


# ---------------------------------------------------------------------------
# Root resolution and enumeration
# ---------------------------------------------------------------------------


def resolve_skill_root(path: Path) -> Path:
    """Accept SKILL.md or containing directory.

    Symlinks are left exactly as they are: whether one is tolerable is the
    policy's decision, and :func:`scan_skill` makes it.
    """
    if not path.exists() and not path.is_symlink():
        raise NotFoundError(
            f"no such skill path: {path}",
            details={"path": str(path)},
        )

    if path.is_dir():
        root = path
    elif path.is_file():
        if path.name != SKILL_ENTRY_FILE:
            raise ValidationError(
                "a skill is named by its directory or by its SKILL.md, "
                f"not by one of its other files: {path.name}",
                details={"path": str(path)},
            )
        root = path.parent
    else:
        raise ValidationError(
            f"skill path is neither a directory nor a regular file: {path}",
            details={"path": str(path)},
        )

    entrypoint = root / SKILL_ENTRY_FILE
    if not entrypoint.is_file():
        raise ValidationError(
            f"skill directory has no {SKILL_ENTRY_FILE} entrypoint: {root}",
            details={"root": str(root), "entrypoint": SKILL_ENTRY_FILE},
        )
    return root


def enumerate_files(root: Path) -> list[Path]:
    """Enumerate without following symlinks.

    Symlinks, sockets, and devices are returned rather than skipped, so that
    validation reports them instead of silently leaving them out of the
    snapshot. Directory symlinks are reported and not descended into.
    """
    found: list[Path] = []
    _walk(root, found)
    return sorted(found, key=lambda item: _relative_key(item, root))


def _walk(directory: Path, found: list[Path]) -> None:
    with os.scandir(directory) as entries:
        for entry in entries:
            child = Path(entry.path)
            if entry.is_symlink():
                found.append(child)
            elif entry.is_dir(follow_symlinks=False):
                _walk(child, found)
            else:
                found.append(child)


def _relative_key(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _relative_path(path: Path, root: Path) -> PurePosixPath:
    try:
        return PurePosixPath(path.relative_to(root).as_posix())
    except ValueError as error:
        raise ValidationError(
            f"file is outside the skill root: {path}",
            details={"path": str(path), "root": str(root)},
        ) from error


# ---------------------------------------------------------------------------
# Per-file validation
# ---------------------------------------------------------------------------


def validate_file(
    path: Path,
    root: Path,
    policy: SkillPolicy,
) -> None:
    """Validate containment, type, suffix, size, and hidden status."""
    relative = _relative_path(path, root)

    if not policy.allow_hidden_files:
        hidden = next((part for part in relative.parts if part.startswith(".")), None)
        if hidden is not None:
            raise ValidationError(
                f"skill contains a hidden path, which is never submitted: {relative}",
                details={"path": relative.as_posix(), "hidden_component": hidden},
            )

    if path.is_symlink() and not policy.allow_symlinks:
        raise ValidationError(
            "skill contains a symlink, and a snapshot must mean the same thing "
            f"on every machine: {relative}",
            details={"path": relative.as_posix()},
        )

    status = _status(path, relative, policy)
    if not stat.S_ISREG(status.st_mode):
        raise ValidationError(
            f"skill contains {_describe_type(status.st_mode)}, which cannot be "
            f"snapshotted: {relative}",
            details={
                "path": relative.as_posix(),
                "kind": _describe_type(status.st_mode),
            },
        )

    suffix = path.suffix.lower()
    if suffix not in policy.allowed_suffixes:
        raise ValidationError(
            f"skill file has an unsupported suffix: {relative}",
            details={
                "path": relative.as_posix(),
                "suffix": suffix,
                "allowed_suffixes": [*sorted(policy.allowed_suffixes)],
            },
        )

    if status.st_size > policy.maximum_file_bytes:
        raise ValidationError(
            f"skill file is larger than {policy.maximum_file_bytes} bytes: {relative}",
            details={
                "path": relative.as_posix(),
                "size": status.st_size,
                "maximum_file_bytes": policy.maximum_file_bytes,
            },
        )

    if not realpath_within(path, root):
        raise ValidationError(
            f"skill file resolves outside the skill root: {relative}",
            details={"path": relative.as_posix(), "root": str(root)},
        )


def _status(path: Path, relative: PurePosixPath, policy: SkillPolicy) -> os.stat_result:
    """Stat a candidate file, reporting an unreadable one as a refusal.

    A file the scanner cannot read — a broken link, a directory it has no
    permission to enter — is not a defect in Techtree, so it is reported the
    same way as anything else the participant needs to fix.
    """
    try:
        return path.stat(follow_symlinks=policy.allow_symlinks)
    except OSError as error:
        raise ValidationError(
            f"skill file cannot be read: {relative}",
            details={"path": relative.as_posix()},
        ) from error


def _describe_type(mode: int) -> str:
    if stat.S_ISDIR(mode):
        return "a directory"
    if stat.S_ISFIFO(mode):
        return "a FIFO"
    if stat.S_ISSOCK(mode):
        return "a socket"
    if stat.S_ISBLK(mode) or stat.S_ISCHR(mode):
        return "a device"
    return "something that is not a regular file"


def media_type_for(path: Path) -> str:
    """Map allowed suffix to stable media type."""
    media_type = MEDIA_TYPES.get(path.suffix.lower())
    if media_type is None:
        raise ValidationError(
            f"no media type is defined for this suffix: {path.name}",
            details={"suffix": path.suffix.lower()},
        )
    return media_type


# ---------------------------------------------------------------------------
# Text decoding
# ---------------------------------------------------------------------------


def _decode_text(data: bytes, reported_path: str) -> str:
    """Read a validated skill file as text, refusing anything unreadable."""
    if b"\x00" in data:
        raise ValidationError(
            f"skill file is binary, and an instruction skill is text: {reported_path}",
            details={"path": reported_path},
        )
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValidationError(
            f"skill file is not valid UTF-8 text: {reported_path}",
            details={"path": reported_path},
        ) from error


# ---------------------------------------------------------------------------
# Whole-skill scan
# ---------------------------------------------------------------------------


def scan_skill(
    path: Path,
    policy: SkillPolicy,
) -> SkillScanResult:
    """Perform complete validation and scanning.

    Raises :class:`~techtree.errors.ValidationError` for anything the policy
    forbids: a shape the snapshot cannot carry, a size over the limit, or a
    file that is not text.
    """
    root = resolve_skill_root(path)
    if root.is_symlink() and not policy.allow_symlinks:
        raise ValidationError(
            f"skill root is a symlink, which is never snapshotted: {root}",
            details={"root": str(root)},
        )

    candidates = enumerate_files(root)
    if len(candidates) > policy.maximum_files:
        raise ValidationError(
            f"skill contains {len(candidates)} files, "
            f"more than the {policy.maximum_files} allowed",
            details={"count": len(candidates), "maximum_files": policy.maximum_files},
        )

    files: list[ScannedFile] = []
    total = 0

    for candidate in candidates:
        validate_file(candidate, root, policy)
        relative = _relative_path(candidate, root)
        data = candidate.read_bytes()
        total += len(data)
        if total > policy.maximum_total_bytes:
            raise ValidationError(
                "skill is larger than the "
                f"{policy.maximum_total_bytes} byte total limit",
                details={
                    "total_bytes": total,
                    "maximum_total_bytes": policy.maximum_total_bytes,
                },
            )
        _decode_text(data, relative.as_posix())
        files.append(
            ScannedFile(
                source_path=candidate,
                relative_path=relative,
                size=len(data),
                media_type=media_type_for(candidate),
                digest=sha256_digest_bytes(data),
            )
        )

    _require_entrypoint(files, root, policy)
    _reject_case_collisions(files)

    return SkillScanResult(
        root=root,
        files=sorted(files, key=lambda item: item.relative_path.as_posix()),
    )


def _require_entrypoint(
    files: list[ScannedFile], root: Path, policy: SkillPolicy
) -> None:
    entrypoint = PurePosixPath(policy.required_entrypoint)
    if not any(item.relative_path == entrypoint for item in files):
        raise ValidationError(
            f"skill directory has no {policy.required_entrypoint} entrypoint: {root}",
            details={"root": str(root), "entrypoint": policy.required_entrypoint},
        )


def _reject_case_collisions(files: list[ScannedFile]) -> None:
    """Refuse paths that differ only by case.

    Such a pair is two files here and one file on a case-insensitive
    filesystem, so the snapshot would not survive a round trip through one
    machine to another.
    """
    seen: dict[str, str] = {}
    for item in files:
        posix = item.relative_path.as_posix()
        folded = posix.casefold()
        existing = seen.get(folded)
        if existing is not None:
            raise ValidationError(
                "skill contains paths that differ only by case, which collide "
                f"on a case-insensitive filesystem: {existing} and {posix}",
                details={"paths": [existing, posix]},
            )
        seen[folded] = posix
