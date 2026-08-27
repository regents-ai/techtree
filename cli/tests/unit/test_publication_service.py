"""Publishing one run, with the one network step substituted. Decisions 0038.

Everything about publishing is local except the request, so everything about
publishing is tested here except the request: a stub transport stands in for it,
records the bytes it was handed, and answers with a receipt a test wrote. What
is exercised on either side of that stub is the real code, including the real
offline verification of a real signed bundle.

The properties these tests hold are the ones that would make the feature a
mistake if they stopped being true:

* a proof that does not verify is never published, whatever else is true of it;
* a report that may not be published is not published;
* no file the run already wrote is touched, byte for byte;
* an address that was volunteered is in the request body and nowhere on disk.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from fixtures.publication import (
    ADDRESS,
    ENDPOINT,
    ENTRY_URL,
    LOG_SEQUENCE,
    RefusingTransport,
    StubTransport,
    receipt_for,
)
from fixtures.receipts.proof import (
    PROOF_RUN_ID,
    RecordedProof,
    signed_proof,
    write_proof,
)
from techtree.canonical import canonical_json_bytes
from techtree.errors import (
    ConflictError,
    NotFoundError,
    PolicyError,
    PrerequisiteError,
    TechtreeError,
    ValidationError,
    VerificationError,
)
from techtree.models.uplift_report import PublicationStatus, UpliftDecision
from techtree.publication.journal import (
    PUBLICATION_JOURNAL_FILENAME,
    PublicationJournal,
)
from techtree.publication.models import PublicationCheck
from techtree.publication.service import (
    PUBLICATION_ENDPOINT_NOT_CONFIGURED,
    PUBLICATION_NOT_ELIGIBLE,
    PUBLICATION_PROOF_NOT_FOUND,
    PUBLICATION_RECEIPT_FILENAME,
    PUBLICATION_RECEIPT_INVALID,
    RUN_ALREADY_PUBLISHED,
    PublicationPlan,
    PublicationService,
)
from techtree.receipts.bundle import BUNDLE_MANIFEST_FILENAME, PROOF_BUNDLE_INVALID

# ---------------------------------------------------------------------------
# A run with a proof in it
# ---------------------------------------------------------------------------


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "runs"
    directory.mkdir()
    return directory


@pytest.fixture
def proof(tmp_path: Path, runs_dir: Path) -> RecordedProof:
    recorded = signed_proof(tmp_path / "home")
    write_proof(recorded, runs_dir / PROOF_RUN_ID)
    return recorded


def service(
    runs_dir: Path,
    transport: object,
    *,
    endpoint: str | None = ENDPOINT,
) -> PublicationService:
    return PublicationService(
        runs_dir=runs_dir,
        endpoint=endpoint,
        transport=transport,  # type: ignore[arg-type]
        clock=lambda: datetime(2026, 8, 27, 9, 0, tzinfo=UTC),
    )


def fingerprint(directory: Path) -> dict[str, str]:
    """Return every file under a directory and the digest of its bytes."""
    return {
        path.relative_to(directory).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------


def test_the_plan_is_the_whole_proof_directory(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """What is sent is the bytes on disk, including the signed manifest.

    The manifest cannot commit to itself, so a submission that carried only the
    files it names would carry nothing the receiver could check them against.
    """
    plan = service(runs_dir, StubTransport()).plan(PROOF_RUN_ID)

    on_disk = fingerprint(runs_dir / PROOF_RUN_ID / "proof")
    assert set(plan.paths) == set(on_disk)
    assert BUNDLE_MANIFEST_FILENAME in plan.paths
    assert plan.byte_count == sum(
        (runs_dir / PROOF_RUN_ID / "proof" / path).stat().st_size for path in plan.paths
    )
    for entry in plan.files:
        assert (
            base64.b64decode(entry.content)
            == (runs_dir / PROOF_RUN_ID / "proof" / entry.path).read_bytes()
        )


def test_the_proof_directory_carries_no_transcript(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """The claim the review makes to a person, checked rather than repeated.

    Every file that would travel is canonical JSON of a protocol document, and
    the vocabulary those documents use has no field for a prompt or a reply.
    """
    plan = service(runs_dir, StubTransport()).plan(PROOF_RUN_ID)

    forbidden = ("prompt", "completion", "messages", "content", "reply", "response")
    for entry in plan.files:
        text = base64.b64decode(entry.content).decode("utf-8").lower()
        for word in forbidden:
            assert f'"{word}"' not in text, (entry.path, word)


def test_a_run_with_no_proof_here_is_not_published(runs_dir: Path) -> None:
    with pytest.raises(NotFoundError) as raised:
        service(runs_dir, StubTransport()).plan(PROOF_RUN_ID)

    assert raised.value.code == PUBLICATION_PROOF_NOT_FOUND


def test_a_proof_that_does_not_verify_is_never_published(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """The whole point of the product, as a refusal.

    One byte of one receipt is changed, which is what a tampered result looks
    like. Nothing is sent, and the transport is never reached at all.
    """
    receipt = runs_dir / PROOF_RUN_ID / "proof" / "receipts" / "baseline" / "0000.json"
    receipt.write_bytes(receipt.read_bytes().replace(b"baseline", b"baselinE", 1))
    transport = StubTransport()

    with pytest.raises(VerificationError) as raised:
        service(runs_dir, transport).plan(PROOF_RUN_ID)

    assert raised.value.code == PROOF_BUNDLE_INVALID
    assert transport.bodies == []


def test_a_report_that_may_not_be_published_is_not(
    tmp_path: Path, runs_dir: Path
) -> None:
    """A development-only report has no eligibility and never gains one.

    The bundle here verifies perfectly well. What it does not do is claim a
    grade that entitles it to be published, which is a separate refusal for a
    separate reason.
    """
    write_proof(
        signed_proof(
            tmp_path / "home",
            proof_grade="development_only",
            decision=UpliftDecision.DEVELOPMENT_ONLY,
        ),
        runs_dir / PROOF_RUN_ID,
    )
    transport = StubTransport()

    with pytest.raises(PolicyError) as raised:
        service(runs_dir, transport).plan(PROOF_RUN_ID)

    assert raised.value.code == PUBLICATION_NOT_ELIGIBLE
    assert transport.bodies == []


def test_a_build_with_no_run_log_configured_refuses_to_guess(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """There is no default address, and inventing one is the one wrong answer."""
    with pytest.raises(PrerequisiteError) as raised:
        service(runs_dir, StubTransport(), endpoint=None).plan(PROOF_RUN_ID)

    assert raised.value.code == PUBLICATION_ENDPOINT_NOT_CONFIGURED


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------


def test_publishing_writes_the_receipt_and_records_the_outcome(
    proof: RecordedProof, runs_dir: Path
) -> None:
    transport = StubTransport()
    publisher = service(runs_dir, transport)

    outcome = publisher.publish(publisher.plan(PROOF_RUN_ID))

    assert transport.endpoints == [ENDPOINT]
    assert outcome.receipt_path.name == PUBLICATION_RECEIPT_FILENAME
    assert outcome.receipt_path.is_file()
    assert publisher.status(PROOF_RUN_ID) is PublicationStatus.PUBLISHED

    journal = PublicationJournal(runs_dir / PROOF_RUN_ID).entries()
    assert [entry.status for entry in journal] == [
        PublicationStatus.PENDING,
        PublicationStatus.PUBLISHED,
    ]
    assert journal[-1].entry_url == ENTRY_URL
    assert journal[-1].log_sequence == LOG_SEQUENCE


def test_publishing_modifies_no_file_the_run_already_wrote(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """Append-only, held as bytes rather than as an intention.

    Every file in the run directory is fingerprinted before and after. What
    publishing may do is add files; what it may not do is change one.
    """
    before = fingerprint(runs_dir / PROOF_RUN_ID)
    publisher = service(runs_dir, StubTransport())

    publisher.publish(publisher.plan(PROOF_RUN_ID))

    after = fingerprint(runs_dir / PROOF_RUN_ID)
    for path, digest in before.items():
        assert after[path] == digest, path
    assert set(after) - set(before) == {
        PUBLICATION_RECEIPT_FILENAME,
        PUBLICATION_JOURNAL_FILENAME,
    }


def test_a_run_already_in_the_log_is_not_published_twice(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """A published entry is withdrawn, never replaced."""
    publisher = service(runs_dir, StubTransport())
    publisher.publish(publisher.plan(PROOF_RUN_ID))

    with pytest.raises(ConflictError) as raised:
        publisher.plan(PROOF_RUN_ID)

    assert raised.value.code == RUN_ALREADY_PUBLISHED


def test_a_failed_attempt_is_recorded_and_leaves_no_receipt(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """The journal is the record of what was attempted, not only of what worked."""
    publisher = service(runs_dir, RefusingTransport())
    plan = publisher.plan(PROOF_RUN_ID)

    with pytest.raises(TechtreeError):
        publisher.publish(plan)

    assert publisher.status(PROOF_RUN_ID) is PublicationStatus.FAILED
    entries = PublicationJournal(runs_dir / PROOF_RUN_ID).entries()
    assert [entry.status for entry in entries] == [
        PublicationStatus.PENDING,
        PublicationStatus.FAILED,
    ]
    assert entries[-1].error_code == "publication_transport_failed"
    assert not (runs_dir / PROOF_RUN_ID / PUBLICATION_RECEIPT_FILENAME).exists()


def test_a_failed_attempt_can_be_made_again(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """Nothing was published, so nothing stands in the way of trying again."""
    publisher = service(runs_dir, RefusingTransport())
    with pytest.raises(TechtreeError):
        publisher.publish(publisher.plan(PROOF_RUN_ID))

    second = service(runs_dir, StubTransport())
    second.publish(second.plan(PROOF_RUN_ID))

    assert second.status(PROOF_RUN_ID) is PublicationStatus.PUBLISHED
    assert len(PublicationJournal(runs_dir / PROOF_RUN_ID).entries()) == 4


def test_a_receipt_for_a_different_submission_is_refused(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """A receipt that names another bundle is not this run's evidence of anything."""
    transport = StubTransport(
        answer=lambda submission: canonical_json_bytes(
            receipt_for(submission, bundle_digest="sha256:" + "0" * 63 + "1")
        )
    )
    publisher = service(runs_dir, transport)

    with pytest.raises(ValidationError) as raised:
        publisher.publish(publisher.plan(PROOF_RUN_ID))

    assert raised.value.code == PUBLICATION_RECEIPT_INVALID
    assert not (runs_dir / PROOF_RUN_ID / PUBLICATION_RECEIPT_FILENAME).exists()


def test_a_receipt_reporting_a_failed_check_is_refused(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """A log that says it did not accept a submission has not accepted it."""
    transport = StubTransport(
        answer=lambda submission: canonical_json_bytes(
            receipt_for(
                submission,
                checks=[
                    PublicationCheck(
                        id="bundle.signature",
                        passed=False,
                        detail="a signature did not verify here",
                    )
                ],
            )
        )
    )
    publisher = service(runs_dir, transport)

    with pytest.raises(ValidationError) as raised:
        publisher.publish(publisher.plan(PROOF_RUN_ID))

    assert raised.value.code == PUBLICATION_RECEIPT_INVALID


def test_an_answer_that_is_not_a_receipt_is_refused(
    proof: RecordedProof, runs_dir: Path
) -> None:
    transport = StubTransport(answer=lambda _submission: b"<html>hello</html>")
    publisher = service(runs_dir, transport)

    with pytest.raises(ValidationError) as raised:
        publisher.publish(publisher.plan(PROOF_RUN_ID))

    assert raised.value.code == PUBLICATION_RECEIPT_INVALID


# ---------------------------------------------------------------------------
# The volunteered address
# ---------------------------------------------------------------------------


def test_no_address_is_sent_unless_one_was_given(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """The default is no, and the default is what the field carries."""
    transport = StubTransport()
    publisher = service(runs_dir, transport)

    outcome = publisher.publish(publisher.plan(PROOF_RUN_ID))

    assert transport.addresses == [None]
    assert outcome.contributor_address_sent is False


def test_an_address_travels_beside_the_body_and_lands_nowhere_on_disk(
    proof: RecordedProof, runs_dir: Path, tmp_path: Path
) -> None:
    """The rule that makes an address safe to ask for.

    It goes beside the request and into nothing else: not into the submission,
    not the journal, not the receipt, not the proof, not any file anywhere under
    the Techtree home. The search below is over every byte of the tree rather
    than over the files this test happens to know about.

    Beside rather than inside is the whole of it. The run log stores the
    submission it is given and serves those exact bytes back at a public
    address, so an address written into the body would be public by
    construction however carefully everything after it behaved.
    """
    transport = StubTransport()
    publisher = service(runs_dir, transport)

    outcome = publisher.publish(
        publisher.plan(PROOF_RUN_ID), contributor_address=ADDRESS.lower()
    )

    assert transport.addresses == [ADDRESS.lower()]
    assert outcome.contributor_address_sent is True
    # Not in the body either, which is the bytes the run log serves back.
    assert ADDRESS.lower().encode() not in transport.bodies[0].lower()
    assert ADDRESS[2:].lower().encode() not in transport.bodies[0].lower()
    for path in sorted(tmp_path.rglob("*")):
        if not path.is_file():
            continue
        raw = path.read_bytes().lower()
        assert ADDRESS.lower().encode() not in raw, path
        assert ADDRESS[2:].lower().encode() not in raw, path


def test_nothing_about_an_address_is_in_the_endpoint(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """Never a URL and never a query string, so never in anybody's access log."""
    transport = StubTransport()
    publisher = service(runs_dir, transport)

    publisher.publish(publisher.plan(PROOF_RUN_ID), contributor_address=ADDRESS.lower())

    assert transport.endpoints == [ENDPOINT]
    assert "?" not in transport.endpoints[0]


def test_the_plan_says_what_a_person_is_shown(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """The three numbers the review prints come off the plan, not off a guess."""
    plan: PublicationPlan = service(runs_dir, StubTransport()).plan(PROOF_RUN_ID)

    assert plan.file_count == len(plan.files) > 1
    assert plan.byte_count > 0
    assert plan.endpoint == ENDPOINT
    assert plan.bundle_digest.startswith("sha256:")
