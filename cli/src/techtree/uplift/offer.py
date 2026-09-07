"""What the improvement loop cannot name yet, written once.

Two surfaces reach the same dead end — a finished result, and the improvement
context exported from one — and both reach it for the same reason: the next
step in the loop is a comparison against a revision of the Skill, and nobody
has written the revision. Its path is the one argument ``uplift prepare``
cannot be called without.

A next action carries the exact arguments to invoke it with, so an action with
a placeholder where a path belongs is not an action at all: nothing can run it,
and a caller that tried would hand Techtree the word it was standing in for.
What the envelope says instead is that the input is missing, by name, with no
step offered against it. Saying so in one place is what keeps the two surfaces
from saying it two ways.
"""

from __future__ import annotations

from techtree.models.cli import CliUnknown

__all__ = ["revision_not_written_yet"]


def revision_not_written_yet() -> CliUnknown:
    """Return the input the next comparison needs and nobody has supplied."""
    return CliUnknown(
        id="candidate_skill_path",
        subject=None,
        reason=(
            "No revised Skill exists yet, so the next comparison has no "
            "candidate to name."
        ),
        resolvable_by=None,
    )
