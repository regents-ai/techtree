"""What a founder Skill has to say before a release may pin it.

Decision 0007's final section fixes the behaviour of the two founder Skills.
Neither exists yet, so this states the contract in checkable form: it runs
against test fixtures today and against the real files the day they arrive,
and the release gate refuses a Skill that does not carry its contract.

The checks are about instructions, not prose style. Each one looks for a
promise the contract requires the Skill to make in its own text, because a
Skill that never says "never output a score" is a Skill nobody can hold to it.

Promises must be stated as rules — bullet lines — rather than mentioned in
passing. Prose that happens to use the same words is not a promise, and a
check that accepted it would pass a Skill that promised nothing.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from typing import Final

#: The rich-terminal-output Skill produces narrative choices and nothing else.
RICH_REQUIRED_OUTPUTS: Final[tuple[str, ...]] = (
    "headline",
    "observation",
    "caveat",
    "next step",
)

#: Nothing it is ever allowed to output or change.
RICH_FORBIDDEN_SUBJECTS: Final[tuple[str, ...]] = (
    "score",
    "delta",
    "wins, losses, or ties",
    "cost",
    "timing",
    "proof grade",
    "status",
    "digest",
    "command",
)

#: What the skill-improver Skill must tell the model to do.
IMPROVER_REQUIRED_RULES: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    ("find one general rule", ("one general rule",)),
    ("make the smallest correction", ("smallest",)),
    ("return one complete revised SKILL.md", ("complete revised skill.md",)),
    ("preserve the rules that are correct", ("preserve",)),
    ("state the tradeoffs", ("tradeoff",)),
    ("make exactly one proposal", ("exactly one proposal",)),
)

#: What it must tell the model never to do.
IMPROVER_FORBIDDEN_SUBJECTS: Final[tuple[str, ...]] = (
    "task-specific exception",
    "input and output pairs",
    "answer table",
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


def check_rich_terminal_output(text: str) -> list[str]:
    """Return every way this Skill fails the rich-output contract."""
    problems = list(check_common(text))
    lowered = text.lower()

    for output in RICH_REQUIRED_OUTPUTS:
        if not _states(lowered, output):
            problems.append(f"it never mentions the {output} it is meant to produce")

    for subject in RICH_FORBIDDEN_SUBJECTS:
        if not _forbids(lowered, subject):
            problems.append(f"it does not promise never to output a {subject}")

    if not _forbids(lowered, "alter"):
        problems.append("it does not promise never to alter a number it was given")

    return problems


def check_skill_improver(text: str) -> list[str]:
    """Return every way this Skill fails the improver contract."""
    problems = list(check_common(text))
    lowered = text.lower()

    for description, phrases in IMPROVER_REQUIRED_RULES:
        if not any(_states(lowered, phrase) for phrase in phrases):
            problems.append(f"it does not say to {description}")

    for subject in IMPROVER_FORBIDDEN_SUBJECTS:
        if not _forbids(lowered, subject):
            problems.append(f"it does not forbid writing a {subject}")

    return problems


CHECKS: Final = {
    "rich-terminal-output": check_rich_terminal_output,
    "skill-improver": check_skill_improver,
}


#: How a Skill says "not this".
DENIALS: Final[tuple[str, ...]] = ("never", "must not", "do not", "not allowed")


def _rules(lowered: str) -> list[str]:
    """Return the Skill's rules: its bullets, each rejoined into one line.

    A bullet that wraps over several lines is still one rule, so the lines are
    rejoined before anything is looked for in them.
    """
    rules: list[str] = []
    current: list[str] | None = None
    for line in lowered.splitlines():
        stripped = line.strip()
        if stripped.startswith(("-", "*")):
            if current is not None:
                rules.append(" ".join(current))
            current = [stripped.lstrip("-*").strip()]
        elif current is not None and stripped and line.startswith((" ", "\t")):
            current.append(stripped)
        elif current is not None:
            rules.append(" ".join(current))
            current = None
    if current is not None:
        rules.append(" ".join(current))
    return rules


def _states(lowered: str, phrase: str) -> bool:
    """Whether some rule line states this phrase."""
    return any(phrase in rule for rule in _rules(lowered))


def _forbids(lowered: str, subject: str) -> bool:
    """Whether some rule line denies this subject."""
    return any(
        subject in rule and any(denial in rule for denial in DENIALS)
        for rule in _rules(lowered)
    )


def describe(problems: Sequence[str]) -> str:
    """Return one line per problem, or a line saying there were none."""
    if not problems:
        return "contract satisfied"
    return "\n".join(f"- {problem}" for problem in problems)
