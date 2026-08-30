"""BranchCode v1: the deterministic procedure the reference taskset scores.

The procedure is specified in section 22.2 of the Climb v0.1 WP0-WP5
specification:

1. Normalize the input to lowercase ASCII.
2. Reject empty or unsupported text.
3. Map ``a=1`` through ``z=26``.
4. Multiply each letter value by its one-indexed position.
5. Sum the products.
6. Count the distinct characters.
7. Add seven times the distinct count.
8. Reduce modulo 97.
9. Format as ``BRANCH-XX``.

Every function here is pure and deterministic: no environment access, no
randomness, no clocks, no network, no I/O.
"""

from __future__ import annotations

__all__ = [
    "ALPHABET",
    "DISTINCT_WEIGHT",
    "MODULUS",
    "branch_code",
    "branch_code_number",
    "normalize_input",
]

ALPHABET = "abcdefghijklmnopqrstuvwxyz"
"""The only characters BranchCode v1 accepts after normalization."""

DISTINCT_WEIGHT = 7
"""Multiplier applied to the distinct-character count (step 7)."""

MODULUS = 97
"""Modulus applied to the weighted sum (step 8)."""

_LETTER_VALUES = {letter: index for index, letter in enumerate(ALPHABET, start=1)}


def normalize_input(value: str) -> str:
    """Strip, lowercase, and require ASCII ``a``-``z``.

    Surrounding whitespace is removed and the remaining text is lowercased.
    The result must be non-empty and contain only the twenty-six ASCII
    lowercase letters; anything else is unsupported input.

    >>> normalize_input("  Maple ")
    'maple'

    Args:
        value: Raw candidate input.

    Returns:
        The normalized lowercase ASCII form of ``value``.

    Raises:
        TypeError: If ``value`` is not a string.
        ValueError: If the normalized text is empty or holds any character
            outside ``a``-``z``.
    """
    if not isinstance(value, str):
        raise TypeError(
            f"BranchCode input must be a string, got {type(value).__name__}"
        )

    normalized = value.strip().lower()
    if not normalized:
        raise ValueError(
            "BranchCode input must not be empty after stripping whitespace"
        )

    unsupported = sorted(
        {character for character in normalized if character not in _LETTER_VALUES}
    )
    if unsupported:
        rendered = ", ".join(repr(character) for character in unsupported)
        raise ValueError(
            f"BranchCode input must be ASCII a-z only; "
            f"unsupported characters: {rendered}"
        )

    return normalized


def branch_code_number(value: str) -> int:
    """Return the BranchCode v1 number in ``0..96``.

    >>> branch_code_number("maple")
    74

    Args:
        value: Raw candidate input; normalized before scoring.

    Returns:
        The weighted positional sum plus seven times the distinct-character
        count, reduced modulo 97.

    Raises:
        TypeError: If ``value`` is not a string.
        ValueError: If ``value`` is empty or not ASCII ``a``-``z``.
    """
    normalized = normalize_input(value)

    weighted_sum = sum(
        _LETTER_VALUES[character] * position
        for position, character in enumerate(normalized, start=1)
    )
    distinct_count = len(set(normalized))

    return (weighted_sum + DISTINCT_WEIGHT * distinct_count) % MODULUS


def branch_code(value: str) -> str:
    """Return the ``BRANCH-XX`` token for ``value``.

    The numeric part is always two digits, zero-padded.

    >>> branch_code("birch")
    'BRANCH-64'
    >>> branch_code("acorn")
    'BRANCH-35'

    Args:
        value: Raw candidate input; normalized before scoring.

    Returns:
        The formatted ``BRANCH-XX`` token.

    Raises:
        TypeError: If ``value`` is not a string.
        ValueError: If ``value`` is empty or not ASCII ``a``-``z``.
    """
    return f"BRANCH-{branch_code_number(value):02d}"
