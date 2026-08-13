"""Table-driven tests for BranchCode v1 and the frozen proving dataset.

These tests cover only the pure half of the reference taskset package
(``algorithm.py`` and ``dataset.py``). Nothing here imports Verifiers, so the
suite runs with pytest alone.

The reference package is not installed into the main project environment; it
ships as a standalone Hatchling package inside the managed engine bundle, so
it is imported from its source directory. Its ``__init__`` re-exports the
Verifiers Taskset, and the pinned Verifiers build exists only in the managed
engine environment, so the two pure modules are imported without executing
that ``__init__``. The Taskset itself is covered by the preflight suite, which
runs inside an environment that does hold the pin.

Every non-ASCII rejection case is written as an escape sequence on purpose:
the point of those cases is the exact code point, and an escape keeps this
file pure ASCII so no editor, terminal, or copy-paste can silently normalize
the character under test.
"""

from __future__ import annotations

import doctest
import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

_PACKAGE_NAME = "procedure_transfer_v1"
_PACKAGE_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "techtree"
    / "resources"
    / "engines"
    / "default"
    / "packages"
    / "procedure-transfer-v1"
    / _PACKAGE_NAME
)


def _load_pure_module(name: str) -> ModuleType:
    """Import one pure module of the reference package on its own.

    Binds a bare parent package first, so ``dataset``'s absolute import of
    ``algorithm`` resolves without running the real ``__init__``, which pulls
    in Verifiers.

    Args:
        name: Module name inside the package, such as ``"algorithm"``.

    Returns:
        The executed module.
    """
    if _PACKAGE_NAME not in sys.modules:
        sys.modules[_PACKAGE_NAME] = ModuleType(_PACKAGE_NAME)

    qualified = f"{_PACKAGE_NAME}.{name}"
    cached = sys.modules.get(qualified)
    if cached is not None:
        return cached

    spec = importlib.util.spec_from_file_location(
        qualified, _PACKAGE_DIR / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None, qualified
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
    return module


algorithm = _load_pure_module("algorithm")
dataset = _load_pure_module("dataset")

BRANCH_TOKEN = re.compile(r"^BRANCH-\d{2}$")


# ---------------------------------------------------------------------------
# Expected values
#
# Every expected value below was computed by hand from section 22.2 and
# independently re-derived with a second implementation. Three worked
# examples, in full:
#
#   maple -> m13*1 + a1*2 + p16*3 + l12*4 + e5*5 = 13+2+48+48+25 = 136
#            distinct 5 -> 136 + 35 = 171 -> 171 mod 97 = 74 -> BRANCH-74
#   cedar -> c3*1 + e5*2 + d4*3 + a1*4 + r18*5  = 3+10+12+4+90  = 119
#            distinct 5 -> 119 + 35 = 154 -> 154 mod 97 = 57 -> BRANCH-57
#   bgt   -> b2*1 + g7*2 + t20*3                = 2+14+60       = 76
#            distinct 3 -> 76 + 21 = 97  -> 97 mod 97  = 0  -> BRANCH-00
# ---------------------------------------------------------------------------

SINGLE_LETTER_CASES: tuple[tuple[str, int, str], ...] = (
    # value = letter_value * 1 + 7 * 1 distinct character
    ("a", 8, "BRANCH-08"),
    ("b", 9, "BRANCH-09"),
    ("c", 10, "BRANCH-10"),
    ("d", 11, "BRANCH-11"),
    ("e", 12, "BRANCH-12"),
    ("f", 13, "BRANCH-13"),
    ("g", 14, "BRANCH-14"),
    ("h", 15, "BRANCH-15"),
    ("i", 16, "BRANCH-16"),
    ("j", 17, "BRANCH-17"),
    ("k", 18, "BRANCH-18"),
    ("l", 19, "BRANCH-19"),
    ("m", 20, "BRANCH-20"),
    ("n", 21, "BRANCH-21"),
    ("o", 22, "BRANCH-22"),
    ("p", 23, "BRANCH-23"),
    ("q", 24, "BRANCH-24"),
    ("r", 25, "BRANCH-25"),
    ("s", 26, "BRANCH-26"),
    ("t", 27, "BRANCH-27"),
    ("u", 28, "BRANCH-28"),
    ("v", 29, "BRANCH-29"),
    ("w", 30, "BRANCH-30"),
    ("x", 31, "BRANCH-31"),
    ("y", 32, "BRANCH-32"),
    ("z", 33, "BRANCH-33"),
)

HAND_COMPUTED_CASES: tuple[tuple[str, int, str], ...] = (
    ("aa", 10, "BRANCH-10"),  # 1 + 2 = 3, distinct 1 -> +7 = 10
    ("ab", 19, "BRANCH-19"),  # 1 + 4 = 5, distinct 2 -> +14 = 19
    ("ba", 18, "BRANCH-18"),  # 2 + 2 = 4, distinct 2 -> +14 = 18
    ("zz", 85, "BRANCH-85"),  # 26 + 52 = 78, distinct 1 -> +7 = 85
    ("zzz", 66, "BRANCH-66"),  # 26+52+78 = 156, +7 = 163, mod 97 = 66
    ("bgt", 0, "BRANCH-00"),  # 2+14+60 = 76, +21 = 97, mod 97 = 0
    ("fern", 57, "BRANCH-57"),  # 6+10+54+56 = 126, +28 = 154, mod 97 = 57
    ("maple", 74, "BRANCH-74"),  # 13+2+48+48+25 = 136, +35 = 171, mod 97 = 74
    ("birch", 64, "BRANCH-64"),  # 2+18+54+12+40 = 126, +35 = 161, mod 97 = 64
    ("acorn", 35, "BRANCH-35"),  # 1+6+45+72+70 = 194, +35 = 229, mod 97 = 35
    # whole alphabet: sum of k*k for k in 1..26 = 6201, +182 = 6383, mod 97 = 78
    ("abcdefghijklmnopqrstuvwxyz", 78, "BRANCH-78"),
)

DATASET_EXPECTED: tuple[tuple[str, str], ...] = (
    ("alder", "BRANCH-85"),
    ("aspen", "BRANCH-18"),
    ("beech", "BRANCH-10"),
    ("cedar", "BRANCH-57"),
    ("hazel", "BRANCH-09"),
    ("larch", "BRANCH-58"),
    ("rowan", "BRANCH-32"),
    ("pinyon", "BRANCH-79"),
    ("poplar", "BRANCH-96"),
    ("spruce", "BRANCH-82"),
    ("willow", "BRANCH-75"),
    ("cypress", "BRANCH-02"),
    ("dogwood", "BRANCH-77"),
    ("hemlock", "BRANCH-33"),
    ("juniper", "BRANCH-27"),
    ("sequoia", "BRANCH-58"),
    ("chestnut", "BRANCH-68"),
    ("hornbeam", "BRANCH-64"),
    ("ironwood", "BRANCH-45"),
    ("laburnum", "BRANCH-93"),
    ("magnolia", "BRANCH-68"),
    ("mangrove", "BRANCH-30"),
    ("mulberry", "BRANCH-25"),
    ("sycamore", "BRANCH-71"),
    ("tamarack", "BRANCH-21"),
    ("buckthorn", "BRANCH-04"),
    ("jacaranda", "BRANCH-11"),
    ("persimmon", "BRANCH-90"),
    ("sassafras", "BRANCH-43"),
    ("whitebeam", "BRANCH-11"),
    ("blackthorn", "BRANCH-85"),
    ("cottonwood", "BRANCH-54"),
    ("elderberry", "BRANCH-20"),
    ("eucalyptus", "BRANCH-14"),
    ("sandalwood", "BRANCH-79"),
    ("bristlecone", "BRANCH-93"),
)

FROZEN_ORDER: tuple[str, ...] = tuple(entry for entry, _ in DATASET_EXPECTED)


# ---------------------------------------------------------------------------
# normalize_input
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("maple", "maple"),
        ("MAPLE", "maple"),
        ("MaPlE", "maple"),
        ("  maple", "maple"),
        ("maple  ", "maple"),
        ("   maple   ", "maple"),
        ("\tmaple\n", "maple"),
        ("\r\n  BIRCH \t ", "birch"),
        ("\x0bacorn\x0c", "acorn"),
        ("Z", "z"),
    ],
)
def test_normalize_input_strips_and_lowercases(raw: str, expected: str) -> None:
    assert algorithm.normalize_input(raw) == expected


@pytest.mark.parametrize("raw", ["  Maple ", "BIRCH", "acorn"])
def test_normalize_input_is_idempotent(raw: str) -> None:
    once = algorithm.normalize_input(raw)
    assert algorithm.normalize_input(once) == once


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("", "empty"),
        (" ", "single space"),
        ("     ", "spaces only"),
        ("\t", "tab only"),
        ("\n", "newline only"),
        ("\t \r\n ", "mixed whitespace only"),
        ("\u00a0", "no-break space only"),
        ("maple oak", "internal space"),
        ("maple\toak", "internal tab"),
        ("maple\noak", "internal newline"),
        ("black-thorn", "hyphen"),
        ("black_thorn", "underscore"),
        ("maple.", "period"),
        ("maple!", "punctuation"),
        ("m4ple", "embedded digit"),
        ("12345", "digits only"),
        ("maple1", "trailing digit"),
        ("1maple", "leading digit"),
        ("caf\u00e9", "latin-1 accent"),
        ("na\u00efve", "latin-1 diaeresis"),
        ("\u00c5SPEN", "latin-1 uppercase"),
        ("map\u0142e", "latin extended"),
        ("\u043c\u0430ple", "cyrillic homoglyph"),
        ("\u65e5\u672c", "cjk"),
        ("\U0001f332", "emoji"),
        ("\uff4d\uff41\uff50\uff4c\uff45", "fullwidth latin"),
        ("maple\u00a0oak", "internal no-break space"),
        ("maple\u200boak", "internal zero-width space"),
        ("\u200bmaple", "leading zero-width space"),
        ("maple\ufe0f", "variation selector"),
    ],
)
def test_normalize_input_rejects_unsupported_text(raw: str, reason: str) -> None:
    assert reason
    with pytest.raises(ValueError):
        algorithm.normalize_input(raw)


@pytest.mark.parametrize("raw", ["", "   ", "\n\t", "\u00a0"])
def test_normalize_input_empty_message_mentions_empty(raw: str) -> None:
    with pytest.raises(ValueError, match="empty"):
        algorithm.normalize_input(raw)


@pytest.mark.parametrize(
    "raw", ["m4ple", "caf\u00e9", "maple oak", "black-thorn", "\U0001f332"]
)
def test_normalize_input_charset_message_mentions_charset(raw: str) -> None:
    with pytest.raises(ValueError, match="a-z"):
        algorithm.normalize_input(raw)


@pytest.mark.parametrize(
    "raw",
    [None, 42, 3.5, b"maple", bytearray(b"maple"), ["maple"], ("maple",), {"maple"}],
)
def test_normalize_input_rejects_non_strings(raw: object) -> None:
    with pytest.raises(TypeError):
        algorithm.normalize_input(raw)


# ---------------------------------------------------------------------------
# branch_code_number / branch_code
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "number", "token"),
    SINGLE_LETTER_CASES + HAND_COMPUTED_CASES,
)
def test_branch_code_matches_hand_computed_values(
    raw: str, number: int, token: str
) -> None:
    assert algorithm.branch_code_number(raw) == number
    assert algorithm.branch_code(raw) == token


@pytest.mark.parametrize(("raw", "number", "token"), SINGLE_LETTER_CASES)
def test_letter_values_run_from_one_to_twenty_six(
    raw: str, number: int, token: str
) -> None:
    # A single letter scores letter_value + 7, so the letter value is recoverable.
    assert token == f"BRANCH-{number:02d}"
    assert number - algorithm.DISTINCT_WEIGHT == algorithm.ALPHABET.index(raw) + 1


@pytest.mark.parametrize("entry", [entry for entry, _ in DATASET_EXPECTED])
def test_branch_code_number_is_always_in_range(entry: str) -> None:
    assert 0 <= algorithm.branch_code_number(entry) < algorithm.MODULUS


@pytest.mark.parametrize("entry", [entry for entry, _ in DATASET_EXPECTED])
def test_branch_code_is_deterministic(entry: str) -> None:
    assert algorithm.branch_code(entry) == algorithm.branch_code(entry)


@pytest.mark.parametrize(
    ("raw", "variant"),
    [
        ("maple", "MAPLE"),
        ("maple", "  Maple  "),
        ("birch", "\tBIRCH\n"),
        ("acorn", "AcOrN"),
        ("cedar", " cedar "),
    ],
)
def test_branch_code_ignores_case_and_surrounding_whitespace(
    raw: str, variant: str
) -> None:
    assert algorithm.branch_code(variant) == algorithm.branch_code(raw)


@pytest.mark.parametrize(
    ("raw", "number", "token"), SINGLE_LETTER_CASES + HAND_COMPUTED_CASES
)
def test_branch_code_is_always_two_digits(raw: str, number: int, token: str) -> None:
    rendered = algorithm.branch_code(raw)
    assert BRANCH_TOKEN.fullmatch(rendered), rendered
    assert len(rendered) == len("BRANCH-00")
    assert rendered == token
    assert int(rendered.removeprefix("BRANCH-")) == number


def test_branch_code_zero_pads_single_digit_numbers() -> None:
    # 'a' scores 8 and 'bgt' scores 0; both must still render two digits.
    assert algorithm.branch_code_number("a") == 8
    assert algorithm.branch_code("a") == "BRANCH-08"
    assert algorithm.branch_code_number("bgt") == 0
    assert algorithm.branch_code("bgt") == "BRANCH-00"


@pytest.mark.parametrize(
    "raw", ["", "   ", "m4ple", "caf\u00e9", "maple oak", "\U0001f332"]
)
def test_branch_code_propagates_rejections(raw: str) -> None:
    with pytest.raises(ValueError):
        algorithm.branch_code_number(raw)
    with pytest.raises(ValueError):
        algorithm.branch_code(raw)


def test_position_weighting_makes_anagrams_differ() -> None:
    assert algorithm.branch_code_number("ab") != algorithm.branch_code_number("ba")


def test_distinct_weight_is_applied_once_per_distinct_character() -> None:
    # 'aa' and 'aaa' share one distinct character; only the positional sum grows.
    assert algorithm.branch_code_number("aa") == (1 * 1 + 1 * 2) + 7
    assert algorithm.branch_code_number("aaa") == (1 * 1 + 1 * 2 + 1 * 3) + 7


def test_algorithm_docstring_examples_hold() -> None:
    results = doctest.testmod(algorithm, verbose=False)
    assert results.attempted > 0
    assert results.failed == 0


# ---------------------------------------------------------------------------
# dataset
# ---------------------------------------------------------------------------


def test_validate_dataset_passes() -> None:
    dataset.validate_dataset()


def test_dataset_has_at_least_thirty_two_entries() -> None:
    assert dataset.MIN_PROVING_INPUTS == 32
    assert len(dataset.PROVING_INPUTS) >= dataset.MIN_PROVING_INPUTS
    assert len(dataset.PROVING_INPUTS) == len(DATASET_EXPECTED)


def test_dataset_entries_are_unique() -> None:
    assert len(set(dataset.PROVING_INPUTS)) == len(dataset.PROVING_INPUTS)


@pytest.mark.parametrize("entry", dataset.PROVING_INPUTS)
def test_dataset_entry_is_normalized_lowercase_ascii(entry: str) -> None:
    assert algorithm.normalize_input(entry) == entry
    assert entry.isascii()
    assert set(entry) <= set(algorithm.ALPHABET)


@pytest.mark.parametrize("entry", dataset.PROVING_INPUTS)
def test_dataset_entry_length_is_in_bounds(entry: str) -> None:
    assert dataset.MIN_INPUT_LENGTH <= len(entry) <= dataset.MAX_INPUT_LENGTH


def test_dataset_length_bounds_are_four_to_twelve() -> None:
    assert dataset.MIN_INPUT_LENGTH == 4
    assert dataset.MAX_INPUT_LENGTH == 12


@pytest.mark.parametrize("entry", dataset.PROVING_INPUTS)
def test_dataset_entry_is_not_a_documentation_example(entry: str) -> None:
    assert entry not in dataset.DOCUMENTATION_EXAMPLES


def test_documentation_examples_are_disjoint_from_dataset() -> None:
    assert dataset.DOCUMENTATION_EXAMPLES
    assert dataset.DOCUMENTATION_EXAMPLES.isdisjoint(dataset.PROVING_INPUTS)


def test_proving_inputs_returns_the_frozen_tuple() -> None:
    assert isinstance(dataset.proving_inputs(), tuple)
    assert dataset.proving_inputs() == dataset.PROVING_INPUTS


def test_proving_inputs_order_is_stable_across_calls() -> None:
    first = dataset.proving_inputs()
    second = dataset.proving_inputs()
    assert first == second
    assert list(first) == list(second)


def test_proving_inputs_order_matches_the_frozen_snapshot() -> None:
    # Membership commitments pin this exact order; changing it is breaking.
    assert dataset.proving_inputs() == FROZEN_ORDER


def test_proving_inputs_order_is_length_then_alphabetical() -> None:
    keyed = [(len(entry), entry) for entry in dataset.PROVING_INPUTS]
    assert keyed == sorted(keyed)


@pytest.mark.parametrize(("entry", "expected"), DATASET_EXPECTED)
def test_dataset_entry_branch_code(entry: str, expected: str) -> None:
    assert algorithm.branch_code(entry) == expected


# ---------------------------------------------------------------------------
# validate_dataset failure modes
# ---------------------------------------------------------------------------

_HEAD = dataset.PROVING_INPUTS[:-1]


@pytest.mark.parametrize(
    ("replacement", "match"),
    [
        (dataset.PROVING_INPUTS[:10], "at least 32"),
        ((*_HEAD, dataset.PROVING_INPUTS[0]), "duplicate"),
        ((*_HEAD, "Sequoias"), "normalized lowercase a-z"),
        ((*_HEAD, "black-thorn"), "a-z"),
        ((*_HEAD, "spruce9"), "a-z"),
        ((*_HEAD, "oak"), "4-12 characters"),
        ((*_HEAD, "thirteenchars"), "4-12 characters"),
        ((*_HEAD, "maple"), "documentation example"),
        (tuple(reversed(dataset.PROVING_INPUTS)), "ordered by length"),
    ],
)
def test_validate_dataset_rejects_broken_datasets(
    monkeypatch: pytest.MonkeyPatch, replacement: tuple[str, ...], match: str
) -> None:
    monkeypatch.setattr(dataset, "PROVING_INPUTS", replacement)
    with pytest.raises(ValueError, match=match):
        dataset.validate_dataset()


def test_validate_dataset_is_restored_after_monkeypatching() -> None:
    # Guards against a broken fixture leaking into the frozen commitment.
    assert dataset.PROVING_INPUTS == FROZEN_ORDER
    dataset.validate_dataset()
