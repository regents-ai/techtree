"""Run-owned inputs and outputs. Spec PR8 §8.3, §8.17, §10.4.

The property this file exists to establish is independence: once a run has
staged its inputs, deleting the draft, the source skill, and the catalog
changes nothing about what the run executes. Everything else here is what
makes that safe — copies rather than links, digests recomputed from the bytes
that landed, and a refusal when any of them disagrees with the run's request.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fixtures.runs.support import RunHarness, run_harness
from techtree.canonical import canonical_json_bytes, digest_object
from techtree.errors import ConflictError, NotFoundError, VerificationError
from techtree.fs import remove_tree
from techtree.models.experiment import ExperimentVariant
from techtree.runs.artifacts import RunArtifactStore, RunInputBundle
from techtree.runs.fake import (
    FAKE_TRACE_SCHEMA_VERSION,
    FakeTracePayload,
    build_fake_episode_receipt,
)
from techtree.runs.validation import PublisherFixtureValidationProvider


@pytest.fixture
def started(temp_techtree_home: Path) -> tuple[RunHarness, str]:
    """Return a harness whose draft has been started, with inputs staged."""
    harness = run_harness(temp_techtree_home)
    status = harness.start()
    return harness, status.state.run_id


# ---------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------


def test_staging_writes_the_whole_input_graph(started: tuple[RunHarness, str]) -> None:
    harness, run_id = started
    inputs = harness.artifacts.inputs_dir(run_id)

    present = {path.relative_to(inputs).as_posix() for path in inputs.rglob("*")}

    assert {
        "draft.json",
        "comparison.json",
        "public/climb.json",
        "public/campaign.json",
        "public/data-policy.json",
        "public/publisher-validation.json",
        "public/publisher-validation-evidence.json",
        "manifests/baseline.json",
        "manifests/candidate.json",
        "skill/artifact.json",
        "skill/bundle.tar",
        "skill/files/SKILL.md",
    } <= present


def test_the_staged_graph_is_the_one_the_request_names(
    started: tuple[RunHarness, str],
) -> None:
    harness, run_id = started
    request = harness.request(run_id)
    bundle = harness.inputs(run_id)

    assert digest_object(bundle.draft) == request.draft_digest
    assert bundle.resolved_climb.campaign_digest == request.campaign_spec_digest
    assert bundle.resolved_climb.data_policy_digest == request.data_policy_digest
    assert digest_object(bundle.baseline) == request.baseline_manifest_digest
    assert digest_object(bundle.candidate) == request.candidate_manifest_digest
    assert bundle.campaign.evaluation_backend == request.evaluation_backend


def test_the_run_needs_neither_the_draft_nor_the_source_skill(
    temp_techtree_home: Path, tmp_path: Path
) -> None:
    """Spec §10.4: after staging, the run owns everything it reads."""
    source = tmp_path / "candidate"
    source.mkdir()
    for item in sorted((Path("tests/fixtures/skills/valid-procedure")).rglob("*")):
        target = source / item.relative_to("tests/fixtures/skills/valid-procedure")
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(item.read_bytes())

    harness = run_harness(temp_techtree_home, skill_path=source)
    run_id = harness.start().state.run_id

    remove_tree(source)
    remove_tree(harness.paths.drafts_dir)

    bundle = harness.inputs(run_id)
    assert bundle.skill.files
    assert (bundle.skill_files / "SKILL.md").exists()


def test_staged_files_are_copies_and_not_links(
    started: tuple[RunHarness, str],
) -> None:
    harness, run_id = started
    entry = harness.inputs(run_id).skill.files[0]
    staged = harness.artifacts.skill_files_dir(run_id) / entry.path
    original = harness.drafts.skill_files_dir(harness.draft_id) / entry.path

    assert staged.read_bytes() == original.read_bytes()
    assert staged.stat().st_ino != original.stat().st_ino
    assert staged.stat().st_nlink == 1


def test_staging_twice_repairs_rather_than_duplicates(
    started: tuple[RunHarness, str],
) -> None:
    """Spec §9.4: a retried start finds inputs already staged."""
    harness, run_id = started
    snapshot = harness.drafts.load_snapshot(harness.draft_id)

    again = harness.artifacts.stage_inputs(
        run_id=run_id, request=harness.request(run_id), snapshot=snapshot
    )

    assert isinstance(again, RunInputBundle)
    staging = [
        path
        for path in harness.paths.run_dir(run_id).iterdir()
        if path.name.startswith(".staging-inputs-")
    ]
    assert staging == []


def test_a_tampered_input_is_refused(started: tuple[RunHarness, str]) -> None:
    harness, run_id = started
    skill_file = harness.artifacts.skill_files_dir(run_id) / "SKILL.md"
    skill_file.write_text("not what the artifact says", encoding="utf-8")

    with pytest.raises(VerificationError) as raised:
        harness.inputs(run_id)

    assert raised.value.code == "run_input_staging_failed"


def test_a_missing_input_is_refused(started: tuple[RunHarness, str]) -> None:
    harness, run_id = started
    (harness.artifacts.inputs_dir(run_id) / "comparison.json").unlink()

    with pytest.raises(NotFoundError) as raised:
        harness.inputs(run_id)

    assert raised.value.code == "run_input_staging_failed"


def test_loading_inputs_that_were_never_staged_is_refused(
    temp_techtree_home: Path,
) -> None:
    harness = run_harness(temp_techtree_home)
    run_id = harness.start().state.run_id
    remove_tree(harness.artifacts.inputs_dir(run_id))

    with pytest.raises(NotFoundError):
        harness.inputs(run_id)


# ---------------------------------------------------------------------------
# Execution outputs
# ---------------------------------------------------------------------------


def test_a_validation_marker_records_its_source(
    started: tuple[RunHarness, str],
) -> None:
    harness, run_id = started
    outcome = PublisherFixtureValidationProvider().validate(
        run_id=run_id, inputs=harness.inputs(run_id)
    )

    reference = harness.artifacts.write_validation_marker(
        run_id, outcome.marker_document()
    )
    written = json.loads(
        (harness.paths.run_dir(run_id) / "validation" / "development.json").read_bytes()
    )

    assert reference.relative_path == "validation/development.json"
    assert reference.size > 0
    assert written["source"] == "publisher_fixture"
    assert written["execution_record"] is None


def test_receipts_are_read_back_in_campaign_order(
    started: tuple[RunHarness, str],
) -> None:
    """Written last first, and still read back in the order that matters."""
    harness, run_id = started
    inputs = harness.inputs(run_id)
    hashes = inputs.ordered_task_hashes

    for position, task_hash in reversed(list(enumerate(hashes))):
        trace = harness.artifacts.write_fake_trace(
            run_id,
            variant=ExperimentVariant.BASELINE,
            position=position,
            payload=_trace(run_id, position, task_hash),
        )
        harness.artifacts.write_episode_receipt(
            run_id,
            position=position,
            receipt=build_fake_episode_receipt(
                request=harness.request(run_id),
                inputs=inputs,
                variant=ExperimentVariant.BASELINE,
                position=position,
                task_hash=task_hash,
                reward=1.0,
                trace_artifact=trace,
            ),
        )

    loaded = harness.artifacts.episode_receipts(run_id, ExperimentVariant.BASELINE)

    assert [receipt.task_hash for receipt in loaded] == hashes


def test_an_output_is_written_exactly_once(started: tuple[RunHarness, str]) -> None:
    harness, run_id = started
    inputs = harness.inputs(run_id)
    payload = _trace(run_id, 0, inputs.ordered_task_hashes[0])

    harness.artifacts.write_fake_trace(
        run_id, variant=ExperimentVariant.BASELINE, position=0, payload=payload
    )

    with pytest.raises(ConflictError):
        harness.artifacts.write_fake_trace(
            run_id, variant=ExperimentVariant.BASELINE, position=0, payload=payload
        )


def test_a_trace_reference_addresses_its_own_bytes(
    started: tuple[RunHarness, str],
) -> None:
    harness, run_id = started
    inputs = harness.inputs(run_id)
    payload = _trace(run_id, 0, inputs.ordered_task_hashes[0])

    reference = harness.artifacts.write_fake_trace(
        run_id, variant=ExperimentVariant.CANDIDATE, position=0, payload=payload
    )
    written = (
        harness.paths.run_dir(run_id) / "fake" / "candidate" / "0000.json"
    ).read_bytes()

    assert written == canonical_json_bytes(payload)
    assert reference.digest == digest_object(payload)
    assert reference.size == len(written)


def test_no_receipts_yet_is_an_empty_list(started: tuple[RunHarness, str]) -> None:
    harness, run_id = started

    assert harness.artifacts.episode_receipts(run_id, ExperimentVariant.BASELINE) == []


def test_the_store_needs_only_paths(temp_techtree_home: Path) -> None:
    """The worker constructs this from a home directory and nothing else."""
    harness = run_harness(temp_techtree_home)
    run_id = harness.start().state.run_id

    independent = RunArtifactStore(harness.paths)

    assert independent.load_inputs(run_id, harness.request(run_id)).draft.id == (
        harness.draft_id
    )


def _trace(run_id: str, position: int, task_hash: str) -> FakeTracePayload:
    return FakeTracePayload(
        schema_version=FAKE_TRACE_SCHEMA_VERSION,
        run_id=run_id,
        variant=ExperimentVariant.BASELINE,
        position=position,
        task_hash=task_hash,
        reward_name="synthetic_reward",
        reward=1.0,
    )
