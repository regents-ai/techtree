"""RFC 6901 JSON Pointer syntax, escaping, and containment.

Two independent parts of the protocol name places inside a document with a
JSON Pointer: the v0.1 mutation contract, which permits a candidate to differ
at exactly one root, and the v0.2 configuration compatibility policy, which
declares where two Campaigns may drift. Both need the same three answers — how
a reference token is spelled, how the tokens are joined, and what it means for
one pointer to lie inside another — and both have to give the same answer, or
a path allowed by one would be read differently by the other.

So the answers live here, underneath both. This module depends on nothing in
the package, which is what lets a protocol model and a comparison function use
it without either importing the other.

Containment is the part worth stating carefully.
``/agents/subject/harness/skills_extra`` is not inside
``/agents/subject/harness/skills``: containment is a boundary between reference
tokens, not a string prefix. A prefix test written with ``startswith`` alone
would admit exactly the field an attacker would add.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "JSON_POINTER_PATTERN",
    "POINTER_SEPARATOR",
    "json_pointer_escape",
    "pointer_is_within",
]

#: RFC 6901 separates reference tokens with a solidus and gives it no other
#: meaning, which is why a token containing one has to be escaped.
POINTER_SEPARATOR: Final = "/"

#: RFC 6901 syntax for a pointer naming at least one reference token. Inside a
#: token the solidus and the tilde may appear only as ``~1`` and ``~0``.
#:
#: The empty pointer, which RFC 6901 gives to the whole document, is
#: deliberately outside the pattern. A policy path that named the whole
#: document would declare an entire Campaign either fixed or free to drift,
#: which states nothing a comparison could act on.
JSON_POINTER_PATTERN: Final = r"^(?:/(?:[^/~]|~[01])*)+$"


def json_pointer_escape(segment: str) -> str:
    """Escape ``~`` as ``~0`` and ``/`` as ``~1``.

    In that order: escaping the solidus first would turn its replacement's
    tilde into a second escape.
    """
    return segment.replace("~", "~0").replace(POINTER_SEPARATOR, "~1")


def pointer_is_within(pointer: str, allowed_root: str) -> bool:
    """Return whether a pointer is the allowed root or descends from it.

    ``/agents/subject/harness/skills_extra`` is not within
    ``/agents/subject/harness/skills``: containment is a boundary between
    reference tokens, not a string prefix.
    """
    return pointer == allowed_root or pointer.startswith(
        f"{allowed_root}{POINTER_SEPARATOR}"
    )
