"""The scientific execution contract. Spec section 11.5, decisions 0001/0002.

``CampaignSpec`` is the reusable half of the kernel: what is measured, on which
tasks, with which agent, under which comparison rules, and under whose data
policy. It is the object every execution artifact points at.

What it deliberately does not own is anything public — no slug, no schedule, no
leaderboard, no candidate visibility. Those live in ``ClimbManifest``. The
separation is not tidiness: a Campaign can be re-run privately, reproduced by a
third party, or referenced by a future program, and none of those uses should
drag a marketing surface along with them. ``extra="forbid"`` on every model
here is what makes "no public policy fields" enforceable rather than aspirational.

A Campaign is also a commitment. The task membership is fixed and hashed before
anything runs, ``shuffle`` cannot be spelled ``True``, and the only difference
a candidate is permitted to introduce is the subject's skill list. Everything in
this module exists to make an uncontrolled comparison unrepresentable rather
than merely discouraged.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, PositiveFloat, PositiveInt, model_validator

from techtree.models.base import (
    ArtifactRef,
    Digest,
    JsonValue,
    NonEmptyString,
    ProtocolModel,
)
from techtree.models.evaluation_backend import (
    EvaluationBackendKind,
    EvaluationBackendSpec,
)

__all__ = [
    "CREDENTIAL_ENV_PATTERN",
    "SKILL_MUTATION_POINTER",
    "SUBJECT_AGENT",
    "AgentSpec",
    "BudgetSpec",
    "CampaignContext",
    "CampaignMetadata",
    "CampaignSpec",
    "CampaignTaskset",
    "EnvironmentSpec",
    "EvidenceRequirements",
    "ExecutionSpec",
    "HarnessSpec",
    "ModelSpec",
    "MutationContract",
    "MutationKind",
    "PackageRef",
    "ProgramRef",
    "PublicContext",
    "RuntimeSpec",
    "SamplingSpec",
    "ScoringSpec",
    "TaskMembershipCommitment",
    "TaskSelection",
    "TasksetRef",
    "VariantSchedule",
]

#: The only agent name v0.1 defines. A second named agent would be a second
#: thing being measured, which the comparison contract has no way to control.
SUBJECT_AGENT = "subject"

#: The single JSON Pointer a candidate is allowed to differ at.
SKILL_MUTATION_POINTER = "/agents/subject/harness/skills"

#: A credential is named, never carried. The name must look like an ordinary
#: environment variable so that nothing resembling a value can hide in the
#: field that is supposed to hold only a name.
CREDENTIAL_ENV_PATTERN = r"^[A-Z][A-Z0-9_]{2,63}$"

_CREDENTIAL_ENV_RE = re.compile(CREDENTIAL_ENV_PATTERN)

#: An OCI reference that names content rather than a moving tag. For a
#: multi-platform repository the digest names the image index.
_IMAGE_INDEX_DIGEST_RE = re.compile(r"@(sha256:[0-9a-f]{64})$")


# ---------------------------------------------------------------------------
# Shared low-level references
# ---------------------------------------------------------------------------


class ProgramRef(ProtocolModel):
    """A reserved pointer at a future ``ImprovementProgram``.

    The program model itself is deferred (spec section 4.4). Only the pointer
    exists, so that artifacts written today can be attributed later without a
    schema break.
    """

    id: NonEmptyString
    version: int = Field(ge=1)


class PublicContext(ProtocolModel):
    """The optional public Climb an execution artifact was produced under."""

    kind: Literal["climb"]
    climb_digest: Digest


class CampaignContext(ProtocolModel):
    """Forward-compatible pointers a Campaign may carry."""

    program_ref: ProgramRef | None = None
    outcome_contract_digest: Digest | None = None


# ---------------------------------------------------------------------------
# Package and taskset
# ---------------------------------------------------------------------------


class PackageRef(ProtocolModel):
    """The source package a taskset is defined in."""

    kind: Literal["embedded", "git", "hub"]
    name: NonEmptyString
    revision: NonEmptyString
    digest: Digest


class TasksetRef(ProtocolModel):
    """Which taskset, from which package, with which configuration."""

    kind: Literal["verifiers"]
    id: NonEmptyString
    package: PackageRef
    config: dict[str, JsonValue]


class TaskSelection(ProtocolModel):
    """How many tasks and rollouts, in which order.

    ``shuffle`` is typed ``Literal[False]``. Decisions document 0001 removes
    shuffling from WP0–WP5 entirely, and there is no seed anywhere in the
    protocol to reproduce a shuffle with, so a document that claimed to be
    shuffled could not be checked by anyone.
    """

    num_tasks: int = Field(ge=1)
    num_rollouts: int = Field(ge=1)
    shuffle: Literal[False]


class TaskMembershipCommitment(ProtocolModel):
    """The exact tasks a Campaign is fixed to, committed in order."""

    mode: Literal["committed"]
    ordered_task_hashes: list[Digest]
    membership_digest: Digest

    @model_validator(mode="after")
    def _check_membership_is_a_usable_commitment(self) -> Self:
        """Reject an empty or repeating membership list."""
        if not self.ordered_task_hashes:
            raise ValueError("a committed membership must list at least one task")
        if len(set(self.ordered_task_hashes)) != len(self.ordered_task_hashes):
            raise ValueError(
                "committed task hashes must be unique; a repeated task would be "
                "scored twice under one commitment"
            )
        return self


class CampaignTaskset(ProtocolModel):
    """The taskset, the slice of it that is used, and its validation receipt."""

    ref: TasksetRef
    selection: TaskSelection
    membership: TaskMembershipCommitment
    validation_receipt_digest: Digest

    @model_validator(mode="after")
    def _check_membership_matches_selection(self) -> Self:
        """Reject a commitment that does not cover exactly the selected tasks."""
        committed = len(self.membership.ordered_task_hashes)
        if committed != self.selection.num_tasks:
            raise ValueError(
                f"membership commits {committed} tasks but the selection asks "
                f"for {self.selection.num_tasks}"
            )
        return self


# ---------------------------------------------------------------------------
# The subject agent
# ---------------------------------------------------------------------------


class ModelSpec(ProtocolModel):
    """Which model answers, and the environment variable holding its key."""

    provider: NonEmptyString
    model_id: NonEmptyString
    revision: NonEmptyString | None
    credential_env: NonEmptyString

    @model_validator(mode="after")
    def _check_credential_env_is_a_name(self) -> Self:
        """Reject anything that is not a plain environment-variable name."""
        if _CREDENTIAL_ENV_RE.fullmatch(self.credential_env) is None:
            raise ValueError(
                "credential_env must be an uppercase environment-variable name "
                "such as TECHTREE_MODEL_API_KEY, never a credential value"
            )
        return self


class SamplingSpec(ProtocolModel):
    """How the subject model is sampled."""

    temperature: float = Field(ge=0.0, le=2.0)
    max_tokens: int = Field(ge=1)


class HarnessSpec(ProtocolModel):
    """The agent harness and the skills inserted into it."""

    id: NonEmptyString
    version: NonEmptyString
    use_bundled_skill: bool
    skills: list[ArtifactRef]


class RuntimeSpec(ProtocolModel):
    """Where the subject agent executes. Not the evaluation backend.

    The image is pinned twice over, because one pin is not enough to say what
    ran. ``image`` names content rather than a tag, and for a multi-platform
    repository the content it names is an OCI image *index* — a list of
    per-platform manifests, not a filesystem. Two hosts on different
    architectures pulling the same index digest therefore run different bytes,
    and a comparison that recorded only the index digest could not tell whether
    the two variants ran the same subject container.

    ``image_platform_digests`` closes that: one platform-specific manifest
    digest per supported platform, resolved from the registry when the pin is
    made and carried in the Campaign from then on. A run records the platform
    the local daemon resolved, and the digest that actually ran is this table's
    entry for that platform.
    """

    type: Literal["docker"]
    image: NonEmptyString
    supported_platforms: list[NonEmptyString]
    image_platform_digests: dict[NonEmptyString, Digest]
    cpu: PositiveFloat | None
    memory_gb: PositiveFloat | None
    network_policy: Literal["restricted", "open"]

    @property
    def image_index_digest(self) -> Digest:
        """The content the pinned reference names."""
        match = _IMAGE_INDEX_DIGEST_RE.search(self.image)
        assert match is not None  # the validator below refuses anything else
        return match.group(1)

    @model_validator(mode="after")
    def _check_platforms_are_listed_once(self) -> Self:
        """Reject an empty or repeating platform list."""
        if not self.supported_platforms:
            raise ValueError("a runtime must support at least one platform")
        if len(set(self.supported_platforms)) != len(self.supported_platforms):
            raise ValueError("supported_platforms must not repeat a platform")
        return self

    @model_validator(mode="after")
    def _check_the_image_is_pinned_for_every_platform(self) -> Self:
        """Reject a moving image, and a platform with no digest behind it."""
        if _IMAGE_INDEX_DIGEST_RE.search(self.image) is None:
            raise ValueError(
                f"image must name content, as repository@sha256:..., not a "
                f"tag; got {self.image!r}"
            )
        declared = sorted(self.image_platform_digests)
        supported = sorted(self.supported_platforms)
        if declared != supported:
            raise ValueError(
                "image_platform_digests must name exactly the supported "
                f"platforms; it names {declared} for {supported}"
            )
        return self


class AgentSpec(ProtocolModel):
    """One named agent, complete."""

    model: ModelSpec
    sampling: SamplingSpec
    harness: HarnessSpec
    runtime: RuntimeSpec
    trainable: bool


class EnvironmentSpec(ProtocolModel):
    """The interaction shape the Campaign runs in."""

    id: Literal["single-agent"]


# ---------------------------------------------------------------------------
# The scientific contract
# ---------------------------------------------------------------------------


class MutationKind(StrEnum):
    """Which shape of skill change the candidate is allowed to make.

    Spec section 3.1. ``skill_insertion`` measures a skill against no skill and
    is what a public Climb requires. ``skill_replacement`` measures one revision
    of a skill against the previous one, which is the shape a local improvement
    loop needs and which no public Climb wraps.
    """

    SKILL_INSERTION = "skill_insertion"
    SKILL_REPLACEMENT = "skill_replacement"


class MutationContract(ProtocolModel):
    """What a candidate is allowed to change, and by how much."""

    kind: MutationKind
    target_agent: Literal["subject"]
    allowed_differences: list[NonEmptyString]
    minimum_skills: int = Field(ge=0)
    maximum_skills: int = Field(ge=1)

    @model_validator(mode="after")
    def _check_bounds_and_pointer(self) -> Self:
        """Reject impossible bounds and any difference beyond the skill list."""
        if self.minimum_skills > self.maximum_skills:
            raise ValueError("minimum_skills cannot exceed maximum_skills")
        if self.allowed_differences != [SKILL_MUTATION_POINTER]:
            raise ValueError(
                "the only allowed difference in v0.1 is exactly "
                f"[{SKILL_MUTATION_POINTER!r}]"
            )
        return self


class VariantSchedule(StrEnum):
    """Whether the two variants run one after the other or side by side.

    Spec section 3.2. ``max_concurrent`` is the Campaign-wide bound either way;
    under ``parallel_variants`` the executor divides it between the two variants
    rather than granting each of them the whole allowance.
    """

    SEQUENTIAL = "baseline_then_candidate"
    PARALLEL = "parallel_variants"


class ExecutionSpec(ProtocolModel):
    """How the two variants are executed against each other."""

    order: VariantSchedule
    max_concurrent: int = Field(ge=1)
    timeout_seconds: int = Field(ge=1)
    retry_limit: int = Field(ge=0)


class ScoringSpec(ProtocolModel):
    """Which reward decides the comparison, and what counts as an improvement."""

    primary_reward: NonEmptyString
    aggregation: Literal["mean"]
    require_candidate_above_baseline: bool
    minimum_absolute_delta: float = Field(ge=0.0)


class EvidenceRequirements(ProtocolModel):
    """Which evidence a valid episode must carry."""

    verifiers_episode: Literal["required"]
    runtime_evidence: Literal["not_required", "optional", "required"]


class BudgetSpec(ProtocolModel):
    """Optional ceilings on what a run may consume."""

    maximum_input_tokens: PositiveInt | None = None
    maximum_output_tokens: PositiveInt | None = None
    maximum_model_calls: PositiveInt | None = None
    maximum_usd: PositiveFloat | None = None


class CampaignMetadata(ProtocolModel):
    """Identity and intent. Nothing public, nothing presentational."""

    id: NonEmptyString
    version: int = Field(ge=1)
    purpose: Literal[
        "component_uplift",
        "baseline",
        "release_assurance",
        "environment_validation",
        "reproduction",
    ]


class CampaignSpec(ProtocolModel):
    """The complete scientific and execution contract."""

    schema_version: Literal["techtree.campaign.v1alpha1"]
    kind: Literal["Campaign"]
    metadata: CampaignMetadata
    context: CampaignContext
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

    @property
    def subject(self) -> AgentSpec:
        """Return the single subject agent."""
        return self.agents[SUBJECT_AGENT]

    @model_validator(mode="after")
    def _check_campaign_contract(self) -> Self:
        """Enforce every WP0–WP5 Campaign rule from spec section 11.5."""
        if set(self.agents) != {SUBJECT_AGENT}:
            raise ValueError(
                f"v0.1 defines exactly one agent named {SUBJECT_AGENT!r}; "
                f"got {sorted(self.agents)}"
            )

        subject = self.agents[SUBJECT_AGENT]
        # The Campaign describes the baseline, so the subject harness carries
        # the skill list the baseline side of the comparison starts from, and
        # which list that is follows from the mutation kind (spec section 3.1).
        baseline_skills = len(subject.harness.skills)
        if self.mutation_contract.kind is MutationKind.SKILL_INSERTION:
            if baseline_skills:
                raise ValueError(
                    "a skill_insertion Campaign describes a baseline that "
                    "carries no skills; the candidate adds exactly one"
                )
        elif baseline_skills != 1:
            raise ValueError(
                "a skill_replacement Campaign describes a baseline that carries "
                f"exactly one skill to replace; got {baseline_skills}"
            )
        if subject.harness.use_bundled_skill:
            raise ValueError(
                "use_bundled_skill is false for the whole of WP0-WP5; a bundled "
                "skill would be an uncontrolled second difference"
            )

        if self.taskset.selection.num_rollouts != 1:
            raise ValueError("v0.1 scores one rollout per task; num_rollouts must be 1")

        if self.mutation_contract.target_agent != SUBJECT_AGENT:
            raise ValueError("the mutation contract must target the subject agent")

        if self.evaluation_backend.kind is not EvaluationBackendKind.LOCAL_TECHTREE:
            raise ValueError(
                "WP0-WP5 Campaigns are evaluated by local_techtree only; "
                f"got {self.evaluation_backend.kind.value}"
            )

        if self.evidence.runtime_evidence != "not_required":
            raise ValueError(
                "runtime evidence is not collected before WP6, so a Campaign "
                "that required it could never produce a valid episode"
            )
        return self
