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
    "SKILL_GITHUB_URL_INVALID",
    "canonical_contributor_address",
    "canonical_skill_github_url",
    "eip55_checksum",
]

#: Stable error code for "that is not an address anybody could have meant".
CONTRIBUTOR_ADDRESS_INVALID: Final = "contributor_address_invalid"

#: Stable error code for an optional public Skill repository URL that is not a
#: canonical GitHub repository address.
SKILL_GITHUB_URL_INVALID: Final = "skill_github_url_invalid"

_ADDRESS_PATTERN: Final = re.compile(r"\A0x[0-9a-fA-F]{40}\Z")

# GitHub user and organization names are at most 39 characters and contain
# alphanumerics or dashes (never at either edge). Repository names are at most
# 100 characters and may also contain dots and underscores. The URL is
# deliberately narrower than what a browser might accept: one spelling, no
# redirects, no .git suffix, and no extra path or URL components.
_GITHUB_OWNER_PATTERN: Final = re.compile(
    r"\A[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z"
)
_GITHUB_REPOSITORY_PATTERN: Final = re.compile(
    r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z"
)

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


def canonical_skill_github_url(typed: str) -> str:
    """Return a canonical GitHub repository URL, or refuse it.

    This is descriptive metadata, not proof that a repository exists or that
    its publisher controls it. Keeping the accepted form strict prevents a
    public link from silently becoming a redirect, a different host, or a
    clone URL with credentials and query data attached.
    """
    from urllib.parse import urlsplit

    if typed != typed.strip():
        raise ValidationError(
            "a Skill GitHub URL has no surrounding whitespace",
            code=SKILL_GITHUB_URL_INVALID,
            details={"reason": "whitespace"},
        )

    try:
        parts = urlsplit(typed)
        # Accessing ``port`` validates a malformed explicit port and may raise
        # ValueError even when the rest of the URL can be split.
        port = parts.port
    except ValueError:
        parts = None
        port = None

    path_parts = parts.path.split("/") if parts is not None else []
    if (
        parts is None
        or parts.scheme != "https"
        or parts.netloc != "github.com"
        or parts.username is not None
        or parts.password is not None
        or port is not None
        or parts.query
        or parts.fragment
        or "?" in typed
        or "#" in typed
        or len(path_parts) != 3
        or path_parts[0]
        or not _GITHUB_OWNER_PATTERN.fullmatch(path_parts[1])
        or not _GITHUB_REPOSITORY_PATTERN.fullmatch(path_parts[2])
        or path_parts[2].lower().endswith(".git")
    ):
        raise ValidationError(
            "a Skill GitHub URL must be exactly https://github.com/owner/repo, "
            "with no .git suffix, query, fragment, credentials, or extra path",
            code=SKILL_GITHUB_URL_INVALID,
            details={"reason": "shape"},
        )
    return typed


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
