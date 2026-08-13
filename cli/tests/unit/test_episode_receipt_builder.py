"""Receipts built from a real evaluation. Spec sections 7.6, 15.

Every happy-path assertion here runs against evidence a paid run actually
produced (``fixtures.receipts.support``), so "the rewards are preserved
exactly" is checked against numbers a subject model really earned rather than
against numbers this test invented. The refusals are provoked by editing a copy
of that evidence in memory, one property at a time, because the whole point of
the taxonomy in spec section 15 is that each way an evaluation can be unusable
is reported as itself.

The division the module draws is the division these tests check. Evidence that
cannot be joined onto the Campaign's commitment is refused; a rollout that
genuinely failed is recorded with an honest status. A test that accepted the
first as a status, or the second as a refusal, would be testing a different
policy than the one spec section 7.6 states.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import pytest

from fixtures.receipts.support import RecordedVariant, recorded_variant
from techtree.canonical import digest_object
from techtree.errors import TechtreeError
from techtree.models.campaign import EvidenceRequirements
from techtree.models.episode_receipt import (
    EpisodeReceipt,
    EvidenceStatus,
    ScoreStatus,
)
from techtree.receipts.episode import (
    EPISODE_COUNT_MISMATCH,
    EPISODE_RECEIPT_INVALID,
    EVALUATION_OUTPUT_CORRUPT,
    EVALUATION_OUTPUT_MISSING,
    REWARD_MISSING,
    REWARD_NON_FINITE,
    TASK_MEMBERSHIP_MISMATCH,
    TRACE_ROLE_MISMATCH,
    build_variant_receipts,
    experiment_variant_of,
    read_variant_episodes,
)
from techtree.verifiers.models import (
    NormalizedEpisode,
    NormalizedExecutionError,
    VariantExecutionResult,
    VariantName,
)

#: A task hash the recorded Campaign does not commit to, spelled as a Techtree
#: digest so that the refusal under test is the membership rule and not the
#: digest syntax.
_FOREIGN_TASK: Final = f"sha256:{'ab' * 32}"


@pytest.fixture(params=[VariantName.BASELINE, VariantName.CANDIDATE])
def recorded(request: pytest.FixtureRequest) -> RecordedVariant:
    """Return one recorded variant's evaluation."""
    variant: VariantName = request.param
    return recorded_variant(variant)


def receipts_for(
    recorded: RecordedVariant,
    *,
    result: VariantExecutionResult | None = None,
    ordered_task_hashes: Sequence[str] | None = None,
    evidence: EvidenceRequirements | None = None,
) -> list[EpisodeReceipt]:
    """Build one variant's receipts, with one input optionally replaced."""
    return build_variant_receipts(
        run_request=recorded.request,
        variant=recorded.variant,
        experiment=recorded.experiment,
        result=recorded.result if result is None else result,
        evaluation_backend=recorded.campaign.evaluation_backend,
        ordered_task_hashes=(
            recorded.ordered_task_hashes
            if ordered_task_hashes is None
            else ordered_task_hashes
        ),
        primary_reward=recorded.primary_reward,
        evidence=recorded.campaign.evidence if evidence is None else evidence,
    )


def with_episodes(
    recorded: RecordedVariant, episodes: Sequence[NormalizedEpisode]
) -> VariantExecutionResult:
    """Return the recorded execution carrying a different episode list."""
    return recorded.result.model_copy(update={"episodes": list(episodes)})


# ---------------------------------------------------------------------------
# Every expected episode has a receipt
# ---------------------------------------------------------------------------


def test_every_committed_task_gets_exactly_one_receipt(
    recorded: RecordedVariant,
) -> None:
    """One receipt per committed task, in the order the Campaign commits."""
    receipts = receipts_for(recorded)

    assert [receipt.task_hash for receipt in receipts] == recorded.ordered_task_hashes
    assert len({receipt.id for receipt in receipts}) == len(receipts)
    assert len({receipt.episode_id for receipt in receipts}) == len(receipts)


def test_receipts_follow_membership_order_not_completion_order(
    recorded: RecordedVariant,
) -> None:
    """The join is on task hash, so a shuffled file still pairs correctly."""
    shuffled = list(reversed(recorded.episodes))
    receipts = receipts_for(recorded, result=with_episodes(recorded, shuffled))

    assert [receipt.task_hash for receipt in receipts] == recorded.ordered_task_hashes


def test_rebuilding_from_the_same_evidence_produces_the_same_receipts(
    recorded: RecordedVariant,
) -> None:
    """Nothing in a receipt is random, so a rebuild is byte-identical."""
    first = receipts_for(recorded)
    second = receipts_for(recorded)

    assert [digest_object(receipt) for receipt in first] == [
        digest_object(receipt) for receipt in second
    ]


# ---------------------------------------------------------------------------
# The rewards are the recorded rewards
# ---------------------------------------------------------------------------


def test_rewards_are_the_numbers_verifiers_recorded(
    recorded: RecordedVariant,
) -> None:
    """Every reward is copied from the evidence, not recomputed from it."""
    receipts = receipts_for(recorded)

    for receipt, episode in zip(
        receipts,
        [
            next(item for item in recorded.episodes if item.task_hash == task_hash)
            for task_hash in recorded.ordered_task_hashes
        ],
        strict=True,
    ):
        trace = episode.traces[0]
        recorded_rewards = {reward.name: reward.score for reward in trace.rewards}
        assert receipt.named_traces["subject"][0].rewards == recorded_rewards
        assert receipt.named_traces["subject"][0].metrics == trace.metrics


def test_the_recorded_run_scored_what_the_evidence_file_says(
    recorded: RecordedVariant,
) -> None:
    """Read the reward straight out of the committed file and compare.

    A deliberately blunt check. It goes around every model in the codebase and
    reads the JSON the engine wrote, so that no amount of parsing, defaulting
    or rounding between here and there can pass unnoticed.
    """
    from_file = {
        json.loads(line)["task_hash"]: json.loads(line)["traces"][0]["rewards"]
        for line in recorded.normalized_episodes_path.read_text().splitlines()
    }
    receipts = receipts_for(recorded)

    for receipt in receipts:
        scored = {
            reward["name"]: reward["score"] for reward in from_file[receipt.task_hash]
        }
        assert receipt.named_traces["subject"][0].rewards == scored


def test_the_candidate_outscored_the_baseline_on_the_shared_tasks() -> None:
    """The recorded probes are a real result, and the receipts carry it."""
    baseline = recorded_variant(VariantName.BASELINE)
    candidate = recorded_variant(VariantName.CANDIDATE)
    reward = candidate.primary_reward

    def scored(recorded: RecordedVariant) -> dict[str, float]:
        return {
            receipt.task_hash: receipt.named_traces["subject"][0].rewards[reward]
            for receipt in receipts_for(recorded)
        }

    without_skill = scored(baseline)
    with_skill = scored(candidate)
    shared = sorted(set(without_skill) & set(with_skill))

    assert len(shared) == 2
    assert [without_skill[task] for task in shared] == [0.0, 0.0]
    assert [with_skill[task] for task in shared] == [1.0, 1.0]


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------


def test_a_receipt_carries_the_runs_own_lineage(recorded: RecordedVariant) -> None:
    """Every reference comes from the immutable request and staged manifest."""
    request = recorded.request

    for receipt in receipts_for(recorded):
        assert receipt.run_id == request.run_id
        assert receipt.campaign_spec_digest == request.campaign_spec_digest
        assert receipt.program_ref == request.program_ref
        assert receipt.public_context == request.public_context
        assert receipt.data_policy_digest == request.data_policy_digest
        assert receipt.outcome_contract_digest == request.outcome_contract_digest
        assert receipt.evaluation_backend == recorded.campaign.evaluation_backend
        assert receipt.variant is experiment_variant_of(recorded.variant)
        assert receipt.experiment_manifest_digest == digest_object(recorded.experiment)
        assert receipt.execution_backend == "verifiers"


def test_a_receipt_names_the_container_the_subject_ran_in(
    recorded: RecordedVariant,
) -> None:
    """A real subject executed, so the runtime is Docker and it is pinned."""
    for receipt, episode in zip(
        receipts_for(recorded),
        [
            next(item for item in recorded.episodes if item.task_hash == task_hash)
            for task_hash in recorded.ordered_task_hashes
        ],
        strict=True,
    ):
        runtime = episode.traces[0].runtime
        assert receipt.subject_runtime.kind == "docker"
        assert receipt.subject_runtime.resolved_image_digest == (
            runtime.image_index_digest
        )


def test_a_receipt_carries_one_named_subject_trace(recorded: RecordedVariant) -> None:
    """The trace is named for the seat it ran in and cited by digest."""
    for receipt, episode in zip(
        receipts_for(recorded),
        [
            next(item for item in recorded.episodes if item.task_hash == task_hash)
            for task_hash in recorded.ordered_task_hashes
        ],
        strict=True,
    ):
        assert sorted(receipt.named_traces) == ["subject"]
        traces = receipt.named_traces["subject"]
        assert len(traces) == 1
        assert traces[0].role == "subject"
        assert traces[0].trace_id == episode.traces[0].trace_id
        assert traces[0].trace_digest == episode.traces[0].raw_trace_digest
        assert receipt.episode_digest == episode.raw_episode_digest


def test_a_receipt_points_at_the_whole_variants_evidence(
    recorded: RecordedVariant,
) -> None:
    """Raw evidence and its projection are both referenced, both by digest."""
    result = recorded.result
    expected = [
        result.resolved_verifiers_config,
        result.raw_traces,
        result.eval_log,
        result.normalized_episodes,
    ]

    for receipt in receipts_for(recorded):
        assert receipt.artifacts == expected


def test_a_receipt_from_the_other_variants_manifest_is_refused() -> None:
    """A manifest that is not the one the request names cannot be receipted."""
    baseline = recorded_variant(VariantName.BASELINE)
    candidate = recorded_variant(VariantName.CANDIDATE)

    with pytest.raises(TechtreeError) as failure:
        build_variant_receipts(
            run_request=baseline.request,
            variant=VariantName.BASELINE,
            experiment=candidate.experiment,
            result=baseline.result,
            evaluation_backend=baseline.campaign.evaluation_backend,
            ordered_task_hashes=baseline.ordered_task_hashes,
            primary_reward=baseline.primary_reward,
            evidence=baseline.campaign.evidence,
        )

    assert failure.value.code == EPISODE_RECEIPT_INVALID


def test_an_execution_from_the_other_variant_is_refused() -> None:
    """A baseline receipt cannot be built from a candidate execution."""
    baseline = recorded_variant(VariantName.BASELINE)
    candidate = recorded_variant(VariantName.CANDIDATE)

    with pytest.raises(TechtreeError) as failure:
        build_variant_receipts(
            run_request=baseline.request,
            variant=VariantName.BASELINE,
            experiment=baseline.experiment,
            result=candidate.result,
            evaluation_backend=baseline.campaign.evaluation_backend,
            ordered_task_hashes=baseline.ordered_task_hashes,
            primary_reward=baseline.primary_reward,
            evidence=baseline.campaign.evidence,
        )

    assert failure.value.code == EPISODE_RECEIPT_INVALID


# ---------------------------------------------------------------------------
# Statuses
# ---------------------------------------------------------------------------


def test_a_clean_scored_episode_is_valid_and_complete(
    recorded: RecordedVariant,
) -> None:
    """The recorded probes completed and scored, so their receipts say so."""
    for receipt in receipts_for(recorded):
        assert receipt.score_status is ScoreStatus.VALID
        assert receipt.evidence_status is EvidenceStatus.COMPLETE


def test_a_failed_episode_is_recorded_rather_than_refused(
    recorded: RecordedVariant,
) -> None:
    """An episode that failed still gets a receipt, and it says it failed."""
    first, *rest = recorded.episodes
    failed = first.model_copy(update={"ok": False})
    receipts = receipts_for(recorded, result=with_episodes(recorded, [failed, *rest]))

    by_task = {receipt.task_hash: receipt for receipt in receipts}
    assert by_task[first.task_hash].score_status is ScoreStatus.ERRORED
    assert all(
        by_task[episode.task_hash].score_status is ScoreStatus.VALID for episode in rest
    )


def test_a_trace_carrying_an_execution_error_is_errored(
    recorded: RecordedVariant,
) -> None:
    """A rollout the provider gave up on is not a valid score."""
    first, *rest = recorded.episodes
    broken = first.traces[0].model_copy(
        update={
            "errors": [
                NormalizedExecutionError(
                    type="ProviderError", message="the provider refused the context"
                )
            ]
        }
    )
    errored = first.model_copy(update={"traces": [broken]})
    receipts = receipts_for(recorded, result=with_episodes(recorded, [errored, *rest]))

    by_task = {receipt.task_hash: receipt for receipt in receipts}
    assert by_task[first.task_hash].score_status is ScoreStatus.ERRORED


def test_evidence_is_partial_when_the_campaign_requires_a_relay(
    recorded: RecordedVariant,
) -> None:
    """This release collects no runtime evidence and must not pretend it did."""
    demanding = EvidenceRequirements(
        verifiers_episode="required", runtime_evidence="required"
    )
    receipts = receipts_for(recorded, evidence=demanding)

    assert all(
        receipt.evidence_status is EvidenceStatus.PARTIAL for receipt in receipts
    )


def test_evidence_is_complete_when_a_relay_is_merely_optional(
    recorded: RecordedVariant,
) -> None:
    """Absence of an optional thing is not incompleteness. Spec section 7.6."""
    optional = EvidenceRequirements(
        verifiers_episode="required", runtime_evidence="optional"
    )
    receipts = receipts_for(recorded, evidence=optional)

    assert all(
        receipt.evidence_status is EvidenceStatus.COMPLETE for receipt in receipts
    )


# ---------------------------------------------------------------------------
# Refusals: the spec section 15 taxonomy
# ---------------------------------------------------------------------------


def test_a_missing_task_is_an_episode_count_mismatch(
    recorded: RecordedVariant,
) -> None:
    """A variant that scored fewer tasks than the Campaign committed to."""
    short = recorded.episodes[:-1]

    with pytest.raises(TechtreeError) as failure:
        receipts_for(recorded, result=with_episodes(recorded, short))

    assert failure.value.code == EPISODE_COUNT_MISMATCH


def test_a_task_the_campaign_never_committed_to_is_a_membership_mismatch(
    recorded: RecordedVariant,
) -> None:
    """The count is right and the tasks are wrong, which is the harder case."""
    first, *rest = recorded.episodes
    foreign = first.model_copy(
        update={
            "task_hash": _FOREIGN_TASK,
            "traces": [first.traces[0].model_copy(update={"task_hash": _FOREIGN_TASK})],
        }
    )

    with pytest.raises(TechtreeError) as failure:
        receipts_for(recorded, result=with_episodes(recorded, [foreign, *rest]))

    assert failure.value.code == TASK_MEMBERSHIP_MISMATCH
    assert failure.value.details["unexpected"] == [_FOREIGN_TASK]


def test_scoring_one_task_twice_is_a_membership_mismatch(
    recorded: RecordedVariant,
) -> None:
    """Two results for one task means one of them would have to be discarded."""
    first, *rest = recorded.episodes
    duplicate = rest[0].model_copy(
        update={
            "task_hash": first.task_hash,
            "traces": [
                rest[0].traces[0].model_copy(update={"task_hash": first.task_hash})
            ],
        }
    )

    with pytest.raises(TechtreeError) as failure:
        receipts_for(
            recorded, result=with_episodes(recorded, [first, duplicate, *rest[1:]])
        )

    assert failure.value.code == TASK_MEMBERSHIP_MISMATCH


def test_a_committed_membership_naming_one_task_twice_is_refused(
    recorded: RecordedVariant,
) -> None:
    """A repeated commitment would let a receipt occupy two positions."""
    repeated = [recorded.ordered_task_hashes[0]] * len(recorded.ordered_task_hashes)

    with pytest.raises(TechtreeError) as failure:
        receipts_for(recorded, ordered_task_hashes=repeated)

    assert failure.value.code == TASK_MEMBERSHIP_MISMATCH


def test_an_episode_with_two_traces_is_a_trace_role_mismatch(
    recorded: RecordedVariant,
) -> None:
    """A v0.1 episode carries exactly one subject rollout."""
    first, *rest = recorded.episodes
    doubled = first.model_copy(update={"traces": [first.traces[0], first.traces[0]]})

    with pytest.raises(TechtreeError) as failure:
        receipts_for(recorded, result=with_episodes(recorded, [doubled, *rest]))

    assert failure.value.code == TRACE_ROLE_MISMATCH


def test_an_episode_with_no_trace_is_a_trace_role_mismatch(
    recorded: RecordedVariant,
) -> None:
    """An episode with nothing in the subject seat scored nobody."""
    first, *rest = recorded.episodes
    empty = first.model_copy(update={"traces": []})

    with pytest.raises(TechtreeError) as failure:
        receipts_for(recorded, result=with_episodes(recorded, [empty, *rest]))

    assert failure.value.code == TRACE_ROLE_MISMATCH


def test_a_clean_rollout_that_scored_nothing_is_a_reward_failure(
    recorded: RecordedVariant,
) -> None:
    """Scoring that did not run is not a result. Spec section 7.6."""
    first, *rest = recorded.episodes
    unscored = first.model_copy(
        update={"traces": [first.traces[0].model_copy(update={"rewards": []})]}
    )

    with pytest.raises(TechtreeError) as failure:
        receipts_for(recorded, result=with_episodes(recorded, [unscored, *rest]))

    assert failure.value.code == REWARD_MISSING
    assert failure.value.details["task_hashes"] == [first.task_hash]


def test_a_non_finite_metric_is_refused(recorded: RecordedVariant) -> None:
    """A number canonical JSON cannot spell must not reach a digest."""
    first, *rest = recorded.episodes
    broken = first.model_copy(
        update={
            "traces": [
                first.traces[0].model_copy(update={"metrics": {"drift": float("nan")}})
            ]
        }
    )

    with pytest.raises(TechtreeError) as failure:
        receipts_for(recorded, result=with_episodes(recorded, [broken, *rest]))

    assert failure.value.code == EVALUATION_OUTPUT_CORRUPT


# ---------------------------------------------------------------------------
# The evidence boundary
# ---------------------------------------------------------------------------


def test_the_recorded_projection_reads_back(recorded: RecordedVariant) -> None:
    """The committed evidence parses into the episodes the tests use."""
    episodes = read_variant_episodes(recorded.normalized_episodes_path)

    assert [episode.task_hash for episode in episodes] == [
        episode.task_hash for episode in recorded.episodes
    ]
    assert [episode.task_position for episode in episodes] == list(range(len(episodes)))


def test_an_absent_projection_is_missing_rather_than_corrupt(tmp_path: Path) -> None:
    """Nothing was written, which is a different failure from unreadable."""
    with pytest.raises(TechtreeError) as failure:
        read_variant_episodes(tmp_path / "normalized-episodes.jsonl")

    assert failure.value.code == EVALUATION_OUTPUT_MISSING


def test_an_empty_projection_is_missing(tmp_path: Path) -> None:
    """An empty file means no episode was ever recorded."""
    path = tmp_path / "normalized-episodes.jsonl"
    path.write_bytes(b"")

    with pytest.raises(TechtreeError) as failure:
        read_variant_episodes(path)

    assert failure.value.code == EVALUATION_OUTPUT_MISSING


def test_a_truncated_projection_is_corrupt(
    recorded: RecordedVariant, tmp_path: Path
) -> None:
    """A file that stops mid-record would silently drop an episode."""
    path = tmp_path / "normalized-episodes.jsonl"
    path.write_text(recorded.normalized_episodes_path.read_text()[:-40])

    with pytest.raises(TechtreeError) as failure:
        read_variant_episodes(path)

    assert failure.value.code == EVALUATION_OUTPUT_CORRUPT


def test_a_non_finite_reward_in_the_file_is_named_as_one(
    recorded: RecordedVariant, tmp_path: Path
) -> None:
    """``NaN`` where a reward should be is a reward failure, not a parse error."""
    lines = recorded.normalized_episodes_path.read_text().splitlines()
    first = json.loads(lines[0])
    first["traces"][0]["rewards"][0]["score"] = float("nan")
    path = tmp_path / "normalized-episodes.jsonl"
    path.write_text("\n".join([json.dumps(first), *lines[1:]]) + "\n")

    with pytest.raises(TechtreeError) as failure:
        read_variant_episodes(path)

    assert failure.value.code == REWARD_NON_FINITE
    assert failure.value.details["line"] == 1


# ---------------------------------------------------------------------------
# What the recorded evidence does and does not contain
# ---------------------------------------------------------------------------


def test_recorded_evidence_carries_no_secret(recorded: RecordedVariant) -> None:
    """The normalized projection is safe to commit, checked rather than assumed.

    The raw upstream record holds complete transcripts and the taskset's own
    expected answers, which is why it stays in the run directory. What the
    engine's normalizer emits is a fixed set of fields, and this fixes that
    set: a future change that started carrying prompts, messages, task data or
    an endpoint into the projection would fail here before it could be
    committed as a fixture.
    """
    allowed_episode = {
        "env_id",
        "episode_id",
        "errors",
        "ok",
        "raw_episode_digest",
        "task_hash",
        "task_position",
        "traces",
    }
    allowed_trace = {
        "agent_role",
        "errors",
        "harness_id",
        "harness_version",
        "last_reply",
        "metrics",
        "model_calls",
        "model_id",
        "num_turns",
        "ok",
        "raw_trace_digest",
        "rewards",
        "runtime",
        "sampling",
        "skill_root_digests",
        "task_hash",
        "tools",
        "trace_id",
        "usage",
        "use_bundled_skill",
        "verifiers_revision",
        "verifiers_version",
    }

    for line in recorded.normalized_episodes_path.read_text().splitlines():
        episode = json.loads(line)
        assert set(episode) == allowed_episode
        for trace in episode["traces"]:
            assert set(trace) == allowed_trace
            # Tools reach a receipt as digests of their prompt material, never
            # as the prompt material itself.
            for tool in trace["tools"]:
                assert set(tool) == {
                    "name",
                    "description_digest",
                    "parameters_digest",
                }
