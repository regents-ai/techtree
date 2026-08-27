"""Checking a local proof, offline, from exactly the bytes it stored.

Spec section 7.12, and the verification order fixed by section 7.11.

Nothing in this module reaches the network, the catalog, the settings file, or
the machine's own identity. It is handed a directory and it answers one
question about it: do these files still say what they said, and do they still
agree with each other? That is the whole of what a self-issued key can
establish, and stating it precisely is what keeps ``P1`` from drifting into
sounding like something a third party checked.

The order is the specification's, and each step depends on the one before it:

```text
 1. Validate the bundle manifest.
 2. Verify every artifact digest.
 3. Verify Campaign and policy linkage.
 4. Verify TasksetLock and validation-receipt linkage.
 5. Verify every EpisodeReceipt envelope signature.
 6. Verify the receipt sets.
 7. Verify the UpliftReport envelope signature.
 8. Recompute the paired aggregate from the receipts.
 9. Require the recomputed result to equal the report.
10. Require the report's publication fields to hold together.
```

Two habits make those steps mean something.

*Everything is recomputed.* A digest recorded beside the thing it describes is
worth nothing on its own; every digest here is taken again from the file's own
bytes, and every aggregate is recomputed from the receipts rather than read out
of the report it is supposed to check.

*Nothing raises past the first problem.* A reader whose bundle is broken wants
to know everything that is broken about it, so every step records a named check
and the verdict is computed from the collected checks. The typed section 15
errors are then raised by the caller — the CLI — which knows whether the reader
asked for a verdict or for a report.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Final

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import digest_object, sha256_digest_bytes
from techtree.errors import VerificationError
from techtree.identity.models import (
    LOCAL_IDENTITY_INVALID,
    SIGNATURE_VERIFICATION_FAILED,
    ExecutorIdentity,
    VerificationMessage,
    VerificationResult,
    VerificationStatus,
)
from techtree.identity.service import verify_signed_object
from techtree.models.base import ObjectEnvelope
from techtree.models.campaign import CampaignSpec
from techtree.models.data_policy import DataPolicy
from techtree.models.episode_receipt import EpisodeReceipt
from techtree.models.experiment import ExperimentManifest, ExperimentVariant
from techtree.models.uplift_report import (
    ComparisonStatus,
    PublicationStatus,
    UpliftReport,
)
from techtree.models.validation import TasksetLock, TasksetValidationReceipt
from techtree.receipts.bundle import (
    BUNDLE_MANIFEST_FILENAME,
    CAMPAIGN_FILENAME,
    DATA_POLICY_FILENAME,
    P1_ARTIFACT_DIGESTS_VERIFY,
    P1_COMPARISON_CONTROLLED,
    P1_PUBLIC_KEY_PRESENT,
    P1_RECEIPTS_SIGNED,
    P1_REPORT_SIGNED,
    P1_SCORE_VALID,
    PROOF_BUNDLE_INVALID,
    PUBLIC_IDENTITY_FILENAME,
    REPORT_FILENAME,
    TASKSET_LOCK_FILENAME,
    VALIDATION_RECEIPT_FILENAME,
    LocalProofBundleManifest,
    experiment_filename,
    receipt_filename,
    receipt_set_filename,
)
from techtree.receipts.compare import COMPARISON_INVALID
from techtree.receipts.execution import (
    COMPARISON_EXECUTION_RECORD_INVALID,
    EXECUTION_RECORD_FILENAME,
    OPERATIONAL_EVIDENCE_UNAVAILABLE,
    ComparisonExecutionRecord,
)
from techtree.receipts.set import (
    RECEIPT_SET_INVALID,
    ReceiptSetManifest,
    verify_receipt_set,
)
from techtree.receipts.uplift import (
    aggregate_primary_result,
    pair_task_rewards,
    publication_eligible_for,
)

__all__ = [
    "LocalProofVerifier",
    "verify_local_bundle",
    "verify_report_envelope",
]

_PASSED: Final = "passed"
_FAILED: Final = "failed"
_WARNING: Final = "warning"

_VARIANT_ORDER: Final[tuple[ExperimentVariant, ...]] = (
    ExperimentVariant.BASELINE,
    ExperimentVariant.CANDIDATE,
)

#: What a P1 report claims, in the only words decisions document 0005 permits.
P1_MEANING: Final = "integrity-bound, participant-attested local execution"


class LocalProofVerifier:
    """Verifies local proofs without needing anything but their own bytes."""

    def verify_report(self, path: Path) -> VerificationResult:
        """Verify one signed UpliftReport envelope against the key beside it."""
        return verify_report_envelope(path)

    def verify_bundle(self, path: Path) -> VerificationResult:
        """Verify a whole proof bundle, in the section 7.11 order."""
        return verify_local_bundle(path)

    def explain(self, result: VerificationResult) -> list[VerificationMessage]:
        """Summarize a verification under the five headings a reader needs.

        Spec section 7.12 requires human output to keep these apart, because
        collapsing them is exactly how "the signature verifies" turns into
        "the result is proven".
        """
        return _explain(result)


# ---------------------------------------------------------------------------
# One envelope
# ---------------------------------------------------------------------------


def verify_report_envelope(path: Path) -> VerificationResult:
    """Verify a signed report envelope using the public key stored beside it.

    A bare envelope carries a signature and a key identifier, and no key. The
    public half lives next to it in the bundle layout, so that is where this
    looks; a report handed over without it cannot be checked at all, and saying
    so is more useful than reporting a signature as unverifiable.
    """
    checks = _Checks()
    envelope = _load_envelope(path, UpliftReport, checks, "uplift-report")
    identity = _load_identity(path.parent / PUBLIC_IDENTITY_FILENAME, checks)
    if envelope is None or identity is None:
        return checks.result()

    checks.extend(
        verify_signed_object(
            identity=identity, envelope=envelope, subject="uplift-report"
        ).messages
    )
    _check_publication(envelope.payload, checks)
    return checks.result()


# ---------------------------------------------------------------------------
# A whole bundle
# ---------------------------------------------------------------------------


def verify_local_bundle(path: Path) -> VerificationResult:
    """Verify one proof bundle offline and return every check it ran."""
    checks = _Checks()
    directory = path if path.is_dir() else path.parent

    # 1. The manifest, and the key it says signed everything.
    sealed = _load_envelope(
        directory / BUNDLE_MANIFEST_FILENAME,
        LocalProofBundleManifest,
        checks,
        "bundle",
    )
    if sealed is None:
        return checks.result()
    manifest = sealed.payload
    identity = manifest.executor_identity
    checks.extend(
        verify_signed_object(
            identity=identity, envelope=sealed, subject="bundle"
        ).messages
    )

    # 2. Every artifact digest, recomputed from the stored file.
    _check_artifacts(directory, manifest, checks)

    # The public key travels as its own file, and it must be the same key.
    stored_identity = _load_identity(directory / PUBLIC_IDENTITY_FILENAME, checks)
    checks.record(
        "bundle.public_key",
        _PASSED if stored_identity == identity else _FAILED,
        LOCAL_IDENTITY_INVALID,
        (
            f"the bundle carries public key {identity.key_id}"
            if stored_identity == identity
            else "the stored public key is not the key the manifest names"
        ),
    )

    documents = _load_documents(directory, checks)
    if documents is None:
        return checks.result()

    # 3-4. Lineage: Campaign, policy, lock, validation receipt.
    _check_linkage(manifest, documents, checks)

    # 5-6. Receipts and the commitments over them.
    receipts = _check_receipts(directory, documents, identity, checks)

    # 7. The report envelope itself.
    checks.extend(
        verify_signed_object(
            identity=identity, envelope=documents.report, subject="uplift-report"
        ).messages
    )
    checks.record(
        "bundle.root_report_digest",
        _PASSED
        if manifest.root_report_digest == documents.report.payload_digest
        else _FAILED,
        PROOF_BUNDLE_INVALID,
        "the manifest's root report digest names the report it carries"
        if manifest.root_report_digest == documents.report.payload_digest
        else "the manifest names a different report than the one it carries",
    )

    # 8-9. The aggregate, recomputed from the receipts.
    if receipts is not None:
        _check_aggregate(documents, receipts, checks)

    # 10. Publication, which never happened and could not have.
    _check_publication(documents.report.payload, checks)

    # The operational record, if this run produced one. Decisions 0007 R6: it
    # is checked as carefully as everything else and its absence is a warning,
    # because it says what the comparison consumed rather than what it proved.
    _check_execution_record(directory, manifest, documents, identity, checks)

    # The decisions-0005 section 3.4 conditions, re-derived from these bytes.
    _check_p1_conditions(
        manifest=manifest,
        documents=documents,
        receipts=receipts,
        identity_matches=stored_identity == identity,
        checks=checks,
    )
    return checks.result()


# ---------------------------------------------------------------------------
# The pieces
# ---------------------------------------------------------------------------


class _Documents:
    """Every parsed document one bundle carries."""

    def __init__(
        self,
        *,
        campaign: CampaignSpec,
        data_policy: DataPolicy,
        taskset_lock: TasksetLock,
        validation_receipt: TasksetValidationReceipt,
        experiments: dict[ExperimentVariant, ExperimentManifest],
        receipt_sets: dict[ExperimentVariant, ReceiptSetManifest],
        report: ObjectEnvelope[UpliftReport],
    ) -> None:
        self.campaign = campaign
        self.data_policy = data_policy
        self.taskset_lock = taskset_lock
        self.validation_receipt = validation_receipt
        self.experiments = experiments
        self.receipt_sets = receipt_sets
        self.report = report


def _load_documents(directory: Path, checks: _Checks) -> _Documents | None:
    """Parse every document the bundle layout requires, or say which is unreadable."""
    campaign = _load_model(directory / CAMPAIGN_FILENAME, CampaignSpec, checks)
    policy = _load_model(directory / DATA_POLICY_FILENAME, DataPolicy, checks)
    lock = _load_model(directory / TASKSET_LOCK_FILENAME, TasksetLock, checks)
    receipt = _load_model(
        directory / VALIDATION_RECEIPT_FILENAME, TasksetValidationReceipt, checks
    )
    report = _load_envelope(
        directory / REPORT_FILENAME, UpliftReport, checks, "uplift-report"
    )
    experiments = {
        variant: _load_model(
            directory / experiment_filename(variant), ExperimentManifest, checks
        )
        for variant in _VARIANT_ORDER
    }
    receipt_sets = {
        variant: _load_model(
            directory / receipt_set_filename(variant), ReceiptSetManifest, checks
        )
        for variant in _VARIANT_ORDER
    }

    if (
        campaign is None
        or policy is None
        or lock is None
        or receipt is None
        or report is None
        or any(value is None for value in experiments.values())
        or any(value is None for value in receipt_sets.values())
    ):
        return None
    return _Documents(
        campaign=campaign,
        data_policy=policy,
        taskset_lock=lock,
        validation_receipt=receipt,
        experiments={
            variant: value
            for variant, value in experiments.items()
            if value is not None
        },
        receipt_sets={
            variant: value
            for variant, value in receipt_sets.items()
            if value is not None
        },
        report=report,
    )


def _check_artifacts(
    directory: Path, manifest: LocalProofBundleManifest, checks: _Checks
) -> None:
    """Recompute every placed artifact's digest and size from its own bytes."""
    for reference in manifest.artifacts:
        relative_path = reference.relative_path
        assert relative_path is not None  # the manifest's own validator requires it
        stored = directory / relative_path
        try:
            data = stored.read_bytes()
        except OSError:
            checks.record(
                f"artifact.{relative_path}",
                _FAILED,
                PROOF_BUNDLE_INVALID,
                f"the bundle names {relative_path}, which is not there",
            )
            continue
        digest = sha256_digest_bytes(data)
        matches = digest == reference.digest and len(data) == reference.size
        checks.record(
            f"artifact.{relative_path}",
            _PASSED if matches else _FAILED,
            PROOF_BUNDLE_INVALID,
            f"{relative_path} matches the digest the bundle commits to"
            if matches
            else (
                f"{relative_path} has changed since the bundle was written: "
                f"committed {reference.digest}, stored {digest}"
            ),
        )


def _check_linkage(
    manifest: LocalProofBundleManifest, documents: _Documents, checks: _Checks
) -> None:
    """Check every edge between the documents, in both directions."""
    report = documents.report.payload
    campaign_digest = digest_object(documents.campaign)
    policy_digest = digest_object(documents.data_policy)
    lock_digest = digest_object(documents.taskset_lock)
    receipt_digest = digest_object(documents.validation_receipt)

    for identifier, expected, found, description in (
        (
            "linkage.manifest_campaign",
            manifest.campaign_spec_digest,
            campaign_digest,
            "the bundle manifest names the Campaign it carries",
        ),
        (
            "linkage.report_campaign",
            report.campaign_spec_digest,
            campaign_digest,
            "the report was produced under the Campaign the bundle carries",
        ),
        (
            "linkage.campaign_policy",
            documents.campaign.data_policy_digest,
            policy_digest,
            "the Campaign names the DataPolicy the bundle carries",
        ),
        (
            "linkage.report_policy",
            report.data_policy_digest,
            policy_digest,
            "the report was produced under that same DataPolicy",
        ),
        (
            "linkage.manifest_policy",
            manifest.data_policy_digest,
            policy_digest,
            "the bundle manifest names that same DataPolicy",
        ),
        (
            "linkage.validation_lock",
            documents.validation_receipt.taskset_lock_digest,
            lock_digest,
            "the validation receipt validates the TasksetLock the bundle carries",
        ),
        (
            "linkage.campaign_validation",
            documents.campaign.taskset.validation_receipt_digest,
            receipt_digest,
            "the Campaign commits to that validation receipt",
        ),
        (
            "linkage.report_validation",
            report.taskset_validation_receipt_digest,
            receipt_digest,
            "the report cites that validation receipt",
        ),
        (
            "linkage.baseline_manifest",
            report.baseline_manifest_digest,
            digest_object(documents.experiments[ExperimentVariant.BASELINE]),
            "the report cites the baseline experiment the bundle carries",
        ),
        (
            "linkage.candidate_manifest",
            report.candidate_manifest_digest,
            digest_object(documents.experiments[ExperimentVariant.CANDIDATE]),
            "the report cites the candidate experiment the bundle carries",
        ),
    ):
        checks.record(
            identifier,
            _PASSED if expected == found else _FAILED,
            COMPARISON_INVALID,
            description
            if expected == found
            else f"{description} — but it names {expected} and this is {found}",
        )

    committed = list(documents.campaign.taskset.membership.ordered_task_hashes)
    locked = list(documents.taskset_lock.ordered_task_hashes)
    checks.record(
        "linkage.taskset_membership",
        _PASSED if committed == locked else _FAILED,
        COMPARISON_INVALID,
        f"the lock holds the {len(committed)} tasks the Campaign commits to"
        if committed == locked
        else "the lock does not hold the tasks the Campaign commits to",
    )
    checks.record(
        "linkage.run_id",
        _PASSED if manifest.run_id == report.run_id else _FAILED,
        PROOF_BUNDLE_INVALID,
        f"the bundle and the report describe run {report.run_id}"
        if manifest.run_id == report.run_id
        else "the bundle and the report describe different runs",
    )


def _check_receipts(
    directory: Path,
    documents: _Documents,
    identity: ExecutorIdentity,
    checks: _Checks,
) -> dict[ExperimentVariant, list[EpisodeReceipt]] | None:
    """Verify every receipt's signature and every variant's commitment."""
    committed = list(documents.taskset_lock.ordered_task_hashes)
    loaded: dict[ExperimentVariant, list[EpisodeReceipt]] = {}

    for variant in _VARIANT_ORDER:
        receipt_set = documents.receipt_sets[variant]
        envelopes: list[ObjectEnvelope[EpisodeReceipt]] = []
        for position in range(receipt_set.receipt_count):
            relative_path = receipt_filename(variant, position)
            envelope = _load_envelope(
                directory / relative_path, EpisodeReceipt, checks, relative_path
            )
            if envelope is None:
                return None
            envelopes.append(envelope)
            checks.extend(
                verify_signed_object(
                    identity=identity, envelope=envelope, subject=relative_path
                ).messages
            )

        try:
            verify_receipt_set(
                manifest=receipt_set,
                signed_receipts=envelopes,
                ordered_task_hashes=committed,
            )
        except VerificationError as error:
            checks.record(
                f"receipt_set.{variant.value}",
                _FAILED,
                RECEIPT_SET_INVALID,
                error.message,
            )
            return None

        checks.record(
            f"receipt_set.{variant.value}",
            _PASSED,
            RECEIPT_SET_INVALID,
            (
                f"the {variant.value} receipt set commits to its "
                f"{receipt_set.receipt_count} receipts in committed task order"
            ),
        )
        expected_manifest = digest_object(documents.experiments[variant])
        checks.record(
            f"receipt_set.{variant.value}.experiment",
            _PASSED
            if receipt_set.experiment_manifest_digest == expected_manifest
            else _FAILED,
            RECEIPT_SET_INVALID,
            f"the {variant.value} receipts were scored under the experiment "
            "manifest the bundle carries"
            if receipt_set.experiment_manifest_digest == expected_manifest
            else f"the {variant.value} receipts were scored under a different "
            "experiment manifest than the one the bundle carries",
        )
        loaded[variant] = [envelope.payload for envelope in envelopes]

    return loaded


def _check_aggregate(
    documents: _Documents,
    receipts: dict[ExperimentVariant, list[EpisodeReceipt]],
    checks: _Checks,
) -> None:
    """Recompute the paired aggregate and require the report to equal it."""
    report = documents.report.payload
    reward = documents.campaign.scoring.primary_reward
    try:
        deltas = pair_task_rewards(
            baseline_receipts=receipts[ExperimentVariant.BASELINE],
            candidate_receipts=receipts[ExperimentVariant.CANDIDATE],
            ordered_task_hashes=list(documents.taskset_lock.ordered_task_hashes),
            reward_name=reward,
        )
        primary = aggregate_primary_result(deltas, reward)
    except VerificationError as error:
        checks.record(
            "aggregate.recomputed",
            _FAILED,
            COMPARISON_INVALID,
            f"the receipts cannot be paired into a comparison: {error.message}",
        )
        return

    matches = list(deltas) == list(report.task_deltas) and primary == (
        report.primary_result
    )
    checks.record(
        "aggregate.recomputed",
        _PASSED if matches else _FAILED,
        COMPARISON_INVALID,
        (
            f"the report's result is the one these receipts produce: "
            f"{primary.baseline_mean:.4f} against {primary.candidate_mean:.4f} "
            f"on {reward}"
        )
        if matches
        else (
            "the report states a different result than the one its own receipts produce"
        ),
    )


def _check_execution_record(
    directory: Path,
    manifest: LocalProofBundleManifest,
    documents: _Documents,
    identity: ExecutorIdentity,
    checks: _Checks,
) -> None:
    """Check the comparison's operational record, when the bundle carries one.

    Three states, and they mean three different things.

    *The manifest commits to a record.* Then it is held to the same standard as
    everything else: it parses, its signature verifies against the same key,
    and it describes this run and these two experiments. A record that fails
    any of those is a failed check — an operational claim signed into a proof
    is still a claim.

    *Nothing is there and nothing was promised.* Decisions document 0007 R6:
    the economics are unknown, the measurement is untouched, and the reader is
    told so as a warning rather than a failure.

    *A file is there that the manifest never named.* That is a failure. The
    signed index is what binds a record to this run, and bytes that arrived
    outside it are not evidence of anything.
    """
    committed = manifest.artifact(EXECUTION_RECORD_FILENAME)
    path = directory / EXECUTION_RECORD_FILENAME
    if committed is None:
        present = path.is_file()
        checks.record(
            "execution_record.present",
            _FAILED if present else _WARNING,
            COMPARISON_EXECUTION_RECORD_INVALID
            if present
            else OPERATIONAL_EVIDENCE_UNAVAILABLE,
            (
                "this bundle holds a comparison execution record its signed "
                "manifest does not commit to, so nothing binds it to this run"
                if present
                else (
                    "this bundle carries no comparison execution record, so "
                    "the cost and timing of this comparison are unavailable; "
                    "what it measured is unaffected"
                )
            ),
        )
        return

    envelope = _load_envelope(
        path, ComparisonExecutionRecord, checks, "execution-record"
    )
    if envelope is None:
        return
    checks.extend(
        verify_signed_object(
            identity=identity, envelope=envelope, subject="execution-record"
        ).messages
    )

    record = envelope.payload
    describes_this_run = (
        record.run_id == manifest.run_id
        and record.campaign_spec_digest == manifest.campaign_spec_digest
    )
    checks.record(
        "execution_record.run",
        _PASSED if describes_this_run else _FAILED,
        COMPARISON_EXECUTION_RECORD_INVALID,
        f"the execution record describes run {manifest.run_id}"
        if describes_this_run
        else "the execution record describes a different run or Campaign",
    )

    expected = {
        variant: digest_object(documents.experiments[variant])
        for variant in _VARIANT_ORDER
    }
    same_experiments = all(
        record.side(variant).experiment_manifest_digest == expected[variant]
        for variant in _VARIANT_ORDER
    )
    checks.record(
        "execution_record.experiments",
        _PASSED if same_experiments else _FAILED,
        COMPARISON_EXECUTION_RECORD_INVALID,
        "the execution record accounts for the two experiments this bundle carries"
        if same_experiments
        else (
            "the execution record accounts for different experiments than the "
            "ones this bundle carries"
        ),
    )


def _check_publication(report: UpliftReport, checks: _Checks) -> None:
    """Require the report's two publication fields to hold together.

    A bundle is written before anybody has been asked whether to publish the
    run, and it is never rewritten afterwards, so the status inside it is
    always one of the two a fresh report can carry: nobody has asked, or the
    rights forbid it. A bundle claiming its report was already published would
    be a bundle somebody had edited after the fact.

    Eligibility is the other half and it is recomputed rather than read. The
    flag is a stored field in a signed document, and what it is supposed to be
    follows from two other fields of the same document, so the check is the
    same shape as the aggregate recomputation above it: work it out again from
    the evidence, and compare.
    """
    status = report.statuses.publication
    unpublished = status in (
        PublicationStatus.NOT_REQUESTED,
        PublicationStatus.BLOCKED,
    )
    checks.record(
        "publication.not_requested",
        _PASSED if unpublished else _FAILED,
        PROOF_BUNDLE_INVALID,
        f"nothing in this proof was published: publication is {status.value}"
        if unpublished
        else (
            f"this report's publication status is {status.value}, and a proof "
            "bundle is written before anything could have been published"
        ),
    )

    expected = publication_eligible_for(grade=report.proof_grade, publication=status)
    agrees = report.publication_eligible == expected
    checks.record(
        "publication.eligibility_recomputed",
        _PASSED if agrees else _FAILED,
        PROOF_BUNDLE_INVALID,
        (
            "the report may be published, which is what its grade and its "
            "rights statement together allow"
            if expected
            else "the report may not be published, and does not claim it may"
        )
        if agrees
        else (
            f"the report says publication_eligible is "
            f"{report.publication_eligible}, and its own proof grade and "
            f"publication status make it {expected}"
        ),
    )


def _check_p1_conditions(
    *,
    manifest: LocalProofBundleManifest,
    documents: _Documents,
    receipts: dict[ExperimentVariant, list[EpisodeReceipt]] | None,
    identity_matches: bool,
    checks: _Checks,
) -> None:
    """Re-derive every decisions-0005 section 3.4 condition from these bytes.

    A report that claims ``P1`` and cannot re-establish all six is overclaiming
    and each missing condition is a failure. A report that claims nothing
    records the same conditions as warnings, so a reader can see exactly what a
    development-only bundle is missing rather than being told only that it is
    not P1.
    """
    report = documents.report.payload
    claimed = report.proof_grade == "P1"
    established = {
        P1_ARTIFACT_DIGESTS_VERIFY: not [
            message
            for message in checks.messages
            if message.id.startswith("artifact.") and message.status == _FAILED
        ],
        P1_RECEIPTS_SIGNED: receipts is not None
        and not [
            message
            for message in checks.messages
            if message.id.startswith("receipts/") and message.status == _FAILED
        ],
        P1_REPORT_SIGNED: documents.report.signature is not None
        and not [
            message
            for message in checks.messages
            if message.id.startswith("uplift-report.") and message.status == _FAILED
        ],
        P1_PUBLIC_KEY_PRESENT: identity_matches,
        P1_COMPARISON_CONTROLLED: report.statuses.comparison
        in (ComparisonStatus.CONTROLLED, ComparisonStatus.CONTROLLED_WITH_WARNINGS),
        P1_SCORE_VALID: report.statuses.score.value == "valid",
    }
    for condition, holds in established.items():
        status: VerificationStatus = (
            _PASSED if holds else (_FAILED if claimed else _WARNING)
        )
        checks.record(
            f"p1.{condition}",
            status,
            PROOF_BUNDLE_INVALID,
            _p1_detail(condition, holds=holds, claimed=claimed),
        )
    checks.record(
        "p1.grade",
        _PASSED,
        PROOF_BUNDLE_INVALID,
        (
            f"this report claims proof grade P1, which means {P1_MEANING}"
            if claimed
            else (
                f"this report claims proof grade {report.proof_grade}, which is "
                "not evidence of anything"
            )
        ),
    )
    # The manifest is named here so that a reader of the P1 block can see which
    # run it belongs to without scrolling back to the linkage checks.
    checks.record(
        "p1.run",
        _PASSED,
        PROOF_BUNDLE_INVALID,
        f"these conditions were checked for run {manifest.run_id}",
    )


def _p1_detail(condition: str, *, holds: bool, claimed: bool) -> str:
    """Return the sentence one section 3.4 condition reports itself with."""
    statements = {
        P1_ARTIFACT_DIGESTS_VERIFY: "every referenced artifact digest verifies",
        P1_RECEIPTS_SIGNED: "every EpisodeReceipt travels in a signed envelope",
        P1_REPORT_SIGNED: "the UpliftReport travels in a signed envelope",
        P1_PUBLIC_KEY_PRESENT: "the local public key is included in the bundle",
        P1_COMPARISON_CONTROLLED: "the comparison is controlled",
        P1_SCORE_VALID: "the score status is valid",
    }
    statement = statements[condition]
    if holds:
        return statement
    if claimed:
        return f"this report claims P1 and {statement} does not hold"
    return f"{statement} does not hold, and this report does not claim P1"


# ---------------------------------------------------------------------------
# The five headings a person reads
# ---------------------------------------------------------------------------


def _explain(result: VerificationResult) -> list[VerificationMessage]:
    """Group a verification into the categories spec section 7.12 separates."""
    integrity = _worst(
        result,
        lambda identifier: (
            identifier.startswith(("artifact.", "bundle."))
            or identifier.endswith(
                (".signature", ".payload_digest", ".signature_present")
            )
        ),
    )
    science = _worst(
        result,
        lambda identifier: identifier.startswith(
            ("linkage.", "aggregate.", "receipt_set.")
        ),
    )
    attestation = _worst(
        result, lambda identifier: identifier.startswith(("p1.", "uplift-report."))
    )
    publication = _worst(
        result, lambda identifier: identifier.startswith("publication.")
    )

    return [
        VerificationMessage(
            id="integrity",
            status=integrity,
            code=SIGNATURE_VERIFICATION_FAILED,
            detail=(
                "Cryptographic integrity: every file still matches the digest "
                "it was committed under, and every signature verifies."
                if integrity == _PASSED
                else "Cryptographic integrity: something in this proof no "
                "longer matches what was signed."
            ),
        ),
        VerificationMessage(
            id="comparison_validity",
            status=science,
            code=COMPARISON_INVALID,
            detail=(
                "Scientific comparison: the documents describe one controlled "
                "comparison, and the report's numbers are the ones its own "
                "receipts produce."
                if science == _PASSED
                else "Scientific comparison: these documents do not describe "
                "one consistent comparison."
            ),
        ),
        VerificationMessage(
            id="participant_attestation",
            status=attestation,
            code=LOCAL_IDENTITY_INVALID,
            detail=(
                "Participant attestation: signed by the participant's own "
                f"local key. P1 means {P1_MEANING}."
            ),
        ),
        VerificationMessage(
            id="independent_reproduction",
            status=_WARNING,
            code=PROOF_BUNDLE_INVALID,
            detail=(
                "No independent reproduction: nobody else has run this "
                "comparison, and no platform witnessed it."
            ),
        ),
        VerificationMessage(
            id="public_publication",
            status=publication,
            code=PROOF_BUNDLE_INVALID,
            detail=(
                "Not published: nothing in this proof was uploaded, and a "
                "bundle is written before anybody could have been asked. "
                "Whether it may be published is checked separately."
            ),
        ),
    ]


def _worst(
    result: VerificationResult, selector: Callable[[str], bool]
) -> VerificationStatus:
    """Return the worst status among the checks a selector matches."""
    statuses = [message.status for message in result.messages if selector(message.id)]
    if not statuses:
        return _FAILED
    if _FAILED in statuses:
        return _FAILED
    if _WARNING in statuses:
        return _WARNING
    return _PASSED


# ---------------------------------------------------------------------------
# Reading files without letting one bad file stop the report
# ---------------------------------------------------------------------------


class _Checks:
    """Collects named checks and turns them into one verdict."""

    def __init__(self) -> None:
        self.messages: list[VerificationMessage] = []

    def record(
        self, identifier: str, status: VerificationStatus, code: str, detail: str
    ) -> None:
        """Record one check."""
        self.messages.append(
            VerificationMessage(id=identifier, status=status, code=code, detail=detail)
        )

    def extend(self, messages: Sequence[VerificationMessage]) -> None:
        """Record checks another verifier already ran."""
        self.messages.extend(messages)

    def result(self) -> VerificationResult:
        """Return the collected verdict."""
        failed = [message for message in self.messages if message.status == _FAILED]
        return VerificationResult(verified=not failed, messages=self.messages)


def _load_model[ModelT: BaseModel](
    path: Path, model: type[ModelT], checks: _Checks
) -> ModelT | None:
    """Parse one bundle document from its stored bytes."""
    try:
        raw = path.read_bytes()
    except OSError:
        checks.record(
            f"document.{path.name}",
            _FAILED,
            PROOF_BUNDLE_INVALID,
            f"this bundle has no {path.name}",
        )
        return None
    try:
        return model.model_validate_json(raw)
    except PydanticValidationError as error:
        checks.record(
            f"document.{path.name}",
            _FAILED,
            PROOF_BUNDLE_INVALID,
            f"{path.name} is not a valid {model.__name__}: {error.errors()[0]['msg']}",
        )
        return None


def _load_envelope[ModelT: BaseModel](
    path: Path, model: type[ModelT], checks: _Checks, subject: str
) -> ObjectEnvelope[ModelT] | None:
    """Parse one signed envelope from its stored bytes."""
    try:
        raw = path.read_bytes()
    except OSError:
        checks.record(
            f"{subject}.present",
            _FAILED,
            PROOF_BUNDLE_INVALID,
            f"this proof has no {path.name}",
        )
        return None
    try:
        return ObjectEnvelope[model].model_validate_json(raw)  # type: ignore[valid-type]
    except PydanticValidationError as error:
        checks.record(
            f"{subject}.present",
            _FAILED,
            PROOF_BUNDLE_INVALID,
            f"{path.name} is not a signed {model.__name__}: {error.errors()[0]['msg']}",
        )
        return None


def _load_identity(path: Path, checks: _Checks) -> ExecutorIdentity | None:
    """Parse the public identity a proof travels with."""
    try:
        raw = path.read_bytes()
    except OSError:
        checks.record(
            "identity.present",
            _FAILED,
            LOCAL_IDENTITY_INVALID,
            (
                f"this proof carries no {path.name}, so there is no key to "
                "check its signatures against"
            ),
        )
        return None
    try:
        return ExecutorIdentity.model_validate_json(raw)
    except PydanticValidationError as error:
        checks.record(
            "identity.present",
            _FAILED,
            LOCAL_IDENTITY_INVALID,
            f"{path.name} is not a valid identity: {error.errors()[0]['msg']}",
        )
        return None
