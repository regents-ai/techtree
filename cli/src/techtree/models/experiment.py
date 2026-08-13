"""One resolved variant of a Campaign, and the comparison. Spec section 11.8.

An ``ExperimentManifest`` is a Campaign with every choice made: this taskset,
this agent, this skill list. Two of them — baseline and candidate — are what a
run actually executes.

The comparison deliberately looks at ``configuration`` and nothing else. A
manifest identifier, a variant name, a creation time, and a public context all
differ between two correct manifests of the same experiment; comparing them
would report differences that mean nothing and bury the one difference that
means everything. ``ManifestComparison`` therefore compares the configurations
and reports whether the only difference found is the one the mutation contract
permits.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import model_validator

from techtree.models.base import (
    Digest,
    JsonValue,
    NonEmptyString,
    ProtocolModel,
    UtcDateTime,
)
from techtree.models.campaign import (
    AgentSpec,
    BudgetSpec,
    CampaignTaskset,
    EnvironmentSpec,
    EvidenceRequirements,
    ExecutionSpec,
    MutationContract,
    MutationKind,
    ProgramRef,
    PublicContext,
    ScoringSpec,
)
from techtree.models.evaluation_backend import EvaluationBackendSpec

__all__ = [
    "ExperimentConfiguration",
    "ExperimentManifest",
    "ExperimentVariant",
    "JsonDifference",
    "ManifestComparison",
]


class ExperimentVariant(StrEnum):
    """Which side of the comparison a manifest describes."""

    BASELINE = "baseline"
    CANDIDATE = "candidate"


class ExperimentConfiguration(ProtocolModel):
    """The part of a manifest that is compared.

    This mirrors the Campaign's scientific fields with the choices resolved. It
    holds no identifier, no timestamp, and no public context, precisely so that
    two manifests of the same experiment have byte-identical configurations
    except where the mutation contract allows them to differ.
    """

    taskset: CampaignTaskset
    environment: EnvironmentSpec
    agents: dict[str, AgentSpec]
    mutation_contract: MutationContract
    evaluation_backend: EvaluationBackendSpec
    execution: ExecutionSpec
    scoring: ScoringSpec
    evidence: EvidenceRequirements
    budgets: BudgetSpec
    data_policy_digest: Digest
    outcome_contract_digest: Digest | None


class ExperimentManifest(ProtocolModel):
    """One fully resolved variant derived from a Campaign."""

    schema_version: Literal["techtree.experiment.v1alpha1"]
    id: NonEmptyString
    campaign_spec_digest: Digest
    program_ref: ProgramRef | None
    public_context: PublicContext | None
    variant: ExperimentVariant
    configuration: ExperimentConfiguration
    configuration_digest: Digest
    created_at: UtcDateTime

    @model_validator(mode="after")
    def _check_variant_skill_count(self) -> Self:
        """Hold each variant to the skill count its mutation kind requires."""
        subject = self.configuration.agents.get("subject")
        if subject is None:
            raise ValueError("an experiment configuration defines a subject agent")
        skills = len(subject.harness.skills)

        if self.variant is ExperimentVariant.CANDIDATE:
            if skills != 1:
                raise ValueError("the candidate variant carries exactly one skill")
            return self

        # What the baseline carries is what the candidate is measured against,
        # and the mutation kind is what says which that is (spec section 3.1):
        # nothing for an insertion, the skill being revised for a replacement.
        # The two sides' root digests are a property of the pair rather than of
        # one manifest, so they are checked where the pair is — the builder when
        # one is derived, ``manifests.compare`` when two are read back.
        if self.configuration.mutation_contract.kind is MutationKind.SKILL_INSERTION:
            if skills != 0:
                raise ValueError("the baseline variant carries no candidate skill")
        elif skills != 1:
            raise ValueError(
                "the baseline variant of a skill_replacement carries exactly one "
                "skill to replace"
            )
        return self


class JsonDifference(ProtocolModel):
    """One JSON Pointer at which two configurations disagree."""

    pointer: NonEmptyString
    baseline: JsonValue | None
    candidate: JsonValue | None


class ManifestComparison(ProtocolModel):
    """Whether the candidate differs from the baseline only where permitted."""

    baseline_configuration_digest: Digest
    candidate_configuration_digest: Digest
    differences: list[JsonDifference]
    allowed_differences: list[NonEmptyString]
    controlled: bool
    violations: list[NonEmptyString]

    @model_validator(mode="after")
    def _check_control_agrees_with_violations(self) -> Self:
        """Reject a comparison that calls itself controlled while listing faults."""
        if self.controlled and self.violations:
            raise ValueError(
                "a controlled comparison has no violations; listing both leaves "
                "a reader unable to tell which one is true"
            )
        if not self.controlled and not self.violations:
            raise ValueError("an uncontrolled comparison must say which rule it broke")
        return self
