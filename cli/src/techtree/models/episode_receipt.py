"""What one episode produced. Spec section 11.10.

The shape is frozen now and fake-populated until WP6, which is the point: the
statuses that say "this number is not evidence" have to exist before the first
number does. ``development_only`` is a first-class score and evidence status
rather than an absent field, so a fake receipt is unmistakably fake to a reader
and to a service, and nothing has to infer it from context.

A receipt points at ``campaign_spec_digest`` and carries the data policy that
governed it. The public Climb is an optional context, never the anchor: a
reproduction run has no Climb, and its receipts must still be complete.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import model_validator

from techtree.models.base import (
    ArtifactRef,
    Digest,
    NonEmptyString,
    ProtocolModel,
)
from techtree.models.campaign import ProgramRef, PublicContext
from techtree.models.evaluation_backend import EvaluationBackendSpec
from techtree.models.experiment import ExperimentVariant

__all__ = [
    "EpisodeReceipt",
    "EvidenceStatus",
    "NamedTraceReceipt",
    "ScoreStatus",
    "SubjectRuntimeReceipt",
]


class ScoreStatus(StrEnum):
    """How much weight the recorded reward carries."""

    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    ERRORED = "errored"
    MISSING = "missing"
    DEVELOPMENT_ONLY = "development_only"


class EvidenceStatus(StrEnum):
    """How complete the supporting evidence is."""

    NOT_COLLECTED = "not_collected"
    COMPLETE = "complete"
    PARTIAL = "partial"
    INVALID = "invalid"
    DEVELOPMENT_ONLY = "development_only"


class NamedTraceReceipt(ProtocolModel):
    """One named trace within an episode."""

    role: NonEmptyString
    trace_id: NonEmptyString
    trace_digest: Digest
    task_hash: Digest
    rewards: dict[str, float]
    metrics: dict[str, float | None]
    ok: bool


class SubjectRuntimeReceipt(ProtocolModel):
    """Where the subject agent actually executed, if it executed."""

    kind: Literal["not_executed", "docker"]
    resolved_image_digest: Digest | None = None
    platform: NonEmptyString | None = None

    @model_validator(mode="after")
    def _check_runtime_evidence_matches_kind(self) -> Self:
        """Reject runtime detail on an episode that never ran a runtime."""
        if self.kind == "not_executed" and (
            self.resolved_image_digest is not None or self.platform is not None
        ):
            raise ValueError(
                "an episode that did not execute a runtime cannot report the "
                "image or platform it executed on"
            )
        if self.kind == "docker" and self.resolved_image_digest is None:
            raise ValueError("a docker episode records the image digest it ran")
        return self


class EpisodeReceipt(ProtocolModel):
    """The complete record of one scored episode."""

    schema_version: Literal["techtree.episode-receipt.v1alpha1"]
    id: NonEmptyString
    run_id: NonEmptyString
    campaign_spec_digest: Digest
    program_ref: ProgramRef | None
    public_context: PublicContext | None
    data_policy_digest: Digest
    outcome_contract_digest: Digest | None
    evaluation_backend: EvaluationBackendSpec
    subject_runtime: SubjectRuntimeReceipt
    variant: ExperimentVariant
    experiment_manifest_digest: Digest
    episode_id: NonEmptyString
    episode_digest: Digest
    task_hash: Digest
    named_traces: dict[str, list[NamedTraceReceipt]]
    score_status: ScoreStatus
    evidence_status: EvidenceStatus
    execution_backend: Literal["fake", "verifiers"]
    artifacts: list[ArtifactRef]

    @model_validator(mode="after")
    def _check_fake_episodes_are_unmistakably_fake(self) -> Self:
        """Refuse to let a fake episode wear a real score."""
        if self.execution_backend == "fake" and (
            self.score_status is not ScoreStatus.DEVELOPMENT_ONLY
            or self.evidence_status is not EvidenceStatus.DEVELOPMENT_ONLY
        ):
            raise ValueError(
                "a fake episode reports development_only score and evidence; "
                "any other status would present invented numbers as results"
            )
        return self
