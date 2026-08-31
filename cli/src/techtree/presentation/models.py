"""The channel-neutral shape of a result. Spec section 7.13.

Both renderers in this build — the terminal one and the compact one a gateway
relays — consume exactly this payload, and nothing else draws a result. The
payload is a contract about *what a result is*, never an assumption about how
anyone draws it: numbers, labels, outcomes, caveats and next steps, with no
markup, no colour and no channel anywhere in it.

Three properties are load-bearing.

*It is derived, never authored.* Every score, status and digest here is copied
out of a signed :class:`~techtree.models.uplift_report.UpliftReport`. Nothing
downstream can alter one, because nothing downstream is given the chance to
compute one.

*It is frozen.* The models are :class:`~techtree.models.base.ProtocolModel`
subclasses even though the payload is not part of the frozen v0.1 protocol,
which is why the schema version says ``presentation`` rather than a protocol
object's name. Freezing means two renderings of one report cannot disagree
because something mutated the payload between them.

*It carries nothing hidden.* A hidden expected answer, a grader's source, or a
credential has no field to enter through, and
:func:`~techtree.presentation.sanitize.ensure_no_hidden_task_material` checks
the free text that could carry one anyway.

One thing that is not a field lives here too: :class:`TaskDisplay`, the
reader's answer to how much of the per-task table they want, and
:func:`selected_task_rows`, which turns that answer into rows. It is here
rather than in either renderer because a reader who asks the same question of
two channels has to be shown the same tasks, and two renderers that each kept
their own idea of which rows "changed" means could quietly disagree about
whether a tie is a change.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Literal, Self

from pydantic import Field, model_validator

from techtree.models.base import Digest, NonEmptyString, ProtocolModel
from techtree.models.cli import NextAction
from techtree.receipts.execution import CostProvenance

__all__ = [
    "PRESENTATION_SCHEMA_VERSION",
    "DerivedCost",
    "EconomicsSource",
    "PresentationCaveat",
    "ScoreBar",
    "SkillSummary",
    "TaskDisplay",
    "TaskOutcome",
    "TaskResultRow",
    "UpliftPresentationPayload",
    "selected_task_rows",
]

#: Deliberately not in :mod:`techtree.constants`, which holds protocol schema
#: versions. A presentation payload is a view, and spec section 3.5 keeps views
#: out of the protocol.
PRESENTATION_SCHEMA_VERSION: Final = "techtree.presentation.uplift.v1"


type TaskOutcome = Literal["win", "loss", "tie"]
"""Which way one task moved between the two variants."""


type EconomicsSource = Literal[
    "comparison_execution_record",
    "episode_receipts",
    "unavailable",
]
"""Where the cost and timing on a payload came from, if anywhere.

Decisions document 0007 R6 puts the comparison's economics in a signed record
of its own. A payload built from a run that has one says so; one built from a
run that does not says that instead, and never quietly presents a number whose
source it cannot name."""


class ScoreBar(ProtocolModel):
    """One score, and the text a renderer draws it as.

    ``display`` is computed once, in the builder, so that the terminal and a
    phone message draw the same bar from the same string rather than each
    inventing a scale.
    """

    label: NonEmptyString
    value: float
    maximum: float = Field(gt=0.0)
    display: NonEmptyString


class TaskResultRow(ProtocolModel):
    """What one committed task contributed to the comparison."""

    position: int = Field(ge=0)
    task_label: NonEmptyString
    baseline_score: float
    candidate_score: float
    delta: float
    outcome: TaskOutcome


class TaskDisplay(StrEnum):
    """Which task rows a reader asked to see."""

    ALL = "all"
    CHANGED = "changed"
    REGRESSIONS = "regressions"
    NONE = "none"


#: Losses first, then wins, then ties. Within a group, committed task order.
_OUTCOME_RANK: Final[dict[str, int]] = {"loss": 0, "win": 1, "tie": 2}


def selected_task_rows(
    rows: list[TaskResultRow], show: TaskDisplay
) -> list[TaskResultRow]:
    """Return the rows a reader asked for, worst first.

    A reader scanning a table wants the rows that moved the wrong way, then the
    ones that moved, then the rest, so the order is fixed here rather than left
    to whichever channel is drawing. ``TaskDisplay.NONE`` selects nothing at
    all, which is the honest reading of a reader who said they did not want the
    table: a channel given no rows prints no table and no heading over it.

    Selecting rows is all this does. No filter can change a count, because
    every count a reader sees comes from the payload rather than from what a
    channel happened to have room for.
    """
    if show is TaskDisplay.NONE:
        return []
    if show is TaskDisplay.REGRESSIONS:
        chosen = [row for row in rows if row.outcome == "loss"]
    elif show is TaskDisplay.CHANGED:
        chosen = [row for row in rows if row.outcome != "tie"]
    else:
        chosen = list(rows)
    return sorted(chosen, key=lambda row: (_OUTCOME_RANK[row.outcome], row.position))


class SkillSummary(ProtocolModel):
    """One side's Skill, described by size and content address.

    A baseline with no Skill is a real state rather than a missing value: it is
    what a Skill-insertion comparison measures against, so it has a label and
    no digest.
    """

    label: NonEmptyString
    root_digest: Digest | None
    file_count: int = Field(ge=0)
    total_bytes: int = Field(ge=0)


class DerivedCost(ProtocolModel):
    """A dollar figure worked out while rendering, from what the run recorded.

    Decisions document 0007 R6 forbids exactly one thing about cost: a figure
    presented as better sourced than it is. This is not a bill and is never
    drawn as one, so everything it rests on travels with it — the two token
    counts that were multiplied, the prices they were multiplied by, and the
    day those prices were read.

    ``cached_input_tokens`` and ``prices_name_a_cached_rate`` are carried
    together because a provider that serves part of the prompt from its own
    cache usually charges less for it. When the recorded prices name no cached
    rate, every token is priced at the full rate and the reader is told the
    figure is on the high side, which is the only direction an unstated
    discount can move it. The count is ``None`` when the run recorded no
    usable cache split, which is not the same as a run that cached nothing.
    """

    usd: float = Field(ge=0.0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    prices_name_a_cached_rate: bool
    model_id: NonEmptyString
    input_usd_per_mtok: float = Field(gt=0.0)
    output_usd_per_mtok: float = Field(gt=0.0)
    prices_recorded_on: NonEmptyString


class PresentationCaveat(ProtocolModel):
    """One thing a reader must know before believing what they just read.

    Caveats are part of the payload rather than of a renderer, so that a
    channel cannot drop one by being short of room.
    """

    code: NonEmptyString
    severity: Literal["info", "warning", "error"]
    text: NonEmptyString


class UpliftPresentationPayload(ProtocolModel):
    """One comparison, ready to be shown anywhere.

    ``comparison_label`` names which result in the chain this is;
    ``change_label`` names the one thing that differed between the two sides,
    in the arrow form decisions document 0019 section 1 fixes. They are two
    fields because they answer two questions — which receipt am I holding, and
    what did it measure — and a channel with room for only one should not have
    to guess which.
    """

    schema_version: Literal["techtree.presentation.uplift.v1"]
    run_id: NonEmptyString
    campaign_title: NonEmptyString
    comparison_label: NonEmptyString
    change_label: NonEmptyString
    baseline_skill: SkillSummary
    candidate_skill: SkillSummary
    baseline_score: float
    candidate_score: float
    absolute_delta: float
    relative_delta: float | None
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    ties: int = Field(ge=0)
    task_rows: list[TaskResultRow]
    baseline_tasks_scored_full: int | None
    candidate_tasks_scored_full: int | None
    baseline_tokens: int | None
    candidate_tokens: int | None
    baseline_seconds: float | None
    candidate_seconds: float | None
    baseline_model_turns: int | None
    candidate_model_turns: int | None
    baseline_rate_limited_calls: int | None
    candidate_rate_limited_calls: int | None
    every_rollout_completed: bool | None
    economics_source: EconomicsSource
    cost_usd: float | None = Field(default=None, ge=0.0)
    cost_provenance: CostProvenance
    derived_cost: DerivedCost | None = None
    cost_unavailable_reason: NonEmptyString | None = None
    decision: NonEmptyString
    proof_grade: NonEmptyString
    verification_status: NonEmptyString
    caveats: list[PresentationCaveat]
    next_actions: list[NextAction]

    @model_validator(mode="after")
    def _check_the_rows_and_the_counts_describe_one_comparison(self) -> Self:
        """Reject a payload whose table and headline disagree."""
        outcomes = [row.outcome for row in self.task_rows]
        counts: tuple[tuple[TaskOutcome, int], ...] = (
            ("win", self.wins),
            ("loss", self.losses),
            ("tie", self.ties),
        )
        for outcome, count in counts:
            if outcomes.count(outcome) != count:
                raise ValueError(
                    f"the payload reports {count} {outcome} rows and carries "
                    f"{outcomes.count(outcome)}"
                )
        positions = [row.position for row in self.task_rows]
        if positions != sorted(positions) or len(set(positions)) != len(positions):
            raise ValueError(
                "task rows are carried in committed task order, each position once"
            )
        return self

    @model_validator(mode="after")
    def _check_the_cost_is_never_shown_without_its_source(self) -> Self:
        """Reject a payload whose cost claims a provenance it does not have.

        Decisions document 0007 R6 forbids exactly one thing about cost: a
        figure presented as better sourced than it is. The shape enforces the
        pair here so that no renderer has to remember to.
        """
        known = self.cost_usd is not None
        claims_source = self.cost_provenance is not CostProvenance.UNAVAILABLE
        if known != claims_source:
            raise ValueError(
                "a cost figure needs a provenance and a provenance needs a "
                f"figure; got {self.cost_usd!r} as {self.cost_provenance.value}"
            )
        if known and self.economics_source != "comparison_execution_record":
            raise ValueError(
                "a cost figure comes from the signed execution record; a "
                f"payload sourced from {self.economics_source} has none"
            )
        return self

    @model_validator(mode="after")
    def _check_a_derived_cost_never_stands_beside_a_reported_one(self) -> Self:
        """Reject a payload carrying two answers to "what did this cost?".

        A figure the provider reported is the better answer wherever there is
        one, so a derived figure exists only in its absence. Two of them in one
        payload would leave each channel free to pick, and two channels showing
        one run would then be able to disagree about money.
        """
        if self.derived_cost is not None and self.cost_usd is not None:
            raise ValueError(
                "a cost is derived only when none was reported; this payload "
                f"carries both {self.derived_cost.usd} and {self.cost_usd}"
            )
        figure = self.derived_cost is not None or self.cost_usd is not None
        if figure == (self.cost_unavailable_reason is not None):
            raise ValueError(
                "a payload with no cost figure says what is missing, and one "
                "with a figure has nothing to explain away"
            )
        return self

    @model_validator(mode="after")
    def _check_the_counts_read_from_the_run_arrive_together(self) -> Self:
        """Reject a payload that read half of one run's recorded traces.

        Turns, throttling and whether every rollout finished are one reading of
        one pair of recorded, digest-checked files. A payload holding some of
        them and not the others would be describing a reading that never
        happened.
        """
        read = (
            self.baseline_model_turns,
            self.candidate_model_turns,
            self.baseline_rate_limited_calls,
            self.candidate_rate_limited_calls,
            self.every_rollout_completed,
        )
        if None in read and any(value is not None for value in read):
            raise ValueError(
                "the counts read from a run's recorded traces are all present "
                f"or all absent; got {read}"
            )
        return self

    @model_validator(mode="after")
    def _check_the_task_counts_fit_the_table(self) -> Self:
        """Reject a headline count that no per-task table could produce."""
        baseline = self.baseline_tasks_scored_full
        candidate = self.candidate_tasks_scored_full
        if baseline is None or candidate is None:
            if baseline is not candidate:
                raise ValueError(
                    "both sides carry a task count or neither does; got "
                    f"{(baseline, candidate)}"
                )
            return self
        for count in (baseline, candidate):
            if not 0 <= count <= len(self.task_rows):
                raise ValueError(
                    f"a side scored between 0 and {len(self.task_rows)} of the "
                    f"comparison's tasks; got {count}"
                )
        return self
