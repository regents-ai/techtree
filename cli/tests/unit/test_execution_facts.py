"""Projecting a bound plan onto the v0.2 run-side documents. Plan v0.2.

Three things are held in place here.

The first is that a projection is refused unless the plan really is the one the
Campaign binds. Everything downstream rests on that check: a document built
from an unbound plan would state facts about a run that never happened, in
fields nothing else could contradict.

The second is that the projection follows the plan. Move a plane and the
projected fields move with it, which is what makes the plan the owner of those
facts rather than a second place they happen to be written.

The third is structural, and it is decision 0040's rule rather than a style
preference: no v0.2 document may state a fact the v0.2 Campaign dropped. That
is checked against the models themselves — the field names they declare and
the model classes they can reach — so a v0.2 document cannot acquire an
evaluation backend or a harness coordinate by nesting a v0.1 model that has
one.
"""

from __future__ import annotations

import typing
from dataclasses import fields as dataclass_fields
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import digest_object
from techtree.constants import (
    CAMPAIGN_V2_SCHEMA_VERSION,
    EPISODE_RECEIPT_SCHEMA_VERSION,
    EPISODE_RECEIPT_V2_SCHEMA_VERSION,
    EVALUATION_BACKEND_SCHEMA_VERSION,
    EXECUTION_PLAN_SCHEMA_VERSION,
    PINNED_VERIFIERS_REVISION,
    RUN_REQUEST_V2_SCHEMA_VERSION,
    SUBJECT_IMAGE,
    SUBJECT_IMAGE_PLATFORM_DIGESTS,
)
from techtree.errors import ValidationError
from techtree.execution_facts import (
    climb_summary_execution_facts,
    compatibility_result_execution_facts,
    episode_receipt_execution_facts,
    experiment_configuration_execution_facts,
    release_core_subject_hermes_version,
    run_request_execution_facts,
    uplift_report_execution_facts,
)
from techtree.models.base import Digest
from techtree.models.campaign import (
    SKILL_MUTATION_POINTER,
    SUBJECT_AGENT,
    AgentSpec,
    AgentSpecV2,
    BudgetSpec,
    CampaignContext,
    CampaignMetadata,
    CampaignSpecV2,
    CampaignTaskset,
    EnvironmentSpec,
    EvidenceRequirements,
    EvidenceRequirementsV2,
    ExecutionSpec,
    HarnessSpec,
    HarnessSpecV2,
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
    ClimbSummary,
    ClimbSummaryV2,
    CompatibilityResult,
    CompatibilityResultV2,
)
from techtree.models.episode_receipt import (
    EpisodeReceipt,
    EpisodeReceiptV2,
    EvidenceStatus,
    ScoreStatus,
    SubjectRuntimeReceipt,
)
from techtree.models.evaluation_backend import (
    AttestationKind,
    EvaluationBackendKind,
    EvaluationBackendSpec,
)
from techtree.models.evidence import ExecutionLocationKind
from techtree.models.execution_plan import (
    EvaluationEngineRef,
    EvidenceBackendSpec,
    ExecutionBackendKind,
    ExecutionBackendSpec,
    ExecutionProvider,
    ResolvedExecutionPlan,
    SubjectBackendKind,
    SubjectBackendSpec,
)
from techtree.models.experiment import (
    ExperimentConfiguration,
    ExperimentConfigurationV2,
    ExperimentManifest,
    ExperimentManifestV2,
    ExperimentVariant,
)
from techtree.models.run import PolicyAcknowledgement, RunRequest, RunRequestV2
from techtree.models.uplift_report import UpliftReport, UpliftReportV2

TASK_DIGEST: Digest = f"sha256:{'11' * 32}"
POLICY_DIGEST: Digest = f"sha256:{'44' * 32}"
RECEIPT_DIGEST: Digest = f"sha256:{'55' * 32}"
MEMBERSHIP_DIGEST: Digest = f"sha256:{'66' * 32}"
PACKAGE_DIGEST: Digest = f"sha256:{'77' * 32}"
WHEEL_DIGEST: Digest = f"sha256:{'33' * 32}"
MANIFEST_DIGEST: Digest = f"sha256:{'88' * 32}"
OTHER_DIGEST: Digest = f"sha256:{'99' * 32}"

HARNESS_ID = "hermes-agent"
HARNESS_VERSION = "0.19.0"

#: One fixed instant, so a document built twice is the same document.
FIXED_TIME = datetime(2026, 1, 1, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def build_plan(**overrides: Any) -> ResolvedExecutionPlan:
    """Build a whole plan, defaulting to the one v0.2.0 resolves."""
    fields: dict[str, Any] = {
        "schema_version": EXECUTION_PLAN_SCHEMA_VERSION,
        "kind": "ResolvedExecutionPlan",
        "evaluation": EvaluationEngineRef(
            kind="verifiers",
            api_generation="v1",
            package_version="0.3.1",
            source_commit=PINNED_VERIFIERS_REVISION,
            wheel_digest=WHEEL_DIGEST,
        ),
        "execution": ExecutionBackendSpec(
            kind=ExecutionBackendKind.LOCAL,
            provider=None,
            provider_environment_coordinate=None,
        ),
        "subject": SubjectBackendSpec(
            kind=SubjectBackendKind.DIRECT,
            harness_id=HARNESS_ID,
            harness_version=HARNESS_VERSION,
            adapter_id=None,
            adapter_version=None,
            adapter_contract_version=None,
        ),
        "evidence": EvidenceBackendSpec(
            native_evidence="required",
            trace_coverage="not_requested",
            coverage_profile_digest=None,
        ),
    }
    fields.update(overrides)
    return ResolvedExecutionPlan(**fields)


def build_campaign(execution_plan_digest: Digest) -> CampaignSpecV2:
    """Build the smallest valid v0.2 Campaign bound to one plan."""
    return CampaignSpecV2(
        schema_version=CAMPAIGN_V2_SCHEMA_VERSION,
        kind="Campaign",
        metadata=CampaignMetadata(
            id="campaign-under-test", version=1, purpose="component_uplift"
        ),
        context=CampaignContext(program_ref=None, outcome_contract_digest=None),
        taskset=CampaignTaskset(
            ref=TasksetRef(
                kind="verifiers",
                id="procedure-transfer-v1",
                package=PackageRef(
                    kind="embedded",
                    name="procedure-transfer-v1",
                    revision="1",
                    digest=PACKAGE_DIGEST,
                ),
                config={},
            ),
            selection=TaskSelection(num_tasks=1, num_rollouts=1, shuffle=False),
            membership=TaskMembershipCommitment(
                mode="committed",
                ordered_task_hashes=[TASK_DIGEST],
                membership_digest=MEMBERSHIP_DIGEST,
            ),
            validation_receipt_digest=RECEIPT_DIGEST,
        ),
        environment=EnvironmentSpec(id="single-agent"),
        agents={
            SUBJECT_AGENT: AgentSpecV2(
                model=build_model_spec(),
                sampling=SamplingSpec(temperature=0.0, max_tokens=512),
                harness=HarnessSpecV2(use_bundled_skill=False, skills=[]),
                runtime=build_runtime_spec(),
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
        evidence=EvidenceRequirementsV2(runtime_evidence="not_required"),
        budgets=BudgetSpec(),
        data_policy_digest=POLICY_DIGEST,
        execution_plan_digest=execution_plan_digest,
    )


def build_model_spec() -> ModelSpec:
    """Return the development subject model."""
    return ModelSpec(
        provider="development",
        model_id="development-placeholder",
        revision=None,
        credential_env="TECHTREE_MODEL_API_KEY",
    )


def build_runtime_spec() -> RuntimeSpec:
    """Return the pinned subject container."""
    return RuntimeSpec(
        type="docker",
        image=SUBJECT_IMAGE,
        supported_platforms=sorted(SUBJECT_IMAGE_PLATFORM_DIGESTS),
        image_platform_digests=dict(SUBJECT_IMAGE_PLATFORM_DIGESTS),
        cpu=2.0,
        memory_gb=4.0,
        network_policy="restricted",
    )


def bound_pair(
    **plan_overrides: Any,
) -> tuple[CampaignSpecV2, ResolvedExecutionPlan]:
    """Return a Campaign and the plan it binds."""
    plan = build_plan(**plan_overrides)
    return build_campaign(digest_object(plan)), plan


#: Every projection, so the binding check can be held to all of them at once.
PROJECTIONS = [
    climb_summary_execution_facts,
    compatibility_result_execution_facts,
    episode_receipt_execution_facts,
    experiment_configuration_execution_facts,
    release_core_subject_hermes_version,
    run_request_execution_facts,
    uplift_report_execution_facts,
]

#: The projections that hand a document the plan's digest.
PROJECTIONS_NAMING_THE_PLAN = [
    compatibility_result_execution_facts,
    episode_receipt_execution_facts,
    experiment_configuration_execution_facts,
    run_request_execution_facts,
    uplift_report_execution_facts,
]


# ---------------------------------------------------------------------------
# The binding
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("projection", PROJECTIONS, ids=lambda call: call.__name__)
def test_nothing_is_projected_from_a_plan_the_campaign_does_not_bind(
    projection: Any,
) -> None:
    campaign, _ = bound_pair()
    other = build_plan(
        subject=SubjectBackendSpec(
            kind=SubjectBackendKind.DIRECT,
            harness_id=HARNESS_ID,
            harness_version="0.20.0",
            adapter_id=None,
            adapter_version=None,
            adapter_contract_version=None,
        )
    )

    with pytest.raises(ValidationError, match="not the one the Campaign binds"):
        projection(campaign, other)


@pytest.mark.parametrize(
    "projection", PROJECTIONS_NAMING_THE_PLAN, ids=lambda call: call.__name__
)
def test_each_projection_names_the_plan_it_was_given(projection: Any) -> None:
    campaign, plan = bound_pair()

    assert projection(campaign, plan).execution_plan_digest == digest_object(plan)


# ---------------------------------------------------------------------------
# The projections follow the plan
# ---------------------------------------------------------------------------


def test_a_local_plan_produces_a_local_execution_location() -> None:
    campaign, plan = bound_pair()

    for projection in (episode_receipt_execution_facts, uplift_report_execution_facts):
        facts = projection(campaign, plan)
        assert facts.execution_location.kind is ExecutionLocationKind.LOCAL


def test_a_hosted_plan_produces_a_hosted_execution_location() -> None:
    campaign, plan = bound_pair(
        execution=ExecutionBackendSpec(
            kind=ExecutionBackendKind.PRIME_HOSTED,
            provider=ExecutionProvider.PRIME,
            provider_environment_coordinate="prime/environments/example",
        )
    )

    for projection in (episode_receipt_execution_facts, uplift_report_execution_facts):
        facts = projection(campaign, plan)
        assert facts.execution_location.kind is ExecutionLocationKind.PRIME_HOSTED


def test_the_summary_shows_the_harness_the_subject_plane_names() -> None:
    campaign, plan = bound_pair()

    facts = climb_summary_execution_facts(campaign, plan)

    assert facts.subject_harness == HARNESS_ID
    assert facts.subject_harness_version == HARNESS_VERSION
    assert facts.execution_backend_kind is ExecutionBackendKind.LOCAL


def test_moving_the_subject_plane_moves_what_the_summary_shows() -> None:
    _, first = bound_pair()
    campaign, second = bound_pair(
        subject=SubjectBackendSpec(
            kind=SubjectBackendKind.FABRIC,
            harness_id=HARNESS_ID,
            harness_version="0.20.0",
            adapter_id="fabric-hermes",
            adapter_version="1.0.0",
            adapter_contract_version="1",
        )
    )

    facts = climb_summary_execution_facts(campaign, second)

    assert digest_object(first) != digest_object(second)
    assert facts.subject_harness_version == "0.20.0"


def test_this_release_supports_the_local_direct_plan() -> None:
    campaign, plan = bound_pair()

    facts = compatibility_result_execution_facts(campaign, plan)

    assert facts.execution_backend_kind is ExecutionBackendKind.LOCAL
    assert facts.execution_backend_supported is True
    assert facts.subject_backend_kind is SubjectBackendKind.DIRECT
    assert facts.subject_backend_supported is True


def test_the_compatibility_facts_carry_the_evaluation_plane() -> None:
    """Every plane a host can fail, including which engine build is planned."""
    campaign, plan = bound_pair()

    facts = compatibility_result_execution_facts(campaign, plan)

    assert facts.evaluation_engine_source_commit == PINNED_VERIFIERS_REVISION
    assert facts.evaluation_engine_wheel_digest == WHEEL_DIGEST


def test_a_plan_this_release_cannot_resolve_is_reported_unsupported() -> None:
    campaign, plan = bound_pair(
        execution=ExecutionBackendSpec(
            kind=ExecutionBackendKind.PRIME_HOSTED,
            provider=ExecutionProvider.PRIME,
            provider_environment_coordinate="prime/environments/example",
        ),
        subject=SubjectBackendSpec(
            kind=SubjectBackendKind.FABRIC,
            harness_id=HARNESS_ID,
            harness_version=HARNESS_VERSION,
            adapter_id="fabric-hermes",
            adapter_version="1.0.0",
            adapter_contract_version="1",
        ),
    )

    facts = compatibility_result_execution_facts(campaign, plan)

    assert facts.execution_backend_supported is False
    assert facts.subject_backend_supported is False


def test_the_release_coordinate_is_the_subject_plane_harness_version() -> None:
    campaign, plan = bound_pair()

    assert release_core_subject_hermes_version(campaign, plan) == HARNESS_VERSION


def test_the_release_coordinate_is_the_one_the_v01_campaign_stated() -> None:
    """The same fact, read from the document that now owns it."""
    campaign, plan = bound_pair()
    v1_subject = AgentSpec(
        model=build_model_spec(),
        sampling=SamplingSpec(temperature=0.0, max_tokens=512),
        harness=HarnessSpec(
            id=HARNESS_ID,
            version=HARNESS_VERSION,
            use_bundled_skill=False,
            skills=[],
        ),
        runtime=build_runtime_spec(),
        trainable=False,
    )

    assert release_core_subject_hermes_version(campaign, plan) == (
        v1_subject.harness.version
    )


# ---------------------------------------------------------------------------
# No v0.2 document states a fact the v0.2 Campaign dropped
# ---------------------------------------------------------------------------

#: Every v0.2 document this work package defines, beside the v0.1 document it
#: is a sibling of. Nothing is derived from anything: the pairs are listed so
#: the tests below can say which document they are talking about.
DOCUMENT_PAIRS: dict[str, tuple[type[BaseModel], type[BaseModel]]] = {
    "climb-summary": (ClimbSummary, ClimbSummaryV2),
    "compatibility-result": (CompatibilityResult, CompatibilityResultV2),
    "episode-receipt": (EpisodeReceipt, EpisodeReceiptV2),
    "experiment-configuration": (ExperimentConfiguration, ExperimentConfigurationV2),
    "experiment-manifest": (ExperimentManifest, ExperimentManifestV2),
    "run-request": (RunRequest, RunRequestV2),
    "uplift-report": (UpliftReport, UpliftReportV2),
}

#: Field names the v0.2 Campaign no longer has. Decision 0040.
FIELDS_THE_V2_CAMPAIGN_DROPPED = frozenset(
    {
        "evaluation_backend",
        "evaluation_backend_kind",
        "evaluation_backend_supported",
        "verifiers_episode",
    }
)

#: Models a v0.2 document must not be able to reach. Each one states, or
#: contains, a fact the execution plan now owns: the evaluation backend, the
#: subject harness coordinates, or the requirement for a Verifiers episode.
MODELS_THE_PLAN_REPLACED = frozenset(
    {
        AgentSpec,
        EvaluationBackendSpec,
        EvidenceRequirements,
        HarnessSpec,
    }
)


def _reachable_models(model: type[BaseModel]) -> set[type[BaseModel]]:
    """Return every model reachable from one model, itself included."""
    seen: set[type[BaseModel]] = set()
    pending: list[type[BaseModel]] = [model]
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        for field in current.model_fields.values():
            for candidate in _annotated_types(field.annotation):
                if (
                    isinstance(candidate, type)
                    and issubclass(candidate, BaseModel)
                    and candidate not in seen
                ):
                    pending.append(candidate)
    return seen


def _annotated_types(annotation: Any) -> list[Any]:
    """Return an annotation and every type nested inside it."""
    found = [annotation]
    for argument in typing.get_args(annotation):
        found.extend(_annotated_types(argument))
    return found


def _reachable_field_names(model: type[BaseModel]) -> set[str]:
    """Return every field name reachable from one model, at any depth."""
    return {
        name
        for reachable in _reachable_models(model)
        for name in reachable.model_fields
    }


@pytest.mark.parametrize("name", sorted(DOCUMENT_PAIRS))
def test_no_v2_document_declares_a_field_the_v2_campaign_dropped(name: str) -> None:
    _, v2 = DOCUMENT_PAIRS[name]

    assert _reachable_field_names(v2).isdisjoint(FIELDS_THE_V2_CAMPAIGN_DROPPED)


@pytest.mark.parametrize("name", sorted(DOCUMENT_PAIRS))
def test_no_v2_document_can_reach_a_model_the_plan_replaced(name: str) -> None:
    _, v2 = DOCUMENT_PAIRS[name]

    assert _reachable_models(v2).isdisjoint(MODELS_THE_PLAN_REPLACED)


@pytest.mark.parametrize("name", sorted(DOCUMENT_PAIRS))
def test_the_v1_document_still_states_what_v2_moved_to_the_plan(name: str) -> None:
    """The frozen documents are untouched; only the v0.2 siblings changed."""
    v1, _ = DOCUMENT_PAIRS[name]
    reachable = _reachable_field_names(v1)

    assert not reachable.isdisjoint(FIELDS_THE_V2_CAMPAIGN_DROPPED)


@pytest.mark.parametrize("name", sorted(DOCUMENT_PAIRS))
def test_the_two_documents_are_siblings_rather_than_one_extending_the_other(
    name: str,
) -> None:
    """Decision 0040's shape rule: siblings, never a document and its refinement.

    Substitutability is what is being refused. If one were a subclass of the
    other, a function asking for the v0.1 document would silently accept the
    v0.2 one and read a Campaign fact that is no longer there.
    """
    v1, v2 = DOCUMENT_PAIRS[name]

    assert not issubclass(v2, v1)
    assert not issubclass(v1, v2)
    assert _field_signature(v1) != _field_signature(v2)


def _field_signature(model: type[BaseModel]) -> dict[str, Any]:
    """Return what a model declares, by name and by declared type."""
    return {name: field.annotation for name, field in model.model_fields.items()}


def test_a_v2_document_carries_exactly_the_facts_its_projection_returns() -> None:
    campaign, plan = bound_pair()
    projected: list[tuple[type[BaseModel], Any]] = [
        (ClimbSummaryV2, climb_summary_execution_facts(campaign, plan)),
        (
            CompatibilityResultV2,
            compatibility_result_execution_facts(campaign, plan),
        ),
        (EpisodeReceiptV2, episode_receipt_execution_facts(campaign, plan)),
        (
            ExperimentConfigurationV2,
            experiment_configuration_execution_facts(campaign, plan),
        ),
        (RunRequestV2, run_request_execution_facts(campaign, plan)),
        (UpliftReportV2, uplift_report_execution_facts(campaign, plan)),
    ]

    for model, facts in projected:
        names = {field.name for field in dataclass_fields(facts)}
        assert names <= set(model.model_fields), model.__name__


# ---------------------------------------------------------------------------
# The two receipts reject each other's bytes
# ---------------------------------------------------------------------------


def build_v1_receipt() -> EpisodeReceipt:
    """Build the smallest valid v0.1 episode receipt."""
    return EpisodeReceipt(
        schema_version=EPISODE_RECEIPT_SCHEMA_VERSION,
        id="receipt-under-test",
        run_id="run-under-test",
        campaign_spec_digest=OTHER_DIGEST,
        program_ref=None,
        public_context=None,
        data_policy_digest=POLICY_DIGEST,
        outcome_contract_digest=None,
        evaluation_backend=EvaluationBackendSpec(
            schema_version=EVALUATION_BACKEND_SCHEMA_VERSION,
            kind=EvaluationBackendKind.LOCAL_TECHTREE,
            attestation=AttestationKind.PARTICIPANT,
        ),
        subject_runtime=SubjectRuntimeReceipt(kind="not_executed"),
        variant=ExperimentVariant.CANDIDATE,
        experiment_manifest_digest=MANIFEST_DIGEST,
        episode_id="episode-under-test",
        episode_digest=TASK_DIGEST,
        task_hash=TASK_DIGEST,
        named_traces={},
        score_status=ScoreStatus.DEVELOPMENT_ONLY,
        evidence_status=EvidenceStatus.DEVELOPMENT_ONLY,
        execution_backend="fake",
        artifacts=[],
    )


def build_v2_receipt() -> EpisodeReceiptV2:
    """Build the smallest valid v0.2 episode receipt."""
    campaign, plan = bound_pair()
    facts = episode_receipt_execution_facts(campaign, plan)
    return EpisodeReceiptV2(
        schema_version=EPISODE_RECEIPT_V2_SCHEMA_VERSION,
        id="receipt-under-test",
        run_id="run-under-test",
        campaign_spec_digest=digest_object(campaign),
        program_ref=None,
        public_context=None,
        data_policy_digest=POLICY_DIGEST,
        outcome_contract_digest=None,
        execution_plan_digest=facts.execution_plan_digest,
        execution_location=facts.execution_location,
        subject_runtime=SubjectRuntimeReceipt(kind="not_executed"),
        variant=ExperimentVariant.CANDIDATE,
        experiment_manifest_digest=MANIFEST_DIGEST,
        episode_id="episode-under-test",
        episode_digest=TASK_DIGEST,
        task_hash=TASK_DIGEST,
        named_traces={},
        score_status=ScoreStatus.DEVELOPMENT_ONLY,
        evidence_status=EvidenceStatus.DEVELOPMENT_ONLY,
        executor_kind="fake",
        artifacts=[],
    )


def test_the_v01_receipt_rejects_v02_bytes() -> None:
    with pytest.raises(PydanticValidationError):
        EpisodeReceipt.model_validate_json(build_v2_receipt().model_dump_json())


def test_the_v02_receipt_rejects_v01_bytes() -> None:
    with pytest.raises(PydanticValidationError):
        EpisodeReceiptV2.model_validate_json(build_v1_receipt().model_dump_json())


def build_v1_request() -> RunRequest:
    """Build the smallest valid v0.1 run request."""
    return RunRequest(
        run_id="run-under-test",
        draft_id="draft-under-test",
        draft_digest=OTHER_DIGEST,
        campaign_spec_digest=OTHER_DIGEST,
        program_ref=None,
        public_context=None,
        data_policy_digest=POLICY_DIGEST,
        outcome_contract_digest=None,
        evaluation_backend=EvaluationBackendSpec(
            schema_version=EVALUATION_BACKEND_SCHEMA_VERSION,
            kind=EvaluationBackendKind.LOCAL_TECHTREE,
            attestation=AttestationKind.PARTICIPANT,
        ),
        taskset_lock_digest=None,
        baseline_manifest_digest=MANIFEST_DIGEST,
        candidate_manifest_digest=TASK_DIGEST,
        policy_acknowledgement=PolicyAcknowledgement(
            data_policy_digest=POLICY_DIGEST,
            method="explicit_cli_review",
            acknowledged_at=FIXED_TIME,
        ),
        executor_kind="fake",
        created_at=FIXED_TIME,
    )


def build_v2_request() -> RunRequestV2:
    """Build the smallest valid v0.2 run request."""
    campaign, plan = bound_pair()
    facts = run_request_execution_facts(campaign, plan)
    return RunRequestV2(
        schema_version=RUN_REQUEST_V2_SCHEMA_VERSION,
        run_id="run-under-test",
        draft_id="draft-under-test",
        draft_digest=OTHER_DIGEST,
        campaign_spec_digest=digest_object(campaign),
        program_ref=None,
        public_context=None,
        data_policy_digest=POLICY_DIGEST,
        outcome_contract_digest=None,
        execution_plan_digest=facts.execution_plan_digest,
        taskset_lock_digest=None,
        baseline_manifest_digest=MANIFEST_DIGEST,
        candidate_manifest_digest=TASK_DIGEST,
        policy_acknowledgement=PolicyAcknowledgement(
            data_policy_digest=POLICY_DIGEST,
            method="explicit_cli_review",
            acknowledged_at=FIXED_TIME,
        ),
        executor_kind="fake",
        created_at=FIXED_TIME,
    )


def test_the_v01_request_rejects_v02_bytes() -> None:
    with pytest.raises(PydanticValidationError):
        RunRequest.model_validate_json(build_v2_request().model_dump_json())


def test_the_v02_request_rejects_v01_bytes() -> None:
    with pytest.raises(PydanticValidationError):
        RunRequestV2.model_validate_json(build_v1_request().model_dump_json())


def test_the_v02_request_says_which_document_it_is() -> None:
    assert build_v2_request().schema_version == "techtree.run-request.v2"


def test_the_v02_receipt_still_refuses_to_dress_a_fake_episode_as_real() -> None:
    campaign, plan = bound_pair()
    facts = episode_receipt_execution_facts(campaign, plan)
    fields = build_v2_receipt().model_dump()
    fields["execution_plan_digest"] = facts.execution_plan_digest
    fields["score_status"] = ScoreStatus.VALID

    with pytest.raises(PydanticValidationError, match="development_only"):
        EpisodeReceiptV2(**fields)
