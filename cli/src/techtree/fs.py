"""Safe filesystem primitives. Spec section 10.9.

Two properties matter here and both are about what a reader can observe.

*Atomicity.* A reader must never see a half-written file. Writes go to a
temporary file in the same directory, are flushed and fsynced, and then replace
the target with ``os.replace``, which is atomic within a filesystem. The
containing directory is fsynced afterwards so the rename itself survives a
crash.

*Immutability.* Campaign, Climb, DataPolicy, manifest, lock, and receipt
artifacts are written exactly once. :func:`open_exclusive` creates them with
``O_EXCL``, so a second attempt to write one is reported as a conflict instead
of quietly replacing evidence.

Nothing here follows symlinks into a location the caller did not name.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import BinaryIO, cast

from techtree.canonical import to_json_value
from techtree.errors import ConflictError, NotFoundError, ValidationError
from techtree.models.base import JsonValue

__all__ = [
    "atomic_write_bytes",
    "atomic_write_json",
    "atomic_write_text",
    "ensure_private_directory",
    "fsync_directory",
    "open_exclusive",
    "read_json",
    "realpath_within",
    "remove_tree",
]

#: Owner read and write only. Techtree state is single-user by design.
_FILE_MODE = 0o600
#: Owner traversal only, so a run directory is not world-readable.
_DIRECTORY_MODE = 0o700


def atomic_write_bytes(path: Path, data: bytes, *, mode: int = _FILE_MODE) -> None:
    """Write, fsync, chmod, and atomically replace."""
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)

    handle, temporary_name = tempfile.mkstemp(
        dir=directory, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    fsync_directory(directory)


def atomic_write_text(path: Path, text: str, *, mode: int = _FILE_MODE) -> None:
    """UTF-8 wrapper."""
    atomic_write_bytes(path, text.encode("utf-8"), mode=mode)


def atomic_write_json(path: Path, value: object, *, mode: int = _FILE_MODE) -> None:
    """Write readable JSON atomically.

    This is the human-readable spelling, indented and newline-terminated. It is
    not the canonical spelling; anything that is going to be hashed is
    serialized with :func:`techtree.canonical.canonical_json_bytes`.
    """
    rendered = json.dumps(
        to_json_value(value),
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )
    atomic_write_text(path, f"{rendered}\n", mode=mode)


def read_json(path: Path) -> JsonValue:
    """Read UTF-8 JSON and raise typed malformed-data errors."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError as error:
        raise NotFoundError(
            f"no such file: {path}",
            details={"path": str(path)},
        ) from error

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValidationError(
            f"file is not valid UTF-8: {path}",
            details={"path": str(path)},
        ) from error

    try:
        return cast(JsonValue, json.loads(text))
    except json.JSONDecodeError as error:
        raise ValidationError(
            f"file is not valid JSON: {path} ({error.msg} at line {error.lineno})",
            details={"path": str(path), "line": error.lineno},
        ) from error


def ensure_private_directory(path: Path) -> None:
    """Create a directory and apply 0700 where supported."""
    if path.is_symlink():
        raise ValidationError(
            f"refusing to use a symlinked directory: {path}",
            details={"path": str(path)},
        )
    path.mkdir(parents=True, exist_ok=True)
    # Windows and some network filesystems have no POSIX mode bits. The
    # directory still exists, which is what the caller asked for.
    with suppress(NotImplementedError, OSError):
        os.chmod(path, _DIRECTORY_MODE)


def fsync_directory(path: Path) -> None:
    """Best-effort directory fsync."""
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        # Directory fsync is unsupported on some platforms and filesystems.
        pass
    finally:
        os.close(descriptor)


def remove_tree(path: Path) -> None:
    """Remove run-owned data without following links."""
    if path.is_symlink():
        # Unlink the link itself; never descend into whatever it points at.
        path.unlink()
        return
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
        return
    path.unlink()


def realpath_within(path: Path, root: Path) -> bool:
    """Return whether a resolved path is contained in root."""
    return path.resolve().is_relative_to(root.resolve())


def open_exclusive(path: Path, mode: int = _FILE_MODE) -> BinaryIO:
    """Create an immutable file with O_EXCL semantics."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, mode)
    except FileExistsError as error:
        raise ConflictError(
            f"refusing to overwrite an immutable artifact: {path}",
            details={"path": str(path)},
        ) from error
    return cast(BinaryIO, os.fdopen(descriptor, "wb"))
