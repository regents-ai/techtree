"""Reward aggregation and the real report. Spec section 7.10.

Nothing here scores anything. Every number in an
:class:`~techtree.models.uplift_report.UpliftReport` is arithmetic over rewards
Verifiers recorded and Techtree copied into receipts without touching them, and
the arithmetic is the smallest that answers the Campaign's own question: two
means, their difference, and how many tasks moved which way.

Five rules shape it, and each one is a way of not lying.

*The join is on task identity.* Two variants complete their episodes in whatever
order the provider and the containers produced. Pairing by position in a list
would compare task 3 against task 7 in exactly the runs where concurrency
worked, so the pairing is by task hash and the row order is the TasksetLock's.

*One receipt per task per variant, or nothing.* A missing task is not a shorter
list and a duplicated task is not a tie-break; both are refusals, because a mean
over the tasks that happened to arrive is a mean over a taskset nobody committed
to.

*The score, not the weighted value.* A weight is the Campaign's opinion about
how much a reward should count. The comparison is on the reward Verifiers
scored, consistently on both sides, exactly as the receipts hold it.

*A relative improvement over nothing is not a number.* When the baseline mean is
zero, ``relative_delta`` is null. Reporting zero or infinity would each be a
different false statement, and the recorded evidence this was built against has
a zero baseline, so it is the ordinary case rather than the edge one.

*A tie is exact equality.* Spec section 7.10 permits a Campaign-declared
tolerance instead, and the frozen
:class:`~techtree.models.campaign.ScoringSpec` declares none, so there is no
tolerance to apply. For the discrete rewards v0.1 measures — ``exact_match`` is
0.0 or 1.0 — exact equality is also the right rule rather than a fallback.

WHAT GRADE AN UNSIGNED REAL REPORT CARRIES, AND WHY

Decisions document 0005 section 3.4 lets a report claim ``proof_grade: P1``
only when its receipts and the report itself are wrapped in *signed* envelopes
under the local executor identity, that identity's public key travels with
them, the comparison is controlled, and the score is valid. Signing is WP7c's
and does not exist yet, so nothing this module builds today can satisfy those
conditions.

The frozen model offers exactly two grades, and it couples the weaker one to the
verdict: a ``development_only`` report must reach a ``development_only``
decision and must not be publication eligible. So an unsigned real report
states everything it measured — execution completed, score valid, evidence
complete, comparison controlled, both means, every task delta — and withholds
the *verdict*, because the verdict is the field the frozen model ties to the
proof grade. It is not a fake report: a fake one is ``development_only`` in its
score, evidence and comparison statuses too, and this one is not.

:func:`decide_uplift` still computes the verdict, and
:class:`LocalAttestation` is the single argument WP7c flips to
``local_ed25519`` once the identity signs. At that point the same inputs
produce a P1 report carrying accepted, rejected or inconclusive.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from datetime import datetime
from enum import StrEnum
from typing import Final, Literal

from techtree.canonical import digest_object
from techtree.constants import UPLIFT_SCHEMA_VERSION
from techtree.errors import VerificationError
from techtree.ids import new_id
from techtree.models.base import Digest, JsonValue
from techtree.models.campaign import SUBJECT_AGENT, CampaignSpec
from techtree.models.episode_receipt import (
    EpisodeReceipt,
    EvidenceStatus,
    ScoreStatus,
)
from techtree.models.experiment import ExperimentManifest, ExperimentVariant
from techtree.models.run import RunRequest
from techtree.models.uplift_report import (
    ComparisonStatus,
    ExecutionStatus,
    PrimaryUpliftResult,
    PublicationStatus,
    TaskDelta,
    UpliftDecision,
    UpliftReport,
    UpliftStatuses,
)
from techtree.receipts.compare import COMPARISON_INVALID, RealComparisonResult
from techtree.receipts.episode import (
    REWARD_MISSING,
    REWARD_NON_FINITE,
    TASK_MEMBERSHIP_MISMATCH,
)
from techtree.receipts.set import ReceiptSetManifest
from techtree.tasksets.membership import membership_digest

__all__ = [
    "LocalAttestation",
    "aggregate_primary_result",
    "build_uplift_report",
    "decide_uplift",
    "pair_task_rewards",
    "proof_grade_for",
    "summarize_receipts",
]

#: What ``publication_eligible`` is in this push, and why. Upload does not
#: exist: no route, no credential, no server. The flag says nothing about the
#: science. Spec section 7.10.
_PUBLICATION_ELIGIBLE: Final = False


class LocalAttestation(StrEnum):
    """Whether the local executor identity binds this report's evidence.

    Spelled as an argument rather than inferred, so that the one condition
    separating a P1 report from an ungraded one is visible at the call site
    that knows the answer.
    """

    #: No identity has sealed anything. What this build does today.
    UNATTESTED = "unattested"

    #: Every receipt and the report travel in signed envelopes under the
    #: participant's own Ed25519 key, and the public key travels with them.
    #: WP7c, decisions document 0005 section 3.4.
    LOCAL_ED25519 = "local_ed25519"


# ---------------------------------------------------------------------------
# Pairing
# ---------------------------------------------------------------------------


def pair_task_rewards(
    *,
    baseline_receipts: Sequence[EpisodeReceipt],
    candidate_receipts: Sequence[EpisodeReceipt],
    ordered_task_hashes: Sequence[Digest],
    reward_name: str,
) -> list[TaskDelta]:
    """Join the two variants by task hash and return rows in TasksetLock order."""
    committed = list(ordered_task_hashes)
    if not committed:
        raise VerificationError(
            "a comparison covers at least one committed task, and this one covers none",
            code=TASK_MEMBERSHIP_MISMATCH,
            details={"task_count": 0},
        )
    if len(set(committed)) != len(committed):
        raise VerificationError(
            "the committed membership names the same task twice, so a pair "
            "could be built from either of two receipts",
            code=TASK_MEMBERSHIP_MISMATCH,
            details={"task_count": len(committed)},
        )

    baseline = _rewards_by_task(baseline_receipts, reward_name, committed, "baseline")
    candidate = _rewards_by_task(
        candidate_receipts, reward_name, committed, "candidate"
    )

    return [
        TaskDelta(
            task_hash=task_hash,
            baseline_reward=baseline[task_hash],
            candidate_reward=candidate[task_hash],
            delta=candidate[task_hash] - baseline[task_hash],
        )
        for task_hash in committed
    ]


def _rewards_by_task(
    receipts: Sequence[EpisodeReceipt],
    reward_name: str,
    committed: Sequence[Digest],
    label: str,
) -> dict[Digest, float]:
    """Read one variant's primary reward per task, refusing anything ambiguous."""
    rewards: dict[Digest, float] = {}
    for receipt in receipts:
        traces = receipt.named_traces.get(SUBJECT_AGENT, [])
        if len(traces) != 1:
            raise VerificationError(
                f"a {label} receipt carries {len(traces)} subject traces; one "
                "episode has exactly one",
                code=TASK_MEMBERSHIP_MISMATCH,
                details={"task_hash": receipt.task_hash, "traces": len(traces)},
            )
        if receipt.task_hash in rewards:
            raise VerificationError(
                f"the {label} variant scored task {receipt.task_hash} twice, so "
                "one of the two rewards would have to be discarded",
                code=TASK_MEMBERSHIP_MISMATCH,
                details={"variant": label, "task_hash": receipt.task_hash},
            )
        reward = traces[0].rewards.get(reward_name)
        if reward is None:
            raise VerificationError(
                f"a {label} receipt records no {reward_name!r} reward, which is "
                "the reward this comparison is decided on",
                code=REWARD_MISSING,
                details={"task_hash": receipt.task_hash, "reward": reward_name},
            )
        _require_finite(reward, label, receipt.task_hash)
        rewards[receipt.task_hash] = reward

    missing: list[JsonValue] = [value for value in committed if value not in rewards]
    unexpected: list[JsonValue] = [
        value for value in sorted(set(rewards) - set(committed))
    ]
    if missing or unexpected:
        raise VerificationError(
            f"the {label} variant scored a different set of tasks than the "
            "Campaign commits to",
            code=TASK_MEMBERSHIP_MISMATCH,
            details={"variant": label, "missing": missing, "unexpected": unexpected},
        )
    return rewards


def _require_finite(value: float, label: str, task_hash: Digest) -> None:
    """Refuse a reward that cannot be averaged or canonically written down."""
    if math.isfinite(value):
        return
    raise VerificationError(
        f"the {label} reward recorded for task {task_hash} is not finite, so it "
        "is not a measurement",
        code=REWARD_NON_FINITE,
        details={"variant": label, "task_hash": task_hash, "value": repr(value)},
    )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def aggregate_primary_result(
    deltas: Sequence[TaskDelta], reward_name: str
) -> PrimaryUpliftResult:
    """Compute the headline result from the paired rows and nothing else."""
    if not deltas:
        raise VerificationError(
            "an uplift result summarizes at least one paired task",
            code=TASK_MEMBERSHIP_MISMATCH,
            details={"reward": reward_name, "task_count": 0},
        )
    for delta in deltas:
        _require_finite(delta.baseline_reward, "baseline", delta.task_hash)
        _require_finite(delta.candidate_reward, "candidate", delta.task_hash)

    baseline_mean = _mean(delta.baseline_reward for delta in deltas)
    candidate_mean = _mean(delta.candidate_reward for delta in deltas)
    absolute = candidate_mean - baseline_mean
    for value, label in (
        (baseline_mean, "baseline mean"),
        (candidate_mean, "candidate mean"),
        (absolute, "absolute delta"),
    ):
        if not math.isfinite(value):
            raise VerificationError(
                f"the {label} over these rewards is not a finite number",
                code=REWARD_NON_FINITE,
                details={"reward": reward_name, "task_count": len(deltas)},
            )

    return PrimaryUpliftResult(
        reward_name=reward_name,
        baseline_mean=baseline_mean,
        candidate_mean=candidate_mean,
        absolute_delta=absolute,
        # Section 7.10: null over a zero baseline. Any number here would be an
        # invented one.
        relative_delta=None if baseline_mean == 0.0 else absolute / baseline_mean,
        wins=sum(
            1 for delta in deltas if delta.candidate_reward > delta.baseline_reward
        ),
        losses=sum(
            1 for delta in deltas if delta.candidate_reward < delta.baseline_reward
        ),
        ties=sum(
            1 for delta in deltas if delta.candidate_reward == delta.baseline_reward
        ),
    )


def _mean(values: Iterable[float]) -> float:
    collected = list(values)
    return sum(collected) / len(collected)


# ---------------------------------------------------------------------------
# The verdict
# ---------------------------------------------------------------------------


def decide_uplift(
    *,
    campaign: CampaignSpec,
    comparison: RealComparisonResult,
    primary: PrimaryUpliftResult,
) -> UpliftDecision:
    """Apply the Campaign's own acceptance rules, and no others.

    ``inconclusive`` is reached when the Campaign predeclared no rule that can
    decide: a scoring contract that neither requires the candidate to out-score
    the baseline nor sets a minimum delta would accept a regression, so calling
    such a result "accepted" would report a verdict nobody specified.
    """
    if not comparison.controlled:
        return UpliftDecision.INVALID

    scoring = campaign.scoring
    if not scoring.require_candidate_above_baseline and (
        scoring.minimum_absolute_delta == 0.0
    ):
        return UpliftDecision.INCONCLUSIVE
    if scoring.require_candidate_above_baseline and primary.absolute_delta <= 0.0:
        return UpliftDecision.REJECTED
    if primary.absolute_delta < scoring.minimum_absolute_delta:
        return UpliftDecision.REJECTED
    return UpliftDecision.ACCEPTED


def summarize_receipts(
    baseline_receipts: Sequence[EpisodeReceipt],
    candidate_receipts: Sequence[EpisodeReceipt],
) -> tuple[ScoreStatus, EvidenceStatus]:
    """Return the score and evidence statuses the whole comparison carries.

    A comparison is only as good as its weakest receipt. One rollout whose
    scoring errored makes the aggregate score invalid rather than making the
    other rollouts' scores worth less, and one receipt whose evidence is
    partial makes the comparison's evidence partial.
    """
    receipts = [*baseline_receipts, *candidate_receipts]
    if not receipts:
        return ScoreStatus.MISSING, EvidenceStatus.NOT_COLLECTED

    score = (
        ScoreStatus.VALID
        if all(receipt.score_status is ScoreStatus.VALID for receipt in receipts)
        else ScoreStatus.INVALID
    )
    evidence = (
        EvidenceStatus.COMPLETE
        if all(
            receipt.evidence_status is EvidenceStatus.COMPLETE for receipt in receipts
        )
        else EvidenceStatus.PARTIAL
    )
    return score, evidence


def proof_grade_for(
    *,
    attestation: LocalAttestation,
    comparison: ComparisonStatus,
    score: ScoreStatus,
) -> Literal["development_only", "P1"]:
    """Return the strongest grade this report is entitled to claim.

    Decisions document 0005 section 3.4. The signature conditions are the
    caller's to establish and are summarized by ``attestation``; the two
    conditions this function can check itself are checked here, so a signed
    report over an uncontrolled comparison still cannot claim P1.
    """
    controlled = comparison in (
        ComparisonStatus.CONTROLLED,
        ComparisonStatus.CONTROLLED_WITH_WARNINGS,
    )
    if (
        attestation is LocalAttestation.LOCAL_ED25519
        and controlled
        and score is ScoreStatus.VALID
    ):
        return "P1"
    return "development_only"


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


def build_uplift_report(
    *,
    run_request: RunRequest,
    campaign: CampaignSpec,
    taskset_validation_receipt_digest: Digest,
    baseline_manifest: ExperimentManifest,
    candidate_manifest: ExperimentManifest,
    baseline_receipt_set: ReceiptSetManifest,
    candidate_receipt_set: ReceiptSetManifest,
    comparison: RealComparisonResult,
    task_deltas: Sequence[TaskDelta],
    primary: PrimaryUpliftResult,
    score: ScoreStatus,
    evidence: EvidenceStatus,
    attestation: LocalAttestation,
    created_at: datetime,
) -> UpliftReport:
    """Construct the canonical real local report, or refuse to construct one.

    Two conditions are refusals rather than statuses. A comparison that is not
    controlled did not measure the Skill, and a score that is not valid did not
    measure anything; in both cases spec section 7.10's decision is ``invalid``,
    and the frozen model has no way to carry that verdict without also claiming
    the P1 grade that decisions document 0005 forbids an uncontrolled
    comparison. A report saying "invalid" is worth less than a run that failed
    with the reason, so the reason is raised.

    ``score`` and ``evidence`` are passed in rather than derived from the
    receipt sets, which commit to receipts by digest and hold no statuses;
    :func:`summarize_receipts` computes them from the receipts themselves.
    """
    _require_reportable(comparison, score, run_request)
    _require_lineage(
        run_request=run_request,
        campaign=campaign,
        baseline_manifest=baseline_manifest,
        candidate_manifest=candidate_manifest,
        baseline_receipt_set=baseline_receipt_set,
        candidate_receipt_set=candidate_receipt_set,
        comparison=comparison,
    )

    grade = proof_grade_for(
        attestation=attestation, comparison=comparison.status, score=score
    )
    decision = (
        decide_uplift(campaign=campaign, comparison=comparison, primary=primary)
        if grade == "P1"
        # An unsigned real report withholds the verdict rather than presenting
        # one the frozen model would have to grade P1. See the module docstring.
        else UpliftDecision.DEVELOPMENT_ONLY
    )

    return UpliftReport(
        schema_version=UPLIFT_SCHEMA_VERSION,
        id=new_id("uplift"),
        run_id=run_request.run_id,
        campaign_spec_digest=run_request.campaign_spec_digest,
        program_ref=run_request.program_ref,
        public_context=run_request.public_context,
        data_policy_digest=run_request.data_policy_digest,
        outcome_contract_digest=run_request.outcome_contract_digest,
        evaluation_backend=campaign.evaluation_backend,
        taskset_validation_receipt_digest=taskset_validation_receipt_digest,
        baseline_manifest_digest=run_request.baseline_manifest_digest,
        candidate_manifest_digest=run_request.candidate_manifest_digest,
        statuses=UpliftStatuses(
            # A report is only built for an execution that finished both
            # variants; a partial one fails the run instead (spec 6.17).
            execution=ExecutionStatus.COMPLETED,
            score=score,
            evidence=evidence,
            comparison=comparison.status,
            # Nothing was uploaded and nothing could have been: this push has
            # no publication path at all, which is "not requested" rather than
            # "blocked by a policy". Spec section 7.10.
            publication=PublicationStatus.NOT_REQUESTED,
        ),
        manifest_comparison=comparison.manifest_comparison,
        primary_result=primary,
        task_deltas=list(task_deltas),
        decision=decision,
        proof_grade=grade,
        publication_eligible=_PUBLICATION_ELIGIBLE,
        created_at=created_at,
    )


def _require_reportable(
    comparison: RealComparisonResult, score: ScoreStatus, run_request: RunRequest
) -> None:
    """Refuse to write a report over evidence that decided nothing."""
    if not comparison.controlled:
        raise VerificationError(
            "this run's two variants were not one controlled experiment, so "
            "there is no uplift to report: "
            + "; ".join(check.detail for check in comparison.failures),
            code=COMPARISON_INVALID,
            details={
                "run_id": run_request.run_id,
                "comparison": comparison.status.value,
                "failed_checks": [check.id for check in comparison.failures],
            },
        )
    if score is not ScoreStatus.VALID:
        raise VerificationError(
            f"this run's recorded scores are {score.value}, so the comparison "
            "measured nothing that may be reported",
            code=COMPARISON_INVALID,
            details={"run_id": run_request.run_id, "score": score.value},
        )


def _require_lineage(
    *,
    run_request: RunRequest,
    campaign: CampaignSpec,
    baseline_manifest: ExperimentManifest,
    candidate_manifest: ExperimentManifest,
    baseline_receipt_set: ReceiptSetManifest,
    candidate_receipt_set: ReceiptSetManifest,
    comparison: RealComparisonResult,
) -> None:
    """Require every object the report cites to belong to the same run.

    The receipt sets are inputs to this check rather than fields of the report:
    the frozen report has nowhere to carry a receipt-set digest, and what it can
    still do is refuse to summarize receipts that belong to a different run,
    variant or manifest.
    """
    campaign_digest = digest_object(campaign)
    for label, expected, found in (
        ("Campaign", run_request.campaign_spec_digest, campaign_digest),
        (
            "baseline manifest",
            run_request.baseline_manifest_digest,
            digest_object(baseline_manifest),
        ),
        (
            "candidate manifest",
            run_request.candidate_manifest_digest,
            digest_object(candidate_manifest),
        ),
        (
            "DataPolicy",
            run_request.data_policy_digest,
            campaign.data_policy_digest,
        ),
    ):
        if expected != found:
            raise VerificationError(
                f"the {label} this report would cite is not the one the run's "
                "request names",
                code=COMPARISON_INVALID,
                details={
                    "run_id": run_request.run_id,
                    "expected": expected,
                    "found": found,
                },
            )

    committed = list(comparison.ordered_task_hashes)
    for manifest_set, variant, manifest_digest in (
        (
            baseline_receipt_set,
            ExperimentVariant.BASELINE,
            run_request.baseline_manifest_digest,
        ),
        (
            candidate_receipt_set,
            ExperimentVariant.CANDIDATE,
            run_request.candidate_manifest_digest,
        ),
    ):
        if (
            manifest_set.run_id == run_request.run_id
            and manifest_set.variant is variant
            and manifest_set.experiment_manifest_digest == manifest_digest
            and manifest_set.receipt_count == len(committed)
            and manifest_set.task_membership_digest == membership_digest(committed)
        ):
            continue
        raise VerificationError(
            f"the {variant.value} receipt set does not commit to this run's "
            f"{variant.value} receipts",
            code=COMPARISON_INVALID,
            details={
                "run_id": run_request.run_id,
                "variant": variant.value,
                "receipt_set_run_id": manifest_set.run_id,
                "receipt_count": manifest_set.receipt_count,
                "committed": len(committed),
            },
        )
