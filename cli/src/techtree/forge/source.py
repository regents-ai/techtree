"""Look at a Source Skill without running any of it, and record what was found.

This is the first record of a Skill-created environment (plan R15-R18,
KTD3, KTD6). Every entry under the Skill's directory is listed and given a
disposition, and nothing is executed, followed or guessed:

* A hidden path is recorded and never opened, and a hidden directory is one
  entry whose contents are not listed. A link is recorded and not followed.
  Anything that is not a regular file or a readable directory is recorded as
  what it is.
* A regular file is hashed. It is admitted when it is UTF-8 text of a type
  an instruction Skill is made of (the suffixes ``skills/scanner.py`` admits)
  and within the per-file limit; anything else (a script, a binary, an
  image) is unsupported, with the reason.
* A file is *required* when the Skill's instructions name it: SKILL.md, and
  every path SKILL.md or an admitted file it names mentions, followed through
  the admitted text. A path counts as named when it appears as a Markdown
  link target, or as a bare path relative to the Skill or to the file that
  mentions it (a directory only with its trailing slash). A link to a file
  that is not there, or outside the Skill, is itself a refusal.

A required file that cannot be admitted refuses the whole Skill: Techtree
never omits what the instructions need and calls the rest the Skill (R16).
An unsupported file nothing names is left out and listed as left out. The
record is written either way; an admitted source also keeps the admitted
bytes, exactly the bytes that were hashed, under ``skill/`` beside it, and a
refused one keeps none. A reduced copy the contributor makes is inspected as
a new source whose lineage names the record it was derived from (R17).

SKILL.md's header is read as the Agent Skills specification declares it,
with a deliberately small reader: top-level ``key: value`` lines with plain,
single- or double-quoted values, and ``metadata`` as one level of indented
``key: value`` lines. Any other YAML is refused with its line number rather
than half-read. What the header declares, including ``allowed-tools``, is a
declaration and grants nothing (R18).
"""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Final
from urllib.parse import unquote

from pydantic import ValidationError as ModelValidationError

from techtree.canonical import sha256_digest_bytes
from techtree.constants import (
    MAX_SKILL_FILE_BYTES,
    MAX_SKILL_FILES,
    MAX_SKILL_TOTAL_BYTES,
)
from techtree.errors import NotFoundError, ValidationError
from techtree.forge.models import (
    FORGE_SOURCE_SCHEMA_VERSION,
    ForgeRefusalReason,
    ForgeSkillDeclaration,
    ForgeSourceEntry,
    ForgeSourceLineage,
    ForgeSourceRecord,
    ForgeSourceRefusal,
    ForgeSourceStatus,
    ForgeUnsupportedReason,
)
from techtree.forge.skill import SKILL_DIRNAME
from techtree.fs import atomic_write_bytes, atomic_write_json
from techtree.ids import new_id, validate_id
from techtree.manifests.builder import skill_content_digest
from techtree.models.skill import SKILL_ENTRY_FILE, SkillFile
from techtree.paths import TechtreePaths
from techtree.skills.scanner import MEDIA_TYPES, resolve_skill_root

__all__ = [
    "SOURCE_FILENAME",
    "inspect_source_skill",
    "read_source_status",
]

#: The record beside the kept bytes.
SOURCE_FILENAME: Final = "source.json"

#: How many entries one inspection lists before it stops: a directory this
#: large is not a Skill, and listing it would not end usefully.
_MAX_ENTRIES: Final = 4096

#: What each unsupported reason says, completing "<path> ...".
UNSUPPORTED_WORDS: Final[dict[ForgeUnsupportedReason, str]] = {
    "hidden": "is hidden, and Techtree never opens hidden files",
    "symlink": "is a link, and what a link points to depends on the machine",
    "special": "is not a regular file",
    "unreadable": "cannot be read",
    "file_type": (
        "is a kind of file Techtree does not carry; only "
        + ", ".join(sorted(MEDIA_TYPES))
        + " text is"
    ),
    "not_text": "is not UTF-8 text",
    "too_large": f"is larger than the {MAX_SKILL_FILE_BYTES} byte limit for one file",
    "case_collision": "differs from another path only by letter case",
}

_TOKEN = re.compile(r"(?<![\w./-])(?:\./)?([\w.-]+(?:/[\w.-]+)*/?)")
_INLINE_LINK = re.compile(r"\]\(\s*<?([^)>\s]+)")
_REFERENCE_LINK = re.compile(r"^\s*\[[^\]]+\]:\s*<?(\S+?)>?\s*$", re.MULTILINE)
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_TOP_LEVEL = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):(?:[ \t]+(.*))?$")
_NESTED = re.compile(r"^[ \t]+([A-Za-z0-9_.-]+):(?:[ \t]+(.*))?$")


@dataclass
class _Entry:
    """One entry while it is being classified; frozen into the record after."""

    path: str
    kind: str
    size: int | None = None
    digest: str | None = None
    reason: ForgeUnsupportedReason | None = None
    media_type: str | None = None
    data: bytes | None = None
    required: bool = False


def inspect_source_skill(
    paths: TechtreePaths, skill_path: Path, *, derived_from: str | None
) -> ForgeSourceStatus:
    """Inventory one Source Skill and write its record, admitted or refused."""
    parent = (
        read_source_status(paths, derived_from).record
        if derived_from is not None
        else None
    )
    root = resolve_skill_root(skill_path)
    if root.is_symlink():
        raise ValidationError(
            f"the Skill is named through a link, which is never followed: {root}",
            code="forge_source_invalid",
            details={"path": str(root)},
        )
    entries = _inventory(root)
    by_path = {entry.path: entry for entry in entries}
    refusals = _mark_required(entries, by_path)
    refusals += [
        _refusal(
            entry.path,
            "required_unsupported",
            f"{entry.path} is named by the Skill's instructions but "
            f"{UNSUPPORTED_WORDS[entry.reason]}",
        )
        for entry in entries
        if entry.required and entry.reason is not None
    ]
    entrypoint = by_path[SKILL_ENTRY_FILE]
    declaration = None
    if entrypoint.data is not None:
        declaration, problems = _declaration(entrypoint.data.decode(), root.name)
        refusals += problems
    admitted = [entry for entry in entries if entry.reason is None]
    refusals += _totals(admitted)
    admitted_files = [
        SkillFile(
            path=entry.path,
            media_type=str(entry.media_type),
            size=len(entry.data or b""),
            digest=str(entry.digest),
        )
        for entry in admitted
    ]
    admitted_digest = skill_content_digest(admitted_files)
    if parent is not None and parent.admitted_digest == admitted_digest:
        raise ValidationError(
            "this copy admits exactly what the Skill it was derived from admits, "
            "so it is not a different Skill; a derivative has to differ from "
            "its original",
            code="forge_source_unchanged",
            details={"derived_from": parent.source_id, "digest": admitted_digest},
        )

    source_id = new_id("forgesrc")
    directory = paths.forge_source_dir(source_id)
    record = ForgeSourceRecord(
        schema_version=FORGE_SOURCE_SCHEMA_VERSION,
        source_id=source_id,
        created_at=datetime.now(UTC),
        origin=str(root.absolute()),
        state="refused" if refusals else "admitted",
        declaration=declaration,
        entries=[
            ForgeSourceEntry(
                path=entry.path,
                kind=entry.kind,  # type: ignore[arg-type]
                size=entry.size,
                digest=entry.digest,
                disposition="admitted" if entry.reason is None else "unsupported",
                reason=entry.reason,
                required=entry.required,
            )
            for entry in entries
        ],
        admitted_files=admitted_files,
        admitted_digest=admitted_digest,
        refusals=refusals,
        lineage=(
            ForgeSourceLineage(
                parent_source_id=parent.source_id,
                parent_admitted_digest=parent.admitted_digest,
            )
            if parent is not None
            else None
        ),
    )
    directory.mkdir(parents=True, mode=0o700)
    if record.state == "admitted":
        for entry in admitted:
            atomic_write_bytes(
                directory / SKILL_DIRNAME / entry.path, entry.data or b""
            )
    atomic_write_json(directory / SOURCE_FILENAME, record.model_dump(mode="json"))
    return _status(directory, record)


def read_source_status(paths: TechtreePaths, source_id: str) -> ForgeSourceStatus:
    """Read one inspected Source Skill's record back from its directory."""
    directory = paths.forge_source_dir(validate_id(source_id, "forgesrc"))
    record_file = directory / SOURCE_FILENAME
    if not record_file.is_file():
        raise NotFoundError(
            f"no inspected Source Skill {source_id}",
            code="forge_source_not_found",
            details={"source_id": source_id, "path": str(directory)},
        )
    try:
        record = ForgeSourceRecord.model_validate_json(record_file.read_bytes())
    except ModelValidationError as error:
        issue = error.errors(include_input=False, include_url=False)[0]
        raise ValidationError(
            f"invalid Source Skill record: {issue['msg']}",
            code="forge_evidence_invalid",
            details={"source_id": source_id, "file": str(record_file)},
        ) from error
    return _status(directory, record)


def _status(directory: Path, record: ForgeSourceRecord) -> ForgeSourceStatus:
    return ForgeSourceStatus(
        source_id=record.source_id,
        path=str(directory),
        snapshot_path=(
            str(directory / SKILL_DIRNAME) if record.state == "admitted" else None
        ),
        record=record,
    )


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


def _inventory(root: Path) -> list[_Entry]:
    listing = _listing(root)
    if listing is None:
        raise ValidationError(
            f"the Skill's directory cannot be read: {root}",
            code="forge_source_invalid",
            details={"path": str(root)},
        )
    entries: list[_Entry] = []
    _walk(root, listing, entries)
    folded: dict[str, list[_Entry]] = {}
    for entry in entries:
        folded.setdefault(entry.path.casefold(), []).append(entry)
    for group in folded.values():
        if len(group) > 1:
            for entry in group:
                if entry.reason is None:
                    entry.reason, entry.data = "case_collision", None
    return entries


def _listing(directory: Path) -> list[os.DirEntry[str]] | None:
    try:
        with os.scandir(directory) as found:
            return sorted(found, key=lambda child: child.name)
    except OSError:
        return None


def _walk(root: Path, listing: list[os.DirEntry[str]], entries: list[_Entry]) -> None:
    for child in listing:
        if len(entries) >= _MAX_ENTRIES:
            raise ValidationError(
                f"the Skill's directory holds more than {_MAX_ENTRIES} entries, "
                "which is more than a Skill is",
                code="forge_source_invalid",
                details={"path": str(root), "maximum_entries": _MAX_ENTRIES},
            )
        path = Path(child.path)
        relative = path.relative_to(root).as_posix()
        if child.name.startswith("."):
            entries.append(_Entry(relative, _kind(child), reason="hidden"))
        elif child.is_symlink():
            entries.append(_Entry(relative, "symlink", reason="symlink"))
        elif child.is_dir(follow_symlinks=False):
            nested = _listing(path)
            if nested is None:
                entries.append(_Entry(relative, "directory", reason="unreadable"))
            else:
                _walk(root, nested, entries)
        elif child.is_file(follow_symlinks=False):
            entries.append(_file(path, relative))
        else:
            entries.append(_Entry(relative, "special", reason="special"))


def _kind(child: os.DirEntry[str]) -> str:
    if child.is_symlink():
        return "symlink"
    if child.is_dir(follow_symlinks=False):
        return "directory"
    if child.is_file(follow_symlinks=False):
        return "file"
    return "special"


def _file(path: Path, relative: str) -> _Entry:
    """Hash one regular file, and keep its bytes when it can be admitted."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return _Entry(relative, "file", reason="unreadable")
    with os.fdopen(descriptor, "rb") as handle:
        status = os.fstat(handle.fileno())
        if not stat.S_ISREG(status.st_mode):
            return _Entry(relative, "special", reason="special")
        media_type = MEDIA_TYPES.get(path.suffix.lower())
        if media_type is None or status.st_size > MAX_SKILL_FILE_BYTES:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
            return _Entry(
                relative,
                "file",
                size=status.st_size,
                digest=f"sha256:{digest}",
                reason="file_type" if media_type is None else "too_large",
            )
        data = handle.read(MAX_SKILL_FILE_BYTES + 1)
    entry = _Entry(
        relative,
        "file",
        size=len(data),
        digest=sha256_digest_bytes(data),
        media_type=media_type,
    )
    if len(data) > MAX_SKILL_FILE_BYTES:
        entry.reason = "too_large"
    elif not _is_text(data):
        entry.reason = "not_text"
    else:
        entry.data = data
    return entry


def _is_text(data: bytes) -> bool:
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


# ---------------------------------------------------------------------------
# What the instructions name
# ---------------------------------------------------------------------------


def _mark_required(
    entries: list[_Entry], by_path: dict[str, _Entry]
) -> list[ForgeSourceRefusal]:
    """Follow the names from SKILL.md through admitted text; mark each named."""
    directories = {
        parent.as_posix()
        for entry in entries
        for parent in PurePosixPath(entry.path).parents
        if parent.name
    } | {entry.path for entry in entries if entry.kind == "directory"}
    refusals: list[ForgeSourceRefusal] = []
    queue = [SKILL_ENTRY_FILE]
    by_path[SKILL_ENTRY_FILE].required = True
    while queue:
        current = by_path[queue.pop(0)]
        if current.data is None:
            continue
        text = current.data.decode("utf-8")
        named: set[str] = set()
        for target in _link_targets(text):
            resolved = _resolve_link(current.path, target)
            if resolved is None:
                refusals.append(
                    _refusal(
                        current.path,
                        "outside_reference",
                        f"{current.path} links to {target}, which is outside the Skill",
                    )
                )
            elif resolved in by_path or resolved in directories:
                named.add(resolved)
            elif resolved != ".":
                refusals.append(
                    _refusal(
                        current.path,
                        "missing_reference",
                        f"{current.path} links to {target}, which is not in the Skill",
                    )
                )
        base = posixpath.dirname(current.path)
        for token in _TOKEN.findall(text):
            for candidate in {token, posixpath.join(base, token)}:
                cleaned = posixpath.normpath(candidate.rstrip(".")) + (
                    "/" if candidate.endswith("/") else ""
                )
                if cleaned in by_path:
                    named.add(cleaned)
                elif cleaned.endswith("/") and cleaned[:-1] in directories:
                    named.add(cleaned[:-1])
        for name in sorted(named):
            for entry in _under(name, entries, by_path):
                if not entry.required:
                    entry.required = True
                    queue.append(entry.path)
    return refusals


def _link_targets(text: str) -> list[str]:
    return [
        target
        for target in [*_INLINE_LINK.findall(text), *_REFERENCE_LINK.findall(text)]
        if not _SCHEME.match(target) and not target.startswith(("#", "//"))
    ]


def _resolve_link(source: str, target: str) -> str | None:
    """The Skill-relative path a link names, or ``None`` when it leaves the Skill."""
    bare = unquote(target.split("#", 1)[0].split("?", 1)[0])
    if not bare:
        return "."
    if bare.startswith("/"):
        return None
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(source), bare))
    if resolved == ".." or resolved.startswith("../"):
        return None
    return resolved


def _under(
    name: str, entries: list[_Entry], by_path: dict[str, _Entry]
) -> list[_Entry]:
    if name in by_path:
        return [by_path[name]]
    return [entry for entry in entries if entry.path.startswith(f"{name}/")]


def _refusal(path: str, reason: ForgeRefusalReason, message: str) -> ForgeSourceRefusal:
    return ForgeSourceRefusal(path=path, reason=reason, message=message)


def _totals(admitted: list[_Entry]) -> list[ForgeSourceRefusal]:
    refusals: list[ForgeSourceRefusal] = []
    if len(admitted) > MAX_SKILL_FILES:
        refusals.append(
            _refusal(
                ".",
                "too_many_files",
                f"the Skill has {len(admitted)} files Techtree would carry, more "
                f"than the {MAX_SKILL_FILES} allowed",
            )
        )
    total = sum(len(entry.data or b"") for entry in admitted)
    if total > MAX_SKILL_TOTAL_BYTES:
        refusals.append(
            _refusal(
                ".",
                "too_many_bytes",
                f"the files Techtree would carry come to {total} bytes, more than "
                f"the {MAX_SKILL_TOTAL_BYTES} allowed",
            )
        )
    return refusals


# ---------------------------------------------------------------------------
# SKILL.md's header
# ---------------------------------------------------------------------------


def _declaration(
    text: str, directory_name: str
) -> tuple[ForgeSkillDeclaration | None, list[ForgeSourceRefusal]]:
    """Read the header the Agent Skills specification defines, or say why not."""
    try:
        fields, metadata = _header(text)
    except _HeaderError as error:
        return None, [_refusal(SKILL_ENTRY_FILE, "declaration", str(error))]
    allowed_tools = fields.pop("allowed-tools", "")
    try:
        declaration = ForgeSkillDeclaration(
            name=fields.pop("name", ""),
            description=fields.pop("description", ""),
            license=fields.pop("license", None),
            compatibility=fields.pop("compatibility", None),
            metadata=metadata,
            allowed_tools=allowed_tools.split(),
            other_fields=fields,
        )
    except ModelValidationError as error:
        issue = error.errors(include_input=False, include_url=False)[0]
        field = ".".join(str(part) for part in issue["loc"])
        return None, [
            _refusal(
                SKILL_ENTRY_FILE,
                "declaration",
                f"SKILL.md declares a {field} the Agent Skills specification does "
                f"not allow: {issue['msg']}",
            )
        ]
    if declaration.name != directory_name:
        return None, [
            _refusal(
                SKILL_ENTRY_FILE,
                "declaration",
                f"SKILL.md names the Skill {declaration.name} but its folder is "
                f"called {directory_name}, and the Agent Skills specification "
                "requires them to match: rename the folder to "
                f"{declaration.name}, or change the name in SKILL.md",
            )
        ]
    return declaration, []


class _HeaderError(Exception):
    """A header line Techtree does not read, said in words."""


def _header(text: str) -> tuple[dict[str, str], dict[str, str]]:
    lines = [line.removesuffix("\r") for line in text.split("\n")]
    if lines[0] != "---":
        raise _HeaderError("SKILL.md does not begin with a --- header")
    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise _HeaderError("SKILL.md's header has no closing ---") from error
    fields: dict[str, str] = {}
    metadata: dict[str, str] = {}
    in_metadata = False
    for number, line in enumerate(lines[1:end], start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        nested = _NESTED.match(line)
        if nested is not None:
            key, value = nested.group(1), nested.group(2)
            if not in_metadata:
                raise _HeaderError(
                    f"SKILL.md line {number} is indented outside metadata, YAML "
                    "Techtree does not read"
                )
            if value is None:
                raise _HeaderError(
                    f"SKILL.md line {number} nests another level under metadata; "
                    "each metadata entry is one key: value line"
                )
            _put(metadata, key, _scalar(value, number), number)
            continue
        top = _TOP_LEVEL.match(line)
        if top is None:
            raise _HeaderError(
                f"SKILL.md line {number} is not a key: value line Techtree reads"
            )
        key, value = top.group(1), top.group(2)
        in_metadata = key == "metadata" and value is None
        if in_metadata:
            if key in fields or "metadata" in fields:
                raise _HeaderError(f"SKILL.md line {number} repeats metadata")
            fields["metadata"] = ""
            continue
        if value is None:
            raise _HeaderError(
                f"SKILL.md line {number} gives {key} no value, or nested YAML "
                "Techtree does not read"
            )
        _put(fields, key, _scalar(value, number), number)
    fields.pop("metadata", None)
    return fields, metadata


def _put(target: dict[str, str], key: str, value: str, number: int) -> None:
    if key in target:
        raise _HeaderError(f"SKILL.md line {number} repeats {key}")
    target[key] = value


def _scalar(raw: str, number: int) -> str:
    value = raw.strip()
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except ValueError:
            parsed = None
        if not isinstance(parsed, str):
            raise _HeaderError(
                f"SKILL.md line {number} has a double-quoted value Techtree cannot read"
            )
        return parsed
    if value.startswith("'"):
        inner = value[1:-1] if len(value) > 1 and value.endswith("'") else None
        if inner is None or "'" in inner.replace("''", ""):
            raise _HeaderError(
                f"SKILL.md line {number} has a single-quoted value Techtree cannot read"
            )
        return inner.replace("''", "'")
    if (
        value[:1] in set("&*!|>{[%@`,?:#")
        or value.startswith("- ")
        or ": " in value
        or " #" in value
        or value.endswith(":")
    ):
        raise _HeaderError(
            f"SKILL.md line {number} uses YAML Techtree does not read; quote the "
            "value to keep it as plain text"
        )
    return value
