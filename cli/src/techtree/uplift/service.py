"""The stage that closes a real run. Spec sections 7.9-7.10, 7.20.

The real executor stops the moment the evidence is complete: two variants
executed, their raw output retained, the engine's own normalized projection
written beside it, and a
:class:`~techtree.verifiers.models.RealExecutionResult` handed back. Spec
section 6.22 fixes that boundary deliberately — WP6 does not invent final
uplift — and until this module existed a real run therefore could not finish at
all. It is what turns the evidence into the run's result.

Everything it does is a pure function of files the run already owns, so it
spends nothing, starts nothing, and reaches nothing outside the run directory:

1. ``building_receipts`` — one receipt per committed task per variant, written
   into the run's receipt tree, signed under the local executor identity, and
   committed to by an ordered receipt-set manifest per variant.
2. ``verifying_comparison`` — one observed fingerprint per variant, taken from
   the traces and the configuration the engine resolved, checked against the
   manifests and against each other.
3. ``building_report`` — the paired rewards, the aggregate, the report, its
   signature, and the portable proof bundle the report is verified from before
   it is written through the run store, so that the journal announces the
   digest of a report whose proof already checked out.

Four choices are worth stating.

*The run's own copies are the only inputs.* The Campaign, the two manifests and
the committed membership come from ``inputs/``, which the artifact store
verified against the run's immutable request; the evidence comes from
``verifiers/<variant>/run/``. Nothing is re-resolved from a draft, a catalog or
a settings file, so a run's result cannot change because something outside it
did.

*The receipts are written before the comparison is checked.* They are the
expensive evaluation's only durable scientific record, and a comparison that
fails is exactly the case where an operator most needs to read them.

*The proof is verified before the result is recorded.* Signing is not a
formality performed on the way out: the bundle is written, verified offline by
the same code a stranger would run, and only then does the report become the
run's result. A run whose proof does not check out fails with its evidence
intact rather than completing with a report nobody could verify.

*It records the run's completion itself.* The fake executor writes its own
result and appends its own completion event, and a real run needs the same two
acts performed by whoever built the report. Doing it here keeps
:func:`techtree.worker.execute.execute_run`'s contract — the report it verifies
against the journal is the report that was recorded — identical for both
executors.

Spec section 7.20's ``UpliftService``, which builds sanitized improvement
context and prepares Skill-replacement drafts, is WP7d's and is a different
object; it will live beside this one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import digest_object
from techtree.errors import ValidationError, VerificationError
from techtree.identity.models import ExecutorIdentity
from techtree.identity.service import IdentityService
from techtree.models.base import ObjectEnvelope
from techtree.models.episode_receipt import EpisodeReceipt
from techtree.models.experiment import ExperimentVariant
from techtree.models.run import RunPhase, RunRequest
from techtree.models.uplift_report import UpliftReport
from techtree.models.validation import TasksetLock
from techtree.paths import TechtreePaths
from techtree.receipts.bundle import (
    PROOF_BUNDLE_INVALID,
    LocalProofBundleContents,
    ReferencedObject,
    assess_local_attestation,
    write_local_bundle,
)
from techtree.receipts.compare import (
    COMPARISON_INVALID,
    ObservedVariant,
    RealComparisonResult,
    compare_real_variants,
    observe_variant,
)
from techtree.receipts.episode import build_variant_receipts, experiment_variant_of
from techtree.receipts.observed import read_resolved_config
from techtree.receipts.set import (
    ReceiptSetManifest,
    build_receipt_set,
    receipt_set_path,
    write_receipt_set,
)
from techtree.receipts.uplift import (
    aggregate_primary_result,
    build_uplift_report,
    pair_task_rewards,
    summarize_receipts,
)
from techtree.receipts.verify import verify_local_bundle
from techtree.runs.artifacts import RunArtifactStore, RunInputBundle
from techtree.runs.events import DETAIL_RESULT_DIGEST, RUN_COMPLETED
from techtree.runs.executor import raise_if_cancel_requested
from techtree.runs.real import TASKSET_LOCK_FILENAME
from techtree.runs.store import RunStore
from techtree.verifiers.models import (
    RealExecutionResult,
    RunPaths,
    VariantExecutionResult,
    VariantName,
)
from techtree.verifiers.outputs import CONFIG_FILENAME

__all__ = [
    "REAL_REPORT_STAGE_FAILED",
    "RealUpliftReportService",
    "VariantReceipts",
]

#: Stable error code for an input this stage cannot read. The scientific
#: refusals report through spec section 15's own codes, raised by the modules
#: that own them.
REAL_REPORT_STAGE_FAILED: Final = "real_report_stage_failed"

#: Both sides, always in comparison order.
_VARIANT_ORDER: Final[tuple[VariantName, ...]] = (
    VariantName.BASELINE,
    VariantName.CANDIDATE,
)


@dataclass(frozen=True)
class VariantReceipts:
    """One variant's signed receipts, its commitment over them, and what it ran."""

    receipts: list[EpisodeReceipt]
    signed_receipts: list[ObjectEnvelope[EpisodeReceipt]]
    receipt_set: ReceiptSetManifest
    observed: ObservedVariant


class RealUpliftReportService:
    """Completes a real run by turning its evidence into a signed UpliftReport."""

    def __init__(
        self,
        *,
        paths: TechtreePaths,
        run_store: RunStore,
        artifact_store: RunArtifactStore,
        identity: IdentityService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._paths = paths
        self._run_store = run_store
        self._artifacts = artifact_store
        self._identity = identity
        self._clock = clock or _utc_now

    def complete(
        self, *, request: RunRequest, execution: RealExecutionResult
    ) -> UpliftReport:
        """Build, check, aggregate, sign, prove and record this run's result."""
        run_id = request.run_id
        raise_if_cancel_requested(self._run_store, run_id)

        inputs = self._artifacts.load_inputs(run_id, request)
        run_paths = RunPaths.for_run(self._paths, run_id)
        lock = self._taskset_lock(run_paths, inputs)
        # Before anything is sealed, so that a machine which cannot sign says so
        # while its evidence is still the only thing at stake.
        identity = self._identity.ensure()

        self._run_store.append(run_id, phase=RunPhase.BUILDING_RECEIPTS)
        sides = {
            variant: self._build_variant(
                request=request,
                inputs=inputs,
                run_paths=run_paths,
                lock=lock,
                variant=variant,
                result=_side(execution, variant),
            )
            for variant in _VARIANT_ORDER
        }
        baseline = sides[VariantName.BASELINE]
        candidate = sides[VariantName.CANDIDATE]

        self._run_store.append(run_id, phase=RunPhase.VERIFYING_COMPARISON)
        comparison = self._compare(
            inputs=inputs, lock=lock, execution=execution, sides=sides
        )

        self._run_store.append(run_id, phase=RunPhase.BUILDING_REPORT)
        report = self._report(
            request=request,
            inputs=inputs,
            lock=lock,
            identity=identity,
            comparison=comparison,
            baseline=baseline,
            candidate=candidate,
        )
        self._prove(
            request=request,
            inputs=inputs,
            lock=lock,
            identity=identity,
            report=report,
            baseline=baseline,
            candidate=candidate,
        )

        self._run_store.write_result(run_id, report)
        self._run_store.append(
            run_id,
            phase=RunPhase.COMPLETED,
            kind=RUN_COMPLETED,
            details={DETAIL_RESULT_DIGEST: digest_object(report)},
        )
        return report

    # -- receipts -----------------------------------------------------------

    def _build_variant(
        self,
        *,
        request: RunRequest,
        inputs: RunInputBundle,
        run_paths: RunPaths,
        lock: TasksetLock,
        variant: VariantName,
        result: VariantExecutionResult,
    ) -> VariantReceipts:
        """Build, persist and commit to one variant's receipts."""
        experiment = (
            inputs.baseline if variant is VariantName.BASELINE else inputs.candidate
        )
        campaign = inputs.campaign
        receipts = build_variant_receipts(
            run_request=request,
            variant=variant,
            experiment=experiment,
            result=result,
            evaluation_backend=campaign.evaluation_backend,
            ordered_task_hashes=lock.ordered_task_hashes,
            primary_reward=campaign.scoring.primary_reward,
            evidence=campaign.evidence,
        )
        for position, receipt in enumerate(receipts):
            self._artifacts.write_episode_receipt(
                request.run_id, position=position, receipt=receipt
            )

        # Signed here, at the moment the receipts exist and before anything is
        # committed to them: the receipt-set manifest commits to the digest of
        # each receipt's payload, which signing does not move, so the
        # commitment and the signature are two independent seals over the same
        # bytes rather than one wrapped in the other.
        envelopes = [self._identity.sign_object(receipt) for receipt in receipts]
        protocol_variant = experiment_variant_of(variant)
        receipt_set = build_receipt_set(
            run_id=request.run_id,
            variant=protocol_variant,
            experiment_manifest_digest=result.experiment_manifest_digest,
            signed_receipts=envelopes,
            ordered_task_hashes=lock.ordered_task_hashes,
        )
        write_receipt_set(
            receipt_set, receipt_set_path(run_paths.root, protocol_variant)
        )

        return VariantReceipts(
            receipts=receipts,
            signed_receipts=envelopes,
            receipt_set=receipt_set,
            observed=observe_variant(
                result=result,
                resolved_config=read_resolved_config(
                    run_paths.variant_output_dir(variant) / CONFIG_FILENAME
                ),
            ),
        )

    # -- comparison ---------------------------------------------------------

    def _compare(
        self,
        *,
        inputs: RunInputBundle,
        lock: TasksetLock,
        execution: RealExecutionResult,
        sides: dict[VariantName, VariantReceipts],
    ) -> RealComparisonResult:
        """Check that the two executions were one experiment."""
        return compare_real_variants(
            campaign=inputs.campaign,
            baseline_manifest=inputs.baseline,
            candidate_manifest=inputs.candidate,
            prepared_manifest_comparison=inputs.comparison,
            baseline_receipts=sides[VariantName.BASELINE].receipts,
            candidate_receipts=sides[VariantName.CANDIDATE].receipts,
            taskset_lock=lock,
            baseline_observed=sides[VariantName.BASELINE].observed,
            candidate_observed=sides[VariantName.CANDIDATE].observed,
            schedule=execution.schedule,
        )

    # -- the report ---------------------------------------------------------

    def _report(
        self,
        *,
        request: RunRequest,
        inputs: RunInputBundle,
        lock: TasksetLock,
        identity: ExecutorIdentity,
        comparison: RealComparisonResult,
        baseline: VariantReceipts,
        candidate: VariantReceipts,
    ) -> UpliftReport:
        """Aggregate the paired rewards and construct the report."""
        campaign = inputs.campaign
        deltas = pair_task_rewards(
            baseline_receipts=baseline.receipts,
            candidate_receipts=candidate.receipts,
            ordered_task_hashes=comparison.ordered_task_hashes,
            reward_name=campaign.scoring.primary_reward,
        )
        primary = aggregate_primary_result(deltas, campaign.scoring.primary_reward)
        score, evidence = summarize_receipts(baseline.receipts, candidate.receipts)

        return build_uplift_report(
            run_request=request,
            campaign=campaign,
            # The Campaign's own commitment. Every validation source in this
            # build is required to have validated against exactly this receipt
            # before a single episode is scored on the taskset, so it is the
            # receipt this run was validated under and not merely a reference.
            taskset_validation_receipt_digest=(
                campaign.taskset.validation_receipt_digest
            ),
            baseline_manifest=inputs.baseline,
            candidate_manifest=inputs.candidate,
            baseline_receipt_set=baseline.receipt_set,
            candidate_receipt_set=candidate.receipt_set,
            comparison=comparison,
            task_deltas=deltas,
            primary=primary,
            score=score,
            evidence=evidence,
            # The one argument that decides the grade, and it is decided by the
            # decisions-0005 section 3.4 conditions rather than by the presence
            # of a key. Every condition is checked; any failure withholds the
            # verdict instead of claiming a grade this run did not earn.
            attestation=assess_local_attestation(
                identity=identity,
                identity_self_check=self._identity.store.verify_pair(),
                referenced_objects=self._referenced_objects(
                    request=request, inputs=inputs, lock=lock
                ),
                signed_receipts={
                    ExperimentVariant.BASELINE: baseline.signed_receipts,
                    ExperimentVariant.CANDIDATE: candidate.signed_receipts,
                },
                comparison=comparison.status,
                score=score,
            ).attestation,
            created_at=self._clock(),
        )

    # -- the proof ----------------------------------------------------------

    def _prove(
        self,
        *,
        request: RunRequest,
        inputs: RunInputBundle,
        lock: TasksetLock,
        identity: ExecutorIdentity,
        report: UpliftReport,
        baseline: VariantReceipts,
        candidate: VariantReceipts,
    ) -> Path:
        """Sign the report, write the portable proof, and verify it offline.

        The bundle is verified before the report is recorded, from the bytes
        just written, with the same verifier a stranger would use. That is what
        turns "the report says P1" into "the conditions P1 names hold in this
        directory": a bundle that does not verify fails the run, and no report
        claiming a grade it cannot support becomes a result.
        """
        signed_report = self._identity.sign_object(report)
        run_root = self._paths.run_dir(request.run_id)
        directory = write_local_bundle(
            run_root=run_root,
            contents=LocalProofBundleContents(
                identity=identity,
                campaign=inputs.campaign,
                data_policy=inputs.resolved_climb.data_policy,
                taskset_lock=lock,
                validation_receipt=inputs.resolved_climb.publisher_validation,
                experiments={
                    ExperimentVariant.BASELINE: inputs.baseline,
                    ExperimentVariant.CANDIDATE: inputs.candidate,
                },
                receipt_sets={
                    ExperimentVariant.BASELINE: baseline.receipt_set,
                    ExperimentVariant.CANDIDATE: candidate.receipt_set,
                },
                receipts={
                    ExperimentVariant.BASELINE: baseline.signed_receipts,
                    ExperimentVariant.CANDIDATE: candidate.signed_receipts,
                },
                report=signed_report,
            ),
            identity_service=self._identity,
        )

        verification = verify_local_bundle(directory)
        if verification.verified:
            return directory
        raise VerificationError(
            "this run's local proof does not verify from the bytes it just "
            "wrote, so its report is not recorded as a result",
            code=PROOF_BUNDLE_INVALID,
            details={
                "run_id": request.run_id,
                "proof_grade": report.proof_grade,
                "failed_checks": [message.id for message in verification.failures],
            },
        )

    def _referenced_objects(
        self, *, request: RunRequest, inputs: RunInputBundle, lock: TasksetLock
    ) -> list[ReferencedObject]:
        """Return every object this report cites, with the digest it cites it under.

        Section 3.4's first condition is that all referenced artifact digests
        verify, and this is the list: each object recomputed from itself and
        compared against the digest some *other* document names it by, so no
        value is ever checked against itself.
        """
        campaign = inputs.campaign
        publisher_validation = inputs.resolved_climb.publisher_validation
        return [
            ReferencedObject("campaign", campaign, request.campaign_spec_digest),
            ReferencedObject(
                "data-policy",
                inputs.resolved_climb.data_policy,
                campaign.data_policy_digest,
            ),
            ReferencedObject(
                "taskset-validation-receipt",
                publisher_validation,
                campaign.taskset.validation_receipt_digest,
            ),
            ReferencedObject(
                "taskset-lock", lock, publisher_validation.taskset_lock_digest
            ),
            ReferencedObject(
                "baseline-experiment",
                inputs.baseline,
                request.baseline_manifest_digest,
            ),
            ReferencedObject(
                "candidate-experiment",
                inputs.candidate,
                request.candidate_manifest_digest,
            ),
        ]

    # -- inputs -------------------------------------------------------------

    def _taskset_lock(self, run_paths: RunPaths, inputs: RunInputBundle) -> TasksetLock:
        """Read the run's own copy of the membership its episodes were joined on.

        Written by the executor before anything was compiled, from the
        validation this run was given, and read back here rather than re-derived
        so that the receipts are ordered by the same list the normalizer used.
        """
        path = run_paths.inputs_dir / TASKSET_LOCK_FILENAME
        try:
            lock = TasksetLock.model_validate_json(path.read_bytes())
        except OSError as error:
            raise ValidationError(
                "this run recorded no validated taskset lock, so its episodes "
                "cannot be ordered by the membership they were scored under",
                code=REAL_REPORT_STAGE_FAILED,
                details={"run_id": inputs.request.run_id, "path": str(path)},
            ) from error
        except PydanticValidationError as error:
            raise ValidationError(
                f"this run's taskset lock cannot be read: {error.errors()[0]['msg']}",
                code=REAL_REPORT_STAGE_FAILED,
                details={"run_id": inputs.request.run_id, "path": str(path)},
            ) from error

        committed = list(inputs.campaign.taskset.membership.ordered_task_hashes)
        if list(lock.ordered_task_hashes) != committed:
            raise ValidationError(
                "this run's taskset lock does not hold the tasks its Campaign "
                "commits to",
                code=COMPARISON_INVALID,
                details={
                    "run_id": inputs.request.run_id,
                    "locked": len(lock.ordered_task_hashes),
                    "committed": len(committed),
                },
            )
        return lock


def _side(
    execution: RealExecutionResult, variant: VariantName
) -> VariantExecutionResult:
    """Return one variant's half of the execution result."""
    return (
        execution.baseline if variant is VariantName.BASELINE else execution.candidate
    )


def _utc_now() -> datetime:
    """Return the current instant in UTC."""
    return datetime.now(UTC)
