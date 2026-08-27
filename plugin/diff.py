"""What changed between two Skills. Specification section 8.14.

Before anyone spends money comparing a revised Skill against the one it came
from, they see exactly what is different. Not a summary of what is different —
the difference itself, computed here from the two texts, byte for byte.

The host model is allowed to talk about a diff. It is not allowed to be the
diff: whatever it says appears beside this, and this is what a person is
actually shown. That is the same rule the numbers follow, for the same reason.

A phone cannot hold a long diff, so it gets the first hunks and is told, in
the answer itself, how much was left out and where to see the rest. A
truncation nobody announced would be a diff that lies by omission.
"""

from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass
from typing import Any, Final

from .channels import ensure_gateway_safe, is_gateway_safe_required
from .models import ChannelKind

#: What a phone gets before the rest is left out, stated.
GATEWAY_DIFF_LINES: Final = 40

#: What a terminal gets before even it is bounded. A Skill is a small file;
#: anything past this is a sign something went wrong rather than a long diff.
TERMINAL_DIFF_LINES: Final = 600

_V1_LABEL: Final = "Skill v1 (measured)"
_V2_LABEL: Final = "Skill v2 (proposed)"


@dataclass(frozen=True)
class SkillDiff:
    """The deterministic difference between two Skills."""

    added_lines: int
    removed_lines: int
    unified: str
    truncated_lines: int
    v1_digest: str
    v2_digest: str
    diff_digest: str

    @property
    def changed_lines(self) -> int:
        """How many lines differ in total."""
        return self.added_lines + self.removed_lines

    @property
    def is_empty(self) -> bool:
        """Whether the two Skills are the same text."""
        return self.changed_lines == 0

    def to_dict(self) -> dict[str, Any]:
        """Return the diff in the shape a result carries it."""
        payload: dict[str, Any] = {
            "added_lines": self.added_lines,
            "removed_lines": self.removed_lines,
            "changed_lines": self.changed_lines,
            "unified": self.unified,
            "v1_digest": self.v1_digest,
            "v2_digest": self.v2_digest,
            "diff_digest": self.diff_digest,
            "truncated": self.truncated_lines > 0,
        }
        if self.truncated_lines:
            payload["truncated_lines"] = self.truncated_lines
            payload["see_all_of_it"] = (
                "Run `hermes techtree result <run-id>` in a terminal, or read "
                "the two Skills, to see the whole difference."
            )
        return payload


def build_skill_diff(
    *,
    v1_text: str,
    v2_text: str,
    channel: ChannelKind = ChannelKind.UNKNOWN,
) -> SkillDiff:
    """Return the difference between two Skills, deterministically.

    The same two texts always produce the same diff and the same diff digest,
    on any machine, so what a person approved can be checked afterwards
    against what was actually run.
    """
    v1_lines = v1_text.splitlines(keepends=True)
    v2_lines = v2_text.splitlines(keepends=True)

    full = list(
        difflib.unified_diff(
            v1_lines, v2_lines, fromfile=_V1_LABEL, tofile=_V2_LABEL, n=3
        )
    )
    added = sum(
        1 for line in full if line.startswith("+") and not line.startswith("+++")
    )
    removed = sum(
        1 for line in full if line.startswith("-") and not line.startswith("---")
    )

    budget = (
        GATEWAY_DIFF_LINES if is_gateway_safe_required(channel) else TERMINAL_DIFF_LINES
    )
    shown = full[:budget]
    truncated = max(0, len(full) - len(shown))
    unified = ensure_gateway_safe("".join(shown))
    if truncated:
        unified += f"\n… {truncated} more diff lines are not shown here.\n"

    return SkillDiff(
        added_lines=added,
        removed_lines=removed,
        unified=unified,
        truncated_lines=truncated,
        v1_digest=text_digest(v1_text),
        v2_digest=text_digest(v2_text),
        diff_digest=_digest("".join(full)),
    )


def text_digest(text: str) -> str:
    """Return the digest of one Skill's text."""
    return _digest(text)


def _digest(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"
