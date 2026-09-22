"""Commit complete emitted task trees without following untrusted filesystem links.

Paths, file bytes, directory membership and the owner-executable bit matter.
Ownership, timestamps and other permission bits do not. No filename is excluded.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from pydantic import TypeAdapter

from techtree.canonical import digest_object, sha256_digest_stream
from techtree.errors import RunError
from techtree.forge.models import (
    FORGE_TASK_CONTENT_SCHEMA_VERSION,
    FORGE_TASK_SET_SCHEMA_VERSION,
    ForgeTaskId,
    TaskContentEntry,
    TaskContentManifest,
    TaskSetCommitment,
)

__all__ = ["commit_task_set", "verify_task_set"]


@contextmanager
def _directory(path: Path | str, parent: int | None = None) -> Iterator[int]:
    descriptor = os.open(
        path,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        dir_fd=parent,
    )
    try:
        yield descriptor
    finally:
        os.close(descriptor)


def stat_signature(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _file(parent: int, name: str, relative: str) -> TaskContentEntry:
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
        dir_fd=parent,
    )
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"not a regular file: {relative!r}")
        digest = sha256_digest_stream(stream)
        if stat_signature(before) != stat_signature(os.fstat(stream.fileno())):
            raise ValueError(f"file changed while hashing: {relative!r}")
    return TaskContentEntry(
        path=relative,
        kind="file",
        executable=bool(before.st_mode & stat.S_IXUSR),
        size=before.st_size,
        digest=digest,
    )


def _walk(descriptor: int, prefix: str = "") -> list[TaskContentEntry]:
    before = os.fstat(descriptor)
    names = sorted(os.listdir(descriptor))
    entries: list[TaskContentEntry] = []
    for name in names:
        # Refuse invalid names before opening anything beneath them.
        relative = prefix + name
        TaskContentEntry.validate_path(relative)
        mode = os.stat(name, dir_fd=descriptor, follow_symlinks=False).st_mode
        if stat.S_ISDIR(mode):
            with _directory(name, descriptor) as child:
                entries.append(
                    TaskContentEntry(
                        path=relative,
                        kind="directory",
                        executable=bool(os.fstat(child).st_mode & stat.S_IXUSR),
                        size=0,
                        digest=None,
                    )
                )
                entries.extend(_walk(child, relative + "/"))
        elif stat.S_ISREG(mode):
            entries.append(_file(descriptor, name, relative))
        else:
            raise ValueError(f"symlink or special file in task content: {relative!r}")
    if names != sorted(os.listdir(descriptor)) or stat_signature(
        before
    ) != stat_signature(os.fstat(descriptor)):
        raise ValueError(f"directory changed while hashing: {prefix!r}")
    return entries


def commit_task_set(tasks_dir: Path, task_ids: list[str]) -> TaskSetCommitment:
    """Hash all named task trees in execution order; refuse, never skip, bad input."""
    try:
        TypeAdapter(list[ForgeTaskId]).validate_python(task_ids)
        if len(set(task_ids)) != len(task_ids):
            raise ValueError("duplicate task ids in generation membership")
        tasks: list[TaskContentManifest] = []
        with _directory(tasks_dir) as root:
            for task_id in task_ids:
                with _directory(task_id, root) as descriptor:
                    entries = sorted(_walk(descriptor), key=lambda entry: entry.path)
                tasks.append(
                    TaskContentManifest(
                        schema_version=FORGE_TASK_CONTENT_SCHEMA_VERSION,
                        task_id=task_id,
                        entries=entries,
                        content_digest=digest_object(
                            {
                                "schema_version": FORGE_TASK_CONTENT_SCHEMA_VERSION,
                                "entries": entries,
                            }
                        ),
                    )
                )
        return TaskSetCommitment(
            schema_version=FORGE_TASK_SET_SCHEMA_VERSION,
            tasks=tasks,
            membership_digest=digest_object(
                {
                    "schema_version": FORGE_TASK_SET_SCHEMA_VERSION,
                    "tasks": [
                        {"task_id": task.task_id, "content_digest": task.content_digest}
                        for task in tasks
                    ],
                }
            ),
        )
    except (OSError, ValueError) as error:
        raise RunError(
            f"cannot commit task content: {error}",
            code="forge_task_content_invalid",
        ) from error


def verify_task_set(tasks_dir: Path, expected: TaskSetCommitment) -> None:
    """Refuse qualification if any committed task bytes or membership have drifted."""
    observed = commit_task_set(tasks_dir, [task.task_id for task in expected.tasks])
    if observed.membership_digest != expected.membership_digest:
        raise RunError(
            "task content changed since the build commitment",
            code="forge_task_content_changed",
            details={
                "expected": expected.membership_digest,
                "observed": observed.membership_digest,
            },
        )
