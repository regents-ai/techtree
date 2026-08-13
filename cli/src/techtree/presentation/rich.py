"""The terminal rendering. Spec section 7.15.

This is the CLI's own renderer. WP9's Hermes operator may hand the same neutral
payload to the founder-supplied ``rich-terminal-output`` Skill instead; both
draw the same result because both are given the same object, and neither can
change a number by drawing it.

Four rules, and each one is about a reader rather than about a terminal.

*Meaning is never carried by colour alone.* Every outcome is spelled ``WIN``,
``LOSS`` or ``TIE``, every caveat is introduced by its severity in words, and a
terminal with no colour at all loses nothing but decoration. ``NO_COLOR`` and
``--no-color`` are honoured by the console the CLI builds, and Rich emits no
escape sequences at all when stdout is not a terminal.

*The rendering is deterministic.* No spinner, no progress animation, no clock,
no dictionary iteration order: the same payload renders to the same bytes,
which is what makes it testable at all.

*The order is the order of trust.* What was compared, then the result, then the
tasks, then what changed, then the caveats — so a reader who stops early stops
having read the honest version. The caveats are never last-resort small print
they can miss; a development-only or failed-verification result says so in the
badge at the top as well.

*Regressions come first.* A reader scanning a table wants the rows that moved
the wrong way, then the ones that moved, then the rest.

The payload's next actions are deliberately not drawn here. Every Techtree
command ends with the same numbered next-steps block, rendered by the CLI from
the envelope it returns, and a result that grew a second one of its own would
be the only command in the product that answers that question twice.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from rich.console import Console
from rich.table import Table

from techtree.presentation.build import (
    VERIFICATION_FAILED,
    VERIFICATION_NOT_VERIFIED,
    VERIFICATION_VERIFIED,
    score_bars,
)
from techtree.presentation.models import TaskResultRow, UpliftPresentationPayload

__all__ = ["TaskDisplay", "outcome_label", "render_uplift_console", "verdict_line"]


class TaskDisplay(StrEnum):
    """Which task rows a reader asked to see."""

    ALL = "all"
    CHANGED = "changed"
    REGRESSIONS = "regressions"
    NONE = "none"


_SEVERITY_PREFIX: Final[dict[str, str]] = {
    "info": "Note:",
    "warning": "Warning:",
    "error": "Error:",
}

_SEVERITY_STYLE: Final[dict[str, str]] = {
    "info": "",
    "warning": "yellow",
    "error": "red",
}

_OUTCOME_LABEL: Final[dict[str, str]] = {
    "win": "WIN",
    "loss": "LOSS",
    "tie": "TIE",
}

#: Losses first, then wins, then ties. Within a group, committed task order.
_OUTCOME_RANK: Final[dict[str, int]] = {"loss": 0, "win": 1, "tie": 2}

_VERIFICATION_BADGE: Final[dict[str, str]] = {
    VERIFICATION_VERIFIED: "local proof verified offline",
    VERIFICATION_FAILED: "LOCAL PROOF DID NOT VERIFY",
    VERIFICATION_NOT_VERIFIED: "local proof not checked",
}

_DECISION_SENTENCE: Final[dict[str, str]] = {
    "accepted": "Accepted: the candidate met the threshold this Campaign declared.",
    "rejected": (
        "Rejected: the candidate did not meet the threshold this Campaign "
        "declared. That is evidence about the Skill, not a failed run."
    ),
    "inconclusive": (
        "Inconclusive: this Campaign declared no rule that can decide this comparison."
    ),
    "invalid": "Invalid: this comparison cannot carry a result.",
    "development_only": (
        "No verdict: this report is development-only and states no verdict."
    ),
}


def outcome_label(outcome: str) -> str:
    """Return the word a reader sees for one task's outcome."""
    return _OUTCOME_LABEL[outcome]


def verdict_line(payload: UpliftPresentationPayload) -> str:
    """Return the one sentence that says what the comparison decided."""
    return _DECISION_SENTENCE[payload.decision]


def render_uplift_console(
    payload: UpliftPresentationPayload,
    console: Console,
    *,
    show_tasks: TaskDisplay = TaskDisplay.CHANGED,
) -> None:
    """Render an accessible, side-by-side terminal result.

    ``show_tasks`` is the reader's choice of how much of the per-task table to
    print (spec section 7.21). It selects rows and nothing else: no filter here
    can change a count, because the counts come from the payload.
    """
    _header(payload, console)
    _primary(payload, console)
    _tasks(payload, console, show_tasks)
    _efficiency(payload, console)
    _what_changed(payload, console)
    _caveats(payload, console)


def _header(payload: UpliftPresentationPayload, console: Console) -> None:
    """Campaign, comparison, and the badge that says how much this is worth."""
    console.print(payload.campaign_title)
    console.print(payload.comparison_label)
    console.print(
        f"[{payload.proof_grade} · {_VERIFICATION_BADGE[payload.verification_status]}]"
    )
    console.print()


def _primary(payload: UpliftPresentationPayload, console: Console) -> None:
    """The two bars, the delta, and the verdict."""
    table = Table(box=None, show_header=False, pad_edge=False, padding=(0, 2))
    table.add_column("side", no_wrap=True)
    table.add_column("bar", no_wrap=True)
    for bar in score_bars(payload):
        table.add_row(bar.label, bar.display)
    console.print(table)
    console.print()

    console.print(f"Change  {payload.absolute_delta:+.3f}  ({_relative(payload)})")
    console.print(
        f"Tasks   {payload.wins} WIN / {payload.losses} LOSS / {payload.ties} TIE"
    )
    console.print()
    console.print(verdict_line(payload))
    console.print()


def _relative(payload: UpliftPresentationPayload) -> str:
    """Say what a relative change is, or why there is not one."""
    if payload.relative_delta is None:
        return "no relative change: the baseline scored nothing"
    return f"{payload.relative_delta:+.1%} relative"


def _tasks(
    payload: UpliftPresentationPayload, console: Console, show: TaskDisplay
) -> None:
    """The per-task table, regressions first."""
    if show is TaskDisplay.NONE:
        return
    rows = _selected(payload.task_rows, show)
    if not rows:
        console.print("Every task scored the same on both sides.")
        console.print()
        return

    table = Table(box=None, pad_edge=False, padding=(0, 2))
    table.add_column("Task", no_wrap=True)
    table.add_column("Baseline", justify="right", no_wrap=True)
    table.add_column("Candidate", justify="right", no_wrap=True)
    table.add_column("Change", justify="right", no_wrap=True)
    table.add_column("Outcome", no_wrap=True)
    for row in rows:
        table.add_row(
            row.task_label,
            f"{row.baseline_score:.3f}",
            f"{row.candidate_score:.3f}",
            f"{row.delta:+.3f}",
            outcome_label(row.outcome),
        )
    console.print(table)
    if len(rows) != len(payload.task_rows):
        console.print(
            f"Showing {len(rows)} of {len(payload.task_rows)} tasks. "
            "Use --show-tasks all for the rest."
        )
    console.print()


def _selected(rows: list[TaskResultRow], show: TaskDisplay) -> list[TaskResultRow]:
    """Return the rows a reader asked for, worst first."""
    if show is TaskDisplay.REGRESSIONS:
        chosen = [row for row in rows if row.outcome == "loss"]
    elif show is TaskDisplay.CHANGED:
        chosen = [row for row in rows if row.outcome != "tie"]
    else:
        chosen = list(rows)
    return sorted(chosen, key=lambda row: (_OUTCOME_RANK[row.outcome], row.position))


def _efficiency(payload: UpliftPresentationPayload, console: Console) -> None:
    """Tokens and time, when the receipts carry them."""
    console.print("Efficiency")
    if payload.baseline_tokens is None and payload.candidate_tokens is None:
        console.print("  Tokens   not recorded in the receipts for this run")
    else:
        console.print(
            f"  Tokens   baseline {payload.baseline_tokens}, "
            f"candidate {payload.candidate_tokens}"
        )
    if payload.baseline_seconds is None and payload.candidate_seconds is None:
        console.print("  Time     not recorded in the receipts for this run")
    else:
        console.print(
            f"  Time     baseline {payload.baseline_seconds}s, "
            f"candidate {payload.candidate_seconds}s"
        )
    console.print()


def _what_changed(payload: UpliftPresentationPayload, console: Console) -> None:
    """The one declared difference, and the statement that it is the only one."""
    console.print("What changed")
    for side, skill in (
        ("Baseline ", payload.baseline_skill),
        ("Candidate", payload.candidate_skill),
    ):
        digest = "none" if skill.root_digest is None else skill.root_digest
        console.print(f"  {side}  {skill.label}")
        console.print(f"             {digest}")
    console.print(
        "  Every other declared field — model, sampling, harness, runtime "
        "image, taskset — was held fixed and checked against what the run "
        "actually did."
    )
    console.print()


def _caveats(payload: UpliftPresentationPayload, console: Console) -> None:
    """Every caveat, in payload order, introduced by severity in words."""
    if not payload.caveats:
        return
    console.print("What this does and does not prove")
    for caveat in payload.caveats:
        console.print(
            f"  {_SEVERITY_PREFIX[caveat.severity]} {caveat.text}",
            style=_SEVERITY_STYLE[caveat.severity] or None,
        )
