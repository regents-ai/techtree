"""Turning a finished comparison into the next one. Spec section 7.19.

A first run answers "does this Skill beat no Skill?". The question after it is
"does this revision beat the Skill that already worked?", and spec section 3.1
gives that its own mutation kind rather than its own protocol: it is the same
Campaign with the mutation contract changed and the baseline given the Skill
being revised.

This module derives that Campaign, and it is written so that the derivation
cannot quietly become a second experiment.

*Every scientific field is copied, deeply.* Taskset, membership, validation
receipt, environment, model, sampling, harness, runtime, tools, scoring,
evidence, budgets, DataPolicy digest and OutcomeContract digest come across
byte-identically. A value this module computed would be a value the source run
never measured under, and the two reports would not be about the same taskset.

*Exactly two things change, and both are named.* The mutation contract becomes
``skill_replacement`` bounded at exactly one Skill, and the subject harness
carries Skill v1. Those two are why the derived Campaign has a different
digest, and they are the whole difference.

*The public wrapper does not come across.* A ``ClimbManifest`` can only require
``skill_insertion`` — :class:`~techtree.models.climb.CandidatePolicy` types it
that way — so no public Climb wraps a replacement, and the derived Campaign
carries no public context. Spec section 7.19 allows a separate Climb to
authorize one later; none exists, so none is invented.

The Skill the baseline carries is the one that was *evaluated*, identified by
its content address. Nothing here reads a directory, so a Skill that has been
edited since the first run cannot become the baseline the second run claims to
have measured against.
"""

from __future__ import annotations

from datetime import datetime

from techtree.canonical import digest_object
from techtree.errors import ValidationError
from techtree.manifests.builder import (
    build_baseline_manifest,
    build_candidate_manifest,
    build_skill_reference,
)
from techtree.manifests.compare import assert_controlled_comparison, compare_manifests
from techtree.models.base import Digest
from techtree.models.campaign import (
    SKILL_MUTATION_POINTER,
    SUBJECT_AGENT,
    AgentSpec,
    CampaignSpec,
    HarnessSpec,
    MutationContract,
    MutationKind,
)
from techtree.models.experiment import ExperimentManifest, ManifestComparison
from techtree.models.skill import SkillArtifact
from techtree.models.uplift_report import UpliftReport

__all__ = [
    "REPLACEMENT_DERIVATION_FAILED",
    "REPLACEMENT_PURPOSE",
    "derive_replacement_manifests",
    "derive_skill_replacement_campaign",
]

#: The one code every refusal in this module reports. Spec section 15 fixes the
#: vocabulary; this is the derivation's own entry in it.
REPLACEMENT_DERIVATION_FAILED = "replacement_derivation_failed"

#: Spec section 7.19: the purpose remains what it was. A Campaign measuring
#: something else is not one an improvement loop continues from, and changing
#: its purpose on the way through would be answering a different question under
#: the first question's name.
REPLACEMENT_PURPOSE = "component_uplift"


def derive_skill_replacement_campaign(
    *,
    source_campaign: CampaignSpec,
    source_run: UpliftReport,
    baseline_skill: SkillArtifact,
    candidate_skill: SkillArtifact,
) -> CampaignSpec:
    """Derive the local Campaign that compares Skill v1 against Skill v2.

    ``source_run`` is the signed report of the run being continued from. It is
    required to be a report *of* ``source_campaign``, so a derivation cannot
    pair one run's evidence with another run's science.
    """
    _require(
        source_run.campaign_spec_digest == digest_object(source_campaign),
        "this report is not a report of the Campaign it is being continued "
        "from, so the run it describes measured something else",
        expected=source_run.campaign_spec_digest,
        computed=digest_object(source_campaign),
    )
    _require(
        source_campaign.metadata.purpose == REPLACEMENT_PURPOSE,
        "a Skill replacement continues a component uplift, and this Campaign's "
        f"purpose is {source_campaign.metadata.purpose}",
        purpose=source_campaign.metadata.purpose,
    )
    _require(
        baseline_skill.root_digest != candidate_skill.root_digest,
        "the proposed Skill has the same content tree as the Skill it would "
        "replace, so the pair would measure nothing",
        root_digest=baseline_skill.root_digest,
    )

    subject = source_campaign.agents[SUBJECT_AGENT]
    replaced = AgentSpec(
        model=subject.model.model_copy(deep=True),
        sampling=subject.sampling.model_copy(deep=True),
        harness=HarnessSpec(
            id=subject.harness.id,
            version=subject.harness.version,
            use_bundled_skill=subject.harness.use_bundled_skill,
            # The baseline of a replacement is the Skill being revised, named
            # by the content address the first run actually evaluated.
            skills=[build_skill_reference(baseline_skill)],
        ),
        runtime=subject.runtime.model_copy(deep=True),
        trainable=subject.trainable,
    )

    return CampaignSpec(
        schema_version=source_campaign.schema_version,
        kind=source_campaign.kind,
        metadata=source_campaign.metadata.model_copy(deep=True),
        context=source_campaign.context.model_copy(deep=True),
        taskset=source_campaign.taskset.model_copy(deep=True),
        environment=source_campaign.environment.model_copy(deep=True),
        agents={SUBJECT_AGENT: replaced},
        mutation_contract=MutationContract(
            kind=MutationKind.SKILL_REPLACEMENT,
            target_agent="subject",
            allowed_differences=[SKILL_MUTATION_POINTER],
            # Both sides carry exactly one Skill: there is nothing to add and
            # nothing to remove, only one tree to swap for another.
            minimum_skills=1,
            maximum_skills=1,
        ),
        evaluation_backend=source_campaign.evaluation_backend.model_copy(deep=True),
        execution=source_campaign.execution.model_copy(deep=True),
        scoring=source_campaign.scoring.model_copy(deep=True),
        evidence=source_campaign.evidence.model_copy(deep=True),
        budgets=source_campaign.budgets.model_copy(deep=True),
        data_policy_digest=source_campaign.data_policy_digest,
    )


def derive_replacement_manifests(
    *,
    campaign: CampaignSpec,
    candidate_skill: SkillArtifact,
    campaign_digest: Digest | None = None,
    created_at: datetime | None = None,
) -> tuple[ExperimentManifest, ExperimentManifest, ManifestComparison]:
    """Build both variants of a replacement and require the pair to be controlled.

    The baseline is built from the Campaign alone, because a replacement
    Campaign *is* its own baseline: it carries Skill v1 in the subject harness.
    The candidate is the same configuration with that one list replaced. Both
    carry no public context, and the comparison is required to be controlled
    before either is returned.
    """
    _require(
        campaign.mutation_contract.kind is MutationKind.SKILL_REPLACEMENT,
        "these manifests would be a Skill replacement and this Campaign "
        f"declares {campaign.mutation_contract.kind.value}",
        mutation_kind=campaign.mutation_contract.kind.value,
    )

    digest = campaign_digest or digest_object(campaign)
    baseline = build_baseline_manifest(
        campaign=campaign,
        campaign_digest=digest,
        public_context=None,
        created_at=created_at,
    )
    candidate = build_candidate_manifest(
        campaign=campaign,
        campaign_digest=digest,
        skill=candidate_skill,
        public_context=None,
        created_at=created_at,
    )
    comparison = compare_manifests(baseline, candidate, campaign.mutation_contract)
    assert_controlled_comparison(comparison)
    return baseline, candidate, comparison


def _require(condition: bool, message: str, **details: str) -> None:
    """Raise a typed refusal unless the condition holds."""
    if condition:
        return
    raise ValidationError(
        message,
        code=REPLACEMENT_DERIVATION_FAILED,
        details=dict(details),
    )
