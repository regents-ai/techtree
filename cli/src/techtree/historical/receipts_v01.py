"""The v0.1 receipt arithmetic, kept beside the v0.1 verifier that needs it.

:mod:`techtree.historical.verify_v01` re-derives a v0.1 proof's result from
its receipts, and that recomputation is only meaningful if it is the one the
v0.1 release ran. The live modules these functions came from now speak the
v0.2 receipt, so the v0.1 forms live here: the same bodies, over the frozen
``EpisodeReceipt``, and nothing else. Nothing here is reached by a v0.2 write
path.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from typing import Literal

from techtree.canonical import digest_object, validate_digest
from techtree.errors import VerificationError
from techtree.models.base import Digest, JsonValue, ObjectEnvelope
from techtree.models.campaign import SUBJECT_AGENT
from techtree.models.episode_receipt import EpisodeReceipt
from techtree.models.experiment import ExperimentVariant
from techtree.models.uplift_report import (
    PrimaryUpliftResult,
    PublicationStatus,
    TaskDelta,
)
from techtree.receipts.episode import (
    EPISODE_COUNT_MISMATCH,
    REWARD_MISSING,
    REWARD_NON_FINITE,
    TASK_MEMBERSHIP_MISMATCH,
)
from techtree.receipts.set import (
    RECEIPT_SET_INVALID,
    RECEIPT_SET_SCHEMA_VERSION,
    ReceiptSetManifest,
)
from techtree.tasksets.membership import membership_digest

__all__ = [
    "aggregate_primary_result",
    "pair_task_rewards",
    "publication_eligible_for",
    "verify_receipt_set",
]


# ---------------------------------------------------------------------------
# Pairing and aggregation
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


def publication_eligible_for(
    *,
    grade: Literal["development_only", "P1"],
    publication: PublicationStatus,
) -> bool:
    """Return whether a v0.1 report may claim to be publishable at all."""
    return grade == "P1" and publication is not PublicationStatus.BLOCKED


# ---------------------------------------------------------------------------
# The receipt-set commitment
# ---------------------------------------------------------------------------


def verify_receipt_set(
    *,
    manifest: ReceiptSetManifest,
    signed_receipts: Sequence[ObjectEnvelope[EpisodeReceipt]],
    ordered_task_hashes: Sequence[Digest],
) -> None:
    """Verify order, count, payload digests and task membership, or refuse.

    Everything is recomputed from the receipts. A recorded value is never
    compared against itself, which is the only way this can detect a receipt
    that was edited after the manifest was written.
    """
    rebuilt = _build_receipt_set(
        run_id=manifest.run_id,
        variant=manifest.variant,
        experiment_manifest_digest=manifest.experiment_manifest_digest,
        signed_receipts=signed_receipts,
        ordered_task_hashes=ordered_task_hashes,
    )
    if rebuilt == manifest:
        return
    raise VerificationError(
        "this receipt set does not commit to the receipts it was given; one of "
        "them, or the manifest itself, changed after it was written",
        code=RECEIPT_SET_INVALID,
        details={
            "run_id": manifest.run_id,
            "variant": manifest.variant.value,
            "recorded": _digest_detail(manifest.ordered_receipt_digests),
            "recomputed": _digest_detail(rebuilt.ordered_receipt_digests),
        },
    )


def _build_receipt_set(
    *,
    run_id: str,
    variant: ExperimentVariant,
    experiment_manifest_digest: Digest,
    signed_receipts: Sequence[ObjectEnvelope[EpisodeReceipt]],
    ordered_task_hashes: Sequence[Digest],
) -> ReceiptSetManifest:
    """Order receipts by TasksetLock membership and build the commitment."""
    committed = [validate_digest(value) for value in ordered_task_hashes]
    by_task = _envelopes_by_task(
        signed_receipts,
        committed=committed,
        run_id=run_id,
        variant=variant,
        experiment_manifest_digest=experiment_manifest_digest,
    )
    return ReceiptSetManifest(
        schema_version=RECEIPT_SET_SCHEMA_VERSION,
        run_id=run_id,
        variant=variant,
        experiment_manifest_digest=validate_digest(experiment_manifest_digest),
        ordered_receipt_digests=[
            by_task[task_hash].payload_digest for task_hash in committed
        ],
        task_membership_digest=membership_digest(committed),
        receipt_count=len(committed),
    )


def _envelopes_by_task(
    signed_receipts: Sequence[ObjectEnvelope[EpisodeReceipt]],
    *,
    committed: Sequence[Digest],
    run_id: str,
    variant: ExperimentVariant,
    experiment_manifest_digest: Digest,
) -> dict[Digest, ObjectEnvelope[EpisodeReceipt]]:
    """Index one variant's sealed receipts by the task each one scored."""
    if len(signed_receipts) != len(committed):
        raise VerificationError(
            f"the {variant.value} receipt set was given {len(signed_receipts)} "
            f"receipts for {len(committed)} committed tasks",
            code=EPISODE_COUNT_MISMATCH,
            details={
                "variant": variant.value,
                "receipts": len(signed_receipts),
                "committed": len(committed),
            },
        )

    by_task: dict[Digest, ObjectEnvelope[EpisodeReceipt]] = {}
    for envelope in signed_receipts:
        receipt = envelope.payload
        _require_sealed(envelope)
        _require_belongs(
            receipt,
            run_id=run_id,
            variant=variant,
            experiment_manifest_digest=experiment_manifest_digest,
        )
        task_hash = validate_digest(receipt.task_hash)
        if task_hash in by_task:
            raise VerificationError(
                f"two {variant.value} receipts claim task {task_hash}",
                code=TASK_MEMBERSHIP_MISMATCH,
                details={"variant": variant.value, "task_hash": task_hash},
            )
        by_task[task_hash] = envelope

    missing: list[JsonValue] = [value for value in committed if value not in by_task]
    unexpected: list[JsonValue] = [
        value for value in sorted(set(by_task) - set(committed))
    ]
    if missing or unexpected:
        raise VerificationError(
            f"the {variant.value} receipts do not cover the tasks the Campaign "
            "commits to",
            code=TASK_MEMBERSHIP_MISMATCH,
            details={
                "variant": variant.value,
                "missing": missing,
                "unexpected": unexpected,
            },
        )
    return by_task


def _require_sealed(envelope: ObjectEnvelope[EpisodeReceipt]) -> None:
    """Require an envelope's digest to describe the payload it carries."""
    computed = digest_object(envelope.payload)
    if computed == envelope.payload_digest:
        return
    raise VerificationError(
        "a receipt no longer matches the digest it was sealed under, so it was "
        "changed after it was written",
        code=RECEIPT_SET_INVALID,
        details={
            "receipt_id": envelope.payload.id,
            "sealed": envelope.payload_digest,
            "computed": computed,
        },
    )


def _require_belongs(
    receipt: EpisodeReceipt,
    *,
    run_id: str,
    variant: ExperimentVariant,
    experiment_manifest_digest: Digest,
) -> None:
    """Require a receipt to belong to the run, variant and manifest committed to."""
    if (
        receipt.run_id == run_id
        and receipt.variant is variant
        and receipt.experiment_manifest_digest == experiment_manifest_digest
    ):
        return
    raise VerificationError(
        "a receipt from a different run, variant or experiment manifest cannot "
        "join this receipt set",
        code=RECEIPT_SET_INVALID,
        details={
            "receipt_id": receipt.id,
            "run_id": receipt.run_id,
            "variant": receipt.variant.value,
            "experiment_manifest_digest": receipt.experiment_manifest_digest,
        },
    )


def _digest_detail(digests: Sequence[Digest]) -> list[JsonValue]:
    """Return a digest list in the shape typed error details carry."""
    return [value for value in digests]
