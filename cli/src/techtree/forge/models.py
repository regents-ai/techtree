"""What a forge build and a forge run record. ``docs/plan/repo2rlenv-local-lane.md``.

Three documents live in a build directory. ``build.json`` says what was built
from what: the repository, the commit, the bootstrap image, the test commands,
and what Repo2RLEnv found and emitted. ``qualification.json`` says which of the
emitted tasks proved out under the model-free checks and which did not, with
the rewards each check observed. ``progress.json`` preserves the last observed
phase and partial evidence. All are private local evidence about a mutable local
subject, not published artifacts.

A forge run starts from a fourth document, the run specification
(:class:`ForgeRunSpec`). It is the experiment's contract, written before any
result exists: which qualified tasks, which grading, which Hermes, which model,
what starting state, and which Skill, if any. Two specifications are comparable
only when they differ in the Skill alone; :mod:`techtree.forge.comparability`
computes that rather than asserting it.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final, Literal, Self

from pydantic import Field, StringConstraints, field_validator, model_validator

from techtree.canonical import verify_object_digest
from techtree.models.base import Digest, NonEmptyString, ProtocolModel, UtcDateTime
from techtree.models.skill import SkillFile

__all__ = [
    "FORGE_BUILD_SCHEMA_VERSION",
    "FORGE_PROGRESS_SCHEMA_VERSION",
    "FORGE_QUALIFICATION_SCHEMA_VERSION",
    "FORGE_RUN_SPEC_SCHEMA_VERSION",
    "FORGE_TASK_CONTENT_SCHEMA_VERSION",
    "FORGE_TASK_SET_SCHEMA_VERSION",
    "ForgeAgentSpec",
    "ForgeArm",
    "ForgeBuildFailure",
    "ForgeBuildPhase",
    "ForgeBuildProgress",
    "ForgeBuildRecord",
    "ForgeBuildStatus",
    "ForgeGradingSpec",
    "ForgeInitialState",
    "ForgeLanguage",
    "ForgeLimits",
    "ForgeModelSpec",
    "ForgePlatform",
    "ForgeQualification",
    "ForgeRunSpec",
    "ForgeSamplingSpec",
    "ForgeSkillName",
    "ForgeSkillSpec",
    "ForgeTaskId",
    "GenerationSummary",
    "QualificationCheck",
    "TaskContentEntry",
    "TaskContentManifest",
    "TaskQualification",
    "TaskSetCommitment",
]

FORGE_BUILD_SCHEMA_VERSION: Final = "techtree.forge-build.v1alpha2"
FORGE_PROGRESS_SCHEMA_VERSION: Final = "techtree.forge-progress.v1alpha1"
FORGE_QUALIFICATION_SCHEMA_VERSION: Final = "techtree.forge-qualification.v1alpha2"
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


class ForgeBuildRecord(ProtocolModel):
    """One build: its inputs, its bootstrap image, and what was generated."""

    schema_version: Literal["techtree.forge-build.v1alpha2"]
    build_id: NonEmptyString
    created_at: UtcDateTime
    repository: NonEmptyString
    head_commit: NonEmptyString
    slug: NonEmptyString
    language: ForgeLanguage
    platform: ForgePlatform
    dockerfile_digest: Digest
    test_commands: list[NonEmptyString] = Field(min_length=1)
    limit: int = Field(ge=1)
    bootstrap_image_tag: NonEmptyString
    bootstrap_image_id: NonEmptyString
    repo2rlenv_version: NonEmptyString
    generation: GenerationSummary
    task_set: TaskSetCommitment

    @model_validator(mode="after")
    def validate_task_set(self) -> Self:
        if self.generation.tasks != [task.task_id for task in self.task_set.tasks]:
            raise ValueError("committed task count or order differs from generation")
        return self


class QualificationCheck(ProtocolModel):
    """One model-free check on one task, and what it saw."""

    name: NonEmptyString
    passed: bool
    detail: str


class TaskQualification(ProtocolModel):
    """Whether one emitted task proved out, and the evidence."""

    task_id: ForgeTaskId
    task_content_digest: Digest
    image_tag: NonEmptyString
    image_id: str
    base_commit: NonEmptyString
    fail_to_pass: int = Field(ge=0)
    pass_to_pass: int = Field(ge=0)
    control_reward: float | None
    reference_reward: float | None
    checks: list[QualificationCheck]
    qualified: bool


class ForgeQualification(ProtocolModel):
    """The qualification of every task one build emitted."""

    schema_version: Literal["techtree.forge-qualification.v1alpha2"]
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
    """What Hermes starts from: an empty home written by Techtree, no memory."""

    home: Literal["fresh-empty"]
    memory_enabled: Literal[False]


class ForgeSkillSpec(ProtocolModel):
    """The one Skill the candidate arm carries, by content."""

    name: ForgeSkillName
    root_digest: Digest
    files: list[SkillFile] = Field(min_length=1)
    exposure: Literal["preloaded"]


class ForgeLimits(ProtocolModel):
    """Bounds on the agent's turn count and on its sandbox.

    The agent's wall-clock allowance is the task's own ``[agent].timeout_sec``,
    which is part of the committed task content rather than repeated here.
    """

    max_turns: int = Field(ge=1)
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


class ForgeBuildFailure(ProtocolModel):
    """A bounded failure description, without command output or model dumps."""

    code: NonEmptyString
    message: NonEmptyString
    error_type: NonEmptyString


class ForgeBuildProgress(ProtocolModel):
    """Last observed work, not evidence that a process is still running."""

    schema_version: Literal["techtree.forge-progress.v1alpha1"]
    build_id: NonEmptyString
    repository: NonEmptyString
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
        if [task.task_id for task in qualification.tasks] != build.generation.tasks:
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
            remaining = build.generation.tasks[len(progress.completed_tasks) :]
            if not remaining or progress.current_task_id != remaining[0]:
                raise ValueError("current task differs from next committed task")
