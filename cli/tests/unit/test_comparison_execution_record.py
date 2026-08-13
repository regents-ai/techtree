"""The comparison's operational record. Decisions document 0007 R6+R8.

Three questions, and the middle one is the one the decision exists for.

*Does it describe what happened?* Timings, exit states, concurrency, the launch
skew and the overlap all come from evidence the run already wrote, and two
builds of one run produce identical bytes.

*Does it ever claim more than it knows?* Cost carries one of four provenances,
and the pair total takes the weakest of the two — an estimate added to a
provider's own figure is an estimate, and calling that sum provider-reported is
the single misstatement R6 names outright. Token counts are absent rather than
zero when nothing reported them, and the coverage counts say how much of a
variant they cover.

*Does it stay out of the way of the score?* Nothing here is an input to a
reward, a decision, or a comparison status. The tests below build records from
cancelled and failed executions to show that the record describes them without
anything in it deciding anything.

The evidence is built here rather than loaded from a fixture, because these
properties are about arithmetic over timestamps and tokens and a fixture would
only make the arithmetic harder to see.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from techtree.canonical import canonical_json_bytes, sha256_digest_bytes
from techtree.models.base import ArtifactRef
from techtree.models.campaign import VariantSchedule
from techtree.models.experiment import ExperimentVariant
from techtree.receipts.execution import (
    NO_COST_SOURCE,
    ComparisonExecutionRecord,
    CostProvenance,
    PairOutcome,
    UsageProvenance,
    VariantCost,
    build_comparison_execution_record,
    read_children_record,
    unavailable_cost,
    weakest_provenance,
)
from techtree.runs.child_registry import LaunchedChild, write_children_record
from techtree.verifiers.models import (
    ChildProcessOutcome,
    NormalizedEpisode,
    NormalizedRuntime,
    NormalizedTrace,
    NormalizedUsage,
    RealExecutionResult,
    SubjectImageResolution,
    VariantExecutionResult,
    VariantName,
)

RUN_ID = "run_01J8ZQ3KAAAAAAAAAAAAAAAAAA"
CAMPAIGN_DIGEST = f"sha256:{'c' * 64}"
STARTED = datetime(2026, 8, 13, 9, 0, 0, tzinfo=UTC)


def digest(label: str) -> str:
    return sha256_digest_bytes(label.encode())


def artifact(label: str) -> ArtifactRef:
    return ArtifactRef(
        digest=digest(label), media_type="application/json", size=64, relative_path=None
    )


def trace(*, calls: int, tokens: tuple[int, int, int] | None) -> NormalizedTrace:
    """One subject rollout, with or without the usage the engine recorded."""
    return NormalizedTrace(
        trace_id=f"trace-{calls}-{tokens}",
        agent_role="subject",
        task_hash=digest("task"),
        ok=True,
        verifiers_version="0.1.6",
        verifiers_revision="0" * 40,
        model_id="qwen/qwen3.7-flash",
        sampling={"temperature": 0.0},
        harness_id="hermes-agent",
        harness_version="0.19.0",
        use_bundled_skill=False,
        skill_root_digests=[],
        runtime=NormalizedRuntime(
            kind="docker",
            runtime_id=None,
            image=f"techtree/subject@{digest('image')}",
            image_index_digest=digest("image"),
            cpu=2.0,
            memory_gb=4.0,
        ),
        tools=[],
        rewards=[],
        metrics={},
        usage=(
            None
            if tokens is None
            else NormalizedUsage(
                input_tokens=tokens[0],
                output_tokens=tokens[1],
                total_tokens=tokens[2],
                cached_input_tokens=0,
            )
        ),
        model_calls=calls,
        num_turns=calls,
        last_reply=None,
        errors=[],
        raw_trace_digest=digest("raw-trace"),
    )


def episode(traces: list[NormalizedTrace]) -> NormalizedEpisode:
    return NormalizedEpisode(
        episode_id="episode",
        env_id="procedure-transfer-v1",
        task_hash=digest("task"),
        task_position=0,
        ok=True,
        traces=traces,
        errors=[],
        raw_episode_digest=digest("raw-episode"),
    )


def variant_result(
    variant: VariantName,
    *,
    elapsed: float,
    offset: float = 0.0,
    traces: list[NormalizedTrace] | None = None,
    exit_code: int = 0,
    cancelled: bool = False,
) -> VariantExecutionResult:
    """One side of an execution, as the run recorded it."""
    started = STARTED + timedelta(seconds=offset)
    return VariantExecutionResult(
        variant=variant,
        experiment_manifest_digest=digest(f"{variant.value}-manifest"),
        resolved_verifiers_config=artifact(f"{variant.value}-config"),
        raw_traces=artifact(f"{variant.value}-raw"),
        eval_log=artifact(f"{variant.value}-log"),
        normalized_episodes=artifact(f"{variant.value}-normalized"),
        image_resolution=SubjectImageResolution(
            variant=variant,
            image=f"techtree/subject@{digest('image')}",
            index_digest=digest("image"),
            platform="linux/arm64",
        ),
        child_outcome=ChildProcessOutcome(
            variant=variant,
            argv_digest=digest(f"{variant.value}-argv"),
            exit_code=exit_code,
            started_at=started,
            finished_at=started + timedelta(seconds=elapsed),
            stdout_artifact=artifact(f"{variant.value}-stdout"),
            stderr_artifact=artifact(f"{variant.value}-stderr"),
            cancelled=cancelled,
        ),
        episodes=[
            episode(
                traces if traces is not None else [trace(calls=3, tokens=(90, 10, 100))]
            )
        ],
    )


def execution(
    *,
    schedule: VariantSchedule = VariantSchedule.PARALLEL,
    baseline: VariantExecutionResult | None = None,
    candidate: VariantExecutionResult | None = None,
) -> RealExecutionResult:
    return RealExecutionResult(
        execution_backend="verifiers",
        engine_digest=digest("engine"),
        verifiers_revision="0" * 40,
        schedule=schedule,
        baseline=baseline or variant_result(VariantName.BASELINE, elapsed=100.0),
        candidate=candidate
        or variant_result(VariantName.CANDIDATE, elapsed=80.0, offset=10.0),
    )


def build(
    tmp_path: Path,
    *,
    result: RealExecutionResult | None = None,
    costs: dict[VariantName, VariantCost] | None = None,
    max_concurrent: int = 4,
) -> ComparisonExecutionRecord:
    return build_comparison_execution_record(
        run_id=RUN_ID,
        campaign_spec_digest=CAMPAIGN_DIGEST,
        campaign_max_concurrent=max_concurrent,
        execution=result or execution(),
        run_root=tmp_path,
        costs=costs,
    )


# ---------------------------------------------------------------------------
# What it describes
# ---------------------------------------------------------------------------


def test_the_record_describes_the_run_and_both_of_its_sides(tmp_path: Path) -> None:
    record = build(tmp_path)

    assert record.schema_version == "techtree.comparison-execution.v1alpha1"
    assert record.run_id == RUN_ID
    assert record.campaign_spec_digest == CAMPAIGN_DIGEST
    assert record.execution_backend == "verifiers"
    assert record.schedule is VariantSchedule.PARALLEL
    assert record.baseline.variant is ExperimentVariant.BASELINE
    assert record.candidate.variant is ExperimentVariant.CANDIDATE
    assert record.outcome is PairOutcome.COMPLETED


def test_the_timings_are_the_ones_the_children_recorded(tmp_path: Path) -> None:
    """Elapsed, overlap and the pair's own window, all from the same clock."""
    record = build(tmp_path)

    assert record.baseline.elapsed_seconds == 100.0
    assert record.candidate.elapsed_seconds == 80.0
    assert record.started_at == STARTED
    assert record.finished_at == STARTED + timedelta(seconds=100)
    assert record.elapsed_seconds == 100.0
    # The candidate started ten seconds late and finished ninety seconds in,
    # so both were running for eighty of the hundred seconds.
    assert record.overlap_seconds == 80.0


def test_two_sides_that_never_ran_together_overlap_by_nothing(
    tmp_path: Path,
) -> None:
    record = build(
        tmp_path,
        result=execution(
            schedule=VariantSchedule.SEQUENTIAL,
            baseline=variant_result(VariantName.BASELINE, elapsed=30.0),
            candidate=variant_result(VariantName.CANDIDATE, elapsed=30.0, offset=60.0),
        ),
    )

    assert record.overlap_seconds == 0.0
    assert record.schedule is VariantSchedule.SEQUENTIAL


def test_the_concurrency_allocation_is_the_one_the_campaign_was_divided_into(
    tmp_path: Path,
) -> None:
    """A parallel pair splits the Campaign's bound; a sequential one does not."""
    parallel = build(tmp_path, max_concurrent=4)
    sequential = build(
        tmp_path,
        result=execution(schedule=VariantSchedule.SEQUENTIAL),
        max_concurrent=4,
    )

    assert parallel.campaign_max_concurrent == 4
    assert (parallel.baseline.max_concurrent, parallel.candidate.max_concurrent) == (
        2,
        2,
    )
    assert (
        sequential.baseline.max_concurrent,
        sequential.candidate.max_concurrent,
    ) == (4, 4)


def test_the_record_names_the_artifacts_it_was_built_from(tmp_path: Path) -> None:
    """Every number here can be traced back to bytes the run still holds."""
    record = build(tmp_path)

    assert record.engine_digest == digest("engine")
    assert record.baseline.experiment_manifest_digest == digest("baseline-manifest")
    assert record.baseline.normalized_episodes_digest == digest("baseline-normalized")
    assert record.baseline.raw_traces_digest == digest("baseline-raw")
    assert record.baseline.resolved_config_digest == digest("baseline-config")
    assert record.baseline.argv_digest == digest("baseline-argv")


def test_two_builds_of_one_execution_are_byte_identical(tmp_path: Path) -> None:
    """Nothing here reads a clock, so a record is a function of the run."""
    result = execution()

    first = build(tmp_path, result=result)
    second = build(tmp_path, result=result)

    assert canonical_json_bytes(first) == canonical_json_bytes(second)


# ---------------------------------------------------------------------------
# Cancellation and failure
# ---------------------------------------------------------------------------


def test_a_cancelled_pair_says_it_was_cancelled(tmp_path: Path) -> None:
    record = build(
        tmp_path,
        result=execution(
            candidate=variant_result(
                VariantName.CANDIDATE, elapsed=5.0, exit_code=143, cancelled=True
            )
        ),
    )

    assert record.outcome is PairOutcome.CANCELLED
    assert record.candidate.cancelled is True
    assert record.candidate.exit_code == 143


def test_a_failed_pair_says_it_failed(tmp_path: Path) -> None:
    record = build(
        tmp_path,
        result=execution(
            baseline=variant_result(VariantName.BASELINE, elapsed=9.0, exit_code=1)
        ),
    )

    assert record.outcome is PairOutcome.FAILED
    assert record.baseline.cancelled is False


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------


def test_tokens_are_summed_from_the_normalized_traces(tmp_path: Path) -> None:
    record = build(
        tmp_path,
        result=execution(
            baseline=variant_result(
                VariantName.BASELINE,
                elapsed=10.0,
                traces=[
                    trace(calls=4, tokens=(100, 20, 120)),
                    trace(calls=2, tokens=(50, 5, 55)),
                ],
            )
        ),
    )
    usage = record.baseline.usage

    assert usage.provenance is UsageProvenance.NORMALIZED_TRACES
    assert usage.input_tokens == 150
    assert usage.output_tokens == 25
    assert usage.total_tokens == 175
    assert usage.cached_input_tokens == 0
    assert usage.model_calls == 6
    assert (usage.traces_total, usage.traces_with_usage) == (2, 2)


def test_a_variant_whose_traces_report_no_usage_says_unavailable(
    tmp_path: Path,
) -> None:
    """Absent tokens are absent, never a zero that reads as "used nothing"."""
    record = build(
        tmp_path,
        result=execution(
            baseline=variant_result(
                VariantName.BASELINE,
                elapsed=10.0,
                traces=[trace(calls=5, tokens=None)],
            )
        ),
    )
    usage = record.baseline.usage

    assert usage.provenance is UsageProvenance.UNAVAILABLE
    assert usage.total_tokens is None
    assert usage.input_tokens is None
    # Calls are counted by every trace, so they are known even here.
    assert usage.model_calls == 5
    assert (usage.traces_total, usage.traces_with_usage) == (1, 0)


def test_partial_usage_coverage_is_visible_as_partial(tmp_path: Path) -> None:
    record = build(
        tmp_path,
        result=execution(
            baseline=variant_result(
                VariantName.BASELINE,
                elapsed=10.0,
                traces=[
                    trace(calls=1, tokens=(10, 1, 11)),
                    trace(calls=1, tokens=None),
                    trace(calls=1, tokens=None),
                ],
            )
        ),
    )
    usage = record.baseline.usage

    assert usage.total_tokens == 11
    assert (usage.traces_total, usage.traces_with_usage) == (3, 1)


def test_both_sides_tokens_are_absent_when_either_side_is(tmp_path: Path) -> None:
    record = build(
        tmp_path,
        result=execution(
            candidate=variant_result(
                VariantName.CANDIDATE,
                elapsed=10.0,
                traces=[trace(calls=1, tokens=None)],
            )
        ),
    )

    assert record.baseline.usage.total_tokens is not None
    assert record.total_tokens is None


# ---------------------------------------------------------------------------
# Cost provenance
# ---------------------------------------------------------------------------


def test_a_run_with_no_price_feed_reports_an_unavailable_cost(
    tmp_path: Path,
) -> None:
    """What every run in this build actually produces."""
    record = build(tmp_path)

    assert record.baseline.cost.provenance is CostProvenance.UNAVAILABLE
    assert record.baseline.cost.cost_usd is None
    assert record.baseline.cost.detail == NO_COST_SOURCE
    assert record.total_cost.provenance is CostProvenance.UNAVAILABLE
    assert record.total_cost.cost_usd is None


@pytest.mark.parametrize(
    "provenance",
    [
        CostProvenance.PROVIDER_REPORTED,
        CostProvenance.COMPUTED_FROM_PINNED_PRICE,
        CostProvenance.ESTIMATED,
    ],
)
def test_every_provenance_is_reachable_through_the_cost_seam(
    tmp_path: Path, provenance: CostProvenance
) -> None:
    """The seam a price feed arrives through carries its own provenance."""
    cost = VariantCost(cost_usd=1.25, provenance=provenance, detail="from the feed")
    record = build(
        tmp_path,
        costs={VariantName.BASELINE: cost, VariantName.CANDIDATE: cost},
    )

    assert record.baseline.cost.provenance is provenance
    assert record.total_cost.cost_usd == 2.5
    assert record.total_cost.provenance is provenance


def test_a_total_never_claims_more_than_its_weakest_half(tmp_path: Path) -> None:
    """An estimate plus a billed figure is an estimate. R6, in one assertion."""
    record = build(
        tmp_path,
        costs={
            VariantName.BASELINE: VariantCost(
                cost_usd=3.0,
                provenance=CostProvenance.PROVIDER_REPORTED,
                detail="the provider billed this",
            ),
            VariantName.CANDIDATE: VariantCost(
                cost_usd=1.0,
                provenance=CostProvenance.ESTIMATED,
                detail="worked out from usage",
            ),
        },
    )

    assert record.total_cost.cost_usd == 4.0
    assert record.total_cost.provenance is CostProvenance.ESTIMATED


def test_a_total_is_absent_when_either_half_is_unknown(tmp_path: Path) -> None:
    record = build(
        tmp_path,
        costs={
            VariantName.BASELINE: VariantCost(
                cost_usd=3.0,
                provenance=CostProvenance.PROVIDER_REPORTED,
                detail="the provider billed this",
            ),
            VariantName.CANDIDATE: unavailable_cost("nothing reported one"),
        },
    )

    assert record.total_cost.cost_usd is None
    assert record.total_cost.provenance is CostProvenance.UNAVAILABLE


def test_the_weakest_provenance_is_the_one_that_claims_least() -> None:
    assert (
        weakest_provenance(
            [
                CostProvenance.PROVIDER_REPORTED,
                CostProvenance.COMPUTED_FROM_PINNED_PRICE,
            ]
        )
        is CostProvenance.COMPUTED_FROM_PINNED_PRICE
    )
    assert (
        weakest_provenance([CostProvenance.ESTIMATED, CostProvenance.UNAVAILABLE])
        is CostProvenance.UNAVAILABLE
    )
    assert (
        weakest_provenance([CostProvenance.PROVIDER_REPORTED])
        is CostProvenance.PROVIDER_REPORTED
    )


def test_a_cost_figure_cannot_be_carried_without_a_provenance() -> None:
    """The shape refuses the misstatement rather than trusting a caller."""
    with pytest.raises(ValueError, match="provenance"):
        VariantCost(
            cost_usd=1.0, provenance=CostProvenance.UNAVAILABLE, detail="no source"
        )
    with pytest.raises(ValueError, match="provenance"):
        VariantCost(
            cost_usd=None,
            provenance=CostProvenance.PROVIDER_REPORTED,
            detail="a source with nothing to source",
        )


# ---------------------------------------------------------------------------
# The scheduler's own record
# ---------------------------------------------------------------------------


def test_the_launch_skew_comes_from_what_the_scheduler_wrote(
    tmp_path: Path,
) -> None:
    """The one measurement only the moment of launching could produce."""
    write_children_record(
        run_root=tmp_path,
        run_id=RUN_ID,
        schedule=VariantSchedule.PARALLEL,
        children=[
            LaunchedChild(
                variant=VariantName.BASELINE,
                pid=4242,
                argv_digest=digest("baseline-argv"),
                started_at=STARTED,
            ),
            LaunchedChild(
                variant=VariantName.CANDIDATE,
                pid=4243,
                argv_digest=digest("candidate-argv"),
                started_at=STARTED + timedelta(milliseconds=31),
            ),
        ],
        launch_skew_seconds=0.031,
    )

    record = build(tmp_path)

    assert record.launch_skew_seconds == pytest.approx(0.031)
    assert record.first_launched is ExperimentVariant.BASELINE
    assert read_children_record(tmp_path) == (0.031, ExperimentVariant.BASELINE)


def test_a_run_that_recorded_no_skew_reports_none(tmp_path: Path) -> None:
    """A sequential pair has no launch gap to measure, and says so."""
    write_children_record(
        run_root=tmp_path,
        run_id=RUN_ID,
        schedule=VariantSchedule.SEQUENTIAL,
        children=[
            LaunchedChild(
                variant=VariantName.BASELINE,
                pid=4242,
                argv_digest=digest("baseline-argv"),
                started_at=STARTED,
            )
        ],
        launch_skew_seconds=None,
    )

    record = build(tmp_path)

    assert record.launch_skew_seconds is None
    assert record.first_launched is None


def test_an_unreadable_operational_record_leaves_the_skew_unknown(
    tmp_path: Path,
) -> None:
    """A record nobody can read reports nothing rather than reconstructing it."""
    (tmp_path / "execution").mkdir(parents=True)
    (tmp_path / "execution" / "children.json").write_text("{", encoding="utf-8")

    record = build(tmp_path)

    assert record.launch_skew_seconds is None
    assert record.first_launched is None
