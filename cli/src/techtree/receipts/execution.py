"""What one comparison cost to run. Decisions document 0007 R6+R8.

A run's receipts say what was scored. They say nothing about what the scoring
consumed — how long each side took, how far apart the two children started, how
many tokens went out, what the provider charged — and a participant deciding
whether to run a second comparison needs exactly that. Decisions document 0007
R6 answers it with a new artifact rather than by reopening the receipts: one
signed, content-addressed ``techtree.comparison-execution.v1alpha1`` record per
comparison, written beside the report and carried in the proof bundle.

Four rules decide everything in this module.

*It is operational evidence, and it is orthogonal to reward truth.* Nothing
here is an input to a score, a decision, or a comparison status. A record that
is missing, incomplete, or absent entirely leaves the measurement exactly as it
was: R6 is explicit that missing economics makes cost and timing unavailable
with an operational-evidence warning, and never invalidates a valid score. That
is why no function here can fail a run.

*Provenance is stated, never implied.* Every cost carries one of four
provenances — provider-reported, computed from a pinned price, estimated, or
unavailable — and an estimate is never shown as provider-reported. When two
variants' costs are added together the sum takes the *weakest* provenance of
the two, because a total that mixed a reported number with a guess and called
itself reported would be the exact misstatement R6 forbids.

*Usage is what the evidence carries, and the coverage says how much.* Token
counts are summed from the engine's own normalized per-trace usage. Traces that
report none are counted rather than treated as zero, so a partial record is
visible as partial. Model calls are counted separately, because every trace
records them and tokens are not always reported alongside: a variant can
honestly know how many calls it made and not know what they consumed.

*Nothing is derived from a wall clock twice.* Elapsed times come from the
child outcomes the run already recorded, launch skew from the operational
record the scheduler already wrote, and the overlap from the two intervals. No
timestamp is taken here, so building the record twice from one run produces
identical bytes.

The record is not part of the frozen v0.1 protocol, and lives here for the same
reason :class:`~techtree.receipts.bundle.LocalProofBundleManifest` does: the
protocol has no such object, and inventing one inside ``models/`` would be an
unratified amendment. R6 leaves the link from ``UpliftReport`` to a later
protocol revision, so nothing in the report points at this record; the bundle's
signed manifest is what binds it to the run.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal, Self

from pydantic import Field, model_validator
from pydantic import ValidationError as PydanticValidationError

from techtree.models.base import (
    Digest,
    NonEmptyString,
    ObjectEnvelope,
    ProtocolModel,
    UtcDateTime,
)
from techtree.models.campaign import VariantSchedule
from techtree.models.experiment import ExperimentVariant
from techtree.runs.child_registry import children_record_path
from techtree.verifiers.compiler import divide_concurrency
from techtree.verifiers.models import (
    RealExecutionResult,
    VariantExecutionResult,
    VariantName,
)

__all__ = [
    "COMPARISON_EXECUTION_RECORD_INVALID",
    "COMPARISON_EXECUTION_SCHEMA_VERSION",
    "EXECUTION_RECORD_FILENAME",
    "OPERATIONAL_EVIDENCE_UNAVAILABLE",
    "ComparisonExecutionRecord",
    "CostProvenance",
    "PairOutcome",
    "TotalCost",
    "UsageProvenance",
    "VariantCost",
    "VariantExecutionSummary",
    "VariantUsage",
    "build_comparison_execution_record",
    "read_children_record",
    "read_execution_record",
    "unavailable_cost",
    "weakest_provenance",
]

#: This record's own schema version. Not in :mod:`techtree.constants`, which
#: holds protocol schema versions, and this is not a protocol object.
COMPARISON_EXECUTION_SCHEMA_VERSION: Final = "techtree.comparison-execution.v1alpha1"

#: Stable error code for a record that does not hold together. Used by the
#: bundle verifier; nothing raises it while a run is being scored, because a
#: broken operational record never invalidates a measurement.
COMPARISON_EXECUTION_RECORD_INVALID: Final = "comparison_execution_record_invalid"

#: What a reader is told when a bundle carries no operational record at all.
#: Decisions document 0007 R6: this is a warning about what is unknown, never
#: a finding about what was measured.
OPERATIONAL_EVIDENCE_UNAVAILABLE: Final = "operational_evidence_unavailable"

#: Where the record is placed inside a proof bundle. Owned here rather than by
#: the bundle module, because the record's own reader needs it and a module
#: that names a file should be the one that writes it.
EXECUTION_RECORD_FILENAME: Final = "comparison-execution.json"

#: Both sides, always in comparison order.
_VARIANT_ORDER: Final[tuple[VariantName, ...]] = (
    VariantName.BASELINE,
    VariantName.CANDIDATE,
)


class CostProvenance(StrEnum):
    """Where a cost figure came from. Decisions document 0007 R6.

    The four values are ordered by how much they claim, and the order is
    load-bearing: :func:`weakest_provenance` uses it so that a total can never
    describe itself as better sourced than the worst number inside it.
    """

    #: The provider billed this and said so.
    PROVIDER_REPORTED = "provider_reported"
    #: Computed from recorded usage and a price the release pinned.
    COMPUTED_FROM_PINNED_PRICE = "computed_from_pinned_price"
    #: A figure Techtree worked out for guidance. Never presented as billed.
    ESTIMATED = "estimated"
    #: No cost is known. The comparison is unaffected.
    UNAVAILABLE = "unavailable"


#: Weakest first, so ``min`` over this order answers "what may the sum claim?".
_PROVENANCE_STRENGTH: Final[dict[CostProvenance, int]] = {
    CostProvenance.UNAVAILABLE: 0,
    CostProvenance.ESTIMATED: 1,
    CostProvenance.COMPUTED_FROM_PINNED_PRICE: 2,
    CostProvenance.PROVIDER_REPORTED: 3,
}


class UsageProvenance(StrEnum):
    """Where token counts came from."""

    #: Summed from the engine's normalized per-trace usage.
    NORMALIZED_TRACES = "normalized_traces"
    #: No trace in this variant reported any usage.
    UNAVAILABLE = "unavailable"


class PairOutcome(StrEnum):
    """How the pair of children ended."""

    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class VariantCost(ProtocolModel):
    """One side's cost, and the honest account of where the number is from."""

    cost_usd: float | None = Field(default=None, ge=0.0)
    provenance: CostProvenance
    detail: NonEmptyString

    @model_validator(mode="after")
    def _check_the_number_and_its_provenance_agree(self) -> Self:
        """Reject a cost that claims a source it has no figure for, or vice versa."""
        known = self.cost_usd is not None
        claims_source = self.provenance is not CostProvenance.UNAVAILABLE
        if known != claims_source:
            raise ValueError(
                "a cost figure needs a provenance and a provenance needs a "
                f"figure; got {self.cost_usd!r} as {self.provenance.value}"
            )
        return self


class TotalCost(ProtocolModel):
    """Both sides' cost added up, at the weakest provenance of the two."""

    cost_usd: float | None = Field(default=None, ge=0.0)
    provenance: CostProvenance

    @model_validator(mode="after")
    def _check_the_number_and_its_provenance_agree(self) -> Self:
        """Reject a total that claims a source it has no figure for."""
        if (self.cost_usd is not None) != (
            self.provenance is not CostProvenance.UNAVAILABLE
        ):
            raise ValueError("a total cost figure needs a provenance, and vice versa")
        return self


class VariantUsage(ProtocolModel):
    """What one side consumed, as the normalized evidence recorded it.

    ``traces_total`` and ``traces_with_usage`` are carried so that partial
    coverage is legible: a variant where three traces of thirty-six reported
    tokens is not a variant whose token count means what a complete one means,
    and a reader is told that rather than left to assume it.
    """

    provenance: UsageProvenance
    model_calls: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    traces_total: int = Field(ge=0)
    traces_with_usage: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_the_counts_and_the_provenance_agree(self) -> Self:
        """Reject a usage block that reports numbers it says it does not have."""
        if self.traces_with_usage > self.traces_total:
            raise ValueError(
                "a variant cannot have more traces reporting usage than traces"
            )
        reported = self.provenance is UsageProvenance.NORMALIZED_TRACES
        if reported != (self.total_tokens is not None):
            raise ValueError(
                "token totals are present exactly when usage was reported; got "
                f"{self.total_tokens!r} as {self.provenance.value}"
            )
        if reported and self.traces_with_usage == 0:
            raise ValueError(
                "usage cannot come from normalized traces when no trace reported any"
            )
        return self


class VariantExecutionSummary(ProtocolModel):
    """Everything one side of the comparison did, operationally."""

    variant: ExperimentVariant
    started_at: UtcDateTime
    finished_at: UtcDateTime
    elapsed_seconds: float = Field(ge=0.0)
    exit_code: int
    cancelled: bool
    episode_count: int = Field(ge=0)
    max_concurrent: int = Field(ge=1)
    usage: VariantUsage
    cost: VariantCost
    experiment_manifest_digest: Digest
    argv_digest: Digest
    normalized_episodes_digest: Digest
    raw_traces_digest: Digest
    resolved_config_digest: Digest

    @model_validator(mode="after")
    def _check_the_clock_moves_forward(self) -> Self:
        """Reject a side that finished before it started."""
        if self.finished_at < self.started_at:
            raise ValueError("a variant cannot finish before it starts")
        return self


class ComparisonExecutionRecord(ProtocolModel):
    """One comparison's operational record. Decisions document 0007 R6+R8."""

    schema_version: Literal["techtree.comparison-execution.v1alpha1"]
    run_id: NonEmptyString
    campaign_spec_digest: Digest
    engine_digest: Digest
    execution_backend: Literal["verifiers"]
    schedule: VariantSchedule
    started_at: UtcDateTime
    finished_at: UtcDateTime
    elapsed_seconds: float = Field(ge=0.0)
    launch_skew_seconds: float | None = Field(default=None, ge=0.0)
    first_launched: ExperimentVariant | None
    overlap_seconds: float = Field(ge=0.0)
    campaign_max_concurrent: int = Field(ge=1)
    outcome: PairOutcome
    baseline: VariantExecutionSummary
    candidate: VariantExecutionSummary

    @model_validator(mode="after")
    def _check_each_side_is_the_side_it_claims(self) -> Self:
        """Reject a record that files a variant under the wrong name."""
        if self.baseline.variant is not ExperimentVariant.BASELINE:
            raise ValueError("the baseline slot holds the baseline variant")
        if self.candidate.variant is not ExperimentVariant.CANDIDATE:
            raise ValueError("the candidate slot holds the candidate variant")
        if (self.launch_skew_seconds is None) != (self.first_launched is None):
            raise ValueError(
                "a launch skew names which side went first, and a side that "
                "went first implies a skew"
            )
        return self

    @property
    def total_cost(self) -> TotalCost:
        """Return both sides added up, claiming only what the weaker side can.

        A total that mixed a provider's own figure with an estimate and called
        itself provider-reported would be the one misstatement decisions
        document 0007 R6 names outright, so the sum takes the weakest
        provenance of the two and is absent entirely when either side is.
        """
        provenance = weakest_provenance(
            [self.baseline.cost.provenance, self.candidate.cost.provenance]
        )
        if provenance is CostProvenance.UNAVAILABLE:
            return TotalCost(cost_usd=None, provenance=provenance)
        # Both sides carry a figure: the validator on VariantCost guarantees a
        # non-unavailable provenance has one.
        assert self.baseline.cost.cost_usd is not None
        assert self.candidate.cost.cost_usd is not None
        return TotalCost(
            cost_usd=self.baseline.cost.cost_usd + self.candidate.cost.cost_usd,
            provenance=provenance,
        )

    @property
    def total_tokens(self) -> int | None:
        """Return both sides' tokens, or ``None`` when either side has none."""
        if self.baseline.usage.total_tokens is None:
            return None
        if self.candidate.usage.total_tokens is None:
            return None
        return self.baseline.usage.total_tokens + self.candidate.usage.total_tokens

    def side(self, variant: ExperimentVariant) -> VariantExecutionSummary:
        """Return one side's summary."""
        return (
            self.baseline if variant is ExperimentVariant.BASELINE else self.candidate
        )


def weakest_provenance(provenances: Sequence[CostProvenance]) -> CostProvenance:
    """Return the least-claiming provenance among several."""
    return min(provenances, key=lambda value: _PROVENANCE_STRENGTH[value])


def unavailable_cost(detail: str) -> VariantCost:
    """Return the cost of a variant whose economics nothing reported."""
    return VariantCost(
        cost_usd=None, provenance=CostProvenance.UNAVAILABLE, detail=detail
    )


#: What this build says when it has no economics at all. Stated once so the
#: sentence a reader meets is the same everywhere, and so the day a price feed
#: lands there is one place that stops being true.
NO_COST_SOURCE: Final = (
    "no cost figure was reported for this variant, and this build pins no "
    "price to compute one from"
)


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------


def build_comparison_execution_record(
    *,
    run_id: str,
    campaign_spec_digest: Digest,
    campaign_max_concurrent: int,
    execution: RealExecutionResult,
    run_root: Path,
    costs: Mapping[VariantName, VariantCost] | None = None,
) -> ComparisonExecutionRecord:
    """Assemble one comparison's operational record from what the run recorded.

    Every value is read from something the run already wrote: the child
    outcomes, the normalized episodes, the artifact references beside them,
    and the scheduler's own children record. ``costs`` is the seam a price
    feed arrives through; with nothing passed, both sides report an
    unavailable cost, which is what this build's runs honestly produce.
    """
    skew_seconds, first_launched = read_children_record(run_root)
    sides = {
        variant: _summary(
            result=_side(execution, variant),
            campaign_max_concurrent=campaign_max_concurrent,
            schedule=execution.schedule,
            variant=variant,
            cost=(costs or {}).get(variant),
        )
        for variant in _VARIANT_ORDER
    }
    baseline = sides[VariantName.BASELINE]
    candidate = sides[VariantName.CANDIDATE]

    started_at = min(baseline.started_at, candidate.started_at)
    finished_at = max(baseline.finished_at, candidate.finished_at)
    return ComparisonExecutionRecord(
        schema_version=COMPARISON_EXECUTION_SCHEMA_VERSION,
        run_id=run_id,
        campaign_spec_digest=campaign_spec_digest,
        engine_digest=execution.engine_digest,
        execution_backend=execution.execution_backend,
        schedule=execution.schedule,
        started_at=started_at,
        finished_at=finished_at,
        elapsed_seconds=_seconds(started_at, finished_at),
        launch_skew_seconds=skew_seconds,
        first_launched=first_launched,
        overlap_seconds=_overlap(baseline, candidate),
        campaign_max_concurrent=campaign_max_concurrent,
        outcome=_outcome(baseline, candidate),
        baseline=baseline,
        candidate=candidate,
    )


def read_execution_record(bundle_dir: Path) -> ComparisonExecutionRecord | None:
    """Return the record one proof bundle carries, or ``None`` when it has none.

    Reading is deliberately separate from checking. The bundle verifier is
    what decides whether a record is signed, intact and about this run; this
    is what a renderer calls afterwards, and it returns nothing rather than
    raising, because a result whose economics cannot be read is still a
    result. A bundle whose record does not verify is already reported by the
    verification the caller ran before it got here.
    """
    path = bundle_dir / EXECUTION_RECORD_FILENAME
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    try:
        envelope = ObjectEnvelope[ComparisonExecutionRecord].model_validate_json(raw)
    except PydanticValidationError:
        return None
    return envelope.payload


def read_children_record(
    run_root: Path,
) -> tuple[float | None, ExperimentVariant | None]:
    """Return the launch skew and which side went first, if the run recorded them.

    The scheduler writes this while the children are being started, which is
    the only moment either value can be observed. A run without the file — a
    sequential schedule records no skew, and an older run may have written
    none — reports neither rather than reconstructing one from timestamps that
    were taken for something else.
    """
    path = children_record_path(run_root)
    try:
        document = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None, None
    if not isinstance(document, dict):
        return None, None

    skew = document.get("launch_skew_seconds")
    if not isinstance(skew, int | float) or isinstance(skew, bool) or skew < 0:
        return None, None

    started = [
        (row.get("started_at"), row.get("variant"))
        for row in document.get("children", [])
        if isinstance(row, dict)
    ]
    first = _first_launched(started)
    if first is None:
        return None, None
    return float(skew), first


# ---------------------------------------------------------------------------
# The pieces
# ---------------------------------------------------------------------------


def _summary(
    *,
    result: VariantExecutionResult,
    campaign_max_concurrent: int,
    schedule: VariantSchedule,
    variant: VariantName,
    cost: VariantCost | None,
) -> VariantExecutionSummary:
    """Describe one side from its own recorded evidence."""
    outcome = result.child_outcome
    baseline_permits, candidate_permits = divide_concurrency(
        schedule, campaign_max_concurrent
    )
    return VariantExecutionSummary(
        variant=_protocol_variant(variant),
        started_at=outcome.started_at,
        finished_at=outcome.finished_at,
        elapsed_seconds=_seconds(outcome.started_at, outcome.finished_at),
        exit_code=outcome.exit_code,
        cancelled=outcome.cancelled,
        episode_count=len(result.episodes),
        max_concurrent=(
            baseline_permits if variant is VariantName.BASELINE else candidate_permits
        ),
        usage=_usage(result),
        cost=cost or unavailable_cost(NO_COST_SOURCE),
        experiment_manifest_digest=result.experiment_manifest_digest,
        argv_digest=outcome.argv_digest,
        normalized_episodes_digest=result.normalized_episodes.digest,
        raw_traces_digest=result.raw_traces.digest,
        resolved_config_digest=result.resolved_verifiers_config.digest,
    )


def _usage(result: VariantExecutionResult) -> VariantUsage:
    """Sum one side's consumption from the engine's normalized traces.

    Two measurements with two different availabilities, kept apart. Model
    calls are counted by every trace, so they are known whenever this variant
    recorded a trace at all. Token usage is reported per trace and may be
    absent, so a trace that reports none is *counted* rather than read as a
    zero, and the coverage travels with the totals.
    """
    traces_total = 0
    traces_with_usage = 0
    model_calls = 0
    totals = {"input": 0, "cached": 0, "output": 0, "total": 0}
    for episode in result.episodes:
        for trace in episode.traces:
            traces_total += 1
            model_calls += trace.model_calls
            usage = trace.usage
            if usage is None:
                continue
            traces_with_usage += 1
            totals["input"] += usage.input_tokens
            totals["cached"] += usage.cached_input_tokens or 0
            totals["output"] += usage.output_tokens
            totals["total"] += usage.total_tokens

    counted = None if traces_total == 0 else model_calls
    if traces_with_usage == 0:
        return VariantUsage(
            provenance=UsageProvenance.UNAVAILABLE,
            model_calls=counted,
            traces_total=traces_total,
            traces_with_usage=0,
        )
    return VariantUsage(
        provenance=UsageProvenance.NORMALIZED_TRACES,
        model_calls=counted,
        input_tokens=totals["input"],
        cached_input_tokens=totals["cached"],
        output_tokens=totals["output"],
        total_tokens=totals["total"],
        traces_total=traces_total,
        traces_with_usage=traces_with_usage,
    )


def _overlap(
    baseline: VariantExecutionSummary, candidate: VariantExecutionSummary
) -> float:
    """Return how long both sides were running at once.

    A parallel comparison's whole claim is that the two sides met the same
    conditions, and the overlap is the measurable part of it. A sequential
    schedule produces zero here, which is the true answer rather than a
    missing one.
    """
    start = max(baseline.started_at, candidate.started_at)
    finish = min(baseline.finished_at, candidate.finished_at)
    return _seconds(start, finish) if finish > start else 0.0


def _outcome(
    baseline: VariantExecutionSummary, candidate: VariantExecutionSummary
) -> PairOutcome:
    """Say how the pair ended, from what the children themselves recorded."""
    if baseline.cancelled or candidate.cancelled:
        return PairOutcome.CANCELLED
    if baseline.exit_code != 0 or candidate.exit_code != 0:
        return PairOutcome.FAILED
    return PairOutcome.COMPLETED


def _first_launched(
    started: Sequence[tuple[object, object]],
) -> ExperimentVariant | None:
    """Return which variant the operational record started first."""
    parsed: list[tuple[datetime, ExperimentVariant]] = []
    for stamp, variant in started:
        if not isinstance(stamp, str) or not isinstance(variant, str):
            return None
        try:
            when = datetime.fromisoformat(stamp)
            side = ExperimentVariant(variant)
        except ValueError:
            return None
        parsed.append((when, side))
    if len(parsed) != len(_VARIANT_ORDER):
        return None
    return min(parsed, key=lambda item: item[0])[1]


def _seconds(start: datetime, finish: datetime) -> float:
    """Return a non-negative duration between two recorded instants."""
    return max(0.0, (finish - start).total_seconds())


def _side(
    execution: RealExecutionResult, variant: VariantName
) -> VariantExecutionResult:
    """Return one side of an execution result."""
    return (
        execution.baseline if variant is VariantName.BASELINE else execution.candidate
    )


def _protocol_variant(variant: VariantName) -> ExperimentVariant:
    """Return the protocol spelling of one variant name."""
    return (
        ExperimentVariant.BASELINE
        if variant is VariantName.BASELINE
        else ExperimentVariant.CANDIDATE
    )


type SignedComparisonExecutionRecord = ObjectEnvelope[ComparisonExecutionRecord]
"""One record inside the envelope the executor signed it with."""
