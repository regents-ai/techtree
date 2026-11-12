"""Field-by-field scoring of a reply against the gold payment requirements.

Reading is lenient only as far as finding the reply's one JSON object (in a code
fence, after a sentence, wherever it sits). Every field is then compared strictly:
same JSON type, same value. Keys the answer does not have are ignored.
"""

from __future__ import annotations

import json
from typing import Any

Path = tuple[str | int, ...]

FIELDS: tuple[Path, ...] = (
    ("x402Version",),
    ("resource", "url"),
    ("resource", "description"),
    ("resource", "mimeType"),
    ("accepts", 0, "scheme"),
    ("accepts", 0, "network"),
    ("accepts", 0, "amount"),
    ("accepts", 0, "asset"),
    ("accepts", 0, "payTo"),
    ("accepts", 0, "maxTimeoutSeconds"),
    ("accepts", 0, "extra", "name"),
    ("accepts", 0, "extra", "version"),
)
"""Every scored field, by its path in the answer."""

_MISSING = object()


def extract(reply: str) -> dict[str, Any] | None:
    """The one top-level JSON object in `reply`, or None when there is none or more
    than one."""
    decoder = json.JSONDecoder()
    found: list[dict[str, Any]] = []
    position = 0
    while (start := reply.find("{", position)) != -1:
        try:
            value, end = decoder.raw_decode(reply, start)
        except json.JSONDecodeError:
            position = start + 1
            continue
        found.append(value)
        position = end
    return found[0] if len(found) == 1 else None


def _at(value: Any, path: Path) -> Any:
    for step in path:
        if isinstance(step, int):
            if not isinstance(value, list) or len(value) != 1:
                return _MISSING
            value = value[step]
        elif isinstance(value, dict) and step in value:
            value = value[step]
        else:
            return _MISSING
    return value


def _same(got: Any, want: Any) -> bool:
    return type(got) is type(want) and got == want


def correct_fields(reply: str, answer: dict[str, Any]) -> int:
    """How many of the answer's fields the reply gets exactly right. `accepts` counts
    only as a list of exactly one requirement."""
    parsed = extract(reply)
    if parsed is None:
        return 0
    return sum(_same(_at(parsed, path), _at(answer, path)) for path in FIELDS)


def reward(reply: str, answer: dict[str, Any]) -> float:
    """The share of fields right, from 0 to 1."""
    return correct_fields(reply, answer) / len(FIELDS)


def solved(reply: str, answer: dict[str, Any]) -> bool:
    """Every field right."""
    return correct_fields(reply, answer) == len(FIELDS)
