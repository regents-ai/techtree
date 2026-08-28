"""Publishing one run to the public log. Decisions document 0038.

The order of the steps below is the product, so it is written once, here, and
the command above it does no deciding of its own.

*The proof is checked before anything is offered.* A result whose own proof does
not hold together is never put in front of somebody as a thing they could
publish. Offering it and then refusing at the end would be the same code with
the trust the wrong way round; this way the only results that reach the question
are the ones that survive it.

*What is sent is the run's own bytes.* The proof directory, file by file,
exactly as it sits on disk, because the bundle manifest already commits to every
one of those files by digest under the participant's key. Re-deriving them would
send something nobody signed. The directory holds no transcripts: an episode
receipt carries digests, task hashes and scores, and the raw episodes are
outside it.

*Nothing about the run is written back.* A completed run's files are final. This
adds two: the countersigned receipt, and a journal of its own that says what was
attempted and how it went. Neither is inside the proof, and nothing already in
the run directory is touched.

*The attempt is recorded before it is made.* The pending line goes down first, so
a process that dies mid-request leaves a run that says an attempt was started
rather than a run that says nothing happened.

*Nothing is written down that has not been checked against the pinned key.* The
receipt is verified against the network key the release pins — not against the
key the receipt itself carries — before it becomes a file. An unverified receipt
is not weaker evidence; it is no evidence, and filing one would put something in
a run directory that looks exactly like proof of publication and is not.

*A retry converges rather than conflicting.* The failure this is for is real and
narrow: the run log accepts a submission, the answer is lost on the way back, the
CLI records a failure, and the person quite reasonably runs the command again.
The log answers the second attempt with the same entry, so the receipt write
finds the same bytes already there and succeeds. Different bytes under the same
name is the case that is genuinely wrong, and that is the one it refuses.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import canonical_json_bytes
from techtree.constants import (
    PUBLICATION_JOURNAL_SCHEMA_VERSION,
    PUBLICATION_SUBMISSION_SCHEMA_VERSION,
)
from techtree.errors import (
    ConflictError,
    NotFoundError,
    PolicyError,
    TechtreeError,
    ValidationError,
    VerificationError,
)
from techtree.fs import fsync_directory, open_exclusive
from techtree.identity.models import VerificationResult
from techtree.models.base import Digest, ObjectEnvelope
from techtree.models.uplift_report import PublicationStatus, UpliftReport
from techtree.publication.journal import PublicationJournal, PublicationJournalEntry
from techtree.publication.models import (
    PublicationReceiptPayload,
    PublicationSubmission,
)
from techtree.publication.transport import PublicationTransport, resolved_endpoint
from techtree.publication.verify import (
    PUBLICATION_RECEIPT_INVALID,
    verify_publication_receipt,
)
from techtree.receipts.bundle import (
    BUNDLE_MANIFEST_FILENAME,
    PROOF_BUNDLE_INVALID,
    REPORT_FILENAME,
    LocalProofBundleManifest,
    proof_bundle_dir,
)
from techtree.receipts.uplift import publication_eligible_for
from techtree.receipts.verify import LocalProofVerifier
from techtree.release.models import PublicationCoordinates

__all__ = [
    "PUBLICATION_NOT_ELIGIBLE",
    "PUBLICATION_PROOF_NOT_FOUND",
    "PUBLICATION_RECEIPT_CONFLICT",
    "PUBLICATION_RECEIPT_FILENAME",
    "RUN_ALREADY_PUBLISHED",
    "PublicationOutcome",
    "PublicationPlan",
    "PublicationService",
]

#: The countersigned receipt, written into the run directory as a new file.
PUBLICATION_RECEIPT_FILENAME: Final = "publication-receipt.json"

#: Stable error codes this module reports.
PUBLICATION_PROOF_NOT_FOUND: Final = "publication_proof_not_found"
PUBLICATION_NOT_ELIGIBLE: Final = "publication_not_eligible"
#: Two different receipts, under one name, for one run. Not a retry: a retry
#: brings back the same entry and therefore the same bytes.
PUBLICATION_RECEIPT_CONFLICT: Final = "publication_receipt_conflict"
RUN_ALREADY_PUBLISHED: Final = "run_already_published"


@dataclass(frozen=True)
class PublicationPlan:
    """Exactly what one publication would send, worked out before it is asked.

    The plan is what a person is shown so that they can agree to something they
    have actually seen, so it carries the two numbers that answer "how much of
    my machine is about to leave it" — how many files, and how many bytes — and
    not the files themselves. The bytes on the wire are
    :meth:`PublicationService.submission_bytes`'s answer and nobody else's, so
    there is one place a submission is built and one shape it can have.
    """

    run_id: str
    bundle_digest: Digest
    endpoint: str
    #: How many files would travel, counted off the proof directory.
    file_count: int
    #: How many bytes of proof would travel, before base64 widens them on the
    #: wire. It is the size of the thing a person recognises — the proof
    #: directory — rather than the size of its encoding.
    byte_count: int
    report: UpliftReport
    verification: VerificationResult


@dataclass(frozen=True)
class PublicationOutcome:
    """What one completed publication produced."""

    run_id: str
    receipt: PublicationReceiptPayload
    receipt_path: Path
    status: PublicationStatus
    #: Whether an address was sent with this submission. The address itself is
    #: not here, and is not anywhere else on this machine either.
    contributor_address_sent: bool


class PublicationService:
    """Plans and performs the publication of one finished run."""

    def __init__(
        self,
        *,
        runs_dir: Path,
        coordinates: PublicationCoordinates,
        endpoint_override: str | None,
        transport: PublicationTransport,
        clock: Callable[[], datetime],
    ) -> None:
        self._runs_dir = runs_dir
        self._coordinates = coordinates
        self._endpoint_override = endpoint_override
        self._transport = transport
        self._clock = clock

    # -- planning -----------------------------------------------------------

    def plan(self, run_id: str) -> PublicationPlan:
        """Return what publishing this run would send, or refuse to publish it.

        Every refusal that can be reached without a network is reached here, so
        a person is only ever asked about a submission that could actually be
        made.
        """
        directory = self._bundle_dir(run_id)
        verification = LocalProofVerifier().verify_bundle(directory)
        if not verification.verified:
            raise VerificationError(
                f"run {run_id}'s own proof does not verify, so there is nothing "
                "here that could honestly be published: "
                f"{verification.failures[0].detail}",
                code=PROOF_BUNDLE_INVALID,
                details={
                    "run_id": run_id,
                    "failed_checks": [message.id for message in verification.failures],
                },
            )

        report = self._report(directory, run_id)
        # Decided from the report's own grade and rights, never from the flag
        # stored beside them. That flag records what the build that WROTE the
        # report allowed, which is a fact about that build: every report signed
        # before publishing existed stores ``false``, so reading it here refused
        # every run that exists, including the certification runs. The offline
        # verifier had the same bug from the other direction and was fixed the
        # same way.
        if not publication_eligible_for(
            grade=report.proof_grade, publication=report.statuses.publication
        ):
            raise PolicyError(
                f"run {run_id}'s report may not be published: "
                + (
                    "its rights statement blocks publication"
                    if report.statuses.publication is PublicationStatus.BLOCKED
                    else f"it is graded {report.proof_grade}, and only a P1 "
                    "report is evidence of anything"
                ),
                code=PUBLICATION_NOT_ELIGIBLE,
                details={
                    "run_id": run_id,
                    "proof_grade": report.proof_grade,
                    "publication": report.statuses.publication.value,
                },
            )

        journal = PublicationJournal(self._run_dir(run_id))
        published = journal.published()
        if published is not None:
            raise ConflictError(
                f"run {run_id} is already in the public log, at "
                f"{published.entry_url}. A published entry stays where it is",
                code=RUN_ALREADY_PUBLISHED,
                details={"run_id": run_id, "entry_url": published.entry_url},
            )

        stored = self._proof_files(directory)
        return PublicationPlan(
            run_id=run_id,
            bundle_digest=self._bundle_digest(directory, run_id),
            endpoint=self.endpoint,
            file_count=len(stored),
            byte_count=sum(len(data) for data in stored.values()),
            report=report,
            verification=verification,
        )

    # -- publishing ---------------------------------------------------------

    def publish(
        self, plan: PublicationPlan, *, contributor_address: str | None = None
    ) -> PublicationOutcome:
        """Send the planned submission, record what happened, and return it.

        ``contributor_address`` is already canonical by the time it arrives:
        checking it is :mod:`techtree.publication.address`'s job. This method's
        job is to make sure it travels beside the request and nowhere else at
        all — not into the submission, not into the journal, not into a log
        line. The run log stores what it is sent and serves those exact bytes
        back at a public address, so an address inside the body would be public
        by construction; the receiving side reads it from a header for that
        reason and refuses a body carrying anything but the proof.
        """
        journal = PublicationJournal(self._run_dir(plan.run_id))
        self._record(journal, plan, status=PublicationStatus.PENDING)

        try:
            envelope = self._submit(plan, contributor_address)
            path = self._write_receipt(plan.run_id, envelope)
        except TechtreeError as error:
            self._record(
                journal, plan, status=PublicationStatus.FAILED, error_code=error.code
            )
            raise

        receipt = envelope.payload
        self._record(
            journal,
            plan,
            status=PublicationStatus.PUBLISHED,
            entry_url=receipt.entry_url,
            log_sequence=receipt.log_sequence,
        )
        return PublicationOutcome(
            run_id=plan.run_id,
            receipt=receipt,
            receipt_path=path,
            status=PublicationStatus.PUBLISHED,
            contributor_address_sent=contributor_address is not None,
        )

    def status(self, run_id: str) -> PublicationStatus:
        """Return where this run stands, read from its journal."""
        return PublicationJournal(self._run_dir(run_id)).status()

    def publication_eligible(self, run_id: str) -> bool:
        """Return whether this run's own report says it may be published.

        Asked by the surfaces that decide whether to *offer* publishing, so a
        run with no proof on this machine is simply not eligible rather than an
        error: nothing is being published here, and a missing bundle is a
        complete answer to the question that was asked.
        """
        try:
            directory = self._bundle_dir(run_id)
        except NotFoundError:
            return False
        return self._report(directory, run_id).publication_eligible

    # -- the request --------------------------------------------------------

    def submission_bytes(self, run_id: str) -> bytes:
        """Return the exact bytes a submission for this run puts on the wire.

        This is the whole of the wire shape and the only place it is built, so
        the request the transport sends and the conformance fixture the
        receiving side is tested against cannot be two different documents that
        happen to look alike. Decisions 0038 fixes the four members; the model
        refuses a fifth, and the canonical encoding fixes the byte order, so
        the same proof directory produces the same bytes on any machine.

        It describes rather than sends. Whether this run *may* be published is
        :meth:`plan`'s question, asked of the run's own verified proof and its
        rights statement before anybody is offered anything, and :meth:`publish`
        is the only method here that opens a socket.
        """
        directory = self._bundle_dir(run_id)
        submission = PublicationSubmission(
            schema_version=PUBLICATION_SUBMISSION_SCHEMA_VERSION,
            run_id=run_id,
            bundle_digest=self._bundle_digest(directory, run_id),
            files=self._files(directory),
        )
        return canonical_json_bytes(submission)

    def _submit(
        self, plan: PublicationPlan, contributor_address: str | None
    ) -> ObjectEnvelope[PublicationReceiptPayload]:
        """Send one submission and return the receipt it came back with."""
        response = self._transport.submit(
            endpoint=plan.endpoint,
            body=self.submission_bytes(plan.run_id),
            contributor_address=contributor_address,
        )
        return self._receipt(response, plan)

    def _receipt(
        self, response: bytes, plan: PublicationPlan
    ) -> ObjectEnvelope[PublicationReceiptPayload]:
        """Parse the answer and refuse everything that is not this run's receipt.

        Parsing is here; the checks are in :mod:`techtree.publication.verify`,
        because they are about the network's word rather than about this run
        directory, and the withdrawal path needs the same ones.
        """
        try:
            envelope = ObjectEnvelope[PublicationReceiptPayload].model_validate_json(
                response
            )
        except PydanticValidationError as error:
            raise ValidationError(
                "the run log answered with something that is not a publication "
                "receipt, so nothing was recorded",
                code=PUBLICATION_RECEIPT_INVALID,
                details={"run_id": plan.run_id},
            ) from error

        verify_publication_receipt(
            envelope,
            coordinates=self._coordinates,
            run_id=plan.run_id,
            bundle_digest=plan.bundle_digest,
        )
        return envelope

    def _write_receipt(
        self, run_id: str, receipt: ObjectEnvelope[PublicationReceiptPayload]
    ) -> Path:
        """Write the receipt into the run directory, converging on a retry.

        Created with ``O_EXCL``, so nothing that is already there is opened for
        writing. What is found there decides the answer: the same bytes mean the
        run log answered the same way twice, which is what a retry after a lost
        response looks like and is a success; different bytes under the same name
        are two different records of one publication, and there is no version of
        that which is safe to resolve by choosing one.
        """
        path = self._run_dir(run_id) / PUBLICATION_RECEIPT_FILENAME
        data = canonical_json_bytes(receipt)
        try:
            with open_exclusive(path) as handle:
                handle.write(data)
                handle.flush()
        except ConflictError as error:
            if path.read_bytes() == data:
                return path
            raise ConflictError(
                f"run {run_id} already holds a different publication receipt, so "
                "this one was not written: two receipts for one run cannot both "
                "be its record",
                code=PUBLICATION_RECEIPT_CONFLICT,
                details={"run_id": run_id, "path": str(path)},
            ) from error
        fsync_directory(path.parent)
        return path

    # -- recording ----------------------------------------------------------

    def _record(
        self,
        journal: PublicationJournal,
        plan: PublicationPlan,
        *,
        status: PublicationStatus,
        entry_url: str | None = None,
        log_sequence: int | None = None,
        error_code: str | None = None,
    ) -> None:
        """Append one line to the run's publication journal."""
        journal.append(
            PublicationJournalEntry(
                schema_version=PUBLICATION_JOURNAL_SCHEMA_VERSION,
                sequence=journal.next_sequence(),
                at=self._clock(),
                run_id=plan.run_id,
                status=status,
                bundle_digest=plan.bundle_digest,
                endpoint=plan.endpoint,
                file_count=plan.file_count,
                byte_count=plan.byte_count,
                entry_url=entry_url,
                log_sequence=log_sequence,
                error_code=error_code,
            )
        )

    # -- reading the run ----------------------------------------------------

    def _run_dir(self, run_id: str) -> Path:
        return self._runs_dir / run_id

    def _bundle_dir(self, run_id: str) -> Path:
        directory = proof_bundle_dir(self._run_dir(run_id))
        if not (directory / BUNDLE_MANIFEST_FILENAME).is_file():
            raise NotFoundError(
                f"run {run_id} has no proof to publish on this machine",
                code=PUBLICATION_PROOF_NOT_FOUND,
                details={"run_id": run_id},
            )
        return directory

    def _bundle_digest(self, directory: Path, run_id: str) -> Digest:
        """Return the digest of the signed manifest that commits to the bundle.

        One value identifies the whole submission, and it is the one the
        verification that just passed checked every file against.
        """
        raw = (directory / BUNDLE_MANIFEST_FILENAME).read_bytes()
        try:
            envelope = ObjectEnvelope[LocalProofBundleManifest].model_validate_json(raw)
        except PydanticValidationError as error:
            raise VerificationError(
                f"run {run_id}'s proof manifest cannot be read",
                code=PROOF_BUNDLE_INVALID,
                details={"run_id": run_id},
            ) from error
        return envelope.payload_digest

    def _report(self, directory: Path, run_id: str) -> UpliftReport:
        """Return the report this bundle carries."""
        raw = (directory / REPORT_FILENAME).read_bytes()
        try:
            envelope = ObjectEnvelope[UpliftReport].model_validate_json(raw)
        except PydanticValidationError as error:
            raise VerificationError(
                f"run {run_id}'s report cannot be read out of its own proof",
                code=PROOF_BUNDLE_INVALID,
                details={"run_id": run_id},
            ) from error
        return envelope.payload

    def _proof_files(self, directory: Path) -> dict[str, bytes]:
        """Return every file in the proof directory against its stored bytes.

        The whole directory rather than the manifest's list: the manifest does
        not commit to itself, and a submission without the signed manifest is a
        submission nothing can be checked against.
        """
        return {
            path.relative_to(directory).as_posix(): path.read_bytes()
            for path in sorted(directory.rglob("*"))
            if path.is_file()
        }

    def _files(self, directory: Path) -> dict[str, str]:
        """Return the proof directory in the shape the wire carries it.

        Path against base64 of the stored bytes, and nothing else. No digest
        and no size travel beside a file, because both would be the submitter's
        own arithmetic over the submitter's own bytes: they prove nothing, and
        a receiving side that read them instead of the bundle's signed manifest
        would be trusting the one party the manifest exists to avoid trusting.
        Decisions 0038 fixes this, and the reason is worth more than the eight
        bytes it saves.
        """
        return {
            path: base64.b64encode(data).decode("ascii")
            for path, data in self._proof_files(directory).items()
        }

    @property
    def endpoint(self) -> str:
        """Return the address this service publishes to, override first.

        Whichever wins is what the plan carries and what the review prints, so
        somebody agreeing to a publication is agreeing to the address it is
        actually going to.
        """
        return resolved_endpoint(self._coordinates, self._endpoint_override)
