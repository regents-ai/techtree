"""Deriving the second comparison. Spec sections 7.19 and 7.22.

A replacement Campaign has one job: to be the first Campaign with the Skill
question changed and nothing else. These tests are mostly the "nothing else" —
a field-by-field walk over everything that must come across untouched, and a
walk over the two things that must not.

The source Campaign is the recorded probes' own, so what is being derived from
is a Campaign that really executed.
"""

from __future__ import annotations

import pytest

from fixtures.receipts.pair import RecordedPair, recorded_pair, recorded_report
from techtree.canonical import digest_object
from techtree.errors import ValidationError, VerificationError
from techtree.models.campaign import (
    SKILL_MUTATION_POINTER,
    SUBJECT_AGENT,
    CampaignSpec,
    MutationKind,
)
from techtree.models.experiment import ExperimentVariant
from techtree.models.skill import SkillArtifact, SkillFile
from techtree.models.uplift_report import UpliftReport
from techtree.uplift.derive import (
    REPLACEMENT_DERIVATION_FAILED,
    derive_replacement_manifests,
    derive_skill_replacement_campaign,
)


def skill(name: str, body: str) -> SkillArtifact:
    """Return a Skill artifact whose root digest describes its one file."""
    from techtree.canonical import sha256_digest_bytes
    from techtree.manifests.builder import skill_content_digest

    data = body.encode("utf-8")
    files = [
        SkillFile(
            path="SKILL.md",
            media_type="text/markdown",
            size=len(data),
            digest=sha256_digest_bytes(data),
        )
    ]
    return SkillArtifact(
        schema_version="techtree.skill.v1alpha1",
        name=name,
        root_digest=skill_content_digest(files),
        archive_digest=sha256_digest_bytes(b"archive-" + data),
        files=files,
        source_kind="manual",
        parent_skill_digest=None,
    )


@pytest.fixture(scope="module")
def pair() -> RecordedPair:
    return recorded_pair()


@pytest.fixture(scope="module")
def source(pair: RecordedPair) -> CampaignSpec:
    return pair.campaign


@pytest.fixture(scope="module")
def report(pair: RecordedPair) -> UpliftReport:
    """The recorded comparison's own report; derivation reads its Campaign digest."""
    return recorded_report(pair)


@pytest.fixture(scope="module")
def v1() -> SkillArtifact:
    return skill("branch-code-v1", "# v1\n\nWork the procedure.\n")


@pytest.fixture(scope="module")
def v2() -> SkillArtifact:
    return skill("branch-code-v2", "# v2\n\nWork the procedure, one branch.\n")


def derive(
    source: CampaignSpec, report: UpliftReport, v1: SkillArtifact, v2: SkillArtifact
) -> CampaignSpec:
    return derive_skill_replacement_campaign(
        source_campaign=source,
        source_run=report,
        baseline_skill=v1,
        candidate_skill=v2,
    )


# ---------------------------------------------------------------------------
# What changes
# ---------------------------------------------------------------------------


def test_the_mutation_becomes_a_replacement_of_exactly_one_skill(
    source: CampaignSpec, report: UpliftReport, v1: SkillArtifact, v2: SkillArtifact
) -> None:
    derived = derive(source, report, v1, v2)
    mutation = derived.mutation_contract

    assert mutation.kind is MutationKind.SKILL_REPLACEMENT
    assert mutation.target_agent == SUBJECT_AGENT
    assert list(mutation.allowed_differences) == [SKILL_MUTATION_POINTER]
    assert (mutation.minimum_skills, mutation.maximum_skills) == (1, 1)


def test_the_baseline_carries_the_skill_that_was_evaluated(
    source: CampaignSpec, report: UpliftReport, v1: SkillArtifact, v2: SkillArtifact
) -> None:
    """By content address, not by anything read off a directory."""
    derived = derive(source, report, v1, v2)
    references = derived.subject.harness.skills

    assert [reference.digest for reference in references] == [v1.root_digest]
    assert source.subject.harness.skills == [], (
        "the source is an insertion Campaign, so its own baseline carries none"
    )


def test_the_derived_campaign_has_a_new_digest(
    source: CampaignSpec, report: UpliftReport, v1: SkillArtifact, v2: SkillArtifact
) -> None:
    assert digest_object(derive(source, report, v1, v2)) != digest_object(source)


# ---------------------------------------------------------------------------
# What does not change. Spec section 7.22: "keeps all non-Skill fields".
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "kind",
        "metadata",
        "context",
        "taskset",
        "environment",
        "evaluation_backend",
        "execution",
        "scoring",
        "evidence",
        "budgets",
        "data_policy_digest",
    ],
)
def test_every_scientific_field_propagates_unchanged(
    field: str,
    source: CampaignSpec,
    report: UpliftReport,
    v1: SkillArtifact,
    v2: SkillArtifact,
) -> None:
    derived = derive(source, report, v1, v2)

    assert getattr(derived, field) == getattr(source, field)


def test_the_subject_differs_only_in_its_skill_list(
    source: CampaignSpec, report: UpliftReport, v1: SkillArtifact, v2: SkillArtifact
) -> None:
    """Model, sampling, harness identity, runtime and trainability all carry over."""
    derived = derive(source, report, v1, v2)
    without_skills = derived.subject.model_copy(
        update={
            "harness": derived.subject.harness.model_copy(
                update={"skills": list(source.subject.harness.skills)}
            )
        }
    )

    assert without_skills == source.subject


def test_the_derived_campaign_carries_nothing_public(
    source: CampaignSpec, report: UpliftReport, v1: SkillArtifact, v2: SkillArtifact
) -> None:
    """No Climb wraps a replacement, so its manifests name no public context."""
    derived = derive(source, report, v1, v2)
    baseline, candidate, _ = derive_replacement_manifests(
        campaign=derived, candidate_skill=v2
    )

    assert baseline.public_context is None
    assert candidate.public_context is None


# ---------------------------------------------------------------------------
# What is refused
# ---------------------------------------------------------------------------


def test_a_report_of_another_campaign_cannot_be_continued_from(
    source: CampaignSpec, report: UpliftReport, v1: SkillArtifact, v2: SkillArtifact
) -> None:
    other = source.model_copy(
        update={"metadata": source.metadata.model_copy(update={"version": 99})}
    )

    with pytest.raises(ValidationError) as raised:
        derive(other, report, v1, v2)

    assert raised.value.code == REPLACEMENT_DERIVATION_FAILED


def test_an_identical_revision_is_refused(
    source: CampaignSpec, report: UpliftReport, v1: SkillArtifact
) -> None:
    """Spec section 7.22: a new Skill digest is required."""
    with pytest.raises(ValidationError) as raised:
        derive(source, report, v1, v1)

    assert raised.value.code == REPLACEMENT_DERIVATION_FAILED


def test_a_campaign_measuring_something_else_is_refused(
    source: CampaignSpec, report: UpliftReport, v1: SkillArtifact, v2: SkillArtifact
) -> None:
    """A replacement continues a component uplift and nothing else."""
    other = source.model_copy(
        update={"metadata": source.metadata.model_copy(update={"purpose": "baseline"})}
    )
    matching = report.model_copy(update={"campaign_spec_digest": digest_object(other)})

    with pytest.raises(ValidationError) as raised:
        derive(other, matching, v1, v2)

    assert raised.value.code == REPLACEMENT_DERIVATION_FAILED


def test_an_insertion_campaign_cannot_produce_replacement_manifests(
    source: CampaignSpec, v2: SkillArtifact
) -> None:
    with pytest.raises(ValidationError) as raised:
        derive_replacement_manifests(campaign=source, candidate_skill=v2)

    assert raised.value.code == REPLACEMENT_DERIVATION_FAILED


# ---------------------------------------------------------------------------
# The pair the derivation produces
# ---------------------------------------------------------------------------


def test_the_pair_is_controlled_and_differs_only_at_the_skill_pointer(
    source: CampaignSpec, report: UpliftReport, v1: SkillArtifact, v2: SkillArtifact
) -> None:
    derived = derive(source, report, v1, v2)
    baseline, candidate, comparison = derive_replacement_manifests(
        campaign=derived, candidate_skill=v2
    )

    assert baseline.variant is ExperimentVariant.BASELINE
    assert candidate.variant is ExperimentVariant.CANDIDATE
    assert comparison.controlled
    assert comparison.violations == []
    assert comparison.differences, "an identical pair would measure nothing"
    for difference in comparison.differences:
        assert difference.pointer.startswith(SKILL_MUTATION_POINTER)


def test_the_pair_names_the_campaign_it_was_derived_from(
    source: CampaignSpec, report: UpliftReport, v1: SkillArtifact, v2: SkillArtifact
) -> None:
    derived = derive(source, report, v1, v2)
    baseline, candidate, _ = derive_replacement_manifests(
        campaign=derived, candidate_skill=v2
    )
    digest = digest_object(derived)

    assert baseline.campaign_spec_digest == candidate.campaign_spec_digest == digest


def test_a_campaign_digest_that_is_not_the_campaigns_is_refused(
    source: CampaignSpec, report: UpliftReport, v1: SkillArtifact, v2: SkillArtifact
) -> None:
    """The manifests must name the Campaign they were actually built from."""
    derived = derive(source, report, v1, v2)

    with pytest.raises((ValidationError, VerificationError)):
        derive_replacement_manifests(
            campaign=derived,
            candidate_skill=v2,
            campaign_digest=digest_object(source),
        )
