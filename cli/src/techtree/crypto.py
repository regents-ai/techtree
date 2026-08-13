"""Ed25519 primitives. Spec sections 10.8 and 2.6.

This module is deliberately inert. It knows how to make a key, move key
material in and out of raw bytes, sign a digest string, and check a signature.
It knows nothing about where keys live, which key is "ours", or when signing
should happen.

Decisions document 0001 froze that boundary for WP0–WP5, when nothing signed
anything; decisions document 0005 amendment 4 turned signing on in WP7. The
boundary itself did not move. There is still no key store here on purpose:
:mod:`techtree.identity` is the one place that knows where a key lives, which
key is this machine's, and when something is signed with it.

What gets signed is the ASCII digest string — ``sha256:`` and 64 hexadecimal
characters — rather than the canonical bytes themselves. A verifier can then
check a signature while holding only the digest, and the thing being attested
to is exactly the value that appears in the protocol document.
"""

from __future__ import annotations

import base64

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from techtree.canonical import validate_digest
from techtree.errors import ValidationError
from techtree.models.base import Digest, SignatureEnvelope

__all__ = [
    "ED25519_PRIVATE_KEY_BYTES",
    "ED25519_PUBLIC_KEY_BYTES",
    "ED25519_SIGNATURE_BYTES",
    "generate_private_key",
    "load_private_key",
    "load_public_key",
    "private_key_bytes",
    "public_key_bytes",
    "public_key_to_base64",
    "sign_digest",
    "verify_signature",
]

ED25519_PRIVATE_KEY_BYTES = 32
ED25519_PUBLIC_KEY_BYTES = 32
ED25519_SIGNATURE_BYTES = 64


def generate_private_key() -> Ed25519PrivateKey:
    """Create a new Ed25519 key."""
    return Ed25519PrivateKey.generate()


def public_key_bytes(private_key: Ed25519PrivateKey) -> bytes:
    """Return raw public-key bytes."""
    return private_key.public_key().public_bytes_raw()


def private_key_bytes(private_key: Ed25519PrivateKey) -> bytes:
    """Return raw private-key bytes."""
    return private_key.private_bytes_raw()


def load_private_key(raw: bytes) -> Ed25519PrivateKey:
    """Load and validate raw private key material."""
    if len(raw) != ED25519_PRIVATE_KEY_BYTES:
        raise ValidationError(
            f"Ed25519 private keys are {ED25519_PRIVATE_KEY_BYTES} raw bytes",
            details={"length": len(raw)},
        )
    return Ed25519PrivateKey.from_private_bytes(raw)


def load_public_key(raw: bytes) -> Ed25519PublicKey:
    """Load and validate raw public key material."""
    if len(raw) != ED25519_PUBLIC_KEY_BYTES:
        raise ValidationError(
            f"Ed25519 public keys are {ED25519_PUBLIC_KEY_BYTES} raw bytes",
            details={"length": len(raw)},
        )
    return Ed25519PublicKey.from_public_bytes(raw)


def public_key_to_base64(public_key: Ed25519PublicKey) -> str:
    """Return the base64 spelling protocol documents carry a public key in."""
    return base64.b64encode(public_key.public_bytes_raw()).decode("ascii")


def sign_digest(
    private_key: Ed25519PrivateKey,
    digest: Digest,
    *,
    key_id: str,
) -> SignatureEnvelope:
    """Sign the ASCII digest string."""
    message = validate_digest(digest).encode("ascii")
    signature = private_key.sign(message)
    return SignatureEnvelope(
        algorithm="ed25519",
        key_id=key_id,
        signature=base64.b64encode(signature).decode("ascii"),
    )


def verify_signature(
    public_key: Ed25519PublicKey,
    digest: Digest,
    signature: SignatureEnvelope,
) -> bool:
    """Verify the digest signature.

    Returns ``False`` for a signature that is well-formed but wrong — a wrong
    key, a different digest, or corrupted signature bytes. A malformed digest
    is a different kind of problem and raises instead.
    """
    message = validate_digest(digest).encode("ascii")
    raw_signature = base64.b64decode(signature.signature, validate=True)
    if len(raw_signature) != ED25519_SIGNATURE_BYTES:
        return False
    try:
        public_key.verify(raw_signature, message)
    except InvalidSignature:
        return False
    return True
