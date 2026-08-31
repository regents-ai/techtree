"""Launching and signalling a worker. Spec PR8 §8.7, §10.1, §10.7.

Nothing here starts a real worker — the detachment and signalling of an actual
process are established by the integration tests, which are the only place a
claim about process groups can be made honestly. What is asserted here is
everything decided *before* the fork: that the command is an argument array
with no shell anywhere near it, that the environment handed to the child is
built from a named list rather than inherited, and that a machine with no
worker program installed says so instead of failing obscurely.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from fixtures.runs.support import ABSENT_PID, RunHarness, run_harness
from techtree.errors import PrerequisiteError, RunError
from techtree.paths import paths_from_root
from techtree.runs.launcher import (
    WorkerLauncher,
    default_worker_executable,
    scrubbed_worker_environment,
)
from techtree.runs.store import RunStore


@pytest.fixture
def started(temp_techtree_home: Path) -> tuple[RunHarness, str]:
    """Return a harness with one created run to launch a worker for."""
    harness = run_harness(temp_techtree_home)
    return harness, harness.start().state.run_id


@pytest.fixture
def unlaunched(temp_techtree_home: Path) -> tuple[RunHarness, str]:
    """Return a run that exists and never got a worker.

    The state is reached the way a real one is: a launch that failed leaves an
    addressable run with no process behind it.
    """
    harness = run_harness(
        temp_techtree_home,
        launcher_failure=RunError("no worker today", code="worker_launch_failed"),
    )
    with pytest.raises(RunError):
        harness.start()
    record = harness.drafts.start_record(harness.draft_id)
    assert record is not None
    return harness, record.run_id


def _launcher(store: RunStore, executable: Path) -> WorkerLauncher:
    return WorkerLauncher(
        worker_executable=executable,
        run_store=store,
        environment_builder=lambda run_id: {},
    )


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------


def test_the_command_is_an_argument_array(started: tuple[RunHarness, str]) -> None:
    """Spec §10.1: there is no string for a shell to reinterpret."""
    harness, run_id = started
    launcher = _launcher(harness.run_store, Path("/opt/techtree/techtree-worker"))

    command = list(launcher.command(run_id))

    assert command == [
        "/opt/techtree/techtree-worker",
        "execute",
        "--run-id",
        run_id,
    ]


def test_a_hostile_run_identifier_stays_one_argument(
    started: tuple[RunHarness, str],
) -> None:
    harness, _ = started
    launcher = _launcher(harness.run_store, Path("/opt/techtree/techtree-worker"))

    command = list(launcher.command("run_x; rm -rf /"))

    assert command[-1] == "run_x; rm -rf /"
    assert len(command) == 4


def test_the_worker_program_is_looked_for_beside_the_interpreter() -> None:
    resolved = default_worker_executable()

    assert resolved.name == "techtree-worker"
    assert resolved.is_absolute()


def test_a_missing_worker_program_is_reported_before_anything_is_written(
    started: tuple[RunHarness, str],
) -> None:
    harness, run_id = started
    launcher = _launcher(harness.run_store, Path("/nonexistent/techtree-worker"))

    with pytest.raises(PrerequisiteError) as raised:
        launcher.launch(run_id)

    assert raised.value.code == "worker_executable_not_found"


# ---------------------------------------------------------------------------
# The environment
# ---------------------------------------------------------------------------


def test_the_worker_is_told_where_the_techtree_home_is(tmp_path: Path) -> None:
    paths = paths_from_root(tmp_path / "home")

    environment = scrubbed_worker_environment(paths, environ={})("run_x")

    assert environment["TECHTREE_HOME"] == str(paths.root)
    assert environment["PYTHONUNBUFFERED"] == "1"


def test_no_provider_credential_is_inherited(tmp_path: Path) -> None:
    """Spec §10.7: the fake worker receives no model-provider credential."""
    paths = paths_from_root(tmp_path / "home")
    hostile = {
        "PATH": "/usr/bin",
        "HOME": "/home/someone",
        "TMPDIR": "/tmp",
        "TECHTREE_LOG_LEVEL": "DEBUG",
        "TECHTREE_MODEL_API_KEY": "sk-live-not-for-the-worker",
        "OPENAI_API_KEY": "sk-live-also-not",
        "AWS_SECRET_ACCESS_KEY": "nor-this",
        "SSH_AUTH_SOCK": "/tmp/agent.sock",
    }

    environment = scrubbed_worker_environment(paths, environ=hostile)("run_x")

    assert set(environment) == {
        "PATH",
        "HOME",
        "TMPDIR",
        "TECHTREE_LOG_LEVEL",
        "TECHTREE_HOME",
        "PYTHONUNBUFFERED",
    }
    assert "sk-live-not-for-the-worker" not in "".join(environment.values())


def test_an_absent_variable_is_not_invented(tmp_path: Path) -> None:
    paths = paths_from_root(tmp_path / "home")

    environment = scrubbed_worker_environment(paths, environ={"PATH": "/usr/bin"})("r")

    assert "TMPDIR" not in environment
    assert "HOME" not in environment


# ---------------------------------------------------------------------------
# Liveness and signals
# ---------------------------------------------------------------------------


def test_a_run_with_no_worker_is_not_alive(
    unlaunched: tuple[RunHarness, str],
) -> None:
    harness, run_id = unlaunched
    launcher = _launcher(harness.run_store, Path("/nonexistent/techtree-worker"))

    assert harness.run_store.read_pid(run_id) is None
    assert launcher.is_alive(run_id) is False


def test_a_live_process_is_reported_alive(
    unlaunched: tuple[RunHarness, str],
) -> None:
    """This process exists, so the check has something true to find."""
    harness, run_id = unlaunched
    _write_pid(harness, run_id, os.getpid())
    launcher = _launcher(harness.run_store, Path("/nonexistent/techtree-worker"))

    assert launcher.is_alive(run_id) is True


def test_a_worker_that_has_gone_is_reported_gone(
    started: tuple[RunHarness, str],
) -> None:
    harness, run_id = started

    launcher = _launcher(harness.run_store, Path("/nonexistent/techtree-worker"))

    assert harness.run_store.read_pid(run_id) == ABSENT_PID
    assert launcher.is_alive(run_id) is False


def test_signalling_a_run_with_no_worker_does_nothing(
    unlaunched: tuple[RunHarness, str],
) -> None:
    harness, run_id = unlaunched
    launcher = _launcher(harness.run_store, Path("/nonexistent/techtree-worker"))

    launcher.request_termination(run_id)
    launcher.force_kill(run_id)


def test_signalling_a_worker_that_has_already_ended_is_not_a_failure(
    started: tuple[RunHarness, str],
) -> None:
    """Being asked to stop something that has stopped is success, not error."""
    harness, run_id = started
    launcher = _launcher(harness.run_store, Path("/nonexistent/techtree-worker"))

    launcher.request_termination(run_id)
    launcher.force_kill(run_id)


def _write_pid(harness: RunHarness, run_id: str, pid: int) -> None:
    """Record a worker against a run whose launch had failed.

    The run is failed, and the store refuses to give a terminal run a worker,
    so the pid file is written the way the store writes it and the journal is
    left alone. This is a test reaching for a process-table fact, not a run
    pretending to have a worker.
    """
    (harness.paths.run_dir(run_id) / "pid").write_text(f"{pid}\n", encoding="utf-8")
