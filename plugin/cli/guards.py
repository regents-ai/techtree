"""What any wording beside a result is checked for.

Section 8.7. These checks guard wording by a host model, which decision 0009
removed from the release: they are reachable from nothing in the released
flow, and no release promise depends on them.

They exist because the failure they prevent is not obvious in the output. A
sentence that says "independently reproduced" reads like praise and is in fact
a false statement about how the result was produced. It looks fine next to a
correct table.

When a check fails, the narrative is discarded whole. It is never edited into
something acceptable, and the model is never asked again automatically: the
deterministic result is complete on its own, and a second completion behind a
person's back is exactly what the one-shot rule forbids.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final

from ..host.channels import bounded_gateway_text, is_gateway_safe_required
from ..services.models import ChannelKind, PresentationNarrative
from .errors import PluginError

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

#: A narrative names no command. Techtree's own answers carry those, and
#: they are rendered from the payload, not from a sentence.
_COMMAND_PATTERN: Final = re.compile(
    r"(?m)(^|[\s`\"'(])(regents|hermes|uv|bash|sh|curl|pip|docker|git|sudo|rm)\s+[\w-]"
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
        forbid_canonical_values(text)
        forbid_new_commands(text, allowed_commands=set())
        forbid_ansi(text)

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
