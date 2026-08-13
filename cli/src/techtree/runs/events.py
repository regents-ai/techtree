"""The append-only run event log. Spec section 18.1.

One run event is one line of canonical JSON. The log is only ever appended to,
never rewritten, which is what lets a reader that arrives halfway through a run
reconstruct everything that has happened without coordinating with the writer.

Three properties are deliberate.

*Canonical bytes.* Lines are serialized with
:func:`techtree.canonical.canonical_json_bytes`, so the same events always
produce the same file and :func:`event_digest` is a meaningful identity for a
run's history rather than an accident of dictionary ordering.

*Durability.* Each append is a single write to a file opened with ``O_APPEND``
followed by an ``fsync``. A crash can therefore lose a whole trailing event, but
it cannot interleave one event's bytes with another's.

*Discontinuity is fatal.* Sequence numbers start at zero and increase by exactly
one. A log that skips is a log that lost something, and a state projected from
it would be quietly wrong; :func:`read_events` refuses it instead. That check is
also what catches a truncated final line, because a partly written event fails
to parse before its sequence is ever considered.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import canonical_json_bytes, sha256_digest_bytes
from techtree.errors import NotFoundError, ValidationError
from techtree.fs import fsync_directory
from techtree.models.base import Digest
from techtree.models.run import RunEvent

__all__ = [
    "append_event",
    "event_digest",
    "next_sequence",
    "read_events",
]

_LINE_SEPARATOR: Final = b"\n"
#: Owner read and write only, matching every other file Techtree writes.
_FILE_MODE: Final = 0o600


def append_event(path: Path, event: RunEvent) -> None:
    """Append compact JSONL and fsync."""
    line = canonical_json_bytes(event) + _LINE_SEPARATOR

    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    descriptor = os.open(path, flags, _FILE_MODE)
    try:
        written = 0
        while written < len(line):
            written += os.write(descriptor, line[written:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)

    # The first append also creates the directory entry, and a durable file
    # whose name is not durable is not much use after a crash.
    fsync_directory(path.parent)


def read_events(path: Path) -> list[RunEvent]:
    """Read events and reject sequence discontinuity."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError as error:
        raise NotFoundError(
            f"no run event log at {path}",
            details={"path": str(path)},
        ) from error

    lines = raw.split(_LINE_SEPARATOR)
    # A well-formed log ends with a separator, which leaves one empty trailing
    # element. Any other empty line is damage.
    if lines and lines[-1] == b"":
        lines.pop()

    events: list[RunEvent] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            raise ValidationError(
                f"run event log line {number} is empty: {path}",
                details={"path": str(path), "line": number},
            )
        try:
            event = RunEvent.model_validate_json(line)
        except PydanticValidationError as error:
            raise ValidationError(
                f"run event log line {number} is not a run event: {path} "
                f"({error.errors()[0]['msg']})",
                details={"path": str(path), "line": number},
            ) from error

        expected = len(events)
        if event.sequence != expected:
            raise ValidationError(
                f"run event log skips from sequence {expected - 1} to "
                f"{event.sequence}: {path}",
                details={
                    "path": str(path),
                    "line": number,
                    "expected_sequence": expected,
                    "sequence": event.sequence,
                },
            )
        events.append(event)

    return events


def next_sequence(events: list[RunEvent]) -> int:
    """Return next sequence number."""
    if not events:
        return 0
    return events[-1].sequence + 1


def event_digest(path: Path) -> Digest:
    """Digest exact event-log bytes."""
    try:
        return sha256_digest_bytes(path.read_bytes())
    except FileNotFoundError as error:
        raise NotFoundError(
            f"no run event log at {path}",
            details={"path": str(path)},
        ) from error
