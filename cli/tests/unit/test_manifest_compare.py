"""The controlled-comparison proof. Spec PR6 §6.5, §6.11, and spec §27.2.

Every negative case in this file is a way of making the candidate differ from
the baseline somewhere it must not, and every one of them has to be caught. The
list is not decorative: each entry is a real way an uplift number could be
manufactured — a slightly better model, a slightly larger token budget, a
different reward, one extra task, a bundled skill quietly switched on — and the
comparison is the only thing standing between that and a published result.

Two mechanics are worth explaining.

Mutated manifests are built with ``model_copy``. The model itself refuses a
baseline with a skill and a candidate without one, and that is exactly why the
comparison has to be tested against manifests the model would not have built:
a document can also be read off a disk, and the comparison is what audits it.

Pointer-prefix confusion is tested twice. Once directly on
:func:`pointer_is_within`, where ``skills_extra`` is the sibling an attacker
would add, and once through a real diff of a sibling field under the same
parent, which is the same mistake made by a real configuration.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fixtures.drafts.support import SyntheticGraph, synthetic_graph
from techtree.canonical import digest_object
from techtree.constants import SKILL_SCHEMA_VERSION
from techtree.errors import VerificationError
from techtree.manifests.builder import (
    build_baseline_manifest,
    build_candidate_manifest,
    build_skill_reference,
    skill_content_digest,
)
from techtree.manifests.compare import (
    assert_controlled_comparison,
    compare_manifests,
    diff_values,
    json_pointer_escape,
    pointer_is_within,
)
from techtree.models.base import ArtifactRef, JsonValue
from techtree.models.campaign import (
    SKILL_MUTATION_POINTER,
    MutationContract,
    MutationKind,
    PublicContext,
)
from techtree.models.experiment import (
    ExperimentConfiguration,
    ExperimentManifest,
    ExperimentVariant,
    ManifestComparison,
)
from techtree.models.skill import SkillArtifact, SkillFile

PINNED_TIME = datetime(2026, 1, 1, tzinfo=UTC)

SKILLS_POINTER = "/agents/subject/harness/skills"


@pytest.fixture
def graph() -> SyntheticGraph:
    return synthetic_graph()


def artifact(name: str = "candidate-under-test", fill: str = "a") -> SkillArtifact:
    """Return a valid artifact; ``fill`` makes two of them differ."""
    files = [
        SkillFile(
            path="SKILL.md",
            media_type="text/markdown",
            size=64,
            digest=f"sha256:{fill * 64}",
        )
    ]
    return SkillArtifact(
        schema_version=SKILL_SCHEMA_VERSION,
        name=name,
        root_digest=skill_content_digest(files),
        archive_digest=f"sha256:{'c' * 64}",
        files=files,
        source_kind="manual",
        parent_skill_digest=None,
    )


def pair(graph: SyntheticGraph) -> tuple[ExperimentManifest, ExperimentManifest]:
    """Return the baseline and candidate a correct preparation would build."""
    context = graph.public_context
    return (
        build_baseline_manifest(
            campaign=graph.campaign,
            campaign_digest=graph.campaign_digest,
            public_context=context,
            created_at=PINNED_TIME,
        ),
        build_candidate_manifest(
            campaign=graph.campaign,
            campaign_digest=graph.campaign_digest,
            skill=artifact(),
            public_context=context,
            created_at=PINNED_TIME,
        ),
    )


def compare(
    graph: SyntheticGraph,
    baseline: ExperimentManifest,
    candidate: ExperimentManifest,
) -> ManifestComparison:
    return compare_manifests(baseline, candidate, graph.campaign.mutation_contract)


def with_configuration(
    manifest: ExperimentManifest, configuration: ExperimentConfiguration
) -> ExperimentManifest:
    """Return a manifest carrying a different configuration, honestly digested.

    ``model_copy`` is what lets a test build a document the model would refuse.
    The digest is recomputed so that the manifest still describes itself; a
    stale digest would fail the comparison for the wrong reason.
    """
    return manifest.model_copy(
        update={
            "configuration": configuration,
            "configuration_digest": digest_object(configuration),
        }
    )


def with_subject(
    manifest: ExperimentManifest, **agent_updates: object
) -> ExperimentManifest:
    """Return a manifest whose subject agent has been altered."""
    configuration = manifest.configuration
    subject = configuration.agents["subject"].model_copy(update=agent_updates)
    return with_configuration(
        manifest,
        configuration.model_copy(
            update={"agents": {**configuration.agents, "subject": subject}}
        ),
    )


def with_harness(
    manifest: ExperimentManifest, **harness_updates: object
) -> ExperimentManifest:
    harness = manifest.configuration.agents["subject"].harness.model_copy(
        update=harness_updates
    )
    return with_subject(manifest, harness=harness)


# ---------------------------------------------------------------------------
# Pointers
# ---------------------------------------------------------------------------


def test_json_pointers_escape_tilde_before_solidus() -> None:
    assert json_pointer_escape("a/b") == "a~1b"
    assert json_pointer_escape("a~b") == "a~0b"
    assert json_pointer_escape("a~/b") == "a~0~1b"
    assert json_pointer_escape("plain") == "plain"


def test_containment_is_a_token_boundary_and_not_a_string_prefix() -> None:
    """A sibling named ``skills_extra`` is not inside ``skills``."""
    assert pointer_is_within(SKILLS_POINTER, SKILLS_POINTER)
    assert pointer_is_within(f"{SKILLS_POINTER}/0", SKILLS_POINTER)
    assert pointer_is_within(f"{SKILLS_POINTER}/0/digest", SKILLS_POINTER)
    assert not pointer_is_within(f"{SKILLS_POINTER}_extra", SKILLS_POINTER)
    assert not pointer_is_within(f"{SKILLS_POINTER}_extra/0", SKILLS_POINTER)
    assert not pointer_is_within("/agents/subject/harness", SKILLS_POINTER)


def test_a_diff_reports_leaves_in_a_stable_order() -> None:
    baseline: JsonValue = {"b": 1, "a": {"y": 1, "x": 1}, "c": [1, 2]}
    candidate: JsonValue = {"b": 2, "a": {"y": 2, "x": 2}, "c": [1, 3]}

    pointers = [item.pointer for item in diff_values(baseline, candidate)]

    assert pointers == ["/a/x", "/a/y", "/b", "/c/1"]


def test_a_diff_reports_added_and_removed_elements_at_their_index() -> None:
    added = diff_values([], ["one"])
    removed = diff_values(["one"], [])

    assert added[0].pointer == "/0"
    assert added[0].baseline is None
    assert added[0].candidate == "one"
    assert removed[0].candidate is None


def test_a_diff_does_not_confuse_a_boolean_with_a_number() -> None:
    """``True == 1`` in Python and not in JSON, and JSON is what is compared."""
    assert diff_values(True, 1)
    assert diff_values(1, 1.0) == []
    assert diff_values(1, 2)


# ---------------------------------------------------------------------------
# The controlled case
# ---------------------------------------------------------------------------


def test_exactly_one_inserted_skill_is_controlled(graph: SyntheticGraph) -> None:
    baseline, candidate = pair(graph)
    comparison = compare(graph, baseline, candidate)

    assert comparison.controlled
    assert comparison.violations == []
    assert comparison.allowed_differences == [SKILL_MUTATION_POINTER]
    assert all(
        pointer_is_within(difference.pointer, SKILL_MUTATION_POINTER)
        for difference in comparison.differences
    )
    assert comparison.differences
    assert_controlled_comparison(comparison)


def test_the_comparison_records_the_configuration_digests(
    graph: SyntheticGraph,
) -> None:
    baseline, candidate = pair(graph)
    comparison = compare(graph, baseline, candidate)

    assert comparison.baseline_configuration_digest == baseline.configuration_digest
    assert comparison.candidate_configuration_digest == candidate.configuration_digest
    assert (
        comparison.baseline_configuration_digest
        != comparison.candidate_configuration_digest
    )


def test_differences_are_sorted_by_pointer(graph: SyntheticGraph) -> None:
    baseline, candidate = pair(graph)
    mutated = with_subject(
        candidate,
        sampling=candidate.configuration.agents["subject"].sampling.model_copy(
            update={"temperature": 1.0}
        ),
    )
    pointers = [item.pointer for item in compare(graph, baseline, mutated).differences]

    assert pointers == sorted(pointers)


# ---------------------------------------------------------------------------
# Every unauthorized mutation
# ---------------------------------------------------------------------------


def test_a_changed_subject_model_is_rejected(graph: SyntheticGraph) -> None:
    baseline, candidate = pair(graph)
    mutated = with_subject(
        candidate,
        model=candidate.configuration.agents["subject"].model.model_copy(
            update={"model_id": "a-better-model"}
        ),
    )

    comparison = compare(graph, baseline, mutated)

    assert not comparison.controlled
    assert any("/agents/subject/model/model_id" in v for v in comparison.violations)


def test_changed_sampling_is_rejected(graph: SyntheticGraph) -> None:
    baseline, candidate = pair(graph)
    mutated = with_subject(
        candidate,
        sampling=candidate.configuration.agents["subject"].sampling.model_copy(
            update={"max_tokens": 4096}
        ),
    )

    assert not compare(graph, baseline, mutated).controlled


def test_a_changed_harness_version_is_rejected(graph: SyntheticGraph) -> None:
    baseline, candidate = pair(graph)
    mutated = with_harness(candidate, version="0.20.0")

    comparison = compare(graph, baseline, mutated)

    assert not comparison.controlled
    assert any("/agents/subject/harness/version" in v for v in comparison.violations)


def test_switching_on_the_bundled_skill_is_rejected(graph: SyntheticGraph) -> None:
    """A sibling of the allowed pointer is not inside the allowed pointer."""
    baseline, candidate = pair(graph)
    mutated = with_harness(candidate, use_bundled_skill=True)

    comparison = compare(graph, baseline, mutated)

    assert not comparison.controlled
    assert any(
        "/agents/subject/harness/use_bundled_skill" in violation
        for violation in comparison.violations
    )


def test_a_changed_runtime_image_is_rejected(graph: SyntheticGraph) -> None:
    baseline, candidate = pair(graph)
    mutated = with_subject(
        candidate,
        runtime=candidate.configuration.agents["subject"].runtime.model_copy(
            update={"image": "something-else:latest"}
        ),
    )

    assert not compare(graph, baseline, mutated).controlled


def test_a_changed_taskset_is_rejected(graph: SyntheticGraph) -> None:
    baseline, candidate = pair(graph)
    taskset = candidate.configuration.taskset
    mutated = with_configuration(
        candidate,
        candidate.configuration.model_copy(
            update={
                "taskset": taskset.model_copy(
                    update={
                        "selection": taskset.selection.model_copy(
                            update={"num_tasks": 2}
                        )
                    }
                )
            }
        ),
    )

    comparison = compare(graph, baseline, mutated)

    assert not comparison.controlled
    assert any("/taskset/selection/num_tasks" in v for v in comparison.violations)


def test_changed_scoring_is_rejected(graph: SyntheticGraph) -> None:
    baseline, candidate = pair(graph)
    mutated = with_configuration(
        candidate,
        candidate.configuration.model_copy(
            update={
                "scoring": candidate.configuration.scoring.model_copy(
                    update={"primary_reward": "a_kinder_reward"}
                )
            }
        ),
    )

    assert not compare(graph, baseline, mutated).controlled


def test_a_changed_data_policy_digest_is_rejected(graph: SyntheticGraph) -> None:
    baseline, candidate = pair(graph)
    mutated = with_configuration(
        candidate,
        candidate.configuration.model_copy(
            update={"data_policy_digest": f"sha256:{'9' * 64}"}
        ),
    )

    comparison = compare(graph, baseline, mutated)

    assert not comparison.controlled
    assert any("different DataPolicy" in v for v in comparison.violations)


def test_a_changed_outcome_contract_digest_is_rejected(
    graph: SyntheticGraph,
) -> None:
    baseline, candidate = pair(graph)
    mutated = with_configuration(
        candidate,
        candidate.configuration.model_copy(
            update={"outcome_contract_digest": f"sha256:{'8' * 64}"}
        ),
    )

    comparison = compare(graph, baseline, mutated)

    assert not comparison.controlled
    assert any("different OutcomeContract" in v for v in comparison.violations)


def test_a_changed_evaluation_backend_is_rejected(graph: SyntheticGraph) -> None:
    baseline, candidate = pair(graph)
    backend = candidate.configuration.evaluation_backend
    mutated = with_configuration(
        candidate,
        candidate.configuration.model_copy(
            update={
                "evaluation_backend": backend.model_copy(
                    update={"workspace_ref": "elsewhere"}
                )
            }
        ),
    )

    comparison = compare(graph, baseline, mutated)

    assert not comparison.controlled
    assert any("different evaluation backend" in v for v in comparison.violations)


def test_a_changed_public_context_is_rejected(graph: SyntheticGraph) -> None:
    baseline, candidate = pair(graph)
    mutated = candidate.model_copy(
        update={
            "public_context": PublicContext(
                kind="climb", climb_digest=f"sha256:{'7' * 64}"
            )
        }
    )

    comparison = compare(graph, baseline, mutated)

    assert not comparison.controlled
    assert any("different public context" in v for v in comparison.violations)


def test_a_changed_campaign_digest_is_rejected(graph: SyntheticGraph) -> None:
    baseline, candidate = pair(graph)
    mutated = candidate.model_copy(
        update={"campaign_spec_digest": f"sha256:{'6' * 64}"}
    )

    comparison = compare(graph, baseline, mutated)

    assert not comparison.controlled
    assert any("different Campaign" in v for v in comparison.violations)


def test_a_changed_program_reference_is_rejected(graph: SyntheticGraph) -> None:
    from techtree.models.campaign import ProgramRef

    baseline, candidate = pair(graph)
    mutated = candidate.model_copy(
        update={"program_ref": ProgramRef(id="some-program", version=1)}
    )

    comparison = compare(graph, baseline, mutated)

    assert not comparison.controlled
    assert any("different improvement program" in v for v in comparison.violations)


# ---------------------------------------------------------------------------
# Skill replacement (spec section 3.1)
# ---------------------------------------------------------------------------


def replacement_contract(graph: SyntheticGraph) -> MutationContract:
    """Return the synthetic Campaign's contract widened to a replacement."""
    return graph.campaign.mutation_contract.model_copy(
        update={"kind": MutationKind.SKILL_REPLACEMENT}
    )


def replacement_pair(
    graph: SyntheticGraph,
    *,
    baseline_fill: str = "a",
    candidate_fill: str = "b",
) -> tuple[ExperimentManifest, ExperimentManifest]:
    """Return a pair carrying one skill each, differing where ``fill`` differs."""
    baseline, candidate = pair(graph)
    return (
        with_harness(
            baseline,
            skills=[build_skill_reference(artifact("skill-v1", baseline_fill))],
        ),
        with_harness(
            candidate,
            skills=[build_skill_reference(artifact("skill-v2", candidate_fill))],
        ),
    )


def test_a_replacement_of_one_skill_by_another_is_controlled(
    graph: SyntheticGraph,
) -> None:
    baseline, candidate = replacement_pair(graph)

    comparison = compare_manifests(baseline, candidate, replacement_contract(graph))

    assert comparison.controlled
    assert comparison.violations == []
    assert comparison.differences
    assert all(
        pointer_is_within(difference.pointer, SKILL_MUTATION_POINTER)
        for difference in comparison.differences
    )
    assert_controlled_comparison(comparison)


def test_a_replacement_by_the_same_skill_is_rejected(graph: SyntheticGraph) -> None:
    baseline, candidate = replacement_pair(graph, candidate_fill="a")

    comparison = compare_manifests(baseline, candidate, replacement_contract(graph))

    assert not comparison.controlled
    assert any("root digest" in v for v in comparison.violations)


def test_a_replacement_that_only_repackages_the_same_content_is_rejected(
    graph: SyntheticGraph,
) -> None:
    """A candidate whose skill is the baseline's, moved, measures nothing.

    The configurations differ, so the identical-configuration rule does not
    catch it. The root digest is what a skill reference means, and it is the
    same on both sides.
    """
    baseline, _ = replacement_pair(graph)
    reference = baseline.configuration.agents["subject"].harness.skills[0]
    repackaged = with_harness(
        baseline.model_copy(update={"variant": ExperimentVariant.CANDIDATE}),
        skills=[reference.model_copy(update={"relative_path": "skills/moved.zip"})],
    )

    comparison = compare_manifests(baseline, repackaged, replacement_contract(graph))

    # The configurations do differ, so the identical-configuration rule stays
    # silent and the root-digest rule is the only thing that catches this.
    assert comparison.differences
    assert not comparison.controlled
    assert any("root digest" in v for v in comparison.violations)
    assert not any("identical to the baseline" in v for v in comparison.violations)


@pytest.mark.parametrize("count", [0, 2], ids=["none", "two"])
def test_a_replacement_baseline_carries_exactly_one_skill(
    graph: SyntheticGraph, count: int
) -> None:
    baseline, candidate = replacement_pair(graph)
    wrong = with_harness(
        baseline,
        skills=[
            build_skill_reference(artifact(f"skill-{index}", fill))
            for index, fill in enumerate("cd"[:count])
        ],
    )

    comparison = compare_manifests(wrong, candidate, replacement_contract(graph))

    assert not comparison.controlled
    assert any("a replacement replaces exactly one" in v for v in comparison.violations)


def test_a_replacement_candidate_still_carries_exactly_one_skill(
    graph: SyntheticGraph,
) -> None:
    baseline, candidate = replacement_pair(graph)
    two = with_harness(
        candidate,
        skills=[
            build_skill_reference(artifact("skill-v2", "b")),
            build_skill_reference(artifact("skill-v3", "c")),
        ],
    )

    comparison = compare_manifests(baseline, two, replacement_contract(graph))

    assert not comparison.controlled
    assert any("carries 2 skills" in v for v in comparison.violations)


def test_the_insertion_contract_still_refuses_a_replacement_shaped_pair(
    graph: SyntheticGraph,
) -> None:
    """The branch is on the mutation kind, not on what the manifests look like."""
    baseline, candidate = replacement_pair(graph)

    comparison = compare(graph, baseline, candidate)

    assert not comparison.controlled
    assert any("a baseline carries none" in v for v in comparison.violations)


# ---------------------------------------------------------------------------
# Skill counts
# ---------------------------------------------------------------------------


def test_a_baseline_that_already_carries_a_skill_is_rejected(
    graph: SyntheticGraph,
) -> None:
    baseline, candidate = pair(graph)
    tampered = with_harness(baseline, skills=[build_skill_reference(artifact())])

    comparison = compare(graph, tampered, candidate)

    assert not comparison.controlled
    assert any("a baseline carries none" in v for v in comparison.violations)


def test_a_candidate_with_no_skill_is_rejected(graph: SyntheticGraph) -> None:
    baseline, candidate = pair(graph)
    empty = with_harness(candidate, skills=[])

    comparison = compare(graph, baseline, empty)

    assert not comparison.controlled
    assert any("carries 0 skills" in v for v in comparison.violations)
    # An empty candidate is also identical to the baseline, which is its own
    # reason to refuse: a pair with no difference measures nothing.
    assert any("measures nothing" in v for v in comparison.violations)


def test_a_candidate_with_two_skills_is_rejected(graph: SyntheticGraph) -> None:
    baseline, candidate = pair(graph)
    two = with_harness(
        candidate,
        skills=[
            build_skill_reference(artifact("candidate-one", "a")),
            build_skill_reference(artifact("second-skill", "b")),
        ],
    )

    comparison = compare(graph, baseline, two)

    assert not comparison.controlled
    assert any("carries 2 skills" in v for v in comparison.violations)


def test_two_identical_configurations_are_rejected(graph: SyntheticGraph) -> None:
    baseline, _ = pair(graph)
    twin = baseline.model_copy(update={"variant": ExperimentVariant.CANDIDATE})

    comparison = compare(graph, baseline, twin)

    assert not comparison.controlled
    assert any("measures nothing" in v for v in comparison.violations)


def test_the_variants_have_to_be_the_right_way_round(graph: SyntheticGraph) -> None:
    baseline, candidate = pair(graph)

    comparison = compare(graph, candidate, baseline)

    assert not comparison.controlled
    assert any("is a candidate manifest" in v for v in comparison.violations)


# ---------------------------------------------------------------------------
# Refusal
# ---------------------------------------------------------------------------


def test_an_uncontrolled_comparison_raises_a_verification_error(
    graph: SyntheticGraph,
) -> None:
    baseline, candidate = pair(graph)
    mutated = with_harness(candidate, version="0.20.0")
    comparison = compare(graph, baseline, mutated)

    with pytest.raises(VerificationError) as caught:
        assert_controlled_comparison(comparison)

    assert caught.value.code == "manifest_comparison_invalid"
    assert caught.value.details["allowed_differences"] == [SKILL_MUTATION_POINTER]


def test_the_inserted_reference_is_the_only_difference(
    graph: SyntheticGraph,
) -> None:
    """The one permitted difference is an appended element, nothing else."""
    baseline, candidate = pair(graph)
    comparison = compare(graph, baseline, candidate)

    assert [item.pointer for item in comparison.differences] == [
        f"{SKILL_MUTATION_POINTER}/0"
    ]
    only = comparison.differences[0]
    assert only.baseline is None
    assert isinstance(only.candidate, dict)
    assert only.candidate["digest"] == build_skill_reference(artifact()).digest
    assert isinstance(build_skill_reference(artifact()), ArtifactRef)
