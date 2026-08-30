"""The ordered commitment over one variant's receipts. Spec section 7.7.

The receipts under test are built from the recorded evaluation, so the digests
being committed to are digests of real results. What is checked here is the
commitment itself: that it is ordered by the Campaign's membership rather than
by whatever order the receipts arrive in, that the same evidence always
produces the same manifest, and that changing anything at all — a reward inside
a receipt, an envelope's digest, the manifest's own order — is detected.

Tamper-evidence is only meaningful if it is demonstrated, so every one of those
edits is made and the resulting refusal is asserted.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import pytest

from fixtures.receipts.support import RecordedVariant, recorded_variant
from techtree.canonical import digest_object, sha256_digest_bytes
from techtree.errors import TechtreeError
from techtree.models.base import ObjectEnvelope
from techtree.models.episode_receipt import EpisodeReceipt
from techtree.models.experiment import ExperimentVariant
from techtree.receipts.episode import (
    EPISODE_COUNT_MISMATCH,
    TASK_MEMBERSHIP_MISMATCH,
    build_variant_receipts,
    experiment_variant_of,
)
from techtree.receipts.set import (
    RECEIPT_SET_INVALID,
    RECEIPT_SET_SCHEMA_VERSION,
    ReceiptSetManifest,
    build_receipt_set,
    receipt_set_path,
    seal_receipt,
    verify_receipt_set,
    write_receipt_set,
)
from techtree.tasksets.membership import membership_digest
from techtree.verifiers.models import VariantName

#: A reward neither recorded variant earned, so an edit to it is visible
#: on both sides of the comparison.
_FLATTERING_REWARD: Final = 0.5


@pytest.fixture(params=[VariantName.BASELINE, VariantName.CANDIDATE])
def recorded(request: pytest.FixtureRequest) -> RecordedVariant:
    """Return one recorded variant's evaluation."""
    variant: VariantName = request.param
    return recorded_variant(variant)


def receipts_of(recorded: RecordedVariant) -> list[EpisodeReceipt]:
    """Build one recorded variant's receipts."""
    return build_variant_receipts(
        run_request=recorded.request,
        variant=recorded.variant,
        experiment=recorded.experiment,
        result=recorded.result,
        evaluation_backend=recorded.campaign.evaluation_backend,
        ordered_task_hashes=recorded.ordered_task_hashes,
        primary_reward=recorded.primary_reward,
        evidence=recorded.campaign.evidence,
    )


def envelopes_of(
    recorded: RecordedVariant,
) -> list[ObjectEnvelope[EpisodeReceipt]]:
    """Seal one recorded variant's receipts."""
    return [seal_receipt(receipt) for receipt in receipts_of(recorded)]


def set_of(
    recorded: RecordedVariant,
    envelopes: list[ObjectEnvelope[EpisodeReceipt]] | None = None,
) -> ReceiptSetManifest:
    """Build the commitment over one recorded variant's receipts."""
    return build_receipt_set(
        run_id=recorded.request.run_id,
        variant=experiment_variant_of(recorded.variant),
        experiment_manifest_digest=recorded.result.experiment_manifest_digest,
        signed_receipts=envelopes_of(recorded) if envelopes is None else envelopes,
        ordered_task_hashes=recorded.ordered_task_hashes,
    )


# ---------------------------------------------------------------------------
# The commitment
# ---------------------------------------------------------------------------


def test_the_set_commits_to_every_receipt_in_membership_order(
    recorded: RecordedVariant,
) -> None:
    """The order is the Campaign's, and the count is the Campaign's."""
    envelopes = envelopes_of(recorded)
    manifest = set_of(recorded, envelopes)

    assert manifest.schema_version == RECEIPT_SET_SCHEMA_VERSION
    assert manifest.run_id == recorded.request.run_id
    assert manifest.variant is experiment_variant_of(recorded.variant)
    assert manifest.receipt_count == len(recorded.ordered_task_hashes)
    assert manifest.ordered_receipt_digests == [
        envelope.payload_digest for envelope in envelopes
    ]


def test_the_set_commits_to_the_membership_the_lock_commits_to(
    recorded: RecordedVariant,
) -> None:
    """The membership digest is the TasksetLock's own, not a second spelling."""
    manifest = set_of(recorded)

    assert manifest.task_membership_digest == membership_digest(
        recorded.ordered_task_hashes
    )


def test_arrival_order_does_not_change_the_commitment(
    recorded: RecordedVariant,
) -> None:
    """Two concurrent variants finish in their own order and must still agree."""
    ordered = envelopes_of(recorded)
    shuffled = list(reversed(ordered))

    assert digest_object(set_of(recorded, ordered)) == digest_object(
        set_of(recorded, shuffled)
    )


def test_the_commitment_is_stable_across_rebuilds(recorded: RecordedVariant) -> None:
    """Same evidence, same digest, every time."""
    assert digest_object(set_of(recorded)) == digest_object(set_of(recorded))


def test_two_variants_commit_to_different_sets() -> None:
    """The baseline and the candidate are different results, committed apart."""
    baseline = set_of(recorded_variant(VariantName.BASELINE))
    candidate = set_of(recorded_variant(VariantName.CANDIDATE))

    assert digest_object(baseline) != digest_object(candidate)
    assert set(baseline.ordered_receipt_digests).isdisjoint(
        candidate.ordered_receipt_digests
    )


# ---------------------------------------------------------------------------
# Verification and tamper-evidence
# ---------------------------------------------------------------------------


def test_an_untouched_set_verifies(recorded: RecordedVariant) -> None:
    """The receipts a manifest was built from verify against it."""
    envelopes = envelopes_of(recorded)

    verify_receipt_set(
        manifest=set_of(recorded, envelopes),
        signed_receipts=envelopes,
        ordered_task_hashes=recorded.ordered_task_hashes,
    )


def test_editing_one_receipts_reward_breaks_the_set(
    recorded: RecordedVariant,
) -> None:
    """The single edit the whole apparatus exists to catch."""
    envelopes = envelopes_of(recorded)
    manifest = set_of(recorded, envelopes)

    original = envelopes[0].payload
    trace = original.named_traces["subject"][0]
    improved = original.model_copy(
        update={
            "named_traces": {
                "subject": [
                    trace.model_copy(
                        update={"rewards": {"exact_match": _FLATTERING_REWARD}}
                    )
                ]
            }
        }
    )
    tampered = [
        envelopes[0].model_copy(update={"payload": improved}),
        *envelopes[1:],
    ]

    with pytest.raises(TechtreeError) as failure:
        verify_receipt_set(
            manifest=manifest,
            signed_receipts=tampered,
            ordered_task_hashes=recorded.ordered_task_hashes,
        )

    assert failure.value.code == RECEIPT_SET_INVALID


def test_resealing_an_edited_receipt_still_breaks_the_set(
    recorded: RecordedVariant,
) -> None:
    """Editing the receipt *and* its envelope changes what the manifest names."""
    envelopes = envelopes_of(recorded)
    manifest = set_of(recorded, envelopes)

    original = envelopes[0].payload
    trace = original.named_traces["subject"][0]
    improved = original.model_copy(
        update={
            "named_traces": {
                "subject": [
                    trace.model_copy(
                        update={"rewards": {"exact_match": _FLATTERING_REWARD}}
                    )
                ]
            }
        }
    )
    resealed = [seal_receipt(improved), *envelopes[1:]]

    with pytest.raises(TechtreeError) as failure:
        verify_receipt_set(
            manifest=manifest,
            signed_receipts=resealed,
            ordered_task_hashes=recorded.ordered_task_hashes,
        )

    assert failure.value.code == RECEIPT_SET_INVALID


def test_reordering_the_manifest_breaks_the_set() -> None:
    """A manifest whose order is not the membership order is not the manifest."""
    recorded = recorded_variant(VariantName.BASELINE)
    envelopes = envelopes_of(recorded)
    manifest = set_of(recorded, envelopes)
    reordered = manifest.model_copy(
        update={
            "ordered_receipt_digests": list(reversed(manifest.ordered_receipt_digests))
        }
    )

    with pytest.raises(TechtreeError) as failure:
        verify_receipt_set(
            manifest=reordered,
            signed_receipts=envelopes,
            ordered_task_hashes=recorded.ordered_task_hashes,
        )

    assert failure.value.code == RECEIPT_SET_INVALID


def test_a_receipt_from_another_run_cannot_join_the_set(
    recorded: RecordedVariant,
) -> None:
    """A receipt has to belong to the run and variant being committed to."""
    envelopes = envelopes_of(recorded)
    stranger = envelopes[0].payload.model_copy(update={"run_id": "run_" + "0" * 32})
    mixed = [seal_receipt(stranger), *envelopes[1:]]

    with pytest.raises(TechtreeError) as failure:
        set_of(recorded, mixed)

    assert failure.value.code == RECEIPT_SET_INVALID


def test_a_receipt_for_the_other_variant_cannot_join_the_set(
    recorded: RecordedVariant,
) -> None:
    """One set is one side of the comparison."""
    envelopes = envelopes_of(recorded)
    other = (
        ExperimentVariant.CANDIDATE
        if recorded.variant is VariantName.BASELINE
        else ExperimentVariant.BASELINE
    )
    crossed = envelopes[0].payload.model_copy(update={"variant": other})
    mixed = [seal_receipt(crossed), *envelopes[1:]]

    with pytest.raises(TechtreeError) as failure:
        set_of(recorded, mixed)

    assert failure.value.code == RECEIPT_SET_INVALID


def test_a_short_set_is_an_episode_count_mismatch(recorded: RecordedVariant) -> None:
    """Fewer receipts than committed tasks is not a smaller comparison."""
    envelopes = envelopes_of(recorded)[:-1]

    with pytest.raises(TechtreeError) as failure:
        set_of(recorded, envelopes)

    assert failure.value.code == EPISODE_COUNT_MISMATCH


def test_a_set_missing_a_committed_task_is_refused() -> None:
    """The count is right and one task is scored twice, which is worse."""
    recorded = recorded_variant(VariantName.BASELINE)
    envelopes = envelopes_of(recorded)
    doubled = [envelopes[0]] * len(envelopes)

    with pytest.raises(TechtreeError) as failure:
        set_of(recorded, doubled)

    assert failure.value.code == TASK_MEMBERSHIP_MISMATCH


# ---------------------------------------------------------------------------
# The manifest is internally consistent by construction
# ---------------------------------------------------------------------------


def test_a_manifest_cannot_miscount_itself(recorded: RecordedVariant) -> None:
    """The model refuses a count that disagrees with the list it counts."""
    document = set_of(recorded).model_dump(mode="json")
    document["receipt_count"] = 99

    with pytest.raises(ValueError, match="receipt_count"):
        ReceiptSetManifest.model_validate_json(json.dumps(document))


def test_a_manifest_cannot_name_one_receipt_twice(recorded: RecordedVariant) -> None:
    """A repeated digest would let one episode occupy two positions."""
    manifest = set_of(recorded)
    document = manifest.model_dump(mode="json")
    first = document["ordered_receipt_digests"][0]
    document["ordered_receipt_digests"] = [first] * manifest.receipt_count

    with pytest.raises(ValueError, match="each receipt once"):
        ReceiptSetManifest.model_validate_json(json.dumps(document))


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def test_the_written_set_hashes_to_the_reference_it_returns(
    recorded: RecordedVariant, tmp_path: Path
) -> None:
    """A reader can check the commitment by hashing what is on disk."""
    manifest = set_of(recorded)
    path = receipt_set_path(tmp_path, experiment_variant_of(recorded.variant))

    reference = write_receipt_set(manifest, path)

    written = path.read_bytes()
    assert sha256_digest_bytes(written) == reference.digest
    assert reference.digest == digest_object(manifest)
    assert reference.size == len(written)
    assert ReceiptSetManifest.model_validate_json(written) == manifest


def test_the_written_set_is_owner_readable_only(
    recorded: RecordedVariant, tmp_path: Path
) -> None:
    """A run's own evidence stays private. Spec section 6.19."""
    path = receipt_set_path(tmp_path, experiment_variant_of(recorded.variant))

    write_receipt_set(set_of(recorded), path)

    assert path.stat().st_mode & 0o777 == 0o600
