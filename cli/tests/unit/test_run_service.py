"""Run control, and the transaction that makes starting safe.
Spec PR8 §8.8, §8.13, §8.15, §8.17, §9.

Starting is the interesting half. It spends a one-time confirmation and a
participant's acceptance of a rights policy, and it has to survive a crash
between any two of the four things it touches. Every crash window in spec §9
is a test here, and each of them asserts the same thing: one draft becomes one
run, whatever happens.

The rest is the reading half — status that never invents a transition, logs
that are bounded and scrubbed, a result that is refused until it verifies, and
a cancellation that can tell three outcomes apart.

The worker's own half of the lifecycle is here too. A worker that fails, is
cancelled, or breaks in a way nobody anticipated still has to leave the run in
a terminal state with a scrubbed reason and exit with a code its launcher can
act on. Those tests run ``execute_run`` in this process against injected
executors, which is the only way to make an executor break on demand; that the
same function survives in a *detached* process is established by
``tests/integration/test_run_process_survival.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from fixtures.runs.support import (
    RunHarness,
    execute_in_process,
    run_harness,
    utc_now,
)
from techtree.canonical import canonical_json_bytes, digest_object
from techtree.drafts.confirmation import ConfirmationService
from techtree.drafts.store import DraftStartRecord, DraftStartStatus
from techtree.errors import (
    EXIT_CANCELLED,
    EXIT_VERIFICATION,
    AuthenticationError,
    CancellationError,
    ConflictError,
    PolicyError,
    RunError,
    TechtreeError,
    UsageError,
    VerificationError,
)
from techtree.fs import atomic_write_bytes, remove_tree
from techtree.models.base import JsonValue
from techtree.models.run import RunPhase, RunState
from techtree.models.uplift_report import UpliftReport
from techtree.runs.events import PHASE_ENTERED, RUN_COMPLETED
from techtree.runs.executor import ExecutionContext, clear_local_cancellation
from techtree.runs.fake import FakeRunExecutor
from techtree.runs.service import DEFAULT_LOG_TAIL
from techtree.runs.store import RunStore
from techtree.worker.execute import EXIT_UNEXPECTED, execute_run


@pytest.fixture
def harness(temp_techtree_home: Path) -> RunHarness:
    """Return one prepared draft and the run stack over it."""
    return run_harness(temp_techtree_home)


# ---------------------------------------------------------------------------
# Starting
# ---------------------------------------------------------------------------


def test_a_correct_token_and_acceptance_start_one_run(harness: RunHarness) -> None:
    status = harness.start()

    assert status.state.phase is RunPhase.CREATED
    assert harness.launcher.launched == [status.state.run_id]
    assert status.state.worker_pid is not None
    assert list(harness.paths.runs_dir.iterdir()) == [
        harness.paths.run_dir(status.state.run_id)
    ]


def test_the_request_records_how_the_policy_was_accepted(
    harness: RunHarness,
) -> None:
    status = harness.start(method="interactive_cli")

    acknowledgement = harness.request(status.state.run_id).policy_acknowledgement
    assert acknowledgement.method == "interactive_cli"
    assert acknowledgement.data_policy_digest == harness.draft.data_policy_digest


def test_the_request_names_the_draft_it_was_built_from(harness: RunHarness) -> None:
    status = harness.start()

    request = harness.request(status.state.run_id)
    assert request.draft_id == harness.draft_id
    assert request.draft_digest == digest_object(harness.draft)
    assert request.executor_kind == "fake"


def test_a_wrong_token_starts_nothing(harness: RunHarness) -> None:
    with pytest.raises(AuthenticationError) as raised:
        harness.start(token="not-the-token")

    assert raised.value.code == "confirmation_token_invalid"
    assert harness.drafts.start_record(harness.draft_id) is None
    assert not harness.paths.runs_dir.exists() or (
        list(harness.paths.runs_dir.iterdir()) == []
    )


def test_an_empty_token_is_a_usage_error(harness: RunHarness) -> None:
    with pytest.raises(UsageError) as raised:
        harness.start(token="   ")

    assert raised.value.code == "confirmation_token_required"


def test_an_expired_token_starts_nothing(temp_techtree_home: Path) -> None:
    moment = [datetime(2026, 1, 1, tzinfo=UTC)]
    confirmation = ConfirmationService(clock=lambda: moment[0])
    expiring = run_harness(temp_techtree_home, confirmation=confirmation)
    moment[0] = moment[0] + timedelta(days=1)

    with pytest.raises(AuthenticationError) as raised:
        expiring.start()

    assert raised.value.code == "confirmation_token_expired"
    assert expiring.drafts.start_record(expiring.draft_id) is None


def test_accepting_a_different_policy_starts_nothing(harness: RunHarness) -> None:
    with pytest.raises(PolicyError) as raised:
        harness.start(digest=f"sha256:{'a' * 64}")

    assert raised.value.code == "policy_acceptance_digest_mismatch"
    assert harness.drafts.start_record(harness.draft_id) is None


def test_a_method_this_build_cannot_produce_is_refused(harness: RunHarness) -> None:
    """No host-agent confirmation channel exists, so none may be claimed."""
    with pytest.raises(PolicyError) as raised:
        harness.start(method="host_agent_confirmation")

    assert raised.value.code == "policy_acceptance_method_invalid"
    assert harness.drafts.start_record(harness.draft_id) is None


# ---------------------------------------------------------------------------
# Idempotency and the crash windows of spec §9
# ---------------------------------------------------------------------------


def test_starting_twice_returns_the_same_run(harness: RunHarness) -> None:
    first = harness.start()
    second = harness.start()

    assert second.state.run_id == first.state.run_id
    assert harness.launcher.launched == [first.state.run_id]
    assert len(list(harness.paths.runs_dir.iterdir())) == 1


def test_a_second_start_does_not_consume_a_second_confirmation(
    harness: RunHarness,
) -> None:
    harness.start()
    consumed_at = harness.drafts.get_confirmation(harness.draft_id).consumed_at

    harness.start()

    assert harness.drafts.get_confirmation(harness.draft_id).consumed_at == consumed_at


def test_a_crash_after_the_claim_repairs_the_same_run(harness: RunHarness) -> None:
    """Spec §9.3: start.json holds the canonical run identifier."""
    claimed = harness.drafts.claim_start(
        draft_id=harness.draft_id,
        token=harness.token,
        run_id="run_" + "1" * 32,
    )
    assert claimed.status is DraftStartStatus.CLAIMED

    status = harness.start(token="the-token-was-already-consumed")

    assert status.state.run_id == claimed.run_id
    assert harness.launcher.launched == [claimed.run_id]
    assert harness.artifacts.inputs_dir(claimed.run_id).exists()


def test_a_crash_after_the_run_was_created_launches_only_once(
    harness: RunHarness,
) -> None:
    """Spec §9.4: retry launches only when no worker has announced itself."""
    first = harness.start()
    harness.launcher.launched.clear()

    again = harness.start()

    assert again.state.run_id == first.state.run_id
    assert harness.launcher.launched == []


def test_a_crash_before_inputs_were_staged_stages_them(harness: RunHarness) -> None:
    first = harness.start()
    remove_tree(harness.artifacts.inputs_dir(first.state.run_id))

    again = harness.start()

    assert again.state.run_id == first.state.run_id
    assert harness.artifacts.inputs_dir(first.state.run_id).exists()
    assert harness.inputs(first.state.run_id).draft.id == harness.draft_id


def test_a_claim_on_another_draft_s_run_is_refused(
    temp_techtree_home: Path,
) -> None:
    """A start record naming a run built from a different draft is corruption."""
    first = run_harness(temp_techtree_home)
    other = run_harness(temp_techtree_home / "second")
    stolen = other.start().state.run_id

    atomic_write_bytes(
        first.paths.draft_dir(first.draft_id) / "start.json",
        canonical_json_bytes(
            DraftStartRecord(
                draft_id=first.draft_id,
                run_id=stolen,
                status=DraftStartStatus.CLAIMED,
                claimed_at=utc_now(),
                launched_at=None,
                launch_error_code=None,
            )
        ),
    )
    # The run has to exist in this home for the claim to be checkable at all.
    remove_tree(first.paths.run_dir(stolen))
    (first.paths.runs_dir).mkdir(parents=True, exist_ok=True)
    _copy_tree(other.paths.run_dir(stolen), first.paths.run_dir(stolen))

    with pytest.raises(ConflictError) as raised:
        first.start()

    assert raised.value.code == "draft_already_started"


def _copy_tree(source: Path, destination: Path) -> None:
    for item in sorted(source.rglob("*")):
        target = destination / item.relative_to(source)
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(item.read_bytes())


def test_a_completed_run_is_not_relaunched(harness: RunHarness) -> None:
    run_id = harness.start().state.run_id
    execute_in_process(harness, run_id)
    harness.launcher.launched.clear()

    again = harness.start()

    assert again.state.phase is RunPhase.COMPLETED
    assert harness.launcher.launched == []


# ---------------------------------------------------------------------------
# A launch that fails
# ---------------------------------------------------------------------------


def test_a_failed_launch_leaves_an_addressable_failed_run(
    temp_techtree_home: Path,
) -> None:
    failing = run_harness(
        temp_techtree_home,
        launcher_failure=RunError("no worker today", code="worker_launch_failed"),
    )

    with pytest.raises(RunError) as raised:
        failing.start()

    record = failing.drafts.start_record(failing.draft_id)
    assert raised.value.code == "worker_launch_failed"
    assert record is not None
    assert record.status is DraftStartStatus.LAUNCH_FAILED
    assert record.launch_error_code == "worker_launch_failed"
    state = failing.run_store.state(record.run_id)
    assert state.phase is RunPhase.FAILED
    assert state.error is not None
    assert state.error.code == "worker_launch_failed"


def test_a_failed_launch_still_consumed_the_confirmation(
    temp_techtree_home: Path,
) -> None:
    failing = run_harness(
        temp_techtree_home,
        launcher_failure=RunError("no worker today", code="worker_launch_failed"),
    )
    with pytest.raises(RunError):
        failing.start()

    assert failing.drafts.get_confirmation(failing.draft_id).consumed_at is not None


def test_retrying_a_failed_launch_returns_the_same_failed_run(
    temp_techtree_home: Path,
) -> None:
    """A draft is spent on exactly one run, including one that never started."""
    failing = run_harness(
        temp_techtree_home,
        launcher_failure=RunError("no worker today", code="worker_launch_failed"),
    )
    with pytest.raises(RunError):
        failing.start()
    first = failing.drafts.start_record(failing.draft_id)

    with pytest.raises(RunError) as raised:
        failing.start()

    assert first is not None
    assert raised.value.details["run_id"] == first.run_id
    assert len(list(failing.paths.runs_dir.iterdir())) == 1


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def test_status_reports_a_worker_that_is_gone_without_failing_the_run(
    harness: RunHarness,
) -> None:
    """Spec §8.8: reading a run's status never invents a transition."""
    run_id = harness.start().state.run_id
    harness.launcher.alive.clear()
    harness.run_store.write_heartbeat(run_id, RunPhase.RUNNING_BASELINE)

    status = harness.service.status(run_id)

    assert status.worker_alive is False
    assert status.state.phase is RunPhase.CREATED
    assert status.result_available is False


def test_a_heartbeat_that_has_stopped_is_reported_stale(
    temp_techtree_home: Path,
) -> None:
    later = utc_now() + timedelta(hours=1)
    harness = run_harness(temp_techtree_home, clock=lambda: later)
    run_id = harness.start().state.run_id
    harness.run_store.write_heartbeat(run_id, RunPhase.CREATED)

    health = harness.service.process_health(run_id)

    assert health.heartbeat_age_seconds is not None
    assert health.heartbeat_age_seconds > 3000
    assert health.heartbeat_stale is True


def test_a_finished_run_is_not_reported_as_a_stale_heartbeat(
    harness: RunHarness,
) -> None:
    run_id = harness.start().state.run_id
    execute_in_process(harness, run_id)

    status = harness.service.status(run_id)

    assert status.state.phase is RunPhase.COMPLETED
    assert status.heartbeat_stale is False
    assert status.result_available is True


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------


def _write_log(harness: RunHarness, run_id: str, text: str) -> None:
    harness.run_store.worker_log_path(run_id).write_text(text, encoding="utf-8")


def test_logs_return_the_last_lines_and_say_they_were_cut(
    harness: RunHarness,
) -> None:
    run_id = harness.start().state.run_id
    _write_log(harness, run_id, "".join(f"line {number}\n" for number in range(500)))

    logs = harness.service.logs(run_id, tail=10)

    assert logs.lines == [f"line {number}" for number in range(490, 500)]
    assert logs.truncated is True


def test_a_short_log_is_not_truncated(harness: RunHarness) -> None:
    run_id = harness.start().state.run_id
    _write_log(harness, run_id, "one\ntwo\n")

    logs = harness.service.logs(run_id, tail=DEFAULT_LOG_TAIL)

    assert logs.lines == ["one", "two"]
    assert logs.truncated is False


@pytest.mark.parametrize("tail", [0, -1, 5001])
def test_a_tail_outside_its_bounds_is_a_usage_error(
    harness: RunHarness, tail: int
) -> None:
    run_id = harness.start().state.run_id

    with pytest.raises(UsageError):
        harness.service.logs(run_id, tail=tail)


@pytest.mark.parametrize("tail", [1, 5000])
def test_the_bounds_themselves_are_allowed(harness: RunHarness, tail: int) -> None:
    run_id = harness.start().state.run_id
    _write_log(harness, run_id, "only line\n")

    assert harness.service.logs(run_id, tail=tail).lines == ["only line"]


def test_a_run_that_has_written_no_log_says_so(harness: RunHarness) -> None:
    run_id = harness.start().state.run_id

    with pytest.raises(TechtreeError) as raised:
        harness.service.logs(run_id)

    assert raised.value.code == "run_logs_unavailable"
    assert raised.value.retryable is True


def test_a_bearer_token_in_the_log_is_scrubbed(harness: RunHarness) -> None:
    run_id = harness.start().state.run_id
    _write_log(
        harness,
        run_id,
        "GET /v1/x\nAuthorization: Bearer sk-live-abcdefghijklmnopqrstuvwxyz\n",
    )

    logs = harness.service.logs(run_id)

    assert "sk-live-abcdefghijklmnopqrstuvwxyz" not in "\n".join(logs.lines)
    assert "[redacted]" in "\n".join(logs.lines)


def test_a_quoted_json_key_in_the_log_is_scrubbed(harness: RunHarness) -> None:
    run_id = harness.start().state.run_id
    _write_log(
        harness,
        run_id,
        '{"api_key": "sk-live-0123456789abcdef", "model_id": "development"}\n',
    )

    line = harness.service.logs(run_id).lines[0]

    assert "sk-live-0123456789abcdef" not in line
    assert "[redacted]" in line
    assert "development" in line


def test_scrubbing_leaves_useful_diagnostics_alone(harness: RunHarness) -> None:
    run_id = harness.start().state.run_id
    digest = f"sha256:{'a' * 64}"
    _write_log(harness, run_id, f"staged inputs for {run_id} at {digest}\n")

    line = harness.service.logs(run_id).lines[0]

    assert run_id in line
    assert digest in line


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


def test_a_result_asked_for_too_early_is_refused_and_retryable(
    harness: RunHarness,
) -> None:
    run_id = harness.start().state.run_id

    with pytest.raises(RunError) as raised:
        harness.service.result(run_id)

    assert raised.value.code == "run_result_not_ready"
    assert raised.value.retryable is True


def test_a_finished_run_returns_its_report(harness: RunHarness) -> None:
    run_id = harness.start().state.run_id
    written = execute_in_process(harness, run_id)

    assert harness.service.result(run_id) == written


def test_a_report_that_is_not_what_the_journal_named_is_refused(
    harness: RunHarness,
) -> None:
    run_id = harness.start().state.run_id
    report = execute_in_process(harness, run_id)
    tampered = report.model_copy(update={"publication_eligible": False, "id": "other"})
    path = harness.run_store.result_path(run_id)
    path.chmod(0o600)
    path.write_bytes(canonical_json_bytes(tampered))

    with pytest.raises(VerificationError) as raised:
        harness.service.result(run_id)

    assert raised.value.code == "run_result_digest_mismatch"


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


def test_cancelling_a_running_run_asks_it_to_stop(harness: RunHarness) -> None:
    run_id = harness.start().state.run_id

    cancellation = harness.service.cancel(run_id)

    assert cancellation.outcome == "requested"
    assert cancellation.status.state.phase is RunPhase.CANCEL_REQUESTED
    assert harness.launcher.terminated == [run_id]


def test_cancelling_twice_changes_nothing(harness: RunHarness) -> None:
    run_id = harness.start().state.run_id
    first = harness.service.cancel(run_id)

    second = harness.service.cancel(run_id)

    assert second.outcome == "already_requested"
    assert (
        second.status.state.cancel_requested_at
        == first.status.state.cancel_requested_at
    )
    assert second.status.state.sequence == first.status.state.sequence


def test_cancelling_a_finished_run_leaves_its_result_alone(
    harness: RunHarness,
) -> None:
    run_id = harness.start().state.run_id
    report = execute_in_process(harness, run_id)
    before = harness.run_store.state(run_id)

    cancellation = harness.service.cancel(run_id)

    assert cancellation.outcome == "already_terminal"
    assert cancellation.status.state.phase is RunPhase.COMPLETED
    assert harness.run_store.state(run_id).sequence == before.sequence
    assert harness.service.result(run_id) == report
    assert harness.launcher.terminated == []


# ---------------------------------------------------------------------------
# The detached worker's own half of the lifecycle
# ---------------------------------------------------------------------------


class BreakingExecutor:
    """An executor that fails the way the thing it stands in for might."""

    def __init__(self, error: BaseException) -> None:
        self._error = error

    def execute(self, context: ExecutionContext) -> UpliftReport:
        """Fail."""
        raise self._error


def _refuse_to_record_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the journal fail on the completion event, and only on that.

    Spec §9.7's crash window: the report is durable and the event announcing
    it is not.
    """
    original = RunStore.append

    def append(
        self: RunStore,
        run_id: str,
        *,
        phase: RunPhase,
        kind: str = PHASE_ENTERED,
        details: dict[str, JsonValue] | None = None,
    ) -> RunState:
        if kind == RUN_COMPLETED:
            raise RunError(
                "the journal could not record the completion",
                code="run_write_failed",
            )
        return original(self, run_id, phase=phase, kind=kind, details=details)

    monkeypatch.setattr(RunStore, "append", append)


def _run_worker(
    harness: RunHarness,
    run_id: str,
    executor: object,
) -> int:
    clear_local_cancellation()
    return execute_run(
        run_id,
        paths=harness.paths,
        executor_factory=lambda request: executor,  # type: ignore[arg-type,return-value]
    )


def test_the_worker_finishes_a_healthy_run_and_exits_zero(
    harness: RunHarness,
) -> None:
    run_id = harness.start().state.run_id

    code = _run_worker(harness, run_id, FakeRunExecutor(step_delay_seconds=0.0))

    assert code == 0
    assert harness.run_store.state(run_id).phase is RunPhase.COMPLETED
    assert harness.service.result(run_id).run_id == run_id


def test_the_worker_records_a_controlled_failure_and_maps_its_code(
    harness: RunHarness,
) -> None:
    run_id = harness.start().state.run_id
    failure = VerificationError(
        "the taskset did not validate", code="taskset_validation_invalid"
    )

    code = _run_worker(harness, run_id, BreakingExecutor(failure))

    state = harness.run_store.state(run_id)
    assert code == EXIT_VERIFICATION
    assert state.phase is RunPhase.FAILED
    assert state.error is not None
    assert state.error.code == "taskset_validation_invalid"


def test_an_unexpected_failure_becomes_a_scrubbed_internal_error(
    harness: RunHarness,
) -> None:
    """Spec §8.10: no raw traceback, and no secret, reaches RunState.error."""
    run_id = harness.start().state.run_id
    leaky = RuntimeError(
        'boom while calling api_key="sk-live-0123456789abcdef" at 0x7fabcdef1234'
    )

    code = _run_worker(harness, run_id, BreakingExecutor(leaky))

    state = harness.run_store.state(run_id)
    assert code == EXIT_UNEXPECTED
    assert state.phase is RunPhase.FAILED
    assert state.error is not None
    assert state.error.code == "internal_error"
    assert "sk-live-0123456789abcdef" not in state.error.message
    assert "[redacted]" in state.error.message
    assert "Traceback" not in state.error.message


def test_a_cancelled_worker_ends_the_run_and_exits_one_hundred_and_thirty(
    harness: RunHarness,
) -> None:
    run_id = harness.start().state.run_id
    cancelled = CancellationError("stop", details={"run_id": run_id})

    code = _run_worker(harness, run_id, BreakingExecutor(cancelled))

    assert code == EXIT_CANCELLED
    assert harness.run_store.state(run_id).phase is RunPhase.CANCELLED


def test_the_worker_leaves_a_heartbeat_behind(harness: RunHarness) -> None:
    run_id = harness.start().state.run_id

    _run_worker(harness, run_id, FakeRunExecutor(step_delay_seconds=0.0))

    assert (harness.paths.run_dir(run_id) / "heartbeat.json").exists()
    assert harness.run_store.state(run_id).heartbeat_at is not None


def test_a_report_written_without_its_completion_event_is_detected(
    harness: RunHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec §9.7: the report is durable, the completion is not. Say so."""
    run_id = harness.start().state.run_id
    _refuse_to_record_completion(monkeypatch)

    code = _run_worker(harness, run_id, FakeRunExecutor(step_delay_seconds=0.0))

    assert code != 0
    assert harness.run_store.result_path(run_id).exists()
    state = harness.run_store.state(run_id)
    assert state.phase is not RunPhase.COMPLETED
    assert state.result_digest is not None
    with pytest.raises(RunError) as raised:
        harness.service.result(run_id)
    assert raised.value.code == "run_result_not_ready"


def test_a_worker_will_not_take_on_a_run_that_has_ended(
    harness: RunHarness,
) -> None:
    run_id = harness.start().state.run_id
    execute_in_process(harness, run_id)
    before = harness.run_store.state(run_id)

    code = _run_worker(harness, run_id, FakeRunExecutor(step_delay_seconds=0.0))

    assert code != 0
    assert harness.run_store.state(run_id).sequence == before.sequence
