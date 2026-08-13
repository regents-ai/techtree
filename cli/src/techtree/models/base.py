"""Shared protocol types, base classes, and envelopes. Spec section 11.2.

Two base classes exist and the distinction matters:

``ProtocolModel``
    Frozen, strict, extra-forbidden. Everything that is hashed, digested, or
    signed derives from it. Immutability is what makes a digest meaningful:
    once an object exists, its canonical bytes cannot drift underneath the
    digest that was taken of them.

``StateModel``
    Strict, extra-forbidden, assignment-validating, and mutable. Local state
    projections that the CLI edits in place derive from it.

Both are *strict*, which in Pydantic v2 is mode-dependent. Python-mode
validation performs no coercion at all, so a protocol object built in code must
be handed real ``datetime`` objects rather than strings. JSON-mode validation
still accepts the single JSON spelling of a type, so stored protocol documents
are loaded with ``model_validate_json`` on the raw bytes, never by decoding to
``dict`` first and calling ``model_validate``. Loading from bytes is also what
lets a caller digest exactly what it parsed.

This module deliberately depends on nothing in the package except
:mod:`techtree.constants`, so it sits underneath canonicalization, crypto, and
every model file.
"""

from __future__ import annotations

import base64
import binascii
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
)

from techtree.constants import DIGEST_PREFIX

__all__ = [
    "DIGEST_PATTERN",
    "ArtifactRef",
    "Base64String",
    "Digest",
    "JsonScalar",
    "JsonValue",
    "NonEmptyString",
    "ObjectEnvelope",
    "ProtocolModel",
    "PublicKeyRef",
    "SignatureEnvelope",
    "StateModel",
    "UtcDateTime",
]


# ---------------------------------------------------------------------------
# JSON value types
# ---------------------------------------------------------------------------

type JsonScalar = str | int | float | bool | None
"""Any value JSON can hold without nesting."""

type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
"""Any value JSON can hold, including arrays and objects."""


# ---------------------------------------------------------------------------
# Constrained scalars
# ---------------------------------------------------------------------------

#: A Techtree digest is the prefix plus 64 lowercase hexadecimal characters.
#: Uppercase hexadecimal is rejected so that one digest string has exactly one
#: spelling and byte comparison is meaningful.
DIGEST_PATTERN = rf"^{DIGEST_PREFIX}[0-9a-f]{{64}}$"

type Digest = Annotated[str, StringConstraints(pattern=DIGEST_PATTERN)]


def _require_utc(value: datetime) -> datetime:
    """Reject naive datetimes and normalize aware ones to UTC."""
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


type UtcDateTime = Annotated[datetime, AfterValidator(_require_utc)]


def _require_visible_characters(value: str) -> str:
    """Reject strings that are empty or made only of whitespace."""
    if not value.strip():
        raise ValueError("value must contain at least one non-whitespace character")
    return value


type NonEmptyString = Annotated[
    str,
    StringConstraints(min_length=1),
    AfterValidator(_require_visible_characters),
]


def _require_base64(value: str) -> str:
    """Reject anything that is not strict, canonical base64."""
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("value must be base64") from error
    # ``b64decode`` tolerates several spellings of the same bytes. Re-encoding
    # and comparing pins the single canonical spelling.
    if base64.b64encode(decoded).decode("ascii") != value:
        raise ValueError("value must be canonical base64")
    return value


type Base64String = Annotated[
    str,
    StringConstraints(min_length=1),
    AfterValidator(_require_base64),
]


# ---------------------------------------------------------------------------
# Base classes
# ---------------------------------------------------------------------------


class ProtocolModel(BaseModel):
    """Frozen, strict, extra-forbidden hashed or signed object."""

    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        validate_default=True,
        populate_by_name=False,
    )


class StateModel(BaseModel):
    """Strict mutable local-state projection."""

    model_config = ConfigDict(
        frozen=False,
        strict=True,
        extra="forbid",
        validate_default=True,
        validate_assignment=True,
        populate_by_name=False,
    )


# ---------------------------------------------------------------------------
# Shared models
# ---------------------------------------------------------------------------


class ArtifactRef(ProtocolModel):
    """A content-addressed pointer to a stored byte stream."""

    digest: Digest
    media_type: NonEmptyString
    size: Annotated[int, Field(gt=0)]
    relative_path: str | None = None


class PublicKeyRef(ProtocolModel):
    """An Ed25519 public key in the form protocol documents carry it."""

    algorithm: Literal["ed25519"]
    key_id: NonEmptyString
    public_key: Base64String


class SignatureEnvelope(ProtocolModel):
    """A detached Ed25519 signature over a digest string."""

    algorithm: Literal["ed25519"]
    key_id: NonEmptyString
    signature: Base64String


class ObjectEnvelope[T: BaseModel](ProtocolModel):
    """A payload together with its digest and an optional signature.

    ``payload_digest`` is carried, never recomputed during validation. A model
    that silently recomputed it could not detect the one thing the field exists
    to detect: a payload that no longer matches the digest it was stored under.
    Services verify the pair explicitly with
    :func:`techtree.canonical.verify_object_digest`.
    """

    payload: T
    payload_digest: Digest
    signature: SignatureEnvelope | None = None
