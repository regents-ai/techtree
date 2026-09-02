"""Configuration compatibility between two Campaigns.

Plan ``docs/plan/v0.2.md``, "Configuration compatibility".

The rule the whole module exists to enforce is that an undeclared difference is
incompatible. Everything else follows from it: a rerun that quietly used a
different model, a larger token budget, one more task, or a second harness is
not a reproduction of the first Campaign, and nobody may call it one because
the policy forgot to mention it.

Every Campaign here is a real, validated ``CampaignSpec`` built from the
synthetic catalog fixture, because that is what the comparison reads. Modified
copies are re-validated rather than trusted: a golden or a stored document is
always a document a model accepted, so a test that compared Campaign-shaped
objects would be testing something the protocol never carries.

Two mechanics are worth stating.

*The pointer-prefix confusion is tested through real configurations.* Declaring
drift at ``/agents/subject/harness/id`` must not admit a change to
``/agents/subject/harness/version``, which is the sibling under the same parent
that a string-prefix test would let through.

*The tamper cases work on stored documents.* A comparison is bytes on disk, and
the attack is not to compute a false verdict but to hand a reader the verdict
from one policy alongside a different, wider policy.
"""

from __future__ import annotations

from typing import Literal

import pytest
from pydantic import ValidationError as PydanticValidationError

from fixtures.drafts.support import SyntheticGraph, synthetic_graph
from techtree.canonical import canonical_json_text, digest_object
from techtree.compatibility import (
    CONFIGURATION_COMPARISON_INVALID,
    assert_comparison_binds_its_policy,
    compare_campaign_configurations,
    observed_drift_paths,
)
from techtree.errors import VerificationError
from techtree.models.campaign import SUBJECT_AGENT, CampaignSpec
from techtree.models.compatibility import (
    COMPARISON_ALGORITHM,
    ConfigurationComparison,
    ConfigurationCompatibilityPolicy,
)
from techtree.pointers import pointer_is_within

HARNESS_ID_POINTER = "/agents/subject/harness/id"
HARNESS_VERSION_POINTER = "/agents/subject/harness/version"
MODEL_ID_POINTER = "/agents/subject/model/model_id"
TASK_HASHES_POINTER = "/taskset/membership/ordered_task_hashes"


@pytest.fixture
def campaign() -> CampaignSpec:
    graph: SyntheticGraph = synthetic_graph()
    return graph.campaign


@pytest.fixture
def twenty_task_campaign(campaign: CampaignSpec) -> CampaignSpec:
    """A Campaign whose committed task list runs past a single-digit index."""
    return with_task_list(campaign, [task_hash(index) for index in range(20)])


def revalidated(campaign: CampaignSpec) -> CampaignSpec:
    """Return the Campaign as a stored document is read: from its own bytes."""
    return CampaignSpec.model_validate_json(canonical_json_text(campaign))


def with_harness(
    campaign: CampaignSpec,
    *,
    harness_id: str | None = None,
    harness_version: str | None = None,
) -> CampaignSpec:
    """Return the Campaign with a different subject harness identity."""
    subject = campaign.agents[SUBJECT_AGENT]
    harness = subject.harness.model_copy(
        update={
            key: value
            for key, value in (("id", harness_id), ("version", harness_version))
            if value is not None
        }
    )
    return revalidated(
        campaign.model_copy(
            update={
                "agents": {
                    SUBJECT_AGENT: subject.model_copy(update={"harness": harness})
                }
            }
        )
    )


def with_model_id(campaign: CampaignSpec, model_id: str) -> CampaignSpec:
    """Return the Campaign with a different subject model."""
    subject = campaign.agents[SUBJECT_AGENT]
    return revalidated(
        campaign.model_copy(
            update={
                "agents": {
                    SUBJECT_AGENT: subject.model_copy(
                        update={
                            "model": subject.model.model_copy(
                                update={"model_id": model_id}
                            )
                        }
                    )
                }
            }
        )
    )


def task_hash(index: int) -> str:
    """Return a distinct, well-formed task hash for one position in a list."""
    return f"sha256:{index:064x}"


def with_task_list(campaign: CampaignSpec, hashes: list[str]) -> CampaignSpec:
    """Return the Campaign committed to exactly these tasks, in this order."""
    taskset = campaign.taskset
    return revalidated(
        campaign.model_copy(
            update={
                "taskset": taskset.model_copy(
                    update={
                        "selection": taskset.selection.model_copy(
                            update={"num_tasks": len(hashes)}
                        ),
                        "membership": taskset.membership.model_copy(
                            update={"ordered_task_hashes": hashes}
                        ),
                    }
                )
            }
        )
    )


def policy_for(
    campaign: CampaignSpec,
    *,
    purpose: Literal["reproduction", "backend_parity"] = "backend_parity",
    allowed: tuple[str, ...] = (),
    required: tuple[str, ...] = (),
) -> ConfigurationCompatibilityPolicy:
    """Return a policy bound to one Campaign."""
    return ConfigurationCompatibilityPolicy(
        purpose=purpose,
        source_campaign_digest=digest_object(campaign),
        required_equal_paths=tuple(sorted(required)),
        allowed_drift_paths=tuple(sorted(allowed)),
        comparison_algorithm=COMPARISON_ALGORITHM,
    )


# ---------------------------------------------------------------------------
# The drift walk
# ---------------------------------------------------------------------------


def test_two_identical_campaigns_drift_nowhere(campaign: CampaignSpec) -> None:
    assert observed_drift_paths(campaign, revalidated(campaign)) == ()


def test_the_walk_reports_the_exact_pointer_that_changed(
    campaign: CampaignSpec,
) -> None:
    candidate = with_harness(campaign, harness_id="fabric-hermes-agent")

    assert observed_drift_paths(campaign, candidate) == (HARNESS_ID_POINTER,)


def test_the_walk_reports_every_changed_pointer_sorted_and_once(
    campaign: CampaignSpec,
) -> None:
    candidate = with_harness(
        campaign, harness_id="fabric-hermes-agent", harness_version="9.9.9"
    )

    paths = observed_drift_paths(campaign, candidate)

    assert paths == (HARNESS_ID_POINTER, HARNESS_VERSION_POINTER)
    assert list(paths) == sorted(set(paths))


# ---------------------------------------------------------------------------
# The verdict
# ---------------------------------------------------------------------------


def test_an_unchanged_campaign_is_an_exact_configuration(
    campaign: CampaignSpec,
) -> None:
    policy = policy_for(campaign, purpose="reproduction")

    comparison = compare_campaign_configurations(
        policy, campaign, revalidated(campaign)
    )

    assert comparison.compatibility == "exact_configuration"
    assert comparison.observed_drift_paths == ()


def test_drift_only_on_declared_paths_is_compatible(campaign: CampaignSpec) -> None:
    candidate = with_harness(
        campaign, harness_id="fabric-hermes-agent", harness_version="9.9.9"
    )
    policy = policy_for(
        campaign,
        allowed=(HARNESS_ID_POINTER, HARNESS_VERSION_POINTER),
        required=(MODEL_ID_POINTER, "/taskset"),
    )

    comparison = compare_campaign_configurations(policy, campaign, candidate)

    assert comparison.compatibility == "compatible_with_declared_drift"
    assert comparison.observed_drift_paths == (
        HARNESS_ID_POINTER,
        HARNESS_VERSION_POINTER,
    )


def test_an_undeclared_difference_is_incompatible(campaign: CampaignSpec) -> None:
    """The rule the whole model exists for."""
    candidate = with_model_id(campaign, "a-quietly-better-model")
    policy = policy_for(campaign, allowed=(HARNESS_ID_POINTER,))

    comparison = compare_campaign_configurations(policy, campaign, candidate)

    assert comparison.compatibility == "incompatible"
    assert comparison.observed_drift_paths == (MODEL_ID_POINTER,)


def test_a_reproduction_policy_declaring_nothing_refuses_any_drift(
    campaign: CampaignSpec,
) -> None:
    candidate = with_harness(campaign, harness_id="fabric-hermes-agent")
    policy = policy_for(campaign, purpose="reproduction")

    comparison = compare_campaign_configurations(policy, campaign, candidate)

    assert comparison.compatibility == "incompatible"


def test_drift_on_a_required_equal_path_is_incompatible(
    campaign: CampaignSpec,
) -> None:
    """Rejected by the undeclared rule, which the non-overlap invariant forces.

    A required-equal path may not lie inside a declared drift path or contain
    one, so a difference falling on it cannot be declared drift either. The
    verdict needs no separate test of those paths, and this pins that the two
    statements really do come out the same way.
    """
    candidate = with_model_id(campaign, "a-quietly-better-model")
    policy = policy_for(
        campaign,
        allowed=(HARNESS_ID_POINTER,),
        required=("/agents/subject/model",),
    )

    comparison = compare_campaign_configurations(policy, campaign, candidate)

    assert comparison.compatibility == "incompatible"
    assert comparison.observed_drift_paths == (MODEL_ID_POINTER,)
    assert not any(
        pointer_is_within(MODEL_ID_POINTER, root) for root in policy.allowed_drift_paths
    )


def test_a_declared_sibling_does_not_admit_the_field_next_to_it(
    campaign: CampaignSpec,
) -> None:
    """``harness/id`` is declared; ``harness/version`` is a different field."""
    candidate = with_harness(campaign, harness_version="9.9.9")
    policy = policy_for(campaign, allowed=(HARNESS_ID_POINTER,))

    comparison = compare_campaign_configurations(policy, campaign, candidate)

    assert comparison.compatibility == "incompatible"
    assert comparison.observed_drift_paths == (HARNESS_VERSION_POINTER,)


def test_a_declared_element_admits_that_element(
    twenty_task_campaign: CampaignSpec,
) -> None:
    hashes = [task_hash(index) for index in range(20)]
    hashes[1] = task_hash(1001)
    candidate = with_task_list(twenty_task_campaign, hashes)
    policy = policy_for(twenty_task_campaign, allowed=(f"{TASK_HASHES_POINTER}/1",))

    comparison = compare_campaign_configurations(
        policy, twenty_task_campaign, candidate
    )

    assert comparison.compatibility == "compatible_with_declared_drift"
    assert comparison.observed_drift_paths == (f"{TASK_HASHES_POINTER}/1",)


@pytest.mark.parametrize("index", range(10, 20))
def test_a_declared_element_does_not_admit_a_longer_index(
    twenty_task_campaign: CampaignSpec, index: int
) -> None:
    """Element 1 is declared. Elements 10 to 19 are ten other tasks.

    Every one of these pointers starts with the declared one as plain text, so
    a containment test written with ``startswith`` alone would call a swapped
    task an approved difference. Ten tasks is ten chances to publish a rerun
    that scored a different taskset.
    """
    hashes = [task_hash(position) for position in range(20)]
    hashes[index] = task_hash(1000 + index)
    candidate = with_task_list(twenty_task_campaign, hashes)
    policy = policy_for(twenty_task_campaign, allowed=(f"{TASK_HASHES_POINTER}/1",))

    comparison = compare_campaign_configurations(
        policy, twenty_task_campaign, candidate
    )

    assert comparison.observed_drift_paths == (f"{TASK_HASHES_POINTER}/{index}",)
    assert comparison.compatibility == "incompatible"


def test_a_declared_root_admits_everything_beneath_it(
    campaign: CampaignSpec,
) -> None:
    candidate = with_harness(
        campaign, harness_id="fabric-hermes-agent", harness_version="9.9.9"
    )
    policy = policy_for(campaign, allowed=("/agents/subject/harness",))

    comparison = compare_campaign_configurations(policy, campaign, candidate)

    assert comparison.compatibility == "compatible_with_declared_drift"


def test_the_comparison_records_both_campaign_digests(
    campaign: CampaignSpec,
) -> None:
    candidate = with_harness(campaign, harness_id="fabric-hermes-agent")
    policy = policy_for(campaign, allowed=(HARNESS_ID_POINTER,))

    comparison = compare_campaign_configurations(policy, campaign, candidate)

    assert comparison.source_campaign_digest == digest_object(campaign)
    assert comparison.candidate_campaign_digest == digest_object(candidate)
    assert comparison.policy_digest == digest_object(policy)


def test_a_policy_written_for_another_campaign_judges_nothing(
    campaign: CampaignSpec,
) -> None:
    """A policy names one source. Judging a different one answers no question."""
    other = with_harness(campaign, harness_id="some-other-harness")
    candidate = revalidated(campaign)
    policy = policy_for(other, allowed=(HARNESS_ID_POINTER,))

    comparison = compare_campaign_configurations(policy, campaign, candidate)

    assert comparison.compatibility == "incompatible"
    assert comparison.observed_drift_paths == ()


# ---------------------------------------------------------------------------
# Tamper cases
# ---------------------------------------------------------------------------


def test_a_comparison_verifies_against_the_policy_it_names(
    campaign: CampaignSpec,
) -> None:
    candidate = with_harness(campaign, harness_id="fabric-hermes-agent")
    policy = policy_for(campaign, allowed=(HARNESS_ID_POINTER,))

    comparison = compare_campaign_configurations(policy, campaign, candidate)

    assert_comparison_binds_its_policy(comparison, policy)


def test_a_swapped_wider_policy_is_refused(campaign: CampaignSpec) -> None:
    """The attack: keep the compatible verdict, hand over different rules."""
    candidate = with_harness(campaign, harness_id="fabric-hermes-agent")
    policy = policy_for(campaign, allowed=(HARNESS_ID_POINTER,))
    comparison = compare_campaign_configurations(policy, campaign, candidate)
    wider = policy_for(campaign, allowed=("/agents",))

    with pytest.raises(VerificationError) as raised:
        assert_comparison_binds_its_policy(comparison, wider)

    assert raised.value.code == CONFIGURATION_COMPARISON_INVALID


def test_a_policy_for_another_source_campaign_is_refused(
    campaign: CampaignSpec,
) -> None:
    """Identical rules, a different anchor. Both halves of the check fire."""
    candidate = with_harness(campaign, harness_id="fabric-hermes-agent")
    policy = policy_for(campaign, allowed=(HARNESS_ID_POINTER,))
    comparison = compare_campaign_configurations(policy, campaign, candidate)
    elsewhere = policy_for(
        with_harness(campaign, harness_id="some-other-harness"),
        allowed=(HARNESS_ID_POINTER,),
    )

    assert elsewhere.allowed_drift_paths == policy.allowed_drift_paths
    assert elsewhere.required_equal_paths == policy.required_equal_paths

    with pytest.raises(VerificationError) as raised:
        assert_comparison_binds_its_policy(comparison, elsewhere)

    assert raised.value.code == CONFIGURATION_COMPARISON_INVALID
    faults = raised.value.details["faults"]
    assert isinstance(faults, list)
    assert len(faults) == 2


def test_a_comparison_moved_onto_another_source_campaign_is_refused(
    campaign: CampaignSpec,
) -> None:
    """The stored comparison is edited, and the policy it names is untouched.

    Swapping the policy is the loud attack. This is the quiet one: keep the
    real policy and the verdict it produced, and re-anchor the comparison to a
    Campaign nobody judged. The policy digest still matches, so only the source
    check stands between that and a reader who believes it.
    """
    candidate = with_harness(campaign, harness_id="fabric-hermes-agent")
    policy = policy_for(campaign, allowed=(HARNESS_ID_POINTER,))
    honest = compare_campaign_configurations(policy, campaign, candidate)
    moved = honest.model_copy(
        update={"source_campaign_digest": digest_object(candidate)}
    )

    assert moved.policy_digest == digest_object(policy)

    with pytest.raises(VerificationError) as raised:
        assert_comparison_binds_its_policy(moved, policy)

    assert raised.value.code == CONFIGURATION_COMPARISON_INVALID
    faults = raised.value.details["faults"]
    assert isinstance(faults, list)
    assert len(faults) == 1


def test_a_stored_comparison_with_an_edited_drift_list_still_names_its_policy(
    campaign: CampaignSpec,
) -> None:
    """Editing the drift list changes the comparison, never the policy digest.

    Which is the point: the binding check proves the rules, and the verdict has
    to be re-derived from the two Campaigns to prove itself.
    """
    candidate = with_model_id(campaign, "a-quietly-better-model")
    policy = policy_for(campaign, allowed=(HARNESS_ID_POINTER,))
    honest = compare_campaign_configurations(policy, campaign, candidate)
    forged = honest.model_copy(
        update={"observed_drift_paths": (), "compatibility": "exact_configuration"}
    )

    assert_comparison_binds_its_policy(forged, policy)
    assert compare_campaign_configurations(policy, campaign, candidate) != forged


# ---------------------------------------------------------------------------
# What the documents refuse to say
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("allowed", "required"),
    [
        # The declared drift path contains the path required to be equal.
        (("/agents",), ("/agents/subject/model",)),
        # And the other way round: the required-equal path contains the path
        # declared free to drift. Either spelling is the same contradiction,
        # and the comparison relies on both being refused.
        ((HARNESS_ID_POINTER,), ("/agents/subject/harness",)),
        # The degenerate case, where the two lists name the same place.
        ((HARNESS_ID_POINTER,), (HARNESS_ID_POINTER,)),
    ],
)
def test_a_policy_cannot_both_fix_and_free_the_same_place(
    campaign: CampaignSpec,
    allowed: tuple[str, ...],
    required: tuple[str, ...],
) -> None:
    with pytest.raises(PydanticValidationError, match="contradicts itself"):
        policy_for(campaign, allowed=allowed, required=required)


def test_a_policy_cannot_repeat_a_path(campaign: CampaignSpec) -> None:
    with pytest.raises(PydanticValidationError, match="must not repeat a pointer"):
        ConfigurationCompatibilityPolicy(
            purpose="reproduction",
            source_campaign_digest=digest_object(campaign),
            required_equal_paths=(),
            allowed_drift_paths=(HARNESS_ID_POINTER, HARNESS_ID_POINTER),
            comparison_algorithm=COMPARISON_ALGORITHM,
        )


def test_a_policy_cannot_spell_one_rule_set_two_ways(campaign: CampaignSpec) -> None:
    with pytest.raises(PydanticValidationError, match="must be sorted"):
        ConfigurationCompatibilityPolicy(
            purpose="reproduction",
            source_campaign_digest=digest_object(campaign),
            required_equal_paths=(),
            allowed_drift_paths=(HARNESS_VERSION_POINTER, HARNESS_ID_POINTER),
            comparison_algorithm=COMPARISON_ALGORITHM,
        )


@pytest.mark.parametrize("path", ["", "agents/subject", "/agents/~2subject"])
def test_a_policy_path_must_be_a_json_pointer(
    campaign: CampaignSpec, path: str
) -> None:
    with pytest.raises(PydanticValidationError):
        ConfigurationCompatibilityPolicy(
            purpose="reproduction",
            source_campaign_digest=digest_object(campaign),
            required_equal_paths=(),
            allowed_drift_paths=(path,),
            comparison_algorithm=COMPARISON_ALGORITHM,
        )


def test_an_exact_configuration_cannot_list_drift(campaign: CampaignSpec) -> None:
    digest = digest_object(campaign)

    with pytest.raises(PydanticValidationError, match="no observed drift"):
        ConfigurationComparison(
            policy_digest=digest,
            source_campaign_digest=digest,
            candidate_campaign_digest=digest,
            observed_drift_paths=(HARNESS_ID_POINTER,),
            compatibility="exact_configuration",
        )


def test_declared_drift_has_to_say_what_drifted(campaign: CampaignSpec) -> None:
    digest = digest_object(campaign)

    with pytest.raises(PydanticValidationError, match="which declared paths"):
        ConfigurationComparison(
            policy_digest=digest,
            source_campaign_digest=digest,
            candidate_campaign_digest=digest,
            observed_drift_paths=(),
            compatibility="compatible_with_declared_drift",
        )


def test_a_comparison_cannot_repeat_or_unsort_its_drift(
    campaign: CampaignSpec,
) -> None:
    digest = digest_object(campaign)

    with pytest.raises(PydanticValidationError, match="must be sorted"):
        ConfigurationComparison(
            policy_digest=digest,
            source_campaign_digest=digest,
            candidate_campaign_digest=digest,
            observed_drift_paths=(HARNESS_VERSION_POINTER, HARNESS_ID_POINTER),
            compatibility="incompatible",
        )
