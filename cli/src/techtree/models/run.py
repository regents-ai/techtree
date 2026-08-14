"""Run requests, phases, events, and local state. Spec 11.12, decisions 0003.

A run has one phase at a time and moves forward through them. The phase names
are part of the CLI contract, so they are an enum rather than free text, and
the event stream records both the phase entered and the phase left — a reader
reconstructing a run from events should never have to infer where it came from.

``RunRequest`` is immutable: it is what was asked for. ``RunState`` is a
``StateModel`` because it is what is currently true, rewritten as the worker
makes progress. Keeping them in separate classes is what stops a heartbeat
update from being able to alter the request it is executing.

Decisions document 0003 A5 puts ``policy_acknowledgement`` here. A draft states
which rights policy must be accepted; the run records that it *was* accepted,
by which method, and when. Holding a valid confirmation token never implied
acceptance, and in machine mode the caller must name the exact policy digest.
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
    "RunEvent",
    "RunPhase",
    "RunProgress",
    "RunRequest",
    "RunState",
    "RunStatus",
    "VariantProgress",
]

type ExecutorKind = Literal["fake", "verifiers"]
"""Which executor a run was created to be executed by.

The two names are the two that exist, and they are the same two an
:class:`~techtree.models.episode_receipt.EpisodeReceipt` records under
``execution_backend`` — a run and the receipts it produces should not need a
translation table to agree on what ran.

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


class PolicyAcknowledgement(ProtocolModel):
    """That a specific rights policy was accepted, how, and when.

    Decisions document 0003 A5. ``explicit_cli_digest`` is the machine-mode
    method and requires the caller to have named the exact policy digest, so
    that automation cannot accept a policy it never read.
    """

    data_policy_digest: Digest
    method: Literal[
        "interactive_cli",
        "explicit_cli_digest",
        "host_agent_confirmation",
    ]
    acknowledged_at: UtcDateTime


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
        if self.policy_acknowledgement.data_policy_digest != self.data_policy_digest:
            raise ValueError(
                "the acknowledged DataPolicy is not the one this run executes under"
            )
        if self.baseline_manifest_digest == self.candidate_manifest_digest:
            raise ValueError("a run compares two different manifests")
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
