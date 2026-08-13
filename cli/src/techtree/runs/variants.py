"""Running both sides of a comparison at once. Spec section 6.15.

A controlled comparison is only as good as the conditions the two variants met,
and the conditions a provider offers drift: queue depth, routing, and a
model's own revision are not constant over the forty minutes an agentic
taskset takes. Running the variants side by side is how that drift is shared
instead of assigned to whichever side went second, and it is why the start
barrier in this module is a scientific control rather than a performance
optimisation.

Three rules follow from it.

*Nothing is verified after the first launch.* Every input either variant needs
is checked before either child starts, because a missing candidate config
discovered after the baseline is already talking to a provider costs the run
its money and its comparability at once.

*Nothing is written between the two launches.* The children are started back to
back and the events that announce them are appended afterwards, so the recorded
skew measures two ``fork`` calls rather than two ``fork`` calls plus a durable
append to a journal.

*One variant's failure ends the other.* A pair is the unit of a comparison. A
baseline that finished cannot be reported against a candidate that did not, so
a failed child causes its sibling to be terminated and the whole pair to fail —
with both children's partial evidence left exactly where they wrote it, because
a failed run is still the only record of what happened.

Cancellation is the same shape and a different meaning: the sibling is
terminated for the same reason, and the run produced no answer rather than a
wrong one.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from techtree.errors import (
    CancellationError,
    RunError,
    TechtreeError,
    ValidationError,
)
from techtree.models.base import JsonValue
from techtree.models.campaign import VariantSchedule
from techtree.models.run import RunPhase, VariantProgress
from techtree.runs.child_registry import (
    ChildRegistry,
    EvaluationChild,
    LaunchedChild,
    write_children_record,
)
from techtree.runs.events import (
    DETAIL_COMPLETED,
    DETAIL_CURRENT,
    DETAIL_ERRORED,
    DETAIL_LABEL,
    DETAIL_RUNNING,
    DETAIL_STATE,
    DETAIL_TOTAL,
    DETAIL_VARIANT,
    PROGRESS_UPDATED,
    VARIANT_COMPLETED,
    VARIANT_PROGRESS,
    VARIANT_STARTED,
)
from techtree.runs.executor import raise_if_cancel_requested
from techtree.runs.store import RunStore
from techtree.verifiers.child import DEFAULT_GRACE_SECONDS
from techtree.verifiers.models import (
    ChildProcessOutcome,
    VariantExecutionPlan,
    VariantName,
)
from techtree.verifiers.outputs import TRACES_FILENAME
from techtree.verifiers.progress import inspect_progress, pending_progress

__all__ = [
    "DEFAULT_POLL_INTERVAL_SECONDS",
    "VARIANT_CHILD_START_FAILED",
    "VARIANT_CONCURRENCY_EXCEEDED",
    "VARIANT_EXECUTION_FAILED",
    "VARIANT_INPUTS_MISSING",
    "LaunchSkew",
    "VariantPair",
    "VariantPairOutcome",
    "VariantScheduler",
    "require_concurrency_budget",
]

#: Stable error codes.
VARIANT_INPUTS_MISSING: Final = "variant_inputs_missing"
VARIANT_CHILD_START_FAILED: Final = "variant_child_start_failed"
VARIANT_EXECUTION_FAILED: Final = "variant_execution_failed"
VARIANT_CONCURRENCY_EXCEEDED: Final = "variant_concurrency_exceeded"

#: How often the scheduler reads both variants' evidence. Spec section 6.15.
DEFAULT_POLL_INTERVAL_SECONDS: Final = 0.25

#: Variants are always addressed in comparison order, never in completion or
#: start order.
_VARIANT_ORDER: Final[tuple[VariantName, ...]] = (
    VariantName.BASELINE,
    VariantName.CANDIDATE,
)

#: What a sequential schedule's progress lines are labelled with.
_EPISODE_LABEL: Final = "{variant} episodes"


# ---------------------------------------------------------------------------
# The pair
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VariantPair:
    """The two plans one comparison executes. Spec section 6.15."""

    baseline: VariantExecutionPlan
    candidate: VariantExecutionPlan

    def __post_init__(self) -> None:
        """Reject a pair that is not one comparison of one taskset."""
        if self.baseline.variant is not VariantName.BASELINE:
            raise ValidationError(
                "the baseline slot holds the baseline plan",
                code=VARIANT_INPUTS_MISSING,
                details={"variant": self.baseline.variant.value},
            )
        if self.candidate.variant is not VariantName.CANDIDATE:
            raise ValidationError(
                "the candidate slot holds the candidate plan",
                code=VARIANT_INPUTS_MISSING,
                details={"variant": self.candidate.variant.value},
            )
        if self.baseline.task_count != self.candidate.task_count:
            raise ValidationError(
                "the two variants of a comparison score the same tasks; this "
                f"pair scores {self.baseline.task_count} against "
                f"{self.candidate.task_count}",
                code=VARIANT_INPUTS_MISSING,
                details={
                    "baseline_task_count": self.baseline.task_count,
                    "candidate_task_count": self.candidate.task_count,
                },
            )

    def plan(self, variant: VariantName) -> VariantExecutionPlan:
        """Return one side's plan."""
        return self.baseline if variant is VariantName.BASELINE else self.candidate

    @property
    def task_count(self) -> int:
        """How many tasks each side scores."""
        return self.baseline.task_count

    @property
    def total_max_concurrent(self) -> int:
        """How many episodes both sides together may have in flight."""
        return self.baseline.max_concurrent + self.candidate.max_concurrent


def require_concurrency_budget(pair: VariantPair, *, max_concurrent: int) -> None:
    """Refuse a pair whose two halves exceed the Campaign's own bound.

    ``max_concurrent`` is Campaign-wide (spec section 3.2), and dividing it is
    :func:`techtree.verifiers.compiler.divide_concurrency`'s job. This is the
    check that the division actually held: granting each side the full
    allowance would double the live subject count the Campaign declared, and a
    Campaign's concurrency bound is a statement about how much of a provider it
    is willing to occupy at once.
    """
    if pair.total_max_concurrent > max_concurrent:
        raise ValidationError(
            f"this pair would run {pair.total_max_concurrent} episodes at once "
            f"and the Campaign permits {max_concurrent}",
            code=VARIANT_CONCURRENCY_EXCEEDED,
            details={
                "campaign_max_concurrent": max_concurrent,
                "baseline_max_concurrent": pair.baseline.max_concurrent,
                "candidate_max_concurrent": pair.candidate.max_concurrent,
            },
        )


# ---------------------------------------------------------------------------
# What one pair's execution produced
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LaunchSkew:
    """How far apart the two children actually started. Spec section 6.15.

    The timestamps are the parent's observation of each launch, taken the
    instant the child's ``start`` returned. ``seconds`` is measured on the
    monotonic clock instead of by subtracting the two timestamps, so a system
    clock adjustment between the launches cannot produce a negative skew or a
    minute-long one.
    """

    baseline_started_at: datetime
    candidate_started_at: datetime
    seconds: float
    first: VariantName


@dataclass(frozen=True)
class VariantPairOutcome:
    """Both children's outcomes, and how far apart they were launched.

    Spec section 6.15 returns the pair of outcomes; the skew rides with them
    because it is a property of the pair rather than of either child, and
    section 6.15 requires the run to record it.
    """

    baseline: ChildProcessOutcome
    candidate: ChildProcessOutcome
    schedule: VariantSchedule
    skew: LaunchSkew | None

    @property
    def outcomes(self) -> tuple[ChildProcessOutcome, ChildProcessOutcome]:
        """Both outcomes, in comparison order."""
        return self.baseline, self.candidate


# ---------------------------------------------------------------------------
# The scheduler
# ---------------------------------------------------------------------------


class VariantScheduler:
    """Starts, watches, and stops the children of one comparison."""

    def __init__(
        self,
        *,
        run_store: RunStore,
        child_registry: ChildRegistry,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        grace_seconds: float = DEFAULT_GRACE_SECONDS,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValidationError(
                "a poller needs a positive interval",
                details={"poll_interval_seconds": poll_interval_seconds},
            )
        self._run_store = run_store
        self._children = child_registry
        self._poll_interval = poll_interval_seconds
        self._grace = grace_seconds
        self._clock = clock or _utc_now

    # -- parallel ----------------------------------------------------------

    def execute_parallel(
        self,
        *,
        run_id: str,
        run_root: Path,
        pair: VariantPair,
        baseline_child: EvaluationChild,
        candidate_child: EvaluationChild,
    ) -> VariantPairOutcome:
        """Run both variants side by side under one ``running_variants`` phase.

        Both children are started before either is polled. If the second cannot
        be started the first is stopped again, because a comparison with one
        live side is not a comparison and the money it would spend buys
        nothing.
        """
        children = {
            VariantName.BASELINE: baseline_child,
            VariantName.CANDIDATE: candidate_child,
        }
        self._require_inputs(pair, children)
        raise_if_cancel_requested(self._run_store, run_id)
        self._run_store.append(run_id, phase=RunPhase.RUNNING_VARIANTS)

        skew = self._start_both(run_id, run_root=run_root, children=children)
        self._announce(run_id, pair, VariantName.BASELINE)
        self._announce(run_id, pair, VariantName.CANDIDATE)

        outcomes = self._watch_both(run_id, pair, children)
        return VariantPairOutcome(
            baseline=outcomes[VariantName.BASELINE],
            candidate=outcomes[VariantName.CANDIDATE],
            schedule=VariantSchedule.PARALLEL,
            skew=skew,
        )

    # -- sequential --------------------------------------------------------

    def execute_sequential(
        self,
        *,
        run_id: str,
        run_root: Path,
        pair: VariantPair,
        baseline_child: EvaluationChild,
        candidate_child: EvaluationChild,
    ) -> VariantPairOutcome:
        """Run one variant and then the other, for a Campaign that asks for it.

        The two sequential phases stay what they have always been and no
        variant event is recorded, because ``variant.started`` and its siblings
        say "both sides are in flight" and here they are not. The inputs are
        still checked as a pair before the first child starts: a candidate
        config that does not exist is worth discovering before the baseline is
        paid for, whichever order they run in.
        """
        children = {
            VariantName.BASELINE: baseline_child,
            VariantName.CANDIDATE: candidate_child,
        }
        self._require_inputs(pair, children)

        outcomes: dict[VariantName, ChildProcessOutcome] = {}
        launched: list[LaunchedChild] = []
        for variant, phase in (
            (VariantName.BASELINE, RunPhase.RUNNING_BASELINE),
            (VariantName.CANDIDATE, RunPhase.RUNNING_CANDIDATE),
        ):
            raise_if_cancel_requested(self._run_store, run_id)
            self._run_store.append(run_id, phase=phase)
            child = children[variant]
            launched.append(self._start_one(run_id, child))
            write_children_record(
                run_root=run_root,
                run_id=run_id,
                schedule=VariantSchedule.SEQUENTIAL,
                children=launched,
                launch_skew_seconds=None,
            )
            outcomes[variant] = self._watch_one(run_id, pair, child)

        return VariantPairOutcome(
            baseline=outcomes[VariantName.BASELINE],
            candidate=outcomes[VariantName.CANDIDATE],
            schedule=VariantSchedule.SEQUENTIAL,
            skew=None,
        )

    # -- the start barrier -------------------------------------------------

    def _require_inputs(
        self,
        pair: VariantPair,
        children: dict[VariantName, EvaluationChild],
    ) -> None:
        """Check every input both variants need, before either child starts."""
        for variant in _VARIANT_ORDER:
            if children[variant].variant is not variant:
                raise ValidationError(
                    f"the {variant.value} slot holds a "
                    f"{children[variant].variant.value} child",
                    code=VARIANT_INPUTS_MISSING,
                    details={"variant": variant.value},
                )
            plan = pair.plan(variant)
            for label, path in (
                ("compiled config", Path(plan.verifiers_input_config_path)),
                ("experiment manifest", Path(plan.experiment_manifest_path)),
            ):
                if not path.is_file():
                    raise ValidationError(
                        f"the {variant.value} variant's {label} is not on disk, "
                        "so neither variant may start",
                        code=VARIANT_INPUTS_MISSING,
                        details={"variant": variant.value, "path": str(path)},
                    )
            for skill in plan.skill_paths:
                if not Path(skill).is_dir():
                    raise ValidationError(
                        f"the {variant.value} variant declares a skill that is "
                        "not staged in the run's own input tree",
                        code=VARIANT_INPUTS_MISSING,
                        details={"variant": variant.value, "path": skill},
                    )
            traces = self._traces_path(plan)
            if traces.exists():
                raise ValidationError(
                    f"the {variant.value} variant's output directory already "
                    "holds evidence; a run writes its own",
                    code=VARIANT_INPUTS_MISSING,
                    details={"variant": variant.value, "path": str(traces)},
                )

    # -- starting ----------------------------------------------------------

    def _start_both(
        self,
        run_id: str,
        *,
        run_root: Path,
        children: dict[VariantName, EvaluationChild],
    ) -> LaunchSkew:
        """Start both children back to back and record how far apart they were."""
        first = self._start_one(run_id, children[VariantName.BASELINE])
        first_monotonic = time.monotonic()
        try:
            second = self._start_one(run_id, children[VariantName.CANDIDATE])
        except BaseException:
            # The pair never existed. Stop the one child that did, so a failed
            # launch does not leave a container talking to a provider.
            self._children.terminate_all(run_id, self._grace)
            raise
        second_monotonic = time.monotonic()

        skew = LaunchSkew(
            baseline_started_at=first.started_at,
            candidate_started_at=second.started_at,
            seconds=max(second_monotonic - first_monotonic, 0.0),
            first=VariantName.BASELINE,
        )
        write_children_record(
            run_root=run_root,
            run_id=run_id,
            schedule=VariantSchedule.PARALLEL,
            children=[first, second],
            launch_skew_seconds=skew.seconds,
        )
        return skew

    def _start_one(self, run_id: str, child: EvaluationChild) -> LaunchedChild:
        """Start one child and register it before anything can fail."""
        try:
            child.start()
        except RunError:
            raise
        except OSError as error:
            raise RunError(
                f"the {child.variant.value} evaluation child could not be "
                f"started: {error.strerror or error}",
                code=VARIANT_CHILD_START_FAILED,
                details={"run_id": run_id, "variant": child.variant.value},
            ) from error
        self._children.register(run_id, child)
        return LaunchedChild(
            variant=child.variant,
            pid=child.pid,
            argv_digest=child.argv_digest,
            started_at=self._clock(),
        )

    # -- watching ----------------------------------------------------------

    def _watch_both(
        self,
        run_id: str,
        pair: VariantPair,
        children: dict[VariantName, EvaluationChild],
    ) -> dict[VariantName, ChildProcessOutcome]:
        """Poll both children until both have ended, or until one fails."""
        reported: dict[VariantName, VariantProgress | None] = {
            variant: None for variant in _VARIANT_ORDER
        }
        exits: dict[VariantName, int] = {}
        outcomes: dict[VariantName, ChildProcessOutcome] = {}

        try:
            while len(outcomes) < len(_VARIANT_ORDER):
                raise_if_cancel_requested(self._run_store, run_id)
                for variant in _VARIANT_ORDER:
                    if variant in outcomes:
                        continue
                    child = children[variant]
                    code = child.poll()
                    progress = self._inspect(pair, variant, code)
                    if code is None:
                        self._report(run_id, reported, variant, progress)
                        continue
                    exits[variant] = code
                    outcomes[variant] = child.outcome()
                    self._children.unregister(run_id, variant)
                    self._emit(run_id, VARIANT_COMPLETED, progress)
                    reported[variant] = progress
                    if code != 0:
                        self._stop_sibling(run_id, variant, children, outcomes)
                if len(outcomes) < len(_VARIANT_ORDER):
                    time.sleep(self._poll_interval)
        except CancellationError:
            self._children.terminate_all(run_id, self._grace)
            self._collect_remaining(children, outcomes)
            raise

        self._require_both_succeeded(run_id, exits)
        return outcomes

    def _watch_one(
        self,
        run_id: str,
        pair: VariantPair,
        child: EvaluationChild,
    ) -> ChildProcessOutcome:
        """Poll one child to its end, reporting phase progress as it goes."""
        variant = child.variant
        last: int | None = None
        try:
            while True:
                raise_if_cancel_requested(self._run_store, run_id)
                code = child.poll()
                progress = self._inspect(pair, variant, code)
                last = self._report_phase_progress(run_id, variant, progress, last)
                if code is not None:
                    break
                time.sleep(self._poll_interval)
        except CancellationError:
            self._children.terminate_all(run_id, self._grace)
            raise

        outcome = child.outcome()
        self._children.unregister(run_id, variant)
        self._require_both_succeeded(run_id, {variant: outcome.exit_code})
        return outcome

    def _stop_sibling(
        self,
        run_id: str,
        failed: VariantName,
        children: dict[VariantName, EvaluationChild],
        outcomes: dict[VariantName, ChildProcessOutcome],
    ) -> None:
        """Terminate the other side of a pair whose first side failed."""
        for variant in _VARIANT_ORDER:
            if variant is failed or variant in outcomes:
                continue
            sibling = children[variant]
            sibling.terminate(self._grace)
            outcomes[variant] = sibling.outcome()
            self._children.unregister(run_id, variant)

    def _collect_remaining(
        self,
        children: dict[VariantName, EvaluationChild],
        outcomes: dict[VariantName, ChildProcessOutcome],
    ) -> None:
        """Describe every child that has not been described yet.

        Called while unwinding, so a child that cannot describe itself is
        skipped rather than allowed to replace the reason the run is stopping.
        """
        for variant in _VARIANT_ORDER:
            if variant in outcomes:
                continue
            try:
                outcomes[variant] = children[variant].outcome()
            except RunError:
                continue

    def _require_both_succeeded(
        self, run_id: str, exits: dict[VariantName, int]
    ) -> None:
        """Fail the pair when either side did not finish cleanly."""
        failed = sorted(
            (variant.value, code) for variant, code in exits.items() if code != 0
        )
        if not failed:
            return
        detail: list[JsonValue] = [
            {"variant": variant, "exit_code": code} for variant, code in failed
        ]
        names = ", ".join(variant for variant, _ in failed)
        raise RunError(
            f"the {names} evaluation did not finish; a comparison needs both "
            "sides, so the pair failed and the partial evidence was kept",
            code=VARIANT_EXECUTION_FAILED,
            details={"run_id": run_id, "variants": detail},
        )

    # -- measurement and events -------------------------------------------

    def _inspect(
        self,
        pair: VariantPair,
        variant: VariantName,
        exit_code: int | None,
    ) -> VariantProgress:
        """Measure one variant from the evidence its child is writing."""
        plan = pair.plan(variant)
        return inspect_progress(
            variant=variant,
            traces_path=self._traces_path(plan),
            total=plan.task_count,
            child_exit_code=exit_code,
            max_concurrent=plan.max_concurrent,
        )

    def _traces_path(self, plan: VariantExecutionPlan) -> Path:
        """Where one variant's child appends its finished episodes."""
        return Path(plan.verifiers_output_dir) / TRACES_FILENAME

    def _announce(self, run_id: str, pair: VariantPair, variant: VariantName) -> None:
        """Record that one side of the comparison is up."""
        self._emit(
            run_id,
            VARIANT_STARTED,
            pending_progress(variant, pair.plan(variant).task_count),
        )

    def _report(
        self,
        run_id: str,
        reported: dict[VariantName, VariantProgress | None],
        variant: VariantName,
        progress: VariantProgress,
    ) -> None:
        """Append a progress event only when something actually moved."""
        if reported[variant] == progress:
            return
        self._emit(run_id, VARIANT_PROGRESS, progress)
        reported[variant] = progress

    def _report_phase_progress(
        self,
        run_id: str,
        variant: VariantName,
        progress: VariantProgress,
        last: int | None,
    ) -> int:
        """Append one sequential phase's progress line when it advances."""
        if progress.completed == last:
            return progress.completed
        with self._cancellation_aware(run_id):
            self._run_store.append(
                run_id,
                phase=None,
                kind=PROGRESS_UPDATED,
                details={
                    DETAIL_CURRENT: progress.completed,
                    DETAIL_TOTAL: progress.total,
                    DETAIL_LABEL: _EPISODE_LABEL.format(variant=variant.value),
                },
            )
        return progress.completed

    def _emit(self, run_id: str, kind: str, progress: VariantProgress) -> None:
        """Append one variant event against whatever phase the run is in."""
        with self._cancellation_aware(run_id):
            self._run_store.append(
                run_id,
                phase=None,
                kind=kind,
                details={
                    DETAIL_VARIANT: progress.variant,
                    DETAIL_COMPLETED: progress.completed,
                    DETAIL_TOTAL: progress.total,
                    DETAIL_RUNNING: progress.running,
                    DETAIL_ERRORED: progress.errored,
                    DETAIL_STATE: progress.state,
                },
            )

    @contextlib.contextmanager
    def _cancellation_aware(self, run_id: str) -> Iterator[None]:
        """Report a refused append as the cancellation that caused it.

        A variant event belongs to ``running_variants`` and to no other phase,
        so an append that lands after another process asked the run to stop is
        refused by the run's own state machine. That refusal is not a defect
        and it is not what the caller has to unwind for: between the poller's
        cancellation check and its append, another process moved the run to
        ``cancel_requested``, and the cancellation is the fact. Anything else
        that made the append fail is re-raised unchanged.
        """
        try:
            yield
        except TechtreeError:
            raise_if_cancel_requested(self._run_store, run_id)
            raise


def _utc_now() -> datetime:
    """Return the current instant in UTC."""
    return datetime.now(UTC)
