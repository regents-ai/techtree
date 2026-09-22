"""What a host agent may be told about a finished forge comparison.

The forge half of the improvement loop reads through this boundary the way
the Climb half reads through :mod:`techtree.uplift.context`: it starts from
what the comparison recorded and subtracts everything a revised Skill must
not be allowed to learn. What comes out is a
:class:`ForgeImprovementContext` — the objective, the headline result, and
a bounded, ordered list of task pairs worth looking at, each with the task's
own instruction, which is the text the agent was shown and nothing more.

What never comes out: the reference patch, the tests and their names, either
arm's patch, any transcript, the repository's local path. A task is named by
its id and the repository by its build slug and commit. Every free-text field
is checked for control sequences and absolute paths before the context is
returned, and a value that carries one is refused, not edited.

The context is derived, not evidence: it is rewritten on every call, nothing
signs it, and nothing uploads it.
"""

from __future__ import annotations

from typing import Final, Literal

from techtree.errors import ValidationError
from techtree.forge.compare import read_comparison_status
from techtree.forge.models import (
    ForgeAttemptOutcome,
    ForgeAttemptPair,
    ForgeAttemptRecord,
    ForgeComparisonRecord,
    ForgePairResult,
    ForgeTaskId,
)
from techtree.forge.run import read_run_status
from techtree.forge.service import read_build_status
from techtree.models.base import Digest, NonEmptyString, ProtocolModel
from techtree.models.skill import SKILL_ENTRY_FILE
from techtree.paths import TechtreePaths
from techtree.presentation.sanitize import (
    ensure_no_control_or_local_path,
    sanitize_label,
)
from techtree.uplift.context import (
    EXAMPLE_CONTRAST_LIMIT,
    EXAMPLE_LIMIT,
    IMPROVEMENT_CONTEXT_FORBIDDEN_MATERIAL,
    IMPROVEMENT_CONTEXT_INVALID,
    REVISION_CONSTRAINTS,
)

__all__ = [
    "FORGE_IMPROVEMENT_CONTEXT_SCHEMA_VERSION",
    "FORGE_PROHIBITED_MATERIAL",
    "FORGE_REVISION_CONSTRAINTS",
    "ForgeImprovementContext",
    "ForgeImprovementExample",
    "ForgeImprovementResult",
    "build_forge_improvement_context",
]

FORGE_IMPROVEMENT_CONTEXT_SCHEMA_VERSION: Final = (
    "techtree.forge-improvement-context.v1alpha1"
)

#: How much of a task's instruction a context carries.
PROMPT_LIMIT: Final = 600

#: The Climb constraints, plus the one a repository task adds: the hidden
#: material is a real fix and real tests, and a Skill that carries either is
#: measuring recall, not method.
FORGE_REVISION_CONSTRAINTS: Final[tuple[str, ...]] = (
    *REVISION_CONSTRAINTS,
    "The revision must not carry the repository's reference fix or its tests, "
    "in whole or in part. It is screened against both before it runs, and "
    "every line it shares with them is recorded on the revision.",
)

#: What this context does not carry, stated to whoever reads it.
FORGE_PROHIBITED_MATERIAL: Final[tuple[str, ...]] = (
    "the reference patch of any task",
    "the tests of any task, and their names",
    "either arm's workspace patch",
    "agent transcripts and logs",
    "the repository's local path",
    "private environment values",
)


class ForgeImprovementExample(ProtocolModel):
    """One paired attempt, as a model proposing a revision may see it."""

    task_id: ForgeTaskId
    attempt: int
    public_prompt: NonEmptyString
    baseline_outcome: ForgeAttemptOutcome | None
    baseline_reward: float | None
    candidate_outcome: ForgeAttemptOutcome | None
    candidate_reward: float | None
    delta: float | None
    result: ForgePairResult
    candidate_agent_seconds: float | None
    candidate_api_calls: int | None


class ForgeImprovementResult(ProtocolModel):
    """The headline the revision has to beat, copied from the comparison."""

    pairs_planned: int
    pairs_graded: int
    wins: int
    losses: int
    ties: int
    unresolved: int
    baseline_mean_reward: float | None
    candidate_mean_reward: float | None
    mean_delta: float | None
    complete: bool


class ForgeImprovementContext(ProtocolModel):
    """Everything a host agent is given to propose one forge Skill revision.

    The fingerprints a proposal binds to are all here: the comparison, both
    runs, the build, and the parent Skill's root and entrypoint digests. None
    of them is the Skill's text; that is read through
    ``techtree uplift skill-source <candidate run>``, which verifies it
    against these same digests.
    """

    schema_version: Literal["techtree.forge-improvement-context.v1alpha1"]
    comparison_id: NonEmptyString
    baseline_run_id: NonEmptyString
    candidate_run_id: NonEmptyString
    build_id: NonEmptyString
    repository: NonEmptyString
    head_commit: NonEmptyString
    parent_skill_name: NonEmptyString
    parent_skill_digest: Digest
    parent_skill_entrypoint_digest: Digest
    objective: NonEmptyString
    current_result: ForgeImprovementResult
    examples: list[ForgeImprovementExample]
    constraints: list[NonEmptyString]
    prohibited_material: list[NonEmptyString]


def build_forge_improvement_context(
    paths: TechtreePaths, comparison_id: str
) -> ForgeImprovementContext:
    """Build the sanitized local context for one recorded comparison."""
    comparison = read_comparison_status(paths, comparison_id).record
    candidate = read_run_status(paths, comparison.candidate_run_id)
    skill = candidate.spec.skill
    if skill is None:
        raise ValidationError(
            "the candidate run carries no Skill, so there is nothing to revise",
            code=IMPROVEMENT_CONTEXT_INVALID,
            details={"comparison_id": comparison_id},
        )
    build = read_build_status(paths, comparison.build_id).build
    if build is None:
        raise ValidationError(
            f"the build {comparison.build_id} this comparison was made on has "
            "no build record",
            code=IMPROVEMENT_CONTEXT_INVALID,
            details={"comparison_id": comparison_id, "build_id": comparison.build_id},
        )
    source = build.require_repository_source("Repository improvement context")
    entrypoint = next(
        (file.digest for file in skill.files if file.path == SKILL_ENTRY_FILE), None
    )
    if entrypoint is None:
        raise ValidationError(
            f"the Skill this comparison measured lists no {SKILL_ENTRY_FILE}",
            code=IMPROVEMENT_CONTEXT_INVALID,
            details={"comparison_id": comparison_id, "skill": skill.root_digest},
        )

    tasks_dir = paths.forge_build_dir(comparison.build_id) / "tasks"
    prompts = {
        task_id: (tasks_dir / task_id / "instruction.md").read_text(encoding="utf-8")
        for task_id in candidate.spec.task_ids
    }
    examples = _select(
        [
            _example(pair, prompts[pair.task_id], candidate.record.attempts)
            for pair in comparison.pairs
        ]
    )
    context = ForgeImprovementContext(
        schema_version=FORGE_IMPROVEMENT_CONTEXT_SCHEMA_VERSION,
        comparison_id=comparison.comparison_id,
        baseline_run_id=comparison.baseline_run_id,
        candidate_run_id=comparison.candidate_run_id,
        build_id=comparison.build_id,
        repository=source.slug,
        head_commit=source.head_commit,
        parent_skill_name=skill.name,
        parent_skill_digest=skill.root_digest,
        parent_skill_entrypoint_digest=entrypoint,
        objective=_objective(comparison),
        current_result=ForgeImprovementResult(
            pairs_planned=comparison.pairs_planned,
            pairs_graded=comparison.pairs_graded,
            wins=comparison.wins,
            losses=comparison.losses,
            ties=comparison.ties,
            unresolved=comparison.unresolved,
            baseline_mean_reward=comparison.baseline.mean_reward,
            candidate_mean_reward=comparison.candidate.mean_reward,
            mean_delta=comparison.mean_delta,
            complete=comparison.complete,
        ),
        examples=examples,
        constraints=list(FORGE_REVISION_CONSTRAINTS),
        prohibited_material=list(FORGE_PROHIBITED_MATERIAL),
    )
    for label, value in _free_text(context):
        _forbid(label, value)
    return context


# ---------------------------------------------------------------------------
# The pieces
# ---------------------------------------------------------------------------


def _example(
    pair: ForgeAttemptPair, prompt: str, attempts: list[ForgeAttemptRecord]
) -> ForgeImprovementExample:
    """Describe one pair; the whole prompt is checked before it is shortened.

    The instruction is a document, so its line breaks are flattened before
    the check; a local path anywhere in it, including past where the example
    is cut, is refused.
    """
    _forbid(f"{pair.task_id}.public_prompt", " ".join(prompt.split()))
    attempt = next(
        (
            a
            for a in attempts
            if a.task_id == pair.task_id and a.attempt == pair.attempt
        ),
        None,
    )
    usage = attempt.usage if attempt is not None else None
    return ForgeImprovementExample(
        task_id=pair.task_id,
        attempt=pair.attempt,
        public_prompt=sanitize_label(prompt, maximum=PROMPT_LIMIT),
        baseline_outcome=pair.baseline_outcome,
        baseline_reward=pair.baseline_reward,
        candidate_outcome=pair.candidate_outcome,
        candidate_reward=pair.candidate_reward,
        delta=pair.delta,
        result=pair.result,
        candidate_agent_seconds=attempt.agent_seconds if attempt is not None else None,
        candidate_api_calls=usage.api_calls if usage is not None else None,
    )


def _rank(example: ForgeImprovementExample) -> tuple[int, float]:
    """Order the pairs a reviser reads: what the Skill hurt first.

    Losses worst-first, then pairs the candidate could not finish, then the
    tasks it still earns nothing on, then the narrowest wins. A tie the
    candidate already scores on is contrast only.
    """
    delta = example.delta if example.delta is not None else 0.0
    if example.result is ForgePairResult.LOSS:
        return (0, delta)
    if example.result is ForgePairResult.UNRESOLVED:
        return (1, 0.0)
    if example.result is ForgePairResult.TIE and not example.candidate_reward:
        return (2, 0.0)
    if example.result is ForgePairResult.WIN:
        return (3, delta)
    return (4, 0.0)


def _select(examples: list[ForgeImprovementExample]) -> list[ForgeImprovementExample]:
    ranked = sorted(enumerate(examples), key=lambda item: (*_rank(item[1]), item[0]))
    chosen: list[ForgeImprovementExample] = []
    contrast = 0
    for _, example in ranked:
        if _rank(example)[0] == 4:
            if contrast >= EXAMPLE_CONTRAST_LIMIT:
                continue
            contrast += 1
        chosen.append(example)
        if len(chosen) >= EXAMPLE_LIMIT:
            break
    return chosen


def _objective(comparison: ForgeComparisonRecord) -> str:
    """State, in one sentence a model can act on, what a revision has to beat."""
    current = comparison.candidate.mean_reward
    beat = (
        f"rises above {current:.3f}"
        if current is not None
        else "is established, since no pair was graded with it"
    )
    return sanitize_label(
        f"Revise {comparison.skill_name} so that the mean reward over the same "
        f"{comparison.pairs_planned} planned task attempts {beat}, without "
        "changing anything else about the experiment.",
        maximum=400,
    )


def _free_text(context: ForgeImprovementContext) -> list[tuple[str, str]]:
    found = [
        ("repository", context.repository),
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
    found.extend(
        (f"examples[{index}].public_prompt", example.public_prompt)
        for index, example in enumerate(context.examples)
    )
    return found


def _forbid(label: str, value: str) -> None:
    try:
        ensure_no_control_or_local_path(value, field=label)
    except ValidationError as error:
        raise ValidationError(
            "a value bound for an improvement context carries material the "
            f"context excludes: {error.message}",
            code=IMPROVEMENT_CONTEXT_FORBIDDEN_MATERIAL,
            details={"field": label},
        ) from error
