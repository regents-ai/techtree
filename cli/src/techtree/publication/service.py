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
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import canonical_json_bytes, sha256_digest_bytes
from techtree.constants import (
    PUBLICATION_JOURNAL_SCHEMA_VERSION,
    PUBLICATION_SUBMISSION_SCHEMA_VERSION,
)
from techtree.errors import (
    ConflictError,
    NotFoundError,
    PolicyError,
    PrerequisiteError,
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
    PublicationReceipt,
    PublicationSubmission,
    SubmittedFile,
)
from techtree.publication.transport import PublicationTransport, validated_endpoint
from techtree.receipts.bundle import (
    BUNDLE_MANIFEST_FILENAME,
    PROOF_BUNDLE_INVALID,
    REPORT_FILENAME,
    LocalProofBundleManifest,
    proof_bundle_dir,
)
from techtree.receipts.verify import LocalProofVerifier

__all__ = [
    "PUBLICATION_ENDPOINT_NOT_CONFIGURED",
    "PUBLICATION_NOT_ELIGIBLE",
    "PUBLICATION_PROOF_NOT_FOUND",
    "PUBLICATION_RECEIPT_FILENAME",
    "PUBLICATION_RECEIPT_INVALID",
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
PUBLICATION_ENDPOINT_NOT_CONFIGURED: Final = "publication_endpoint_not_configured"
PUBLICATION_RECEIPT_INVALID: Final = "publication_receipt_invalid"
RUN_ALREADY_PUBLISHED: Final = "run_already_published"


@dataclass(frozen=True)
class PublicationPlan:
    """Exactly what one publication would send, worked out before it is asked."""

    run_id: str
    bundle_digest: Digest
    endpoint: str
    files: list[SubmittedFile]
    report: UpliftReport
    verification: VerificationResult

    @property
    def file_count(self) -> int:
        """Return how many files would travel."""
        return len(self.files)

    @property
    def byte_count(self) -> int:
        """Return how many bytes of proof would travel."""
        return sum(entry.size for entry in self.files)

    @property
    def paths(self) -> list[str]:
        """Return where each file sits in the proof, in reading order."""
        return [entry.path for entry in self.files]


@dataclass(frozen=True)
class PublicationOutcome:
    """What one completed publication produced."""

    run_id: str
    receipt: PublicationReceipt
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
        endpoint: str | None,
        transport: PublicationTransport,
        clock: Callable[[], datetime],
    ) -> None:
        self._runs_dir = runs_dir
        self._endpoint = endpoint
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
        if not report.publication_eligible:
            raise PolicyError(
                f"run {run_id}'s report is not eligible to be published: it is "
                f"graded {report.proof_grade} and its publication status is "
                f"{report.statuses.publication.value}",
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

        return PublicationPlan(
            run_id=run_id,
            bundle_digest=self._bundle_digest(directory, run_id),
            endpoint=self._configured_endpoint(run_id),
            files=self._files(directory),
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
            receipt = self._submit(plan, contributor_address)
            path = self._write_receipt(plan.run_id, receipt)
        except TechtreeError as error:
            self._record(
                journal, plan, status=PublicationStatus.FAILED, error_code=error.code
            )
            raise

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

    def _submit(
        self, plan: PublicationPlan, contributor_address: str | None
    ) -> PublicationReceipt:
        """Send one submission and return the receipt it came back with."""
        submission = PublicationSubmission(
            schema_version=PUBLICATION_SUBMISSION_SCHEMA_VERSION,
            run_id=plan.run_id,
            bundle_digest=plan.bundle_digest,
            files=plan.files,
        )
        response = self._transport.submit(
            endpoint=validated_endpoint(plan.endpoint),
            body=canonical_json_bytes(submission),
            contributor_address=contributor_address,
        )
        return self._receipt(response, plan)

    def _receipt(self, response: bytes, plan: PublicationPlan) -> PublicationReceipt:
        """Parse the response, and refuse a receipt for something else.

        A receipt that names another run or another bundle is not this run's
        evidence of anything, whatever else it is, and writing it into this run
        directory would put a false record beside a true one.
        """
        try:
            receipt = PublicationReceipt.model_validate_json(response)
        except PydanticValidationError as error:
            raise ValidationError(
                "the run log answered with something that is not a publication "
                "receipt, so nothing was recorded",
                code=PUBLICATION_RECEIPT_INVALID,
                details={"run_id": plan.run_id},
            ) from error

        if receipt.run_id != plan.run_id or receipt.bundle_digest != plan.bundle_digest:
            raise ValidationError(
                "the run log's receipt is for a different submission than the "
                "one that was sent",
                code=PUBLICATION_RECEIPT_INVALID,
                details={
                    "run_id": plan.run_id,
                    "receipt_run_id": receipt.run_id,
                    "receipt_bundle_digest": receipt.bundle_digest,
                },
            )
        if receipt.failed_checks:
            raise ValidationError(
                f"the run log accepted nothing: {receipt.failed_checks[0].detail}",
                code=PUBLICATION_RECEIPT_INVALID,
                details={
                    "run_id": plan.run_id,
                    "failed_checks": [check.id for check in receipt.failed_checks],
                },
            )
        return receipt

    def _write_receipt(self, run_id: str, receipt: PublicationReceipt) -> Path:
        """Write the receipt into the run directory as a new file.

        Created with ``O_EXCL``, so a second publication of the same run reports
        a conflict rather than replacing a record. Nothing that was already in
        the run directory is opened for writing at all.
        """
        path = self._run_dir(run_id) / PUBLICATION_RECEIPT_FILENAME
        data = canonical_json_bytes(receipt)
        with open_exclusive(path) as handle:
            handle.write(data)
            handle.flush()
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

    def _files(self, directory: Path) -> list[SubmittedFile]:
        """Return every file in the proof directory, in path order.

        The whole directory rather than the manifest's list: the manifest does
        not commit to itself, and a submission without the signed manifest is a
        submission nothing can be checked against.
        """
        entries: list[SubmittedFile] = []
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            data = path.read_bytes()
            entries.append(
                SubmittedFile(
                    path=path.relative_to(directory).as_posix(),
                    digest=sha256_digest_bytes(data),
                    size=len(data),
                    content=base64.b64encode(data).decode("ascii"),
                )
            )
        return entries

    def _configured_endpoint(self, run_id: str) -> str:
        """Return where to publish, or refuse to guess.

        There is no default address and there will not be one. A build that has
        not been told where the public log is cannot invent somewhere to send a
        proof bundle, and quietly doing nothing would be worse than saying so.
        """
        if self._endpoint is None:
            raise PrerequisiteError(
                "this build has not been told where the public run log is, so "
                "there is nowhere to publish to. Set publication_endpoint in "
                "the Techtree settings file, or TECHTREE_PUBLICATION_ENDPOINT "
                "in the environment",
                code=PUBLICATION_ENDPOINT_NOT_CONFIGURED,
                details={"run_id": run_id},
            )
        return self._endpoint
