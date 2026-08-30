"""Where the local signing key lives. Spec section 7.5.

```text
<techtree home>/identities/
├── executor-private-key.bin       mode 0600, raw Ed25519 private bytes
└── executor-public.json           mode 0600, canonical ExecutorIdentity
```

The directory is :attr:`~techtree.paths.TechtreePaths.identities_dir`, which
WP0 resolved and deliberately never created: decisions document 0001 forbade
device keys through WP5, so the location was settled and the directory did not
exist. This module is the first thing entitled to create it.

Four properties are the reason this is a module rather than two file writes.

*Creation is exclusive.* The private key is created with ``O_EXCL``, so a
second creation attempt is reported as a conflict instead of quietly replacing
the key every existing receipt was signed under. A replaced key does not
invalidate old signatures loudly; it invalidates them silently, which is worse.

*The private half is never returned as bytes.* :meth:`IdentityStore.load_private`
hands back a key object that can sign. Nothing here exposes a serialization of
it, no error detail carries it, and the only bytes written are the ones written
once at creation.

*The pair is checkable without a document.* :meth:`IdentityStore.verify_pair`
signs a fixed, domain-separated challenge in memory and verifies it against the
stored public half. That is how a caller learns the two files still belong to
each other before it signs anything real with them.

*Both halves are digested together.* The key identifier is the digest of the
public key bytes, so it is derived rather than assigned: two files that
disagree about which key they describe cannot both be self-consistent.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import canonical_json_bytes, sha256_digest_bytes
from techtree.crypto import (
    ED25519_PRIVATE_KEY_BYTES,
    generate_private_key,
    load_private_key,
    load_public_key,
    private_key_bytes,
    public_key_bytes,
    public_key_to_base64,
    sign_digest,
    verify_signature,
)
from techtree.errors import ConflictError, NotFoundError, ValidationError
from techtree.fs import (
    atomic_write_bytes,
    ensure_private_directory,
    fsync_directory,
    open_exclusive,
)
from techtree.identity.models import LOCAL_IDENTITY_INVALID, ExecutorIdentity
from techtree.paths import TechtreePaths

__all__ = [
    "IDENTITY_SELF_CHECK_CHALLENGE",
    "PRIVATE_KEY_FILENAME",
    "PUBLIC_IDENTITY_FILENAME",
    "IdentityStore",
]

#: Raw Ed25519 private bytes. The specification permits raw or a clearly
#: versioned encoding; raw is what the primitives already read and write, and
#: an encoding this file did not need would be one more thing to get wrong.
PRIVATE_KEY_FILENAME: Final = "executor-private-key.bin"

PUBLIC_IDENTITY_FILENAME: Final = "executor-public.json"

#: What :meth:`IdentityStore.verify_pair` signs. Domain-separated so that a
#: signature made during a self-check can never be replayed as a signature over
#: a protocol object: no canonical document digests to this value.
IDENTITY_SELF_CHECK_CHALLENGE: Final = b"techtree/identity/self-check/v1"

#: Owner read and write only, for both halves. The public half is not secret,
#: but it is local state in a single-user directory and there is no reason for
#: it to be more readable than everything beside it.
_FILE_MODE: Final = 0o600


class IdentityStore:
    """Creates, loads, and self-checks the local executor identity."""

    def __init__(
        self,
        paths: TechtreePaths,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._paths = paths
        self._clock = clock or _utc_now

    # -- placement ----------------------------------------------------------

    @property
    def directory(self) -> Path:
        """Return the directory both halves of the identity live in."""
        return self._paths.identities_dir

    @property
    def private_key_path(self) -> Path:
        """Return where the private half lives. Never copied anywhere else."""
        return self.directory / PRIVATE_KEY_FILENAME

    @property
    def public_identity_path(self) -> Path:
        """Return where the public half lives."""
        return self.directory / PUBLIC_IDENTITY_FILENAME

    # -- lifecycle ----------------------------------------------------------

    def exists(self) -> bool:
        """Return whether both halves of the identity are present."""
        return self.private_key_path.is_file() and self.public_identity_path.is_file()

    def create(self) -> ExecutorIdentity:
        """Generate a key, write both halves exclusively, and return the public one.

        The private half is written first and with ``O_EXCL``: it is the file
        whose existence means "this machine has an identity", so it is the file
        that has to win the race. The public half is derived from it, which is
        why rewriting it over a stale one is correct rather than destructive.
        """
        ensure_private_directory(self.directory)
        private_key = generate_private_key()

        try:
            with open_exclusive(self.private_key_path, _FILE_MODE) as handle:
                handle.write(private_key_bytes(private_key))
                handle.flush()
                os.fsync(handle.fileno())
        except ConflictError as error:
            raise ConflictError(
                "this machine already has a local signing key; replacing it "
                "would silently orphan every receipt signed under the old one",
                code=LOCAL_IDENTITY_INVALID,
                details={"path": str(self.private_key_path)},
            ) from error

        identity = _identity_for(private_key, created_at=self._clock())
        atomic_write_bytes(
            self.public_identity_path,
            canonical_json_bytes(identity),
            mode=_FILE_MODE,
        )
        fsync_directory(self.directory)
        return identity

    # -- loading ------------------------------------------------------------

    def load_public(self) -> ExecutorIdentity:
        """Load and validate the public identity from its stored bytes."""
        path = self.public_identity_path
        try:
            raw = path.read_bytes()
        except FileNotFoundError as error:
            raise NotFoundError(
                "this machine has no local signing identity yet; `techtree "
                "setup` creates one",
                code=LOCAL_IDENTITY_INVALID,
                details={"path": str(path)},
            ) from error

        try:
            return ExecutorIdentity.model_validate_json(raw)
        except PydanticValidationError as error:
            raise ValidationError(
                "the stored local identity is not a valid identity document: "
                f"{error.errors()[0]['msg']}",
                code=LOCAL_IDENTITY_INVALID,
                details={"path": str(path)},
            ) from error

    def load_private(self) -> Ed25519PrivateKey:
        """Load the private half into memory.

        Nothing about the material reaches the caller except a key object that
        can sign: no bytes, no encoding, and no detail in the errors raised
        when the file is unusable.
        """
        path = self.private_key_path
        try:
            raw = path.read_bytes()
        except FileNotFoundError as error:
            raise NotFoundError(
                "this machine has no local signing key yet; `techtree setup` "
                "creates one",
                code=LOCAL_IDENTITY_INVALID,
                details={"path": str(path)},
            ) from error

        if len(raw) != ED25519_PRIVATE_KEY_BYTES:
            raise ValidationError(
                "the stored local signing key is not an Ed25519 private key",
                code=LOCAL_IDENTITY_INVALID,
                details={"path": str(path), "length": len(raw)},
            )
        return load_private_key(raw)

    def verify_pair(self) -> bool:
        """Sign a fixed challenge in memory and check it against the public half.

        Returns ``False`` for two well-formed files that describe different
        keys. A file that cannot be read or parsed at all is a different
        problem and raises, because "your identity is missing" and "your
        identity does not match itself" call for different repairs.
        """
        private_key = self.load_private()
        identity = self.load_public()
        public_key = load_public_key(public_key_bytes(private_key))
        if public_key_to_base64(public_key) != identity.public_key:
            return False
        if _key_id_for(private_key) != identity.key_id:
            return False

        challenge = sha256_digest_bytes(IDENTITY_SELF_CHECK_CHALLENGE)
        signature = sign_digest(private_key, challenge, key_id=identity.key_id)
        return verify_signature(public_key, challenge, signature)


# ---------------------------------------------------------------------------
# Derivation
# ---------------------------------------------------------------------------


def _identity_for(
    private_key: Ed25519PrivateKey, *, created_at: datetime
) -> ExecutorIdentity:
    """Return the public identity describing one private key."""
    return ExecutorIdentity(
        kind="local_ed25519",
        key_id=_key_id_for(private_key),
        algorithm="ed25519",
        public_key=public_key_to_base64(private_key.public_key()),
        created_at=created_at,
    )


def _key_id_for(private_key: Ed25519PrivateKey) -> str:
    """Return the content-addressed identifier of a key's public half.

    Derived rather than assigned: a key identifier that was chosen could be
    reused for a different key, and every signature Techtree checks names the
    key by this string.
    """
    return sha256_digest_bytes(public_key_bytes(private_key))


def _utc_now() -> datetime:
    return datetime.now(UTC)
