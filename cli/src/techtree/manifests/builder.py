"""Deriving the two experiment variants from one Campaign. Spec PR6 §6.4.

The Campaign is the experiment. A manifest is the Campaign with the one open
choice made — which skill the subject harness carries — and nothing else decided
differently. Everything in this module exists to keep that sentence literally
true.

Four rules make it true rather than merely intended.

*Copy, never re-derive.* The taskset, environment, agents, mutation contract,
evaluation backend, execution plan, scoring rule, evidence requirements,
budgets, DataPolicy digest, and OutcomeContract digest are copied out of the
Campaign exactly as they were found. Nothing is normalized, defaulted, or
recomputed on the way through, because a value this module produced would be a
value the Campaign did not commit to.

*Copy deeply.* A frozen model still holds real lists and dicts. Deep copies are
what stop a manifest and the Campaign it came from — or a baseline and its
candidate — from sharing a container a later caller could mutate.

*Carry no local path and no public policy.* A manifest is a scientific document
two machines must be able to produce identically, so the candidate skill enters
as a content address and nothing about the Climb's schedule, leaderboard, or
publication policy enters at all. The public wrapper is referenced through
``public_context`` and never folded into ``configuration``; that separation is
what lets :mod:`techtree.manifests.compare` compare configurations alone.

*Identify the skill by its content tree.* The harness-facing reference carries
``SkillArtifact.root_digest``, not the archive digest. The archive is transport
integrity — the bytes that happen to move the skill from here to there — while
the tree digest is what the experiment actually inserted. Two archives of the
same tree are the same science; the manifest has to say so.

Timestamps and identifiers can be injected. A test that pins both gets a
byte-stable manifest, which is the only way to assert on a digest.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Final

from techtree.canonical import digest_object
from techtree.constants import EXPERIMENT_SCHEMA_VERSION
from techtree.errors import ValidationError
from techtree.models.base import ArtifactRef, Digest, JsonValue
from techtree.models.campaign import (
    AgentSpec,
    CampaignSpec,
    HarnessSpec,
    MutationKind,
    PublicContext,
)
from techtree.models.experiment import (
    ExperimentConfiguration,
    ExperimentManifest,
    ExperimentVariant,
)
from techtree.models.skill import SkillArtifact, SkillFile

__all__ = [
    "MANIFEST_BUILD_FAILED",
    "MANIFEST_ID_PREFIX",
    "SKILL_MEDIA_TYPE",
    "assert_manifest_matches_campaign",
    "build_baseline_manifest",
    "build_candidate_manifest",
    "build_experiment_configuration",
    "build_skill_reference",
    "manifest_id_for",
    "skill_content_digest",
]

#: The media type of an instruction skill's canonical content tree. It is not
#: ``application/x-tar``: what the reference addresses is the tree, and the tar
#: is one possible encoding of it.
SKILL_MEDIA_TYPE: Final = "application/vnd.techtree.instruction-skill.v1"

#: Manifest identifiers are derived from the configuration digest rather than
#: drawn at random. Two derivations of the same experiment then name it the
#: same way, and an identifier can never disagree with the document it labels.
MANIFEST_ID_PREFIX: Final = "experiment"

#: The one error code every failure in this module reports. Spec PR6 §6.10.
MANIFEST_BUILD_FAILED: Final = "manifest_build_failed"

#: How much of the digest a derived identifier carries, matching the display-id
#: convention of decisions document 0003 A1.
_ID_HEX_LENGTH: Final = 24


def build_experiment_configuration(
    campaign: CampaignSpec,
) -> ExperimentConfiguration:
    """Copy the Campaign scientific fields into an ``ExperimentConfiguration``.

    This is the baseline configuration, because a Campaign describes the subject
    as the candidate is measured against it — with no skill for an insertion,
    and with the skill being revised for a replacement.
    :func:`build_candidate_manifest` produces the other variant by replacing
    exactly one field of exactly one agent.
    """
    return ExperimentConfiguration(
        taskset=campaign.taskset.model_copy(deep=True),
        environment=campaign.environment.model_copy(deep=True),
        agents={
            name: agent.model_copy(deep=True) for name, agent in campaign.agents.items()
        },
        mutation_contract=campaign.mutation_contract.model_copy(deep=True),
        evaluation_backend=campaign.evaluation_backend.model_copy(deep=True),
        execution=campaign.execution.model_copy(deep=True),
        scoring=campaign.scoring.model_copy(deep=True),
        evidence=campaign.evidence.model_copy(deep=True),
        budgets=campaign.budgets.model_copy(deep=True),
        data_policy_digest=campaign.data_policy_digest,
        outcome_contract_digest=campaign.context.outcome_contract_digest,
    )


def skill_content_digest(files: Sequence[SkillFile]) -> Digest:
    """Return the digest of a skill's canonical content tree.

    The tree is exactly its sorted file list: each path, its media type, its
    size, and the digest of its bytes. Digesting that list commits to every
    file's content and to the shape of the directory, and to nothing about how
    the tree was packed or where it was read from.
    """
    return digest_object(list(files))


def build_skill_reference(skill: SkillArtifact) -> ArtifactRef:
    """Create the harness-facing reference to canonical skill content."""
    total = sum(file.size for file in skill.files)
    if total <= 0:
        raise ValidationError(
            "the candidate skill has no content to insert, so there is nothing "
            "for the experiment to measure",
            code=MANIFEST_BUILD_FAILED,
            details={"file_count": len(skill.files), "total_bytes": total},
        )

    recomputed = skill_content_digest(skill.files)
    if recomputed != skill.root_digest:
        raise ValidationError(
            "the candidate skill's root digest does not describe the files it lists",
            code=MANIFEST_BUILD_FAILED,
            details={
                "stated_root_digest": skill.root_digest,
                "computed_root_digest": recomputed,
            },
        )

    return ArtifactRef(
        digest=skill.root_digest,
        media_type=SKILL_MEDIA_TYPE,
        size=total,
        relative_path=None,
    )


def build_baseline_manifest(
    *,
    campaign: CampaignSpec,
    campaign_digest: Digest,
    public_context: PublicContext | None,
    created_at: datetime | None = None,
    manifest_id: str | None = None,
) -> ExperimentManifest:
    """Build the baseline variant."""
    configuration = build_experiment_configuration(campaign)
    _require_campaign_baseline(configuration, campaign)
    return finalize_manifest(
        campaign=campaign,
        campaign_digest=campaign_digest,
        public_context=public_context,
        variant=ExperimentVariant.BASELINE,
        configuration=configuration,
        created_at=created_at,
        manifest_id=manifest_id,
    )


def build_candidate_manifest(
    *,
    campaign: CampaignSpec,
    campaign_digest: Digest,
    skill: SkillArtifact,
    public_context: PublicContext | None,
    created_at: datetime | None = None,
    manifest_id: str | None = None,
) -> ExperimentManifest:
    """Build the candidate variant with exactly one skill reference.

    The candidate configuration is the baseline configuration with the subject
    harness's skill list replaced. Building it by replacement rather than by a
    second derivation from the Campaign is what guarantees no other field can
    drift: a field this function does not name cannot differ from the baseline.
    """
    configuration = build_experiment_configuration(campaign)
    baseline_subject = _require_campaign_baseline(configuration, campaign)
    reference = build_skill_reference(skill)

    mutation = campaign.mutation_contract
    if mutation.kind is MutationKind.SKILL_REPLACEMENT:
        replaced = baseline_subject.harness.skills[0]
        if replaced.digest == reference.digest:
            raise ValidationError(
                "the replacement skill has the same content tree as the skill it "
                "replaces, so the pair would measure nothing",
                code=MANIFEST_BUILD_FAILED,
                details={
                    "baseline_root_digest": replaced.digest,
                    "candidate_root_digest": reference.digest,
                },
            )

    if not mutation.minimum_skills <= 1 <= mutation.maximum_skills:
        raise ValidationError(
            "this Campaign's mutation contract does not permit a single "
            f"candidate skill; it allows {mutation.minimum_skills} to "
            f"{mutation.maximum_skills}",
            code=MANIFEST_BUILD_FAILED,
            details={
                "minimum_skills": mutation.minimum_skills,
                "maximum_skills": mutation.maximum_skills,
            },
        )

    target = mutation.target_agent
    subject = configuration.agents[target]
    with_skill = AgentSpec(
        model=subject.model,
        sampling=subject.sampling,
        harness=HarnessSpec(
            id=subject.harness.id,
            version=subject.harness.version,
            use_bundled_skill=subject.harness.use_bundled_skill,
            skills=[reference],
        ),
        runtime=subject.runtime,
        trainable=subject.trainable,
    )

    return finalize_manifest(
        campaign=campaign,
        campaign_digest=campaign_digest,
        public_context=public_context,
        variant=ExperimentVariant.CANDIDATE,
        configuration=configuration.model_copy(
            update={"agents": {**configuration.agents, target: with_skill}}
        ),
        created_at=created_at,
        manifest_id=manifest_id,
    )


def finalize_manifest(
    *,
    campaign: CampaignSpec,
    campaign_digest: Digest,
    public_context: PublicContext | None,
    variant: ExperimentVariant,
    configuration: ExperimentConfiguration,
    created_at: datetime | None,
    manifest_id: str | None,
) -> ExperimentManifest:
    """Validate lineage, calculate ``configuration_digest``, and construct."""
    if digest_object(campaign) != campaign_digest:
        raise ValidationError(
            "the Campaign digest a manifest was asked to carry is not the "
            "digest of the Campaign it was built from",
            code=MANIFEST_BUILD_FAILED,
            details={
                "stated_campaign_digest": campaign_digest,
                "computed_campaign_digest": digest_object(campaign),
            },
        )

    configuration_digest = digest_object(configuration)
    manifest = ExperimentManifest(
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        id=manifest_id or manifest_id_for(configuration_digest),
        campaign_spec_digest=campaign_digest,
        program_ref=(
            None
            if campaign.context.program_ref is None
            else campaign.context.program_ref.model_copy(deep=True)
        ),
        public_context=(
            None if public_context is None else public_context.model_copy(deep=True)
        ),
        variant=variant,
        configuration=configuration,
        configuration_digest=configuration_digest,
        created_at=created_at or datetime.now(UTC),
    )
    assert_manifest_matches_campaign(manifest, campaign, campaign_digest)
    return manifest


def assert_manifest_matches_campaign(
    manifest: ExperimentManifest,
    campaign: CampaignSpec,
    campaign_digest: Digest,
) -> None:
    """Check, after the fact, that a manifest is the Campaign it claims to be.

    Everything here was already true by construction when the manifest came
    from this module. It is checked again because a manifest can also arrive
    from disk, and because a postcondition that only holds when the code is
    correct is not a postcondition.
    """
    configuration = manifest.configuration
    for label, expected, found in (
        ("Campaign digest", campaign_digest, manifest.campaign_spec_digest),
        ("improvement program", campaign.context.program_ref, manifest.program_ref),
        (
            "OutcomeContract digest",
            campaign.context.outcome_contract_digest,
            configuration.outcome_contract_digest,
        ),
        (
            "DataPolicy digest",
            campaign.data_policy_digest,
            configuration.data_policy_digest,
        ),
        (
            "evaluation backend",
            campaign.evaluation_backend,
            configuration.evaluation_backend,
        ),
        ("taskset", campaign.taskset, configuration.taskset),
        ("environment", campaign.environment, configuration.environment),
        (
            "mutation contract",
            campaign.mutation_contract,
            configuration.mutation_contract,
        ),
        ("execution plan", campaign.execution, configuration.execution),
        ("scoring rule", campaign.scoring, configuration.scoring),
        ("evidence requirement", campaign.evidence, configuration.evidence),
        ("budget", campaign.budgets, configuration.budgets),
    ):
        if expected != found:
            raise ValidationError(
                f"the manifest's {label} is not the Campaign's",
                code=MANIFEST_BUILD_FAILED,
                details={"field": label},
            )

    if set(configuration.agents) != set(campaign.agents):
        agents: dict[str, JsonValue] = {
            "campaign_agents": list(sorted(campaign.agents)),
            "manifest_agents": list(sorted(configuration.agents)),
        }
        raise ValidationError(
            "the manifest names different agents than the Campaign",
            code=MANIFEST_BUILD_FAILED,
            details=agents,
        )

    target = campaign.mutation_contract.target_agent
    for name, agent in configuration.agents.items():
        expected_agent = campaign.agents[name]
        if name == target:
            # The skill list is the one field the mutation contract allows to
            # differ, so the subject is compared with it set aside.
            agent = agent.model_copy(
                update={
                    "harness": agent.harness.model_copy(
                        update={"skills": list(expected_agent.harness.skills)}
                    )
                }
            )
        if agent != expected_agent:
            raise ValidationError(
                f"the manifest's {name} agent differs from the Campaign's "
                "outside the skill list",
                code=MANIFEST_BUILD_FAILED,
                details={"agent": name},
            )


def manifest_id_for(configuration_digest: Digest) -> str:
    """Return the display identifier one configuration digest implies."""
    hexadecimal = configuration_digest.split(":", 1)[1]
    return f"{MANIFEST_ID_PREFIX}_{hexadecimal[:_ID_HEX_LENGTH]}"


def _require_campaign_baseline(
    configuration: ExperimentConfiguration, campaign: CampaignSpec
) -> AgentSpec:
    """Fail closed when the Campaign's subject is not the baseline its kind needs.

    An insertion measures a skill against no skill, so its Campaign carries
    none. A replacement measures a revision against the skill it revises, so its
    Campaign carries exactly that one. Either way the Campaign *is* the baseline,
    and a Campaign that is not the baseline its own contract describes has no
    comparison to offer.
    """
    target = campaign.mutation_contract.target_agent
    subject = configuration.agents.get(target)
    if subject is None:
        missing: dict[str, JsonValue] = {
            "target_agent": target,
            "agents": list(sorted(configuration.agents)),
        }
        raise ValidationError(
            f"the Campaign defines no {target} agent for the mutation contract "
            "to target",
            code=MANIFEST_BUILD_FAILED,
            details=missing,
        )

    skills = subject.harness.skills
    if campaign.mutation_contract.kind is MutationKind.SKILL_INSERTION:
        if skills:
            raise ValidationError(
                "the Campaign's own subject already carries a skill, so there is "
                "no baseline to compare a candidate against",
                code=MANIFEST_BUILD_FAILED,
                details={"skill_count": len(skills)},
            )
    elif len(skills) != 1:
        raise ValidationError(
            "a skill_replacement Campaign's subject carries exactly the one "
            "skill the candidate replaces, so there is no baseline to compare a "
            "candidate against",
            code=MANIFEST_BUILD_FAILED,
            details={"skill_count": len(skills)},
        )
    return subject
