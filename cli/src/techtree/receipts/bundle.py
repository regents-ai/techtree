"""The portable local proof. Spec section 7.11.

A run directory holds everything: inputs, raw upstream traces, container logs,
the worker's own log. Most of it may not leave the machine — the DataPolicy
prohibits uploading or publishing raw episodes — and most of it is not what a
reader checking a claim needs. The proof bundle is the subset that travels:

```text
runs/<run-id>/proof/
├── bundle.json                        signed manifest over everything below
├── executor-public.json               the key the participant signed with
├── campaign.json
├── data-policy.json
├── taskset-lock.json
├── taskset-validation-receipt.json
├── baseline-experiment.json
├── candidate-experiment.json
├── baseline-receipt-set.json
├── candidate-receipt-set.json
├── receipts/{baseline,candidate}/NNNN.json    signed EpisodeReceipt envelopes
└── uplift-report.json                 the signed UpliftReport envelope
```

Raw ``traces.jsonl``, the upstream log and the worker log stay behind. The
receipts cite their digests, so a reader holding the run directory can check
them; a reader holding only the bundle cannot, and the bundle never pretends
otherwise.

Three decisions shape this module.

*Every file is canonical bytes.* The digest of a bundle file and the digest of
the object inside it are the same number, so verification hashes what is on
disk rather than what a parser reconstructed. That is what "verifiable from
exact stored bytes" has to mean to be worth saying.

*The manifest is signed too.* Section 7.11 describes ``bundle.json`` as the
manifest; it is stored as a signed envelope around it. Without that, the one
thing the artifact digests cannot protect is the artifact list itself: a
bundle whose manifest was rewritten to name a different set of files — a
report from another run of the same participant, say — would otherwise verify.
Signing it binds the list to the same key as everything it lists.

*P1 is a conclusion, never an assumption.* :data:`P1_CONDITIONS` is the
decisions-0005 section 3.4 list, spelled once. It is evaluated twice on
purpose: :func:`assess_local_attestation` decides, before a report exists,
whether this run is entitled to a signed grade at all, and
:func:`techtree.receipts.verify.verify_local_bundle` re-derives every condition
from the written bytes afterwards. A report claiming P1 whose bundle does not
re-establish all six is not recorded as a result.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, Self

from pydantic import BaseModel, model_validator

from techtree.canonical import canonical_json_bytes, digest_object, sha256_digest_bytes
from techtree.fs import atomic_write_bytes, ensure_private_directory
from techtree.identity.models import ExecutorIdentity
from techtree.identity.service import IdentityService, verify_signed_object
from techtree.models.base import (
    ArtifactRef,
    Digest,
    NonEmptyString,
    ObjectEnvelope,
    ProtocolModel,
)
from techtree.models.campaign import CampaignSpec
from techtree.models.data_policy import DataPolicy
from techtree.models.episode_receipt import EpisodeReceipt, ScoreStatus
from techtree.models.experiment import ExperimentManifest, ExperimentVariant
from techtree.models.uplift_report import ComparisonStatus, UpliftReport
from techtree.models.validation import TasksetLock, TasksetValidationReceipt
from techtree.receipts.set import ReceiptSetManifest
from techtree.receipts.uplift import LocalAttestation

__all__ = [
    "BUNDLE_DIRECTORY",
    "BUNDLE_MANIFEST_FILENAME",
    "BUNDLE_MEDIA_TYPE",
    "LOCAL_PROOF_BUNDLE_SCHEMA_VERSION",
    "P1_ARTIFACT_DIGESTS_VERIFY",
    "P1_COMPARISON_CONTROLLED",
    "P1_CONDITIONS",
    "P1_PUBLIC_KEY_PRESENT",
    "P1_RECEIPTS_SIGNED",
    "P1_REPORT_SIGNED",
    "P1_SCORE_VALID",
    "PROOF_BUNDLE_INVALID",
    "PUBLIC_IDENTITY_FILENAME",
    "REPORT_FILENAME",
    "AttestationAssessment",
    "LocalProofBundleContents",
    "LocalProofBundleManifest",
    "ProofCondition",
    "ReferencedObject",
    "assess_local_attestation",
    "build_local_bundle",
    "bundle_files",
    "experiment_filename",
    "proof_bundle_dir",
    "receipt_filename",
    "receipt_set_filename",
    "write_local_bundle",
]

#: A local bundle manifest, versioned as one: the frozen v0.1 protocol has no
#: proof-bundle object and inventing one would be an unratified amendment.
LOCAL_PROOF_BUNDLE_SCHEMA_VERSION: Final = "techtree.local-proof-bundle.v1alpha1"

#: Stable error code. Spec section 15.
PROOF_BUNDLE_INVALID: Final = "proof_bundle_invalid"

BUNDLE_DIRECTORY: Final = "proof"
BUNDLE_MANIFEST_FILENAME: Final = "bundle.json"
PUBLIC_IDENTITY_FILENAME: Final = "executor-public.json"
CAMPAIGN_FILENAME: Final = "campaign.json"
DATA_POLICY_FILENAME: Final = "data-policy.json"
TASKSET_LOCK_FILENAME: Final = "taskset-lock.json"
VALIDATION_RECEIPT_FILENAME: Final = "taskset-validation-receipt.json"
REPORT_FILENAME: Final = "uplift-report.json"
RECEIPTS_DIRECTORY: Final = "receipts"

BUNDLE_MEDIA_TYPE: Final = "application/json"

#: Receipt filenames are positional, so reading the directory in name order
#: reads the receipts back in the Campaign's committed task order.
_POSITION_WIDTH: Final = 4

_PASSED: Final = "passed"
_FAILED: Final = "failed"

#: Both sides, always in comparison order, so a bundle written twice from the
#: same run places its files identically.
_VARIANT_ORDER: Final[tuple[ExperimentVariant, ...]] = (
    ExperimentVariant.BASELINE,
    ExperimentVariant.CANDIDATE,
)

# ---------------------------------------------------------------------------
# The section 3.4 conditions, spelled once
# ---------------------------------------------------------------------------

#: "all referenced artifact digests verify"
P1_ARTIFACT_DIGESTS_VERIFY: Final = "artifact_digests_verify"
#: "all EpisodeReceipts are wrapped in signed ObjectEnvelopes"
P1_RECEIPTS_SIGNED: Final = "receipts_signed"
#: "the UpliftReport is wrapped in a signed ObjectEnvelope"
P1_REPORT_SIGNED: Final = "report_signed"
#: "the local public key is included in the bundle"
P1_PUBLIC_KEY_PRESENT: Final = "public_key_in_bundle"
#: "the comparison is controlled or controlled_with_warnings"
P1_COMPARISON_CONTROLLED: Final = "comparison_controlled"
#: "score status is valid"
P1_SCORE_VALID: Final = "score_valid"

#: Decisions document 0005 section 3.4, in the order it states them. Every one
#: is a condition on stored bytes; none of them is satisfied by a claim in a
#: document about itself.
P1_CONDITIONS: Final[tuple[str, ...]] = (
    P1_ARTIFACT_DIGESTS_VERIFY,
    P1_RECEIPTS_SIGNED,
    P1_REPORT_SIGNED,
    P1_PUBLIC_KEY_PRESENT,
    P1_COMPARISON_CONTROLLED,
    P1_SCORE_VALID,
)


class ProofCondition(ProtocolModel):
    """One decisions-0005 section 3.4 condition and whether it holds."""

    id: NonEmptyString
    status: Literal["passed", "failed"]
    detail: NonEmptyString


@dataclass(frozen=True)
class AttestationAssessment:
    """Whether this run may sign its report into a P1 grade, and why."""

    attestation: LocalAttestation
    conditions: list[ProofCondition]

    @property
    def failures(self) -> list[ProofCondition]:
        """Return every condition that does not hold."""
        return [
            condition for condition in self.conditions if condition.status == _FAILED
        ]


@dataclass(frozen=True)
class ReferencedObject:
    """One object a report cites, together with the digest it cites it under."""

    label: str
    value: BaseModel
    expected: Digest


# ---------------------------------------------------------------------------
# The manifest
# ---------------------------------------------------------------------------


class LocalProofBundleManifest(ProtocolModel):
    """Everything one portable local proof carries, committed to by digest."""

    schema_version: Literal["techtree.local-proof-bundle.v1alpha1"]
    run_id: NonEmptyString
    campaign_spec_digest: Digest
    data_policy_digest: Digest
    executor_identity: ExecutorIdentity
    artifacts: list[ArtifactRef]
    root_report_digest: Digest

    @model_validator(mode="after")
    def _check_every_artifact_is_placed_once(self) -> Self:
        """Reject a manifest that names a file twice or names none."""
        paths = [artifact.relative_path for artifact in self.artifacts]
        if not paths:
            raise ValueError("a proof bundle commits to at least one artifact")
        if any(path is None for path in paths):
            raise ValueError(
                "every artifact in a proof bundle is placed by relative path; "
                "a digest with nowhere to look is not checkable"
            )
        if len(set(paths)) != len(paths):
            raise ValueError("a proof bundle places each artifact exactly once")
        return self

    def artifact(self, relative_path: str) -> ArtifactRef | None:
        """Return one placed artifact, or ``None`` when it is not carried."""
        for reference in self.artifacts:
            if reference.relative_path == relative_path:
                return reference
        return None


@dataclass(frozen=True)
class LocalProofBundleContents:
    """The objects one bundle is written from.

    The receipts and the report arrive already signed. This module places
    bytes; it does not decide what is worth signing, and it never holds private
    key material.
    """

    identity: ExecutorIdentity
    campaign: CampaignSpec
    data_policy: DataPolicy
    taskset_lock: TasksetLock
    validation_receipt: TasksetValidationReceipt
    experiments: Mapping[ExperimentVariant, ExperimentManifest]
    receipt_sets: Mapping[ExperimentVariant, ReceiptSetManifest]
    receipts: Mapping[ExperimentVariant, Sequence[ObjectEnvelope[EpisodeReceipt]]]
    report: ObjectEnvelope[UpliftReport]


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------


def proof_bundle_dir(run_root: Path) -> Path:
    """Return where one run's portable proof lives."""
    return run_root / BUNDLE_DIRECTORY


def experiment_filename(variant: ExperimentVariant) -> str:
    """Return one variant's experiment manifest filename."""
    return f"{variant.value}-experiment.json"


def receipt_set_filename(variant: ExperimentVariant) -> str:
    """Return one variant's receipt-set manifest filename."""
    return f"{variant.value}-receipt-set.json"


def receipt_filename(variant: ExperimentVariant, position: int) -> str:
    """Return one receipt's placement inside the bundle."""
    return f"{RECEIPTS_DIRECTORY}/{variant.value}/{position:0{_POSITION_WIDTH}d}.json"


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def bundle_files(contents: LocalProofBundleContents) -> dict[str, bytes]:
    """Return every bundle file except the manifest, as canonical bytes.

    The manifest is excluded because it commits to these: a file cannot carry
    the digest of a document that carries its digest.
    """
    files: dict[str, bytes] = {
        PUBLIC_IDENTITY_FILENAME: canonical_json_bytes(contents.identity),
        CAMPAIGN_FILENAME: canonical_json_bytes(contents.campaign),
        DATA_POLICY_FILENAME: canonical_json_bytes(contents.data_policy),
        TASKSET_LOCK_FILENAME: canonical_json_bytes(contents.taskset_lock),
        VALIDATION_RECEIPT_FILENAME: canonical_json_bytes(contents.validation_receipt),
        REPORT_FILENAME: canonical_json_bytes(contents.report),
    }
    for variant in _VARIANT_ORDER:
        files[experiment_filename(variant)] = canonical_json_bytes(
            contents.experiments[variant]
        )
        files[receipt_set_filename(variant)] = canonical_json_bytes(
            contents.receipt_sets[variant]
        )
        for position, envelope in enumerate(contents.receipts[variant]):
            files[receipt_filename(variant, position)] = canonical_json_bytes(envelope)
    return files


def build_local_bundle(
    *, run_id: str, contents: LocalProofBundleContents
) -> LocalProofBundleManifest:
    """Return the manifest committing to every file this bundle carries."""
    files = bundle_files(contents)
    return LocalProofBundleManifest(
        schema_version=LOCAL_PROOF_BUNDLE_SCHEMA_VERSION,
        run_id=run_id,
        campaign_spec_digest=digest_object(contents.campaign),
        data_policy_digest=digest_object(contents.data_policy),
        executor_identity=contents.identity,
        artifacts=[
            ArtifactRef(
                digest=sha256_digest_bytes(data),
                media_type=BUNDLE_MEDIA_TYPE,
                size=len(data),
                relative_path=relative_path,
            )
            for relative_path, data in sorted(files.items())
        ],
        root_report_digest=contents.report.payload_digest,
    )


def write_local_bundle(
    *,
    run_root: Path,
    contents: LocalProofBundleContents,
    identity_service: IdentityService,
) -> Path:
    """Write the bundle and its signed manifest, and return the directory.

    The manifest is written last. A bundle interrupted halfway has no manifest
    and is therefore not a bundle, which is a better outcome than one that
    names files that are not there yet.
    """
    directory = proof_bundle_dir(run_root)
    ensure_private_directory(directory)

    for relative_path, data in sorted(bundle_files(contents).items()):
        destination = directory / relative_path
        ensure_private_directory(destination.parent)
        atomic_write_bytes(destination, data)

    manifest = build_local_bundle(
        run_id=contents.report.payload.run_id, contents=contents
    )
    sealed = identity_service.sign_object(manifest)
    atomic_write_bytes(
        directory / BUNDLE_MANIFEST_FILENAME, canonical_json_bytes(sealed)
    )
    return directory


# ---------------------------------------------------------------------------
# The section 3.4 assessment
# ---------------------------------------------------------------------------


def assess_local_attestation(
    *,
    identity: ExecutorIdentity | None,
    identity_self_check: bool,
    referenced_objects: Sequence[ReferencedObject],
    signed_receipts: Mapping[
        ExperimentVariant, Sequence[ObjectEnvelope[EpisodeReceipt]]
    ],
    comparison: ComparisonStatus,
    score: ScoreStatus,
) -> AttestationAssessment:
    """Decide whether this run's report may be signed into a P1 grade.

    Five of the six section 3.4 conditions can be established before a report
    exists, and they are established here, from the objects themselves rather
    than from anything anyone recorded about them. The sixth — that the report
    travels in a signed envelope — is a fact about a document that does not
    exist yet; it is settled by verifying the written bundle before the report
    is recorded as the run's result, and it is reported here as pending on the
    same identity that would sign it.

    Any failure returns :attr:`~techtree.receipts.uplift.LocalAttestation.
    UNATTESTED`, which is what makes the report withhold its verdict instead of
    claiming a grade it did not earn.
    """
    conditions = [
        _artifact_digests_condition(referenced_objects),
        _receipts_signed_condition(identity, signed_receipts),
        _report_signed_condition(identity, identity_self_check),
        _public_key_condition(identity, identity_self_check),
        _comparison_condition(comparison),
        _score_condition(score),
    ]
    failed = [condition for condition in conditions if condition.status == _FAILED]
    return AttestationAssessment(
        attestation=(
            LocalAttestation.UNATTESTED if failed else LocalAttestation.LOCAL_ED25519
        ),
        conditions=conditions,
    )


def _artifact_digests_condition(
    referenced: Sequence[ReferencedObject],
) -> ProofCondition:
    """Require every object the report cites to re-digest to the cited digest."""
    if not referenced:
        return ProofCondition(
            id=P1_ARTIFACT_DIGESTS_VERIFY,
            status=_FAILED,
            detail="no referenced artifact was offered for checking",
        )
    broken = [
        item.label for item in referenced if digest_object(item.value) != item.expected
    ]
    if broken:
        return ProofCondition(
            id=P1_ARTIFACT_DIGESTS_VERIFY,
            status=_FAILED,
            detail=(
                "these objects no longer match the digests this run cites them "
                f"under: {', '.join(sorted(broken))}"
            ),
        )
    return ProofCondition(
        id=P1_ARTIFACT_DIGESTS_VERIFY,
        status=_PASSED,
        detail=f"{len(referenced)} referenced artifact digests recomputed and matched",
    )


def _receipts_signed_condition(
    identity: ExecutorIdentity | None,
    signed_receipts: Mapping[
        ExperimentVariant, Sequence[ObjectEnvelope[EpisodeReceipt]]
    ],
) -> ProofCondition:
    """Require every receipt to travel in an envelope this key's signature verifies."""
    if identity is None:
        return ProofCondition(
            id=P1_RECEIPTS_SIGNED,
            status=_FAILED,
            detail="there is no local identity, so no receipt is signed",
        )
    total = 0
    unverified: list[str] = []
    for variant in _VARIANT_ORDER:
        for position, envelope in enumerate(signed_receipts.get(variant, ())):
            total += 1
            result = verify_signed_object(identity=identity, envelope=envelope)
            if not result.verified:
                unverified.append(f"{variant.value}/{position}")
    if not total:
        return ProofCondition(
            id=P1_RECEIPTS_SIGNED,
            status=_FAILED,
            detail="this comparison has no receipts to sign",
        )
    if unverified:
        return ProofCondition(
            id=P1_RECEIPTS_SIGNED,
            status=_FAILED,
            detail=(
                "these receipts are not sealed by a verifying signature: "
                + ", ".join(unverified)
            ),
        )
    return ProofCondition(
        id=P1_RECEIPTS_SIGNED,
        status=_PASSED,
        detail=f"{total} receipts travel in signed envelopes that verify",
    )


def _report_signed_condition(
    identity: ExecutorIdentity | None, self_check: bool
) -> ProofCondition:
    """Require a usable key for the report envelope that is about to be made."""
    if identity is None or not self_check:
        return ProofCondition(
            id=P1_REPORT_SIGNED,
            status=_FAILED,
            detail=("no usable local identity is available to sign this run's report"),
        )
    return ProofCondition(
        id=P1_REPORT_SIGNED,
        status=_PASSED,
        detail=(
            f"the report is signed under key {identity.key_id}, and the written "
            "bundle is verified before the report is recorded"
        ),
    )


def _public_key_condition(
    identity: ExecutorIdentity | None, self_check: bool
) -> ProofCondition:
    """Require the public half to exist and to match the key that signs."""
    if identity is None:
        return ProofCondition(
            id=P1_PUBLIC_KEY_PRESENT,
            status=_FAILED,
            detail="this machine has no local identity to include in a bundle",
        )
    if not self_check:
        return ProofCondition(
            id=P1_PUBLIC_KEY_PRESENT,
            status=_FAILED,
            detail=("the stored public key does not describe the key that would sign"),
        )
    return ProofCondition(
        id=P1_PUBLIC_KEY_PRESENT,
        status=_PASSED,
        detail=f"public key {identity.key_id} travels with the proof",
    )


def _comparison_condition(comparison: ComparisonStatus) -> ProofCondition:
    """Require a controlled comparison, warnings included."""
    controlled = comparison in (
        ComparisonStatus.CONTROLLED,
        ComparisonStatus.CONTROLLED_WITH_WARNINGS,
    )
    return ProofCondition(
        id=P1_COMPARISON_CONTROLLED,
        status=_PASSED if controlled else _FAILED,
        detail=f"the comparison is {comparison.value}",
    )


def _score_condition(score: ScoreStatus) -> ProofCondition:
    """Require valid scores."""
    return ProofCondition(
        id=P1_SCORE_VALID,
        status=_PASSED if score is ScoreStatus.VALID else _FAILED,
        detail=f"the recorded score status is {score.value}",
    )
