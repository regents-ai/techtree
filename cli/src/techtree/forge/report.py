"""The report a person opens: one self-contained HTML file per comparison.

The file answers, in this order, what a developer deciding about a Skill
asks first: what was tested, did it help, where did it lose, what did each
arm use, and how much the conclusion can carry. Everything on the page is
copied from the comparison record and the two runs' own evidence files;
nothing is computed here that the record does not already hold.

The page is plain HTML with its own stylesheet inside it, no script and
nothing fetched, so it can be opened from disk, attached to a message or
kept beside the evidence for years and read the same way. Every planned
pair is listed whether or not it was resolved: a pair without a verdict
on both sides is shown as exactly that, never folded into a total.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Final

from techtree.forge.models import (
    ForgeArmTotals,
    ForgeAttemptOutcome,
    ForgeAttemptPair,
    ForgeBuildTasks,
    ForgeCollectionTasks,
    ForgeComparisonRecord,
    ForgeOutputFailureKind,
    ForgeOutputs,
    ForgePairResult,
    ForgeQualification,
    ForgeRepositorySource,
    ForgeRunStatus,
    ForgeTaskConsistency,
    GenerationSummary,
    QualificationCheck,
    TaskQualification,
)
from techtree.forge.qualify import (
    NOT_STARTED_DETAIL,
    SOLUTION_FAILED_DETAIL,
    SOLUTION_TIMED_OUT_DETAIL,
    TIMED_OUT_DETAIL,
)

__all__ = [
    "FEW_TASKS",
    "OUTCOME_WORDS",
    "OUTPUT_FAILURE_WORDS",
    "PATCH_LIMIT_BYTES",
    "REJECTION_WORDS",
    "SKIP_WORDS",
    "build_summary",
    "first_failed_check",
    "import_summary",
    "render_report",
    "task_verdict",
]

#: How every attempt outcome is said to a person, in the terminal and on the page.
OUTCOME_WORDS: Final[dict[ForgeAttemptOutcome, str]] = {
    ForgeAttemptOutcome.GRADED: "graded",
    ForgeAttemptOutcome.AGENT_TIMED_OUT: "agent ran out of time",
    ForgeAttemptOutcome.AGENT_FAILED: "agent did not finish",
    ForgeAttemptOutcome.OUTPUTS_REJECTED: "outputs refused before grading",
    ForgeAttemptOutcome.VERIFIER_TIMED_OUT: "tests ran out of time",
    ForgeAttemptOutcome.NO_VERDICT: "tests left no verdict",
}

#: How each reason an attempt's outputs were not taken as they are is said.
OUTPUT_FAILURE_WORDS: Final[dict[ForgeOutputFailureKind, str]] = {
    "escaping_link": "link that may leave the working directory",
    "special_entry": "not a file, folder or link",
    "artifact_missing": "required output not left",
    "output_too_large": "output too large to keep",
    "capture_incomplete": "outputs not fully read",
}

#: Fewer qualified tasks than this and a comparison can say how one attempt
#: went, not whether the Skill helps.
FEW_TASKS: Final = 3

#: Why the task generator passed a candidate commit over, in a person's words,
#: read as "N for <reason>". The keys are the generator's own; one it has not
#: named before is shown as is.
SKIP_WORDS: Final[dict[str, str]] = {
    "merge_commit": "being a merge commit",
    "excluded_author": "being by an excluded author",
    "short_message": "having a message too short to describe a problem",
    "problem_statement_too_short": "having a message too short to describe a problem",
    "non_bugfix_type": "being marked as something other than a bug fix",
    "no_bugfix_signal": "not saying it fixes a bug",
    "diff_fetch_failed": "changes that could not be read",
    "empty_source_patch": "changing no source file",
    "no_test_patch": "changing no test",
    "ci_only_patch": "changing only the automation setup",
    "too_many_source_files": "touching too many source files",
    "no_new_test_funcs": "adding no new test",
    "root_commit": "being the repository's first commit",
    "no_fail_to_pass": "new tests that did not go from failing to passing when run",
    "no_parseable_test_output": "a test run that left no readable result",
}

#: Why a committed task was rejected at qualification, in a person's words,
#: keyed by the first check that failed.
REJECTION_WORDS: Final[dict[str, str]] = {
    "image_build": "the task's environment image did not build",
    "workspace_at_base_commit": (
        "the image's copy of the repository is not clean at the task's starting commit"
    ),
    "verifier_material_absent": (
        "the image already carries the tests or the reference solution"
    ),
    "tests_recognized": "no test was named that should go from failing to passing",
    "control_fails": (
        "the unrepaired code did not fail its tests the way the task requires"
    ),
    "reference_passes": "the reference repair did not make the tests pass",
    "hidden_material_private": (
        "the instruction or the environment carries a file of the tests or the "
        "reference solution"
    ),
    "no_op_fails": "a run that did nothing did not score 0",
    "reference_solution_passes": "the reference solution did not make the tests pass",
    "alternative_solution_passes": "the task's other correct solution did not score 1",
    "wrong_solution_fails": "the task's deliberately wrong solution did not score 0",
    "verifier_output_bounded": (
        "the tests left more output than a task may, or something other than "
        "plain files"
    ),
}

#: What a person is told when a graded run stopped before its tests gave a
#: verdict, by the detail the check kept.
_STOPPED_WORDS: Final[dict[str, str]] = {
    TIMED_OUT_DETAIL: "its tests did not finish within the task's own time limit",
    SOLUTION_TIMED_OUT_DETAIL: (
        "its reference solution did not finish within the task's own time limit"
    ),
    SOLUTION_FAILED_DETAIL: "its reference solution stopped with an error",
    NOT_STARTED_DETAIL: "its environment could not be started",
}


def build_summary(
    generation: GenerationSummary, qualification: ForgeQualification | None
) -> str:
    """What the build made, how much of it qualified, and what it passed over."""
    emitted = generation.emitted
    tasks = f"{emitted} generated {_plural(emitted, 'task', 'tasks')}"
    if emitted == 0:
        sentence = "No task was generated"
    elif qualification is None:
        sentence = f"{tasks}; qualification has not finished"
    else:
        sentence = f"{len(qualification.qualified_task_ids)} of {tasks} qualified"
    if generation.skipped:
        by_words: dict[str, int] = {}
        for reason, count in generation.skip_reasons.items():
            words = SKIP_WORDS.get(reason, reason)
            by_words[words] = by_words.get(words, 0) + count
        said = "; ".join(
            f"{count} for {words}"
            for words, count in sorted(by_words.items(), key=lambda i: (-i[1], i[0]))
        )
        sentence += (
            f". {generation.skipped} of {generation.candidates} candidate "
            f"{_plural(generation.candidates, 'commit', 'commits')} "
            f"{_plural(generation.skipped, 'was', 'were')} passed over: {said}"
        )
    return sentence + "."


def import_summary(imported: int, qualification: ForgeQualification | None) -> str:
    """How much of an imported package qualified."""
    tasks = f"{imported} imported {_plural(imported, 'task', 'tasks')}"
    if qualification is None:
        return f"{tasks}; qualification has not finished"
    return f"{len(qualification.qualified_task_ids)} of {tasks} qualified"


def task_verdict(task: TaskQualification) -> str:
    """``task: qualified``, or ``task: rejected, <why>`` in a person's words."""
    failed = first_failed_check(task)
    if failed is None:
        return f"{task.task_id}: qualified"
    words = _STOPPED_WORDS.get(failed.detail) or REJECTION_WORDS.get(
        failed.name, failed.name
    )
    return f"{task.task_id}: rejected, {words}"


def first_failed_check(task: TaskQualification) -> QualificationCheck | None:
    return next((check for check in task.checks if not check.passed), None)


#: A patch longer than this is cut on the page; the file beside the run is whole.
PATCH_LIMIT_BYTES: Final = 65_536

_RESULT_WORDS: Final[dict[ForgePairResult, str]] = {
    ForgePairResult.WIN: "win",
    ForgePairResult.LOSS: "loss",
    ForgePairResult.TIE: "tie",
    ForgePairResult.UNRESOLVED: "unresolved",
}

_STYLE: Final = """
:root { color-scheme: light dark; }
body { margin: 0 auto; max-width: 72rem; padding: 1.5rem 1rem 4rem;
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
h1 { font-size: 1.6rem; margin: 0 0 .25rem; }
h2 { font-size: 1.15rem; margin: 2rem 0 .5rem; border-bottom: 1px solid
  color-mix(in srgb, currentColor 25%, transparent); padding-bottom: .25rem; }
.label { display: inline-block; font-size: .8rem; letter-spacing: .02em;
  border: 1px solid currentColor; border-radius: 999px; padding: .1rem .6rem;
  margin: .25rem 0 1rem; }
.meta { font-size: .9rem; opacity: .85; }
.meta dt { float: left; clear: left; width: 9rem; opacity: .7; }
.meta dd { margin: 0 0 .15rem 9rem; word-break: break-all; }
.summary { font-size: 1.1rem; }
.partial { border-left: 4px solid #c47f00; padding: .5rem .75rem; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: .95rem; }
th, td { text-align: left; vertical-align: top; padding: .35rem .5rem;
  border-bottom: 1px solid color-mix(in srgb, currentColor 15%, transparent); }
th { font-weight: 600; }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
.win { color: #1a7f37; } .loss { color: #b42318; } .unresolved { color: #c47f00; }
details { margin: .5rem 0; }
summary { cursor: pointer; }
pre { overflow: auto; font-size: .82rem; padding: .75rem; border-radius: .25rem;
  background: color-mix(in srgb, currentColor 7%, transparent); }
code { font-size: .9em; overflow-wrap: anywhere; }
ul.plain { padding-left: 1.2rem; }
footer { margin-top: 3rem; font-size: .85rem; opacity: .7; }
"""


def render_report(
    record: ForgeComparisonRecord,
    *,
    repository: ForgeRepositorySource | None,
    baseline: ForgeRunStatus,
    candidate: ForgeRunStatus,
) -> str:
    """Return the page for ``record`` as one HTML document.

    ``repository`` is where a build's tasks came from; a comparison on a
    collection has none, and its page says the tasks were written from a
    Skill.
    """
    spec = candidate.spec
    match record.tasks_from:
        case ForgeBuildTasks(build_id=build_id):
            assert repository is not None  # a build's tasks come from a repository
            subject = _short_name(repository.repository)
            label = "Local evidence about a mutable subject"
            source = [
                _dd("Repository", repository.repository),
                _dd("Commit", repository.head_commit),
                _dd("Build", build_id),
            ]
            task = "repair this repository"
        case ForgeCollectionTasks(collection_id=collection_id, version=version):
            subject = f"collection {collection_id}"
            label = (
                "Evaluation on Skill-derived tasks: local evidence about a "
                "mutable subject"
            )
            source = [_dd("Collection", f"{collection_id}, version {version}")]
            task = "complete these tasks, which were written from a Skill"
    parts = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_e(record.skill_name)} on {_e(subject)}</title>",
        f"<style>{_STYLE}</style></head><body>",
        f"<h1>Skill experiment: {_e(record.skill_name)} on {_e(subject)}</h1>",
        f'<div class="label">{_e(label)}</div>',
        '<dl class="meta">',
        *source,
        _dd("Baseline run", record.baseline_run_id),
        _dd("Candidate run", record.candidate_run_id),
        _dd("Comparison", record.comparison_id),
        _dd("Created", record.created_at.isoformat()),
        "</dl>",
        "<h2>The question</h2>",
        "<p>Does the Skill <strong>"
        + _e(record.skill_name)
        + "</strong> (<code>"
        + _e(record.skill_digest[:19])
        + "</code>) help Hermes Agent v"
        + _e(spec.agent.version)
        + " with "
        + _e(spec.model.model_id)
        + " from "
        + _e(spec.model.provider)
        + " "
        + _e(task)
        + "? Both arms ran the same "
        + str(len(spec.task_ids))
        + _plural(len(spec.task_ids), " task", " tasks")
        + ", "
        + str(spec.sampling.repetitions)
        + _plural(spec.sampling.repetitions, " attempt", " attempts")
        + " each, from a fresh Hermes state with memory off, in a sandbox with "
        "no network. The candidate had the Skill preloaded; the baseline had "
        "nothing else different.</p>",
        "<h2>In short</h2>",
        f'<p class="summary{"" if record.complete else " partial"}">'
        f"{_e(record.summary)}</p>",
        "<h2>Where the Skill lost</h2>",
        _regressions(record),
        "<h2>Baseline, candidate, difference</h2>",
        _totals_table(record.baseline, record.candidate),
        "<h2>Task by task</h2>",
        _pairs_table(record),
        "<h2>What each attempt left, and its grading</h2>",
        *(_pair_details(pair, baseline, candidate) for pair in record.pairs),
        "<h2>What differed between the arms</h2>",
        _differences(record),
        "<h2>Limits of this evidence</h2>",
        _limits(record),
        "<footer>Written by <code>techtree forge compare</code>. The comparison "
        "record beside this page holds every number here in machine-readable "
        "form.</footer>",
        "</body></html>",
    ]
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def _totals_table(baseline: ForgeArmTotals, candidate: ForgeArmTotals) -> str:
    rows = [
        (
            "Attempts graded",
            f"{baseline.attempts_graded} of {baseline.attempts_planned}",
            f"{candidate.attempts_graded} of {candidate.attempts_planned}",
            _signed_int(candidate.attempts_graded - baseline.attempts_graded),
        ),
        (
            "Mean reward (graded attempts)",
            _number(baseline.mean_reward),
            _number(candidate.mean_reward),
            _signed(
                None
                if baseline.mean_reward is None or candidate.mean_reward is None
                else candidate.mean_reward - baseline.mean_reward
            ),
        ),
        (
            "Agent time",
            _seconds(baseline.agent_seconds),
            _seconds(candidate.agent_seconds),
            _signed_seconds(candidate.agent_seconds - baseline.agent_seconds),
        ),
        (
            "Model calls",
            _count(baseline.api_calls),
            _count(candidate.api_calls),
            _signed_count(baseline.api_calls, candidate.api_calls),
        ),
        (
            "Tokens",
            _count(baseline.total_tokens),
            _count(candidate.total_tokens),
            _signed_count(baseline.total_tokens, candidate.total_tokens),
        ),
        (
            "Cost",
            _cost(baseline),
            _cost(candidate),
            _signed(
                None
                if baseline.cost_usd is None or candidate.cost_usd is None
                else candidate.cost_usd - baseline.cost_usd,
                prefix="$",
            ),
        ),
        ("Run ended", baseline.state, candidate.state, ""),
    ]
    body = "".join(
        f"<tr><th>{_e(label)}</th><td class=n>{_e(b)}</td>"
        f"<td class=n>{_e(c)}</td><td class=n>{_e(d)}</td></tr>"
        for label, b, c, d in rows
    )
    return (
        '<div class="scroll"><table><thead><tr><th></th><th class=n>Baseline</th>'
        "<th class=n>Candidate</th><th class=n>Difference</th></tr></thead>"
        f"<tbody>{body}</tbody></table></div>"
    )


def _regressions(record: ForgeComparisonRecord) -> str:
    if not record.regressions:
        return "<p>The Skill lost no graded pair.</p>"
    items = "".join(
        f"<li><code>{_e(r.task_id)}</code>: lost "
        f"{_attempts(r.attempts_lost)}"
        + (f"; won {_attempts(r.attempts_won)}" if r.attempts_won else "")
        + "</li>"
        for r in record.regressions
    )
    return (
        f"<p>The Skill lost on {len(record.regressions)} "
        f"{_plural(len(record.regressions), 'task', 'tasks')}, whatever the mean "
        f'difference says.</p><ul class="plain">{items}</ul>'
    )


def _attempts(attempts: list[int]) -> str:
    return _plural(len(attempts), "attempt ", "attempts ") + ", ".join(
        str(a) for a in attempts
    )


def _consistency_words(task: ForgeTaskConsistency, repetitions: int) -> str:
    if repetitions == 1:
        return "one attempt"
    parts = [
        f"{task.wins} {_plural(task.wins, 'win', 'wins')}",
        f"{task.losses} {_plural(task.losses, 'loss', 'losses')}",
        f"{task.ties} {_plural(task.ties, 'tie', 'ties')}",
    ]
    if task.unresolved:
        parts.append(f"{task.unresolved} unresolved")
    words = ", ".join(parts)
    return f"{words}; went both ways" if task.went_both_ways else words


def _pairs_table(record: ForgeComparisonRecord) -> str:
    consistency = {task.task_id: task for task in record.consistency}
    rows: list[str] = []
    seen: set[str] = set()
    for pair in record.pairs:
        first = pair.task_id not in seen
        seen.add(pair.task_id)
        across = ""
        if first:
            task = consistency[pair.task_id]
            span = sum(p.task_id == pair.task_id for p in record.pairs)
            both = ' class="loss"' if task.went_both_ways else ""
            across = (
                f"<td rowspan={span}{both}>"
                f"{_e(_consistency_words(task, record.repetitions))}</td>"
            )
        rows.append(
            "<tr>"
            f"<td>{_e(pair.task_id)}</td><td class=n>{pair.attempt}</td>"
            f"<td>{_e(_side(pair.baseline_outcome, pair.baseline_reward))}</td>"
            f"<td>{_e(_side(pair.candidate_outcome, pair.candidate_reward))}</td>"
            f"<td class=n>{_e(_signed(pair.delta))}</td>"
            f'<td class="{pair.result.value}">{_e(_RESULT_WORDS[pair.result])}</td>'
            f"{across}</tr>"
        )
    body = "".join(rows)
    note = (
        "<p>One attempt per task; consistency across attempts was not measured.</p>"
        if record.repetitions == 1
        else ""
    )
    counts = (
        f"{record.wins} {_plural(record.wins, 'win', 'wins')}, "
        f"{record.losses} {_plural(record.losses, 'loss', 'losses')}, "
        f"{record.ties} {_plural(record.ties, 'tie', 'ties')}, "
        f"{record.unresolved} unresolved of {record.pairs_planned} planned "
        f"{_plural(record.pairs_planned, 'pair', 'pairs')}."
    )
    return (
        f"<p>{_e(counts)}</p>"
        '<div class="scroll"><table><thead><tr><th>Task</th><th class=n>Attempt</th>'
        "<th>Baseline</th><th>Candidate</th><th class=n>Difference</th>"
        "<th>Result</th><th>Across attempts</th></tr></thead>"
        f"<tbody>{body}</tbody></table></div>{note}"
    )


def _pair_details(
    pair: ForgeAttemptPair, baseline: ForgeRunStatus, candidate: ForgeRunStatus
) -> str:
    title = f"{pair.task_id} #{pair.attempt}: {_RESULT_WORDS[pair.result]}" + (
        f" ({_signed(pair.delta)})" if pair.delta is not None else ""
    )
    return (
        f'<details><summary class="{pair.result.value}">{_e(title)}</summary>'
        + _arm_details("Baseline", baseline, pair.task_id, pair.attempt)
        + _arm_details("Candidate", candidate, pair.task_id, pair.attempt)
        + "</details>"
    )


def _arm_details(label: str, status: ForgeRunStatus, task_id: str, attempt: int) -> str:
    attempt_dir = Path(status.path) / "tasks" / task_id / str(attempt)
    patch = _read_text(attempt_dir / "patch.diff")
    details = _read_text(attempt_dir / "grading" / "verifier" / "reward-details.json")
    record = next(
        (
            a
            for a in status.record.attempts
            if (a.task_id, a.attempt) == (task_id, attempt)
        ),
        None,
    )
    parts = [f"<h3>{_e(label)}</h3>"]
    if record is not None and record.outputs is not None:
        parts.append(_outputs_details(record.outputs, attempt_dir))
    elif patch is None:
        parts.append("<p>No patch was recorded for this attempt.</p>")
    elif not patch.strip():
        parts.append("<p>The agent changed nothing.</p>")
    else:
        parts.append(
            f"<p>Patch (<code>{_e(str(attempt_dir / 'patch.diff'))}</code>)</p>"
        )
        parts.append(f"<pre>{_e(_clip(patch, attempt_dir / 'patch.diff'))}</pre>")
    if details is not None:
        parts.append("<p>Grading</p>")
        parts.append(f"<pre>{_e(_pretty_json(details))}</pre>")
    return "".join(parts)


def _outputs_details(outputs: ForgeOutputs, attempt_dir: Path) -> str:
    manifest = attempt_dir / "outputs" / "manifest.json"
    parts = [
        f"<p>{outputs.added} added, {outputs.modified} changed, "
        f"{outputs.deleted} deleted in <code>{_e(outputs.work_dir)}</code> "
        f"(<code>{_e(str(manifest))}</code>)</p>"
    ]
    parts.extend(
        "<p>"
        + (f"<code>{_e(failure.path)}</code>: " if failure.path is not None else "")
        + f"{_e(OUTPUT_FAILURE_WORDS[failure.kind])} ({_e(failure.detail)})</p>"
        for failure in outputs.failures
    )
    return "".join(parts)


def _differences(record: ForgeComparisonRecord) -> str:
    comparison = record.comparability
    items = "".join(
        f"<li><code>{_e(d.pointer)}</code>: baseline "
        f"<code>{_e(_brief(d.baseline))}</code>, candidate "
        f"<code>{_e(_brief(d.candidate))}</code></li>"
        for d in comparison.differences
    )
    allowed = ", ".join(comparison.allowed_differences)
    baseline_digest = _e(comparison.baseline_configuration_digest)
    candidate_digest = _e(comparison.candidate_configuration_digest)
    return (
        f"<p>The comparability gate allowed the arms to differ only at "
        f"<code>{_e(allowed)}</code>, and found these differences:</p>"
        f'<ul class="plain">{items}</ul>'
        f"<p>Baseline specification <code>{baseline_digest}</code>; candidate "
        f"specification <code>{candidate_digest}</code>.</p>"
    )


def _limits(record: ForgeComparisonRecord) -> str:
    match record.tasks_from:
        case ForgeBuildTasks():
            tasks = "this repository's tasks"
            graded = "the reference repair was graded when the build was qualified"
            derived = []
        case ForgeCollectionTasks():
            tasks = "these tasks"
            graded = "the reference solutions were graded when the tasks were qualified"
            derived = [
                "The tasks were written from a Skill, so they test whether the "
                "agent can use what that Skill teaches. They say nothing about "
                "how it does on other work, and a win here is not evidence that "
                "Skills help in general.",
            ]
    items = [
        "This is evidence about one agent, as configured on this machine, on "
        f"{tasks}. The subject can change: a different Hermes "
        "build, a provider routing the same model name elsewhere, or another "
        "day may give a different result.",
        *derived,
        f"Rewards come from the tasks' own tests, run locally the way {graded}.",
        "A cost is what Hermes reported; an attempt Hermes could not put a "
        "dollar figure on is listed with its status, not as free.",
    ]
    if not record.complete:
        items.append(
            f"{record.unresolved} of {record.pairs_planned} planned pairs have no "
            "verdict on both arms. The counts above are over the graded pairs "
            "only; this is a partial observation, not a complete result."
        )
    limits = (
        '<ul class="plain">' + "".join(f"<li>{_e(i)}</li>" for i in items) + "</ul>"
    )
    if not record.not_established:
        return limits
    unknowns = "".join(f"<li>{_e(i)}</li>" for i in record.not_established)
    return f'{limits}<p>The run did not establish:</p><ul class="plain">{unknowns}</ul>'


# ---------------------------------------------------------------------------
# Words and numbers
# ---------------------------------------------------------------------------


def _side(outcome: ForgeAttemptOutcome | None, reward: float | None) -> str:
    if outcome is None:
        return "not attempted"
    words = OUTCOME_WORDS[outcome]
    return f"reward {reward:g}" if reward is not None else words


def _cost(totals: ForgeArmTotals) -> str:
    statuses = f" ({', '.join(totals.cost_statuses)})" if totals.cost_statuses else ""
    if totals.cost_usd is None:
        return "no dollar figure" + statuses
    return f"${totals.cost_usd:.4f}{statuses}"


def _number(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def _signed(value: float | None, prefix: str = "") -> str:
    return "—" if value is None else f"{value:+.3f}".replace("+", f"+{prefix}", 1)


def _signed_int(value: int) -> str:
    return f"{value:+d}"


def _count(value: int | None) -> str:
    return "—" if value is None else f"{value:,}"


def _signed_count(baseline: int | None, candidate: int | None) -> str:
    if baseline is None or candidate is None:
        return "—"
    return f"{candidate - baseline:+,}"


def _seconds(value: float) -> str:
    return f"{value:.0f} s"


def _signed_seconds(value: float) -> str:
    return f"{value:+.0f} s"


def _plural(count: int, one: str, many: str) -> str:
    return one if count == 1 else many


def _short_name(repository: str) -> str:
    return Path(repository).name or repository


def _brief(value: object) -> str:
    text = json.dumps(value, sort_keys=True)
    return text if len(text) <= 240 else text[:237] + "..."


def _pretty_json(text: str) -> str:
    try:
        return json.dumps(json.loads(text), indent=2, sort_keys=True)
    except ValueError:
        return text


def _clip(patch: str, path: Path) -> str:
    encoded = patch.encode("utf-8")
    if len(encoded) <= PATCH_LIMIT_BYTES:
        return patch
    kept = encoded[:PATCH_LIMIT_BYTES].decode("utf-8", errors="ignore")
    return (
        f"{kept}\n... cut after {PATCH_LIMIT_BYTES} bytes; "
        f"the whole patch is at {path}\n"
    )


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _dd(label: str, value: str) -> str:
    return f"<dt>{_e(label)}</dt><dd>{_e(value)}</dd>"


def _e(text: str) -> str:
    return escape(text, quote=True)
