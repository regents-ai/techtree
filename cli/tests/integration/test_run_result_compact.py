"""What a phone or a gateway carries, and what ``proof verify`` answers.

Spec sections 7.16, 7.12 and 7.21.

The compact rendering is what a host agent forwards into a chat, so it is
checked for the two ways that channel goes wrong: an escape sequence nothing
there can draw, and a summary that quotes an uplift without the qualifications
that bound it.

``techtree proof verify`` is checked in the same file because it is the command
the compact rendering points at. It runs against a directory, needs nothing
else, and reports a broken proof as a typed failure with an exit code rather
than as a printed remark.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from fixtures.receipts.staged import RecordedEvidenceExecutor, staged_recorded_run
from fixtures.runs.support import run_cli
from techtree.canonical import canonical_json_bytes
from techtree.errors import EXIT_OK, EXIT_VERIFICATION
from techtree.paths import paths_from_root
from techtree.presentation.compact import UNVERIFIED_HEADLINE
from techtree.receipts.bundle import (
    PROOF_BUNDLE_INVALID,
    REPORT_FILENAME,
    proof_bundle_dir,
)
from techtree.runs.validation import PublisherFixtureValidationProvider
from techtree.worker.execute import execute_run

pytestmark = pytest.mark.integration

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


@pytest.fixture(scope="module")
def finished(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
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
    return {"home": home, "run_id": run.run_id, "paths": run.paths}


def compact(finished: dict[str, Any], *arguments: str) -> str:
    result = run_cli(
        finished["home"],
        "run",
        "result",
        finished["run_id"],
        "--format",
        "compact",
        *arguments,
        machine=False,
    )
    assert result.exit_code == EXIT_OK, result.stderr
    return result.stdout


def piped(finished: dict[str, Any], *arguments: str) -> str:
    """Ask for the result the way a script does: no format, nothing at a terminal."""
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
# The gateway rendering
# ---------------------------------------------------------------------------


def test_the_compact_result_leads_with_the_measurement(
    finished: dict[str, Any],
) -> None:
    text = " ".join(compact(finished).split())

    # Tickets e83 and 637: what the run established, then how much of the task
    # family is still failing. Ticket of9's counts and the mean they come from
    # stay in the same breath, one line underneath.
    assert text.startswith(
        "**Improved on this development task family — Solved 24 of 36 · "
        "12 still failing · 0 regressions**"
    )
    assert "- Not broad-capability evidence" in text
    assert "- Tasks: 0 of 36 → 24 of 36 (+24), mean 0.000 → 0.667 (+0.667)" in text
    assert "win, " not in text
    assert "threshold" not in text


def test_the_compact_result_names_the_proof_beside_the_numbers(
    finished: dict[str, Any],
) -> None:
    text = compact(finished)

    assert "- Proof: local P1, signature verified offline" in text
    assert "- Raw episodes: retained locally; not uploaded" in text


def test_the_compact_result_keeps_the_warnings(finished: dict[str, Any]) -> None:
    text = " ".join(compact(finished).split())

    assert "The comparison is controlled with warnings" in text
    assert "Nobody has independently reproduced this comparison" in text


def test_the_compact_result_carries_no_escape_sequences(
    finished: dict[str, Any],
) -> None:
    assert ANSI.search(compact(finished)) is None
    assert "\x1b" not in compact(finished)


def test_the_compact_result_is_short_enough_to_send(
    finished: dict[str, Any],
) -> None:
    """A phone message, not a terminal dump.

    The budget has moved four times. Decisions document 0007 R6 added the
    cost and its provenance, decisions document 0009 added the sentence saying
    the task family is a toy introductory one, the recorded evidence became a
    thirty-six task comparison, which spends a few more lines on the task table
    the renderer caps at five rows, and decisions document 0019 section 3 added
    the two statements this channel was missing: that everything except the
    Skill was the same on both sides, and how long each side took. All of them
    are things the reader is owed in the channel a number is most likely to be
    quoted out of, so they are paid for out of the budget rather than out of
    honesty.

    What the bound is really protecting is that the table cannot grow with the
    membership: thirty-six tasks render in the same handful of rows two did.
    """
    text = compact(finished)

    assert len(text.splitlines()) < 56


def test_a_piped_reader_who_asks_for_every_task_is_given_them(
    finished: dict[str, Any],
) -> None:
    """techtree-python-fg1. The command's own next action tells a script to ask.

    Nothing that reads this product is at a terminal, so the flag being real in
    the terminal rendering alone was the flag not being real at all.
    """
    default = piped(finished)
    everything = piped(finished, "--show-tasks", "all")

    assert everything != default
    assert len(default) < len(everything)
    assert default.count("(WIN)") == 5
    assert everything.count("(WIN)") == 24
    assert everything.count("(TIE)") == 12


def test_the_compact_result_shows_only_what_was_asked_for(
    finished: dict[str, Any],
) -> None:
    none = compact(finished, "--show-tasks", "none")
    regressions = compact(finished, "--show-tasks", "regressions")

    # This run has no losses, so both of these have no table to print.
    assert "(WIN)" not in none
    assert "Changed tasks" not in none
    assert "All 36 tasks:" not in none
    assert "(WIN)" not in regressions
    assert "Regressions" not in regressions
    # Cutting the table never cuts a qualification.
    assert "The comparison is controlled with warnings" in " ".join(none.split())


def test_the_compact_result_offers_one_next_step_in_words(
    finished: dict[str, Any],
) -> None:
    assert "Next: I can show every task locally" in compact(finished)


# ---------------------------------------------------------------------------
# techtree proof verify
# ---------------------------------------------------------------------------


def test_the_finished_result_offers_publishing(finished: dict[str, Any]) -> None:
    """Decisions 0038: a finished, verified result offers publishing.

    The envelope carries at most three actions, so this is also the check that
    the offer is one of the three a caller is actually handed rather than one
    that was thought of and then truncated away.
    """
    result = run_cli(finished["home"], "run", "result", finished["run_id"])
    envelope = result.envelope()

    offer = next(
        action for action in envelope["next_actions"] if action["id"] == "publish_run"
    )
    assert offer["cli"] == ["techtree", "proof", "publish", finished["run_id"]]
    assert offer["requires_user_confirmation"] is True


def test_a_result_nobody_verified_offers_no_publishing(
    finished: dict[str, Any],
) -> None:
    """``--no-verify`` checks nothing, so it establishes nothing to publish on."""
    result = run_cli(
        finished["home"], "run", "result", finished["run_id"], "--no-verify"
    )

    identifiers = [action["id"] for action in result.envelope()["next_actions"]]
    assert "publish_run" not in identifiers


def test_verifying_a_run_by_identifier(finished: dict[str, Any]) -> None:
    result = run_cli(finished["home"], "proof", "verify", finished["run_id"])
    envelope = result.envelope()

    assert result.exit_code == EXIT_OK
    assert envelope["ok"] is True
    assert envelope["data"]["verified"] is True
    assert envelope["data"]["kind"] == "bundle"
    # Decision 0024 section 7: a verified proof still names something to do
    # next. Decisions 0038 adds the offer to publish, for a verified run whose
    # own report says it may be, and it comes first because it is the step the
    # verification has just made available.
    assert [action["id"] for action in envelope["next_actions"]] == [
        "publish_run",
        "proof_checks",
    ]


def test_verifying_a_bundle_directory_anywhere(
    finished: dict[str, Any], tmp_path: Path
) -> None:
    """Offline and portable: a bundle carried elsewhere still checks out."""
    carried = tmp_path / "carried"
    shutil.copytree(
        proof_bundle_dir(finished["paths"].run_dir(finished["run_id"])), carried
    )

    result = run_cli(tmp_path / "empty-home", "proof", "verify", str(carried))

    assert result.exit_code == EXIT_OK
    assert result.envelope()["data"]["verified"] is True


def test_verifying_one_signed_report_file(finished: dict[str, Any]) -> None:
    report = (
        proof_bundle_dir(finished["paths"].run_dir(finished["run_id"]))
        / REPORT_FILENAME
    )

    result = run_cli(finished["home"], "proof", "verify", str(report))

    assert result.exit_code == EXIT_OK
    assert result.envelope()["data"]["kind"] == "report"


def test_the_human_verification_keeps_the_five_answers_apart(
    finished: dict[str, Any],
) -> None:
    result = run_cli(
        finished["home"], "proof", "verify", finished["run_id"], machine=False
    )
    text = " ".join(result.stdout.split())

    assert "Cryptographic integrity" in text
    assert "Scientific comparison" in text
    assert "Participant attestation" in text
    assert "No independent reproduction" in text
    assert "Not published" in text


def test_a_tampered_proof_fails_with_the_documented_exit_code(
    finished: dict[str, Any], tmp_path: Path
) -> None:
    tampered = tmp_path / "tampered"
    shutil.copytree(
        proof_bundle_dir(finished["paths"].run_dir(finished["run_id"])), tampered
    )
    document = json.loads((tampered / REPORT_FILENAME).read_text(encoding="utf-8"))
    document["payload"]["primary_result"]["candidate_mean"] = 0.0
    (tampered / REPORT_FILENAME).write_bytes(canonical_json_bytes(document))

    result = run_cli(tmp_path / "empty-home", "proof", "verify", str(tampered))
    envelope = result.envelope()

    assert result.exit_code == EXIT_VERIFICATION
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == PROOF_BUNDLE_INVALID
    assert envelope["data"]["verified"] is False
    assert envelope["error"]["details"]["failed_checks"]


def test_a_result_whose_proof_was_tampered_with_fails_the_command(
    finished: dict[str, Any], tmp_path: Path
) -> None:
    """The report is still shown; the exit code says not to believe it."""
    home = tmp_path / "tampered-home"
    shutil.copytree(finished["home"], home)
    bundle = proof_bundle_dir(paths_from_root(home).run_dir(finished["run_id"]))
    document = json.loads((bundle / REPORT_FILENAME).read_text(encoding="utf-8"))
    document["payload"]["primary_result"]["candidate_mean"] = 0.5
    (bundle / REPORT_FILENAME).write_bytes(canonical_json_bytes(document))

    result = run_cli(home, "run", "result", finished["run_id"])
    envelope = result.envelope()

    assert result.exit_code == EXIT_VERIFICATION
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == PROOF_BUNDLE_INVALID
    assert envelope["data"]["presentation"]["verification_status"] == (
        "verification_failed"
    )


def test_the_compact_rendering_of_a_broken_proof_leads_with_the_warning(
    finished: dict[str, Any], tmp_path: Path
) -> None:
    home = tmp_path / "tampered-compact-home"
    shutil.copytree(finished["home"], home)
    bundle = proof_bundle_dir(paths_from_root(home).run_dir(finished["run_id"]))
    document = json.loads((bundle / REPORT_FILENAME).read_text(encoding="utf-8"))
    document["payload"]["primary_result"]["candidate_mean"] = 0.5
    (bundle / REPORT_FILENAME).write_bytes(canonical_json_bytes(document))

    result = run_cli(
        home, "run", "result", finished["run_id"], "--format", "compact", machine=False
    )

    assert result.stdout.startswith(UNVERIFIED_HEADLINE)


def test_verifying_something_that_is_not_there_says_so(tmp_path: Path) -> None:
    result = run_cli(tmp_path / "empty-home", "proof", "verify", "run_" + "0" * 32)

    assert result.exit_code != EXIT_OK
    assert result.envelope()["error"]["code"] == "proof_target_not_found"
