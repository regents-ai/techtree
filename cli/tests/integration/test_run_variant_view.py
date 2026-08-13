"""Watching a comparison from the outside. Spec section 6.20.

A concurrent Campaign has two positions at once, and the two commands a caller
uses to follow it have to say so honestly: status exposes both sides' episode
counts to a program and shows them side by side to a person, and logs can be
pointed at one side's evaluation rather than at the worker's own output.

Three rules are tested here, and each of them is a rule about not overstating
what is known.

*No delta before both sides finish.* A partial mean of a partial run reads like
an answer. The score column says provisional and the table carries the sentence
that explains why.

*A variant's log is the engine's log.* Never the child's captured stdout, which
with rich output disabled is a dump of every subject transcript.

*A variant that has not started says so.* Asking for a log that does not exist
yet is an ordinary answer, not a crash.
"""

from __future__ import annotations

import pytest

from fixtures.runs.support import run_cli, run_harness
from techtree.cli.commands.run import PROVISIONAL_SCORE
from techtree.errors import EXIT_OK
from techtree.models.run import RunPhase
from techtree.paths import TechtreePaths
from techtree.runs.events import (
    DETAIL_COMPLETED,
    DETAIL_ERRORED,
    DETAIL_RUNNING,
    DETAIL_STATE,
    DETAIL_TOTAL,
    DETAIL_VARIANT,
    VARIANT_PROGRESS,
)
from techtree.verifiers.models import RunPaths, VariantName
from techtree.verifiers.outputs import EVAL_LOG_FILENAME

pytestmark = pytest.mark.integration


type RunningRun = tuple[TechtreePaths, str]


@pytest.fixture
def comparison(tmp_path_factory: pytest.TempPathFactory) -> RunningRun:
    """A run projected into the concurrent phase with both sides in flight.

    No worker is launched. These questions are about what the two commands
    report, and a real worker racing to a terminal phase would clear the
    projection out from under them.
    """
    home = tmp_path_factory.mktemp("techtree-home")
    harness = run_harness(home)
    run_id = harness.start().state.run_id
    paths = harness.paths

    store = harness.run_store
    for phase in (RunPhase.VALIDATING_TASKSET, RunPhase.RUNNING_VARIANTS):
        store.append(run_id, phase=phase)
    for variant, completed, state in (
        (VariantName.BASELINE, 7, "running"),
        (VariantName.CANDIDATE, 8, "running"),
    ):
        store.append(
            run_id,
            phase=None,
            kind=VARIANT_PROGRESS,
            details={
                DETAIL_VARIANT: variant.value,
                DETAIL_COMPLETED: completed,
                DETAIL_TOTAL: 20,
                DETAIL_RUNNING: 1,
                DETAIL_ERRORED: 0,
                DETAIL_STATE: state,
            },
        )
    return paths, run_id


def _unwrapped(text: str) -> str:
    """Return console output with its soft line wrapping removed."""
    return " ".join(line.strip() for line in text.splitlines())


def write_variant_log(paths: TechtreePaths, run_id: str, text: str) -> None:
    """Put an evaluation log where a variant's child would have left one."""
    run_paths = RunPaths.for_run(paths, run_id)
    output_dir = run_paths.variant_output_dir(VariantName.BASELINE)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / EVAL_LOG_FILENAME).write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def test_a_program_reads_both_sides_without_parsing_a_table(
    comparison: RunningRun,
) -> None:
    paths, run_id = comparison

    data = run_cli(paths.root, "run", "status", run_id).data()

    assert data["variant_progress"]["baseline"]["completed"] == 7
    assert data["variant_progress"]["candidate"]["completed"] == 8
    assert data["variant_progress"]["baseline"]["total"] == 20


def test_machine_progress_carries_no_terminal_formatting(
    comparison: RunningRun,
) -> None:
    paths, run_id = comparison

    result = run_cli(paths.root, "run", "status", run_id)

    assert "\x1b[" not in result.stdout


def test_a_person_sees_the_two_sides_beside_each_other(
    comparison: RunningRun,
) -> None:
    paths, run_id = comparison

    result = run_cli(paths.root, "run", "status", run_id, machine=False)

    assert result.exit_code == EXIT_OK
    assert "Baseline" in result.stdout
    assert "Skill candidate" in result.stdout
    assert "7 / 20" in result.stdout
    assert "8 / 20" in result.stdout


def test_no_uplift_is_shown_while_either_side_is_unfinished(
    comparison: RunningRun,
) -> None:
    paths, run_id = comparison

    result = run_cli(paths.root, "run", "status", run_id, machine=False)

    assert PROVISIONAL_SCORE in result.stdout
    assert "provisional until every task completes" in _unwrapped(result.stdout)


def test_a_run_with_no_variants_shows_no_comparison_table(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    home = tmp_path_factory.mktemp("techtree-home")
    harness = run_harness(home)
    run_id = harness.start().state.run_id

    result = run_cli(harness.paths.root, "run", "status", run_id, machine=False)

    assert "Skill candidate" not in result.stdout


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------


def test_one_sides_evaluation_log_can_be_read_on_its_own(
    comparison: RunningRun,
) -> None:
    paths, run_id = comparison
    write_variant_log(paths, run_id, "rollout done: task=0 reward=0.000\n")

    data = run_cli(paths.root, "run", "logs", run_id, "--variant", "baseline").data()

    assert data["lines"] == ["rollout done: task=0 reward=0.000"]


def test_a_variant_log_is_scrubbed_like_every_other_log(
    comparison: RunningRun,
) -> None:
    paths, run_id = comparison
    write_variant_log(paths, run_id, "PRIME_API_KEY=sk-should-never-be-shown\n")

    data = run_cli(paths.root, "run", "logs", run_id, "--variant", "baseline").data()

    assert "sk-should-never-be-shown" not in "\n".join(data["lines"])


def test_a_variant_that_has_not_started_is_an_ordinary_answer(
    comparison: RunningRun,
) -> None:
    paths, run_id = comparison

    envelope = run_cli(
        paths.root, "run", "logs", run_id, "--variant", "candidate"
    ).envelope()

    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "run_logs_unavailable"


def test_the_variant_log_response_never_names_a_file(
    comparison: RunningRun,
) -> None:
    paths, run_id = comparison
    write_variant_log(paths, run_id, "one line\n")

    result = run_cli(paths.root, "run", "logs", run_id, "--variant", "baseline")

    assert EVAL_LOG_FILENAME not in result.stdout


def test_following_a_variant_log_is_refused_rather_than_half_supported(
    comparison: RunningRun,
) -> None:
    paths, run_id = comparison

    envelope = run_cli(
        paths.root,
        "run",
        "logs",
        run_id,
        "--variant",
        "baseline",
        "--follow",
    ).envelope()

    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "run_follow_not_supported_for_variant"
