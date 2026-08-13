"""Composing a result. Specification sections 8.8 and 8.21.

The host model is a stub throughout: no model is called, and nothing is spent.
"""

from __future__ import annotations

from typing import Any

import pytest
from techtree_hermes.errors import PluginError
from techtree_hermes.models import ChannelKind
from techtree_hermes.release import load_embedded_release_core
from techtree_hermes.services.presentation import (
    GATEWAY_ORDER,
    TERMINAL_ORDER,
    PresentationService,
)

CORE = load_embedded_release_core()

GOOD_NARRATIVE: dict[str, Any] = {
    "headline": "The Skill helped on the tasks it was measured on.",
    "observations": ["Most of the change came from one rule."],
    "caveats": ["The provider does not expose an immutable model revision."],
    "next_step": "Verify the proof before relying on it.",
    "selected_task_refs": ["task-01"],
}


class StubHost:
    """A host model that answers once, from a script."""

    def __init__(self, parsed: Any = None, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.parsed = GOOD_NARRATIVE if parsed is None else parsed
        self.error = error

    def complete_structured(
        self, *, system: str, user: str, schema: dict[str, Any], purpose: str
    ) -> dict[str, Any]:
        self.calls.append(
            {"system": system, "user": user, "schema": schema, "purpose": purpose}
        )
        if self.error is not None:
            raise self.error
        return {"parsed": self.parsed, "model": "host-model-1", "provider": "host"}


def _payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "run_id": "run_" + "0" * 32,
        "campaign_title": "Procedure transfer",
        "comparison_label": "no Skill versus starter Skill v1",
        "baseline_score": 2.0,
        "candidate_score": 24.0,
        "absolute_delta": 22.0,
        "wins": 22,
        "losses": 1,
        "ties": 13,
        "task_rows": [{"position": 0, "task_label": "task-01", "outcome": "win"}],
        "decision": "improved",
        "proof_grade": "P1",
        "verification_status": "verified",
        "caveats": [],
        "next_actions": [],
    }
    payload.update(overrides)
    return payload


def _envelope(**overrides: Any) -> dict[str, Any]:
    return {
        "schema_version": "techtree.cli.v1",
        "command": "run result",
        "ok": True,
        "data": {"report": {"run_id": "run_x"}, "presentation": _payload(**overrides)},
        "error": None,
        "messages": [],
        "warnings": [],
        "next_actions": [],
    }


def _service(host: Any = None) -> PresentationService:
    return PresentationService(llm=host, release=CORE)


# Deterministic first, always -------------------------------------------------------


def test_the_numbers_come_through_untouched() -> None:
    result = _service().deterministic_only(
        result_envelope=_envelope(), channel=ChannelKind.TERMINAL
    )

    assert result["presentation"]["candidate_score"] == 24.0
    assert result["presentation"]["wins"] == 22
    assert result["proof_grade"] == "P1"
    assert "not been independently reproduced" in result["reproduction"]


def test_each_channel_has_its_mandatory_order() -> None:
    terminal = _service().deterministic_only(
        result_envelope=_envelope(), channel=ChannelKind.TERMINAL
    )
    gateway = _service().deterministic_only(
        result_envelope=_envelope(), channel=ChannelKind.GATEWAY
    )

    assert terminal["order"] == list(TERMINAL_ORDER)
    assert gateway["order"] == list(GATEWAY_ORDER)
    assert terminal["order"].index("scores") < terminal["order"].index("narrative")
    assert gateway["order"].index("scores") < gateway["order"].index("narrative")


def test_no_narrative_is_written_unless_one_was_asked_for() -> None:
    host = StubHost()

    result = _service(host).explain_result(
        result_envelope=_envelope(), channel=ChannelKind.TERMINAL
    )

    assert result["narrative"] is None
    assert host.calls == []


def test_a_host_without_a_model_still_returns_the_result() -> None:
    result = _service(None).explain_result(
        result_envelope=_envelope(),
        channel=ChannelKind.TERMINAL,
        include_host_explanation=True,
    )

    assert result["presentation"]["candidate_score"] == 24.0
    assert result["narrative"] is None
    assert "no model" in result["narrative_note"]


# One completion --------------------------------------------------------------------


def test_exactly_one_host_completion_is_made() -> None:
    host = StubHost()

    result = _service(host).explain_result(
        result_envelope=_envelope(),
        channel=ChannelKind.TERMINAL,
        include_host_explanation=True,
    )

    assert len(host.calls) == 1
    assert host.calls[0]["purpose"] == "result_narrative"
    assert result["narrative"]["headline"] == GOOD_NARRATIVE["headline"]


def test_the_model_is_asked_with_the_schema_that_has_no_numbers() -> None:
    host = StubHost()

    _service(host).explain_result(
        result_envelope=_envelope(),
        channel=ChannelKind.TERMINAL,
        include_host_explanation=True,
    )

    schema = host.calls[0]["schema"]
    assert "baseline_score" not in schema["properties"]
    assert schema["additionalProperties"] is False


# Falling back ------------------------------------------------------------------------


def test_an_invalid_narrative_falls_back_to_the_deterministic_result() -> None:
    host = StubHost(
        parsed={
            "headline": "It scored 30/36.",
            "observations": [],
            "caveats": [],
        }
    )

    result = _service(host).explain_result(
        result_envelope=_envelope(),
        channel=ChannelKind.TERMINAL,
        include_host_explanation=True,
    )

    assert result["narrative"] is None
    assert result["presentation"]["candidate_score"] == 24.0
    assert result["narrative_code"] == "presentation_claim_forbidden"


def test_a_failed_completion_falls_back_and_is_not_retried() -> None:
    host = StubHost(error=RuntimeError("provider down"))

    result = _service(host).explain_result(
        result_envelope=_envelope(),
        channel=ChannelKind.TERMINAL,
        include_host_explanation=True,
    )

    assert result["narrative"] is None
    assert result["narrative_code"] == "host_llm_unavailable"
    assert len(host.calls) == 1


def test_a_narrative_naming_an_unknown_task_falls_back() -> None:
    host = StubHost(parsed={**GOOD_NARRATIVE, "selected_task_refs": ["task-99"]})

    result = _service(host).explain_result(
        result_envelope=_envelope(),
        channel=ChannelKind.TERMINAL,
        include_host_explanation=True,
    )

    assert result["narrative"] is None
    assert "not in this comparison" in result["narrative_note"]


# A result that did not verify ---------------------------------------------------------


@pytest.mark.parametrize(
    "status", ["failed", "proof_invalid", "unverified", "verification_error"]
)
def test_a_result_that_did_not_verify_gets_no_encouraging_words(status: str) -> None:
    """The failure leads; wording that would soften it is never written."""
    host = StubHost()

    result = _service(host).explain_result(
        result_envelope=_envelope(verification_status=status),
        channel=ChannelKind.TERMINAL,
        include_host_explanation=True,
    )

    assert result["leads_with"] == "verification_failure"
    assert result["narrative"] is None
    assert host.calls == []


def test_a_result_that_did_not_verify_can_still_be_inspected() -> None:
    result = _service().deterministic_only(
        result_envelope=_envelope(verification_status="proof_invalid"),
        channel=ChannelKind.TERMINAL,
    )

    assert result["presentation"]["candidate_score"] == 24.0
    assert result["narration_allowed"] is False


# Channels -----------------------------------------------------------------------------


def test_a_phone_narrative_is_trimmed_to_fit() -> None:
    host = StubHost(
        parsed={
            **GOOD_NARRATIVE,
            "observations": ["A long observation. " * 40 for _ in range(3)],
        }
    )

    result = _service(host).explain_result(
        result_envelope=_envelope(),
        channel=ChannelKind.GATEWAY,
        include_host_explanation=True,
    )

    narrative = result["narrative"]
    assert narrative is not None
    assert len(narrative["observations"]) < 3
    assert narrative["caveats"] == GOOD_NARRATIVE["caveats"]


def test_a_result_with_no_presentation_payload_is_refused_not_invented() -> None:
    """Nothing here makes up a presentation Techtree did not produce."""
    with pytest.raises(PluginError, match="no presentation payload"):
        _service().deterministic_only(
            result_envelope={"ok": True, "data": {"report": {}}},
            channel=ChannelKind.TERMINAL,
        )
