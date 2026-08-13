"""The run event log, state machine, and store. Spec sections 18.1 to 18.3, 7.

Four properties carry the whole subsystem and each is tested directly.

*The transition table is the contract.* A run's phases are part of the CLI's
machine-facing output, so the table is written out again here by hand and
compared with the one the module derives. Every ordered pair of phases is then
pushed through :func:`validate_transition`, so a new edge cannot appear without
a test noticing.

*The event vocabulary is closed.* Nine kinds exhaust what a run can say about
itself. Each fixes the phases it may sit between and the details it carries, and
each of those rules is checked from both sides: the placement that is correct is
accepted, and the placements that are not are refused.

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
from techtree.runs.events import (
    CANCEL_REQUESTED,
    DETAIL_CURRENT,
    DETAIL_ERROR,
    DETAIL_LABEL,
    DETAIL_REQUEST_DIGEST,
    DETAIL_REQUESTED_BY,
    DETAIL_RESULT_DIGEST,
    DETAIL_TOTAL,
    DETAIL_WORKER_PID,
    EVENT_KINDS,
    PHASE_ENTERED,
    PROGRESS_UPDATED,
    RESULT_WRITTEN,
    RUN_CANCELLED,
    RUN_COMPLETED,
    RUN_CREATED,
    RUN_FAILED,
    SAME_PHASE_EVENT_KINDS,
    WORKER_STARTED,
    append_event,
    event_digest,
    next_sequence,
    read_events,
    validate_event_kind,
)
from techtree.runs.machine import (
    ALLOWED_TRANSITIONS,
    apply_event,
    can_cancel,
    initial_state,
    is_terminal,
    phase_progress_allowed,
    reduce_events,
    validate_same_phase_event,
    validate_transition,
)
from techtree.runs.store import RunStore

# ---------------------------------------------------------------------------
# The transition table, written out independently of the module that builds it
# ---------------------------------------------------------------------------

EXPECTED_TRANSITIONS: dict[RunPhase, set[RunPhase]] = {
    RunPhase.CREATED: {
        RunPhase.VALIDATING_TASKSET,
        RunPhase.FAILED,
        RunPhase.CANCEL_REQUESTED,
    },
    RunPhase.VALIDATING_TASKSET: {
        RunPhase.RUNNING_BASELINE,
        RunPhase.FAILED,
        RunPhase.CANCEL_REQUESTED,
    },
    RunPhase.RUNNING_BASELINE: {
        RunPhase.RUNNING_CANDIDATE,
        RunPhase.FAILED,
        RunPhase.CANCEL_REQUESTED,
    },
    RunPhase.RUNNING_CANDIDATE: {
        RunPhase.BUILDING_RECEIPTS,
        RunPhase.FAILED,
        RunPhase.CANCEL_REQUESTED,
    },
    RunPhase.BUILDING_RECEIPTS: {
        RunPhase.VERIFYING_COMPARISON,
        RunPhase.FAILED,
        RunPhase.CANCEL_REQUESTED,
    },
    RunPhase.VERIFYING_COMPARISON: {
        RunPhase.BUILDING_REPORT,
        RunPhase.FAILED,
        RunPhase.CANCEL_REQUESTED,
    },
    RunPhase.BUILDING_REPORT: {
        RunPhase.COMPLETED,
        RunPhase.FAILED,
        RunPhase.CANCEL_REQUESTED,
    },
    RunPhase.CANCEL_REQUESTED: {
        RunPhase.CANCELLED,
        RunPhase.FAILED,
    },
    RunPhase.COMPLETED: set(),
    RunPhase.FAILED: set(),
    RunPhase.CANCELLED: set(),
}

TERMINAL_PHASES = {RunPhase.COMPLETED, RunPhase.FAILED, RunPhase.CANCELLED}

#: The nine canonical kinds, spelled out rather than imported, for the same
#: reason the transition table is: they are a published contract.
SPECIFIED_EVENT_KINDS = {
    "run.created",
    "worker.started",
    "phase.entered",
    "progress.updated",
    "cancel.requested",
    "run.failed",
    "run.cancelled",
    "result.written",
    "run.completed",
}

#: The phases a run passes through on the way to a finished report.
WORKING_PATH = (
    RunPhase.VALIDATING_TASKSET,
    RunPhase.RUNNING_BASELINE,
    RunPhase.RUNNING_CANDIDATE,
    RunPhase.BUILDING_RECEIPTS,
    RunPhase.VERIFYING_COMPARISON,
    RunPhase.BUILDING_REPORT,
)

RUN_ID = "run_00000000000000000000000000000001"
OTHER_RUN_ID = "run_00000000000000000000000000000002"
DRAFT_ID = "draft_0000000000000000000000000000000a"
FIXED_TIME = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def digest_of(label: str) -> Digest:
    """Return a stable, distinct digest for a test fixture."""
    return sha256_digest_bytes(label.encode("utf-8"))


FAILURE = CliError(
    code="run_error",
    message="the fake executor stopped",
    retryable=False,
    details={},
)


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
    kind: str = PHASE_ENTERED,
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
        kind=RUN_CREATED,
        details={DETAIL_REQUEST_DIGEST: digest_of("request")},
        run_id=run_id,
    )


def progress_details(current: int, total: int, label: str) -> dict[str, JsonValue]:
    """Return the details a ``progress.updated`` event carries."""
    return {DETAIL_CURRENT: current, DETAIL_TOTAL: total, DETAIL_LABEL: label}


def log_through(*phases: RunPhase, run_id: str = RUN_ID) -> list[RunEvent]:
    """Return a valid log that walks a run from created through ``phases``."""
    events = [created_event(run_id)]
    for phase in phases:
        events.append(
            build_event(
                sequence=len(events),
                phase=phase,
                previous_phase=events[-1].phase,
                run_id=run_id,
                offset_seconds=len(events),
            )
        )
    return events


def follow(events: list[RunEvent], **overrides: Any) -> RunEvent:
    """Return an event that continues an existing log."""
    overrides.setdefault("previous_phase", events[-1].phase)
    return build_event(
        sequence=len(events),
        offset_seconds=len(events),
        **overrides,
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
    """Move a run through working phases and return the state after each step."""
    return [store.append(run_id, phase=phase) for phase in phases]


def reach_building_report(store: RunStore, run_id: str = RUN_ID) -> RunState:
    """Advance a created run to the phase in which a report is written."""
    return advance(store, run_id, list(WORKING_PATH))[-1]


# ---------------------------------------------------------------------------
# Transition table
# ---------------------------------------------------------------------------


def test_transition_table_matches_the_specified_edges() -> None:
    assert {phase: set(targets) for phase, targets in ALLOWED_TRANSITIONS.items()} == (
        EXPECTED_TRANSITIONS
    )


def test_every_phase_appears_in_the_transition_table() -> None:
    assert set(ALLOWED_TRANSITIONS) == set(RunPhase)


def test_no_phase_has_an_edge_to_itself() -> None:
    # A run that reports without moving is not making a transition. Those
    # events go through validate_same_phase_event instead.
    assert all(phase not in targets for phase, targets in ALLOWED_TRANSITIONS.items())


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
    assert raised.value.code == "run_transition_invalid"
    assert raised.value.details["phase"] == current.value
    assert raised.value.details["target_phase"] == target.value


@pytest.mark.parametrize("phase", list(RunPhase), ids=lambda phase: phase.value)
def test_is_terminal_names_the_three_ended_phases(phase: RunPhase) -> None:
    assert is_terminal(phase) is (phase in TERMINAL_PHASES)


@pytest.mark.parametrize("phase", list(RunPhase), ids=lambda phase: phase.value)
def test_can_cancel_covers_working_phases_only(phase: RunPhase) -> None:
    working = phase not in TERMINAL_PHASES and phase is not RunPhase.CANCEL_REQUESTED
    assert can_cancel(phase) is working


@pytest.mark.parametrize("phase", list(RunPhase), ids=lambda phase: phase.value)
def test_only_a_phase_doing_work_has_progress(phase: RunPhase) -> None:
    doing_work = phase not in TERMINAL_PHASES and phase is not RunPhase.CREATED
    assert phase_progress_allowed(phase) is doing_work


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
# Event kinds
# ---------------------------------------------------------------------------


def test_the_event_vocabulary_is_the_nine_specified_kinds() -> None:
    assert set(EVENT_KINDS) == SPECIFIED_EVENT_KINDS


def test_the_three_same_phase_kinds_are_the_specified_ones() -> None:
    assert set(SAME_PHASE_EVENT_KINDS) == {
        "worker.started",
        "progress.updated",
        "result.written",
    }


#: One correctly placed event per kind: the placement each kind is defined by.
CANONICAL_PLACEMENTS: list[tuple[str, RunPhase | None, RunPhase, dict[str, Any]]] = [
    (
        RUN_CREATED,
        None,
        RunPhase.CREATED,
        {DETAIL_REQUEST_DIGEST: digest_of("request")},
    ),
    (WORKER_STARTED, RunPhase.CREATED, RunPhase.CREATED, {DETAIL_WORKER_PID: 4321}),
    (PHASE_ENTERED, RunPhase.CREATED, RunPhase.VALIDATING_TASKSET, {}),
    (
        PROGRESS_UPDATED,
        RunPhase.RUNNING_BASELINE,
        RunPhase.RUNNING_BASELINE,
        progress_details(1, 20, "tasks"),
    ),
    (
        CANCEL_REQUESTED,
        RunPhase.RUNNING_BASELINE,
        RunPhase.CANCEL_REQUESTED,
        {DETAIL_REQUESTED_BY: "cli"},
    ),
    (
        RUN_FAILED,
        RunPhase.RUNNING_BASELINE,
        RunPhase.FAILED,
        {DETAIL_ERROR: FAILURE.model_dump()},
    ),
    (RUN_CANCELLED, RunPhase.CANCEL_REQUESTED, RunPhase.CANCELLED, {}),
    (
        RESULT_WRITTEN,
        RunPhase.BUILDING_REPORT,
        RunPhase.BUILDING_REPORT,
        {DETAIL_RESULT_DIGEST: digest_of("report")},
    ),
    (
        RUN_COMPLETED,
        RunPhase.BUILDING_REPORT,
        RunPhase.COMPLETED,
        {DETAIL_RESULT_DIGEST: digest_of("report")},
    ),
]


def test_every_kind_has_a_placement_under_test() -> None:
    assert {placement[0] for placement in CANONICAL_PLACEMENTS} == SPECIFIED_EVENT_KINDS


@pytest.mark.parametrize(
    ("kind", "previous_phase", "phase", "details"),
    CANONICAL_PLACEMENTS,
    ids=[placement[0] for placement in CANONICAL_PLACEMENTS],
)
def test_a_correctly_placed_event_is_accepted(
    kind: str,
    previous_phase: RunPhase | None,
    phase: RunPhase,
    details: dict[str, Any],
) -> None:
    validate_event_kind(
        build_event(
            sequence=0 if kind == RUN_CREATED else 3,
            phase=phase,
            previous_phase=previous_phase,
            kind=kind,
            details=details,
        )
    )


@pytest.mark.parametrize("kind", ["created", "worker_started", "run.restarted"])
def test_an_unknown_event_kind_is_refused(kind: str) -> None:
    with pytest.raises(ValidationError) as raised:
        validate_event_kind(
            build_event(
                sequence=1,
                phase=RunPhase.VALIDATING_TASKSET,
                previous_phase=RunPhase.CREATED,
                kind=kind,
            )
        )
    assert raised.value.code == "run_event_kind_invalid"


#: Placements that name a kind the phases contradict.
MISPLACED_EVENTS: list[tuple[str, str, RunPhase | None, RunPhase]] = [
    ("created after the opening", RUN_CREATED, None, RunPhase.CREATED),
    ("created from a phase", RUN_CREATED, RunPhase.CREATED, RunPhase.CREATED),
    ("created elsewhere", RUN_CREATED, None, RunPhase.RUNNING_BASELINE),
    (
        "worker outside created",
        WORKER_STARTED,
        RunPhase.RUNNING_BASELINE,
        RunPhase.RUNNING_BASELINE,
    ),
    (
        "worker as a transition",
        WORKER_STARTED,
        RunPhase.CREATED,
        RunPhase.VALIDATING_TASKSET,
    ),
    (
        "phase change that changes nothing",
        PHASE_ENTERED,
        RunPhase.RUNNING_BASELINE,
        RunPhase.RUNNING_BASELINE,
    ),
    (
        "phase change into failed",
        PHASE_ENTERED,
        RunPhase.RUNNING_BASELINE,
        RunPhase.FAILED,
    ),
    (
        "phase change into completed",
        PHASE_ENTERED,
        RunPhase.BUILDING_REPORT,
        RunPhase.COMPLETED,
    ),
    (
        "phase change into cancelled",
        PHASE_ENTERED,
        RunPhase.CANCEL_REQUESTED,
        RunPhase.CANCELLED,
    ),
    (
        "phase change into cancel_requested",
        PHASE_ENTERED,
        RunPhase.RUNNING_BASELINE,
        RunPhase.CANCEL_REQUESTED,
    ),
    (
        "progress across phases",
        PROGRESS_UPDATED,
        RunPhase.RUNNING_BASELINE,
        RunPhase.RUNNING_CANDIDATE,
    ),
    (
        "cancellation that stays put",
        CANCEL_REQUESTED,
        RunPhase.CANCEL_REQUESTED,
        RunPhase.CANCEL_REQUESTED,
    ),
    (
        "cancellation elsewhere",
        CANCEL_REQUESTED,
        RunPhase.RUNNING_BASELINE,
        RunPhase.RUNNING_CANDIDATE,
    ),
    (
        "failure elsewhere",
        RUN_FAILED,
        RunPhase.RUNNING_BASELINE,
        RunPhase.RUNNING_CANDIDATE,
    ),
    (
        "cancelled without a request",
        RUN_CANCELLED,
        RunPhase.RUNNING_BASELINE,
        RunPhase.CANCELLED,
    ),
    (
        "result outside building_report",
        RESULT_WRITTEN,
        RunPhase.RUNNING_BASELINE,
        RunPhase.RUNNING_BASELINE,
    ),
    (
        "result as a transition",
        RESULT_WRITTEN,
        RunPhase.VERIFYING_COMPARISON,
        RunPhase.BUILDING_REPORT,
    ),
    (
        "completion from elsewhere",
        RUN_COMPLETED,
        RunPhase.RUNNING_BASELINE,
        RunPhase.COMPLETED,
    ),
    (
        "completion into another phase",
        RUN_COMPLETED,
        RunPhase.BUILDING_REPORT,
        RunPhase.BUILDING_REPORT,
    ),
]

#: Details generous enough that no placement above fails for a missing key.
EVERY_DETAIL: dict[str, JsonValue] = {
    DETAIL_REQUEST_DIGEST: digest_of("request"),
    DETAIL_WORKER_PID: 4321,
    DETAIL_REQUESTED_BY: "cli",
    DETAIL_ERROR: FAILURE.model_dump(),
    DETAIL_RESULT_DIGEST: digest_of("report"),
    **progress_details(1, 20, "tasks"),
}


@pytest.mark.parametrize(
    ("kind", "previous_phase", "phase"),
    [case[1:] for case in MISPLACED_EVENTS],
    ids=[case[0] for case in MISPLACED_EVENTS],
)
def test_an_event_whose_kind_and_phases_disagree_is_refused(
    kind: str,
    previous_phase: RunPhase | None,
    phase: RunPhase,
) -> None:
    with pytest.raises(ValidationError) as raised:
        validate_event_kind(
            build_event(
                sequence=3,
                phase=phase,
                previous_phase=previous_phase,
                kind=kind,
                details=dict(EVERY_DETAIL),
            )
        )
    assert raised.value.code == "run_event_kind_invalid"


#: The kinds §7.4 defines as carrying something, and what they carry.
PLACEMENTS_WITH_DETAILS = [
    placement for placement in CANONICAL_PLACEMENTS if placement[3]
]


@pytest.mark.parametrize(
    ("kind", "previous_phase", "phase", "details"),
    PLACEMENTS_WITH_DETAILS,
    ids=[placement[0] for placement in PLACEMENTS_WITH_DETAILS],
)
def test_an_event_missing_the_details_its_kind_carries_is_refused(
    kind: str,
    previous_phase: RunPhase | None,
    phase: RunPhase,
    details: dict[str, Any],
) -> None:
    for key in details:
        incomplete = {name: value for name, value in details.items() if name != key}
        with pytest.raises(ValidationError) as raised:
            validate_event_kind(
                build_event(
                    sequence=0 if kind == RUN_CREATED else 3,
                    phase=phase,
                    previous_phase=previous_phase,
                    kind=kind,
                    details=incomplete,
                )
            )
        assert raised.value.code == "run_event_kind_invalid"


# ---------------------------------------------------------------------------
# Same-phase events
# ---------------------------------------------------------------------------


def test_a_run_records_the_worker_progress_and_the_result_without_moving() -> None:
    events = log_through(*WORKING_PATH)
    state = reduce_events(events)

    validate_same_phase_event(
        state,
        follow(events, phase=state.phase, kind=PROGRESS_UPDATED),
    )
    validate_same_phase_event(
        state,
        follow(events, phase=state.phase, kind=RESULT_WRITTEN),
    )
    validate_same_phase_event(
        reduce_events([created_event()]),
        build_event(
            sequence=1,
            phase=RunPhase.CREATED,
            previous_phase=RunPhase.CREATED,
            kind=WORKER_STARTED,
        ),
    )


@pytest.mark.parametrize(
    "kind",
    sorted(EVENT_KINDS - SAME_PHASE_EVENT_KINDS),
)
def test_no_other_kind_may_leave_a_run_where_it_is(kind: str) -> None:
    events = log_through(RunPhase.VALIDATING_TASKSET)
    state = reduce_events(events)

    with pytest.raises(RunError) as raised:
        validate_same_phase_event(state, follow(events, phase=state.phase, kind=kind))
    assert raised.value.code == "run_transition_invalid"


def test_a_run_that_has_not_started_working_reports_no_progress() -> None:
    events = [created_event()]
    state = reduce_events(events)

    with pytest.raises(RunError) as raised:
        validate_same_phase_event(
            state,
            follow(events, phase=RunPhase.CREATED, kind=PROGRESS_UPDATED),
        )
    assert raised.value.code == "run_transition_invalid"


def test_an_ended_run_records_nothing_further() -> None:
    events = log_through(*WORKING_PATH)
    events.append(
        follow(
            events,
            phase=RunPhase.COMPLETED,
            kind=RUN_COMPLETED,
            details={DETAIL_RESULT_DIGEST: digest_of("report")},
        )
    )
    state = reduce_events(events)

    with pytest.raises(RunError) as raised:
        validate_same_phase_event(
            state,
            follow(events, phase=RunPhase.COMPLETED, kind=RESULT_WRITTEN),
        )
    assert raised.value.code == "run_transition_invalid"


def test_apply_event_admits_a_same_phase_event_the_table_has_no_edge_for() -> None:
    events = log_through(RunPhase.VALIDATING_TASKSET, RunPhase.RUNNING_BASELINE)
    state = reduce_events(events)

    reported = apply_event(
        state,
        follow(
            events,
            phase=RunPhase.RUNNING_BASELINE,
            kind=PROGRESS_UPDATED,
            details=progress_details(4, 20, "tasks"),
        ),
    )

    assert reported.phase is RunPhase.RUNNING_BASELINE
    assert reported.progress == RunProgress(current=4, total=20, label="tasks")


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
    assert raised.value.code == "run_event_sequence_invalid"
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

    with pytest.raises(ValidationError) as raised:
        read_events(path)
    assert raised.value.code == "run_event_sequence_invalid"


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
    assert raised.value.code == "run_event_log_corrupt"
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


def test_a_log_must_open_with_the_created_event() -> None:
    with pytest.raises(ValidationError) as raised:
        initial_state(
            build_event(
                sequence=0,
                phase=RunPhase.CREATED,
                previous_phase=None,
                kind=WORKER_STARTED,
            )
        )
    assert raised.value.code == "run_event_kind_invalid"


def test_a_log_must_open_in_created() -> None:
    with pytest.raises(ValidationError):
        reduce_events(
            [
                build_event(
                    sequence=0,
                    phase=RunPhase.RUNNING_BASELINE,
                    previous_phase=None,
                    kind=RUN_CREATED,
                    details={DETAIL_REQUEST_DIGEST: digest_of("request")},
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
                    kind=RUN_CREATED,
                    details={DETAIL_REQUEST_DIGEST: digest_of("request")},
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
    assert raised.value.code == "run_event_sequence_invalid"
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

    with pytest.raises(ValidationError) as raised:
        apply_event(
            state,
            build_event(
                sequence=1,
                phase=RunPhase.VALIDATING_TASKSET,
                previous_phase=RunPhase.CREATED,
                run_id=OTHER_RUN_ID,
            ),
        )
    assert raised.value.code == "run_event_log_corrupt"


def test_apply_event_rejects_a_forbidden_transition() -> None:
    state = reduce_events([created_event()])

    with pytest.raises(RunError) as raised:
        apply_event(
            state,
            build_event(
                sequence=1,
                phase=RunPhase.RUNNING_BASELINE,
                previous_phase=RunPhase.CREATED,
            ),
        )
    assert raised.value.code == "run_transition_invalid"


def test_apply_event_rejects_an_unknown_kind() -> None:
    state = reduce_events([created_event()])

    with pytest.raises(ValidationError) as raised:
        apply_event(
            state,
            build_event(
                sequence=1,
                phase=RunPhase.VALIDATING_TASKSET,
                previous_phase=RunPhase.CREATED,
                kind="advanced",
            ),
        )
    assert raised.value.code == "run_event_kind_invalid"


def test_progress_survives_within_a_phase_and_resets_when_it_changes() -> None:
    events = log_through(RunPhase.VALIDATING_TASKSET)
    events.append(
        follow(
            events,
            phase=RunPhase.VALIDATING_TASKSET,
            kind=PROGRESS_UPDATED,
            details=progress_details(3, 20, "tasks"),
        )
    )

    carried = reduce_events(events)
    assert carried.progress == RunProgress(current=3, total=20, label="tasks")

    events.append(follow(events, phase=RunPhase.RUNNING_BASELINE))
    assert reduce_events(events).progress is None


def test_malformed_progress_is_rejected() -> None:
    events = log_through(RunPhase.VALIDATING_TASKSET)
    events.append(
        follow(
            events,
            phase=RunPhase.VALIDATING_TASKSET,
            kind=PROGRESS_UPDATED,
            details=progress_details(30, 20, "tasks"),
        )
    )

    with pytest.raises(ValidationError) as raised:
        reduce_events(events)
    assert raised.value.code == "run_event_kind_invalid"


@pytest.mark.parametrize("phase", list(WORKING_PATH), ids=lambda phase: phase.value)
def test_a_run_can_fail_from_every_working_phase(phase: RunPhase) -> None:
    reached = WORKING_PATH[: WORKING_PATH.index(phase) + 1]
    events = log_through(*reached)
    events.append(
        follow(
            events,
            phase=RunPhase.FAILED,
            kind=RUN_FAILED,
            details={DETAIL_ERROR: FAILURE.model_dump()},
        )
    )

    state = reduce_events(events)

    assert state.phase is RunPhase.FAILED
    assert state.error == FAILURE


def test_a_failed_run_records_why() -> None:
    state = reduce_events(
        [
            created_event(),
            build_event(
                sequence=1,
                phase=RunPhase.FAILED,
                previous_phase=RunPhase.CREATED,
                kind=RUN_FAILED,
                details={DETAIL_ERROR: FAILURE.model_dump()},
            ),
        ]
    )

    assert state.phase is RunPhase.FAILED
    assert state.error == FAILURE


def test_a_failure_without_an_error_is_rejected() -> None:
    with pytest.raises(ValidationError) as raised:
        reduce_events(
            [
                created_event(),
                build_event(
                    sequence=1,
                    phase=RunPhase.FAILED,
                    previous_phase=RunPhase.CREATED,
                    kind=RUN_FAILED,
                ),
            ]
        )
    assert raised.value.code == "run_event_kind_invalid"


def test_cancellation_records_when_it_was_asked_for() -> None:
    events = log_through(RunPhase.VALIDATING_TASKSET, RunPhase.RUNNING_BASELINE)
    events.append(
        follow(
            events,
            phase=RunPhase.CANCEL_REQUESTED,
            kind=CANCEL_REQUESTED,
            details={DETAIL_REQUESTED_BY: "cli"},
        )
    )
    asked_at = events[-1].timestamp
    events.append(follow(events, phase=RunPhase.CANCELLED, kind=RUN_CANCELLED))

    state = reduce_events(events)

    assert state.phase is RunPhase.CANCELLED
    assert state.cancel_requested_at == asked_at
    assert state.updated_at == events[-1].timestamp
    assert is_terminal(state.phase)


def test_a_second_cancellation_request_cannot_be_recorded() -> None:
    events = log_through(RunPhase.VALIDATING_TASKSET)
    events.append(
        follow(
            events,
            phase=RunPhase.CANCEL_REQUESTED,
            kind=CANCEL_REQUESTED,
            details={DETAIL_REQUESTED_BY: "cli"},
        )
    )
    events.append(
        follow(
            events,
            phase=RunPhase.CANCEL_REQUESTED,
            kind=CANCEL_REQUESTED,
            details={DETAIL_REQUESTED_BY: "cli"},
        )
    )

    with pytest.raises(ValidationError):
        reduce_events(events)


def test_the_worker_pid_and_its_start_time_come_from_the_log() -> None:
    state = reduce_events(
        [
            created_event(),
            build_event(
                sequence=1,
                phase=RunPhase.CREATED,
                previous_phase=RunPhase.CREATED,
                kind=WORKER_STARTED,
                details={DETAIL_WORKER_PID: 4321},
                offset_seconds=5,
            ),
        ]
    )

    assert state.worker_pid == 4321
    assert state.worker_started_at == FIXED_TIME + timedelta(seconds=5)


@pytest.mark.parametrize("pid", [0, -1, "4321", True])
def test_an_impossible_worker_pid_is_rejected(pid: Any) -> None:
    with pytest.raises(ValidationError) as raised:
        reduce_events(
            [
                created_event(),
                build_event(
                    sequence=1,
                    phase=RunPhase.CREATED,
                    previous_phase=RunPhase.CREATED,
                    kind=WORKER_STARTED,
                    details={DETAIL_WORKER_PID: pid},
                ),
            ]
        )
    assert raised.value.code == "run_event_kind_invalid"


def test_the_result_digest_is_projected_from_both_kinds_that_carry_it() -> None:
    digest = digest_of("report")
    events = log_through(*WORKING_PATH)
    events.append(
        follow(
            events,
            phase=RunPhase.BUILDING_REPORT,
            kind=RESULT_WRITTEN,
            details={DETAIL_RESULT_DIGEST: digest},
        )
    )
    assert reduce_events(events).result_digest == digest

    events.append(
        follow(
            events,
            phase=RunPhase.COMPLETED,
            kind=RUN_COMPLETED,
            details={DETAIL_RESULT_DIGEST: digest},
        )
    )
    finished = reduce_events(events)
    assert finished.phase is RunPhase.COMPLETED
    assert finished.result_digest == digest


def test_a_malformed_result_digest_is_rejected() -> None:
    events = log_through(*WORKING_PATH)
    events.append(
        follow(
            events,
            phase=RunPhase.BUILDING_REPORT,
            kind=RESULT_WRITTEN,
            details={DETAIL_RESULT_DIGEST: "not-a-digest"},
        )
    )

    with pytest.raises(ValidationError) as raised:
        reduce_events(events)
    assert raised.value.code == "run_event_kind_invalid"


def test_the_reducer_agrees_with_applying_events_one_at_a_time() -> None:
    events = [
        created_event(),
        build_event(
            sequence=1,
            phase=RunPhase.CREATED,
            previous_phase=RunPhase.CREATED,
            kind=WORKER_STARTED,
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
            kind=PROGRESS_UPDATED,
            details=progress_details(20, 20, "tasks"),
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

    state = store.create(request)

    raw = (paths.run_dir(RUN_ID) / "request.json").read_bytes()
    assert sha256_digest_bytes(raw) == digest_object(request)
    assert store.get_request(RUN_ID) == request
    assert state.phase is RunPhase.CREATED
    assert state.sequence == 0


def test_create_opens_the_log_and_the_projection(
    created_run: RunStore,
    paths: TechtreePaths,
) -> None:
    run_dir = paths.run_dir(RUN_ID)

    events = read_events(run_dir / "events.jsonl")
    assert len(events) == 1
    assert events[0].kind == RUN_CREATED
    assert events[0].details[DETAIL_REQUEST_DIGEST] == digest_object(build_request())
    assert json.loads((run_dir / "state.json").read_text())["phase"] == "created"
    assert created_run.state(RUN_ID).phase is RunPhase.CREATED


def test_a_run_directory_is_private(
    created_run: RunStore, paths: TechtreePaths
) -> None:
    mode = paths.run_dir(RUN_ID).stat().st_mode & 0o777

    assert mode == 0o700


def test_creating_the_same_run_twice_is_a_conflict(created_run: RunStore) -> None:
    with pytest.raises(ConflictError) as raised:
        created_run.create(build_request())
    assert raised.value.code == "run_already_exists"


def test_an_unknown_run_is_not_found(store: RunStore) -> None:
    for call in (
        lambda: store.get_request(RUN_ID),
        lambda: store.state(RUN_ID),
        lambda: store.rebuild_state(RUN_ID),
        lambda: store.read_pid(RUN_ID),
        lambda: store.get_result(RUN_ID),
        lambda: store.append(RUN_ID, phase=RunPhase.VALIDATING_TASKSET),
        lambda: store.request_cancel(RUN_ID, requested_by="cli"),
        lambda: store.write_pid(RUN_ID, 1),
        lambda: store.write_heartbeat(RUN_ID, RunPhase.CREATED),
        lambda: store.write_result(RUN_ID, build_report()),
    ):
        with pytest.raises(NotFoundError) as raised:
            call()
        assert raised.value.code == "run_not_found"


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
    state = created_run.append(RUN_ID, phase=RunPhase.VALIDATING_TASKSET)

    assert state.phase is RunPhase.VALIDATING_TASKSET
    assert state.sequence == 1
    events = read_events(paths.run_dir(RUN_ID) / "events.jsonl")
    assert events[-1].previous_phase is RunPhase.CREATED
    assert events[-1].kind == PHASE_ENTERED


def test_append_refuses_a_transition_the_machine_forbids(
    created_run: RunStore,
    paths: TechtreePaths,
) -> None:
    with pytest.raises(RunError) as raised:
        created_run.append(RUN_ID, phase=RunPhase.RUNNING_BASELINE)
    assert raised.value.code == "run_transition_invalid"

    # The refusal happens before the log is touched.
    assert len(read_events(paths.run_dir(RUN_ID) / "events.jsonl")) == 1


@pytest.mark.parametrize("kind", ["", "validating_taskset", "run.restarted"])
def test_append_refuses_a_kind_outside_the_vocabulary(
    created_run: RunStore,
    paths: TechtreePaths,
    kind: str,
) -> None:
    with pytest.raises(ValidationError) as raised:
        created_run.append(RUN_ID, phase=RunPhase.VALIDATING_TASKSET, kind=kind)
    assert raised.value.code == "run_event_kind_invalid"

    # The refusal happens before the log is touched.
    assert len(read_events(paths.run_dir(RUN_ID) / "events.jsonl")) == 1


def test_append_refuses_a_kind_the_phase_does_not_admit(
    created_run: RunStore,
    paths: TechtreePaths,
) -> None:
    with pytest.raises(ValidationError) as raised:
        created_run.append(
            RUN_ID,
            phase=RunPhase.VALIDATING_TASKSET,
            kind=RUN_FAILED,
            details={DETAIL_ERROR: FAILURE.model_dump()},
        )
    assert raised.value.code == "run_event_kind_invalid"
    assert len(read_events(paths.run_dir(RUN_ID) / "events.jsonl")) == 1


def test_nothing_is_appended_after_a_run_ends(created_run: RunStore) -> None:
    created_run.append(
        RUN_ID,
        phase=RunPhase.FAILED,
        kind=RUN_FAILED,
        details={DETAIL_ERROR: FAILURE.model_dump()},
    )

    with pytest.raises(RunError):
        created_run.append(
            RUN_ID,
            phase=RunPhase.CANCEL_REQUESTED,
            kind=CANCEL_REQUESTED,
            details={DETAIL_REQUESTED_BY: "cli"},
        )

    state = created_run.state(RUN_ID)
    assert state.error is not None
    assert state.error.message == FAILURE.message
    assert state == created_run.rebuild_state(RUN_ID)


def test_a_cancellation_request_is_recorded_once_however_often_it_is_asked(
    created_run: RunStore,
    paths: TechtreePaths,
) -> None:
    advance(created_run, RUN_ID, [RunPhase.VALIDATING_TASKSET])

    first = created_run.request_cancel(RUN_ID, requested_by="cli")
    again = created_run.request_cancel(RUN_ID, requested_by="another cli")

    assert first.phase is RunPhase.CANCEL_REQUESTED
    assert again == first
    events = read_events(paths.run_dir(RUN_ID) / "events.jsonl")
    assert [event.kind for event in events] == [
        RUN_CREATED,
        PHASE_ENTERED,
        CANCEL_REQUESTED,
    ]
    assert events[-1].details[DETAIL_REQUESTED_BY] == "cli"
    assert events[-1].previous_phase is RunPhase.VALIDATING_TASKSET


def test_an_ended_run_cannot_be_cancelled(created_run: RunStore) -> None:
    created_run.append(
        RUN_ID,
        phase=RunPhase.FAILED,
        kind=RUN_FAILED,
        details={DETAIL_ERROR: FAILURE.model_dump()},
    )

    with pytest.raises(RunError) as raised:
        created_run.request_cancel(RUN_ID, requested_by="cli")
    assert raised.value.code == "run_not_cancellable"


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


def test_state_rebuilds_when_the_projection_lags_the_journal(
    created_run: RunStore,
    paths: TechtreePaths,
) -> None:
    projection = paths.run_dir(RUN_ID) / "state.json"
    stale = projection.read_bytes()
    advance(created_run, RUN_ID, [RunPhase.VALIDATING_TASKSET])
    expected = created_run.state(RUN_ID)
    projection.write_bytes(stale)

    assert created_run.state(RUN_ID) == expected


def test_state_ahead_of_the_journal_is_corruption_not_a_cache_miss(
    created_run: RunStore,
    paths: TechtreePaths,
) -> None:
    advance(created_run, RUN_ID, [RunPhase.VALIDATING_TASKSET])
    projection = paths.run_dir(RUN_ID) / "state.json"
    current = json.loads(projection.read_text())
    current["sequence"] = current["sequence"] + 5
    projection.write_text(json.dumps(current))

    with pytest.raises(ConflictError) as caught:
        created_run.state(RUN_ID)
    assert caught.value.code == "run_state_ahead_of_journal"


def test_state_rebuilds_identically_from_the_events_alone(
    created_run: RunStore,
    paths: TechtreePaths,
) -> None:
    created_run.write_pid(RUN_ID, 424242)
    incremental = advance(created_run, RUN_ID, list(WORKING_PATH))
    created_run.write_result(RUN_ID, build_report())
    incremental.append(
        created_run.append(
            RUN_ID,
            phase=RunPhase.COMPLETED,
            kind=RUN_COMPLETED,
            details={DETAIL_RESULT_DIGEST: digest_object(build_report())},
        )
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
        created_run, RUN_ID, [RunPhase.VALIDATING_TASKSET, RunPhase.RUNNING_BASELINE]
    )
    states.append(created_run.request_cancel(RUN_ID, requested_by="cli"))
    states.append(
        created_run.append(RUN_ID, phase=RunPhase.CANCELLED, kind=RUN_CANCELLED)
    )
    events = read_events(paths.run_dir(RUN_ID) / "events.jsonl")

    for position, state in enumerate(states, start=2):
        assert state == reduce_events(events[:position])


def test_the_worker_pid_is_readable_and_recorded(created_run: RunStore) -> None:
    created_run.write_pid(RUN_ID, 1234)

    assert created_run.read_pid(RUN_ID) == 1234
    assert created_run.state(RUN_ID).worker_pid == 1234
    assert created_run.state(RUN_ID).phase is RunPhase.CREATED


def test_a_worker_announces_itself_before_the_run_starts_working(
    created_run: RunStore,
) -> None:
    advance(created_run, RUN_ID, [RunPhase.VALIDATING_TASKSET])

    with pytest.raises(ValidationError) as raised:
        created_run.write_pid(RUN_ID, 1234)
    assert raised.value.code == "run_event_kind_invalid"

    # The refusal happens before anything is written, so no pid file names a
    # worker the log never mentions.
    assert created_run.read_pid(RUN_ID) is None


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
    reach_building_report(created_run)

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


def test_a_result_belongs_to_the_phase_that_builds_the_report(
    created_run: RunStore,
) -> None:
    advance(created_run, RUN_ID, [RunPhase.VALIDATING_TASKSET])

    with pytest.raises(ValidationError) as raised:
        created_run.write_result(RUN_ID, build_report())
    assert raised.value.code == "run_event_kind_invalid"

    # Nothing is left in the run directory, so the write that the phase does
    # admit is still possible later.
    assert not created_run.result_path(RUN_ID).exists()
    advance(created_run, RUN_ID, list(WORKING_PATH[1:]))
    created_run.write_result(RUN_ID, build_report())
    assert created_run.state(RUN_ID).result_digest == digest_object(build_report())


def test_a_result_from_another_run_is_refused(created_run: RunStore) -> None:
    with pytest.raises(ValidationError):
        created_run.write_result(RUN_ID, build_report(run_id=OTHER_RUN_ID))


def test_an_ended_run_records_neither_a_result_nor_a_worker(
    created_run: RunStore,
) -> None:
    created_run.request_cancel(RUN_ID, requested_by="cli")
    created_run.append(RUN_ID, phase=RunPhase.CANCELLED, kind=RUN_CANCELLED)

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
            lambda: created_run.append(RUN_ID, phase=RunPhase.VALIDATING_TASKSET),
            lambda: created_run.request_cancel(RUN_ID, requested_by="cli"),
            lambda: created_run.rebuild_state(RUN_ID),
            lambda: created_run.write_pid(RUN_ID, 7),
            lambda: created_run.write_heartbeat(RUN_ID, RunPhase.CREATED),
            lambda: created_run.write_result(RUN_ID, build_report()),
        ):
            with pytest.raises(ConflictError) as raised:
                call()
            assert raised.value.code == "run_lock_timeout"
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

    created_run.request_cancel(RUN_ID, requested_by="cli")
    state = created_run.append(RUN_ID, phase=RunPhase.CANCELLED, kind=RUN_CANCELLED)

    events = read_events(paths.run_dir(RUN_ID) / "events.jsonl")
    assert events[-2].previous_phase is RunPhase.RUNNING_BASELINE
    assert state.cancel_requested_at is not None
    assert is_terminal(state.phase)
