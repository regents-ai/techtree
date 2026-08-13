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

from collections.abc import Mapping
from typing import Any, Final

from ..channels import is_gateway_safe_required
from ..errors import PluginError, scrub_text
from ..guards import bounded_narrative, validate_narrative
from ..llm import HostLlmRequest, HostLlmResult, OneShotHostLlm
from ..models import ChannelKind, PresentationNarrative, ReleaseCore
from ..narrative import (
    REPRODUCTION_STATEMENT,
    allowed_task_refs,
    build_presentation_input,
    parse_presentation_narrative,
    presentation_output_schema,
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
    ) -> dict[str, Any]:
        """Return the deterministic result, and a narrative when one is allowed.

        Exactly one host completion is made, and only when one was asked for,
        the host offers a model, and the result is one a narrative may be
        written about at all.
        """
        presentation = self.deterministic_only(
            result_envelope=result_envelope, channel=channel
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
    ) -> dict[str, Any]:
        """Return everything Techtree said, in the order this channel reads it."""
        payload = _payload_of(result_envelope)
        verified = _verification_ok(payload)
        return {
            "ok": bool(result_envelope.get("ok", True)),
            "command": "run result",
            "channel": channel.value,
            "order": list(
                GATEWAY_ORDER if is_gateway_safe_required(channel) else TERMINAL_ORDER
            ),
            "presentation": dict(payload),
            "report": _report_of(result_envelope),
            "verification_status": payload.get("verification_status"),
            "proof_grade": payload.get("proof_grade"),
            "narration_allowed": verified,
            "leads_with": "result" if verified else "verification_failure",
            "reproduction": REPRODUCTION_STATEMENT,
            "narrative": None,
        }

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
