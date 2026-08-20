"""What may reach a rendering. Spec section 7.17.

The functions here are the last gate between a run's evidence and something a
person or a gateway sees, so each test is a specific thing that must not get
through: a credential, an escape sequence, a private path, a traceback carrying
environment values.

The payload walk is the part worth insisting on. It checks every string the
payload holds rather than the fields somebody remembered to check, which is
what keeps a field added next year from being the one that leaks.
"""

from __future__ import annotations

import pytest

from techtree.errors import REDACTED, ValidationError
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
    ensure_no_secret_patterns,
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
        "baseline_tokens": None,
        "candidate_tokens": None,
        "baseline_seconds": None,
        "candidate_seconds": None,
        "economics_source": "unavailable",
        "cost_usd": None,
        "cost_provenance": CostProvenance.UNAVAILABLE,
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


def test_a_label_redacts_something_that_looks_like_a_key() -> None:
    assert REDACTED in sanitize_label("api_key=sk-abcdefghijklmnopqrstuvwxyz012345")


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
# Secrets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "TECHTREE_MODEL_API_KEY=sk-1234567890abcdefghij",
        "Authorization: Bearer abcdefghijklmnop",
        # Long enough to be a password rather than the next word of a
        # sentence, which is the line the scrubber draws on an unquoted value.
        "password: hunter2hunter2",
    ],
)
def test_a_credential_shaped_value_is_refused(value: str) -> None:
    with pytest.raises(ValidationError) as raised:
        ensure_no_secret_patterns(value)

    assert raised.value.code == PRESENTATION_REDACTION_FAILED


def test_an_error_about_a_credential_does_not_repeat_it() -> None:
    secret = "sk-abcdefghijklmnopqrstuvwxyz"

    with pytest.raises(ValidationError) as raised:
        ensure_no_secret_patterns(f"api_key={secret}")

    assert secret not in raised.value.message
    assert secret not in str(raised.value.details)


def test_a_digest_is_not_mistaken_for_a_secret() -> None:
    ensure_no_secret_patterns(f"sha256:{'a' * 64}")


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


def test_a_payload_carrying_a_credential_is_refused() -> None:
    with pytest.raises(ValidationError):
        ensure_no_hidden_task_material(
            payload(
                caveats=[
                    PresentationCaveat(
                        code="leak",
                        severity="info",
                        text="api_key=sk-abcdefghijklmnopqrstuvwxyz012345",
                    )
                ]
            )
        )


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
