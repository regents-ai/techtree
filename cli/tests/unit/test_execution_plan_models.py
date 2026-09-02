"""The four-plane execution plan and the Campaign that binds it. Plan v0.2.

Two things are being held in place here.

The first is that each plane says one thing and says it consistently: an
execution backend cannot claim a provider it does not have, a subject backend
cannot be a Fabric subject with no adapter, and requested trace coverage
cannot be unfalsifiable. The second, and the reason the plan exists, is that
the Campaign's digest moves when any plane moves. A Campaign whose digest did
not move would let a backend change reinterpret evidence that was already
signed under the old one.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import digest_object, verify_object_digest
from techtree.constants import (
    CAMPAIGN_V2_SCHEMA_VERSION,
    EXECUTION_PLAN_SCHEMA_VERSION,
    PINNED_VERIFIERS_REVISION,
    SUBJECT_IMAGE,
    SUBJECT_IMAGE_PLATFORM_DIGESTS,
)
from techtree.models.base import Digest
from techtree.models.campaign import (
    SKILL_MUTATION_POINTER,
    AgentSpecV2,
    BudgetSpec,
    CampaignContext,
    CampaignMetadata,
    CampaignSpec,
    CampaignSpecV2,
    CampaignTaskset,
    EnvironmentSpec,
    EvidenceRequirementsV2,
    ExecutionSpec,
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
from techtree.models.execution_plan import (
    SUPPORTED_EXECUTION_BACKEND_KINDS,
    SUPPORTED_SUBJECT_BACKEND_KINDS,
    EvaluationEngineRef,
    EvidenceBackendSpec,
    ExecutionBackendKind,
    ExecutionBackendSpec,
    ExecutionProvider,
    ResolvedExecutionPlan,
    SubjectBackendKind,
    SubjectBackendSpec,
)

TASK_DIGEST: Digest = f"sha256:{'11' * 32}"
PROFILE_DIGEST: Digest = f"sha256:{'22' * 32}"
WHEEL_DIGEST: Digest = f"sha256:{'33' * 32}"
POLICY_DIGEST: Digest = f"sha256:{'44' * 32}"
RECEIPT_DIGEST: Digest = f"sha256:{'55' * 32}"
MEMBERSHIP_DIGEST: Digest = f"sha256:{'66' * 32}"
PACKAGE_DIGEST: Digest = f"sha256:{'77' * 32}"


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def engine(**overrides: Any) -> EvaluationEngineRef:
    """Build the evaluation-engine plane, defaulting to the pinned build."""
    fields: dict[str, Any] = {
        "kind": "verifiers",
        "api_generation": "v1",
        "package_version": "0.3.1",
        "source_commit": PINNED_VERIFIERS_REVISION,
        "wheel_digest": WHEEL_DIGEST,
    }
    fields.update(overrides)
    return EvaluationEngineRef(**fields)


def execution(**overrides: Any) -> ExecutionBackendSpec:
    """Build the execution plane, defaulting to what v0.2.0 emits."""
    fields: dict[str, Any] = {
        "kind": ExecutionBackendKind.LOCAL,
        "provider": None,
        "provider_environment_coordinate": None,
    }
    fields.update(overrides)
    return ExecutionBackendSpec(**fields)


def subject(**overrides: Any) -> SubjectBackendSpec:
    """Build the subject plane, defaulting to the direct integration."""
    fields: dict[str, Any] = {
        "kind": SubjectBackendKind.DIRECT,
        "harness_id": "hermes-agent",
        "harness_version": "0.19.0",
        "adapter_id": None,
        "adapter_version": None,
        "adapter_contract_version": None,
    }
    fields.update(overrides)
    return SubjectBackendSpec(**fields)


def evidence(**overrides: Any) -> EvidenceBackendSpec:
    """Build the evidence plane, defaulting to native evidence only."""
    fields: dict[str, Any] = {
        "native_evidence": "required",
        "trace_coverage": "not_requested",
        "coverage_profile_digest": None,
    }
    fields.update(overrides)
    return EvidenceBackendSpec(**fields)


def plan(**overrides: Any) -> ResolvedExecutionPlan:
    """Build a whole plan, defaulting to the one v0.2.0 resolves."""
    fields: dict[str, Any] = {
        "schema_version": EXECUTION_PLAN_SCHEMA_VERSION,
        "kind": "ResolvedExecutionPlan",
        "evaluation": engine(),
        "execution": execution(),
        "subject": subject(),
        "evidence": evidence(),
    }
    fields.update(overrides)
    return ResolvedExecutionPlan(**fields)


def campaign(execution_plan_digest: Digest) -> CampaignSpecV2:
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
            "subject": AgentSpecV2(
                model=ModelSpec(
                    provider="development",
                    model_id="development-placeholder",
                    revision=None,
                    credential_env="TECHTREE_MODEL_API_KEY",
                ),
                sampling=SamplingSpec(temperature=0.0, max_tokens=512),
                harness=HarnessSpecV2(use_bundled_skill=False, skills=[]),
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


# ---------------------------------------------------------------------------
# Plane 1: the evaluation engine
# ---------------------------------------------------------------------------


def test_the_pinned_engine_is_valid() -> None:
    reference = engine()

    assert reference.source_commit == PINNED_VERIFIERS_REVISION
    assert reference.wheel_digest == WHEEL_DIGEST


@pytest.mark.parametrize("moving", ["main", "v0.3.1", "b2e4e81"])
def test_a_moving_engine_name_is_rejected(moving: str) -> None:
    with pytest.raises(PydanticValidationError, match="never a branch or a tag"):
        engine(source_commit=moving)


def test_an_uppercase_commit_is_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="lowercase commit"):
        engine(source_commit=PINNED_VERIFIERS_REVISION.upper())


# ---------------------------------------------------------------------------
# Plane 2: the execution backend
# ---------------------------------------------------------------------------


def test_local_execution_names_no_provider() -> None:
    assert execution().provider is None


def test_local_execution_rejects_a_provider() -> None:
    with pytest.raises(PydanticValidationError, match="has no provider"):
        execution(provider=ExecutionProvider.PRIME)


def test_local_execution_rejects_a_provider_environment() -> None:
    with pytest.raises(PydanticValidationError, match="no provider environment"):
        execution(provider_environment_coordinate="techtree/conformance@0.1.0")


def test_hosted_execution_is_representable() -> None:
    """The hosted vocabulary is in the protocol even though v0.2.0 emits local."""
    hosted = execution(
        kind=ExecutionBackendKind.PRIME_HOSTED,
        provider=ExecutionProvider.PRIME,
        provider_environment_coordinate="techtree/techtree-v02-conformance@0.1.0",
    )

    assert hosted.kind is ExecutionBackendKind.PRIME_HOSTED


def test_hosted_execution_without_a_provider_is_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="must name the prime provider"):
        execution(
            kind=ExecutionBackendKind.PRIME_HOSTED,
            provider=None,
            provider_environment_coordinate="techtree/conformance@0.1.0",
        )


def test_hosted_execution_without_an_environment_is_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="public environment"):
        execution(
            kind=ExecutionBackendKind.PRIME_HOSTED,
            provider=ExecutionProvider.PRIME,
            provider_environment_coordinate=None,
        )


def test_only_local_execution_is_supported_by_this_release() -> None:
    assert frozenset({ExecutionBackendKind.LOCAL}) == SUPPORTED_EXECUTION_BACKEND_KINDS


# ---------------------------------------------------------------------------
# Plane 3: the subject backend
# ---------------------------------------------------------------------------


def test_a_direct_subject_names_only_its_harness() -> None:
    assert subject().adapter_id is None


def test_a_fabric_subject_names_its_adapter() -> None:
    fabric = subject(
        kind=SubjectBackendKind.FABRIC,
        adapter_id="nvidia.fabric.hermes",
        adapter_version="0.2.0",
        adapter_contract_version="fabric.adapter/v1alpha2",
    )

    assert fabric.adapter_id == "nvidia.fabric.hermes"
    assert fabric.harness_id == "hermes-agent"


def test_a_fabric_subject_without_an_adapter_is_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="adapter_contract_version"):
        subject(kind=SubjectBackendKind.FABRIC)


@pytest.mark.parametrize(
    "kind", [SubjectBackendKind.DIRECT, SubjectBackendKind.VERIFIERS_NATIVE]
)
def test_a_subject_with_no_adapter_rejects_adapter_coordinates(
    kind: SubjectBackendKind,
) -> None:
    with pytest.raises(PydanticValidationError, match="has no adapter"):
        subject(kind=kind, adapter_id="nvidia.fabric.hermes")


def test_only_the_direct_subject_is_supported_by_this_release() -> None:
    assert frozenset({SubjectBackendKind.DIRECT}) == SUPPORTED_SUBJECT_BACKEND_KINDS


# ---------------------------------------------------------------------------
# Plane 4: the evidence backend
# ---------------------------------------------------------------------------


def test_native_evidence_alone_names_no_profile() -> None:
    assert evidence().coverage_profile_digest is None


def test_requested_coverage_names_its_profile() -> None:
    requested = evidence(
        trace_coverage="requested", coverage_profile_digest=PROFILE_DIGEST
    )

    assert requested.coverage_profile_digest == PROFILE_DIGEST


def test_requested_coverage_without_a_profile_is_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="unfalsifiable"):
        evidence(trace_coverage="requested")


def test_an_unrequested_profile_is_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="must not name a"):
        evidence(coverage_profile_digest=PROFILE_DIGEST)


# ---------------------------------------------------------------------------
# The planes are independent
# ---------------------------------------------------------------------------


def test_hosted_execution_does_not_require_a_fabric_subject() -> None:
    resolved = plan(
        execution=execution(
            kind=ExecutionBackendKind.PRIME_HOSTED,
            provider=ExecutionProvider.PRIME,
            provider_environment_coordinate="techtree/techtree-v02-conformance@0.1.0",
        )
    )

    assert resolved.subject.kind is SubjectBackendKind.DIRECT


def test_a_fabric_subject_does_not_require_hosted_execution() -> None:
    resolved = plan(
        subject=subject(
            kind=SubjectBackendKind.FABRIC,
            adapter_id="nvidia.fabric.hermes",
            adapter_version="0.2.0",
            adapter_contract_version="fabric.adapter/v1alpha2",
        )
    )

    assert resolved.execution.kind is ExecutionBackendKind.LOCAL


def test_requested_coverage_does_not_change_the_other_planes() -> None:
    resolved = plan(
        evidence=evidence(
            trace_coverage="requested", coverage_profile_digest=PROFILE_DIGEST
        )
    )

    assert resolved.execution.kind is ExecutionBackendKind.LOCAL
    assert resolved.subject.kind is SubjectBackendKind.DIRECT


# ---------------------------------------------------------------------------
# The Campaign binding
# ---------------------------------------------------------------------------


def test_a_campaign_binds_the_plan_it_was_built_from() -> None:
    resolved = plan()
    bound = campaign(digest_object(resolved))

    assert verify_object_digest(resolved, bound.execution_plan_digest)


def test_a_campaign_without_a_plan_digest_is_rejected() -> None:
    document = json.loads(campaign(digest_object(plan())).model_dump_json())
    del document["execution_plan_digest"]

    with pytest.raises(PydanticValidationError, match="execution_plan_digest"):
        CampaignSpecV2.model_validate_json(json.dumps(document))


@pytest.mark.parametrize(
    ("plane", "changed"),
    [
        ("evaluation", lambda: engine(package_version="0.3.2")),
        (
            "execution",
            lambda: execution(
                kind=ExecutionBackendKind.PRIME_HOSTED,
                provider=ExecutionProvider.PRIME,
                provider_environment_coordinate="techtree/conformance@0.1.0",
            ),
        ),
        (
            "subject",
            lambda: subject(
                kind=SubjectBackendKind.FABRIC,
                adapter_id="nvidia.fabric.hermes",
                adapter_version="0.2.0",
                adapter_contract_version="fabric.adapter/v1alpha2",
            ),
        ),
        (
            "evidence",
            lambda: evidence(
                trace_coverage="requested", coverage_profile_digest=PROFILE_DIGEST
            ),
        ),
    ],
)
def test_changing_any_plane_changes_the_campaign_digest(
    plane: str, changed: Any
) -> None:
    """The whole point of the binding: no plane can move in silence."""
    original = plan()
    variant = plan(**{plane: changed()})

    assert digest_object(original) != digest_object(variant)
    assert digest_object(campaign(digest_object(original))) != digest_object(
        campaign(digest_object(variant))
    )


def test_a_plan_that_does_not_match_the_bound_digest_fails_verification() -> None:
    """The tamper case: a swapped plan beside an unchanged Campaign."""
    bound = campaign(digest_object(plan()))
    tampered = plan(subject=subject(harness_version="0.20.1"))

    assert not verify_object_digest(tampered, bound.execution_plan_digest)


def test_a_tampered_campaign_no_longer_matches_its_own_digest() -> None:
    """And the other direction: the plan stands, the Campaign is edited."""
    resolved = plan()
    bound = campaign(digest_object(resolved))
    stored_digest = digest_object(bound)
    tampered = campaign(digest_object(plan(evaluation=engine(package_version="0.3.2"))))

    assert digest_object(tampered) != stored_digest
    assert not verify_object_digest(resolved, tampered.execution_plan_digest)


# ---------------------------------------------------------------------------
# The v0.1 Campaign is untouched
# ---------------------------------------------------------------------------


def test_the_v01_campaign_carries_no_plan_digest() -> None:
    """Frozen evidence recomputes this object's digest, so it gains no fields."""
    assert "execution_plan_digest" not in CampaignSpec.model_fields


def test_the_v02_campaign_drops_what_the_plan_now_owns() -> None:
    """A fact stated in both documents is a fact that can disagree with itself."""
    assert "evaluation_backend" not in CampaignSpecV2.model_fields
    assert set(HarnessSpecV2.model_fields).isdisjoint({"id", "version"})
    assert "verifiers_episode" not in EvidenceRequirementsV2.model_fields


def test_the_two_campaign_documents_are_siblings() -> None:
    """Neither is a refinement of the other, so neither is assignable as it."""
    assert not issubclass(CampaignSpecV2, CampaignSpec)
    assert not issubclass(CampaignSpec, CampaignSpecV2)


def test_the_v01_campaign_rejects_v02_bytes() -> None:
    bound = campaign(digest_object(plan()))

    with pytest.raises(PydanticValidationError):
        CampaignSpec.model_validate_json(bound.model_dump_json())


def test_the_v02_campaign_rejects_v01_bytes() -> None:
    """The reverse direction: nothing coerces a v0.1 document into a v0.2 one."""
    frozen = (
        Path(__file__).resolve().parents[1] / "golden" / "campaign.json"
    ).read_text(encoding="utf-8")

    with pytest.raises(PydanticValidationError):
        CampaignSpecV2.model_validate_json(frozen)


def test_the_v02_campaign_does_not_inherit_the_v01_backend_rule() -> None:
    """The local_techtree rule belongs to the document that has the field."""
    bound = campaign(digest_object(plan()))

    assert "evaluation_backend" not in bound.model_dump_json()
