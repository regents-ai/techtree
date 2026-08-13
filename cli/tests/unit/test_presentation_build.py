"""The channel-neutral payload. Spec sections 7.13 and 7.14.

The payload is the only thing any channel is allowed to draw a result from, so
these tests are about what it may and may not contain, and about it being the
same object every time it is built from the same report.

The report and receipts come from the recorded probes — real ``exact_match``
measurements of 0/2 against 2/2 — so what is under test is a presentation of
something that was actually measured rather than of numbers written for the
occasion.
"""

from __future__ import annotations

import pytest

from fixtures.receipts.pair import RecordedPair, recorded_pair
from fixtures.receipts.proof import execution_record as fixture_execution_record
from techtree.canonical import canonical_json_bytes
from techtree.identity.models import VerificationMessage, VerificationResult
from techtree.models.campaign import VariantSchedule
from techtree.models.episode_receipt import EpisodeReceipt
from techtree.models.experiment import ExperimentVariant
from techtree.models.skill import SkillArtifact, SkillFile
from techtree.models.uplift_report import UpliftReport
from techtree.presentation.build import (
    BASELINE_SKILL_LABEL,
    FIRST_RESULT_LABEL,
    P1_MEANING,
    SECOND_RESULT_LABEL,
    VERIFICATION_FAILED,
    VERIFICATION_NOT_VERIFIED,
    VERIFICATION_VERIFIED,
    build_uplift_presentation,
    score_bars,
)
from techtree.presentation.models import (
    PresentationCaveat,
    UpliftPresentationPayload,
)
from techtree.receipts.compare import compare_real_variants
from techtree.receipts.episode import experiment_variant_of
from techtree.receipts.execution import (
    ComparisonExecutionRecord,
    CostProvenance,
    VariantCost,
)
from techtree.receipts.set import ReceiptSetManifest, build_receipt_set, seal_receipt
from techtree.receipts.uplift import (
    LocalAttestation,
    aggregate_primary_result,
    build_uplift_report,
    pair_task_rewards,
    summarize_receipts,
)
from techtree.verifiers.models import VariantName

CAMPAIGN_TITLE = "Techtree Hello World"


def verified() -> VerificationResult:
    return VerificationResult(
        verified=True,
        messages=[
            VerificationMessage(
                id="bundle.signature",
                status="passed",
                code="signature_verification_failed",
                detail="the signature verifies",
            )
        ],
    )


def unverified() -> VerificationResult:
    return VerificationResult(
        verified=False,
        messages=[
            VerificationMessage(
                id="artifact.uplift-report.json",
                status="failed",
                code="proof_bundle_invalid",
                detail="uplift-report.json has changed since the bundle was written",
            )
        ],
    )


def candidate_skill() -> SkillArtifact:
    return SkillArtifact(
        schema_version="techtree.skill.v1alpha1",
        name="branch-code-v1",
        root_digest=f"sha256:{'a' * 64}",
        archive_digest=f"sha256:{'b' * 64}",
        files=[
            SkillFile(
                path="SKILL.md",
                media_type="text/markdown",
                size=1024,
                digest=f"sha256:{'c' * 64}",
            )
        ],
        source_kind="manual",
        parent_skill_digest=None,
    )


@pytest.fixture(scope="module")
def pair() -> RecordedPair:
    return recorded_pair()


@pytest.fixture(scope="module")
def receipts(pair: RecordedPair) -> dict[VariantName, list[EpisodeReceipt]]:
    return {
        variant: pair.receipts(variant)
        for variant in (VariantName.BASELINE, VariantName.CANDIDATE)
    }


@pytest.fixture(scope="module")
def report(
    pair: RecordedPair, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> UpliftReport:
    """Build the signed-grade report the recorded evidence produces."""
    return _report(pair, receipts, LocalAttestation.LOCAL_ED25519)


@pytest.fixture(scope="module")
def development_report(
    pair: RecordedPair, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> UpliftReport:
    """Build the same comparison with nothing signed."""
    return _report(pair, receipts, LocalAttestation.UNATTESTED)


def _report(
    pair: RecordedPair,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    attestation: LocalAttestation,
) -> UpliftReport:
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
    deltas = pair_task_rewards(
        baseline_receipts=receipts[VariantName.BASELINE],
        candidate_receipts=receipts[VariantName.CANDIDATE],
        ordered_task_hashes=comparison.ordered_task_hashes,
        reward_name=pair.primary_reward,
    )
    score, evidence = summarize_receipts(
        receipts[VariantName.BASELINE], receipts[VariantName.CANDIDATE]
    )
    return build_uplift_report(
        run_request=pair.request,
        campaign=pair.campaign,
        taskset_validation_receipt_digest=(
            pair.campaign.taskset.validation_receipt_digest
        ),
        baseline_manifest=pair.baseline_manifest,
        candidate_manifest=pair.candidate_manifest,
        baseline_receipt_set=_receipt_set(pair, receipts, VariantName.BASELINE),
        candidate_receipt_set=_receipt_set(pair, receipts, VariantName.CANDIDATE),
        comparison=comparison,
        task_deltas=deltas,
        primary=aggregate_primary_result(deltas, pair.primary_reward),
        score=score,
        evidence=evidence,
        attestation=attestation,
        created_at=pair.request.created_at,
    )


def _receipt_set(
    pair: RecordedPair,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    variant: VariantName,
) -> ReceiptSetManifest:
    return build_receipt_set(
        run_id=pair.request.run_id,
        variant=experiment_variant_of(variant),
        experiment_manifest_digest=pair.results[variant].experiment_manifest_digest,
        signed_receipts=[seal_receipt(receipt) for receipt in receipts[variant]],
        ordered_task_hashes=pair.ordered_task_hashes,
    )


def build(
    report: UpliftReport,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    verification: VerificationResult | None = None,
    execution_record: ComparisonExecutionRecord | None = None,
) -> UpliftPresentationPayload:
    return build_uplift_presentation(
        report=report,
        baseline_receipts=receipts[VariantName.BASELINE],
        candidate_receipts=receipts[VariantName.CANDIDATE],
        campaign_title=CAMPAIGN_TITLE,
        baseline_skill=None,
        candidate_skill=candidate_skill(),
        verification=verification,
        execution_record=execution_record,
    )


def execution_record(
    report: UpliftReport, *, costs: dict[str, VariantCost] | None = None
) -> ComparisonExecutionRecord:
    """Return an operational record for this run, with the cost asked for."""
    record = fixture_execution_record(
        report.campaign_spec_digest,
        {
            ExperimentVariant.BASELINE: report.baseline_manifest_digest,
            ExperimentVariant.CANDIDATE: report.candidate_manifest_digest,
        },
        run_id=report.run_id,
    )
    if costs is None:
        return record
    return record.model_copy(
        update={
            "baseline": record.baseline.model_copy(update={"cost": costs["baseline"]}),
            "candidate": record.candidate.model_copy(
                update={"cost": costs["candidate"]}
            ),
        }
    )


# ---------------------------------------------------------------------------
# What it says
# ---------------------------------------------------------------------------


def test_the_payload_states_what_the_report_measured(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    payload = build(report, receipts, verified())

    assert payload.run_id == report.run_id
    assert payload.baseline_score == 0.0
    assert payload.candidate_score == 1.0
    assert payload.absolute_delta == 1.0
    # A zero baseline has no relative change; reporting one would invent it.
    assert payload.relative_delta is None
    assert (payload.wins, payload.losses, payload.ties) == (2, 0, 0)
    assert [row.outcome for row in payload.task_rows] == ["win", "win"]


def test_the_payload_copies_the_verdict_rather_than_deciding_one(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    payload = build(report, receipts, verified())

    assert payload.decision == report.decision.value
    assert payload.proof_grade == report.proof_grade == "P1"


def test_an_insertion_comparison_says_what_it_compared(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    payload = build(report, receipts, verified())

    assert payload.comparison_label == FIRST_RESULT_LABEL
    assert payload.baseline_skill.label == BASELINE_SKILL_LABEL
    assert payload.baseline_skill.root_digest is None
    assert payload.candidate_skill.label == "branch-code-v1"
    assert payload.candidate_skill.file_count == 1


def test_a_replacement_comparison_says_what_it_compared(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    payload = build_uplift_presentation(
        report=report,
        baseline_receipts=receipts[VariantName.BASELINE],
        candidate_receipts=receipts[VariantName.CANDIDATE],
        campaign_title=CAMPAIGN_TITLE,
        baseline_skill=candidate_skill(),
        candidate_skill=candidate_skill(),
        verification=verified(),
    )

    assert payload.comparison_label == SECOND_RESULT_LABEL
    assert payload.baseline_skill.root_digest is not None


def test_the_task_rows_name_tasks_by_position_and_hash(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    payload = build(report, receipts, verified())

    first = payload.task_rows[0]
    _, _, hexadecimal = report.task_deltas[0].task_hash.partition(":")

    assert first.task_label.startswith("task 01 · ")
    assert first.task_label.endswith(hexadecimal[:8])


# ---------------------------------------------------------------------------
# What it warns about
# ---------------------------------------------------------------------------


def test_a_controlled_comparison_with_warnings_says_so_plainly(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """The handoff rule: warnings are rendered, never hidden."""
    payload = build(report, receipts, verified())
    caveat = _caveat(payload, "comparison_controlled_with_warnings")

    assert caveat.severity == "warning"
    assert "controlled with warnings" in caveat.text


def test_a_p1_result_explains_p1_in_the_only_permitted_words(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    payload = build(report, receipts, verified())
    caveat = _caveat(payload, "local_participant_attestation")

    assert P1_MEANING in caveat.text
    assert caveat.severity == "warning"


def test_every_result_states_its_standing_limits(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    payload = build(report, receipts, verified())
    codes = [caveat.code for caveat in payload.caveats]

    assert "no_independent_reproduction" in codes
    assert "no_server_upload" in codes
    assert "no_external_evidence_service" in codes


def test_a_development_only_report_leads_with_an_error_caveat(
    development_report: UpliftReport,
    receipts: dict[VariantName, list[EpisodeReceipt]],
) -> None:
    payload = build(development_report, receipts, None)

    assert payload.caveats[0].code == "development_only_result"
    assert payload.caveats[0].severity == "error"
    assert payload.proof_grade == "development_only"
    assert payload.decision == "development_only"


def test_a_failed_verification_is_an_error_caveat(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    payload = build(report, receipts, unverified())

    assert payload.verification_status == VERIFICATION_FAILED
    assert _caveat(payload, "proof_verification_failed").severity == "error"


def test_an_unchecked_proof_is_not_a_verified_one(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    payload = build(report, receipts, None)

    assert payload.verification_status == VERIFICATION_NOT_VERIFIED
    assert _caveat(payload, "proof_not_verified").severity == "warning"


def test_a_verified_proof_says_it_was_checked_offline(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    payload = build(report, receipts, verified())

    assert payload.verification_status == VERIFICATION_VERIFIED


# ---------------------------------------------------------------------------
# Determinism and safety
# ---------------------------------------------------------------------------


def test_the_same_report_builds_the_same_bytes(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """Deterministic: one report, one payload, byte for byte."""
    first = build(report, receipts, verified())
    second = build(report, receipts, verified())

    assert canonical_json_bytes(first) == canonical_json_bytes(second)


def test_the_payload_carries_no_hidden_material(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """No expected answer, no reply, no grader source has a field to enter by."""
    payload = build(report, receipts, verified())
    fields = set(type(payload).model_fields)

    assert "answer" not in " ".join(fields)
    assert "reply" not in " ".join(fields)
    assert "prompt" not in " ".join(fields)


def test_a_result_without_an_execution_record_says_its_economics_are_unknown(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """Decisions 0007 R6: unavailable and warned about, never invented."""
    payload = build(report, receipts, verified())

    assert payload.economics_source == "unavailable"
    assert payload.baseline_tokens is None
    assert payload.candidate_seconds is None
    assert payload.cost_usd is None
    assert payload.cost_provenance is CostProvenance.UNAVAILABLE
    caveat = _caveat(payload, "operational_evidence_unavailable")
    assert caveat.severity == "warning"
    assert "unaffected" in caveat.text


def test_a_result_with_an_execution_record_is_sourced_from_it(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """The signed record is the source of timing, tokens and cost."""
    record = execution_record(report)
    payload = build(report, receipts, verified(), record)

    assert payload.economics_source == "comparison_execution_record"
    assert payload.baseline_tokens == record.baseline.usage.total_tokens
    assert payload.candidate_tokens == record.candidate.usage.total_tokens
    assert payload.baseline_seconds == record.baseline.elapsed_seconds
    assert payload.candidate_seconds == record.candidate.elapsed_seconds


@pytest.mark.parametrize(
    ("provenance", "code", "severity"),
    [
        (CostProvenance.PROVIDER_REPORTED, "cost_provider_reported", "info"),
        (
            CostProvenance.COMPUTED_FROM_PINNED_PRICE,
            "cost_computed_from_pinned_price",
            "info",
        ),
        (CostProvenance.ESTIMATED, "cost_estimated", "warning"),
    ],
)
def test_every_cost_provenance_reaches_the_payload_with_its_own_caveat(
    report: UpliftReport,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    provenance: CostProvenance,
    code: str,
    severity: str,
) -> None:
    """An estimate is labelled as one, in the payload every channel reads."""
    cost = VariantCost(cost_usd=2.5, provenance=provenance, detail="from the feed")
    payload = build(
        report,
        receipts,
        verified(),
        execution_record(report, costs={"baseline": cost, "candidate": cost}),
    )

    assert payload.cost_usd == 5.0
    assert payload.cost_provenance is provenance
    assert _caveat(payload, code).severity == severity


def test_a_recorded_run_with_no_cost_says_so_without_touching_the_result(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """What this build produces today: timing and tokens, and no cost."""
    payload = build(report, receipts, verified(), execution_record(report))

    assert payload.cost_usd is None
    assert payload.cost_provenance is CostProvenance.UNAVAILABLE
    assert payload.baseline_tokens is not None
    caveat = _caveat(payload, "cost_unavailable")
    assert caveat.severity == "warning"
    assert "unaffected" in caveat.text


def test_the_next_actions_only_name_commands_this_build_has(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    payload = build(report, receipts, verified())

    assert [action.id for action in payload.next_actions] == [
        "inspect_tasks",
        "verify_proof",
        "improvement_context",
        "prepare_replacement",
    ]
    assert all(action.cli is not None for action in payload.next_actions)


def test_a_development_only_result_is_not_offered_a_proof_to_verify(
    development_report: UpliftReport,
    receipts: dict[VariantName, list[EpisodeReceipt]],
) -> None:
    """It has no proof bundle, so offering the command would offer a failure."""
    payload = build(development_report, receipts, None)

    assert [action.id for action in payload.next_actions] == ["inspect_tasks"]


def test_the_score_bars_are_drawn_on_one_scale(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    bars = score_bars(build(report, receipts, verified()))

    assert [bar.label for bar in bars] == ["Baseline", "Candidate"]
    assert len({bar.maximum for bar in bars}) == 1
    assert len({len(bar.display) for bar in bars}) == 1


def _caveat(payload: UpliftPresentationPayload, code: str) -> PresentationCaveat:
    return next(caveat for caveat in payload.caveats if caveat.code == code)
