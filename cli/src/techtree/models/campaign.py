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

Two Campaign documents live here, and they are siblings rather than a
document and its refinement. ``CampaignSpec`` is v0.1, and its canonical bytes
are frozen: every published proof recomputes this exact object's digest, so a
field added to it would invalidate evidence that has already been signed.
``CampaignSpecV2`` is v0.2. It binds the digest of the execution plan the
Campaign is resolved against, and it drops the three facts that plan now owns
— the evaluation backend, the subject harness coordinates, and the requirement
for a Verifiers episode — because a fact stated in two documents is a fact
that can disagree with itself.

What the two share is the scientific contract, and they share it through
``_CampaignScience``, which is not a document: it has no ``schema_version``
and no ``kind``, so it cannot be stored or mistaken for a Campaign, and a
function that asks for one Campaign will not silently accept the other.
Nothing anywhere branches on which document is in hand. Decision 0040 records
why v0.2 could not simply add a field, and ``techtree-di5`` is where the live
write path cuts over and the v0.1 shape becomes read-only history.
"""

from __future__ import annotations

import re
from collections.abc import Collection
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
    "AgentSpecV2",
    "BudgetSpec",
    "CampaignContext",
    "CampaignMetadata",
    "CampaignSpec",
    "CampaignSpecV2",
    "CampaignTaskset",
    "EnvironmentSpec",
    "EvidenceRequirements",
    "EvidenceRequirementsV2",
    "ExecutionSpec",
    "HarnessSpec",
    "HarnessSpecV2",
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


class HarnessSpecV2(ProtocolModel):
    """The skills inserted into the subject harness.

    Which harness that is — its id and its version — is the execution plan's
    subject plane, and is not restated here. A Campaign that named the harness
    as well could disagree with the plan it is bound to, and there would be no
    principled way to say which of the two ran.
    """

    use_bundled_skill: bool
    skills: list[ArtifactRef]


class AgentSpecV2(ProtocolModel):
    """One named agent, complete, under the v0.2 Campaign."""

    model: ModelSpec
    sampling: SamplingSpec
    harness: HarnessSpecV2
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


class EvidenceRequirementsV2(ProtocolModel):
    """Which evidence a valid episode must carry, under the v0.2 Campaign.

    That a Verifiers episode is required is the execution plan's evidence
    plane, so it is not restated here. What remains is the requirement the
    plan does not speak to: whether the subject's runtime must be receipted.
    """

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


class _CampaignScience(ProtocolModel):
    """The scientific contract both Campaign documents state identically.

    This is not a document and is never stored, published, or digested on its
    own: it has no ``schema_version`` and no ``kind``, so nothing can serialize
    it or mistake it for a Campaign. It exists so that the rules below are
    written once, and so that the two Campaign documents are *siblings* — a
    v0.2 Campaign is not a v0.1 Campaign with extras, and a function that asks
    for one will not silently accept the other.
    """

    metadata: CampaignMetadata
    context: CampaignContext
    taskset: CampaignTaskset
    environment: EnvironmentSpec
    mutation_contract: MutationContract
    execution: ExecutionSpec
    scoring: ScoringSpec
    budgets: BudgetSpec
    data_policy_digest: Digest

    @model_validator(mode="after")
    def _check_the_comparison_is_controlled(self) -> Self:
        """Enforce the rules that read only the shared scientific fields."""
        if self.taskset.selection.num_rollouts != 1:
            raise ValueError("v0.1 scores one rollout per task; num_rollouts must be 1")

        if self.mutation_contract.target_agent != SUBJECT_AGENT:
            raise ValueError("the mutation contract must target the subject agent")
        return self


def _check_the_baseline_is_the_declared_one(
    *,
    agent_names: Collection[str],
    mutation_kind: MutationKind,
    baseline_skills: int,
    use_bundled_skill: bool,
) -> None:
    """Check the subject agent against the mutation the Campaign declares.

    Both Campaign documents describe the baseline side of the comparison, so
    both answer to this rule; only the shape of the agent they hold differs,
    which is why the rule takes the three facts it needs rather than an agent.
    """
    if set(agent_names) != {SUBJECT_AGENT}:
        raise ValueError(
            f"a Campaign defines exactly one agent named {SUBJECT_AGENT!r}; "
            f"got {sorted(agent_names)}"
        )

    # The Campaign describes the baseline, so the subject harness carries the
    # skill list the baseline side of the comparison starts from, and which
    # list that is follows from the mutation kind (spec section 3.1).
    if mutation_kind is MutationKind.SKILL_INSERTION:
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
    if use_bundled_skill:
        raise ValueError(
            "use_bundled_skill is false for the whole of WP0-WP5; a bundled "
            "skill would be an uncontrolled second difference"
        )


class CampaignSpec(_CampaignScience):
    """The complete scientific and execution contract."""

    # Frozen. Every published v0.1 proof recomputes this exact object's digest
    # from the bytes it stored, so a field added here would invalidate evidence
    # that has already been signed, and the docstring stays as it was because
    # it is published in schemas/v1alpha1/campaign.schema.json.

    schema_version: Literal["techtree.campaign.v1alpha1"]
    kind: Literal["Campaign"]
    agents: dict[str, AgentSpec]
    evaluation_backend: EvaluationBackendSpec
    evidence: EvidenceRequirements

    @property
    def subject(self) -> AgentSpec:
        """Return the single subject agent."""
        return self.agents[SUBJECT_AGENT]

    @model_validator(mode="after")
    def _check_campaign_contract(self) -> Self:
        """Enforce every WP0–WP5 Campaign rule from spec section 11.5."""
        subject = self.agents.get(SUBJECT_AGENT)
        _check_the_baseline_is_the_declared_one(
            agent_names=self.agents,
            mutation_kind=self.mutation_contract.kind,
            baseline_skills=len(subject.harness.skills) if subject else 0,
            use_bundled_skill=bool(subject and subject.harness.use_bundled_skill),
        )

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


class CampaignSpecV2(_CampaignScience):
    """A Campaign that binds exactly one resolved execution plan.

    Plan v0.2, "Campaign and execution-plan ownership": the plan is not a
    mutable run-time choice beneath an already frozen Campaign. Because the
    digest is a field, selecting a different evaluation engine, execution
    backend, subject backend, or evidence backend changes the Campaign's own
    canonical bytes, so a backend change can only ever produce a *different*
    Campaign — never a quiet reinterpretation of an existing one.

    The digest is carried rather than the plan itself, which is the same shape
    ``data_policy_digest`` already has and for the same reason: a Campaign
    points at the immutable objects it rests on, and each of those objects is
    fetched, digested, and checked on its own terms.

    Three things the v0.1 document carries are absent here, because the plan
    now owns them and a fact stated twice is a fact that can disagree with
    itself:

    ``evaluation_backend``
        Who orchestrated the run is the plan's execution plane.
    ``agents.subject.harness.id`` and ``.version``
        Which harness is measured is the plan's subject plane.
    ``evidence.verifiers_episode``
        That native episode evidence is required is the plan's evidence plane.

    This is a sibling of :class:`CampaignSpec`, not a refinement of it. The two
    share the scientific contract and nothing else, and neither validates as
    the other.
    """

    schema_version: Literal["techtree.campaign.v2"]
    kind: Literal["Campaign"]
    agents: dict[str, AgentSpecV2]
    evidence: EvidenceRequirementsV2
    execution_plan_digest: Digest

    @property
    def subject(self) -> AgentSpecV2:
        """Return the single subject agent."""
        return self.agents[SUBJECT_AGENT]

    @model_validator(mode="after")
    def _check_campaign_contract(self) -> Self:
        """Enforce the Campaign rules the execution plan does not own."""
        subject = self.agents.get(SUBJECT_AGENT)
        _check_the_baseline_is_the_declared_one(
            agent_names=self.agents,
            mutation_kind=self.mutation_contract.kind,
            baseline_skills=len(subject.harness.skills) if subject else 0,
            use_bundled_skill=bool(subject and subject.harness.use_bundled_skill),
        )

        if self.evidence.runtime_evidence != "not_required":
            raise ValueError(
                "runtime evidence is not collected before WP6, so a Campaign "
                "that required it could never produce a valid episode"
            )
        return self
