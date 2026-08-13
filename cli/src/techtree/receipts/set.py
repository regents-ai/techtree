"""The ordered commitment over one variant's receipts. Spec section 7.7.

An uplift report cannot carry dozens of receipt digests as a loose list and
still be checkable. What it can carry is one digest, of one manifest, that
commits to every receipt in the Campaign's own committed order together with
the membership that fixes that order. This module is that manifest.

Three properties are the whole point.

*Ordered by membership, never by arrival.* Two concurrent variants finish their
episodes in whatever order the provider and the containers produced, and a
commitment built in that order would differ between two correct runs of the
same experiment. Receipts are indexed by task hash and emitted in the order the
TasksetLock fixes, so two variants of one comparison commit to the same
positions.

*Tamper-evident in both directions.* Each receipt travels inside an
:class:`~techtree.models.base.ObjectEnvelope` carrying the digest of its own
canonical bytes, and the manifest commits to those digests. Editing a receipt
breaks its envelope; editing an envelope breaks the manifest; reordering the
manifest breaks the membership commitment. :func:`verify_receipt_set`
recomputes all three from the receipts themselves rather than trusting any
recorded value.

*Local, and honestly named.* The frozen v0.1 protocol has no receipt-set
object, so this is a versioned local manifest and says so in its schema
version. It is written into the run directory and referenced by digest; it is
not published and not part of the Campaign graph.

Signatures are deliberately not verified here. The envelope carries an optional
detached signature, and the key that would check it belongs to the local
executor identity (spec section 7.5), which is a later slice. This module
verifies structure, order and content; a caller that holds the identity adds
the signature check on top and nothing here has to change for it to.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Final, Literal, Self

from pydantic import Field, model_validator

from techtree.canonical import (
    canonical_json_bytes,
    digest_object,
    sha256_digest_bytes,
    validate_digest,
)
from techtree.errors import VerificationError
from techtree.fs import atomic_write_bytes, ensure_private_directory
from techtree.models.base import (
    ArtifactRef,
    Digest,
    JsonValue,
    NonEmptyString,
    ObjectEnvelope,
    ProtocolModel,
)
from techtree.models.episode_receipt import EpisodeReceipt
from techtree.models.experiment import ExperimentVariant
from techtree.receipts.episode import (
    EPISODE_COUNT_MISMATCH,
    TASK_MEMBERSHIP_MISMATCH,
)
from techtree.tasksets.membership import membership_digest

__all__ = [
    "RECEIPT_SET_INVALID",
    "RECEIPT_SET_MEDIA_TYPE",
    "RECEIPT_SET_SCHEMA_VERSION",
    "ReceiptSetManifest",
    "build_receipt_set",
    "receipt_set_path",
    "seal_receipt",
    "verify_receipt_set",
    "write_receipt_set",
]

#: A local bundle manifest, versioned as one. Spec section 7.7 permits exactly
#: this when the frozen protocol has no receipt-set object to extend.
RECEIPT_SET_SCHEMA_VERSION: Final = "techtree.receipt-set.v1alpha1"

#: Stable error code. Spec section 15.
RECEIPT_SET_INVALID: Final = "receipt_set_invalid"

RECEIPT_SET_MEDIA_TYPE: Final = "application/json"

#: The manifest sits *beside* one variant's receipt directory rather than
#: inside it. A run's receipt directory is read back whole and every file in it
#: is parsed as a receipt (``techtree.runs.artifacts``), so a manifest filed
#: among them would be read as a malformed receipt the first time a run's
#: results were loaded.
_RECEIPTS_DIRECTORY: Final = "receipts"
_RECEIPT_SET_SUFFIX: Final = "-set.json"


class ReceiptSetManifest(ProtocolModel):
    """One variant's receipts, committed to in committed task order."""

    schema_version: Literal["techtree.receipt-set.v1alpha1"]
    run_id: NonEmptyString
    variant: ExperimentVariant
    experiment_manifest_digest: Digest
    ordered_receipt_digests: list[Digest]
    task_membership_digest: Digest
    receipt_count: int = Field(ge=1)

    @model_validator(mode="after")
    def _check_the_commitment_is_internally_consistent(self) -> Self:
        """Reject a manifest whose count or digests contradict themselves."""
        if len(self.ordered_receipt_digests) != self.receipt_count:
            raise ValueError(
                f"the manifest lists {len(self.ordered_receipt_digests)} receipt "
                f"digests and claims a receipt_count of {self.receipt_count}"
            )
        if len(set(self.ordered_receipt_digests)) != len(self.ordered_receipt_digests):
            raise ValueError(
                "a receipt set commits to each receipt once; a repeated digest "
                "would let one episode occupy two positions"
            )
        return self


def seal_receipt(receipt: EpisodeReceipt) -> ObjectEnvelope[EpisodeReceipt]:
    """Wrap one receipt with the digest of its own canonical bytes.

    Unsigned. The envelope's signature field is filled in by whoever holds the
    local executor identity; the digest is what makes the payload immutable and
    is computed here, where the payload is built.
    """
    return ObjectEnvelope[EpisodeReceipt](
        payload=receipt,
        payload_digest=digest_object(receipt),
        signature=None,
    )


def build_receipt_set(
    *,
    run_id: str,
    variant: ExperimentVariant,
    experiment_manifest_digest: Digest,
    signed_receipts: Sequence[ObjectEnvelope[EpisodeReceipt]],
    ordered_task_hashes: Sequence[Digest],
) -> ReceiptSetManifest:
    """Order receipts by TasksetLock membership and build the commitment."""
    committed = [validate_digest(value) for value in ordered_task_hashes]
    by_task = _envelopes_by_task(
        signed_receipts,
        committed=committed,
        run_id=run_id,
        variant=variant,
        experiment_manifest_digest=experiment_manifest_digest,
    )
    return ReceiptSetManifest(
        schema_version=RECEIPT_SET_SCHEMA_VERSION,
        run_id=run_id,
        variant=variant,
        experiment_manifest_digest=validate_digest(experiment_manifest_digest),
        ordered_receipt_digests=[
            by_task[task_hash].payload_digest for task_hash in committed
        ],
        task_membership_digest=membership_digest(committed),
        receipt_count=len(committed),
    )


def verify_receipt_set(
    *,
    manifest: ReceiptSetManifest,
    signed_receipts: Sequence[ObjectEnvelope[EpisodeReceipt]],
    ordered_task_hashes: Sequence[Digest],
) -> None:
    """Verify order, count, payload digests and task membership, or refuse.

    Everything is recomputed from the receipts. A recorded value is never
    compared against itself, which is the only way this can detect a receipt
    that was edited after the manifest was written.
    """
    rebuilt = build_receipt_set(
        run_id=manifest.run_id,
        variant=manifest.variant,
        experiment_manifest_digest=manifest.experiment_manifest_digest,
        signed_receipts=signed_receipts,
        ordered_task_hashes=ordered_task_hashes,
    )
    if rebuilt == manifest:
        return
    raise VerificationError(
        "this receipt set does not commit to the receipts it was given; one of "
        "them, or the manifest itself, changed after it was written",
        code=RECEIPT_SET_INVALID,
        details={
            "run_id": manifest.run_id,
            "variant": manifest.variant.value,
            "recorded": _digest_detail(manifest.ordered_receipt_digests),
            "recomputed": _digest_detail(rebuilt.ordered_receipt_digests),
        },
    )


def receipt_set_path(run_root: Path, variant: ExperimentVariant) -> Path:
    """Return where one variant's receipt-set manifest lives inside a run."""
    return run_root / _RECEIPTS_DIRECTORY / f"{variant.value}{_RECEIPT_SET_SUFFIX}"


def write_receipt_set(manifest: ReceiptSetManifest, path: Path) -> ArtifactRef:
    """Write canonical JSON and return the digest reference to it.

    Canonical bytes rather than the readable spelling, so that the digest of
    the file and the digest of the object are the same number and a reader can
    check the commitment by hashing what is on disk.
    """
    data = canonical_json_bytes(manifest)
    ensure_private_directory(path.parent)
    atomic_write_bytes(path, data)
    return ArtifactRef(
        digest=sha256_digest_bytes(data),
        media_type=RECEIPT_SET_MEDIA_TYPE,
        size=len(data),
        relative_path=None,
    )


# ---------------------------------------------------------------------------
# Joining
# ---------------------------------------------------------------------------


def _envelopes_by_task(
    signed_receipts: Sequence[ObjectEnvelope[EpisodeReceipt]],
    *,
    committed: Sequence[Digest],
    run_id: str,
    variant: ExperimentVariant,
    experiment_manifest_digest: Digest,
) -> dict[Digest, ObjectEnvelope[EpisodeReceipt]]:
    """Index one variant's sealed receipts by the task each one scored."""
    if len(signed_receipts) != len(committed):
        raise VerificationError(
            f"the {variant.value} receipt set was given {len(signed_receipts)} "
            f"receipts for {len(committed)} committed tasks",
            code=EPISODE_COUNT_MISMATCH,
            details={
                "variant": variant.value,
                "receipts": len(signed_receipts),
                "committed": len(committed),
            },
        )

    by_task: dict[Digest, ObjectEnvelope[EpisodeReceipt]] = {}
    for envelope in signed_receipts:
        receipt = envelope.payload
        _require_sealed(envelope)
        _require_belongs(
            receipt,
            run_id=run_id,
            variant=variant,
            experiment_manifest_digest=experiment_manifest_digest,
        )
        task_hash = validate_digest(receipt.task_hash)
        if task_hash in by_task:
            raise VerificationError(
                f"two {variant.value} receipts claim task {task_hash}",
                code=TASK_MEMBERSHIP_MISMATCH,
                details={"variant": variant.value, "task_hash": task_hash},
            )
        by_task[task_hash] = envelope

    missing: list[JsonValue] = [value for value in committed if value not in by_task]
    unexpected: list[JsonValue] = [
        value for value in sorted(set(by_task) - set(committed))
    ]
    if missing or unexpected:
        raise VerificationError(
            f"the {variant.value} receipts do not cover the tasks the Campaign "
            "commits to",
            code=TASK_MEMBERSHIP_MISMATCH,
            details={
                "variant": variant.value,
                "missing": missing,
                "unexpected": unexpected,
            },
        )
    return by_task


def _require_sealed(envelope: ObjectEnvelope[EpisodeReceipt]) -> None:
    """Require an envelope's digest to describe the payload it carries."""
    computed = digest_object(envelope.payload)
    if computed == envelope.payload_digest:
        return
    raise VerificationError(
        "a receipt no longer matches the digest it was sealed under, so it was "
        "changed after it was written",
        code=RECEIPT_SET_INVALID,
        details={
            "receipt_id": envelope.payload.id,
            "sealed": envelope.payload_digest,
            "computed": computed,
        },
    )


def _require_belongs(
    receipt: EpisodeReceipt,
    *,
    run_id: str,
    variant: ExperimentVariant,
    experiment_manifest_digest: Digest,
) -> None:
    """Require a receipt to belong to the run, variant and manifest committed to."""
    if (
        receipt.run_id == run_id
        and receipt.variant is variant
        and receipt.experiment_manifest_digest == experiment_manifest_digest
    ):
        return
    raise VerificationError(
        "a receipt from a different run, variant or experiment manifest cannot "
        "join this receipt set",
        code=RECEIPT_SET_INVALID,
        details={
            "receipt_id": receipt.id,
            "run_id": receipt.run_id,
            "variant": receipt.variant.value,
            "experiment_manifest_digest": receipt.experiment_manifest_digest,
        },
    )


def _digest_detail(digests: Sequence[Digest]) -> list[JsonValue]:
    """Return a digest list in the shape typed error details carry."""
    return [value for value in digests]
