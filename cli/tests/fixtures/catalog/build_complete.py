"""Builds the complete synthetic catalog fixture. Decisions 0003 A2.

The packaged catalog is empty until the generation chain exists, so the graph
logic has nothing real to resolve. This script writes the thing it can resolve
instead: a small, entirely synthetic catalog whose digests are computed for
real, so every check the repository and the service perform is exercised
against a graph that genuinely holds together.

Nothing here is science. The tasks are named ``synthetic-task-000`` and the
engine is a string, because a fixture that looked like a real Taskset would
eventually be mistaken for one. What is real is the shape: a Climb pointing at
a Campaign, pointing at a DataPolicy and a publisher validation receipt,
pointing in turn at the normalized evidence that receipt was issued from.

Three Climbs share the one Campaign so that listing can be filtered by status
without three copies of the same science.

Every object is written as canonical JSON, which is also the form its digest is
taken over, so the bytes on disk are fully determined by their contents. Run
``uv run python tests/fixtures/catalog/build_complete.py`` to rewrite the
fixture; the contract tests fail if the committed files differ from what this
script produces.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel

from techtree.canonical import canonical_json_bytes, digest_object
from techtree.constants import (
    CAMPAIGN_SCHEMA_VERSION,
    CATALOG_SCHEMA_VERSION,
    CLIMB_SCHEMA_VERSION,
    DATA_POLICY_SCHEMA_VERSION,
    EVALUATION_BACKEND_SCHEMA_VERSION,
    PINNED_VERIFIERS_REVISION,
    TASKSET_LOCK_SCHEMA_VERSION,
    TASKSET_VALIDATION_SCHEMA_VERSION,
    VALIDATION_EVIDENCE_SCHEMA_VERSION,
)
from techtree.models.base import ArtifactRef, Digest
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
    PackageRef,
    RuntimeSpec,
    SamplingSpec,
    ScoringSpec,
    TaskMembershipCommitment,
    TaskSelection,
    TasksetRef,
)
from techtree.models.catalog import (
    CatalogClimbEntry,
    CatalogIndex,
    CatalogObjectLocation,
)
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
from techtree.models.evaluation_backend import (
    AttestationKind,
    EvaluationBackendKind,
    EvaluationBackendSpec,
)
from techtree.models.validation import (
    TasksetLock,
    TasksetValidationReceipt,
    UpstreamValidationSummary,
    ValidationCheck,
    ValidationEvidence,
    ValidationEvidenceSummary,
    ValidationEvidenceTask,
    ValidationMethod,
    ValidationTaskOutcome,
)
from techtree.tasksets.membership import membership_digest

#: Where the committed fixture lives.
FIXTURE_DIRECTORY: Final[Path] = Path(__file__).resolve().parent / "complete"

#: How many synthetic tasks the fixture Campaign commits to. Small enough to
#: read in a failing assertion, large enough that an off-by-one shows up.
TASK_COUNT: Final = 4

MEDIA_TYPE: Final = "application/json"

CAMPAIGN_PATH: Final = "campaigns/synthetic.json"
DATA_POLICY_PATH: Final = "data-policies/synthetic.json"
RECEIPT_PATH: Final = "taskset-validations/synthetic.json"
EVIDENCE_PATH: Final = "validation-evidence/synthetic.json"

type ClimbStatus = Literal["open", "closed", "development"]
type ProofGrade = Literal["development_only", "P1"]
type SkillVisibility = Literal["public", "private"]

#: The three public wrappers around the one synthetic Campaign, and the status
#: each of them exists to exercise.
CLIMB_VARIANTS: Final[tuple[tuple[str, ClimbStatus, ProofGrade], ...]] = (
    ("synthetic-open", "open", "P1"),
    ("synthetic-development", "development", "development_only"),
    ("synthetic-closed", "closed", "P1"),
)


@dataclass(frozen=True)
class CatalogFile:
    """One object, where it goes, and what the index calls it."""

    kind: Literal[
        "campaign",
        "data_policy",
        "taskset_validation",
        "validation_evidence",
    ]
    path: str
    model: BaseModel


def synthetic_digest(label: str) -> Digest:
    """Return a deterministic digest derived from a label.

    Used only where the fixture needs a digest of something it does not ship —
    an engine bundle, a source package. Everything the fixture does ship is
    digested from its real contents.
    """
    return f"sha256:{hashlib.sha256(label.encode('utf-8')).hexdigest()}"


def synthetic_id(prefix: str, label: str) -> str:
    """Return a deterministic prefixed identifier."""
    return f"{prefix}_{hashlib.sha256(label.encode('utf-8')).hexdigest()[:32]}"


def task_hashes() -> list[Digest]:
    """Return the synthetic task hashes the fixture commits to, in order."""
    return [
        synthetic_digest(f"synthetic-task-{position:03d}")
        for position in range(TASK_COUNT)
    ]


def build_data_policy() -> DataPolicy:
    """Return the rights statement the synthetic Campaign runs under."""
    return DataPolicy(
        schema_version=DATA_POLICY_SCHEMA_VERSION,
        id=synthetic_id("policy", "synthetic-data-policy"),
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


def build_taskset_ref() -> TasksetRef:
    """Return the synthetic taskset reference the whole graph shares."""
    return TasksetRef(
        kind="verifiers",
        id="synthetic-taskset",
        package=PackageRef(
            kind="embedded",
            name="synthetic-package",
            revision="1",
            digest=synthetic_digest("synthetic-package-source"),
        ),
        config={},
    )


def build_taskset_lock() -> TasksetLock:
    """Return the publisher lock the receipt and evidence were issued under.

    The lock itself is not part of the public catalog — only its digest is
    referenced — so it is built here and never written.
    """
    hashes = task_hashes()
    return TasksetLock(
        schema_version=TASKSET_LOCK_SCHEMA_VERSION,
        taskset_ref=build_taskset_ref(),
        engine_digest=synthetic_digest("synthetic-engine-bundle"),
        resolved_package_digest=synthetic_digest("synthetic-package-source"),
        ordered_task_hashes=hashes,
        membership_digest=membership_digest(hashes),
        task_count=TASK_COUNT,
    )


def build_validation_method() -> ValidationMethod:
    """Return how the synthetic validation was performed."""
    return ValidationMethod(
        kind="verifiers_validate",
        mode="all",
        runtime="subprocess",
        validator_revision=PINNED_VERIFIERS_REVISION,
    )


def build_validation_evidence(lock: TasksetLock) -> ValidationEvidence:
    """Return the normalized per-task record the publisher would ship."""
    passed = ValidationTaskOutcome(valid=True, reason="valid")
    return ValidationEvidence(
        schema_version=VALIDATION_EVIDENCE_SCHEMA_VERSION,
        taskset_lock_digest=digest_object(lock),
        method=build_validation_method(),
        tasks=[
            ValidationEvidenceTask(
                position=position,
                task_hash=task_hash,
                gold=passed,
                setup=passed,
            )
            for position, task_hash in enumerate(lock.ordered_task_hashes)
        ],
        summary=ValidationEvidenceSummary(
            total=TASK_COUNT,
            valid=TASK_COUNT,
            invalid=0,
            error=0,
            timeout=0,
            missing=0,
        ),
    )


def build_validation_receipt(
    lock: TasksetLock, evidence: ValidationEvidence
) -> TasksetValidationReceipt:
    """Return the publisher receipt the Campaign commits to."""
    return TasksetValidationReceipt(
        schema_version=TASKSET_VALIDATION_SCHEMA_VERSION,
        taskset_lock_digest=digest_object(lock),
        engine_digest=lock.engine_digest,
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
                id=identifier,
                status="passed",
                detail=detail,
            )
            for identifier, detail in (
                ("upstream_gold", "every gold answer validated"),
                ("upstream_setup", "every task set up cleanly"),
                ("membership_repeatability", "two inspections agreed"),
                ("task_hash_uniqueness", "no task hash repeats"),
                ("committed_membership_match", "membership matches the lock"),
                ("expected_task_count", f"{TASK_COUNT} tasks, as expected"),
            )
        ],
        normalized_evidence=ArtifactRef(
            digest=digest_object(evidence),
            media_type=MEDIA_TYPE,
            size=len(canonical_json_bytes(evidence)),
            relative_path=None,
        ),
    )


def build_campaign(
    *,
    lock: TasksetLock,
    validation_receipt_digest: Digest,
    data_policy_digest: Digest,
) -> CampaignSpec:
    """Return the synthetic scientific contract the Climbs wrap."""
    return CampaignSpec(
        schema_version=CAMPAIGN_SCHEMA_VERSION,
        kind="Campaign",
        metadata=CampaignMetadata(
            id=synthetic_id("campaign", "synthetic-campaign"),
            version=1,
            purpose="component_uplift",
        ),
        context=CampaignContext(program_ref=None, outcome_contract_digest=None),
        taskset=CampaignTaskset(
            ref=lock.taskset_ref,
            selection=TaskSelection(
                num_tasks=TASK_COUNT,
                num_rollouts=1,
                shuffle=False,
            ),
            membership=TaskMembershipCommitment(
                mode="committed",
                ordered_task_hashes=list(lock.ordered_task_hashes),
                membership_digest=lock.membership_digest,
            ),
            validation_receipt_digest=validation_receipt_digest,
        ),
        environment=EnvironmentSpec(id="single-agent"),
        agents={
            SUBJECT_AGENT: AgentSpec(
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
                    skills=[],
                ),
                runtime=RuntimeSpec(
                    type="docker",
                    image="techtree-development-placeholder:not-executed",
                    supported_platforms=["linux/arm64", "linux/amd64"],
                    cpu=2.0,
                    memory_gb=4.0,
                    network_policy="restricted",
                ),
                trainable=False,
            )
        },
        mutation_contract=MutationContract(
            kind="skill_insertion",
            target_agent="subject",
            allowed_differences=[SKILL_MUTATION_POINTER],
            minimum_skills=1,
            maximum_skills=1,
        ),
        evaluation_backend=EvaluationBackendSpec(
            schema_version=EVALUATION_BACKEND_SCHEMA_VERSION,
            kind=EvaluationBackendKind.LOCAL_TECHTREE,
            attestation=AttestationKind.PARTICIPANT,
            workspace_ref=None,
            provider_run_ref=None,
            executor_identity=None,
        ),
        execution=ExecutionSpec(
            order="baseline_then_candidate",
            max_concurrent=1,
            timeout_seconds=600,
            retry_limit=0,
        ),
        scoring=ScoringSpec(
            primary_reward="synthetic_reward",
            aggregation="mean",
            require_candidate_above_baseline=True,
            minimum_absolute_delta=0.0,
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


def build_climb(
    *,
    campaign_digest: Digest,
    slug: str,
    status: ClimbStatus,
    proof_grade: ProofGrade,
    skill_visibility: SkillVisibility = "public",
    version: int = 1,
) -> ClimbManifest:
    """Return one public wrapper around the synthetic Campaign."""
    return ClimbManifest(
        schema_version=CLIMB_SCHEMA_VERSION,
        kind="Climb",
        metadata=ClimbMetadata(
            id=synthetic_id("climb", f"{slug}@{version}"),
            slug=slug,
            version=version,
            title=f"Synthetic {status} Climb",
            summary=(
                "A synthetic Climb used to exercise catalog resolution. It "
                "measures nothing."
            ),
            status=status,
            opens_at=datetime(2026, 1, 1, tzinfo=UTC),
            closes_at=datetime(2027, 1, 1, tzinfo=UTC),
        ),
        campaign_spec_digest=campaign_digest,
        candidate_policy=CandidatePolicy(
            required_mutation="skill_insertion",
            skill_visibility=skill_visibility,
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
            proof_grade=proof_grade,
        ),
        leaderboard=LeaderboardPolicy(enabled=False, evidence_required="not_required"),
    )


def write_catalog(
    destination: Path,
    *,
    climbs: Mapping[str, ClimbManifest],
    objects: Sequence[CatalogFile],
) -> None:
    """Write every object and the index that addresses them.

    ``climbs`` maps a relative path to the manifest that belongs there.
    """
    for path, climb in climbs.items():
        _write_object(destination / path, climb)
    for entry in objects:
        _write_object(destination / entry.path, entry.model)

    index = CatalogIndex(
        schema_version=CATALOG_SCHEMA_VERSION,
        climbs=[
            CatalogClimbEntry(
                reference=f"{climb.metadata.slug}@{climb.metadata.version}",
                digest=digest_object(climb),
                path=path,
            )
            for path, climb in climbs.items()
        ],
        objects={
            digest_object(entry.model): CatalogObjectLocation(
                kind=entry.kind,
                path=entry.path,
                media_type=MEDIA_TYPE,
            )
            for entry in objects
        },
    )
    write_index(destination, index)


def write_index(destination: Path, index: CatalogIndex) -> None:
    """Write one catalog index as readable, stably ordered JSON."""
    destination.mkdir(parents=True, exist_ok=True)
    document = json.loads(canonical_json_bytes(index).decode("utf-8"))
    rendered = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False)
    (destination / "catalog.json").write_text(f"{rendered}\n", encoding="utf-8")


def build(destination: Path = FIXTURE_DIRECTORY) -> None:
    """Write the complete synthetic catalog fixture."""
    data_policy = build_data_policy()
    lock = build_taskset_lock()
    evidence = build_validation_evidence(lock)
    receipt = build_validation_receipt(lock, evidence)
    campaign = build_campaign(
        lock=lock,
        validation_receipt_digest=digest_object(receipt),
        data_policy_digest=digest_object(data_policy),
    )
    campaign_digest = digest_object(campaign)

    climbs = {
        f"climbs/{slug}.json": build_climb(
            campaign_digest=campaign_digest,
            slug=slug,
            status=status,
            proof_grade=proof_grade,
        )
        for slug, status, proof_grade in CLIMB_VARIANTS
    }

    write_catalog(
        destination,
        climbs=climbs,
        objects=[
            CatalogFile(kind="campaign", path=CAMPAIGN_PATH, model=campaign),
            CatalogFile(kind="data_policy", path=DATA_POLICY_PATH, model=data_policy),
            CatalogFile(kind="taskset_validation", path=RECEIPT_PATH, model=receipt),
            CatalogFile(kind="validation_evidence", path=EVIDENCE_PATH, model=evidence),
        ],
    )


def _write_object(path: Path, model: BaseModel) -> None:
    """Write one object as the canonical bytes its digest is taken over."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(model))


if __name__ == "__main__":
    build()
