"""What the two channels draw. Spec sections 7.15 and 7.16.

Both renderers are pure functions of one payload, so both are tested the way a
reader meets them: by rendering and reading the text.

Three properties matter more than the layout.

*Nothing is carried by colour alone.* Every outcome has a word, every caveat
has its severity in words, and a terminal with no colour loses only decoration.

*The gateway rendering is bounded and free of escape sequences.* A phone
message with an ANSI sequence in it is a broken message, and a twenty-row table
in one is unreadable.

*Neither channel drops a warning.* Room is made by cutting the table, never by
cutting a qualification.
"""

from __future__ import annotations

import io
import re

import pytest
from rich.console import Console

from techtree.models.cli import NextAction
from techtree.presentation.build import FIRST_RESULT_LABEL, SECOND_RESULT_LABEL
from techtree.presentation.compact import (
    UNVERIFIED_HEADLINE,
    render_uplift_markdown,
)
from techtree.presentation.models import (
    PRESENTATION_SCHEMA_VERSION,
    EconomicsSource,
    PresentationCaveat,
    SkillSummary,
    TaskResultRow,
    UpliftPresentationPayload,
)
from techtree.presentation.rich import TaskDisplay, render_uplift_console, verdict_line
from techtree.receipts.execution import CostProvenance

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def rows(count: int) -> list[TaskResultRow]:
    """Return a mixed table: one regression, several wins, the rest ties."""
    built: list[TaskResultRow] = []
    for position in range(count):
        if position == 0:
            baseline, candidate, outcome = 1.0, 0.0, "loss"
        elif position % 2 == 1:
            baseline, candidate, outcome = 0.0, 1.0, "win"
        else:
            baseline, candidate, outcome = 0.0, 0.0, "tie"
        built.append(
            TaskResultRow(
                position=position,
                task_label=f"task {position + 1:02d} · abcdef{position:02d}",
                baseline_score=baseline,
                candidate_score=candidate,
                delta=candidate - baseline,
                outcome=outcome,  # type: ignore[arg-type]
            )
        )
    return built


def payload(
    *,
    task_count: int = 20,
    comparison_label: str = "No tested Skill → Skill v1",
    decision: str = "accepted",
    proof_grade: str = "P1",
    verification_status: str = "verified_offline",
    economics_source: EconomicsSource = "unavailable",
    baseline_tokens: int | None = None,
    candidate_tokens: int | None = None,
    baseline_seconds: float | None = None,
    candidate_seconds: float | None = None,
    cost_usd: float | None = None,
    cost_provenance: CostProvenance = CostProvenance.UNAVAILABLE,
) -> UpliftPresentationPayload:
    table = rows(task_count)
    return UpliftPresentationPayload(
        schema_version=PRESENTATION_SCHEMA_VERSION,
        run_id="run_" + "0" * 32,
        campaign_title="Techtree Hello World",
        comparison_label=comparison_label,
        baseline_skill=SkillSummary(
            label="No tested Skill", root_digest=None, file_count=0, total_bytes=0
        ),
        candidate_skill=SkillSummary(
            label="branch-code-v1",
            root_digest=f"sha256:{'a' * 64}",
            file_count=2,
            total_bytes=3072,
        ),
        baseline_score=0.05,
        candidate_score=0.45,
        absolute_delta=0.4,
        relative_delta=8.0,
        wins=sum(1 for row in table if row.outcome == "win"),
        losses=sum(1 for row in table if row.outcome == "loss"),
        ties=sum(1 for row in table if row.outcome == "tie"),
        task_rows=table,
        baseline_tokens=baseline_tokens,
        candidate_tokens=candidate_tokens,
        baseline_seconds=baseline_seconds,
        candidate_seconds=candidate_seconds,
        economics_source=economics_source,
        cost_usd=cost_usd,
        cost_provenance=cost_provenance,
        decision=decision,
        proof_grade=proof_grade,
        verification_status=verification_status,
        caveats=[
            PresentationCaveat(
                code="comparison_controlled_with_warnings",
                severity="warning",
                text="The comparison is controlled with warnings.",
            ),
            PresentationCaveat(
                code="no_server_upload",
                severity="info",
                text="Nothing was uploaded.",
            ),
        ],
        next_actions=[
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
    )


def rendered(
    value: UpliftPresentationPayload,
    *,
    show_tasks: TaskDisplay = TaskDisplay.CHANGED,
    color: bool = False,
    width: int = 100,
) -> str:
    output = io.StringIO()
    console = Console(
        file=output,
        width=width,
        no_color=not color,
        force_terminal=color,
        highlight=False,
        emoji=False,
        markup=False,
    )
    render_uplift_console(value, console, show_tasks=show_tasks)
    return output.getvalue()


# ---------------------------------------------------------------------------
# The terminal
# ---------------------------------------------------------------------------


def test_the_header_says_what_was_compared_and_how_much_it_is_worth() -> None:
    text = rendered(payload())
    lines = text.splitlines()

    assert lines[0] == "Techtree Hello World"
    assert lines[1] == "No tested Skill → Skill v1"
    assert lines[2] == "[P1 · local proof verified offline]"


def test_the_outcomes_are_words_rather_than_colours() -> None:
    text = rendered(payload(), show_tasks=TaskDisplay.ALL)

    assert "WIN" in text
    assert "LOSS" in text
    assert "TIE" in text


def test_a_coloured_rendering_says_the_same_words() -> None:
    """Colour is decoration: stripping it loses nothing a reader needs."""
    plain = rendered(payload())
    coloured = ANSI.sub("", rendered(payload(), color=True))

    assert coloured == plain


def test_no_escape_sequence_survives_a_plain_console() -> None:
    assert ANSI.search(rendered(payload())) is None


def test_the_same_payload_renders_the_same_bytes() -> None:
    assert rendered(payload()) == rendered(payload())


def test_regressions_are_shown_first() -> None:
    text = rendered(payload(), show_tasks=TaskDisplay.ALL)
    body = text[text.index("Task ") :]

    assert body.index("LOSS") < body.index("WIN")


@pytest.mark.parametrize(
    ("show", "expected"),
    [
        (TaskDisplay.ALL, 20),
        (TaskDisplay.CHANGED, 11),
        (TaskDisplay.REGRESSIONS, 1),
        (TaskDisplay.NONE, 0),
    ],
)
def test_the_reader_chooses_how_much_of_the_table_to_see(
    show: TaskDisplay, expected: int
) -> None:
    text = rendered(payload(), show_tasks=show)

    assert len(re.findall(r"task \d\d · ", text)) == expected


def test_a_filtered_table_says_that_it_is_filtered() -> None:
    text = rendered(payload(), show_tasks=TaskDisplay.REGRESSIONS)

    assert "Showing 1 of 20 tasks" in text


def test_the_verdict_is_a_sentence_rather_than_a_status_word() -> None:
    assert verdict_line(payload()).startswith("Accepted:")
    assert "evidence about the Skill" in verdict_line(payload(decision="rejected"))
    assert verdict_line(payload(decision="development_only")).startswith("No verdict")


def test_what_changed_names_both_sides_and_says_the_rest_was_held_fixed() -> None:
    text = rendered(payload())

    assert "What changed" in text
    assert "branch-code-v1" in text
    assert "held fixed" in text


def test_the_caveats_are_introduced_by_severity_in_words() -> None:
    text = rendered(payload())

    assert "Warning: The comparison is controlled with warnings." in text
    assert "Note: Nothing was uploaded." in text


def test_a_failed_verification_is_visible_in_the_badge() -> None:
    text = rendered(payload(verification_status="verification_failed"))

    assert "LOCAL PROOF DID NOT VERIFY" in text.splitlines()[2]


def test_efficiency_says_it_was_not_recorded_rather_than_showing_zero() -> None:
    """An unknown number is said to be unknown, never drawn as a zero."""
    text = rendered(payload())

    assert "Tokens   not recorded for this run" in text
    assert "Time     not recorded for this run" in text
    assert "Cost     unavailable" in text
    assert "Source   nothing recorded it" in text
    assert "$" not in text


def test_efficiency_shows_what_the_execution_record_recorded() -> None:
    """Decisions 0007 R6: tokens, time and cost, from the signed record."""
    text = rendered(
        payload(
            economics_source="comparison_execution_record",
            baseline_tokens=1_186_432,
            candidate_tokens=1_204_771,
            baseline_seconds=612.0,
            candidate_seconds=598.0,
            cost_usd=4.1,
            cost_provenance=CostProvenance.PROVIDER_REPORTED,
        )
    )

    assert "Tokens   baseline 1186432, candidate 1204771" in text
    assert "Time     baseline 612.0s, candidate 598.0s" in text
    assert "Cost     $4.10 (reported by the provider)" in text
    assert "Source   this run's signed execution record" in text


@pytest.mark.parametrize(
    ("provenance", "phrase"),
    [
        (CostProvenance.PROVIDER_REPORTED, "reported by the provider"),
        (CostProvenance.COMPUTED_FROM_PINNED_PRICE, "computed from the pinned price"),
        (CostProvenance.ESTIMATED, "estimated, not billed"),
    ],
)
def test_every_cost_figure_is_shown_with_where_it_came_from(
    provenance: CostProvenance, phrase: str
) -> None:
    """An estimate is never allowed to read as a figure the provider billed."""
    text = rendered(
        payload(
            economics_source="comparison_execution_record",
            cost_usd=4.1,
            cost_provenance=provenance,
        )
    )

    assert f"Cost     $4.10 ({phrase})" in text
    if provenance is not CostProvenance.PROVIDER_REPORTED:
        assert "reported by the provider" not in text


# ---------------------------------------------------------------------------
# The gateway
# ---------------------------------------------------------------------------


def test_the_compact_rendering_carries_no_escape_sequences() -> None:
    assert ANSI.search(render_uplift_markdown(payload())) is None
    assert "\x1b" not in render_uplift_markdown(payload())


def test_the_compact_rendering_leads_with_the_headline_and_the_numbers() -> None:
    first = render_uplift_markdown(payload()).splitlines()[0]

    assert first.startswith("**The Skill met the Campaign's threshold:")
    assert "0.050 → 0.450 (+0.400)" in first


def test_the_compact_rendering_is_bounded() -> None:
    text = render_uplift_markdown(payload(task_count=40))

    assert len(re.findall(r"task \d\d · ", text)) == 5
    assert len(text.splitlines()) < 30


def test_the_compact_rendering_keeps_every_qualification() -> None:
    """Room is made by cutting the table, never by cutting a warning."""
    text = render_uplift_markdown(payload(task_count=40), maximum_task_rows=1)

    assert "The comparison is controlled with warnings." in text


def test_the_compact_rendering_names_the_proof_beside_the_numbers() -> None:
    text = render_uplift_markdown(payload())

    assert "- Proof: local P1, signature verified offline" in text
    assert "- Raw episodes: retained locally; not uploaded" in text


def test_the_compact_rendering_shows_the_regression_first() -> None:
    text = render_uplift_markdown(payload())
    body = text[text.index("Largest changes") :]

    assert body.index("LOSS") < body.index("WIN")


def test_a_result_whose_proof_failed_says_so_before_the_numbers() -> None:
    """The channel a number is most likely to be quoted out of."""
    text = render_uplift_markdown(payload(verification_status="verification_failed"))

    assert text.splitlines()[0] == UNVERIFIED_HEADLINE
    assert "signature DID NOT verify" in text


def test_a_development_only_result_is_not_dressed_up_as_a_verdict() -> None:
    text = render_uplift_markdown(
        payload(
            decision="development_only",
            proof_grade="development_only",
            verification_status="not_verified",
        )
    )

    assert text.startswith("**Development-only result, no verdict")
    assert "signature not checked" in text


def test_the_same_payload_renders_the_same_markdown() -> None:
    assert render_uplift_markdown(payload()) == render_uplift_markdown(payload())


@pytest.mark.parametrize(
    "label",
    [FIRST_RESULT_LABEL, SECOND_RESULT_LABEL],
    ids=["first_result", "second_result"],
)
def test_both_channels_name_the_climb_and_which_result_this_is(label: str) -> None:
    """Decisions 0009: the same two names reach a terminal and a gateway.

    A reader who sees only one of the two channels still has to be able to say
    which Climb produced the numbers and whether this is the first receipt or
    the second iteration. The rich renderer leads with both; the compact one
    carries them on one line because it has only a handful to spend.
    """
    subject = payload(comparison_label=label)

    terminal = rendered(subject).splitlines()
    assert terminal[0] == "Techtree Hello World"
    assert terminal[1] == label

    gateway = render_uplift_markdown(subject)
    assert f"- Techtree Hello World — {label}" in gateway
    assert ANSI.search(gateway) is None
