"""Where an answer is going to be read. Specification sections 6.1, 7.8.

A terminal and a phone are not the same room. A terminal can take Techtree's
own rendered output; a phone gets text that a chat app will not mangle, and
never a control character that means something to a terminal emulator.

The plugin does not guess which one it is talking to. It uses an explicit hint
when a caller gives one, a documented host field if the host ever provides
one, and otherwise treats the answer as if a phone were reading it. Guessing
from the operating system would be worse than useless: the same host serves
both at once.

Everything here is about shape and size, never about truth. Bounding an answer
may drop detail, and when it does it says so; it never changes a number, a
verdict, or a status.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Final

from .errors import CODE_CHANNEL_INVALID, ChannelError
from .models import ChannelKind

#: Control characters that never belong in an answer: the escape that starts
#: an ANSI sequence, NUL, and the C1 range, plus the rest of C0 apart from the
#: tab and newline that ordinary text uses.
_UNSAFE_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")

#: How much text a gateway answer may carry before it is cut, with the cut
#: stated. Chat apps split or drop long messages, and a silently split proof
#: summary is a misleading proof summary.
GATEWAY_TEXT_LIMIT: Final = 3500

#: What a truncated gateway answer ends with, so nobody mistakes a cut for the
#: end of the story.
TRUNCATION_NOTE: Final = (
    "\n\n… truncated. Ask for the part you need, or use the terminal."
)

#: Host callback fields that would state the channel. Hermes 0.20.0 documents
#: none — its slash commands and tool calls look identical from a terminal and
#: from a phone — so nothing is inferred from a callback today. The lookup is
#: here so that the day a host documents one, this is the only edit.
DOCUMENTED_CHANNEL_KEYS: Final[tuple[str, ...]] = ()


def resolve_channel(
    explicit: str | None, callback_context: Mapping[str, Any] | None = None
) -> ChannelKind:
    """Return the channel to answer for.

    An explicit hint wins, a documented host field comes second, and anything
    else is unknown — which is treated exactly like a gateway.

    Raises:
        ChannelError: when a caller names a channel that does not exist.
    """
    if explicit is not None:
        if not isinstance(explicit, str):
            raise ChannelError("a channel must be named as text")
        try:
            return ChannelKind(explicit.strip().lower())
        except ValueError as error:
            raise ChannelError(
                f"{explicit!r} is not a channel; use terminal, gateway, or unknown",
                code=CODE_CHANNEL_INVALID,
            ) from error

    for key in DOCUMENTED_CHANNEL_KEYS:
        value = (callback_context or {}).get(key)
        if isinstance(value, str):
            try:
                return ChannelKind(value.strip().lower())
            except ValueError:
                continue

    return ChannelKind.UNKNOWN


def is_gateway_safe_required(channel: ChannelKind) -> bool:
    """Whether this channel must receive compact, control-free text.

    Unknown counts as yes. An answer that is safe for a phone is also fine in
    a terminal; the reverse is not true, so the doubt resolves that way.
    """
    return channel is not ChannelKind.TERMINAL


def ensure_gateway_safe(value: str) -> str:
    """Return text with nothing in it that a display would obey.

    Escape sequences, NUL, and other control characters are removed rather
    than escaped: they carry no meaning worth keeping in an answer, and one of
    them reaching a terminal would let borrowed output redraw someone's screen.
    """
    if not isinstance(value, str):
        raise ChannelError("only text can be made safe to display")
    return _UNSAFE_CONTROL.sub("", value)


def bounded_gateway_text(value: str, maximum_chars: int = GATEWAY_TEXT_LIMIT) -> str:
    """Return text no longer than the limit, saying so when it was cut.

    The cut is made at a whitespace boundary where there is one nearby, so a
    word — or a digest — is not split in half and misread.
    """
    safe = ensure_gateway_safe(value)
    if len(safe) <= maximum_chars:
        return safe

    budget = max(0, maximum_chars - len(TRUNCATION_NOTE))
    cut = safe[:budget]
    boundary = cut.rfind("\n")
    if boundary < budget - 200:
        boundary = cut.rfind(" ")
    if boundary > 0:
        cut = cut[:boundary]
    return cut.rstrip() + TRUNCATION_NOTE
