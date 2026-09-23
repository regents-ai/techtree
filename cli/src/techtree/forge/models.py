"""What a forge build and a forge run record. ``docs/plan/repo2rlenv-local-lane.md``.

Three documents live in a build directory. ``build.json`` says what was built
from what: a typed repository or Skill source around shared task commitments.
The repository branch owns its Git and Repo2RLEnv evidence.
``qualification.json`` says which of the
committed tasks proved out under the model-free checks and which did not, with
the rewards each check observed. ``progress.json`` preserves the last observed
phase and partial evidence. All are private local evidence about a mutable local
subject, not published artifacts.

A forge run starts from a fourth document, the run specification
(:class:`ForgeRunSpec`). It is the experiment's contract, written before any
result exists: which qualified tasks, which grading, which Hermes, which model,
what starting state, and which Skill, if any. Two specifications are comparable
only when they differ in the Skill alone; :mod:`techtree.forge.comparability`
computes that rather than asserting it.

A revision (:class:`ForgeRevisionRecord`) is one more Skill declared against a
finished comparison: the same specification with the Skill alone replaced,
screened against the tasks' hidden material, and once measured, its own run
and comparison named beside the verdict.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final, Literal, Self

from pydantic import Field, StringConstraints, field_validator, model_validator

from techtree.canonical import verify_object_digest
from techtree.errors import ValidationError
from techtree.models.base import (
    Digest,
    JsonValue,
    NonEmptyString,
    ProtocolModel,
    UtcDateTime,
)
from techtree.models.experiment import ManifestComparison
from techtree.models.skill import SkillFile

__all__ = [
    "BASE_IMAGE_REFERENCE",
    "FORGE_BUILD_SCHEMA_VERSION",
    "FORGE_COLLECTION_ACCEPTANCE_SCHEMA_VERSION",
    "FORGE_COLLECTION_SCHEMA_VERSION",
    "FORGE_COMPARISON_SCHEMA_VERSION",
    "FORGE_CONSTRUCTION_APPROVAL_SCHEMA_VERSION",
    "FORGE_CONSTRUCTION_CALL_SCHEMA_VERSION",
    "FORGE_CONSTRUCTION_PACKAGE_SCHEMA_VERSION",
    "FORGE_CONSTRUCTION_RUN_SCHEMA_VERSION",
    "FORGE_CONSTRUCTION_SCHEMA_VERSION",
    "FORGE_PLAN_APPROVAL_SCHEMA_VERSION",
    "FORGE_PLAN_ATTEMPT_SCHEMA_VERSION",
    "FORGE_PLAN_SCHEMA_VERSION",
    "FORGE_PROGRESS_SCHEMA_VERSION",
    "FORGE_PROPOSAL_SCHEMA_VERSION",
    "FORGE_QUALIFICATION_SCHEMA_VERSION",
    "FORGE_REVISION_SCHEMA_VERSION",
    "FORGE_RUN_SCHEMA_VERSION",
    "FORGE_RUN_SPEC_SCHEMA_VERSION",
    "FORGE_SOURCE_SCHEMA_VERSION",
    "FORGE_TASK_CONTENT_SCHEMA_VERSION",
    "FORGE_TASK_SET_SCHEMA_VERSION",
    "MAX_PLANNED_TASKS",
    "VERDICT_MINIMUM_PAIRS",
    "AgentSkillName",
    "ForgeAgentSpec",
    "ForgeArm",
    "ForgeArmTotals",
    "ForgeAttemptOutcome",
    "ForgeAttemptPair",
    "ForgeAttemptRecord",
    "ForgeAuthoringCapabilities",
    "ForgeBaseImage",
    "ForgeBuildFailure",
    "ForgeBuildPhase",
    "ForgeBuildProgress",
    "ForgeBuildRecord",
    "ForgeBuildStatus",
    "ForgeCollectionAcceptance",
    "ForgeCollectionCandidate",
    "ForgeCollectionMember",
    "ForgeCollectionParent",
    "ForgeCollectionRecord",
    "ForgeCollectionReview",
    "ForgeCollectionState",
    "ForgeCollectionStatus",
    "ForgeComparisonRecord",
    "ForgeComparisonStatus",
    "ForgeConstructionApproval",
    "ForgeConstructionCall",
    "ForgeConstructionCallReview",
    "ForgeConstructionCallState",
    "ForgeConstructionDisclosure",
    "ForgeConstructionLimits",
    "ForgeConstructionPackage",
    "ForgeConstructionRecord",
    "ForgeConstructionReview",
    "ForgeConstructionRun",
    "ForgeConstructionState",
    "ForgeConstructionStatus",
    "ForgeConstructionTaskStatus",
    "ForgeCreatedFile",
    "ForgeCreatedPackage",
    "ForgeCreatorRecipe",
    "ForgeEvidence",
    "ForgeGradingSpec",
    "ForgeInitialState",
    "ForgeLanguage",
    "ForgeLimits",
    "ForgeModelSpec",
    "ForgePairResult",
    "ForgePlanApproval",
    "ForgePlanAttempt",
    "ForgePlanAttemptState",
    "ForgePlanDisclosure",
    "ForgePlanLimits",
    "ForgePlanRecord",
    "ForgePlanReview",
    "ForgePlanState",
    "ForgePlanStatus",
    "ForgePlanningRecipe",
    "ForgePlatform",
    "ForgeProposalParent",
    "ForgeProposalRecord",
    "ForgeProposalStatus",
    "ForgeProposedTask",
    "ForgeProposedTaskName",
    "ForgeQualification",
    "ForgeRefusalReason",
    "ForgeRepositorySource",
    "ForgeRevisionRecord",
    "ForgeRevisionStatus",
    "ForgeRunRecord",
    "ForgeRunSpec",
    "ForgeRunStatus",
    "ForgeSamplingSpec",
    "ForgeScreeningFinding",
    "ForgeSkillDeclaration",
    "ForgeSkillName",
    "ForgeSkillSource",
    "ForgeSkillSpec",
    "ForgeSourceEntry",
    "ForgeSourceLineage",
    "ForgeSourceRecord",
    "ForgeSourceRefusal",
    "ForgeSourceStatus",
    "ForgeTaskConsistency",
    "ForgeTaskId",
    "ForgeTaskRegression",
    "ForgeUnsupportedReason",
    "ForgeUsage",
    "ForgeVerdict",
    "GenerationSummary",
    "QualificationCheck",
    "RepositoryTaskQualification",
    "SkillTaskQualification",
    "TaskContentEntry",
    "TaskContentManifest",
    "TaskQualification",
    "TaskQualificationEvidence",
    "TaskSetCommitment",
    "forge_verdict",
    "proposal_content",
]

FORGE_BUILD_SCHEMA_VERSION: Final = "techtree.forge-build.v1alpha3"
FORGE_PROGRESS_SCHEMA_VERSION: Final = "techtree.forge-progress.v1alpha3"
FORGE_QUALIFICATION_SCHEMA_VERSION: Final = "techtree.forge-qualification.v1alpha4"
FORGE_RUN_SCHEMA_VERSION: Final = "techtree.forge-run.v1alpha1"
FORGE_RUN_SPEC_SCHEMA_VERSION: Final = "techtree.forge-run-spec.v1alpha1"
FORGE_TASK_CONTENT_SCHEMA_VERSION: Final = "techtree.forge-task-content.v1alpha1"
FORGE_TASK_SET_SCHEMA_VERSION: Final = "techtree.forge-task-set.v1alpha1"

type ForgeTaskId = Annotated[
    str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
]

#: The Docker platforms Repo2RLEnv builds for. The host's own is chosen; an
#: image emulated for a foreign architecture would time out the tests.
type ForgePlatform = Literal["linux/arm64", "linux/amd64"]
type ForgeBuildPhase = Literal[
    "preparing",
    "admission",
    "cloning",
    "bootstrap",
    "generation",
    "content",
    "qualification",
    "completed",
]


class ForgeLanguage(StrEnum):
    """The language hint Repo2RLEnv normalizes test commands by."""

    PYTHON = "python"
    NODE = "node"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    C_CPP = "c_cpp"


class GenerationSummary(ProtocolModel):
    """What the ``commit_runtime`` pipeline reported for one build."""

    candidates: int = Field(ge=0)
    emitted: int = Field(ge=0)
    skipped: int = Field(ge=0)
    skip_reasons: dict[str, int]
    tasks: list[ForgeTaskId]

    @model_validator(mode="after")
    def validate_membership(self) -> Self:
        if self.emitted != len(self.tasks):
            raise ValueError("emitted task count does not match task membership")
        if len(set(self.tasks)) != len(self.tasks):
            raise ValueError("duplicate task ids in generation membership")
        return self


class TaskContentEntry(ProtocolModel):
    """One relative path; only bytes, kind and owner-executable bit are committed."""

    path: NonEmptyString
    kind: Literal["file", "directory"]
    executable: bool
    size: int = Field(ge=0)
    digest: Digest | None

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        value.encode("utf-8")
        if (
            "\\" in value
            or "\x00" in value
            or any(part in {"", ".", ".."} for part in value.split("/"))
        ):
            raise ValueError("task content path must be a safe relative UTF-8 path")
        return value

    @model_validator(mode="after")
    def validate_kind(self) -> Self:
        if self.kind == "file" and self.digest is None:
            raise ValueError("file content digest is missing")
        if self.kind == "directory" and (self.digest is not None or self.size != 0):
            raise ValueError("directory entry cannot carry file bytes")
        return self


class TaskContentManifest(ProtocolModel):
    """The complete task tree, sorted by relative path, with no exclusions."""

    schema_version: Literal["techtree.forge-task-content.v1alpha1"]
    task_id: ForgeTaskId
    entries: list[TaskContentEntry]
    content_digest: Digest

    @model_validator(mode="after")
    def validate_commitment(self) -> Self:
        paths = [entry.path for entry in self.entries]
        if paths != sorted(set(paths)):
            raise ValueError("task content paths must be unique and sorted")
        if not verify_object_digest(
            {"schema_version": self.schema_version, "entries": self.entries},
            self.content_digest,
        ):
            raise ValueError("task content digest does not match entries")
        return self


class TaskSetCommitment(ProtocolModel):
    """Commit every task's identity and content in generation's execution order."""

    schema_version: Literal["techtree.forge-task-set.v1alpha1"]
    tasks: list[TaskContentManifest]
    membership_digest: Digest

    @model_validator(mode="after")
    def validate_commitment(self) -> Self:
        if len({task.task_id for task in self.tasks}) != len(self.tasks):
            raise ValueError("duplicate task ids in committed membership")
        if not verify_object_digest(
            {
                "schema_version": self.schema_version,
                "tasks": [
                    {"task_id": task.task_id, "content_digest": task.content_digest}
                    for task in self.tasks
                ],
            },
            self.membership_digest,
        ):
            raise ValueError("ordered membership digest does not match tasks")
        return self


class ForgeRepositorySource(ProtocolModel):
    """The repository inputs and commit-runtime producer's generation evidence."""

    kind: Literal["repository"]
    repository: NonEmptyString
    head_commit: NonEmptyString
    slug: NonEmptyString
    language: ForgeLanguage
    dockerfile_digest: Digest
    test_commands: list[NonEmptyString] = Field(min_length=1)
    limit: int = Field(ge=1)
    bootstrap_image_tag: NonEmptyString
    bootstrap_image_id: NonEmptyString
    repo2rlenv_version: NonEmptyString
    generation: GenerationSummary


#: An image name pinned to a content digest; the only form a task recipe may
#: name an external base image in.
BASE_IMAGE_REFERENCE: Final = r"[a-z0-9][a-z0-9._/:-]*@sha256:[0-9a-f]{64}"


class ForgeBaseImage(ProtocolModel):
    """One release-allow-listed base image, as pulled before the task build."""

    reference: Annotated[str, StringConstraints(pattern=f"^{BASE_IMAGE_REFERENCE}$")]
    image_id: NonEmptyString


class ForgeSkillSource(ProtocolModel):
    """Source Skill commitment and the pinned recipe that produced the tasks.

    The source commitment identifies the retained private Skill snapshot, not
    a Skill supplied to a subject agent. Upstream revision names exact Git
    bytes of the producer, never a fabricated commit for the source Skill.
    The base images are the recipe's external ``FROM`` references, every one
    on the release allow-list and pulled by digest before the offline build.
    """

    kind: Literal["skill"]
    source_skill_digest: Digest
    recipe: NonEmptyString
    recipe_version: NonEmptyString
    producer: NonEmptyString
    producer_version: NonEmptyString
    upstream_url: NonEmptyString
    upstream_revision: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
    harbor_version: NonEmptyString
    base_images: list[ForgeBaseImage]

    @field_validator("base_images")
    @classmethod
    def validate_base_images(cls, value: list[ForgeBaseImage]) -> list[ForgeBaseImage]:
        if not value:
            raise ValueError("a Skill build names at least one base image")
        if len({image.reference for image in value}) != len(value):
            raise ValueError("base images repeat a reference")
        return value


class ForgeBuildRecord(ProtocolModel):
    """One producer's provenance around the shared committed task packages."""

    schema_version: Literal["techtree.forge-build.v1alpha3"]
    build_id: NonEmptyString
    created_at: UtcDateTime
    source: Annotated[
        ForgeRepositorySource | ForgeSkillSource, Field(discriminator="kind")
    ]
    platform: ForgePlatform
    task_set: TaskSetCommitment

    def require_repository_source(self, operation: str) -> ForgeRepositorySource:
        """Refuse operations whose evidence still depends on repository tasks."""
        if not isinstance(self.source, ForgeRepositorySource):
            raise ValidationError(
                f"{operation} currently supports only repository-sourced builds; "
                f"build {self.build_id} has a {self.source.kind} source",
                code="forge_source_unsupported",
                details={
                    "build_id": self.build_id,
                    "source": self.source.kind,
                    "operation": operation,
                },
            )
        return self.source

    @model_validator(mode="after")
    def validate_task_set(self) -> Self:
        if isinstance(
            self.source, ForgeRepositorySource
        ) and self.source.generation.tasks != [
            task.task_id for task in self.task_set.tasks
        ]:
            raise ValueError("committed task count or order differs from generation")
        return self


class QualificationCheck(ProtocolModel):
    """One model-free check on one task, and what it saw."""

    name: NonEmptyString
    passed: bool
    detail: str


class TaskQualificationEvidence(ProtocolModel):
    """What every producer's qualification records about one task.

    The common profile builds the task's image offline, checks that the
    image carries no verifier material, grades a run that does nothing and a
    run of the reference, and keeps every check with what it saw.
    """

    task_id: ForgeTaskId
    task_content_digest: Digest
    image_tag: NonEmptyString
    image_id: str
    control_reward: float | None
    reference_reward: float | None
    checks: list[QualificationCheck]
    qualified: bool


class RepositoryTaskQualification(TaskQualificationEvidence):
    """A repository task's evidence, with the commit and test names it graded."""

    kind: Literal["repository"]
    base_commit: NonEmptyString
    fail_to_pass: int = Field(ge=0)
    pass_to_pass: int = Field(ge=0)


class SkillTaskQualification(TaskQualificationEvidence):
    """A Skill task's evidence: no commit and no test names, only the checks.

    Its recipe cases are graded as the reference is: ``alternative_reward``
    after the package's other correct solution, which must pass, and
    ``wrong_reward`` after its deliberately wrong one, which must fail.
    """

    kind: Literal["skill"]
    alternative_reward: float | None
    wrong_reward: float | None


type TaskQualification = Annotated[
    RepositoryTaskQualification | SkillTaskQualification, Field(discriminator="kind")
]


class ForgeQualification(ProtocolModel):
    """The qualification of every task one build committed."""

    schema_version: Literal["techtree.forge-qualification.v1alpha4"]
    build_id: NonEmptyString
    membership_digest: Digest
    qualified_at: UtcDateTime
    model_calls: Literal[0]
    tasks: list[TaskQualification]
    qualified_task_ids: list[ForgeTaskId]

    @model_validator(mode="after")
    def validate_qualified_membership(self) -> Self:
        if self.qualified_task_ids != [
            task.task_id for task in self.tasks if task.qualified
        ]:
            raise ValueError("qualified task count or order differs from task evidence")
        return self


#: The name a Skill is visible to Hermes under: its directory name, in the
#: identifier form Hermes accepts for a Skill.
type ForgeSkillName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]*$")]


class ForgeArm(StrEnum):
    """Which side of the comparison a run specification describes."""

    BASELINE = "baseline"
    CANDIDATE = "candidate"


class ForgeGradingSpec(ProtocolModel):
    """How a run is scored.

    The procedure is the Harbor task's: ``bash /tests/test.sh`` in a fresh
    container from the task image with the agent's workspace mounted, the
    reward read from ``/logs/verifier/reward.json`` then ``reward.txt``. It is
    executed by this local experiment, not by Verifiers, and is labelled so.
    """

    procedure: Literal["harbor-compatible"]
    executed_by: Literal["local-experiment"]


class ForgeAgentSpec(ProtocolModel):
    """The Hermes that will act: which executable, and what it says it is."""

    harness: Literal["hermes"]
    executable: NonEmptyString
    version: NonEmptyString


class ForgeModelSpec(ProtocolModel):
    """The model the run asks Hermes for.

    Techtree copies no credential: Hermes reads its own authentication store,
    so whatever it can reach under that provider name is what answers.
    """

    provider: NonEmptyString
    model_id: NonEmptyString
    reasoning: NonEmptyString | None
    credential_source: Literal["hermes-auth-store"]


class ForgeInitialState(ProtocolModel):
    """What Hermes starts from: a home Techtree emptied of all but the sign-in."""

    home: Literal["fresh-empty"]
    memory_enabled: Literal[False]


class ForgeSkillSpec(ProtocolModel):
    """The one Skill the candidate arm carries, by content."""

    name: ForgeSkillName
    root_digest: Digest
    files: list[SkillFile] = Field(min_length=1)
    exposure: Literal["preloaded"]


class ForgeLimits(ProtocolModel):
    """Bounds on the agent's time and on its sandbox.

    The agent's wall-clock allowance is the task's own ``[agent].timeout_sec``,
    part of the committed task content rather than repeated here; Hermes is
    given it as its run budget and Techtree enforces it from outside. A
    Hermes one-shot has no turn cap, so none is claimed.
    """

    agent_budget: Literal["task-timeout"]
    turns: Literal["unbounded"]
    container_cpus: int = Field(ge=1)
    container_memory_mb: int = Field(ge=1)
    network: Literal[False]


class ForgeSamplingSpec(ProtocolModel):
    """How many attempts each task gets, and what is *not* controlled.

    Hermes exposes no temperature or seed, so sampling is the provider's
    default on every attempt and is declared as such.
    """

    control: Literal["provider-default"]
    repetitions: int = Field(ge=1)


class ForgeRunSpec(ProtocolModel):
    """One arm of a forge experiment, declared before it runs.

    Everything a Skill-effect claim depends on is here: the build and the
    subset of its qualified tasks, the grading, the agent, the model, the
    starting state, the limits, the sampling plan, and the Skill. Facts the
    experiment cannot establish are listed under ``not_established`` so the
    report can say so instead of implying them.
    """

    schema_version: Literal["techtree.forge-run-spec.v1alpha1"]
    arm: ForgeArm
    build_id: NonEmptyString
    membership_digest: Digest
    task_ids: list[ForgeTaskId] = Field(min_length=1)
    grading: ForgeGradingSpec
    agent: ForgeAgentSpec
    model: ForgeModelSpec
    initial_state: ForgeInitialState
    skill: ForgeSkillSpec | None
    limits: ForgeLimits
    sampling: ForgeSamplingSpec
    not_established: list[NonEmptyString]

    @model_validator(mode="after")
    def validate_arm_skill(self) -> Self:
        if len(set(self.task_ids)) != len(self.task_ids):
            raise ValueError("a task may be named once in a run specification")
        if self.arm is ForgeArm.BASELINE and self.skill is not None:
            raise ValueError("the baseline arm carries no Skill")
        if self.arm is ForgeArm.CANDIDATE and self.skill is None:
            raise ValueError("the candidate arm carries exactly one Skill")
        return self


class ForgeEvidence(StrEnum):
    """The evidence one attempt can leave; a claim needs all of it."""

    USAGE_REPORT = "usage_report"
    AGENT_TRANSCRIPT = "agent_transcript"
    WORKSPACE_PATCH = "workspace_patch"
    VERIFIER_VERDICT = "verifier_verdict"


class ForgeAttemptOutcome(StrEnum):
    """How one attempt ended. Only ``graded`` carries a reward."""

    GRADED = "graded"
    AGENT_TIMED_OUT = "agent_timed_out"
    AGENT_FAILED = "agent_failed"
    VERIFIER_TIMED_OUT = "verifier_timed_out"
    NO_VERDICT = "no_verdict"


class ForgeUsage(ProtocolModel):
    """What Hermes reported about its own run, kept as reported.

    Every field is Hermes' word: the model named here is the model it says
    answered, the cost its own estimate, and ``cost_status`` and
    ``cost_source`` say whether that estimate is one at all — a subscription
    Hermes cannot price is recorded as unpriced, never as free. ``completed``
    and ``failed`` are read rather than the exit code, because Hermes prints
    a failure message and exits zero.
    """

    model: str | None
    provider: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    api_calls: int | None
    estimated_cost_usd: float | None
    cost_status: str | None
    cost_source: str | None
    completed: bool | None
    failed: bool | None
    failure: str | None


class ForgeAttemptRecord(ProtocolModel):
    """One attempt at one task: what ran, what it left, how it was scored."""

    task_id: ForgeTaskId
    attempt: int = Field(ge=1)
    started_at: UtcDateTime
    finished_at: UtcDateTime
    config_digest: Digest
    hermes_arguments: list[NonEmptyString]
    agent_exit_code: int | None
    agent_timed_out: bool
    agent_seconds: float = Field(ge=0.0)
    usage: ForgeUsage | None
    patch_digest: Digest | None
    verifier_timed_out: bool
    reward: float | None
    reward_details: dict[str, JsonValue]
    outcome: ForgeAttemptOutcome
    evidence: list[ForgeEvidence]

    @model_validator(mode="after")
    def validate_reward_follows_outcome(self) -> Self:
        if (self.reward is not None) != (self.outcome is ForgeAttemptOutcome.GRADED):
            raise ValueError("a reward is recorded exactly when the attempt was graded")
        return self


class ForgeRunRecord(ProtocolModel):
    """A forge run as it stands: its specification's digest and every attempt.

    Written before the first attempt and after every one, so an interrupted
    run keeps what it had. ``state`` says whether it ended, and how.
    """

    schema_version: Literal["techtree.forge-run.v1alpha1"]
    run_id: NonEmptyString
    spec_digest: Digest
    started_at: UtcDateTime
    updated_at: UtcDateTime
    state: Literal["unfinished", "completed", "failed", "cancelled"]
    attempts: list[ForgeAttemptRecord]
    failure: ForgeBuildFailure | None


class ForgeRunStatus(ProtocolModel):
    """A run read back from its directory."""

    run_id: NonEmptyString
    path: NonEmptyString
    spec: ForgeRunSpec
    record: ForgeRunRecord


FORGE_COMPARISON_SCHEMA_VERSION: Final = "techtree.forge-comparison.v1alpha2"

#: Fewer graded pairs than this and no verdict is given.
VERDICT_MINIMUM_PAIRS: Final = 3


class ForgePairResult(StrEnum):
    """What one paired attempt says about the Skill.

    A pair is resolved only when both arms were graded; any attempt that
    ended another way leaves the pair ``unresolved``, never a loss and never
    a zero.
    """

    WIN = "win"
    LOSS = "loss"
    TIE = "tie"
    UNRESOLVED = "unresolved"


class ForgeAttemptPair(ProtocolModel):
    """The same task and repetition on both arms, side by side.

    A side that has no recorded attempt is ``None`` on both of its fields:
    the run was interrupted before it got there, and the pair says so.
    """

    task_id: ForgeTaskId
    attempt: int = Field(ge=1)
    baseline_outcome: ForgeAttemptOutcome | None
    baseline_reward: float | None
    candidate_outcome: ForgeAttemptOutcome | None
    candidate_reward: float | None
    delta: float | None
    result: ForgePairResult

    @model_validator(mode="after")
    def validate_result_follows_rewards(self) -> Self:
        graded = self.baseline_reward is not None and self.candidate_reward is not None
        if graded != (self.result is not ForgePairResult.UNRESOLVED):
            raise ValueError("a pair is resolved exactly when both arms were graded")
        if graded != (self.delta is not None):
            raise ValueError("a difference is recorded exactly when both were graded")
        return self


class ForgeVerdict(StrEnum):
    """What the comparison says about the Skill, decided by these rules in order.

    ``inconclusive`` when any planned pair is unresolved or fewer than
    :data:`VERDICT_MINIMUM_PAIRS` pairs were graded; ``mixed`` with at least
    one win and one loss; ``improved`` with wins and no losses; ``regressed``
    with losses and no wins; ``no_difference`` when every graded pair tied.
    """

    INCONCLUSIVE = "inconclusive"
    MIXED = "mixed"
    IMPROVED = "improved"
    REGRESSED = "regressed"
    NO_DIFFERENCE = "no_difference"


class ForgeTaskRegression(ProtocolModel):
    """One task the Skill lost at least once: which attempts, and which it won."""

    task_id: ForgeTaskId
    attempts_lost: list[int]
    attempts_won: list[int]

    @model_validator(mode="after")
    def validate_lost_at_least_once(self) -> Self:
        if not self.attempts_lost:
            raise ValueError("a regression names at least one lost attempt")
        return self


class ForgeTaskConsistency(ProtocolModel):
    """How one task went across its attempts, and whether it went both ways."""

    task_id: ForgeTaskId
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    ties: int = Field(ge=0)
    unresolved: int = Field(ge=0)
    went_both_ways: bool

    @model_validator(mode="after")
    def validate_both_ways_follows_counts(self) -> Self:
        if self.went_both_ways != (self.wins > 0 and self.losses > 0):
            raise ValueError("a task went both ways exactly when it won and lost")
        return self


class ForgeArmTotals(ProtocolModel):
    """What one arm did and used, added up over its recorded attempts.

    ``mean_reward`` is over the arm's graded attempts alone. ``cost_usd`` is
    a sum only when every attempt with a usage report carried a dollar
    figure; otherwise it is ``None`` and ``cost_statuses`` says what Hermes
    reported instead, because an unpriced attempt is not a free one.
    """

    run_id: NonEmptyString
    state: Literal["unfinished", "completed", "failed", "cancelled"]
    attempts_planned: int = Field(ge=0)
    attempts_recorded: int = Field(ge=0)
    attempts_graded: int = Field(ge=0)
    mean_reward: float | None
    agent_seconds: float = Field(ge=0.0)
    api_calls: int | None
    total_tokens: int | None
    cost_usd: float | None
    cost_statuses: list[NonEmptyString]


class ForgeComparisonRecord(ProtocolModel):
    """Two arms of one experiment, paired task by task.

    ``complete`` is true only when every planned pair was graded on both
    sides; anything less is a partial observation. ``verdict`` is the one
    word the comparison stands behind, ``regressions`` every task the Skill
    lost at least once, and ``consistency`` how each task went across its
    attempts; ``summary`` leads with the verdict in words. The comparability
    gate's finding is kept whole so a reader can see what was allowed to
    differ.
    """

    schema_version: Literal["techtree.forge-comparison.v1alpha2"]
    comparison_id: NonEmptyString
    created_at: UtcDateTime
    build_id: NonEmptyString
    baseline_run_id: NonEmptyString
    candidate_run_id: NonEmptyString
    skill_name: ForgeSkillName
    skill_digest: Digest
    comparability: ManifestComparison
    baseline: ForgeArmTotals
    candidate: ForgeArmTotals
    pairs: list[ForgeAttemptPair]
    pairs_planned: int = Field(ge=0)
    pairs_graded: int = Field(ge=0)
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    ties: int = Field(ge=0)
    unresolved: int = Field(ge=0)
    mean_delta: float | None
    complete: bool
    repetitions: int = Field(ge=1)
    verdict: ForgeVerdict
    regressions: list[ForgeTaskRegression]
    consistency: list[ForgeTaskConsistency]
    summary: NonEmptyString
    not_established: list[NonEmptyString]

    @model_validator(mode="after")
    def validate_counts_agree(self) -> Self:
        if self.wins + self.losses + self.ties != self.pairs_graded:
            raise ValueError("wins, losses and ties add up to the graded pairs")
        if self.pairs_graded + self.unresolved != self.pairs_planned:
            raise ValueError("graded and unresolved pairs add up to the planned pairs")
        if len(self.pairs) != self.pairs_planned:
            raise ValueError("every planned pair is listed, resolved or not")
        if self.complete != (self.unresolved == 0):
            raise ValueError(
                "a comparison is complete exactly when no pair is unresolved"
            )
        if (self.mean_delta is None) != (self.pairs_graded == 0):
            raise ValueError("a mean difference exists exactly when a pair was graded")
        if self.verdict is not forge_verdict(
            wins=self.wins,
            losses=self.losses,
            graded=self.pairs_graded,
            unresolved=self.unresolved,
        ):
            raise ValueError("the verdict follows the rules from the counts")
        if [r.task_id for r in self.regressions] != [
            c.task_id for c in self.consistency if c.losses > 0
        ]:
            raise ValueError("the regressions are exactly the tasks with a loss")
        if sum(c.wins for c in self.consistency) != self.wins:
            raise ValueError("the tasks' wins add up to the comparison's")
        if sum(c.losses for c in self.consistency) != self.losses:
            raise ValueError("the tasks' losses add up to the comparison's")
        if sum(c.ties for c in self.consistency) != self.ties:
            raise ValueError("the tasks' ties add up to the comparison's")
        if sum(c.unresolved for c in self.consistency) != self.unresolved:
            raise ValueError("the tasks' unresolved pairs add up to the comparison's")
        return self


def forge_verdict(
    *, wins: int, losses: int, graded: int, unresolved: int
) -> ForgeVerdict:
    """Apply the verdict rules, in their order, to the counts."""
    if unresolved > 0 or graded < VERDICT_MINIMUM_PAIRS:
        return ForgeVerdict.INCONCLUSIVE
    if wins and losses:
        return ForgeVerdict.MIXED
    if wins:
        return ForgeVerdict.IMPROVED
    if losses:
        return ForgeVerdict.REGRESSED
    return ForgeVerdict.NO_DIFFERENCE


class ForgeComparisonStatus(ProtocolModel):
    """A comparison read back from its directory, with where its report is."""

    comparison_id: NonEmptyString
    path: NonEmptyString
    report_path: NonEmptyString
    record: ForgeComparisonRecord


FORGE_REVISION_SCHEMA_VERSION: Final = "techtree.forge-revision.v1alpha1"


class ForgeScreeningFinding(ProtocolModel):
    """One line of a revised Skill that also occurs in a task's hidden material.

    Screening is evidence, not a verdict: a line shared with the reference
    patch or the tests is recorded here, on the revision, so the person who
    approves the second run sees it, and the report can say the Skill may
    carry the answer rather than the method. The excerpt is bounded and the
    line is named by its number in the Skill, never by the hidden file's.
    """

    task_id: ForgeTaskId
    material: Literal["reference_patch", "tests", "test_names"]
    skill_path: NonEmptyString
    line: int = Field(ge=1)
    excerpt: NonEmptyString


class ForgeRevisionRecord(ProtocolModel):
    """One revised Skill declared against a finished comparison.

    Written when the revision is prepared and once more when it has been
    measured. ``state`` says which: a measured revision names the run it
    made, the comparison of that run against the same baseline, and a
    one-line verdict against the comparison it revised from. It is kept
    whether it improved or regressed; nothing here chooses.
    """

    schema_version: Literal["techtree.forge-revision.v1alpha1"]
    revision_id: NonEmptyString
    created_at: UtcDateTime
    updated_at: UtcDateTime
    comparison_id: NonEmptyString
    build_id: NonEmptyString
    baseline_run_id: NonEmptyString
    parent_run_id: NonEmptyString
    parent_skill_digest: Digest
    skill: ForgeSkillSpec
    spec_digest: Digest
    comparability: ManifestComparison
    screening: list[ForgeScreeningFinding]
    state: Literal["prepared", "measured"]
    measured_run_id: NonEmptyString | None
    measured_comparison_id: NonEmptyString | None
    verdict: NonEmptyString | None

    @model_validator(mode="after")
    def validate_measurement(self) -> Self:
        measured = self.state == "measured"
        facts = (self.measured_run_id, self.measured_comparison_id, self.verdict)
        if measured != all(fact is not None for fact in facts):
            raise ValueError(
                "a measured revision names its run, its comparison and its verdict"
            )
        if not measured and any(fact is not None for fact in facts):
            raise ValueError("a prepared revision has no measurement yet")
        if self.skill.root_digest == self.parent_skill_digest:
            raise ValueError("a revision differs from the Skill it revises")
        return self


class ForgeRevisionStatus(ProtocolModel):
    """A revision read back from its directory, with the specification it runs."""

    revision_id: NonEmptyString
    path: NonEmptyString
    spec: ForgeRunSpec
    record: ForgeRevisionRecord


class ForgeBuildFailure(ProtocolModel):
    """A bounded failure description, without command output or model dumps."""

    code: NonEmptyString
    message: NonEmptyString
    error_type: NonEmptyString


class ForgeBuildProgress(ProtocolModel):
    """Last observed work, not evidence that a process is still running."""

    schema_version: Literal["techtree.forge-progress.v1alpha3"]
    build_id: NonEmptyString
    #: The repository path or the imported task directory the build began from.
    origin: NonEmptyString
    started_at: UtcDateTime
    updated_at: UtcDateTime
    phase: ForgeBuildPhase
    state: Literal["unfinished", "failed", "cancelled", "completed"]
    membership_digest: Digest | None
    current_task_id: ForgeTaskId | None
    completed_tasks: list[TaskQualification]
    failure: ForgeBuildFailure | None

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if self.updated_at < self.started_at:
            raise ValueError("progress timestamp precedes its start")
        if (self.state in {"failed", "cancelled"}) != (self.failure is not None):
            raise ValueError("progress terminal state and failure receipt disagree")
        if self.state == "completed" and (
            self.phase != "completed" or self.current_task_id is not None
        ):
            raise ValueError("completed progress must have no unfinished task")
        return self


class ForgeBuildStatus(ProtocolModel):
    """Stored evidence and explicit completion facts, including unfinished builds."""

    build_id: NonEmptyString
    build: ForgeBuildRecord | None
    path: NonEmptyString
    tasks_path: NonEmptyString
    qualification: ForgeQualification | None
    progress: ForgeBuildProgress | None
    generation_finished: bool | None
    qualification_finished: bool | None
    usable_tasks: int | None = Field(ge=0)

    @model_validator(mode="after")
    def validate_evidence_linkage(self) -> Self:
        build, progress, qualification = self.build, self.progress, self.qualification
        if build is None and progress is None:
            raise ValueError("neither a build nor a progress record exists")
        for record in (build, progress, qualification):
            if record is not None and record.build_id != self.build_id:
                raise ValueError("stored build id differs from requested build")
        if progress is not None:
            self._validate_progress(progress, build)
            if progress.state == "completed" and qualification is None:
                raise ValueError("completed progress has no final qualification")
        if (build is not None) != (self.generation_finished is True):
            raise ValueError("generation completion fact contradicts build evidence")
        if qualification is None:
            if self.qualification_finished is True or self.usable_tasks is not None:
                raise ValueError(
                    "qualification completion or usable count has no final evidence"
                )
            return self
        if build is None:
            raise ValueError("qualification has no committed build")
        if self.qualification_finished is not True or self.usable_tasks != len(
            qualification.qualified_task_ids
        ):
            raise ValueError(
                "qualification completion or usable count contradicts evidence"
            )
        if qualification.membership_digest != build.task_set.membership_digest:
            raise ValueError("qualification membership digest differs from build")
        if [task.task_id for task in qualification.tasks] != [
            task.task_id for task in build.task_set.tasks
        ]:
            raise ValueError("qualification task count or order differs from build")
        if [task.task_content_digest for task in qualification.tasks] != [
            task.content_digest for task in build.task_set.tasks
        ]:
            raise ValueError("qualification task content digests differ from build")
        if (
            progress is not None
            and progress.state == "completed"
            and progress.completed_tasks != qualification.tasks
        ):
            raise ValueError("completed progress differs from final task evidence")
        return self

    @staticmethod
    def _validate_progress(
        progress: ForgeBuildProgress, build: ForgeBuildRecord | None
    ) -> None:
        if progress.phase in {"qualification", "completed"} and (
            build is None or progress.membership_digest is None
        ):
            raise ValueError("qualification phase has no committed build or membership")
        if build is None:
            if (
                progress.membership_digest is not None
                or progress.completed_tasks
                or progress.current_task_id is not None
            ):
                raise ValueError("partial task evidence has no committed build")
            return
        if progress.membership_digest not in {None, build.task_set.membership_digest}:
            raise ValueError("progress membership digest differs from build")
        if progress.membership_digest is None and (
            progress.completed_tasks or progress.current_task_id is not None
        ):
            raise ValueError("partial task evidence has no membership commitment")
        expected = build.task_set.tasks[: len(progress.completed_tasks)]
        observed = [
            (task.task_id, task.task_content_digest)
            for task in progress.completed_tasks
        ]
        if observed != [(task.task_id, task.content_digest) for task in expected]:
            raise ValueError(
                "partial task evidence is not the committed ordered prefix"
            )
        if progress.current_task_id is not None:
            remaining = [
                task.task_id
                for task in build.task_set.tasks[len(progress.completed_tasks) :]
            ]
            if not remaining or progress.current_task_id != remaining[0]:
                raise ValueError("current task differs from next committed task")


FORGE_SOURCE_SCHEMA_VERSION: Final = "techtree.forge-source.v1alpha1"

#: A Skill's name as the Agent Skills specification allows it: lowercase
#: letters and digits in hyphen-separated runs, at most 64 characters.
type AgentSkillName = Annotated[
    str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=64)
]

#: Why one file of a Source Skill cannot be carried: a hidden path (never
#: opened), a link, a device or other special file, a file or directory that
#: cannot be read, a type Techtree does not admit (scripts, binaries,
#: images), bytes that are not UTF-8 text, a file over the per-file limit,
#: or a path that differs from another only by case.
type ForgeUnsupportedReason = Literal[
    "hidden",
    "symlink",
    "special",
    "unreadable",
    "file_type",
    "not_text",
    "too_large",
    "case_collision",
]

#: Why a whole Source Skill is refused: a file its instructions need cannot
#: be carried, a link names a file that is not there or one outside the
#: Skill, the SKILL.md header is not one Techtree reads, or the admitted
#: files exceed the count or byte limits.
type ForgeRefusalReason = Literal[
    "required_unsupported",
    "missing_reference",
    "outside_reference",
    "declaration",
    "too_many_files",
    "too_many_bytes",
]


class ForgeSourceEntry(ProtocolModel):
    """One entry of a Source Skill as it was found, and what became of it.

    ``required`` means the Skill's instructions name it: SKILL.md itself, and
    every path SKILL.md or a file it names mentions, followed through the
    admitted text. A hidden directory, and a directory that cannot be read,
    is one entry; nothing under it is opened.
    """

    path: NonEmptyString
    kind: Literal["file", "symlink", "directory", "special"]
    size: int | None = Field(ge=0)
    digest: Digest | None
    disposition: Literal["admitted", "unsupported"]
    reason: ForgeUnsupportedReason | None
    required: bool

    @model_validator(mode="after")
    def validate_disposition(self) -> Self:
        if (self.disposition == "admitted") != (self.reason is None):
            raise ValueError("an unsupported entry says why, an admitted one does not")
        if self.disposition == "admitted" and (
            self.kind != "file" or self.size is None or self.digest is None
        ):
            raise ValueError("an admitted entry is a file with its size and digest")
        return self


class ForgeSkillDeclaration(ProtocolModel):
    """What SKILL.md's header declares, per the Agent Skills specification.

    Declarations only: ``allowed_tools`` is what the Skill asks for, and it
    grants nothing. Capabilities granted to authoring or to task execution
    are separate facts on the approvals that grant them.
    """

    name: AgentSkillName
    description: Annotated[str, StringConstraints(min_length=1, max_length=1024)]
    license: NonEmptyString | None
    compatibility: (
        Annotated[str, StringConstraints(min_length=1, max_length=500)] | None
    )
    metadata: dict[NonEmptyString, str]
    allowed_tools: list[NonEmptyString]
    other_fields: dict[NonEmptyString, str]


class ForgeSourceRefusal(ProtocolModel):
    """One reason the Source Skill cannot be used, naming the path concerned."""

    path: NonEmptyString
    reason: ForgeRefusalReason
    message: NonEmptyString


class ForgeSourceLineage(ProtocolModel):
    """The inspected Skill a reduced derivative was made from."""

    parent_source_id: NonEmptyString
    parent_admitted_digest: Digest


class ForgeSourceRecord(ProtocolModel):
    """One inspection of a Source Skill: the first record of an environment.

    Written once and never changed. Every entry found is listed with its
    disposition; ``admitted_files`` and ``admitted_digest`` describe exactly
    the bytes an admitted source keeps under ``skill/`` beside this record,
    the bytes that may later be disclosed to an authoring model. A refused
    source keeps no bytes; its record is what a derivative's lineage names.
    """

    schema_version: Literal["techtree.forge-source.v1alpha1"]
    source_id: NonEmptyString
    created_at: UtcDateTime
    origin: NonEmptyString
    state: Literal["admitted", "refused"]
    declaration: ForgeSkillDeclaration | None
    entries: list[ForgeSourceEntry]
    admitted_files: list[SkillFile]
    admitted_digest: Digest
    refusals: list[ForgeSourceRefusal]
    lineage: ForgeSourceLineage | None

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        if (self.state == "refused") != bool(self.refusals):
            raise ValueError(
                "a refused source says why, an admitted one has no refusal"
            )
        if self.state == "admitted" and self.declaration is None:
            raise ValueError("an admitted source carries its declaration")
        admitted = [
            (entry.path, entry.size, entry.digest)
            for entry in self.entries
            if entry.disposition == "admitted"
        ]
        if admitted != [(f.path, f.size, f.digest) for f in self.admitted_files]:
            raise ValueError("admitted files differ from the admitted entries")
        if not verify_object_digest(self.admitted_files, self.admitted_digest):
            raise ValueError("admitted digest does not describe the admitted files")
        return self


class ForgeSourceStatus(ProtocolModel):
    """A Source Skill record read back, with where its kept bytes are."""

    source_id: NonEmptyString
    path: NonEmptyString
    snapshot_path: NonEmptyString | None
    record: ForgeSourceRecord


FORGE_PLAN_SCHEMA_VERSION: Final = "techtree.forge-plan.v1alpha1"
FORGE_PLAN_APPROVAL_SCHEMA_VERSION: Final = "techtree.forge-plan-approval.v1alpha1"
FORGE_PLAN_ATTEMPT_SCHEMA_VERSION: Final = "techtree.forge-plan-attempt.v1alpha1"
FORGE_PROPOSAL_SCHEMA_VERSION: Final = "techtree.forge-proposal.v1alpha1"
FORGE_CONSTRUCTION_SCHEMA_VERSION: Final = "techtree.forge-construction.v1alpha1"
FORGE_CONSTRUCTION_APPROVAL_SCHEMA_VERSION: Final = (
    "techtree.forge-construction-approval.v1alpha1"
)
FORGE_CONSTRUCTION_RUN_SCHEMA_VERSION: Final = (
    "techtree.forge-construction-run.v1alpha1"
)
FORGE_CONSTRUCTION_CALL_SCHEMA_VERSION: Final = (
    "techtree.forge-construction-call.v1alpha1"
)
FORGE_CONSTRUCTION_PACKAGE_SCHEMA_VERSION: Final = (
    "techtree.forge-construction-package.v1alpha1"
)
FORGE_COLLECTION_SCHEMA_VERSION: Final = "techtree.forge-collection.v1alpha1"
FORGE_COLLECTION_ACCEPTANCE_SCHEMA_VERSION: Final = (
    "techtree.forge-collection-acceptance.v1alpha1"
)

#: The most tasks one plan may ask for: Skill2Env's own default workflow count.
MAX_PLANNED_TASKS: Final = 8

#: A proposed task's name: lowercase letters and digits in hyphen-separated runs.
type ForgeProposedTaskName = Annotated[
    str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=64)
]


class ForgePlanningRecipe(ProtocolModel):
    """The planning instructions: Techtree's own text, adapted from Skill2Env."""

    name: Literal["skill2env-planner"]
    instructions_digest: Digest
    upstream_url: NonEmptyString
    upstream_revision: NonEmptyString


class ForgePlanDisclosure(ProtocolModel):
    """Exactly what leaves the machine: the Skill's kept files, inside the prompt.

    ``files`` are the admitted files of the Source Skill, re-read and re-hashed
    from the kept copy; ``prompt_digest`` and ``prompt_bytes`` describe the one
    text sent, which is kept beside the plan as ``prompt.md``.
    """

    files: list[SkillFile] = Field(min_length=1)
    prompt_bytes: int = Field(ge=1)
    prompt_digest: Digest


class ForgeAuthoringCapabilities(ProtocolModel):
    """What the planner or the creator may do besides answer: nothing.

    Hermes is asked for its text-only toolset, which holds no tool, and runs
    with memory off and without its rules, memory or Skills injected.
    """

    tools: Literal["none"]
    toolset: Literal["bot_room"]
    memory_enabled: Literal[False]


class ForgePlanLimits(ProtocolModel):
    """The bounds one planning approval covers."""

    max_tasks: int = Field(ge=1, le=MAX_PLANNED_TASKS)
    attempts: Literal[1]
    wall_seconds: int = Field(ge=1)
    answer_bytes: int = Field(ge=1)


class ForgePlanReview(ProtocolModel):
    """Everything one planning approval binds, and nothing else.

    Its digest is the approval: a changed Skill copy, instruction text,
    Hermes, model, capability or limit is a different review, and an
    approval of the old one does not carry over.
    """

    source_id: NonEmptyString
    source_digest: Digest
    retry_of: NonEmptyString | None
    recipe: ForgePlanningRecipe
    agent: ForgeAgentSpec
    model: ForgeModelSpec
    disclosure: ForgePlanDisclosure
    egress: Literal["model-provider"]
    capabilities: ForgeAuthoringCapabilities
    limits: ForgePlanLimits


class ForgePlanRecord(ProtocolModel):
    """One prepared planning phase, written before anything is sent.

    Never changed. ``planning_digest`` is the digest of ``review``; an
    approval names it, and ``--yes`` continues this plan only while the
    review it would make again is the same.
    """

    schema_version: Literal["techtree.forge-plan.v1alpha1"]
    plan_id: NonEmptyString
    created_at: UtcDateTime
    review: ForgePlanReview
    planning_digest: Digest

    @model_validator(mode="after")
    def validate_digest(self) -> Self:
        if not verify_object_digest(self.review, self.planning_digest):
            raise ValueError("planning digest does not describe the review")
        return self


class ForgePlanApproval(ProtocolModel):
    """A person's approval of one prepared plan, written before the call."""

    schema_version: Literal["techtree.forge-plan-approval.v1alpha1"]
    plan_id: NonEmptyString
    planning_digest: Digest
    approved_at: UtcDateTime
    reviewed_on: Literal["cli", "host-agent"]
    answered_with: Literal["prompt", "yes-flag"]


#: How a planning attempt stands. ``started`` is written before Hermes is
#: launched; an attempt that stays ``started`` after its process has gone
#: never recorded an end, and is read as ``outcome_unknown``.
type ForgePlanAttemptState = Literal[
    "started", "succeeded", "rejected", "failed", "outcome_unknown"
]


class ForgePlanAttempt(ProtocolModel):
    """The one planner call a planning approval covers, checkpointed.

    Written with ``started`` before Hermes is launched and again when it has
    ended. ``succeeded`` names the proposal it made; ``rejected`` means the
    planner answered with something that is not a usable proposal, kept as
    ``answer.txt``; ``failed`` means Hermes said it failed; ``outcome_unknown``
    means it was stopped mid-call, so the provider may or may not have
    answered or charged. None of them is retried.
    """

    schema_version: Literal["techtree.forge-plan-attempt.v1alpha1"]
    plan_id: NonEmptyString
    planning_digest: Digest
    process_id: int = Field(ge=1)
    started_at: UtcDateTime
    updated_at: UtcDateTime
    state: ForgePlanAttemptState
    hermes_arguments: list[NonEmptyString]
    config_digest: Digest
    exit_code: int | None
    stopped: Literal["wall_time", "person"] | None
    seconds: float | None = Field(ge=0.0)
    usage: ForgeUsage | None
    answer_bytes: int | None = Field(ge=0)
    answer_digest: Digest | None
    proposal_id: NonEmptyString | None
    failure: ForgeBuildFailure | None

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if (self.state == "succeeded") != (self.proposal_id is not None):
            raise ValueError("an attempt names a proposal exactly when it succeeded")
        if (self.state in {"rejected", "failed"}) != (self.failure is not None):
            raise ValueError("a rejected or failed attempt says why, no other does")
        if (self.state == "outcome_unknown") != (self.stopped is not None):
            raise ValueError("an attempt with an unknown outcome says what stopped it")
        return self


class ForgeProposedTask(ProtocolModel):
    """One task the planner or the contributor proposes, before anything is built."""

    name: ForgeProposedTaskName
    summary: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    scenario: Annotated[str, StringConstraints(min_length=1, max_length=4000)]
    success_criteria: list[
        Annotated[str, StringConstraints(min_length=1, max_length=1000)]
    ] = Field(min_length=1, max_length=12)
    verifier_strategy: Annotated[str, StringConstraints(min_length=1, max_length=4000)]


class ForgeProposalParent(ProtocolModel):
    """The proposal a contributor's correction was made from."""

    proposal_id: NonEmptyString
    proposal_digest: Digest


class ForgeProposalRecord(ProtocolModel):
    """A set of proposed tasks: the planner's, or a contributor's correction.

    Never changed; a correction is a new proposal naming its parent.
    ``proposal_digest`` covers the Source Skill's digest and the tasks, and is
    what a construction approval will name.
    """

    schema_version: Literal["techtree.forge-proposal.v1alpha1"]
    proposal_id: NonEmptyString
    created_at: UtcDateTime
    source_id: NonEmptyString
    source_digest: Digest
    plan_id: NonEmptyString
    origin: Literal["planner", "contributor"]
    parent: ForgeProposalParent | None
    tasks: list[ForgeProposedTask] = Field(min_length=1)
    proposal_digest: Digest

    @model_validator(mode="after")
    def validate_proposal(self) -> Self:
        if (self.origin == "contributor") != (self.parent is not None):
            raise ValueError("a contributor's proposal names its parent, no other does")
        names = [task.name for task in self.tasks]
        if len(set(names)) != len(names):
            raise ValueError("each proposed task has its own name")
        if not verify_object_digest(
            proposal_content(self.source_digest, self.tasks), self.proposal_digest
        ):
            raise ValueError("proposal digest does not describe the tasks")
        return self


def proposal_content(
    source_digest: Digest, tasks: list[ForgeProposedTask]
) -> dict[str, object]:
    """Return what a proposal digest covers."""
    return {
        "schema_version": FORGE_PROPOSAL_SCHEMA_VERSION,
        "source_digest": source_digest,
        "tasks": tasks,
    }


#: Where a plan stands, read from its records.
type ForgePlanState = Literal[
    "prepared", "running", "succeeded", "rejected", "failed", "outcome_unknown"
]


class ForgePlanStatus(ProtocolModel):
    """A plan read back: its review, its approval and its attempt, if any.

    ``state`` is the reading of those records: ``prepared`` until approved,
    ``running`` while the process that started the attempt is still alive,
    then the attempt's own state, where an attempt left ``started`` by a
    process that is gone reads ``outcome_unknown``.
    """

    plan_id: NonEmptyString
    path: NonEmptyString
    state: ForgePlanState
    record: ForgePlanRecord
    approval: ForgePlanApproval | None
    attempt: ForgePlanAttempt | None


class ForgeProposalStatus(ProtocolModel):
    """A proposal read back from its directory."""

    proposal_id: NonEmptyString
    path: NonEmptyString
    record: ForgeProposalRecord


# ---------------------------------------------------------------------------
# Construction: building task packages from one reviewed proposal
# ---------------------------------------------------------------------------


class ForgeCreatorRecipe(ProtocolModel):
    """The building instructions and the package contract the creator follows."""

    name: Literal["skill2env-creator"]
    instructions_digest: Digest
    contract_digest: Digest
    base_image: NonEmptyString
    upstream_url: NonEmptyString
    upstream_revision: NonEmptyString


class ForgeConstructionCallReview(ProtocolModel):
    """One creator call an approval covers: the task and the exact prompt."""

    task_name: ForgeProposedTaskName
    package_name: Annotated[
        str, StringConstraints(pattern=r"^task_[a-z0-9-]+_[a-z0-9]{8}$")
    ]
    prompt_bytes: int = Field(ge=1)
    prompt_digest: Digest


class ForgeConstructionDisclosure(ProtocolModel):
    """What leaves the machine: per call, one task and the Skill's files."""

    files: list[SkillFile] = Field(min_length=1)
    calls: list[ForgeConstructionCallReview] = Field(min_length=1)


class ForgeConstructionLimits(ProtocolModel):
    """The bounds one construction approval covers."""

    calls: int = Field(ge=1)
    attempts_per_call: Literal[1]
    wall_seconds_per_call: int = Field(ge=1)
    answer_bytes_per_call: int = Field(ge=1)


class ForgeConstructionReview(ProtocolModel):
    """Everything one construction approval covers, bound by one digest.

    ``corrected_by`` lists the corrections of the proposal that existed when
    the review was made; a correction made after it makes the review stale.
    ``source_skill`` is the ``provider/id`` every package's ``task.toml``
    names, and ``platform`` the Docker platform its image is built for.
    """

    proposal_id: NonEmptyString
    proposal_digest: Digest
    corrected_by: list[NonEmptyString]
    source_id: NonEmptyString
    source_digest: Digest
    source_skill: Annotated[
        str, StringConstraints(pattern=r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9._-]+$")
    ]
    retry_of: NonEmptyString | None
    recipe: ForgeCreatorRecipe
    agent: ForgeAgentSpec
    model: ForgeModelSpec
    platform: ForgePlatform
    disclosure: ForgeConstructionDisclosure
    egress: Literal["model-provider"]
    capabilities: ForgeAuthoringCapabilities
    limits: ForgeConstructionLimits

    @model_validator(mode="after")
    def validate_calls(self) -> Self:
        names = [call.task_name for call in self.disclosure.calls]
        if len(set(names)) != len(names):
            raise ValueError("a construction calls the creator once per task")
        if self.limits.calls != len(names):
            raise ValueError("the call limit is the number of calls reviewed")
        return self


class ForgeConstructionRecord(ProtocolModel):
    """A prepared construction: its review and the digest an approval names."""

    schema_version: Literal["techtree.forge-construction.v1alpha1"]
    construction_id: NonEmptyString
    created_at: UtcDateTime
    review: ForgeConstructionReview
    construction_digest: Digest

    @model_validator(mode="after")
    def validate_digest(self) -> Self:
        if not verify_object_digest(self.review, self.construction_digest):
            raise ValueError("construction digest does not describe its review")
        return self


class ForgeConstructionApproval(ProtocolModel):
    """A person's approval of exactly one prepared construction."""

    schema_version: Literal["techtree.forge-construction-approval.v1alpha1"]
    construction_id: NonEmptyString
    construction_digest: Digest
    approved_at: UtcDateTime
    reviewed_on: Literal["cli", "host-agent"]
    answered_with: Literal["prompt", "yes-flag"]


class ForgeConstructionRun(ProtocolModel):
    """The one pass an approval covers, from its start to its end.

    Written before the first call with the process that makes them, and again
    when the pass ends: ``stopped`` is ``person`` when Ctrl-C ended it early.
    """

    schema_version: Literal["techtree.forge-construction-run.v1alpha1"]
    construction_id: NonEmptyString
    process_id: int = Field(ge=1)
    started_at: UtcDateTime
    ended_at: UtcDateTime | None
    stopped: Literal["person"] | None

    @model_validator(mode="after")
    def validate_end(self) -> Self:
        if self.stopped is not None and self.ended_at is None:
            raise ValueError("a pass that was stopped has ended")
        return self


class ForgeConstructionCall(ProtocolModel):
    """One creator call, checkpointed like a planner call.

    Written with ``started`` before Hermes is launched and again when it has
    ended. ``succeeded`` names the package Techtree wrote from the answer;
    ``rejected`` means the answer is not a usable package, kept as
    ``answer.txt``; ``failed`` means Hermes said it failed;
    ``outcome_unknown`` means it was stopped mid-call. None is retried.
    """

    schema_version: Literal["techtree.forge-construction-call.v1alpha1"]
    construction_id: NonEmptyString
    construction_digest: Digest
    task_name: ForgeProposedTaskName
    process_id: int = Field(ge=1)
    started_at: UtcDateTime
    updated_at: UtcDateTime
    state: ForgePlanAttemptState
    hermes_arguments: list[NonEmptyString]
    config_digest: Digest
    exit_code: int | None
    stopped: Literal["wall_time", "person"] | None
    seconds: float | None = Field(ge=0.0)
    usage: ForgeUsage | None
    answer_bytes: int | None = Field(ge=0)
    answer_digest: Digest | None
    package_name: NonEmptyString | None
    failure: ForgeBuildFailure | None

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if (self.state == "succeeded") != (self.package_name is not None):
            raise ValueError("a call names a package exactly when it succeeded")
        if (self.state in {"rejected", "failed"}) != (self.failure is not None):
            raise ValueError("a rejected or failed call says why, no other does")
        if (self.state == "outcome_unknown") != (self.stopped is not None):
            raise ValueError("a call with an unknown outcome says what stopped it")
        return self


class ForgeConstructionPackage(ProtocolModel):
    """Where one written package went: the build that admitted and checked it.

    ``usable_tasks`` is what that build's qualification kept for use; a
    package the importer refused, or whose checks failed or were stopped,
    names the build and says why.
    """

    schema_version: Literal["techtree.forge-construction-package.v1alpha1"]
    construction_id: NonEmptyString
    task_name: ForgeProposedTaskName
    package_name: NonEmptyString
    build_id: NonEmptyString
    usable_tasks: int = Field(ge=0)
    failure: ForgeBuildFailure | None

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if (self.usable_tasks == 0) != (self.failure is not None):
            raise ValueError("a package that cannot be used says why, no other does")
        return self


class ForgeCreatedFile(ProtocolModel):
    """One file of a package, as the creator answered it."""

    path: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    text: str
    executable: bool


class ForgeCreatedPackage(ProtocolModel):
    """A creator's answer: the task's words and its files, but not ``task.toml``.

    Techtree writes ``task.toml`` itself from the pinned contract, as
    Skill2Env's host does; the creator gives the parts only it can know.
    """

    description: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    keywords: list[Annotated[str, StringConstraints(min_length=1, max_length=64)]] = (
        Field(min_length=1, max_length=8)
    )
    artifacts: list[Annotated[str, StringConstraints(min_length=2, max_length=255)]] = (
        Field(min_length=1, max_length=16)
    )
    files: list[ForgeCreatedFile] = Field(min_length=1, max_length=64)


#: Where a construction stands, read from its records.
type ForgeConstructionState = Literal["prepared", "running", "finished", "stopped"]
#: Where one of its calls stands.
type ForgeConstructionCallState = Literal[
    "not_called", "running", "succeeded", "rejected", "failed", "outcome_unknown"
]


class ForgeConstructionTaskStatus(ProtocolModel):
    """One task of a construction: its call, if made, and its package, if any."""

    task_name: ForgeProposedTaskName
    package_name: NonEmptyString
    state: ForgeConstructionCallState
    call: ForgeConstructionCall | None
    package: ForgeConstructionPackage | None


class ForgeConstructionStatus(ProtocolModel):
    """A construction read back: review, approval, pass and every task.

    ``state`` is ``prepared`` until approved, ``running`` while the process
    making the pass is alive, ``finished`` when the pass ended on its own, and
    ``stopped`` when Ctrl-C ended it or its process is gone before it ended.
    A call left ``started`` by a process that is gone reads
    ``outcome_unknown``.
    """

    construction_id: NonEmptyString
    path: NonEmptyString
    state: ForgeConstructionState
    record: ForgeConstructionRecord
    approval: ForgeConstructionApproval | None
    run: ForgeConstructionRun | None
    tasks: list[ForgeConstructionTaskStatus]


class ForgeCollectionCandidate(ProtocolModel):
    """One proposed task as acceptance shows it: how it went, last time tried.

    ``construction_id`` is the construction that last called the creator for
    it. ``build_id`` names the build its package became, if one was written,
    and ``usable`` is whether that build qualified it; the build's status says
    why one did not. ``why`` is what stopped a call that made no package.
    """

    task_name: ForgeProposedTaskName
    construction_id: NonEmptyString
    state: ForgeConstructionCallState
    build_id: NonEmptyString | None
    usable: bool
    why: NonEmptyString | None

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if self.usable and (self.build_id is None or self.why is not None):
            raise ValueError("a usable task names its build and no reason it stopped")
        return self


class ForgeCollectionMember(ProtocolModel):
    """One accepted task: exactly the bytes and the qualification it had."""

    task_name: ForgeProposedTaskName
    build_id: NonEmptyString
    task_id: ForgeTaskId
    content_digest: Digest
    qualification_digest: Digest


class ForgeCollectionParent(ProtocolModel):
    """The accepted collection a new version replaces."""

    collection_id: NonEmptyString
    collection_digest: Digest
    version: int = Field(ge=1)


class ForgeCollectionReview(ProtocolModel):
    """What accepting a collection covers.

    Every task of the proposal with its outcome, so nothing that failed is
    out of sight, and the exact members: the qualified tasks being accepted,
    each by its content and qualification digests. ``constructions`` is the
    retry chain the outcomes come from, newest first.
    """

    proposal_id: NonEmptyString
    proposal_digest: Digest
    source_id: NonEmptyString
    source_digest: Digest
    constructions: list[NonEmptyString] = Field(min_length=1)
    previous: ForgeCollectionParent | None
    version: int = Field(ge=1)
    tasks: list[ForgeCollectionCandidate] = Field(min_length=1)
    members: list[ForgeCollectionMember] = Field(min_length=1)
    membership_digest: Digest

    @model_validator(mode="after")
    def validate_membership(self) -> Self:
        usable = {task.task_name for task in self.tasks if task.usable}
        names = [member.task_name for member in self.members]
        if len(set(names)) != len(names) or not set(names) <= usable:
            raise ValueError("members are distinct tasks that qualified")
        if not verify_object_digest(self.members, self.membership_digest):
            raise ValueError("membership digest does not describe the members")
        expected = 1 if self.previous is None else self.previous.version + 1
        if self.version != expected:
            raise ValueError("a collection is one version after the one it replaces")
        return self


class ForgeCollectionRecord(ProtocolModel):
    """A prepared collection: its review and the digest acceptance names."""

    schema_version: Literal["techtree.forge-collection.v1alpha1"]
    collection_id: NonEmptyString
    created_at: UtcDateTime
    review: ForgeCollectionReview
    collection_digest: Digest

    @model_validator(mode="after")
    def validate_digest(self) -> Self:
        if not verify_object_digest(self.review, self.collection_digest):
            raise ValueError("collection digest does not describe its review")
        return self


class ForgeCollectionAcceptance(ProtocolModel):
    """A person's acceptance of exactly one prepared collection; it freezes it."""

    schema_version: Literal["techtree.forge-collection-acceptance.v1alpha1"]
    collection_id: NonEmptyString
    collection_digest: Digest
    accepted_at: UtcDateTime
    reviewed_on: Literal["cli", "host-agent"]
    answered_with: Literal["prompt", "yes-flag"]


type ForgeCollectionState = Literal["prepared", "accepted"]


class ForgeCollectionStatus(ProtocolModel):
    """A collection read back; ``accepted`` means frozen."""

    collection_id: NonEmptyString
    path: NonEmptyString
    state: ForgeCollectionState
    record: ForgeCollectionRecord
    acceptance: ForgeCollectionAcceptance | None
