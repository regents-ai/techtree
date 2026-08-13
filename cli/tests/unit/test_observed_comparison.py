"""The controlled-comparison verifier. Spec section 7.9.

Every case here starts from the two paid probes of 2026-08-13 — a real
``exact_match`` 0/2 against 2/2, on the same Campaign, the same subject model,
the same pinned engine and the same image — and then breaks exactly one thing.
That is the whole design of this file: a comparison verifier is only worth
having if it rejects each unauthorized difference *on its own*, so each test
changes one field and names the check that must catch it.

Two constructions are synthesized rather than recorded, and both are marked
where they appear.

*The replacement pair.* Both probes were a Skill insertion, so no recorded
evidence exists of one Skill measured against another. The declared side of a
replacement is built through the same Campaign and manifest builders as any
other, and the observed side restates the mounted Skill digests on the recorded
candidate's own fingerprint.

*A few single-field faults.* Where breaking a field through the recorded
evidence would mean rewriting an episode file, the fingerprint is edited
instead. The extraction of a fingerprint from evidence is
``test_observed_configuration.py``'s subject; what is under test here is what
the comparison does with two of them.
"""

from __future__ import annotations

import dataclasses
from typing import Final

import pytest

from fixtures.receipts.pair import RecordedPair, recorded_pair, trimmed_campaign
from techtree.canonical import digest_object
from techtree.models.base import ArtifactRef
from techtree.models.campaign import (
    SUBJECT_AGENT,
    AgentSpec,
    CampaignSpec,
    HarnessSpec,
    ModelSpec,
    MutationContract,
    MutationKind,
    VariantSchedule,
)
from techtree.models.episode_receipt import EpisodeReceipt
from techtree.models.uplift_report import ComparisonStatus
from techtree.receipts.compare import (
    SKILL_INDEX_TOOL,
    ObservedVariant,
    RealComparisonResult,
    compare_real_variants,
    observe_variant,
)
from techtree.verifiers.models import (
    NormalizedTool,
    VariantExecutionResult,
    VariantName,
)

#: A digest that is a digest and nothing else, for a Skill no probe ran.
_OTHER_SKILL: Final = digest_object({"fixture": "some other skill tree"})


@pytest.fixture(scope="module")
def pair() -> RecordedPair:
    """Return the recorded comparison, loaded once for the whole module."""
    return recorded_pair()


# ---------------------------------------------------------------------------
# Running the comparison
# ---------------------------------------------------------------------------


def compare(
    pair: RecordedPair,
    *,
    campaign: CampaignSpec | None = None,
    baseline_manifest: object | None = None,
    candidate_manifest: object | None = None,
    prepared: object | None = None,
    baseline_receipts: list[EpisodeReceipt] | None = None,
    candidate_receipts: list[EpisodeReceipt] | None = None,
    taskset_lock: object | None = None,
    baseline_observed: ObservedVariant | None = None,
    candidate_observed: ObservedVariant | None = None,
    schedule: VariantSchedule = VariantSchedule.PARALLEL,
) -> RealComparisonResult:
    """Compare the recorded pair with any one input replaced."""
    return compare_real_variants(
        campaign=campaign or pair.campaign,
        baseline_manifest=baseline_manifest or pair.baseline_manifest,  # type: ignore[arg-type]
        candidate_manifest=candidate_manifest or pair.candidate_manifest,  # type: ignore[arg-type]
        prepared_manifest_comparison=prepared or pair.prepared_comparison,  # type: ignore[arg-type]
        baseline_receipts=(
            pair.receipts(VariantName.BASELINE)
            if baseline_receipts is None
            else baseline_receipts
        ),
        candidate_receipts=(
            pair.receipts(VariantName.CANDIDATE)
            if candidate_receipts is None
            else candidate_receipts
        ),
        taskset_lock=taskset_lock or pair.taskset_lock,  # type: ignore[arg-type]
        baseline_observed=baseline_observed or pair.observed(VariantName.BASELINE),
        candidate_observed=candidate_observed or pair.observed(VariantName.CANDIDATE),
        schedule=schedule,
    )


def failed_checks(result: RealComparisonResult) -> list[str]:
    """Return the identifiers of every check that failed."""
    return [check.id for check in result.failures]


def with_configuration(observed: ObservedVariant, **changes: object) -> ObservedVariant:
    """Return one side's observation with fields of its fingerprint replaced."""
    return dataclasses.replace(
        observed, configuration=observed.configuration.model_copy(update=changes)
    )


def with_tools(
    observed: ObservedVariant, tools: list[NormalizedTool]
) -> ObservedVariant:
    """Return one side's observation offering a different tool surface."""
    return dataclasses.replace(observed, tools=sorted(tools, key=lambda t: t.name))


def _sampled_with(
    pair: RecordedPair, variant: VariantName, **changes: float
) -> ObservedVariant:
    """Fingerprint one side as if it had been sampled under other settings.

    Both the rollouts and the resolved configuration are moved together,
    because the fingerprint refuses a variant whose two records of its own
    sampling disagree — which is a different defect from the one under test.
    """
    result = pair.results[variant]
    episodes = [
        episode.model_copy(
            update={
                "traces": [
                    trace.model_copy(update={"sampling": {**trace.sampling, **changes}})
                    for trace in episode.traces
                ]
            }
        )
        for episode in result.episodes
    ]
    resolved = dict(pair.resolved_configs[variant])
    resolved["sampling"] = {**resolved["sampling"], **changes}
    return observe_variant(
        result=result.model_copy(update={"episodes": episodes}),
        resolved_config=resolved,
        runtime=pair.campaign.subject.runtime,
    )


def with_reward_weight(
    result: VariantExecutionResult, weight: float
) -> VariantExecutionResult:
    """Return the recorded evidence with every reward carrying a new weight."""
    episodes = []
    for episode in result.episodes:
        traces = [
            trace.model_copy(
                update={
                    "rewards": [
                        reward.model_copy(update={"weight": weight})
                        for reward in trace.rewards
                    ]
                }
            )
            for trace in episode.traces
        ]
        episodes.append(episode.model_copy(update={"traces": traces}))
    return result.model_copy(update={"episodes": episodes})


# ---------------------------------------------------------------------------
# The controlled cases
# ---------------------------------------------------------------------------


def test_a_recorded_skill_insertion_is_controlled(pair: RecordedPair) -> None:
    """The real thing passes, warnings and all."""
    result = compare(pair)

    assert result.status is ComparisonStatus.CONTROLLED_WITH_WARNINGS
    assert result.controlled
    assert not result.failures
    assert result.mutation_kind is MutationKind.SKILL_INSERTION
    assert [row.task_hash for row in result.rows] == pair.ordered_task_hashes
    assert result.manifest_comparison.controlled


def test_the_one_honest_warning_is_the_only_one(pair: RecordedPair) -> None:
    """Decisions document 0007 R5: the image warning is gone, the revision stays.

    The container is pinned by content per platform now and the daemon is asked
    what it holds, so what ran is a check. What model build answered still is
    not discoverable, and that is said out loud.
    """
    assert [check.id for check in compare(pair).warnings] == [
        "model_revision_discoverable"
    ]


def test_a_pinned_revision_is_simply_controlled() -> None:
    """``controlled`` is reachable: it needs a Campaign that says more."""
    campaign = _with_model_revision(trimmed_campaign(), "2026-08-01")
    pinned = recorded_pair(campaign=campaign)

    result = compare(pinned)

    assert result.status is ComparisonStatus.CONTROLLED
    assert not result.warnings


def test_a_skill_replacement_is_controlled() -> None:
    """One Skill measured against another, which no paid probe recorded.

    The declared pair is built by the ordinary builders from a replacement
    Campaign; the observed pair restates the mounted Skill digests on the
    recorded candidate's own fingerprint, because there is no recorded
    execution of a subject carrying the Skill being replaced.
    """
    replacement = _replacement_pair()
    baseline_observed = with_configuration(
        replacement.observed(VariantName.BASELINE),
        skill_root_digests=[_OTHER_SKILL],
    )

    result = compare(replacement, baseline_observed=baseline_observed)

    assert result.mutation_kind is MutationKind.SKILL_REPLACEMENT
    assert result.controlled, failed_checks(result)


def test_the_schedule_is_recorded_with_its_skew(pair: RecordedPair) -> None:
    """Spec section 7.9's schedule check, including the parallel metadata."""
    result = compare(pair, schedule=VariantSchedule.PARALLEL)

    assert result.schedule.schedule is VariantSchedule.PARALLEL
    assert result.schedule.start_skew_seconds > 0
    assert result.schedule.completion_window_seconds >= (
        result.schedule.start_skew_seconds
    )
    assert "schedule_recorded" in [check.id for check in result.checks]


def test_a_sequential_schedule_is_recorded_as_the_one_that_ran(
    pair: RecordedPair,
) -> None:
    """Which schedule ran is recorded, not judged."""
    result = compare(pair, schedule=VariantSchedule.SEQUENTIAL)

    assert result.schedule.schedule is VariantSchedule.SEQUENTIAL
    assert result.controlled


# ---------------------------------------------------------------------------
# The tool surface
# ---------------------------------------------------------------------------


def test_only_the_skill_index_tool_may_describe_itself_differently(
    pair: RecordedPair,
) -> None:
    """The measured Hermes fact, as a rule rather than a surprise."""
    baseline = pair.observed(VariantName.BASELINE)
    candidate = pair.observed(VariantName.CANDIDATE)
    differing = [
        tool.name
        for tool in candidate.tools
        if tool.description_digest
        != {left.name: left for left in baseline.tools}[tool.name].description_digest
    ]

    assert differing == [SKILL_INDEX_TOOL]
    assert compare(pair).controlled


def test_a_second_differing_description_is_not_permitted(pair: RecordedPair) -> None:
    """One tool's description may change. Two is drift."""
    candidate = pair.observed(VariantName.CANDIDATE)
    edited = with_tools(
        candidate,
        [
            (
                tool.model_copy(update={"description_digest": _OTHER_SKILL})
                if tool.name == "terminal"
                else tool
            )
            for tool in candidate.tools
        ],
    )

    result = compare(pair, candidate_observed=edited)

    assert result.status is ComparisonStatus.INVALID
    assert "observed_tool_inventory" in failed_checks(result)


def test_a_differing_description_on_another_tool_is_not_permitted(
    pair: RecordedPair,
) -> None:
    """The whitelist is a named tool, not a count."""
    baseline = pair.observed(VariantName.BASELINE)
    aligned = with_tools(
        baseline,
        [
            (
                tool.model_copy(
                    update={
                        "description_digest": _skill_index_description(
                            pair.observed(VariantName.CANDIDATE)
                        )
                    }
                )
                if tool.name == SKILL_INDEX_TOOL
                else (
                    tool.model_copy(update={"description_digest": _OTHER_SKILL})
                    if tool.name == "read_file"
                    else tool
                )
            )
            for tool in baseline.tools
        ],
    )

    result = compare(pair, baseline_observed=aligned)

    assert result.status is ComparisonStatus.INVALID
    assert "observed_tool_inventory" in failed_checks(result)


def test_a_differing_parameter_schema_is_not_permitted(pair: RecordedPair) -> None:
    """A description is prompt text; a schema is what the tool can be asked to do."""
    candidate = pair.observed(VariantName.CANDIDATE)
    edited = with_tools(
        candidate,
        [
            (
                tool.model_copy(update={"parameters_digest": _OTHER_SKILL})
                if tool.name == SKILL_INDEX_TOOL
                else tool
            )
            for tool in candidate.tools
        ],
    )

    result = compare(pair, candidate_observed=edited)

    assert result.status is ComparisonStatus.INVALID
    assert "observed_tool_inventory" in failed_checks(result)


def test_an_extra_tool_is_not_permitted(pair: RecordedPair) -> None:
    """A candidate offered a tool the baseline was not is a second difference."""
    candidate = pair.observed(VariantName.CANDIDATE)
    edited = with_tools(
        candidate,
        [
            *candidate.tools,
            NormalizedTool(
                name="deploy_to_production",
                description_digest=_OTHER_SKILL,
                parameters_digest=_OTHER_SKILL,
            ),
        ],
    )

    result = compare(pair, candidate_observed=edited)

    assert result.status is ComparisonStatus.INVALID
    assert "observed_tool_inventory" in failed_checks(result)


# ---------------------------------------------------------------------------
# Everything the two executions had to share
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"model_id": "some-other-model"}, "observed_model"),
        ({"sampling_digest": _OTHER_SKILL}, "observed_sampling"),
        ({"harness_version": "0.20.0"}, "observed_harness"),
        ({"harness_id": "another-agent"}, "observed_harness"),
        ({"use_bundled_skill": True}, "observed_bundled_skill"),
        ({"runtime_image": "python@sha256:" + "0" * 64}, "observed_runtime_image"),
        ({"runtime_image_index_digest": _OTHER_SKILL}, "observed_runtime_image"),
        (
            {"runtime_image_platform_digest": _OTHER_SKILL},
            "observed_runtime_platform_digest",
        ),
        ({"runtime_platform": "linux/amd64"}, "observed_runtime_platform_digest"),
        ({"verifiers_revision": "0" * 40}, "observed_verifiers_build"),
        ({"verifiers_version": "0.4.0"}, "observed_verifiers_build"),
    ],
)
def test_an_unauthorized_observed_difference_is_invalid(
    pair: RecordedPair, changes: dict[str, object], expected: str
) -> None:
    """One field at a time, each caught by the check that owns it."""
    result = compare(
        pair,
        candidate_observed=with_configuration(
            pair.observed(VariantName.CANDIDATE), **changes
        ),
    )

    assert result.status is ComparisonStatus.INVALID
    assert expected in failed_checks(result)
    assert not result.rows


def test_a_different_reward_weight_is_invalid(pair: RecordedPair) -> None:
    """The reward contract is part of what two variants must share.

    Broken in the evidence rather than in the fingerprint: the weight is read
    off the recorded traces, so re-weighting them is what a drifting scorer
    would actually look like.
    """
    reweighted = observe_variant(
        result=with_reward_weight(pair.results[VariantName.CANDIDATE], 2.0),
        resolved_config=pair.resolved_configs[VariantName.CANDIDATE],
        runtime=pair.campaign.subject.runtime,
    )

    result = compare(pair, candidate_observed=reweighted)

    assert result.status is ComparisonStatus.INVALID
    assert "observed_reward_contract" in failed_checks(result)


def test_a_declared_skill_the_subject_never_read_is_invalid(
    pair: RecordedPair,
) -> None:
    """Spec section 7.9: observed Skill digests match each manifest."""
    result = compare(
        pair,
        candidate_observed=with_configuration(
            pair.observed(VariantName.CANDIDATE), skill_root_digests=[_OTHER_SKILL]
        ),
    )

    assert result.status is ComparisonStatus.INVALID
    assert "observed_matches_declared_candidate" in failed_checks(result)


def test_a_baseline_that_mounted_a_skill_is_invalid(pair: RecordedPair) -> None:
    """An insertion's baseline reads no Skill, and it is checked against evidence."""
    result = compare(
        pair,
        baseline_observed=with_configuration(
            pair.observed(VariantName.BASELINE), skill_root_digests=[_OTHER_SKILL]
        ),
    )

    assert result.status is ComparisonStatus.INVALID
    assert "observed_matches_declared_baseline" in failed_checks(result)


def test_a_subject_sampled_differently_than_declared_is_invalid(
    pair: RecordedPair,
) -> None:
    """The effective sampling table is checked against the manifest, key by key."""
    observed = _sampled_with(pair, VariantName.CANDIDATE, temperature=0.7)

    result = compare(pair, candidate_observed=observed)

    assert result.status is ComparisonStatus.INVALID
    assert "observed_matches_declared_candidate" in failed_checks(result)
    assert "observed_sampling" in failed_checks(result)


def test_an_undeclared_sampling_parameter_is_invalid(pair: RecordedPair) -> None:
    """A parameter nobody declared is a difference nobody authorized."""
    observed = _sampled_with(pair, VariantName.BASELINE, top_p=0.9)

    result = compare(pair, baseline_observed=observed)

    assert result.status is ComparisonStatus.INVALID
    assert "observed_matches_declared_baseline" in failed_checks(result)


# ---------------------------------------------------------------------------
# The pairing
# ---------------------------------------------------------------------------


def test_a_missing_task_is_invalid(pair: RecordedPair) -> None:
    """A comparison over the tasks that arrived is not the committed comparison."""
    result = compare(pair, candidate_receipts=pair.receipts(VariantName.CANDIDATE)[:1])

    assert result.status is ComparisonStatus.INVALID
    assert "paired_task_rewards" in failed_checks(result)
    assert result.rows == []


def test_a_duplicated_task_is_invalid(pair: RecordedPair) -> None:
    """Two receipts for one task would let either be the measurement."""
    receipts = pair.receipts(VariantName.BASELINE)
    result = compare(pair, baseline_receipts=[*receipts, receipts[0]])

    assert result.status is ComparisonStatus.INVALID
    assert "paired_task_rewards" in failed_checks(result)


def test_episodes_scored_out_of_committed_order_are_invalid(
    pair: RecordedPair,
) -> None:
    """Order is the Campaign's, not the provider's."""
    candidate = pair.observed(VariantName.CANDIDATE)
    result = compare(
        pair,
        candidate_observed=dataclasses.replace(
            candidate, ordered_task_hashes=list(reversed(candidate.ordered_task_hashes))
        ),
    )

    assert result.status is ComparisonStatus.INVALID
    assert "observed_task_order" in failed_checks(result)


def test_a_variant_with_the_wrong_episode_count_is_invalid(
    pair: RecordedPair,
) -> None:
    """Every committed task is executed on both sides or the pair is not one."""
    candidate = pair.observed(VariantName.CANDIDATE)
    result = compare(
        pair, candidate_observed=dataclasses.replace(candidate, episode_count=1)
    )

    assert result.status is ComparisonStatus.INVALID
    assert "observed_episode_count" in failed_checks(result)


# ---------------------------------------------------------------------------
# What the two documents declared
# ---------------------------------------------------------------------------


def test_a_manifest_from_another_campaign_is_invalid(pair: RecordedPair) -> None:
    """Two variants of two Campaigns are not two variants of one experiment."""
    other = recorded_pair(campaign=_with_model_revision(trimmed_campaign(), "2026-01"))

    result = compare(pair, candidate_manifest=other.candidate_manifest)

    assert result.status is ComparisonStatus.INVALID
    assert "declared_campaign" in failed_checks(result)
    assert "declared_model" in failed_checks(result)


def test_a_lock_over_other_tasks_is_invalid(pair: RecordedPair) -> None:
    """The lock has to pin the tasks the Campaign commits to."""
    lock = pair.taskset_lock
    reordered = lock.model_copy(
        update={"ordered_task_hashes": list(reversed(lock.ordered_task_hashes))}
    )

    result = compare(pair, taskset_lock=reordered)

    assert result.status is ComparisonStatus.INVALID
    assert "declared_taskset_lock" in failed_checks(result)


def test_a_comparison_the_run_was_not_prepared_with_is_invalid(
    pair: RecordedPair,
) -> None:
    """The executed manifests must reproduce the prepared comparison."""
    prepared = pair.prepared_comparison.model_copy(
        update={"baseline_configuration_digest": _OTHER_SKILL}
    )

    result = compare(pair, prepared=prepared)

    assert result.status is ComparisonStatus.INVALID
    assert "declared_comparison_unchanged" in failed_checks(result)


def test_an_insertion_whose_baseline_declares_a_skill_is_invalid(
    pair: RecordedPair,
) -> None:
    """The mutation shape is checked on the loaded documents, again."""
    replacement = _replacement_pair()

    result = compare(
        pair,
        baseline_manifest=replacement.baseline_manifest,
        prepared=replacement.prepared_comparison,
    )

    assert result.status is ComparisonStatus.INVALID
    assert "declared_mutation_skill_insertion" in failed_checks(result)


def test_a_replacement_whose_sides_name_one_skill_is_invalid() -> None:
    """Replacing a Skill with itself measures nothing."""
    recorded_skill = (
        _replacement_pair()
        .candidate_manifest.configuration.agents[SUBJECT_AGENT]
        .harness.skills[0]
    )
    unchanged = _replacement_pair(replaced=recorded_skill)

    result = compare(
        unchanged,
        baseline_observed=with_configuration(
            unchanged.observed(VariantName.BASELINE),
            skill_root_digests=[recorded_skill.digest],
        ),
    )

    assert result.status is ComparisonStatus.INVALID
    assert "declared_only_skill_differs" in failed_checks(result)
    assert "declared_mutation_skill_replacement" in failed_checks(result)


# ---------------------------------------------------------------------------
# Building the replacement pair
# ---------------------------------------------------------------------------


def _replacement_pair(*, replaced: ArtifactRef | None = None) -> RecordedPair:
    """Return a declared ``skill_replacement`` comparison over recorded evidence.

    The Campaign's own baseline carries the Skill being replaced, which is what
    :class:`~techtree.models.campaign.MutationKind.SKILL_REPLACEMENT` means, and
    the candidate carries the Skill the recorded probe actually mounted.
    """
    base = trimmed_campaign()
    subject = base.agents[SUBJECT_AGENT]
    replaced = replaced or ArtifactRef(
        digest=_OTHER_SKILL,
        media_type="application/vnd.techtree.instruction-skill.v1",
        size=1024,
        relative_path=None,
    )
    campaign = CampaignSpec(
        **{
            **dict(base),
            "mutation_contract": MutationContract(
                **{
                    **dict(base.mutation_contract),
                    "kind": MutationKind.SKILL_REPLACEMENT,
                }
            ),
            "agents": {
                SUBJECT_AGENT: AgentSpec(
                    **{
                        **dict(subject),
                        "harness": HarnessSpec(
                            **{**dict(subject.harness), "skills": [replaced]}
                        ),
                    }
                )
            },
        }
    )
    return recorded_pair(campaign=campaign)


def _with_model_revision(campaign: CampaignSpec, revision: str) -> CampaignSpec:
    """Return the Campaign with a provider revision pinned on its subject."""
    subject = campaign.agents[SUBJECT_AGENT]
    return CampaignSpec(
        **{
            **dict(campaign),
            "agents": {
                SUBJECT_AGENT: AgentSpec(
                    **{
                        **dict(subject),
                        "model": ModelSpec(
                            **{**dict(subject.model), "revision": revision}
                        ),
                    }
                )
            },
        }
    )


def _skill_index_description(observed: ObservedVariant) -> str:
    """Return the Skill-index tool's description digest on one side."""
    return next(
        tool.description_digest
        for tool in observed.tools
        if tool.name == SKILL_INDEX_TOOL
    )
