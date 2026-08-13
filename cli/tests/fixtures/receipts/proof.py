"""One complete, signed local proof, built without running anything.

``fixtures.receipts.staged`` puts a real comparison inside a real run; that is
what the integration tests drive. The verifier's own tests need something
different: a proof whose every input is under the test's control, so that one
condition at a time can be broken and the verdict watched.

So this module builds the smallest complete proof there is — a synthetic
Campaign graph from ``fixtures.catalog.build_complete``, two experiment
manifests through the real manifest builder, four receipts constructed
directly, and a report signed by a key made in the test's own temporary home.
Every edge a verifier checks is a real edge; only the *evidence* is synthetic,
which is the one thing the verifier does not look at.

The receipts are built rather than parsed from recorded evidence on purpose: a
test that breaks the pairing needs to write a receipt that could not have come
from a real evaluation, and a builder that refuses to make one is exactly what
:mod:`techtree.receipts.episode` is for.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

from fixtures.catalog.build_complete import (
    build_campaign,
    build_data_policy,
    build_taskset_lock,
    build_validation_evidence,
    build_validation_receipt,
    synthetic_digest,
    synthetic_id,
)
from techtree.canonical import digest_object
from techtree.constants import EPISODE_RECEIPT_SCHEMA_VERSION, UPLIFT_SCHEMA_VERSION
from techtree.identity.models import ExecutorIdentity
from techtree.identity.service import IdentityService
from techtree.identity.store import IdentityStore
from techtree.manifests.builder import build_experiment_configuration, finalize_manifest
from techtree.models.base import ArtifactRef, Digest, ObjectEnvelope
from techtree.models.campaign import SUBJECT_AGENT, CampaignSpec, VariantSchedule
from techtree.models.data_policy import DataPolicy
from techtree.models.episode_receipt import (
    EpisodeReceipt,
    EvidenceStatus,
    NamedTraceReceipt,
    ScoreStatus,
    SubjectRuntimeReceipt,
)
from techtree.models.experiment import (
    ExperimentConfiguration,
    ExperimentManifest,
    ExperimentVariant,
    JsonDifference,
    ManifestComparison,
)
from techtree.models.uplift_report import (
    ComparisonStatus,
    ExecutionStatus,
    PublicationStatus,
    TaskDelta,
    UpliftDecision,
    UpliftReport,
    UpliftStatuses,
)
from techtree.models.validation import TasksetLock, TasksetValidationReceipt
from techtree.paths import paths_from_root
from techtree.receipts.bundle import (
    LocalProofBundleContents,
    write_local_bundle,
)
from techtree.receipts.execution import (
    COMPARISON_EXECUTION_SCHEMA_VERSION,
    NO_COST_SOURCE,
    ComparisonExecutionRecord,
    PairOutcome,
    UsageProvenance,
    VariantExecutionSummary,
    VariantUsage,
    unavailable_cost,
)
from techtree.receipts.set import ReceiptSetManifest, build_receipt_set
from techtree.receipts.uplift import aggregate_primary_result

__all__ = [
    "PROOF_RUN_ID",
    "RecordedProof",
    "execution_record",
    "signed_proof",
    "write_proof",
]

#: The run every proof this module builds belongs to. Fixed, because a proof is
#: checked against itself and a random identifier would make a failure message
#: differ between two runs of the same test.
PROOF_RUN_ID: Final = synthetic_id("run", "proof-run")

_FIXTURE_INSTANT: Final = datetime(2026, 1, 1, tzinfo=UTC)

#: Which committed tasks the synthetic comparison scores. The Campaign commits
#: to more; a proof over a subset would fail the membership check, which is one
#: of the things the tests break deliberately.
_SUBJECT_IMAGE_DIGEST: Final = synthetic_digest("subject-image")


@dataclass(frozen=True)
class RecordedProof:
    """A complete signed proof, and every object that went into it."""

    identity: ExecutorIdentity
    identity_service: IdentityService
    campaign: CampaignSpec
    data_policy: DataPolicy
    taskset_lock: TasksetLock
    validation_receipt: TasksetValidationReceipt
    experiments: dict[ExperimentVariant, ExperimentManifest]
    receipts: dict[ExperimentVariant, list[ObjectEnvelope[EpisodeReceipt]]]
    receipt_sets: dict[ExperimentVariant, ReceiptSetManifest]
    report: ObjectEnvelope[UpliftReport]
    #: Decisions 0007 R6's operational record, when the proof carries one. A
    #: proof without it is complete, which is the point of the field being
    #: optional here as well as in the bundle.
    execution_record: ObjectEnvelope[ComparisonExecutionRecord] | None = None

    @property
    def contents(self) -> LocalProofBundleContents:
        """Return what a bundle would be written from."""
        return LocalProofBundleContents(
            identity=self.identity,
            campaign=self.campaign,
            data_policy=self.data_policy,
            taskset_lock=self.taskset_lock,
            validation_receipt=self.validation_receipt,
            experiments=self.experiments,
            receipt_sets=self.receipt_sets,
            receipts=self.receipts,
            report=self.report,
            execution_record=self.execution_record,
        )


def signed_proof(
    home: Path,
    *,
    proof_grade: str = "P1",
    decision: UpliftDecision = UpliftDecision.ACCEPTED,
    comparison: ComparisonStatus = ComparisonStatus.CONTROLLED_WITH_WARNINGS,
    score: ScoreStatus = ScoreStatus.VALID,
    sign_receipts: bool = True,
    sign_report: bool = True,
    with_execution_record: bool = True,
) -> RecordedProof:
    """Build one complete proof, signed by a key created under ``home``.

    The keyword arguments exist so that a test can produce a proof that is
    correct in every way except one. That is the only way to check that a
    condition is actually being checked rather than being assumed by a
    verifier that never met a counterexample.
    """
    identity_service = IdentityService(IdentityStore(paths_from_root(home)))
    identity = identity_service.ensure()

    data_policy = build_data_policy()
    lock = build_taskset_lock()
    evidence = build_validation_evidence(lock)
    validation_receipt = build_validation_receipt(lock, evidence)
    campaign = build_campaign(
        lock=lock,
        validation_receipt_digest=digest_object(validation_receipt),
        data_policy_digest=digest_object(data_policy),
    )
    campaign_digest = digest_object(campaign)

    skill = ArtifactRef(
        digest=synthetic_digest("skill-archive"),
        media_type="application/zip",
        size=4096,
        relative_path=None,
    )
    experiments = {
        ExperimentVariant.BASELINE: _manifest(
            campaign, campaign_digest, ExperimentVariant.BASELINE, skill=None
        ),
        ExperimentVariant.CANDIDATE: _manifest(
            campaign, campaign_digest, ExperimentVariant.CANDIDATE, skill=skill
        ),
    }

    committed = list(campaign.taskset.membership.ordered_task_hashes)
    receipts = {
        variant: [
            _receipt(
                campaign=campaign,
                campaign_digest=campaign_digest,
                data_policy_digest=digest_object(data_policy),
                experiment=experiments[variant],
                variant=variant,
                position=position,
                task_hash=task_hash,
                reward=_reward(variant, position),
                score=score,
            )
            for position, task_hash in enumerate(committed)
        ]
        for variant in _VARIANTS
    }
    sealed = {
        variant: [
            identity_service.sign_object(receipt)
            if sign_receipts
            else ObjectEnvelope[EpisodeReceipt](
                payload=receipt, payload_digest=digest_object(receipt), signature=None
            )
            for receipt in receipts[variant]
        ]
        for variant in _VARIANTS
    }
    receipt_sets = {
        variant: build_receipt_set(
            run_id=PROOF_RUN_ID,
            variant=variant,
            experiment_manifest_digest=digest_object(experiments[variant]),
            signed_receipts=sealed[variant],
            ordered_task_hashes=committed,
        )
        for variant in _VARIANTS
    }

    report = _report(
        campaign=campaign,
        campaign_digest=campaign_digest,
        data_policy_digest=digest_object(data_policy),
        validation_receipt_digest=digest_object(validation_receipt),
        experiments=experiments,
        committed=committed,
        proof_grade=proof_grade,
        decision=decision,
        comparison=comparison,
        score=score,
    )
    sealed_report = (
        identity_service.sign_object(report)
        if sign_report
        else ObjectEnvelope[UpliftReport](
            payload=report, payload_digest=digest_object(report), signature=None
        )
    )

    return RecordedProof(
        identity=identity,
        identity_service=identity_service,
        campaign=campaign,
        data_policy=data_policy,
        taskset_lock=lock,
        validation_receipt=validation_receipt,
        experiments=experiments,
        receipts=sealed,
        receipt_sets=receipt_sets,
        report=sealed_report,
        execution_record=(
            identity_service.sign_object(
                execution_record(
                    campaign_digest,
                    {
                        variant: digest_object(manifest)
                        for variant, manifest in experiments.items()
                    },
                )
            )
            if with_execution_record
            else None
        ),
    )


def execution_record(
    campaign_digest: Digest,
    experiment_digests: dict[ExperimentVariant, Digest],
    *,
    run_id: str = PROOF_RUN_ID,
) -> ComparisonExecutionRecord:
    """Return the operational record this synthetic comparison would produce.

    Constructed rather than built from an execution, for the same reason the
    receipts here are: the verifier's tests need a record whose every field
    they control. What
    ``tests/unit/test_comparison_execution_record.py`` proves is that the real
    builder produces this shape from real evidence.
    """
    finished = _FIXTURE_INSTANT + timedelta(seconds=90)
    return ComparisonExecutionRecord(
        schema_version=COMPARISON_EXECUTION_SCHEMA_VERSION,
        run_id=run_id,
        campaign_spec_digest=campaign_digest,
        engine_digest=synthetic_digest("engine-bundle"),
        execution_backend="verifiers",
        schedule=VariantSchedule.PARALLEL,
        started_at=_FIXTURE_INSTANT,
        finished_at=finished,
        elapsed_seconds=90.0,
        launch_skew_seconds=0.02,
        first_launched=ExperimentVariant.BASELINE,
        overlap_seconds=88.0,
        campaign_max_concurrent=4,
        outcome=PairOutcome.COMPLETED,
        baseline=_execution_side(
            ExperimentVariant.BASELINE, experiment_digests, finished
        ),
        candidate=_execution_side(
            ExperimentVariant.CANDIDATE, experiment_digests, finished
        ),
    )


def _execution_side(
    variant: ExperimentVariant,
    experiment_digests: dict[ExperimentVariant, Digest],
    finished: datetime,
) -> VariantExecutionSummary:
    """Return one side of the fixture's operational record."""
    return VariantExecutionSummary(
        variant=variant,
        started_at=_FIXTURE_INSTANT,
        finished_at=finished,
        elapsed_seconds=90.0,
        exit_code=0,
        cancelled=False,
        episode_count=2,
        max_concurrent=2,
        usage=VariantUsage(
            provenance=UsageProvenance.NORMALIZED_TRACES,
            model_calls=12,
            input_tokens=2048,
            cached_input_tokens=0,
            output_tokens=256,
            total_tokens=2304,
            traces_total=2,
            traces_with_usage=2,
        ),
        cost=unavailable_cost(NO_COST_SOURCE),
        experiment_manifest_digest=experiment_digests[variant],
        argv_digest=synthetic_digest(f"{variant.value}-argv"),
        normalized_episodes_digest=synthetic_digest(f"{variant.value}-normalized"),
        raw_traces_digest=synthetic_digest(f"{variant.value}-raw-traces"),
        resolved_config_digest=synthetic_digest(f"{variant.value}-resolved-config"),
    )


def write_proof(proof: RecordedProof, run_root: Path) -> Path:
    """Write one proof bundle under a run directory and return the directory."""
    return write_local_bundle(
        run_root=run_root,
        contents=proof.contents,
        identity_service=proof.identity_service,
    )


# ---------------------------------------------------------------------------
# The pieces
# ---------------------------------------------------------------------------

_VARIANTS: Final[tuple[ExperimentVariant, ...]] = (
    ExperimentVariant.BASELINE,
    ExperimentVariant.CANDIDATE,
)


def _reward(variant: ExperimentVariant, position: int) -> float:
    """Return the reward one side recorded for one task.

    The candidate improves on half the tasks, regresses on one, and ties on the
    rest, so a proof built from this has something of every kind in it.
    """
    if variant is ExperimentVariant.BASELINE:
        return 1.0 if position % 4 == 0 else 0.0
    if position == 0:
        return 0.0
    return 1.0 if position % 2 == 0 else 0.0


def _manifest(
    campaign: CampaignSpec,
    campaign_digest: Digest,
    variant: ExperimentVariant,
    *,
    skill: ArtifactRef | None,
) -> ExperimentManifest:
    """Build one variant through the same finalizer the run service uses."""
    configuration = build_experiment_configuration(campaign)
    if skill is not None:
        configuration = _with_skill(configuration, skill)
    return finalize_manifest(
        campaign=campaign,
        campaign_digest=campaign_digest,
        public_context=None,
        variant=variant,
        configuration=configuration,
        created_at=_FIXTURE_INSTANT,
        manifest_id=None,
    )


def _with_skill(
    configuration: ExperimentConfiguration, skill: ArtifactRef
) -> ExperimentConfiguration:
    """Return the same configuration with the candidate Skill mounted."""
    subject = configuration.agents[SUBJECT_AGENT]
    return ExperimentConfiguration(
        **{
            **dict(configuration),
            "agents": {
                **configuration.agents,
                SUBJECT_AGENT: subject.model_copy(
                    update={
                        "harness": subject.harness.model_copy(
                            update={"skills": [skill]}
                        )
                    }
                ),
            },
        }
    )


def _receipt(
    *,
    campaign: CampaignSpec,
    campaign_digest: Digest,
    data_policy_digest: Digest,
    experiment: ExperimentManifest,
    variant: ExperimentVariant,
    position: int,
    task_hash: Digest,
    reward: float,
    score: ScoreStatus,
) -> EpisodeReceipt:
    """Return one receipt of the shape a real evaluation produces."""
    label = f"{variant.value}/{position}"
    return EpisodeReceipt(
        schema_version=EPISODE_RECEIPT_SCHEMA_VERSION,
        id=synthetic_id("receipt", f"receipt/{label}"),
        run_id=PROOF_RUN_ID,
        campaign_spec_digest=campaign_digest,
        program_ref=None,
        public_context=None,
        data_policy_digest=data_policy_digest,
        outcome_contract_digest=None,
        evaluation_backend=campaign.evaluation_backend,
        subject_runtime=SubjectRuntimeReceipt(
            kind="docker",
            resolved_image_digest=_SUBJECT_IMAGE_DIGEST,
            platform="linux/arm64",
        ),
        variant=variant,
        experiment_manifest_digest=digest_object(experiment),
        episode_id=synthetic_id("episode", f"episode/{label}"),
        episode_digest=synthetic_digest(f"raw-episode/{label}"),
        task_hash=task_hash,
        named_traces={
            SUBJECT_AGENT: [
                NamedTraceReceipt(
                    role=SUBJECT_AGENT,
                    trace_id=synthetic_id("trace", f"trace/{label}"),
                    trace_digest=synthetic_digest(f"raw-trace/{label}"),
                    task_hash=task_hash,
                    rewards={campaign.scoring.primary_reward: reward},
                    metrics={},
                    ok=True,
                )
            ]
        },
        score_status=score,
        evidence_status=EvidenceStatus.COMPLETE,
        execution_backend="verifiers",
        artifacts=[
            ArtifactRef(
                digest=synthetic_digest(f"normalized-episodes/{variant.value}"),
                media_type="application/x-ndjson",
                size=65536,
                relative_path=None,
            )
        ],
    )


def _report(
    *,
    campaign: CampaignSpec,
    campaign_digest: Digest,
    data_policy_digest: Digest,
    validation_receipt_digest: Digest,
    experiments: dict[ExperimentVariant, ExperimentManifest],
    committed: list[Digest],
    proof_grade: str,
    decision: UpliftDecision,
    comparison: ComparisonStatus,
    score: ScoreStatus,
) -> UpliftReport:
    """Return the report these receipts produce, aggregated by the real code."""
    deltas = [
        TaskDelta(
            task_hash=task_hash,
            baseline_reward=_reward(ExperimentVariant.BASELINE, position),
            candidate_reward=_reward(ExperimentVariant.CANDIDATE, position),
            delta=(
                _reward(ExperimentVariant.CANDIDATE, position)
                - _reward(ExperimentVariant.BASELINE, position)
            ),
        )
        for position, task_hash in enumerate(committed)
    ]
    baseline = experiments[ExperimentVariant.BASELINE]
    candidate = experiments[ExperimentVariant.CANDIDATE]
    return UpliftReport(
        schema_version=UPLIFT_SCHEMA_VERSION,
        id=synthetic_id("uplift", "proof-report"),
        run_id=PROOF_RUN_ID,
        campaign_spec_digest=campaign_digest,
        program_ref=None,
        public_context=None,
        data_policy_digest=data_policy_digest,
        outcome_contract_digest=None,
        evaluation_backend=campaign.evaluation_backend,
        taskset_validation_receipt_digest=validation_receipt_digest,
        baseline_manifest_digest=digest_object(baseline),
        candidate_manifest_digest=digest_object(candidate),
        statuses=UpliftStatuses(
            execution=ExecutionStatus.COMPLETED,
            score=score,
            evidence=EvidenceStatus.COMPLETE,
            comparison=comparison,
            publication=PublicationStatus.NOT_REQUESTED,
        ),
        manifest_comparison=ManifestComparison(
            baseline_configuration_digest=baseline.configuration_digest,
            candidate_configuration_digest=candidate.configuration_digest,
            differences=[
                JsonDifference(
                    pointer="/agents/subject/harness/skills/0",
                    baseline=None,
                    candidate=synthetic_digest("skill-archive"),
                )
            ],
            allowed_differences=["/agents/subject/harness/skills"],
            controlled=True,
            violations=[],
        ),
        primary_result=aggregate_primary_result(
            deltas, campaign.scoring.primary_reward
        ),
        task_deltas=deltas,
        decision=decision,
        proof_grade=proof_grade,  # type: ignore[arg-type]
        publication_eligible=False,
        created_at=_FIXTURE_INSTANT,
    )


def replace_report(proof: RecordedProof, report: UpliftReport) -> RecordedProof:
    """Return the same proof around a different report, signed by the same key."""
    return replace(proof, report=proof.identity_service.sign_object(report))
