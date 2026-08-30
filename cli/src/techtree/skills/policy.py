"""What a candidate skill is allowed to be. Spec section 15.1.

The policy is the whole answer to "may this directory be submitted?", stated as
data rather than as conditionals spread through the scanner. It is frozen, so a
scan cannot widen the rules it was handed partway through.

Every limit here exists for a reason a participant can be told:

* An instruction skill is text a model reads. Only text suffixes are allowed,
  which is also what makes secret scanning meaningful — bytes nobody can read
  cannot be checked.
* ``SKILL.md`` must exist, because that is the entrypoint the harness loads.
* Hidden files are excluded rather than filtered. ``.env``, ``.git``, and
  editor state are the usual accidental contents of a skill directory, and
  quietly dropping them would make the snapshot disagree with what the
  participant sees on disk.
* Symlinks are excluded because a link's meaning depends on the machine it is
  read on, and a snapshot must mean the same thing everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from techtree.constants import (
    ALLOWED_SKILL_SUFFIXES,
    MAX_SKILL_FILE_BYTES,
    MAX_SKILL_FILES,
    MAX_SKILL_TOTAL_BYTES,
)
from techtree.models.skill import SKILL_ENTRY_FILE

__all__ = [
    "SkillPolicy",
    "default_instruction_skill_policy",
]


@dataclass(frozen=True)
class SkillPolicy:
    """The limits a candidate skill directory is validated against."""

    allowed_suffixes: frozenset[str] = field(default=ALLOWED_SKILL_SUFFIXES)
    maximum_files: int = MAX_SKILL_FILES
    maximum_file_bytes: int = MAX_SKILL_FILE_BYTES
    maximum_total_bytes: int = MAX_SKILL_TOTAL_BYTES
    required_entrypoint: str = SKILL_ENTRY_FILE
    allow_symlinks: bool = False
    allow_hidden_files: bool = False


def default_instruction_skill_policy() -> SkillPolicy:
    """Return v0.1 Markdown instruction-skill policy."""
    return SkillPolicy(
        allowed_suffixes=ALLOWED_SKILL_SUFFIXES,
        maximum_files=MAX_SKILL_FILES,
        maximum_file_bytes=MAX_SKILL_FILE_BYTES,
        maximum_total_bytes=MAX_SKILL_TOTAL_BYTES,
        required_entrypoint=SKILL_ENTRY_FILE,
        allow_symlinks=False,
        allow_hidden_files=False,
    )
