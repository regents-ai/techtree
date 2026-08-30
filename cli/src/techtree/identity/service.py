"""Signing objects, and checking signed ones. Spec sections 7.5 and 7.12.

Everything that gets signed in Techtree goes through :meth:`IdentityService.
sign_object`, and everything that gets checked goes through
:func:`verify_signed_object`. Keeping both on one page is what makes the two
halves impossible to drift apart: the signature is made over the digest of the
payload's canonical bytes, and the check recomputes that digest from the
payload it was handed rather than trusting the one the envelope records.

That recomputation is the entire point of the envelope. A stored envelope
carries ``payload_digest`` and never recalculates it during validation, so an
edited payload keeps its old digest and looks fine to a parser. Verification is
where the two are compared, and it is why a receipt that was changed after it
was written cannot pass.

Verification takes the identity it should check against as an argument rather
than reading the local store. A proof bundle carries the public key that signed
it, and a bundle is verified against *that* key — offline, on another machine,
with no Techtree identity of its own. Checking a stranger's bundle against this
machine's key would fail every bundle for the wrong reason.

What a verified signature proves is bounded and worth stating plainly: these
bytes have not changed since the holder of that private key signed them. The
key is self-issued and local, so nothing here says who ran the evaluation, and
nothing here is a third party's word for anything.
"""

from __future__ import annotations

from base64 import b64decode
from typing import Final

from pydantic import BaseModel

from techtree.canonical import digest_object
from techtree.crypto import load_public_key, sign_digest, verify_signature
from techtree.errors import ValidationError
from techtree.identity.models import (
    LOCAL_IDENTITY_INVALID,
    SIGNATURE_VERIFICATION_FAILED,
    ExecutorIdentity,
    VerificationMessage,
    VerificationResult,
)
from techtree.identity.store import IdentityStore
from techtree.models.base import ObjectEnvelope

__all__ = [
    "IdentityService",
    "verify_signed_object",
]

_PASSED: Final = "passed"
_FAILED: Final = "failed"


class IdentityService:
    """The local identity, ready to sign and to check its own signatures."""

    def __init__(self, store: IdentityStore) -> None:
        self._store = store

    @property
    def store(self) -> IdentityStore:
        """Return the store this service signs with."""
        return self._store

    def ensure(self) -> ExecutorIdentity:
        """Return the existing valid identity, creating one if there is none.

        Creation happens when a person has asked for something that needs a
        key — ``techtree setup``, or a run they started reaching the point
        where its receipts are sealed. Nothing creates a key at import time and
        nothing creates one on a machine that is only being inspected.

        An identity whose two halves no longer describe each other is not
        silently replaced. The old key signed real receipts; replacing it would
        make those signatures unverifiable without saying so.
        """
        if not self._store.exists():
            return self._store.create()

        identity = self._store.load_public()
        if self._store.verify_pair():
            return identity
        raise ValidationError(
            "the two halves of this machine's local signing identity do not "
            "describe the same key, so nothing may be signed with it",
            code=LOCAL_IDENTITY_INVALID,
            details={"key_id": identity.key_id},
        )

    def sign_object[T: BaseModel](self, value: T) -> ObjectEnvelope[T]:
        """Canonicalize, digest, and sign one protocol object."""
        identity = self._store.load_public()
        digest = digest_object(value)
        signature = sign_digest(
            self._store.load_private(), digest, key_id=identity.key_id
        )
        return ObjectEnvelope[T](
            payload=value, payload_digest=digest, signature=signature
        )

    def verify_envelope[T: BaseModel](
        self, envelope: ObjectEnvelope[T]
    ) -> VerificationResult:
        """Verify one envelope against this machine's own public identity."""
        return verify_signed_object(
            identity=self._store.load_public(), envelope=envelope
        )


def verify_signed_object[T: BaseModel](
    *,
    identity: ExecutorIdentity,
    envelope: ObjectEnvelope[T],
    subject: str = "object",
) -> VerificationResult:
    """Verify one envelope's digest and signature against a public identity.

    ``subject`` names what is being checked — a bundle path, usually — so that
    a reader of a failed bundle verification learns which of forty receipts is
    the problem rather than that "a signature" failed.
    """
    messages: list[VerificationMessage] = []

    computed = digest_object(envelope.payload)
    digest_matches = computed == envelope.payload_digest
    messages.append(
        VerificationMessage(
            id=f"{subject}.payload_digest",
            status=_PASSED if digest_matches else _FAILED,
            code=SIGNATURE_VERIFICATION_FAILED,
            detail=(
                "the payload still matches the digest it was signed under"
                if digest_matches
                else (
                    "the payload no longer matches the digest it was signed "
                    f"under: sealed {envelope.payload_digest}, computed {computed}"
                )
            ),
        )
    )

    signature = envelope.signature
    if signature is None:
        messages.append(
            VerificationMessage(
                id=f"{subject}.signature_present",
                status=_FAILED,
                code=SIGNATURE_VERIFICATION_FAILED,
                detail="this object carries no signature, so nothing vouches for it",
            )
        )
        return VerificationResult(verified=False, messages=messages)

    named_key = signature.key_id == identity.key_id
    messages.append(
        VerificationMessage(
            id=f"{subject}.signature_key",
            status=_PASSED if named_key else _FAILED,
            code=LOCAL_IDENTITY_INVALID,
            detail=(
                f"signed by key {identity.key_id}"
                if named_key
                else (
                    f"signed by key {signature.key_id}, which is not the key "
                    f"{identity.key_id} this proof carries"
                )
            ),
        )
    )

    verified = named_key and digest_matches and _signature_verifies(identity, envelope)
    messages.append(
        VerificationMessage(
            id=f"{subject}.signature",
            status=_PASSED if verified else _FAILED,
            code=SIGNATURE_VERIFICATION_FAILED,
            detail=(
                "the signature verifies against the public key carried with it"
                if verified
                else "the signature does not verify against the public key "
                "carried with it"
            ),
        )
    )
    return VerificationResult(verified=verified, messages=messages)


def _signature_verifies[T: BaseModel](
    identity: ExecutorIdentity, envelope: ObjectEnvelope[T]
) -> bool:
    """Check the detached signature against the identity's public key."""
    signature = envelope.signature
    if signature is None:
        return False
    public_key = load_public_key(b64decode(identity.public_key, validate=True))
    return verify_signature(public_key, envelope.payload_digest, signature)
