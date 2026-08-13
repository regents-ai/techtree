"""The Campaign kernel and its public wrapper. Spec 11.5, 11.6, 11.8, 27.2.

The tests read the committed golden documents, change one thing, and check that
the change is either accepted or refused. Working from the goldens means these
tests exercise exactly the bytes the protocol ships, and a model change that
would silently widen the contract shows up here rather than in a schema diff
nobody reads.

The theme throughout is separation. A Campaign must not be able to hold public
product policy; a Climb must not be able to hold scientific configuration; and
a comparison must not be able to differ anywhere except the one place the
mutation contract names.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import digest_object, sha256_digest_bytes
from techtree.errors import PolicyError
from techtree.models.campaign import SKILL_MUTATION_POINTER, CampaignSpec
from techtree.models.climb import ClimbManifest, ResolvedClimb
from techtree.models.data_policy import DataPolicy
from techtree.models.episode_receipt import EpisodeReceipt
from techtree.models.experiment import (
    ExperimentConfiguration,
    ExperimentManifest,
    ExperimentVariant,
)
from techtree.models.run import RunRequest
from techtree.models.skill import SubmissionDraft
from techtree.models.uplift_report import UpliftReport
from techtree.models.validation import TasksetValidationReceipt

GOLDEN_DIRECTORY = Path(__file__).resolve().parents[1] / "golden"


def golden(name: str) -> dict[str, Any]:
    """Load one committed golden fixture as a mutable JSON document."""
    text = (GOLDEN_DIRECTORY / f"{name}.json").read_text(encoding="utf-8")
    document: dict[str, Any] = json.loads(text)
    return document


def campaign(document: dict[str, Any]) -> CampaignSpec:
    """Validate a Campaign document the way stored bytes are validated."""
    return CampaignSpec.model_validate_json(json.dumps(document))


def climb(document: dict[str, Any]) -> ClimbManifest:
    """Validate a Climb document the way stored bytes are validated."""
    return ClimbManifest.model_validate_json(json.dumps(document))


def experiment(document: dict[str, Any]) -> ExperimentManifest:
    """Validate an experiment manifest the way stored bytes are validated."""
    return ExperimentManifest.model_validate_json(json.dumps(document))


# ---------------------------------------------------------------------------
# The kernel boundary
# ---------------------------------------------------------------------------


def test_development_campaign_is_valid() -> None:
    spec = campaign(golden("campaign"))

    assert spec.metadata.purpose == "component_uplift"
    assert spec.taskset.selection.shuffle is False
    assert spec.taskset.selection.num_rollouts == 1
    assert spec.subject.harness.skills == []
    assert spec.subject.harness.use_bundled_skill is False
    assert spec.evidence.runtime_evidence == "not_required"


@pytest.mark.parametrize(
    "field",
    ["slug", "leaderboard", "publication", "candidate_policy", "opens_at"],
)
def test_campaign_rejects_public_policy_fields(field: str) -> None:
    document = golden("campaign")
    document[field] = "anything"

    with pytest.raises(PydanticValidationError, match="Extra inputs"):
        campaign(document)


@pytest.mark.parametrize(
    "field",
    ["agents", "taskset", "scoring", "mutation_contract", "execution"],
)
def test_climb_rejects_scientific_fields(field: str) -> None:
    document = golden("climb")
    document[field] = "anything"

    with pytest.raises(PydanticValidationError, match="Extra inputs"):
        climb(document)


def test_campaign_requires_a_data_policy_digest() -> None:
    document = golden("campaign")
    del document["data_policy_digest"]

    with pytest.raises(PydanticValidationError, match="data_policy_digest"):
        campaign(document)


def test_campaign_rejects_a_malformed_data_policy_digest() -> None:
    document = golden("campaign")
    document["data_policy_digest"] = "not-a-digest"

    with pytest.raises(PydanticValidationError):
        campaign(document)


# ---------------------------------------------------------------------------
# The comparison contract
# ---------------------------------------------------------------------------


def test_campaign_requires_exactly_one_subject_agent() -> None:
    document = golden("campaign")
    document["agents"]["opponent"] = document["agents"]["subject"]

    with pytest.raises(PydanticValidationError, match="exactly one agent"):
        campaign(document)


def test_campaign_rejects_a_renamed_agent() -> None:
    document = golden("campaign")
    document["agents"] = {"assistant": document["agents"]["subject"]}

    with pytest.raises(PydanticValidationError, match="exactly one agent"):
        campaign(document)


def test_campaign_rejects_shuffle_true() -> None:
    document = golden("campaign")
    document["taskset"]["selection"]["shuffle"] = True

    with pytest.raises(PydanticValidationError):
        campaign(document)


def test_campaign_rejects_more_than_one_rollout() -> None:
    document = golden("campaign")
    document["taskset"]["selection"]["num_rollouts"] = 2

    with pytest.raises(PydanticValidationError, match="num_rollouts must be 1"):
        campaign(document)


def test_campaign_rejects_a_baseline_that_already_carries_a_skill() -> None:
    document = golden("campaign")
    document["agents"]["subject"]["harness"]["skills"] = [
        {
            "digest": sha256_digest_bytes(b"skill"),
            "media_type": "application/zip",
            "size": 10,
            "relative_path": None,
        }
    ]

    with pytest.raises(PydanticValidationError, match="carries no skills"):
        campaign(document)


def test_campaign_rejects_a_bundled_skill() -> None:
    document = golden("campaign")
    document["agents"]["subject"]["harness"]["use_bundled_skill"] = True

    with pytest.raises(PydanticValidationError, match="use_bundled_skill is false"):
        campaign(document)


def test_campaign_allows_exactly_one_difference() -> None:
    assert campaign(golden("campaign")).mutation_contract.allowed_differences == [
        SKILL_MUTATION_POINTER
    ]


@pytest.mark.parametrize(
    "allowed",
    [
        [],
        ["/agents/subject/model"],
        ["/agents/subject/harness/skills", "/agents/subject/sampling"],
    ],
)
def test_campaign_rejects_any_other_allowed_difference(allowed: list[str]) -> None:
    document = golden("campaign")
    document["mutation_contract"]["allowed_differences"] = allowed

    with pytest.raises(PydanticValidationError, match="only allowed difference"):
        campaign(document)


def test_campaign_rejects_a_membership_that_misses_a_task() -> None:
    document = golden("campaign")
    document["taskset"]["membership"]["ordered_task_hashes"].pop()

    with pytest.raises(PydanticValidationError, match="membership commits"):
        campaign(document)


def test_campaign_rejects_a_repeated_task() -> None:
    document = golden("campaign")
    hashes = document["taskset"]["membership"]["ordered_task_hashes"]
    hashes[1] = hashes[0]

    with pytest.raises(PydanticValidationError, match="must be unique"):
        campaign(document)


def test_campaign_rejects_a_non_local_evaluation_backend() -> None:
    document = golden("campaign")
    document["evaluation_backend"]["kind"] = "prime_lab"
    document["evaluation_backend"]["attestation"] = "platform"
    document["evaluation_backend"]["workspace_ref"] = "workspace/abc"

    with pytest.raises(PydanticValidationError, match="local_techtree only"):
        campaign(document)


def test_campaign_rejects_required_runtime_evidence() -> None:
    document = golden("campaign")
    document["evidence"]["runtime_evidence"] = "required"

    with pytest.raises(PydanticValidationError, match="not collected before WP6"):
        campaign(document)


@pytest.mark.parametrize(
    "value",
    ["sk-live-abcdefghijklmnop", "techtree_model_api_key", "AB", "A KEY"],
)
def test_campaign_rejects_an_unsafe_credential_env(value: str) -> None:
    document = golden("campaign")
    document["agents"]["subject"]["model"]["credential_env"] = value

    with pytest.raises(PydanticValidationError, match="credential_env must be"):
        campaign(document)


def test_campaign_runtime_stays_docker() -> None:
    document = golden("campaign")
    document["agents"]["subject"]["runtime"]["type"] = "process"

    with pytest.raises(PydanticValidationError):
        campaign(document)


# ---------------------------------------------------------------------------
# Optional forward-compatible pointers
# ---------------------------------------------------------------------------


def test_program_ref_is_optional() -> None:
    assert campaign(golden("campaign")).context.program_ref is None


def test_program_ref_may_be_present() -> None:
    document = golden("campaign")
    document["context"]["program_ref"] = {"id": "program-1", "version": 1}

    reference = campaign(document).context.program_ref

    assert reference is not None
    assert reference.id == "program-1"


def test_outcome_contract_digest_is_optional() -> None:
    assert campaign(golden("campaign")).context.outcome_contract_digest is None


def test_outcome_contract_digest_may_be_present() -> None:
    document = golden("campaign")
    document["context"]["outcome_contract_digest"] = sha256_digest_bytes(b"outcome")

    assert campaign(document).context.outcome_contract_digest is not None


def test_public_context_is_optional_on_execution_artifacts() -> None:
    document = golden("experiment-baseline")
    document["public_context"] = None

    assert experiment(document).public_context is None


def test_execution_artifacts_anchor_on_the_campaign_digest() -> None:
    baseline = experiment(golden("experiment-baseline"))
    candidate = experiment(golden("experiment-candidate"))
    spec_digest = digest_object(campaign(golden("campaign")))

    assert baseline.campaign_spec_digest == spec_digest
    assert candidate.campaign_spec_digest == spec_digest


# ---------------------------------------------------------------------------
# Digest sensitivity
# ---------------------------------------------------------------------------


def test_one_field_change_changes_the_campaign_digest() -> None:
    original = campaign(golden("campaign"))
    document = golden("campaign")
    document["scoring"]["minimum_absolute_delta"] = 0.06

    assert digest_object(campaign(document)) != digest_object(original)


def test_reparsing_the_same_document_gives_the_same_digest() -> None:
    assert digest_object(campaign(golden("campaign"))) == digest_object(
        campaign(golden("campaign"))
    )


# ---------------------------------------------------------------------------
# The public wrapper
# ---------------------------------------------------------------------------


def test_development_climb_is_valid() -> None:
    manifest = climb(golden("climb"))

    assert manifest.metadata.slug == "procedure-transfer-dev"
    assert manifest.metadata.status == "development"
    assert manifest.publication.proof_grade == "development_only"
    assert manifest.leaderboard.enabled is False


def test_development_climb_cannot_enable_a_leaderboard() -> None:
    document = golden("climb")
    document["leaderboard"]["enabled"] = True

    with pytest.raises(PydanticValidationError, match="cannot enable a leaderboard"):
        climb(document)


def test_climb_rejects_a_schedule_that_closes_before_it_opens() -> None:
    document = golden("climb")
    document["metadata"]["opens_at"] = "2026-02-01T00:00:00Z"
    document["metadata"]["closes_at"] = "2026-01-01T00:00:00Z"

    with pytest.raises(PydanticValidationError, match="closes_at must be after"):
        climb(document)


# ---------------------------------------------------------------------------
# The resolved graph
# ---------------------------------------------------------------------------


def resolved(
    climb_document: dict[str, Any] | None = None,
    policy_document: dict[str, Any] | None = None,
) -> ResolvedClimb:
    """Assemble the development graph, optionally with one object replaced.

    The graph is relinked after the replacement so that its digest edges stay
    correct. Without that, every test about a rights contradiction would be
    intercepted by the edge check and prove nothing about rights.
    """
    policy = DataPolicy.model_validate_json(
        json.dumps(policy_document or golden("data-policy"))
    )
    receipt = TasksetValidationReceipt.model_validate_json(
        json.dumps(golden("taskset-validation-receipt"))
    )
    campaign_document = golden("campaign")
    campaign_document["data_policy_digest"] = digest_object(policy)
    spec = campaign(campaign_document)

    manifest_document = climb_document or golden("climb")
    manifest_document["campaign_spec_digest"] = digest_object(spec)
    manifest = climb(manifest_document)

    return ResolvedClimb(
        climb=manifest,
        climb_digest=digest_object(manifest),
        campaign=spec,
        campaign_digest=digest_object(spec),
        data_policy=policy,
        data_policy_digest=digest_object(policy),
        publisher_validation=receipt,
        publisher_validation_digest=digest_object(receipt),
    )


def test_the_development_graph_resolves() -> None:
    graph = resolved()

    assert graph.climb.campaign_spec_digest == graph.campaign_digest
    assert graph.campaign.data_policy_digest == graph.data_policy_digest
    assert (
        graph.campaign.taskset.validation_receipt_digest
        == graph.publisher_validation_digest
    )


def test_a_climb_pointing_at_another_campaign_is_rejected() -> None:
    graph = resolved()

    with pytest.raises(PydanticValidationError, match="different Campaign"):
        ResolvedClimb(
            climb=graph.climb,
            climb_digest=graph.climb_digest,
            campaign=graph.campaign,
            campaign_digest=sha256_digest_bytes(b"another campaign"),
            data_policy=graph.data_policy,
            data_policy_digest=graph.data_policy_digest,
            publisher_validation=graph.publisher_validation,
            publisher_validation_digest=graph.publisher_validation_digest,
        )


def test_a_campaign_pointing_at_another_data_policy_is_rejected() -> None:
    graph = resolved()

    with pytest.raises(PydanticValidationError, match="different DataPolicy"):
        ResolvedClimb(
            climb=graph.climb,
            climb_digest=graph.climb_digest,
            campaign=graph.campaign,
            campaign_digest=graph.campaign_digest,
            data_policy=graph.data_policy,
            data_policy_digest=sha256_digest_bytes(b"another policy"),
            publisher_validation=graph.publisher_validation,
            publisher_validation_digest=graph.publisher_validation_digest,
        )


def test_a_campaign_pointing_at_another_validation_receipt_is_rejected() -> None:
    graph = resolved()

    with pytest.raises(PydanticValidationError, match="different validation receipt"):
        ResolvedClimb(
            climb=graph.climb,
            climb_digest=graph.climb_digest,
            campaign=graph.campaign,
            campaign_digest=graph.campaign_digest,
            data_policy=graph.data_policy,
            data_policy_digest=graph.data_policy_digest,
            publisher_validation=graph.publisher_validation,
            publisher_validation_digest=sha256_digest_bytes(b"another receipt"),
        )


def test_candidate_constraints_must_match_the_mutation_bounds() -> None:
    document = golden("climb")
    document["candidate_policy"]["constraints"]["max_skills"] = 3

    with pytest.raises(PydanticValidationError, match="mutation bounds"):
        resolved(climb_document=document)


def test_a_public_policy_contradiction_fails_the_graph() -> None:
    document = golden("data-policy")
    document["derived_artifacts"]["uplift_report"] = "private"

    with pytest.raises(PolicyError, match="uplift report"):
        resolved(policy_document=document)


# ---------------------------------------------------------------------------
# Experiment variants
# ---------------------------------------------------------------------------


def test_baseline_and_candidate_differ_only_in_the_skill_list() -> None:
    baseline = experiment(golden("experiment-baseline"))
    candidate = experiment(golden("experiment-candidate"))

    baseline_fields = baseline.configuration.model_dump()
    candidate_fields = candidate.configuration.model_dump()
    baseline_subject = baseline_fields["agents"]["subject"]["harness"].pop("skills")
    candidate_subject = candidate_fields["agents"]["subject"]["harness"].pop("skills")

    assert baseline_fields == candidate_fields
    assert baseline_subject == []
    assert len(candidate_subject) == 1


def test_baseline_cannot_carry_a_candidate_skill() -> None:
    document = golden("experiment-candidate")
    document["variant"] = ExperimentVariant.BASELINE.value

    with pytest.raises(PydanticValidationError, match="carries no candidate skill"):
        experiment(document)


def test_candidate_must_carry_exactly_one_skill() -> None:
    document = golden("experiment-baseline")
    document["variant"] = ExperimentVariant.CANDIDATE.value

    with pytest.raises(PydanticValidationError, match="exactly one skill"):
        experiment(document)


def test_experiment_configuration_digest_matches_its_configuration() -> None:
    for name in ("experiment-baseline", "experiment-candidate"):
        manifest = experiment(golden(name))
        assert digest_object(manifest.configuration) == manifest.configuration_digest


# ---------------------------------------------------------------------------
# The kernel anchor, checked structurally
# ---------------------------------------------------------------------------

#: Artifacts that name the Campaign, the rights policy, and the optional public
#: context directly. ``ExperimentManifest`` keeps the policy and the outcome
#: contract inside its comparable ``configuration``, so it is checked
#: separately below rather than being bent to fit this list.
DIRECT_EXECUTION_ARTIFACTS = [
    SubmissionDraft,
    EpisodeReceipt,
    UpliftReport,
    RunRequest,
]


def optional_fields(model: type[BaseModel]) -> set[str]:
    """Return the names of fields that accept ``None``."""
    return {
        name
        for name, field in model.model_fields.items()
        if type(None) in getattr(field.annotation, "__args__", ())
    }


@pytest.mark.parametrize(
    "model", DIRECT_EXECUTION_ARTIFACTS, ids=lambda model: model.__name__
)
def test_every_execution_artifact_anchors_on_the_campaign(
    model: type[BaseModel],
) -> None:
    """Artifacts reference the Campaign digest, never the public Climb."""
    fields = model.model_fields

    assert fields["campaign_spec_digest"].is_required()
    assert fields["data_policy_digest"].is_required()
    assert "climb_digest" not in fields


@pytest.mark.parametrize(
    "model", DIRECT_EXECUTION_ARTIFACTS, ids=lambda model: model.__name__
)
def test_every_execution_artifact_treats_the_climb_as_optional_context(
    model: type[BaseModel],
) -> None:
    assert {
        "public_context",
        "program_ref",
        "outcome_contract_digest",
    } <= optional_fields(model)


def test_the_experiment_manifest_anchors_through_its_configuration() -> None:
    """The comparable half carries the policy; the manifest carries the anchor."""
    assert ExperimentManifest.model_fields["campaign_spec_digest"].is_required()
    assert {"public_context", "program_ref"} <= optional_fields(ExperimentManifest)

    configuration = ExperimentConfiguration.model_fields
    assert configuration["data_policy_digest"].is_required()
    assert "outcome_contract_digest" in optional_fields(ExperimentConfiguration)
