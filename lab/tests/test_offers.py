import json
import random
import re
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from payment_terms import offers, scoring

SEED_ZERO = offers.generate(0)


def test_split_sizes() -> None:
    assert len(SEED_ZERO["train"]) == 1024
    assert len(SEED_ZERO["held_out"]) == 64


@settings(max_examples=25, deadline=None)
@given(st.integers(min_value=0, max_value=10_000))
def test_splits_never_share_a_task(seed: int) -> None:
    splits = offers.generate(seed)
    train, held_out = splits["train"], splits["held_out"]
    for field in ("id", "prompt"):
        assert not {getattr(i, field) for i in train} & {getattr(i, field) for i in held_out}
    train_answers = {json.dumps(i.answer, sort_keys=True) for i in train}
    held_out_answers = {json.dumps(i.answer, sort_keys=True) for i in held_out}
    assert not train_answers & held_out_answers
    assert len(train_answers) == len(train) and len(held_out_answers) == len(held_out)
    for name, items in splits.items():
        assert all(i.split == name == offers.split_of(i.answer) for i in items)


@settings(max_examples=10, deadline=None)
@given(st.integers(min_value=0, max_value=10_000))
def test_generation_is_fixed_by_the_seed(seed: int) -> None:
    assert offers.generate(seed) == offers.generate(seed)


def test_ids_are_unique_slugs() -> None:
    items = SEED_ZERO["train"] + SEED_ZERO["held_out"]
    assert len({i.id for i in items}) == len(items)
    assert SEED_ZERO["held_out"][0].id == "payment-terms-held-out-0000"
    assert SEED_ZERO["train"][0].id == "payment-terms-train-0000"


def test_every_prompt_states_its_answer() -> None:
    for item in SEED_ZERO["train"] + SEED_ZERO["held_out"]:
        requirement = item.answer["accepts"][0]
        assert requirement["payTo"] in item.prompt
        assert item.answer["resource"]["url"] in item.prompt
        assert f'"{item.answer["resource"]["description"]}"' in item.prompt
        assert item.prompt.endswith(offers.INSTRUCTION)


def test_gold_answers_solve() -> None:
    for item in SEED_ZERO["train"] + SEED_ZERO["held_out"]:
        assert scoring.solved(json.dumps(item.answer), item.answer)


@given(st.integers(min_value=1, max_value=10**12), st.integers(min_value=0, max_value=6))
def test_decimal_reads_back_as_the_amount(amount: int, places: int) -> None:
    assert Decimal(offers.decimal(amount, places)) * offers.UNIT == amount


_SMALL = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
    "eighteen", "nineteen",
]  # fmt: skip
_TENS = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_WORDS = {w: n for n, w in enumerate(_SMALL)} | {w: 10 * (n + 2) for n, w in enumerate(_TENS)}


def _words(text: str) -> int:
    total = 0
    for token in text.replace("-", " ").split():
        total = total * 100 if token == "hundred" else total + _WORDS[token]
    return total


def read_price(text: str) -> int:
    """A price as a reader would take it, in base units."""
    if m := re.fullmatch(r"\$?(\d+(?:\.\d+)?)(?: USDC)?", text):
        return int(Decimal(m[1]) * offers.UNIT)
    if m := re.fullmatch(r"(\d+) cents?", text):
        return int(m[1]) * 10_000
    if m := re.fullmatch(r"(.+) dollars? and (.+) cents?", text):
        return _words(m[1]) * offers.UNIT + _words(m[2]) * 10_000
    if m := re.fullmatch(r"(.+) dollars?", text):
        return _words(m[1]) * offers.UNIT
    if m := re.fullmatch(r"(.+) cents?", text):
        return _words(m[1]) * 10_000
    if m := re.fullmatch(r"(.+) dollars? (.+)", text):
        return _words(m[1]) * offers.UNIT + _words(m[2]) * 10_000
    raise ValueError(text)


AMOUNTS = st.one_of(
    st.integers(min_value=1, max_value=19_999).map(lambda cents: cents * 10_000),
    st.integers(min_value=1, max_value=99).map(lambda units: units * 100),
)


@given(AMOUNTS, st.integers(min_value=0, max_value=2**32))
def test_every_wording_states_the_price(amount: int, seed: int) -> None:
    assert read_price(offers.amount_words(amount, random.Random(seed))) == amount


def test_drawn_amounts_have_a_wording() -> None:
    rng = random.Random(0)
    for _ in range(2000):
        amount = offers.draw(rng).amount
        assert read_price(offers.amount_words(amount, rng)) == amount


def test_number_words() -> None:
    assert offers.number_words(0) == "zero"
    assert offers.number_words(15) == "fifteen"
    assert offers.number_words(40) == "forty"
    assert offers.number_words(99) == "ninety-nine"
    assert offers.number_words(105) == "one hundred five"
    assert offers.number_words(199) == "one hundred ninety-nine"


def test_amount_wordings() -> None:
    forms = {offers.amount_words(1_500_000, random.Random(n)) for n in range(200)}
    assert forms == {
        "$1.50",
        "1.50 USDC",
        "1.5 USDC",
        "150 cents",
        "one dollar and fifty cents",
        "one dollar fifty",
    }
    assert {offers.amount_words(3600, random.Random(n)) for n in range(50)} == {
        "$0.0036",
        "0.0036 USDC",
    }
