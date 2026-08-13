"""Generate the packaged development catalog. Spec section 24.3, decisions 0003.

This is the publisher. It produces the one Climb this build ships —
``procedure-transfer-dev@1`` — and every object underneath it, and none of that
is written by hand.

The pipeline is the binding order from spec section 25, executed literally:
install the engine this build ships into a throwaway Techtree home, load the
reference taskset twice in fresh processes, lock the membership that comes out,
run the pinned model-free Verifiers validation over every task, have the engine
normalize the raw output into deterministic evidence, and issue the receipt. A
DataPolicy, a CampaignSpec, and a ClimbManifest are then built around the
digests those steps produced.

Two properties make the result worth trusting.

*The receipt is not the publisher's opinion.* It is produced by
:class:`~techtree.tasksets.service.TasksetService` — the same object a
participant's worker uses — from a real validation run. A participant who
repeats the work reproduces the receipt digest exactly, and that equality is
how a Campaign's validation commitment is checked (decisions document 0003 A1).
Nothing here can fabricate a receipt, because nothing here builds one.

*Every byte is a function of its inputs.* Identifiers are derived from fixed
labels rather than issued at random, the Climb carries no schedule it would
have to invent, and every object is written in exactly the canonical bytes its
digest is taken over. ``make generated-check`` reruns this whole pipeline in a
throwaway copy of the repository and fails on any difference, so a real engine
install and a real validation run happen on every check.

What is *not* shipped: the raw ``validate`` output, the worker log, and the
publisher's :class:`~techtree.models.validation.ValidationExecutionRecord`.
Decisions document 0003 A4 allows a public object to reference an artifact only
when the catalog can resolve it, and those four files are execution outputs that
differ between two correct runs (``docs/verifiers-pin.md``, finding C0). They
stay in the build directory and are discarded with it.

Run it with ``make fixture-catalog``.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
    SUBJECT_IMAGE,
    SUBJECT_IMAGE_PLATFORM_DIGESTS,
)
from techtree.engines.bundle import default_engine_descriptor
from techtree.engines.installer import EngineInstaller, find_uv
from techtree.engines.registry import EngineRegistry
from techtree.models.base import Digest
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
    RuntimeSpec,
    SamplingSpec,
    ScoringSpec,
    TaskMembershipCommitment,
    TaskSelection,
    TasksetRef,
    VariantSchedule,
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
from techtree.models.validation import TasksetLock, TasksetValidationReceipt
from techtree.paths import ensure_path_layout, paths_from_root
from techtree.settings import Settings
from techtree.tasksets.service import TasksetService, TasksetValidationRun

REPOSITORY_ROOT: Final = Path(__file__).resolve().parent.parent
CATALOG_ROOT: Final = REPOSITORY_ROOT / "src" / "techtree" / "resources" / "catalog"

#: Decisions document 0001 fixes both public names. ``procedure-transfer-v1``
#: is reserved for the first real WP6 subject evaluation and is never what a
#: development fixture is called.
CLIMB_SLUG: Final = "procedure-transfer-dev"
CLIMB_VERSION: Final = 1
CAMPAIGN_LABEL: Final = "procedure-transfer-dev-campaign@1"
DATA_POLICY_LABEL: Final = "procedure-transfer-dev-policy@1"

#: The reference taskset, spec section 22. Its distribution name is also its
#: Verifiers taskset id.
REFERENCE_PACKAGE: Final = "procedure-transfer-v1"
TASKSET_ID: Final = "procedure-transfer-v1"

#: Every frozen proving input becomes one task, and the Campaign commits to all
#: of them. Decisions document 0001: membership is the first ``num_tasks`` in
#: iteration order and there is no shuffle.
TASK_COUNT: Final = 36

#: The reward the reference taskset defines, spec section 22.5.
PRIMARY_REWARD: Final = "exact_match"


MEDIA_TYPE: Final = "application/json"

CLIMB_PATH: Final = f"climbs/{CLIMB_SLUG}.json"
CAMPAIGN_PATH: Final = f"campaigns/{CLIMB_SLUG}.json"
DATA_POLICY_PATH: Final = f"data-policies/{CLIMB_SLUG}.json"
RECEIPT_PATH: Final = f"taskset-validations/{CLIMB_SLUG}.json"
EVIDENCE_PATH: Final = f"validation-evidence/{CLIMB_SLUG}.json"

_INDEX_FILENAME: Final = "catalog.json"
_BUILD_PREFIX: Final = "techtree-fixture-catalog-"


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


def derived_id(prefix: str, label: str) -> str:
    """Return the identifier one fixed label always produces.

    Generated fixtures cannot carry random identifiers: a UUID would make this
    tool's output differ from its own output, and ``make generated-check``
    would fail on every run for no reason. The label is what varies, and it is
    a constant.
    """
    return f"{prefix}_{hashlib.sha256(label.encode('utf-8')).hexdigest()[:32]}"


# ---------------------------------------------------------------------------
# The real work: engine, lock, validation
# ---------------------------------------------------------------------------


def reference_taskset_ref() -> TasksetRef:
    """Return the taskset reference, read from the bundle's own descriptor.

    Decisions document 0003 A8 requires the Campaign's package digest, the
    engine descriptor's ``source_digest``, and the lock's
    ``resolved_package_digest`` to be equal. Reading the descriptor here rather
    than restating a digest is how the first of those three stops being a
    number somebody typed.
    """
    descriptor = default_engine_descriptor()
    package = next(
        entry for entry in descriptor.packages if entry.name == REFERENCE_PACKAGE
    )
    return TasksetRef(
        kind="verifiers",
        id=TASKSET_ID,
        package=PackageRef(
            kind="embedded",
            name=REFERENCE_PACKAGE,
            revision=package.version,
            digest=package.source_digest,
        ),
        config={},
    )


def task_selection() -> TaskSelection:
    """Return the selection the Campaign commits to. Never shuffled."""
    return TaskSelection(num_tasks=TASK_COUNT, num_rollouts=1, shuffle=False)


def publish_validation(build_root: Path) -> TasksetValidationRun:
    """Install the engine, lock the taskset, and validate it for real.

    The lock is resolved before the Campaign exists, because the Campaign's
    membership commitment is built *from* the lock. The validation therefore
    compares the lock with itself: the publisher is the party that decides what
    the membership is, and the check it can honestly make is that the taskset
    it locked is the taskset it validated. A participant runs the identical
    code against the published commitment instead, which is the check that
    matters and the one that has something to disagree with.
    """
    home = build_root / "home"
    paths = paths_from_root(home)
    ensure_path_layout(paths)

    registry = EngineRegistry(paths, Settings())
    engine = EngineInstaller(paths, registry, find_uv()).install()

    service = TasksetService(registry, engine.digest)
    lock = service.resolve(
        taskset_ref=reference_taskset_ref(), selection=task_selection()
    )
    return service.validate(
        lock=lock,
        committed_task_hashes=lock.ordered_task_hashes,
        expected_task_count=TASK_COUNT,
        run_dir=build_root / "validation",
    )


# ---------------------------------------------------------------------------
# The objects built around it
# ---------------------------------------------------------------------------


def build_development_data_policy() -> DataPolicy:
    """Return the development rights policy. Spec section 11.4."""
    return DataPolicy(
        schema_version=DATA_POLICY_SCHEMA_VERSION,
        id=derived_id("policy", DATA_POLICY_LABEL),
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


def build_procedure_transfer_campaign(
    *,
    taskset_lock: TasksetLock,
    validation_receipt_digest: Digest,
    data_policy_digest: Digest,
) -> CampaignSpec:
    """Return the scientific contract. Spec section 23.3, decisions 0001.

    The subject *model* is the frozen development placeholder: which model
    answers is a founder-ratified release coordinate (decisions document 0006),
    and ``check_live_campaign`` refuses to execute a Campaign that still names
    the placeholder.

    The subject *runtime* is not a placeholder any more. Decisions document
    0007 R5 makes image pinning release-blocking, and an image pin is not a
    coordinate anybody ratifies — it is a fact about a registry, read from one.
    So the container this Campaign will run is named here by content, for every
    platform it supports, from the day WP11 pinned it.
    """
    return CampaignSpec(
        schema_version=CAMPAIGN_SCHEMA_VERSION,
        kind="Campaign",
        metadata=CampaignMetadata(
            id=derived_id("campaign", CAMPAIGN_LABEL),
            version=1,
            purpose="component_uplift",
        ),
        context=CampaignContext(program_ref=None, outcome_contract_digest=None),
        taskset=CampaignTaskset(
            ref=taskset_lock.taskset_ref,
            selection=task_selection(),
            membership=TaskMembershipCommitment(
                mode="committed",
                ordered_task_hashes=list(taskset_lock.ordered_task_hashes),
                membership_digest=taskset_lock.membership_digest,
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
                    image=SUBJECT_IMAGE,
                    supported_platforms=sorted(SUBJECT_IMAGE_PLATFORM_DIGESTS),
                    image_platform_digests=dict(SUBJECT_IMAGE_PLATFORM_DIGESTS),
                    cpu=2.0,
                    memory_gb=4.0,
                    network_policy="restricted",
                ),
                trainable=False,
            )
        },
        mutation_contract=MutationContract(
            kind=MutationKind.SKILL_INSERTION,
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
            order=VariantSchedule.SEQUENTIAL,
            max_concurrent=1,
            timeout_seconds=600,
            retry_limit=0,
        ),
        scoring=ScoringSpec(
            primary_reward=PRIMARY_REWARD,
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


def build_procedure_transfer_climb(*, campaign_digest: Digest) -> ClimbManifest:
    """Return the public wrapper. Spec section 23.4.

    No schedule. A development Climb is open for as long as this build exists,
    and inventing an opening date would put a fact in a public object that
    nothing established.
    """
    return ClimbManifest(
        schema_version=CLIMB_SCHEMA_VERSION,
        kind="Climb",
        metadata=ClimbMetadata(
            id=derived_id("climb", f"{CLIMB_SLUG}@{CLIMB_VERSION}"),
            slug=CLIMB_SLUG,
            version=CLIMB_VERSION,
            title="Procedure Transfer Development Climb",
            summary=(
                "Does writing down a procedure as a skill let an agent apply it "
                "to inputs it has never seen? This development Climb exercises "
                "the whole Techtree loop against a real, model-free validated "
                "taskset; its results are produced by the fake executor and are "
                "not evidence."
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


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def write_catalog(
    *,
    climbs: Mapping[str, ClimbManifest],
    objects: Sequence[CatalogFile],
    destination: Path,
) -> None:
    """Write every object and the index that addresses them.

    Objects are written in exactly the canonical bytes their digest is taken
    over, so the file on disk *is* the digested form. The index is readable
    JSON: nothing addresses it by digest, and it is the one file a person opens
    to see what a build ships.
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
    document = json.loads(canonical_json_bytes(index).decode("utf-8"))
    rendered = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / _INDEX_FILENAME).write_text(f"{rendered}\n", encoding="utf-8")


def _write_object(path: Path, model: BaseModel) -> None:
    """Write one object as the canonical bytes its digest is taken over."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(model))


def _remove_stale_objects(destination: Path, keep: Sequence[str]) -> None:
    """Delete catalog files this build no longer ships.

    The generator owns the whole directory. A file left behind from an earlier
    shape would be shipped in the package while nothing referenced it, which is
    exactly the dangling artifact decisions document 0003 A4 rules out.
    """
    kept = {destination / relative for relative in keep}
    kept.add(destination / _INDEX_FILENAME)
    for path in sorted(destination.rglob("*")):
        if path.is_file() and path not in kept:
            path.unlink()
    for path in sorted(destination.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def build(destination: Path = CATALOG_ROOT) -> TasksetValidationReceipt:
    """Generate the complete packaged catalog and return the publisher receipt."""
    with tempfile.TemporaryDirectory(prefix=_BUILD_PREFIX) as directory:
        validation = publish_validation(Path(directory))

    data_policy = build_development_data_policy()
    campaign = build_procedure_transfer_campaign(
        taskset_lock=validation.lock,
        validation_receipt_digest=validation.receipt_digest,
        data_policy_digest=digest_object(data_policy),
    )
    climb = build_procedure_transfer_climb(campaign_digest=digest_object(campaign))

    objects = [
        CatalogFile(kind="campaign", path=CAMPAIGN_PATH, model=campaign),
        CatalogFile(kind="data_policy", path=DATA_POLICY_PATH, model=data_policy),
        CatalogFile(
            kind="taskset_validation", path=RECEIPT_PATH, model=validation.receipt
        ),
        CatalogFile(
            kind="validation_evidence", path=EVIDENCE_PATH, model=validation.evidence
        ),
    ]
    _remove_stale_objects(destination, [CLIMB_PATH, *(entry.path for entry in objects)])
    write_catalog(
        climbs={CLIMB_PATH: climb},
        objects=objects,
        destination=destination,
    )
    return validation.receipt


def main() -> None:
    """Generate the complete fixture catalog and report what it commits to."""
    receipt = build()
    sys.stdout.write(
        f"{CLIMB_SLUG}@{CLIMB_VERSION}: {TASK_COUNT} tasks, validation "
        f"{receipt.status}, receipt {digest_object(receipt)}\n"
    )


if __name__ == "__main__":
    main()
