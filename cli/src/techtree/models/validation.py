"""Taskset locking and mechanical validation. Spec 11.9, decisions 0003 A1.

Three objects, with a deliberate split between them.

``TasksetLock``
    What the taskset resolved to: engine, package, ordered task hashes, and the
    membership digest computed from them.

``TasksetValidationReceipt``
    The scientific answer to one narrow question — is this taskset mechanically
    valid and internally consistent? It carries no identifier, no timestamp, no
    duration, no path, and no raw log. Decisions document 0003 makes the
    receipt's own content digest its identity, which is what allows the
    publisher's receipt and a participant's locally recomputed receipt to be
    compared by equality instead of by narrative. A display identifier can be
    derived with :func:`validation_display_id`; it is never stored.

``ValidationExecutionRecord``
    Everything the receipt refuses to carry: when it ran, on which host, with
    which command, and which raw artifacts it left behind. It is local
    operational provenance, never part of the Campaign graph, never referenced
    by a public Climb, and never byte-compared by ``make generated-check``.

Between the raw upstream output and the receipt sits ``ValidationEvidence``:
the normalized, deterministic form of what the validator reported, with
elapsed times, temporary paths, run identifiers, and host detail removed. That
is the artifact a receipt points at and the one that ships publicly.

The receipt does not answer whether the environment is discriminative, robust
to reward hacking, suitable for RL, or economically useful. Those belong to a
future ``EnvironmentQualificationReport``.
"""

from __future__ import annotations

from typing import Final, Literal, Self

from pydantic import Field, model_validator

from techtree.models.base import (
    ArtifactRef,
    Digest,
    NonEmptyString,
    ProtocolModel,
    StateModel,
    UtcDateTime,
)
from techtree.models.campaign import TasksetRef

__all__ = [
    "REQUIRED_VALIDATION_CHECKS",
    "TasksetLock",
    "TasksetValidationReceipt",
    "UpstreamValidationSummary",
    "ValidationCheck",
    "ValidationEvidence",
    "ValidationEvidenceSummary",
    "ValidationEvidenceTask",
    "ValidationExecutionRecord",
    "ValidationMethod",
    "ValidationTaskOutcome",
    "validation_display_id",
]

#: Every check a receipt must report on. A receipt that silently omits one is
#: not a weaker receipt, it is an unreadable one: a reader cannot tell whether
#: the check passed or was never attempted.
REQUIRED_VALIDATION_CHECKS: Final[tuple[str, ...]] = (
    "upstream_gold",
    "upstream_setup",
    "membership_repeatability",
    "task_hash_uniqueness",
    "committed_membership_match",
    "expected_task_count",
)

#: How many hexadecimal characters of the receipt digest a display identifier
#: shows. Enough to be unambiguous in a terminal, short enough to read aloud.
_DISPLAY_ID_HEX_LENGTH: Final = 24


class TasksetLock(ProtocolModel):
    """What a taskset reference resolved to, pinned."""

    schema_version: Literal["techtree.taskset-lock.v1alpha1"]
    taskset_ref: TasksetRef
    engine_digest: Digest
    resolved_package_digest: Digest
    ordered_task_hashes: list[Digest]
    membership_digest: Digest
    task_count: int = Field(ge=1)

    @model_validator(mode="after")
    def _check_task_list(self) -> Self:
        """Reject a hash list that disagrees with the count or repeats a task."""
        if len(self.ordered_task_hashes) != self.task_count:
            raise ValueError(
                f"lock records {len(self.ordered_task_hashes)} task hashes but "
                f"a task_count of {self.task_count}"
            )
        if len(set(self.ordered_task_hashes)) != len(self.ordered_task_hashes):
            raise ValueError("locked task hashes must be unique")
        return self


class ValidationCheck(ProtocolModel):
    """One mechanical check and what it found."""

    id: NonEmptyString
    status: Literal["passed", "failed", "warning", "not_run"]
    detail: NonEmptyString


class UpstreamValidationSummary(ProtocolModel):
    """What the upstream validator reported, in aggregate."""

    mode: Literal["all", "gold", "setup"]
    total: int = Field(ge=0)
    recorded: int = Field(ge=0)
    valid: int = Field(ge=0)
    invalid: int = Field(ge=0)
    error: int = Field(ge=0)
    timeout: int = Field(ge=0)
    missing: int = Field(ge=0)
    valid_rate: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_counts_add_up(self) -> Self:
        """Reject a summary whose parts do not account for its total."""
        counted = self.valid + self.invalid + self.error + self.timeout + self.missing
        if counted != self.total:
            raise ValueError(
                f"summary accounts for {counted} tasks but reports a total of "
                f"{self.total}"
            )
        if self.recorded > self.total:
            raise ValueError("recorded cannot exceed total")
        return self


class ValidationMethod(ProtocolModel):
    """How the validation was performed, in reproducible terms."""

    kind: Literal["verifiers_validate"]
    mode: Literal["all"]
    runtime: Literal["subprocess"]
    validator_revision: NonEmptyString


class ValidationTaskOutcome(ProtocolModel):
    """One validator verdict for one task."""

    valid: bool
    reason: NonEmptyString


class ValidationEvidenceTask(ProtocolModel):
    """The normalized per-task record the validator produced."""

    position: int = Field(ge=0)
    task_hash: Digest
    gold: ValidationTaskOutcome
    setup: ValidationTaskOutcome


class ValidationEvidenceSummary(ProtocolModel):
    """Aggregate counts over the normalized task records."""

    total: int = Field(ge=0)
    valid: int = Field(ge=0)
    invalid: int = Field(ge=0)
    error: int = Field(ge=0)
    timeout: int = Field(ge=0)
    missing: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_counts_add_up(self) -> Self:
        """Reject a summary whose parts do not account for its total."""
        counted = self.valid + self.invalid + self.error + self.timeout + self.missing
        if counted != self.total:
            raise ValueError(
                f"evidence accounts for {counted} tasks but reports a total of "
                f"{self.total}"
            )
        return self


class ValidationEvidence(ProtocolModel):
    """Deterministic normalized validator output. Decisions 0003 A1.

    Normalization has already removed elapsed times, wall-clock timestamps,
    temporary paths, run identifiers, process identifiers, hostnames, absolute
    output directories, log prefixes, and tracebacks from successful runs.
    What remains is the part two honest parties must agree on.
    """

    schema_version: Literal["techtree.validation-evidence.v1alpha1"]
    taskset_lock_digest: Digest
    method: ValidationMethod
    tasks: list[ValidationEvidenceTask]
    summary: ValidationEvidenceSummary

    @model_validator(mode="after")
    def _check_tasks_are_a_dense_ordered_run(self) -> Self:
        """Reject gaps, repeats, or an order that depends on who wrote the file."""
        positions = [task.position for task in self.tasks]
        if positions != list(range(len(self.tasks))):
            raise ValueError(
                "evidence tasks must be sorted by position and cover 0..n-1 "
                "without gaps"
            )
        hashes = [task.task_hash for task in self.tasks]
        if len(set(hashes)) != len(hashes):
            raise ValueError("evidence task hashes must be unique")
        if self.summary.total != len(self.tasks):
            raise ValueError(
                f"evidence lists {len(self.tasks)} tasks but its summary reports "
                f"{self.summary.total}"
            )
        return self


class TasksetValidationReceipt(ProtocolModel):
    """Is this taskset mechanically valid and internally consistent?

    Decisions document 0003 A1 removed the identifier, creation time, raw
    artifact list, durations, absolute paths, and tracebacks that the original
    shape carried. Every one of those varies between two correct runs of the
    same validation, which meant the publisher's receipt and a participant's
    receipt could never be equal even when they agreed completely. They now
    are, and that equality is the check.
    """

    schema_version: Literal["techtree.taskset-validation.v1alpha1"]
    taskset_lock_digest: Digest
    engine_digest: Digest
    method: ValidationMethod
    status: Literal["valid", "invalid", "errored"]
    upstream_summary: UpstreamValidationSummary
    checks: list[ValidationCheck]
    normalized_evidence: ArtifactRef | None

    @model_validator(mode="after")
    def _check_required_checks_are_reported(self) -> Self:
        """Reject a receipt that omits or repeats a required check."""
        reported = [check.id for check in self.checks]
        if len(set(reported)) != len(reported):
            raise ValueError("a receipt reports each check exactly once")
        missing = [name for name in REQUIRED_VALIDATION_CHECKS if name not in reported]
        if missing:
            raise ValueError(
                "receipt is missing required checks: " + ", ".join(missing)
            )
        if self.status == "valid" and any(
            check.status == "failed" for check in self.checks
        ):
            raise ValueError("a receipt with a failed check is not valid")
        return self


class ValidationExecutionRecord(StateModel):
    """Local operational provenance for one validation execution.

    Decisions document 0003 A1. This is the mutable, host-specific companion to
    the receipt. It is never part of the Campaign graph, never referenced by a
    public Climb, never the publisher commitment, and never byte-compared by
    generated-fixture checks.
    """

    schema_version: Literal["techtree.validation-execution.v1alpha1"]
    id: NonEmptyString
    receipt_digest: Digest
    started_at: UtcDateTime
    finished_at: UtcDateTime
    command: list[NonEmptyString]
    command_digest: Digest
    host_platform: NonEmptyString
    worker_pid: int | None
    raw_artifacts: list[ArtifactRef]

    @model_validator(mode="after")
    def _check_execution_window(self) -> Self:
        """Reject a record that finished before it started."""
        if self.finished_at < self.started_at:
            raise ValueError("finished_at cannot precede started_at")
        if not self.command:
            raise ValueError("a validation execution records the command it ran")
        return self


def validation_display_id(receipt_digest: Digest) -> str:
    """Return the human-facing identifier derived from a receipt digest.

    The value is derived for display only. Storing it inside the receipt would
    put a second, redundant identity in an object whose whole point is that its
    content is its identity.
    """
    _, _, hexadecimal = receipt_digest.partition(":")
    return f"validation_{hexadecimal[:_DISPLAY_ID_HEX_LENGTH]}"
