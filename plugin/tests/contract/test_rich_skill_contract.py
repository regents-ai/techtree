"""The rich-output Skill's behavioural contract. Decision 0007, section 8.5.

The founder writes this Skill; the release pins it by digest. It does not
exist yet, so the contract runs against a clearly-labelled fixture today and
against the real file the day it arrives — the same check either way, which is
the point of writing it now.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from founder_skill_contract import check_rich_terminal_output, describe
from techtree_hermes.constants import PLUGIN_ROOT
from techtree_hermes.errors import contains_secret_material

NAME = "rich-terminal-output"
FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "skills" / NAME / "SKILL.md"
)
BUNDLED = PLUGIN_ROOT / "skills" / NAME / "SKILL.md"


def test_the_fixture_satisfies_the_contract() -> None:
    problems = check_rich_terminal_output(FIXTURE.read_text("utf-8"))

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
        "Never output a score.",
        "Never output a proof grade.",
        "Never output a digest.",
        "Never alter any number, verdict, or status that was given to you.",
    ],
)
def test_a_skill_that_drops_a_promise_fails_the_contract(removed: str) -> None:
    weakened = FIXTURE.read_text("utf-8").replace(removed, "")

    assert check_rich_terminal_output(weakened)


def test_a_skill_that_never_names_its_outputs_fails() -> None:
    assert check_rich_terminal_output("---\nname: x\ndescription: y\n---\n# Nothing\n")


@pytest.mark.skipif(
    not BUNDLED.is_file(), reason="the founder Skill does not exist yet"
)
def test_the_bundled_skill_satisfies_the_contract() -> None:
    problems = check_rich_terminal_output(BUNDLED.read_text("utf-8"))

    assert not problems, describe(problems)
