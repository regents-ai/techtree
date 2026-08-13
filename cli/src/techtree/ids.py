"""Prefixed local identifiers. Spec section 10.6.

An identifier looks like ``run_5b1c...`` — a namespace prefix, an underscore,
and 32 lowercase hexadecimal characters from a UUID4.

Identifiers are labels, not integrity values. Two objects with the same
identifier are not thereby the same object; only a digest says that. Nothing in
the protocol should ever compare identifiers where it means to compare content.
"""

from __future__ import annotations

import re
import uuid
from typing import Final

from techtree.errors import ValidationError

__all__ = [
    "ID_PREFIXES",
    "id_prefix",
    "new_id",
    "validate_id",
]

#: Every namespace WP0–WP5 issues identifiers for. The set is closed so that a
#: typo in a prefix fails at the point it is written rather than becoming a
#: silent new namespace.
ID_PREFIXES: Final[frozenset[str]] = frozenset(
    {
        "campaign",
        "climb",
        "draft",
        "run",
        "receipt",
        "uplift",
        "policy",
    }
)

_ID_PATTERN = re.compile(r"^(?P<prefix>[a-z][a-z0-9]*)_(?P<body>[0-9a-f]{32})$")


def _require_known_prefix(prefix: str) -> str:
    if prefix not in ID_PREFIXES:
        raise ValidationError(
            f"unknown identifier prefix {prefix!r}",
            details={"prefix": prefix, "known": ", ".join(sorted(ID_PREFIXES))},
        )
    return prefix


def new_id(prefix: str) -> str:
    """Create a new prefixed UUID4 hexadecimal identifier."""
    _require_known_prefix(prefix)
    return f"{prefix}_{uuid.uuid4().hex}"


def validate_id(value: str, expected_prefix: str | None = None) -> str:
    """Validate syntax and optionally require one prefix."""
    match = _ID_PATTERN.fullmatch(value)
    if match is None:
        raise ValidationError(
            "identifier must be <prefix>_<32 lowercase hexadecimal characters>",
            details={"value": value},
        )

    prefix = match.group("prefix")
    _require_known_prefix(prefix)

    if expected_prefix is not None:
        _require_known_prefix(expected_prefix)
        if prefix != expected_prefix:
            raise ValidationError(
                f"expected a {expected_prefix} identifier, got a {prefix} identifier",
                details={"value": value, "expected_prefix": expected_prefix},
            )

    return value


def id_prefix(value: str) -> str:
    """Return the prefix from a valid ID."""
    validated = validate_id(value)
    return validated.split("_", 1)[0]
