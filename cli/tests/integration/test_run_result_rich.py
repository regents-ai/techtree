"""What a person sees when a real run finishes. Spec section 7.21.

The run is real, its report is signed, and the command is the one an operator
types. What is under test is the honesty of the answer rather than its layout:
the grade is explained in the only words decisions document 0005 permits, the
comparison's warnings are in front of the reader, the limits of a local proof
are stated, and nothing anywhere claims the result was reproduced by anybody.

The machine envelope is checked in the same file, because a host agent reading
JSON is the caller most likely to quote a number without its qualifications.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from fixtures.receipts.staged import RecordedEvidenceExecutor, staged_recorded_run
from fixtures.runs.support import run_cli
from techtree.errors import EXIT_OK
from techtree.presentation.build import P1_MEANING
from techtree.runs.validation import PublisherFixtureValidationProvider
from techtree.worker.execute import execute_run

pytestmark = pytest.mark.integration

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


@pytest.fixture(scope="module")
def finished(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """One completed real run, reused by every test in this module."""
    home = tmp_path_factory.mktemp("home")
    run = staged_recorded_run(home)
    execute_run(
        run.run_id,
        paths=run.paths,
        executor_factory=lambda request: RecordedEvidenceExecutor(
            pair=run.pair, paths=run.paths
        ),
        validation_provider_factory=lambda request: (
            PublisherFixtureValidationProvider()
        ),
    )
    return {"home": home, "run_id": run.run_id}


def flat(text: str) -> str:
    """Collapse the console's own line wrapping, which is not the content.

    Rich wraps to the terminal width, so a sentence a test cares about is a
    sentence rather than a line. Flattening keeps the assertions about wording.
    """
    return " ".join(text.split())


def human(finished: dict[str, Any], *arguments: str) -> str:
    result = run_cli(
        finished["home"],
        "run",
        "result",
        finished["run_id"],
        *arguments,
        machine=False,
    )
    assert result.exit_code == EXIT_OK, result.stderr
    return result.stdout


# ---------------------------------------------------------------------------
# The rich rendering
# ---------------------------------------------------------------------------


def test_the_result_shows_the_comparison_and_the_measurement(
    finished: dict[str, Any],
) -> None:
    text = human(finished, "--format", "rich")

    assert "Techtree Hello World" in text
    assert "Hello World Uplift Receipt" in text
    assert "No tested Skill" in text
    assert "Baseline" in text
    assert "Candidate" in text
    assert "Solved 24 of 36 · 12 still failing · 0 regressions" in text


def test_the_result_leads_with_what_the_run_established(
    finished: dict[str, Any],
) -> None:
    """Tickets e83 and 637. The iteration frame, not a benchmark that was passed."""
    text = human(finished, "--format", "rich")

    assert "Result  Improved on this development task family" in text
    assert "Not broad-capability evidence" in text
    assert "threshold" not in text
    assert "WIN / " not in text


def test_the_result_explains_p1_in_the_permitted_words(
    finished: dict[str, Any],
) -> None:
    text = human(finished, "--format", "rich")

    assert "[P1 · local proof verified offline]" in text
    assert P1_MEANING in flat(text)


def test_the_result_never_claims_independent_reproduction(
    finished: dict[str, Any],
) -> None:
    """The one sentence this product must never print."""
    text = human(finished, "--format", "rich")

    flattened = flat(text)

    # The phrase appears once, as the denial it is.
    assert flattened.count("independently reproduced") == 1
    assert "Nobody has independently reproduced this comparison" in flattened


def test_the_result_states_the_limits_of_a_local_proof(
    finished: dict[str, Any],
) -> None:
    text = human(finished, "--format", "rich")

    flattened = flat(text)

    # Decisions 0038: the caveat says what publishing would carry rather than
    # promising that nothing can be sent, because now something can be.
    assert "The raw episodes stay on this machine." in flattened
    assert "never its episodes" in flattened
    assert "No external evidence service is required, used, or contacted." in flattened


def test_the_result_shows_the_comparison_warnings_plainly(
    finished: dict[str, Any],
) -> None:
    """A controlled-with-warnings comparison says so, in words, in the open."""
    text = human(finished, "--format", "rich")

    assert "Warning: The comparison is controlled with warnings" in flat(text)


def test_the_result_says_which_skill_changed_and_that_nothing_else_did(
    finished: dict[str, Any],
) -> None:
    text = human(finished, "--format", "rich")

    assert "hello-world-v1" in text
    assert "No tested Skill → Skill v1" in flat(text)
    assert "Everything else was the same on both sides" in flat(text)
    assert "checked against what the run actually did" in flat(text)


def test_the_task_table_can_be_asked_for_in_full(finished: dict[str, Any]) -> None:
    changed = human(finished, "--format", "rich", "--show-tasks", "changed")
    none = human(finished, "--format", "rich", "--show-tasks", "none")

    assert changed.count("WIN") >= 2
    assert "task 01" not in none


def test_a_piped_human_result_carries_no_escape_sequences(
    finished: dict[str, Any],
) -> None:
    assert ANSI.search(human(finished, "--format", "rich")) is None


def test_the_result_offers_the_next_steps_this_build_can_carry_out(
    finished: dict[str, Any],
) -> None:
    text = human(finished, "--format", "rich")

    assert "techtree proof verify" in text
    assert "--show-tasks all" in text


def test_the_default_rendering_of_a_piped_result_is_the_compact_one(
    finished: dict[str, Any],
) -> None:
    """Spec section 7.21: rich at a terminal, compact when piped."""
    text = human(finished)

    assert text.startswith("**Improved on this development task family")


# ---------------------------------------------------------------------------
# The machine envelope
# ---------------------------------------------------------------------------


def test_the_machine_envelope_carries_the_report_and_the_presentation(
    finished: dict[str, Any],
) -> None:
    result = run_cli(finished["home"], "run", "result", finished["run_id"])
    envelope = result.envelope()

    assert result.exit_code == EXIT_OK
    assert envelope["ok"] is True
    assert envelope["data"]["report"]["proof_grade"] == "P1"
    assert envelope["data"]["presentation"]["verification_status"] == "verified_offline"


def test_the_machine_envelope_carries_every_caveat(
    finished: dict[str, Any],
) -> None:
    envelope = run_cli(finished["home"], "run", "result", finished["run_id"]).envelope()
    codes = {caveat["code"] for caveat in envelope["data"]["presentation"]["caveats"]}

    assert "local_participant_attestation" in codes
    assert "no_independent_reproduction" in codes
    assert "comparison_controlled_with_warnings" in codes


def test_the_machine_envelope_has_no_escape_sequences(
    finished: dict[str, Any],
) -> None:
    result = run_cli(finished["home"], "run", "result", finished["run_id"])

    assert "\x1b" not in result.stdout
    assert ANSI.search(json.dumps(result.envelope())) is None


def test_the_result_can_be_read_without_verifying_the_proof(
    finished: dict[str, Any],
) -> None:
    """``--no-verify`` says "not checked" rather than pretending it checked."""
    envelope = run_cli(
        finished["home"], "run", "result", finished["run_id"], "--no-verify"
    ).envelope()

    assert envelope["data"]["presentation"]["verification_status"] == "not_verified"


def test_the_path_format_says_where_the_proof_is(finished: dict[str, Any]) -> None:
    text = human(finished, "--format", "path")

    assert "proof/" in text
    assert "proof/uplift-report.json" in text
    # Relative to the run directory: a caller already has the run identifier,
    # and an absolute path is host detail.
    assert str(finished["home"]) not in text
