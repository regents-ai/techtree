"""The development executor, and why nothing it produces is evidence.
Spec PR8 §8.6.

The product loop — prepare, start, detach, watch, cancel, read a result — has
to be finished and trustworthy long before there is a real evaluation behind
it. This executor is what makes that possible: it walks every phase, writes
every artifact, and produces a complete, structurally valid
:class:`~techtree.models.uplift_report.UpliftReport` without calling a model,
starting a container, or running a Verifiers evaluation.

The numbers in that report are invented. Everything in this module is arranged
so that no reader, human or machine, can mistake them for measurements:

* Every receipt reports ``execution_backend = "fake"``, and the frozen model
  refuses such a receipt unless its score and evidence statuses are both
  ``development_only``.
* Every receipt's subject runtime is ``not_executed``, because none was.
* The report's decision and proof grade are ``development_only``, its
  publication status is ``blocked``, and it is not publication eligible. The
  frozen model refuses any other combination.
* The traces are :class:`FakeTracePayload` documents under ``fake/``, which is
  a local development shape and deliberately not a Verifiers Trace.

What *is* real is every check around the numbers. The staged inputs are
verified, the validation provider is consulted and its answer checked, the
receipt count and order are re-read from disk and required to match the
Campaign's committed membership, the manifest comparison is recomputed from
the staged manifests and required to equal the prepared one, and the
aggregation joins the two variants by task hash rather than by file order. A
real executor replacing this one keeps all of that and changes only where the
rewards come from.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime
from typing import Final, Literal

from techtree.canonical import canonical_json_bytes, digest_object, sha256_digest_bytes
from techtree.constants import EPISODE_RECEIPT_SCHEMA_VERSION, UPLIFT_SCHEMA_VERSION
from techtree.errors import ValidationError, VerificationError
from techtree.ids import new_id
from techtree.manifests.compare import assert_controlled_comparison, compare_manifests
from techtree.models.base import ArtifactRef, Digest, JsonValue, ProtocolModel
from techtree.models.episode_receipt import (
    EpisodeReceipt,
    EvidenceStatus,
    NamedTraceReceipt,
    ScoreStatus,
    SubjectRuntimeReceipt,
)
from techtree.models.evaluation_backend import SUPPORTED_EVALUATION_BACKEND_KINDS
from techtree.models.experiment import ExperimentVariant, ManifestComparison
from techtree.models.run import RunPhase, RunRequest
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
from techtree.runs.artifacts import RunInputBundle
from techtree.runs.events import (
    DETAIL_CURRENT,
    DETAIL_LABEL,
    DETAIL_RESULT_DIGEST,
    DETAIL_TOTAL,
    PROGRESS_UPDATED,
    RUN_COMPLETED,
)
from techtree.runs.executor import (
    ExecutionContext,
    interruptible_sleep,
    raise_if_cancel_requested,
)
from techtree.runs.validation import TasksetValidationOutcome

__all__ = [
    "FAKE_RECEIPT_INVALID",
    "FAKE_REPORT_INVALID",
    "FAKE_TRACE_SCHEMA_VERSION",
    "SUBJECT_TRACE_ROLE",
    "FakeRunExecutor",
    "FakeTracePayload",
    "aggregate_fake_results",
    "build_development_uplift_report",
    "build_fake_episode_receipt",
    "default_fake_rewards",
]

#: Stable error codes. Spec PR8 §8.16.
FAKE_RECEIPT_INVALID: Final = "fake_receipt_invalid"
FAKE_REPORT_INVALID: Final = "fake_report_invalid"

#: A local development artifact, not a Verifiers Trace. The name says v1 with
#: no ``alpha`` because it is not a protocol object and will never be
#: negotiated with anyone.
FAKE_TRACE_SCHEMA_VERSION: Final = "techtree.fake-trace.v1"

#: The one named trace role a v0.1 episode carries.
SUBJECT_TRACE_ROLE: Final = "subject"

#: What a fake success and a fake failure score. Two values, so that a delta
#: exists at all; no scientific meaning attaches to either.
_SUCCESS_REWARD: Final = 1.0
_FAILURE_REWARD: Final = 0.0

#: Fractions of the taskset the two variants "succeed" on, before the rule
#: that a candidate must out-score a baseline is applied.
_BASELINE_SUCCESS_FRACTION: Final = 0.25
_CANDIDATE_SUCCESS_FRACTION: Final = 0.85

#: How many hexadecimal characters a derived identifier carries, matching the
#: 32 that :mod:`techtree.ids` issues.
_DERIVED_ID_LENGTH: Final = 32


class FakeTracePayload(ProtocolModel):
    """One invented episode's trace. A development artifact, never evidence."""

    schema_version: Literal["techtree.fake-trace.v1"]
    run_id: str
    variant: ExperimentVariant
    position: int
    task_hash: Digest
    reward_name: str
    reward: float


# ---------------------------------------------------------------------------
# Reward vectors
# ---------------------------------------------------------------------------


def default_fake_rewards(task_count: int) -> tuple[list[float], list[float]]:
    """Return the baseline and candidate reward vectors for a taskset.

    Successes occupy the first positions so that a fixture is deterministic
    and a failing assertion is readable. The positions carry no meaning: the
    tasks are not ordered by difficulty, and nothing about task *n* makes it
    the one a baseline gets right.
    """
    if task_count < 0:
        raise ValidationError(
            f"a taskset does not have {task_count} tasks",
            code=FAKE_RECEIPT_INVALID,
            details={"task_count": task_count},
        )
    if task_count == 0:
        return [], []

    baseline_successes = max(math.floor(task_count * _BASELINE_SUCCESS_FRACTION), 1)
    candidate_successes = min(
        max(
            math.floor(task_count * _CANDIDATE_SUCCESS_FRACTION),
            baseline_successes + 1,
        ),
        task_count,
    )
    return (
        _reward_vector(task_count, baseline_successes),
        _reward_vector(task_count, candidate_successes),
    )


def _reward_vector(task_count: int, successes: int) -> list[float]:
    return [
        _SUCCESS_REWARD if position < successes else _FAILURE_REWARD
        for position in range(task_count)
    ]


# ---------------------------------------------------------------------------
# Receipts
# ---------------------------------------------------------------------------


def build_fake_episode_receipt(
    *,
    request: RunRequest,
    inputs: RunInputBundle,
    variant: ExperimentVariant,
    position: int,
    task_hash: Digest,
    reward: float,
    trace_artifact: ArtifactRef,
) -> EpisodeReceipt:
    """Build one receipt carrying every generic Campaign reference exactly.

    Nothing here is derived, defaulted, or re-resolved: the Campaign, the
    improvement program, the public context, the DataPolicy, and the
    OutcomeContract all come from the immutable request, and the evaluation
    backend from the Campaign this run owns. A future real executor writes the
    same fields from the same places.
    """
    campaign = inputs.campaign
    if campaign.evaluation_backend != request.evaluation_backend:
        raise VerificationError(
            "the Campaign this run owns names a different evaluation backend "
            "than the run's request",
            code=FAKE_RECEIPT_INVALID,
            details={"run_id": request.run_id},
        )

    trace_digest = trace_artifact.digest
    episode_digest = _episode_digest(
        run_id=request.run_id,
        variant=variant,
        position=position,
        task_hash=task_hash,
        trace_digest=trace_digest,
    )

    return EpisodeReceipt(
        schema_version=EPISODE_RECEIPT_SCHEMA_VERSION,
        id=_derived_id("receipt", episode_digest),
        run_id=request.run_id,
        campaign_spec_digest=request.campaign_spec_digest,
        program_ref=request.program_ref,
        public_context=request.public_context,
        data_policy_digest=request.data_policy_digest,
        outcome_contract_digest=request.outcome_contract_digest,
        evaluation_backend=campaign.evaluation_backend,
        # No subject ran. Anything else here would be the single most
        # misleading field a fake receipt could carry.
        subject_runtime=SubjectRuntimeReceipt(kind="not_executed"),
        variant=variant,
        experiment_manifest_digest=_manifest_digest(request, variant),
        episode_id=_derived_id("episode", episode_digest),
        episode_digest=episode_digest,
        task_hash=task_hash,
        named_traces={
            SUBJECT_TRACE_ROLE: [
                NamedTraceReceipt(
                    role=SUBJECT_TRACE_ROLE,
                    trace_id=_derived_id("trace", trace_digest),
                    trace_digest=trace_digest,
                    task_hash=task_hash,
                    rewards={campaign.scoring.primary_reward: reward},
                    metrics={},
                    ok=True,
                )
            ]
        },
        score_status=ScoreStatus.DEVELOPMENT_ONLY,
        evidence_status=EvidenceStatus.DEVELOPMENT_ONLY,
        execution_backend="fake",
        artifacts=[trace_artifact],
    )


def _manifest_digest(request: RunRequest, variant: ExperimentVariant) -> Digest:
    if variant is ExperimentVariant.BASELINE:
        return request.baseline_manifest_digest
    return request.candidate_manifest_digest


def _episode_digest(
    *,
    run_id: str,
    variant: ExperimentVariant,
    position: int,
    task_hash: Digest,
    trace_digest: Digest,
) -> Digest:
    """Return a content digest for one invented episode."""
    return sha256_digest_bytes(
        canonical_json_bytes(
            {
                "run_id": run_id,
                "variant": variant.value,
                "position": position,
                "task_hash": task_hash,
                "trace_digest": trace_digest,
            }
        )
    )


def _derived_id(prefix: str, digest: Digest) -> str:
    """Return a deterministic identifier in the shape ids.py issues."""
    _, _, hexadecimal = digest.partition(":")
    return f"{prefix}_{hexadecimal[:_DERIVED_ID_LENGTH]}"


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def aggregate_fake_results(
    *,
    reward_name: str,
    baseline: Sequence[EpisodeReceipt],
    candidate: Sequence[EpisodeReceipt],
    ordered_task_hashes: Sequence[Digest],
) -> tuple[PrimaryUpliftResult, list[TaskDelta]]:
    """Join the two variants by task hash and compute the headline result.

    The join is by task hash and never by position in a list. Two variants
    that happened to write their receipts in different orders would still be
    compared task for task, and a variant missing a task is a failure rather
    than a shorter list.
    """
    baseline_rewards = _rewards_by_task(baseline, reward_name, "baseline")
    candidate_rewards = _rewards_by_task(candidate, reward_name, "candidate")
    committed = list(ordered_task_hashes)

    _require_membership(baseline_rewards.keys(), committed, "baseline")
    _require_membership(candidate_rewards.keys(), committed, "candidate")

    deltas = [
        TaskDelta(
            task_hash=task_hash,
            baseline_reward=baseline_rewards[task_hash],
            candidate_reward=candidate_rewards[task_hash],
            delta=candidate_rewards[task_hash] - baseline_rewards[task_hash],
        )
        for task_hash in committed
    ]

    baseline_mean = _mean(delta.baseline_reward for delta in deltas)
    candidate_mean = _mean(delta.candidate_reward for delta in deltas)
    absolute = candidate_mean - baseline_mean

    return (
        PrimaryUpliftResult(
            reward_name=reward_name,
            baseline_mean=baseline_mean,
            candidate_mean=candidate_mean,
            absolute_delta=absolute,
            # A relative improvement over nothing is not a number, and
            # reporting zero or infinity would each be a different lie.
            relative_delta=None if baseline_mean == 0.0 else absolute / baseline_mean,
            wins=sum(1 for delta in deltas if delta.delta > 0),
            losses=sum(1 for delta in deltas if delta.delta < 0),
            ties=sum(1 for delta in deltas if delta.delta == 0),
        ),
        deltas,
    )


def _rewards_by_task(
    receipts: Sequence[EpisodeReceipt],
    reward_name: str,
    label: str,
) -> dict[Digest, float]:
    rewards: dict[Digest, float] = {}
    for receipt in receipts:
        traces = receipt.named_traces.get(SUBJECT_TRACE_ROLE, [])
        if len(traces) != 1:
            raise VerificationError(
                f"a {label} receipt carries {len(traces)} subject traces; one "
                "episode has exactly one",
                code=FAKE_RECEIPT_INVALID,
                details={"task_hash": receipt.task_hash},
            )
        trace = traces[0]
        if trace.task_hash != receipt.task_hash:
            raise VerificationError(
                f"a {label} receipt's trace was recorded against a different "
                "task than the receipt",
                code=FAKE_RECEIPT_INVALID,
                details={"task_hash": receipt.task_hash},
            )
        if reward_name not in trace.rewards:
            raise VerificationError(
                f"a {label} receipt records no {reward_name} reward, which is "
                "the reward the Campaign is scored on",
                code=FAKE_RECEIPT_INVALID,
                details={"task_hash": receipt.task_hash, "reward": reward_name},
            )
        if receipt.task_hash in rewards:
            raise VerificationError(
                f"the {label} variant scored one task twice",
                code=FAKE_RECEIPT_INVALID,
                details={"task_hash": receipt.task_hash},
            )
        rewards[receipt.task_hash] = trace.rewards[reward_name]
    return rewards


def _require_membership(
    scored: Iterable[Digest],
    committed: Sequence[Digest],
    label: str,
) -> None:
    scored_set = set(scored)
    committed_set = set(committed)
    if scored_set == committed_set:
        return
    missing: list[JsonValue] = [item for item in sorted(committed_set - scored_set)]
    unexpected: list[JsonValue] = [item for item in sorted(scored_set - committed_set)]
    raise VerificationError(
        f"the {label} variant scored a different set of tasks than the "
        "Campaign commits to",
        code=FAKE_RECEIPT_INVALID,
        details={"missing": missing, "unexpected": unexpected},
    )


def _mean(values: Iterable[float]) -> float:
    collected = list(values)
    if not collected:
        return 0.0
    return sum(collected) / len(collected)


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


def build_development_uplift_report(
    *,
    request: RunRequest,
    inputs: RunInputBundle,
    validation: TasksetValidationOutcome,
    baseline_receipts: Sequence[EpisodeReceipt],
    candidate_receipts: Sequence[EpisodeReceipt],
    comparison: ManifestComparison,
    created_at: datetime,
) -> UpliftReport:
    """Build the one report a fake run is allowed to produce."""
    primary, deltas = aggregate_fake_results(
        reward_name=inputs.campaign.scoring.primary_reward,
        baseline=baseline_receipts,
        candidate=candidate_receipts,
        ordered_task_hashes=inputs.ordered_task_hashes,
    )

    try:
        return UpliftReport(
            schema_version=UPLIFT_SCHEMA_VERSION,
            id=new_id("uplift"),
            run_id=request.run_id,
            campaign_spec_digest=request.campaign_spec_digest,
            program_ref=request.program_ref,
            public_context=request.public_context,
            data_policy_digest=request.data_policy_digest,
            outcome_contract_digest=request.outcome_contract_digest,
            evaluation_backend=inputs.campaign.evaluation_backend,
            taskset_validation_receipt_digest=digest_object(validation.receipt),
            baseline_manifest_digest=request.baseline_manifest_digest,
            candidate_manifest_digest=request.candidate_manifest_digest,
            statuses=UpliftStatuses(
                # The run really did complete; only what it measured is fake,
                # and the other four statuses are where that is stated.
                execution=ExecutionStatus.COMPLETED,
                score=ScoreStatus.DEVELOPMENT_ONLY,
                evidence=EvidenceStatus.DEVELOPMENT_ONLY,
                comparison=ComparisonStatus.DEVELOPMENT_ONLY,
                publication=PublicationStatus.BLOCKED,
            ),
            manifest_comparison=comparison,
            primary_result=primary,
            task_deltas=deltas,
            decision=UpliftDecision.DEVELOPMENT_ONLY,
            proof_grade="development_only",
            publication_eligible=False,
            created_at=created_at,
        )
    except ValueError as error:
        raise ValidationError(
            f"the development report is not a valid report: {error}",
            code=FAKE_REPORT_INVALID,
            details={"run_id": request.run_id},
        ) from error


# ---------------------------------------------------------------------------
# The executor
# ---------------------------------------------------------------------------


class FakeRunExecutor:
    """Walks a run through every phase without evaluating anything."""

    def __init__(
        self,
        *,
        step_delay_seconds: float = 0.1,
        baseline_rewards: Sequence[float] | None = None,
        candidate_rewards: Sequence[float] | None = None,
    ) -> None:
        if step_delay_seconds < 0:
            raise ValidationError(
                "a step delay is not negative",
                details={"step_delay_seconds": step_delay_seconds},
            )
        self._step_delay = step_delay_seconds
        self._baseline_rewards = (
            None if baseline_rewards is None else list(baseline_rewards)
        )
        self._candidate_rewards = (
            None if candidate_rewards is None else list(candidate_rewards)
        )

    def execute(self, context: ExecutionContext) -> UpliftReport:
        """Execute the full development-only flow."""
        request = context.request
        run_id = request.run_id
        store = context.run_store

        inputs = context.artifact_store.load_inputs(run_id, request)
        self._require_fake_executor(request)
        self._require_supported_backend(inputs)

        def check() -> None:
            raise_if_cancel_requested(store, run_id)

        store.append(run_id, phase=RunPhase.VALIDATING_TASKSET)
        validation = context.validation_provider.validate(run_id=run_id, inputs=inputs)
        context.artifact_store.write_validation_marker(
            run_id, validation.marker_document()
        )
        self._require_valid_validation(inputs, validation)
        check()

        task_hashes = inputs.ordered_task_hashes
        baseline_rewards, candidate_rewards = self._reward_vectors(len(task_hashes))

        store.append(run_id, phase=RunPhase.RUNNING_BASELINE)
        self._score_variant(
            context,
            inputs=inputs,
            variant=ExperimentVariant.BASELINE,
            task_hashes=task_hashes,
            rewards=baseline_rewards,
            check=check,
        )

        store.append(run_id, phase=RunPhase.RUNNING_CANDIDATE)
        self._score_variant(
            context,
            inputs=inputs,
            variant=ExperimentVariant.CANDIDATE,
            task_hashes=task_hashes,
            rewards=candidate_rewards,
            check=check,
        )

        store.append(run_id, phase=RunPhase.BUILDING_RECEIPTS)
        baseline_receipts = context.artifact_store.episode_receipts(
            run_id, ExperimentVariant.BASELINE
        )
        candidate_receipts = context.artifact_store.episode_receipts(
            run_id, ExperimentVariant.CANDIDATE
        )
        self._require_receipts(baseline_receipts, task_hashes, "baseline")
        self._require_receipts(candidate_receipts, task_hashes, "candidate")
        check()

        store.append(run_id, phase=RunPhase.VERIFYING_COMPARISON)
        comparison = self._recompute_comparison(inputs)
        check()

        store.append(run_id, phase=RunPhase.BUILDING_REPORT)
        report = build_development_uplift_report(
            request=request,
            inputs=inputs,
            validation=validation,
            baseline_receipts=baseline_receipts,
            candidate_receipts=candidate_receipts,
            comparison=comparison,
            created_at=context.clock(),
        )
        store.write_result(run_id, report)
        store.append(
            run_id,
            phase=RunPhase.COMPLETED,
            kind=RUN_COMPLETED,
            details={DETAIL_RESULT_DIGEST: digest_object(report)},
        )
        return report

    # -- phases -------------------------------------------------------------

    def _score_variant(
        self,
        context: ExecutionContext,
        *,
        inputs: RunInputBundle,
        variant: ExperimentVariant,
        task_hashes: Sequence[Digest],
        rewards: Sequence[float],
        check: Callable[[], None],
    ) -> None:
        """Invent one reward per committed task, in Campaign order."""
        run_id = context.request.run_id
        reward_name = inputs.campaign.scoring.primary_reward
        total = len(task_hashes)

        for position, task_hash in enumerate(task_hashes):
            check()
            trace = context.artifact_store.write_fake_trace(
                run_id,
                variant=variant,
                position=position,
                payload=FakeTracePayload(
                    schema_version=FAKE_TRACE_SCHEMA_VERSION,
                    run_id=run_id,
                    variant=variant,
                    position=position,
                    task_hash=task_hash,
                    reward_name=reward_name,
                    reward=rewards[position],
                ),
            )
            context.artifact_store.write_episode_receipt(
                run_id,
                position=position,
                receipt=build_fake_episode_receipt(
                    request=context.request,
                    inputs=inputs,
                    variant=variant,
                    position=position,
                    task_hash=task_hash,
                    reward=rewards[position],
                    trace_artifact=trace,
                ),
            )
            # phase=None: cancellation may land between the receipt write and
            # this append, so the store, not this executor, names the phase.
            context.run_store.append(
                run_id,
                phase=None,
                kind=PROGRESS_UPDATED,
                details={
                    DETAIL_CURRENT: position + 1,
                    DETAIL_TOTAL: total,
                    DETAIL_LABEL: f"{variant.value} episodes",
                },
            )
            interruptible_sleep(seconds=self._step_delay, check=check)

    def _recompute_comparison(self, inputs: RunInputBundle) -> ManifestComparison:
        """Recompute the comparison and require it to equal the prepared one."""
        comparison = compare_manifests(
            inputs.baseline,
            inputs.candidate,
            inputs.campaign.mutation_contract,
        )
        assert_controlled_comparison(comparison)
        if comparison != inputs.comparison:
            raise VerificationError(
                "the comparison recomputed from this run's own manifests is "
                "not the comparison the draft was prepared with",
                code=FAKE_REPORT_INVALID,
                details={"run_id": inputs.request.run_id},
            )
        return comparison

    # -- preconditions ------------------------------------------------------

    def _require_fake_executor(self, request: RunRequest) -> None:
        if request.executor_kind != "fake":
            raise ValidationError(
                f"this run asks for a {request.executor_kind} executor, and "
                "this is the fake one",
                code=FAKE_REPORT_INVALID,
                details={"run_id": request.run_id},
            )

    def _require_supported_backend(self, inputs: RunInputBundle) -> None:
        kind = inputs.campaign.evaluation_backend.kind
        if kind not in SUPPORTED_EVALUATION_BACKEND_KINDS:
            raise ValidationError(
                f"this Campaign is evaluated by {kind.value}, which this build "
                "does not run",
                code=FAKE_REPORT_INVALID,
                details={
                    "run_id": inputs.request.run_id,
                    "evaluation_backend": kind.value,
                },
            )

    def _require_valid_validation(
        self,
        inputs: RunInputBundle,
        validation: TasksetValidationOutcome,
    ) -> None:
        """Refuse to score a taskset the provider did not vouch for."""
        if validation.receipt.status != "valid":
            raise VerificationError(
                "the taskset validation this run was given reports "
                f"{validation.receipt.status}, so nothing may be scored on it",
                code=FAKE_REPORT_INVALID,
                details={
                    "run_id": inputs.request.run_id,
                    "status": validation.receipt.status,
                },
            )
        committed = inputs.ordered_task_hashes
        if validation.lock.ordered_task_hashes != committed:
            raise VerificationError(
                "the validated taskset does not hold the tasks the Campaign commits to",
                code=FAKE_REPORT_INVALID,
                details={"run_id": inputs.request.run_id},
            )

    def _require_receipts(
        self,
        receipts: Sequence[EpisodeReceipt],
        task_hashes: Sequence[Digest],
        label: str,
    ) -> None:
        """Require the receipts on disk to be the Campaign's tasks, in order."""
        found = [receipt.task_hash for receipt in receipts]
        if found != list(task_hashes):
            expected_detail: list[JsonValue] = [item for item in task_hashes]
            found_detail: list[JsonValue] = [item for item in found]
            raise VerificationError(
                f"the {label} receipts on disk are not this Campaign's tasks "
                "in the order it commits to them",
                code=FAKE_RECEIPT_INVALID,
                details={"expected": expected_detail, "found": found_detail},
            )

    def _reward_vectors(self, task_count: int) -> tuple[list[float], list[float]]:
        """Return the injected reward vectors, or the default ones."""
        if self._baseline_rewards is None or self._candidate_rewards is None:
            return default_fake_rewards(task_count)

        for label, vector in (
            ("baseline", self._baseline_rewards),
            ("candidate", self._candidate_rewards),
        ):
            if len(vector) != task_count:
                raise ValidationError(
                    f"the injected {label} rewards cover {len(vector)} tasks "
                    f"and this Campaign commits to {task_count}",
                    code=FAKE_RECEIPT_INVALID,
                    details={"task_count": task_count, "rewards": len(vector)},
                )
        return list(self._baseline_rewards), list(self._candidate_rewards)
