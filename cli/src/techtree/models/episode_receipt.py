"""What one episode produced. Spec section 11.10.

The shape is frozen now and fake-populated until WP6, which is the point: the
statuses that say "this number is not evidence" have to exist before the first
number does. ``development_only`` is a first-class score and evidence status
rather than an absent field, so a fake receipt is unmistakably fake to a reader
and to a service, and nothing has to infer it from context.

A receipt points at ``campaign_spec_digest`` and carries the data policy that
governed it. The public Climb is an optional context, never the anchor: a
reproduction run has no Climb, and its receipts must still be complete.

Two receipt documents live here and they are siblings, on the terms decision
0040 fixes. ``EpisodeReceipt`` is v0.1 and its bytes are frozen.
``EpisodeReceiptV2`` receipts an episode of a v0.2 Campaign: it names the
execution plan that Campaign binds and reports where the work ran as the
proof's ``execution_location`` facet, in place of the ``evaluation_backend``
the v0.1 receipt copied out of the Campaign. Whose word the result rests on is
not restated either — that is the evidence contract's ``execution_observation``
facet, and one answer in two documents is one answer that can disagree with
itself.
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
from techtree.models.evidence import ExecutionLocation
from techtree.models.experiment import ExperimentVariant
from techtree.models.run import ExecutorKind

__all__ = [
    "EpisodeReceipt",
    "EpisodeReceiptV2",
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


def _check_a_fake_episode_is_unmistakably_fake(
    *,
    executor: str,
    score_status: ScoreStatus,
    evidence_status: EvidenceStatus,
) -> None:
    """Refuse to let a fake episode wear a real score, in either shape."""
    if executor == "fake" and (
        score_status is not ScoreStatus.DEVELOPMENT_ONLY
        or evidence_status is not EvidenceStatus.DEVELOPMENT_ONLY
    ):
        raise ValueError(
            "a fake episode reports development_only score and evidence; "
            "any other status would present invented numbers as results"
        )


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
        _check_a_fake_episode_is_unmistakably_fake(
            executor=self.execution_backend,
            score_status=self.score_status,
            evidence_status=self.evidence_status,
        )
        return self


class EpisodeReceiptV2(ProtocolModel):
    """The complete record of one scored episode of a v0.2 Campaign.

    A sibling of :class:`EpisodeReceipt`, not a refinement of it. Two fields
    replace the ``evaluation_backend`` the v0.1 receipt copied out of its
    Campaign: ``execution_plan_digest`` names the plan the Campaign is bound
    to, which fixes all four planes at once, and ``execution_location`` is the
    proof's own facet for where the work ran.

    ``executor_kind`` below is neither of them, and it is renamed for exactly
    that reason. It names the executor that produced this episode — the fake
    one or Verifiers — which is a fact about this process rather than one the
    Campaign or the plan declares, and the ``fake`` value is what keeps an
    invented number from wearing a real score. The v0.1 receipt calls it
    ``execution_backend``, which in v0.2 is one word away from the plan's
    execution plane; the spelling here is the one
    :data:`~techtree.models.run.ExecutorKind` already gives it, so a run and
    its receipts name that fact identically.
    """

    schema_version: Literal["techtree.episode-receipt.v2"]
    id: NonEmptyString
    run_id: NonEmptyString
    campaign_spec_digest: Digest
    program_ref: ProgramRef | None
    public_context: PublicContext | None
    data_policy_digest: Digest
    outcome_contract_digest: Digest | None
    execution_plan_digest: Digest
    execution_location: ExecutionLocation
    subject_runtime: SubjectRuntimeReceipt
    variant: ExperimentVariant
    experiment_manifest_digest: Digest
    episode_id: NonEmptyString
    episode_digest: Digest
    task_hash: Digest
    named_traces: dict[str, list[NamedTraceReceipt]]
    score_status: ScoreStatus
    evidence_status: EvidenceStatus
    executor_kind: ExecutorKind
    artifacts: list[ArtifactRef]

    @model_validator(mode="after")
    def _check_fake_episodes_are_unmistakably_fake(self) -> Self:
        """Refuse to let a fake episode wear a real score."""
        _check_a_fake_episode_is_unmistakably_fake(
            executor=self.executor_kind,
            score_status=self.score_status,
            evidence_status=self.evidence_status,
        )
        return self
