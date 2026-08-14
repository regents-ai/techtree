"""A real evaluation becoming a real result. Spec sections 7.9, 7.10, 7.20.

Two claims are made here and they are different sizes.

The first is scientific: the evidence two paid probes produced on 2026-08-13 —
``qwen/qwen3.7-flash`` in real Docker containers, ``exact_match`` 0/2 without
the ``branch-code-v1`` Skill and 2/2 with it — passes a controlled comparison
and aggregates to the uplift it actually measured. Nothing in that path is
invented and nothing in it is rescored.

The second is operational, and it is the one WP6 could not make: a run reaches
``completed`` with that report inside it. The run is prepared from a real
catalog, staged through the real run service, and driven through the real
worker entry point; only the evaluation itself is replayed from the recorded
evidence rather than executed again. No container starts, no provider is
called, and nothing is spent.

What that leaves for the paid acceptance run is the evaluation, which is
exactly what a paid run is for.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from fixtures.receipts.pair import RecordedPair, recorded_pair
from fixtures.receipts.staged import (
    RecordedEvidenceExecutor,
    StagedRecordedRun,
    staged_recorded_run,
)
from techtree.canonical import digest_object
from techtree.models.base import ObjectEnvelope
from techtree.models.campaign import VariantSchedule
from techtree.models.episode_receipt import (
    EpisodeReceipt,
    EvidenceStatus,
    ScoreStatus,
)
from techtree.models.run import RunPhase
from techtree.models.uplift_report import (
    ComparisonStatus,
    ExecutionStatus,
    PublicationStatus,
    UpliftDecision,
    UpliftReport,
)
from techtree.receipts.compare import SKILL_INDEX_TOOL, compare_real_variants
from techtree.receipts.episode import experiment_variant_of
from techtree.receipts.set import (
    ReceiptSetManifest,
    build_receipt_set,
    receipt_set_path,
    seal_receipt,
    verify_receipt_set,
)
from techtree.receipts.uplift import (
    LocalAttestation,
    aggregate_primary_result,
    build_uplift_report,
    pair_task_rewards,
    summarize_receipts,
)
from techtree.runs.validation import PublisherFixtureValidationProvider
from techtree.verifiers.models import VariantName
from techtree.worker.execute import execute_run

pytestmark = pytest.mark.integration


def test_the_recorded_probes_produce_a_complete_report() -> None:
    """The whole post-evaluation pipeline, over evidence that was paid for."""
    pair = recorded_pair()
    receipts = {
        variant: pair.receipts(variant)
        for variant in (VariantName.BASELINE, VariantName.CANDIDATE)
    }

    # 1. The receipts carry the rewards Verifiers recorded, and nothing else.
    def rewards(variant: VariantName) -> list[float]:
        return [
            receipt.named_traces["subject"][0].rewards["exact_match"]
            for receipt in receipts[variant]
        ]

    assert rewards(VariantName.BASELINE) == [0.0] * 36
    assert sum(rewards(VariantName.CANDIDATE)) == 24.0
    assert set(rewards(VariantName.CANDIDATE)) == {0.0, 1.0}

    # 2. The two executions were one experiment, tool surface included.
    comparison = compare_real_variants(
        campaign=pair.campaign,
        baseline_manifest=pair.baseline_manifest,
        candidate_manifest=pair.candidate_manifest,
        prepared_manifest_comparison=pair.prepared_comparison,
        baseline_receipts=receipts[VariantName.BASELINE],
        candidate_receipts=receipts[VariantName.CANDIDATE],
        taskset_lock=pair.taskset_lock,
        baseline_observed=pair.observed(VariantName.BASELINE),
        candidate_observed=pair.observed(VariantName.CANDIDATE),
        schedule=VariantSchedule.PARALLEL,
    )
    assert comparison.status is ComparisonStatus.CONTROLLED_WITH_WARNINGS, [
        check.detail for check in comparison.failures
    ]
    assert [check.id for check in comparison.warnings] == [
        "model_revision_discoverable"
    ]
    assert SKILL_INDEX_TOOL in next(
        check.detail
        for check in comparison.checks
        if check.id == "observed_tool_inventory"
    )

    # 3. The aggregate is the measurement, with a zero baseline's null ratio.
    deltas = pair_task_rewards(
        baseline_receipts=receipts[VariantName.BASELINE],
        candidate_receipts=receipts[VariantName.CANDIDATE],
        ordered_task_hashes=comparison.ordered_task_hashes,
        reward_name=pair.primary_reward,
    )
    primary = aggregate_primary_result(deltas, pair.primary_reward)
    assert primary.baseline_mean == 0.0
    assert primary.candidate_mean == pytest.approx(24 / 36)
    assert primary.relative_delta is None
    assert (primary.wins, primary.losses, primary.ties) == (24, 0, 12)

    # 4. The report says what was measured and grades itself honestly.
    score, evidence = summarize_receipts(
        receipts[VariantName.BASELINE], receipts[VariantName.CANDIDATE]
    )
    report = build_uplift_report(
        run_request=pair.request,
        campaign=pair.campaign,
        taskset_validation_receipt_digest=(
            pair.campaign.taskset.validation_receipt_digest
        ),
        baseline_manifest=pair.baseline_manifest,
        candidate_manifest=pair.candidate_manifest,
        baseline_receipt_set=_receipt_set(pair, VariantName.BASELINE),
        candidate_receipt_set=_receipt_set(pair, VariantName.CANDIDATE),
        comparison=comparison,
        task_deltas=deltas,
        primary=primary,
        score=score,
        evidence=evidence,
        attestation=LocalAttestation.UNATTESTED,
        created_at=pair.request.created_at,
    )
    assert report.statuses.score is ScoreStatus.VALID
    assert report.statuses.evidence is EvidenceStatus.COMPLETE
    assert report.proof_grade == "development_only"
    assert report.decision is UpliftDecision.DEVELOPMENT_ONLY


def test_a_real_run_completes_end_to_end(tmp_path: Path) -> None:
    """The loop closes: prepared, started, staged, executed, reported, completed."""
    run = staged_recorded_run(tmp_path / "home")
    assert run.run_store.state(run.run_id).phase is RunPhase.CREATED

    exit_code = execute_run(
        run.run_id,
        paths=run.paths,
        executor_factory=lambda request: RecordedEvidenceExecutor(
            pair=run.pair, paths=run.paths
        ),
        validation_provider_factory=lambda request: (
            PublisherFixtureValidationProvider()
        ),
    )

    assert exit_code == 0
    state = run.run_store.state(run.run_id)
    assert state.phase is RunPhase.COMPLETED
    assert state.error is None

    report = _report_on_disk(run)
    assert state.result_digest == digest_object(report)
    assert report.run_id == run.run_id
    assert report.statuses.execution is ExecutionStatus.COMPLETED
    assert report.statuses.score is ScoreStatus.VALID
    assert report.statuses.evidence is EvidenceStatus.COMPLETE
    assert report.statuses.comparison is ComparisonStatus.CONTROLLED_WITH_WARNINGS
    assert report.statuses.publication is PublicationStatus.NOT_REQUESTED
    assert report.primary_result.baseline_mean == 0.0
    assert report.primary_result.candidate_mean == pytest.approx(24 / 36)
    assert report.primary_result.wins == 24
    assert report.publication_eligible is False


def test_the_run_walks_every_phase_the_state_machine_defines(
    tmp_path: Path,
) -> None:
    """A concurrent real run's phases, in order, from its own journal."""
    run = staged_recorded_run(tmp_path / "home")
    execute_run(
        run.run_id,
        paths=run.paths,
        executor_factory=lambda request: RecordedEvidenceExecutor(
            pair=run.pair, paths=run.paths
        ),
        validation_provider_factory=lambda request: (
            PublisherFixtureValidationProvider()
        ),
    )

    phases: list[str] = []
    for line in _events(run):
        phase = str(line["phase"])
        if not phases or phases[-1] != phase:
            phases.append(phase)

    assert phases == [
        RunPhase.CREATED.value,
        RunPhase.VALIDATING_TASKSET.value,
        RunPhase.RUNNING_VARIANTS.value,
        RunPhase.BUILDING_RECEIPTS.value,
        RunPhase.VERIFYING_COMPARISON.value,
        RunPhase.BUILDING_REPORT.value,
        RunPhase.COMPLETED.value,
    ]


def test_the_completed_run_leaves_checkable_receipts(tmp_path: Path) -> None:
    """Both variants' receipts and both commitments, on disk and verifiable."""
    run = staged_recorded_run(tmp_path / "home")
    execute_run(
        run.run_id,
        paths=run.paths,
        executor_factory=lambda request: RecordedEvidenceExecutor(
            pair=run.pair, paths=run.paths
        ),
        validation_provider_factory=lambda request: (
            PublisherFixtureValidationProvider()
        ),
    )

    committed = list(run.campaign.taskset.membership.ordered_task_hashes)
    for variant in (VariantName.BASELINE, VariantName.CANDIDATE):
        protocol_variant = experiment_variant_of(variant)
        receipts = run.artifacts.episode_receipts(run.run_id, protocol_variant)
        assert [receipt.task_hash for receipt in receipts] == committed
        assert all(receipt.execution_backend == "verifiers" for receipt in receipts)
        assert all(receipt.score_status is ScoreStatus.VALID for receipt in receipts)

        path = receipt_set_path(run.paths.run_dir(run.run_id), protocol_variant)
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        manifest = ReceiptSetManifest.model_validate_json(path.read_bytes())
        envelopes: list[ObjectEnvelope[EpisodeReceipt]] = [
            seal_receipt(receipt) for receipt in receipts
        ]
        verify_receipt_set(
            manifest=manifest,
            signed_receipts=envelopes,
            ordered_task_hashes=committed,
        )
        # The receipts on disk are the payloads; the signatures live on the
        # envelopes in the run's proof bundle, which
        # ``test_local_sign_and_verify`` checks. Re-sealing them here proves
        # the commitment holds over the bytes the run wrote, which is the
        # property this test is about.
        assert [envelope.payload_digest for envelope in envelopes] == list(
            manifest.ordered_receipt_digests
        )


def test_a_completed_run_records_no_second_result(tmp_path: Path) -> None:
    """A run that has ended is closed, report included."""
    run = staged_recorded_run(tmp_path / "home")
    execute_run(
        run.run_id,
        paths=run.paths,
        executor_factory=lambda request: RecordedEvidenceExecutor(
            pair=run.pair, paths=run.paths
        ),
        validation_provider_factory=lambda request: (
            PublisherFixtureValidationProvider()
        ),
    )

    second = execute_run(
        run.run_id,
        paths=run.paths,
        executor_factory=lambda request: RecordedEvidenceExecutor(
            pair=run.pair, paths=run.paths
        ),
        validation_provider_factory=lambda request: (
            PublisherFixtureValidationProvider()
        ),
    )

    assert second != 0
    assert run.run_store.state(run.run_id).phase is RunPhase.COMPLETED


# ---------------------------------------------------------------------------
# Reading what the run wrote
# ---------------------------------------------------------------------------


def _receipt_set(pair: RecordedPair, variant: VariantName) -> ReceiptSetManifest:
    """Return one variant's ordered commitment over its recorded receipts."""
    return build_receipt_set(
        run_id=pair.request.run_id,
        variant=experiment_variant_of(variant),
        experiment_manifest_digest=pair.results[variant].experiment_manifest_digest,
        signed_receipts=[seal_receipt(receipt) for receipt in pair.receipts(variant)],
        ordered_task_hashes=pair.ordered_task_hashes,
    )


def _report_on_disk(run: StagedRecordedRun) -> UpliftReport:
    """Load the report the run recorded, from the bytes it wrote."""
    path = run.run_store.result_path(run.run_id)
    return UpliftReport.model_validate_json(path.read_bytes())


def _events(run: StagedRecordedRun) -> list[dict[str, object]]:
    """Return the run's journal, one decoded record per line."""
    path = run.paths.run_dir(run.run_id) / "events.jsonl"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
