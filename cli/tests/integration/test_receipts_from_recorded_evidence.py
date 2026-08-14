"""Receipts built from a real evaluation, end to end. Spec sections 7.6-7.8.

The expensive half of a Climb is the evaluation. The half this exercises is
everything that happens after it, and the point of the test is that the second
half needs none of the first half's apparatus: no Docker, no provider, no
credential, no money, no engine subprocess. Recorded evidence is copied into a
run directory exactly where a finished evaluation would have left it, and the
whole receipt pipeline runs over it as it would over a live run — parse,
receipt, seal, commit, write, read back, verify, fingerprint.

Three claims are only checkable at this level and are checked here.

*The pipeline reads a run directory, not a fixture object.* Every input is
loaded from a file in the run tree, which is what the real caller will do.

*What it writes stays private and stays checkable.* The receipt-set manifest
lands under the run's own ``receipts/`` tree with owner-only permissions, and
re-reading the bytes from disk reproduces the commitment that was written.

*It leaves the run's existing artifacts alone.* A run's per-episode receipts
are loaded by listing a directory and parsing everything in it, so the new
manifest has to land somewhere that does not break that, and the check is to
write both and read the receipts back through the run's own artifact store.
"""

from __future__ import annotations

import shutil
import stat
from pathlib import Path

import pytest

from fixtures.receipts.support import (
    NORMALIZED_EPISODES_FILE,
    RESOLVED_CONFIG_FILE,
    RecordedVariant,
    recorded_variant,
)
from techtree.canonical import sha256_digest_bytes
from techtree.models.base import ObjectEnvelope
from techtree.models.campaign import SUBJECT_AGENT
from techtree.models.episode_receipt import (
    EpisodeReceipt,
    EvidenceStatus,
    ScoreStatus,
)
from techtree.paths import paths_from_root
from techtree.receipts.episode import (
    build_variant_receipts,
    experiment_variant_of,
    read_variant_episodes,
)
from techtree.receipts.observed import observed_from_episodes, read_resolved_config
from techtree.receipts.set import (
    ReceiptSetManifest,
    build_receipt_set,
    receipt_set_path,
    seal_receipt,
    verify_receipt_set,
    write_receipt_set,
)
from techtree.runs.artifacts import RunArtifactStore
from techtree.verifiers.models import VERIFIERS_DIRECTORY, VariantName

pytestmark = pytest.mark.integration


def stage_recorded_run(home: Path, recorded: RecordedVariant) -> Path:
    """Lay one recorded variant out where a finished evaluation would have."""
    run_root = home / "runs" / recorded.request.run_id
    output = run_root / VERIFIERS_DIRECTORY / recorded.variant.value / "run"
    output.mkdir(parents=True)
    for name in (NORMALIZED_EPISODES_FILE, RESOLVED_CONFIG_FILE):
        shutil.copyfile(recorded.directory / name, output / name)
    return run_root


def test_receipts_are_built_from_a_run_directory_without_executing_anything(
    tmp_path: Path,
) -> None:
    """The whole post-evaluation pipeline, over evidence a paid run produced."""
    recorded = recorded_variant(VariantName.CANDIDATE)
    run_root = stage_recorded_run(tmp_path, recorded)
    output = run_root / VERIFIERS_DIRECTORY / recorded.variant.value / "run"

    # 1. The engine's projection is the only door the evidence comes through.
    episodes = read_variant_episodes(output / NORMALIZED_EPISODES_FILE)
    assert [episode.task_hash for episode in episodes] == recorded.ordered_task_hashes

    # 2. One receipt per committed task, with the rewards that were recorded.
    receipts = build_variant_receipts(
        run_request=recorded.request,
        variant=recorded.variant,
        experiment=recorded.experiment,
        result=recorded.result.model_copy(update={"episodes": episodes}),
        evaluation_backend=recorded.campaign.evaluation_backend,
        ordered_task_hashes=recorded.ordered_task_hashes,
        primary_reward=recorded.primary_reward,
        evidence=recorded.campaign.evidence,
    )
    assert [receipt.task_hash for receipt in receipts] == recorded.ordered_task_hashes
    assert all(receipt.score_status is ScoreStatus.VALID for receipt in receipts)
    assert all(
        receipt.evidence_status is EvidenceStatus.COMPLETE for receipt in receipts
    )
    assert all(receipt.execution_backend == "verifiers" for receipt in receipts)
    rewards = [
        receipt.named_traces["subject"][0].rewards[recorded.primary_reward]
        for receipt in receipts
    ]
    assert len(rewards) == 36
    assert set(rewards) <= {0.0, 1.0}
    # The candidate mounted the starter Skill and the baseline mounted nothing,
    # so one side scores the calibrated twenty-four and the other scores none.
    assert sum(rewards) == (24.0 if recorded.variant is VariantName.CANDIDATE else 0.0)

    # 3. The ordered commitment, written into the run's own tree.
    envelopes: list[ObjectEnvelope[EpisodeReceipt]] = [
        seal_receipt(receipt) for receipt in receipts
    ]
    variant = experiment_variant_of(recorded.variant)
    manifest = build_receipt_set(
        run_id=recorded.request.run_id,
        variant=variant,
        experiment_manifest_digest=recorded.result.experiment_manifest_digest,
        signed_receipts=envelopes,
        ordered_task_hashes=recorded.ordered_task_hashes,
    )
    path = receipt_set_path(run_root, variant)
    reference = write_receipt_set(manifest, path)

    assert path.is_relative_to(run_root)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert sha256_digest_bytes(path.read_bytes()) == reference.digest

    # 4. Read back from disk, the commitment still holds over the receipts.
    from_disk = ReceiptSetManifest.model_validate_json(path.read_bytes())
    assert from_disk == manifest
    verify_receipt_set(
        manifest=from_disk,
        signed_receipts=envelopes,
        ordered_task_hashes=recorded.ordered_task_hashes,
    )

    # 5. And what the engine actually resolved is recoverable beside it.
    observed = observed_from_episodes(
        episodes,
        resolved_config=read_resolved_config(output / RESOLVED_CONFIG_FILE),
        image_resolution=recorded.image_resolution,
        runtime=recorded.campaign.agents[SUBJECT_AGENT].runtime,
    )
    assert observed.model_id == "qwen/qwen3.7-flash"
    assert observed.runtime_kind == "docker"
    assert len(observed.skill_root_digests) == 1


def test_the_manifest_does_not_disturb_the_runs_own_receipt_directory(
    temp_techtree_home: Path,
) -> None:
    """The run's receipts still read back after a set has been written.

    A run's receipt directory is loaded by listing it and parsing every file in
    it, so where the set manifest lands is a correctness question and not a
    matter of taste. This writes both the way a run does and reads the receipts
    back through the run's own artifact store.
    """
    recorded = recorded_variant(VariantName.CANDIDATE)
    paths = paths_from_root(temp_techtree_home)
    store = RunArtifactStore(paths)
    run_id = recorded.request.run_id
    variant = experiment_variant_of(recorded.variant)

    receipts = build_variant_receipts(
        run_request=recorded.request,
        variant=recorded.variant,
        experiment=recorded.experiment,
        result=recorded.result,
        evaluation_backend=recorded.campaign.evaluation_backend,
        ordered_task_hashes=recorded.ordered_task_hashes,
        primary_reward=recorded.primary_reward,
        evidence=recorded.campaign.evidence,
    )
    for position, receipt in enumerate(receipts):
        store.write_episode_receipt(run_id, position=position, receipt=receipt)

    manifest = build_receipt_set(
        run_id=run_id,
        variant=variant,
        experiment_manifest_digest=recorded.result.experiment_manifest_digest,
        signed_receipts=[seal_receipt(receipt) for receipt in receipts],
        ordered_task_hashes=recorded.ordered_task_hashes,
    )
    write_receipt_set(manifest, receipt_set_path(paths.run_dir(run_id), variant))

    assert store.episode_receipts(run_id, variant) == receipts


def test_both_recorded_variants_produce_independent_receipt_sets(
    tmp_path: Path,
) -> None:
    """Each side of a comparison commits to its own receipts and only its own."""
    manifests: dict[str, ReceiptSetManifest] = {}
    for variant in (VariantName.BASELINE, VariantName.CANDIDATE):
        recorded = recorded_variant(variant)
        run_root = stage_recorded_run(tmp_path / variant.value, recorded)
        output = run_root / VERIFIERS_DIRECTORY / variant.value / "run"
        episodes = read_variant_episodes(output / NORMALIZED_EPISODES_FILE)
        receipts = build_variant_receipts(
            run_request=recorded.request,
            variant=variant,
            experiment=recorded.experiment,
            result=recorded.result.model_copy(update={"episodes": episodes}),
            evaluation_backend=recorded.campaign.evaluation_backend,
            ordered_task_hashes=recorded.ordered_task_hashes,
            primary_reward=recorded.primary_reward,
            evidence=recorded.campaign.evidence,
        )
        manifests[variant.value] = build_receipt_set(
            run_id=recorded.request.run_id,
            variant=experiment_variant_of(variant),
            experiment_manifest_digest=recorded.result.experiment_manifest_digest,
            signed_receipts=[seal_receipt(receipt) for receipt in receipts],
            ordered_task_hashes=recorded.ordered_task_hashes,
        )

    baseline, candidate = manifests["baseline"], manifests["candidate"]
    assert baseline.receipt_count == 36
    assert candidate.receipt_count == 36
    # Both variants are two sides of one comparison over one committed
    # membership, which makes the disjointness below the whole of the claim:
    # same tasks, same Campaign, and still not one receipt in common, because a
    # receipt belongs to one side of one comparison and to nothing else.
    assert baseline.task_membership_digest == candidate.task_membership_digest
    assert set(baseline.ordered_receipt_digests).isdisjoint(
        candidate.ordered_receipt_digests
    )
