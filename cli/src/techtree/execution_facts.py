"""Projecting a bound execution plan onto the v0.2 run-side documents.

Plan `docs/plan/v0.2.md`, "Four-plane execution model" and "Campaign and
execution-plan ownership"; decision 0040.

Under v0.1 every run-side document copied its execution and subject facts out
of the Campaign: the experiment manifest, the run request, the episode
receipt, the uplift report, the climb summary, and the compatibility result all
restated ``evaluation_backend``, and two of them restated the subject harness
as well. Under v0.2 those facts belong to the four planes of the
:class:`~techtree.models.execution_plan.ResolvedExecutionPlan` the Campaign
binds, and the v0.2 Campaign does not carry them at all.

This module is the one place that projection is written. Every function here
is pure: it reads a Campaign and a plan, it returns a value, and it touches no
clock, no file, no host. That is what lets the same projection be checked in a
test and used by a producer without either one drifting from the other.

Three things are load-bearing.

*Nothing is projected from a plan the Campaign is not bound to.* Every
function begins by re-deriving the plan's digest and comparing it against the
Campaign's ``execution_plan_digest``. A projection taken from an unbound plan
would state facts about a run that never happened, and would do it in a
document nobody could tell was wrong.

*One frozen record per document.* Each function returns exactly the fields its
document owes to the plan and nothing else, so "which fields of this document
come from the plan" is a question with a typed answer rather than a comment.

*The plan states where the work runs, and a run that cannot honour it refuses.*
:class:`~techtree.models.evidence.ExecutionLocation` is projected from the
plan's execution plane, because that is the location the Campaign was frozen
against. A run that would execute somewhere else is a run of a different plan,
and the producer refuses it rather than receipting a location the Campaign
never agreed to.
"""

from __future__ import annotations

from dataclasses import dataclass

from techtree.canonical import digest_object
from techtree.errors import ValidationError
from techtree.models.base import Digest
from techtree.models.campaign import CampaignSpecV2
from techtree.models.evidence import ExecutionLocation, ExecutionLocationKind
from techtree.models.execution_plan import (
    SUPPORTED_EXECUTION_BACKEND_KINDS,
    SUPPORTED_SUBJECT_BACKEND_KINDS,
    ExecutionBackendKind,
    ResolvedExecutionPlan,
    SubjectBackendKind,
)

__all__ = [
    "ClimbSummaryExecutionFacts",
    "CompatibilityResultExecutionFacts",
    "EpisodeReceiptExecutionFacts",
    "ExperimentConfigurationExecutionFacts",
    "RunRequestExecutionFacts",
    "UpliftReportExecutionFacts",
    "bound_execution_plan_digest",
    "climb_summary_execution_facts",
    "compatibility_result_execution_facts",
    "episode_receipt_execution_facts",
    "experiment_configuration_execution_facts",
    "release_core_subject_hermes_version",
    "run_request_execution_facts",
    "uplift_report_execution_facts",
]


# ---------------------------------------------------------------------------
# The binding
# ---------------------------------------------------------------------------


def bound_execution_plan_digest(
    campaign: CampaignSpecV2,
    plan: ResolvedExecutionPlan,
) -> Digest:
    """Return the plan's digest, refusing a plan this Campaign is not bound to.

    The digest is re-derived from the plan rather than taken from the Campaign,
    which is the only way the pair can be checked at all: a Campaign that
    simply repeated a stored number would agree with any plan handed to it.
    """
    digest = digest_object(plan)
    if digest != campaign.execution_plan_digest:
        raise ValidationError(
            "this execution plan is not the one the Campaign binds",
            details={
                "campaign_execution_plan_digest": campaign.execution_plan_digest,
                "plan_digest": digest,
            },
        )
    return digest


def _execution_location(plan: ResolvedExecutionPlan) -> ExecutionLocation:
    """Return the location the plan's execution plane fixes.

    The two vocabularies are the same two words on purpose: the execution
    plane's kind is what the proof's location facet reports, so the projection
    is a rename and never a decision.
    """
    return ExecutionLocation(kind=ExecutionLocationKind(plan.execution.kind.value))


# ---------------------------------------------------------------------------
# One record per document
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ExperimentConfigurationExecutionFacts:
    """What an :class:`ExperimentConfigurationV2` owes to the plan."""

    execution_plan_digest: Digest


@dataclass(frozen=True, slots=True)
class RunRequestExecutionFacts:
    """What a :class:`RunRequestV2` owes to the plan."""

    execution_plan_digest: Digest


@dataclass(frozen=True, slots=True)
class EpisodeReceiptExecutionFacts:
    """What an :class:`EpisodeReceiptV2` owes to the plan."""

    execution_plan_digest: Digest
    execution_location: ExecutionLocation


@dataclass(frozen=True, slots=True)
class UpliftReportExecutionFacts:
    """What an :class:`UpliftReportV2` owes to the plan."""

    execution_plan_digest: Digest
    execution_location: ExecutionLocation


@dataclass(frozen=True, slots=True)
class ClimbSummaryExecutionFacts:
    """What a :class:`ClimbSummaryV2` owes to the plan.

    The harness coordinates are display facts about what is being measured,
    and they come from the subject plane because that is where the v0.2
    Campaign no longer states them.
    """

    subject_harness: str
    subject_harness_version: str
    execution_backend_kind: ExecutionBackendKind


@dataclass(frozen=True, slots=True)
class CompatibilityResultExecutionFacts:
    """What a :class:`CompatibilityResultV2` owes to the plan.

    All three planes a host can fail, because a result that reported two of
    them would be silent about the third. The evaluation plane is carried as
    the two coordinates a reader can act on: the commit the engine was built
    from, and the digest of the wheel itself.

    Support is decided against the kinds this release resolves, which are
    narrower than the kinds the protocol can express. A plan naming a backend
    the release does not resolve is not a malformed plan; it is a plan this
    build cannot run, which is exactly what a compatibility result is for.
    There is no matching flag for the evaluation plane: whether the engine on
    this host is the wheel the plan pins is a comparison against something
    installed, which the producer makes, not a property of the plan.
    """

    execution_plan_digest: Digest
    evaluation_engine_source_commit: str
    evaluation_engine_wheel_digest: Digest
    execution_backend_kind: ExecutionBackendKind
    execution_backend_supported: bool
    subject_backend_kind: SubjectBackendKind
    subject_backend_supported: bool


# ---------------------------------------------------------------------------
# The projections
# ---------------------------------------------------------------------------


def experiment_configuration_execution_facts(
    campaign: CampaignSpecV2,
    plan: ResolvedExecutionPlan,
) -> ExperimentConfigurationExecutionFacts:
    """Project the plan onto a v0.2 experiment configuration."""
    return ExperimentConfigurationExecutionFacts(
        execution_plan_digest=bound_execution_plan_digest(campaign, plan)
    )


def run_request_execution_facts(
    campaign: CampaignSpecV2,
    plan: ResolvedExecutionPlan,
) -> RunRequestExecutionFacts:
    """Project the plan onto a v0.2 run request."""
    return RunRequestExecutionFacts(
        execution_plan_digest=bound_execution_plan_digest(campaign, plan)
    )


def episode_receipt_execution_facts(
    campaign: CampaignSpecV2,
    plan: ResolvedExecutionPlan,
) -> EpisodeReceiptExecutionFacts:
    """Project the plan onto a v0.2 episode receipt."""
    return EpisodeReceiptExecutionFacts(
        execution_plan_digest=bound_execution_plan_digest(campaign, plan),
        execution_location=_execution_location(plan),
    )


def uplift_report_execution_facts(
    campaign: CampaignSpecV2,
    plan: ResolvedExecutionPlan,
) -> UpliftReportExecutionFacts:
    """Project the plan onto a v0.2 uplift report."""
    return UpliftReportExecutionFacts(
        execution_plan_digest=bound_execution_plan_digest(campaign, plan),
        execution_location=_execution_location(plan),
    )


def climb_summary_execution_facts(
    campaign: CampaignSpecV2,
    plan: ResolvedExecutionPlan,
) -> ClimbSummaryExecutionFacts:
    """Project the plan onto a v0.2 climb summary."""
    bound_execution_plan_digest(campaign, plan)
    return ClimbSummaryExecutionFacts(
        subject_harness=plan.subject.harness_id,
        subject_harness_version=plan.subject.harness_version,
        execution_backend_kind=plan.execution.kind,
    )


def compatibility_result_execution_facts(
    campaign: CampaignSpecV2,
    plan: ResolvedExecutionPlan,
) -> CompatibilityResultExecutionFacts:
    """Project the plan onto a v0.2 compatibility result."""
    return CompatibilityResultExecutionFacts(
        execution_plan_digest=bound_execution_plan_digest(campaign, plan),
        evaluation_engine_source_commit=plan.evaluation.source_commit,
        evaluation_engine_wheel_digest=plan.evaluation.wheel_digest,
        execution_backend_kind=plan.execution.kind,
        execution_backend_supported=(
            plan.execution.kind in SUPPORTED_EXECUTION_BACKEND_KINDS
        ),
        subject_backend_kind=plan.subject.kind,
        subject_backend_supported=plan.subject.kind in SUPPORTED_SUBJECT_BACKEND_KINDS,
    )


def release_core_subject_hermes_version(
    campaign: CampaignSpecV2,
    plan: ResolvedExecutionPlan,
) -> str:
    """Return the subject harness version a v0.2 ReleaseCore states.

    ``ReleaseCore.subject_hermes_version`` is read out of the tree being
    released rather than decided by the founder, and today it is read from the
    introductory Campaign's ``agents.subject.harness.version``
    (:mod:`techtree.release.generate`). A v0.2 Campaign does not carry that
    field, so the coordinate comes from the subject plane of the plan the
    Campaign binds — the same fact, from the document that now owns it.

    This is the projection, not the change of producer. Generation reads the
    packaged catalog, and the packaged catalog stays on the v0.1 Campaign until
    a v0.2 release identity exists; ``techtree-di5`` is where the producer
    starts calling this.
    """
    bound_execution_plan_digest(campaign, plan)
    return plan.subject.harness_version
