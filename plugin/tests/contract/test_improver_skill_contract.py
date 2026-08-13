"""The skill-improver Skill's behavioural contract. Decision 0007, section 8.5.

The founder writes this Skill; the release pins it by digest. It does not
exist yet, so the contract runs against a clearly-labelled fixture today and
against the real file the day it arrives — the same check either way, which is
the point of writing it now.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from founder_skill_contract import check_skill_improver, describe
from techtree_hermes.constants import PLUGIN_ROOT
from techtree_hermes.errors import contains_secret_material

NAME = "skill-improver"
FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "skills" / NAME / "SKILL.md"
)
BUNDLED = PLUGIN_ROOT / "skills" / NAME / "SKILL.md"


def test_the_fixture_satisfies_the_contract() -> None:
    problems = check_skill_improver(FIXTURE.read_text("utf-8"))

    assert not problems, describe(problems)


def test_the_fixture_says_plainly_that_it_is_not_the_founder_skill() -> None:
    """It must never be mistaken for the real thing, or shipped as one."""
    text = FIXTURE.read_text("utf-8")

    assert "FIXTURE" in text
    assert "not the founder" in text.lower()
    assert not BUNDLED.is_file(), "a fixture must never become the bundled Skill"


def test_the_fixture_carries_no_credential() -> None:
    assert not contains_secret_material(FIXTURE.read_text("utf-8"))


@pytest.mark.parametrize(
    "removed",
    [
        "Find one general rule that explains the failure pattern.",
        "Never write an answer table.",
        "Make exactly one proposal.",
        "State the tradeoffs your change makes.",
    ],
)
def test_a_skill_that_drops_a_promise_fails_the_contract(removed: str) -> None:
    weakened = FIXTURE.read_text("utf-8").replace(removed, "")

    assert check_skill_improver(weakened)


def test_a_skill_that_states_no_rules_fails() -> None:
    assert check_skill_improver("---\nname: x\ndescription: y\n---\n# Nothing\n")


@pytest.mark.skipif(
    not BUNDLED.is_file(), reason="the founder Skill does not exist yet"
)
def test_the_bundled_skill_satisfies_the_contract() -> None:
    problems = check_skill_improver(BUNDLED.read_text("utf-8"))

    assert not problems, describe(problems)
