"""The bounded wait behind ``run.wait``. Machine contract, WP1.4.

``docs/v0.2/MACHINE_CONTRACT.md`` promises six things about waiting, and each
of them is a test here.

*The bound is explicit and is not negotiable.* Thirty seconds by default,
ninety at most, and asking for more is a usage error rather than a request
quietly cut down to size.

*Expiry is an ordinary answer.* A wait that runs out returns the run's current
state with no error, and the caller tells expiry from movement by comparing the
state digest it passed with the one it got back.

*It ends early on movement and on the run ending.* Either is what the caller
was waiting for.

*It does not busy-poll.* The worker's heartbeat interval is the fastest rate at
which anything new can exist to observe, so it is the fastest rate the log is
read at.

*It leaves nothing running.* The loop belongs to the invocation, and the
invocation ends.

The timing is injected rather than waited out, so the pacing can be asserted
exactly instead of approximately. One test does wait, for real, because "returns
within the bound" is a claim about wall-clock time and nothing else can make it.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Final

import pytest
from typer.testing import CliRunner

from fixtures.runs.support import RunHarness, execute_in_process, run_harness
from techtree.cli.app import create_app
from techtree.cli.commands.run import RUN_WATCH_NOT_SUPPORTED_WITH_WAIT
from techtree.constants import DEFAULT_WORKER_HEARTBEAT_SECONDS
from techtree.errors import EXIT_OK, EXIT_USAGE, EXIT_VALIDATION, UsageError
from techtree.models.run import PublicRunState, RunPhase, RunStatus
from techtree.runs.service import (
    DEFAULT_WAIT_TIMEOUT_SECONDS,
    MAXIMUM_WAIT_TIMEOUT_SECONDS,
    MINIMUM_WAIT_TIMEOUT_SECONDS,
    RUN_WAIT_TIMEOUT_OUT_OF_RANGE,
    RunService,
)

#: A run identifier that is well formed and belongs to nothing.
ABSENT_RUN: Final = "run_00000000000000000000000000000009"


class FakeTime:
    """A clock that only moves when the wait sleeps, and every sleep it made.

    Injecting both is what makes the pacing assertable: a wait against this
    clock takes no wall-clock time at all, and the list of sleeps is exactly
    the sampling interval the contract talks about.
    """

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        """Return the current instant, which only sleeping advances."""
        return self.now

    def sleep(self, seconds: float) -> None:
        """Record a sleep and let the clock jump by it."""
        self.slept.append(seconds)
        self.now += seconds


@pytest.fixture
def harness(temp_techtree_home: Path) -> RunHarness:
    return run_harness(temp_techtree_home)


@pytest.fixture
def started(harness: RunHarness) -> str:
    """Return the identifier of one started, unfinished run."""
    return harness.start().state.run_id


# ---------------------------------------------------------------------------
# The bound
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "timeout_seconds",
    [
        MAXIMUM_WAIT_TIMEOUT_SECONDS + 1,
        MINIMUM_WAIT_TIMEOUT_SECONDS - 1,
        -30,
        600,
    ],
)
def test_a_bound_outside_the_contract_is_a_usage_error(
    harness: RunHarness, started: str, timeout_seconds: int
) -> None:
    """Not clamped. A caller that believed it had ten minutes is told it did not."""
    with pytest.raises(UsageError) as raised:
        harness.service.wait(started, timeout_seconds=timeout_seconds)

    assert raised.value.code == RUN_WAIT_TIMEOUT_OUT_OF_RANGE
    assert raised.value.details["maximum"] == MAXIMUM_WAIT_TIMEOUT_SECONDS


def test_the_bound_is_checked_before_the_run_is_read(harness: RunHarness) -> None:
    """A malformed request is answered as one, not as a missing run."""
    with pytest.raises(UsageError) as raised:
        harness.service.wait(ABSENT_RUN, timeout_seconds=600)

    assert raised.value.code == RUN_WAIT_TIMEOUT_OUT_OF_RANGE


# ---------------------------------------------------------------------------
# Expiry
# ---------------------------------------------------------------------------


def test_a_wait_on_a_run_that_does_not_move_expires_at_its_bound(
    harness: RunHarness, started: str
) -> None:
    fake = FakeTime()

    harness.service.wait(
        started,
        timeout_seconds=DEFAULT_WAIT_TIMEOUT_SECONDS,
        monotonic=fake.monotonic,
        sleep=fake.sleep,
    )

    assert sum(fake.slept) == DEFAULT_WAIT_TIMEOUT_SECONDS
    assert fake.now == DEFAULT_WAIT_TIMEOUT_SECONDS


def test_expiry_is_not_an_error_and_the_run_is_still_where_it_was(
    harness: RunHarness, started: str
) -> None:
    """The answer after an expired wait is the ordinary answer."""
    fake = FakeTime()
    before = harness.service.state_digest(started)

    harness.service.wait(
        started, timeout_seconds=4, monotonic=fake.monotonic, sleep=fake.sleep
    )

    status = harness.service.status(started)
    assert status.state.phase is RunPhase.CREATED
    assert harness.service.state_digest(started) == before


def test_a_wait_that_expires_really_does_return_within_its_bound(
    harness: RunHarness, started: str
) -> None:
    """The one test that waits, because the claim is about wall-clock time."""
    began = time.monotonic()

    harness.service.wait(started, timeout_seconds=MINIMUM_WAIT_TIMEOUT_SECONDS)

    elapsed = time.monotonic() - began
    assert MINIMUM_WAIT_TIMEOUT_SECONDS <= elapsed < MINIMUM_WAIT_TIMEOUT_SECONDS + 5


# ---------------------------------------------------------------------------
# Ending early
# ---------------------------------------------------------------------------


def test_a_wait_ends_as_soon_as_the_run_moves(
    harness: RunHarness, started: str
) -> None:
    """The run advancing is what the caller was waiting for."""
    fake = FakeTime()

    def sleep_and_advance_the_run(seconds: float) -> None:
        fake.sleep(seconds)
        if len(fake.slept) == 1:
            harness.run_store.append(started, phase=RunPhase.VALIDATING_TASKSET)

    harness.service.wait(
        started,
        timeout_seconds=DEFAULT_WAIT_TIMEOUT_SECONDS,
        monotonic=fake.monotonic,
        sleep=sleep_and_advance_the_run,
    )

    assert fake.slept == [DEFAULT_WORKER_HEARTBEAT_SECONDS]
    assert fake.now < DEFAULT_WAIT_TIMEOUT_SECONDS


def test_a_wait_from_a_state_the_run_has_already_left_returns_at_once(
    harness: RunHarness, started: str
) -> None:
    """The caller's own digest is the baseline, so movement it missed still counts."""
    fake = FakeTime()
    before = harness.service.state_digest(started)
    harness.run_store.append(started, phase=RunPhase.VALIDATING_TASKSET)

    harness.service.wait(
        started,
        timeout_seconds=DEFAULT_WAIT_TIMEOUT_SECONDS,
        since_state_digest=before,
        monotonic=fake.monotonic,
        sleep=fake.sleep,
    )

    assert fake.slept == []


def test_a_wait_on_a_finished_run_returns_at_once(harness: RunHarness) -> None:
    """A run that has ended will never move again, so waiting for it is over."""
    run_id = harness.start().state.run_id
    execute_in_process(harness, run_id)
    fake = FakeTime()

    harness.service.wait(
        run_id,
        timeout_seconds=DEFAULT_WAIT_TIMEOUT_SECONDS,
        since_state_digest=harness.service.state_digest(run_id),
        monotonic=fake.monotonic,
        sleep=fake.sleep,
    )

    assert fake.slept == []
    assert harness.service.status(run_id).state.phase is RunPhase.COMPLETED


# ---------------------------------------------------------------------------
# How often it looks, and what it leaves behind
# ---------------------------------------------------------------------------


def test_the_log_is_never_read_faster_than_the_worker_heartbeat(
    harness: RunHarness, started: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two seconds is the fastest rate at which anything new can exist to see."""
    fake = FakeTime()
    reads: list[float] = []
    reading = harness.run_store.state_digest

    def counted(run_id: str) -> str:
        reads.append(fake.now)
        return reading(run_id)

    monkeypatch.setattr(harness.run_store, "state_digest", counted)

    harness.service.wait(
        started, timeout_seconds=5, monotonic=fake.monotonic, sleep=fake.sleep
    )

    assert fake.slept == [2, 2, 1]
    assert max(fake.slept) == DEFAULT_WORKER_HEARTBEAT_SECONDS
    # One read to establish the baseline and one per sample; in five seconds
    # that is five looks, not a loop as fast as the disk will answer.
    assert reads == [0.0, 0.0, 2.0, 4.0, 5.0]


def test_a_wait_leaves_nothing_running(harness: RunHarness, started: str) -> None:
    """No daemon, no background process, nothing outliving the call."""
    fake = FakeTime()
    before = threading.active_count()

    harness.service.wait(
        started, timeout_seconds=8, monotonic=fake.monotonic, sleep=fake.sleep
    )

    assert threading.active_count() == before


# ---------------------------------------------------------------------------
# The command a caller actually runs
# ---------------------------------------------------------------------------


def invoke(home: Path, *arguments: str) -> Any:
    return CliRunner().invoke(create_app(), ["--home", str(home), *arguments])


def envelope(result: Any) -> dict[str, Any]:
    """Return the one JSON object machine mode wrote."""
    import json

    lines = [line for line in result.stdout.splitlines() if line.startswith("{")]
    assert len(lines) == 1, result.stdout
    parsed: Any = json.loads(lines[0])
    assert isinstance(parsed, dict)
    return parsed


def test_status_carries_the_public_state_and_the_state_digest(
    temp_techtree_home: Path, harness: RunHarness, started: str
) -> None:
    result = invoke(temp_techtree_home, "--json", "run", "status", started)

    assert result.exit_code == EXIT_OK
    payload = envelope(result)["data"]
    assert payload["phase"] == RunPhase.CREATED.value
    assert payload["public_state"] == PublicRunState.PREPARED.value
    assert payload["state_digest"] == harness.service.state_digest(started)


def test_an_answer_never_carries_a_digest_newer_than_the_phase_beside_it(
    temp_techtree_home: Path, started: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The digest is read first, so it can lag the state and never lead it.

    A run advances while it is being read, so the two reads can land either
    side of an event. A digest read afterwards would name a moment the phase
    beside it had already been left, and a caller that recorded it as seen
    would wait for a move it had been given a stale name for.
    """
    reads: list[str] = []
    reading_digest = RunService.state_digest
    reading_status = RunService.status

    def digest(self: RunService, run_id: str) -> str:
        reads.append("state_digest")
        return reading_digest(self, run_id)

    def status(self: RunService, run_id: str) -> RunStatus:
        reads.append("status")
        return reading_status(self, run_id)

    monkeypatch.setattr(RunService, "state_digest", digest)
    monkeypatch.setattr(RunService, "status", status)

    result = invoke(temp_techtree_home, "--json", "run", "status", started)

    assert result.exit_code == EXIT_OK
    assert reads == ["state_digest", "status"]


def test_a_reader_who_stops_waiting_still_gets_an_answer(
    temp_techtree_home: Path,
    harness: RunHarness,
    started: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``Ctrl-C`` stops the waiting, never the run, and is not a failure."""

    def interrupted(self: RunService, run_id: str, **options: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(RunService, "wait", interrupted)

    result = invoke(
        temp_techtree_home, "--json", "run", "status", started, "--timeout-seconds", "5"
    )

    assert result.exit_code == EXIT_OK
    body = envelope(result)
    assert body["ok"] is True
    assert body["data"]["state_digest"] == harness.service.state_digest(started)
    assert harness.service.status(started).state.phase is RunPhase.CREATED


def test_a_person_who_stops_waiting_is_told_the_run_is_unaffected(
    temp_techtree_home: Path, started: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrupted(self: RunService, run_id: str, **options: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(RunService, "wait", interrupted)

    result = invoke(
        temp_techtree_home, "run", "status", started, "--timeout-seconds", "5"
    )

    assert result.exit_code == EXIT_OK
    assert "Stopped waiting. The run is unaffected." in result.stdout


def test_asking_for_longer_than_the_ceiling_is_refused_at_the_command_line(
    temp_techtree_home: Path, started: str
) -> None:
    result = invoke(
        temp_techtree_home,
        "--json",
        "run",
        "status",
        started,
        "--timeout-seconds",
        str(MAXIMUM_WAIT_TIMEOUT_SECONDS + 1),
    )

    assert result.exit_code == EXIT_USAGE
    assert envelope(result)["error"]["code"] == RUN_WAIT_TIMEOUT_OUT_OF_RANGE


def test_a_digest_that_is_not_a_digest_is_refused(
    temp_techtree_home: Path, started: str
) -> None:
    result = invoke(
        temp_techtree_home,
        "--json",
        "run",
        "status",
        started,
        "--since-state-digest",
        "yesterday",
    )

    assert result.exit_code == EXIT_VALIDATION


def test_a_state_the_run_has_left_is_answered_without_waiting(
    temp_techtree_home: Path, harness: RunHarness, started: str
) -> None:
    """The wait is over before it starts, so the command is as quick as a read."""
    before = harness.service.state_digest(started)
    harness.run_store.append(started, phase=RunPhase.VALIDATING_TASKSET)
    began = time.monotonic()

    result = invoke(
        temp_techtree_home,
        "--json",
        "run",
        "status",
        started,
        "--since-state-digest",
        before,
    )

    assert result.exit_code == EXIT_OK
    assert time.monotonic() - began < DEFAULT_WAIT_TIMEOUT_SECONDS
    payload = envelope(result)["data"]
    assert payload["state_digest"] != before
    assert payload["public_state"] == PublicRunState.RUNNING.value


def test_a_wait_that_expires_answers_normally_at_the_command_line(
    temp_techtree_home: Path, harness: RunHarness, started: str
) -> None:
    """Nothing moves, the bound runs out, and the answer is the ordinary one."""
    before = harness.service.state_digest(started)

    result = invoke(
        temp_techtree_home,
        "--json",
        "run",
        "status",
        started,
        "--timeout-seconds",
        str(MINIMUM_WAIT_TIMEOUT_SECONDS),
    )

    assert result.exit_code == EXIT_OK
    body = envelope(result)
    assert body["ok"] is True
    assert body["error"] is None
    assert body["data"]["state_digest"] == before


def test_watching_and_waiting_are_not_asked_for_together(
    temp_techtree_home: Path, started: str
) -> None:
    """One prints until the run ends; the other answers once. Neither wins quietly."""
    result = invoke(
        temp_techtree_home,
        "run",
        "status",
        started,
        "--watch",
        "--timeout-seconds",
        "5",
    )

    assert result.exit_code == EXIT_USAGE
    assert RUN_WATCH_NOT_SUPPORTED_WITH_WAIT in result.stdout
