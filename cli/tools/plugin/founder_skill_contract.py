"""What a founder Skill has to say before a release may pin it.

Decision 0007's final section fixes the behaviour of the founder Skills, and
decision 0009 reduced the set to one the plugin bundles: `skill-improver`.
This states that Skill's contract in checkable form, so the release gate
refuses a Skill that does not carry it.

The checks are about instructions, not prose style. Each one looks for a
promise the contract requires the Skill to make in its own text, because a
Skill that never says "make only one proposal" is a Skill nobody can hold to
it.

Promises must be stated as rules — list items — rather than mentioned in
passing. Prose that happens to use the same words is not a promise, and a
check that accepted it would pass a Skill that promised nothing. Bulleted and
numbered lists both count: a numbered step is as much a rule as a dashed one.

A prohibition may be written two ways, and both count: inside the rule
("never write X"), or as a list under a heading that already said "Do not:".

Decision 0010 rewrote the founder Skill's prohibitions in semantic language so
the prompt never teaches a model the literal phrases the deterministic guard
looks for. The vocabulary below therefore accepts either wording for the same
promise; what is required is unchanged.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Final

#: What the skill-improver Skill must tell the model to do. Each entry is a
#: promise and the phrasings that count as stating it.
IMPROVER_REQUIRED_RULES: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    ("find one general rule", ("one general rule",)),
    ("make the smallest correction", ("smallest", "minimal edits")),
    (
        "return one complete revised SKILL.md",
        ("complete revised skill.md", "complete replacement `skill.md`"),
    ),
    ("preserve the rules that are correct", ("preserve",)),
    ("state the tradeoffs", ("tradeoff",)),
    ("make exactly one proposal", ("exactly one proposal", "more than one candidate")),
)

#: What it must tell the model never to do, and the phrasings that count.
IMPROVER_FORBIDDEN_SUBJECTS: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    (
        "case-specific exception",
        (
            "task-specific exception",
            "case-specific exception",
            "exceptions tied to particular observed cases",
        ),
    ),
    (
        "copied evaluation case",
        ("input and output pairs", "evaluation case or its result"),
    ),
    (
        "mapping of evaluation cases to results",
        (
            "answer table",
            "evaluation-case mapping",
            "mappings or exceptions tied to particular observed cases",
        ),
    ),
)

#: Every Skill file must name itself and say what it is for.
FRONT_MATTER = re.compile(r"^---\n(?P<body>.*?)\n---\n", re.DOTALL)

MAXIMUM_CHARACTERS: Final = 20_000


def check_common(text: str) -> Iterator[str]:
    """Yield problems any founder Skill would have."""
    if not text.strip():
        yield "the Skill is empty"
        return
    if len(text) > MAXIMUM_CHARACTERS:
        yield f"the Skill is {len(text)} characters, longer than reviewed"

    front_matter = FRONT_MATTER.match(text)
    if front_matter is None:
        yield "the Skill has no front matter naming it"
        return
    body = front_matter.group("body").lower()
    if "name:" not in body:
        yield "the front matter does not name the Skill"
    if "description:" not in body:
        yield "the front matter does not say what the Skill is for"


def check_skill_improver(text: str) -> list[str]:
    """Return every way this Skill fails the improver contract."""
    problems = list(check_common(text))
    rules = _rules(text.lower())

    for description, phrases in IMPROVER_REQUIRED_RULES:
        if not any(_states(rules, phrase) for phrase in phrases):
            problems.append(f"it does not say to {description}")

    for description, phrases in IMPROVER_FORBIDDEN_SUBJECTS:
        if not any(_forbids(rules, phrase) for phrase in phrases):
            problems.append(f"it does not forbid writing a {description}")

    return problems


CHECKS: Final = {"skill-improver": check_skill_improver}


#: How a rule says "not this" in its own words.
DENIALS: Final[tuple[str, ...]] = ("never", "must not", "do not", "not allowed")

#: A heading that turns the list beneath it into prohibitions.
_DENIAL_LEAD_IN: Final = re.compile(r"\b(do not|never|must not|not allowed)\s*:\s*$")

#: A rule line: bulleted or numbered.
_LIST_ITEM: Final = re.compile(r"^(?:[-*]|\d+[.)])\s+")


@dataclass(frozen=True)
class _Rule:
    """One rule line, and whether the section it sits in already denied it."""

    text: str
    denied_by_section: bool


def _rules(lowered: str) -> list[_Rule]:
    """Return the Skill's rules: its list items, each rejoined into one line.

    An item that wraps over several lines is still one rule, so the lines are
    rejoined before anything is looked for in them.
    """
    rules: list[_Rule] = []
    current: list[str] | None = None
    denied_section = False

    for line in lowered.splitlines():
        stripped = line.strip()
        if _LIST_ITEM.match(stripped):
            if current is not None:
                rules.append(_Rule(" ".join(current), denied_section))
            current = [_LIST_ITEM.sub("", stripped, count=1).strip()]
        elif current is not None and stripped and line.startswith((" ", "\t")):
            current.append(stripped)
        else:
            if current is not None:
                rules.append(_Rule(" ".join(current), denied_section))
                current = None
            if stripped:
                denied_section = _DENIAL_LEAD_IN.search(stripped) is not None

    if current is not None:
        rules.append(_Rule(" ".join(current), denied_section))
    return rules


def _states(rules: Sequence[_Rule], phrase: str) -> bool:
    """Whether some rule states this phrase."""
    return any(phrase in rule.text for rule in rules)


def _forbids(rules: Sequence[_Rule], subject: str) -> bool:
    """Whether some rule denies this subject, in its words or its section's."""
    return any(
        subject in rule.text
        and (rule.denied_by_section or any(denial in rule.text for denial in DENIALS))
        for rule in rules
    )


def describe(problems: Sequence[str]) -> str:
    """Return one line per problem, or a line saying there were none."""
    if not problems:
        return "contract satisfied"
    return "\n".join(f"- {problem}" for problem in problems)
