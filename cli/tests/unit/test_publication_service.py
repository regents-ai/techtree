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
* an address that was volunteered travels beside the request body and lands
  nowhere on disk.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from fixtures.publication import (
    ADDRESS,
    COORDINATES,
    ENDPOINT,
    ENTRY_URL,
    LOG_SEQUENCE,
    NETWORK_KEY,
    PINNED_ENDPOINT,
    PUBLIC_LOG_URL,
    RefusingTransport,
    StubTransport,
    network_signed,
    receipt_for,
)
from fixtures.publication.conformance import (
    CONFORMANCE_RUN_ID,
    FIXTURE_PATH,
    materialize_proof,
)
from fixtures.receipts.proof import (
    PROOF_RUN_ID,
    RecordedProof,
    signed_proof,
    write_proof,
)
from techtree.canonical import (
    canonical_json_bytes,
    digest_object,
    sha256_digest_bytes,
)
from techtree.crypto import (
    load_private_key,
    public_key_bytes,
    public_key_to_base64,
    sign_digest,
)
from techtree.errors import (
    ConflictError,
    NotFoundError,
    PolicyError,
    TechtreeError,
    ValidationError,
    VerificationError,
)
from techtree.models.base import ObjectEnvelope, PublicKeyRef
from techtree.models.uplift_report import PublicationStatus, UpliftDecision
from techtree.publication.journal import (
    PUBLICATION_JOURNAL_FILENAME,
    PublicationJournal,
)
from techtree.publication.models import (
    PublicationCheck,
    PublicationReceiptPayload,
    PublicationSubmission,
)
from techtree.publication.service import (
    PUBLICATION_NOT_ELIGIBLE,
    PUBLICATION_PROOF_NOT_FOUND,
    PUBLICATION_RECEIPT_CONFLICT,
    PUBLICATION_RECEIPT_FILENAME,
    RUN_ALREADY_PUBLISHED,
    PublicationPlan,
    PublicationService,
)
from techtree.publication.transport import PUBLICATION_ENDPOINT_INVALID
from techtree.publication.verify import PUBLICATION_RECEIPT_INVALID
from techtree.receipts.bundle import (
    BUNDLE_DIRECTORY,
    BUNDLE_MANIFEST_FILENAME,
    PROOF_BUNDLE_INVALID,
    REPORT_FILENAME,
)

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
    endpoint_override: str | None = ENDPOINT,
) -> PublicationService:
    return PublicationService(
        runs_dir=runs_dir,
        coordinates=COORDINATES,
        endpoint_override=endpoint_override,
        transport=transport,  # type: ignore[arg-type]
        clock=lambda: datetime(2026, 8, 27, 9, 0, tzinfo=UTC),
    )


def answering(**overrides: object) -> StubTransport:
    """Return a transport answering with a receipt built from ``overrides``."""
    return StubTransport(
        answer=lambda submission: canonical_json_bytes(
            network_signed(receipt_for(submission, **overrides))  # type: ignore[arg-type]
        )
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
# The wire shape
#
# Decisions 0038 fixes it: four members, and ``files`` a mapping of path to
# base64. Both halves of the feature were built at once from opposite ends and
# disagreed about exactly this, so it is held here as bytes rather than as an
# intention.
# ---------------------------------------------------------------------------


def test_the_submission_has_exactly_the_four_members_the_contract_names(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """A fifth member added later fails here rather than at the run log.

    The run log refuses a body carrying anything it did not ask for, because
    what it stores it serves back at a public address. A field somebody adds to
    this model would otherwise be discovered by a participant whose publication
    failed.
    """
    body = json.loads(service(runs_dir, StubTransport()).submission_bytes(PROOF_RUN_ID))

    assert set(body) == {"schema_version", "run_id", "bundle_digest", "files"}
    assert body["schema_version"] == "techtree.publication-submission.v1alpha1"
    assert body["run_id"] == PROOF_RUN_ID


def test_a_submission_that_places_no_file_is_not_a_submission() -> None:
    """An empty mapping is a publication of nothing, and is refused as one.

    The mapping shape already makes it impossible to place one file twice, so
    emptiness is the only way left for the file set to be wrong on its own
    terms, and it is the one the model still has to say out loud.
    """
    with pytest.raises(PydanticValidationError):
        PublicationSubmission(
            schema_version="techtree.publication-submission.v1alpha1",
            run_id=PROOF_RUN_ID,
            bundle_digest="sha256:" + "0" * 64,
            files={},
        )


def test_the_submission_is_the_whole_proof_directory_as_a_mapping(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """What is sent is the bytes on disk, including the signed manifest.

    The manifest cannot commit to itself, so a submission that carried only the
    files it names would carry nothing the receiver could check them against.
    """
    body = json.loads(service(runs_dir, StubTransport()).submission_bytes(PROOF_RUN_ID))

    directory = runs_dir / PROOF_RUN_ID / "proof"
    assert set(body["files"]) == set(fingerprint(directory))
    assert BUNDLE_MANIFEST_FILENAME in body["files"]
    for path, content in body["files"].items():
        assert base64.b64decode(content) == (directory / path).read_bytes()


def test_no_file_travels_with_a_digest_or_a_size_beside_it(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """The reason ``files`` is a mapping, held as a shape rather than a comment.

    A digest the submitter wrote next to bytes the submitter wrote is worth
    nothing and is dangerous the moment anybody downstream believes it. Every
    digest the receiving side works with comes out of the bundle's own signed
    manifest, so the submission gives it nothing else to reach for.

    Held over the raw bytes rather than the parsed document, because the names
    of the fields the earlier shape carried are what must not come back. Base64
    cannot contain a quotation mark, so a quoted key in this body is a key.
    """
    raw = service(runs_dir, StubTransport()).submission_bytes(PROOF_RUN_ID)

    for gone in (b'"digest"', b'"size"', b'"content"', b'"path"'):
        assert gone not in raw, gone


def test_the_proof_directory_carries_no_transcript(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """The claim the review makes to a person, checked rather than repeated.

    Every file that would travel is canonical JSON of a protocol document, and
    the vocabulary those documents use has no field for a prompt or a reply.
    """
    body = json.loads(service(runs_dir, StubTransport()).submission_bytes(PROOF_RUN_ID))

    forbidden = ("prompt", "completion", "messages", "content", "reply", "response")
    for path, content in body["files"].items():
        text = base64.b64decode(content).decode("utf-8").lower()
        for word in forbidden:
            assert f'"{word}"' not in text, (path, word)


def test_the_request_carries_exactly_the_submission_that_was_built(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """One builder, one shape, and no second document that merely looks alike.

    The conformance fixture the receiving side is tested against comes out of
    :meth:`~techtree.publication.service.PublicationService.submission_bytes`.
    This is what makes that fixture evidence about the request rather than
    about a function nothing sends.
    """
    transport = StubTransport()
    publisher = service(runs_dir, transport)

    publisher.publish(publisher.plan(PROOF_RUN_ID))

    assert transport.bodies == [publisher.submission_bytes(PROOF_RUN_ID)]


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------


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


def test_a_build_with_nothing_configured_publishes_to_the_pinned_address(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """A stable release publishes out of the box. Decisions 0038's founder ruling.

    The address is a release coordinate rather than a setting, so a wheel
    somebody installed and never configured still knows where the run log is.
    """
    plan = service(runs_dir, StubTransport(), endpoint_override=None).plan(PROOF_RUN_ID)

    assert plan.endpoint == PINNED_ENDPOINT


def test_a_development_override_wins_over_the_pinned_address(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """The override is for a throwaway local instance, and it is what is used."""
    transport = StubTransport()
    publisher = service(runs_dir, transport, endpoint_override=ENDPOINT)

    plan = publisher.plan(PROOF_RUN_ID)
    publisher.publish(plan)

    assert plan.endpoint == ENDPOINT
    assert transport.endpoints == [ENDPOINT]


def test_an_override_that_is_not_an_address_is_refused(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """A person can get the override wrong; nothing else here can."""
    transport = StubTransport()

    with pytest.raises(ValidationError) as raised:
        service(
            runs_dir, transport, endpoint_override="http://techtree.example/log"
        ).plan(PROOF_RUN_ID)

    assert raised.value.code == PUBLICATION_ENDPOINT_INVALID
    assert transport.bodies == []


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
    transport = answering(bundle_digest="sha256:" + "0" * 63 + "1")
    publisher = service(runs_dir, transport)

    with pytest.raises(ValidationError) as raised:
        publisher.publish(publisher.plan(PROOF_RUN_ID))

    assert raised.value.code == PUBLICATION_RECEIPT_INVALID
    assert not (runs_dir / PROOF_RUN_ID / PUBLICATION_RECEIPT_FILENAME).exists()


def test_a_receipt_reporting_a_failed_check_is_refused(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """A log that says it did not accept a submission has not accepted it."""
    transport = answering(
        checks=[
            PublicationCheck(
                id="bundle.signature",
                passed=False,
                detail="a signature did not verify here",
            )
        ]
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
    """The three numbers the review prints come off the plan, not off a guess.

    They are counted off the proof directory rather than off the encoded
    submission, so what a person is shown is the size of the thing they
    recognise — their run's proof — and not the size of its base64.
    """
    directory = runs_dir / PROOF_RUN_ID / "proof"
    plan: PublicationPlan = service(runs_dir, StubTransport()).plan(PROOF_RUN_ID)

    assert plan.file_count == len(fingerprint(directory)) > 1
    assert plan.byte_count == sum(
        path.stat().st_size for path in directory.rglob("*") if path.is_file()
    )
    assert plan.endpoint == ENDPOINT
    assert plan.bundle_digest.startswith("sha256:")


# ---------------------------------------------------------------------------
# The countersignature
#
# Requiring a receipt to carry a key and a signature proves nothing: a server
# that wanted to lie would invent a key and sign its own invention with it. What
# these hold is that the key is the pinned one, that the signature is over the
# payload that arrived, and that the entry address is on the log this release
# names. Decisions 0038's founder ruling of 2026-08-27.
# ---------------------------------------------------------------------------


def _unverified(envelope: object) -> StubTransport:
    """Return a transport answering with these exact envelope bytes."""
    return StubTransport(answer=lambda _submission: canonical_json_bytes(envelope))


def _refuses(runs_dir: Path, transport: StubTransport) -> ValidationError:
    """Publish through a transport that answers badly, and return the refusal."""
    publisher = service(runs_dir, transport)
    with pytest.raises(ValidationError) as raised:
        publisher.publish(publisher.plan(PROOF_RUN_ID))
    assert not (runs_dir / PROOF_RUN_ID / PUBLICATION_RECEIPT_FILENAME).exists()
    assert raised.value.code == PUBLICATION_RECEIPT_INVALID
    return raised.value


def test_a_receipt_nobody_signed_is_refused(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """A receipt with no signature is a claim with nothing behind it."""
    payload = receipt_for(_submission(runs_dir))
    envelope = ObjectEnvelope[PublicationReceiptPayload](
        payload=payload, payload_digest=digest_object(payload), signature=None
    )

    error = _refuses(runs_dir, _unverified(envelope))

    assert error.details["check"] == "receipt.signature_present"


def test_a_receipt_signed_by_another_key_is_refused(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """The attack the pin exists for: a key the answering server made up."""
    impostor = load_private_key(bytes(range(100, 132)))
    payload = receipt_for(_submission(runs_dir))
    digest = digest_object(payload)
    envelope = ObjectEnvelope[PublicationReceiptPayload](
        payload=payload,
        payload_digest=digest,
        signature=sign_digest(
            impostor,
            digest,
            key_id=sha256_digest_bytes(public_key_bytes(impostor)),
        ),
    )

    error = _refuses(runs_dir, _unverified(envelope))

    assert error.details["check"] == "receipt.signature_key"


def test_a_receipt_that_names_the_pinned_key_and_signs_with_another_is_refused(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """Naming the right key is not the same as being signed by it."""
    impostor = load_private_key(bytes(range(100, 132)))
    payload = receipt_for(_submission(runs_dir))
    digest = digest_object(payload)
    envelope = ObjectEnvelope[PublicationReceiptPayload](
        payload=payload,
        payload_digest=digest,
        signature=sign_digest(impostor, digest, key_id=NETWORK_KEY.key_id),
    )

    error = _refuses(runs_dir, _unverified(envelope))

    assert error.details["check"] == "receipt.signature"


def test_a_receipt_edited_after_it_was_signed_is_refused(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """The envelope carries the digest it was signed under and never recomputes it.

    So a payload changed afterwards keeps a digest that no longer describes it,
    and recomputing here is what catches it.
    """
    signed = network_signed(receipt_for(_submission(runs_dir)))
    envelope = ObjectEnvelope[PublicationReceiptPayload](
        payload=receipt_for(_submission(runs_dir), log_sequence=1),
        payload_digest=signed.payload_digest,
        signature=signed.signature,
    )

    error = _refuses(runs_dir, _unverified(envelope))

    assert error.details["check"] == "receipt.payload_digest"


def test_a_receipt_carrying_a_key_it_does_not_name_is_refused(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """The identifier is the digest of the key, so this is caught for free."""
    other = load_private_key(bytes(range(100, 132)))
    carried = PublicKeyRef(
        algorithm="ed25519",
        key_id=NETWORK_KEY.key_id,
        public_key=public_key_to_base64(other.public_key()),
    )

    error = _refuses(runs_dir, answering(public_key=carried))

    assert error.details["check"] == "receipt.carried_key"


def test_an_entry_on_another_origin_is_refused(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """An address somewhere else is a link the answering server chose."""
    error = _refuses(
        runs_dir, answering(entry_url="https://elsewhere.example/runs/sha256:x")
    )

    assert error.details["check"] == "receipt.entry_url"


def test_an_entry_on_the_pinned_log_over_plain_http_is_refused(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """The right host over the wrong scheme is still the wrong address."""
    insecure = ENTRY_URL.replace("https://", "http://")

    error = _refuses(runs_dir, answering(entry_url=insecure))

    assert error.details["check"] == "receipt.entry_url"


def test_a_receipt_that_verifies_is_written_as_the_envelope_that_arrived(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """What is filed is the signed document, not this build's reading of it.

    A stored payload without its digest and signature could not be checked again
    by anybody, which is the whole reason the network signs one.
    """
    publisher = service(runs_dir, StubTransport())

    outcome = publisher.publish(publisher.plan(PROOF_RUN_ID))

    stored = ObjectEnvelope[PublicationReceiptPayload].model_validate_json(
        outcome.receipt_path.read_bytes()
    )
    assert stored.signature is not None
    assert stored.signature.key_id == NETWORK_KEY.key_id
    assert stored.payload_digest == digest_object(stored.payload)
    assert stored.payload.entry_url.startswith(PUBLIC_LOG_URL)


# ---------------------------------------------------------------------------
# The crash window
#
# The run log accepts a submission, the answer is lost on the way back, the CLI
# records a failure, and the person runs the command again. Decisions 0038
# requires the second attempt to converge rather than to leave a run holding two
# records of one publication.
# ---------------------------------------------------------------------------


def test_a_retry_after_a_lost_answer_converges_on_the_same_receipt(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """The exact window: receipt written, process dead before the journal said so.

    Reconstructed rather than mocked — the receipt file is left exactly where a
    crash would have left it, and the journal is truncated to the pending line
    it would have ended on.
    """
    publisher = service(runs_dir, StubTransport())
    first = publisher.publish(publisher.plan(PROOF_RUN_ID))
    written = first.receipt_path.read_bytes()
    _truncate_journal_to_pending(runs_dir / PROOF_RUN_ID)

    retried = service(runs_dir, StubTransport())
    outcome = retried.publish(retried.plan(PROOF_RUN_ID))

    assert outcome.receipt_path.read_bytes() == written
    assert outcome.status is PublicationStatus.PUBLISHED
    assert retried.status(PROOF_RUN_ID) is PublicationStatus.PUBLISHED


def test_a_second_different_receipt_for_one_run_is_refused(
    proof: RecordedProof, runs_dir: Path
) -> None:
    """Two receipts for one run cannot both be its record, so neither replaces the
    other."""
    publisher = service(runs_dir, StubTransport())
    publisher.publish(publisher.plan(PROOF_RUN_ID))
    written = (runs_dir / PROOF_RUN_ID / PUBLICATION_RECEIPT_FILENAME).read_bytes()
    _truncate_journal_to_pending(runs_dir / PROOF_RUN_ID)

    retried = service(runs_dir, answering(log_sequence=LOG_SEQUENCE + 1))
    with pytest.raises(ConflictError) as raised:
        retried.publish(retried.plan(PROOF_RUN_ID))

    assert raised.value.code == PUBLICATION_RECEIPT_CONFLICT
    assert (
        runs_dir / PROOF_RUN_ID / PUBLICATION_RECEIPT_FILENAME
    ).read_bytes() == written


def _truncate_journal_to_pending(run_dir: Path) -> None:
    """Leave the journal ending on its pending line, as a crash would have."""
    journal = run_dir / PUBLICATION_JOURNAL_FILENAME
    lines = journal.read_bytes().splitlines(keepends=True)
    journal.write_bytes(lines[0])


def _submission(runs_dir: Path) -> PublicationSubmission:
    """Return the submission this run would send, for building an answer to it."""
    return PublicationSubmission.model_validate_json(
        service(runs_dir, StubTransport()).submission_bytes(PROOF_RUN_ID)
    )


def test_a_report_written_before_publishing_existed_is_still_publishable(
    tmp_path: Path,
) -> None:
    """The defect the staged rehearsal found, and the reason it is one.

    Every report signed before publishing existed stores
    ``publication_eligible: false``, because the build that wrote it had
    nowhere to publish to. Reading that flag here refused every run that
    exists - including the certification runs this release rests on - with a
    message naming the grade and the status as the reason, when those two are
    exactly what make it eligible.

    So eligibility is decided the way the report's own rules decide it, from
    the grade and the rights statement. The offline verifier had the same bug
    from the other direction and was fixed the same way.

    The bundle here is the conformance fixture, which is a real signed proof
    from before the flag was computed. A freshly built one cannot stand in for
    it: it stores the new answer, so it would pass whatever this code did.
    """
    runs = tmp_path / "runs"
    directory = runs / CONFORMANCE_RUN_ID / BUNDLE_DIRECTORY
    directory.parent.mkdir(parents=True)
    materialize_proof(FIXTURE_PATH.read_bytes(), directory)

    stored = json.loads((directory / REPORT_FILENAME).read_text(encoding="utf-8"))
    assert stored["payload"]["publication_eligible"] is False
    assert stored["payload"]["proof_grade"] == "P1"

    plan = service(runs, StubTransport()).plan(CONFORMANCE_RUN_ID)

    assert plan.run_id == CONFORMANCE_RUN_ID
