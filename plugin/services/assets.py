"""The founder-supplied starter Skill. Specification section 7.10.

The introductory comparison runs a Skill the founder wrote, materialized by
Techtree from the pinned public release and checked against the digest the
release names. The plugin never downloads it, never accepts a URL for it, and
never treats a Skill it cannot verify as the starter Skill.

Today no release names one. The three founder Skills are the last unchosen
release coordinates, so this build's release carries placeholder digests for
them, and the installed Techtree ships no command that would hand one over.
Rather than guess at either, this says so exactly: the guided introduction
stops with a reason a person can act on.
"""

from __future__ import annotations

from typing import Any, Final, Protocol

from ..errors import PluginError
from ..models import ReleaseCore

#: The digest a release carries where a Skill has not been chosen yet.
PLACEHOLDER_DIGEST: Final = "sha256:" + "0" * 64

CODE_STARTER_SKILL_MISSING: Final = "starter_skill_missing"
CODE_STARTER_SKILL_DIGEST_MISMATCH: Final = "starter_skill_digest_mismatch"


class StarterSkill(Protocol):
    """Where the starter Skill is, and what proves it is the right one."""

    path: str
    digest: str


class SkillProvider(Protocol):
    """How the plugin obtains the founder-supplied starter Skill."""

    def materialize(self, services: Any) -> dict[str, Any]:
        """Return the local path and verified digest of starter Skill v1."""


class ReleaseSkillProvider:
    """Asks Techtree for the starter Skill named by this build's release."""

    def materialize(self, services: Any) -> dict[str, Any]:
        """Return the starter Skill, or explain why there is not one yet.

        Raises:
            PluginError: with ``starter_skill_missing`` when this release does
                not name a starter Skill.
        """
        release: ReleaseCore = services.release_core
        if not names_a_starter_skill(release):
            raise PluginError(
                "this plugin build's release does not name a starter Skill yet, "
                "so the guided introduction cannot prepare one",
                code=CODE_STARTER_SKILL_MISSING,
                repair="Use a published release, or prepare your own Skill.",
            )
        raise PluginError(
            "the installed Techtree does not offer a way to materialize the "
            "starter Skill this release names",
            code=CODE_STARTER_SKILL_MISSING,
            repair="Update Techtree to the version this plugin release pins.",
        )


def names_a_starter_skill(release: ReleaseCore) -> bool:
    """Whether this release has chosen its starter Skill."""
    return (
        not release.placeholder_release
        and release.starter_skill_digest != PLACEHOLDER_DIGEST
        and "starter_skill_digest" not in release.placeholder_fields
    )


def verify_starter_skill_result(result: dict[str, Any], release: ReleaseCore) -> None:
    """Check a materialized Skill against the digest the release names.

    Raises:
        PluginError: when the answer carries no digest, or a different one.
    """
    digest = result.get("digest")
    if not isinstance(digest, str) or not digest:
        raise PluginError(
            "the starter Skill was returned without a digest to check it by",
            code=CODE_STARTER_SKILL_DIGEST_MISMATCH,
        )
    if digest != release.starter_skill_digest:
        raise PluginError(
            "the starter Skill that was materialized is not the one this release names",
            code=CODE_STARTER_SKILL_DIGEST_MISMATCH,
            repair="Reinstall the pinned Techtree release.",
        )
    path = result.get("path")
    if not isinstance(path, str) or not path:
        raise PluginError(
            "the starter Skill was returned without a local path",
            code=CODE_STARTER_SKILL_MISSING,
        )


def materialize_starter_skill(services: Any) -> dict[str, Any]:
    """Materialize starter Skill v1 and verify it against the release."""
    result: dict[str, Any] = services.assets.materialize(services)
    verify_starter_skill_result(result, services.release_core)
    return result
