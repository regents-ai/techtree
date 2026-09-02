"""Run requests, phases, events, and local state. Spec 11.12, decisions 0003.

A run has one phase at a time and moves forward through them. The phase names
are part of the CLI contract, so they are an enum rather than free text, and
the event stream records both the phase entered and the phase left — a reader
reconstructing a run from events should never have to infer where it came from.

``RunRequest`` is immutable: it is what was asked for. ``RunState`` is a
``StateModel`` because it is what is currently true, rewritten as the worker
makes progress. Keeping them in separate classes is what stops a heartbeat
update from being able to alter the request it is executing.

``RunRequestV2`` is the v0.2 sibling of the request, on the terms decision
0040 fixes: it names the execution plan its Campaign binds instead of
restating the Campaign's evaluation backend. ``RunState`` has no v0.2 sibling
because it states no execution or subject fact — it is the run's own position,
its worker's liveness, and its result — so there is nothing in it for the
execution plan to own.

Decisions document 0003 A5 puts ``policy_acknowledgement`` here. A draft states
which rights policy must be accepted; the run records that it *was* accepted,
by which method, and when. Decisions document 0019 section 2 makes that one
answer to one review rather than a handle that had to be presented: nothing is
started without the review having been shown and explicitly accepted, and a
caller that cannot be asked has to say so with a flag.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from techtree.models.base import (
    Digest,
    JsonValue,
    NonEmptyString,
    ProtocolModel,
    StateModel,
    UtcDateTime,
)
from techtree.models.campaign import ProgramRef, PublicContext
from techtree.models.cli import CliError
from techtree.models.evaluation_backend import EvaluationBackendSpec

__all__ = [
    "ExecutorKind",
    "PolicyAcknowledgement",
    "PublicRunState",
    "RunEvent",
    "RunPhase",
    "RunProgress",
    "RunRequest",
    "RunRequestV2",
    "RunState",
    "RunStatus",
    "VariantProgress",
]

type ExecutorKind = Literal["fake", "verifiers"]
"""Which executor a run was created to be executed by.

The two names are the two that exist, and they are the same two the receipts
of a run record — under ``execution_backend`` in
:class:`~techtree.models.episode_receipt.EpisodeReceipt`, and under
``executor_kind`` in its v0.2 sibling, which spells it the way this alias
does. A run and the receipts it produces should not need a translation table
to agree on what ran.

The value is decided when the run is created, from the Campaign, because that
is when a person is told what is about to happen and what it will cost. It is
a record of the answer, not the place the answer is worked out: the worker
re-reads the run's own staged Campaign and refuses a request that disagrees
with it, so a hand-edited request buys nothing.
"""


class RunPhase(StrEnum):
    """Where a run currently is."""

    CREATED = "created"
    VALIDATING_TASKSET = "validating_taskset"
    RUNNING_BASELINE = "running_baseline"
    RUNNING_CANDIDATE = "running_candidate"
    #: Both variants in flight at once. The sequential pair above stays for the
    #: fake executor; spec section 3.3 adds this one rather than replacing them.
    RUNNING_VARIANTS = "running_variants"
    BUILDING_RECEIPTS = "building_receipts"
    VERIFYING_COMPARISON = "verifying_comparison"
    BUILDING_REPORT = "building_report"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"


class PublicRunState(StrEnum):
    """Where a run is, in the five words a caller outside Techtree is told.

    ``RunPhase`` above is the run's own vocabulary and stays exactly as it is:
    the event log records phases, the worker moves between phases, and no phase
    is retired. This is a projection over those phases rather than a
    replacement for them, and it exists so the public vocabulary does not have
    to grow every time a backend adds a step to a run.

    The mapping is total and is written out once, in
    :data:`techtree.runs.machine.PUBLIC_STATE_BY_PHASE`, against the table in
    ``docs/v0.2/MACHINE_CONTRACT.md``.
    """

    PREPARED = "prepared"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PolicyAcknowledgement(ProtocolModel):
    """That a specific rights policy was accepted, how, and when.

    Decisions document 0003 A5, as amended by 0019 section 2.
    ``explicit_cli_review`` says the review of what the run would do — its
    size, the spending limit its Campaign declares, the one change being
    measured, where model calls go, and what an upload would carry — was put in
    front of whoever started it and
    explicitly accepted. It covers both spellings of that answer at the command
    line, the typed ``y`` and the flag an operator passes instead, because the
    fact being recorded is the same one; who gave the answer is recorded
    separately on the run's ``run.approved`` event.

    ``host_agent_confirmation`` is the approval surface the plugin presents in
    a conversation: the review is shown there, the person confirms there, and
    the plugin then starts that exact draft. The process that writes this
    record is not the one that asked the question, so which surface it was is
    declared by whoever starts the run rather than guessed at from the fact
    that nobody was prompted here.
    """

    data_policy_digest: Digest
    method: Literal[
        "explicit_cli_review",
        "host_agent_confirmation",
    ]
    acknowledged_at: UtcDateTime


def _check_the_request_runs_what_it_acknowledged(
    *,
    acknowledged_data_policy_digest: Digest,
    data_policy_digest: Digest,
    baseline_manifest_digest: Digest,
    candidate_manifest_digest: Digest,
) -> None:
    """Enforce the two rules every run request answers to, in either shape."""
    if acknowledged_data_policy_digest != data_policy_digest:
        raise ValueError(
            "the acknowledged DataPolicy is not the one this run executes under"
        )
    if baseline_manifest_digest == candidate_manifest_digest:
        raise ValueError("a run compares two different manifests")


class RunRequest(ProtocolModel):
    """What was asked for, fixed at the moment the run was created."""

    run_id: NonEmptyString
    draft_id: NonEmptyString
    draft_digest: Digest
    campaign_spec_digest: Digest
    program_ref: ProgramRef | None
    public_context: PublicContext | None
    data_policy_digest: Digest
    outcome_contract_digest: Digest | None
    evaluation_backend: EvaluationBackendSpec
    taskset_lock_digest: Digest | None
    baseline_manifest_digest: Digest
    candidate_manifest_digest: Digest
    policy_acknowledgement: PolicyAcknowledgement
    executor_kind: ExecutorKind
    created_at: UtcDateTime

    @model_validator(mode="after")
    def _check_acknowledged_policy_is_the_one_being_run(self) -> Self:
        """Reject a run acknowledging a different policy than it executes under."""
        _check_the_request_runs_what_it_acknowledged(
            acknowledged_data_policy_digest=(
                self.policy_acknowledgement.data_policy_digest
            ),
            data_policy_digest=self.data_policy_digest,
            baseline_manifest_digest=self.baseline_manifest_digest,
            candidate_manifest_digest=self.candidate_manifest_digest,
        )
        return self


class RunRequestV2(ProtocolModel):
    """What was asked for, under a v0.2 Campaign.

    A sibling of :class:`RunRequest`, on the terms decision 0040 fixes: the
    two share the request contract and nothing else, and neither validates as
    the other. What changes is where the run's execution facts come from. The
    v0.1 request restates the Campaign's ``evaluation_backend``; this one
    names the execution plan its Campaign binds, and the engine, the execution
    backend, the subject harness, and the evidence the run owes are that plan's
    four planes. A request that restated any of them could disagree with the
    plan the Campaign froze.

    It also says what it is. The v0.1 request carries no version literal, and
    for as long as it had no published schema that cost nothing; this one has
    a schema, so a reader who opens ``request.json`` learns which document is
    in front of them from the document rather than from its directory.
    """

    schema_version: Literal["techtree.run-request.v2"]
    run_id: NonEmptyString
    draft_id: NonEmptyString
    draft_digest: Digest
    campaign_spec_digest: Digest
    program_ref: ProgramRef | None
    public_context: PublicContext | None
    data_policy_digest: Digest
    outcome_contract_digest: Digest | None
    execution_plan_digest: Digest
    taskset_lock_digest: Digest | None
    baseline_manifest_digest: Digest
    candidate_manifest_digest: Digest
    policy_acknowledgement: PolicyAcknowledgement
    executor_kind: ExecutorKind
    created_at: UtcDateTime

    @model_validator(mode="after")
    def _check_acknowledged_policy_is_the_one_being_run(self) -> Self:
        """Reject a run acknowledging a different policy than it executes under."""
        _check_the_request_runs_what_it_acknowledged(
            acknowledged_data_policy_digest=(
                self.policy_acknowledgement.data_policy_digest
            ),
            data_policy_digest=self.data_policy_digest,
            baseline_manifest_digest=self.baseline_manifest_digest,
            candidate_manifest_digest=self.candidate_manifest_digest,
        )
        return self


class RunEvent(ProtocolModel):
    """One appended record of something that happened to a run."""

    sequence: int = Field(ge=0)
    timestamp: UtcDateTime
    run_id: NonEmptyString
    previous_phase: RunPhase | None
    phase: RunPhase
    kind: NonEmptyString
    details: dict[str, JsonValue]


class RunProgress(StateModel):
    """How far through the current phase the worker is."""

    current: int = Field(ge=0)
    total: int = Field(ge=0)
    label: NonEmptyString

    @model_validator(mode="after")
    def _check_progress_is_within_its_total(self) -> Self:
        """Reject progress that has passed the end of the work it describes."""
        if self.current > self.total:
            raise ValueError("progress cannot exceed its total")
        return self


class VariantProgress(StateModel):
    """How far one side of a concurrent comparison has got. Spec section 3.3.

    ``RunProgress`` measures one position in one phase, which is all a
    sequential run has to report. When both variants are in flight there are two
    positions at once, and each carries its own episode counts and its own
    lifecycle, so they are projected side by side rather than flattened.
    """

    variant: Literal["baseline", "candidate"]
    completed: int = Field(ge=0)
    total: int = Field(ge=0)
    running: int = Field(ge=0)
    errored: int = Field(ge=0)
    state: Literal["pending", "running", "completed", "failed", "cancelled"]


class RunState(StateModel):
    """What is currently true of a run, rewritten as it advances."""

    run_id: NonEmptyString
    phase: RunPhase
    sequence: int = Field(ge=0)
    updated_at: UtcDateTime
    worker_pid: int | None
    worker_started_at: UtcDateTime | None
    heartbeat_at: UtcDateTime | None
    cancel_requested_at: UtcDateTime | None
    error: CliError | None
    progress: RunProgress | None
    variant_progress: dict[str, VariantProgress] = Field(default_factory=dict)
    result_digest: Digest | None


class RunStatus(ProtocolModel):
    """A run's state plus the liveness facts only the host can determine."""

    state: RunState
    worker_alive: bool
    heartbeat_stale: bool
    result_available: bool
