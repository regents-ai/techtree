"""Waiting on a run this process does not own. Machine contract, WP1.4.

The unit tests establish what the wait does against an injected clock. What
they cannot establish is the thing the wait is for: that a separate ``techtree
run status`` process, waiting, sees a *detached worker* advance and answers as
soon as it does. That needs two real processes, which is what this file uses.

The bound is generous and the assertions are about the shape of the answer
rather than about a duration, so a slow machine makes this test slower and
never makes it wrong.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from fixtures.runs.support import (
    bigger_catalog,
    prepare_only,
    run_cli,
    start_through_the_cli,
    wait_for_terminal,
)
from techtree.errors import EXIT_OK
from techtree.models.run import PublicRunState
from techtree.runs.service import DEFAULT_WAIT_TIMEOUT_SECONDS
from techtree.skills.service import PreparedDraft

pytestmark = pytest.mark.integration

#: Long enough that a run is still going while another process waits on it.
SLOW_TASK_COUNT = 40


@pytest.fixture
def slow_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    """Return a home and a run in it that takes several seconds to finish."""
    catalog = bigger_catalog(
        tmp_path / "catalog", monkeypatch, task_count=SLOW_TASK_COUNT
    )
    home = tmp_path / "home"
    home.mkdir()
    _, prepared = prepare_only(home, catalog_root=catalog)
    return home, _run_id(home, prepared)


def _run_id(home: Path, prepared: PreparedDraft) -> str:
    started = start_through_the_cli(home, prepared)
    assert started.exit_code == EXIT_OK, started.stdout + started.stderr
    return str(started.data()["run_id"])


def test_a_waiting_process_answers_as_soon_as_the_worker_moves(
    slow_run: tuple[Path, str],
) -> None:
    """The digest it was given is gone, and it did not sit out its bound."""
    home, run_id = slow_run
    first = run_cli(home, "run", "status", run_id).data()
    if first["terminal"]:
        # A run that finished before anything could wait on it has nothing left
        # to move, and the wait would rightly return the digest it was given.
        # That is the next test's subject, not this one's.
        pytest.skip("the run ended before the first read")
    seen = first["state_digest"]

    began = time.monotonic()
    waited = run_cli(
        home,
        "run",
        "status",
        run_id,
        "--since-state-digest",
        seen,
        "--timeout-seconds",
        str(DEFAULT_WAIT_TIMEOUT_SECONDS),
    )

    assert waited.exit_code == EXIT_OK
    assert time.monotonic() - began < DEFAULT_WAIT_TIMEOUT_SECONDS
    payload = waited.data()
    assert payload["state_digest"] != seen
    assert payload["public_state"] in {
        PublicRunState.RUNNING.value,
        PublicRunState.COMPLETED.value,
    }


def test_waiting_on_a_finished_run_is_answered_immediately(
    slow_run: tuple[Path, str],
) -> None:
    """A run that has ended will never move again, so the wait is already over."""
    home, run_id = slow_run
    wait_for_terminal(home, run_id)

    began = time.monotonic()
    waited = run_cli(
        home,
        "run",
        "status",
        run_id,
        "--timeout-seconds",
        str(DEFAULT_WAIT_TIMEOUT_SECONDS),
    )

    assert waited.exit_code == EXIT_OK
    assert time.monotonic() - began < DEFAULT_WAIT_TIMEOUT_SECONDS
    payload = waited.data()
    assert payload["public_state"] == PublicRunState.COMPLETED.value
    assert payload["terminal"] is True


def test_the_wait_leaves_no_process_behind(slow_run: tuple[Path, str]) -> None:
    """The waiting invocation ends; the run it was watching does not.

    ``run_cli`` waits for the child to exit, so the command returning at all is
    the whole of the first half. The second half is that the run is untouched
    by having been watched, and still finishes on its own.
    """
    home, run_id = slow_run

    waited = run_cli(home, "run", "status", run_id, "--timeout-seconds", "1")

    assert waited.exit_code == EXIT_OK
    assert wait_for_terminal(home, run_id)["phase"] == "completed"
