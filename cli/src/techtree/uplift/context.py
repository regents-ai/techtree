"""What a host agent may be told about a finished run. Spec section 7.18.

The improvement loop needs a model to read one run's outcome and propose a
better Skill. This module is the boundary that model reads through, and its
whole design is a subtraction: it starts from what the run proved and removes
everything a Skill must not be allowed to learn.

What comes out is a :class:`SkillImprovementContext` — the objective, the
headline result, and a bounded, ordered list of tasks worth looking at. What
never comes out is listed in ``prohibited_material``, on the artifact itself,
so a consumer is told what it is not being given rather than left to guess.

Three rules decide the contents.

*It is built from the run's signed record.* The report and the episode receipts
are the objects the run's local proof covers; the engine's raw and normalized
evaluation output is not. Building from the signed half is what makes the
context deterministic — the same run always produces the same bytes — and what
stops a context from asserting something the run's own attestation does not.

*Subject replies are excluded, and that is the load-bearing decision.* Spec
section 11.5 lists subject replies among what a sanitized context may include;
spec section 7.18 requires expected answers to be excluded, and spec section
7.22 requires a test proving a hidden answer is omitted. For a taskset scored
by matching an answer, a reply the subject got *right* is the expected answer,
word for word. Handing those to the model that writes Skill v2 would let the
answers be written into the Skill, and the v1-against-v2 comparison would then
measure memorization while presenting itself as measuring procedure — the
contaminated benchmark spec section 7.17 exists to prevent. The exclusions
control, so replies stay out. :class:`ImprovementExample` keeps the field,
because it is the typed seat a later release can fill once something in the
protocol can say which rewards make a reply safe to show; in this build it is
always ``None`` and ``prohibited_material`` says so.

*Nothing local leaks.* No filesystem path, no environment value, no credential,
and no provider detail has a field to enter through, and every free-text field
is run through the same sanitizer a rendering uses. A task is named by its
position and its committed hash, which is the identifier the TasksetLock
already commits to in public.

The context is not signed, is not proof, and is not uploaded.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, Literal, Protocol

from techtree.canonical import digest_object
from techtree.errors import ValidationError
from techtree.models.base import Digest, NonEmptyString, ProtocolModel
from techtree.models.campaign import CampaignSpec
from techtree.models.episode_receipt import EpisodeReceipt, ScoreStatus
from techtree.models.skill import SkillArtifact
from techtree.models.uplift_report import (
    PrimaryUpliftResult,
    TaskDelta,
    UpliftReport,
)
from techtree.presentation.sanitize import (
    ensure_no_control_or_local_path,
    ensure_no_secret_patterns,
    sanitize_label,
)

__all__ = [
    "EXAMPLE_CONTRAST_LIMIT",
    "EXAMPLE_LIMIT",
    "IMPROVEMENT_CONTEXT_FORBIDDEN_MATERIAL",
    "IMPROVEMENT_CONTEXT_INVALID",
    "IMPROVEMENT_CONTEXT_SCHEMA_VERSION",
    "PROHIBITED_MATERIAL",
    "REVISION_CONSTRAINTS",
    "ImprovementExample",
    "ImprovementOutcome",
    "SkillImprovementContext",
    "TaskPublicProjection",
    "TaskPublicProjectionProvider",
    "build_improvement_context",
    "hash_only_projection",
]

#: Not in :mod:`techtree.constants`, which holds protocol schema versions. Spec
#: section 7.18's context is local machine-readable material, not a protocol
#: object: nothing signs it, nothing references it by digest, and no schema is
#: exported for it.
IMPROVEMENT_CONTEXT_SCHEMA_VERSION: Final = "techtree.skill-improvement-context.v1"

#: Stable error codes. Both are spec ``docs/spec/climb-v0.1-wp9-wp11.md``
#: section 20's, named there because that is where the context is consumed and
#: used here because this is where the two conditions occur: a context that
#: could not be built honestly, and one whose free text carried something the
#: exclusion list forbids.
IMPROVEMENT_CONTEXT_INVALID: Final = "improvement_context_invalid"
IMPROVEMENT_CONTEXT_FORBIDDEN_MATERIAL: Final = "improvement_context_forbidden_material"

#: How many tasks a context carries at most. A context is read by a model with
#: a finite window, and a run with hundreds of tasks would otherwise push the
#: regressions — the part that matters most — out of reach.
EXAMPLE_LIMIT: Final = 20

#: How many stable successes ride along as contrast. Spec section 7.18 asks for
#: "a small contrast sample", and small is what keeps the list about failures.
EXAMPLE_CONTRAST_LIMIT: Final = 3


type ImprovementOutcome = Literal[
    "stable_success",
    "stable_failure",
    "improved",
    "regressed",
]
"""How one task moved between the two variants of the source run."""


#: What a revision is allowed to be. Stated on the artifact because the model
#: reading it is being asked to produce a Skill, and a constraint it was never
#: told about is a constraint it will break.
REVISION_CONSTRAINTS: Final[tuple[str, ...]] = (
    "The revision is an instruction Skill: Markdown and plain text files, with "
    "SKILL.md as its entry point.",
    "The revision changes only the Skill's own files. Nothing else about the "
    "experiment may differ, and nothing else will be allowed to.",
    "The revision must not encode answers to specific tasks. It is measured on "
    "the same committed tasks, and a Skill that memorizes them measures nothing.",
    "The revision must not contain credentials, keys, tokens, or absolute local "
    "paths. The scanner refuses a Skill that does.",
    "The revision must differ from the Skill it replaces. An identical tree "
    "would compare a Skill against itself.",
)

#: What this context does not carry, stated to whoever reads it. Every entry is
#: proved absent by the exclusion matrix in ``tests/unit/test_improvement_context``.
PROHIBITED_MATERIAL: Final[tuple[str, ...]] = (
    "hidden expected answers",
    "hidden grader material",
    "sealed task content",
    "subject final replies",
    "provider secrets and credentials",
    "private environment values",
    "unredacted local filesystem paths",
)


class TaskPublicProjection(ProtocolModel):
    """The publicly showable face of one committed task."""

    task_label: NonEmptyString
    public_prompt: str | None


class TaskPublicProjectionProvider(Protocol):
    """How a caller supplies the public face of one task.

    The taskset's own public material is not carried in a receipt, so this
    build has nothing to resolve a prompt from and
    :func:`hash_only_projection` names a task by its position and committed
    hash. The seat exists so that a later release with a DataPolicy-gated
    public projection can fill it without changing this module.
    """

    def __call__(self, *, task_hash: Digest, position: int) -> TaskPublicProjection:
        """Return what may be shown about one committed task."""
        ...


def hash_only_projection(*, task_hash: Digest, position: int) -> TaskPublicProjection:
    """Name a task by its place in the Campaign and the head of its hash.

    A committed task hash is not hidden material: it is the identifier the
    TasksetLock, the receipts and the report already carry, and the publisher's
    validation evidence lists it in public. The prompt is absent because no
    public projection of one exists here, not because one was dropped.
    """
    _, _, hexadecimal = task_hash.partition(":")
    return TaskPublicProjection(
        task_label=f"task {position + 1:02d} · {hexadecimal[:8]}",
        public_prompt=None,
    )


class ImprovementExample(ProtocolModel):
    """One committed task, as a model proposing a revision may see it."""

    task_hash: Digest
    task_label: NonEmptyString
    public_prompt: str | None
    subject_reply: str | None
    reward: float
    outcome: ImprovementOutcome
    public_metrics: dict[str, float | None]
    error_summary: str | None


class SkillImprovementContext(ProtocolModel):
    """Everything a host agent is given to propose one Skill revision."""

    schema_version: Literal["techtree.skill-improvement-context.v1"]
    source_run_id: NonEmptyString
    campaign_spec_digest: Digest
    parent_skill_digest: Digest
    data_policy_digest: Digest
    objective: NonEmptyString
    current_result: PrimaryUpliftResult
    examples: list[ImprovementExample]
    constraints: list[NonEmptyString]
    prohibited_material: list[NonEmptyString]


def build_improvement_context(
    *,
    report: UpliftReport,
    candidate_receipts: Sequence[EpisodeReceipt],
    baseline_receipts: Sequence[EpisodeReceipt],
    campaign: CampaignSpec,
    parent_skill: SkillArtifact,
    task_public_projection: TaskPublicProjectionProvider = hash_only_projection,
) -> SkillImprovementContext:
    """Build the sanitized local context for one completed run.

    Every number comes from the signed report or the signed receipts, so two
    builds over one run produce identical bytes. Ordering is spec section
    7.18's: regressions, then the tasks the candidate still fails, then the
    narrowest wins, and a small contrast sample of what already works.
    """
    _require(
        report.campaign_spec_digest == digest_object(campaign),
        "this report is not a report of the Campaign the context would "
        "describe, so the two are about different experiments",
        expected=report.campaign_spec_digest,
        computed=digest_object(campaign),
    )
    _require(
        bool(report.task_deltas),
        "this run compared no tasks, so there is nothing to improve against",
        run_id=report.run_id,
    )

    by_task = {
        receipt.task_hash: receipt
        for receipt in candidate_receipts
        if receipt.run_id == report.run_id
    }
    examples = _select(
        [
            _example(
                delta=delta,
                position=position,
                receipt=by_task.get(delta.task_hash),
                projection=task_public_projection(
                    task_hash=delta.task_hash, position=position
                ),
            )
            for position, delta in enumerate(report.task_deltas)
        ]
    )

    context = SkillImprovementContext(
        schema_version=IMPROVEMENT_CONTEXT_SCHEMA_VERSION,
        source_run_id=report.run_id,
        campaign_spec_digest=report.campaign_spec_digest,
        parent_skill_digest=parent_skill.root_digest,
        data_policy_digest=report.data_policy_digest,
        objective=_objective(campaign, report.primary_result),
        current_result=report.primary_result,
        examples=examples,
        constraints=list(REVISION_CONSTRAINTS),
        prohibited_material=list(PROHIBITED_MATERIAL),
    )
    ensure_no_hidden_material(context)
    return context


def ensure_no_hidden_material(context: SkillImprovementContext) -> None:
    """Check every free-text field before a context is handed to anything.

    The shape already keeps hidden material out; this keeps a credential or an
    absolute path out of the free text the shape still allows, exactly as the
    presentation payload is checked before it is rendered.
    """
    for label, value in _free_text(context):
        _forbid(label, value)


# ---------------------------------------------------------------------------
# The pieces
# ---------------------------------------------------------------------------


def _example(
    *,
    delta: TaskDelta,
    position: int,
    receipt: EpisodeReceipt | None,
    projection: TaskPublicProjection,
) -> ImprovementExample:
    """Describe one task from the signed record of what it scored.

    A caller's projection is checked for credentials *before* it is shortened,
    because shortening a leaked key would hide the fact that one reached this
    far. Bounding and flattening happen after, and only to text that has
    already been found clean.
    """
    _forbid("task_label", projection.task_label)
    if projection.public_prompt is not None:
        _forbid("public_prompt", projection.public_prompt)

    return ImprovementExample(
        task_hash=delta.task_hash,
        task_label=sanitize_label(projection.task_label),
        public_prompt=(
            None
            if projection.public_prompt is None
            else sanitize_label(projection.public_prompt, maximum=600)
        ),
        # Always absent in this build. See this module's docstring: for a
        # taskset scored by matching an answer, a correct reply is the expected
        # answer, and spec section 7.18's exclusions control.
        subject_reply=None,
        reward=delta.candidate_reward,
        outcome=_outcome(delta),
        public_metrics={
            "baseline_reward": delta.baseline_reward,
            "delta": delta.delta,
            **_recorded_metrics(receipt),
        },
        error_summary=_error_summary(receipt),
    )


def _outcome(delta: TaskDelta) -> ImprovementOutcome:
    """Return which way one task moved, and whether it stands where it should.

    A reward of zero is the one value every Verifiers reward function agrees
    means "earned nothing here", so it is what separates a task that stably
    works from one that stably does not. Nothing else about the reward's scale
    is assumed, because nothing else about it is declared.
    """
    if delta.delta < 0:
        return "regressed"
    if delta.delta > 0:
        return "improved"
    return "stable_success" if delta.candidate_reward > 0.0 else "stable_failure"


def _recorded_metrics(receipt: EpisodeReceipt | None) -> dict[str, float | None]:
    """Return the metrics this task's subject traces recorded, if any.

    These are the evaluation's own named measurements, which the report already
    carries the rewards half of. A metric whose name would collide with the two
    this context computes is left out rather than silently overwriting one.
    """
    if receipt is None:
        return {}
    recorded: dict[str, float | None] = {}
    for traces in receipt.named_traces.values():
        for trace in traces:
            for name, value in sorted(trace.metrics.items()):
                if name in ("baseline_reward", "delta"):
                    continue
                recorded[sanitize_label(name, maximum=64)] = value
    return recorded


def _error_summary(receipt: EpisodeReceipt | None) -> str | None:
    """Say why a task's score is not usable evidence, when it is not.

    The engine's recorded exception text lives in the normalized evaluation
    output, which the run's proof does not cover and this context does not
    read. What the signed receipt does say is the status its score carries,
    and that is the part a reviser can act on.
    """
    if receipt is None:
        return "no receipt was recorded for this task in the candidate variant"
    if receipt.score_status is ScoreStatus.VALID:
        return None
    return f"the recorded score for this task is {receipt.score_status.value}"


_OUTCOME_RANK: Final[dict[ImprovementOutcome, int]] = {
    "regressed": 0,
    "stable_failure": 1,
    "improved": 2,
    "stable_success": 3,
}


def _select(examples: Sequence[ImprovementExample]) -> list[ImprovementExample]:
    """Order and bound the tasks a reviser is shown. Spec section 7.18.

    Regressions come first and worst-first, because a regression is the one
    outcome that says the Skill actively hurt. Then the tasks the candidate
    still fails. Then the wins by the narrowest margin, which are the ones a
    small change could lose. Stable successes ride along only as contrast and
    only a few of them.

    The list is *emitted* in that order too, not restored to Campaign order. A
    model reads from the top and a bounded list read from the top should start
    with what went wrong. Committed order is recoverable from the report, which
    carries every task; this list carries the ones worth looking at.
    """
    ranked = sorted(
        enumerate(examples),
        key=lambda item: (
            _OUTCOME_RANK[item[1].outcome],
            _within_group(item[1]),
            item[0],
        ),
    )
    chosen: list[ImprovementExample] = []
    contrast = 0
    for _, example in ranked:
        if example.outcome == "stable_success":
            if contrast >= EXAMPLE_CONTRAST_LIMIT:
                continue
            contrast += 1
        chosen.append(example)
        if len(chosen) >= EXAMPLE_LIMIT:
            break
    return chosen


def _within_group(example: ImprovementExample) -> float:
    """Return the margin that orders one task inside its outcome group.

    Regressions are worst first, so the most negative delta sorts first. Wins
    are narrowest first, so the smallest positive delta sorts first. Both are
    the same expression, which is why they are one line.
    """
    delta = example.public_metrics.get("delta")
    return 0.0 if delta is None else delta


def _objective(campaign: CampaignSpec, result: PrimaryUpliftResult) -> str:
    """State, in one sentence a model can act on, what a revision has to beat.

    The margin clause is dropped when the Campaign declares no margin, because
    "by at least 0.000" is a requirement that is not one, and a model told to
    satisfy it would be being told something false about the contract.
    """
    scoring = campaign.scoring
    threshold = scoring.minimum_absolute_delta
    tasks = len(campaign.taskset.membership.ordered_task_hashes)
    margin = "" if threshold <= 0.0 else f", by at least {threshold:.3f}"
    return sanitize_label(
        f"Revise the Skill so that mean {scoring.primary_reward} over the same "
        f"{tasks} committed tasks rises above {result.candidate_mean:.3f}"
        f"{margin}, without changing anything else about the experiment.",
        maximum=400,
    )


def _free_text(context: SkillImprovementContext) -> list[tuple[str, str]]:
    """Return every free-text field a context carries, with its name."""
    found = [
        ("objective", context.objective),
        *(
            (f"constraints[{index}]", value)
            for index, value in enumerate(context.constraints)
        ),
        *(
            (f"prohibited_material[{index}]", value)
            for index, value in enumerate(context.prohibited_material)
        ),
    ]
    for index, example in enumerate(context.examples):
        found.append((f"examples[{index}].task_label", example.task_label))
        for name in ("public_prompt", "subject_reply", "error_summary"):
            value = getattr(example, name)
            if value is not None:
                found.append((f"examples[{index}].{name}", value))
        found.extend(
            (f"examples[{index}].public_metrics[{key}]", key)
            for key in example.public_metrics
        )
    return found


def _forbid(label: str, value: str) -> None:
    """Refuse one string that carries material a context may not carry.

    Refusing rather than quietly redacting is the same rule spec section 7.17
    applies to a rendering, for the same reason: a context that swallowed a
    leaked key would hide the fact that one reached this far.
    """
    try:
        ensure_no_secret_patterns(value)
        ensure_no_control_or_local_path(value, field=label)
    except ValidationError as error:
        raise ValidationError(
            "a value bound for an improvement context carries material the "
            f"context excludes: {error.message}",
            code=IMPROVEMENT_CONTEXT_FORBIDDEN_MATERIAL,
            details={"field": label},
        ) from error


def _require(condition: bool, message: str, **details: str) -> None:
    """Raise a typed refusal unless the condition holds."""
    if condition:
        return
    raise ValidationError(
        message,
        code=IMPROVEMENT_CONTEXT_INVALID,
        details=dict(details),
    )
