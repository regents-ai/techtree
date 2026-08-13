"""Staging a proposed Skill, and handing it to Techtree. Section 8.13.

A model wrote this Skill, so nothing here trusts it. The plugin writes it to a
file only it can read, hands the path to Techtree's ordinary preparation
command, and lets Techtree do what it does for any candidate Skill: snapshot
it, scan it, hash it, and build a draft. The plugin's copy is deleted as soon
as Techtree owns one.

That order matters for a reason worth stating: the scanner is Techtree's, and
a plugin that pre-approved a Skill it generated would be marking its own
homework. What this file does is plumbing — write it down, pass it over,
clean up.

Nothing about the proposal survives in the plugin. The draft Techtree returns
is what a later turn refers to, and that draft is on disk in Techtree's own
store, not in this process.
"""

from __future__ import annotations

import os
import stat
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from ..errors import PluginError
from ..models import SkillRevisionOutput

CODE_PROPOSAL_PREPARE_FAILED: Final = "skill_revision_prepare_failed"
CODE_PROPOSAL_UNCHANGED: Final = "skill_revision_unchanged"

#: What Techtree must tell us about a prepared replacement before anyone is
#: asked to approve running it. Specification section 8.13.
REQUIRED_REPLACEMENT_FIELDS: Final[tuple[str, ...]] = (
    "draft_id",
    "confirmation_token",
    "data_policy_digest",
    "campaign_spec_digest",
    "baseline_skill_digest",
    "candidate_skill_digest",
    "estimated_episodes",
    "source_run_id",
)

_SKILL_FILENAME: Final = "SKILL.md"
_DIRECTORY_MODE: Final = stat.S_IRWXU
_FILE_MODE: Final = stat.S_IRUSR | stat.S_IWUSR


@dataclass(frozen=True)
class StagedSkill:
    """A proposed Skill on disk, waiting to be handed over."""

    directory: Path
    entrypoint: Path

    def remove(self) -> None:
        """Delete the staged copy and the directory that held it."""
        try:
            self.entrypoint.unlink(missing_ok=True)
            self.directory.rmdir()
        except OSError:
            # A cleanup that fails is worth nothing to shout about: the file
            # is in a private temporary directory and carries no secret.
            return


class ProposalService:
    """Writes a proposed Skill down, and hands it to Techtree to judge."""

    def __init__(self, *, plugin_data_root: Path | None = None, bridge: Any) -> None:
        self._root = plugin_data_root
        self._bridge = bridge

    def write_temporary_skill(
        self, *, demo_id: str, output: SkillRevisionOutput
    ) -> StagedSkill:
        """Write the proposed SKILL.md where only this user can read it."""
        parent = self._root or Path(tempfile.gettempdir())
        parent.mkdir(parents=True, exist_ok=True)
        directory = Path(
            tempfile.mkdtemp(prefix=f"techtree-proposal-{demo_id[:12]}-", dir=parent)
        )
        os.chmod(directory, _DIRECTORY_MODE)

        entrypoint = directory / _SKILL_FILENAME
        entrypoint.write_text(output.revised_skill_markdown, encoding="utf-8")
        os.chmod(entrypoint, _FILE_MODE)
        return StagedSkill(directory=directory, entrypoint=entrypoint)

    def prepare_replacement_draft(
        self, *, source_run_id: str, skill_path: Path, label: str = "revision"
    ) -> dict[str, Any]:
        """Invoke ordinary `techtree uplift prepare` and check what came back.

        Techtree snapshots the Skill, scans it, hashes it, and creates the
        second draft. Everything that decides whether this Skill may run is
        Techtree's, and this never bypasses any of it.
        """
        envelope = self._bridge.invoke(
            [
                "uplift",
                "prepare",
                "--from-run",
                source_run_id,
                "--candidate-skill",
                str(skill_path),
                "--label",
                label,
            ]
        )
        if not envelope.get("ok"):
            raise PluginError(
                _message(envelope, "Techtree would not prepare the revised Skill"),
                code=CODE_PROPOSAL_PREPARE_FAILED,
            )

        data = envelope.get("data")
        if not isinstance(data, Mapping):
            raise PluginError(
                "Techtree's preparation carried no draft to start",
                code=CODE_PROPOSAL_PREPARE_FAILED,
            )

        validate_replacement_response(data, source_run_id)
        return dict(data)

    def remove_temporary_skill(self, staged: StagedSkill) -> None:
        """Delete the plugin's copy once Techtree has its own snapshot."""
        staged.remove()


def validate_replacement_response(
    response: Mapping[str, Any], source_run_id: str
) -> None:
    """Check a prepared replacement says everything approval depends on.

    Raises:
        PluginError: when a field a person needs before approving is missing,
            when the draft belongs to another run, or when the two Skills turn
            out to be the same text after all.
    """
    missing = [name for name in REQUIRED_REPLACEMENT_FIELDS if not response.get(name)]
    if missing:
        raise PluginError(
            f"this prepared comparison does not say {missing}, which a person "
            "needs before approving it",
            code=CODE_PROPOSAL_PREPARE_FAILED,
        )

    if response["source_run_id"] != source_run_id:
        raise PluginError(
            "this prepared comparison belongs to a different run",
            code=CODE_PROPOSAL_PREPARE_FAILED,
        )

    if response["baseline_skill_digest"] == response["candidate_skill_digest"]:
        raise PluginError(
            "the revised Skill is identical to the one that was measured, so "
            "there is nothing to compare",
            code=CODE_PROPOSAL_UNCHANGED,
            repair="Read the proposal's rationale; no change was actually made.",
        )


def _message(envelope: Mapping[str, Any], fallback: str) -> str:
    error = envelope.get("error")
    if isinstance(error, Mapping) and isinstance(error.get("message"), str):
        return str(error["message"])
    return fallback
