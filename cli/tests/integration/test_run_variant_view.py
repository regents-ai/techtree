"""Watching a comparison from the outside. Spec section 6.20.

A concurrent Campaign has two positions at once, and the two commands a caller
uses to follow it have to say so honestly: status exposes both sides' episode
counts to a program and shows them side by side to a person, and logs can be
pointed at one side's evaluation rather than at the worker's own output.

Four rules are tested here, and each of them is a rule about not overstating
what is known.

*No delta before both sides finish.* A partial mean of a partial run reads like
an answer. The score column says provisional and the table carries the sentence
that explains why.

*A variant's log is the engine's log.* Never the child's captured stdout, which
with rich output disabled is a dump of every subject transcript.

*A variant that has not started says so.* Asking for a log that does not exist
yet is an ordinary answer, not a crash.

*A run that has ended reports no position.* Progress measures work in flight
through the phase a run is in, and a run that has finished has none. The phase
already says what happened, so the row is left out rather than filled in.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fixtures.runs.support import execute_in_process, run_cli, run_harness
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
from techtree.verifiers.outputs import EVAL_LOG_PATH

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
    log = output_dir / EVAL_LOG_PATH
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(text, encoding="utf-8")


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


def test_a_run_still_going_reports_where_it_has_got_to(
    comparison: RunningRun,
) -> None:
    """techtree-python-1sl. The row exists for exactly as long as it means something."""
    paths, run_id = comparison

    result = run_cli(paths.root, "run", "status", run_id, machine=False)

    assert result.exit_code == EXIT_OK
    assert "Progress" in result.stdout


def test_a_run_that_has_ended_reports_no_progress_at_all(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """techtree-python-1sl. A finished run used to report that it never started.

    Entering a phase discards the position inside the last one, so a finished
    run holds no progress, and the row read as though the run had never begun
    while the phase beside it said it had completed. There is no number to put
    there and no completion to claim; the phase has already said how it ended.
    """
    home = tmp_path_factory.mktemp("techtree-home")
    harness = run_harness(home)
    run_id = harness.start().state.run_id
    execute_in_process(harness, run_id)

    result = run_cli(harness.paths.root, "run", "status", run_id, machine=False)

    assert result.exit_code == EXIT_OK
    assert "completed" in result.stdout
    assert "Progress" not in result.stdout
    # The machine envelope is a contract and says exactly what it always said:
    # a caller reading `phase` already has the answer.
    machine = run_cli(harness.paths.root, "run", "status", run_id).data()
    assert machine["progress"] is None
    assert machine["terminal"] is True


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

    assert Path(EVAL_LOG_PATH).name not in result.stdout


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


# ---------------------------------------------------------------------------
# Watching, rather than asking once
# ---------------------------------------------------------------------------


def test_the_watch_line_carries_both_sides_and_no_score() -> None:
    """A watcher following a comparison sees two counts. Spec section 6.20.

    One number could only be one side's or a sum of both, and a reader seeing
    "18 / 72" cannot tell a comparison running evenly from one whose candidate
    never started. No score appears on the line at all: a watch line scrolling
    past is the easiest place for a partial mean to be mistaken for the answer.
    """
    from techtree.cli.commands.run import PROVISIONAL_SCORE as _SCORE
    from techtree.cli.commands.run import watch_line

    line = watch_line(_watching_payload(baseline=7, candidate=8))

    assert "baseline 7/20" in line
    assert "candidate 8/20" in line
    assert RunPhase.RUNNING_VARIANTS.value in line
    assert _SCORE not in line


def test_the_watch_line_says_which_side_has_not_started() -> None:
    """A missing variant is named as not started, never rendered as zero of zero."""
    from techtree.cli.commands.run import watch_line

    line = watch_line(_watching_payload(baseline=3, candidate=None))

    assert "baseline 3/20" in line
    assert "candidate not started" in line


def test_a_sequential_run_still_shows_one_position(tmp_path: Path) -> None:
    """The concurrent line replaces the sequential one only when there is one."""
    from techtree.cli.commands.run import watch_line

    payload = _watching_payload(baseline=None, candidate=None)
    line = watch_line(payload.model_copy(update={"phase": RunPhase.RUNNING_BASELINE}))

    assert line == RunPhase.RUNNING_BASELINE.value


def _watching_payload(*, baseline: int | None, candidate: int | None):  # type: ignore[no-untyped-def]
    """Build the status payload a watcher would have in hand."""
    from datetime import UTC, datetime

    from techtree.cli.commands.run import RunStatusPayload
    from techtree.models.run import PublicRunState, VariantProgress

    progress = {}
    for name, completed in (("baseline", baseline), ("candidate", candidate)):
        if completed is None:
            continue
        progress[name] = VariantProgress(
            variant=name,  # type: ignore[arg-type]
            completed=completed,
            total=20,
            running=1,
            errored=0,
            state="running",
        )
    return RunStatusPayload(
        run_id="run_00000000000000000000000000000001",
        phase=RunPhase.RUNNING_VARIANTS,
        public_state=PublicRunState.RUNNING,
        state_digest="sha256:" + "00" * 32,
        sequence=9,
        updated_at=datetime(2026, 8, 13, tzinfo=UTC),
        progress=None,
        variant_progress=progress,
        worker_pid=1234,
        worker_alive=True,
        heartbeat_at=None,
        heartbeat_age_seconds=None,
        heartbeat_stale=False,
        cancel_requested_at=None,
        terminal=False,
        result_available=False,
        result_digest=None,
        error=None,
        fake_executor=False,
    )
