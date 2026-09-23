"""Comparing the two arms of a forge experiment, task by task.

A comparison is derived, never authored: it reads two recorded runs, asks
the comparability gate whether they were one experiment apart from the
Skill, and if so pairs every planned attempt on one arm with the same task
and repetition on the other. Only a pair graded on both sides is counted as
a win, a loss or a tie; an attempt that timed out, did not finish or left no
verdict leaves its pair unresolved, and a run that was interrupted before a
task leaves that pair unresolved too. Nothing unresolved is ever a zero.

What is written is one directory under the Techtree home per comparison:
the record as JSON, and the self-contained HTML report a person opens. The
record repeats every number on the page, so a machine reads the JSON and a
person reads the page and neither can disagree with the other.
"""

from __future__ import annotations

from datetime import UTC, datetime
from statistics import fmean
from typing import Final

from pydantic import ValidationError as ModelValidationError

from techtree.errors import NotFoundError, ValidationError
from techtree.forge.comparability import (
    assert_comparable_run_specs,
    compare_run_specs,
)
from techtree.forge.models import (
    FORGE_COMPARISON_SCHEMA_VERSION,
    VERDICT_MINIMUM_PAIRS,
    ForgeArmTotals,
    ForgeAttemptOutcome,
    ForgeAttemptPair,
    ForgeAttemptRecord,
    ForgeComparisonRecord,
    ForgeComparisonStatus,
    ForgePairResult,
    ForgeRunStatus,
    ForgeTaskConsistency,
    ForgeTaskRegression,
    ForgeVerdict,
    forge_verdict,
)
from techtree.forge.report import render_report
from techtree.forge.run import read_run_status
from techtree.forge.service import read_build_status
from techtree.fs import atomic_write_bytes, atomic_write_json
from techtree.ids import new_id, validate_id
from techtree.models.experiment import ManifestComparison
from techtree.paths import TechtreePaths

__all__ = [
    "COMPARISON_FILENAME",
    "REPORT_FILENAME",
    "VERDICT_WORDS",
    "build_comparison",
    "compare_runs",
    "read_comparison_status",
]

COMPARISON_FILENAME: Final = "comparison.json"
REPORT_FILENAME: Final = "report.html"


def compare_runs(
    paths: TechtreePaths, baseline_id: str, candidate_id: str
) -> ForgeComparisonStatus:
    """Compare two recorded runs, write the record and the report, and return them.

    Refuses, through the comparability gate, any pair that differs somewhere
    other than the arm and the Skill; nothing is written for a refused pair.
    """
    baseline = read_run_status(paths, baseline_id)
    candidate = read_run_status(paths, candidate_id)
    comparability = compare_run_specs(baseline.spec, candidate.spec)
    assert_comparable_run_specs(comparability)
    build_id = baseline.spec.require_build("Repository comparison report").build_id
    build = read_build_status(paths, build_id).build
    if build is None:
        raise NotFoundError(
            f"the build {build_id} these runs were made on has no build record",
            code="forge_build_not_found",
            details={"build_id": build_id},
        )

    source = build.require_repository_source("Repository comparison report")
    record = build_comparison(
        baseline,
        candidate,
        comparability,
        comparison_id=new_id("forgecmp"),
        created_at=datetime.now(UTC),
    )
    directory = paths.forge_comparison_dir(record.comparison_id)
    directory.mkdir(parents=True, mode=0o700)
    atomic_write_json(directory / COMPARISON_FILENAME, record.model_dump(mode="json"))
    page = render_report(
        record,
        repository=source.repository,
        head_commit=source.head_commit,
        baseline=baseline,
        candidate=candidate,
    )
    atomic_write_bytes(directory / REPORT_FILENAME, page.encode("utf-8"))
    return ForgeComparisonStatus(
        comparison_id=record.comparison_id,
        path=str(directory),
        report_path=str(directory / REPORT_FILENAME),
        record=record,
    )


def build_comparison(
    baseline: ForgeRunStatus,
    candidate: ForgeRunStatus,
    comparability: ManifestComparison,
    *,
    comparison_id: str,
    created_at: datetime,
) -> ForgeComparisonRecord:
    """Pair the two arms' attempts and add them up; nothing is read from disk."""
    skill = candidate.spec.skill
    if skill is None:
        raise ValidationError(
            "the candidate arm carries no Skill, so there is nothing to compare",
            code="forge_candidate_without_skill",
        )
    spec = baseline.spec
    pairs = [
        _pair(task_id, attempt, baseline.record.attempts, candidate.record.attempts)
        for task_id in spec.task_ids
        for attempt in range(1, spec.sampling.repetitions + 1)
    ]
    graded = [pair for pair in pairs if pair.result is not ForgePairResult.UNRESOLVED]
    wins = sum(pair.result is ForgePairResult.WIN for pair in graded)
    losses = sum(pair.result is ForgePairResult.LOSS for pair in graded)
    ties = sum(pair.result is ForgePairResult.TIE for pair in graded)
    deltas = [pair.delta for pair in graded if pair.delta is not None]
    mean_delta = fmean(deltas) if deltas else None
    consistency = [_consistency(task_id, pairs) for task_id in spec.task_ids]
    regressions = [
        _regression(task.task_id, pairs) for task in consistency if task.losses > 0
    ]
    verdict = forge_verdict(
        wins=wins,
        losses=losses,
        graded=len(graded),
        unresolved=len(pairs) - len(graded),
    )

    return ForgeComparisonRecord(
        schema_version=FORGE_COMPARISON_SCHEMA_VERSION,
        comparison_id=comparison_id,
        created_at=created_at,
        build_id=spec.require_build("Repository comparison report").build_id,
        baseline_run_id=baseline.run_id,
        candidate_run_id=candidate.run_id,
        skill_name=skill.name,
        skill_digest=skill.root_digest,
        comparability=comparability,
        baseline=_totals(baseline),
        candidate=_totals(candidate),
        pairs=pairs,
        pairs_planned=len(pairs),
        pairs_graded=len(graded),
        wins=wins,
        losses=losses,
        ties=ties,
        unresolved=len(pairs) - len(graded),
        mean_delta=mean_delta,
        complete=len(graded) == len(pairs),
        repetitions=spec.sampling.repetitions,
        verdict=verdict,
        regressions=regressions,
        consistency=consistency,
        summary=_summary(
            skill.name,
            pairs,
            graded,
            wins,
            losses,
            ties,
            verdict=verdict,
            regressions=regressions,
            consistency=consistency,
            repetitions=spec.sampling.repetitions,
        ),
        not_established=list(spec.not_established),
    )


def read_comparison_status(
    paths: TechtreePaths, comparison_id: str
) -> ForgeComparisonStatus:
    """Read one comparison's record back from its directory."""
    directory = paths.forge_comparison_dir(validate_id(comparison_id, "forgecmp"))
    record_file = directory / COMPARISON_FILENAME
    if not record_file.is_file():
        raise NotFoundError(
            f"no recorded forge comparison {comparison_id}",
            code="forge_comparison_not_found",
            details={"comparison_id": comparison_id, "path": str(directory)},
        )
    try:
        record = ForgeComparisonRecord.model_validate_json(record_file.read_bytes())
    except ModelValidationError as error:
        issue = error.errors(include_input=False, include_url=False)[0]
        raise ValidationError(
            f"invalid forge comparison evidence: {issue['msg']}",
            code="forge_evidence_invalid",
            details={"comparison_id": comparison_id, "path": str(directory)},
        ) from error
    return ForgeComparisonStatus(
        comparison_id=comparison_id,
        path=str(directory),
        report_path=str(directory / REPORT_FILENAME),
        record=record,
    )


# ---------------------------------------------------------------------------
# Pairing and totals
# ---------------------------------------------------------------------------


def _pair(
    task_id: str,
    attempt: int,
    baseline: list[ForgeAttemptRecord],
    candidate: list[ForgeAttemptRecord],
) -> ForgeAttemptPair:
    left = _find(baseline, task_id, attempt)
    right = _find(candidate, task_id, attempt)
    left_reward = left.reward if left is not None else None
    right_reward = right.reward if right is not None else None
    if left_reward is None or right_reward is None:
        delta = None
        result = ForgePairResult.UNRESOLVED
    else:
        delta = right_reward - left_reward
        if delta > 0:
            result = ForgePairResult.WIN
        elif delta < 0:
            result = ForgePairResult.LOSS
        else:
            result = ForgePairResult.TIE
    return ForgeAttemptPair(
        task_id=task_id,
        attempt=attempt,
        baseline_outcome=left.outcome if left is not None else None,
        baseline_reward=left_reward,
        candidate_outcome=right.outcome if right is not None else None,
        candidate_reward=right_reward,
        delta=delta,
        result=result,
    )


def _find(
    attempts: list[ForgeAttemptRecord], task_id: str, attempt: int
) -> ForgeAttemptRecord | None:
    return next(
        (a for a in attempts if a.task_id == task_id and a.attempt == attempt), None
    )


def _totals(status: ForgeRunStatus) -> ForgeArmTotals:
    attempts = status.record.attempts
    rewards = [a.reward for a in attempts if a.reward is not None]
    usages = [a.usage for a in attempts if a.usage is not None]
    calls = [u.api_calls for u in usages if u.api_calls is not None]
    tokens = [u.total_tokens for u in usages if u.total_tokens is not None]
    costs = [u.estimated_cost_usd for u in usages]
    return ForgeArmTotals(
        run_id=status.run_id,
        state=status.record.state,
        attempts_planned=len(status.spec.task_ids) * status.spec.sampling.repetitions,
        attempts_recorded=len(attempts),
        attempts_graded=sum(a.outcome is ForgeAttemptOutcome.GRADED for a in attempts),
        mean_reward=fmean(rewards) if rewards else None,
        agent_seconds=sum(a.agent_seconds for a in attempts),
        api_calls=sum(calls) if calls else None,
        total_tokens=sum(tokens) if tokens else None,
        cost_usd=(
            sum(cost for cost in costs if cost is not None)
            if costs and all(cost is not None for cost in costs)
            else None
        ),
        cost_statuses=sorted({u.cost_status for u in usages if u.cost_status}),
    )


def _consistency(task_id: str, pairs: list[ForgeAttemptPair]) -> ForgeTaskConsistency:
    own = [pair.result for pair in pairs if pair.task_id == task_id]
    wins = own.count(ForgePairResult.WIN)
    losses = own.count(ForgePairResult.LOSS)
    return ForgeTaskConsistency(
        task_id=task_id,
        wins=wins,
        losses=losses,
        ties=own.count(ForgePairResult.TIE),
        unresolved=own.count(ForgePairResult.UNRESOLVED),
        went_both_ways=wins > 0 and losses > 0,
    )


def _regression(task_id: str, pairs: list[ForgeAttemptPair]) -> ForgeTaskRegression:
    own = [pair for pair in pairs if pair.task_id == task_id]
    return ForgeTaskRegression(
        task_id=task_id,
        attempts_lost=[p.attempt for p in own if p.result is ForgePairResult.LOSS],
        attempts_won=[p.attempt for p in own if p.result is ForgePairResult.WIN],
    )


#: The verdict as the summary opens with it.
VERDICT_WORDS: Final[dict[ForgeVerdict, str]] = {
    ForgeVerdict.INCONCLUSIVE: "Inconclusive",
    ForgeVerdict.MIXED: "Mixed",
    ForgeVerdict.IMPROVED: "Improved with the Skill",
    ForgeVerdict.REGRESSED: "Regressed with the Skill",
    ForgeVerdict.NO_DIFFERENCE: "No difference",
}


def _summary(
    skill_name: str,
    pairs: list[ForgeAttemptPair],
    graded: list[ForgeAttemptPair],
    wins: int,
    losses: int,
    ties: int,
    *,
    verdict: ForgeVerdict,
    regressions: list[ForgeTaskRegression],
    consistency: list[ForgeTaskConsistency],
    repetitions: int,
) -> str:
    planned = len(pairs)
    sentences: list[str] = [_verdict_sentence(verdict, planned, len(graded))]
    if not graded:
        sentences.append(f"Nothing can be said about {skill_name} yet.")
        return " ".join(sentences)
    baseline_mean = fmean(
        pair.baseline_reward for pair in graded if pair.baseline_reward is not None
    )
    candidate_mean = fmean(
        pair.candidate_reward for pair in graded if pair.candidate_reward is not None
    )
    sentences.append(
        f"Over {len(graded)} graded {'pair' if len(graded) == 1 else 'pairs'}, "
        f"{skill_name} won {wins}, lost {losses} and tied {ties}; mean reward "
        f"{baseline_mean:.2f} without it and {candidate_mean:.2f} with it "
        f"({candidate_mean - baseline_mean:+.2f})."
    )
    if regressions:
        named = ", ".join(r.task_id for r in regressions)
        sentences.append(
            f"The Skill lost on {len(regressions)} "
            f"{'task' if len(regressions) == 1 else 'tasks'}: {named}."
        )
    if repetitions == 1:
        sentences.append(
            "One attempt per task; consistency across attempts was not measured."
        )
    elif any(task.went_both_ways for task in consistency):
        both = ", ".join(t.task_id for t in consistency if t.went_both_ways)
        sentences.append(
            f"The same task went both ways across attempts: {both}; the Skill's "
            "effect there is not steady."
        )
    return " ".join(sentences)


def _verdict_sentence(verdict: ForgeVerdict, planned: int, graded: int) -> str:
    opening = VERDICT_WORDS[verdict]
    if verdict is not ForgeVerdict.INCONCLUSIVE:
        return f"{opening}."
    pairs = "pair" if planned == 1 else "pairs"
    if graded < planned:
        return (
            f"{opening}: {graded} of {planned} planned {pairs} "
            f"{'has' if planned == 1 else 'have'} a verdict on both arms, so this "
            "is not a complete result."
        )
    return (
        f"{opening}: {graded} of {planned} planned {pairs} graded, fewer than "
        f"the {VERDICT_MINIMUM_PAIRS} a verdict needs."
    )
