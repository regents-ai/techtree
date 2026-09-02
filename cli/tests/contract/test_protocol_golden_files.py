"""The committed protocol goldens. Spec sections 8, 24.4, 27.3.

A golden is a representative instance of a protocol object, generated from
typed Python and committed. These tests hold four things in place:

* Exactly the expected files exist, so a golden cannot quietly disappear.
* Each one still validates against its model, loaded the way stored documents
  are loaded — from bytes, in JSON mode.
* The formatting is deterministic, so a regeneration produces a diff only when
  the content actually changed.
* The fixture graph is internally consistent: the Climb's Campaign digest is
  the digest of the committed Campaign, and so on down.

The last one is the reason the goldens are worth having. A set of unrelated
example documents would prove that each model parses. A consistent graph proves
that the digests joining them mean what the protocol says they mean.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import canonical_json_bytes, digest_object, sha256_digest_bytes
from techtree.compatibility import compare_campaign_configurations
from techtree.identity.models import ExecutorIdentity
from techtree.models.approval import (
    MONETARY_AMOUNT_PATTERN,
    ExecutionApproval,
    RemoteExecutionEstimate,
)
from techtree.models.base import ObjectEnvelope
from techtree.models.campaign import (
    CampaignSpec,
    CampaignSpecV2,
    _CampaignScience,
)
from techtree.models.catalog import ClimbSummary, ClimbSummaryV2
from techtree.models.cli import CliEnvelope
from techtree.models.climb import ClimbManifest
from techtree.models.compatibility import (
    ConfigurationComparison,
    ConfigurationCompatibilityPolicy,
)
from techtree.models.data_policy import DataPolicy
from techtree.models.episode_receipt import EpisodeReceipt, EpisodeReceiptV2
from techtree.models.evidence import (
    ArtifactIntegrityStatus,
    ComparisonValidityStatus,
    EvidenceArtifactRef,
    EvidenceFacets,
    ExecutionLocationKind,
    ProviderAttestationStatus,
    ProviderRecordStatus,
    may_headline_uplift,
)
from techtree.models.execution_plan import ResolvedExecutionPlan
from techtree.models.experiment import (
    ExperimentManifest,
    ExperimentManifestV2,
    ExperimentVariant,
)
from techtree.models.run import RunRequestV2
from techtree.models.skill import SkillArtifact
from techtree.models.uplift_report import UpliftReport, UpliftReportV2
from techtree.models.validation import TasksetLock, TasksetValidationReceipt
from techtree.presentation.models import UpliftPresentationPayload
from techtree.receipts.execution import ComparisonExecutionRecord
from techtree.uplift.context import SkillImprovementContext

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIRECTORY = REPOSITORY_ROOT / "tests" / "golden"

#: Spec section 8. One representative instance per protocol object that a
#: reviewer should be able to read in a diff.
GOLDEN_MODELS: dict[str, type[BaseModel]] = {
    "campaign": CampaignSpec,
    # The second Campaign of the backend-parity pair. Two immutable Campaigns
    # are what a parity study compares, so the golden set holds both of them.
    "campaign-parity-candidate": CampaignSpec,
    "campaign-v2": CampaignSpecV2,
    "cli-envelope": CliEnvelope[ClimbSummary],
    "climb": ClimbManifest,
    # The v0.2 run-side documents. Every execution and subject fact in them
    # comes from the plan the Campaign binds, never from the Campaign.
    "climb-summary-v2": ClimbSummaryV2,
    # The same public Climb over the v0.2 Campaign. The wrapper's own shape
    # did not change in v0.2, so this is the v0.1 document naming the second
    # Campaign, committed so the v0.2 summary's edges can be checked.
    "climb-v2": ClimbManifest,
    # Not a protocol object either — decisions 0007 R6 puts the comparison's
    # operational record outside the frozen v0.1 protocol — and a golden for
    # the same reason: presentation and the plugin both read this shape.
    "comparison-execution": ComparisonExecutionRecord,
    "configuration-comparison": ConfigurationComparison,
    "configuration-compatibility-policy": ConfigurationCompatibilityPolicy,
    "data-policy": DataPolicy,
    "episode-receipt-v2": EpisodeReceiptV2,
    "execution-plan": ResolvedExecutionPlan,
    # The v0.2 evidence contract. Plan `docs/plan/v0.2.md`, "Evidence contract"
    # and "Evidence availability and proof closure".
    "evidence-artifact-ref": EvidenceArtifactRef,
    "evidence-facets": EvidenceFacets,
    "execution-approval": ExecutionApproval,
    "executor-identity": ExecutorIdentity,
    "experiment-baseline": ExperimentManifest,
    "experiment-baseline-v2": ExperimentManifestV2,
    "experiment-candidate": ExperimentManifest,
    "experiment-candidate-v2": ExperimentManifestV2,
    "fake-uplift-report": UpliftReport,
    # Not a protocol object — spec section 7.18's context is local working
    # material — but spec section 7.4 asks for the golden, because the shape
    # WP10's plugin builds against should change in a diff and not in silence.
    "improvement-context": SkillImprovementContext,
    "presentation-payload": UpliftPresentationPayload,
    "real-episode-receipt": ObjectEnvelope[EpisodeReceipt],
    "real-uplift-report": ObjectEnvelope[UpliftReport],
    "remote-execution-estimate": RemoteExecutionEstimate,
    "run-request-v2": RunRequestV2,
    "skill-artifact": SkillArtifact,
    "taskset-lock": TasksetLock,
    "taskset-validation-receipt": TasksetValidationReceipt,
    "uplift-report-v2": UpliftReportV2,
}


def golden_text(name: str) -> str:
    """Return one committed golden as text."""
    return (GOLDEN_DIRECTORY / f"{name}.json").read_text(encoding="utf-8")


def golden_document(name: str) -> dict[str, Any]:
    """Return one committed golden as a parsed document."""
    document: dict[str, Any] = json.loads(golden_text(name))
    return document


def load(name: str) -> Any:
    """Validate one committed golden the way a stored document is loaded."""
    return GOLDEN_MODELS[name].model_validate_json(golden_text(name))


def test_exactly_the_expected_goldens_are_committed() -> None:
    committed = {path.name for path in GOLDEN_DIRECTORY.iterdir()}

    assert committed == {f"{name}.json" for name in GOLDEN_MODELS}


@pytest.mark.parametrize("name", sorted(GOLDEN_MODELS))
def test_each_golden_validates_against_its_model(name: str) -> None:
    assert isinstance(load(name), BaseModel)


@pytest.mark.parametrize("name", sorted(GOLDEN_MODELS))
def test_each_golden_is_deterministically_formatted(name: str) -> None:
    text = golden_text(name)
    expected = json.dumps(
        json.loads(text), indent=2, sort_keys=True, ensure_ascii=False
    )

    assert text == f"{expected}\n"


@pytest.mark.parametrize("name", sorted(GOLDEN_MODELS))
def test_each_golden_round_trips_through_its_model(name: str) -> None:
    """Parsing and re-canonicalizing must reproduce the same bytes."""
    parsed = load(name)
    reparsed = GOLDEN_MODELS[name].model_validate_json(
        canonical_json_bytes(parsed).decode("utf-8")
    )

    assert canonical_json_bytes(reparsed) == canonical_json_bytes(parsed)


@pytest.mark.parametrize("name", sorted(GOLDEN_MODELS))
def test_each_golden_has_a_stable_digest(name: str) -> None:
    assert digest_object(load(name)) == digest_object(load(name))


@pytest.mark.parametrize("name", sorted(GOLDEN_MODELS))
def test_no_golden_mentions_relay(name: str) -> None:
    """Decisions 0001: no Relay package, field, exporter, or status."""
    assert "relay" not in golden_text(name).lower()


@pytest.mark.parametrize("name", sorted(GOLDEN_MODELS))
def test_no_golden_contains_a_local_path(name: str) -> None:
    """Absolute paths are host detail and never enter a protocol document."""
    text = golden_text(name)

    assert "/Users/" not in text
    assert "/home/" not in text
    assert "/private/var/" not in text


@pytest.mark.parametrize("name", sorted(GOLDEN_MODELS))
def test_no_golden_carries_a_credential_value(name: str) -> None:
    """A credential is named by an environment variable, never carried."""
    text = golden_text(name)

    assert "sk-" not in text
    assert "Bearer " not in text


# ---------------------------------------------------------------------------
# The fixture graph
# ---------------------------------------------------------------------------


def test_the_climb_points_at_the_committed_campaign() -> None:
    climb: ClimbManifest = load("climb")

    assert climb.campaign_spec_digest == digest_object(load("campaign"))


def test_the_v02_campaign_points_at_the_committed_execution_plan() -> None:
    campaign: CampaignSpecV2 = load("campaign-v2")

    assert campaign.execution_plan_digest == digest_object(load("execution-plan"))


def test_the_v02_campaign_restates_the_v01_scientific_contract() -> None:
    """The two goldens must be the same experiment, or the pair proves nothing."""
    v1: CampaignSpec = load("campaign")
    v2: CampaignSpecV2 = load("campaign-v2")

    shared = set(_CampaignScience.model_fields)
    assert {name: getattr(v2, name) for name in shared} == {
        name: getattr(v1, name) for name in shared
    }


def test_the_v02_campaign_golden_drops_what_the_plan_owns() -> None:
    """Read off the committed bytes, not off the model."""
    document = golden_document("campaign-v2")

    assert "evaluation_backend" not in document
    assert "verifiers_episode" not in document["evidence"]
    assert set(document["agents"]["subject"]["harness"]) == {
        "skills",
        "use_bundled_skill",
    }


def test_the_v02_climb_wraps_the_v02_campaign() -> None:
    climb: ClimbManifest = load("climb-v2")

    assert climb.campaign_spec_digest == digest_object(load("campaign-v2"))


#: Every v0.2 run-side golden, and where in it the bound plan is named. The
#: experiment manifests name it inside the configuration the two arms are
#: compared on; the climb summary names it through its compatibility result.
V2_RUN_SIDE_GOLDENS: dict[str, tuple[str, ...]] = {
    "climb-summary-v2": ("compatibility",),
    "episode-receipt-v2": (),
    "experiment-baseline-v2": ("configuration",),
    "experiment-candidate-v2": ("configuration",),
    "run-request-v2": (),
    "uplift-report-v2": (),
}


@pytest.mark.parametrize("name", sorted(V2_RUN_SIDE_GOLDENS))
def test_every_v02_run_side_golden_names_the_committed_plan(name: str) -> None:
    document = golden_document(name)
    for key in V2_RUN_SIDE_GOLDENS[name]:
        document = document[key]

    assert document["execution_plan_digest"] == digest_object(load("execution-plan"))


@pytest.mark.parametrize("name", sorted(V2_RUN_SIDE_GOLDENS))
def test_no_v02_run_side_golden_states_a_dropped_campaign_fact(name: str) -> None:
    """Read off the committed bytes: the words are simply not in the file."""
    text = golden_text(name)

    assert "evaluation_backend" not in text
    assert "verifiers_episode" not in text


def test_the_v02_run_side_goldens_anchor_to_the_v02_campaign() -> None:
    v2_digest = digest_object(load("campaign-v2"))
    anchored = (
        "episode-receipt-v2",
        "experiment-baseline-v2",
        "experiment-candidate-v2",
        "run-request-v2",
        "uplift-report-v2",
    )

    for name in anchored:
        assert golden_document(name)["campaign_spec_digest"] == v2_digest, name


def test_the_v02_receipt_and_report_say_where_the_work_ran() -> None:
    plan: ResolvedExecutionPlan = load("execution-plan")
    receipt: EpisodeReceiptV2 = load("episode-receipt-v2")
    report: UpliftReportV2 = load("uplift-report-v2")

    assert receipt.execution_location.kind.value == plan.execution.kind.value
    assert report.execution_location.kind.value == plan.execution.kind.value


def test_the_v02_experiments_are_the_two_variants_of_one_plan() -> None:
    baseline: ExperimentManifestV2 = load("experiment-baseline-v2")
    candidate: ExperimentManifestV2 = load("experiment-candidate-v2")

    assert baseline.variant is ExperimentVariant.BASELINE
    assert candidate.variant is ExperimentVariant.CANDIDATE
    assert (
        baseline.configuration.execution_plan_digest
        == candidate.configuration.execution_plan_digest
    )
    assert baseline.configuration_digest != candidate.configuration_digest


def test_the_v02_run_request_runs_the_two_committed_manifests() -> None:
    request: RunRequestV2 = load("run-request-v2")

    assert request.baseline_manifest_digest == digest_object(
        load("experiment-baseline-v2")
    )
    assert request.candidate_manifest_digest == digest_object(
        load("experiment-candidate-v2")
    )


def test_the_v02_report_compares_the_committed_v02_experiments() -> None:
    report: UpliftReportV2 = load("uplift-report-v2")
    baseline: ExperimentManifestV2 = load("experiment-baseline-v2")
    candidate: ExperimentManifestV2 = load("experiment-candidate-v2")

    assert report.baseline_manifest_digest == digest_object(baseline)
    assert report.candidate_manifest_digest == digest_object(candidate)
    assert (
        report.manifest_comparison.baseline_configuration_digest
        == baseline.configuration_digest
    )
    assert (
        report.manifest_comparison.candidate_configuration_digest
        == candidate.configuration_digest
    )


def test_the_two_experiment_manifests_reject_each_other_bytes() -> None:
    """Siblings, on decision 0040's terms: neither validates as the other."""
    with pytest.raises(PydanticValidationError):
        ExperimentManifest.model_validate_json(golden_text("experiment-baseline-v2"))
    with pytest.raises(PydanticValidationError):
        ExperimentManifestV2.model_validate_json(golden_text("experiment-baseline"))


def test_the_v02_summary_shows_the_harness_the_plan_names() -> None:
    summary: ClimbSummaryV2 = load("climb-summary-v2")
    plan: ResolvedExecutionPlan = load("execution-plan")

    assert summary.subject_harness == plan.subject.harness_id
    assert summary.subject_harness_version == plan.subject.harness_version
    assert summary.execution_backend_kind is plan.execution.kind
    assert summary.climb_digest == digest_object(load("climb-v2"))
    assert summary.campaign_spec_digest == digest_object(load("campaign-v2"))


def test_the_campaign_points_at_the_committed_data_policy() -> None:
    campaign: CampaignSpec = load("campaign")

    assert campaign.data_policy_digest == digest_object(load("data-policy"))


def test_the_campaign_points_at_the_committed_validation_receipt() -> None:
    campaign: CampaignSpec = load("campaign")

    assert campaign.taskset.validation_receipt_digest == digest_object(
        load("taskset-validation-receipt")
    )


def test_the_receipt_points_at_the_committed_lock() -> None:
    receipt: TasksetValidationReceipt = load("taskset-validation-receipt")

    assert receipt.taskset_lock_digest == digest_object(load("taskset-lock"))


def test_the_lock_and_the_campaign_commit_to_the_same_tasks() -> None:
    lock: TasksetLock = load("taskset-lock")
    campaign: CampaignSpec = load("campaign")

    assert lock.ordered_task_hashes == campaign.taskset.membership.ordered_task_hashes
    assert lock.membership_digest == campaign.taskset.membership.membership_digest


def test_the_compatibility_policy_names_the_committed_campaign() -> None:
    policy: ConfigurationCompatibilityPolicy = load(
        "configuration-compatibility-policy"
    )

    assert policy.source_campaign_digest == digest_object(load("campaign"))
    assert policy.purpose == "backend_parity"


def test_the_committed_comparison_is_the_one_the_comparator_computes() -> None:
    """The golden is the real output, so it cannot drift from the function."""
    policy: ConfigurationCompatibilityPolicy = load(
        "configuration-compatibility-policy"
    )
    stored: ConfigurationComparison = load("configuration-comparison")

    recomputed = compare_campaign_configurations(
        policy, load("campaign"), load("campaign-parity-candidate")
    )

    assert recomputed == stored


def test_the_comparison_names_the_committed_policy_and_both_campaigns() -> None:
    comparison: ConfigurationComparison = load("configuration-comparison")

    assert comparison.policy_digest == digest_object(
        load("configuration-compatibility-policy")
    )
    assert comparison.source_campaign_digest == digest_object(load("campaign"))
    assert comparison.candidate_campaign_digest == digest_object(
        load("campaign-parity-candidate")
    )


def test_the_parity_pair_drifts_only_where_the_policy_allows() -> None:
    """Spec: the two Campaigns are the same experiment on a second harness."""
    comparison: ConfigurationComparison = load("configuration-comparison")
    policy: ConfigurationCompatibilityPolicy = load(
        "configuration-compatibility-policy"
    )
    source: CampaignSpec = load("campaign")
    candidate: CampaignSpec = load("campaign-parity-candidate")

    assert comparison.compatibility == "compatible_with_declared_drift"
    assert set(comparison.observed_drift_paths) <= set(policy.allowed_drift_paths)
    assert source.subject.harness.id != candidate.subject.harness.id
    assert source.subject.model == candidate.subject.model
    assert source.taskset == candidate.taskset
    assert source.data_policy_digest == candidate.data_policy_digest


def test_both_experiments_reference_the_same_campaign_and_policy() -> None:
    baseline: ExperimentManifest = load("experiment-baseline")
    candidate: ExperimentManifest = load("experiment-candidate")

    assert baseline.campaign_spec_digest == candidate.campaign_spec_digest
    assert (
        baseline.configuration.data_policy_digest
        == candidate.configuration.data_policy_digest
    )
    assert (
        baseline.configuration.evaluation_backend
        == candidate.configuration.evaluation_backend
    )
    assert baseline.public_context == candidate.public_context
    assert baseline.program_ref == candidate.program_ref


def test_the_two_experiments_are_the_two_variants() -> None:
    assert load("experiment-baseline").variant is ExperimentVariant.BASELINE
    assert load("experiment-candidate").variant is ExperimentVariant.CANDIDATE


def test_the_candidate_carries_the_committed_skill_archive() -> None:
    candidate: ExperimentManifest = load("experiment-candidate")
    skill: SkillArtifact = load("skill-artifact")

    inserted = candidate.configuration.agents["subject"].harness.skills

    assert [reference.digest for reference in inserted] == [skill.archive_digest]


def test_the_fake_report_compares_the_committed_experiments() -> None:
    report: UpliftReport = load("fake-uplift-report")

    assert report.baseline_manifest_digest == digest_object(load("experiment-baseline"))
    assert report.candidate_manifest_digest == digest_object(
        load("experiment-candidate")
    )
    assert report.campaign_spec_digest == digest_object(load("campaign"))


def test_the_fake_report_is_unmistakably_a_development_artifact() -> None:
    report: UpliftReport = load("fake-uplift-report")

    assert report.proof_grade == "development_only"
    assert report.decision.value == "development_only"
    assert report.statuses.score.value == "development_only"
    assert report.statuses.evidence.value == "development_only"
    assert report.statuses.comparison.value == "development_only"
    assert report.statuses.publication.value == "blocked"
    assert report.publication_eligible is False


def test_the_real_report_states_what_it_measured_and_grades_itself_honestly() -> None:
    """Spec section 3.4: what a signed real report is allowed to claim."""
    sealed: ObjectEnvelope[UpliftReport] = load("real-uplift-report")
    report = sealed.payload

    assert report.proof_grade == "P1"
    assert report.decision.value == "accepted"
    assert report.statuses.score.value == "valid"
    assert report.statuses.evidence.value == "complete"
    assert report.statuses.comparison.value == "controlled_with_warnings"
    # Nothing has been published: a report is written before anybody is asked.
    # Sealed evidence under a policy that publishes the report is eligible to
    # be, which is what publishing one later requires. Decisions 0038.
    assert report.statuses.publication.value == "not_requested"
    assert report.publication_eligible is True


def test_the_real_receipt_is_a_verifiers_receipt_rather_than_a_fake_one() -> None:
    sealed: ObjectEnvelope[EpisodeReceipt] = load("real-episode-receipt")
    receipt = sealed.payload

    assert receipt.execution_backend == "verifiers"
    assert receipt.subject_runtime.kind == "docker"
    assert receipt.score_status.value == "valid"
    assert receipt.evidence_status.value == "complete"


@pytest.mark.parametrize("name", ["real-episode-receipt", "real-uplift-report"])
def test_a_signed_golden_carries_a_signature_over_its_own_payload(name: str) -> None:
    """The envelope's digest describes the payload it travels with."""
    sealed: ObjectEnvelope[Any] = load(name)

    assert sealed.signature is not None
    assert sealed.signature.algorithm == "ed25519"
    assert sealed.payload_digest == digest_object(sealed.payload)


@pytest.mark.parametrize("name", ["real-episode-receipt", "real-uplift-report"])
def test_a_signed_golden_verifies_against_the_fixture_identity(name: str) -> None:
    """A golden signature is checkable, which is the only thing that makes it
    worth committing: a stale one would be a silently unverifiable example."""
    from techtree.identity.service import verify_signed_object

    identity = _fixture_identity()
    sealed: ObjectEnvelope[Any] = load(name)

    assert sealed.signature is not None
    assert sealed.signature.key_id == identity.key_id
    assert verify_signed_object(identity=identity, envelope=sealed).verified


#: Every way a stored document could name the half of a key that never leaves
#: this machine. The bare word "private" is not one of them: spec section
#: 7.18's context lists "private environment values" among what it excludes,
#: and a test that failed on the word would be failing on the promise.
_PRIVATE_KEY_SPELLINGS = (
    "private_key",
    "private key",
    "privatekey",
    "secret_key",
    "begin private",
)


def test_no_golden_carries_private_key_material() -> None:
    """Only the public half of a key ever appears in a stored document."""
    for name in GOLDEN_MODELS:
        text = golden_text(name).lower()
        for spelling in _PRIVATE_KEY_SPELLINGS:
            assert spelling not in text, (name, spelling)


def test_the_improvement_context_carries_no_reply_and_no_hidden_material() -> None:
    """Spec section 7.18: the exclusions are visible in the committed bytes."""
    context: SkillImprovementContext = load("improvement-context")
    report: UpliftReport = load("real-uplift-report").payload

    assert context.source_run_id == report.run_id
    assert context.current_result == report.primary_result
    assert all(example.subject_reply is None for example in context.examples)
    assert "subject final replies" in context.prohibited_material
    assert "hidden expected answers" in context.prohibited_material
    # Regressions lead, because a bounded list is read from the top.
    assert [example.outcome for example in context.examples][:2] == [
        "regressed",
        "regressed",
    ]


def test_the_presentation_payload_says_only_what_the_report_says() -> None:
    """Spec section 7.13: a view of the report, never a second opinion."""
    payload: UpliftPresentationPayload = load("presentation-payload")
    report: UpliftReport = load("real-uplift-report").payload

    assert payload.run_id == report.run_id
    assert payload.decision == report.decision.value
    assert payload.proof_grade == report.proof_grade
    assert payload.baseline_score == report.primary_result.baseline_mean
    assert payload.candidate_score == report.primary_result.candidate_mean
    assert (payload.wins, payload.losses, payload.ties) == (
        report.primary_result.wins,
        report.primary_result.losses,
        report.primary_result.ties,
    )
    assert len(payload.task_rows) == len(report.task_deltas)


def test_the_presentation_payload_explains_p1_in_the_permitted_words() -> None:
    """Decisions 0005 section 3.4: never "independently reproduced"."""
    payload: UpliftPresentationPayload = load("presentation-payload")
    text = golden_text("presentation-payload")
    codes = {caveat.code for caveat in payload.caveats}

    absent = next(
        caveat
        for caveat in payload.caveats
        if caveat.code == "no_independent_reproduction"
    )

    assert "integrity-bound, participant-attested local execution" in text
    # The phrase may appear only as the denial it is.
    assert absent.text.startswith("Nobody has independently reproduced")
    assert text.count("independently reproduced") == 1
    assert {
        "local_participant_attestation",
        "no_independent_reproduction",
        "no_server_upload",
        "no_external_evidence_service",
    } <= codes


def _fixture_identity() -> ExecutorIdentity:
    """Return the committed public identity the signed goldens name."""
    identity: ExecutorIdentity = load("executor-identity")
    return identity


def test_the_evidence_facets_describe_the_committed_campaign() -> None:
    facets: EvidenceFacets = load("evidence-facets")

    assert facets.comparison_validity.campaign_digest == digest_object(load("campaign"))


def test_the_evidence_facets_are_what_v020_emits_and_nothing_more() -> None:
    """Plan `docs/plan/v0.2.md`: local, absent, and an empty reproduction list.

    The hosted values stay in the protocol so WP1 cuts it once. A golden that
    populated one would be documenting a capability this release does not have.
    """
    facets: EvidenceFacets = load("evidence-facets")
    observation = facets.execution_observation

    assert facets.execution_location.kind is ExecutionLocationKind.LOCAL
    assert observation.provider_record.status is ProviderRecordStatus.ABSENT
    assert observation.provider_attestation.status is ProviderAttestationStatus.ABSENT
    assert facets.reproductions == ()


def test_the_evidence_facets_golden_may_headline() -> None:
    """Integrity verified and the comparison valid, which is the whole rule."""
    facets: EvidenceFacets = load("evidence-facets")

    assert facets.artifact_integrity.status is ArtifactIntegrityStatus.VERIFIED
    assert facets.comparison_validity.status is ComparisonValidityStatus.VALID
    assert may_headline_uplift(facets)


def test_the_availability_statement_describes_the_committed_receipt() -> None:
    """The claim is checkable against the bytes it is a claim about."""
    reference: EvidenceArtifactRef = load("evidence-artifact-ref")
    sealed: ObjectEnvelope[EpisodeReceipt] = load("real-episode-receipt")

    assert reference.digest == digest_object(sealed)
    assert reference.size_bytes == len(canonical_json_bytes(sealed))
    assert reference.availability == "embedded_in_proof"
    assert reference.verification == "recomputable_from_bundle"


def test_the_approval_binds_the_committed_estimate_plan_budget_and_account() -> None:
    approval: ExecutionApproval = load("execution-approval")
    estimate: RemoteExecutionEstimate = load("remote-execution-estimate")

    assert approval.estimate_digest == digest_object(estimate)
    assert approval.execution_plan_digest == estimate.execution_plan_digest
    assert approval.maximum_authorized_cost == estimate.maximum_authorized_cost
    assert approval.billing_principal_label == estimate.billing_principal_label


def test_the_estimate_golden_prices_the_two_arms_separately() -> None:
    """The authorized maximum is what both arms together may spend."""
    estimate: RemoteExecutionEstimate = load("remote-execution-estimate")
    arms = estimate.per_arm_ceilings

    assert estimate.ceiling_scope.value == "per_arm_ceiling"
    assert arms is not None
    assert Decimal(arms.baseline) + Decimal(arms.candidate) == Decimal(
        estimate.maximum_authorized_cost
    )


def test_the_approval_golden_was_given_by_a_person() -> None:
    """Plan `docs/plan/v0.2.md`: the model never approves paid inference."""
    approval: ExecutionApproval = load("execution-approval")

    assert approval.approval_method.value == "terminal_confirmation"


def test_the_cli_envelope_golden_carries_the_committed_climb_summary() -> None:
    envelope: CliEnvelope[ClimbSummary] = load("cli-envelope")
    climb: ClimbManifest = load("climb")

    assert envelope.ok is True
    assert envelope.error is None
    assert envelope.data is not None
    assert envelope.data.climb_digest == digest_object(climb)
    assert envelope.data.campaign_spec_digest == climb.campaign_spec_digest
    assert len(envelope.next_actions) <= 3


# ---------------------------------------------------------------------------
# Digest sensitivity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "pointer"),
    [
        ("campaign", ("scoring", "minimum_absolute_delta")),
        ("climb", ("metadata", "title")),
        ("data-policy", ("raw_episodes", "reproduction_access")),
        ("evidence-artifact-ref", ("size_bytes",)),
        ("evidence-facets", ("comparison_validity", "campaign_digest")),
        ("execution-approval", ("estimate_digest",)),
        ("execution-approval", ("maximum_authorized_cost",)),
        ("remote-execution-estimate", ("execution_plan_digest",)),
        # The authorized maximum is the sum of the two arm ceilings, so it
        # cannot be moved on its own. The approval golden carries the
        # unconstrained copy of the same number, and is tampered with above.
        ("remote-execution-estimate", ("estimated_cost",)),
        ("taskset-lock", ("engine_digest",)),
        # The v0.2 run-side documents. Each execution fact they take from the
        # plan is part of what they are, so moving one produces a different
        # document rather than the same document under a new backend.
        ("climb-summary-v2", ("subject_harness_version",)),
        ("climb-summary-v2", ("compatibility", "execution_plan_digest")),
        ("episode-receipt-v2", ("execution_plan_digest",)),
        ("episode-receipt-v2", ("execution_location", "kind")),
        ("experiment-baseline-v2", ("configuration", "execution_plan_digest")),
        ("run-request-v2", ("execution_plan_digest",)),
        ("uplift-report-v2", ("execution_plan_digest",)),
        ("uplift-report-v2", ("execution_location", "kind")),
    ],
)
def test_one_changed_field_changes_the_digest(
    name: str, pointer: tuple[str, ...]
) -> None:
    original = load(name)
    document = golden_document(name)

    target: Any = document
    for key in pointer[:-1]:
        target = target[key]
    current = target[pointer[-1]]
    target[pointer[-1]] = (
        sha256_digest_bytes(b"changed")
        if isinstance(current, str) and current.startswith("sha256:")
        else _changed(current)
    )

    changed = GOLDEN_MODELS[name].model_validate_json(json.dumps(document))

    assert digest_object(changed) != digest_object(original)


def _changed(value: Any) -> Any:
    """Return a different but still valid value of the same kind."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, int | float):
        return value + 1
    if value == "prohibited":
        return "allowed"
    if value == "consent_required":
        return "prohibited"
    # An execution location is one of two words, so the only different value
    # it can take is the other one.
    if value == "local":
        return "prime_hosted"
    # A monetary amount has one canonical spelling, so it cannot be changed by
    # appending to it. Raising the whole units keeps the result an amount.
    if isinstance(value, str) and re.fullmatch(MONETARY_AMOUNT_PATTERN, value):
        whole, _, fraction = value.partition(".")
        raised = str(int(whole) + 1)
        return f"{raised}.{fraction}" if fraction else raised
    return f"{value} (changed)"
