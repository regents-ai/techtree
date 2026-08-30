"""Shared construction for the PR8 run tests. Spec PR8 §8.17.

Every run in these tests starts from a real prepared draft, built by the real
preparation service against the complete synthetic catalog fixture. A test that
hand-assembled a draft would be testing its own assembly, and the properties
PR8 has to establish — that a run owns its inputs, that a start is idempotent,
that the report carries exact Campaign lineage — are only meaningful against a
draft that was genuinely prepared.

Two layers are offered.

:func:`run_harness` wires the whole run-control stack over a temporary home
with a launcher that records launches instead of making them. That is what the
unit tests want: every branch of :class:`~techtree.runs.service.RunService`
without a process anywhere.

:func:`execute_in_process` runs the fake executor directly against a created
run, which is what the executor and cancellation tests want: real files, real
events, no subprocess to wait for.

:func:`bigger_catalog` writes a variant of the committed catalog fixture with
more tasks in it. The integration tests that have to observe a run *while it is
running* need one that lasts longer than the command that started it, and
lengthening the taskset is the honest way to get that — nothing about the code
under test changes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import pytest

from fixtures.drafts.support import COMPLETE_CATALOG, VALID_SKILL, preparation_service
from techtree.canonical import digest_object
from techtree.drafts.store import DraftStore
from techtree.errors import TechtreeError
from techtree.models.run import PolicyAcknowledgement, RunRequest, RunStatus
from techtree.models.skill import SubmissionDraft
from techtree.models.uplift_report import UpliftReport
from techtree.paths import TechtreePaths, paths_from_root
from techtree.runs.artifacts import RunArtifactStore, RunInputBundle
from techtree.runs.executor import ExecutionContext, clear_local_cancellation
from techtree.runs.fake import FakeRunExecutor
from techtree.runs.launcher import WorkerLauncher
from techtree.runs.service import ApprovalActor, RunService
from techtree.runs.store import RunStore
from techtree.runs.validation import (
    PublisherFixtureValidationProvider,
    TasksetValidationProvider,
)
from techtree.skills.service import PreparedDraft
from techtree.verifiers.credentials import PRIME_CREDENTIAL_ENV

#: The Climb every run test enters. Development status, development-only proof
#: grade: exactly what a fake executor is entitled to run.
DEVELOPMENT_CLIMB: Final = "synthetic-development"

#: A process id no test machine has running. Used where a run has to name a
#: worker that is definitely not there.
ABSENT_PID: Final = 2**22 - 1


def utc_now() -> datetime:
    """Return the current instant in UTC."""
    return datetime.now(UTC)


class RecordingLauncher(WorkerLauncher):
    """A launcher that records what it was asked to do and starts nothing.

    Every unit test of the service needs a launch to have "happened" without a
    process existing, and needs to be able to make one fail on demand.
    """

    def __init__(
        self,
        run_store: RunStore,
        *,
        failure: TechtreeError | None = None,
        pid: int = ABSENT_PID,
    ) -> None:
        super().__init__(
            worker_executable=Path("/nonexistent/techtree-worker"),
            run_store=run_store,
            environment_builder=lambda run_id: {},
        )
        self.launched: list[str] = []
        self.terminated: list[str] = []
        self.killed: list[str] = []
        self.alive: set[str] = set()
        self._failure = failure
        self._pid = pid

    def launch(self, run_id: str) -> int:
        """Record a launch, or fail the way a real one would."""
        if self._failure is not None:
            raise self._failure
        self.launched.append(run_id)
        self.alive.add(run_id)
        return self._pid

    def is_alive(self, run_id: str) -> bool:
        """Return whether this launcher believes the run is still going."""
        return run_id in self.alive

    def request_termination(self, run_id: str) -> None:
        """Record a termination request."""
        self.terminated.append(run_id)

    def force_kill(self, run_id: str) -> None:
        """Record a kill."""
        self.killed.append(run_id)
        self.alive.discard(run_id)


@dataclass
class RunHarness:
    """One prepared draft and the whole run-control stack over it."""

    paths: TechtreePaths
    drafts: DraftStore
    prepared: PreparedDraft
    run_store: RunStore
    artifacts: RunArtifactStore
    launcher: RecordingLauncher
    service: RunService

    @property
    def draft(self) -> SubmissionDraft:
        """Return the prepared draft."""
        return self.prepared.draft

    @property
    def draft_id(self) -> str:
        """Return the prepared draft's identifier."""
        return self.prepared.draft.id

    def acknowledgement(
        self,
        *,
        digest: str | None = None,
        method: str = "explicit_cli_review",
        at: datetime | None = None,
    ) -> PolicyAcknowledgement:
        """Return an acceptance of this draft's data policy."""
        return PolicyAcknowledgement(
            data_policy_digest=digest or self.draft.data_policy_digest,
            method=method,  # type: ignore[arg-type]
            acknowledged_at=at or utc_now(),
        )

    def start(
        self,
        *,
        approved_by: ApprovalActor = "human_via_cli",
        **acknowledgement: Any,
    ) -> RunStatus:
        """Start this draft the way the CLI would."""
        return self.service.start(
            draft_id=self.draft_id,
            policy_acknowledgement=self.acknowledgement(**acknowledgement),
            approved_by=approved_by,
        )

    def request(self, run_id: str) -> RunRequest:
        """Return the run's immutable request."""
        return self.run_store.get_request(run_id)

    def inputs(self, run_id: str) -> RunInputBundle:
        """Return the run's staged inputs."""
        return self.artifacts.load_inputs(run_id, self.request(run_id))


def run_harness(
    home: Path,
    *,
    catalog_root: Path = COMPLETE_CATALOG,
    skill_path: Path = VALID_SKILL,
    launcher_failure: TechtreeError | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> RunHarness:
    """Prepare one real draft and wire the run stack over it."""
    paths = paths_from_root(home)
    preparation, drafts = preparation_service(paths, catalog_root=catalog_root)
    prepared = preparation.prepare(
        climb_reference=DEVELOPMENT_CLIMB,
        skill_path=skill_path,
        candidate_label="candidate-under-test",
    )

    run_store = RunStore(paths)
    artifacts = RunArtifactStore(paths)
    launcher = RecordingLauncher(run_store, failure=launcher_failure)
    return RunHarness(
        paths=paths,
        drafts=drafts,
        prepared=prepared,
        run_store=run_store,
        artifacts=artifacts,
        launcher=launcher,
        service=RunService(
            paths=paths,
            draft_store=drafts,
            run_store=run_store,
            artifact_store=artifacts,
            launcher=launcher,
            clock=clock,
        ),
    )


def execution_context(
    harness: RunHarness,
    run_id: str,
    *,
    provider: TasksetValidationProvider | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> ExecutionContext:
    """Return the context an executor is handed for one created run."""
    return ExecutionContext(
        request=harness.request(run_id),
        run_store=harness.run_store,
        artifact_store=harness.artifacts,
        validation_provider=provider or PublisherFixtureValidationProvider(),
        clock=clock,
    )


def execute_in_process(
    harness: RunHarness,
    run_id: str,
    *,
    executor: FakeRunExecutor | None = None,
    provider: TasksetValidationProvider | None = None,
) -> UpliftReport:
    """Run the fake executor to completion in this process."""
    clear_local_cancellation()
    chosen = executor or FakeRunExecutor(step_delay_seconds=0.0)
    return chosen.execute(execution_context(harness, run_id, provider=provider))


@dataclass(frozen=True)
class CliRun:
    """What one real ``techtree`` subprocess did."""

    exit_code: int
    stdout: str
    stderr: str

    def envelope(self) -> dict[str, Any]:
        """Parse the single JSON object on stdout, insisting there is one."""
        lines = [line for line in self.stdout.splitlines() if line.startswith("{")]
        assert len(lines) == 1, f"expected one JSON object, got {self.stdout!r}"
        parsed: Any = json.loads(lines[0])
        assert isinstance(parsed, dict)
        return parsed

    def data(self) -> dict[str, Any]:
        """Return the envelope's payload, insisting the command succeeded."""
        envelope = self.envelope()
        assert envelope["ok"] is True, envelope.get("error")
        payload = envelope["data"]
        assert isinstance(payload, dict)
        return payload


def run_cli(
    home: Path,
    *arguments: str,
    machine: bool = True,
    timeout: float = 120.0,
    stdin: str | None = None,
    environment: Mapping[str, str] | None = None,
) -> CliRun:
    """Invoke the real CLI in a separate process.

    A separate process is the point: the boundary these tests are about is a
    program that exits, and none of that can be observed from inside the
    interpreter that would be answering the questions.

    The child never receives an evaluation credential. Since decisions document
    0025 the shipped Campaign names a real subject, so a ``climb start`` typed
    on a machine that is signed in to the provider would launch containers and
    spend money — which no unattended test may ever do. Dropping the variable
    is not the whole of that guard, because the pinned client also reads the
    Prime CLI configuration under ``HOME``; a test that starts a run passes a
    ``HOME`` with none through ``environment``.
    """
    command = [sys.executable, "-m", "techtree", "--home", str(home)]
    if machine:
        command += ["--json", "--no-input"]
    command += list(arguments)

    inherited = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("TECHTREE_") and name != PRIME_CREDENTIAL_ENV
    }
    environment = {**inherited, **(environment or {})}
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        input="" if stdin is None else stdin,
        env=environment,
        check=False,
    )
    return CliRun(
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def start_through_the_cli(home: Path, prepared: PreparedDraft) -> CliRun:
    """Start a prepared draft the way a host agent would."""
    return run_cli(
        home,
        "climb",
        "start",
        prepared.draft.id,
        "--yes",
    )


def wait_for_terminal(
    home: Path, run_id: str, *, timeout: float = 120.0
) -> dict[str, Any]:
    """Poll ``run status`` from fresh processes until the run ends."""
    deadline = time.monotonic() + timeout
    payload = run_cli(home, "run", "status", run_id).data()
    while not payload["terminal"]:
        if time.monotonic() > deadline:
            raise AssertionError(f"run {run_id} never ended: {payload}")
        time.sleep(0.2)
        payload = run_cli(home, "run", "status", run_id).data()
    return payload


def wait_until(condition: Callable[[], bool], *, timeout: float = 60.0) -> None:
    """Wait for a condition, failing the test rather than hanging."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.05)
    raise AssertionError("condition was never met")


def prepare_only(
    home: Path,
    *,
    catalog_root: Path = COMPLETE_CATALOG,
    skill_path: Path = VALID_SKILL,
) -> tuple[TechtreePaths, PreparedDraft]:
    """Prepare one real draft without wiring anything else over it."""
    paths = paths_from_root(home)
    preparation, _ = preparation_service(paths, catalog_root=catalog_root)
    return paths, preparation.prepare(
        climb_reference=DEVELOPMENT_CLIMB,
        skill_path=skill_path,
        candidate_label="candidate-under-test",
    )


def bigger_catalog(
    destination: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    task_count: int,
) -> Path:
    """Write a catalog fixture whose Campaign commits to more tasks.

    The same builder that produced the committed fixture produces this one, so
    it is the same graph with a longer taskset rather than a second fixture
    that could drift away from the first.
    """
    from fixtures.drafts.support import catalog_fixture_builder

    builder: Any = catalog_fixture_builder()
    monkeypatch.setattr(builder, "TASK_COUNT", task_count)
    builder.build(destination)
    return destination


def worker_environment(paths: TechtreePaths) -> Mapping[str, str]:
    """Return the environment a real launched worker would be given."""
    from techtree.runs.launcher import scrubbed_worker_environment

    return scrubbed_worker_environment(paths)("run_id")


def report_digest(report: UpliftReport) -> str:
    """Return the digest a run's journal records for this report."""
    return digest_object(report)
