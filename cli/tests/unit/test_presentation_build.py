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

import io

import pytest
from rich.console import Console

from fixtures.receipts.pair import RecordedPair, recorded_pair
from fixtures.receipts.proof import execution_record as fixture_execution_record
from techtree.canonical import canonical_json_bytes
from techtree.identity.models import VerificationMessage, VerificationResult
from techtree.models.campaign import SUBJECT_AGENT, CampaignSpec, VariantSchedule
from techtree.models.episode_receipt import EpisodeReceipt
from techtree.models.experiment import ExperimentVariant
from techtree.models.skill import SkillArtifact, SkillFile
from techtree.models.uplift_report import UpliftReport
from techtree.presentation.build import (
    BASELINE_SKILL_LABEL,
    FIRST_CHANGE_LABEL,
    FIRST_RESULT_LABEL,
    HELD_FIXED_LINE,
    LATER_RESULT_LABEL,
    P1_MEANING,
    SECOND_CHANGE_LABEL,
    SECOND_RESULT_LABEL,
    VERIFICATION_FAILED,
    VERIFICATION_NOT_VERIFIED,
    VERIFICATION_VERIFIED,
    build_uplift_presentation,
    cost_explanation,
    cost_summary,
    efficiency_sentence,
    score_bars,
    task_count_line,
)
from techtree.presentation.compact import render_uplift_markdown
from techtree.presentation.evidence import RecordedEvidence, VariantEvidence
from techtree.presentation.models import (
    PresentationCaveat,
    UpliftPresentationPayload,
)
from techtree.presentation.rich import (
    TaskDisplay,
    render_uplift_console,
    verdict_line,
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


def candidate_skill(
    *,
    name: str = "branch-code-v1",
    root: str = "a",
    parent_skill_digest: str | None = None,
) -> SkillArtifact:
    return SkillArtifact(
        schema_version="techtree.skill.v1alpha1",
        name=name,
        root_digest=f"sha256:{root * 64}",
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
        parent_skill_digest=parent_skill_digest,
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
    recorded_evidence: RecordedEvidence | None = None,
    campaign: CampaignSpec | None = None,
) -> UpliftPresentationPayload:
    return build_uplift_presentation(
        report=report,
        campaign=recorded_pair().campaign if campaign is None else campaign,
        baseline_receipts=receipts[VariantName.BASELINE],
        candidate_receipts=receipts[VariantName.CANDIDATE],
        campaign_title=CAMPAIGN_TITLE,
        baseline_skill=None,
        candidate_skill=candidate_skill(),
        verification=verification,
        execution_record=execution_record,
        recorded_evidence=recorded_evidence,
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
    assert payload.candidate_score == pytest.approx(24 / 36)
    assert payload.absolute_delta == pytest.approx(24 / 36)
    # A zero baseline has no relative change; reporting one would invent it.
    assert payload.relative_delta is None
    assert (payload.wins, payload.losses, payload.ties) == (24, 0, 12)
    assert sorted(set(row.outcome for row in payload.task_rows)) == ["tie", "win"]


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
    assert payload.change_label == FIRST_CHANGE_LABEL
    assert payload.baseline_skill.label == BASELINE_SKILL_LABEL
    assert payload.baseline_skill.root_digest is None
    assert payload.candidate_skill.label == "branch-code-v1"
    assert payload.candidate_skill.file_count == 1


def _compare(
    report: UpliftReport,
    receipts: dict[VariantName, list[EpisodeReceipt]],
    *,
    baseline: SkillArtifact | None,
    candidate: SkillArtifact,
) -> UpliftPresentationPayload:
    """Build one payload over an arbitrary pair of Skills."""
    return build_uplift_presentation(
        report=report,
        campaign=recorded_pair().campaign,
        baseline_receipts=receipts[VariantName.BASELINE],
        candidate_receipts=receipts[VariantName.CANDIDATE],
        campaign_title=CAMPAIGN_TITLE,
        baseline_skill=baseline,
        candidate_skill=candidate,
        verification=verified(),
    )


def test_a_replacement_comparison_says_what_it_compared(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """Decisions 0019 s1: the baseline is a Skill here, and is named as one."""
    payload = _compare(
        report,
        receipts,
        baseline=candidate_skill(name="branch-code-v1"),
        candidate=candidate_skill(
            name="branch-code-v2", root="d", parent_skill_digest=f"sha256:{'a' * 64}"
        ),
    )

    assert payload.comparison_label == SECOND_RESULT_LABEL
    assert payload.change_label == SECOND_CHANGE_LABEL
    assert payload.baseline_skill.label == "branch-code-v1"
    assert payload.baseline_skill.label != BASELINE_SKILL_LABEL
    assert payload.baseline_skill.root_digest is not None
    assert payload.candidate_skill.label == "branch-code-v2"


def test_a_third_comparison_is_not_labelled_as_the_second(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """The ordinal comes from the chain, so it stops where the chain does.

    A baseline that is itself a revision means this comparison is at least the
    third, and the run's own two Skills cannot say which. Naming the Skills is
    what a reader can act on; claiming "Iteration 2" would be a receipt for
    work nobody did.
    """
    payload = _compare(
        report,
        receipts,
        baseline=candidate_skill(
            name="branch-code-v2", root="d", parent_skill_digest=f"sha256:{'a' * 64}"
        ),
        candidate=candidate_skill(
            name="branch-code-v3", root="e", parent_skill_digest=f"sha256:{'d' * 64}"
        ),
    )

    assert payload.comparison_label == LATER_RESULT_LABEL
    assert payload.change_label == "branch-code-v2 → branch-code-v3"


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


def test_a_run_the_provider_priced_nothing_for_still_gets_a_derived_figure(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """techtree-python-nom. Every token was recorded, so a cost is workable.

    The signed record's own cost stays absent, because nothing may be written
    back into it. The figure is worked out from the tokens it already holds
    and the prices this release recorded, and it says which of the two it is.
    """
    record = execution_record(report)
    payload = build(report, receipts, verified(), record)

    assert payload.cost_usd is None
    assert payload.cost_provenance is CostProvenance.UNAVAILABLE
    derived = payload.derived_cost
    assert derived is not None
    assert derived.input_tokens == 2 * 2048
    assert derived.output_tokens == 2 * 256
    assert derived.usd == pytest.approx((4096 * 0.03 + 512 * 0.13) / 1_000_000)
    assert derived.model_id == "qwen/qwen3.7-flash"
    assert payload.cost_unavailable_reason is None
    assert _caveat(payload, "cost_derived_while_rendering").severity == "info"


def test_a_derived_figure_says_it_was_worked_out_and_names_what_from(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """techtree-python-nom. The sentence a reader judges the number by."""
    payload = build(report, receipts, verified(), execution_record(report))

    assert "not billed" in cost_summary(payload)
    explanation = " ".join(cost_explanation(payload))
    assert "4,096 input and 512 output tokens" in explanation
    assert "Your provider's bill is what you actually pay." in explanation


def test_a_reported_cost_is_preferred_over_one_that_could_be_worked_out(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """techtree-python-nom. A bill beats arithmetic wherever there is one."""
    cost = VariantCost(
        cost_usd=2.5,
        provenance=CostProvenance.PROVIDER_REPORTED,
        detail="from the feed",
    )
    payload = build(
        report,
        receipts,
        verified(),
        execution_record(report, costs={"baseline": cost, "candidate": cost}),
    )

    assert payload.derived_cost is None
    assert payload.cost_usd == 5.0
    assert cost_summary(payload) == "$5.00, reported by the provider"
    assert cost_explanation(payload) == []


def test_cached_input_is_priced_at_the_full_rate_and_said_to_be(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """techtree-python-nom. An unstated discount is never quietly assumed."""
    record = execution_record(report)
    cached = record.baseline.usage.model_copy(update={"cached_input_tokens": 1024})
    payload = build(
        report,
        receipts,
        verified(),
        record.model_copy(
            update={"baseline": record.baseline.model_copy(update={"usage": cached})}
        ),
    )

    derived = payload.derived_cost
    assert derived is not None
    assert derived.cached_input_tokens == 1024
    assert derived.prices_name_a_cached_rate is False
    # The figure is the same as the one with no cache at all: nothing was
    # discounted, and the reader is told the number is on the high side.
    assert derived.usd == pytest.approx((4096 * 0.03 + 512 * 0.13) / 1_000_000)
    explanation = " ".join(cost_explanation(payload))
    assert "1,024 of those input tokens came back from the provider's cache" in (
        explanation
    )
    assert "on the high side" in explanation


def test_a_run_with_no_execution_record_says_which_half_is_missing(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """techtree-python-nom. "Unavailable" alone tells a reader nothing."""
    payload = build(report, receipts, verified())

    assert payload.derived_cost is None
    assert payload.cost_usd is None
    reason = payload.cost_unavailable_reason
    assert reason is not None
    assert "no signed execution record" in reason
    assert cost_summary(payload) == "unavailable"
    assert cost_explanation(payload) == [reason]


def test_a_model_this_release_priced_nothing_for_invents_no_cost(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """techtree-python-nom. A missing price is stated, never guessed around."""
    payload = build(
        report,
        receipts,
        verified(),
        execution_record(report),
        campaign=_measuring("some-vendor/unpriced-model"),
    )

    assert payload.derived_cost is None
    reason = payload.cost_unavailable_reason
    assert reason is not None
    assert "recorded no provider prices" in reason
    assert "some-vendor/unpriced-model" in reason


# ---------------------------------------------------------------------------
# The count, the turns, the throttling and the named coordinate
# ---------------------------------------------------------------------------


def seen(
    *,
    baseline_turns: int = 406,
    candidate_turns: int = 73,
    baseline_refused: int = 4,
    candidate_refused: int = 0,
    completed: bool = True,
) -> RecordedEvidence:
    """Return one reading of a run's own recorded files."""
    return RecordedEvidence(
        baseline=VariantEvidence(
            model_turns=baseline_turns,
            rollouts=2,
            rollouts_completed=2 if completed else 1,
            rate_limited_calls=baseline_refused,
        ),
        candidate=VariantEvidence(
            model_turns=candidate_turns,
            rollouts=2,
            rollouts_completed=2,
            rate_limited_calls=candidate_refused,
        ),
    )


def test_the_headline_is_offered_as_a_count_of_tasks(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """techtree-python-of9. The recorded pair is 0 of 36 against 24 of 36."""
    payload = build(report, receipts, verified())

    assert payload.baseline_tasks_scored_full == 0
    assert payload.candidate_tasks_scored_full == 24
    assert task_count_line(payload) == "0 of 36 → 24 of 36 (+24)"


def test_a_reward_that_is_not_all_or_nothing_gets_no_invented_count(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """techtree-python-of9. A task scored 0.4 was neither right nor wrong."""
    payload = build(report, receipts, verified())
    partial = payload.task_rows[0].model_copy(
        update={"candidate_score": 0.4, "delta": 0.4}
    )
    graded = payload.model_copy(
        update={
            "task_rows": [partial, *payload.task_rows[1:]],
            "baseline_tasks_scored_full": None,
            "candidate_tasks_scored_full": None,
        }
    )

    assert task_count_line(graded) is None


def test_the_turn_counts_are_carried_and_read_as_a_finding(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """techtree-python-bmk. Two bare durations are not a finding; this is."""
    payload = build(
        report, receipts, verified(), execution_record(report), recorded_evidence=seen()
    )

    assert payload.baseline_model_turns == 406
    assert payload.candidate_model_turns == 73
    sentence = efficiency_sentence(payload)
    assert sentence is not None
    assert "73 model turns against the baseline's 406" in sentence
    assert "finished in 90.0s against 90.0s" in sentence
    assert "also depends on this machine" in sentence


def test_a_run_whose_files_could_not_be_read_claims_no_turns(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """techtree-python-bmk. Nothing is inferred from a reading that failed."""
    payload = build(report, receipts, verified(), execution_record(report))

    assert payload.baseline_model_turns is None
    assert payload.every_rollout_completed is None
    assert efficiency_sentence(payload) is None


def test_an_asymmetric_rate_limit_is_a_warning_that_names_both_sides(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """techtree-python-vmp. The founder found this by reading raw eval logs."""
    payload = build(report, receipts, verified(), recorded_evidence=seen())

    caveat = _caveat(payload, "provider_rate_limiting")
    assert caveat.severity == "warning"
    assert caveat.text == (
        "The provider refused 4 model calls with a rate limit on the baseline "
        "side and 0 on the candidate side. Every rollout still ran to completion."
    )


def test_an_even_rate_limit_is_stated_without_being_a_qualification(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """techtree-python-vmp. Nothing is asymmetric, so nothing is qualified."""
    payload = build(
        report,
        receipts,
        verified(),
        recorded_evidence=seen(baseline_refused=0, candidate_refused=0),
    )

    caveat = _caveat(payload, "provider_rate_limiting")
    assert caveat.severity == "info"
    assert caveat.text.startswith("The provider refused no model call on either side.")


def test_a_rollout_that_did_not_complete_is_not_claimed_to_have(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """techtree-python-vmp. The completion clause is a claim, and it is checked."""
    payload = build(
        report, receipts, verified(), recorded_evidence=seen(completed=False)
    )

    assert payload.every_rollout_completed is False
    assert (
        "still ran to completion" not in _caveat(payload, "provider_rate_limiting").text
    )


def test_a_run_with_no_reading_says_nothing_about_throttling(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """techtree-python-vmp. Silence, never a zero nobody counted."""
    payload = build(report, receipts, verified())

    assert [caveat.code for caveat in payload.caveats].count(
        "provider_rate_limiting"
    ) == 0


def test_the_weak_attestation_warning_names_the_coordinate(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """techtree-python-6rq. "At least one coordinate" is true and unusable."""
    payload = build(report, receipts, verified())

    text = _caveat(payload, "comparison_controlled_with_warnings").text
    assert "no immutable build identifier for qwen/qwen3.7-flash" in text
    assert "not provably the same model build" in text
    assert "a mismatch would have made the comparison invalid" in text


def test_a_cause_this_build_cannot_name_keeps_the_general_wording(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> None:
    """techtree-python-6rq. The model-revision sentence is never borrowed.

    The Campaign here publishes a model revision, so the one warning this build
    knows how to name is not the one this comparison recorded. The reader gets
    the honest general sentence rather than a plausible wrong cause.
    """
    payload = build(
        report,
        receipts,
        verified(),
        campaign=_measuring("qwen/qwen3.7-flash", revision="2026-08-01"),
    )

    text = _caveat(payload, "comparison_controlled_with_warnings").text
    assert "no plainer name for it" in text
    assert "model build" not in text


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


def _measuring(model_id: str, *, revision: str | None = None) -> CampaignSpec:
    """Return the recorded Campaign with a different subject model on it."""
    campaign = recorded_pair().campaign
    subject = campaign.subject
    return campaign.model_copy(
        update={
            "agents": {
                **campaign.agents,
                SUBJECT_AGENT: subject.model_copy(
                    update={
                        "model": subject.model.model_copy(
                            update={"model_id": model_id, "revision": revision}
                        )
                    }
                ),
            }
        }
    )


# ---------------------------------------------------------------------------
# The four statements
#
# Decisions document 0019 section 3 fixes what the public experience says, and
# it says it through both channels or through neither. These read a real
# payload — the one the recorded probes produce — through both renderers and
# require all four statements out of each.
# ---------------------------------------------------------------------------


def _flat(text: str) -> str:
    """Return one rendering with its line wrapping undone.

    The terminal wraps to its width, so a sentence a reader meets as one
    sentence is several lines of bytes. Comparing the sentence rather than the
    lines is what keeps a wording assertion from being a layout assertion.
    """
    return " ".join(text.split())


def _terminal(payload: UpliftPresentationPayload) -> str:
    """Render one payload the way a terminal shows it."""
    output = io.StringIO()
    console = Console(
        file=output,
        width=100,
        no_color=True,
        highlight=False,
        emoji=False,
        markup=False,
    )
    render_uplift_console(payload, console, show_tasks=TaskDisplay.ALL)
    return output.getvalue()


@pytest.fixture
def channels(
    report: UpliftReport, receipts: dict[VariantName, list[EpisodeReceipt]]
) -> tuple[UpliftPresentationPayload, str, str]:
    """Return one real payload and both renderings of it."""
    payload = build(report, receipts, verified(), execution_record(report))
    return payload, _terminal(payload), render_uplift_markdown(payload)


def test_both_channels_say_the_system_was_the_same_on_both_sides(
    channels: tuple[UpliftPresentationPayload, str, str],
) -> None:
    """Statement 1: same agent and same tasks."""
    _, terminal, gateway = channels

    for text in (terminal, gateway):
        assert HELD_FIXED_LINE in _flat(text)
    assert "checked against what the run actually did" in _flat(terminal)


def test_both_channels_say_the_skill_was_the_only_change(
    channels: tuple[UpliftPresentationPayload, str, str],
) -> None:
    """Statement 2: the one changed component, named on both sides."""
    payload, terminal, gateway = channels

    assert payload.change_label == FIRST_CHANGE_LABEL
    for text in (terminal, gateway):
        assert payload.change_label in text
    # The complete bundle is content-addressed, and the terminal has room to
    # print the address a reader would check it by.
    assert payload.candidate_skill.root_digest is not None
    assert payload.candidate_skill.root_digest in terminal


def test_both_channels_say_what_the_measured_difference_was(
    channels: tuple[UpliftPresentationPayload, str, str],
) -> None:
    """Statement 3: scores, uplift, outcomes, cost, timing, regressions, validity."""
    payload, terminal, gateway = channels

    assert f"{payload.baseline_score:.3f}" in terminal
    assert f"{payload.candidate_score:.3f}" in terminal
    assert f"{payload.absolute_delta:+.3f}" in terminal
    outcomes = f"{payload.wins} WIN / {payload.losses} LOSS / {payload.ties} TIE"
    assert outcomes in terminal
    assert verdict_line(payload) in terminal
    assert "Cost" in terminal
    assert "Time" in terminal

    assert f"{payload.baseline_score:.3f} → {payload.candidate_score:.3f}" in gateway
    assert f"{payload.absolute_delta:+.3f}" in gateway
    assert (
        f"- Tasks: {payload.wins} win, {payload.losses} loss, {payload.ties} tie"
    ) in gateway
    assert "- Cost:" in gateway
    assert "- Time:" in gateway


def test_both_channels_say_what_the_receipt_is_worth_and_how_to_check_it(
    channels: tuple[UpliftPresentationPayload, str, str],
) -> None:
    """Statement 4: the local receipt, in the four words it may be described in.

    The terminal does not print the command itself. Every Techtree command ends
    with one next-steps block, rendered by the CLI from the envelope, and the
    payload carries the action that block prints; a result that drew a second
    one would answer the same question twice.
    """
    payload, terminal, gateway = channels

    for text in (terminal, gateway):
        assert P1_MEANING in text
        assert "offline" in text
        assert "independently reproduced" in text

    assert "techtree proof verify" in gateway
    verify = next(
        action for action in payload.next_actions if action.id == "verify_proof"
    )
    assert verify.cli == ["techtree", "proof", "verify", payload.run_id]
