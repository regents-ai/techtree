import re
from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from payment_terms import offers
from techtree_lab import digests

DIGEST = re.compile(r"sha256:[0-9a-f]{64}")

HELD_OUT_DIGEST = "sha256:4fb725b4192fd61c42887153db986a1985e33eb8fdaee30286230bbf29ce808d"
"""The held-out split for seed 0. A change here changes every task a report names."""


def test_held_out_digest_is_stable() -> None:
    assert digests.taskset(offers.generate(0)["held_out"]) == HELD_OUT_DIGEST


def test_held_out_digest_names_ids_prompts_and_answers() -> None:
    items = offers.generate(0)["held_out"]
    rows = [{"id": i.id, "prompt": i.prompt, "answer": i.answer} for i in items]
    assert digests.taskset(items) == digests.canonical(rows)
    assert digests.taskset(items[1:]) != HELD_OUT_DIGEST


def test_canonical_json_matches_rfc_8785() -> None:
    value = {"b": 1.0, "a": [0.5, 2, "é", 0.9167, 1e-7], "c": None}
    expected = '{"a":[0.5,2,"é",0.9167,1e-7],"b":1,"c":null}'.encode()
    assert digests.canonical(value) == digests.of_bytes(expected)


KEYS = st.text(max_size=8)
VALUES = st.none() | st.booleans() | st.integers(-(2**53 - 1), 2**53 - 1) | st.text(max_size=8)


@given(st.dictionaries(KEYS, VALUES, max_size=8), st.randoms())
def test_canonical_digest_ignores_key_order(value: dict[str, Any], rng: Any) -> None:
    items = list(value.items())
    rng.shuffle(items)
    shuffled = dict(items)
    assert digests.canonical(shuffled) == digests.canonical(value)
    assert DIGEST.fullmatch(digests.canonical(value))


@given(st.binary())
def test_byte_digest_shape(data: bytes) -> None:
    assert DIGEST.fullmatch(digests.of_bytes(data))
