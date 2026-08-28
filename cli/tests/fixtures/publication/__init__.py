"""A run log that never existed, standing in for one that does not yet.

Decisions 0038 puts the whole of publishing behind one seam, and this is what
the tests put in it. A stub transport records the bytes it was handed and
answers with a receipt signed here; everything on either side of it — the
offline verification, the plan, the receipt file, the journal — is the real
code, so substituting this replaces the request and nothing else.

This is a package rather than a module because ``conformance-submission.json``
sits beside it: the submission bytes the other half of this feature is tested
against, and :mod:`fixtures.publication.conformance`, which produces them.

The receipts are built rather than recorded because there is nothing to record
from: no server exists yet. What they have to be is well-formed envelopes
carrying the payloads :mod:`techtree.publication.models` defines, signed by the
key :data:`COORDINATES` pins — because the CLI checks every answer against the
pinned key before it writes anything down, and a fixture that could not produce
a verifying signature would only ever exercise the refusal.

The key here is a test key and is spelled like one: its private half is the
bytes 0 to 31, in a repository, in a file called fixtures. Nothing about it is
secret and nothing about it needs to be. The release pins a different key
entirely, and a test that wants to check the pin exercises the mismatch on
purpose.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final

from pydantic import BaseModel

from techtree.canonical import canonical_json_bytes, digest_object, sha256_digest_bytes
from techtree.crypto import load_private_key, public_key_bytes, public_key_to_base64
from techtree.crypto import sign_digest as _sign_digest
from techtree.errors import TechtreeError
from techtree.models.base import ObjectEnvelope, PublicKeyRef
from techtree.publication.models import (
    PublicationCheck,
    PublicationReceiptPayload,
    PublicationSubmission,
    WithdrawalReceiptPayload,
)
from techtree.publication.transport import PUBLICATION_TRANSPORT_FAILED
from techtree.release.models import PinnedNetworkKey, PublicationCoordinates

__all__ = [
    "ADDRESS",
    "COORDINATES",
    "ENDPOINT",
    "ENDPOINT_VARIABLE",
    "ENTRY_URL",
    "LOG_SEQUENCE",
    "NETWORK_KEY",
    "PINNED_ENDPOINT",
    "PUBLIC_LOG_URL",
    "RefusingTransport",
    "StubTransport",
    "network_signed",
    "receipt_for",
    "withdrawal_receipt_for",
]

#: What the release pins: where a submission goes, and where an entry is then
#: read. Both are addresses on a host that does not exist.
PINNED_ENDPOINT: Final = "https://run-log.techtree.example/api/v1/publications"
PUBLIC_LOG_URL: Final = "https://run-log.techtree.example/runs"

#: The development override, which is a different address on purpose: a test
#: that sets it and sees it used has seen the override win rather than seen two
#: spellings of the same string agree.
ENDPOINT: Final = "https://techtree.example/api/v1/run-log"

#: The setting that names it, and the environment variable that overrides it.
ENDPOINT_VARIABLE: Final = "TECHTREE_PUBLICATION_ENDPOINT"

#: One of EIP-55's own worked examples, so a test that sends it is sending an
#: address that is well formed in the way a real one would be.
ADDRESS: Final = "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"

LOG_SEQUENCE: Final = 7

#: A run is addressed on the log by its bundle digest, so an entry address is
#: the public log's own address with one appended. Decisions 0038.
ENTRY_URL: Final = f"{PUBLIC_LOG_URL}/sha256:{'7' * 64}"

_ACCEPTED_AT: Final = datetime(2026, 8, 27, 9, 0, tzinfo=UTC)
_WITHDRAWN_AT: Final = datetime(2026, 8, 28, 9, 0, tzinfo=UTC)

#: The stand-in run log's signing key. Thirty-two bytes counting up, because a
#: test key that looked like a real one would be a test key somebody could
#: mistake for a real one.
_NETWORK_PRIVATE_KEY: Final = load_private_key(bytes(range(32)))
_NETWORK_PUBLIC_BYTES: Final = public_key_bytes(_NETWORK_PRIVATE_KEY)

NETWORK_KEY: Final = PinnedNetworkKey(
    algorithm="ed25519",
    key_id=sha256_digest_bytes(_NETWORK_PUBLIC_BYTES),
    public_key=public_key_to_base64(_NETWORK_PRIVATE_KEY.public_key()),
)

#: The coordinates a test build publishes against.
COORDINATES: Final = PublicationCoordinates(
    submission_endpoint=PINNED_ENDPOINT,
    public_log_url=PUBLIC_LOG_URL,
    network_key=NETWORK_KEY,
)

#: The key as it is carried inside a receipt payload, which is a plain
#: reference rather than the pinned type: the receiving side has no reason to
#: know about this repository's release models, and the CLI compares the two
#: field for field.
CARRIED_KEY: Final = PublicKeyRef(
    algorithm=NETWORK_KEY.algorithm,
    key_id=NETWORK_KEY.key_id,
    public_key=NETWORK_KEY.public_key,
)


def network_signed[T: BaseModel](payload: T) -> ObjectEnvelope[T]:
    """Return the payload in the envelope the stand-in run log would sign it in."""
    digest = digest_object(payload)
    return ObjectEnvelope[T](
        payload=payload,
        payload_digest=digest,
        signature=_sign_digest(_NETWORK_PRIVATE_KEY, digest, key_id=NETWORK_KEY.key_id),
    )


class StubTransport:
    """The seam, standing still."""

    def __init__(
        self, answer: Callable[[PublicationSubmission], bytes] | None = None
    ) -> None:
        self.bodies: list[bytes] = []
        #: What travelled beside each body. An address is never inside one.
        self.addresses: list[str | None] = []
        self.endpoints: list[str] = []
        self._answer = answer

    def submit(
        self, *, endpoint: str, body: bytes, contributor_address: str | None
    ) -> bytes:
        """Record what was sent and return what the test wants back."""
        self.endpoints.append(endpoint)
        self.bodies.append(body)
        self.addresses.append(contributor_address)
        submission = PublicationSubmission.model_validate_json(body)
        if self._answer is not None:
            return self._answer(submission)
        return canonical_json_bytes(network_signed(receipt_for(submission)))

    @property
    def submission(self) -> PublicationSubmission:
        """Return the one submission that was sent."""
        assert len(self.bodies) == 1
        return PublicationSubmission.model_validate_json(self.bodies[0])


class RefusingTransport:
    """A run log nobody can reach, which is every run log today."""

    def submit(
        self, *, endpoint: str, body: bytes, contributor_address: str | None
    ) -> bytes:
        """Fail the way an unreachable address fails."""
        raise TechtreeError(
            "the run log could not be reached, so nothing was sent",
            code=PUBLICATION_TRANSPORT_FAILED,
            retryable=True,
        )


def receipt_for(
    submission: PublicationSubmission,
    *,
    run_id: str | None = None,
    bundle_digest: str | None = None,
    checks: list[PublicationCheck] | None = None,
    entry_url: str | None = None,
    public_key: PublicKeyRef | None = None,
    log_sequence: int | None = None,
) -> PublicationReceiptPayload:
    """Return the payload a network that accepted this submission would sign."""
    return PublicationReceiptPayload(
        schema_version="techtree.publication-receipt.v1alpha1",
        id="publication_0123456789abcdef0123456789abcdef",
        run_id=run_id or submission.run_id,
        log_sequence=LOG_SEQUENCE if log_sequence is None else log_sequence,
        bundle_digest=bundle_digest or submission.bundle_digest,
        accepted_at=_ACCEPTED_AT,
        checks=checks
        or [
            PublicationCheck(
                id="bundle.signature",
                passed=True,
                detail="the participant's key signed every file",
            )
        ],
        entry_url=entry_url or ENTRY_URL,
        public_key=public_key or CARRIED_KEY,
    )


def withdrawal_receipt_for(
    bundle_digest: str,
    *,
    entry_url: str | None = None,
) -> WithdrawalReceiptPayload:
    """Return the payload a network that marked an entry withdrawn would sign."""
    return WithdrawalReceiptPayload(
        schema_version="techtree.publication-withdrawal-receipt.v1alpha1",
        bundle_digest=bundle_digest,
        entry_url=entry_url or ENTRY_URL,
        withdrawn_at=_WITHDRAWN_AT,
        public_key=CARRIED_KEY,
    )
