"""The worker outlives the command that started it. Spec PR8 §8.1, §8.17.

This is the claim the whole slice exists to make, and it cannot be made from
inside one process. A real ``techtree climb start`` subprocess is run to
completion — not backgrounded, *exited* — and only then is the run looked at,
from further subprocesses that share nothing with it.

The taskset is deliberately longer here than in the other tests. A run that
finished before its launcher did would prove nothing about survival, so the
Campaign this test builds commits to enough tasks that the worker is
demonstrably still going after the starting process is gone.

One run is started and every observation is taken from it, in order: what was
true the moment the launching process exited, and what was true once the run
had finished. Re-running the whole flow per assertion would cost a great deal
and prove the same thing several times.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from fixtures.runs.support import (
    CliRun,
    bigger_catalog,
    prepare_only,
    run_cli,
    start_through_the_cli,
    wait_for_terminal,
)
from techtree.canonical import digest_object
from techtree.errors import EXIT_OK
from techtree.paths import TechtreePaths
from techtree.runs.events import read_events
from techtree.runs.machine import reduce_events
from techtree.runs.store import RunStore

pytestmark = pytest.mark.integration

#: Long enough that the run is unambiguously still going once the launching
#: process has exited, short enough to stay a test.
SLOW_TASK_COUNT = 40


@dataclass(frozen=True)
class Survivor:
    """One slow run, observed while it ran and after it ended."""

    home: Path
    paths: TechtreePaths
    run_id: str
    worker_pid: int
    while_running: dict[str, Any]
    result_while_running: CliRun
    process_group: int
    session: int
    final: dict[str, Any]


@pytest.fixture(scope="module")
def survivor(tmp_path_factory: pytest.TempPathFactory) -> Survivor:
    """Start a slow run in a real process and watch it outlive its launcher."""
    root = tmp_path_factory.mktemp("survival")
    with pytest.MonkeyPatch.context() as patch:
        catalog = bigger_catalog(root / "catalog", patch, task_count=SLOW_TASK_COUNT)
        home = root / "home"
        home.mkdir()
        paths, prepared = prepare_only(home, catalog_root=catalog)

    started = start_through_the_cli(home, prepared)
    assert started.exit_code == EXIT_OK, started.stdout + started.stderr
    payload = started.data()
    run_id = payload["run_id"]
    worker_pid = payload["worker_pid"]

    # The launching process has exited: ``subprocess.run`` waited for it. Every
    # observation from here is of an orphan.
    while_running = run_cli(home, "run", "status", run_id).data()
    early_result = run_cli(home, "run", "result", run_id)
    group = os.getpgid(worker_pid)
    session = os.getsid(worker_pid)

    return Survivor(
        home=home,
        paths=paths,
        run_id=run_id,
        worker_pid=worker_pid,
        while_running=while_running,
        result_while_running=early_result,
        process_group=group,
        session=session,
        final=wait_for_terminal(home, run_id),
    )


def test_the_worker_was_still_going_after_its_launcher_exited(
    survivor: Survivor,
) -> None:
    assert survivor.while_running["terminal"] is False
    assert survivor.while_running["worker_alive"] is True
    assert survivor.while_running["worker_pid"] == survivor.worker_pid


def test_a_result_asked_for_too_early_says_to_check_the_status(
    survivor: Survivor,
) -> None:
    """Spec §8.15: retryable, and pointed at the command that answers."""
    envelope = survivor.result_while_running.envelope()

    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "run_result_not_ready"
    assert envelope["error"]["retryable"] is True
    assert envelope["next_actions"][0]["cli"] == [
        "techtree",
        "run",
        "status",
        survivor.run_id,
    ]


def test_the_worker_is_its_own_session_leader(survivor: Survivor) -> None:
    """``start_new_session`` is what stops a closing terminal ending a run."""
    assert survivor.process_group == survivor.worker_pid
    assert survivor.session == survivor.worker_pid
    assert survivor.worker_pid != os.getpid()


def test_the_worker_reported_a_heartbeat_while_it_worked(
    survivor: Survivor,
) -> None:
    assert (survivor.paths.run_dir(survivor.run_id) / "heartbeat.json").exists()
    assert survivor.final["heartbeat_at"] is not None


def test_the_run_finished_without_anything_watching_it(survivor: Survivor) -> None:
    assert survivor.final["phase"] == "completed"
    assert survivor.final["result_available"] is True
    assert survivor.final["error"] is None


def test_the_finished_run_reads_back_from_a_fresh_process(
    survivor: Survivor,
) -> None:
    result = run_cli(survivor.home, "run", "result", survivor.run_id)

    assert result.exit_code == EXIT_OK
    # ``run result`` answers with the report and the neutral presentation
    # payload every channel draws from (spec section 7.21).
    report = result.data()["report"]
    assert report["run_id"] == survivor.run_id
    assert len(report["task_deltas"]) == SLOW_TASK_COUNT
    assert report["publication_eligible"] is False


def test_the_journal_and_the_result_digest_agree(survivor: Survivor) -> None:
    events = read_events(survivor.paths.run_dir(survivor.run_id) / "events.jsonl")
    rebuilt = reduce_events(events)
    report = RunStore(survivor.paths).get_result(survivor.run_id)

    assert [event.sequence for event in events] == list(range(len(events)))
    assert rebuilt.phase.value == "completed"
    assert rebuilt.result_digest == digest_object(report)
    assert rebuilt.worker_pid == survivor.worker_pid


def test_the_worker_recorded_what_it_was_doing(survivor: Survivor) -> None:
    logs = run_cli(survivor.home, "run", "logs", survivor.run_id).data()

    assert any(str(survivor.worker_pid) in line for line in logs["lines"])
    assert any("completed" in line for line in logs["lines"])
