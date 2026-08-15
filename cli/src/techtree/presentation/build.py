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

from techtree.identity.models import VerificationResult
from techtree.models.cli import NextAction
from techtree.models.episode_receipt import EpisodeReceipt
from techtree.models.skill import SkillArtifact
from techtree.models.uplift_report import (
    ComparisonStatus,
    TaskDelta,
    UpliftDecision,
    UpliftReport,
)
from techtree.presentation.models import (
    PRESENTATION_SCHEMA_VERSION,
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
from techtree.receipts.execution import (
    ComparisonExecutionRecord,
    CostProvenance,
    TotalCost,
)

__all__ = [
    "BASELINE_SKILL_LABEL",
    "FIRST_CHANGE_LABEL",
    "FIRST_RESULT_LABEL",
    "HELD_FIXED_LINE",
    "LATER_RESULT_LABEL",
    "P1_MEANING",
    "SCORE_BAR_WIDTH",
    "SECOND_CHANGE_LABEL",
    "SECOND_RESULT_LABEL",
    "VERIFICATION_FAILED",
    "VERIFICATION_NOT_VERIFIED",
    "VERIFICATION_VERIFIED",
    "build_uplift_presentation",
    "score_bars",
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

#: How wide a score bar is drawn, in cells. Fixed so two bars are comparable
#: and so a rendering is the same width on every terminal.
SCORE_BAR_WIDTH: Final = 24

VERIFICATION_VERIFIED: Final = "verified_offline"
VERIFICATION_FAILED: Final = "verification_failed"
VERIFICATION_NOT_VERIFIED: Final = "not_verified"

_FILLED: Final = "█"
_EMPTY: Final = "·"


def build_uplift_presentation(
    *,
    report: UpliftReport,
    baseline_receipts: Sequence[EpisodeReceipt],
    candidate_receipts: Sequence[EpisodeReceipt],
    campaign_title: str,
    baseline_skill: SkillArtifact | None,
    candidate_skill: SkillArtifact,
    verification: VerificationResult | None,
    execution_record: ComparisonExecutionRecord | None = None,
) -> UpliftPresentationPayload:
    """Build a channel-neutral presentation payload from a signed report.

    ``verification`` is the result of checking the run's proof bundle offline,
    or ``None`` when the reader asked not to check it. The three states are
    kept apart in ``verification_status`` because "not checked" and "checked
    and failed" are different things to tell somebody, and a development-only
    report has no proof to check at all.

    ``execution_record`` is decisions document 0007 R6's signed operational
    record, when the run carries one. It is the only source of a cost figure
    and the preferred source of tokens and timing; a payload built without one
    says so in ``economics_source`` and carries the operational-evidence
    caveat rather than a number nobody signed.
    """
    economics = _economics(execution_record, baseline_receipts, candidate_receipts)
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
        task_rows=_task_rows(report.task_deltas),
        baseline_tokens=economics.baseline_tokens,
        candidate_tokens=economics.candidate_tokens,
        baseline_seconds=economics.baseline_seconds,
        candidate_seconds=economics.candidate_seconds,
        economics_source=economics.source,
        cost_usd=economics.cost.cost_usd,
        cost_provenance=economics.cost.provenance,
        decision=report.decision.value,
        proof_grade=report.proof_grade,
        verification_status=_verification_status(verification),
        caveats=_caveats(report, verification, economics),
        next_actions=_next_actions(report.run_id, report.proof_grade),
    )
    ensure_no_hidden_task_material(payload)
    return payload


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


def _caveats(
    report: UpliftReport,
    verification: VerificationResult | None,
    economics: _Economics,
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
                text=(
                    "The comparison is controlled with warnings: at least one "
                    "declared coordinate could not be confirmed from what the "
                    "run observed, so it is attested more weakly than the rest. "
                    "No mismatch was found; a mismatch would have made the "
                    "comparison invalid."
                ),
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
    caveats.append(_economics_caveat(economics))
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


def _economics_caveat(economics: _Economics) -> PresentationCaveat:
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
        return PresentationCaveat(
            code="cost_unavailable",
            severity="warning",
            text=(
                "Timing and token counts come from this run's signed execution "
                "record. No cost was reported for it and this build pins no "
                "price to compute one from, so the cost is unavailable. What "
                "the comparison measured is unaffected."
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
