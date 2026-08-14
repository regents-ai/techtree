"""What a proposed Skill, and any wording beside a result, is checked for.

Section 8.7. The half of this module that checks a revised Skill guards the
one host completion the release makes. The narrative checks below it guard
wording by a host model, which decision 0009 removed from the release: they
are reachable from nothing in the released flow, and no release promise
depends on them.

They exist because the failure they prevent is not obvious in the output. A
sentence that says "roughly two thirds of tasks now pass" reads like commentary
and is in fact a claim about a number nobody computed. A sentence that says
"independently reproduced" reads like praise and is in fact a false statement
about how the result was produced. Both look fine next to a correct table.

When a check fails, the narrative is discarded whole. It is never edited into
something acceptable, and the model is never asked again automatically: the
deterministic result is complete on its own, and a second completion behind a
person's back is exactly what the one-shot rule forbids.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final

from .channels import bounded_gateway_text, is_gateway_safe_required
from .constants import MAX_STARTER_SKILL_BYTES
from .errors import PluginError, contains_secret_material
from .models import ChannelKind, PresentationNarrative

CODE_PRESENTATION_CLAIM_FORBIDDEN: Final = "presentation_claim_forbidden"
CODE_PRESENTATION_TOO_LARGE: Final = "presentation_output_too_large"


class NarrativeRejectedError(PluginError):
    """The narrative said something it was not allowed to say."""

    code = CODE_PRESENTATION_CLAIM_FORBIDDEN


#: Claims that are false about a local result however they are phrased. Each
#: entry is a pattern rather than a string, because "was independently
#: reproduced" and "independent reproduction" are the same claim.
_FORBIDDEN_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("independent reproduction", re.compile(r"independent(ly)?\s+reproduc", re.I)),
    (
        "website verification",
        re.compile(r"(website|techtree\.sh)[^.]{0,40}verif", re.I),
    ),
    (
        "sealed evaluation",
        re.compile(r"\bsealed\b[^.]{0,20}(evaluation|benchmark)", re.I),
    ),
    ("held-out evaluation", re.compile(r"held[- ]out", re.I)),
    ("hosted execution", re.compile(r"(prime|platform|cloud)[- ]hosted", re.I)),
    ("training-ready data", re.compile(r"training[- ]ready", re.I)),
    (
        "a guarantee",
        re.compile(r"guarantee[ds]?\s+(improvement|results?|gains?)", re.I),
    ),
    (
        "a general capability claim",
        re.compile(r"(universally|generally|always)\s+(learned|improves?|works)", re.I),
    ),
    (
        "a generalization claim",
        re.compile(r"generaliz\w*\s+(proof|proven|guarantee)", re.I),
    ),
    ("a leaderboard claim", re.compile(r"leaderboard|state[- ]of[- ]the[- ]art", re.I)),
)

#: Values that belong to Techtree's payload and never to a sentence.
_NUMERIC_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("a score fraction", re.compile(r"\d+\s*/\s*\d+")),
    ("a percentage", re.compile(r"\d+(\.\d+)?\s*%")),
    ("a decimal value", re.compile(r"\b\d+\.\d+\b")),
    # Both dash characters are deliberate: the ASCII hyphen and the Unicode
    # minus sign. A model that writes a negative delta with the typographic
    # one is stating a value just as much, and the guard has to catch both.
    ("a signed delta", re.compile(r"[+−-]\s?\d+(\.\d+)?\b")),  # noqa: RUF001
    (
        "a counted outcome",
        re.compile(
            r"\b\d+\s+(wins?|losses|loses|ties?|tasks?|episodes?|points?|tokens?"
            r"|seconds?|dollars?)\b",
            re.I,
        ),
    ),
    (
        "a named value",
        re.compile(
            r"\b(score|delta|cost|runtime|duration|latency|accuracy)\b[^.]{0,12}\d",
            re.I,
        ),
    ),
)

#: Statuses, grades, and addresses the payload renders itself.
_CANONICAL_TOKENS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("a digest", re.compile(r"sha256:[0-9a-f]{8,}", re.I)),
    ("an identifier", re.compile(r"\b(run|draft|receipt|climb)_[0-9a-f]{8,}\b", re.I)),
    ("a proof grade", re.compile(r"\bP[0-3]\b|\bdevelopment_only\b")),
    (
        "a controlled-status code",
        re.compile(r"\bcontrolled(_with_warnings)?\b|\binvalid\b", re.I),
    ),
)

#: A narrative names no command. Techtree's own next actions carry those, and
#: they are rendered from the payload, not from a sentence.
_COMMAND_PATTERN: Final = re.compile(
    r"(?m)(^|[\s`\"'(])(techtree|hermes|uv|bash|sh|curl|pip|docker|git|sudo|rm)\s+[\w-]"
)

_ANSI_PATTERN: Final = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[@-Z\\-_]")

#: How much room a narrative has, per channel.
TERMINAL_NARRATIVE_CHARACTERS: Final = 2000
GATEWAY_NARRATIVE_CHARACTERS: Final = 700


def validate_narrative(
    narrative: PresentationNarrative,
    *,
    allowed_task_refs: set[str],
    channel: ChannelKind,
) -> None:
    """Check everything the model wrote, and raise on the first problem.

    Raises:
        NarrativeRejected: naming what was said that could not be allowed.
    """
    for text in narrative.texts():
        forbid_unapproved_claims(text)
        forbid_numeric_claims(text)
        forbid_canonical_values(text)
        forbid_new_commands(text, allowed_commands=set())
        forbid_ansi(text)
        forbid_secret_patterns(text)

    unknown = sorted(set(narrative.selected_task_refs) - allowed_task_refs)
    if unknown:
        raise NarrativeRejectedError(
            f"the narrative names tasks that are not in this comparison: {unknown}"
        )

    budget = (
        GATEWAY_NARRATIVE_CHARACTERS
        if is_gateway_safe_required(channel)
        else TERMINAL_NARRATIVE_CHARACTERS
    )
    written = sum(len(text) for text in narrative.texts())
    if written > budget * 4:
        raise NarrativeRejectedError(
            f"the narrative is {written} characters, far more than the "
            f"{budget} this channel has room for",
            code=CODE_PRESENTATION_TOO_LARGE,
        )


def forbid_unapproved_claims(text: str) -> None:
    """Refuse a sentence that claims something untrue about a local result."""
    for described, pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(text):
            raise NarrativeRejectedError(
                f"the narrative claims {described}, which is not true of a "
                "comparison run on this machine"
            )


def forbid_numeric_claims(text: str) -> None:
    """Refuse a sentence that states a value Techtree is responsible for."""
    for described, pattern in _NUMERIC_PATTERNS:
        if pattern.search(text):
            raise NarrativeRejectedError(
                f"the narrative states {described}; every number in a result "
                "comes from Techtree's own payload"
            )


def forbid_canonical_values(text: str) -> None:
    """Refuse a sentence that restates a status, grade, digest, or identifier."""
    for described, pattern in _CANONICAL_TOKENS:
        if pattern.search(text):
            raise NarrativeRejectedError(
                f"the narrative states {described}, which is rendered from the "
                "payload rather than written"
            )


def forbid_new_commands(text: str, allowed_commands: set[str]) -> None:
    """Refuse a sentence that tells the reader to run something.

    A narrative that can name a command is a narrative that can be talked into
    naming a different one.
    """
    match = _COMMAND_PATTERN.search(text)
    if match and match.group(2).lower() not in {
        name.lower() for name in allowed_commands
    }:
        raise NarrativeRejectedError(
            f"the narrative tells the reader to run {match.group(2)!r}; commands "
            "come from Techtree's own next actions"
        )


def forbid_ansi(text: str) -> None:
    """Refuse a sentence carrying terminal control codes."""
    if _ANSI_PATTERN.search(text) or "\x00" in text:
        raise NarrativeRejectedError(
            "the narrative carries terminal control codes, which a result never "
            "needs and a phone must never receive"
        )


def forbid_secret_patterns(text: str) -> None:
    """Refuse a sentence carrying something that looks like a credential."""
    if contains_secret_material(text):
        raise NarrativeRejectedError(
            "the narrative carries something that looks like a credential"
        )


def bounded_narrative(
    narrative: PresentationNarrative, channel: ChannelKind = ChannelKind.UNKNOWN
) -> PresentationNarrative:
    """Return the narrative trimmed to what this channel has room for.

    Trimming drops words. It never drops a caveat: a phone that showed the
    praise and cut the warning would be worse than one that showed neither, so
    the caveats are kept and the observations give way.
    """
    budget = (
        GATEWAY_NARRATIVE_CHARACTERS
        if is_gateway_safe_required(channel)
        else TERMINAL_NARRATIVE_CHARACTERS
    )
    headline = bounded_gateway_text(narrative.headline, min(budget, 160))
    caveats = tuple(
        bounded_gateway_text(text, budget // 2) for text in narrative.caveats[:2]
    )
    remaining = max(0, budget - len(headline) - sum(map(len, caveats)))
    observations = tuple(_fit(narrative.observations, remaining))
    next_step = (
        bounded_gateway_text(narrative.next_step, budget // 3)
        if narrative.next_step
        else None
    )
    return PresentationNarrative(
        headline=headline,
        observations=observations,
        caveats=caveats,
        next_step=next_step,
        selected_task_refs=narrative.selected_task_refs[:5],
    )


def _fit(texts: Iterable[str], budget: int) -> list[str]:
    kept: list[str] = []
    left = budget
    for text in texts:
        if len(text) > left:
            break
        kept.append(text)
        left -= len(text)
    return kept


# A revised Skill ------------------------------------------------------------------
#
# Decision 0007's skill-improver contract: one general rule, the smallest
# correction, no task-specific exceptions, and never copied input/output pairs.
# The last one is what these guards can actually check, and it matters most: a
# Skill that lists the answers is not a Skill, it is a lookup table that would
# score well once and teach nothing.

CODE_SKILL_REVISION_INVALID: Final = "skill_revision_output_invalid"
CODE_SKILL_REVISION_SECRET: Final = "skill_revision_secret_detected"

#: A revision is a whole file. These say "here is a change to apply" instead.
_PATCH_MARKERS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    # A unified diff names files and hunks. A bare "---" is front matter, and
    # every Skill starts with some.
    ("a diff", re.compile(r"(?m)^(\+\+\+|---) \S|^@@ [-+]\d")),
    ("a diff block", re.compile(r"```\s*diff", re.I)),
    (
        "an instruction to patch",
        re.compile(r"\b(apply (this|the) (patch|diff))\b", re.I),
    ),
    (
        "an elision",
        re.compile(r"(\.\.\.|…)\s*(rest|remainder|unchanged|as before)", re.I),
    ),
    (
        "an elision",
        re.compile(r"\[\s*(unchanged|no changes?|same as before)\s*\]", re.I),
    ),
)

#: Shapes that pair a case with its answer, whatever they are called.
_ANSWER_TABLE_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (
        "a table of expected answers",
        re.compile(
            r"(?im)^\|[^|\n]*\b(input|case|task|example)\b[^|\n]*\|[^|\n]*"
            r"\b(output|answer|expected|result|value)\b"
        ),
    ),
    (
        "an answer key",
        re.compile(r"\b(answer key|expected answers?|solution table)\b", re.I),
    ),
    (
        "a lookup of cases to answers",
        re.compile(r"(?m)^\s*[-*]?\s*[\"'`][^\"'`\n]{1,80}[\"'`]\s*(->|=>|→|:|=)\s*\S"),
    ),
)

#: How many mapping lines make a list of examples into a lookup table.
_MAXIMUM_MAPPING_LINES: Final = 2

#: A Skill teaches a procedure. It does not ship commands to run.
_SKILL_COMMAND_PATTERN: Final = re.compile(
    r"```\s*(bash|sh|zsh|shell|console|powershell)\b", re.I
)


def forbid_patch_instructions(markdown: str) -> None:
    """Refuse a revision that describes a change instead of being the file."""
    for described, pattern in _PATCH_MARKERS:
        if pattern.search(markdown):
            raise NarrativeRejectedError(
                f"the revision is {described} rather than a complete SKILL.md",
                code=CODE_SKILL_REVISION_INVALID,
            )


def forbid_answer_table(markdown: str) -> None:
    """Refuse a revision that lists cases with their answers.

    This is the failure the improver contract exists to prevent. A revision
    that memorizes the cases it was shown would score well on exactly those
    cases and teach the subject nothing, which is the opposite of what a Skill
    comparison is for.
    """
    for described, pattern in _ANSWER_TABLE_PATTERNS:
        if pattern.search(markdown):
            raise NarrativeRejectedError(
                f"the revision contains {described}; a Skill states a rule, not "
                "the answers",
                code=CODE_SKILL_REVISION_INVALID,
            )

    mappings = re.findall(
        r"(?m)^\s*[-*]?\s*\S[^\n]{0,80}?\s(?:->|=>|→)\s\S[^\n]{0,80}$", markdown
    )
    if len(mappings) > _MAXIMUM_MAPPING_LINES:
        raise NarrativeRejectedError(
            f"the revision maps {len(mappings)} cases to results; a Skill states "
            "a rule, not the answers",
            code=CODE_SKILL_REVISION_INVALID,
        )


def forbid_copied_examples(markdown: str, task_inputs: Iterable[str]) -> None:
    """Refuse a revision that quotes the cases it was shown.

    Exact rather than heuristic: these are the public prompts the improvement
    context actually carried, so finding one verbatim in the revision is proof
    that the model wrote down a case instead of a rule.
    """
    for prompt in task_inputs:
        candidate = prompt.strip()
        if len(candidate) >= 24 and candidate in markdown:
            raise NarrativeRejectedError(
                "the revision copies a task it was shown; a Skill states a rule, "
                "not the cases",
                code=CODE_SKILL_REVISION_INVALID,
            )


def forbid_command_attachment(markdown: str) -> None:
    """Refuse a revision that ships something to run."""
    if _SKILL_COMMAND_PATTERN.search(markdown):
        raise NarrativeRejectedError(
            "the revision attaches commands to run; a Skill teaches a procedure",
            code=CODE_SKILL_REVISION_INVALID,
        )


def validate_revised_skill(
    markdown: str,
    *,
    task_inputs: Iterable[str] = (),
    maximum_bytes: int = MAX_STARTER_SKILL_BYTES,
) -> None:
    """Check a proposed SKILL.md before anyone stages or reads it.

    Preliminary only. Techtree's own scanner is the authority on whether a
    Skill may be prepared; these checks exist so that an obviously unusable
    proposal is refused here, with a reason, rather than deep inside a
    preparation.
    """
    if not markdown.strip():
        raise NarrativeRejectedError(
            "the revision is empty", code=CODE_SKILL_REVISION_INVALID
        )
    if "\x00" in markdown:
        raise NarrativeRejectedError(
            "the revision contains a NUL byte", code=CODE_SKILL_REVISION_INVALID
        )
    if len(markdown.encode("utf-8")) > maximum_bytes:
        raise NarrativeRejectedError(
            f"the revision is larger than the {maximum_bytes} bytes a Skill may be",
            code=CODE_SKILL_REVISION_INVALID,
        )
    if contains_secret_material(markdown):
        raise NarrativeRejectedError(
            "the revision carries something that looks like a credential",
            code=CODE_SKILL_REVISION_SECRET,
        )

    forbid_ansi(markdown)
    forbid_patch_instructions(markdown)
    forbid_answer_table(markdown)
    forbid_copied_examples(markdown, task_inputs)
    forbid_command_attachment(markdown)
