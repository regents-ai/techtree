"""Composing a result. Specification sections 8.8 and 8.21.

Decision 0009 removed presentation wording by a host model from the release,
so there is no model here to stub: composing a result reads Techtree's payload
and nothing else.
"""

from __future__ import annotations

from typing import Any

import pytest
from techtree_hermes.errors import PluginError
from techtree_hermes.models import ChannelKind
from techtree_hermes.narrative import FIRST_RESULT_LABEL, SECOND_RESULT_LABEL
from techtree_hermes.release import load_embedded_release_core
from techtree_hermes.services.presentation import (
    GATEWAY_ORDER,
    TERMINAL_ORDER,
    PresentationService,
)

CORE = load_embedded_release_core()


def _payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "run_id": "run_" + "0" * 32,
        "campaign_title": "Hello World Skill Uplift",
        "comparison_label": "no Skill versus hello-world-starter-v1",
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


def _service() -> PresentationService:
    return PresentationService(release=CORE)


# Deterministic, and only deterministic ---------------------------------------------


def test_the_numbers_come_through_untouched() -> None:
    result = _service().deterministic_only(
        result_envelope=_envelope(), channel=ChannelKind.TERMINAL
    )

    assert result["presentation"]["candidate_score"] == 24.0
    assert result["presentation"]["wins"] == 22
    assert result["proof_grade"] == "P1"
    assert "not been independently reproduced" in result["reproduction"]


def test_a_composed_result_carries_no_model_written_words() -> None:
    """Decision 0009: no host-model presentation completion exists."""
    result = _service().deterministic_only(
        result_envelope=_envelope(), channel=ChannelKind.TERMINAL
    )

    assert "narrative" not in result
    assert "narration_allowed" not in result
    assert not hasattr(_service(), "explain_result")


def test_each_channel_has_its_mandatory_order() -> None:
    terminal = _service().deterministic_only(
        result_envelope=_envelope(), channel=ChannelKind.TERMINAL
    )
    gateway = _service().deterministic_only(
        result_envelope=_envelope(), channel=ChannelKind.GATEWAY
    )

    assert terminal["order"] == list(TERMINAL_ORDER)
    assert gateway["order"] == list(GATEWAY_ORDER)
    assert "narrative" not in terminal["order"]
    assert "narrative" not in gateway["order"]
    assert terminal["order"].index("scores") < terminal["order"].index("proof")


# The Hello World labels ---------------------------------------------------------------


def test_the_first_comparison_is_the_hello_world_uplift_receipt() -> None:
    result = _service().deterministic_only(
        result_envelope=_envelope(), channel=ChannelKind.TERMINAL
    )

    assert result["result_label"] == FIRST_RESULT_LABEL == "Hello World Uplift Receipt"


def test_the_second_comparison_is_iteration_two() -> None:
    result = _service().deterministic_only(
        result_envelope=_envelope(),
        channel=ChannelKind.TERMINAL,
        comparison="second",
        source_feedback_report_digest="sha256:" + "a" * 64,
    )

    assert result["result_label"] == SECOND_RESULT_LABEL == "Hello World — Iteration 2"
    assert result["receipt"]["label"] == SECOND_RESULT_LABEL
    assert result["receipt"]["source_feedback_report_digest"] == "sha256:" + "a" * 64


# A result that did not verify ---------------------------------------------------------


@pytest.mark.parametrize(
    "status", ["failed", "proof_invalid", "unverified", "verification_error"]
)
def test_a_result_that_did_not_verify_leads_with_the_failure(status: str) -> None:
    result = _service().deterministic_only(
        result_envelope=_envelope(verification_status=status),
        channel=ChannelKind.TERMINAL,
    )

    assert result["leads_with"] == "verification_failure"
    assert result["outcome"]["candidate_improved"] is None


def test_a_result_that_did_not_verify_can_still_be_inspected() -> None:
    result = _service().deterministic_only(
        result_envelope=_envelope(verification_status="proof_invalid"),
        channel=ChannelKind.TERMINAL,
    )

    assert result["presentation"]["candidate_score"] == 24.0
    assert result["leads_with"] == "verification_failure"


# Channels -----------------------------------------------------------------------------


def test_a_phone_gets_the_canonical_facts_without_the_table() -> None:
    result = _service().deterministic_only(
        result_envelope=_envelope(), channel=ChannelKind.GATEWAY
    )

    assert result["presentation"]["candidate_score"] == 24.0
    assert "task_rows" not in result["presentation"]
    assert result["presentation"]["task_count"] == 1
    assert result["report"] is None


def test_a_result_with_no_presentation_payload_is_refused_not_invented() -> None:
    """Nothing here makes up a presentation Techtree did not produce."""
    with pytest.raises(PluginError, match="no presentation payload"):
        _service().deterministic_only(
            result_envelope={"ok": True, "data": {"report": {}}},
            channel=ChannelKind.TERMINAL,
        )
