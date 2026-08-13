"""The run event log, state machine, and store. Spec sections 18.1 to 18.3.

Three properties carry the whole subsystem and each is tested directly.

*The transition table is the contract.* A run's phases are part of the CLI's
machine-facing output, so the table is written out again here by hand and
compared with the one the module derives. Every ordered pair of phases is then
pushed through :func:`validate_transition`, so a new edge cannot appear without
a test noticing.

*The log is the truth.* State produced step by step as a run advances must equal
state rebuilt from the log afterwards, and a log that skips a sequence number
must be refused rather than projected.

*Two writers never disagree.* Every mutation goes through the per-run lock, and
files written once are refused a second time.
"""

from __future__ import annotations

import itertools
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from filelock import FileLock

from techtree.canonical import canonical_json_bytes, digest_object, sha256_digest_bytes
from techtree.errors import ConflictError, NotFoundError, RunError, ValidationError
from techtree.models.base import Digest, JsonValue
from techtree.models.campaign import ProgramRef, PublicContext
from techtree.models.cli import CliError
from techtree.models.episode_receipt import EvidenceStatus, ScoreStatus
from techtree.models.evaluation_backend import (
    AttestationKind,
    EvaluationBackendKind,
    EvaluationBackendSpec,
)
from techtree.models.experiment import ManifestComparison
from techtree.models.run import (
    PolicyAcknowledgement,
    RunEvent,
    RunPhase,
    RunProgress,
    RunRequest,
    RunState,
)
from techtree.models.uplift_report import (
    ComparisonStatus,
    ExecutionStatus,
    PrimaryUpliftResult,
    PublicationStatus,
    UpliftDecision,
    UpliftReport,
    UpliftStatuses,
)
from techtree.paths import TechtreePaths, paths_from_root
from techtree.runs import store as store_module
from techtree.runs.events import append_event, event_digest, next_sequence, read_events
from techtree.runs.machine import (
    ALLOWED_TRANSITIONS,
    DETAIL_ERROR,
    DETAIL_PROGRESS,
    DETAIL_RESULT_DIGEST,
    DETAIL_WORKER_PID,
    apply_event,
    can_cancel,
    is_terminal,
    reduce_events,
    validate_transition,
)
from techtree.runs.store import RunStore

# ---------------------------------------------------------------------------
# The transition table, written out independently of the module that builds it
# ---------------------------------------------------------------------------

EXPECTED_TRANSITIONS: dict[RunPhase, set[RunPhase]] = {
    RunPhase.CREATED: {
        RunPhase.CREATED,
        RunPhase.VALIDATING_TASKSET,
        RunPhase.FAILED,
        RunPhase.CANCEL_REQUESTED,
    },
    RunPhase.VALIDATING_TASKSET: {
        RunPhase.VALIDATING_TASKSET,
        RunPhase.RUNNING_BASELINE,
        RunPhase.FAILED,
        RunPhase.CANCEL_REQUESTED,
    },
    RunPhase.RUNNING_BASELINE: {
        RunPhase.RUNNING_BASELINE,
        RunPhase.RUNNING_CANDIDATE,
        RunPhase.FAILED,
        RunPhase.CANCEL_REQUESTED,
    },
    RunPhase.RUNNING_CANDIDATE: {
        RunPhase.RUNNING_CANDIDATE,
        RunPhase.BUILDING_RECEIPTS,
        RunPhase.FAILED,
        RunPhase.CANCEL_REQUESTED,
    },
    RunPhase.BUILDING_RECEIPTS: {
        RunPhase.BUILDING_RECEIPTS,
        RunPhase.VERIFYING_COMPARISON,
        RunPhase.FAILED,
        RunPhase.CANCEL_REQUESTED,
    },
    RunPhase.VERIFYING_COMPARISON: {
        RunPhase.VERIFYING_COMPARISON,
        RunPhase.BUILDING_REPORT,
        RunPhase.FAILED,
        RunPhase.CANCEL_REQUESTED,
    },
    RunPhase.BUILDING_REPORT: {
        RunPhase.BUILDING_REPORT,
        RunPhase.COMPLETED,
        RunPhase.FAILED,
        RunPhase.CANCEL_REQUESTED,
    },
    RunPhase.CANCEL_REQUESTED: {
        RunPhase.CANCEL_REQUESTED,
        RunPhase.CANCELLED,
        RunPhase.FAILED,
    },
    RunPhase.COMPLETED: set(),
    RunPhase.FAILED: set(),
    RunPhase.CANCELLED: set(),
}

TERMINAL_PHASES = {RunPhase.COMPLETED, RunPhase.FAILED, RunPhase.CANCELLED}

RUN_ID = "run_00000000000000000000000000000001"
OTHER_RUN_ID = "run_00000000000000000000000000000002"
DRAFT_ID = "draft_0000000000000000000000000000000a"
FIXED_TIME = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def digest_of(label: str) -> Digest:
    """Return a stable, distinct digest for a test fixture."""
    return sha256_digest_bytes(label.encode("utf-8"))


# ---------------------------------------------------------------------------
# Fixtures and builders
# ---------------------------------------------------------------------------


def build_request(run_id: str = RUN_ID) -> RunRequest:
    """Return a complete run request with a matching policy acknowledgement."""
    data_policy_digest = digest_of("data-policy")
    return RunRequest(
        run_id=run_id,
        draft_id=DRAFT_ID,
        draft_digest=digest_of("draft"),
        campaign_spec_digest=digest_of("campaign"),
        program_ref=ProgramRef(id="procedure-transfer", version=1),
        public_context=PublicContext(kind="climb", climb_digest=digest_of("climb")),
        data_policy_digest=data_policy_digest,
        outcome_contract_digest=None,
        evaluation_backend=EvaluationBackendSpec(
            schema_version="techtree.evaluation-backend.v1alpha1",
            kind=EvaluationBackendKind.LOCAL_TECHTREE,
            attestation=AttestationKind.PARTICIPANT,
        ),
        taskset_lock_digest=digest_of("taskset-lock"),
        baseline_manifest_digest=digest_of("baseline"),
        candidate_manifest_digest=digest_of("candidate"),
        policy_acknowledgement=PolicyAcknowledgement(
            data_policy_digest=data_policy_digest,
            method="explicit_cli_digest",
            acknowledged_at=FIXED_TIME,
        ),
        executor_kind="fake",
        created_at=FIXED_TIME,
    )


def build_report(run_id: str = RUN_ID) -> UpliftReport:
    """Return a development-only report for the run under test."""
    return UpliftReport(
        schema_version="techtree.uplift-report.v1alpha1",
        id="uplift_0000000000000000000000000000000b",
        run_id=run_id,
        campaign_spec_digest=digest_of("campaign"),
        program_ref=None,
        public_context=None,
        data_policy_digest=digest_of("data-policy"),
        outcome_contract_digest=None,
        evaluation_backend=EvaluationBackendSpec(
            schema_version="techtree.evaluation-backend.v1alpha1",
            kind=EvaluationBackendKind.LOCAL_TECHTREE,
            attestation=AttestationKind.PARTICIPANT,
        ),
        taskset_validation_receipt_digest=digest_of("receipt"),
        baseline_manifest_digest=digest_of("baseline"),
        candidate_manifest_digest=digest_of("candidate"),
        statuses=UpliftStatuses(
            execution=ExecutionStatus.COMPLETED,
            score=ScoreStatus.DEVELOPMENT_ONLY,
            evidence=EvidenceStatus.DEVELOPMENT_ONLY,
            comparison=ComparisonStatus.DEVELOPMENT_ONLY,
            publication=PublicationStatus.BLOCKED,
        ),
        manifest_comparison=ManifestComparison(
            baseline_configuration_digest=digest_of("baseline-configuration"),
            candidate_configuration_digest=digest_of("candidate-configuration"),
            differences=[],
            allowed_differences=["/agents/subject/harness/skills"],
            controlled=True,
            violations=[],
        ),
        primary_result=PrimaryUpliftResult(
            reward_name="reward",
            baseline_mean=0.25,
            candidate_mean=0.85,
            absolute_delta=0.6,
            relative_delta=2.4,
            wins=12,
            losses=0,
            ties=8,
        ),
        task_deltas=[],
        decision=UpliftDecision.DEVELOPMENT_ONLY,
        proof_grade="development_only",
        publication_eligible=False,
        created_at=FIXED_TIME,
    )


def build_event(
    *,
    sequence: int,
    phase: RunPhase,
    previous_phase: RunPhase | None,
    kind: str = "test",
    details: dict[str, JsonValue] | None = None,
    run_id: str = RUN_ID,
    offset_seconds: int = 0,
) -> RunEvent:
    """Return one run event with a deterministic timestamp."""
    return RunEvent(
        sequence=sequence,
        timestamp=FIXED_TIME + timedelta(seconds=offset_seconds),
        run_id=run_id,
        previous_phase=previous_phase,
        phase=phase,
        kind=kind,
        details=dict(details or {}),
    )


def created_event(run_id: str = RUN_ID) -> RunEvent:
    """Return the event every run opens with."""
    return build_event(
        sequence=0,
        phase=RunPhase.CREATED,
        previous_phase=None,
        kind="created",
        run_id=run_id,
    )


@pytest.fixture
def paths(temp_techtree_home: Path) -> TechtreePaths:
    """Return a path layout rooted in an isolated home."""
    return paths_from_root(temp_techtree_home)


@pytest.fixture
def store(paths: TechtreePaths) -> RunStore:
    """Return a run store over an isolated home."""
    return RunStore(paths)


@pytest.fixture
def created_run(store: RunStore) -> RunStore:
    """Return a store holding one freshly created run."""
    store.create(build_request())
    return store


def write_log(path: Path, events: list[RunEvent]) -> None:
    """Write a log directly, bypassing the store's validation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(canonical_json_bytes(event) + b"\n" for event in events))


def advance(store: RunStore, run_id: str, phases: list[RunPhase]) -> list[RunState]:
    """Move a run through phases and return the state after each step."""
    return [store.append(run_id, phase=phase, kind=phase.value) for phase in phases]


# ---------------------------------------------------------------------------
# Transition table
# ---------------------------------------------------------------------------


def test_transition_table_matches_the_specified_edges() -> None:
    assert {phase: set(targets) for phase, targets in ALLOWED_TRANSITIONS.items()} == (
        EXPECTED_TRANSITIONS
    )


def test_every_phase_appears_in_the_transition_table() -> None:
    assert set(ALLOWED_TRANSITIONS) == set(RunPhase)


@pytest.mark.parametrize(
    ("current", "target"),
    list(itertools.product(RunPhase, RunPhase)),
    ids=lambda phase: phase.value,
)
def test_validate_transition_allows_exactly_the_specified_edges(
    current: RunPhase,
    target: RunPhase,
) -> None:
    if target in EXPECTED_TRANSITIONS[current]:
        validate_transition(current, target)
        return

    with pytest.raises(RunError) as raised:
        validate_transition(current, target)
    assert raised.value.details["phase"] == current.value
    assert raised.value.details["target_phase"] == target.value


@pytest.mark.parametrize("phase", list(RunPhase), ids=lambda phase: phase.value)
def test_is_terminal_names_the_three_ended_phases(phase: RunPhase) -> None:
    assert is_terminal(phase) is (phase in TERMINAL_PHASES)


@pytest.mark.parametrize("phase", list(RunPhase), ids=lambda phase: phase.value)
def test_can_cancel_covers_working_phases_only(phase: RunPhase) -> None:
    working = phase not in TERMINAL_PHASES and phase is not RunPhase.CANCEL_REQUESTED
    assert can_cancel(phase) is working


def test_the_normal_path_runs_from_created_to_completed() -> None:
    path = [
        RunPhase.CREATED,
        RunPhase.VALIDATING_TASKSET,
        RunPhase.RUNNING_BASELINE,
        RunPhase.RUNNING_CANDIDATE,
        RunPhase.BUILDING_RECEIPTS,
        RunPhase.VERIFYING_COMPARISON,
        RunPhase.BUILDING_REPORT,
        RunPhase.COMPLETED,
    ]
    for current, target in itertools.pairwise(path):
        validate_transition(current, target)


# ---------------------------------------------------------------------------
# Event log
# ---------------------------------------------------------------------------


def test_appended_events_read_back_in_order(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    first = created_event()
    second = build_event(
        sequence=1,
        phase=RunPhase.VALIDATING_TASKSET,
        previous_phase=RunPhase.CREATED,
    )

    append_event(path, first)
    append_event(path, second)

    assert read_events(path) == [first, second]


def test_each_event_occupies_exactly_one_line(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    append_event(path, created_event())
    append_event(
        path,
        build_event(
            sequence=1,
            phase=RunPhase.VALIDATING_TASKSET,
            previous_phase=RunPhase.CREATED,
            details={"note": "line\nbreak"},
        ),
    )

    assert len(path.read_bytes().splitlines()) == 2


def test_reading_a_missing_log_is_not_found(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError):
        read_events(tmp_path / "events.jsonl")


def test_a_log_that_skips_a_sequence_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    write_log(
        path,
        [
            created_event(),
            build_event(
                sequence=2,
                phase=RunPhase.VALIDATING_TASKSET,
                previous_phase=RunPhase.CREATED,
            ),
        ],
    )

    with pytest.raises(ValidationError) as raised:
        read_events(path)
    assert raised.value.details["expected_sequence"] == 1
    assert raised.value.details["sequence"] == 2


def test_a_log_that_repeats_a_sequence_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    write_log(
        path,
        [
            created_event(),
            build_event(
                sequence=1,
                phase=RunPhase.VALIDATING_TASKSET,
                previous_phase=RunPhase.CREATED,
            ),
            build_event(
                sequence=1,
                phase=RunPhase.RUNNING_BASELINE,
                previous_phase=RunPhase.VALIDATING_TASKSET,
            ),
        ],
    )

    with pytest.raises(ValidationError):
        read_events(path)


def test_a_log_that_does_not_start_at_zero_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    write_log(
        path,
        [build_event(sequence=1, phase=RunPhase.CREATED, previous_phase=None)],
    )

    with pytest.raises(ValidationError):
        read_events(path)


def test_a_truncated_final_line_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    append_event(path, created_event())
    raw = path.read_bytes()
    path.write_bytes(raw + raw[: len(raw) // 2])

    with pytest.raises(ValidationError) as raised:
        read_events(path)
    assert raised.value.details["line"] == 2


def test_a_blank_line_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    append_event(path, created_event())
    path.write_bytes(path.read_bytes() + b"\n")

    with pytest.raises(ValidationError):
        read_events(path)


def test_an_empty_log_reads_as_no_events(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_bytes(b"")

    assert read_events(path) == []


def test_next_sequence_follows_the_last_event(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    assert next_sequence([]) == 0

    append_event(path, created_event())
    assert next_sequence(read_events(path)) == 1


def test_the_same_history_always_digests_to_the_same_bytes(tmp_path: Path) -> None:
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    for path, details in (
        (first, {"a": 1, "b": 2}),
        # The same details, written in the other order. Canonical JSON fixes
        # key order, so the bytes on disk must not notice.
        (second, {"b": 2, "a": 1}),
    ):
        append_event(path, created_event())
        append_event(
            path,
            build_event(
                sequence=1,
                phase=RunPhase.VALIDATING_TASKSET,
                previous_phase=RunPhase.CREATED,
                details=dict(details),
            ),
        )

    assert event_digest(first) == event_digest(second)


def test_the_log_digest_changes_when_an_event_is_appended(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    append_event(path, created_event())
    before = event_digest(path)

    append_event(
        path,
        build_event(
            sequence=1,
            phase=RunPhase.VALIDATING_TASKSET,
            previous_phase=RunPhase.CREATED,
        ),
    )

    assert event_digest(path) != before


def test_digesting_a_missing_log_is_not_found(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError):
        event_digest(tmp_path / "events.jsonl")


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------


def test_the_created_event_projects_an_empty_run() -> None:
    state = reduce_events([created_event()])

    assert state.run_id == RUN_ID
    assert state.phase is RunPhase.CREATED
    assert state.sequence == 0
    assert state.updated_at == FIXED_TIME
    assert state.worker_pid is None
    assert state.worker_started_at is None
    assert state.heartbeat_at is None
    assert state.cancel_requested_at is None
    assert state.error is None
    assert state.progress is None
    assert state.result_digest is None


def test_an_empty_log_cannot_be_projected() -> None:
    with pytest.raises(ValidationError):
        reduce_events([])


def test_a_log_must_open_in_created() -> None:
    with pytest.raises(ValidationError):
        reduce_events(
            [
                build_event(
                    sequence=0, phase=RunPhase.RUNNING_BASELINE, previous_phase=None
                )
            ]
        )


def test_a_first_event_cannot_claim_an_earlier_phase() -> None:
    with pytest.raises(ValidationError):
        reduce_events(
            [
                build_event(
                    sequence=0,
                    phase=RunPhase.CREATED,
                    previous_phase=RunPhase.CREATED,
                )
            ]
        )


def test_apply_event_rejects_an_out_of_order_sequence() -> None:
    state = reduce_events([created_event()])

    with pytest.raises(ValidationError) as raised:
        apply_event(
            state,
            build_event(
                sequence=5,
                phase=RunPhase.VALIDATING_TASKSET,
                previous_phase=RunPhase.CREATED,
            ),
        )
    assert raised.value.details["expected_sequence"] == 1


def test_apply_event_rejects_a_disagreeing_previous_phase() -> None:
    state = reduce_events([created_event()])

    with pytest.raises(ValidationError):
        apply_event(
            state,
            build_event(
                sequence=1,
                phase=RunPhase.RUNNING_BASELINE,
                previous_phase=RunPhase.VALIDATING_TASKSET,
            ),
        )


def test_apply_event_rejects_an_event_from_another_run() -> None:
    state = reduce_events([created_event()])

    with pytest.raises(ValidationError):
        apply_event(
            state,
            build_event(
                sequence=1,
                phase=RunPhase.VALIDATING_TASKSET,
                previous_phase=RunPhase.CREATED,
                run_id=OTHER_RUN_ID,
            ),
        )


def test_apply_event_rejects_a_forbidden_transition() -> None:
    state = reduce_events([created_event()])

    with pytest.raises(RunError):
        apply_event(
            state,
            build_event(
                sequence=1,
                phase=RunPhase.COMPLETED,
                previous_phase=RunPhase.CREATED,
            ),
        )


def test_progress_survives_within_a_phase_and_resets_when_it_changes() -> None:
    events = [
        created_event(),
        build_event(
            sequence=1,
            phase=RunPhase.VALIDATING_TASKSET,
            previous_phase=RunPhase.CREATED,
        ),
        build_event(
            sequence=2,
            phase=RunPhase.VALIDATING_TASKSET,
            previous_phase=RunPhase.VALIDATING_TASKSET,
            details={
                DETAIL_PROGRESS: {"current": 3, "total": 20, "label": "tasks"},
            },
        ),
        build_event(
            sequence=3,
            phase=RunPhase.VALIDATING_TASKSET,
            previous_phase=RunPhase.VALIDATING_TASKSET,
        ),
    ]

    carried = reduce_events(events)
    assert carried.progress == RunProgress(current=3, total=20, label="tasks")

    events.append(
        build_event(
            sequence=4,
            phase=RunPhase.RUNNING_BASELINE,
            previous_phase=RunPhase.VALIDATING_TASKSET,
        )
    )
    assert reduce_events(events).progress is None


def test_malformed_progress_is_rejected() -> None:
    with pytest.raises(ValidationError):
        reduce_events(
            [
                created_event(),
                build_event(
                    sequence=1,
                    phase=RunPhase.VALIDATING_TASKSET,
                    previous_phase=RunPhase.CREATED,
                    details={DETAIL_PROGRESS: {"current": 30, "total": 20}},
                ),
            ]
        )


def test_a_failed_run_records_why() -> None:
    error = CliError(
        code="engine_error",
        message="the managed engine exited 1",
        retryable=False,
        details={},
    )
    state = reduce_events(
        [
            created_event(),
            build_event(
                sequence=1,
                phase=RunPhase.FAILED,
                previous_phase=RunPhase.CREATED,
                details={DETAIL_ERROR: error.model_dump()},
            ),
        ]
    )

    assert state.phase is RunPhase.FAILED
    assert state.error == error


def test_a_failure_without_an_error_is_rejected() -> None:
    with pytest.raises(ValidationError):
        reduce_events(
            [
                created_event(),
                build_event(
                    sequence=1,
                    phase=RunPhase.FAILED,
                    previous_phase=RunPhase.CREATED,
                ),
            ]
        )


def test_cancellation_records_the_first_request_only() -> None:
    events = [
        created_event(),
        build_event(
            sequence=1,
            phase=RunPhase.CANCEL_REQUESTED,
            previous_phase=RunPhase.CREATED,
            offset_seconds=10,
        ),
        build_event(
            sequence=2,
            phase=RunPhase.CANCEL_REQUESTED,
            previous_phase=RunPhase.CANCEL_REQUESTED,
            offset_seconds=20,
        ),
        build_event(
            sequence=3,
            phase=RunPhase.CANCELLED,
            previous_phase=RunPhase.CANCEL_REQUESTED,
            offset_seconds=30,
        ),
    ]

    state = reduce_events(events)

    assert state.phase is RunPhase.CANCELLED
    assert state.cancel_requested_at == FIXED_TIME + timedelta(seconds=10)
    assert state.updated_at == FIXED_TIME + timedelta(seconds=30)


def test_the_worker_pid_and_its_start_time_come_from_the_log() -> None:
    state = reduce_events(
        [
            created_event(),
            build_event(
                sequence=1,
                phase=RunPhase.CREATED,
                previous_phase=RunPhase.CREATED,
                details={DETAIL_WORKER_PID: 4321},
                offset_seconds=5,
            ),
        ]
    )

    assert state.worker_pid == 4321
    assert state.worker_started_at == FIXED_TIME + timedelta(seconds=5)


@pytest.mark.parametrize("pid", [0, -1, "4321", True])
def test_an_impossible_worker_pid_is_rejected(pid: Any) -> None:
    with pytest.raises(ValidationError):
        reduce_events(
            [
                created_event(),
                build_event(
                    sequence=1,
                    phase=RunPhase.CREATED,
                    previous_phase=RunPhase.CREATED,
                    details={DETAIL_WORKER_PID: pid},
                ),
            ]
        )


def test_a_malformed_result_digest_is_rejected() -> None:
    with pytest.raises(ValidationError):
        reduce_events(
            [
                created_event(),
                build_event(
                    sequence=1,
                    phase=RunPhase.CREATED,
                    previous_phase=RunPhase.CREATED,
                    details={DETAIL_RESULT_DIGEST: "not-a-digest"},
                ),
            ]
        )


def test_the_reducer_agrees_with_applying_events_one_at_a_time() -> None:
    events = [
        created_event(),
        build_event(
            sequence=1,
            phase=RunPhase.CREATED,
            previous_phase=RunPhase.CREATED,
            details={DETAIL_WORKER_PID: 99},
        ),
        build_event(
            sequence=2,
            phase=RunPhase.VALIDATING_TASKSET,
            previous_phase=RunPhase.CREATED,
        ),
        build_event(
            sequence=3,
            phase=RunPhase.VALIDATING_TASKSET,
            previous_phase=RunPhase.VALIDATING_TASKSET,
            details={DETAIL_PROGRESS: {"current": 20, "total": 20, "label": "tasks"}},
        ),
        build_event(
            sequence=4,
            phase=RunPhase.RUNNING_BASELINE,
            previous_phase=RunPhase.VALIDATING_TASKSET,
        ),
    ]

    incremental = reduce_events(events[:1])
    for event in events[1:]:
        incremental = apply_event(incremental, event)

    assert incremental == reduce_events(events)


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


def test_create_writes_the_request_as_its_own_digest(
    store: RunStore,
    paths: TechtreePaths,
) -> None:
    request = build_request()

    store.create(request)

    raw = (paths.run_dir(RUN_ID) / "request.json").read_bytes()
    assert sha256_digest_bytes(raw) == digest_object(request)
    assert store.get_request(RUN_ID) == request


def test_create_opens_the_log_and_the_projection(
    created_run: RunStore,
    paths: TechtreePaths,
) -> None:
    run_dir = paths.run_dir(RUN_ID)

    events = read_events(run_dir / "events.jsonl")
    assert len(events) == 1
    assert events[0].kind == "created"
    assert events[0].details["request_digest"] == digest_object(build_request())
    assert json.loads((run_dir / "state.json").read_text())["phase"] == "created"
    assert created_run.state(RUN_ID).phase is RunPhase.CREATED


def test_a_run_directory_is_private(
    created_run: RunStore, paths: TechtreePaths
) -> None:
    mode = paths.run_dir(RUN_ID).stat().st_mode & 0o777

    assert mode == 0o700


def test_creating_the_same_run_twice_is_a_conflict(created_run: RunStore) -> None:
    with pytest.raises(ConflictError):
        created_run.create(build_request())


def test_an_unknown_run_is_not_found(store: RunStore) -> None:
    for call in (
        lambda: store.get_request(RUN_ID),
        lambda: store.state(RUN_ID),
        lambda: store.rebuild_state(RUN_ID),
        lambda: store.read_pid(RUN_ID),
        lambda: store.get_result(RUN_ID),
        lambda: store.append(RUN_ID, phase=RunPhase.VALIDATING_TASKSET, kind="x"),
        lambda: store.write_pid(RUN_ID, 1),
        lambda: store.write_heartbeat(RUN_ID, RunPhase.CREATED),
        lambda: store.write_result(RUN_ID, build_report()),
    ):
        with pytest.raises(NotFoundError):
            call()


def test_an_identifier_that_is_not_a_run_identifier_is_refused(
    store: RunStore,
) -> None:
    for identifier in ("draft_0000000000000000000000000000000a", "../escape", "run_1"):
        with pytest.raises(ValidationError):
            store.state(identifier)


def test_append_advances_the_run_and_records_where_it_came_from(
    created_run: RunStore,
    paths: TechtreePaths,
) -> None:
    state = created_run.append(
        RUN_ID,
        phase=RunPhase.VALIDATING_TASKSET,
        kind="validating_taskset",
    )

    assert state.phase is RunPhase.VALIDATING_TASKSET
    assert state.sequence == 1
    events = read_events(paths.run_dir(RUN_ID) / "events.jsonl")
    assert events[-1].previous_phase is RunPhase.CREATED


def test_append_refuses_a_transition_the_machine_forbids(created_run: RunStore) -> None:
    with pytest.raises(RunError):
        created_run.append(RUN_ID, phase=RunPhase.COMPLETED, kind="completed")


def test_append_refuses_an_unnamed_event_kind(created_run: RunStore) -> None:
    with pytest.raises(ValidationError):
        created_run.append(RUN_ID, phase=RunPhase.VALIDATING_TASKSET, kind="")


def test_nothing_is_appended_after_a_run_ends(created_run: RunStore) -> None:
    created_run.append(
        RUN_ID,
        phase=RunPhase.FAILED,
        kind="failed",
        details={
            DETAIL_ERROR: {
                "code": "run_error",
                "message": "the fake executor stopped",
                "retryable": False,
                "details": {},
            }
        },
    )

    with pytest.raises(RunError):
        created_run.append(RUN_ID, phase=RunPhase.CANCEL_REQUESTED, kind="cancel")

    state = created_run.state(RUN_ID)
    assert state.error is not None
    assert state.error.message == "the fake executor stopped"
    assert state == created_run.rebuild_state(RUN_ID)


def test_state_rebuilds_when_the_projection_is_missing(
    created_run: RunStore,
    paths: TechtreePaths,
) -> None:
    advance(created_run, RUN_ID, [RunPhase.VALIDATING_TASKSET])
    projection = paths.run_dir(RUN_ID) / "state.json"
    expected = created_run.state(RUN_ID)
    projection.unlink()

    assert created_run.state(RUN_ID) == expected
    assert projection.exists()


def test_state_rebuilds_when_the_projection_is_damaged(
    created_run: RunStore,
    paths: TechtreePaths,
) -> None:
    advance(created_run, RUN_ID, [RunPhase.VALIDATING_TASKSET])
    projection = paths.run_dir(RUN_ID) / "state.json"
    expected = created_run.state(RUN_ID)
    projection.write_text("{ not json")

    assert created_run.state(RUN_ID) == expected


def test_state_rebuilds_identically_from_the_events_alone(
    created_run: RunStore,
    paths: TechtreePaths,
) -> None:
    created_run.write_pid(RUN_ID, 424242)
    incremental = advance(
        created_run,
        RUN_ID,
        [
            RunPhase.VALIDATING_TASKSET,
            RunPhase.RUNNING_BASELINE,
            RunPhase.RUNNING_CANDIDATE,
            RunPhase.BUILDING_RECEIPTS,
            RunPhase.VERIFYING_COMPARISON,
            RunPhase.BUILDING_REPORT,
        ],
    )
    created_run.write_result(RUN_ID, build_report())
    incremental.append(
        created_run.append(RUN_ID, phase=RunPhase.COMPLETED, kind="done")
    )

    created_run.write_heartbeat(RUN_ID, RunPhase.COMPLETED)
    rebuilt = created_run.rebuild_state(RUN_ID)

    assert rebuilt.model_copy(update={"heartbeat_at": None}) == incremental[-1]
    assert reduce_events(read_events(paths.run_dir(RUN_ID) / "events.jsonl")) == (
        rebuilt.model_copy(update={"heartbeat_at": None})
    )
    # The stored projection is read back through the same model, so every
    # field survives the round trip through JSON, not only the ones in memory.
    assert created_run.state(RUN_ID) == rebuilt
    assert rebuilt.phase is RunPhase.COMPLETED
    assert rebuilt.worker_pid == 424242
    assert rebuilt.heartbeat_at is not None
    assert rebuilt.result_digest == digest_object(build_report())


def test_each_appended_state_matches_the_reduction_of_its_prefix(
    created_run: RunStore,
    paths: TechtreePaths,
) -> None:
    states = advance(
        created_run,
        RUN_ID,
        [
            RunPhase.VALIDATING_TASKSET,
            RunPhase.RUNNING_BASELINE,
            RunPhase.CANCEL_REQUESTED,
            RunPhase.CANCELLED,
        ],
    )
    events = read_events(paths.run_dir(RUN_ID) / "events.jsonl")

    for position, state in enumerate(states, start=2):
        assert state == reduce_events(events[:position])


def test_the_worker_pid_is_readable_and_recorded(created_run: RunStore) -> None:
    created_run.write_pid(RUN_ID, 1234)

    assert created_run.read_pid(RUN_ID) == 1234
    assert created_run.state(RUN_ID).worker_pid == 1234
    assert created_run.state(RUN_ID).phase is RunPhase.CREATED


def test_an_absent_pid_file_reads_as_no_worker(created_run: RunStore) -> None:
    assert created_run.read_pid(RUN_ID) is None


def test_an_impossible_pid_is_refused(created_run: RunStore) -> None:
    with pytest.raises(ValidationError):
        created_run.write_pid(RUN_ID, 0)


def test_a_damaged_pid_file_is_reported(
    created_run: RunStore,
    paths: TechtreePaths,
) -> None:
    (paths.run_dir(RUN_ID) / "pid").write_text("not a pid\n")

    with pytest.raises(ValidationError):
        created_run.read_pid(RUN_ID)


def test_the_heartbeat_reaches_the_projection_without_touching_the_log(
    created_run: RunStore,
    paths: TechtreePaths,
) -> None:
    before = event_digest(paths.run_dir(RUN_ID) / "events.jsonl")

    created_run.write_heartbeat(RUN_ID, RunPhase.CREATED)

    state = created_run.state(RUN_ID)
    assert state.heartbeat_at is not None
    assert event_digest(paths.run_dir(RUN_ID) / "events.jsonl") == before
    assert created_run.rebuild_state(RUN_ID).heartbeat_at == state.heartbeat_at


def test_a_later_heartbeat_replaces_an_earlier_one(created_run: RunStore) -> None:
    created_run.write_heartbeat(RUN_ID, RunPhase.CREATED)
    first = created_run.state(RUN_ID).heartbeat_at

    created_run.write_heartbeat(RUN_ID, RunPhase.CREATED)

    second = created_run.state(RUN_ID).heartbeat_at
    assert first is not None
    assert second is not None
    assert second >= first


def test_a_damaged_heartbeat_is_reported(
    created_run: RunStore,
    paths: TechtreePaths,
) -> None:
    (paths.run_dir(RUN_ID) / "heartbeat.json").write_text('{"phase": "created"}')

    with pytest.raises(ValidationError):
        created_run.rebuild_state(RUN_ID)


def test_the_result_is_written_once_and_read_back(
    created_run: RunStore,
    paths: TechtreePaths,
) -> None:
    report = build_report()
    advance(created_run, RUN_ID, [RunPhase.VALIDATING_TASKSET])

    created_run.write_result(RUN_ID, report)

    assert created_run.result_path(RUN_ID) == (
        paths.run_dir(RUN_ID) / "report" / "uplift.json"
    )
    assert created_run.get_result(RUN_ID) == report
    assert created_run.state(RUN_ID).result_digest == digest_object(report)
    assert sha256_digest_bytes(
        created_run.result_path(RUN_ID).read_bytes()
    ) == digest_object(report)

    with pytest.raises(ConflictError):
        created_run.write_result(RUN_ID, report)


def test_a_result_from_another_run_is_refused(created_run: RunStore) -> None:
    with pytest.raises(ValidationError):
        created_run.write_result(RUN_ID, build_report(run_id=OTHER_RUN_ID))


def test_an_ended_run_records_neither_a_result_nor_a_worker(
    created_run: RunStore,
) -> None:
    advance(created_run, RUN_ID, [RunPhase.CANCEL_REQUESTED, RunPhase.CANCELLED])

    with pytest.raises(RunError):
        created_run.write_result(RUN_ID, build_report())
    with pytest.raises(RunError):
        created_run.write_pid(RUN_ID, 99)

    # The refusal happens before anything is written, so nothing is left behind.
    assert not created_run.result_path(RUN_ID).exists()
    assert created_run.read_pid(RUN_ID) is None


def test_a_result_that_was_never_written_is_not_found(created_run: RunStore) -> None:
    with pytest.raises(NotFoundError):
        created_run.get_result(RUN_ID)


def test_the_worker_log_sits_beside_the_run(
    created_run: RunStore,
    paths: TechtreePaths,
) -> None:
    assert created_run.worker_log_path(RUN_ID) == (paths.run_dir(RUN_ID) / "worker.log")


def test_every_mutation_waits_for_the_per_run_lock(
    created_run: RunStore,
    paths: TechtreePaths,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(store_module, "LOCK_TIMEOUT_SECONDS", 0.05)
    held = FileLock(paths.run_dir(RUN_ID) / ".lock", timeout=1)
    held.acquire()
    try:
        for call in (
            lambda: created_run.append(
                RUN_ID, phase=RunPhase.VALIDATING_TASKSET, kind="x"
            ),
            lambda: created_run.rebuild_state(RUN_ID),
            lambda: created_run.write_pid(RUN_ID, 7),
            lambda: created_run.write_heartbeat(RUN_ID, RunPhase.CREATED),
            lambda: created_run.write_result(RUN_ID, build_report()),
        ):
            with pytest.raises(ConflictError):
                call()
    finally:
        held.release()


def test_creating_a_run_waits_for_its_lock(
    store: RunStore,
    paths: TechtreePaths,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(store_module, "LOCK_TIMEOUT_SECONDS", 0.05)
    run_dir = paths.run_dir(RUN_ID)
    run_dir.mkdir(parents=True)
    held = FileLock(run_dir / ".lock", timeout=1)
    held.acquire()
    try:
        with pytest.raises(ConflictError):
            store.create(build_request())
    finally:
        held.release()


def test_a_second_run_has_its_own_lock(created_run: RunStore) -> None:
    created_run.create(build_request(run_id=OTHER_RUN_ID))

    assert created_run.state(OTHER_RUN_ID).run_id == OTHER_RUN_ID
    assert created_run.state(RUN_ID).run_id == RUN_ID


def test_a_cancelled_run_keeps_the_phase_it_was_asked_to_leave(
    created_run: RunStore,
    paths: TechtreePaths,
) -> None:
    advance(
        created_run, RUN_ID, [RunPhase.VALIDATING_TASKSET, RunPhase.RUNNING_BASELINE]
    )

    created_run.append(RUN_ID, phase=RunPhase.CANCEL_REQUESTED, kind="cancel_requested")
    state = created_run.append(RUN_ID, phase=RunPhase.CANCELLED, kind="cancelled")

    events = read_events(paths.run_dir(RUN_ID) / "events.jsonl")
    assert events[-2].previous_phase is RunPhase.RUNNING_BASELINE
    assert state.cancel_requested_at is not None
    assert is_terminal(state.phase)
