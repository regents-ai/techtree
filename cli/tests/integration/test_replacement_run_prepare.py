"""The improvement loop closes. Spec sections 7.18-7.20, section 16 rows 12-13.

One test drives the whole of it and the others take it apart:

```text
a real insertion run completes and signs itself
        ↓  techtree uplift context
sanitized improvement context, no hidden material, deterministic
        ↓  a revised Skill a person wrote
        ↓  techtree uplift prepare
a Skill-replacement Campaign, derived from the first run's own Campaign
a controlled pair: Skill v1 as evaluated, against Skill v2 as scanned
        ↓  techtree uplift start
a second run, through the same kernel, reaching completed
        ↓
a second signed UpliftReport whose proof verifies offline
```

Nothing here calls a model, starts a container, or spends anything. The first
run replays the paid probes of 2026-08-13; the second lays out the stub
described in ``fixtures.receipts.replacement``, which is honest about being
one.

The claim the loop makes is not that Skill v2 is better. It is that a
participant who has one run can get a second controlled comparison out of the
same kernel, with the baseline pinned to the Skill the first run actually
measured rather than to whatever is in a directory now.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from fixtures.drafts.support import preparation_service
from fixtures.receipts.replacement import (
    REVISED_SKILL_REFERENCE_PATH,
    REVISED_SKILL_REFERENCE_TEXT,
    ReplacementEvidenceExecutor,
    write_revised_skill,
)
from fixtures.receipts.staged import (
    RecordedEvidenceExecutor,
    StagedRecordedRun,
    staged_recorded_run,
)
from fixtures.runs.support import (
    RecordingLauncher,
    execute_in_process,
    run_cli,
    run_harness,
    utc_now,
)
from techtree.canonical import digest_object, sha256_digest_bytes
from techtree.cli.commands.uplift import _prepare_payload
from techtree.drafts.store import DraftStore
from techtree.errors import PolicyError, VerificationError
from techtree.models.campaign import MutationKind
from techtree.models.experiment import ExperimentVariant
from techtree.models.run import PolicyAcknowledgement, RunPhase
from techtree.models.skill import SubmissionDraft
from techtree.models.uplift_report import UpliftDecision, UpliftReport
from techtree.presentation.build import (
    BASELINE_SKILL_LABEL,
    SECOND_CHANGE_LABEL,
    SECOND_RESULT_LABEL,
    build_uplift_presentation,
)
from techtree.receipts.bundle import proof_bundle_dir
from techtree.receipts.verify import verify_local_bundle
from techtree.runs.artifacts import RUN_INPUT_STAGING_FAILED, RunArtifactStore
from techtree.runs.service import RunService
from techtree.runs.store import RunStore
from techtree.runs.validation import PublisherFixtureValidationProvider
from techtree.skills.service import PreparedDraft
from techtree.uplift.service import SOURCE_RUN_NOT_USABLE, UpliftService
from techtree.worker.execute import execute_run

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Driving the loop
# ---------------------------------------------------------------------------


def _uplift_service(run: StagedRecordedRun) -> UpliftService:
    """Build the service the improvement commands act through, on this home."""
    catalog = run.paths.root / "recorded-catalog"
    preparation, _ = preparation_service(run.paths, catalog_root=catalog)
    return UpliftService(
        paths=run.paths,
        run_service=RunService(
            paths=run.paths,
            draft_store=DraftStore(run.paths),
            run_store=run.run_store,
            artifact_store=run.artifacts,
            launcher=RecordingLauncher(run.run_store),
            clock=utc_now,
        ),
        artifact_store=run.artifacts,
        skill_service=preparation,
    )


def _first_run(home: Path) -> StagedRecordedRun:
    """Complete one real insertion run from the recorded probe evidence."""
    run = staged_recorded_run(home)
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
    assert run.run_store.state(run.run_id).phase is RunPhase.COMPLETED
    return run


def _start(run: StagedRecordedRun, prepared: PreparedDraft) -> str:
    """Approve the second run and start the prepared replacement."""
    draft: SubmissionDraft = prepared.draft
    status = RunService(
        paths=run.paths,
        draft_store=DraftStore(run.paths),
        run_store=run.run_store,
        artifact_store=run.artifacts,
        launcher=RecordingLauncher(run.run_store),
        clock=utc_now,
    ).start(
        draft_id=draft.id,
        policy_acknowledgement=PolicyAcknowledgement(
            data_policy_digest=draft.data_policy_digest,
            method="explicit_cli_review",
            acknowledged_at=utc_now(),
        ),
        approved_by="human_via_cli",
    )
    return status.state.run_id


# ---------------------------------------------------------------------------
# The whole loop
# ---------------------------------------------------------------------------


def test_a_finished_run_becomes_a_second_controlled_comparison(
    tmp_path: Path,
) -> None:
    """Insertion run, context, revision, replacement run, second signed report."""
    first = _first_run(tmp_path / "home")
    service = _uplift_service(first)

    # 1. The context is exportable, and it names the Skill that was measured.
    context = service.improvement_context(first.run_id)
    first_inputs = first.artifacts.load_inputs(
        first.run_id, first.run_store.get_request(first.run_id)
    )
    skill_v1 = first_inputs.candidate_skill.artifact
    assert context.source_run_id == first.run_id
    assert context.parent_skill_digest == skill_v1.root_digest
    assert all(example.subject_reply is None for example in context.examples)

    # 2. A revision a person wrote goes through the ordinary scanner path.
    prepared = service.prepare_replacement(
        source_run_id=first.run_id,
        candidate_skill_path=write_revised_skill(tmp_path / "skill-v2"),
        candidate_label="branch-code-v2",
    )
    draft = prepared.draft
    campaign = prepared.source.campaign

    # 3. The derived Campaign is a replacement, and no Climb wraps it.
    assert campaign.mutation_contract.kind is MutationKind.SKILL_REPLACEMENT
    assert prepared.source.climb is None
    assert draft.public_context is None
    assert campaign.subject.harness.skills[0].digest == skill_v1.root_digest
    assert draft.skill_artifact.parent_skill_digest == skill_v1.root_digest
    assert prepared.manifest_comparison.controlled

    # 4. The second run goes through the same kernel and completes.
    second_run_id = _start(first, prepared)
    exit_code = execute_run(
        second_run_id,
        paths=first.paths,
        executor_factory=lambda request: ReplacementEvidenceExecutor(paths=first.paths),
        validation_provider_factory=lambda request: (
            PublisherFixtureValidationProvider()
        ),
    )
    assert exit_code == 0, first.run_store.state(second_run_id).error
    assert first.run_store.state(second_run_id).phase is RunPhase.COMPLETED

    # 5. A second signed report, whose proof verifies from its own bytes.
    second: UpliftReport = first.run_store.get_result(second_run_id)
    assert second.run_id == second_run_id
    assert second.campaign_spec_digest == digest_object(campaign)
    assert second.public_context is None
    assert second.proof_grade == "P1"
    assert verify_local_bundle(
        proof_bundle_dir(first.paths.run_dir(second_run_id))
    ).verified

    # 6. And the two reports are about two different experiments.
    assert second.campaign_spec_digest != first_inputs.source.campaign_digest
    assert second.id != first.run_store.get_result(first.run_id).id


def test_the_second_report_is_presented_as_a_replacement(tmp_path: Path) -> None:
    """A v1-against-v2 result must not be labelled as a v1-against-nothing one."""
    first = _first_run(tmp_path / "home")
    service = _uplift_service(first)
    prepared = service.prepare_replacement(
        source_run_id=first.run_id,
        candidate_skill_path=write_revised_skill(tmp_path / "skill-v2"),
        candidate_label="branch-code-v2",
    )
    second_run_id = _start(first, prepared)
    execute_run(
        second_run_id,
        paths=first.paths,
        executor_factory=lambda request: ReplacementEvidenceExecutor(paths=first.paths),
        validation_provider_factory=lambda request: (
            PublisherFixtureValidationProvider()
        ),
    )

    artifacts = RunArtifactStore(first.paths)
    inputs = artifacts.load_inputs(
        second_run_id, RunStore(first.paths).get_request(second_run_id)
    )
    assert inputs.baseline_skill is not None

    payload = build_uplift_presentation(
        report=first.run_store.get_result(second_run_id),
        campaign=inputs.campaign,
        baseline_receipts=artifacts.episode_receipts(
            second_run_id, ExperimentVariant.BASELINE
        ),
        candidate_receipts=artifacts.episode_receipts(
            second_run_id, ExperimentVariant.CANDIDATE
        ),
        campaign_title=inputs.source.title,
        baseline_skill=inputs.baseline_skill.artifact,
        candidate_skill=inputs.candidate_skill.artifact,
        verification=verify_local_bundle(
            proof_bundle_dir(first.paths.run_dir(second_run_id))
        ),
    )

    assert payload.comparison_label == SECOND_RESULT_LABEL
    assert payload.change_label == SECOND_CHANGE_LABEL
    # Decisions 0019 s1: this baseline carries a Skill, so it is named as the
    # Skill it carries and never as the absence of one.
    assert payload.baseline_skill.label == inputs.baseline_skill.artifact.name
    assert payload.baseline_skill.label != BASELINE_SKILL_LABEL
    assert payload.baseline_skill.root_digest == (
        inputs.baseline_skill.artifact.root_digest
    )
    assert payload.candidate_skill.root_digest != payload.baseline_skill.root_digest


def test_a_revision_may_be_a_tree_and_the_whole_tree_is_carried(
    tmp_path: Path,
) -> None:
    """Decisions 0019 s1: a Skill version is a tree on both sides of the arrow.

    The revision here carries a supporting file under ``references/``. It has
    to survive the scanner, the draft, and the second run's staged inputs, and
    the Skill being revised has to be staged beside it, because the subject is
    handed both trees rather than both digests.
    """
    first = _first_run(tmp_path / "home")
    service = _uplift_service(first)

    prepared = service.prepare_replacement(
        source_run_id=first.run_id,
        candidate_skill_path=write_revised_skill(
            tmp_path / "skill-v2", supporting=True
        ),
        candidate_label="branch-code-v2",
    )

    assert list(prepared.draft.included_files) == [
        "SKILL.md",
        REVISED_SKILL_REFERENCE_PATH,
    ]
    second_run_id = _start(first, prepared)
    staged = first.artifacts.skill_files_dir(second_run_id)
    assert (staged / REVISED_SKILL_REFERENCE_PATH).is_file()
    assert (staged / REVISED_SKILL_REFERENCE_PATH).read_text(encoding="utf-8") == (
        REVISED_SKILL_REFERENCE_TEXT
    )

    inputs = first.artifacts.load_inputs(
        second_run_id, RunStore(first.paths).get_request(second_run_id)
    )
    assert inputs.baseline_skill is not None
    assert (inputs.baseline_skill.files / "SKILL.md").is_file()
    assert [entry.path for entry in inputs.candidate_skill.artifact.files] == [
        "SKILL.md",
        REVISED_SKILL_REFERENCE_PATH,
    ]


def test_the_same_measurements_on_both_sides_are_reported_as_a_tie(
    tmp_path: Path,
) -> None:
    """The stub gives each side the same recorded episodes, and the report says so."""
    first = _first_run(tmp_path / "home")
    service = _uplift_service(first)
    prepared = service.prepare_replacement(
        source_run_id=first.run_id,
        candidate_skill_path=write_revised_skill(tmp_path / "skill-v2"),
    )
    second_run_id = _start(first, prepared)
    execute_run(
        second_run_id,
        paths=first.paths,
        executor_factory=lambda request: ReplacementEvidenceExecutor(paths=first.paths),
        validation_provider_factory=lambda request: (
            PublisherFixtureValidationProvider()
        ),
    )

    report = first.run_store.get_result(second_run_id)
    assert report.primary_result.absolute_delta == 0.0
    assert (report.primary_result.wins, report.primary_result.losses) == (0, 0)
    # A rejected candidate is a measurement. It is still a complete, signed,
    # verifiable report, which is what spec section 7.22 asks to be proved.
    assert report.decision is UpliftDecision.REJECTED
    assert report.statuses.comparison.value.startswith("controlled")


# ---------------------------------------------------------------------------
# The safety rules of spec section 7.20
# ---------------------------------------------------------------------------


def test_a_run_that_has_not_finished_cannot_be_improved_from(tmp_path: Path) -> None:
    """Nothing is derived from a run whose result does not exist yet."""
    run = staged_recorded_run(tmp_path / "home")
    service = _uplift_service(run)

    with pytest.raises(Exception) as raised:
        service.improvement_context(run.run_id)

    assert "run_result_not_ready" in str(raised.value) or "created" in str(raised.value)


def test_a_development_only_run_cannot_be_improved_from(tmp_path: Path) -> None:
    """Invented numbers are not evidence, so nothing may be built on them.

    A completed development run is the real article here, produced by the
    development executor rather than manufactured: it reaches ``completed``,
    it has a report, and every one of its numbers is a placeholder.
    """
    harness = run_harness(tmp_path / "home")
    run_id = harness.start().state.run_id
    report = execute_in_process(harness, run_id)
    assert report.proof_grade == "development_only"

    preparation, _ = preparation_service(harness.paths)
    service = UpliftService(
        paths=harness.paths,
        run_service=harness.service,
        artifact_store=harness.artifacts,
        skill_service=preparation,
    )

    with pytest.raises(PolicyError) as raised:
        service.improvement_context(run_id)

    assert raised.value.code == SOURCE_RUN_NOT_USABLE

    with pytest.raises(PolicyError):
        service.prepare_replacement(
            source_run_id=run_id,
            candidate_skill_path=write_revised_skill(tmp_path / "skill-v2"),
        )


def test_a_broken_proof_stops_a_replacement_being_prepared(tmp_path: Path) -> None:
    """Spec section 7.20: the source run must still verify locally."""
    first = _first_run(tmp_path / "home")
    service = _uplift_service(first)
    bundle = proof_bundle_dir(first.paths.run_dir(first.run_id))
    manifest = bundle / "bundle.json"
    manifest.write_bytes(manifest.read_bytes().replace(b"sha256:", b"sha256:0", 1))

    with pytest.raises(VerificationError):
        service.prepare_replacement(
            source_run_id=first.run_id,
            candidate_skill_path=write_revised_skill(tmp_path / "skill-v2"),
        )


def test_a_revision_identical_to_the_skill_it_replaces_is_refused(
    tmp_path: Path,
) -> None:
    """An identical tree on both sides would compare a Skill against itself."""
    first = _first_run(tmp_path / "home")
    service = _uplift_service(first)
    inputs = first.artifacts.load_inputs(
        first.run_id, first.run_store.get_request(first.run_id)
    )

    unchanged = tmp_path / "skill-v1-copy"
    unchanged.mkdir()
    for entry in inputs.candidate_skill.artifact.files:
        target = unchanged / entry.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((inputs.candidate_skill.files / entry.path).read_bytes())

    with pytest.raises(Exception) as raised:
        service.prepare_replacement(
            source_run_id=first.run_id, candidate_skill_path=unchanged
        )

    assert "replacement_derivation_failed" in str(raised.value.__dict__.get("code", ""))


# ---------------------------------------------------------------------------
# The CLI surface. Spec section 7.21.
# ---------------------------------------------------------------------------


def test_the_cli_exports_a_context_and_prepares_a_replacement(
    tmp_path: Path,
) -> None:
    """``uplift context`` and ``uplift prepare``, through the real program."""
    first = _first_run(tmp_path / "home")
    home = first.paths.root

    exported = run_cli(home, "uplift", "context", first.run_id)
    assert exported.exit_code == 0, exported.stderr
    context = exported.data()["context"]
    assert context["source_run_id"] == first.run_id
    assert all(example["subject_reply"] is None for example in context["examples"])
    assert "subject final replies" in context["prohibited_material"]
    # The same bytes are on disk beside the run, where a plugin can read them.
    written = first.paths.run_dir(first.run_id) / exported.data()["relative_path"]
    assert json.loads(written.read_text("utf-8")) == context

    prepared = run_cli(
        home,
        "uplift",
        "prepare",
        "--from-run",
        first.run_id,
        "--candidate-skill",
        str(write_revised_skill(tmp_path / "skill-v2")),
        "--label",
        "branch-code-v2",
    )
    assert prepared.exit_code == 0, prepared.stderr
    payload = prepared.data()
    assert payload["controlled"] is True
    assert payload["baseline_skill_digest"] != payload["candidate_skill_digest"]
    assert payload["source_run_id"] == first.run_id
    # Ticket jgf: the maximum the derived Campaign declares travels with the
    # replacement draft, so the surface a second run is approved from states
    # the same figure this terminal states.
    inputs = first.artifacts.load_inputs(
        first.run_id, first.run_store.get_request(first.run_id)
    )
    assert payload["campaign_maximum_usd"] == inputs.campaign.budgets.maximum_usd
    assert payload["campaign_maximum_usd"] is not None

    started = run_cli(home, "uplift", "start", payload["draft_id"], "--yes")
    assert started.exit_code == 0, started.stderr
    assert started.data()["draft_digest"] == payload["draft_digest"]
    assert started.data()["policy_acknowledgement_method"] == "explicit_cli_review"
    assert started.data()["approved_by"] == "operator_via_flag"


def test_the_declared_maximum_is_read_off_the_campaign_and_never_invented(
    tmp_path: Path,
) -> None:
    """Ticket jgf: the figure follows the Campaign, whatever the Campaign says.

    Decision 0019 section 2 puts the declared maximum in the review a second
    paid run is approved from, and a review that supplied a figure of its own
    would be right for this Campaign and wrong for the next one. So the payload
    is projected twice from the same prepared draft: once against the Campaign
    the run was derived from, and once against the same Campaign with its
    maximum removed. The answer tracks the Campaign both times, and the second
    one reports that there is no figure rather than reaching for the first.
    """
    first = _first_run(tmp_path / "home")
    prepared = _uplift_service(first).prepare_replacement(
        source_run_id=first.run_id,
        candidate_skill_path=write_revised_skill(tmp_path / "skill-v2"),
        candidate_label="branch-code-v2",
    )
    campaign = prepared.source.campaign
    declared = campaign.budgets.maximum_usd
    assert declared is not None

    assert _prepare_payload(first.run_id, prepared).campaign_maximum_usd == declared

    undeclared = dataclasses.replace(
        prepared,
        source=dataclasses.replace(
            prepared.source,
            campaign=campaign.model_copy(
                update={
                    "budgets": campaign.budgets.model_copy(update={"maximum_usd": None})
                }
            ),
        ),
    )

    assert _prepare_payload(first.run_id, undeclared).campaign_maximum_usd is None


def test_the_cli_hands_over_the_runs_own_verified_skill_text(
    tmp_path: Path,
) -> None:
    """Decisions 0007 R2: the text, verified, with the context's fingerprints.

    This is the seam that keeps verification inside Techtree. A consumer asks
    for the Skill by run, gets the text back with the digests it was checked
    against, and never composes a path into a run directory of its own.
    """
    first = _first_run(tmp_path / "home")
    home = first.paths.root

    read = run_cli(home, "uplift", "skill-source", first.run_id)
    assert read.exit_code == 0, read.stderr
    payload = read.data()

    inputs = first.artifacts.load_inputs(
        first.run_id, first.run_store.get_request(first.run_id)
    )
    skill = inputs.candidate_skill.artifact
    entry = next(file for file in skill.files if file.path == "SKILL.md")

    assert payload["source_run_id"] == first.run_id
    assert payload["skill_root_digest"] == skill.root_digest
    assert payload["entrypoint_path"] == "SKILL.md"
    assert payload["entrypoint_digest"] == entry.digest
    assert payload["file_count"] == len(skill.files)
    # The text really is the measured bytes, not a rendering of them.
    text: str = payload["entrypoint_text"]
    assert sha256_digest_bytes(text.encode("utf-8")) == entry.digest
    assert payload["entrypoint_size"] == len(text.encode("utf-8"))

    # And it lines up with what the context pins, which is what lets a caller
    # bind a proposal to one Skill and one result.
    context = run_cli(home, "uplift", "context", first.run_id).data()["context"]
    assert context["parent_skill_digest"] == payload["skill_root_digest"]
    assert context["parent_skill_entrypoint_digest"] == payload["entrypoint_digest"]
    assert context["source_run_id"] == payload["source_run_id"]
    assert context["source_report_digest"] == digest_object(
        first.run_store.get_result(first.run_id)
    )


def test_the_cli_refuses_to_hand_over_a_snapshot_that_was_edited(
    tmp_path: Path,
) -> None:
    """A run's copy that no longer hashes to what the run measured is refused.

    Nobody may be handed text described as the Skill a result came from unless
    it still is that Skill, so the check is made at the moment of the read
    rather than trusted from when the run staged its inputs.
    """
    first = _first_run(tmp_path / "home")
    home = first.paths.root
    assert run_cli(home, "uplift", "skill-source", first.run_id).exit_code == 0

    entrypoint = first.artifacts.skill_files_dir(first.run_id) / "SKILL.md"
    entrypoint.chmod(0o600)
    entrypoint.write_text(
        f"{entrypoint.read_text(encoding='utf-8')}\nand one more rule.\n",
        encoding="utf-8",
    )

    refused = run_cli(home, "uplift", "skill-source", first.run_id)

    assert refused.exit_code != 0
    assert refused.envelope()["error"]["code"] == RUN_INPUT_STAGING_FAILED


def test_a_development_only_run_hands_over_no_skill_text(tmp_path: Path) -> None:
    """Spec section 7.20 applies to the text as much as to the numbers."""
    harness = run_harness(tmp_path / "home")
    run_id = harness.start().state.run_id
    assert execute_in_process(harness, run_id).proof_grade == "development_only"

    preparation, _ = preparation_service(harness.paths)
    service = UpliftService(
        paths=harness.paths,
        run_service=harness.service,
        artifact_store=harness.artifacts,
        skill_service=preparation,
    )

    with pytest.raises(PolicyError) as raised:
        service.verified_source_skill(run_id)

    assert raised.value.code == SOURCE_RUN_NOT_USABLE


def test_the_cli_refuses_to_start_a_replacement_without_approval(
    tmp_path: Path,
) -> None:
    """Spec section 7.20: the second run is approved the same way the first was."""
    first = _first_run(tmp_path / "home")
    home = first.paths.root
    prepared = run_cli(
        home,
        "uplift",
        "prepare",
        "--from-run",
        first.run_id,
        "--candidate-skill",
        str(write_revised_skill(tmp_path / "skill-v2")),
    ).data()

    refused = run_cli(home, "uplift", "start", prepared["draft_id"])

    assert refused.exit_code != 0
    assert refused.envelope()["error"]["code"] == "policy_acceptance_required"
    assert "--yes" in refused.envelope()["error"]["message"]
