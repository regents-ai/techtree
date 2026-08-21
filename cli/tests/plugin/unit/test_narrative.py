"""What the model is shown, and what shape its answer must take. Section 8.6."""

from __future__ import annotations

import json
from typing import Any

import pytest
from techtree_hermes.errors import PluginError
from techtree_hermes.models import ChannelKind
from techtree_hermes.narrative import (
    ALLOWED_FACTS,
    FORBIDDEN_CLAIMS,
    allowed_task_refs,
    build_presentation_input,
    parse_presentation_narrative,
    presentation_output_schema,
)

#: The values that always come from Techtree, never from a sentence.
NUMERIC_TRUTH_FIELDS = (
    "baseline_score",
    "candidate_score",
    "absolute_delta",
    "wins",
    "losses",
    "ties",
    "proof_grade",
    "status",
    "receipt_digest",
)


def _payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "techtree.presentation.uplift.v1",
        "run_id": "run_" + "0" * 32,
        "campaign_title": "Procedure transfer",
        "comparison_label": "no Skill versus starter Skill v1",
        "baseline_skill": {"label": "none", "digest": None},
        "candidate_skill": {"label": "starter", "digest": "sha256:" + "a" * 64},
        "baseline_score": 2.0,
        "candidate_score": 24.0,
        "absolute_delta": 22.0,
        "relative_delta": 11.0,
        "wins": 22,
        "losses": 1,
        "ties": 13,
        "task_rows": [
            {"position": 0, "task_label": "task-01", "outcome": "win"},
            {"position": 1, "task_label": "task-02", "outcome": "tie"},
        ],
        "decision": "improved",
        "proof_grade": "P1",
        "verification_status": "verified",
        "caveats": [
            {
                "code": "model_revision_unavailable",
                "severity": "warning",
                "text": "The provider does not expose an immutable revision.",
            }
        ],
        "next_actions": [],
    }
    payload.update(overrides)
    return payload


# The input -----------------------------------------------------------------------


def test_the_model_is_shown_the_facts_it_may_reason_over() -> None:
    given = build_presentation_input(
        deterministic_payload=_payload(), channel=ChannelKind.TERMINAL
    )

    assert set(given["facts"]) <= set(ALLOWED_FACTS)
    assert given["facts"]["decision"] == "improved"
    assert given["facts"]["candidate_score"] == 24.0


def test_the_model_is_shown_nothing_from_inside_a_run() -> None:
    """No episodes, no traces, no per-task scores, no skill digests."""
    given = build_presentation_input(
        deterministic_payload=_payload(), channel=ChannelKind.GATEWAY
    )

    document = json.dumps(given)
    assert "task_rows" not in given
    assert "sha256:" not in document
    assert "run_" not in document


def test_the_model_is_told_what_it_may_not_claim() -> None:
    given = build_presentation_input(
        deterministic_payload=_payload(), channel=ChannelKind.TERMINAL
    )

    assert given["forbidden_claims"] == list(FORBIDDEN_CLAIMS)
    assert "independently reproduced" in given["reproduction_statement"]


def test_the_model_is_told_which_tasks_it_may_name() -> None:
    given = build_presentation_input(
        deterministic_payload=_payload(), channel=ChannelKind.TERMINAL
    )

    assert given["allowed_task_refs"] == ["task-01", "task-02"]
    assert allowed_task_refs(_payload()) == {"task-01", "task-02"}


def test_the_model_is_told_how_much_room_it_has() -> None:
    assert (
        build_presentation_input(
            deterministic_payload=_payload(), channel=ChannelKind.GATEWAY
        )["room"]
        == "short"
    )
    assert (
        build_presentation_input(
            deterministic_payload=_payload(), channel=ChannelKind.TERMINAL
        )["room"]
        == "ordinary"
    )


def test_the_verified_caveats_are_passed_through_as_written() -> None:
    given = build_presentation_input(
        deterministic_payload=_payload(), channel=ChannelKind.TERMINAL
    )

    assert given["verified_caveats"] == [
        "The provider does not expose an immutable revision."
    ]


# The output schema ------------------------------------------------------------------


def test_the_schema_has_no_numeric_truth_field() -> None:
    """The model cannot return a score because there is nowhere to put one."""
    schema = presentation_output_schema()

    for field in NUMERIC_TRUTH_FIELDS:
        assert field not in schema["properties"]


def test_the_schema_is_closed_and_bounded() -> None:
    schema = presentation_output_schema()

    assert schema["additionalProperties"] is False
    for definition in schema["properties"].values():
        assert "maxLength" in definition or "maxItems" in definition


def test_the_schema_asks_only_for_the_four_narrative_choices() -> None:
    """Decision 0007: headline, observations, one caveat, next step."""
    properties = set(presentation_output_schema()["properties"])

    assert properties == {
        "headline",
        "observations",
        "caveats",
        "next_step",
        "selected_task_refs",
    }


def test_no_schema_field_invites_a_number() -> None:
    document = json.dumps(presentation_output_schema()).lower()

    assert "number" not in document
    assert "integer" not in document


# Parsing ---------------------------------------------------------------------------


def test_a_well_formed_answer_parses() -> None:
    narrative = parse_presentation_narrative(
        {
            "headline": "The Skill helped.",
            "observations": ["Most gains came from one rule."],
            "caveats": ["The provider revision is not pinned."],
            "next_step": "Verify the proof.",
            "selected_task_refs": ["task-01"],
        }
    )

    assert narrative.headline == "The Skill helped."
    assert narrative.observations == ("Most gains came from one rule.",)


def test_an_answer_carrying_a_score_field_is_refused() -> None:
    """A model returning a baseline_score misunderstood its job."""
    with pytest.raises(PluginError, match="fields it was not asked for"):
        parse_presentation_narrative(
            {
                "headline": "It improved.",
                "observations": [],
                "caveats": [],
                "baseline_score": 2.0,
            }
        )


@pytest.mark.parametrize(
    "answer",
    [
        {"observations": [], "caveats": []},
        {"headline": "  ", "observations": [], "caveats": []},
        {"observations": [], "caveats": []},
        {
            "headline": "It improved.",
            "observations": "not a list",
            "caveats": [],
        },
        {
            "headline": "It improved.",
            "observations": [1, 2],
            "caveats": [],
        },
        {
            "headline": "It improved.",
            "observations": [],
            "caveats": [],
            "next_step": 7,
        },
    ],
)
def test_a_malformed_answer_is_refused(answer: dict[str, Any]) -> None:
    with pytest.raises(PluginError):
        parse_presentation_narrative(answer)


def test_empty_items_are_dropped_rather_than_kept() -> None:
    narrative = parse_presentation_narrative(
        {
            "headline": "It improved.",
            "observations": ["A point.", "   ", ""],
            "caveats": [],
        }
    )

    assert narrative.observations == ("A point.",)
    assert narrative.next_step is None
