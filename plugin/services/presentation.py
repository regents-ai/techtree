"""Putting a result in front of a person. Specification section 8.8.

The deterministic part is always there and always first. The model-authored
part is optional, checked, and second — and when anything about it is wrong,
it simply is not there, and the result is complete without it.

The two orderings below are not styling. They exist so that nobody ever reads
a sentence about a comparison before reading the comparison, and so that a
proof that did not verify is the first thing said rather than a footnote under
an encouraging headline.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final

from ..channels import is_gateway_safe_required
from ..errors import PluginError, scrub_text
from ..guards import bounded_narrative, validate_narrative
from ..llm import HostLlmRequest, HostLlmResult, OneShotHostLlm
from ..models import ChannelKind, PresentationNarrative, ReleaseCore
from ..narrative import (
    REPRODUCTION_STATEMENT,
    SAME_MEMBERSHIP_DISCLOSURE,
    SECOND_RESULT_FORBIDDEN_WORDS,
    allowed_task_refs,
    build_presentation_input,
    parse_presentation_narrative,
    presentation_output_schema,
    second_result_receipt,
)

#: What the one host completion here is for.
NARRATIVE_PURPOSE: Final = "result_narrative"

#: The order a terminal reads a result in. Specification section 8.8.
TERMINAL_ORDER: Final[tuple[str, ...]] = (
    "scores",
    "controlled_change",
    "proof",
    "narrative",
    "next_actions",
)

#: The order a phone reads a result in.
GATEWAY_ORDER: Final[tuple[str, ...]] = (
    "scores",
    "outcomes",
    "caveat",
    "narrative",
    "next_action",
    "proof_path",
)


class PresentationService:
    """Composes one result out of Techtree's numbers and, sometimes, words."""

    def __init__(self, *, llm: Any, release: ReleaseCore) -> None:
        self._llm = llm
        self._release = release

    def explain_result(
        self,
        *,
        result_envelope: Mapping[str, Any],
        channel: ChannelKind,
        include_host_explanation: bool = False,
        comparison: str = "first",
        source_feedback_report_digest: str | None = None,
    ) -> dict[str, Any]:
        """Return the deterministic result, and a narrative when one is allowed.

        Exactly one host completion is made, and only when one was asked for,
        the host offers a model, and the result is one a narrative may be
        written about at all.
        """
        presentation = self.deterministic_only(
            result_envelope=result_envelope,
            channel=channel,
            comparison=comparison,
            source_feedback_report_digest=source_feedback_report_digest,
        )
        if not include_host_explanation:
            return presentation
        if self._llm is None:
            return _with_note(presentation, "this host offers no model to explain with")
        if not presentation["narration_allowed"]:
            return _with_note(
                presentation,
                "this result is not one to write encouraging words about; the "
                "verification status leads instead",
            )

        payload = _payload_of(result_envelope)
        request = HostLlmRequest(
            system=str(
                build_presentation_input(
                    deterministic_payload=payload, channel=channel
                )["instructions"]
            ),
            user=_input_text(payload, channel),
            schema=presentation_output_schema(),
            purpose=NARRATIVE_PURPOSE,
        )

        try:
            result = OneShotHostLlm(self._llm).complete(request)
            narrative = self._checked_narrative(result, payload, channel)
        except PluginError as error:
            return _with_note(presentation, scrub_text(str(error)), code=error.code)

        return self.merge_presentation(presentation, narrative, channel)

    def deterministic_only(
        self,
        *,
        result_envelope: Mapping[str, Any],
        channel: ChannelKind,
        comparison: str = "first",
        source_feedback_report_digest: str | None = None,
    ) -> dict[str, Any]:
        """Return everything Techtree said, in the order this channel reads it."""
        payload = _payload_of(result_envelope)
        verified = _verification_ok(payload)
        compact = is_gateway_safe_required(channel)
        result: dict[str, Any] = {
            "ok": bool(result_envelope.get("ok", True)),
            "command": "run result",
            "channel": channel.value,
            "order": list(GATEWAY_ORDER if compact else TERMINAL_ORDER),
            "presentation": compact_presentation(payload) if compact else dict(payload),
            "report": None if compact else _report_of(result_envelope),
            "verification_status": payload.get("verification_status"),
            "proof_grade": payload.get("proof_grade"),
            "narration_allowed": verified,
            "leads_with": "result" if verified else "verification_failure",
            "reproduction": REPRODUCTION_STATEMENT,
            "outcome": describe_outcome(payload),
            "usage": usage_summary(payload),
            "narrative": None,
        }

        if comparison == "second":
            result["receipt"] = second_result_receipt(
                source_feedback_report_digest=source_feedback_report_digest,
                decision=payload.get("decision"),
                verification_status=payload.get("verification_status"),
            )
            result["comparison_labels"] = {
                "baseline": "Skill v1",
                "candidate": "Skill v2",
            }
        return result

    def merge_presentation(
        self,
        deterministic: Mapping[str, Any],
        narrative: PresentationNarrative | None,
        channel: ChannelKind,
    ) -> dict[str, Any]:
        """Return the deterministic result with a checked narrative beside it."""
        merged = dict(deterministic)
        merged["narrative"] = narrative.to_dict() if narrative is not None else None
        merged["channel"] = channel.value
        return merged

    def _checked_narrative(
        self,
        result: HostLlmResult,
        payload: Mapping[str, Any],
        channel: ChannelKind,
    ) -> PresentationNarrative:
        narrative = parse_presentation_narrative(result.parsed)
        validate_narrative(
            narrative,
            allowed_task_refs=allowed_task_refs(payload),
            channel=channel,
        )
        return bounded_narrative(narrative, channel)


def _with_note(
    presentation: Mapping[str, Any], note: str, code: str | None = None
) -> dict[str, Any]:
    """Return the deterministic result, saying why no narrative came with it."""
    without = dict(presentation)
    without["narrative"] = None
    without["narrative_note"] = note
    if code is not None:
        without["narrative_code"] = code
    return without


def _payload_of(result_envelope: Mapping[str, Any]) -> Mapping[str, Any]:
    data = result_envelope.get("data")
    payload = data.get("presentation") if isinstance(data, Mapping) else None
    if not isinstance(payload, Mapping):
        raise PluginError(
            "this run result carries no presentation payload to show",
            code="host_llm_output_invalid",
        )
    return payload


def _report_of(result_envelope: Mapping[str, Any]) -> Mapping[str, Any] | None:
    data = result_envelope.get("data")
    report = data.get("report") if isinstance(data, Mapping) else None
    return report if isinstance(report, Mapping) else None


def _verification_ok(payload: Mapping[str, Any]) -> bool:
    """Whether this result is one a narrative may be written about.

    A result whose proof did not verify is still worth inspecting, and the
    plugin still shows it. What it does not get is a paragraph of encouraging
    wording on top: the failure leads, and words that would soften it are not
    written at all.
    """
    status = str(payload.get("verification_status") or "").lower()
    if not status:
        return False
    return not any(
        bad in status for bad in ("fail", "invalid", "unverified", "error", "mismatch")
    )


def _input_text(payload: Mapping[str, Any], channel: ChannelKind) -> str:
    """Return the facts as the one text block the host model is given."""
    import json

    document = build_presentation_input(deterministic_payload=payload, channel=channel)
    document.pop("instructions", None)
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False)


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


def usage_summary(
    payload: Mapping[str, Any], execution_record: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Report tokens, time, and cost with where each number came from.

    Decision 0007 R6: cost is shown with explicit provenance, and an estimate
    is never presented as a provider-reported figure. This build has no signed
    execution record to read — Techtree does not produce one yet — so cost is
    reported as unavailable rather than guessed at, and tokens and timing are
    attributed to the run report they actually came from. Missing economics
    never invalidates a score; it makes the economics unavailable.
    """
    if execution_record is not None:
        return {
            "source": "comparison_execution_record",
            "baseline_tokens": execution_record.get("baseline_total_tokens"),
            "candidate_tokens": execution_record.get("candidate_total_tokens"),
            "baseline_seconds": execution_record.get("baseline_elapsed_seconds"),
            "candidate_seconds": execution_record.get("candidate_elapsed_seconds"),
            "cost_usd": execution_record.get("cost_usd"),
            "cost_provenance": execution_record.get("cost_provenance", "unavailable"),
        }

    return {
        "source": "run_report",
        "baseline_tokens": payload.get("baseline_tokens"),
        "candidate_tokens": payload.get("candidate_tokens"),
        "baseline_seconds": payload.get("baseline_seconds"),
        "candidate_seconds": payload.get("candidate_seconds"),
        "cost_usd": None,
        "cost_provenance": "unavailable",
        "note": (
            "This build reports no signed execution record, so cost is not "
            "shown. The comparison itself is unaffected."
        ),
    }


def forbidden_second_result_words(text: str) -> list[str]:
    """Return the words that would oversell a second comparison.

    The plugin's own fixed sentences are removed before scanning. One of them
    says the result has NOT been independently reproduced, and a check that
    flagged the honest sentence for containing the dishonest word would be a
    check that punishes candour.
    """
    lowered = text.lower()
    for honest in (REPRODUCTION_STATEMENT, SAME_MEMBERSHIP_DISCLOSURE):
        lowered = lowered.replace(honest.lower(), "")
    return [word for word in SECOND_RESULT_FORBIDDEN_WORDS if word in lowered]


#: What a phone is shown of a result: the canonical facts, without the table.
COMPACT_PRESENTATION_FIELDS: Final[tuple[str, ...]] = (
    "run_id",
    "campaign_title",
    "comparison_label",
    "baseline_score",
    "candidate_score",
    "absolute_delta",
    "relative_delta",
    "wins",
    "losses",
    "ties",
    "decision",
    "proof_grade",
    "verification_status",
)


def compact_presentation(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return the canonical facts a phone can hold.

    Every number a reader needs to judge the comparison, and none of the
    per-task table: a twenty-row table in a chat message is unreadable, and a
    chat app would split it anyway. The full payload is still in Techtree, one
    terminal command away, and the answer says so.
    """
    compact = {
        name: payload[name] for name in COMPACT_PRESENTATION_FIELDS if name in payload
    }
    caveats = payload.get("caveats")
    if isinstance(caveats, Sequence):
        compact["caveats"] = [
            caveat.get("text")
            for caveat in caveats
            if isinstance(caveat, Mapping) and isinstance(caveat.get("text"), str)
        ][:2]
    rows = payload.get("task_rows")
    if isinstance(rows, Sequence):
        compact["task_count"] = len(rows)
        compact["task_rows_available_in_terminal"] = True
    return compact
