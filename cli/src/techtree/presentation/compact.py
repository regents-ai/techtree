"""The rendering a phone can carry. Spec section 7.16.

A gateway message is not a small terminal. It has no escape sequences, no
column alignment, a reader holding a phone, and a channel that may truncate
anything long. So this renderer is bounded by construction: a headline, the
counts, the honest qualifications, at most a few task rows, and one sentence
about what could happen next.

Two things are *not* dropped to make it fit.

*Every warning and error survives.* Room is made by cutting the table, never by
cutting a caveat. A result that only says what went well on a phone and keeps
its qualifications for the desktop would be dishonest in exactly the channel
where somebody is most likely to forward it to someone else.

*The proof grade travels with the numbers.* A one-line quote of an uplift with
no grade beside it is the shape misinformation takes, so the grade and whether
its proof verified are part of the same block as the scores.

Nothing here emits ANSI, and nothing here formats a number differently from the
terminal renderer: both read the same payload fields.
"""

from __future__ import annotations

from typing import Final

from techtree.presentation.build import (
    VERIFICATION_FAILED,
    VERIFICATION_NOT_VERIFIED,
    VERIFICATION_VERIFIED,
)
from techtree.presentation.models import TaskResultRow, UpliftPresentationPayload

__all__ = [
    "DEFAULT_MAXIMUM_TASK_ROWS",
    "UNVERIFIED_HEADLINE",
    "render_uplift_markdown",
]

#: Enough rows to show a pattern, few enough to read on a phone.
DEFAULT_MAXIMUM_TASK_ROWS: Final = 5

#: What a result whose proof failed says before it says anything else.
UNVERIFIED_HEADLINE: Final = (
    "**This run's local proof did not verify. Do not rely on the numbers below.**"
)

_VERIFICATION_PHRASE: Final[dict[str, str]] = {
    VERIFICATION_VERIFIED: "signature verified offline",
    VERIFICATION_FAILED: "signature DID NOT verify",
    VERIFICATION_NOT_VERIFIED: "signature not checked",
}

_HEADLINE: Final[dict[str, str]] = {
    "accepted": "The Skill met the Campaign's threshold",
    "rejected": "The Skill did not meet the Campaign's threshold",
    "inconclusive": "This comparison could not be decided",
    "invalid": "This comparison is not valid",
    "development_only": "Development-only result, no verdict",
}


def render_uplift_markdown(
    payload: UpliftPresentationPayload,
    *,
    maximum_task_rows: int = DEFAULT_MAXIMUM_TASK_ROWS,
) -> str:
    """Return compact Markdown suitable for a phone or gateway message.

    A result whose proof did not verify says that first and in bold. This is
    the channel a number is most likely to be quoted out of, so the sentence
    that would stop somebody quoting it cannot be further down.
    """
    lines = [
        f"**{_HEADLINE[payload.decision]}: "
        f"{payload.baseline_score:.3f} → {payload.candidate_score:.3f} "
        f"({payload.absolute_delta:+.3f})**",
        "",
    ]
    if payload.verification_status == VERIFICATION_FAILED:
        lines = [UNVERIFIED_HEADLINE, "", *lines]
    lines += [
        f"- {payload.campaign_title} — {payload.comparison_label}",
        f"- Wins: {payload.wins}",
        f"- Losses: {payload.losses}",
        f"- Ties: {payload.ties}",
        f"- Proof: local {payload.proof_grade}, "
        f"{_VERIFICATION_PHRASE[payload.verification_status]}",
        "- Raw episodes: retained locally; not uploaded",
    ]

    rows = _worst_first(payload)[:maximum_task_rows]
    if rows:
        lines.append("")
        lines.append(
            f"Largest changes ({len(rows)} of {len(payload.task_rows)} tasks):"
        )
        lines.extend(
            f"- {row.task_label}: {row.baseline_score:.2f} → "
            f"{row.candidate_score:.2f} ({row.outcome.upper()})"
            for row in rows
        )

    qualifications = [caveat for caveat in payload.caveats if caveat.severity != "info"]
    if qualifications:
        lines.append("")
        lines.extend(f"- {caveat.text}" for caveat in qualifications)

    lines.append("")
    lines.append(_next_line(payload))
    return "\n".join(lines)


def _next_line(payload: UpliftPresentationPayload) -> str:
    """Offer, in one line, the steps this result actually has.

    A development-only result has no proof to check and nothing may be derived
    from it, so it is offered the one thing it can do. Everything else is left
    unsaid rather than promised on a channel with no room to explain.
    """
    if payload.proof_grade == "development_only":
        return "Next: I can show every task locally."
    return (
        "Next: I can show every task locally, set up a comparison against a "
        "revised Skill, or verify this run's local proof."
    )


def _worst_first(payload: UpliftPresentationPayload) -> list[TaskResultRow]:
    """Return the tasks that moved, regressions first, ties never."""
    changed = [row for row in payload.task_rows if row.outcome != "tie"]
    return sorted(
        changed, key=lambda row: (0 if row.outcome == "loss" else 1, row.position)
    )
