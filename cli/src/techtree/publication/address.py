"""Checking an EVM address somebody typed. Decisions document 0038.

An address is optional, it is volunteered, and it is unverifiable. Nobody has
proved control of the account, and this module cannot change that — what it can
do is refuse the two mistakes that are cheap to catch and expensive to make.

*The shape.* ``0x`` and exactly forty hexadecimal characters, after the
surrounding whitespace a paste brings with it has been trimmed off. Anything
else is a typo or a different kind of identifier, and either way it is not what
was asked for.

*The checksum, where there is one.* EIP-55 hides a checksum in the letter case
of an address: the hexadecimal is case-insensitive, so the case of each letter
is free to carry four bits of a Keccak-256 digest of the address itself. An
address written in one case carries no checksum and there is nothing to check.
An address written in mixed case does carry one, and checking it costs a hash
and catches a single mistyped character — which is the difference between a
recognisable contributor and an address that belongs to nobody and always will,
because there is no undo and no support desk.

What travels is the lowercase spelling. It is the same address, it is the form
the checksum is computed from, and one canonical form is what makes an address
usable as a key.

Nothing here stores anything. The caller sends the canonical form and keeps no
copy: an address is a detail somebody volunteered about themselves, not
evidence, and it belongs in no journal, no proof bundle and no log.
"""

from __future__ import annotations

import re
from typing import Final

from techtree.errors import ValidationError
from techtree.publication.keccak import keccak256

__all__ = [
    "CONTRIBUTOR_ADDRESS_INVALID",
    "canonical_contributor_address",
    "eip55_checksum",
]

#: Stable error code for "that is not an address anybody could have meant".
CONTRIBUTOR_ADDRESS_INVALID: Final = "contributor_address_invalid"

_ADDRESS_PATTERN: Final = re.compile(r"\A0x[0-9a-fA-F]{40}\Z")

#: A digest nibble of eight or more uppercases the hexadecimal character it
#: sits beside. EIP-55, in the one sentence it amounts to.
_UPPERCASE_THRESHOLD: Final = 8


def canonical_contributor_address(typed: str) -> str:
    """Return the lowercase form of a typed address, or refuse it.

    Refusals carry the reason rather than a generic "invalid": somebody who has
    pasted the wrong forty characters and somebody who has mistyped one of the
    right forty need to be told different things.
    """
    trimmed = typed.strip()
    if not _ADDRESS_PATTERN.match(trimmed):
        raise ValidationError(
            "an address is 0x followed by exactly 40 hexadecimal characters, "
            f"and this one is not: {_shape_of(trimmed)}",
            code=CONTRIBUTOR_ADDRESS_INVALID,
            details={"reason": "shape"},
        )

    body = trimmed[2:]
    if body == body.lower() or body == body.upper():
        # One case throughout carries no checksum, so there is nothing here to
        # be right or wrong about.
        return trimmed.lower()

    if trimmed != eip55_checksum(trimmed):
        raise ValidationError(
            "this address is written in mixed case, which carries a checksum, "
            "and the checksum does not match: one character of it is wrong. "
            "An address nobody controls cannot be undone, so it is refused "
            "rather than sent",
            code=CONTRIBUTOR_ADDRESS_INVALID,
            details={"reason": "checksum"},
        )
    return trimmed.lower()


def eip55_checksum(address: str) -> str:
    """Return the mixed-case EIP-55 spelling of a well-formed address."""
    body = address[2:].lower()
    digest = keccak256(body.encode("ascii")).hex()
    return "0x" + "".join(
        character.upper()
        if int(digest[position], 16) >= _UPPERCASE_THRESHOLD
        else character
        for position, character in enumerate(body)
    )


def _shape_of(typed: str) -> str:
    """Describe what was typed without repeating it back.

    A refusal that echoed the string would put it in the envelope, in the
    terminal's scrollback, and in whatever a host agent keeps — which is
    exactly where a volunteered address must not end up. The length and whether
    the prefix was there are enough for somebody to see what they did.
    """
    prefix = "starts with 0x" if typed[:2].lower() == "0x" else "no 0x prefix"
    return f"{prefix}, {len(typed)} characters"
