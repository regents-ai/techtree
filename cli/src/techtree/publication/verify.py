"""Checking what the run log answered. Decisions document 0038.

A countersignature is only worth the prior knowledge of which key made it. A
receipt that carries a key and a signature and is checked against *itself*
proves nothing at all: a server that wanted to lie would generate a key, sign
its own invention with it, and hand a participant both halves of a consistent
fiction. So the key is not learned from the answer. It is pinned in the release
(:class:`~techtree.release.models.PublicationCoordinates`), and everything below
is checked against the pin.

Six things have to hold before a receipt is written into a run directory, and
they are six rather than one because each closes a different way of being lied
to.

*The digest matches the payload.* An envelope carries the digest it was signed
under and never recomputes it while parsing, so a payload edited after signing
keeps a digest that no longer describes it. Recomputing here is what catches
that, and it is the same check every other signed document in this protocol
gets.

*The signature names the pinned key.* Not a key, the key. A different identifier
is a different key, including a rotated one: rotation is a new key and a new
release that pins it.

*The receipt carries the key it names.* The identifier is the digest of the
public key, so a receipt whose carried key does not hash to the identifier it
names is inconsistent with itself, and it is caught without a rule of its own.

*The signature verifies.* Against the pinned public key and the digest, which is
the only step that involves any cryptography and the only one that would be
sufficient if the five around it were not needed to make it mean something.

*The receipt is for what was sent.* A receipt naming another run or another
bundle is somebody else's evidence, and filing it in this run's directory would
put a false record beside a true one.

*The entry is on the log this release pins, and every reported check passed.* An
address on another origin is a link somebody else chose. A receipt that reports
a check it did not pass has not accepted the submission, whatever else it says.

Nothing here contacts anything, and nothing here writes anything. It answers one
question — is this the run log's own word about the thing I sent — and the caller
decides what to do about the answer.
"""

from __future__ import annotations

from base64 import b64decode
from typing import Final, NoReturn
from urllib.parse import urlsplit

from techtree.canonical import digest_object
from techtree.crypto import load_public_key, verify_signature
from techtree.errors import ValidationError
from techtree.models.base import Digest, JsonValue, ObjectEnvelope, PublicKeyRef
from techtree.publication.models import (
    PublicationReceiptPayload,
    WithdrawalReceiptPayload,
)
from techtree.release.models import PublicationCoordinates

__all__ = [
    "PUBLICATION_RECEIPT_INVALID",
    "verify_publication_receipt",
    "verify_withdrawal_receipt",
]

#: Stable error code for every way an answer fails to be the run log's own word
#: about what was sent. One code with a named check in its details, rather than
#: six codes: a caller acts on all of them the same way — it writes nothing down
#: — and the detail is what a person needs to understand which one it was.
PUBLICATION_RECEIPT_INVALID: Final = "publication_receipt_invalid"


def verify_publication_receipt(
    envelope: ObjectEnvelope[PublicationReceiptPayload],
    *,
    coordinates: PublicationCoordinates,
    run_id: str,
    bundle_digest: Digest,
) -> None:
    """Raise unless this is the pinned run log's receipt for what was sent.

    Args:
        envelope: what the run log answered, already parsed.
        coordinates: the endpoint, public log origin and network key this
            release pins.
        run_id: the run whose proof was submitted.
        bundle_digest: the bundle digest that was submitted.

    Raises:
        ValidationError: on the first check that does not hold, naming it.
    """
    receipt = envelope.payload
    _check_countersignature(envelope, coordinates, subject=run_id)

    if receipt.run_id != run_id or receipt.bundle_digest != bundle_digest:
        _refuse(
            "receipt.subject",
            "the run log's receipt is for a different submission than the one "
            "that was sent",
            run_id=run_id,
            receipt_run_id=receipt.run_id,
            receipt_bundle_digest=receipt.bundle_digest,
        )

    _check_entry_url(receipt.entry_url, coordinates, subject=run_id)

    if receipt.failed_checks:
        _refuse(
            "receipt.checks",
            f"the run log accepted nothing: {receipt.failed_checks[0].detail}",
            run_id=run_id,
            failed_checks=[check.id for check in receipt.failed_checks],
        )


def verify_withdrawal_receipt(
    envelope: ObjectEnvelope[WithdrawalReceiptPayload],
    *,
    coordinates: PublicationCoordinates,
    bundle_digest: Digest,
) -> None:
    """Raise unless this is the pinned run log's record of this withdrawal.

    The same countersignature and the same origin rule as a publication
    receipt, because it is the same key making the same kind of statement. What
    it does not check is a list of checks: a withdrawal is a request the network
    either honoured or refused, and a refusal is a status rather than a document.

    Args:
        envelope: what the run log answered, already parsed.
        coordinates: the endpoint, public log origin and network key this
            release pins.
        bundle_digest: the entry the withdrawal was asked for.

    Raises:
        ValidationError: on the first check that does not hold, naming it.
    """
    receipt = envelope.payload
    _check_countersignature(envelope, coordinates, subject=bundle_digest)

    if receipt.bundle_digest != bundle_digest:
        _refuse(
            "withdrawal.subject",
            "the run log's answer withdraws a different entry than the one "
            "that was asked for",
            bundle_digest=bundle_digest,
            receipt_bundle_digest=receipt.bundle_digest,
        )

    _check_entry_url(receipt.entry_url, coordinates, subject=bundle_digest)


# ---------------------------------------------------------------------------
# The checks both answers get
# ---------------------------------------------------------------------------


def _check_countersignature(
    envelope: ObjectEnvelope[PublicationReceiptPayload]
    | ObjectEnvelope[WithdrawalReceiptPayload],
    coordinates: PublicationCoordinates,
    *,
    subject: str,
) -> None:
    """Raise unless the pinned network key signed exactly these payload bytes."""
    computed = digest_object(envelope.payload)
    if computed != envelope.payload_digest:
        _refuse(
            "receipt.payload_digest",
            "the run log's answer no longer matches the digest it was signed "
            f"under: sealed {envelope.payload_digest}, computed {computed}",
            subject=subject,
        )

    signature = envelope.signature
    if signature is None:
        _refuse(
            "receipt.signature_present",
            "the run log's answer carries no signature, so nothing countersigns it",
            subject=subject,
        )

    pinned = coordinates.network_key
    if signature.key_id != pinned.key_id:
        _refuse(
            "receipt.signature_key",
            f"the run log's answer is signed by key {signature.key_id}, which "
            f"is not the key {pinned.key_id} this release publishes to",
            subject=subject,
        )

    if not _same_key(envelope.payload.public_key, pinned):
        _refuse(
            "receipt.carried_key",
            "the run log's answer names the pinned key and carries a different one",
            subject=subject,
        )

    public_key = load_public_key(b64decode(pinned.public_key, validate=True))
    if not verify_signature(public_key, envelope.payload_digest, signature):
        _refuse(
            "receipt.signature",
            "the run log's answer does not verify against the public key this "
            "release pins",
            subject=subject,
        )


def _check_entry_url(
    entry_url: str, coordinates: PublicationCoordinates, *, subject: str
) -> None:
    """Raise unless the entry lives on the public log this release pins."""
    pinned = urlsplit(coordinates.public_log_url)
    entry = urlsplit(entry_url)
    if entry.scheme != "https" or entry.netloc != pinned.netloc:
        _refuse(
            "receipt.entry_url",
            f"the run log says this entry lives at {entry_url}, which is not on "
            f"{coordinates.public_log_url}",
            subject=subject,
            entry_url=entry_url,
        )


def _same_key(carried: PublicKeyRef, pinned: PublicKeyRef) -> bool:
    """Return whether two key references describe the same key, field for field."""
    return (
        carried.algorithm == pinned.algorithm
        and carried.key_id == pinned.key_id
        and carried.public_key == pinned.public_key
    )


def _refuse(check: str, message: str, **details: JsonValue) -> NoReturn:
    """Raise the one refusal, naming which check did not hold."""
    raise ValidationError(
        message,
        code=PUBLICATION_RECEIPT_INVALID,
        details={"check": check, **details},
    )
