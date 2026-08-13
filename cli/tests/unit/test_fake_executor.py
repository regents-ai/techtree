"""The development executor. Spec PR8 §8.6, §8.17, §10.6.

Two halves. The first is that the executor does the real work around the fake
numbers: every phase in order, the validation provider consulted once and its
answer enforced, one receipt per Campaign task per variant in committed order,
the comparison recomputed rather than trusted, and the aggregation joined by
task hash.

The second is that nothing it produces can be mistaken for evidence. Spec
§10.6 lists six fields no PR8 code path may set to a real value, and they are
asserted here one at a time rather than as a summary, because a summary that
drifted would still pass.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from fixtures.runs.support import (
    RunHarness,
    execute_in_process,
    execution_context,
    run_harness,
)
from techtree.canonical import digest_object
from techtree.errors import CancellationError, VerificationError
from techtree.models.episode_receipt import EvidenceStatus, ScoreStatus
from techtree.models.experiment import ExperimentVariant
from techtree.models.run import RunEvent, RunPhase
from techtree.models.uplift_report import (
    ComparisonStatus,
    ExecutionStatus,
    PublicationStatus,
    UpliftDecision,
)
from techtree.runs.artifacts import RunInputBundle
from techtree.runs.events import (
    PHASE_ENTERED,
    PROGRESS_UPDATED,
    RUN_COMPLETED,
    read_events,
)
from techtree.runs.fake import (
    FakeRunExecutor,
    aggregate_fake_results,
    default_fake_rewards,
)
from techtree.runs.validation import (
    PublisherFixtureValidationProvider,
    TasksetValidationOutcome,
)


@pytest.fixture
def created(temp_techtree_home: Path) -> tuple[RunHarness, str]:
    """Return a harness with one created, staged, unexecuted run."""
    harness = run_harness(temp_techtree_home)
    return harness, harness.start().state.run_id


class CountingProvider:
    """A provider that answers correctly and counts how often it is asked."""

    def __init__(self) -> None:
        self.calls = 0
        self._real = PublisherFixtureValidationProvider()

    def validate(
        self, *, run_id: str, inputs: RunInputBundle
    ) -> TasksetValidationOutcome:
        """Delegate, counting."""
        self.calls += 1
        return self._real.validate(run_id=run_id, inputs=inputs)


class RefusingProvider:
    """A provider that reports the taskset is not fit to be scored."""

    def validate(
        self, *, run_id: str, inputs: RunInputBundle
    ) -> TasksetValidationOutcome:
        """Refuse."""
        raise VerificationError(
            "the taskset did not validate",
            code="taskset_validation_invalid",
            details={"run_id": run_id},
        )


# ---------------------------------------------------------------------------
# Reward vectors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("task_count", "baseline_successes", "candidate_successes"),
    [(1, 1, 1), (2, 1, 2), (4, 1, 3), (10, 2, 8), (100, 25, 85)],
)
def test_default_rewards_follow_the_stated_fractions(
    task_count: int, baseline_successes: int, candidate_successes: int
) -> None:
    baseline, candidate = default_fake_rewards(task_count)

    assert len(baseline) == len(candidate) == task_count
    assert sum(baseline) == baseline_successes
    assert sum(candidate) == candidate_successes


def test_default_rewards_put_successes_first() -> None:
    """Deterministic fixtures, and no meaning attached to position."""
    baseline, candidate = default_fake_rewards(8)

    assert baseline == [1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert candidate == [1.0] * 6 + [0.0] * 2


def test_an_empty_taskset_produces_no_rewards() -> None:
    assert default_fake_rewards(0) == ([], [])


# ---------------------------------------------------------------------------
# The phases
# ---------------------------------------------------------------------------


def test_every_phase_is_entered_in_order(created: tuple[RunHarness, str]) -> None:
    harness, run_id = created

    execute_in_process(harness, run_id)

    entered = [
        event.phase
        for event in _events(harness, run_id)
        if event.kind in (PHASE_ENTERED, RUN_COMPLETED)
    ]
    assert entered == [
        RunPhase.VALIDATING_TASKSET,
        RunPhase.RUNNING_BASELINE,
        RunPhase.RUNNING_CANDIDATE,
        RunPhase.BUILDING_RECEIPTS,
        RunPhase.VERIFYING_COMPARISON,
        RunPhase.BUILDING_REPORT,
        RunPhase.COMPLETED,
    ]


def test_progress_is_reported_once_per_episode(
    created: tuple[RunHarness, str],
) -> None:
    harness, run_id = created
    total = len(harness.inputs(run_id).ordered_task_hashes)

    execute_in_process(harness, run_id)

    progress = [
        event for event in _events(harness, run_id) if event.kind == PROGRESS_UPDATED
    ]
    assert len(progress) == total * 2
    assert [event.details["current"] for event in progress[:total]] == list(
        range(1, total + 1)
    )


def test_the_validation_provider_is_asked_exactly_once(
    created: tuple[RunHarness, str],
) -> None:
    harness, run_id = created
    provider = CountingProvider()

    execute_in_process(harness, run_id, provider=provider)

    assert provider.calls == 1


def test_a_refused_validation_stops_before_any_episode(
    created: tuple[RunHarness, str],
) -> None:
    harness, run_id = created

    with pytest.raises(VerificationError):
        execute_in_process(harness, run_id, provider=RefusingProvider())

    assert harness.artifacts.episode_receipts(run_id, ExperimentVariant.BASELINE) == []
    assert harness.run_store.state(run_id).phase is RunPhase.VALIDATING_TASKSET


def test_the_marker_is_written_before_the_first_episode(
    created: tuple[RunHarness, str],
) -> None:
    harness, run_id = created

    execute_in_process(harness, run_id)

    marker = harness.paths.run_dir(run_id) / "validation" / "development.json"
    assert marker.exists()


# ---------------------------------------------------------------------------
# The receipts
# ---------------------------------------------------------------------------


def test_there_is_one_receipt_per_task_per_variant(
    created: tuple[RunHarness, str],
) -> None:
    harness, run_id = created
    hashes = harness.inputs(run_id).ordered_task_hashes

    execute_in_process(harness, run_id)

    baseline = harness.artifacts.episode_receipts(run_id, ExperimentVariant.BASELINE)
    candidate = harness.artifacts.episode_receipts(run_id, ExperimentVariant.CANDIDATE)
    assert len(baseline) + len(candidate) == len(hashes) * 2


def test_receipts_follow_the_committed_membership_order(
    created: tuple[RunHarness, str],
) -> None:
    harness, run_id = created
    hashes = harness.inputs(run_id).ordered_task_hashes

    execute_in_process(harness, run_id)

    for variant in ExperimentVariant:
        receipts = harness.artifacts.episode_receipts(run_id, variant)
        assert [receipt.task_hash for receipt in receipts] == hashes


def test_every_generic_campaign_reference_propagates_exactly(
    created: tuple[RunHarness, str],
) -> None:
    """Spec §8.6: the receipt's lineage is copied, never re-derived."""
    harness, run_id = created
    request = harness.request(run_id)
    campaign = harness.inputs(run_id).campaign

    execute_in_process(harness, run_id)

    for variant in ExperimentVariant:
        for receipt in harness.artifacts.episode_receipts(run_id, variant):
            assert receipt.run_id == run_id
            assert receipt.campaign_spec_digest == request.campaign_spec_digest
            assert receipt.program_ref == request.program_ref
            assert receipt.public_context == request.public_context
            assert receipt.data_policy_digest == request.data_policy_digest
            assert receipt.outcome_contract_digest == request.outcome_contract_digest
            assert receipt.evaluation_backend == campaign.evaluation_backend
            assert receipt.variant is variant


def test_a_receipt_names_the_manifest_its_variant_ran(
    created: tuple[RunHarness, str],
) -> None:
    harness, run_id = created
    request = harness.request(run_id)

    execute_in_process(harness, run_id)

    baseline = harness.artifacts.episode_receipts(run_id, ExperimentVariant.BASELINE)
    candidate = harness.artifacts.episode_receipts(run_id, ExperimentVariant.CANDIDATE)
    assert {receipt.experiment_manifest_digest for receipt in baseline} == {
        request.baseline_manifest_digest
    }
    assert {receipt.experiment_manifest_digest for receipt in candidate} == {
        request.candidate_manifest_digest
    }


def test_no_subject_runtime_ever_executed(created: tuple[RunHarness, str]) -> None:
    harness, run_id = created

    execute_in_process(harness, run_id)

    for variant in ExperimentVariant:
        for receipt in harness.artifacts.episode_receipts(run_id, variant):
            assert receipt.subject_runtime.kind == "not_executed"
            assert receipt.subject_runtime.resolved_image_digest is None
            assert receipt.subject_runtime.platform is None


def test_every_receipt_is_marked_development_only(
    created: tuple[RunHarness, str],
) -> None:
    harness, run_id = created

    execute_in_process(harness, run_id)

    for variant in ExperimentVariant:
        for receipt in harness.artifacts.episode_receipts(run_id, variant):
            assert receipt.execution_backend == "fake"
            assert receipt.score_status is ScoreStatus.DEVELOPMENT_ONLY
            assert receipt.evidence_status is EvidenceStatus.DEVELOPMENT_ONLY


def test_a_receipt_carries_exactly_one_subject_trace(
    created: tuple[RunHarness, str],
) -> None:
    harness, run_id = created
    reward_name = harness.inputs(run_id).campaign.scoring.primary_reward

    execute_in_process(harness, run_id)

    receipt = harness.artifacts.episode_receipts(run_id, ExperimentVariant.BASELINE)[0]
    traces = receipt.named_traces["subject"]
    assert list(receipt.named_traces) == ["subject"]
    assert len(traces) == 1
    assert traces[0].task_hash == receipt.task_hash
    assert list(traces[0].rewards) == [reward_name]
    assert receipt.artifacts[0].digest == traces[0].trace_digest


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


def test_the_report_cannot_be_published(created: tuple[RunHarness, str]) -> None:
    """Spec §10.6, one field at a time."""
    harness, run_id = created

    report = execute_in_process(harness, run_id)

    assert report.publication_eligible is False
    assert report.proof_grade == "development_only"
    assert report.decision is UpliftDecision.DEVELOPMENT_ONLY
    assert report.statuses.score is ScoreStatus.DEVELOPMENT_ONLY
    assert report.statuses.evidence is EvidenceStatus.DEVELOPMENT_ONLY
    assert report.statuses.comparison is ComparisonStatus.DEVELOPMENT_ONLY
    assert report.statuses.publication is PublicationStatus.BLOCKED
    assert report.statuses.execution is ExecutionStatus.COMPLETED


def test_the_report_carries_the_campaign_lineage(
    created: tuple[RunHarness, str],
) -> None:
    harness, run_id = created
    request = harness.request(run_id)
    inputs = harness.inputs(run_id)

    report = execute_in_process(harness, run_id)

    assert report.run_id == run_id
    assert report.campaign_spec_digest == request.campaign_spec_digest
    assert report.data_policy_digest == request.data_policy_digest
    assert report.public_context == request.public_context
    assert report.program_ref == request.program_ref
    assert report.evaluation_backend == inputs.campaign.evaluation_backend
    assert report.taskset_validation_receipt_digest == digest_object(
        inputs.resolved_climb.publisher_validation
    )
    assert report.manifest_comparison == inputs.comparison


def test_the_report_is_recorded_in_the_journal(
    created: tuple[RunHarness, str],
) -> None:
    harness, run_id = created

    report = execute_in_process(harness, run_id)

    state = harness.run_store.state(run_id)
    assert state.phase is RunPhase.COMPLETED
    assert state.result_digest == digest_object(report)
    assert harness.run_store.get_result(run_id) == report


def test_one_delta_per_committed_task_in_committed_order(
    created: tuple[RunHarness, str],
) -> None:
    harness, run_id = created
    hashes = harness.inputs(run_id).ordered_task_hashes

    report = execute_in_process(harness, run_id)

    assert [delta.task_hash for delta in report.task_deltas] == hashes


def test_a_baseline_that_scored_nothing_has_no_relative_delta(
    created: tuple[RunHarness, str],
) -> None:
    harness, run_id = created
    count = len(harness.inputs(run_id).ordered_task_hashes)

    report = execute_in_process(
        harness,
        run_id,
        executor=FakeRunExecutor(
            step_delay_seconds=0.0,
            baseline_rewards=[0.0] * count,
            candidate_rewards=[1.0] * count,
        ),
    )

    assert report.primary_result.baseline_mean == 0.0
    assert report.primary_result.relative_delta is None
    assert report.primary_result.absolute_delta == 1.0
    assert report.primary_result.wins == count


def test_wins_losses_and_ties_are_counted_directly(
    created: tuple[RunHarness, str],
) -> None:
    harness, run_id = created

    report = execute_in_process(
        harness,
        run_id,
        executor=FakeRunExecutor(
            step_delay_seconds=0.0,
            baseline_rewards=[1.0, 0.0, 1.0, 1.0],
            candidate_rewards=[1.0, 1.0, 0.0, 1.0],
        ),
    )

    assert (
        report.primary_result.wins,
        report.primary_result.losses,
        report.primary_result.ties,
    ) == (1, 1, 2)


def test_the_join_is_by_task_hash_and_not_by_file_order(
    created: tuple[RunHarness, str],
) -> None:
    """Reverse one variant's receipts and the same answer must come out."""
    harness, run_id = created
    hashes = harness.inputs(run_id).ordered_task_hashes
    reward_name = harness.inputs(run_id).campaign.scoring.primary_reward

    execute_in_process(harness, run_id)
    baseline = harness.artifacts.episode_receipts(run_id, ExperimentVariant.BASELINE)
    candidate = harness.artifacts.episode_receipts(run_id, ExperimentVariant.CANDIDATE)

    ordered, deltas = aggregate_fake_results(
        reward_name=reward_name,
        baseline=baseline,
        candidate=candidate,
        ordered_task_hashes=hashes,
    )
    shuffled, shuffled_deltas = aggregate_fake_results(
        reward_name=reward_name,
        baseline=list(reversed(baseline)),
        candidate=list(reversed(candidate)),
        ordered_task_hashes=hashes,
    )

    assert ordered == shuffled
    assert deltas == shuffled_deltas


def test_a_variant_missing_a_task_is_refused(
    created: tuple[RunHarness, str],
) -> None:
    harness, run_id = created
    hashes = harness.inputs(run_id).ordered_task_hashes

    execute_in_process(harness, run_id)
    baseline = harness.artifacts.episode_receipts(run_id, ExperimentVariant.BASELINE)
    candidate = harness.artifacts.episode_receipts(run_id, ExperimentVariant.CANDIDATE)

    with pytest.raises(VerificationError) as raised:
        aggregate_fake_results(
            reward_name=harness.inputs(run_id).campaign.scoring.primary_reward,
            baseline=baseline[:-1],
            candidate=candidate,
            ordered_task_hashes=hashes,
        )

    assert raised.value.code == "fake_receipt_invalid"


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


def test_cancelling_during_validation_stops_the_run(
    created: tuple[RunHarness, str],
) -> None:
    harness, run_id = created

    class CancellingProvider:
        def validate(
            self, *, run_id: str, inputs: RunInputBundle
        ) -> TasksetValidationOutcome:
            outcome = PublisherFixtureValidationProvider().validate(
                run_id=run_id, inputs=inputs
            )
            harness.run_store.request_cancel(run_id, requested_by="test")
            return outcome

    with pytest.raises(CancellationError):
        execute_in_process(harness, run_id, provider=CancellingProvider())

    assert harness.run_store.state(run_id).phase is RunPhase.CANCEL_REQUESTED
    assert harness.artifacts.episode_receipts(run_id, ExperimentVariant.BASELINE) == []


@pytest.mark.parametrize(
    "variant", [ExperimentVariant.BASELINE, ExperimentVariant.CANDIDATE]
)
def test_cancelling_mid_variant_stops_before_the_next_episode(
    created: tuple[RunHarness, str],
    variant: ExperimentVariant,
) -> None:
    """A run asked to stop while scoring stops at the next episode boundary."""
    harness, run_id = created
    total = len(harness.inputs(run_id).ordered_task_hashes)
    executor = FakeRunExecutor(step_delay_seconds=0.05)
    context = execution_context(harness, run_id)
    failure: list[BaseException] = []

    def execute() -> None:
        try:
            executor.execute(context)
        except BaseException as error:
            failure.append(error)

    worker = threading.Thread(target=execute)
    worker.start()
    try:
        _wait_until(lambda: _receipt_count(harness, run_id, variant) >= 1)
        harness.run_store.request_cancel(run_id, requested_by="test")
    finally:
        worker.join(timeout=30)

    assert not worker.is_alive()
    assert isinstance(failure[0], CancellationError)
    assert harness.run_store.state(run_id).phase is RunPhase.CANCEL_REQUESTED
    written = sum(_receipt_count(harness, run_id, each) for each in ExperimentVariant)
    assert _receipt_count(harness, run_id, variant) >= 1
    assert written < total * 2
    assert not harness.run_store.result_path(run_id).exists()


def _receipt_count(harness: RunHarness, run_id: str, variant: ExperimentVariant) -> int:
    return len(harness.artifacts.episode_receipts(run_id, variant))


def _wait_until(condition: Callable[[], bool], *, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("condition was never met")


def _events(harness: RunHarness, run_id: str) -> list[RunEvent]:
    return read_events(harness.paths.run_dir(run_id) / "events.jsonl")
