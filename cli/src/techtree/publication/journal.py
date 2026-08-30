"""A completed run's publication journal. Decisions document 0038.

A run's own event log closes when the run ends. That is not an inconvenience to
work around: ``events.jsonl`` is the record of an execution, the state machine
is what makes it derivable, and a file that a later command appends to is a file
whose earlier bytes were not final. Publishing happens after all of that, is not
part of the execution, and must not touch a byte the run wrote.

So it is recorded in a journal of its own, in the same run directory, created
the first time somebody publishes and appended to after that. Every property the
run's own log has, this one has for the same reasons: canonical JSON one line at
a time, sequence numbers that start at zero and increase by exactly one, and an
``O_APPEND`` write followed by an ``fsync``, so a crash can lose a trailing line
but cannot interleave two.

What it does not carry is a contributor address. An address is a detail somebody
volunteered about themselves rather than evidence about a run; it is sent and
not kept, so there is nothing here to read it back out of.

The publication status of a run is derived from this file and from nowhere else.
The signed report inside the proof bundle says ``not_requested``, permanently
and correctly: it was not requested when the report was written, and rewriting a
signed document to say otherwise would break the proof it is part of.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final, Literal, Self

from pydantic import Field, model_validator
from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import canonical_json_bytes
from techtree.errors import ValidationError
from techtree.fs import fsync_directory
from techtree.models.base import Digest, NonEmptyString, ProtocolModel, UtcDateTime
from techtree.models.uplift_report import PublicationStatus

__all__ = [
    "ATTEMPT_STATUSES",
    "PUBLICATION_JOURNAL_CORRUPT",
    "PUBLICATION_JOURNAL_FILENAME",
    "PublicationJournal",
    "PublicationJournalEntry",
]

#: The file, beside the run's own records and never inside its proof.
PUBLICATION_JOURNAL_FILENAME: Final = "publication.jsonl"

#: Stable error code for a journal whose lines do not form a history.
PUBLICATION_JOURNAL_CORRUPT: Final = "publication_journal_corrupt"

_LINE_SEPARATOR: Final = b"\n"
#: Owner read and write only, matching every other file Techtree writes.
_FILE_MODE: Final = 0o600

#: The three statuses a publication attempt moves through. The other two
#: members of :class:`~techtree.models.uplift_report.PublicationStatus` describe
#: a report rather than an attempt: ``not_requested`` is what a run with no
#: journal at all is, and ``blocked`` is a data policy's answer, decided before
#: anything is attempted.
ATTEMPT_STATUSES: Final[frozenset[PublicationStatus]] = frozenset(
    {
        PublicationStatus.PENDING,
        PublicationStatus.PUBLISHED,
        PublicationStatus.FAILED,
    }
)


class PublicationJournalEntry(ProtocolModel):
    """One thing that happened when somebody published this run."""

    schema_version: Literal["techtree.publication-journal.v1alpha1"]
    sequence: int = Field(ge=0)
    at: UtcDateTime
    run_id: NonEmptyString
    status: PublicationStatus
    #: The bundle this attempt was about, so a journal with several attempts in
    #: it says which proof each one carried.
    bundle_digest: Digest
    #: Where it was sent. An origin and a path; a submission never travels in a
    #: query string, so nothing here can contain one.
    endpoint: NonEmptyString
    file_count: int = Field(gt=0)
    byte_count: int = Field(gt=0)
    #: Set by a published attempt: where the entry now lives, and the log
    #: position the network gave it.
    entry_url: NonEmptyString | None = None
    log_sequence: int | None = Field(default=None, ge=0)
    #: Set by a failed attempt: the stable code of what went wrong. The message
    #: belongs to the envelope the command already returned; a code is what a
    #: later reader can act on.
    error_code: NonEmptyString | None = None

    @model_validator(mode="after")
    def _check_the_outcome_carries_what_it_means(self) -> Self:
        """Reject an entry that reports one outcome and describes another."""
        if self.status not in ATTEMPT_STATUSES:
            raise ValueError(
                "a journal entry records an attempt, which is pending, "
                "published or failed"
            )
        published = self.status is PublicationStatus.PUBLISHED
        landed = self.entry_url is not None or self.log_sequence is not None
        if published and (self.entry_url is None or self.log_sequence is None):
            raise ValueError(
                "a published entry records where it landed and its log position"
            )
        if not published and landed:
            raise ValueError(
                "only a published entry has somewhere it landed and a log position"
            )
        failed = self.status is PublicationStatus.FAILED
        if failed and self.error_code is None:
            raise ValueError("a failed entry records why it failed")
        if not failed and self.error_code is not None:
            raise ValueError("only a failed entry carries a failure code")
        return self


class PublicationJournal:
    """The append-only record of what has been published about one run."""

    def __init__(self, run_root: Path) -> None:
        self._path = run_root / PUBLICATION_JOURNAL_FILENAME

    @property
    def path(self) -> Path:
        """Return the journal file, whether or not it exists yet."""
        return self._path

    def entries(self) -> list[PublicationJournalEntry]:
        """Return every entry, refusing a history with a hole in it.

        A sequence that skips is a journal that lost a line, and a status
        derived from it would be quietly wrong. That check also catches a
        half-written trailing line, which fails to parse before its sequence is
        ever considered.
        """
        try:
            raw = self._path.read_bytes()
        except FileNotFoundError:
            return []

        entries: list[PublicationJournalEntry] = []
        for position, line in enumerate(raw.splitlines()):
            if not line.strip():
                continue
            try:
                entry = PublicationJournalEntry.model_validate_json(line)
            except PydanticValidationError as error:
                raise ValidationError(
                    f"line {position + 1} of this run's publication journal "
                    "cannot be read",
                    code=PUBLICATION_JOURNAL_CORRUPT,
                    details={"path": str(self._path), "line": position + 1},
                ) from error
            if entry.sequence != len(entries):
                raise ValidationError(
                    f"this run's publication journal jumps from {len(entries) - 1} "
                    f"to {entry.sequence}, so a line is missing",
                    code=PUBLICATION_JOURNAL_CORRUPT,
                    details={"path": str(self._path), "sequence": entry.sequence},
                )
            entries.append(entry)
        return entries

    def status(self) -> PublicationStatus:
        """Return where this run stands, derived from the journal alone.

        A run nobody has published has no journal, and that is
        ``not_requested`` — the same thing its report has said since it was
        written.
        """
        entries = self.entries()
        if not entries:
            return PublicationStatus.NOT_REQUESTED
        return entries[-1].status

    def published(self) -> PublicationJournalEntry | None:
        """Return the entry that published this run, if one did."""
        for entry in reversed(self.entries()):
            if entry.status is PublicationStatus.PUBLISHED:
                return entry
        return None

    def next_sequence(self) -> int:
        """Return the sequence the next appended entry takes."""
        return len(self.entries())

    def append(self, entry: PublicationJournalEntry) -> None:
        """Append one entry durably.

        A single ``O_APPEND`` write of one whole line, then an ``fsync``. The
        entry is serialized before the file is opened, so an entry that cannot
        be written down does not leave a partial line behind it.
        """
        line = canonical_json_bytes(entry) + _LINE_SEPARATOR
        descriptor = os.open(
            self._path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, _FILE_MODE
        )
        try:
            written = 0
            while written < len(line):
                written += os.write(descriptor, line[written:])
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        fsync_directory(self._path.parent)
