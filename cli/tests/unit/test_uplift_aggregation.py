"""Reward aggregation, the verdict, and the report. Spec section 7.10.

The numbers come from the two paid probes: ``exact_match`` 0.0 on both tasks
without the Skill, 1.0 on both with it. That makes the recorded case the one
spec section 7.10 singles out — a zero baseline, whose relative delta is null
rather than infinite — and every other case is built by changing the recorded
rewards to the shape being tested.

The report tests are about honesty rather than arithmetic. Each of the five
statuses is independent, and what this file pins is which combinations the
builder will produce and which it refuses to produce at all: a comparison that
was not controlled and a score that was not valid do not become a report with a
sad word in it, they become a failed run with a reason.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Final

import pytest

from fixtures.receipts.pair import RecordedPair, recorded_pair, trimmed_campaign
from techtree.canonical import digest_object
from techtree.errors import VerificationError
from techtree.models.campaign import CampaignSpec, ScoringSpec, VariantSchedule
from techtree.models.episode_receipt import EvidenceStatus, ScoreStatus
from techtree.models.uplift_report import (
    ComparisonStatus,
    ExecutionStatus,
    PublicationStatus,
    TaskDelta,
    UpliftDecision,
    UpliftReport,
)
from techtree.receipts.compare import (
    RealComparisonResult,
    compare_real_variants,
)
from techtree.receipts.episode import experiment_variant_of
from techtree.receipts.set import ReceiptSetManifest, build_receipt_set, seal_receipt
from techtree.receipts.uplift import (
    LocalAttestation,
    aggregate_primary_result,
    build_uplift_report,
    decide_uplift,
    pair_task_rewards,
    proof_grade_for,
    summarize_receipts,
)
from techtree.verifiers.models import VariantName

_PRIMARY: Final = "exact_match"
_INSTANT: Final = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def pair() -> RecordedPair:
    """Return the recorded comparison, loaded once for the whole module."""
    return recorded_pair()


@pytest.fixture(scope="module")
def controlled(pair: RecordedPair) -> RealComparisonResult:
    """Return the recorded pair's own controlled comparison."""
    return _compare(pair)


def _compare(
    pair: RecordedPair,
    *,
    candidate_observed: object | None = None,
) -> RealComparisonResult:
    """Compare the recorded pair, optionally with one side altered."""
    return compare_real_variants(
        campaign=pair.campaign,
        baseline_manifest=pair.baseline_manifest,
        candidate_manifest=pair.candidate_manifest,
        prepared_manifest_comparison=pair.prepared_comparison,
        baseline_receipts=pair.receipts(VariantName.BASELINE),
        candidate_receipts=pair.receipts(VariantName.CANDIDATE),
        taskset_lock=pair.taskset_lock,
        baseline_observed=pair.observed(VariantName.BASELINE),
        candidate_observed=candidate_observed  # type: ignore[arg-type]
        or pair.observed(VariantName.CANDIDATE),
        schedule=VariantSchedule.PARALLEL,
    )


# ---------------------------------------------------------------------------
# Pairing and aggregation
# ---------------------------------------------------------------------------


def test_the_recorded_probes_aggregate_to_a_measured_uplift(
    pair: RecordedPair,
) -> None:
    """0/2 without the Skill against 2/2 with it, as recorded."""
    deltas = _deltas(pair)
    primary = aggregate_primary_result(deltas, _PRIMARY)

    assert [delta.baseline_reward for delta in deltas] == [0.0, 0.0]
    assert [delta.candidate_reward for delta in deltas] == [1.0, 1.0]
    assert primary.baseline_mean == 0.0
    assert primary.candidate_mean == 1.0
    assert primary.absolute_delta == 1.0
    # Spec section 7.10: a relative improvement over nothing is not a number.
    assert primary.relative_delta is None
    assert (primary.wins, primary.losses, primary.ties) == (2, 0, 0)


def test_rows_come_back_in_committed_order_however_they_arrived(
    pair: RecordedPair,
) -> None:
    """The join is on task identity, so arrival order cannot change the answer."""
    forwards = _deltas(pair)
    backwards = pair_task_rewards(
        baseline_receipts=list(reversed(pair.receipts(VariantName.BASELINE))),
        candidate_receipts=list(reversed(pair.receipts(VariantName.CANDIDATE))),
        ordered_task_hashes=pair.ordered_task_hashes,
        reward_name=_PRIMARY,
    )

    assert forwards == backwards
    assert [delta.task_hash for delta in forwards] == pair.ordered_task_hashes


def test_a_nonzero_baseline_gets_a_relative_delta() -> None:
    """The ordinary case, kept beside the recorded one."""
    primary = aggregate_primary_result(
        [_delta("a", 0.5, 1.0), _delta("b", 0.5, 0.5)], _PRIMARY
    )

    assert primary.baseline_mean == 0.5
    assert primary.candidate_mean == 0.75
    assert primary.absolute_delta == 0.25
    assert primary.relative_delta == 0.5


def test_wins_losses_and_ties_count_every_task_once() -> None:
    """Three tasks, one of each, counted by comparing the two rewards."""
    primary = aggregate_primary_result(
        [_delta("a", 0.0, 1.0), _delta("b", 1.0, 0.0), _delta("c", 1.0, 1.0)],
        _PRIMARY,
    )

    assert (primary.wins, primary.losses, primary.ties) == (1, 1, 1)
    assert primary.wins + primary.losses + primary.ties == 3
    assert primary.absolute_delta == 0.0


def test_a_regression_is_reported_as_one() -> None:
    """A candidate that scores worse produces a negative delta, not an error."""
    primary = aggregate_primary_result([_delta("a", 1.0, 0.0)], _PRIMARY)

    assert primary.absolute_delta == -1.0
    assert primary.relative_delta == -1.0
    assert (primary.wins, primary.losses, primary.ties) == (0, 1, 0)


def test_an_empty_comparison_is_refused() -> None:
    """A mean over no tasks is not a measurement."""
    with pytest.raises(VerificationError) as error:
        aggregate_primary_result([], _PRIMARY)

    assert error.value.code == "task_membership_mismatch"


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_a_non_finite_reward_is_refused(value: float) -> None:
    """Spec section 7.10: reject non-finite values."""
    with pytest.raises(VerificationError) as error:
        aggregate_primary_result([_delta("a", 0.0, value)], _PRIMARY)

    assert error.value.code == "reward_non_finite"


def test_a_missing_receipt_is_refused(pair: RecordedPair) -> None:
    """A comparison over the tasks that arrived is not the committed one."""
    with pytest.raises(VerificationError) as error:
        pair_task_rewards(
            baseline_receipts=pair.receipts(VariantName.BASELINE)[:1],
            candidate_receipts=pair.receipts(VariantName.CANDIDATE),
            ordered_task_hashes=pair.ordered_task_hashes,
            reward_name=_PRIMARY,
        )

    assert error.value.code == "task_membership_mismatch"


def test_a_duplicate_receipt_is_refused(pair: RecordedPair) -> None:
    """One task scored twice would let either result be the measurement."""
    receipts = pair.receipts(VariantName.CANDIDATE)

    with pytest.raises(VerificationError) as error:
        pair_task_rewards(
            baseline_receipts=pair.receipts(VariantName.BASELINE),
            candidate_receipts=[*receipts, receipts[0]],
            ordered_task_hashes=pair.ordered_task_hashes,
            reward_name=_PRIMARY,
        )

    assert error.value.code == "task_membership_mismatch"


def test_a_reward_the_campaign_is_decided_on_must_be_present(
    pair: RecordedPair,
) -> None:
    """A receipt with no primary reward is a refusal, not a zero."""
    with pytest.raises(VerificationError) as error:
        pair_task_rewards(
            baseline_receipts=pair.receipts(VariantName.BASELINE),
            candidate_receipts=pair.receipts(VariantName.CANDIDATE),
            ordered_task_hashes=pair.ordered_task_hashes,
            reward_name="a_reward_nobody_scored",
        )

    assert error.value.code == "reward_missing"


def test_a_committed_membership_naming_one_task_twice_is_refused(
    pair: RecordedPair,
) -> None:
    """The order rows come back in must be an order."""
    with pytest.raises(VerificationError) as error:
        pair_task_rewards(
            baseline_receipts=pair.receipts(VariantName.BASELINE),
            candidate_receipts=pair.receipts(VariantName.CANDIDATE),
            ordered_task_hashes=[pair.ordered_task_hashes[0]] * 2,
            reward_name=_PRIMARY,
        )

    assert error.value.code == "task_membership_mismatch"


# ---------------------------------------------------------------------------
# The verdict
# ---------------------------------------------------------------------------


def test_the_recorded_uplift_is_accepted(
    pair: RecordedPair, controlled: RealComparisonResult
) -> None:
    """The Campaign asks for any improvement, and a whole point arrived."""
    assert (
        decide_uplift(
            campaign=pair.campaign,
            comparison=controlled,
            primary=aggregate_primary_result(_deltas(pair), _PRIMARY),
        )
        is UpliftDecision.ACCEPTED
    )


def test_a_candidate_that_did_not_improve_is_rejected(
    pair: RecordedPair, controlled: RealComparisonResult
) -> None:
    """``require_candidate_above_baseline`` means strictly above."""
    tied = aggregate_primary_result([_delta("a", 1.0, 1.0)], _PRIMARY)

    assert (
        decide_uplift(campaign=pair.campaign, comparison=controlled, primary=tied)
        is UpliftDecision.REJECTED
    )


def test_an_improvement_below_the_declared_minimum_is_rejected(
    pair: RecordedPair, controlled: RealComparisonResult
) -> None:
    """A Campaign that asks for a tenth of a point does not accept a fiftieth."""
    campaign = _with_scoring(
        pair.campaign, require_above=True, minimum_absolute_delta=0.1
    )
    small = aggregate_primary_result([_delta("a", 0.5, 0.52)], _PRIMARY)

    assert (
        decide_uplift(campaign=campaign, comparison=controlled, primary=small)
        is UpliftDecision.REJECTED
    )


def test_a_campaign_that_predeclared_no_rule_is_inconclusive(
    pair: RecordedPair, controlled: RealComparisonResult
) -> None:
    """Nothing to accept against is not the same as accepted."""
    campaign = _with_scoring(
        pair.campaign, require_above=False, minimum_absolute_delta=0.0
    )

    assert (
        decide_uplift(
            campaign=campaign,
            comparison=controlled,
            primary=aggregate_primary_result(_deltas(pair), _PRIMARY),
        )
        is UpliftDecision.INCONCLUSIVE
    )


def test_an_uncontrolled_comparison_decides_invalid(pair: RecordedPair) -> None:
    """No arithmetic over an uncontrolled pair means anything."""
    broken = _broken_comparison(pair)

    assert broken.status is ComparisonStatus.INVALID
    assert (
        decide_uplift(
            campaign=pair.campaign,
            comparison=broken,
            primary=aggregate_primary_result(_deltas(pair), _PRIMARY),
        )
        is UpliftDecision.INVALID
    )


# ---------------------------------------------------------------------------
# Statuses and grade
# ---------------------------------------------------------------------------


def test_the_recorded_receipts_are_valid_and_complete(pair: RecordedPair) -> None:
    """What the receipts say, summarized without softening."""
    assert summarize_receipts(
        pair.receipts(VariantName.BASELINE), pair.receipts(VariantName.CANDIDATE)
    ) == (ScoreStatus.VALID, EvidenceStatus.COMPLETE)


def test_one_errored_rollout_makes_the_whole_score_invalid(
    pair: RecordedPair,
) -> None:
    """A comparison is only as good as its weakest receipt."""
    receipts = pair.receipts(VariantName.CANDIDATE)
    errored = [
        receipts[0].model_copy(update={"score_status": ScoreStatus.ERRORED}),
        *receipts[1:],
    ]

    score, evidence = summarize_receipts(pair.receipts(VariantName.BASELINE), errored)

    assert score is ScoreStatus.INVALID
    assert evidence is EvidenceStatus.COMPLETE


@pytest.mark.parametrize(
    ("attestation", "comparison", "score", "expected"),
    [
        (
            LocalAttestation.UNATTESTED,
            ComparisonStatus.CONTROLLED,
            ScoreStatus.VALID,
            "development_only",
        ),
        (
            LocalAttestation.LOCAL_ED25519,
            ComparisonStatus.CONTROLLED,
            ScoreStatus.VALID,
            "P1",
        ),
        (
            LocalAttestation.LOCAL_ED25519,
            ComparisonStatus.CONTROLLED_WITH_WARNINGS,
            ScoreStatus.VALID,
            "P1",
        ),
        (
            LocalAttestation.LOCAL_ED25519,
            ComparisonStatus.INVALID,
            ScoreStatus.VALID,
            "development_only",
        ),
        (
            LocalAttestation.LOCAL_ED25519,
            ComparisonStatus.CONTROLLED,
            ScoreStatus.ERRORED,
            "development_only",
        ),
    ],
)
def test_the_proof_grade_needs_every_condition(
    attestation: LocalAttestation,
    comparison: ComparisonStatus,
    score: ScoreStatus,
    expected: str,
) -> None:
    """Decisions document 0005 section 3.4, as a truth table."""
    assert (
        proof_grade_for(attestation=attestation, comparison=comparison, score=score)
        == expected
    )


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


def test_an_unsigned_real_report_states_what_it_measured(
    pair: RecordedPair, controlled: RealComparisonResult
) -> None:
    """Real statuses, real numbers, and no verdict this build may claim."""
    report = _report(pair, controlled, attestation=LocalAttestation.UNATTESTED)

    assert report.statuses.execution is ExecutionStatus.COMPLETED
    assert report.statuses.score is ScoreStatus.VALID
    assert report.statuses.evidence is EvidenceStatus.COMPLETE
    assert report.statuses.comparison is ComparisonStatus.CONTROLLED_WITH_WARNINGS
    assert report.statuses.publication is PublicationStatus.NOT_REQUESTED
    assert report.primary_result.candidate_mean == 1.0
    assert [delta.delta for delta in report.task_deltas] == [1.0, 1.0]
    # No local identity signs anything yet, so no P1 and therefore no verdict.
    assert report.proof_grade == "development_only"
    assert report.decision is UpliftDecision.DEVELOPMENT_ONLY
    assert report.publication_eligible is False


def test_an_unsigned_real_report_is_not_a_fake_one(
    pair: RecordedPair, controlled: RealComparisonResult
) -> None:
    """The difference a reader has to be able to see."""
    report = _report(pair, controlled, attestation=LocalAttestation.UNATTESTED)

    assert report.statuses.score is not ScoreStatus.DEVELOPMENT_ONLY
    assert report.statuses.evidence is not EvidenceStatus.DEVELOPMENT_ONLY
    assert report.statuses.comparison is not ComparisonStatus.DEVELOPMENT_ONLY


def test_a_signed_report_carries_the_verdict_and_p1(
    pair: RecordedPair, controlled: RealComparisonResult
) -> None:
    """The shape WP7c produces once the local identity signs."""
    report = _report(pair, controlled, attestation=LocalAttestation.LOCAL_ED25519)

    assert report.proof_grade == "P1"
    assert report.decision is UpliftDecision.ACCEPTED
    # Publication is absent from this push, not blocked by the science.
    assert report.publication_eligible is False
    assert report.statuses.publication is PublicationStatus.NOT_REQUESTED


def test_a_rejected_candidate_still_produces_a_valid_report(
    pair: RecordedPair, controlled: RealComparisonResult
) -> None:
    """A report that says no is a result, not a failure."""
    report = _report(
        pair,
        controlled,
        attestation=LocalAttestation.LOCAL_ED25519,
        deltas=[_delta(hash_, 1.0, 0.0) for hash_ in pair.ordered_task_hashes],
    )

    assert report.decision is UpliftDecision.REJECTED
    assert report.proof_grade == "P1"
    assert report.primary_result.absolute_delta == -1.0
    assert report.statuses.comparison is ComparisonStatus.CONTROLLED_WITH_WARNINGS


def test_an_inconclusive_campaign_produces_an_inconclusive_report() -> None:
    """Every decision spec section 7.10 names is reachable and truthful.

    The whole comparison is rebuilt over the altered Campaign rather than the
    report alone, because a report's lineage is checked against the run request
    that named the Campaign it executed.
    """
    undecidable = recorded_pair(
        campaign=_with_scoring(
            trimmed_campaign(), require_above=False, minimum_absolute_delta=0.0
        )
    )

    report = _report(
        undecidable,
        _compare(undecidable),
        attestation=LocalAttestation.LOCAL_ED25519,
    )

    assert report.decision is UpliftDecision.INCONCLUSIVE


def test_an_uncontrolled_comparison_produces_no_report(pair: RecordedPair) -> None:
    """The reason is worth more than a report with 'invalid' written in it."""
    with pytest.raises(VerificationError) as error:
        _report(pair, _broken_comparison(pair))

    assert error.value.code == "comparison_invalid"
    assert error.value.details["comparison"] == "invalid"


def test_an_invalid_score_produces_no_report(
    pair: RecordedPair, controlled: RealComparisonResult
) -> None:
    """Nothing was measured, so nothing is reported."""
    with pytest.raises(VerificationError) as error:
        _report(pair, controlled, score=ScoreStatus.INVALID)

    assert error.value.code == "comparison_invalid"
    assert error.value.details["score"] == "invalid"


def test_a_receipt_set_from_another_run_is_refused(
    pair: RecordedPair, controlled: RealComparisonResult
) -> None:
    """A report summarizes its own run's receipts and no others."""
    foreign = _receipt_set(pair, VariantName.CANDIDATE).model_copy(
        update={"run_id": "run_somebody_elses000000000000000"}
    )

    with pytest.raises(VerificationError) as error:
        _report(pair, controlled, candidate_receipt_set=foreign)

    assert error.value.code == "comparison_invalid"


def test_a_report_over_another_campaign_is_refused(
    pair: RecordedPair, controlled: RealComparisonResult
) -> None:
    """Lineage is checked against the run's own immutable request."""
    other = trimmed_campaign(task_hashes=list(reversed(pair.ordered_task_hashes)))

    with pytest.raises(VerificationError) as error:
        _report(pair, controlled, campaign=other)

    assert error.value.code == "comparison_invalid"


# ---------------------------------------------------------------------------
# Construction helpers
# ---------------------------------------------------------------------------


def _deltas(pair: RecordedPair) -> list[TaskDelta]:
    """Return the recorded pair's own paired rows."""
    return pair_task_rewards(
        baseline_receipts=pair.receipts(VariantName.BASELINE),
        candidate_receipts=pair.receipts(VariantName.CANDIDATE),
        ordered_task_hashes=pair.ordered_task_hashes,
        reward_name=_PRIMARY,
    )


def _delta(seed: str, baseline: float, candidate: float) -> TaskDelta:
    """Return one paired row for a task named by a seed or by its hash."""
    task_hash = seed if seed.startswith("sha256:") else digest_object({"task": seed})
    return TaskDelta(
        task_hash=task_hash,
        baseline_reward=baseline,
        candidate_reward=candidate,
        delta=candidate - baseline,
    )


def _receipt_set(pair: RecordedPair, variant: VariantName) -> ReceiptSetManifest:
    """Return one variant's ordered commitment over its recorded receipts."""
    return build_receipt_set(
        run_id=pair.request.run_id,
        variant=experiment_variant_of(variant),
        experiment_manifest_digest=pair.results[variant].experiment_manifest_digest,
        signed_receipts=[seal_receipt(receipt) for receipt in pair.receipts(variant)],
        ordered_task_hashes=pair.ordered_task_hashes,
    )


def _report(
    pair: RecordedPair,
    comparison: RealComparisonResult,
    *,
    attestation: LocalAttestation = LocalAttestation.UNATTESTED,
    campaign: CampaignSpec | None = None,
    deltas: Sequence[TaskDelta] | None = None,
    score: ScoreStatus | None = None,
    candidate_receipt_set: ReceiptSetManifest | None = None,
) -> UpliftReport:
    """Build the recorded pair's report with any one input replaced."""
    rows = list(deltas) if deltas is not None else _deltas(pair)
    resolved_score, evidence = summarize_receipts(
        pair.receipts(VariantName.BASELINE), pair.receipts(VariantName.CANDIDATE)
    )
    return build_uplift_report(
        run_request=pair.request,
        campaign=campaign or pair.campaign,
        taskset_validation_receipt_digest=(
            pair.campaign.taskset.validation_receipt_digest
        ),
        baseline_manifest=pair.baseline_manifest,
        candidate_manifest=pair.candidate_manifest,
        baseline_receipt_set=_receipt_set(pair, VariantName.BASELINE),
        candidate_receipt_set=candidate_receipt_set
        or _receipt_set(pair, VariantName.CANDIDATE),
        comparison=comparison,
        task_deltas=rows,
        primary=aggregate_primary_result(rows, _PRIMARY),
        score=score or resolved_score,
        evidence=evidence,
        attestation=attestation,
        created_at=_INSTANT,
    )


def _broken_comparison(pair: RecordedPair) -> RealComparisonResult:
    """Return a comparison of the recorded pair against a different model."""
    return _compare(
        pair,
        candidate_observed=dataclasses.replace(
            pair.observed(VariantName.CANDIDATE),
            configuration=pair.observed(VariantName.CANDIDATE).configuration.model_copy(
                update={"model_id": "some-other-model"}
            ),
        ),
    )


def _with_scoring(
    campaign: CampaignSpec, *, require_above: bool, minimum_absolute_delta: float
) -> CampaignSpec:
    """Return the Campaign with a different acceptance rule."""
    return CampaignSpec(
        **{
            **dict(campaign),
            "scoring": ScoringSpec(
                primary_reward=campaign.scoring.primary_reward,
                aggregation="mean",
                require_candidate_above_baseline=require_above,
                minimum_absolute_delta=minimum_absolute_delta,
            ),
        }
    )
