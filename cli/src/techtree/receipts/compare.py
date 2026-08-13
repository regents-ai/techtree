"""Proving the two variants were one experiment. Spec section 7.9.

:mod:`techtree.manifests.compare` proves that the two documents a run was
prepared from differ only where the Campaign permits. That is a claim about
*intentions*. This module makes the harder claim: that the two executions the
run actually performed differ only there too.

The difference matters because everything between a manifest and a container
can drift. A provider can route a model identifier somewhere else, a harness can
resolve a different version, a daemon can hand back a different image, a
configuration can pick up a sampling parameter nobody declared. None of that is
visible in a manifest, and all of it would be reported as uplift.

So the comparison runs over three sources at once:

*What was declared* — the two ``ExperimentManifest`` documents and the Campaign
they were derived from, checked field by field and then diffed whole.

*What was observed* — one fingerprint per variant, computed by
:mod:`techtree.receipts.observed` from the traces the runtime wrote and the
configuration the engine resolved, checked against the manifest that variant was
supposed to be and against the other variant's fingerprint.

*What was joined* — one receipt per committed task on each side, paired by task
hash in the order the TasksetLock fixes, so the aggregation downstream cannot
pair by arrival order or quietly drop a task.

Four decisions are worth stating.

*The whole tool surface cannot be required to match, and here is exactly what
may not.* Mounting a Skill changes what the subject is offered, because Hermes
0.19.0 renders the index of visible Skills into the description of its own
Skill-management tool. Across two recorded probes of the same Campaign the
fifteen tool names, fifteen parameter schemas and fourteen of the fifteen
descriptions are byte-identical, and ``skill_manage``'s description differs. A
check that required one tool-inventory digest would therefore reject every
clean run. What is permitted is the exact derived difference decisions document
0007 ratified: the tool names and parameter schemas of the pinned harness
conformance fixture (:mod:`techtree.harness`), unchanged on both sides, with at
most one differing description and only on :data:`SKILL_INDEX_TOOL`. A second
differing description, a differing schema, a differing description anywhere
else, or any departure from the fixture's own surface is a violation — the
fixture is what stops a moved harness pin from being read as the Skill index
doing what the Skill index does.

*A weaker claim is a warning, never silence and never a failure.* One thing
about a real run is honestly unverifiable here: a provider that publishes no
model revision cannot be pinned to one. It is recorded as a warning, which is
what
:class:`~techtree.models.uplift_report.ComparisonStatus.CONTROLLED_WITH_WARNINGS`
exists for, and it is never allowed to absorb an actual mismatch: a model that
differs is a failure whether or not its revision was discoverable. What ran in
the container used to be a warning of the same kind and is a check now — see
:func:`_runtime_pin_checks`.

*This function reports; it does not refuse.* Like
:func:`~techtree.manifests.compare.compare_manifests`, it returns what it found
so that an operator can read every check. Turning an invalid comparison into a
refusal is :mod:`techtree.receipts.uplift`'s job, at the point where a report
would otherwise be written.

*The observed inputs are richer than section 7.9's signature.* The specification
sketches ``compare_real_variants`` as taking receipts alone. A frozen
``EpisodeReceipt`` carries rewards and lineage and no configuration at all, so
the observed side is passed explicitly as :class:`ObservedVariant`, built by
:func:`observe_variant` from the same evidence the receipts were built from.
The schedule is passed for the same reason: which schedule ran, and how far
apart the two children were, is a fact about the execution rather than about
either variant.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal, Self

from pydantic import Field, model_validator

from techtree.canonical import digest_object, validate_digest
from techtree.harness import harness_conformance
from techtree.manifests.compare import compare_manifests
from techtree.models.base import Digest, JsonValue, NonEmptyString, ProtocolModel
from techtree.models.campaign import (
    SUBJECT_AGENT,
    AgentSpec,
    CampaignSpec,
    MutationKind,
    RuntimeSpec,
    VariantSchedule,
)
from techtree.models.episode_receipt import EpisodeReceipt
from techtree.models.experiment import (
    ExperimentManifest,
    ExperimentVariant,
    ManifestComparison,
)
from techtree.models.uplift_report import ComparisonStatus
from techtree.models.validation import TasksetLock
from techtree.receipts.observed import (
    ObservedSubjectConfiguration,
    observed_from_episodes,
)
from techtree.tasksets.membership import membership_digest
from techtree.verifiers.models import (
    ChildProcessOutcome,
    NormalizedTool,
    VariantExecutionResult,
)

__all__ = [
    "COMPARISON_INVALID",
    "SKILL_INDEX_TOOL",
    "ComparisonCheck",
    "ObservedVariant",
    "PairedReceiptRow",
    "RealComparisonResult",
    "ScheduleObservation",
    "compare_real_variants",
    "observe_variant",
]

#: Stable error code. Spec section 15. Raised by whoever turns an invalid
#: comparison into a refusal, never by this module.
COMPARISON_INVALID: Final = "comparison_invalid"

#: The one tool whose *description* two controlled variants may disagree about.
#:
#: Hermes 0.19.0 lists the Skills currently visible to the subject inside this
#: tool's description, so inserting or replacing a Skill necessarily changes it.
#: It is a consequence of the mutation rather than a second difference, and it
#: was measured on the recorded probes rather than assumed: see
#: ``tests/fixtures/receipts/support.py`` and
#: ``test_inserting_a_skill_changes_exactly_one_tool_description``.
SKILL_INDEX_TOOL: Final = "skill_manage"

_PASSED: Final = "passed"
_FAILED: Final = "failed"
_WARNING: Final = "warning"


class ComparisonCheck(ProtocolModel):
    """One named question about a comparison, and its answer.

    The same shape as
    :class:`~techtree.models.validation.ValidationCheck` and
    :class:`~techtree.verifiers.models.ExecutionCheck`, and for the same
    reason: a reader wants an ordered list of named verdicts, not an exception
    that stops at whichever rule happened to fail first.
    """

    id: NonEmptyString
    status: Literal["passed", "failed", "warning"]
    detail: NonEmptyString


class ScheduleObservation(ProtocolModel):
    """How the two variants were placed in time. Spec section 7.9.

    Operational metadata, deliberately kept apart from the scientific checks: a
    wide launch skew does not invalidate a comparison, it just means the two
    sides saw the provider at more distant moments, and a reader deciding how
    much that matters needs the number rather than a verdict about it.
    """

    schedule: VariantSchedule
    start_skew_seconds: float = Field(ge=0.0)
    completion_window_seconds: float = Field(ge=0.0)
    overlapped: bool


class PairedReceiptRow(ProtocolModel):
    """One committed task, and the two receipts that scored it."""

    position: int = Field(ge=0)
    task_hash: Digest
    baseline_receipt_id: NonEmptyString
    baseline_receipt_digest: Digest
    candidate_receipt_id: NonEmptyString
    candidate_receipt_digest: Digest


class RealComparisonResult(ProtocolModel):
    """Whether the two executions were one experiment, and how it was checked.

    A local object, versioned by the run directory it lives in rather than by
    the protocol: the frozen v0.1 schema has no controlled-comparison document,
    and inventing one here would be a protocol amendment nobody ratified.
    """

    status: ComparisonStatus
    mutation_kind: MutationKind
    manifest_comparison: ManifestComparison
    ordered_task_hashes: list[Digest]
    rows: list[PairedReceiptRow]
    checks: list[ComparisonCheck]
    schedule: ScheduleObservation
    baseline_observed: ObservedSubjectConfiguration
    candidate_observed: ObservedSubjectConfiguration

    @property
    def failures(self) -> list[ComparisonCheck]:
        """Return every check that found a scientific invariant broken."""
        return [check for check in self.checks if check.status == _FAILED]

    @property
    def warnings(self) -> list[ComparisonCheck]:
        """Return every check that found a weaker claim than it wanted."""
        return [check for check in self.checks if check.status == _WARNING]

    @property
    def controlled(self) -> bool:
        """Whether this comparison may carry a scientific result."""
        return self.status in (
            ComparisonStatus.CONTROLLED,
            ComparisonStatus.CONTROLLED_WITH_WARNINGS,
        )

    @model_validator(mode="after")
    def _check_the_status_is_the_one_the_checks_support(self) -> Self:
        """Reject a result whose headline disagrees with its own checks."""
        expected = _status_for(self.checks)
        if self.status is not expected:
            raise ValueError(
                f"a comparison whose checks are {expected.value} cannot report "
                f"{self.status.value}"
            )
        if self.status is not ComparisonStatus.INVALID and not self.rows:
            raise ValueError("a controlled comparison pairs at least one task")
        return self


@dataclass(frozen=True)
class ObservedVariant:
    """Everything about one variant that was measured rather than declared.

    :class:`~techtree.receipts.observed.ObservedSubjectConfiguration` is the
    fingerprint, and it commits the tool inventory to a single digest. A
    controlled comparison has to look inside that digest — one tool description
    is allowed to differ — so the tools travel beside it, together with the
    effective sampling table the fingerprint also summarizes, the tasks this
    variant actually scored, and the operational envelope its child recorded.
    """

    variant: ExperimentVariant
    configuration: ObservedSubjectConfiguration
    tools: list[NormalizedTool]
    sampling: dict[str, JsonValue]
    ordered_task_hashes: list[Digest]
    episode_count: int
    child_outcome: ChildProcessOutcome


def observe_variant(
    *,
    result: VariantExecutionResult,
    resolved_config: Mapping[str, Any],
    runtime: RuntimeSpec,
) -> ObservedVariant:
    """Fingerprint one executed variant from its own evidence.

    Raises whatever :func:`~techtree.receipts.observed.observed_from_episodes`
    raises: a variant whose own rollouts disagree about what they ran has no
    single observed configuration, and there is nothing to compare.
    """
    configuration = observed_from_episodes(
        result.episodes,
        resolved_config=resolved_config,
        image_resolution=result.image_resolution,
        runtime=runtime,
    )
    # The same reference rollout the fingerprint was taken from, chosen the
    # same way: every rollout of one variant has already been required to agree
    # with every other, so the first one describes all of them.
    reference = next(trace for episode in result.episodes for trace in episode.traces)
    return ObservedVariant(
        variant=ExperimentVariant(result.variant.value),
        configuration=configuration,
        tools=sorted(reference.tools, key=lambda tool: tool.name),
        sampling=dict(reference.sampling),
        ordered_task_hashes=[
            validate_digest(episode.task_hash) for episode in result.episodes
        ],
        episode_count=len(result.episodes),
        child_outcome=result.child_outcome,
    )


def compare_real_variants(
    *,
    campaign: CampaignSpec,
    baseline_manifest: ExperimentManifest,
    candidate_manifest: ExperimentManifest,
    prepared_manifest_comparison: ManifestComparison,
    baseline_receipts: Sequence[EpisodeReceipt],
    candidate_receipts: Sequence[EpisodeReceipt],
    taskset_lock: TasksetLock,
    baseline_observed: ObservedVariant,
    candidate_observed: ObservedVariant,
    schedule: VariantSchedule,
) -> RealComparisonResult:
    """Verify declared and observed control and return the paired rows."""
    committed = [validate_digest(value) for value in taskset_lock.ordered_task_hashes]
    recomputed = compare_manifests(
        baseline_manifest, candidate_manifest, campaign.mutation_contract
    )

    checks: list[ComparisonCheck] = [
        *_declared_checks(
            campaign=campaign,
            baseline=baseline_manifest,
            candidate=candidate_manifest,
            prepared=prepared_manifest_comparison,
            recomputed=recomputed,
            taskset_lock=taskset_lock,
        ),
        *_observed_checks(
            campaign=campaign,
            baseline_manifest=baseline_manifest,
            candidate_manifest=candidate_manifest,
            baseline=baseline_observed,
            candidate=candidate_observed,
            committed=committed,
        ),
    ]
    rows, pairing = _pair_receipts(
        baseline_receipts=baseline_receipts,
        candidate_receipts=candidate_receipts,
        committed=committed,
    )
    checks.append(pairing)

    observation = _observe_schedule(
        schedule=schedule,
        baseline=baseline_observed.child_outcome,
        candidate=candidate_observed.child_outcome,
    )
    checks.append(
        _check(
            "schedule_recorded",
            _PASSED,
            f"the variants ran under {schedule.value}, launched "
            f"{observation.start_skew_seconds:.3f}s apart and completed within "
            f"{observation.completion_window_seconds:.3f}s",
        )
    )

    status = _status_for(checks)
    return RealComparisonResult(
        status=status,
        mutation_kind=campaign.mutation_contract.kind,
        manifest_comparison=recomputed,
        ordered_task_hashes=committed,
        rows=[] if status is ComparisonStatus.INVALID else rows,
        checks=checks,
        schedule=observation,
        baseline_observed=baseline_observed.configuration,
        candidate_observed=candidate_observed.configuration,
    )


# ---------------------------------------------------------------------------
# What the two documents declared
# ---------------------------------------------------------------------------


def _declared_checks(
    *,
    campaign: CampaignSpec,
    baseline: ExperimentManifest,
    candidate: ExperimentManifest,
    prepared: ManifestComparison,
    recomputed: ManifestComparison,
    taskset_lock: TasksetLock,
) -> list[ComparisonCheck]:
    """Check every field spec section 7.9 requires the two variants to share.

    The whole-configuration diff below already covers most of these, and they
    are stated separately anyway. A diff can say that two documents disagree at
    a pointer; it cannot say which disagreement was structurally impossible,
    and an operator reading a failed comparison wants to be told "the two sides
    name a different model", not "``/agents/subject/model/model_id``".
    """
    left = baseline.configuration
    right = candidate.configuration
    subject_left = _subject(baseline)
    subject_right = _subject(candidate)

    checks = [
        _same(
            "declared_campaign",
            "Campaign",
            baseline.campaign_spec_digest,
            candidate.campaign_spec_digest,
        ),
        _same(
            "declared_data_policy",
            "DataPolicy",
            left.data_policy_digest,
            right.data_policy_digest,
        ),
        _same(
            "declared_program_and_context",
            "improvement program or public context",
            (baseline.program_ref, baseline.public_context),
            (candidate.program_ref, candidate.public_context),
        ),
        _same(
            "declared_outcome_contract",
            "OutcomeContract",
            left.outcome_contract_digest,
            right.outcome_contract_digest,
        ),
        _same(
            "declared_evaluation_backend",
            "evaluation backend",
            left.evaluation_backend,
            right.evaluation_backend,
        ),
        _same(
            "declared_environment", "environment", left.environment, right.environment
        ),
        _same(
            "declared_model", "subject model", subject_left.model, subject_right.model
        ),
        _same(
            "declared_sampling",
            "sampling",
            subject_left.sampling,
            subject_right.sampling,
        ),
        _same(
            "declared_harness",
            "harness identity, version or bundled-Skill setting",
            _harness_identity(subject_left),
            _harness_identity(subject_right),
        ),
        _same(
            "declared_runtime",
            "subject runtime or image",
            subject_left.runtime,
            subject_right.runtime,
        ),
        _same(
            "declared_execution_contract",
            "execution, scoring, evidence or budget contract",
            (left.execution, left.scoring, left.evidence, left.budgets),
            (right.execution, right.scoring, right.evidence, right.budgets),
        ),
        *_taskset_checks(campaign, baseline, candidate, taskset_lock),
        *_manifest_comparison_checks(prepared, recomputed),
        _mutation_check(campaign, subject_left, subject_right),
    ]
    return checks


def _taskset_checks(
    campaign: CampaignSpec,
    baseline: ExperimentManifest,
    candidate: ExperimentManifest,
    lock: TasksetLock,
) -> list[ComparisonCheck]:
    """Require one taskset, one committed membership, and one lock over it."""
    committed = list(campaign.taskset.membership.ordered_task_hashes)
    agreeing = (
        baseline.configuration.taskset == campaign.taskset
        and candidate.configuration.taskset == campaign.taskset
    )
    locked = (
        list(lock.ordered_task_hashes) == committed
        and lock.membership_digest == campaign.taskset.membership.membership_digest
        and lock.membership_digest == membership_digest(committed)
        and lock.taskset_ref == campaign.taskset.ref
        and lock.task_count == len(committed)
    )
    return [
        _check(
            "declared_taskset",
            _PASSED if agreeing else _FAILED,
            (
                "both variants commit to the Campaign's taskset and membership"
                if agreeing
                else "a variant commits to a different taskset or membership "
                "than the Campaign"
            ),
        ),
        _check(
            "declared_taskset_lock",
            _PASSED if locked else _FAILED,
            (
                f"the lock pins the {len(committed)} tasks the Campaign commits to"
                if locked
                else "the taskset lock does not pin the tasks, the membership "
                "digest or the taskset the Campaign commits to"
            ),
        ),
    ]


def _manifest_comparison_checks(
    prepared: ManifestComparison, recomputed: ManifestComparison
) -> list[ComparisonCheck]:
    """Require the recomputed diff to be controlled and to be the prepared one."""
    return [
        _check(
            "declared_only_skill_differs",
            _PASSED if recomputed.controlled else _FAILED,
            (
                "the candidate configuration differs from the baseline only "
                "where the mutation contract permits"
                if recomputed.controlled
                else "; ".join(recomputed.violations)
            ),
        ),
        _check(
            "declared_comparison_unchanged",
            _PASSED if recomputed == prepared else _FAILED,
            (
                "the comparison recomputed from the executed manifests is the "
                "one the run was prepared with"
                if recomputed == prepared
                else "the executed manifests do not produce the comparison this "
                "run was prepared with"
            ),
        ),
    ]


def _mutation_check(
    campaign: CampaignSpec, baseline: AgentSpec, candidate: AgentSpec
) -> ComparisonCheck:
    """Hold the declared skill lists to the shape the mutation kind requires."""
    kind = campaign.mutation_contract.kind
    left = [reference.digest for reference in baseline.harness.skills]
    right = [reference.digest for reference in candidate.harness.skills]

    if kind is MutationKind.SKILL_INSERTION:
        ok = not left and len(right) == 1
        detail = (
            "the baseline declares no Skill and the candidate declares one"
            if ok
            else f"a skill_insertion declares 0 then 1 Skill; got {len(left)} "
            f"then {len(right)}"
        )
    else:
        ok = len(left) == 1 and len(right) == 1 and left != right
        detail = (
            "the baseline and the candidate each declare one Skill, and they "
            "are different Skills"
            if ok
            else "a skill_replacement declares one differing Skill on each side"
        )
    return _check(f"declared_mutation_{kind.value}", _PASSED if ok else _FAILED, detail)


# ---------------------------------------------------------------------------
# What the two executions did
# ---------------------------------------------------------------------------


def _observed_checks(
    *,
    campaign: CampaignSpec,
    baseline_manifest: ExperimentManifest,
    candidate_manifest: ExperimentManifest,
    baseline: ObservedVariant,
    candidate: ObservedVariant,
    committed: Sequence[Digest],
) -> list[ComparisonCheck]:
    """Check what actually ran, against the other side and against the manifest."""
    left = baseline.configuration
    right = candidate.configuration

    return [
        _check(
            "observed_task_order",
            (
                _PASSED
                if baseline.ordered_task_hashes
                == candidate.ordered_task_hashes
                == list(committed)
                else _FAILED
            ),
            (
                "both variants scored the committed tasks in committed order"
                if baseline.ordered_task_hashes
                == candidate.ordered_task_hashes
                == list(committed)
                else "a variant scored a different set of tasks, or scored them "
                "in an order the Campaign did not commit to"
            ),
        ),
        _check(
            "observed_episode_count",
            (
                _PASSED
                if baseline.episode_count == candidate.episode_count == len(committed)
                else _FAILED
            ),
            (
                f"both variants recorded {len(committed)} episodes"
                if baseline.episode_count == candidate.episode_count == len(committed)
                else f"the variants recorded {baseline.episode_count} and "
                f"{candidate.episode_count} episodes for {len(committed)} tasks"
            ),
        ),
        _same("observed_model", "model", left.model_id, right.model_id),
        _same(
            "observed_sampling",
            "effective sampling",
            left.sampling_digest,
            right.sampling_digest,
        ),
        _same(
            "observed_harness",
            "harness",
            (left.harness_id, left.harness_version),
            (right.harness_id, right.harness_version),
        ),
        _same(
            "observed_bundled_skill",
            "bundled-Skill setting",
            left.use_bundled_skill,
            right.use_bundled_skill,
        ),
        _same(
            "observed_runtime_image",
            "subject runtime or image",
            (left.runtime_kind, left.runtime_image, left.runtime_image_index_digest),
            (right.runtime_kind, right.runtime_image, right.runtime_image_index_digest),
        ),
        _same(
            "observed_runtime_platform_digest",
            "resolved platform-specific image digest",
            (left.runtime_platform, left.runtime_image_platform_digest),
            (right.runtime_platform, right.runtime_image_platform_digest),
        ),
        *_runtime_pin_checks(campaign, baseline, candidate),
        _tool_surface_check(baseline, candidate),
        _same(
            "observed_reward_contract",
            "reward names or weights",
            left.reward_contract_digest,
            right.reward_contract_digest,
        ),
        _same(
            "observed_verifiers_build",
            "Verifiers build",
            (left.verifiers_version, left.verifiers_revision),
            (right.verifiers_version, right.verifiers_revision),
        ),
        _declared_to_observed(baseline_manifest, baseline),
        _declared_to_observed(candidate_manifest, candidate),
        *_weaker_claim_warnings(campaign),
    ]


def _tool_surface_check(
    baseline: ObservedVariant, candidate: ObservedVariant
) -> ComparisonCheck:
    """Permit the Skill index delta and nothing else. See :data:`SKILL_INDEX_TOOL`."""
    left = {tool.name: tool for tool in baseline.tools}
    right = {tool.name: tool for tool in candidate.tools}

    departure = _conformance_departure(baseline, candidate)
    if departure is not None:
        return _check("observed_tool_inventory", _FAILED, departure)

    if set(left) != set(right):
        added = sorted(set(right) - set(left))
        removed = sorted(set(left) - set(right))
        return _check(
            "observed_tool_inventory",
            _FAILED,
            "the two variants were offered different tools "
            f"(added {added or 'nothing'}, removed {removed or 'nothing'})",
        )

    schemas = sorted(
        name
        for name in left
        if left[name].parameters_digest != right[name].parameters_digest
    )
    if schemas:
        return _check(
            "observed_tool_inventory",
            _FAILED,
            f"the parameter schema of {', '.join(schemas)} differs between the "
            "two variants",
        )

    descriptions = sorted(
        name
        for name in left
        if left[name].description_digest != right[name].description_digest
    )
    if not descriptions:
        return _check(
            "observed_tool_inventory",
            _PASSED,
            f"both variants were offered the same {len(left)} tools, described "
            "identically",
        )
    if descriptions == [SKILL_INDEX_TOOL]:
        return _check(
            "observed_tool_inventory",
            _PASSED,
            f"both variants were offered the same {len(left)} tools with the "
            f"same schemas; only {SKILL_INDEX_TOOL}'s description differs, "
            "which is where the harness lists the Skills the subject can see",
        )
    return _check(
        "observed_tool_inventory",
        _FAILED,
        f"the description of {', '.join(descriptions)} differs between the two "
        f"variants; only {SKILL_INDEX_TOOL}'s may",
    )


def _conformance_departure(
    baseline: ObservedVariant, candidate: ObservedVariant
) -> str | None:
    """Return why the offered tools are not the pinned harness's, or nothing.

    Decisions document 0007 R9 item 4. A comparison sees one description
    differing on one tool and cannot tell, from inside itself, whether that is
    the Skill index doing its job or a harness that changed underneath the
    Campaign. The pinned fixture is the outside evidence: it fixes the tool
    count, the names and the parameter schemas of the harness build the
    Campaign declares, so anything else is a departure and not a derived
    difference.
    """
    for observed in (baseline, candidate):
        configuration = observed.configuration
        try:
            pinned = harness_conformance(
                configuration.harness_id, configuration.harness_version
            )
        except FileNotFoundError:
            return (
                f"no tool surface was ever recorded for "
                f"{configuration.harness_id} {configuration.harness_version}, "
                "so the difference between the two variants cannot be shown to "
                "be the Skill index alone"
            )
        offered = sorted(tool.name for tool in observed.tools)
        if offered != sorted(pinned.tool_names):
            return (
                f"the {observed.variant.value} was offered {len(offered)} tools "
                f"where {configuration.harness_id} "
                f"{configuration.harness_version} offers "
                f"{len(pinned.tool_names)}, so the harness is not the one the "
                "Campaign declares"
            )
        expected = pinned.parameters_by_tool
        reshaped = sorted(
            tool.name
            for tool in observed.tools
            if tool.parameters_digest != expected[tool.name]
        )
        if reshaped:
            return (
                f"the {observed.variant.value} was offered a different "
                f"parameter schema for {', '.join(reshaped)} than "
                f"{configuration.harness_id} {configuration.harness_version} "
                "records"
            )
        if pinned.skill_index_tool != SKILL_INDEX_TOOL:
            return (
                f"{configuration.harness_id} {configuration.harness_version} "
                f"renders its Skill index into {pinned.skill_index_tool}, not "
                f"{SKILL_INDEX_TOOL}"
            )
    return None


def _declared_to_observed(
    manifest: ExperimentManifest, observed: ObservedVariant
) -> ComparisonCheck:
    """Check one variant's execution against the manifest it was supposed to be.

    Spec section 7.8 names this ``compare_declared_to_observed``. It lives here
    because a check that only has meaning inside a controlled comparison should
    be read beside the other checks of that comparison, and because
    ``ComparisonCheck`` is this section's type.
    """
    subject = _subject(manifest)
    configuration = observed.configuration
    declared_sampling: dict[str, JsonValue] = {
        "max_tokens": subject.sampling.max_tokens,
        "temperature": subject.sampling.temperature,
    }
    mismatches = [
        label
        for label, declared, seen in (
            ("model", subject.model.model_id, configuration.model_id),
            ("harness", subject.harness.id, configuration.harness_id),
            ("harness version", subject.harness.version, configuration.harness_version),
            (
                "bundled-Skill setting",
                subject.harness.use_bundled_skill,
                configuration.use_bundled_skill,
            ),
            ("runtime", subject.runtime.type, configuration.runtime_kind),
            ("runtime image", subject.runtime.image, configuration.runtime_image),
            (
                "Skill list",
                [reference.digest for reference in subject.harness.skills],
                list(configuration.skill_root_digests),
            ),
            # Every parameter the engine resolved, and no parameter it did not:
            # an undeclared sampling key is a difference the manifest never
            # authorized, whichever variant picked it up.
            ("sampling", declared_sampling, dict(observed.sampling)),
        )
        if declared != seen
    ]
    variant = observed.variant.value
    return _check(
        f"observed_matches_declared_{variant}",
        _PASSED if not mismatches else _FAILED,
        (
            f"the {variant} executed the subject its manifest declares"
            if not mismatches
            else f"the {variant} executed a different {', '.join(mismatches)} "
            "than its manifest declares"
        ),
    )


def _runtime_pin_checks(
    campaign: CampaignSpec, baseline: ObservedVariant, candidate: ObservedVariant
) -> list[ComparisonCheck]:
    """Hold both executions to the container the Campaign pinned.

    Decisions document 0007 R5. This used to be a warning, because the only
    evidence of what ran was the reference the Campaign had asked for: the
    pinned Verifiers build records no resolved digest, so "the image is the one
    we asked for" was the strongest true statement available. It is a check now
    because the Campaign pins a manifest digest per platform and every run asks
    the local daemon what it holds, so the claim has evidence under it. An
    execution that cannot be tied to the pin is invalid rather than warned
    about — a container nobody can name is not a weaker result.
    """
    runtime = campaign.subject.runtime
    pinned = runtime.image_index_digest
    matched = sorted(
        observed.variant.value
        for observed in (baseline, candidate)
        if observed.configuration.runtime_image_index_digest == pinned
    )
    both = len(matched) == 2

    platforms = sorted(
        {observed.configuration.runtime_platform for observed in (baseline, candidate)}
    )
    pinned_platform = len(platforms) == 1 and platforms[0] in (
        runtime.image_platform_digests
    )
    return [
        _check(
            "observed_runtime_image_pinned",
            _PASSED if both else _FAILED,
            (
                "the daemon confirmed both variants ran the image content the "
                "Campaign pinned"
                if both
                else "the container the daemon holds is not the one the Campaign pinned"
            ),
        ),
        _check(
            "observed_runtime_platform_pinned",
            _PASSED if pinned_platform else _FAILED,
            (
                f"both variants were served on {platforms[0]}, a platform the "
                "Campaign pins a manifest digest for"
                if pinned_platform
                else "the variants were served on platforms the Campaign does "
                "not pin one manifest digest for"
            ),
        ),
    ]


def _weaker_claim_warnings(campaign: CampaignSpec) -> list[ComparisonCheck]:
    """Record the one fact about a real run that cannot be independently pinned.

    It is not a scientific failure and it may not be left unsaid. Presenting
    "both variants named the same model" as "both variants ran the same model
    build" would be making the stronger claim from the weaker evidence, which is
    the whole thing a controlled comparison exists to stop. Decisions document
    0007 R5 accepts it for v0.1 and forbids suppressing it to obtain the word
    "controlled".
    """
    if campaign.subject.model.revision is not None:
        return []
    return [
        _check(
            "model_revision_discoverable",
            _WARNING,
            f"the provider publishes no revision for "
            f"{campaign.subject.model.model_id}, so both variants are known "
            "to have used the same model identifier and not the same "
            "model build",
        )
    ]


# ---------------------------------------------------------------------------
# The join
# ---------------------------------------------------------------------------


def _pair_receipts(
    *,
    baseline_receipts: Sequence[EpisodeReceipt],
    candidate_receipts: Sequence[EpisodeReceipt],
    committed: Sequence[Digest],
) -> tuple[list[PairedReceiptRow], ComparisonCheck]:
    """Join the two sides task by task, in committed order.

    A missing task and a duplicated task are both reported rather than raised,
    because they are findings about the comparison and belong in its list of
    checks beside every other finding.
    """
    left, left_faults = _by_task(baseline_receipts, committed, "baseline")
    right, right_faults = _by_task(candidate_receipts, committed, "candidate")
    faults = [*left_faults, *right_faults]
    if faults:
        return [], _check("paired_task_rewards", _FAILED, "; ".join(faults))

    rows = [
        PairedReceiptRow(
            position=position,
            task_hash=task_hash,
            baseline_receipt_id=left[task_hash].id,
            baseline_receipt_digest=digest_object(left[task_hash]),
            candidate_receipt_id=right[task_hash].id,
            candidate_receipt_digest=digest_object(right[task_hash]),
        )
        for position, task_hash in enumerate(committed)
    ]
    return rows, _check(
        "paired_task_rewards",
        _PASSED,
        f"every one of the {len(rows)} committed tasks is scored exactly once "
        "on each side",
    )


def _by_task(
    receipts: Sequence[EpisodeReceipt],
    committed: Sequence[Digest],
    label: str,
) -> tuple[dict[Digest, EpisodeReceipt], list[str]]:
    """Index one side's receipts by task and report what does not line up."""
    by_task: dict[Digest, EpisodeReceipt] = {}
    faults: list[str] = []
    for receipt in receipts:
        if receipt.task_hash in by_task:
            faults.append(f"the {label} scored {receipt.task_hash} twice")
            continue
        by_task[receipt.task_hash] = receipt

    missing = [value for value in committed if value not in by_task]
    unexpected = sorted(set(by_task) - set(committed))
    if missing:
        faults.append(f"the {label} did not score {len(missing)} committed task(s)")
    if unexpected:
        faults.append(
            f"the {label} scored {len(unexpected)} task(s) the Campaign does "
            "not commit to"
        )
    return by_task, faults


# ---------------------------------------------------------------------------
# Placement in time
# ---------------------------------------------------------------------------


def _observe_schedule(
    *,
    schedule: VariantSchedule,
    baseline: ChildProcessOutcome,
    candidate: ChildProcessOutcome,
) -> ScheduleObservation:
    """Record how far apart the two children started and finished."""
    started = (baseline.started_at, candidate.started_at)
    finished = (baseline.finished_at, candidate.finished_at)
    return ScheduleObservation(
        schedule=schedule,
        start_skew_seconds=abs((started[1] - started[0]).total_seconds()),
        completion_window_seconds=(max(finished) - min(started)).total_seconds(),
        overlapped=max(started) < min(finished),
    )


# ---------------------------------------------------------------------------
# Small shared pieces
# ---------------------------------------------------------------------------


def _status_for(checks: Sequence[ComparisonCheck]) -> ComparisonStatus:
    """Return the one status a list of checks supports. Spec section 7.9."""
    if any(check.status == _FAILED for check in checks):
        return ComparisonStatus.INVALID
    if any(check.status == _WARNING for check in checks):
        return ComparisonStatus.CONTROLLED_WITH_WARNINGS
    return ComparisonStatus.CONTROLLED


def _check(identifier: str, status: str, detail: str) -> ComparisonCheck:
    """Build one check, validated as the model it is."""
    return ComparisonCheck.model_validate(
        {"id": identifier, "status": status, "detail": detail}
    )


def _same(identifier: str, label: str, left: object, right: object) -> ComparisonCheck:
    """Report whether two sides agree, without printing what they hold.

    The values themselves are deliberately not in the detail. A model
    identifier is harmless, a resolved configuration is not, and one rule for
    all of them is the rule that cannot leak.
    """
    agree = left == right
    return _check(
        identifier,
        _PASSED if agree else _FAILED,
        (
            f"the baseline and the candidate share one {label}"
            if agree
            else f"the baseline and the candidate do not share one {label}"
        ),
    )


def _subject(manifest: ExperimentManifest) -> AgentSpec:
    """Return the manifest's subject agent, which its own validator requires."""
    subject = manifest.configuration.agents.get(SUBJECT_AGENT)
    if subject is None:  # pragma: no cover - the model refuses to be built without one
        raise ValueError("an experiment configuration defines a subject agent")
    return subject


def _harness_identity(subject: AgentSpec) -> tuple[str, str, bool]:
    """Return the part of a harness two variants must share.

    Not the skill list: that is the one field the mutation contract permits to
    differ, and comparing it here would fail every correct comparison.
    """
    return (
        subject.harness.id,
        subject.harness.version,
        subject.harness.use_bundled_skill,
    )
