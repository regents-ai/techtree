"""What may reach a rendering. Spec section 7.17.

The functions here are the last gate between a run's evidence and something a
person or a gateway sees, so each test is a specific thing that must not get
through: an escape sequence, a private path, a traceback carrying environment
values. Credential-shaped text is deliberately not one of them — decision 0036
removed every such check from this project.

The payload walk is the part worth insisting on. It checks every string the
payload holds rather than the fields somebody remembered to check, which is
what keeps a field added next year from being the one that leaks.
"""

from __future__ import annotations

import pytest

from techtree.errors import ValidationError
from techtree.models.cli import NextAction
from techtree.presentation.models import (
    PRESENTATION_SCHEMA_VERSION,
    PresentationCaveat,
    SkillSummary,
    TaskResultRow,
    UpliftPresentationPayload,
)
from techtree.presentation.sanitize import (
    PRESENTATION_REDACTION_FAILED,
    ensure_no_hidden_task_material,
    sanitize_error_summary,
    sanitize_label,
)
from techtree.receipts.execution import CostProvenance
from techtree.verifiers.models import NormalizedExecutionError


def payload(**overrides: object) -> UpliftPresentationPayload:
    """Return a minimal valid payload with one field replaced."""
    base = {
        "schema_version": PRESENTATION_SCHEMA_VERSION,
        "run_id": "run_" + "0" * 32,
        "campaign_title": "A Climb",
        "comparison_label": "Hello World Uplift Receipt",
        "change_label": "No tested Skill → Skill v1",
        "baseline_skill": SkillSummary(
            label="No tested Skill", root_digest=None, file_count=0, total_bytes=0
        ),
        "candidate_skill": SkillSummary(
            label="branch-code-v1",
            root_digest=f"sha256:{'a' * 64}",
            file_count=1,
            total_bytes=1024,
        ),
        "baseline_score": 0.0,
        "candidate_score": 1.0,
        "absolute_delta": 1.0,
        "relative_delta": None,
        "wins": 1,
        "losses": 0,
        "ties": 0,
        "task_rows": [
            TaskResultRow(
                position=0,
                task_label="task 01 · abcdef01",
                baseline_score=0.0,
                candidate_score=1.0,
                delta=1.0,
                outcome="win",
            )
        ],
        "baseline_tasks_scored_full": 0,
        "candidate_tasks_scored_full": 1,
        "baseline_tokens": None,
        "candidate_tokens": None,
        "baseline_seconds": None,
        "candidate_seconds": None,
        "baseline_model_turns": None,
        "candidate_model_turns": None,
        "baseline_rate_limited_calls": None,
        "candidate_rate_limited_calls": None,
        "every_rollout_completed": None,
        "economics_source": "unavailable",
        "cost_usd": None,
        "cost_provenance": CostProvenance.UNAVAILABLE,
        "derived_cost": None,
        "cost_unavailable_reason": "This run wrote no signed execution record.",
        "decision": "accepted",
        "proof_grade": "P1",
        "verification_status": "verified_offline",
        "caveats": [
            PresentationCaveat(code="no_server_upload", severity="info", text="Nothing")
        ],
        "next_actions": [
            NextAction(
                id="verify_proof",
                label="Verify this run's local proof",
                reason=None,
                cli=["techtree", "proof", "verify", "run_" + "0" * 32],
                hermes_tool=None,
                hermes_args=None,
                requires_user_confirmation=False,
            )
        ],
    }
    base.update(overrides)
    return UpliftPresentationPayload(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------


def test_a_label_loses_its_escape_sequences() -> None:
    assert sanitize_label("\x1b[31mred\x1b[0m") == "red"


def test_a_label_loses_its_control_characters() -> None:
    assert sanitize_label("two\nlines\tapart") == "two lines apart"


def test_a_label_is_bounded() -> None:
    long = "a long Climb title " * 20

    shortened = sanitize_label(long, 20)

    assert len(shortened) <= 20
    assert shortened.endswith("…")


def test_a_label_keeps_ordinary_text_unchanged() -> None:
    assert sanitize_label("Techtree Hello World") == "Techtree Hello World"


def test_an_error_summary_drops_the_traceback() -> None:
    summary = sanitize_error_summary(
        NormalizedExecutionError(
            type="TimeoutError",
            message="the subject did not answer",
            traceback='File "/Users/someone/secret.py", line 3, in run',
        )
    )

    assert summary == "TimeoutError: the subject did not answer"


def test_an_error_summary_is_bounded_and_flat() -> None:
    summary = sanitize_error_summary(
        NormalizedExecutionError(type="RuntimeError", message="a\n" * 500),
        maximum=40,
    )

    assert len(summary) <= 40
    assert "\n" not in summary


# ---------------------------------------------------------------------------
# The payload walk
# ---------------------------------------------------------------------------


def test_a_clean_payload_passes() -> None:
    ensure_no_hidden_task_material(payload())


def test_a_payload_carrying_an_escape_sequence_is_refused() -> None:
    with pytest.raises(ValidationError) as raised:
        ensure_no_hidden_task_material(payload(campaign_title="\x1b[31mA Climb"))

    assert raised.value.code == PRESENTATION_REDACTION_FAILED
    assert raised.value.details["field"] == "campaign_title"


def test_a_payload_naming_a_private_path_is_refused() -> None:
    with pytest.raises(ValidationError) as raised:
        ensure_no_hidden_task_material(
            payload(
                caveats=[
                    PresentationCaveat(
                        code="path",
                        severity="info",
                        text="see /Users/someone/.techtree/runs for the evidence",
                    )
                ]
            )
        )

    assert raised.value.code == PRESENTATION_REDACTION_FAILED


def test_the_walk_reaches_a_nested_field() -> None:
    """Nested and listed strings are checked, not only the top level."""
    with pytest.raises(ValidationError) as raised:
        ensure_no_hidden_task_material(
            payload(
                task_rows=[
                    TaskResultRow(
                        position=0,
                        task_label="task 01 \x1b[5m",
                        baseline_score=0.0,
                        candidate_score=1.0,
                        delta=1.0,
                        outcome="win",
                    )
                ]
            )
        )

    assert raised.value.details["field"] == "task_rows[0].task_label"
