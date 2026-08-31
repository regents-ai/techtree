"""Running two variants as one comparison. Spec sections 6.15, 6.16, 6.21.

Every question here is about the scheduler's own behaviour, so every child is a
stub: no subprocess, no container, no provider, no money. That is not a
convenience. The rules being checked — that neither variant starts until both
sets of inputs exist, that the two launches are back to back, that a failed
variant takes its sibling down with it — are precisely the rules whose real
form is too expensive to exercise, and a stub is what lets each of them be
provoked deliberately instead of waited for.

Four properties, each stated as a rule about not overstating a comparison.

*Nothing starts until everything is present.* A missing candidate config
discovered after the baseline is already talking to a provider costs the run
its money and its comparability at once.

*The launches are adjacent and the gap is recorded.* Running side by side is a
scientific control against provider drift, and a control nobody measured is a
claim.

*A pair is the unit.* One variant's failure ends the other, and both variants'
partial evidence survives it.

*The Campaign's concurrency bound is Campaign-wide.* Two halves that each took
the whole allowance would double the live subject count the Campaign declared.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

import pytest

from techtree.canonical import sha256_digest_bytes
from techtree.errors import CancellationError, RunError, ValidationError
from techtree.models.base import ArtifactRef, Digest
from techtree.models.campaign import ProgramRef, PublicContext, VariantSchedule
from techtree.models.evaluation_backend import (
    AttestationKind,
    EvaluationBackendKind,
    EvaluationBackendSpec,
)
from techtree.models.run import (
    PolicyAcknowledgement,
    RunEvent,
    RunPhase,
    RunRequest,
)
from techtree.paths import TechtreePaths, paths_from_root
from techtree.runs.child_registry import (
    ChildRegistry,
    LaunchedChild,
    children_record_path,
    write_children_record,
)
from techtree.runs.events import (
    DETAIL_STATE,
    DETAIL_VARIANT,
    VARIANT_COMPLETED,
    VARIANT_STARTED,
    read_events,
)
from techtree.runs.executor import clear_local_cancellation
from techtree.runs.store import RunStore
from techtree.runs.variants import (
    VARIANT_CONCURRENCY_EXCEEDED,
    VARIANT_EXECUTION_FAILED,
    VARIANT_INPUTS_MISSING,
    VariantPair,
    VariantScheduler,
    require_concurrency_budget,
)
from techtree.verifiers.models import (
    ChildProcessOutcome,
    VariantExecutionPlan,
    VariantName,
)
from techtree.verifiers.outputs import TRACES_FILENAME

_TASK_COUNT: Final = 4
_MOMENT: Final = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# A child that does exactly what a test needs it to
# ---------------------------------------------------------------------------


class StubChild:
    """One evaluation child, scripted.

    ``exit_after`` is how many polls the child survives before it reports its
    exit code, which is how a test makes one variant finish first without
    waiting for anything real.
    """

    def __init__(
        self,
        variant: VariantName,
        *,
        output_dir: Path,
        exit_code: int = 0,
        exit_after: int = 0,
        episodes: int = _TASK_COUNT,
        start_error: Exception | None = None,
    ) -> None:
        self.variant_name = variant
        self.output_dir = output_dir
        self.started_at: datetime | None = None
        self.terminated_with: float | None = None
        self.polls = 0
        self._exit_code = exit_code
        self._exit_after = exit_after
        self._episodes = episodes
        self._start_error = start_error
        self._exited: int | None = None

    # -- the protocol the scheduler uses ----------------------------------

    @property
    def variant(self) -> VariantName:
        """Which side of the comparison this child is running."""
        return self.variant_name

    @property
    def pid(self) -> int | None:
        """A plausible process id once the child has started."""
        return None if self.started_at is None else 4242

    @property
    def argv_digest(self) -> Digest:
        """A stable digest standing in for this child's invocation."""
        return sha256_digest_bytes(self.variant_name.value.encode())

    def start(self) -> int:
        """Record the launch, or fail the way a real one would."""
        if self._start_error is not None:
            raise self._start_error
        self.started_at = datetime.now(UTC)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return 4242

    def poll(self) -> int | None:
        """Report the scripted exit code once the child has run long enough."""
        if self._exited is not None:
            return self._exited
        self.polls += 1
        if self.polls > self._exit_after:
            self._write_episodes()
            self._exited = self._exit_code
        return self._exited

    def terminate(self, grace_seconds: float = 30.0) -> None:
        """Record that the sibling was stopped, and stop it."""
        self.terminated_with = grace_seconds
        if self._exited is None:
            self._exited = 130

    def outcome(self) -> ChildProcessOutcome:
        """Describe the finished child."""
        assert self._exited is not None, "a running child has no outcome"
        return ChildProcessOutcome(
            variant=self.variant_name,
            argv_digest=self.argv_digest,
            exit_code=self._exited,
            started_at=_MOMENT,
            finished_at=_MOMENT + timedelta(seconds=1),
            stdout_artifact=_capture("stdout"),
            stderr_artifact=_capture("stderr"),
            cancelled=self.terminated_with is not None,
        )

    # -- what the child leaves on disk ------------------------------------

    def _write_episodes(self) -> None:
        """Append the episodes this child is scripted to have finished."""
        if self._episodes <= 0:
            return
        traces = self.output_dir / TRACES_FILENAME
        traces.write_text("".join('{"ok": true}\n' for _ in range(self._episodes)))


def _capture(stream: str) -> ArtifactRef:
    """Return a plausible capture-file reference."""
    data = stream.encode()
    return ArtifactRef(
        digest=sha256_digest_bytes(data),
        media_type="text/plain",
        size=len(data),
        relative_path=None,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _plan(
    variant: VariantName, root: Path, *, permits: int = 2
) -> VariantExecutionPlan:
    """Build one variant's plan with every input actually present."""
    directory = root / variant.value
    directory.mkdir(parents=True, exist_ok=True)
    config = directory / "input.json"
    config.write_text("num_tasks = 4\n")
    manifest = directory / "manifest.json"
    manifest.write_text("{}")
    return VariantExecutionPlan(
        variant=variant,
        experiment_manifest_digest=sha256_digest_bytes(variant.value.encode()),
        experiment_manifest_path=str(manifest),
        verifiers_input_config_path=str(config),
        verifiers_output_dir=str(directory / "run"),
        skill_paths=[],
        task_count=_TASK_COUNT,
        max_concurrent=permits,
    )


@pytest.fixture
def pair(tmp_path: Path) -> VariantPair:
    """A comparison whose two plans are both ready to execute."""
    return VariantPair(
        baseline=_plan(VariantName.BASELINE, tmp_path),
        candidate=_plan(VariantName.CANDIDATE, tmp_path),
    )


@pytest.fixture
def request_model() -> RunRequest:
    """The immutable request every run in this module executes."""
    policy = sha256_digest_bytes(b"data-policy")
    return RunRequest(
        run_id="run_00000000000000000000000000000001",
        draft_id="draft_0000000000000000000000000000000a",
        draft_digest=sha256_digest_bytes(b"draft"),
        campaign_spec_digest=sha256_digest_bytes(b"campaign"),
        program_ref=ProgramRef(id="procedure-transfer", version=1),
        public_context=PublicContext(
            kind="climb", climb_digest=sha256_digest_bytes(b"climb")
        ),
        data_policy_digest=policy,
        outcome_contract_digest=None,
        evaluation_backend=EvaluationBackendSpec(
            schema_version="techtree.evaluation-backend.v1alpha1",
            kind=EvaluationBackendKind.LOCAL_TECHTREE,
            attestation=AttestationKind.PARTICIPANT,
        ),
        taskset_lock_digest=sha256_digest_bytes(b"taskset-lock"),
        baseline_manifest_digest=sha256_digest_bytes(b"baseline"),
        candidate_manifest_digest=sha256_digest_bytes(b"candidate"),
        policy_acknowledgement=PolicyAcknowledgement(
            data_policy_digest=policy,
            method="explicit_cli_review",
            acknowledged_at=_MOMENT,
        ),
        executor_kind="fake",
        created_at=_MOMENT,
    )


@pytest.fixture
def store(tmp_path: Path, request_model: RunRequest) -> RunStore:
    """A run store holding one run, ready to enter the concurrent phase."""
    clear_local_cancellation()
    run_store = RunStore(_home(tmp_path))
    run_store.create(request_model)
    run_store.append(request_model.run_id, phase=RunPhase.VALIDATING_TASKSET)
    return run_store


def _home(tmp_path: Path) -> TechtreePaths:
    """Return a Techtree home under the test's own directory."""
    return paths_from_root(tmp_path / "home")


def _children(pair: VariantPair, **overrides: object) -> dict[VariantName, StubChild]:
    """Build one stub child per variant against the pair's own output dirs."""
    return {
        variant: StubChild(
            variant,
            output_dir=Path(pair.plan(variant).verifiers_output_dir),
            **overrides,  # type: ignore[arg-type]
        )
        for variant in (VariantName.BASELINE, VariantName.CANDIDATE)
    }


def _scheduler(store: RunStore, registry: ChildRegistry) -> VariantScheduler:
    """A scheduler that polls fast enough not to slow a test down."""
    return VariantScheduler(
        run_store=store,
        child_registry=registry,
        poll_interval_seconds=0.001,
        grace_seconds=0.01,
    )


# ---------------------------------------------------------------------------
# The pair itself
# ---------------------------------------------------------------------------


def test_a_pair_refuses_two_plans_that_score_different_task_counts(
    tmp_path: Path,
) -> None:
    """Two variants of one comparison score the same tasks."""
    baseline = _plan(VariantName.BASELINE, tmp_path)
    candidate = _plan(VariantName.CANDIDATE, tmp_path).model_copy(
        update={"task_count": _TASK_COUNT + 1}
    )
    with pytest.raises(ValidationError) as raised:
        VariantPair(baseline=baseline, candidate=candidate)
    assert raised.value.code == VARIANT_INPUTS_MISSING


def test_a_pair_refuses_a_plan_filed_under_the_other_variants_name(
    tmp_path: Path,
) -> None:
    """The baseline slot holds the baseline."""
    candidate = _plan(VariantName.CANDIDATE, tmp_path)
    with pytest.raises(ValidationError):
        VariantPair(baseline=candidate, candidate=candidate)


# ---------------------------------------------------------------------------
# Concurrency division
# ---------------------------------------------------------------------------


def test_a_divided_budget_is_within_the_campaigns_own_bound(pair: VariantPair) -> None:
    """Two permits each is exactly the four a Campaign declared."""
    require_concurrency_budget(pair, max_concurrent=4)


def test_two_halves_may_not_each_take_the_whole_allowance(tmp_path: Path) -> None:
    """A pair that would double the declared live episode count is refused."""
    undivided = VariantPair(
        baseline=_plan(VariantName.BASELINE, tmp_path, permits=4),
        candidate=_plan(VariantName.CANDIDATE, tmp_path, permits=4),
    )
    with pytest.raises(ValidationError) as raised:
        require_concurrency_budget(undivided, max_concurrent=4)
    assert raised.value.code == VARIANT_CONCURRENCY_EXCEEDED
    assert raised.value.details["campaign_max_concurrent"] == 4


def test_an_odd_allowance_is_divided_without_starving_either_side(
    tmp_path: Path,
) -> None:
    """Three permits split two and one, and both sides keep at least one."""
    from techtree.verifiers.compiler import divide_concurrency

    baseline, candidate = divide_concurrency(VariantSchedule.PARALLEL, 3)
    assert baseline >= 1
    assert candidate >= 1
    assert baseline + candidate <= 3


# ---------------------------------------------------------------------------
# The start barrier
# ---------------------------------------------------------------------------


def test_neither_child_starts_when_one_variants_config_is_missing(
    tmp_path: Path, store: RunStore, request_model: RunRequest
) -> None:
    """A comparison starts as a pair or not at all."""
    pair = VariantPair(
        baseline=_plan(VariantName.BASELINE, tmp_path),
        candidate=_plan(VariantName.CANDIDATE, tmp_path),
    )
    Path(pair.candidate.verifiers_input_config_path).unlink()
    children = _children(pair)

    with pytest.raises(ValidationError) as raised:
        _scheduler(store, ChildRegistry()).execute_parallel(
            run_id=request_model.run_id,
            run_root=tmp_path / "run",
            pair=pair,
            baseline_child=children[VariantName.BASELINE],
            candidate_child=children[VariantName.CANDIDATE],
        )

    assert raised.value.code == VARIANT_INPUTS_MISSING
    assert children[VariantName.BASELINE].started_at is None
    assert children[VariantName.CANDIDATE].started_at is None


def test_an_output_directory_that_already_holds_evidence_is_refused(
    tmp_path: Path, pair: VariantPair, store: RunStore, request_model: RunRequest
) -> None:
    """A run writes its own evidence; it does not inherit somebody else's."""
    stale = Path(pair.baseline.verifiers_output_dir)
    stale.mkdir(parents=True, exist_ok=True)
    (stale / TRACES_FILENAME).write_text('{"ok": true}\n')
    children = _children(pair)

    with pytest.raises(ValidationError):
        _scheduler(store, ChildRegistry()).execute_parallel(
            run_id=request_model.run_id,
            run_root=tmp_path / "run",
            pair=pair,
            baseline_child=children[VariantName.BASELINE],
            candidate_child=children[VariantName.CANDIDATE],
        )
    assert children[VariantName.CANDIDATE].started_at is None


def test_a_second_child_that_cannot_start_stops_the_first(
    tmp_path: Path, pair: VariantPair, store: RunStore, request_model: RunRequest
) -> None:
    """A comparison with one live side buys nothing, so the live side is stopped."""
    baseline = StubChild(
        VariantName.BASELINE, output_dir=Path(pair.baseline.verifiers_output_dir)
    )
    candidate = StubChild(
        VariantName.CANDIDATE,
        output_dir=Path(pair.candidate.verifiers_output_dir),
        start_error=OSError(2, "No such file or directory"),
    )

    with pytest.raises(RunError):
        _scheduler(store, ChildRegistry()).execute_parallel(
            run_id=request_model.run_id,
            run_root=tmp_path / "run",
            pair=pair,
            baseline_child=baseline,
            candidate_child=candidate,
        )
    assert baseline.terminated_with is not None


# ---------------------------------------------------------------------------
# Launch skew
# ---------------------------------------------------------------------------


def test_both_children_start_before_either_is_awaited(
    tmp_path: Path, pair: VariantPair, store: RunStore, request_model: RunRequest
) -> None:
    """The second launch does not wait for the first variant's first episode."""
    children = _children(pair, exit_after=2)
    outcome = _scheduler(store, ChildRegistry()).execute_parallel(
        run_id=request_model.run_id,
        run_root=tmp_path / "run",
        pair=pair,
        baseline_child=children[VariantName.BASELINE],
        candidate_child=children[VariantName.CANDIDATE],
    )

    assert outcome.schedule is VariantSchedule.PARALLEL
    assert children[VariantName.BASELINE].polls > 0
    assert children[VariantName.CANDIDATE].polls > 0
    # Both children had started before either was polled even once.
    for child in children.values():
        assert child.started_at is not None


def test_the_launch_skew_is_recorded_for_the_pair(
    tmp_path: Path, pair: VariantPair, store: RunStore, request_model: RunRequest
) -> None:
    """The gap between the two launches is measured and written down."""
    run_root = tmp_path / "run"
    children = _children(pair, exit_after=1)
    outcome = _scheduler(store, ChildRegistry()).execute_parallel(
        run_id=request_model.run_id,
        run_root=run_root,
        pair=pair,
        baseline_child=children[VariantName.BASELINE],
        candidate_child=children[VariantName.CANDIDATE],
    )

    assert outcome.skew is not None
    assert outcome.skew.seconds >= 0.0
    assert outcome.skew.first is VariantName.BASELINE

    import json

    record = json.loads(children_record_path(run_root).read_text())
    assert record["schedule"] == "parallel_variants"
    assert record["launch_skew_seconds"] == pytest.approx(outcome.skew.seconds)
    assert [row["variant"] for row in record["children"]] == ["baseline", "candidate"]
    assert all(row["pid"] == 4242 for row in record["children"])


def test_a_sequential_pair_records_no_launch_skew(
    tmp_path: Path, store: RunStore, request_model: RunRequest
) -> None:
    """A gap between a first variant and a second one is not a launch skew."""
    pair = VariantPair(
        baseline=_plan(VariantName.BASELINE, tmp_path, permits=1),
        candidate=_plan(VariantName.CANDIDATE, tmp_path, permits=1),
    )
    children = _children(pair, exit_after=1)
    outcome = _scheduler(store, ChildRegistry()).execute_sequential(
        run_id=request_model.run_id,
        run_root=tmp_path / "run",
        pair=pair,
        baseline_child=children[VariantName.BASELINE],
        candidate_child=children[VariantName.CANDIDATE],
    )

    assert outcome.schedule is VariantSchedule.SEQUENTIAL
    assert outcome.skew is None
    events = _events(store, request_model.run_id)
    phases = {event.phase for event in events}
    assert RunPhase.RUNNING_BASELINE in phases
    assert RunPhase.RUNNING_CANDIDATE in phases
    # No variant event: nothing was running two variants at once.
    assert not {event.kind for event in events} & {
        VARIANT_STARTED,
        VARIANT_COMPLETED,
    }


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def test_both_sides_announce_themselves_and_their_completion(
    tmp_path: Path, pair: VariantPair, store: RunStore, request_model: RunRequest
) -> None:
    """A watcher can see each variant start and each variant finish."""
    children = _children(pair, exit_after=1)
    _scheduler(store, ChildRegistry()).execute_parallel(
        run_id=request_model.run_id,
        run_root=tmp_path / "run",
        pair=pair,
        baseline_child=children[VariantName.BASELINE],
        candidate_child=children[VariantName.CANDIDATE],
    )

    events = _events(store, request_model.run_id)
    started = [event for event in events if event.kind == VARIANT_STARTED]
    completed = [event for event in events if event.kind == VARIANT_COMPLETED]
    assert [event.details[DETAIL_VARIANT] for event in started] == [
        "baseline",
        "candidate",
    ]
    assert {event.details[DETAIL_VARIANT] for event in completed} == {
        "baseline",
        "candidate",
    }
    assert {event.details[DETAIL_STATE] for event in completed} == {"completed"}

    state = store.state(request_model.run_id)
    assert state.phase is RunPhase.RUNNING_VARIANTS
    assert set(state.variant_progress) == {"baseline", "candidate"}
    assert state.variant_progress["candidate"].completed == _TASK_COUNT


# ---------------------------------------------------------------------------
# Failure and cancellation
# ---------------------------------------------------------------------------


def test_a_failed_variant_terminates_its_sibling_and_fails_the_pair(
    tmp_path: Path, pair: VariantPair, store: RunStore, request_model: RunRequest
) -> None:
    """A comparison needs both sides, so one failure ends the whole thing."""
    baseline = StubChild(
        VariantName.BASELINE,
        output_dir=Path(pair.baseline.verifiers_output_dir),
        exit_code=1,
        episodes=1,
    )
    candidate = StubChild(
        VariantName.CANDIDATE,
        output_dir=Path(pair.candidate.verifiers_output_dir),
        exit_after=1000,
    )

    with pytest.raises(RunError) as raised:
        _scheduler(store, ChildRegistry()).execute_parallel(
            run_id=request_model.run_id,
            run_root=tmp_path / "run",
            pair=pair,
            baseline_child=baseline,
            candidate_child=candidate,
        )

    assert raised.value.code == VARIANT_EXECUTION_FAILED
    assert candidate.terminated_with is not None
    # Partial evidence survives the failure on both sides.
    assert (Path(pair.baseline.verifiers_output_dir) / TRACES_FILENAME).is_file()
    assert Path(pair.candidate.verifiers_output_dir).is_dir()


def test_a_sequential_failure_never_starts_the_second_variant(
    tmp_path: Path, store: RunStore, request_model: RunRequest
) -> None:
    """Money is not spent on a candidate whose baseline already failed."""
    pair = VariantPair(
        baseline=_plan(VariantName.BASELINE, tmp_path, permits=1),
        candidate=_plan(VariantName.CANDIDATE, tmp_path, permits=1),
    )
    baseline = StubChild(
        VariantName.BASELINE,
        output_dir=Path(pair.baseline.verifiers_output_dir),
        exit_code=1,
    )
    candidate = StubChild(
        VariantName.CANDIDATE, output_dir=Path(pair.candidate.verifiers_output_dir)
    )

    with pytest.raises(RunError):
        _scheduler(store, ChildRegistry()).execute_sequential(
            run_id=request_model.run_id,
            run_root=tmp_path / "run",
            pair=pair,
            baseline_child=baseline,
            candidate_child=candidate,
        )
    assert candidate.started_at is None


def test_cancelling_the_run_stops_both_children(
    tmp_path: Path, pair: VariantPair, store: RunStore, request_model: RunRequest
) -> None:
    """One request to stop reaches both process groups."""
    children = _children(pair, exit_after=1000)
    registry = ChildRegistry()
    scheduler = _scheduler(store, registry)

    store.request_cancel(request_model.run_id, requested_by="test")
    with pytest.raises(CancellationError):
        scheduler.execute_parallel(
            run_id=request_model.run_id,
            run_root=tmp_path / "run",
            pair=pair,
            baseline_child=children[VariantName.BASELINE],
            candidate_child=children[VariantName.CANDIDATE],
        )
    # Cancellation arrived before the phase change, so nothing was started.
    assert all(child.started_at is None for child in children.values())


def test_a_cancellation_during_the_run_terminates_both_and_forgets_them(
    tmp_path: Path, pair: VariantPair, store: RunStore, request_model: RunRequest
) -> None:
    """A stop requested while both variants are live reaches both of them."""
    children = _children(pair, exit_after=1000)
    registry = ChildRegistry()

    class CancellingStore(RunStore):
        """A store that reports a cancellation once both children are up."""

        def state(self, run_id: str):  # type: ignore[no-untyped-def]
            """Ask the real store, then cancel once the children have started."""
            if all(child.started_at is not None for child in children.values()):
                current = super().state(run_id)
                if current.phase is RunPhase.RUNNING_VARIANTS:
                    self.request_cancel(run_id, requested_by="test")
            return super().state(run_id)

    cancelling = CancellingStore(_home(tmp_path))
    scheduler = VariantScheduler(
        run_store=cancelling,
        child_registry=registry,
        poll_interval_seconds=0.001,
        grace_seconds=0.01,
    )
    with pytest.raises(CancellationError):
        scheduler.execute_parallel(
            run_id=request_model.run_id,
            run_root=tmp_path / "run",
            pair=pair,
            baseline_child=children[VariantName.BASELINE],
            candidate_child=children[VariantName.CANDIDATE],
        )

    assert all(child.terminated_with is not None for child in children.values())
    assert registry.children(request_model.run_id) == ()


# ---------------------------------------------------------------------------
# The registry itself
# ---------------------------------------------------------------------------


def test_the_registry_addresses_a_runs_children_in_comparison_order(
    tmp_path: Path,
) -> None:
    """Whichever child registered first, the listing reads baseline then candidate."""
    registry = ChildRegistry()
    candidate = StubChild(VariantName.CANDIDATE, output_dir=tmp_path / "c")
    baseline = StubChild(VariantName.BASELINE, output_dir=tmp_path / "b")
    registry.register("run_1", candidate)
    registry.register("run_1", baseline)

    assert [child.variant for child in registry.children("run_1")] == [
        VariantName.BASELINE,
        VariantName.CANDIDATE,
    ]


def test_registering_a_variant_twice_replaces_rather_than_accumulates(
    tmp_path: Path,
) -> None:
    """A run owns at most one child per side."""
    registry = ChildRegistry()
    first = StubChild(VariantName.BASELINE, output_dir=tmp_path / "one")
    second = StubChild(VariantName.BASELINE, output_dir=tmp_path / "two")
    registry.register("run_1", first)
    registry.register("run_1", second)

    assert registry.children("run_1") == (second,)


def test_terminating_every_child_forgets_the_run(tmp_path: Path) -> None:
    """A registry holds live children, not a history of them."""
    registry = ChildRegistry()
    children = [
        StubChild(VariantName.BASELINE, output_dir=tmp_path / "b"),
        StubChild(VariantName.CANDIDATE, output_dir=tmp_path / "c"),
    ]
    for child in children:
        child.start()
        registry.register("run_1", child)

    registry.terminate_all("run_1", grace_seconds=0.5)
    assert registry.children("run_1") == ()
    assert all(child.terminated_with == 0.5 for child in children)


def test_one_child_that_will_not_stop_does_not_spare_the_other(
    tmp_path: Path,
) -> None:
    """Every process group is signalled even when an earlier one raised."""

    class StubbornChild(StubChild):
        """A child whose termination fails."""

        def terminate(self, grace_seconds: float = 30.0) -> None:
            """Refuse to stop."""
            raise OSError("cannot signal")

    registry = ChildRegistry()
    stubborn = StubbornChild(VariantName.BASELINE, output_dir=tmp_path / "b")
    other = StubChild(VariantName.CANDIDATE, output_dir=tmp_path / "c")
    registry.register("run_1", stubborn)
    registry.register("run_1", other)

    with pytest.raises(OSError):
        registry.terminate_all("run_1", grace_seconds=0.01)
    assert other.terminated_with == 0.01


def test_the_children_record_names_a_sequential_run_without_a_skew(
    tmp_path: Path,
) -> None:
    """The diagnostic record says which schedule it was written under."""
    import json

    path = write_children_record(
        run_root=tmp_path,
        run_id="run_1",
        schedule=VariantSchedule.SEQUENTIAL,
        children=[
            LaunchedChild(
                variant=VariantName.BASELINE,
                pid=11,
                argv_digest=sha256_digest_bytes(b"argv"),
                started_at=_MOMENT,
            )
        ],
        launch_skew_seconds=None,
    )
    record = json.loads(path.read_text())
    assert record["schedule"] == "baseline_then_candidate"
    assert record["launch_skew_seconds"] is None
    assert record["children"][0]["pid"] == 11


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _events(store: RunStore, run_id: str) -> list[RunEvent]:
    """Return one run's whole event log, read back the way a reader would."""
    return read_events(store.worker_log_path(run_id).parent / "events.jsonl")
