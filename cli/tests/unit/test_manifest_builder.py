"""Deriving experiment variants from a Campaign. Spec PR6 §6.4 and §6.11.

The builder has one job and one failure mode. Its job is to carry the
Campaign's scientific configuration into two manifests without changing any of
it; its failure mode is carrying something else — a value it normalized, a
public policy that leaked in, a skill identified by the wrong digest. Every
test here is a way of asking whether something changed that should not have.

The Campaign under test is the complete synthetic one from the catalog
fixture. Using it rather than a hand-built minimal Campaign means the tests
exercise the same object graph the CLI resolves, including the fields nobody
thinks about until one of them is dropped.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fixtures.drafts.support import SyntheticGraph, synthetic_graph
from techtree.canonical import canonical_json_bytes, digest_object
from techtree.constants import SKILL_SCHEMA_VERSION
from techtree.errors import ValidationError
from techtree.manifests.builder import (
    SKILL_MEDIA_TYPE,
    assert_manifest_matches_campaign,
    build_baseline_manifest,
    build_candidate_manifest,
    build_experiment_configuration,
    build_skill_reference,
    skill_content_digest,
)
from techtree.models.campaign import (
    AgentSpec,
    CampaignSpec,
    HarnessSpec,
    MutationContract,
    MutationKind,
    PublicContext,
)
from techtree.models.experiment import ExperimentManifest, ExperimentVariant
from techtree.models.skill import SkillArtifact, SkillFile

PINNED_TIME = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def graph() -> SyntheticGraph:
    return synthetic_graph()


def skill_files() -> list[SkillFile]:
    """Return a small, valid, sorted candidate file list."""
    return [
        SkillFile(
            path="SKILL.md",
            media_type="text/markdown",
            size=64,
            digest=f"sha256:{'a' * 64}",
        ),
        SkillFile(
            path="reference/notes.md",
            media_type="text/markdown",
            size=32,
            digest=f"sha256:{'b' * 64}",
        ),
    ]


def skill_artifact(files: list[SkillFile] | None = None) -> SkillArtifact:
    """Return a candidate artifact whose root digest describes its files."""
    entries = files if files is not None else skill_files()
    return SkillArtifact(
        schema_version=SKILL_SCHEMA_VERSION,
        name="candidate-under-test",
        root_digest=skill_content_digest(entries),
        archive_digest=f"sha256:{'c' * 64}",
        files=entries,
        source_kind="manual",
        parent_skill_digest=None,
    )


def baseline_of(graph: SyntheticGraph) -> ExperimentManifest:
    return build_baseline_manifest(
        campaign=graph.campaign,
        campaign_digest=graph.campaign_digest,
        public_context=graph.public_context,
        created_at=PINNED_TIME,
    )


def candidate_of(
    graph: SyntheticGraph, skill: SkillArtifact | None = None
) -> ExperimentManifest:
    return build_candidate_manifest(
        campaign=graph.campaign,
        campaign_digest=graph.campaign_digest,
        skill=skill or skill_artifact(),
        public_context=graph.public_context,
        created_at=PINNED_TIME,
    )


# ---------------------------------------------------------------------------
# What is carried across
# ---------------------------------------------------------------------------


def test_the_baseline_preserves_the_campaign_and_carries_no_skill(
    graph: SyntheticGraph,
) -> None:
    manifest = baseline_of(graph)
    configuration = manifest.configuration

    assert manifest.variant is ExperimentVariant.BASELINE
    assert configuration.agents["subject"].harness.skills == []
    assert configuration.taskset == graph.campaign.taskset
    assert configuration.execution == graph.campaign.execution
    assert configuration.scoring == graph.campaign.scoring
    assert configuration.evidence == graph.campaign.evidence
    assert configuration.budgets == graph.campaign.budgets
    assert configuration.mutation_contract == graph.campaign.mutation_contract
    assert manifest.campaign_spec_digest == graph.campaign_digest


def test_the_candidate_preserves_the_campaign_and_carries_exactly_one_skill(
    graph: SyntheticGraph,
) -> None:
    baseline = baseline_of(graph)
    candidate = candidate_of(graph)

    assert candidate.variant is ExperimentVariant.CANDIDATE
    assert len(candidate.configuration.agents["subject"].harness.skills) == 1

    # Everything except the skill list is the baseline's, byte for byte.
    stripped = candidate.configuration.agents["subject"].harness.model_copy(
        update={"skills": []}
    )
    assert stripped == baseline.configuration.agents["subject"].harness


def test_the_skill_reference_identifies_the_content_tree(
    graph: SyntheticGraph,
) -> None:
    """The archive is transport; the tree digest is the scientific identity."""
    artifact = skill_artifact()
    reference = (
        candidate_of(graph, artifact).configuration.agents["subject"].harness.skills[0]
    )

    assert reference.digest == artifact.root_digest
    assert reference.digest != artifact.archive_digest
    assert reference.media_type == SKILL_MEDIA_TYPE
    assert reference.size == sum(file.size for file in artifact.files)
    assert reference.relative_path is None


def test_the_public_context_is_copied_exactly(graph: SyntheticGraph) -> None:
    for manifest in (baseline_of(graph), candidate_of(graph)):
        assert manifest.public_context == graph.public_context
        assert manifest.public_context is not graph.public_context


def test_the_data_policy_digest_is_the_campaigns(graph: SyntheticGraph) -> None:
    for manifest in (baseline_of(graph), candidate_of(graph)):
        assert (
            manifest.configuration.data_policy_digest
            == graph.campaign.data_policy_digest
        )


def test_the_evaluation_backend_is_copied_exactly(graph: SyntheticGraph) -> None:
    for manifest in (baseline_of(graph), candidate_of(graph)):
        assert (
            manifest.configuration.evaluation_backend
            == graph.campaign.evaluation_backend
        )


def test_the_outcome_contract_digest_is_copied_exactly(
    graph: SyntheticGraph,
) -> None:
    with_contract = graph.campaign.model_copy(
        update={
            "context": graph.campaign.context.model_copy(
                update={"outcome_contract_digest": f"sha256:{'d' * 64}"}
            )
        }
    )
    manifest = build_baseline_manifest(
        campaign=with_contract,
        campaign_digest=digest_object(with_contract),
        public_context=None,
        created_at=PINNED_TIME,
    )

    assert manifest.configuration.outcome_contract_digest == f"sha256:{'d' * 64}"


def test_no_public_climb_policy_reaches_the_configuration(
    graph: SyntheticGraph,
) -> None:
    """Spec PR6 §12: the Climb's publication policy is not science."""
    rendered = canonical_json_bytes(candidate_of(graph).configuration).decode()

    for public_only in (
        "leaderboard",
        "proof_grade",
        "opens_at",
        "closes_at",
        "skill_visibility",
        "report_visibility",
        graph.resolved.climb.metadata.slug,
    ):
        assert public_only not in rendered


def test_no_local_path_reaches_a_manifest(graph: SyntheticGraph) -> None:
    manifest = candidate_of(graph)
    rendered = canonical_json_bytes(manifest).decode()

    assert "/Users/" not in rendered
    assert "/tmp/" not in rendered
    # The only field that could hold one names nothing at all: a manifest
    # points at content, and where those bytes happen to sit is the draft's
    # business rather than the experiment's.
    assert all(
        reference.relative_path is None
        for reference in manifest.configuration.agents["subject"].harness.skills
    )


def test_building_does_not_mutate_the_campaign(graph: SyntheticGraph) -> None:
    before = digest_object(graph.campaign)
    baseline_of(graph)
    candidate_of(graph)

    assert digest_object(graph.campaign) == before
    assert graph.campaign.subject.harness.skills == []


def test_pinned_inputs_produce_a_byte_stable_manifest(
    graph: SyntheticGraph,
) -> None:
    first = candidate_of(graph)
    second = candidate_of(graph)

    assert digest_object(first) == digest_object(second)
    assert first.id == second.id


def test_the_configuration_digest_is_the_digest_of_the_configuration(
    graph: SyntheticGraph,
) -> None:
    manifest = baseline_of(graph)

    assert manifest.configuration_digest == digest_object(manifest.configuration)
    assert build_experiment_configuration(graph.campaign) == manifest.configuration


# ---------------------------------------------------------------------------
# What is refused
# ---------------------------------------------------------------------------


def test_a_campaign_digest_that_is_not_the_campaigns_is_refused(
    graph: SyntheticGraph,
) -> None:
    with pytest.raises(ValidationError) as caught:
        build_baseline_manifest(
            campaign=graph.campaign,
            campaign_digest=f"sha256:{'0' * 64}",
            public_context=None,
            created_at=PINNED_TIME,
        )

    assert caught.value.code == "manifest_build_failed"


def test_a_campaign_whose_subject_already_carries_a_skill_is_refused(
    graph: SyntheticGraph,
) -> None:
    """Fail closed: there would be no baseline to compare a candidate against."""
    tampered = _campaign_with_a_skill(graph.campaign)

    with pytest.raises(ValidationError) as caught:
        build_baseline_manifest(
            campaign=tampered,
            campaign_digest=digest_object(tampered),
            public_context=None,
            created_at=PINNED_TIME,
        )

    assert caught.value.code == "manifest_build_failed"
    assert "baseline" in caught.value.message


def test_a_campaign_that_does_not_allow_one_skill_refuses_a_candidate(
    graph: SyntheticGraph,
) -> None:
    demanding = graph.campaign.model_copy(
        update={
            "mutation_contract": MutationContract(
                kind=MutationKind.SKILL_INSERTION,
                target_agent="subject",
                allowed_differences=list(
                    graph.campaign.mutation_contract.allowed_differences
                ),
                minimum_skills=2,
                maximum_skills=2,
            )
        }
    )

    with pytest.raises(ValidationError) as caught:
        build_candidate_manifest(
            campaign=demanding,
            campaign_digest=digest_object(demanding),
            skill=skill_artifact(),
            public_context=None,
            created_at=PINNED_TIME,
        )

    assert caught.value.code == "manifest_build_failed"


def test_a_skill_whose_root_digest_does_not_describe_its_files_is_refused() -> None:
    lying = skill_artifact().model_copy(update={"root_digest": f"sha256:{'e' * 64}"})

    with pytest.raises(ValidationError) as caught:
        build_skill_reference(lying)

    assert caught.value.code == "manifest_build_failed"
    assert "root digest" in caught.value.message


def test_a_skill_with_no_content_is_refused() -> None:
    empty = [
        SkillFile(
            path="SKILL.md",
            media_type="text/markdown",
            size=0,
            digest=f"sha256:{'f' * 64}",
        )
    ]

    with pytest.raises(ValidationError) as caught:
        build_skill_reference(skill_artifact(empty))

    assert caught.value.code == "manifest_build_failed"


def test_the_postcondition_catches_a_manifest_that_drifted(
    graph: SyntheticGraph,
) -> None:
    """A manifest can also arrive from disk, so the check is not only a proof."""
    manifest = baseline_of(graph)
    drifted = manifest.model_copy(
        update={
            "configuration": manifest.configuration.model_copy(
                update={
                    "scoring": manifest.configuration.scoring.model_copy(
                        update={"primary_reward": "something_else"}
                    )
                }
            )
        }
    )

    with pytest.raises(ValidationError) as caught:
        assert_manifest_matches_campaign(drifted, graph.campaign, graph.campaign_digest)

    assert caught.value.details["field"] == "scoring rule"


def _campaign_with_a_skill(campaign: CampaignSpec) -> CampaignSpec:
    """Return a Campaign whose subject already carries a skill.

    Built with ``model_copy`` because the Campaign model refuses to validate
    one, and the point of the test is that the builder refuses it too rather
    than relying on the model having been the only gate.
    """
    subject = campaign.subject
    return campaign.model_copy(
        update={
            "agents": {
                "subject": AgentSpec(
                    model=subject.model,
                    sampling=subject.sampling,
                    harness=HarnessSpec(
                        id=subject.harness.id,
                        version=subject.harness.version,
                        use_bundled_skill=False,
                        skills=[build_skill_reference(skill_artifact())],
                    ),
                    runtime=subject.runtime,
                    trainable=subject.trainable,
                )
            }
        }
    )


def test_a_manifest_without_a_public_context_is_still_valid(
    graph: SyntheticGraph,
) -> None:
    """A Campaign can be run privately; the public wrapper is optional."""
    manifest = build_baseline_manifest(
        campaign=graph.campaign,
        campaign_digest=graph.campaign_digest,
        public_context=None,
        created_at=PINNED_TIME,
    )

    assert manifest.public_context is None
    assert isinstance(graph.public_context, PublicContext)
