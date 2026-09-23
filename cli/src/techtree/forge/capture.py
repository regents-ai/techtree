"""What a subject left in its working directory, recorded before grading.

A Skill task's subject works in the task image's working directory, copied
out to the host and mounted back into its sandbox. That directory is read
twice: once as the image left it, before the subject starts, and once after
the subject has finished and its sandbox is gone. The difference is the
subject's output: every entry it added, modified or deleted, each with its
type, size and digest, and the bytes of every regular file it left, within
the bounds the run declared. The manifest is written before the tests run,
so what they graded is on record even if they change the directory.

Nothing here follows a link on the host. Entries are read with ``lstat``, a
file is opened only with ``O_NOFOLLOW`` and read only once ``fstat`` says it
is a regular file, and a link's target is recorded as written. What cannot
be taken as it is becomes an explicit failure: a link that, followed the way
the container would follow it, strays at any step from the entries recorded
in the working directory or ends outside it, whether the subject left the
link or only changed what one of the image's links passes through; an entry
that is not a file, folder or link; a required output the subject did not
leave; an output too large to keep; and a capture left incomplete by the
bounds or by an entry that could not be read or kept.
"""

from __future__ import annotations

import hashlib
import os
import stat
from collections import deque
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

from techtree.canonical import canonical_json_bytes, sha256_digest_bytes
from techtree.forge.models import (
    FORGE_OUTPUT_MANIFEST_SCHEMA_VERSION,
    ForgeOutputChange,
    ForgeOutputChangeKind,
    ForgeOutputEntry,
    ForgeOutputFailure,
    ForgeOutputKind,
    ForgeOutputLimits,
    ForgeOutputManifest,
    ForgeOutputs,
)
from techtree.fs import atomic_write_bytes

__all__ = [
    "MANIFEST_FILENAME",
    "OUTPUT_LIMITS",
    "Snapshot",
    "capture_outputs",
    "take_snapshot",
]

#: The bounds a run on a Skill collection declares for each working
#: directory: how many entries are read, how many bytes are read to digest
#: them, and how many bytes of the subject's files are kept.
OUTPUT_LIMITS: Final = ForgeOutputLimits(
    entries=10_000, checked_bytes=1024 * 1024 * 1024, kept_bytes=64 * 1024 * 1024
)
MANIFEST_FILENAME: Final = "manifest.json"
_KEPT_DIRNAME: Final = "files"
_CHUNK: Final = 1024 * 1024
#: Links followed in one resolution before it counts as a loop, as Linux does.
_LINK_HOPS: Final = 40
#: Path parts walked in one resolution before the link is refused unfollowed.
_LINK_STEPS: Final = 4096


@dataclass(frozen=True)
class Snapshot:
    """A working directory's entries by relative path, and what went unread.

    ``unread`` holds the paths whose state is unknown: a folder that could
    not be listed, an entry that could not be read, and ``""`` for the whole
    directory once a bound stopped the read.
    """

    entries: dict[str, ForgeOutputEntry]
    unread: list[str]
    incomplete: list[ForgeOutputFailure]


def take_snapshot(root: Path, limits: ForgeOutputLimits) -> Snapshot:
    """Read every entry under ``root`` without following a link."""
    reader = _Reader(limits)
    reader.walk(root)
    return Snapshot(
        entries=reader.entries, unread=reader.unread, incomplete=reader.incomplete
    )


def capture_outputs(
    root: Path,
    before: Snapshot,
    *,
    work_dir: str,
    artifacts: list[str],
    limits: ForgeOutputLimits,
    destination: Path,
) -> ForgeOutputs:
    """Record what changed under ``root`` since ``before``, and keep it.

    ``work_dir`` is where ``root`` is mounted in the task's containers and
    ``artifacts`` are the task's required outputs, both container paths,
    every artifact inside ``work_dir``. The manifest and the kept files are
    written under ``destination``. An entry whose state after the subject is
    unknown is not reported as deleted; the capture is incomplete instead.
    """
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    after = take_snapshot(root, limits)
    failures = [*before.incomplete, *after.incomplete]
    base = PurePosixPath(work_dir)
    tree, earlier = _tree(after.entries), _tree(before.entries)
    changes: list[ForgeOutputChange] = []
    kept_bytes = 0
    for path in sorted(before.entries.keys() | after.entries.keys()):
        old, new = before.entries.get(path), after.entries.get(path)
        if old == new:
            # A link the subject left alone can still be turned outward by
            # what it changed along the way.
            if (
                new is not None
                and new.target is not None
                and _leaves(base, path, new.target, tree)
                and not _leaves(base, path, new.target, earlier)
            ):
                failures.append(
                    ForgeOutputFailure(
                        kind="escaping_link",
                        path=path,
                        detail=f"the link points to {new.target}, which stayed "
                        f"among the entries in {work_dir} until the subject's "
                        "changes and does not now",
                    )
                )
            continue
        if new is None and _unread(after, path):
            continue
        change: ForgeOutputChangeKind = (
            "added" if old is None else "deleted" if new is None else "modified"
        )
        kept = False
        if new is not None and new.kind == "file":
            size = new.size or 0
            if kept_bytes + size > limits.kept_bytes:
                failures.append(
                    ForgeOutputFailure(
                        kind="output_too_large",
                        path=path,
                        detail=f"{size} bytes would pass the "
                        f"{limits.kept_bytes}-byte bound on kept outputs",
                    )
                )
            else:
                kept = _keep(root, path, new, destination / _KEPT_DIRNAME, failures)
                kept_bytes += size if kept else 0
        if (
            new is not None
            and new.target is not None
            and _leaves(base, path, new.target, tree)
        ):
            failures.append(
                ForgeOutputFailure(
                    kind="escaping_link",
                    path=path,
                    detail=f"the link points to {new.target}, which does not stay "
                    f"among the entries in {work_dir}",
                )
            )
        if new is not None and new.kind == "other":
            failures.append(
                ForgeOutputFailure(
                    kind="special_entry",
                    path=path,
                    detail="its contents cannot be recorded",
                )
            )
        changes.append(
            ForgeOutputChange(
                change=change, path=path, before=old, after=new, kept=kept
            )
        )
    for artifact in artifacts:
        relative = PurePosixPath(artifact).relative_to(work_dir).as_posix()
        if relative != "." and relative not in after.entries:
            failures.append(
                ForgeOutputFailure(
                    kind="artifact_missing",
                    path=relative,
                    detail=f"the task requires {artifact}, and it was not left",
                )
            )
    manifest = ForgeOutputManifest(
        schema_version=FORGE_OUTPUT_MANIFEST_SCHEMA_VERSION,
        work_dir=work_dir,
        limits=limits,
        changes=changes,
        kept_bytes=kept_bytes,
        failures=failures,
    )
    encoded = canonical_json_bytes(manifest)
    atomic_write_bytes(destination / MANIFEST_FILENAME, encoded)
    return ForgeOutputs(
        work_dir=work_dir,
        manifest_digest=sha256_digest_bytes(encoded),
        added=sum(change.change == "added" for change in changes),
        modified=sum(change.change == "modified" for change in changes),
        deleted=sum(change.change == "deleted" for change in changes),
        kept_bytes=kept_bytes,
        failures=failures,
    )


class _Reader:
    """One bounded, link-free read of a directory tree, depth first."""

    def __init__(self, limits: ForgeOutputLimits) -> None:
        self._limits = limits
        self._checked = 0
        self.entries: dict[str, ForgeOutputEntry] = {}
        self.unread: list[str] = []
        self.incomplete: list[ForgeOutputFailure] = []

    def walk(self, root: Path) -> None:
        pending = [(root, PurePosixPath())]
        while pending:
            directory, relative = pending.pop()
            where = relative.as_posix() if relative.parts else None
            try:
                with os.scandir(directory) as found:
                    children = sorted(found, key=lambda child: child.name)
            except OSError as error:
                self._incomplete(where, f"not listed: {_why(error)}")
                self.unread.append(where or "")
                continue
            folders = []
            for child in children:
                if len(self.entries) >= self._limits.entries:
                    self._stop(
                        None,
                        f"more than {self._limits.entries} entries; the rest were "
                        "not read",
                    )
                    return
                if not _is_text(child.name):
                    self._incomplete(
                        where, "an entry whose name is not text was not read"
                    )
                    continue
                path = (relative / child.name).as_posix()
                entry = self._entry(Path(child.path), path)
                if entry is None:
                    if self.unread[-1:] == [""]:
                        return
                    self.unread.append(path)
                    continue
                self.entries[path] = entry
                if entry.kind == "directory":
                    folders.append((Path(child.path), PurePosixPath(path)))
            pending.extend(reversed(folders))

    def _entry(self, where: Path, path: str) -> ForgeOutputEntry | None:
        try:
            status = os.lstat(where)
        except OSError as error:
            self._incomplete(path, f"not read: {_why(error)}")
            return None
        if stat.S_ISDIR(status.st_mode):
            return _entry(path, "directory")
        if stat.S_ISLNK(status.st_mode):
            try:
                target = os.readlink(where)
            except OSError as error:
                self._incomplete(path, f"not read: {_why(error)}")
                return None
            if not _is_text(target):
                self._incomplete(path, "the link's target is not text")
                return None
            return _entry(path, "symlink", target=target)
        if not stat.S_ISREG(status.st_mode):
            return _entry(path, "other")
        if self._checked + status.st_size > self._limits.checked_bytes:
            self._stop(
                path,
                f"reading it would pass the {self._limits.checked_bytes}-byte "
                "bound on what is checked; the rest were not read",
            )
            return None
        digest = self._digest(where, path)
        if digest is None:
            return None
        return ForgeOutputEntry(
            path=path,
            kind="file",
            size=digest[1],
            digest=digest[0],
            executable=bool(status.st_mode & stat.S_IXUSR),
            target=None,
        )

    def _digest(self, where: Path, path: str) -> tuple[str, int] | None:
        """Digest a regular file through a descriptor that follows no link."""
        try:
            descriptor = os.open(
                where, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
            )
        except OSError as error:
            self._incomplete(path, f"not read: {_why(error)}")
            return None
        hasher = hashlib.sha256()
        size = 0
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                self._incomplete(path, "it stopped being a regular file while read")
                return None
            while chunk := os.read(descriptor, _CHUNK):
                size += len(chunk)
                self._checked += len(chunk)
                if self._checked > self._limits.checked_bytes:
                    self._stop(
                        path,
                        f"it grew past the {self._limits.checked_bytes}-byte "
                        "bound on what is checked",
                    )
                    return None
                hasher.update(chunk)
        except OSError as error:
            self._incomplete(path, f"not read: {_why(error)}")
            return None
        finally:
            os.close(descriptor)
        return f"sha256:{hasher.hexdigest()}", size

    def _stop(self, path: str | None, detail: str) -> None:
        self._incomplete(path, detail)
        self.unread.append("")

    def _incomplete(self, path: str | None, detail: str) -> None:
        self.incomplete.append(
            ForgeOutputFailure(kind="capture_incomplete", path=path, detail=detail)
        )


def _entry(
    path: str, kind: ForgeOutputKind, *, target: str | None = None
) -> ForgeOutputEntry:
    return ForgeOutputEntry(
        path=path, kind=kind, size=None, digest=None, executable=False, target=target
    )


def _keep(
    root: Path,
    path: str,
    entry: ForgeOutputEntry,
    kept: Path,
    failures: list[ForgeOutputFailure],
) -> bool:
    """Copy one regular file the subject left, if it is still what was read."""
    try:
        descriptor = os.open(
            root / path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
        )
        with os.fdopen(descriptor, "rb") as source:
            data = source.read((entry.size or 0) + 1)
    except OSError as error:
        failures.append(_incomplete(path, f"not kept: {_why(error)}"))
        return False
    if sha256_digest_bytes(data) != entry.digest:
        failures.append(_incomplete(path, "it changed between reading and keeping"))
        return False
    copy = kept / path
    try:
        copy.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        written = os.open(
            copy,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
        )
        with os.fdopen(written, "wb") as out:
            out.write(data)
    except OSError as error:
        failures.append(_incomplete(path, f"not kept: {_why(error)}"))
        return False
    return True


def _incomplete(path: str, detail: str) -> ForgeOutputFailure:
    return ForgeOutputFailure(kind="capture_incomplete", path=path, detail=detail)


@dataclass(frozen=True)
class _Node:
    """One entry of the directory after the subject, with the entries under it."""

    entry: ForgeOutputEntry | None
    children: dict[str, _Node]


def _tree(entries: dict[str, ForgeOutputEntry]) -> _Node:
    root = _Node(entry=None, children={})
    for path in sorted(entries):
        *folders, name = path.split("/")
        node = root
        for folder in folders:
            node = node.children[folder]
        node.children[name] = _Node(entry=entries[path], children={})
    return root


def _leaves(base: PurePosixPath, link: str, target: str, tree: _Node) -> bool:
    """Whether following the link at ``link`` to ``target`` could leave ``base``.

    The target is walked one part at a time as the container's kernel walks
    it: from the root for an absolute target, from the link's own folder
    otherwise, and through every link it meets. Inside ``base`` each part
    must name an entry recorded there exactly, since the host's disk may
    match a name that differs in case or spelling and lead somewhere else.
    Outside ``base`` a part may only be one of the folders above it, on the
    way back in. The walk must end inside ``base``, within the kernel's 40
    links and a bound on its steps; a link that needs more is refused too.
    """
    above = 0
    *folders, _ = link.split("/")
    stack = [tree]
    for folder in folders:
        stack.append(stack[-1].children[folder])
    pending = deque(PurePosixPath(target).parts)
    hops = 1
    steps = 0
    while pending:
        steps += 1
        if steps > _LINK_STEPS:
            return True
        part = pending.popleft()
        if part.startswith("/"):
            above, stack = len(base.parts) - 1, [tree]
        elif part == "..":
            if above or len(stack) == 1:
                above = min(above + 1, len(base.parts) - 1)
            else:
                stack.pop()
        elif above:
            if part != base.parts[-above]:
                return True
            above -= 1
        else:
            node = stack[-1].children.get(part)
            if node is None or node.entry is None:
                return True
            if node.entry.kind == "symlink":
                hops += 1
                if hops > _LINK_HOPS:
                    return True
                onward = PurePosixPath(node.entry.target or "").parts
                pending.extendleft(reversed(onward))
            else:
                stack.append(node)
    return above > 0


def _unread(snapshot: Snapshot, path: str) -> bool:
    return any(
        prefix == "" or path == prefix or path.startswith(f"{prefix}/")
        for prefix in snapshot.unread
    )


def _is_text(name: str) -> bool:
    try:
        name.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _why(error: OSError) -> str:
    return error.strerror or "it could not be read"
