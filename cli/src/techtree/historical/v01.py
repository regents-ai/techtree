"""Reading v0.1 evidence in v0.2, without rewriting a byte of it.

Plan ``docs/plan/v0.2.md``, "v0.1 compatibility": historical artifacts are read
through versioned read-only projectors, their source bytes and digests are
never rewritten, and old shapes never return to a live write path.

A v0.1 proof is a directory of canonical JSON committed to by a signed
manifest, and the whole of what makes it worth keeping is that those exact
bytes still hash to the digests somebody signed. So this module opens files and
does arithmetic over what it finds, and that is all it does. It writes nothing,
signs nothing, and moves nothing: a projector that had to place a file
somewhere in order to read one would be a writer that also reads, and the
promise the plan makes about frozen evidence would then rest on that writer
being careful rather than on it not existing.

What comes back is a read model in three parts, kept apart because they answer
different questions and can disagree:

*Byte identity.* :class:`ProjectedArtifact` puts the digest and the size the
signed manifest recorded beside the digest and the size these stored bytes
actually have. Nothing here believes a recorded value; every observed one is
taken again from the file.

*The normalized outcome.* :attr:`ProjectedProof.verification` is
:func:`techtree.receipts.verify.verify_local_bundle` — the same offline
verification a v0.1 reader ran, over the same bytes, reported in the same
:class:`~techtree.identity.models.VerificationResult`. This module does not
re-implement it, soften it, or put a second opinion beside it.

*The claim semantics.* :class:`ProjectedClaims` is what the signed report is
allowed to say about itself: its grade, the words that grade means, the five
statuses, whether it is eligible to be published, and the measured result. Each
one is copied out of the report's own bytes rather than re-derived, because a
projector that recomputed a verdict would be issuing one.

Where this projection stops
---------------------------

The v0.2 read models named in the plan — the four-plane execution plan
(WP1.1), comparison validity, evidence availability and reproduction lists
(WP1.3), and the ``techtree.cli.v2`` envelope (WP1.6) — are being built beside
this one and are not in the tree yet. Nothing here invents a shape for them.
The projection stops at the v0.1 objects, the verification result, and the
report's own claims, which are the v0.2 read shapes that exist today; when the
newer read models land they are built from a projection, rather than from a
second reading of the bundle.

A publication submission is projected in memory and carries no verification.
Offline bundle verification reads a proof *directory*, and this module will not
create one: :func:`project_publication_submission` establishes byte identity
and claim semantics from the bytes the submission itself carries, and a caller
who wants the verification too points :func:`project_proof_directory` at the
directory those bytes came from.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import digest_object, sha256_digest_bytes
from techtree.errors import VerificationError
from techtree.identity.models import VerificationResult
from techtree.models.base import ArtifactRef, ObjectEnvelope
from techtree.models.episode_receipt import EpisodeReceipt
from techtree.models.experiment import ExperimentVariant
from techtree.models.uplift_report import UpliftReport
from techtree.publication.models import PublicationSubmission
from techtree.receipts.bundle import (
    BUNDLE_MANIFEST_FILENAME,
    PROOF_BUNDLE_INVALID,
    REPORT_FILENAME,
    LocalProofBundleManifest,
    receipt_set_filename,
)
from techtree.receipts.set import ReceiptSetManifest
from techtree.receipts.verify import P1_MEANING, verify_local_bundle

__all__ = [
    "V01_PROJECTOR",
    "ProjectedArtifact",
    "ProjectedClaims",
    "ProjectedProof",
    "ProjectedReceipt",
    "ProjectedReport",
    "ProjectedResult",
    "ProjectedSeal",
    "ProjectedSubmission",
    "project_proof_directory",
    "project_publication_submission",
    "project_signed_receipt",
    "project_signed_report",
]

#: Which projector produced a projection, versioned by the release whose
#: evidence it reads, so a reader holding one can say what it was read as.
V01_PROJECTOR: Final = "techtree.historical-projector.v0_1"

#: Both sides, in comparison order, so two projections of the same proof list
#: their receipt sets identically.
_VARIANT_ORDER: Final[tuple[ExperimentVariant, ...]] = (
    ExperimentVariant.BASELINE,
    ExperimentVariant.CANDIDATE,
)

#: The grade whose meaning decisions document 0005 fixes in words.
_ATTESTED_GRADE: Final = "P1"


# ---------------------------------------------------------------------------
# The read model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectedArtifact:
    """One file a signed manifest committed to, against what is stored now.

    ``observed_digest`` and ``observed_size`` are ``None`` when the manifest
    names a file that is not there. A missing artifact is reported as missing
    rather than as a mismatch, because they are different failures: one bundle
    lost a file, the other had a file changed under it.
    """

    relative_path: str
    recorded_digest: str
    recorded_size: int
    observed_digest: str | None
    observed_size: int | None

    @property
    def present(self) -> bool:
        """Whether the bytes this artifact names could be read at all."""
        return self.observed_digest is not None

    @property
    def byte_identical(self) -> bool:
        """Whether the stored bytes are exactly the bytes that were signed."""
        return (
            self.observed_digest == self.recorded_digest
            and self.observed_size == self.recorded_size
        )


@dataclass(frozen=True)
class ProjectedSeal:
    """One signed document's recorded digest, against its payload's own.

    An envelope carries the digest it was signed under. Recomputing it from the
    payload is the cheapest check that can tell a reader the two no longer
    describe each other, and it is deliberately kept apart from the signature
    check: a payload that was edited and re-digested has an intact seal here
    and a broken signature in the verification.
    """

    recorded_payload_digest: str
    observed_payload_digest: str
    signing_key_id: str | None
    stored_bytes: int

    @property
    def digest_intact(self) -> bool:
        """Whether the payload still matches the digest it was signed under."""
        return self.recorded_payload_digest == self.observed_payload_digest

    @property
    def signed(self) -> bool:
        """Whether this document travels with a signature at all."""
        return self.signing_key_id is not None


@dataclass(frozen=True)
class ProjectedResult:
    """The measurement a v0.1 report recorded, copied and not recomputed."""

    reward_name: str
    baseline_mean: float
    candidate_mean: float
    absolute_delta: float
    relative_delta: float | None
    wins: int
    losses: int
    ties: int
    task_count: int


@dataclass(frozen=True)
class ProjectedClaims:
    """Everything a v0.1 report is allowed to say about itself.

    ``grade_meaning`` is the one sentence decisions document 0005 permits for a
    P1 grade, and it is ``None`` for any other grade rather than a softer
    sentence: a projector that supplied words for a grade the decisions do not
    define would be defining one.
    """

    run_id: str
    proof_grade: str
    grade_meaning: str | None
    decision: str
    execution_status: str
    score_status: str
    evidence_status: str
    comparison_status: str
    publication_status: str
    publication_eligible: bool
    result: ProjectedResult


@dataclass(frozen=True)
class ProjectedReport:
    """One frozen signed UpliftReport, read back from its stored bytes."""

    projector: str
    seal: ProjectedSeal
    claims: ProjectedClaims


@dataclass(frozen=True)
class ProjectedReceipt:
    """One frozen signed EpisodeReceipt, read back from its stored bytes."""

    projector: str
    seal: ProjectedSeal
    run_id: str
    variant: str
    task_hash: str
    score_status: str
    evidence_status: str
    execution_backend: str


@dataclass(frozen=True)
class ProjectedProof:
    """One frozen v0.1 proof bundle, as a v0.2 reader sees it."""

    projector: str
    run_id: str
    #: The digest the manifest was signed under. A bundle does not commit to
    #: its own manifest — a file cannot carry the digest of a document that
    #: carries its digest — so this is the value a publication addresses the
    #: whole bundle by.
    bundle_digest: str
    campaign_spec_digest: str
    data_policy_digest: str
    root_report_digest: str
    executor_key_id: str
    manifest_seal: ProjectedSeal
    report_seal: ProjectedSeal
    artifacts: tuple[ProjectedArtifact, ...]
    #: Each variant against how many receipts its signed set commits to.
    receipt_counts: tuple[tuple[str, int], ...]
    claims: ProjectedClaims
    verification: VerificationResult

    @property
    def bytes_intact(self) -> bool:
        """Whether every committed file is still byte-for-byte what was signed."""
        return bool(self.artifacts) and all(
            artifact.byte_identical for artifact in self.artifacts
        )

    @property
    def verified(self) -> bool:
        """Whether the offline verification of these bytes still passes."""
        return self.verification.verified

    def artifact(self, relative_path: str) -> ProjectedArtifact | None:
        """Return one projected artifact, or ``None`` when it is not committed."""
        for artifact in self.artifacts:
            if artifact.relative_path == relative_path:
                return artifact
        return None


@dataclass(frozen=True)
class ProjectedSubmission:
    """One frozen v0.1 publication submission, read without unpacking it.

    ``carried_paths`` is every file the submission travels with and
    ``artifacts`` is every file the manifest inside it commits to. They differ
    by exactly the manifest, which is why both are here: a submission carrying
    a file nobody signed shows up as the difference between the two, and a
    projection that reported only the signed list could not show it.
    """

    projector: str
    run_id: str
    #: The digest the submission addresses the bundle by, as the wire document
    #: states it.
    recorded_bundle_digest: str
    #: The digest of the manifest the submission actually carries, taken again
    #: from that manifest's own payload. It is recomputed rather than read out
    #: of the envelope beside it, because a submission that stated its bundle
    #: digest and carried an envelope stating the same value would prove only
    #: that one document agrees with itself.
    observed_bundle_digest: str
    carried_paths: tuple[str, ...]
    artifacts: tuple[ProjectedArtifact, ...]
    manifest_seal: ProjectedSeal
    report_seal: ProjectedSeal
    claims: ProjectedClaims

    @property
    def addresses_the_bundle_it_carries(self) -> bool:
        """Whether the manifest this carries is the bundle it is addressed as.

        The stated digest against the recomputed one, so a manifest payload
        edited in transit fails here even when every artifact it names is
        untouched and every digest it records was left alone.
        """
        return self.recorded_bundle_digest == self.observed_bundle_digest

    @property
    def seals_intact(self) -> bool:
        """Whether both signed documents still match their recorded digests."""
        return self.manifest_seal.digest_intact and self.report_seal.digest_intact

    @property
    def bytes_intact(self) -> bool:
        """Whether every committed file is still byte-for-byte what was signed."""
        return bool(self.artifacts) and all(
            artifact.byte_identical for artifact in self.artifacts
        )

    @property
    def unsigned_paths(self) -> tuple[str, ...]:
        """Return every carried file the signed manifest does not commit to."""
        committed = {artifact.relative_path for artifact in self.artifacts}
        committed.add(BUNDLE_MANIFEST_FILENAME)
        return tuple(path for path in self.carried_paths if path not in committed)


# ---------------------------------------------------------------------------
# The projectors
# ---------------------------------------------------------------------------


def project_proof_directory(directory: Path) -> ProjectedProof:
    """Project one stored v0.1 proof directory into the v0.2 read model.

    The directory is opened and nothing else is done to it. The verification
    carried in the result is the existing offline verification of the same
    bytes, run here so that a caller holding a projection holds the outcome
    too and never a second implementation of it.
    """
    manifest_bytes = _stored(directory / BUNDLE_MANIFEST_FILENAME)
    report_bytes = _stored(directory / REPORT_FILENAME)
    sealed_manifest = _envelope(manifest_bytes, LocalProofBundleManifest)
    sealed_report = _envelope(report_bytes, UpliftReport)
    manifest = sealed_manifest.payload

    return ProjectedProof(
        projector=V01_PROJECTOR,
        run_id=manifest.run_id,
        bundle_digest=sealed_manifest.payload_digest,
        campaign_spec_digest=manifest.campaign_spec_digest,
        data_policy_digest=manifest.data_policy_digest,
        root_report_digest=manifest.root_report_digest,
        executor_key_id=manifest.executor_identity.key_id,
        manifest_seal=_seal(sealed_manifest, manifest_bytes),
        report_seal=_seal(sealed_report, report_bytes),
        artifacts=tuple(
            _artifact(reference, _optional(directory / _placed(reference)))
            for reference in manifest.artifacts
        ),
        receipt_counts=tuple(
            (
                variant.value,
                _parse(
                    ReceiptSetManifest,
                    _stored(directory / receipt_set_filename(variant)),
                    "receipt set",
                ).receipt_count,
            )
            for variant in _VARIANT_ORDER
        ),
        claims=_claims(sealed_report.payload),
        verification=verify_local_bundle(directory),
    )


def project_publication_submission(raw: bytes) -> ProjectedSubmission:
    """Project one stored v0.1 publication submission from its own bytes.

    The submission carries a whole proof directory base64-encoded, so every
    digest checked here is taken from bytes that travelled inside the document
    being read — the manifest's own digest included, recomputed from its
    payload rather than read out of the envelope carrying it. Nothing is
    unpacked to disk and nothing is re-encoded: the ``raw`` handed in is still
    the only copy when this returns.
    """
    submission = _parse(PublicationSubmission, raw, "publication submission")
    carried = {path: _decoded(path, value) for path, value in submission.files.items()}
    manifest_bytes = _carried(carried, BUNDLE_MANIFEST_FILENAME, submission.run_id)
    report_bytes = _carried(carried, REPORT_FILENAME, submission.run_id)
    sealed_manifest = _envelope(manifest_bytes, LocalProofBundleManifest)
    sealed_report = _envelope(report_bytes, UpliftReport)
    manifest_seal = _seal(sealed_manifest, manifest_bytes)

    return ProjectedSubmission(
        projector=V01_PROJECTOR,
        run_id=submission.run_id,
        recorded_bundle_digest=submission.bundle_digest,
        observed_bundle_digest=manifest_seal.observed_payload_digest,
        carried_paths=tuple(sorted(carried)),
        artifacts=tuple(
            _artifact(reference, carried.get(_placed(reference)))
            for reference in sealed_manifest.payload.artifacts
        ),
        manifest_seal=manifest_seal,
        report_seal=_seal(sealed_report, report_bytes),
        claims=_claims(sealed_report.payload),
    )


def project_signed_report(raw: bytes) -> ProjectedReport:
    """Project one stored v0.1 signed UpliftReport envelope."""
    sealed = _envelope(raw, UpliftReport)
    return ProjectedReport(
        projector=V01_PROJECTOR,
        seal=_seal(sealed, raw),
        claims=_claims(sealed.payload),
    )


def project_signed_receipt(raw: bytes) -> ProjectedReceipt:
    """Project one stored v0.1 signed EpisodeReceipt envelope."""
    sealed = _envelope(raw, EpisodeReceipt)
    receipt = sealed.payload
    return ProjectedReceipt(
        projector=V01_PROJECTOR,
        seal=_seal(sealed, raw),
        run_id=receipt.run_id,
        variant=receipt.variant.value,
        task_hash=receipt.task_hash,
        score_status=receipt.score_status.value,
        evidence_status=receipt.evidence_status.value,
        execution_backend=receipt.execution_backend,
    )


# ---------------------------------------------------------------------------
# The pieces
# ---------------------------------------------------------------------------


def _claims(report: UpliftReport) -> ProjectedClaims:
    """Copy out what a report claims, in the report's own vocabulary."""
    primary = report.primary_result
    return ProjectedClaims(
        run_id=report.run_id,
        proof_grade=report.proof_grade,
        grade_meaning=(P1_MEANING if report.proof_grade == _ATTESTED_GRADE else None),
        decision=report.decision.value,
        execution_status=report.statuses.execution.value,
        score_status=report.statuses.score.value,
        evidence_status=report.statuses.evidence.value,
        comparison_status=report.statuses.comparison.value,
        publication_status=report.statuses.publication.value,
        publication_eligible=report.publication_eligible,
        result=ProjectedResult(
            reward_name=primary.reward_name,
            baseline_mean=primary.baseline_mean,
            candidate_mean=primary.candidate_mean,
            absolute_delta=primary.absolute_delta,
            relative_delta=primary.relative_delta,
            wins=primary.wins,
            losses=primary.losses,
            ties=primary.ties,
            task_count=len(report.task_deltas),
        ),
    )


def _artifact(reference: ArtifactRef, stored: bytes | None) -> ProjectedArtifact:
    """Put one recorded commitment beside the bytes it describes."""
    return ProjectedArtifact(
        relative_path=_placed(reference),
        recorded_digest=reference.digest,
        recorded_size=reference.size,
        observed_digest=None if stored is None else sha256_digest_bytes(stored),
        observed_size=None if stored is None else len(stored),
    )


def _placed(reference: ArtifactRef) -> str:
    """Return where one committed artifact sits inside its bundle.

    A bundle manifest's own validator refuses a reference with nowhere to look,
    so this narrows a type rather than deciding anything.
    """
    if reference.relative_path is None:
        raise VerificationError(
            "a v0.1 proof places every artifact it commits to; this manifest "
            "carries a digest with nowhere to look",
            code=PROOF_BUNDLE_INVALID,
            details={"digest": reference.digest},
        )
    return reference.relative_path


def _seal[T: BaseModel](envelope: ObjectEnvelope[T], stored: bytes) -> ProjectedSeal:
    """Return one envelope's recorded digest beside the recomputed one."""
    return ProjectedSeal(
        recorded_payload_digest=envelope.payload_digest,
        observed_payload_digest=digest_object(envelope.payload),
        signing_key_id=(
            None if envelope.signature is None else envelope.signature.key_id
        ),
        stored_bytes=len(stored),
    )


def _stored(path: Path) -> bytes:
    """Return one stored file's bytes, or say which file cannot be read."""
    data = _optional(path)
    if data is None:
        raise VerificationError(
            f"a v0.1 proof carries {path.name}; this one does not",
            code=PROOF_BUNDLE_INVALID,
            details={"file": path.name},
        )
    return data


def _optional(path: Path) -> bytes | None:
    """Return one stored file's bytes, or ``None`` when it is not there."""
    try:
        return path.read_bytes()
    except OSError:
        return None


def _carried(files: dict[str, bytes], name: str, run_id: str) -> bytes:
    """Return one file a submission must travel with, or say it is missing."""
    data = files.get(name)
    if data is None:
        raise VerificationError(
            f"a v0.1 publication submission carries {name}; this one does not",
            code=PROOF_BUNDLE_INVALID,
            details={"run_id": run_id, "file": name},
        )
    return data


def _decoded(path: str, value: str) -> bytes:
    """Return one carried file's bytes, or say which member cannot be decoded."""
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise VerificationError(
            f"a v0.1 publication submission carries {path} as base64; "
            "these bytes are not",
            code=PROOF_BUNDLE_INVALID,
            details={"file": path},
        ) from error


def _envelope[T: BaseModel](raw: bytes, model: type[T]) -> ObjectEnvelope[T]:
    """Parse one stored signed document into the envelope it travels in."""
    return _parse(_envelope_model(model), raw, f"signed {model.__name__}")


def _envelope_model[T: BaseModel](model: type[T]) -> type[ObjectEnvelope[T]]:
    """Return the envelope type one payload model travels in."""
    return ObjectEnvelope[model]  # type: ignore[valid-type]


def _parse[T: BaseModel](model: type[T], raw: bytes, subject: str) -> T:
    """Validate stored bytes, or report which document could not be read.

    From bytes and in JSON mode, which is how every stored document in this
    codebase is loaded: a projector that read a historical document more
    leniently than the code that wrote it would be reading a shape nobody
    signed.
    """
    try:
        return model.model_validate_json(raw)
    except PydanticValidationError as error:
        raise VerificationError(
            f"this v0.1 {subject} cannot be read",
            code=PROOF_BUNDLE_INVALID,
            details={"subject": subject},
        ) from error
