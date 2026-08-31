"""The rendering a phone can carry. Spec section 7.16.

A gateway message is not a small terminal. It has no escape sequences, no
column alignment, a reader holding a phone, and a channel that may truncate
anything long. So this renderer is bounded by construction: a headline, the
counts, the honest qualifications, at most a few task rows, and one sentence
about what could happen next.

The row cap is a default, not a refusal. A reader who says ``--show-tasks all``
has asked for every task on purpose, and the bound exists so that an unasked-for
message is short rather than so that somebody who asked can be told no. So the
cap applies to the selections a reader did not have to name, and the explicit
request for everything overrides it.

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
    HELD_FIXED_LINE,
    NOT_BROAD_CAPABILITY_LINE,
    VERIFICATION_FAILED,
    VERIFICATION_NOT_VERIFIED,
    VERIFICATION_VERIFIED,
    cost_explanation,
    cost_summary,
    decision_headline,
    efficiency_sentence,
    solved_line,
    task_count_line,
)
from techtree.presentation.models import (
    TaskDisplay,
    UpliftPresentationPayload,
    selected_task_rows,
)

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


def render_uplift_markdown(
    payload: UpliftPresentationPayload,
    *,
    maximum_task_rows: int = DEFAULT_MAXIMUM_TASK_ROWS,
    show_tasks: TaskDisplay = TaskDisplay.CHANGED,
) -> str:
    """Return compact Markdown suitable for a phone or gateway message.

    A result whose proof did not verify says that first and in bold. This is
    the channel a number is most likely to be quoted out of, so the sentence
    that would stop somebody quoting it cannot be further down.

    ``show_tasks`` is the same choice the terminal renderer takes, answered by
    the same reader through the same option, and it selects rows through the
    same rule. A reader who asks a piped command for every task and is handed
    the default five has been told the option works when it did not.
    """
    lines = [
        f"**{decision_headline(payload)} — {solved_line(payload)}**",
        "",
        f"- {NOT_BROAD_CAPABILITY_LINE}",
    ]
    if payload.verification_status == VERIFICATION_FAILED:
        lines = [UNVERIFIED_HEADLINE, "", *lines]
    lines += [
        f"- {payload.campaign_title} — {payload.comparison_label}",
        f"- Changed: {payload.change_label}. {HELD_FIXED_LINE}",
        f"- Tasks: {_headline_numbers(payload)}",
        f"- Proof: local {payload.proof_grade}, "
        f"{_VERIFICATION_PHRASE[payload.verification_status]}",
        f"- Cost: {cost_summary(payload)}",
        *(f"- {line}" for line in cost_explanation(payload)),
        *_work(payload),
        "- Raw episodes: retained locally; not uploaded",
    ]

    lines += _table(payload, show_tasks, maximum_task_rows)

    qualifications = [caveat for caveat in payload.caveats if caveat.severity != "info"]
    if qualifications:
        lines.append("")
        lines.extend(f"- {caveat.text}" for caveat in qualifications)

    lines.append("")
    lines.append(_next_line(payload))
    return "\n".join(lines)


def _headline_numbers(payload: UpliftPresentationPayload) -> str:
    """Return how the two sides scored, in the unit a person counts in.

    The bold line above carries what was established and what is still failing.
    This carries the movement underneath it: both sides' counts where the
    reward has them, and the means they came from in the same breath, so that
    nothing is lost by quoting either one.
    """
    means = (
        f"{payload.baseline_score:.3f} → {payload.candidate_score:.3f} "
        f"({payload.absolute_delta:+.3f})"
    )
    counted = task_count_line(payload)
    if counted is None:
        return f"mean {means}"
    return f"{counted}, mean {means}"


def _work(payload: UpliftPresentationPayload) -> list[str]:
    """Return what each side spent doing the same tasks, in one bullet.

    The channel with the least room still carries this: a Skill that took a
    third of the model turns did something a reader wants to know, and unlike
    the clock, that number does not move when the same run is repeated on a
    busier afternoon. The sentence carries both times, so a run that has it
    does not also get a bare pair of durations.
    """
    sentence = efficiency_sentence(payload)
    if sentence is not None:
        return [f"- Work: {sentence}"]
    return [f"- Time: {_time(payload)}"]


def _time(payload: UpliftPresentationPayload) -> str:
    """Return how long each side took, or say it was not recorded.

    Decisions document 0019 section 3 puts timing in the measured difference,
    so the channel with the least room still carries it: a comparison whose
    two sides took very different amounts of time is a comparison a reader
    should be able to ask about.
    """
    baseline = payload.baseline_seconds
    candidate = payload.candidate_seconds
    if baseline is None and candidate is None:
        return "not recorded for this run"
    return f"baseline {_seconds(baseline)}, candidate {_seconds(candidate)}"


def _seconds(value: float | None) -> str:
    """Return one side's elapsed time, or the word for an absent one."""
    if value is None:
        return "unavailable"
    return f"{value:.1f}s"


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
        "revised Skill, or check this run's local receipt offline with "
        "`techtree proof verify`."
    )


def _table(
    payload: UpliftPresentationPayload, show: TaskDisplay, maximum_task_rows: int
) -> list[str]:
    """Return the heading and the rows for the table this reader asked for.

    The cap is the bound this channel keeps by default, and it is applied to
    every selection except the one a reader had to type out. Asking for all
    tasks is a deliberate override of a default, so it is honoured; a reader
    who wanted a short message never asked for the long one.

    A reader who asked for no table, or a selection with nothing in it, gets
    neither rows nor a heading over them. A heading with nothing underneath is
    a line that says a table exists somewhere it does not.
    """
    selected = selected_task_rows(payload.task_rows, show)
    shown = selected if show is TaskDisplay.ALL else selected[:maximum_task_rows]
    if not shown:
        return []
    return [
        "",
        _heading(payload, show, shown=len(shown), selected=len(selected)),
        *(
            f"- {row.task_label}: {row.baseline_score:.2f} → "
            f"{row.candidate_score:.2f} ({row.outcome.upper()})"
            for row in shown
        ),
    ]


def _heading(
    payload: UpliftPresentationPayload,
    show: TaskDisplay,
    *,
    shown: int,
    selected: int,
) -> str:
    """Say what the rows underneath are, and say when some were left out.

    The heading a reader can check is the heading that names its own
    selection. Calling a full table the largest changes claims a ranking that
    nothing performed, and calling a list of losses by the same name reads as
    though the wins had also been in the running and only just lost.

    The counts follow the same rule. Where every row a reader asked for is
    printed, the pair says how much of the whole comparison that is; where the
    cap left some out, it says how many of the asked-for rows are here instead,
    because that is the number that tells a reader something is missing.
    """
    if show is TaskDisplay.ALL:
        return f"All {selected} tasks:"
    name = "Regressions" if show is TaskDisplay.REGRESSIONS else "Changed tasks"
    if shown < selected:
        return f"{name} ({shown} of {selected} shown):"
    return f"{name} ({selected} of {len(payload.task_rows)} tasks):"
