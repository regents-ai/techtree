"""A run log that never existed, standing in for one that does not yet.

Decisions 0038 puts the whole of publishing behind one seam, and this is what
the tests put in it. A stub transport records the bytes it was handed and
answers with a receipt written here; everything on either side of it — the
offline verification, the plan, the receipt file, the journal — is the real
code, so substituting this replaces the request and nothing else.

This is a package rather than a module because ``conformance-submission.json``
sits beside it: the submission bytes the other half of this feature is tested
against, and :mod:`fixtures.publication.conformance`, which produces them.

The receipt is built rather than recorded because there is nothing to record
from: no server exists yet. What it has to be is a well-formed
:class:`~techtree.publication.models.PublicationReceipt`, and the model is what
says what that means.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final

from techtree.canonical import canonical_json_bytes
from techtree.errors import TechtreeError
from techtree.models.base import PublicKeyRef, SignatureEnvelope
from techtree.publication.models import (
    PublicationCheck,
    PublicationReceipt,
    PublicationSubmission,
)
from techtree.publication.transport import PUBLICATION_TRANSPORT_FAILED

__all__ = [
    "ADDRESS",
    "ENDPOINT",
    "ENDPOINT_VARIABLE",
    "ENTRY_URL",
    "LOG_SEQUENCE",
    "RefusingTransport",
    "StubTransport",
    "receipt_for",
]

#: An address with a run log at it, which there is not.
ENDPOINT: Final = "https://techtree.example/api/v1/run-log"

#: The setting that names it, and the environment variable that overrides it.
ENDPOINT_VARIABLE: Final = "TECHTREE_PUBLICATION_ENDPOINT"

#: One of EIP-55's own worked examples, so a test that sends it is sending an
#: address that is well formed in the way a real one would be.
ADDRESS: Final = "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"

LOG_SEQUENCE: Final = 7
ENTRY_URL: Final = "https://techtree.example/log/7"

_ACCEPTED_AT: Final = datetime(2026, 8, 27, 9, 0, tzinfo=UTC)


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
        return canonical_json_bytes(receipt_for(submission))

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
) -> PublicationReceipt:
    """Return the receipt a network that accepted this submission would sign."""
    return PublicationReceipt(
        schema_version="techtree.publication-receipt.v1alpha1",
        id="publication_0123456789abcdef0123456789abcdef",
        run_id=run_id or submission.run_id,
        log_sequence=LOG_SEQUENCE,
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
        entry_url=ENTRY_URL,
        public_key=PublicKeyRef(
            algorithm="ed25519",
            key_id="techtree-run-log",
            public_key=base64.b64encode(b"n" * 32).decode("ascii"),
        ),
        signature=SignatureEnvelope(
            algorithm="ed25519",
            key_id="techtree-run-log",
            signature=base64.b64encode(b"s" * 64).decode("ascii"),
        ),
    )
