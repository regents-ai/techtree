"""The local identity, and the shape of a verification verdict.

Spec sections 7.5 and 7.12.

Two vocabularies live here because they are used together everywhere and
neither one belongs to the frozen v0.1 protocol.

:class:`ExecutorIdentity` is the public half of the participant's key, written
into the identities directory and copied into every proof bundle. It is a
:class:`~techtree.models.base.ProtocolModel` so that it is frozen, canonically
serializable, and digestible like everything else a bundle commits to. The
private half has no model at all: it is raw bytes on disk and an in-memory key
object, and giving it a document shape would be the first step towards it
appearing in one.

:class:`VerificationResult` is how every check in this subsystem reports. A
verifier that raised on the first broken thing would tell a reader which rule
failed first rather than what is wrong with what they are holding, so checks
are collected: each one named, each one with its own stable code, and the
verdict computed from them rather than asserted alongside them.
"""

from __future__ import annotations

from typing import Final, Literal, Self

from pydantic import model_validator

from techtree.models.base import (
    Base64String,
    NonEmptyString,
    ProtocolModel,
    UtcDateTime,
)

__all__ = [
    "LOCAL_IDENTITY_INVALID",
    "SIGNATURE_VERIFICATION_FAILED",
    "ExecutorIdentity",
    "VerificationMessage",
    "VerificationResult",
    "VerificationStatus",
]

type VerificationStatus = Literal["passed", "failed", "warning"]
"""What one check found. ``warning`` is a claim that holds more weakly than it
wanted to, never a failure that someone decided to be relaxed about."""

#: Stable error codes. Spec section 15.
LOCAL_IDENTITY_INVALID: Final = "local_identity_invalid"
SIGNATURE_VERIFICATION_FAILED: Final = "signature_verification_failed"


class ExecutorIdentity(ProtocolModel):
    """The public half of one participant-controlled local signing key.

    ``created_at`` is operational identity metadata: it says when this machine
    made a key, and it is deliberately not part of any scientific comparison.
    Two participants running the same Campaign produce the same measurements
    and different identities.
    """

    kind: Literal["local_ed25519"]
    key_id: NonEmptyString
    algorithm: Literal["ed25519"]
    public_key: Base64String
    created_at: UtcDateTime


class VerificationMessage(ProtocolModel):
    """One named check and what it found.

    ``code`` is the spec section 15 error code a failure of this check reports
    under, so a machine reading a failed verification gets the same vocabulary
    whether it read the envelope or the exception.
    """

    id: NonEmptyString
    status: VerificationStatus
    code: NonEmptyString
    detail: NonEmptyString


class VerificationResult(ProtocolModel):
    """Every check a verification ran, and whether the thing verified."""

    verified: bool
    messages: list[VerificationMessage]

    @property
    def failures(self) -> list[VerificationMessage]:
        """Return every check that failed."""
        return [message for message in self.messages if message.status == "failed"]

    @property
    def warnings(self) -> list[VerificationMessage]:
        """Return every check that passed with a weaker claim than it wanted."""
        return [message for message in self.messages if message.status == "warning"]

    @model_validator(mode="after")
    def _check_the_verdict_is_the_one_the_checks_support(self) -> Self:
        """Reject a result whose verdict disagrees with its own checks."""
        if self.verified and self.failures:
            raise ValueError(
                "a verification that reports success cannot carry a failed check"
            )
        if not self.verified and not self.failures:
            raise ValueError(
                "a verification that reports failure must name the check that failed"
            )
        if not self.messages:
            raise ValueError("a verification result records the checks it ran")
        return self
