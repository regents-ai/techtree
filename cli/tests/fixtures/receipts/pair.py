"""One controlled comparison, assembled from the two recorded probes.

``fixtures.receipts.support`` loads each paid probe on its own: one baseline and
one candidate, two tasks each, the candidate with the ``branch-code-v1`` Skill
mounted, both of ``qwen/qwen3.7-flash`` in real Docker containers on 2026-08-13.
They were separate probe runs, so each carries its own run request and its own
experiment manifest, and nothing joins them into a comparison.

This module joins them, and is explicit about which half is recorded and which
half is re-derived.

RECORDED, UNTOUCHED
    Every episode, every reward, every tool digest, every runtime record and
    both resolved ``config.toml`` files. The evidence a report is built from is
    exactly the evidence the paid probes produced.

RE-DERIVED, AND WHY
    The declared documents. Both probes were run under the Campaign
    ``fixtures.verifiers.support`` derives, which :func:`recorded_pair` checks
    rather than assumes — but that Campaign commits to thirty-six tasks and only
    two of them were ever scored on both sides. So the Campaign's committed
    membership, and with it the two manifests, the run request and the taskset
    lock, are re-issued over exactly those two tasks. Every scientific
    coordinate in them — model, sampling, harness, runtime image, mutation
    contract, scoring rule, DataPolicy, the candidate Skill's root digest — is
    the recorded one, unchanged.

What that buys is a comparison that is real where it matters: two variants of
one Campaign, differing only in a mounted Skill, with a measured 0/2 against
2/2 on ``exact_match`` and a tool surface that differs in exactly the one
description Hermes renders its Skill index into.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

from fixtures.receipts.support import RecordedVariant, recorded_variant
from techtree.canonical import digest_object
from techtree.catalog.repository import EmbeddedCatalogRepository
from techtree.constants import TASKSET_LOCK_SCHEMA_VERSION
from techtree.engines.bundle import default_engine_digest
from techtree.manifests.builder import (
    build_experiment_configuration,
    finalize_manifest,
)
from techtree.manifests.compare import compare_manifests
from techtree.models.base import ArtifactRef, Digest
from techtree.models.campaign import (
    SUBJECT_AGENT,
    AgentSpec,
    CampaignSpec,
    CampaignTaskset,
    HarnessSpec,
    TaskMembershipCommitment,
    TaskSelection,
)
from techtree.models.data_policy import DataPolicy
from techtree.models.episode_receipt import EpisodeReceipt
from techtree.models.experiment import (
    ExperimentConfiguration,
    ExperimentManifest,
    ExperimentVariant,
    ManifestComparison,
)
from techtree.models.run import PolicyAcknowledgement, RunRequest
from techtree.models.uplift_report import UpliftReport
from techtree.models.validation import TasksetLock
from techtree.receipts.compare import (
    ObservedVariant,
    compare_real_variants,
    observe_variant,
)
from techtree.receipts.episode import build_variant_receipts, experiment_variant_of
from techtree.receipts.set import ReceiptSetManifest, build_receipt_set, seal_receipt
from techtree.receipts.uplift import (
    LocalAttestation,
    aggregate_primary_result,
    build_uplift_report,
    pair_task_rewards,
    summarize_receipts,
)
from techtree.runs.real import executor_kind_for
from techtree.tasksets.membership import membership_digest
from techtree.verifiers.models import VariantExecutionResult, VariantName

__all__ = [
    "RecordedPair",
    "recorded_pair",
    "recorded_report",
    "trimmed_campaign",
]

#: A moment inside the window the probes ran in. Fixed rather than current so
#: that two loads of this fixture produce the same documents.
_FIXTURE_INSTANT: Final = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class RecordedPair:
    """Both sides of one controlled comparison, declared and observed."""

    campaign: CampaignSpec
    campaign_digest: Digest
    baseline_manifest: ExperimentManifest
    candidate_manifest: ExperimentManifest
    prepared_comparison: ManifestComparison
    request: RunRequest
    taskset_lock: TasksetLock
    results: dict[VariantName, VariantExecutionResult]
    resolved_configs: dict[VariantName, dict[str, Any]]

    @property
    def primary_reward(self) -> str:
        """The reward this Campaign's comparison is decided on."""
        return self.campaign.scoring.primary_reward

    @property
    def ordered_task_hashes(self) -> list[Digest]:
        """The tasks both probes scored, in committed order."""
        return list(self.campaign.taskset.membership.ordered_task_hashes)

    def manifest(self, variant: VariantName) -> ExperimentManifest:
        """Return one side's declared manifest."""
        return (
            self.baseline_manifest
            if variant is VariantName.BASELINE
            else self.candidate_manifest
        )

    def observed(self, variant: VariantName) -> ObservedVariant:
        """Fingerprint one side from its own recorded evidence."""
        return observe_variant(
            result=self.results[variant],
            resolved_config=self.resolved_configs[variant],
            runtime=self.campaign.agents[SUBJECT_AGENT].runtime,
        )

    def receipts(self, variant: VariantName) -> list[EpisodeReceipt]:
        """Build one side's receipts from its recorded evidence."""
        return build_variant_receipts(
            run_request=self.request,
            variant=variant,
            experiment=self.manifest(variant),
            result=self.results[variant],
            evaluation_backend=self.campaign.evaluation_backend,
            ordered_task_hashes=self.ordered_task_hashes,
            primary_reward=self.primary_reward,
            evidence=self.campaign.evidence,
        )


def recorded_report(
    pair: RecordedPair,
    *,
    attestation: LocalAttestation = LocalAttestation.LOCAL_ED25519,
) -> UpliftReport:
    """Build the report the recorded comparison produces, through the real code.

    Every step is the production one — the observed comparison, the paired
    rewards, the aggregate, the report builder — so a test that needs "a report
    of this run" gets the report of this run rather than an approximation of
    one.
    """
    receipts = {
        variant: pair.receipts(variant)
        for variant in (VariantName.BASELINE, VariantName.CANDIDATE)
    }
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
        schedule=pair.campaign.execution.order,
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
        data_policy=recorded_data_policy(pair.campaign),
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
    """Commit to one side's receipts the way a run does."""
    return build_receipt_set(
        run_id=pair.request.run_id,
        variant=experiment_variant_of(variant),
        experiment_manifest_digest=digest_object(pair.manifest(variant)),
        signed_receipts=[seal_receipt(receipt) for receipt in receipts[variant]],
        ordered_task_hashes=pair.ordered_task_hashes,
    )


def recorded_data_policy(campaign: CampaignSpec) -> DataPolicy:
    """Return the rights statement one Campaign runs under.

    Loaded from the packaged catalog by the digest the Campaign itself names,
    so a fixture cannot pair a Campaign with a policy it was not executed
    under — which is exactly what ``build_uplift_report`` refuses to do.
    """
    return EmbeddedCatalogRepository.packaged().load_data_policy(
        campaign.data_policy_digest
    )


def trimmed_campaign(task_hashes: list[Digest] | None = None) -> CampaignSpec:
    """Return the recorded run's own Campaign, committed to the tasks it scored.

    Read from the evidence rather than re-derived from the source tree. The
    Campaign a run executed is a fact about that run, and asking the current
    tree to reproduce it means the fixture stops working every time a release
    coordinate moves — which it did, on the membership change and again on the
    sampling cap. Worse, it made the re-derivation correct by assertion where
    it can simply be correct by construction: the manifests, the request and
    the lock below are now built from the Campaign the evidence names, so they
    cannot describe a different experiment than the episodes beside them.

    Only the committed membership is narrowed, and only to tasks the recorded
    evidence actually covers.
    """
    full = recorded_variant(VariantName.CANDIDATE).campaign
    committed = task_hashes or _shared_task_hashes()
    return CampaignSpec(
        **{
            **dict(full),
            "taskset": CampaignTaskset(
                ref=full.taskset.ref,
                selection=TaskSelection(
                    num_tasks=len(committed), num_rollouts=1, shuffle=False
                ),
                membership=TaskMembershipCommitment(
                    mode="committed",
                    ordered_task_hashes=list(committed),
                    membership_digest=membership_digest(committed),
                ),
                validation_receipt_digest=full.taskset.validation_receipt_digest,
            ),
        }
    )


def recorded_pair(
    *,
    campaign: CampaignSpec | None = None,
    baseline_manifest: ExperimentManifest | None = None,
    candidate_manifest: ExperimentManifest | None = None,
    request: RunRequest | None = None,
) -> RecordedPair:
    """Assemble one controlled comparison over the recorded probe evidence.

    The declared documents may be supplied by a caller that staged a real run
    and therefore already owns them; otherwise they are built here from the
    same Campaign through the same manifest builder the run service uses.
    """
    probes = {
        variant: recorded_variant(variant)
        for variant in (VariantName.BASELINE, VariantName.CANDIDATE)
    }
    _require_recorded_campaign(probes[VariantName.CANDIDATE])

    resolved_campaign = campaign or trimmed_campaign()
    campaign_digest = digest_object(resolved_campaign)
    committed = list(resolved_campaign.taskset.membership.ordered_task_hashes)

    baseline = baseline_manifest or _manifest(
        resolved_campaign, campaign_digest, ExperimentVariant.BASELINE, skill=None
    )
    candidate = candidate_manifest or _manifest(
        resolved_campaign,
        campaign_digest,
        ExperimentVariant.CANDIDATE,
        skill=_recorded_skill_reference(probes[VariantName.CANDIDATE]),
    )

    return RecordedPair(
        campaign=resolved_campaign,
        campaign_digest=campaign_digest,
        baseline_manifest=baseline,
        candidate_manifest=candidate,
        prepared_comparison=compare_manifests(
            baseline, candidate, resolved_campaign.mutation_contract
        ),
        request=request
        or _request(
            campaign=resolved_campaign,
            campaign_digest=campaign_digest,
            baseline=baseline,
            candidate=candidate,
        ),
        taskset_lock=_taskset_lock(resolved_campaign),
        results={
            variant: restrict_to_tasks(
                probes[variant].result,
                committed,
                experiment_manifest_digest=digest_object(
                    baseline if variant is VariantName.BASELINE else candidate
                ),
            )
            for variant in (VariantName.BASELINE, VariantName.CANDIDATE)
        },
        resolved_configs={
            variant: probes[variant].resolved_config
            for variant in (VariantName.BASELINE, VariantName.CANDIDATE)
        },
    )


def restrict_to_tasks(
    result: VariantExecutionResult,
    task_hashes: list[Digest],
    *,
    experiment_manifest_digest: Digest,
) -> VariantExecutionResult:
    """Keep the recorded episodes for one set of tasks, in committed order.

    Each episode is one task's independent measurement, so selecting a subset
    of them selects measurements rather than altering any. The manifest digest
    is restated because the comparison's manifests are re-issued over the two
    shared tasks and a receipt is required to name the manifest it was built
    against.
    """
    by_task = {episode.task_hash: episode for episode in result.episodes}
    return result.model_copy(
        update={
            "episodes": [by_task[task_hash] for task_hash in task_hashes],
            "experiment_manifest_digest": experiment_manifest_digest,
        }
    )


# ---------------------------------------------------------------------------
# The declared half
# ---------------------------------------------------------------------------


def _manifest(
    campaign: CampaignSpec,
    campaign_digest: Digest,
    variant: ExperimentVariant,
    *,
    skill: ArtifactRef | None,
) -> ExperimentManifest:
    """Build one variant through the same finalizer the run service uses."""
    configuration = build_experiment_configuration(campaign)
    if skill is not None:
        configuration = _with_skill(configuration, skill)
    return finalize_manifest(
        campaign=campaign,
        campaign_digest=campaign_digest,
        public_context=None,
        variant=variant,
        configuration=configuration,
        created_at=_FIXTURE_INSTANT,
        manifest_id=None,
    )


def _with_skill(
    configuration: ExperimentConfiguration, skill: ArtifactRef
) -> ExperimentConfiguration:
    """Return the configuration with the subject's Skill list replaced."""
    subject = configuration.agents[SUBJECT_AGENT]
    return ExperimentConfiguration(
        **{
            **dict(configuration),
            "agents": {
                SUBJECT_AGENT: AgentSpec(
                    **{
                        **dict(subject),
                        "harness": HarnessSpec(
                            **{**dict(subject.harness), "skills": [skill]}
                        ),
                    }
                )
            },
        }
    )


def _recorded_skill_reference(candidate: RecordedVariant) -> ArtifactRef:
    """Return the Skill reference the recorded candidate manifest declares."""
    subject = candidate.experiment.configuration.agents[SUBJECT_AGENT]
    return subject.harness.skills[0]


def _request(
    *,
    campaign: CampaignSpec,
    campaign_digest: Digest,
    baseline: ExperimentManifest,
    candidate: ExperimentManifest,
) -> RunRequest:
    """Build the request one run of this pair would have been created from.

    Derived, not recorded: the probes were two runs and this comparison is one.
    Every digest in it is a digest of an object above.
    """
    return RunRequest(
        run_id="run_recordedpair00000000000000000",
        draft_id="draft_recordedpair0000000000000000",
        draft_digest=digest_object({"fixture": "recorded-pair-draft"}),
        campaign_spec_digest=campaign_digest,
        program_ref=None,
        public_context=None,
        data_policy_digest=campaign.data_policy_digest,
        outcome_contract_digest=None,
        evaluation_backend=campaign.evaluation_backend,
        taskset_lock_digest=None,
        baseline_manifest_digest=digest_object(baseline),
        candidate_manifest_digest=digest_object(candidate),
        policy_acknowledgement=PolicyAcknowledgement(
            data_policy_digest=campaign.data_policy_digest,
            method="explicit_cli_review",
            acknowledged_at=_FIXTURE_INSTANT,
        ),
        executor_kind=executor_kind_for(campaign),
        created_at=_FIXTURE_INSTANT,
    )


def _taskset_lock(campaign: CampaignSpec) -> TasksetLock:
    """Return the lock this comparison's episodes were joined on.

    The engine is the pinned bundle this build resolves, which is the engine
    that inspected the taskset the probes were scored on.
    """
    committed = list(campaign.taskset.membership.ordered_task_hashes)
    return TasksetLock(
        schema_version=TASKSET_LOCK_SCHEMA_VERSION,
        taskset_ref=campaign.taskset.ref,
        engine_digest=default_engine_digest(),
        resolved_package_digest=campaign.taskset.ref.package.digest,
        ordered_task_hashes=committed,
        membership_digest=membership_digest(committed),
        task_count=len(committed),
    )


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


def _shared_task_hashes() -> list[Digest]:
    """Return the tasks both probes scored, in the baseline's committed order."""
    baseline = recorded_variant(VariantName.BASELINE)
    candidate = recorded_variant(VariantName.CANDIDATE)
    scored = set(candidate.ordered_task_hashes)
    shared = [value for value in baseline.ordered_task_hashes if value in scored]
    if shared != candidate.ordered_task_hashes:
        raise AssertionError(
            "the recorded candidate scored tasks the recorded baseline did not, "
            "so the two probes cannot be paired"
        )
    return shared


def _require_recorded_campaign(probe: RecordedVariant) -> None:
    """Prove both variants of the recorded evidence name one Campaign.

    What has to hold is that the two sides are two variants of ONE experiment.
    That used to be checked against the source tree, which coupled the fixture
    to whatever the current release coordinates happened to be; it is checked
    between the two recorded variants instead, which is where the claim
    actually lives. A pair whose sides ran under different Campaigns is not a
    comparison, and that is true whatever the tree says today.
    """
    other = recorded_variant(
        VariantName.BASELINE
        if probe.variant is VariantName.CANDIDATE
        else VariantName.CANDIDATE
    )
    if digest_object(probe.campaign) != digest_object(other.campaign):
        raise AssertionError(
            "the two recorded variants name different Campaigns, so they are "
            "not two sides of one comparison"
        )
