"""The complete scoring policy for the conformance environment."""

from __future__ import annotations


def normalized_exact_match(reply: str, expected: str) -> float:
    """Return one only for the exact case-sensitive token, ignoring outer space."""
    return 1.0 if reply.strip() == expected else 0.0
