"""The frozen proving dataset for the BranchCode v1 reference taskset.

``PROVING_INPUTS`` is a literal, hand-written tuple. It is never generated,
sampled, shuffled, or extended at runtime: the ordered membership of this
tuple is what the Campaign membership commitment pins, so any change to the
contents *or* the order is a breaking change to every existing commitment.

Ordering rule (stable and auditable): by length ascending, then
alphabetically within each length.

None of these strings ever appears in a documentation example, a docstring,
or a candidate skill; the worked examples are reserved separately in
``DOCUMENTATION_EXAMPLES`` so the proving inputs stay unseen.
"""

from __future__ import annotations

from procedure_transfer_v1.algorithm import normalize_input

__all__ = [
    "DOCUMENTATION_EXAMPLES",
    "MAX_INPUT_LENGTH",
    "MIN_INPUT_LENGTH",
    "MIN_PROVING_INPUTS",
    "PROVING_INPUTS",
    "proving_inputs",
    "validate_dataset",
]

MIN_PROVING_INPUTS = 32
"""Specification floor on the size of the frozen dataset."""

MIN_INPUT_LENGTH = 4
"""Shortest permitted proving input."""

MAX_INPUT_LENGTH = 12
"""Longest permitted proving input."""

DOCUMENTATION_EXAMPLES = frozenset({"acorn", "birch", "maple"})
"""Worked-example inputs reserved for documentation and never proven against."""

PROVING_INPUTS: tuple[str, ...] = (
    # length 5
    "alder",
    "aspen",
    "beech",
    "cedar",
    "hazel",
    "larch",
    "rowan",
    # length 6
    "pinyon",
    "poplar",
    "spruce",
    "willow",
    # length 7
    "cypress",
    "dogwood",
    "hemlock",
    "juniper",
    "sequoia",
    # length 8
    "chestnut",
    "hornbeam",
    "ironwood",
    "laburnum",
    "magnolia",
    "mangrove",
    "mulberry",
    "sycamore",
    "tamarack",
    # length 9
    "buckthorn",
    "jacaranda",
    "persimmon",
    "sassafras",
    "whitebeam",
    # length 10
    "blackthorn",
    "cottonwood",
    "elderberry",
    "eucalyptus",
    "sandalwood",
    # length 11
    "bristlecone",
)
"""The frozen, ordered proving inputs. Do not reorder, add, or remove."""


def proving_inputs() -> tuple[str, ...]:
    """Return the immutable, ordered proving inputs.

    Returns:
        ``PROVING_INPUTS`` itself; tuples are immutable, so callers cannot
        disturb the committed order.
    """
    return PROVING_INPUTS


def validate_dataset() -> None:
    """Check every invariant the frozen dataset must satisfy.

    Verifies the dataset size floor, uniqueness, the ASCII ``a``-``z``
    charset, the length bounds, the length-then-alphabetical order, and that
    no proving input collides with a reserved documentation example.

    Raises:
        ValueError: On the first invariant that fails.
    """
    count = len(PROVING_INPUTS)
    if count < MIN_PROVING_INPUTS:
        raise ValueError(
            f"PROVING_INPUTS must hold at least {MIN_PROVING_INPUTS} entries, "
            f"found {count}"
        )

    seen: set[str] = set()
    for entry in PROVING_INPUTS:
        if entry in seen:
            raise ValueError(f"PROVING_INPUTS contains a duplicate entry: {entry!r}")
        seen.add(entry)

        if normalize_input(entry) != entry:
            raise ValueError(
                "PROVING_INPUTS entry must already be normalized lowercase a-z: "
                f"{entry!r}"
            )

        if not MIN_INPUT_LENGTH <= len(entry) <= MAX_INPUT_LENGTH:
            raise ValueError(
                f"PROVING_INPUTS entry must be {MIN_INPUT_LENGTH}-{MAX_INPUT_LENGTH} "
                f"characters, found {len(entry)}: {entry!r}"
            )

        if entry in DOCUMENTATION_EXAMPLES:
            raise ValueError(
                f"PROVING_INPUTS entry overlaps a documentation example: {entry!r}"
            )

    ordered = tuple(sorted(PROVING_INPUTS, key=lambda entry: (len(entry), entry)))
    if ordered != PROVING_INPUTS:
        raise ValueError(
            "PROVING_INPUTS must be ordered by length ascending, then alphabetically"
        )
