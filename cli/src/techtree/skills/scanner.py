"""Validate and scan a candidate skill directory. Spec section 15.2.

This module answers one question completely: given a path a participant typed,
what exactly is going to be snapshotted, and is any of it something we must
refuse to copy?

It refuses rather than repairs. A symlink is not resolved, a hidden file is not
skipped, an oversized file is not truncated, and a file holding what looks like
a credential is not stripped. Every one of those would produce a snapshot that
differs from what the participant believes they submitted, and the snapshot is
the scientific input to an experiment.

Two rules govern secret handling and neither has an exception:

* A finding names the rule, the file, and the line. It never carries the
  matched text, and neither does the error raised for it, so nothing secret
  reaches a log, an error envelope, or a support transcript.
* A ``blocking`` finding stops the scan. Only ``warning`` findings are
  returned, which is why :attr:`SkillScanResult.secret_findings` holds warnings
  alone: anything blocking has already raised.

The rules are deliberately conservative. They look for credential shapes that
are hard to write by accident — key blocks, provider token prefixes, and
assignments to secret-sounding names — and they ignore environment references
and placeholders, because a skill that documents ``API_KEY=${MY_KEY}`` is doing
the right thing and must not be punished for it.
"""

from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Final, Literal

from techtree.canonical import sha256_digest_bytes
from techtree.errors import NotFoundError, ValidationError
from techtree.fs import realpath_within
from techtree.models.base import Digest, JsonValue
from techtree.models.skill import SKILL_ENTRY_FILE, SecretFinding
from techtree.skills.policy import SkillPolicy

__all__ = [
    "MEDIA_TYPES",
    "ScannedFile",
    "SkillScanResult",
    "enumerate_files",
    "media_type_for",
    "resolve_skill_root",
    "scan_file_for_secrets",
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
    secret_findings: list[SecretFinding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


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
# Secret rules
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _SecretRule:
    rule_id: str
    pattern: re.Pattern[str]
    severity: Literal["warning", "blocking"]


#: A name that, when something is assigned to it, is almost certainly a secret.
_SECRET_NAME = (
    r"[A-Za-z0-9_.-]*"
    r"(?:api[_-]?key|access[_-]?key|secret[_-]?key|secret|token|password|passwd|"
    r"passphrase|credential|private[_-]?key)"
    r"[A-Za-z0-9_.-]*"
)

#: Names that only sound like secrets. Every entry is a real Techtree field or
#: a common counter, and flagging one would train participants to ignore the
#: scanner. Kept in step with ``techtree.errors``.
_SAFE_NAMES: Final[frozenset[str]] = frozenset(
    {
        "credential_env",
        "max_tokens",
        "num_tokens",
        "secret_scanning",
        "token_count",
        "tokens",
        "total_tokens",
    }
)

_SECRET_ASSIGNMENT = re.compile(
    rf"(?i)(?P<name>\b{_SECRET_NAME})[\"']?\s*[:=]\s*"
    r"(?P<value>\"[^\"]*\"|'[^']*'|<[^>]*>|\S+)"
)

_RULES: Final[tuple[_SecretRule, ...]] = (
    _SecretRule(
        rule_id="private_key_block",
        pattern=re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY(?: BLOCK)?-----"),
        severity="blocking",
    ),
    _SecretRule(
        rule_id="authorization_header",
        pattern=re.compile(
            r"(?i)\bauthorization\b\s*[:=]\s*[\"']?(?:bearer|basic|token)\s+\S+"
        ),
        severity="blocking",
    ),
    _SecretRule(
        rule_id="provider_token_prefix",
        pattern=re.compile(
            r"\b(?:"
            r"sk-[A-Za-z0-9_-]{16,}"
            r"|(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{16,}"
            r"|gh[pousr]_[A-Za-z0-9]{20,}"
            r"|github_pat_[A-Za-z0-9_]{20,}"
            r"|xox[abprs]-[A-Za-z0-9-]{10,}"
            r"|glpat-[A-Za-z0-9_-]{16,}"
            r"|AIza[A-Za-z0-9_-]{30,}"
            r")\b"
        ),
        severity="blocking",
    ),
    _SecretRule(
        rule_id="aws_access_key_id",
        pattern=re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        severity="blocking",
    ),
    _SecretRule(
        rule_id="aws_secret_assignment",
        pattern=re.compile(
            r"(?i)\baws_(?:secret_access_key|session_token)\b\s*[:=]\s*\S+"
        ),
        severity="blocking",
    ),
)

#: A long unbroken run of key-ish characters. Digests, Verifiers task hashes,
#: and hexadecimal fingerprints are exactly the identifiers a skill has a good
#: reason to quote, so pure hexadecimal is excluded and the rest is a warning
#: rather than a refusal.
_OPAQUE_RUN = re.compile(r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+_-]{40,}={0,2}")
_PURE_HEX = re.compile(r"[0-9a-fA-F]+")

#: Values that name a secret instead of being one: environment references,
#: angle-bracket placeholders, and masked text.
_PLACEHOLDER = re.compile(
    r"^(?:"
    r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?"
    r"|<[^>]*>"
    r"|\.{3,}"
    r"|\*+"
    r"|x{3,}"
    r")$",
    re.IGNORECASE,
)
_ENV_REFERENCE = re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?")


def _is_placeholder(raw_value: str) -> bool:
    """Return whether an assigned value names a secret rather than holding one."""
    value = raw_value.strip().strip("\"'").strip()
    if not value:
        return True
    if _PLACEHOLDER.fullmatch(value):
        return True
    # ``Bearer ${TOKEN}`` and friends: an environment reference with decoration.
    return bool(_ENV_REFERENCE.fullmatch(value.split()[-1]))


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
# Secret scanning
# ---------------------------------------------------------------------------


def scan_file_for_secrets(path: Path) -> list[SecretFinding]:
    """Find secret patterns without returning secret text."""
    reported = str(path)
    return _findings_for_text(_decode_text(path.read_bytes(), reported), reported)


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


def _findings_for_text(text: str, reported_path: str) -> list[SecretFinding]:
    """Report at most one finding per line.

    A credential usually matches several rules at once — an AWS secret is also
    a secret assignment, and a key body is also an opaque run. One line, one
    finding, named by the most specific rule that fired, is what a participant
    can act on.
    """
    findings: list[SecretFinding] = []
    for number, line in enumerate(text.splitlines(), start=1):
        rule_id, severity = _classify_line(line)
        if rule_id is None or severity is None:
            continue
        findings.append(
            SecretFinding(
                path=reported_path,
                rule_id=rule_id,
                line=number,
                severity=severity,
            )
        )
    return findings


def _classify_line(
    line: str,
) -> tuple[str | None, Literal["warning", "blocking"] | None]:
    """Return the most specific rule that fires on one line, if any."""
    for rule in _RULES:
        if rule.pattern.search(line):
            return rule.rule_id, rule.severity
    if _has_secret_assignment(line):
        return "secret_assignment", "blocking"
    if _has_opaque_run(line):
        return "high_entropy_string", "warning"
    return None, None


def _has_secret_assignment(line: str) -> bool:
    for match in _SECRET_ASSIGNMENT.finditer(line):
        name = match.group("name").strip("\"' ").lower()
        if name in _SAFE_NAMES:
            continue
        if _is_placeholder(match.group("value")):
            continue
        return True
    return False


def _has_opaque_run(line: str) -> bool:
    return any(
        not _PURE_HEX.fullmatch(match.group(0)) for match in _OPAQUE_RUN.finditer(line)
    )


# ---------------------------------------------------------------------------
# Whole-skill scan
# ---------------------------------------------------------------------------


def scan_skill(
    path: Path,
    policy: SkillPolicy,
) -> SkillScanResult:
    """Perform complete validation and scanning.

    Raises :class:`~techtree.errors.ValidationError` for anything the policy
    forbids and for any blocking secret finding. The findings attached to a
    successful result are warnings, and the caller decides what to do with
    them.
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
    findings: list[SecretFinding] = []
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
        reported = relative.as_posix()
        findings.extend(_findings_for_text(_decode_text(data, reported), reported))
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
    _reject_blocking_findings(findings)

    return SkillScanResult(
        root=root,
        files=sorted(files, key=lambda item: item.relative_path.as_posix()),
        secret_findings=findings,
        warnings=_warnings_for(findings),
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


def _reject_blocking_findings(findings: list[SecretFinding]) -> None:
    blocking = [item for item in findings if item.severity == "blocking"]
    if not blocking:
        return
    located: list[JsonValue] = [
        {"path": item.path, "rule_id": item.rule_id, "line": item.line}
        for item in blocking
    ]
    summary = ", ".join(
        f"{item.path}:{item.line} ({item.rule_id})" for item in blocking
    )
    raise ValidationError(
        "skill contains what looks like a credential and was not snapshotted; "
        f"remove it and prepare again: {summary}",
        details={"findings": located},
    )


def _warnings_for(findings: list[SecretFinding]) -> list[str]:
    return [
        f"{item.path}:{item.line} looks like an opaque credential "
        f"({item.rule_id}); confirm it is not one before submitting"
        for item in findings
        if item.severity == "warning"
    ]
