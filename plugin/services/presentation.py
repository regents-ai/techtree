"""Putting a result in front of a person. Specification section 8.8.

Everything here is deterministic. Techtree computes the result, renders it,
and the plugin relays exactly what it said: no model is asked to word a
result, and there is nothing to check afterwards because nothing was written.

The two orderings below are not styling. They exist so that a proof that did
not verify is the first thing said rather than a footnote under a friendlier
number.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final

from ..cli.errors import PluginError
from ..host.channels import bounded_gateway_text, is_gateway_safe_required
from .models import ChannelKind
from .narrative import FIRST_RESULT_LABEL, REPRODUCTION_STATEMENT

#: The order a terminal reads a result in. Specification section 8.8.
TERMINAL_ORDER: Final[tuple[str, ...]] = (
    "scores",
    "controlled_change",
    "proof",
    "publication_offer",
)

#: The order a phone reads a result in.
GATEWAY_ORDER: Final[tuple[str, ...]] = (
    "scores",
    "outcomes",
    "caveat",
    "next_action",
    "proof_path",
)


class PresentationService:
    """Composes one result out of Techtree's numbers, and only those."""

    def deterministic_only(
        self,
        *,
        result: Mapping[str, Any],
        channel: ChannelKind,
    ) -> dict[str, Any]:
        """Return everything Techtree said, in the order this channel reads it.

        ``result`` is the answer of ``regents techtree run result``: the
        presentation payload, the uplift report and the execution record at
        its top level.
        """
        payload = _payload_of(result)
        verified = _verification_ok(payload)
        compact = is_gateway_safe_required(channel)
        return {
            "channel": channel.value,
            "order": list(GATEWAY_ORDER if compact else TERMINAL_ORDER),
            "presentation": compact_presentation(payload) if compact else dict(payload),
            "verification_status": payload.get("verification_status"),
            "proof_grade": payload.get("proof_grade"),
            "leads_with": "result" if verified else "verification_failure",
            "reproduction": REPRODUCTION_STATEMENT,
            "outcome": describe_outcome(payload),
            "usage": usage_summary(payload),
            "completion_summary": completion_summary(result),
            "result_label": FIRST_RESULT_LABEL,
        }


def _payload_of(result: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = result.get("presentation")
    if not isinstance(payload, Mapping):
        raise PluginError(
            "this run result carries no presentation payload to show",
            code="host_llm_output_invalid",
        )
    return payload


def _verification_ok(payload: Mapping[str, Any]) -> bool:
    """Whether this result's proof verified.

    A result whose proof did not verify is still worth inspecting, and the
    plugin still shows it. What changes is the order: the failure is read
    first, rather than after the numbers it calls into question.
    """
    status = str(payload.get("verification_status") or "").lower()
    if not status:
        return False
    return not any(
        bad in status for bad in ("fail", "invalid", "unverified", "error", "mismatch")
    )


# What the result actually says -------------------------------------------------


#: Decisions that mean the candidate did better. Anything else does not, and
#: the wording follows the payload rather than hope.
_POSITIVE_DECISIONS: Final = frozenset({"improved", "improvement", "accepted"})
_NEGATIVE_DECISIONS: Final = frozenset({"regressed", "worse", "rejected"})


def describe_outcome(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Say plainly what happened, including when nothing good did.

    A comparison that shows no improvement is a comparison that worked, and a
    result whose proof did not verify is not an outcome at all yet. Neither is
    softened here, and neither is left for a sentence to decide.
    """
    decision = str(payload.get("decision") or "").lower()
    verified = _verification_ok(payload)

    if not verified:
        summary = (
            "This result did not verify, so it says nothing about either Skill yet."
        )
        improved = None
    elif decision in _POSITIVE_DECISIONS:
        summary = "The candidate did better than the baseline on this task set."
        improved = True
    elif decision in _NEGATIVE_DECISIONS:
        summary = "The candidate did worse than the baseline on this task set."
        improved = False
    else:
        summary = (
            "This comparison is not a clear win either way; the decision is "
            f"{payload.get('decision')!r}."
        )
        improved = False

    return {
        "candidate_improved": improved,
        "summary": summary,
        "decision": payload.get("decision"),
        "wins": payload.get("wins"),
        "losses": payload.get("losses"),
        "ties": payload.get("ties"),
        "controlled": payload.get("verification_status"),
    }


def usage_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Report tokens, time, and cost with where each number came from.

    Decision 0007 R6: cost is shown with explicit provenance, and a figure that
    was worked out is never presented as one the provider reported. Every value
    here is read off Techtree's payload, including the word for where the
    economics came from and, when no figure exists, Techtree's own sentence
    saying which half of a cost this run is missing. Nothing is computed here
    and no figure is invented for a run that recorded none: missing economics
    never invalidates a score; it makes the economics unavailable.
    """
    return {
        "source": payload.get("economics_source", "unavailable"),
        "baseline_tokens": payload.get("baseline_tokens"),
        "candidate_tokens": payload.get("candidate_tokens"),
        "baseline_seconds": payload.get("baseline_seconds"),
        "candidate_seconds": payload.get("candidate_seconds"),
        "derived_cost": payload.get("derived_cost"),
        "cost_unavailable_reason": payload.get("cost_unavailable_reason"),
    }


def completion_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    """Return headline completion totals from the signed execution record.

    The overall elapsed time is the record's own value, not a sum or a new
    clock reading. A total token count is meaningful only when both variants
    reported one, so a partial record keeps the total explicitly unavailable.
    The side values remain available here and in ``usage`` for a reader who
    wants the breakdown.
    """
    payload = result.get("presentation")
    record = result.get("execution_record")
    if not isinstance(record, Mapping):
        return {
            "elapsed_seconds": None,
            "total_tokens": None,
            "baseline_seconds": (
                payload.get("baseline_seconds")
                if isinstance(payload, Mapping)
                else None
            ),
            "candidate_seconds": (
                payload.get("candidate_seconds")
                if isinstance(payload, Mapping)
                else None
            ),
            "baseline_tokens": (
                payload.get("baseline_tokens") if isinstance(payload, Mapping) else None
            ),
            "candidate_tokens": (
                payload.get("candidate_tokens")
                if isinstance(payload, Mapping)
                else None
            ),
        }

    baseline = record.get("baseline")
    candidate = record.get("candidate")
    baseline = baseline if isinstance(baseline, Mapping) else {}
    candidate = candidate if isinstance(candidate, Mapping) else {}
    baseline_usage = baseline.get("usage")
    candidate_usage = candidate.get("usage")
    baseline_usage = baseline_usage if isinstance(baseline_usage, Mapping) else {}
    candidate_usage = candidate_usage if isinstance(candidate_usage, Mapping) else {}
    baseline_tokens = _token_total(baseline_usage.get("total_tokens"))
    candidate_tokens = _token_total(candidate_usage.get("total_tokens"))
    return {
        "elapsed_seconds": record.get("elapsed_seconds"),
        "total_tokens": (
            baseline_tokens + candidate_tokens
            if baseline_tokens is not None and candidate_tokens is not None
            else None
        ),
        "baseline_seconds": baseline.get("elapsed_seconds"),
        "candidate_seconds": candidate.get("elapsed_seconds"),
        "baseline_tokens": baseline_tokens,
        "candidate_tokens": candidate_tokens,
    }


def _token_total(value: Any) -> int | None:
    """Return a recorded token total, never treating a malformed value as zero."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


#: What a phone is shown of a result: the canonical facts, without the table.
#:
#: A whitelist, and it stays one: a field reaches a phone because it was named
#: here, never because it happened to be in the payload. Widening it is a
#: deliberate act, which is why each addition below says what a reader loses
#: without it.
COMPACT_PRESENTATION_FIELDS: Final[tuple[str, ...]] = (
    "run_id",
    "campaign_title",
    "comparison_label",
    "baseline_score",
    "candidate_score",
    "absolute_delta",
    "relative_delta",
    # The count a person actually reads a result in. A mean over a toy task
    # set is not the number anyone repeats to somebody else, and a phone that
    # carried only the mean showed strictly less than the terminal did.
    "baseline_tasks_scored_full",
    "candidate_tasks_scored_full",
    "wins",
    "losses",
    "ties",
    # How much work each side did, which unlike the clock is a property of the
    # work rather than of the machine and the afternoon it ran on.
    "baseline_model_turns",
    "candidate_model_turns",
    # How often the provider refused each side, and whether every rollout still
    # ran to completion. Two sides that met different amounts of throttling did
    # not quite meet the same conditions.
    "baseline_rate_limited_calls",
    "candidate_rate_limited_calls",
    "every_rollout_completed",
    # What it cost and, inseparably, what kind of figure that is: one worked
    # out while rendering, with its basis, or none with the reason there is
    # none. Decision 0007 R6 forbids the figure without its basis, so the
    # reason field is part of the same widening.
    "derived_cost",
    "cost_unavailable_reason",
    "decision",
    "proof_grade",
    "verification_status",
)

#: How many qualifications a phone carries, and how much room they may take
#: between them. Warnings and errors, never a note in place of one: room is
#: made by cutting detail, not by cutting the sentence that tells a reader how
#: much the result proves.
#:
#: The block is bounded because everything else in a compact answer is a few
#: hundred bytes and this is the one part of it a run can make arbitrarily
#: long. An answer over the channel's budget is replaced whole by an apology
#: rather than shortened, so an unbounded caveat block is how a phone ends up
#: with no result at all.
COMPACT_CAVEAT_LIMIT: Final = 4
COMPACT_CAVEAT_CHARACTERS: Final = 900


def compact_presentation(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return the canonical facts a phone can hold.

    Every number a reader needs to judge the comparison, and none of the
    per-task table: a twenty-row table in a chat message is unreadable, and a
    chat app would split it anyway. The full payload is still in Techtree, one
    terminal command away, and the answer says so.

    Room is made by cutting the table and the notes, never by cutting a
    qualification: the caveats a phone carries are the warnings and errors, and
    a note is never kept in place of one.
    """
    compact = {
        name: payload[name] for name in COMPACT_PRESENTATION_FIELDS if name in payload
    }
    caveats = payload.get("caveats")
    if isinstance(caveats, Sequence):
        texts = [
            caveat["text"]
            for caveat in caveats
            if isinstance(caveat, Mapping)
            and isinstance(caveat.get("text"), str)
            and caveat.get("severity") != "info"
        ]
        kept = _fitted_caveats(texts)
        compact["caveats"] = kept
        if len(kept) < len(texts):
            compact["caveats_not_shown"] = len(texts) - len(kept)
    rows = payload.get("task_rows")
    if isinstance(rows, Sequence):
        compact["task_count"] = len(rows)
        compact["task_rows_available_in_terminal"] = True
    return compact


def _fitted_caveats(texts: Sequence[str]) -> list[str]:
    """Return the qualifications that fit, most serious first, unreworded.

    Techtree orders these by how much they matter — what would make the result
    invalid, then what bounds how much it proves — so taking them in order
    takes the ones a reader most needs. A sentence is kept whole or not at all,
    except the first, which is kept even if the whole budget has to be spent
    cutting it: a phone with no qualification at all is the one outcome worth
    avoiding at any price. Whatever is left out is counted, never silently
    dropped, and the full list is one terminal command away.
    """
    kept: list[str] = []
    remaining = COMPACT_CAVEAT_CHARACTERS
    for text in texts[:COMPACT_CAVEAT_LIMIT]:
        if not kept:
            kept.append(bounded_gateway_text(text, remaining))
        elif len(text) <= remaining:
            kept.append(text)
        else:
            break
        remaining -= len(kept[-1])
    return kept
