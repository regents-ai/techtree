"""Regenerate the protocol golden fixtures. Spec section 24.4.

A golden is one representative, fully valid instance of a protocol object,
written from typed Python rather than typed by hand. Their job is to fail
loudly: any change to a model shows up here as a diff in a file a reviewer can
read, next to the field that moved.

Everything in this module is fixed. Identifiers are derived from labels, the
timestamp is a constant, and no value is read from the clock, the environment,
or the host. That is what lets ``make generated-check`` regenerate the tree in
a throwaway copy of the repository and compare it byte for byte.

Where the fixture graph has a real edge — a Climb pointing at a Campaign, a
Campaign pointing at its DataPolicy — the digest is computed from the object it
refers to, so the goldens are a consistent graph and not a set of unrelated
documents. Digests that would come from outside the protocol (an engine bundle,
a skill archive, a Docker image) are derived from a label instead; they are
fixture values, and nothing here pretends otherwise.

These files are development fixtures. They are not the packaged catalog, which
is generated separately and ships empty until the real generation chain exists
(decisions document 0003 A2).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel

from techtree.canonical import digest_object, sha256_digest_bytes, to_json_value
from techtree.constants import (
    CAMPAIGN_SCHEMA_VERSION,
    CLI_SCHEMA_VERSION,
    CLIMB_SCHEMA_VERSION,
    DATA_POLICY_SCHEMA_VERSION,
    EPISODE_RECEIPT_SCHEMA_VERSION,
    EVALUATION_BACKEND_SCHEMA_VERSION,
    EXPERIMENT_SCHEMA_VERSION,
    PINNED_VERIFIERS_REVISION,
    SKILL_SCHEMA_VERSION,
    TASKSET_LOCK_SCHEMA_VERSION,
    TASKSET_VALIDATION_SCHEMA_VERSION,
    UPLIFT_SCHEMA_VERSION,
)
from techtree.crypto import (
    load_private_key,
    public_key_bytes,
    public_key_to_base64,
    sign_digest,
)
from techtree.identity.models import (
    ExecutorIdentity,
    VerificationMessage,
    VerificationResult,
)
from techtree.models.base import ArtifactRef, Digest, ObjectEnvelope
from techtree.models.campaign import (
    SKILL_MUTATION_POINTER,
    SUBJECT_AGENT,
    AgentSpec,
    BudgetSpec,
    CampaignContext,
    CampaignMetadata,
    CampaignSpec,
    CampaignTaskset,
    EnvironmentSpec,
    EvidenceRequirements,
    ExecutionSpec,
    HarnessSpec,
    ModelSpec,
    MutationContract,
    MutationKind,
    PackageRef,
    PublicContext,
    RuntimeSpec,
    SamplingSpec,
    ScoringSpec,
    TaskMembershipCommitment,
    TaskSelection,
    TasksetRef,
    VariantSchedule,
)
from techtree.models.catalog import (
    ClimbSummary,
    CompatibilityIssue,
    CompatibilityResult,
    DataPolicySummary,
    EngineCompatibilityStatus,
)
from techtree.models.cli import CliEnvelope, CliMessage, MessageLevel, NextAction
from techtree.models.climb import (
    CandidateConstraints,
    CandidatePolicy,
    ClimbManifest,
    ClimbMetadata,
    LeaderboardPolicy,
    PublicationPolicy,
)
from techtree.models.data_policy import (
    CandidateSkillPolicy,
    DataOwner,
    DataPolicy,
    DerivedArtifactPolicy,
    RawEpisodePolicy,
    RevocationPolicy,
)
from techtree.models.episode_receipt import (
    EpisodeReceipt,
    EvidenceStatus,
    NamedTraceReceipt,
    ScoreStatus,
    SubjectRuntimeReceipt,
)
from techtree.models.evaluation_backend import (
    AttestationKind,
    EvaluationBackendKind,
    EvaluationBackendSpec,
)
from techtree.models.experiment import (
    ExperimentConfiguration,
    ExperimentManifest,
    ExperimentVariant,
    JsonDifference,
    ManifestComparison,
)
from techtree.models.skill import SkillArtifact, SkillFile
from techtree.models.uplift_report import (
    ComparisonStatus,
    ExecutionStatus,
    PrimaryUpliftResult,
    PublicationStatus,
    TaskDelta,
    UpliftDecision,
    UpliftReport,
    UpliftStatuses,
)
from techtree.models.validation import (
    TasksetLock,
    TasksetValidationReceipt,
    UpstreamValidationSummary,
    ValidationCheck,
    ValidationMethod,
)
from techtree.presentation.build import build_uplift_presentation
from techtree.presentation.models import UpliftPresentationPayload
from techtree.receipts.uplift import aggregate_primary_result
from techtree.tasksets.membership import membership_digest
from techtree.uplift.context import SkillImprovementContext
from techtree.uplift.context import (
    build_improvement_context as build_improvement_context_for,
)

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

#: One fixed instant for every fixture. A golden that read the clock would
#: differ from itself on the next regeneration.
FIXED_TIME = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

#: The development fixtures named by decisions document 0001.
CAMPAIGN_REFERENCE = "procedure-transfer-dev-campaign@1"
CLIMB_SLUG = "procedure-transfer-dev"
TASKSET_ID = "procedure-transfer-v1"
TASK_COUNT = 20


def fixture_digest(label: str) -> Digest:
    """Return a fixed digest standing in for a value produced outside v0.1.

    Engine bundles, skill archives, and container images are digested by the
    subsystems that build them. A golden needs a stable placeholder for those,
    and deriving it from a label keeps it both fixed and traceable to what it
    represents.
    """
    return sha256_digest_bytes(f"techtree-golden/{label}".encode())


def fixture_id(prefix: str, label: str) -> str:
    """Return a fixed prefixed identifier for a fixture object."""
    _, _, hexadecimal = fixture_digest(label).partition(":")
    return f"{prefix}_{hexadecimal[:32]}"


# ---------------------------------------------------------------------------
# The fixture graph
# ---------------------------------------------------------------------------


def build_data_policy() -> DataPolicy:
    """Return the development rights policy from spec section 11.4."""
    return DataPolicy(
        schema_version=DATA_POLICY_SCHEMA_VERSION,
        id=fixture_id("policy", "data-policy"),
        version=1,
        owner=DataOwner(kind="participant", account_ref=None),
        raw_episodes=RawEpisodePolicy(
            local_retention="allowed",
            server_upload="prohibited",
            public_release="prohibited",
            reproduction_access="consent_required",
            training_use="prohibited",
        ),
        derived_artifacts=DerivedArtifactPolicy(
            aggregate_scores="public",
            uplift_report="public",
            redacted_trace_projection="public",
            anonymized_product_analytics="allowed",
        ),
        candidate_skill=CandidateSkillPolicy(
            ownership="participant",
            public_release="required_for_climb",
            training_use="prohibited",
        ),
        revocation=RevocationPolicy(
            future_use_revocable=True,
            immutable_published_proofs_remain=True,
        ),
    )


def ordered_task_hashes() -> list[Digest]:
    """Return the fixed committed membership of the fixture taskset."""
    return [fixture_digest(f"task/{position}") for position in range(TASK_COUNT)]


def build_taskset_lock() -> TasksetLock:
    """Return the publisher lock the fixture Campaign is committed to."""
    hashes = ordered_task_hashes()
    return TasksetLock(
        schema_version=TASKSET_LOCK_SCHEMA_VERSION,
        taskset_ref=build_taskset_ref(),
        engine_digest=fixture_digest("engine-bundle"),
        resolved_package_digest=fixture_digest("reference-package"),
        ordered_task_hashes=hashes,
        membership_digest=membership_digest(hashes),
        task_count=TASK_COUNT,
    )


def build_validation_method() -> ValidationMethod:
    """Return how the fixture taskset was validated."""
    return ValidationMethod(
        kind="verifiers_validate",
        mode="all",
        runtime="subprocess",
        validator_revision=PINNED_VERIFIERS_REVISION,
    )


def build_validation_receipt(lock_digest: Digest) -> TasksetValidationReceipt:
    """Return the deterministic publisher receipt. Decisions 0003 A1."""
    return TasksetValidationReceipt(
        schema_version=TASKSET_VALIDATION_SCHEMA_VERSION,
        taskset_lock_digest=lock_digest,
        engine_digest=fixture_digest("engine-bundle"),
        method=build_validation_method(),
        status="valid",
        upstream_summary=UpstreamValidationSummary(
            mode="all",
            total=TASK_COUNT,
            recorded=TASK_COUNT,
            valid=TASK_COUNT,
            invalid=0,
            error=0,
            timeout=0,
            missing=0,
            valid_rate=1.0,
        ),
        checks=[
            ValidationCheck(
                id="upstream_gold",
                status="passed",
                detail=f"{TASK_COUNT} of {TASK_COUNT} gold answers validated",
            ),
            ValidationCheck(
                id="upstream_setup",
                status="passed",
                detail=f"{TASK_COUNT} of {TASK_COUNT} task setups validated",
            ),
            ValidationCheck(
                id="membership_repeatability",
                status="passed",
                detail="two inspections produced the same ordered task hashes",
            ),
            ValidationCheck(
                id="task_hash_uniqueness",
                status="passed",
                detail="no task hash appears twice",
            ),
            ValidationCheck(
                id="committed_membership_match",
                status="passed",
                detail="the recomputed membership digest matches the commitment",
            ),
            ValidationCheck(
                id="expected_task_count",
                status="passed",
                detail=f"the taskset yielded the expected {TASK_COUNT} tasks",
            ),
        ],
        normalized_evidence=ArtifactRef(
            digest=fixture_digest("validation-evidence"),
            media_type="application/json",
            size=8192,
            relative_path="validation-evidence.json",
        ),
    )


def build_taskset_ref() -> TasksetRef:
    """Return the reference to the embedded development taskset."""
    return TasksetRef(
        kind="verifiers",
        id=TASKSET_ID,
        package=PackageRef(
            kind="embedded",
            name=TASKSET_ID,
            revision="1",
            digest=fixture_digest("reference-package"),
        ),
        config={"num_tasks": TASK_COUNT},
    )


def build_subject_agent(skills: list[ArtifactRef]) -> AgentSpec:
    """Return the frozen development subject from decisions document 0001."""
    return AgentSpec(
        model=ModelSpec(
            provider="development",
            model_id="development-placeholder",
            revision=None,
            credential_env="TECHTREE_MODEL_API_KEY",
        ),
        sampling=SamplingSpec(temperature=0.0, max_tokens=512),
        harness=HarnessSpec(
            id="hermes-agent",
            version="0.19.0",
            use_bundled_skill=False,
            skills=skills,
        ),
        runtime=RuntimeSpec(
            type="docker",
            image="techtree-development-placeholder:not-executed",
            supported_platforms=["linux/amd64", "linux/arm64"],
            cpu=2.0,
            memory_gb=4.0,
            network_policy="restricted",
        ),
        trainable=False,
    )


def build_mutation_contract() -> MutationContract:
    """Return the single permitted difference between the two variants."""
    return MutationContract(
        kind=MutationKind.SKILL_INSERTION,
        target_agent="subject",
        allowed_differences=[SKILL_MUTATION_POINTER],
        minimum_skills=1,
        maximum_skills=1,
    )


def build_evaluation_backend() -> EvaluationBackendSpec:
    """Return the only backend WP0–WP5 permits."""
    return EvaluationBackendSpec(
        schema_version=EVALUATION_BACKEND_SCHEMA_VERSION,
        kind=EvaluationBackendKind.LOCAL_TECHTREE,
        attestation=AttestationKind.PARTICIPANT,
        workspace_ref=None,
        provider_run_ref=None,
        executor_identity=None,
    )


def build_campaign_taskset(receipt_digest: Digest) -> CampaignTaskset:
    """Return the Campaign's committed view of the taskset."""
    hashes = ordered_task_hashes()
    return CampaignTaskset(
        ref=build_taskset_ref(),
        selection=TaskSelection(
            num_tasks=TASK_COUNT,
            num_rollouts=1,
            shuffle=False,
        ),
        membership=TaskMembershipCommitment(
            mode="committed",
            ordered_task_hashes=hashes,
            membership_digest=membership_digest(hashes),
        ),
        validation_receipt_digest=receipt_digest,
    )


def build_campaign(data_policy_digest: Digest, receipt_digest: Digest) -> CampaignSpec:
    """Return the development Campaign from spec section 23.3."""
    return CampaignSpec(
        schema_version=CAMPAIGN_SCHEMA_VERSION,
        kind="Campaign",
        metadata=CampaignMetadata(
            id=fixture_id("campaign", "campaign"),
            version=1,
            purpose="component_uplift",
        ),
        context=CampaignContext(program_ref=None, outcome_contract_digest=None),
        taskset=build_campaign_taskset(receipt_digest),
        environment=EnvironmentSpec(id="single-agent"),
        agents={"subject": build_subject_agent([])},
        mutation_contract=build_mutation_contract(),
        evaluation_backend=build_evaluation_backend(),
        execution=ExecutionSpec(
            order=VariantSchedule.SEQUENTIAL,
            max_concurrent=1,
            timeout_seconds=1800,
            retry_limit=0,
        ),
        scoring=ScoringSpec(
            primary_reward="reward",
            aggregation="mean",
            require_candidate_above_baseline=True,
            minimum_absolute_delta=0.05,
        ),
        evidence=EvidenceRequirements(
            verifiers_episode="required",
            runtime_evidence="not_required",
        ),
        budgets=BudgetSpec(
            maximum_input_tokens=None,
            maximum_output_tokens=None,
            maximum_model_calls=None,
            maximum_usd=None,
        ),
        data_policy_digest=data_policy_digest,
    )


def build_climb(campaign_digest: Digest) -> ClimbManifest:
    """Return the development Climb from spec section 23.4."""
    return ClimbManifest(
        schema_version=CLIMB_SCHEMA_VERSION,
        kind="Climb",
        metadata=ClimbMetadata(
            id=fixture_id("climb", "climb"),
            slug=CLIMB_SLUG,
            version=1,
            title="Procedure Transfer Development Climb",
            summary=(
                "A development Climb used to exercise the Techtree protocol "
                "end to end. It produces no publishable evidence."
            ),
            status="development",
            opens_at=None,
            closes_at=None,
        ),
        campaign_spec_digest=campaign_digest,
        candidate_policy=CandidatePolicy(
            required_mutation="skill_insertion",
            skill_visibility="public",
            constraints=CandidateConstraints(
                min_skills=1,
                max_skills=1,
                format="techtree-instruction-skill-v1",
            ),
        ),
        publication=PublicationPolicy(
            report_visibility="public",
            raw_episode_visibility="prohibited",
            public_trace_projection="redacted",
            proof_grade="development_only",
        ),
        leaderboard=LeaderboardPolicy(enabled=False, evidence_required="not_required"),
    )


def build_skill_artifact() -> SkillArtifact:
    """Return a representative candidate skill."""
    return SkillArtifact(
        schema_version=SKILL_SCHEMA_VERSION,
        name="procedure-transfer-notes",
        root_digest=fixture_digest("skill-root"),
        archive_digest=fixture_digest("skill-archive"),
        files=[
            SkillFile(
                path="SKILL.md",
                media_type="text/markdown",
                size=1024,
                digest=fixture_digest("skill-file/SKILL.md"),
            ),
            SkillFile(
                path="examples/worked.md",
                media_type="text/markdown",
                size=2048,
                digest=fixture_digest("skill-file/examples/worked.md"),
            ),
        ],
        source_kind="manual",
        parent_skill_digest=None,
    )


def build_experiment_configuration(
    data_policy_digest: Digest,
    receipt_digest: Digest,
    skills: list[ArtifactRef],
) -> ExperimentConfiguration:
    """Return one resolved configuration, differing only in the skill list."""
    return ExperimentConfiguration(
        taskset=build_campaign_taskset(receipt_digest),
        environment=EnvironmentSpec(id="single-agent"),
        agents={"subject": build_subject_agent(skills)},
        mutation_contract=build_mutation_contract(),
        evaluation_backend=build_evaluation_backend(),
        execution=ExecutionSpec(
            order=VariantSchedule.SEQUENTIAL,
            max_concurrent=1,
            timeout_seconds=1800,
            retry_limit=0,
        ),
        scoring=ScoringSpec(
            primary_reward="reward",
            aggregation="mean",
            require_candidate_above_baseline=True,
            minimum_absolute_delta=0.05,
        ),
        evidence=EvidenceRequirements(
            verifiers_episode="required",
            runtime_evidence="not_required",
        ),
        budgets=BudgetSpec(
            maximum_input_tokens=None,
            maximum_output_tokens=None,
            maximum_model_calls=None,
            maximum_usd=None,
        ),
        data_policy_digest=data_policy_digest,
        outcome_contract_digest=None,
    )


def build_experiment(
    variant: ExperimentVariant,
    campaign_digest: Digest,
    climb_digest: Digest,
    configuration: ExperimentConfiguration,
) -> ExperimentManifest:
    """Return one fully resolved experiment manifest."""
    return ExperimentManifest(
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        id=fixture_id("receipt", f"experiment/{variant.value}"),
        campaign_spec_digest=campaign_digest,
        program_ref=None,
        public_context=PublicContext(kind="climb", climb_digest=climb_digest),
        variant=variant,
        configuration=configuration,
        configuration_digest=digest_object(configuration),
        created_at=FIXED_TIME,
    )


def build_fake_uplift_report(
    campaign_digest: Digest,
    climb_digest: Digest,
    data_policy_digest: Digest,
    receipt_digest: Digest,
    baseline: ExperimentManifest,
    candidate: ExperimentManifest,
) -> UpliftReport:
    """Return the fake report shape from spec section 11.11.

    Every status says development_only. A fake run that produced a report
    claiming anything else would be indistinguishable from a real one in the
    only place a reader looks.
    """
    return UpliftReport(
        schema_version=UPLIFT_SCHEMA_VERSION,
        id=fixture_id("uplift", "uplift-report"),
        run_id=fixture_id("run", "run"),
        campaign_spec_digest=campaign_digest,
        program_ref=None,
        public_context=PublicContext(kind="climb", climb_digest=climb_digest),
        data_policy_digest=data_policy_digest,
        outcome_contract_digest=None,
        evaluation_backend=build_evaluation_backend(),
        taskset_validation_receipt_digest=receipt_digest,
        baseline_manifest_digest=digest_object(baseline),
        candidate_manifest_digest=digest_object(candidate),
        statuses=UpliftStatuses(
            execution=ExecutionStatus.COMPLETED,
            score=ScoreStatus.DEVELOPMENT_ONLY,
            evidence=EvidenceStatus.DEVELOPMENT_ONLY,
            comparison=ComparisonStatus.DEVELOPMENT_ONLY,
            publication=PublicationStatus.BLOCKED,
        ),
        manifest_comparison=ManifestComparison(
            baseline_configuration_digest=baseline.configuration_digest,
            candidate_configuration_digest=candidate.configuration_digest,
            differences=[],
            allowed_differences=[SKILL_MUTATION_POINTER],
            controlled=True,
            violations=[],
        ),
        primary_result=PrimaryUpliftResult(
            reward_name="reward",
            baseline_mean=0.5,
            candidate_mean=0.75,
            absolute_delta=0.25,
            relative_delta=0.5,
            wins=5,
            losses=0,
            ties=15,
        ),
        task_deltas=[
            TaskDelta(
                task_hash=task_hash,
                baseline_reward=0.5,
                candidate_reward=0.75 if position < 5 else 0.5,
                delta=0.25 if position < 5 else 0.0,
            )
            for position, task_hash in enumerate(ordered_task_hashes())
        ],
        decision=UpliftDecision.DEVELOPMENT_ONLY,
        proof_grade="development_only",
        publication_eligible=False,
        created_at=FIXED_TIME,
    )


def fixture_private_key() -> Ed25519PrivateKey:
    """Return the fixed key the signed goldens are signed with.

    A signed golden needs a key, and a golden that generated a fresh one would
    differ from itself on every regeneration. The seed is derived from a label
    like every other fixture value here, so this is a development fixture key
    and nothing else: it signs three example documents, it exists in this file
    where anyone can see it, and no machine's real identity is ever this.
    """
    _, _, hexadecimal = fixture_digest("executor-identity").partition(":")
    return load_private_key(bytes.fromhex(hexadecimal))


def build_executor_identity() -> ExecutorIdentity:
    """Return the public half of the fixture signing key. Spec section 7.5."""
    private_key = fixture_private_key()
    return ExecutorIdentity(
        kind="local_ed25519",
        key_id=sha256_digest_bytes(public_key_bytes(private_key)),
        algorithm="ed25519",
        public_key=public_key_to_base64(private_key.public_key()),
        created_at=FIXED_TIME,
    )


def sign_fixture[T: BaseModel](value: T) -> ObjectEnvelope[T]:
    """Wrap one fixture object in the signed envelope a real one travels in.

    Ed25519 signatures are deterministic, so the same object and the same key
    always produce the same bytes and the golden is stable.
    """
    identity = build_executor_identity()
    digest = digest_object(value)
    return ObjectEnvelope[T](
        payload=value,
        payload_digest=digest,
        signature=sign_digest(fixture_private_key(), digest, key_id=identity.key_id),
    )


def build_real_episode_receipt(
    campaign_digest: Digest,
    climb_digest: Digest,
    data_policy_digest: Digest,
    candidate: ExperimentManifest,
) -> EpisodeReceipt:
    """Return one receipt of the shape a real Verifiers episode produces.

    The difference from a fake receipt is the whole point of the golden: the
    execution backend is ``verifiers``, the subject ran in a Docker image that
    reported a digest, the reward is one Verifiers recorded, and the score and
    evidence statuses are real ones rather than ``development_only``.
    """
    task_hash = ordered_task_hashes()[0]
    return EpisodeReceipt(
        schema_version=EPISODE_RECEIPT_SCHEMA_VERSION,
        id=fixture_id("receipt", "episode-receipt"),
        run_id=fixture_id("run", "real-run"),
        campaign_spec_digest=campaign_digest,
        program_ref=None,
        public_context=PublicContext(kind="climb", climb_digest=climb_digest),
        data_policy_digest=data_policy_digest,
        outcome_contract_digest=None,
        evaluation_backend=build_evaluation_backend(),
        subject_runtime=SubjectRuntimeReceipt(
            kind="docker",
            resolved_image_digest=fixture_digest("subject-image"),
            platform="linux/arm64",
        ),
        variant=ExperimentVariant.CANDIDATE,
        experiment_manifest_digest=digest_object(candidate),
        episode_id=fixture_id("episode", "episode"),
        episode_digest=fixture_digest("raw-episode"),
        task_hash=task_hash,
        named_traces={
            SUBJECT_AGENT: [
                NamedTraceReceipt(
                    role=SUBJECT_AGENT,
                    trace_id=fixture_id("trace", "trace"),
                    trace_digest=fixture_digest("raw-trace"),
                    task_hash=task_hash,
                    rewards={"exact_match": 1.0},
                    metrics={},
                    ok=True,
                )
            ]
        },
        score_status=ScoreStatus.VALID,
        evidence_status=EvidenceStatus.COMPLETE,
        execution_backend="verifiers",
        artifacts=[
            ArtifactRef(
                digest=fixture_digest("resolved-config"),
                media_type="application/toml",
                size=2048,
                relative_path=None,
            ),
            ArtifactRef(
                digest=fixture_digest("raw-traces"),
                media_type="application/x-ndjson",
                size=262144,
                relative_path=None,
            ),
            ArtifactRef(
                digest=fixture_digest("eval-log"),
                media_type="text/plain",
                size=16384,
                relative_path=None,
            ),
            ArtifactRef(
                digest=fixture_digest("normalized-episodes"),
                media_type="application/x-ndjson",
                size=65536,
                relative_path=None,
            ),
        ],
    )


def real_task_deltas() -> list[TaskDelta]:
    """Return a fixed set of paired task rewards with wins, losses and ties."""
    pattern = {position: value for position, value in enumerate([1.0] * 6 + [0.0] * 14)}
    rows: list[TaskDelta] = []
    for position, task_hash in enumerate(ordered_task_hashes()):
        baseline = pattern[position]
        # Six tasks the baseline already passed stay passed, eight more pass
        # with the Skill, and two regress: a golden that only improved would
        # not exercise the shape a reader most needs to be able to read.
        candidate = 1.0 if 6 <= position < 14 else (0.0 if position < 2 else baseline)
        rows.append(
            TaskDelta(
                task_hash=task_hash,
                baseline_reward=baseline,
                candidate_reward=candidate,
                delta=candidate - baseline,
            )
        )
    return rows


def build_real_uplift_report(
    campaign_digest: Digest,
    climb_digest: Digest,
    data_policy_digest: Digest,
    receipt_digest: Digest,
    baseline: ExperimentManifest,
    candidate: ExperimentManifest,
) -> UpliftReport:
    """Return the shape a signed real report takes. Spec sections 7.10 and 3.4.

    ``P1`` is stated here because the decisions-0005 section 3.4 conditions are
    what a real run establishes before it may write one, and a golden's job is
    to show the shape a reader will meet. The statuses are the ones a real
    controlled comparison in this build produces, warnings included.
    """
    deltas = real_task_deltas()
    return UpliftReport(
        schema_version=UPLIFT_SCHEMA_VERSION,
        id=fixture_id("uplift", "real-uplift-report"),
        run_id=fixture_id("run", "real-run"),
        campaign_spec_digest=campaign_digest,
        program_ref=None,
        public_context=PublicContext(kind="climb", climb_digest=climb_digest),
        data_policy_digest=data_policy_digest,
        outcome_contract_digest=None,
        evaluation_backend=build_evaluation_backend(),
        taskset_validation_receipt_digest=receipt_digest,
        baseline_manifest_digest=digest_object(baseline),
        candidate_manifest_digest=digest_object(candidate),
        statuses=UpliftStatuses(
            execution=ExecutionStatus.COMPLETED,
            score=ScoreStatus.VALID,
            evidence=EvidenceStatus.COMPLETE,
            # The honest status of a real comparison in this build: no mismatch
            # was found, and two claims are weaker than they would like to be.
            comparison=ComparisonStatus.CONTROLLED_WITH_WARNINGS,
            publication=PublicationStatus.NOT_REQUESTED,
        ),
        manifest_comparison=ManifestComparison(
            baseline_configuration_digest=baseline.configuration_digest,
            candidate_configuration_digest=candidate.configuration_digest,
            differences=[
                JsonDifference(
                    pointer=f"{SKILL_MUTATION_POINTER}/0",
                    baseline=None,
                    candidate=fixture_digest("skill-archive"),
                )
            ],
            allowed_differences=[SKILL_MUTATION_POINTER],
            controlled=True,
            violations=[],
        ),
        primary_result=aggregate_primary_result(deltas, "exact_match"),
        task_deltas=deltas,
        decision=UpliftDecision.ACCEPTED,
        proof_grade="P1",
        publication_eligible=False,
        created_at=FIXED_TIME,
    )


def build_presentation_payload(
    report: UpliftReport,
    receipt: EpisodeReceipt,
    skill: SkillArtifact,
    climb: ClimbManifest,
) -> UpliftPresentationPayload:
    """Return what every channel draws one real result from. Spec section 7.13."""
    return build_uplift_presentation(
        report=report,
        baseline_receipts=[receipt],
        candidate_receipts=[receipt],
        campaign_title=climb.metadata.title,
        baseline_skill=None,
        candidate_skill=skill,
        # A fixture verdict standing in for a real offline verification, which
        # needs a bundle on disk. The payload only reads whether it verified.
        verification=VerificationResult(
            verified=True,
            messages=[
                VerificationMessage(
                    id="bundle.signature",
                    status="passed",
                    code="signature_verification_failed",
                    detail="the signature verifies against the public key carried "
                    "with it",
                )
            ],
        ),
    )


def real_variant_receipts(
    receipt: EpisodeReceipt, *, candidate: bool
) -> list[EpisodeReceipt]:
    """Return one receipt per committed task, scored as the deltas record.

    The golden receipt is one episode. A context describes a whole run, so the
    fixture is widened to the run the report already describes rather than the
    context being shown a run with nineteen tasks missing.
    """
    receipts: list[EpisodeReceipt] = []
    for position, delta in enumerate(real_task_deltas()):
        reward = delta.candidate_reward if candidate else delta.baseline_reward
        traces = [
            trace.model_copy(
                update={
                    "task_hash": delta.task_hash,
                    "rewards": {"exact_match": reward},
                    "ok": True,
                }
            )
            for trace in receipt.named_traces[SUBJECT_AGENT]
        ]
        receipts.append(
            receipt.model_copy(
                update={
                    "id": fixture_id("receipt", f"episode-receipt-{position}"),
                    "task_hash": delta.task_hash,
                    "named_traces": {SUBJECT_AGENT: traces},
                    "variant": (
                        ExperimentVariant.CANDIDATE
                        if candidate
                        else ExperimentVariant.BASELINE
                    ),
                }
            )
        )
    return receipts


def build_improvement_context(
    report: UpliftReport,
    receipt: EpisodeReceipt,
    campaign: CampaignSpec,
    skill: SkillArtifact,
) -> SkillImprovementContext:
    """Return the sanitized context a host agent reads. Spec section 7.18.

    It is a golden because the contract WP10 builds against is the *shape* of
    what a model is handed, and a change to that shape should show up in a
    diff rather than in a plugin's output. What it proves at a glance is the
    exclusion: ``prohibited_material`` is spelled out and no example carries a
    reply.
    """
    return build_improvement_context_for(
        report=report,
        candidate_receipts=real_variant_receipts(receipt, candidate=True),
        baseline_receipts=real_variant_receipts(receipt, candidate=False),
        campaign=campaign,
        parent_skill=skill,
    )


def build_climb_summary(
    campaign: CampaignSpec,
    campaign_digest: Digest,
    climb: ClimbManifest,
    climb_digest: Digest,
    data_policy: DataPolicy,
) -> ClimbSummary:
    """Return what ``climb show`` displays for the development Climb."""
    compatibility = CompatibilityResult(
        compatible=False,
        host_platform="darwin/arm64",
        host_supported=True,
        required_engine_digest=fixture_digest("engine-bundle"),
        engine_status=EngineCompatibilityStatus.NOT_INSTALLED,
        evaluation_backend_kind=campaign.evaluation_backend.kind,
        evaluation_backend_supported=True,
        issues=[
            CompatibilityIssue(
                code="engine_not_installed",
                severity="error",
                message=(
                    "The managed evaluation engine this Climb requires is not "
                    "installed yet."
                ),
                blocking=True,
            )
        ],
    )
    return ClimbSummary(
        reference=f"{climb.metadata.slug}@{climb.metadata.version}",
        climb_digest=climb_digest,
        campaign_spec_digest=campaign_digest,
        title=climb.metadata.title,
        summary=climb.metadata.summary,
        status=climb.metadata.status,
        purpose=campaign.metadata.purpose,
        taskset_id=campaign.taskset.ref.id,
        task_count=campaign.taskset.selection.num_tasks,
        subject_harness=campaign.subject.harness.id,
        subject_harness_version=campaign.subject.harness.version,
        mutation_kind=campaign.mutation_contract.kind,
        candidate_skill_visibility=climb.candidate_policy.skill_visibility,
        evaluation_backend=campaign.evaluation_backend.kind,
        proof_grade=climb.publication.proof_grade,
        data_policy=DataPolicySummary(
            raw_episode_server_upload=data_policy.raw_episodes.server_upload,
            raw_episode_training_use=data_policy.raw_episodes.training_use,
            candidate_skill_public_release=(data_policy.candidate_skill.public_release),
            uplift_report_visibility=data_policy.derived_artifacts.uplift_report,
        ),
        compatibility=compatibility,
    )


def build_cli_envelope(summary: ClimbSummary) -> CliEnvelope[ClimbSummary]:
    """Return a representative successful CLI response."""
    return CliEnvelope[ClimbSummary](
        schema_version=CLI_SCHEMA_VERSION,
        ok=True,
        command="climb show",
        data=summary,
        messages=[
            CliMessage(
                level=MessageLevel.INFO,
                code="development_climb",
                text=(
                    "This is a development Climb. Its results are not "
                    "publishable evidence."
                ),
            )
        ],
        warnings=[
            CliMessage(
                level=MessageLevel.WARNING,
                code="engine_not_installed",
                text=(
                    "The evaluation engine is not installed, so this Climb "
                    "cannot be prepared yet."
                ),
            )
        ],
        next_actions=[
            NextAction(
                id="install_engine",
                label="Install the evaluation engine",
                reason="The engine this Climb requires is not installed.",
                cli=["techtree", "engine", "install"],
                hermes_tool=None,
                hermes_args=None,
                requires_user_confirmation=False,
            )
        ],
        error=None,
    )


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def golden_objects() -> dict[str, BaseModel]:
    """Return filename/model mapping."""
    data_policy = build_data_policy()
    data_policy_digest = digest_object(data_policy)

    lock = build_taskset_lock()
    receipt = build_validation_receipt(digest_object(lock))
    receipt_digest = digest_object(receipt)

    campaign = build_campaign(data_policy_digest, receipt_digest)
    campaign_digest = digest_object(campaign)

    climb = build_climb(campaign_digest)
    climb_digest = digest_object(climb)

    skill = build_skill_artifact()
    candidate_skill = ArtifactRef(
        digest=skill.archive_digest,
        media_type="application/zip",
        size=4096,
        relative_path="candidate-skill.zip",
    )

    baseline = build_experiment(
        ExperimentVariant.BASELINE,
        campaign_digest,
        climb_digest,
        build_experiment_configuration(data_policy_digest, receipt_digest, []),
    )
    candidate = build_experiment(
        ExperimentVariant.CANDIDATE,
        campaign_digest,
        climb_digest,
        build_experiment_configuration(
            data_policy_digest, receipt_digest, [candidate_skill]
        ),
    )

    summary = build_climb_summary(
        campaign, campaign_digest, climb, climb_digest, data_policy
    )

    real_receipt = build_real_episode_receipt(
        campaign_digest, climb_digest, data_policy_digest, candidate
    )
    real_report = build_real_uplift_report(
        campaign_digest,
        climb_digest,
        data_policy_digest,
        receipt_digest,
        baseline,
        candidate,
    )

    return {
        "campaign": campaign,
        "climb": climb,
        "cli-envelope": build_cli_envelope(summary),
        "data-policy": data_policy,
        # The public half of the key the two signed goldens were signed with,
        # so a reader of those signatures has something to check them against.
        "executor-identity": build_executor_identity(),
        "experiment-baseline": baseline,
        "experiment-candidate": candidate,
        "fake-uplift-report": build_fake_uplift_report(
            campaign_digest,
            climb_digest,
            data_policy_digest,
            receipt_digest,
            baseline,
            candidate,
        ),
        "improvement-context": build_improvement_context(
            real_report, real_receipt, campaign, skill
        ),
        "presentation-payload": build_presentation_payload(
            real_report, real_receipt, skill, climb
        ),
        # The two real shapes travel signed, because that is how they exist on
        # disk once a run has proved itself: the receipt inside its envelope in
        # the proof bundle, and the report inside the envelope the bundle
        # commits to. Spec sections 7.5 and 7.11.
        "real-episode-receipt": sign_fixture(real_receipt),
        "real-uplift-report": sign_fixture(real_report),
        "skill-artifact": skill,
        "taskset-lock": lock,
        "taskset-validation-receipt": receipt,
    }


def write_golden(object_: BaseModel, destination: Path) -> None:
    """Write canonical or documented pretty JSON.

    The documented pretty form: the canonical JSON value mapping, sorted keys,
    two-space indent, one trailing newline. It is deterministic, and it is
    readable in a diff, which the RFC 8785 single-line form is not.
    """
    rendered = json.dumps(
        to_json_value(object_),
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(f"{rendered}\n", encoding="utf-8")


def main() -> None:
    """Regenerate all goldens."""
    directory = REPOSITORY_ROOT / "tests" / "golden"
    directory.mkdir(parents=True, exist_ok=True)

    objects = golden_objects()
    expected = {f"{name}.json" for name in objects}
    for stale in sorted(directory.glob("*.json")):
        if stale.name not in expected:
            stale.unlink()

    for name, object_ in sorted(objects.items()):
        write_golden(object_, directory / f"{name}.json")

    print(f"wrote {len(objects)} goldens to {directory.relative_to(REPOSITORY_ROOT)}")


if __name__ == "__main__":
    main()
