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
"""

from __future__ import annotations

from typing import Final, Literal, Self

from pydantic import Field, model_validator

from techtree.models.base import Digest, NonEmptyString, ProtocolModel
from techtree.models.cli import NextAction
from techtree.receipts.execution import CostProvenance

__all__ = [
    "PRESENTATION_SCHEMA_VERSION",
    "EconomicsSource",
    "PresentationCaveat",
    "ScoreBar",
    "SkillSummary",
    "TaskOutcome",
    "TaskResultRow",
    "UpliftPresentationPayload",
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


class PresentationCaveat(ProtocolModel):
    """One thing a reader must know before believing what they just read.

    Caveats are part of the payload rather than of a renderer, so that a
    channel cannot drop one by being short of room.
    """

    code: NonEmptyString
    severity: Literal["info", "warning", "error"]
    text: NonEmptyString


class UpliftPresentationPayload(ProtocolModel):
    """One comparison, ready to be shown anywhere."""

    schema_version: Literal["techtree.presentation.uplift.v1"]
    run_id: NonEmptyString
    campaign_title: NonEmptyString
    comparison_label: NonEmptyString
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
    baseline_tokens: int | None
    candidate_tokens: int | None
    baseline_seconds: float | None
    candidate_seconds: float | None
    economics_source: EconomicsSource
    cost_usd: float | None = Field(default=None, ge=0.0)
    cost_provenance: CostProvenance
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
