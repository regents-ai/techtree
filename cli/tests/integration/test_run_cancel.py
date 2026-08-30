"""Stopping a real detached run. Spec PR8 §8.14, §8.17.

Cancellation crosses a process boundary twice: the CLI appends the request to
the journal and signals the worker's process group, and the worker notices at
its next safe point and writes its own terminal event. Neither half can be
observed honestly in one process, so this file uses a real worker and a real
signal throughout.

What is asserted is that the two halves agree — the run ends in ``cancelled``,
not merely ``cancel_requested`` — that asking twice is harmless, and that a run
which has already finished is left exactly as it was. Cancellation inside each
individual executor phase is established deterministically in
``tests/unit/test_fake_executor.py``; what could not be shown there is that the
signal reaches a process this one does not own.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from fixtures.runs.support import (
    bigger_catalog,
    prepare_only,
    run_cli,
    start_through_the_cli,
    wait_for_terminal,
    wait_until,
)
from techtree.errors import EXIT_NOT_FOUND, EXIT_OK, EXIT_USAGE
from techtree.paths import TechtreePaths
from techtree.runs.events import read_events
from techtree.skills.service import PreparedDraft

pytestmark = pytest.mark.integration

#: Long enough to cancel a run that is genuinely in the middle of scoring.
SLOW_TASK_COUNT = 40


@pytest.fixture
def slow_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, TechtreePaths, PreparedDraft]:
    """Prepare a draft whose Campaign takes several seconds to score."""
    catalog = bigger_catalog(
        tmp_path / "catalog", monkeypatch, task_count=SLOW_TASK_COUNT
    )
    home = tmp_path / "home"
    home.mkdir()
    paths, prepared = prepare_only(home, catalog_root=catalog)
    return home, paths, prepared


def _start_and_reach_baseline(home: Path, prepared: PreparedDraft) -> str:
    """Start a run and wait until it is genuinely scoring episodes."""
    run_id = str(start_through_the_cli(home, prepared).data()["run_id"])

    def scoring() -> bool:
        phase = run_cli(home, "run", "status", run_id).data()["phase"]
        return phase in ("running_baseline", "running_candidate")

    wait_until(scoring)
    return run_id


def test_cancelling_a_running_worker_ends_the_run_as_cancelled(
    slow_run: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    home, paths, prepared = slow_run
    run_id = _start_and_reach_baseline(home, prepared)

    cancelled = run_cli(home, "run", "cancel", run_id, "--confirm")

    assert cancelled.exit_code == EXIT_OK
    assert cancelled.data()["outcome"] == "requested"
    final = wait_for_terminal(home, run_id)
    assert final["phase"] == "cancelled"
    assert final["result_available"] is False
    assert not (paths.run_dir(run_id) / "report" / "uplift.json").exists()


def test_the_signal_reaches_the_worker_process_group(
    slow_run: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    """The worker is gone afterwards, which is what the signal was for."""
    home, _, prepared = slow_run
    run_id = _start_and_reach_baseline(home, prepared)
    worker_pid = run_cli(home, "run", "status", run_id).data()["worker_pid"]

    run_cli(home, "run", "cancel", run_id, "--confirm")
    wait_for_terminal(home, run_id)

    wait_until(lambda: not _process_exists(worker_pid))
    assert run_cli(home, "run", "status", run_id).data()["worker_alive"] is False


def test_the_journal_records_the_request_and_the_ending(
    slow_run: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    home, paths, prepared = slow_run
    run_id = _start_and_reach_baseline(home, prepared)

    run_cli(home, "run", "cancel", run_id, "--confirm")
    wait_for_terminal(home, run_id)

    kinds = _event_kinds(paths, run_id)
    assert kinds.count("cancel.requested") == 1
    assert kinds[-1] == "run.cancelled"


def test_asking_twice_is_harmless(
    slow_run: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    home, paths, prepared = slow_run
    run_id = _start_and_reach_baseline(home, prepared)

    first = run_cli(home, "run", "cancel", run_id, "--confirm")
    second = run_cli(home, "run", "cancel", run_id, "--confirm")

    assert first.data()["outcome"] in ("requested", "already_requested")
    assert second.data()["outcome"] in ("already_requested", "already_terminal")
    wait_for_terminal(home, run_id)
    kinds = _event_kinds(paths, run_id)
    assert kinds.count("cancel.requested") == 1


def test_cancelling_a_finished_run_leaves_its_result_alone(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _, prepared = prepare_only(home)
    run_id = start_through_the_cli(home, prepared).data()["run_id"]
    wait_for_terminal(home, run_id)
    before = run_cli(home, "run", "result", run_id).data()

    cancelled = run_cli(home, "run", "cancel", run_id, "--confirm")

    assert cancelled.exit_code == EXIT_OK
    assert cancelled.data()["outcome"] == "already_terminal"
    assert cancelled.data()["phase"] == "completed"
    assert run_cli(home, "run", "result", run_id).data() == before


def test_a_machine_caller_must_confirm(
    tmp_path: Path,
) -> None:
    """Possession of a run identifier is not intent to stop the run."""
    home = tmp_path / "home"
    home.mkdir()
    _, prepared = prepare_only(home)
    run_id = start_through_the_cli(home, prepared).data()["run_id"]

    refused = run_cli(home, "run", "cancel", run_id)

    assert refused.exit_code == EXIT_USAGE
    envelope = refused.envelope()
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "run_cancel_confirmation_required"
    wait_for_terminal(home, run_id)
    assert run_cli(home, "run", "status", run_id).data()["phase"] == "completed"


def test_a_person_who_says_no_leaves_the_run_alone(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _, prepared = prepare_only(home)
    run_id = start_through_the_cli(home, prepared).data()["run_id"]

    refused = run_cli(home, "run", "cancel", run_id, machine=False, stdin="n\n")

    assert refused.exit_code == EXIT_USAGE
    wait_for_terminal(home, run_id)
    assert run_cli(home, "run", "status", run_id).data()["phase"] == "completed"


# ---------------------------------------------------------------------------
# Who is asked, and when
# ---------------------------------------------------------------------------


def test_a_run_that_has_already_ended_is_never_asked_about(tmp_path: Path) -> None:
    """techtree-python-253. There is nothing left to stop, so there is nothing to ask.

    Nothing answers this command's standard input, so a confirmation put to a
    finished run would not merely be pointless: it would be unanswerable, and
    the command would fail where it should have said that the run had ended.
    """
    home = tmp_path / "home"
    home.mkdir()
    _, prepared = prepare_only(home)
    run_id = start_through_the_cli(home, prepared).data()["run_id"]
    wait_for_terminal(home, run_id)

    cancelled = run_cli(home, "run", "cancel", run_id, machine=False)

    assert cancelled.exit_code == EXIT_OK, cancelled.stdout + cancelled.stderr
    assert "Stop run" not in cancelled.stdout
    assert "had already ended in completed" in cancelled.stdout
    assert "A run that has ended cannot be cancelled" in " ".join(
        cancelled.stdout.split()
    )


def test_an_identifier_that_names_no_run_is_never_asked_about(
    tmp_path: Path,
) -> None:
    """techtree-python-253. Answering a question about a run nobody has."""
    home = tmp_path / "home"
    home.mkdir()
    prepare_only(home)

    missing = run_cli(home, "run", "cancel", "run_" + "0" * 32, machine=False)

    assert missing.exit_code == EXIT_NOT_FOUND
    assert "Stop run" not in missing.stdout
    assert "Code: run_not_found" in missing.stdout


def test_a_run_that_is_still_going_is_still_asked_about(
    slow_run: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    """techtree-python-253. Reading the state replaced no question worth asking."""
    home, _, prepared = slow_run
    run_id = _start_and_reach_baseline(home, prepared)

    refused = run_cli(home, "run", "cancel", run_id, machine=False, stdin="n\n")

    assert refused.exit_code == EXIT_USAGE
    assert f"Stop run {run_id}?" in refused.stdout
    assert run_cli(home, "run", "status", run_id).data()["phase"] != "cancelled"
    run_cli(home, "run", "cancel", run_id, "--confirm")
    wait_for_terminal(home, run_id)


def test_a_confirmation_nobody_can_answer_is_a_usage_outcome(
    slow_run: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    """techtree-python-xse. An unanswered question is not a defect in Techtree.

    Standard input is closed, so the prompt reaches end of input the instant it
    is written. That is the same outcome as a person saying no, and reporting
    it as an internal error told the caller the product was broken.
    """
    home, _, prepared = slow_run
    run_id = _start_and_reach_baseline(home, prepared)

    unanswered = run_cli(home, "run", "cancel", run_id, machine=False)

    assert unanswered.exit_code == EXIT_USAGE
    assert "Code: run_cancel_confirmation_required" in unanswered.stdout
    assert "internal_error" not in unanswered.stdout
    assert run_cli(home, "run", "status", run_id).data()["phase"] != "cancelled"
    run_cli(home, "run", "cancel", run_id, "--confirm")
    wait_for_terminal(home, run_id)


def test_a_piped_yes_is_a_caller_that_genuinely_answered(
    slow_run: tuple[Path, TechtreePaths, PreparedDraft],
) -> None:
    """techtree-python-xse. Having no terminal is not the same as having no answer."""
    home, _, prepared = slow_run
    run_id = _start_and_reach_baseline(home, prepared)

    cancelled = run_cli(home, "run", "cancel", run_id, machine=False, stdin="y\n")

    assert cancelled.exit_code == EXIT_OK, cancelled.stdout + cancelled.stderr
    assert f"Stop run {run_id}?" in cancelled.stdout
    assert wait_for_terminal(home, run_id)["phase"] == "cancelled"


def _event_kinds(paths: TechtreePaths, run_id: str) -> list[str]:
    journal = paths.run_dir(run_id) / "events.jsonl"
    return [event.kind for event in read_events(journal)]


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
