"""Withdrawing one published entry. Decisions document 0038.

The founder settled two things about withdrawal on 2026-08-27 and this module
is both of them.

*A published entry is withdrawn, never deleted.* Withdrawal is an appended
event: the entry stays where it is, marked, and the address it lives at goes on
answering. Nothing here asks for removal, and what comes back names where the
entry still is rather than reporting that it is gone.

*It is implemented rather than promised.* A public promise with no executable
path would be worse than neither, so this is the executable path. The
participant signs a canonical request with the same key that signed the run —
the identity store already holds it, and it is the only key this machine has —
and the network verifies that signature against the participant key inside the
publication it already accepted. That is why the request carries no public key
of its own: a key that arrived with the request would be a key the requester
chose, and looking it up in the accepted bundle instead is the whole of the
authorisation.

Two things are deliberately absent.

*No reason.* Nothing a submitter writes appears on the site, and a free-text
reason attached to a public entry is the one string that would. There is no
field for one and there will not be one.

*No local record.* The public log is the record of a withdrawal, because that is
where the appended event lives. Writing a second one beside the run would make
this machine a source of truth about a public log's contents that it cannot
keep current, and a run directory is addressed by run and a withdrawal by bundle
digest — a person withdrawing an entry may not have the run on this machine at
all.

The request goes to the same address a submission goes to. Decisions 0038 gives
the site exactly one write address, and discriminating on ``schema_version``
inside one address is what keeps that true.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import canonical_json_bytes
from techtree.constants import PUBLICATION_WITHDRAWAL_SCHEMA_VERSION
from techtree.errors import ValidationError
from techtree.identity.service import IdentityService
from techtree.models.base import Digest, ObjectEnvelope
from techtree.publication.models import WithdrawalReceiptPayload, WithdrawalRequest
from techtree.publication.transport import PublicationTransport
from techtree.publication.verify import (
    PUBLICATION_RECEIPT_INVALID,
    verify_withdrawal_receipt,
)
from techtree.release.models import PublicationCoordinates

__all__ = [
    "WithdrawalOutcome",
    "WithdrawalService",
]


@dataclass(frozen=True)
class WithdrawalOutcome:
    """What the run log said when it marked one entry withdrawn."""

    bundle_digest: Digest
    entry_url: str
    withdrawn_at: datetime
    #: The participant key the request was signed with, so a person can see that
    #: the entry was withdrawn by the identity that published it.
    key_id: str


class WithdrawalService:
    """Builds, signs and sends one withdrawal, and checks what came back."""

    def __init__(
        self,
        *,
        coordinates: PublicationCoordinates,
        endpoint: str,
        identity: IdentityService,
        transport: PublicationTransport,
        clock: Callable[[], datetime],
    ) -> None:
        self._coordinates = coordinates
        self._endpoint = endpoint
        self._identity = identity
        self._transport = transport
        self._clock = clock

    @property
    def endpoint(self) -> str:
        """Return the address this withdrawal is sent to."""
        return self._endpoint

    def request(self, bundle_digest: Digest) -> ObjectEnvelope[WithdrawalRequest]:
        """Return the signed request this withdrawal would send.

        Separate from :meth:`withdraw` so that what is signed can be shown to a
        person, and inspected by a test, without anything being sent. Signing is
        local work; only :meth:`withdraw` opens a socket.
        """
        return self._identity.sign_object(
            WithdrawalRequest(
                schema_version=PUBLICATION_WITHDRAWAL_SCHEMA_VERSION,
                bundle_digest=bundle_digest,
                requested_at=self._clock(),
            )
        )

    def withdraw(self, bundle_digest: Digest) -> WithdrawalOutcome:
        """Send the signed withdrawal and return what the run log answered.

        No volunteered address travels with a withdrawal. There is nothing to
        volunteer: the request is about an entry that already exists, and the
        header exists for a submission's optional contributor address alone.
        """
        signed = self.request(bundle_digest)
        response = self._transport.submit(
            endpoint=self.endpoint,
            body=canonical_json_bytes(signed),
            contributor_address=None,
        )
        receipt = self._receipt(response, bundle_digest)
        return WithdrawalOutcome(
            bundle_digest=receipt.bundle_digest,
            entry_url=receipt.entry_url,
            withdrawn_at=receipt.withdrawn_at,
            key_id=self._identity.store.load_public().key_id,
        )

    def _receipt(
        self, response: bytes, bundle_digest: Digest
    ) -> WithdrawalReceiptPayload:
        """Parse the answer and refuse anything that is not this withdrawal's."""
        try:
            envelope = ObjectEnvelope[WithdrawalReceiptPayload].model_validate_json(
                response
            )
        except PydanticValidationError as error:
            raise ValidationError(
                "the run log answered with something that is not a withdrawal "
                "receipt, so nothing is known about what it did",
                code=PUBLICATION_RECEIPT_INVALID,
                details={"bundle_digest": bundle_digest},
            ) from error

        verify_withdrawal_receipt(
            envelope, coordinates=self._coordinates, bundle_digest=bundle_digest
        )
        return envelope.payload
