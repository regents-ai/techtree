import copy
import json
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from payment_terms import offers, scoring

GOLD = offers.generate(0)["held_out"][0].answer
FIELD_COUNT = len(scoring.FIELDS)

JSON = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False) | st.text(),
    lambda children: st.lists(children) | st.dictionaries(st.text(), children),
    max_leaves=20,
)


def _parent(value: dict[str, Any], path: scoring.Path) -> Any:
    for step in path[:-1]:
        value = value[step]  # type: ignore[index]
    return value


def _set(value: dict[str, Any], path: scoring.Path, new: Any) -> dict[str, Any]:
    changed = copy.deepcopy(value)
    _parent(changed, path)[path[-1]] = new
    return changed


def _drop(value: dict[str, Any], path: scoring.Path) -> dict[str, Any]:
    changed = copy.deepcopy(value)
    del _parent(changed, path)[path[-1]]
    return changed


def _get(value: dict[str, Any], path: scoring.Path) -> Any:
    for step in path:
        value = value[step]  # type: ignore[index]
    return value


@given(st.text())
def test_reward_is_in_bounds_for_any_text(reply: str) -> None:
    assert 0.0 <= scoring.reward(reply, GOLD) <= 1.0


@given(JSON)
def test_reward_is_in_bounds_for_any_json(value: Any) -> None:
    reward = scoring.reward(json.dumps(value), GOLD)
    assert 0.0 <= reward <= 1.0
    assert scoring.solved(json.dumps(value), GOLD) == (reward == 1.0)


@pytest.mark.parametrize(
    "reply",
    [
        json.dumps(GOLD),
        json.dumps(GOLD, indent=2),
        f"Here are the requirements:\n```json\n{json.dumps(GOLD, indent=2)}\n```",
        f"{json.dumps(GOLD)}\nThat is the body.",
        json.dumps({**GOLD, "error": "Payment required"}),
    ],
)
def test_gold_answer_solves_however_it_is_wrapped(reply: str) -> None:
    assert scoring.reward(reply, GOLD) == 1.0
    assert scoring.solved(reply, GOLD)


@pytest.mark.parametrize("path", scoring.FIELDS, ids=lambda p: ".".join(map(str, p)))
@pytest.mark.parametrize("wrong", ["value", "type", "missing"])
def test_each_wrong_field_loses_one_share(path: scoring.Path, wrong: str) -> None:
    gold_value = _get(GOLD, path)
    if wrong == "missing":
        changed = _drop(GOLD, path)
    elif wrong == "type":
        changed = _set(GOLD, path, _other_type(gold_value))
    else:
        changed = _set(GOLD, path, gold_value + 1 if isinstance(gold_value, int) else "x")
    reply = json.dumps(changed)
    assert scoring.correct_fields(reply, GOLD) == FIELD_COUNT - 1
    assert scoring.reward(reply, GOLD) == pytest.approx((FIELD_COUNT - 1) / FIELD_COUNT)
    assert not scoring.solved(reply, GOLD)


def _other_type(value: int | str) -> int | str | list[str]:
    """The same value as another JSON type: 2 and "2", "3600" and 3600."""
    if isinstance(value, int):
        return str(value)
    return int(value) if value.isdigit() else [value]


def test_letter_case_counts() -> None:
    lower = _set(GOLD, ("accepts", 0, "asset"), offers.USDC.lower())
    assert scoring.correct_fields(json.dumps(lower), GOLD) == FIELD_COUNT - 1


def test_accepts_holds_exactly_one_requirement() -> None:
    requirement = GOLD["accepts"][0]
    two = _set(GOLD, ("accepts",), [requirement, requirement])
    bare = _set(GOLD, ("accepts",), requirement)
    accepts_fields = sum(1 for path in scoring.FIELDS if path[0] == "accepts")
    assert scoring.correct_fields(json.dumps(two), GOLD) == FIELD_COUNT - accepts_fields
    assert scoring.correct_fields(json.dumps(bare), GOLD) == FIELD_COUNT - accepts_fields


@pytest.mark.parametrize(
    "reply",
    [
        "",
        "I cannot help with that.",
        "[1, 2, 3]",
        f"{json.dumps(GOLD)}\n{json.dumps(GOLD)}",
        '{"x402Version": 2,',
    ],
)
def test_no_single_object_scores_zero(reply: str) -> None:
    assert scoring.reward(reply, GOLD) == 0.0
    assert scoring.extract(reply) is None
