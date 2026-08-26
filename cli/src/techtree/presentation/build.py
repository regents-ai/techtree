"""Turning one signed report into one neutral payload. Spec section 7.14.

Everything a reader is shown comes from here, and everything here comes from
the signed report and the signed receipts it commits to. That is the whole
design: a renderer receives numbers it cannot recompute, statuses it cannot
soften, and caveats it cannot drop, so two channels showing the same run cannot
say different things about it.

Four rules shape what is built.

*The report decides, the builder describes.* No score is recomputed, no verdict
is re-derived, and no status is interpreted. ``decision``, ``proof_grade`` and
the comparison status are copied; the caveats are the plain-English reading of
those same fields rather than a second opinion about them.

*Warnings are carried, never smoothed.* A real comparison in this build is
usually ``controlled_with_warnings`` — a provider that publishes no model
revision, a daemon that reports no resolved image digest — and that is a fact
about how strongly the run is attested. It arrives as a caveat with warning
severity, in front of the reader, in every channel.

*A rejected candidate is a measurement.* The decision is stated as what it is.
A Skill that did not clear the Campaign's declared threshold produced evidence
about that Skill, and framing it as a failure of the run would be both
discouraging and wrong.

*Nothing is offered that does not exist.* ``next_actions`` names commands this
build actually has. Section 7.14's four steps are all present for a graded
result: look at the tasks, export the context a host agent proposes a revision
from, prepare the v1-against-v2 comparison, and verify the local proof. The
reasoning turn itself is WP9+'s, so what is offered is the deterministic
command that produces its input rather than a promise to think.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from techtree.errors import PrerequisiteError
from techtree.identity.models import VerificationResult
from techtree.models.campaign import CampaignSpec
from techtree.models.cli import NextAction
from techtree.models.episode_receipt import EpisodeReceipt
from techtree.models.skill import SkillArtifact
from techtree.models.uplift_report import (
    ComparisonStatus,
    TaskDelta,
    UpliftDecision,
    UpliftReport,
)
from techtree.presentation.evidence import RecordedEvidence
from techtree.presentation.models import (
    PRESENTATION_SCHEMA_VERSION,
    DerivedCost,
    EconomicsSource,
    PresentationCaveat,
    ScoreBar,
    SkillSummary,
    TaskOutcome,
    TaskResultRow,
    UpliftPresentationPayload,
)
from techtree.presentation.sanitize import (
    ensure_no_hidden_task_material,
    sanitize_label,
)
from techtree.receipts.compare import (
    MODEL_REVISION_UNDISCOVERABLE,
    weaker_claim_warnings,
)
from techtree.receipts.execution import (
    ComparisonExecutionRecord,
    CostProvenance,
    TotalCost,
    VariantUsage,
)
from techtree.verifiers.budget import price_profile_for

__all__ = [
    "BASELINE_SKILL_LABEL",
    "FIRST_CHANGE_LABEL",
    "FIRST_RESULT_LABEL",
    "HELD_FIXED_LINE",
    "LATER_RESULT_LABEL",
    "NOT_BROAD_CAPABILITY_LINE",
    "P1_MEANING",
    "SCORE_BAR_WIDTH",
    "SECOND_CHANGE_LABEL",
    "SECOND_RESULT_LABEL",
    "VERIFICATION_FAILED",
    "VERIFICATION_NOT_VERIFIED",
    "VERIFICATION_VERIFIED",
    "build_uplift_presentation",
    "cost_explanation",
    "cost_summary",
    "decision_headline",
    "efficiency_sentence",
    "score_bars",
    "solved_line",
    "task_count_line",
    "task_counts",
]

#: What a Skill-insertion comparison measures against. Not an absent value,
#: and not what a replacement measures against: a replacement's baseline is a
#: Skill, and it is called by its own name.
BASELINE_SKILL_LABEL: Final = "No tested Skill"

#: What each result is called. Decisions document 0009 fixes the spellings: the
#: first result is the receipt for adding a Skill, and a later one is the same
#: comparison run again with a revised Skill. Which of them a reader is holding
#: is worked out from the Skills the run itself carries, never assumed — a
#: third comparison labelled as the second would be a receipt for work nobody
#: did.
FIRST_RESULT_LABEL: Final = "Hello World Uplift Receipt"
SECOND_RESULT_LABEL: Final = "Hello World — Iteration 2"
LATER_RESULT_LABEL: Final = "Hello World — A Later Iteration"

#: The other half of decisions document 0019 section 3's second statement, and
#: the whole of its first: one changed Skill, and everything else the same. It
#: is a constant rather than a sentence each renderer writes, because a channel
#: that made a weaker version of this claim than another channel would be the
#: one somebody quoted.
HELD_FIXED_LINE: Final = (
    "Everything else was the same on both sides: the same model sampled the "
    "same way, the same harness and tools, the same runtime image, the same "
    "tasks in the same order, the same reward, and the same declared limits."
)

#: What changed, in the words decisions document 0019 section 1 fixes. The two
#: sides are named as roles rather than by digest, because the digests are
#: printed underneath and a reader needs the shape of the comparison first.
FIRST_CHANGE_LABEL: Final = "No tested Skill → Skill v1"
SECOND_CHANGE_LABEL: Final = "Skill v1 → Skill v2"

#: Decisions document 0005 section 3.4, verbatim. The only words this build is
#: permitted to explain ``P1`` with.
P1_MEANING: Final = "integrity-bound, participant-attested local execution"

#: What each decision actually established, said as what was measured rather
#: than as a verdict that was won.
#:
#: The bar on this Climb is to beat a baseline of zero by any margin at all, on
#: a synthetic task family, at proof grade P1, with no publication eligibility.
#: "Accepted" and "met the threshold" are both literally true of that and both
#: read as a benchmark somebody passed, which is the one thing this result is
#: not. So the accepted case says what it can defend — that the Skill improved
#: on this particular task family — and the standing line underneath says what
#: it cannot.
#:
#: An accepted decision always means the candidate out-scored the baseline:
#: :func:`~techtree.receipts.uplift.decide_uplift` reaches it only through a
#: positive delta. A rejected one may still have moved the score a little, so
#: it is described by the bar it fell under rather than as no improvement.
DECISION_HEADLINE: Final[dict[str, str]] = {
    "accepted": "Improved on this development task family",
    "rejected": "Did not clear the bar this Climb declared",
    "inconclusive": "Not decided: this Climb declared no rule that could decide it",
    "invalid": "Not valid: this comparison cannot carry a result",
    "development_only": "Development-only: this report states no verdict",
}

#: The sentence that stops any of the headlines above being read as a claim
#: about what the Skill can do in general. It is not a footer: decisions
#: document 0013's toy/synthetic boundary belongs in the first lines, beside
#: the number a reader would otherwise quote on its own.
NOT_BROAD_CAPABILITY_LINE: Final = "Not broad-capability evidence"

#: How wide a score bar is drawn, in cells. Fixed so two bars are comparable
#: and so a rendering is the same width on every terminal.
SCORE_BAR_WIDTH: Final = 24

VERIFICATION_VERIFIED: Final = "verified_offline"
VERIFICATION_FAILED: Final = "verification_failed"
VERIFICATION_NOT_VERIFIED: Final = "not_verified"

_FILLED: Final = "█"
_EMPTY: Final = "·"

#: What one task is worth when it is got right. The rewards this build measures
#: are all-or-nothing, and a headline count is only offered for a reward that
#: is: see :func:`_tasks_scored_full`.
_FULL_SCORE: Final = 1.0

#: The unit the recorded prices are quoted in.
_TOKENS_PER_MILLION: Final = 1_000_000.0


def build_uplift_presentation(
    *,
    report: UpliftReport,
    campaign: CampaignSpec,
    baseline_receipts: Sequence[EpisodeReceipt],
    candidate_receipts: Sequence[EpisodeReceipt],
    campaign_title: str,
    baseline_skill: SkillArtifact | None,
    candidate_skill: SkillArtifact,
    verification: VerificationResult | None,
    execution_record: ComparisonExecutionRecord | None = None,
    recorded_evidence: RecordedEvidence | None = None,
) -> UpliftPresentationPayload:
    """Build a channel-neutral presentation payload from a signed report.

    ``verification`` is the result of checking the run's proof bundle offline,
    or ``None`` when the reader asked not to check it. The three states are
    kept apart in ``verification_status`` because "not checked" and "checked
    and failed" are different things to tell somebody, and a development-only
    report has no proof to check at all.

    ``execution_record`` is decisions document 0007 R6's signed operational
    record, when the run carries one. It is the only source of a *reported*
    cost figure and the preferred source of tokens and timing; a payload built
    without one says so in ``economics_source`` and carries the
    operational-evidence caveat rather than a number nobody signed.

    ``campaign`` is the run's own signed Campaign. It says which model was
    measured, which is what lets a cost be worked out from the prices this
    release recorded and what lets the weaker-claim warning name its
    coordinate instead of gesturing at one.

    ``recorded_evidence`` is what
    :func:`~techtree.presentation.evidence.read_recorded_evidence` read back
    out of the run's own digest-checked files, when they are still there. It
    adds nothing to any artifact; it is counted while the result is drawn.
    """
    economics = _economics(execution_record, baseline_receipts, candidate_receipts)
    task_rows = _task_rows(report.task_deltas)
    scored_full = _tasks_scored_full(task_rows)
    seen = recorded_evidence
    baseline_seen = None if seen is None else seen.baseline
    candidate_seen = None if seen is None else seen.candidate
    derived = _derived_cost(campaign, execution_record, economics)
    unavailable = (
        None
        if derived is not None or economics.cost.cost_usd is not None
        else _cost_unavailable_reason(campaign, execution_record, economics)
    )
    generation = _generation(baseline_skill)
    primary = report.primary_result
    payload = UpliftPresentationPayload(
        schema_version=PRESENTATION_SCHEMA_VERSION,
        run_id=report.run_id,
        campaign_title=sanitize_label(campaign_title),
        comparison_label=_comparison_label(generation),
        change_label=_change_label(generation, baseline_skill, candidate_skill),
        baseline_skill=_skill_summary(baseline_skill, _baseline_label(baseline_skill)),
        candidate_skill=_skill_summary(candidate_skill, candidate_skill.name),
        baseline_score=primary.baseline_mean,
        candidate_score=primary.candidate_mean,
        absolute_delta=primary.absolute_delta,
        relative_delta=primary.relative_delta,
        wins=primary.wins,
        losses=primary.losses,
        ties=primary.ties,
        task_rows=task_rows,
        baseline_tasks_scored_full=scored_full[0],
        candidate_tasks_scored_full=scored_full[1],
        baseline_tokens=economics.baseline_tokens,
        candidate_tokens=economics.candidate_tokens,
        baseline_seconds=economics.baseline_seconds,
        candidate_seconds=economics.candidate_seconds,
        baseline_model_turns=(
            None if baseline_seen is None else baseline_seen.model_turns
        ),
        candidate_model_turns=(
            None if candidate_seen is None else candidate_seen.model_turns
        ),
        baseline_rate_limited_calls=(
            None if baseline_seen is None else baseline_seen.rate_limited_calls
        ),
        candidate_rate_limited_calls=(
            None if candidate_seen is None else candidate_seen.rate_limited_calls
        ),
        every_rollout_completed=(
            None if seen is None else seen.every_rollout_completed
        ),
        economics_source=economics.source,
        cost_usd=economics.cost.cost_usd,
        cost_provenance=economics.cost.provenance,
        derived_cost=derived,
        cost_unavailable_reason=unavailable,
        decision=report.decision.value,
        proof_grade=report.proof_grade,
        verification_status=_verification_status(verification),
        caveats=_caveats(
            report=report,
            campaign=campaign,
            verification=verification,
            economics=economics,
            recorded_evidence=recorded_evidence,
            derived=derived,
        ),
        next_actions=_next_actions(report.run_id, report.proof_grade),
    )
    ensure_no_hidden_task_material(payload)
    return payload


def task_counts(payload: UpliftPresentationPayload) -> tuple[int, int, int] | None:
    """Return each side's count and the total, in the unit a person counts in.

    A mean is what the report holds and a count is what a reader thinks in, and
    the two are the same fact for an all-or-nothing reward. A reward that is not
    all-or-nothing has no such count, and this returns nothing rather than
    rounding one into existence.

    The three numbers are returned rather than one sentence because the two
    channels have room for different words around them and must never be free
    to disagree about the numbers themselves.
    """
    baseline = payload.baseline_tasks_scored_full
    candidate = payload.candidate_tasks_scored_full
    if baseline is None or candidate is None:
        return None
    return baseline, candidate, len(payload.task_rows)


def task_count_line(payload: UpliftPresentationPayload) -> str | None:
    """Return the count, both sides and the movement, as one line."""
    counted = task_counts(payload)
    if counted is None:
        return None
    baseline, candidate, total = counted
    return f"{baseline} of {total} → {candidate} of {total} ({candidate - baseline:+d})"


def decision_headline(payload: UpliftPresentationPayload) -> str:
    """Return what this comparison established, in one line."""
    return DECISION_HEADLINE[payload.decision]


def solved_line(payload: UpliftPresentationPayload) -> str:
    """Return the count a reader can act on: solved, still failing, regressed.

    In a Skill-insertion comparison the baseline scores nothing on every task,
    so a tie means both sides failed the task rather than that nothing moved.
    Reporting wins and ties would then read as a clean sweep while hiding the
    most actionable fact in the run, which is how many tasks are still failing.
    Wins, losses and ties stay in the per-task table and in the machine
    envelope, where they are read by something that knows what they mean.

    A reward that is not all-or-nothing carries no count of solved tasks (see
    :func:`_tasks_scored_full`), and nothing is inferred in its absence: the
    regressions are reported on their own rather than beside a number this
    build would have had to invent.
    """
    regressions = f"{payload.losses} regression{'' if payload.losses == 1 else 's'}"
    counted = task_counts(payload)
    if counted is None:
        return regressions
    _, candidate, total = counted
    return (
        f"Solved {candidate} of {total} · {total - candidate} still failing · "
        f"{regressions}"
    )


def efficiency_sentence(payload: UpliftPresentationPayload) -> str | None:
    """Return what the candidate saved against the baseline, on this run.

    The two sides' turn counts, token totals and clocks are the most striking
    measurement most runs produce, and a pair of numbers on adjacent lines is
    not a finding. The difference is, so it is stated — and stated as a fact
    about this one controlled comparison, because without that anchor the
    percentages read as a general claim about what Skills do, which nothing
    here measures.

    Every figure needs both of its sides. A measurement one side did not record
    is left out entirely rather than compared against a zero, and a side that
    spent exactly what the other did contributes no difference to report. A
    comparison with no differences left to report gets no sentence at all.
    """
    turns = _saving(
        payload.baseline_model_turns,
        payload.candidate_model_turns,
        fewer="took {count} fewer model turn{s}",
        more="took {count} more model turn{s}",
    )
    tokens = _saving(
        payload.baseline_tokens,
        payload.candidate_tokens,
        fewer="used {count} fewer token{s}",
        more="used {count} more token{s}",
    )
    clock = _saving(
        payload.baseline_seconds,
        payload.candidate_seconds,
        fewer="finished {count} seconds sooner",
        more="finished {count} seconds later",
    )
    savings = [phrase for phrase in (turns, tokens, clock) if phrase is not None]
    if not savings:
        return None
    counted = turns is not None or tokens is not None
    return (
        f"On this controlled run the Skill {_listed(savings)}. "
        f"{_WORK_OR_WEATHER[counted, clock is not None]}"
    )


#: What the numbers above are properties of. Turn and token counts are
#: properties of the work and reproduce; a clock also reads this machine and
#: how busy the provider was that afternoon, and a reader deciding what to
#: repeat needs to know which of the two they are holding.
_WORK_OR_WEATHER: Final[dict[tuple[bool, bool], str]] = {
    (True, True): (
        "Those counts are properties of the work; how long each side took also "
        "depends on this machine and on how busy the provider was."
    ),
    (True, False): "Those counts are properties of the work.",
    (False, True): (
        "How long each side took depends on this machine and on how busy the "
        "provider was, as well as on the work."
    ),
}


def _saving(
    baseline: float | int | None,
    candidate: float | int | None,
    *,
    fewer: str,
    more: str,
) -> str | None:
    """Return one measured difference, or nothing where there is not one."""
    if baseline is None or candidate is None or baseline == candidate:
        return None
    difference = abs(baseline - candidate)
    count = f"{difference:,.1f}" if isinstance(difference, float) else f"{difference:,}"
    phrase = (fewer if candidate < baseline else more).format(
        count=count, s="" if difference == 1 else "s"
    )
    if not baseline:
        return phrase
    return f"{phrase} ({difference / baseline:.0%})"


def _listed(phrases: list[str]) -> str:
    """Join what was measured into one readable list."""
    if len(phrases) == 1:
        return phrases[0]
    if len(phrases) == 2:
        return f"{phrases[0]} and {phrases[1]}"
    return f"{', '.join(phrases[:-1])}, and {phrases[-1]}"


def _calls(count: int) -> str:
    """Return a count of model calls, in the number the count actually is."""
    return f"{count:,} model call" if count == 1 else f"{count:,} model calls"


def cost_summary(payload: UpliftPresentationPayload) -> str:
    """Return the figure and, in the same breath, what kind of figure it is.

    Decisions document 0007 R6: a number that was worked out and a number that
    was billed are different claims, and the one word that tells them apart
    travels with the number rather than somewhere below it.
    """
    if payload.cost_usd is not None:
        return f"${payload.cost_usd:.2f}, {_COST_PROVENANCE[payload.cost_provenance]}"
    if payload.derived_cost is not None:
        return f"about ${payload.derived_cost.usd:.2f}, worked out here, not billed"
    return "unavailable"


def cost_explanation(payload: UpliftPresentationPayload) -> list[str]:
    """Return what a reader needs in order to judge the figure above it."""
    if payload.cost_usd is not None:
        return []
    derived = payload.derived_cost
    if derived is None:
        assert payload.cost_unavailable_reason is not None
        return [payload.cost_unavailable_reason]
    lines = [
        f"Computed from {derived.input_tokens:,} input and "
        f"{derived.output_tokens:,} output tokens at the prices this release "
        "recorded. Your provider's bill is what you actually pay."
    ]
    cached = derived.cached_input_tokens
    if cached and not derived.prices_name_a_cached_rate:
        lines.append(
            f"{cached:,} of those input tokens came back from the provider's "
            "cache. The recorded prices name no separate rate for those, so "
            "every token is priced at the full rate and the figure above is "
            "on the high side."
        )
    return lines


def score_bars(payload: UpliftPresentationPayload) -> list[ScoreBar]:
    """Return the two bars a renderer draws the headline with.

    The scale is the larger of the two scores or one, so a reward that is
    bounded at 1.0 draws against a full bar and one that is not stays
    comparable between the two sides.
    """
    maximum = max(1.0, payload.baseline_score, payload.candidate_score)
    return [
        ScoreBar(
            label=label,
            value=value,
            maximum=maximum,
            display=_bar(value, maximum),
        )
        for label, value in (
            ("Baseline", payload.baseline_score),
            ("Candidate", payload.candidate_score),
        )
    ]


# ---------------------------------------------------------------------------
# The pieces
# ---------------------------------------------------------------------------


def _bar(value: float, maximum: float) -> str:
    """Return one fixed-width bar, plus the number it draws."""
    filled = (
        0
        if value <= 0
        else min(SCORE_BAR_WIDTH, round(SCORE_BAR_WIDTH * value / maximum))
    )
    return f"{_FILLED * filled}{_EMPTY * (SCORE_BAR_WIDTH - filled)}  {value:.3f}"


def _generation(baseline_skill: SkillArtifact | None) -> int | None:
    """Return which comparison in the chain this is, or ``None`` when unknown.

    A :class:`~techtree.models.skill.SkillArtifact` names the Skill it revises
    and nothing further back, so the chain a run can see is the chain its own
    two Skills record. That is enough to tell the first two apart, which is the
    distinction that matters: a baseline carrying no Skill is the first
    comparison, and a baseline carrying a Skill that revised nothing is the
    second. A baseline that is itself a revision means the chain runs deeper
    than this run can count, and the honest answer there is that the number is
    not known rather than a number that happens to be two.
    """
    if baseline_skill is None:
        return 1
    if baseline_skill.parent_skill_digest is None:
        return 2
    return None


def _comparison_label(generation: int | None) -> str:
    """Return which result in the chain a reader is looking at.

    Decisions document 0009 names the first two. Anything further along is
    named as what it is — a later iteration — because a receipt that claimed
    an ordinal the run cannot prove would be worse than one that does not
    claim an ordinal at all. Which Skill sat on each side is spelled out under
    "what changed" rather than compressed into this line.
    """
    if generation == 1:
        return FIRST_RESULT_LABEL
    if generation == 2:
        return SECOND_RESULT_LABEL
    return LATER_RESULT_LABEL


def _change_label(
    generation: int | None,
    baseline_skill: SkillArtifact | None,
    candidate_skill: SkillArtifact,
) -> str:
    """Return the one change this comparison measured, as an arrow.

    Decisions document 0019 section 1 fixes the wording of the first two. Once
    the chain runs deeper than the run can number, the two Skills are named by
    their own names instead, which is always true of them.
    """
    if generation == 1:
        return FIRST_CHANGE_LABEL
    if generation == 2:
        return SECOND_CHANGE_LABEL
    assert baseline_skill is not None
    return (
        f"{sanitize_label(baseline_skill.name)} → "
        f"{sanitize_label(candidate_skill.name)}"
    )


def _baseline_label(baseline_skill: SkillArtifact | None) -> str:
    """Return what the baseline side is called.

    Decisions document 0019 section 1: a baseline is a role, not the absence of
    a Skill. A replacement's baseline carries the Skill being revised, and
    naming it "No tested Skill" beside that Skill's own digest would print a
    contradiction.
    """
    if baseline_skill is None:
        return BASELINE_SKILL_LABEL
    return baseline_skill.name


def _skill_summary(skill: SkillArtifact | None, label: str) -> SkillSummary:
    """Summarize one side's Skill by size and content address."""
    if skill is None:
        return SkillSummary(
            label=sanitize_label(label), root_digest=None, file_count=0, total_bytes=0
        )
    return SkillSummary(
        label=sanitize_label(label),
        root_digest=skill.root_digest,
        file_count=len(skill.files),
        total_bytes=sum(file.size for file in skill.files),
    )


def _task_rows(deltas: Sequence[TaskDelta]) -> list[TaskResultRow]:
    """Return one row per committed task, in the report's own order."""
    return [
        TaskResultRow(
            position=position,
            task_label=_task_label(position, delta.task_hash),
            baseline_score=delta.baseline_reward,
            candidate_score=delta.candidate_reward,
            delta=delta.delta,
            outcome=_outcome(delta),
        )
        for position, delta in enumerate(deltas)
    ]


def _task_label(position: int, task_hash: str) -> str:
    """Name one task by its place and the first cell of its hash.

    The taskset's public names are not carried in a receipt, and a hash is not
    hidden material: it is the same identifier the TasksetLock commits to. The
    prefix is enough to tell two rows apart and to find the task in the lock.
    """
    _, _, hexadecimal = task_hash.partition(":")
    return f"task {position + 1:02d} · {hexadecimal[:8]}"


def _outcome(delta: TaskDelta) -> TaskOutcome:
    """Return which way one task moved."""
    if delta.candidate_reward > delta.baseline_reward:
        return "win"
    if delta.candidate_reward < delta.baseline_reward:
        return "loss"
    return "tie"


def _tasks_scored_full(rows: Sequence[TaskResultRow]) -> tuple[int | None, int | None]:
    """Return how many tasks each side got right, when that is a countable thing.

    A person reads "24 of 36", not "0.667". The translation is only honest for
    a reward that is all-or-nothing: a task scored 0.4 was not got right and
    was not got wrong, and counting it either way would invent a number the
    report does not contain. So the count is offered only when every score on
    both sides is exactly zero or exactly the full reward, and the mean stands
    alone otherwise.
    """
    if not rows:
        return None, None
    scores = [(row.baseline_score, row.candidate_score) for row in rows]
    if any(value not in (0.0, _FULL_SCORE) for pair in scores for value in pair):
        return None, None
    return (
        sum(1 for baseline, _ in scores if baseline == _FULL_SCORE),
        sum(1 for _, candidate in scores if candidate == _FULL_SCORE),
    )


@dataclass(frozen=True)
class _Economics:
    """What a payload can honestly say about cost and time, and from where."""

    source: EconomicsSource
    baseline_tokens: int | None
    candidate_tokens: int | None
    baseline_seconds: float | None
    candidate_seconds: float | None
    cost: TotalCost


def _economics(
    record: ComparisonExecutionRecord | None,
    baseline_receipts: Sequence[EpisodeReceipt],
    candidate_receipts: Sequence[EpisodeReceipt],
) -> _Economics:
    """Decide what this payload may say about what the comparison consumed.

    Decisions document 0007 R6 makes the signed execution record the source of
    this, so it is preferred whenever there is one. Without it, the receipts
    are asked for a token total — they carry one only if the evaluation
    recorded tokens as a metric — and time and cost are simply not known. In
    no branch is a number produced that this payload could not name a source
    for.
    """
    if record is not None:
        return _Economics(
            source="comparison_execution_record",
            baseline_tokens=record.baseline.usage.total_tokens,
            candidate_tokens=record.candidate.usage.total_tokens,
            baseline_seconds=record.baseline.elapsed_seconds,
            candidate_seconds=record.candidate.elapsed_seconds,
            cost=record.total_cost,
        )

    baseline_tokens = _tokens(baseline_receipts)
    candidate_tokens = _tokens(candidate_receipts)
    recorded = baseline_tokens is not None or candidate_tokens is not None
    return _Economics(
        source="episode_receipts" if recorded else "unavailable",
        baseline_tokens=baseline_tokens,
        candidate_tokens=candidate_tokens,
        baseline_seconds=None,
        candidate_seconds=None,
        cost=TotalCost(cost_usd=None, provenance=CostProvenance.UNAVAILABLE),
    )


def _derived_cost(
    campaign: CampaignSpec,
    record: ComparisonExecutionRecord | None,
    economics: _Economics,
) -> DerivedCost | None:
    """Work one comparison's cost out from the tokens it recorded, or return none.

    Only ever reached when the provider reported no cost of its own: a figure
    it billed is the better answer wherever there is one. Nothing computed here
    is written anywhere. It is multiplication, done while the result is drawn,
    over token counts the signed execution record already holds and prices this
    release recorded on a named day.

    A model this release recorded no prices for produces nothing rather than a
    guess, and so does a run whose sides did not both report their usage. Both
    are said out loud by the caveat rather than shown as a blank.
    """
    if record is None or economics.cost.provenance is not CostProvenance.UNAVAILABLE:
        return None
    usage = (record.baseline.usage, record.candidate.usage)
    input_tokens = _summed(usage, "input_tokens")
    output_tokens = _summed(usage, "output_tokens")
    if input_tokens is None or output_tokens is None:
        return None
    try:
        prices = price_profile_for(campaign.subject.model.model_id)
    except PrerequisiteError:
        return None

    cached = _summed(usage, "cached_input_tokens")
    return DerivedCost(
        usd=(
            input_tokens * prices.input_usd_per_mtok
            + output_tokens * prices.output_usd_per_mtok
        )
        / _TOKENS_PER_MILLION,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        # A split that claims more cached input than there was input describes
        # no cache this can price around, so it is carried as unknown rather
        # than repaired into something plausible.
        cached_input_tokens=(
            None if cached is None or cached > input_tokens else cached
        ),
        # The recorded profile quotes one rate per direction and says outright
        # that they are the highest uncached ones. Until a profile distinguishes
        # a cached rate, every input token is priced as though the provider
        # cached none of it, which can only make the figure too high.
        prices_name_a_cached_rate=False,
        model_id=sanitize_label(prices.model_id),
        input_usd_per_mtok=prices.input_usd_per_mtok,
        output_usd_per_mtok=prices.output_usd_per_mtok,
        prices_recorded_on=sanitize_label(prices.recorded_on),
    )


def _summed(usage: tuple[VariantUsage, VariantUsage], field: str) -> int | None:
    """Return both sides' count of one thing, or ``None`` when a side has none."""
    total = 0
    for side in usage:
        recorded = getattr(side, field)
        if recorded is None:
            return None
        total += int(recorded)
    return total


def _tokens(receipts: Sequence[EpisodeReceipt]) -> int | None:
    """Return one side's token total when the receipts carry one.

    A receipt records whatever metrics the evaluation recorded. The pinned
    build records token usage on the trace rather than in that table, so this
    is ``None`` for every run this release produces, and the caveat that says
    so is emitted rather than a zero that would read as "used no tokens".
    """
    totals: list[float] = []
    for receipt in receipts:
        for traces in receipt.named_traces.values():
            for trace in traces:
                recorded = trace.metrics.get("total_tokens")
                if recorded is None:
                    return None
                totals.append(recorded)
    return int(sum(totals)) if totals else None


def _verification_status(verification: VerificationResult | None) -> str:
    """Return the three-state answer to "was this proof checked?"."""
    if verification is None:
        return VERIFICATION_NOT_VERIFIED
    return VERIFICATION_VERIFIED if verification.verified else VERIFICATION_FAILED


#: How each cost provenance is spelled for a person, in one phrase that fits
#: beside the number. Owned here rather than by either renderer, so that the
#: terminal and a phone cannot describe one figure two ways.
_COST_PROVENANCE: Final[dict[CostProvenance, str]] = {
    CostProvenance.PROVIDER_REPORTED: "reported by the provider",
    CostProvenance.COMPUTED_FROM_PINNED_PRICE: "computed from the pinned price",
    CostProvenance.ESTIMATED: "estimated, not billed",
    CostProvenance.UNAVAILABLE: "unavailable",
}


def _caveats(
    *,
    report: UpliftReport,
    campaign: CampaignSpec,
    verification: VerificationResult | None,
    economics: _Economics,
    recorded_evidence: RecordedEvidence | None,
    derived: DerivedCost | None,
) -> list[PresentationCaveat]:
    """Return everything a reader has to know to read the numbers correctly.

    The order is the order they matter in: what would make the result invalid
    first, then what bounds how much it proves, then the standing facts about
    this release.
    """
    caveats: list[PresentationCaveat] = []

    if report.proof_grade == "development_only":
        caveats.append(
            PresentationCaveat(
                code="development_only_result",
                severity="error",
                text=(
                    "This report is development-only. Its numbers are not "
                    "evidence and it withholds a verdict."
                ),
            )
        )
    if verification is not None and not verification.verified:
        failures = verification.failures
        remainder = (
            "" if len(failures) == 1 else f" ({len(failures) - 1} more checks failed)"
        )
        caveats.append(
            PresentationCaveat(
                code="proof_verification_failed",
                severity="error",
                text=(
                    "This run's local proof did not verify, so nothing below "
                    f"can be relied on: {failures[0].detail}{remainder}."
                ),
            )
        )
    if verification is None and report.proof_grade == "P1":
        caveats.append(
            PresentationCaveat(
                code="proof_not_verified",
                severity="warning",
                text=(
                    "The local proof was not checked for this rendering. Run "
                    "`techtree proof verify` to check it."
                ),
            )
        )
    if report.statuses.comparison is ComparisonStatus.CONTROLLED_WITH_WARNINGS:
        caveats.append(
            PresentationCaveat(
                code="comparison_controlled_with_warnings",
                severity="warning",
                text=_weak_attestation_text(campaign),
            )
        )
    if report.proof_grade == "P1":
        caveats.append(
            PresentationCaveat(
                code="local_participant_attestation",
                severity="warning",
                text=(
                    f"Proof grade P1 means {P1_MEANING}. Your own local key "
                    "vouches for bytes that verify against each other — not "
                    "for who ran them."
                ),
            )
        )
    caveats.append(
        PresentationCaveat(
            code="no_independent_reproduction",
            severity="warning",
            text=(
                "Nobody has independently reproduced this comparison, and no "
                "platform witnessed it."
            ),
        )
    )
    caveats.append(
        PresentationCaveat(
            code="introductory_task_family",
            severity="warning",
            text=(
                "This is a toy introductory Climb. Its task family is "
                "synthetic and demonstrates the mechanism; it measures no "
                "broad capability."
            ),
        )
    )
    caveats.append(
        PresentationCaveat(
            code="no_server_upload",
            severity="info",
            text=(
                "Nothing was uploaded. The raw episodes stay on this machine, "
                "and publication was never requested. Model inference was "
                "still sent to the model provider this run used, under that "
                "provider's policies."
            ),
        )
    )
    caveats.append(
        PresentationCaveat(
            # Spec section 7.15 calls this "no Relay requirement". The reader
            # is a participant rather than an architect, so the caveat says
            # what it means for them and names no internal component.
            code="no_external_evidence_service",
            severity="info",
            text="No external evidence service is required, used, or contacted.",
        )
    )
    throttling = _throttling_caveat(recorded_evidence)
    if throttling is not None:
        caveats.append(throttling)
    caveats.append(_economics_caveat(economics, derived))
    if report.decision is UpliftDecision.REJECTED:
        caveats.append(
            PresentationCaveat(
                code="rejected_is_evidence",
                severity="info",
                text=(
                    "A rejected candidate is a measurement, not a failed run: "
                    "this Skill did not meet the threshold the Campaign "
                    "declared in advance."
                ),
            )
        )
    return caveats


def _weak_attestation_text(campaign: CampaignSpec) -> str:
    """Say which declared coordinate the run could not confirm, when it can.

    "At least one declared coordinate could not be confirmed" is true and
    useless: a reader cannot weigh a warning whose subject is withheld. The
    subject is not guessed here — the same function the comparison itself used
    to decide whether to raise this warning is asked again, over the run's own
    signed Campaign, and the coordinate is named only when that answer names
    it. A cause this build does not have a plain sentence for keeps the honest
    general wording rather than borrowing the model-revision one.
    """
    recorded = weaker_claim_warnings(campaign)
    coordinates = {check.id for check in recorded}
    if coordinates == {MODEL_REVISION_UNDISCOVERABLE}:
        named = (
            "Your provider publishes no immutable build identifier for "
            f"{sanitize_label(campaign.subject.model.model_id)}, so both sides "
            "provably used the same model name but not provably the same model "
            "build."
        )
    else:
        named = (
            "At least one declared coordinate could not be confirmed from what "
            "the run observed, and this build has no plainer name for it."
        )
    return (
        "The comparison is controlled with warnings, which means one "
        f"coordinate is attested more weakly than the rest. {named} No "
        "mismatch was found; a mismatch would have made the comparison invalid."
    )


def _throttling_caveat(
    recorded_evidence: RecordedEvidence | None,
) -> PresentationCaveat | None:
    """Say how often the provider refused each side, when the run still says.

    Two sides that met different amounts of throttling did not quite meet the
    same conditions, so an asymmetry is part of how much the comparison proves
    and is raised as a warning. An even count is worth stating and is not a
    qualification of anything, so it is a note. A run whose recorded traces
    can no longer be read says nothing here at all.
    """
    if recorded_evidence is None:
        return None
    baseline = recorded_evidence.baseline.rate_limited_calls
    candidate = recorded_evidence.candidate.rate_limited_calls
    if baseline == candidate == 0:
        text = "The provider refused no model call on either side."
    else:
        text = (
            f"The provider refused {_calls(baseline)} with a rate limit on the "
            f"baseline side and {candidate:,} on the candidate side."
        )
    if recorded_evidence.every_rollout_completed:
        text = f"{text} Every rollout still ran to completion."
    return PresentationCaveat(
        code="provider_rate_limiting",
        severity="warning" if baseline != candidate else "info",
        text=text,
    )


#: What each cost provenance means to a reader, in the words decisions
#: document 0007 R6 requires: a computed or estimated figure is never allowed
#: to read as one the provider billed.
_COST_CAVEATS: Final[
    dict[CostProvenance, tuple[str, Literal["info", "warning", "error"], str]]
] = {
    CostProvenance.PROVIDER_REPORTED: (
        "cost_provider_reported",
        "info",
        "The cost shown is the figure the provider reported for this "
        "comparison, taken from its signed execution record.",
    ),
    CostProvenance.COMPUTED_FROM_PINNED_PRICE: (
        "cost_computed_from_pinned_price",
        "info",
        "The cost shown was computed from the recorded token usage and the "
        "price this release pins. The provider did not report it.",
    ),
    CostProvenance.ESTIMATED: (
        "cost_estimated",
        "warning",
        "The cost shown is an estimate. It is not a figure the provider "
        "reported and it is not what you were charged.",
    ),
}


def _cost_unavailable_reason(
    campaign: CampaignSpec,
    record: ComparisonExecutionRecord | None,
    economics: _Economics,
) -> str:
    """Say which of the two things a cost needs this run is missing.

    "Unavailable" on its own leaves a reader who has just spent money unable
    to tell whether the run lost the tokens or the release lost the prices, so
    the sentence names whichever one is actually absent.
    """
    if record is None:
        return (
            "This run wrote no signed execution record, so there is no signed "
            "token total to work a cost out from."
        )
    model_id = campaign.subject.model.model_id
    try:
        price_profile_for(model_id)
    except PrerequisiteError:
        return (
            "This release recorded no provider prices for "
            f"{sanitize_label(model_id)}, so the tokens this run recorded "
            "cannot be turned into a cost."
        )
    if economics.cost.provenance is not CostProvenance.UNAVAILABLE:
        return _COST_PROVENANCE[economics.cost.provenance]
    return (
        "Neither side of this comparison reported how many tokens it used, "
        "and the provider reported no cost of its own."
    )


def _economics_caveat(
    economics: _Economics, derived: DerivedCost | None
) -> PresentationCaveat:
    """Say where the cost and timing came from, or that they are unknown.

    Decisions document 0007 R6: missing economics is an operational-evidence
    warning about what is unknown, and never a finding about the measurement.
    Both sentences below end by saying so, because the reader most likely to
    meet this caveat is the one who needs to be told that their result still
    stands.
    """
    if economics.source == "comparison_execution_record":
        named = _COST_CAVEATS.get(economics.cost.provenance)
        if named is not None:
            code, severity, text = named
            return PresentationCaveat(code=code, severity=severity, text=text)
        if derived is not None:
            return PresentationCaveat(
                code="cost_derived_while_rendering",
                severity="info",
                text=(
                    "Timing and token counts come from this run's signed "
                    "execution record. The provider reported no figure for what "
                    "it charged, so the one shown was worked out from those "
                    "token counts and the prices this release recorded. It was "
                    "not written into anything this run signed, and what the "
                    "comparison measured is unaffected."
                ),
            )
        return PresentationCaveat(
            code="cost_unavailable",
            severity="warning",
            text=(
                "Timing and token counts come from this run's signed execution "
                "record. No cost was reported for it and none could be worked "
                "out from what it recorded. What the comparison measured is "
                "unaffected."
            ),
        )
    if economics.source == "episode_receipts":
        return PresentationCaveat(
            code="operational_evidence_unavailable",
            severity="warning",
            text=(
                "This run has no signed execution record, so its timing and "
                "cost are unavailable; the token count shown comes from the "
                "receipts. What the comparison measured is unaffected."
            ),
        )
    return PresentationCaveat(
        code="operational_evidence_unavailable",
        severity="warning",
        text=(
            "This run has no signed execution record, so how long it took, "
            "how many tokens it used and what it cost are all unavailable. "
            "What the comparison measured is unaffected."
        ),
    )


def _next_actions(run_id: str, proof_grade: str) -> list[NextAction]:
    """Return the steps this build can actually carry out for this report.

    A development-only report is offered only the first of them. It has no
    proof bundle and never claimed one, and nothing may be derived from
    invented numbers, so the three commands that would refuse it are not
    suggested: an action a caller cannot carry out is worse than one fewer
    suggestion.
    """
    actions = [
        NextAction(
            id="inspect_tasks",
            label="Look at every task, including the ones that regressed",
            reason="The per-task table is where a Skill's effect is legible.",
            cli=["techtree", "run", "result", run_id, "--show-tasks", "all"],
            hermes_tool=None,
            hermes_args=None,
            requires_user_confirmation=False,
        )
    ]
    if proof_grade == "development_only":
        return actions

    # Ordered by usefulness, because the CLI envelope carries at most three and
    # truncates from the end. Checking that the result is real comes before
    # acting on it, and the context has to exist before a revision can be
    # compared against anything.
    actions.append(
        NextAction(
            id="verify_proof",
            label="Verify this run's local proof",
            reason="It checks offline, from the bytes the run stored.",
            cli=["techtree", "proof", "verify", run_id],
            hermes_tool=None,
            hermes_args=None,
            requires_user_confirmation=False,
        )
    )
    actions.append(
        NextAction(
            id="improvement_context",
            label="Export what a host agent needs to propose one Skill revision",
            reason=(
                "It carries the regressions, the failures and the objective, "
                "and no hidden task material."
            ),
            cli=["techtree", "uplift", "context", run_id],
            hermes_tool=None,
            hermes_args=None,
            requires_user_confirmation=False,
        )
    )
    actions.append(
        NextAction(
            id="prepare_replacement",
            label="Prepare a comparison of this Skill against a revision of it",
            reason=(
                "The baseline is pinned to the Skill this run measured, so the "
                "second comparison starts where this one ended."
            ),
            cli=[
                "techtree",
                "uplift",
                "prepare",
                "--from-run",
                run_id,
                "--candidate-skill",
                "PATH",
            ],
            hermes_tool=None,
            hermes_args=None,
            requires_user_confirmation=True,
        )
    )
    return actions
