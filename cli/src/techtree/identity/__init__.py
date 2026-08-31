"""The one local key that binds a participant to their own receipts.

Spec section 7.5. Decisions document 0005, amendment 4.

WP0 built the Ed25519 primitives and froze them shut: :mod:`techtree.crypto`
knows how to make a key and check a signature, and nothing in the package knew
where a key lived or when to use one. This package is the activation, and it is
deliberately the *whole* of it — every other module asks this one to sign, so
there is exactly one place that touches private material.

Three rules hold everywhere below.

*The private half never leaves the identities directory.* It is written once,
owner-readable only, and loaded into memory to sign a digest. It is never
serialized into a document, never logged, never carried in a typed error's
details, and never written into a proof bundle. Only the public half travels.

*The key is self-issued, and the vocabulary says so.* Nothing registers it,
nothing uploads it, and no authority vouches for it. What a signature over
these receipts proves is that the participant's own key vouches for bytes that
verify against each other — which is what ``proof_grade: P1`` is permitted to
mean and nothing more.

*What is signed is the digest string.* :func:`techtree.crypto.sign_digest`
signs the ASCII ``sha256:...`` spelling of the canonical bytes, so a verifier
holding the digest can check the signature, and the thing attested to is
exactly the value that appears in the protocol document.

The division of labour:

``models``
    The public identity, and the shape a verification verdict is reported in.
``store``
    Where the key material lives on disk, and how it is created and loaded.
``service``
    Signing objects into envelopes, and verifying envelopes against a key.
"""

from __future__ import annotations

__all__: list[str] = []
