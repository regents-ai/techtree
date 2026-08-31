"""The record of what has been published about one run. Decisions 0038.

A run's own event log is closed by the time anybody publishes, and this is the
file that carries what happens afterwards. It is a second append-only journal
rather than an extension of the first, and the tests here hold the three things
that makes it worth having: it never loses its place, it never carries an
outcome it cannot describe, and it never carries a volunteered address.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest
from pydantic import ValidationError as PydanticValidationError

from fixtures.publication import ADDRESS, ENDPOINT, ENTRY_URL, LOG_SEQUENCE
from techtree.canonical import canonical_json_bytes
from techtree.constants import PUBLICATION_JOURNAL_SCHEMA_VERSION
from techtree.errors import ValidationError
from techtree.models.uplift_report import PublicationStatus
from techtree.publication.journal import (
    PUBLICATION_JOURNAL_CORRUPT,
    PublicationJournal,
    PublicationJournalEntry,
)

RUN_ID: Final = "run_0123456789abcdef0123456789abcdef"
BUNDLE: Final = "sha256:" + "a" * 64
_INSTANT: Final = datetime(2026, 8, 27, 9, 0, tzinfo=UTC)


def entry(
    sequence: int,
    status: PublicationStatus,
    **overrides: object,
) -> PublicationJournalEntry:
    values: dict[str, object] = {
        "schema_version": PUBLICATION_JOURNAL_SCHEMA_VERSION,
        "sequence": sequence,
        "at": _INSTANT,
        "run_id": RUN_ID,
        "status": status,
        "bundle_digest": BUNDLE,
        "endpoint": ENDPOINT,
        "file_count": 12,
        "byte_count": 372736,
    }
    if status is PublicationStatus.PUBLISHED:
        values |= {"entry_url": ENTRY_URL, "log_sequence": LOG_SEQUENCE}
    if status is PublicationStatus.FAILED:
        values["error_code"] = "publication_transport_failed"
    values |= overrides
    return PublicationJournalEntry(**values)  # type: ignore[arg-type]


def test_a_run_nobody_published_has_no_journal_and_no_status(tmp_path: Path) -> None:
    """The same answer its report has carried since it was written."""
    journal = PublicationJournal(tmp_path)

    assert journal.entries() == []
    assert journal.status() is PublicationStatus.NOT_REQUESTED
    assert journal.published() is None
    assert not journal.path.exists()


def test_the_status_is_the_last_thing_that_happened(tmp_path: Path) -> None:
    journal = PublicationJournal(tmp_path)

    journal.append(entry(0, PublicationStatus.PENDING))
    assert journal.status() is PublicationStatus.PENDING

    journal.append(entry(1, PublicationStatus.FAILED))
    assert journal.status() is PublicationStatus.FAILED
    assert journal.published() is None

    journal.append(entry(2, PublicationStatus.PENDING))
    journal.append(entry(3, PublicationStatus.PUBLISHED))
    assert journal.status() is PublicationStatus.PUBLISHED
    published = journal.published()
    assert published is not None
    assert published.entry_url == ENTRY_URL


def test_a_journal_that_lost_a_line_is_refused(tmp_path: Path) -> None:
    """A status derived from a history with a hole in it is quietly wrong."""
    journal = PublicationJournal(tmp_path)
    journal.append(entry(0, PublicationStatus.PENDING))
    journal.append(entry(2, PublicationStatus.PUBLISHED))

    with pytest.raises(ValidationError) as raised:
        journal.entries()

    assert raised.value.code == PUBLICATION_JOURNAL_CORRUPT


def test_a_half_written_final_line_is_refused(tmp_path: Path) -> None:
    """A crash mid-append loses a whole line, and a torn one is not a line."""
    journal = PublicationJournal(tmp_path)
    journal.append(entry(0, PublicationStatus.PENDING))
    whole = canonical_json_bytes(entry(1, PublicationStatus.PUBLISHED))
    with journal.path.open("ab") as handle:
        handle.write(whole[: len(whole) // 2] + b"\n")

    with pytest.raises(ValidationError) as raised:
        journal.entries()

    assert raised.value.code == PUBLICATION_JOURNAL_CORRUPT


def test_appending_never_rewrites_what_is_already_there(tmp_path: Path) -> None:
    """Append-only, as bytes: the prefix is identical before and after."""
    journal = PublicationJournal(tmp_path)
    journal.append(entry(0, PublicationStatus.PENDING))
    before = journal.path.read_bytes()

    journal.append(entry(1, PublicationStatus.PUBLISHED))

    assert journal.path.read_bytes().startswith(before)


@pytest.mark.parametrize(
    ("status", "overrides"),
    [
        (PublicationStatus.PUBLISHED, {"entry_url": None}),
        (PublicationStatus.PUBLISHED, {"log_sequence": None}),
        (PublicationStatus.PENDING, {"entry_url": ENTRY_URL, "log_sequence": 1}),
        (PublicationStatus.PENDING, {"error_code": "publication_failed"}),
        (PublicationStatus.FAILED, {"error_code": None}),
        (PublicationStatus.NOT_REQUESTED, {}),
        (PublicationStatus.BLOCKED, {}),
    ],
)
def test_an_entry_that_reports_one_outcome_and_describes_another_is_refused(
    status: PublicationStatus, overrides: dict[str, object]
) -> None:
    """An entry that cannot be interpreted is worse than no entry."""
    with pytest.raises(PydanticValidationError):
        entry(0, status, **overrides)


def test_a_journal_entry_has_nowhere_to_put_an_address() -> None:
    """The field does not exist, so nothing can put one there by accident.

    An address is sent and not kept. This is that rule as a shape rather than
    as a habit: the model forbids unknown fields, so a caller that tried to
    record one would be refused rather than obeyed.
    """
    assert "contributor_address_unverified" not in (
        PublicationJournalEntry.model_fields
    )

    with pytest.raises(PydanticValidationError):
        entry(0, PublicationStatus.PENDING, contributor_address_unverified=ADDRESS)
