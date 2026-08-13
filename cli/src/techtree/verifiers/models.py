"""Local integration types for native Verifiers execution. Spec section 6.6.

Nothing in this module is a Techtree protocol root. These objects describe one
machine's execution of one Campaign: which child ran, where its bytes landed,
and what the pinned engine's normalizer made of them. They are hashed and
written into a run directory, never into the Campaign graph and never onto a
website.

``RunPaths`` is the one addition the specification names but the repository did
not yet have (spec section 6.19). It exists here rather than in
``techtree.paths`` because every path it owns belongs to Verifiers execution;
``TechtreePaths`` stays the answer to "where does Techtree keep its state", and
this stays the answer to "where does one variant's evaluation live".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal, Self

from pydantic import Field, model_validator

from techtree.models.base import (
    ArtifactRef,
    Digest,
    JsonValue,
    NonEmptyString,
    ProtocolModel,
)
from techtree.models.campaign import VariantSchedule
from techtree.paths import TechtreePaths

__all__ = [
    "COMMAND_LOG_FILENAME",
    "INPUT_CONFIG_FILENAME",
    "NORMALIZED_EPISODES_FILENAME",
    "STDERR_LOG_FILENAME",
    "STDOUT_LOG_FILENAME",
    "VERIFIERS_DIRECTORY",
    "ChildProcessOutcome",
    "ExecutionCheck",
    "NormalizedEpisode",
    "NormalizedExecutionError",
    "NormalizedReward",
    "NormalizedRuntime",
    "NormalizedTool",
    "NormalizedTrace",
    "NormalizedUsage",
    "RealExecutionResult",
    "RunPaths",
    "SubjectImageResolution",
    "VariantExecutionPlan",
    "VariantExecutionResult",
    "VariantName",
]

#: The run-owned subtree every variant's evaluation lives under.
VERIFIERS_DIRECTORY: Final = "verifiers"
#: The configuration Techtree compiles, as opposed to the one the engine
#: resolves and writes back out under its own name.
INPUT_CONFIG_FILENAME: Final = "input.toml"

#: What the engine writes when it normalizes one variant's raw episodes. It sits
#: beside the raw evidence inside ``run/`` (spec section 6.19) rather than above
#: it, so that one directory holds everything one execution produced.
NORMALIZED_EPISODES_FILENAME: Final = "normalized-episodes.jsonl"

#: Where a live child's captured streams land. Spec section 6.10 redirects both
#: to run-owned files; section 6.19 names them.
STDOUT_LOG_FILENAME: Final = "stdout.log"
STDERR_LOG_FILENAME: Final = "stderr.log"

#: The dry run is short and captured whole, so it is recorded in one file rather
#: than as a pair of streams. Spec section 6.19.
COMMAND_LOG_FILENAME: Final = "command.log"

_DRY_RUN_DIRECTORY: Final = "dry-run"
_RUN_DIRECTORY: Final = "run"
_INPUTS_DIRECTORY: Final = "inputs"
_MANIFESTS_DIRECTORY: Final = "manifests"
_SKILL_FILES_PATH: Final = ("skill", "files")


class VariantName(StrEnum):
    """Which side of the comparison a child process is running."""

    BASELINE = "baseline"
    CANDIDATE = "candidate"


# ---------------------------------------------------------------------------
# Where one run's evaluation lives
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunPaths:
    """Every path one run's Verifiers execution is allowed to touch.

    Spec section 6.19. The layout is per variant so that a parallel schedule
    cannot have two children writing the same file, and so that a cancelled
    variant's partial evidence stays legible next to its sibling's complete
    evidence.
    """

    root: Path

    @classmethod
    def for_run(cls, paths: TechtreePaths, run_id: str) -> Self:
        """Locate one run's directory inside a Techtree home."""
        return cls(root=paths.run_dir(run_id))

    @property
    def inputs_dir(self) -> Path:
        """The run's own copies of everything it executes."""
        return self.root / _INPUTS_DIRECTORY

    @property
    def skill_files_dir(self) -> Path:
        """The run-owned skill tree a compiled config may point at."""
        return self.inputs_dir.joinpath(*_SKILL_FILES_PATH)

    def manifest_path(self, variant: VariantName) -> Path:
        """The run's own copy of one variant's experiment manifest."""
        return self.inputs_dir / _MANIFESTS_DIRECTORY / f"{variant.value}.json"

    @property
    def verifiers_dir(self) -> Path:
        """The root of every variant's evaluation."""
        return self.root / VERIFIERS_DIRECTORY

    def variant_dir(self, variant: VariantName) -> Path:
        """One variant's evaluation directory."""
        return self.verifiers_dir / variant.value

    def variant_input_config(self, variant: VariantName) -> Path:
        """The configuration Techtree compiles for one variant."""
        return self.variant_dir(variant) / INPUT_CONFIG_FILENAME

    def variant_dry_run_dir(self, variant: VariantName) -> Path:
        """Where the engine writes the resolved config during validation.

        Separate from the run directory on purpose: a dry run writes only
        ``config.toml`` (``docs/verifiers-eval.md``, finding E2), and letting
        it land beside real evidence would leave a directory that looks like a
        truncated run.
        """
        return self.variant_dir(variant) / _DRY_RUN_DIRECTORY

    def variant_dry_run_command_log(self, variant: VariantName) -> Path:
        """What the dry-run invocation was, and what it said back."""
        return self.variant_dry_run_dir(variant) / COMMAND_LOG_FILENAME

    def variant_output_dir(self, variant: VariantName) -> Path:
        """Where the engine writes one variant's real evaluation output."""
        return self.variant_dir(variant) / _RUN_DIRECTORY

    def variant_stdout_log(self, variant: VariantName) -> Path:
        """Where one variant's child sends everything it prints.

        Never a console. With ``rich`` disabled the pinned CLI dumps every
        trace as indented JSON when the run ends, and those are the subject's
        transcripts (``docs/verifiers-eval.md``).
        """
        return self.variant_output_dir(variant) / STDOUT_LOG_FILENAME

    def variant_stderr_log(self, variant: VariantName) -> Path:
        """Where one variant's child sends its diagnostics."""
        return self.variant_output_dir(variant) / STDERR_LOG_FILENAME

    def variant_normalized_episodes(self, variant: VariantName) -> Path:
        """One variant's normalized projection, beside the evidence it projects."""
        return self.variant_output_dir(variant) / NORMALIZED_EPISODES_FILENAME

    def relative(self, path: Path) -> str:
        """Return ``path`` as a POSIX path relative to the run directory."""
        return path.relative_to(self.root).as_posix()

    def owns(self, path: Path) -> bool:
        """Whether ``path`` lies inside the run's own input tree."""
        return path.is_absolute() and path.is_relative_to(self.inputs_dir)


# ---------------------------------------------------------------------------
# Planning and process outcome
# ---------------------------------------------------------------------------


class VariantExecutionPlan(ProtocolModel):
    """Everything one variant's child process needs, resolved."""

    variant: VariantName
    experiment_manifest_digest: Digest
    experiment_manifest_path: NonEmptyString
    verifiers_input_config_path: NonEmptyString
    verifiers_output_dir: NonEmptyString
    skill_paths: list[NonEmptyString]
    task_count: int = Field(ge=1)
    max_concurrent: int = Field(ge=1)


class SubjectImageResolution(ProtocolModel):
    """What the local daemon answered about the pinned subject image.

    The pinned Verifiers build asks Docker for a reference and records only the
    reference, so the evaluation's own output cannot say what the daemon held or
    which platform it served. Techtree asks, once per variant, immediately
    before that variant's child is launched, and records the answer here.

    Two facts, both from the daemon: the content digest it holds for the
    reference — for a multi-platform repository, the OCI image index — and the
    platform it resolved that index to on this host. The platform-specific
    manifest digest is not asked of the daemon because the daemon does not know
    it; it is a property of the pinned index, recorded in the Campaign per
    supported platform, and the comparison reads it out by the platform observed
    here.
    """

    variant: VariantName
    image: NonEmptyString
    index_digest: Digest
    platform: NonEmptyString


class ChildProcessOutcome(ProtocolModel):
    """What one Verifiers child process did.

    ``argv_digest`` rather than the argv itself. The compiled invocation never
    carries a secret, but a digest is what makes that claim checkable without
    re-reading a command line into a log.
    """

    variant: VariantName
    argv_digest: Digest
    exit_code: int
    started_at: datetime
    finished_at: datetime
    stdout_artifact: ArtifactRef
    stderr_artifact: ArtifactRef
    cancelled: bool

    @model_validator(mode="after")
    def _check_the_clock_moves_forward(self) -> Self:
        """Reject a process that finished before it started."""
        if self.finished_at < self.started_at:
            raise ValueError("a child process cannot finish before it starts")
        return self


# ---------------------------------------------------------------------------
# The normalized projection of upstream evidence
# ---------------------------------------------------------------------------


class NormalizedExecutionError(ProtocolModel):
    """One failure the engine's normalizer preserved.

    ``traceback`` is present only for an episode or trace that actually failed
    (spec section 6.12); a successful record carries none, because a stack
    trace from a healthy run is host noise rather than evidence.
    """

    type: NonEmptyString
    message: str
    traceback: str | None = None


class NormalizedReward(ProtocolModel):
    """One reward as Verifiers scored it, with its weighted contribution."""

    name: NonEmptyString
    score: float
    weight: float
    value: float

    @model_validator(mode="after")
    def _check_every_number_is_finite(self) -> Self:
        """Reject a reward carrying a non-finite score, weight, or value."""
        for field, number in (
            ("score", self.score),
            ("weight", self.weight),
            ("value", self.value),
        ):
            if number != number or number in (float("inf"), float("-inf")):
                raise ValueError(f"reward {field} must be finite; got {number!r}")
        return self


class NormalizedUsage(ProtocolModel):
    """Token consumption for one trace, and what the provider said it cost.

    ``cost_usd`` is the provider's own figure and is absent whenever the
    provider publishes none. Nothing here computes a cost from a price list:
    an operational record downstream states where a cost came from, and a
    number invented at this level could not be told apart from a reported one.
    """

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0.0)


class NormalizedTool(ProtocolModel):
    """One tool the subject was offered, described by digest.

    A tool's description and parameter schema are prompt material. They are
    hashed rather than copied so that a receipt can prove two variants were
    offered identical tools without republishing the prompt surface.
    """

    name: NonEmptyString
    description_digest: Digest
    parameters_digest: Digest


class NormalizedRuntime(ProtocolModel):
    """The box one trace ran in, as the evaluation recorded it.

    ``image_index_digest`` is the content the reference names — for a
    multi-platform repository, the OCI image index. The pinned Verifiers build
    records the reference it was asked to run and nothing about what the daemon
    resolved it to, so this is a projection of the request rather than a report
    from the daemon; what the daemon confirmed is captured separately by
    :class:`SubjectImageResolution` and the two are required to agree.
    """

    kind: Literal["docker"]
    runtime_id: str | None
    image: NonEmptyString
    image_index_digest: Digest
    cpu: float | None
    memory_gb: float | None


class NormalizedTrace(ProtocolModel):
    """One subject rollout, projected onto the fields a receipt may cite."""

    trace_id: NonEmptyString
    agent_role: Literal["subject"]
    task_hash: Digest
    ok: bool
    # Recorded by the run itself rather than inferred: every upstream trace
    # carries the Verifiers build that wrote it, which is what lets the pin be
    # checked from the evidence instead of from a caller's claim about it.
    verifiers_version: NonEmptyString
    verifiers_revision: NonEmptyString
    model_id: NonEmptyString
    # The settings this rollout was actually sampled under, resolved by the
    # engine and carried by the rollout itself. Two variants that disagree here
    # were sampled differently, whatever their manifests declared.
    sampling: dict[str, JsonValue]
    harness_id: NonEmptyString
    harness_version: NonEmptyString
    use_bundled_skill: bool
    skill_root_digests: list[Digest]
    runtime: NormalizedRuntime
    tools: list[NormalizedTool]
    rewards: list[NormalizedReward]
    metrics: dict[str, float | None]
    usage: NormalizedUsage | None
    model_calls: int = Field(ge=0)
    num_turns: int = Field(ge=0)
    last_reply: str | None
    errors: list[NormalizedExecutionError]
    raw_trace_digest: Digest

    @model_validator(mode="after")
    def _check_rewards_are_named_once(self) -> Self:
        """Reject a trace that scores the same reward twice."""
        names = [reward.name for reward in self.rewards]
        if len(set(names)) != len(names):
            raise ValueError("a trace records each reward exactly once")
        return self

    @model_validator(mode="after")
    def _check_sampling_was_resolved(self) -> Self:
        """Reject a trace that records no sampling settings at all."""
        if not self.sampling:
            raise ValueError(
                "a trace records the sampling settings its rollout resolved"
            )
        return self

    def reward(self, name: str) -> NormalizedReward | None:
        """Return one reward by name, or ``None`` when it was not scored."""
        for reward in self.rewards:
            if reward.name == name:
                return reward
        return None


class NormalizedEpisode(ProtocolModel):
    """One task's episode, ordered by the Campaign's committed membership."""

    episode_id: NonEmptyString
    env_id: NonEmptyString
    task_hash: Digest
    task_position: int = Field(ge=0)
    ok: bool
    traces: list[NormalizedTrace]
    errors: list[NormalizedExecutionError]
    raw_episode_digest: Digest

    @model_validator(mode="after")
    def _check_every_trace_belongs_to_this_task(self) -> Self:
        """Reject an episode whose traces score a different task."""
        for trace in self.traces:
            if trace.task_hash != self.task_hash:
                raise ValueError(
                    "an episode's traces all score the episode's own task; got "
                    f"{trace.task_hash} inside {self.task_hash}"
                )
        return self


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


class VariantExecutionResult(ProtocolModel):
    """One variant, executed, with raw evidence and its normalized projection."""

    variant: VariantName
    experiment_manifest_digest: Digest
    resolved_verifiers_config: ArtifactRef
    raw_traces: ArtifactRef
    eval_log: ArtifactRef
    normalized_episodes: ArtifactRef
    child_outcome: ChildProcessOutcome
    image_resolution: SubjectImageResolution
    episodes: list[NormalizedEpisode]

    @model_validator(mode="after")
    def _check_the_outcome_describes_this_variant(self) -> Self:
        """Reject a result whose child outcome belongs to the other variant."""
        if self.child_outcome.variant is not self.variant:
            raise ValueError(
                f"a {self.variant.value} result carries a "
                f"{self.child_outcome.variant.value} child outcome"
            )
        if self.image_resolution.variant is not self.variant:
            raise ValueError(
                f"a {self.variant.value} result carries a "
                f"{self.image_resolution.variant.value} image resolution"
            )
        return self


class RealExecutionResult(ProtocolModel):
    """What WP6 hands WP7: both variants, executed under one schedule."""

    execution_backend: Literal["verifiers"]
    engine_digest: Digest
    verifiers_revision: NonEmptyString
    schedule: VariantSchedule
    baseline: VariantExecutionResult
    candidate: VariantExecutionResult

    @model_validator(mode="after")
    def _check_each_side_is_the_side_it_claims(self) -> Self:
        """Reject a result that files a variant under the wrong name."""
        if self.baseline.variant is not VariantName.BASELINE:
            raise ValueError("the baseline slot holds the baseline variant")
        if self.candidate.variant is not VariantName.CANDIDATE:
            raise ValueError("the candidate slot holds the candidate variant")
        return self


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


class ExecutionCheck(ProtocolModel):
    """One named question about an execution, and its answer.

    The same shape as ``ValidationCheck`` (spec section 21.5) and for the same
    reason: a caller reads an ordered list of named verdicts rather than
    catching exceptions to discover which rule failed.
    """

    id: NonEmptyString
    status: Literal["passed", "failed", "warning", "not_run"]
    detail: NonEmptyString
