"""The deterministic snapshot archive. Spec section 15.3.

A skill archive is content-addressed, so two people who submit the same files
must produce the same bytes. Ordinary tar does not do that: it records the
mtime, owner, group, and permission bits it happens to find, none of which are
part of what the participant wrote. Every one of those is normalized here —
mtime 0, uid and gid 0, empty owner names, mode 0644, members in lexicographic
order — until the only thing left that can change the archive digest is the
content of the files.

The archive is uncompressed in WP2. Compression would add a second thing to
keep deterministic (the compressor's version and settings) in exchange for
saving a few kilobytes on a two-megabyte cap.

Extraction is the other half. :func:`safe_extract_archive` never uses
``extractall``: it reads each member itself and refuses links, devices,
absolute names, and traversal, because an archive is untrusted input the moment
it comes back off disk.
"""

from __future__ import annotations

import io
import tarfile
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from techtree.canonical import sha256_digest_bytes
from techtree.errors import NotFoundError, ValidationError, VerificationError
from techtree.fs import atomic_write_bytes, ensure_private_directory
from techtree.models.base import Digest
from techtree.models.skill import SkillArtifact
from techtree.skills.scanner import ScannedFile

__all__ = [
    "build_deterministic_tar",
    "normalized_tar_info",
    "safe_extract_archive",
    "verify_archive",
]

#: The single mode every member carries. Skill files are data a harness reads;
#: none of them is executable, and preserving the source machine's bits would
#: make the digest depend on a participant's umask.
_MEMBER_MODE = 0o644
#: The format is pinned rather than left to the tarfile default, which has
#: changed between Python versions. PAX spells long names and non-ASCII names
#: in exactly one way.
_TAR_FORMAT = tarfile.PAX_FORMAT


def normalized_tar_info(
    relative_path: PurePosixPath,
    size: int,
) -> tarfile.TarInfo:
    """Return uid/gid 0, empty names, mtime 0, mode 0644."""
    _require_safe_member_name(relative_path.as_posix())
    if size < 0:
        raise ValidationError(
            f"archive member size cannot be negative: {relative_path}",
            details={"path": relative_path.as_posix(), "size": size},
        )

    info = tarfile.TarInfo(name=relative_path.as_posix())
    info.size = size
    info.mtime = 0
    info.mode = _MEMBER_MODE
    info.type = tarfile.REGTYPE
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    return info


def build_deterministic_tar(
    files: Sequence[ScannedFile],
    output_path: Path,
) -> Digest:
    """Write lexicographically and return archive digest.

    The caller's ordering is irrelevant: members are sorted by their POSIX
    relative path. Each file is re-read and re-digested here, so a source file
    edited between the scan and the snapshot is reported rather than quietly
    archived.
    """
    ordered = sorted(files, key=lambda item: item.relative_path.as_posix())
    _reject_duplicate_members(ordered)

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=_TAR_FORMAT) as archive:
        for item in ordered:
            data = _read_unchanged(item)
            archive.addfile(
                normalized_tar_info(item.relative_path, len(data)),
                io.BytesIO(data),
            )

    payload = buffer.getvalue()
    atomic_write_bytes(output_path, payload)
    return sha256_digest_bytes(payload)


def _reject_duplicate_members(files: Sequence[ScannedFile]) -> None:
    seen: set[str] = set()
    for item in files:
        posix = item.relative_path.as_posix()
        if posix in seen:
            raise ValidationError(
                f"archive would contain the same path twice: {posix}",
                details={"path": posix},
            )
        seen.add(posix)


def _read_unchanged(item: ScannedFile) -> bytes:
    """Read a scanned file and confirm it is still what was scanned."""
    try:
        data = item.source_path.read_bytes()
    except FileNotFoundError as error:
        raise VerificationError(
            "a scanned skill file disappeared before it could be archived: "
            f"{item.relative_path}",
            details={"path": item.relative_path.as_posix()},
        ) from error

    if len(data) != item.size or sha256_digest_bytes(data) != item.digest:
        raise VerificationError(
            "a skill file changed after it was scanned, so the snapshot was "
            f"abandoned: {item.relative_path}",
            details={
                "path": item.relative_path.as_posix(),
                "scanned_size": item.size,
                "observed_size": len(data),
            },
        )
    return data


def verify_archive(
    archive_path: Path,
    artifact: SkillArtifact,
) -> bool:
    """Verify archive and member manifest.

    The artifact is the manifest and the archive is checked against it: same
    members, same order, same sizes, same content digests, and the normalized
    metadata this module writes. Returns ``False`` for any disagreement.
    """
    payload = _read_archive(archive_path)
    if sha256_digest_bytes(payload) != artifact.archive_digest:
        return False

    expected = [(entry.path, entry.size, entry.digest) for entry in artifact.files]

    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
        members = archive.getmembers()
        if len(members) != len(expected):
            return False
        for member, (path, size, digest) in zip(members, expected, strict=True):
            if not _member_is_normalized(member, path, size):
                return False
            stream = archive.extractfile(member)
            if stream is None:
                return False
            if sha256_digest_bytes(stream.read()) != digest:
                return False
    return True


def _member_is_normalized(member: tarfile.TarInfo, path: str, size: int) -> bool:
    return (
        member.isreg()
        and member.name == path
        and member.size == size
        and member.mtime == 0
        and member.mode == _MEMBER_MODE
        and member.uid == 0
        and member.gid == 0
        and member.uname == ""
        and member.gname == ""
    )


def safe_extract_archive(
    archive_path: Path,
    destination: Path,
) -> None:
    """Reject links, devices, absolute paths, and traversal.

    Only regular-file members are accepted, which is everything
    :func:`build_deterministic_tar` writes. Parent directories are created by
    this function, so a hostile archive cannot use a directory member to place
    anything of its own choosing.
    """
    payload = _read_archive(archive_path)
    ensure_private_directory(destination)
    root = destination.resolve()

    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
        for member in archive.getmembers():
            _require_extractable(member)
            target = _resolve_member_target(member.name, root)
            stream = archive.extractfile(member)
            if stream is None:
                raise ValidationError(
                    f"archive member has no readable content: {member.name}",
                    details={"member": member.name},
                )
            ensure_private_directory(target.parent)
            atomic_write_bytes(target, stream.read())


def _require_extractable(member: tarfile.TarInfo) -> None:
    if member.issym() or member.islnk():
        raise ValidationError(
            f"archive contains a link, which is never extracted: {member.name}",
            details={"member": member.name, "kind": "link"},
        )
    if member.ischr() or member.isblk() or member.isfifo() or member.isdev():
        raise ValidationError(
            f"archive contains a device or FIFO entry: {member.name}",
            details={"member": member.name, "kind": "device"},
        )
    if not member.isreg():
        raise ValidationError(
            f"archive contains an entry that is not a regular file: {member.name}",
            details={"member": member.name, "kind": "not_regular"},
        )
    _require_safe_member_name(member.name)


def _require_safe_member_name(name: str) -> None:
    if not name or name in {".", ".."}:
        raise ValidationError(
            "archive member name is empty or refers to a directory itself",
            details={"member": name},
        )
    if (
        name.startswith("/")
        or name.startswith("\\")
        or PurePosixPath(name).is_absolute()
    ):
        raise ValidationError(
            f"archive member name is absolute: {name}",
            details={"member": name},
        )
    if "\\" in name:
        raise ValidationError(
            f"archive member name contains a backslash: {name}",
            details={"member": name},
        )
    if ".." in PurePosixPath(name).parts:
        raise ValidationError(
            f"archive member name escapes the destination: {name}",
            details={"member": name},
        )
    if name.endswith("/"):
        raise ValidationError(
            f"archive member name is a directory: {name}",
            details={"member": name},
        )


def _resolve_member_target(name: str, root: Path) -> Path:
    target = (root / PurePosixPath(name)).resolve()
    if not target.is_relative_to(root):
        raise ValidationError(
            f"archive member would be written outside the destination: {name}",
            details={"member": name, "destination": str(root)},
        )
    return target


def _read_archive(archive_path: Path) -> bytes:
    try:
        return archive_path.read_bytes()
    except FileNotFoundError as error:
        raise NotFoundError(
            f"no such archive: {archive_path}",
            details={"path": str(archive_path)},
        ) from error
