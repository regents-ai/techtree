"""The result of one comparison. Spec section 11.11.

An ``UpliftReport`` answers one question: did the candidate satisfy the
scientific comparison contract? It does not answer whether anyone should deploy
the result. That is a release decision, it depends on cost, risk, and product
context that this object knows nothing about, and it belongs to a future
``ReleaseDecision``.

The five statuses are separate on purpose. A run can complete while its scores
are development-only; scores can be valid while evidence is partial; a
comparison can be controlled while publication is blocked by the data policy.
Collapsing them into one "status" would force a caller to guess which of those
five things a single word referred to.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from techtree.models.base import Digest, NonEmptyString, ProtocolModel, UtcDateTime
from techtree.models.campaign import ProgramRef, PublicContext
from techtree.models.episode_receipt import EvidenceStatus, ScoreStatus
from techtree.models.evaluation_backend import EvaluationBackendSpec
from techtree.models.experiment import ManifestComparison

__all__ = [
    "ComparisonStatus",
    "ExecutionStatus",
    "PrimaryUpliftResult",
    "PublicationStatus",
    "TaskDelta",
    "UpliftDecision",
    "UpliftReport",
    "UpliftStatuses",
]


class ExecutionStatus(StrEnum):
    """How the run itself ended."""

    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ComparisonStatus(StrEnum):
    """Whether the two manifests differed only where permitted."""

    PENDING = "pending"
    CONTROLLED = "controlled"
    CONTROLLED_WITH_WARNINGS = "controlled_with_warnings"
    INVALID = "invalid"
    DEVELOPMENT_ONLY = "development_only"


class PublicationStatus(StrEnum):
    """Where the report stands with respect to being published."""

    NOT_REQUESTED = "not_requested"
    BLOCKED = "blocked"
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"


class UpliftDecision(StrEnum):
    """The verdict on the scientific comparison contract."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"
    INVALID = "invalid"
    DEVELOPMENT_ONLY = "development_only"


class TaskDelta(ProtocolModel):
    """What one task contributed to the comparison."""

    task_hash: Digest
    baseline_reward: float
    candidate_reward: float
    delta: float


class PrimaryUpliftResult(ProtocolModel):
    """The headline comparison on the primary reward."""

    reward_name: NonEmptyString
    baseline_mean: float
    candidate_mean: float
    absolute_delta: float
    relative_delta: float | None
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    ties: int = Field(ge=0)


class UpliftStatuses(ProtocolModel):
    """The five independent statuses of a report."""

    execution: ExecutionStatus
    score: ScoreStatus
    evidence: EvidenceStatus
    comparison: ComparisonStatus
    publication: PublicationStatus


class UpliftReport(ProtocolModel):
    """The complete result of one baseline-versus-candidate comparison."""

    schema_version: Literal["techtree.uplift-report.v1alpha1"]
    id: NonEmptyString
    run_id: NonEmptyString
    campaign_spec_digest: Digest
    program_ref: ProgramRef | None
    public_context: PublicContext | None
    data_policy_digest: Digest
    outcome_contract_digest: Digest | None
    evaluation_backend: EvaluationBackendSpec
    taskset_validation_receipt_digest: Digest
    baseline_manifest_digest: Digest
    candidate_manifest_digest: Digest
    statuses: UpliftStatuses
    manifest_comparison: ManifestComparison
    primary_result: PrimaryUpliftResult
    task_deltas: list[TaskDelta]
    decision: UpliftDecision
    proof_grade: Literal["development_only", "P1"]
    publication_eligible: bool
    created_at: UtcDateTime

    @model_validator(mode="after")
    def _check_report_cannot_overclaim(self) -> Self:
        """Keep a development-only report from presenting itself as evidence."""
        development_only = self.proof_grade == "development_only"
        if development_only and self.decision is not UpliftDecision.DEVELOPMENT_ONLY:
            raise ValueError(
                "a development_only report reaches a development_only decision"
            )
        if development_only and self.publication_eligible:
            raise ValueError("a development_only report is never publication eligible")
        if self.publication_eligible and self.statuses.publication is (
            PublicationStatus.BLOCKED
        ):
            raise ValueError(
                "a report cannot be publication eligible while its publication "
                "status is blocked"
            )
        if self.baseline_manifest_digest == self.candidate_manifest_digest:
            raise ValueError(
                "a report compares two different manifests; an identical pair "
                "measures nothing"
            )
        return self
