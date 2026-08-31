"""Canonical serialization, digests, and the Verifiers hash boundary.

Spec sections 10.7 and 2.8.

This is the only place in Techtree that turns an object into bytes for hashing.
Every digest in the protocol is the SHA-256 of the RFC 8785 canonical JSON form
produced here, which is what makes two independently built copies of the same
object agree on one digest.

RFC 8785 fixes key ordering, string escaping, and number formatting, so the
remaining job is converting Python values into the JSON data model without ever
introducing an ambiguity of our own:

* Aware datetimes become UTC instants spelled with ``Z``. Naive datetimes are
  rejected, because "9am" is not an instant and two readers would disagree
  about which bytes it should produce.
* ``NaN`` and the infinities are rejected. JSON cannot spell them.
* Types with more than one reasonable JSON spelling — ``bytes``, ``set``,
  arbitrary objects — are rejected rather than guessed at.

The Verifiers boundary is here too, and deliberately narrow.
:func:`normalize_verifiers_task_hash` accepts only what Verifiers actually
emits: a bare 64-character lowercase hexadecimal string. It never accepts an
already-prefixed Techtree digest, because silently passing those through would
turn the boundary into a place where an unvalidated string can enter the
protocol wearing a valid-looking digest. Prefixed digests go through
:func:`validate_digest`.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from pathlib import PurePath
from typing import Final

import rfc8785
from pydantic import BaseModel

from techtree.constants import DIGEST_PREFIX
from techtree.errors import ValidationError
from techtree.models.base import DIGEST_PATTERN, Digest, JsonValue

__all__ = [
    "VERIFIERS_TASK_HASH_LENGTH",
    "canonical_json_bytes",
    "canonical_json_text",
    "digest_object",
    "normalize_verifiers_task_hash",
    "sha256_digest_bytes",
    "to_json_value",
    "validate_digest",
    "verify_bytes_digest",
    "verify_object_digest",
]

#: Verifiers emits raw SHA-256 hexadecimal, so a task hash is always this long.
VERIFIERS_TASK_HASH_LENGTH: Final = 64

_DIGEST_RE = re.compile(DIGEST_PATTERN)
_RAW_TASK_HASH_RE = re.compile(rf"^[0-9a-f]{{{VERIFIERS_TASK_HASH_LENGTH}}}$")


# ---------------------------------------------------------------------------
# Conversion to the JSON data model
# ---------------------------------------------------------------------------


def _unsupported(value: object, reason: str) -> ValidationError:
    return ValidationError(
        f"cannot canonicalize {type(value).__name__}: {reason}",
        details={"python_type": type(value).__name__},
    )


def _float_to_json(value: float) -> float:
    if math.isnan(value) or math.isinf(value):
        raise ValidationError(
            "cannot canonicalize a non-finite number",
            details={"value": repr(value)},
        )
    return value


def _datetime_to_json(value: datetime) -> str:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValidationError(
            "cannot canonicalize a naive datetime; it does not name an instant",
            details={"value": value.isoformat()},
        )
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _model_to_json(value: BaseModel) -> dict[str, JsonValue]:
    # Fields are read straight off the instance rather than through
    # ``model_dump`` so that every leaf passes through the rules in this module
    # instead of Pydantic's own serializers.
    return {
        name: to_json_value(getattr(value, name)) for name in type(value).model_fields
    }


def to_json_value(value: object) -> JsonValue:
    """Convert supported values to the JSON data model.

    Supports Pydantic models, enums, aware datetimes, paths, decimals,
    mappings, sequences, and JSON scalars. Everything else is rejected.
    """
    if value is None or isinstance(value, str):
        return value
    # ``bool`` is a subclass of ``int``; it has to be settled first.
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return _float_to_json(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValidationError(
                "cannot canonicalize a non-finite decimal",
                details={"value": str(value)},
            )
        return float(value)
    if isinstance(value, datetime):
        return _datetime_to_json(value)
    if isinstance(value, Enum):
        return to_json_value(value.value)
    if isinstance(value, PurePath):
        return value.as_posix()
    if isinstance(value, BaseModel):
        return _model_to_json(value)
    if isinstance(value, Mapping):
        converted: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise _unsupported(key, "mapping keys must be strings")
            converted[key] = to_json_value(item)
        return converted
    if isinstance(value, bytes | bytearray | memoryview):
        raise _unsupported(value, "encode binary data as base64 text first")
    if isinstance(value, set | frozenset):
        raise _unsupported(value, "sets have no defined order; use a list")
    if isinstance(value, Sequence):
        return [to_json_value(item) for item in value]
    raise _unsupported(value, "no canonical JSON representation is defined")


# ---------------------------------------------------------------------------
# Canonical bytes
# ---------------------------------------------------------------------------


def canonical_json_bytes(value: object) -> bytes:
    """Serialize a JSON value using RFC 8785 and return UTF-8 bytes."""
    json_value = to_json_value(value)
    try:
        return rfc8785.dumps(json_value)
    except rfc8785.CanonicalizationError as error:
        raise ValidationError(
            f"value cannot be canonicalized: {error}",
        ) from error


def canonical_json_text(value: object) -> str:
    """Return canonical JSON text."""
    return canonical_json_bytes(value).decode("utf-8")


# ---------------------------------------------------------------------------
# Digests
# ---------------------------------------------------------------------------


def sha256_digest_bytes(data: bytes) -> Digest:
    """Return ``sha256:<hex>`` for raw bytes."""
    return f"{DIGEST_PREFIX}{hashlib.sha256(data).hexdigest()}"


def digest_object(value: object) -> Digest:
    """Canonicalize a protocol object and return its digest."""
    return sha256_digest_bytes(canonical_json_bytes(value))


def validate_digest(value: str) -> Digest:
    """Validate an already-prefixed Techtree digest and return it unchanged."""
    if _DIGEST_RE.fullmatch(value) is None:
        raise ValidationError(
            "digest must be sha256: followed by 64 lowercase hexadecimal characters",
            details={"value": value},
        )
    return value


def verify_bytes_digest(data: bytes, expected: Digest) -> bool:
    """Use constant-time comparison for raw byte digest."""
    return hmac.compare_digest(sha256_digest_bytes(data), validate_digest(expected))


def verify_object_digest(value: object, expected: Digest) -> bool:
    """Use constant-time comparison for canonical object digest."""
    return hmac.compare_digest(digest_object(value), validate_digest(expected))


# ---------------------------------------------------------------------------
# Verifiers boundary
# ---------------------------------------------------------------------------


def normalize_verifiers_task_hash(raw: str) -> Digest:
    """Convert a Verifiers task hash to Techtree digest representation.

    Accepts exactly one shape: 64 lowercase hexadecimal characters, with no
    prefix, no surrounding whitespace, and no uppercase.
    """
    if raw.startswith(DIGEST_PREFIX):
        raise ValidationError(
            "Verifiers task hashes are unprefixed; "
            "use validate_digest for Techtree digests",
            details={"value": raw},
        )
    if len(raw) != VERIFIERS_TASK_HASH_LENGTH:
        raise ValidationError(
            "Verifiers task hash must be exactly "
            f"{VERIFIERS_TASK_HASH_LENGTH} characters",
            details={"length": len(raw)},
        )
    if _RAW_TASK_HASH_RE.fullmatch(raw) is None:
        raise ValidationError(
            "Verifiers task hash must be lowercase hexadecimal",
            details={"value": raw},
        )
    return f"{DIGEST_PREFIX}{raw}"
