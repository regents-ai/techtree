"""What may appear in a result, enforced rather than intended.

Spec section 7.17.

The evidence a run produces contains material that must not travel into a
rendering. Some of it is obvious — a provider key in an error string, an
absolute path naming somebody's home directory. Some of it is the whole point
of the evaluation: the taskset's hidden expected answers and the grader that
knows them. A presentation that leaked either would not be a cosmetic bug; it
would be a contaminated benchmark.

So the rule here is that the payload's *shape* keeps hidden material out and
these functions keep it out of the free text the shape still allows:

```text
may appear      task ordinal or public name, public prompt summary when the
                policy allows it, score, delta
never appears   hidden expected answer, grader source, provider key,
                authorization header, absolute private path, a traceback
                carrying environment values
```

One decision is worth stating because it was a decision and not an oversight.
The engine's normalized output carries each rollout's *final reply* — what the
subject actually answered. It is the participant's own material, it is often
the most useful thing in a failed task, and it is not hidden verifier material.
It still does not appear in a presentation payload in this release: a reply is
free text from a model, a rendering is a place a reader trusts, and the release
that shows replies should show them where a person asked for them (spec section
7.18's improvement context) rather than in the summary a phone message quotes.
The payload therefore has no field for one.
"""

from __future__ import annotations

import re
from typing import Final

from pydantic import BaseModel

from techtree.errors import ValidationError, sanitize_text
from techtree.presentation.models import UpliftPresentationPayload
from techtree.verifiers.models import NormalizedExecutionError

__all__ = [
    "PRESENTATION_REDACTION_FAILED",
    "ensure_no_hidden_task_material",
    "ensure_no_secret_patterns",
    "sanitize_error_summary",
    "sanitize_label",
]

#: Stable error code. Spec section 15.
PRESENTATION_REDACTION_FAILED: Final = "presentation_redaction_failed"

#: Escape sequences of every shape a terminal would act on. A payload is
#: channel-neutral, so an escape sequence in it is either an accident or an
#: attempt to control someone else's terminal.
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[@-_]|\x9b[0-9;?]*[@-~]")

#: Everything a terminal treats as a command rather than as text, newline and
#: tab included: a rendering places its own line breaks.
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")

_WHITESPACE_RUN = re.compile(r"\s+")

#: A rooted filesystem path with at least two segments, POSIX or Windows.
#: Digests, identifiers and prose do not look like this; ``~/.techtree/...``
#: does, and so does a temporary directory naming a person's account.
_ABSOLUTE_PATH = re.compile(r"(?:[A-Za-z]:\\|/)[\w.-]+[/\\][\w.\-/\\]*")

#: What a truncated label ends with. One character, and not an escape.
_ELLIPSIS: Final = "…"


def sanitize_label(value: str, maximum: int = 120) -> str:
    """Return one line of plain, bounded, secret-free text.

    Applied to everything a person or another system supplied — a Climb title,
    a Skill name — because those are the fields that reach a rendering without
    having been through a protocol validator that cared what was in them.
    """
    flattened = _WHITESPACE_RUN.sub(" ", _CONTROL.sub(" ", _ANSI.sub("", value)))
    scrubbed = sanitize_text(flattened).strip()
    if len(scrubbed) <= maximum:
        return scrubbed
    return scrubbed[: maximum - 1].rstrip() + _ELLIPSIS


def sanitize_error_summary(error: NormalizedExecutionError, maximum: int = 200) -> str:
    """Summarize one recorded failure in one safe line.

    The traceback is dropped rather than scrubbed. It is the field most likely
    to carry an environment value, and its diagnostic worth is to somebody
    reading the run directory, not to somebody reading a result.
    """
    summary = f"{error.type}: {error.message}" if error.message else error.type
    return sanitize_label(summary, maximum)


def ensure_no_secret_patterns(value: str) -> None:
    """Raise when a string carries something that looks like a credential.

    The scrubber is the authority: if redacting the value would change it, the
    value contains something that must not be shown. Raising rather than
    quietly redacting is deliberate — a presentation that silently swallowed a
    leaked key would hide the fact that one reached this far.
    """
    if sanitize_text(value) == value:
        return
    raise ValidationError(
        "a value bound for a result rendering looks like a credential, so "
        "nothing is rendered",
        code=PRESENTATION_REDACTION_FAILED,
        details={"length": len(value)},
    )


def ensure_no_hidden_task_material(payload: UpliftPresentationPayload) -> None:
    """Check every string in a payload before anything renders it.

    Walks the payload rather than the fields somebody remembered, so a field
    added later is covered the day it is added.
    """
    for path, value in _strings(payload, ""):
        ensure_no_secret_patterns(value)
        if _ANSI.search(value) or _CONTROL.search(value):
            raise ValidationError(
                "a result rendering may not carry terminal control sequences",
                code=PRESENTATION_REDACTION_FAILED,
                details={"field": path},
            )
        if _ABSOLUTE_PATH.search(value):
            raise ValidationError(
                "a result rendering may not name an absolute local path",
                code=PRESENTATION_REDACTION_FAILED,
                details={"field": path},
            )


def _strings(value: object, path: str) -> list[tuple[str, str]]:
    """Return every string inside a payload, with the field it came from."""
    if isinstance(value, str):
        return [(path, value)]
    if isinstance(value, BaseModel):
        found: list[tuple[str, str]] = []
        for name in type(value).model_fields:
            found.extend(_strings(getattr(value, name), f"{path}.{name}".lstrip(".")))
        return found
    if isinstance(value, dict):
        found = []
        for key, item in value.items():
            found.extend(_strings(item, f"{path}[{key}]"))
        return found
    if isinstance(value, list | tuple):
        found = []
        for position, item in enumerate(value):
            found.extend(_strings(item, f"{path}[{position}]"))
        return found
    return []
