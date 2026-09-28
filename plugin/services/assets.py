"""The founder-supplied starter Skill. Specification section 7.10.

The introductory comparison runs a Skill the founder wrote, materialized by
Techtree from the pinned public release and checked against the digest the
release names. The plugin never downloads it, never accepts a URL for it, and
never treats a Skill it cannot verify as the starter Skill.

Every release names the starter Skill concretely (Techtree decisions
document 0026), so there is no "not chosen yet" state to handle here — what is
left is the check that matters: the bytes on disk must be the bytes the release
pinned, or they are not read out to anybody.

Obtaining one is Techtree's job and is asked for by name: ``skill starter``,
across the ordinary regents boundary, with no options. Techtree resolves it from
the address its own release publishes, reuses a copy already on the machine,
scans it, and proves it against the digest that release pins. What comes back
is then proved a second time here, against the release *this build* carries,
because a Skill that satisfied some other release is not the one this
comparison is about.
"""

from __future__ import annotations

from typing import Any, Final, Protocol

from ..cli.errors import PluginError
from .models import ReleaseCore, answer_error, is_success

#: Nothing usable came back about the pinned starter Skill, and Techtree did
#: not say why in its own words.
CODE_STARTER_SKILL_UNAVAILABLE: Final = "starter_skill_unavailable"
CODE_STARTER_SKILL_DIGEST_MISMATCH: Final = "starter_skill_digest_mismatch"

#: The read-only Techtree command that puts the starter Skill this release
#: pins on this machine and says where it landed. It downloads nothing the
#: release did not already name, and reuses a copy that is already here.
STARTER_SKILL_ARGUMENTS: Final = ("skill", "starter")


class SkillProvider(Protocol):
    """How the plugin obtains the founder-supplied starter Skill."""

    def materialize(self, services: Any) -> dict[str, Any]:
        """Return what Techtree said about the starter Skill on this machine."""


class ReleaseSkillProvider:
    """Asks Techtree for the starter Skill named by this build's release.

    The answer is Techtree's own payload, returned unchanged: where the Skill
    is, the tree digest it was verified against, and the short label a
    comparison carrying it is filed under. Renaming any of those here would
    only give the same facts a second set of names to drift between.
    """

    def materialize(self, services: Any) -> dict[str, Any]:
        """Return Techtree's own answer about the pinned starter Skill.

        Raises:
            PluginError: carrying Techtree's own code and sentence when the
                command failed. Nothing is diagnosed here on Techtree's
                behalf — it knows why it could not hand a Skill over, and
                repeating what it said is the only honest thing to report.
        """
        answer = services.bridge.invoke(list(STARTER_SKILL_ARGUMENTS))
        if not is_success(answer):
            error = answer_error(answer)
            raise PluginError(str(error["message"]), code=str(error["code"]))
        return dict(answer)


def verify_starter_skill_result(result: dict[str, Any], release: ReleaseCore) -> None:
    """Check a materialized Skill against the digest the release names.

    Techtree verifies the Skill against its own release document before it
    keeps a copy. This is the second half of that, made on the plugin's side:
    the tree digest that came back has to be the one *this* build's release
    names, or the Skill is refused however well it verified elsewhere.

    Raises:
        PluginError: when the answer carries no digest, a different one, or
            leaves out something preparing the comparison needs.
    """
    digest = result.get("skill_root_digest")
    if not isinstance(digest, str) or not digest:
        raise PluginError(
            "the starter Skill was returned without a digest to check it by",
            code=CODE_STARTER_SKILL_DIGEST_MISMATCH,
        )
    if digest != release.starter_skill_digest:
        raise PluginError(
            "the starter Skill that was materialized is not the one this release names",
            code=CODE_STARTER_SKILL_DIGEST_MISMATCH,
            repair="Reinstall the regents-cli version this plugin release pins.",
        )
    path = result.get("skill_path")
    if not isinstance(path, str) or not path:
        raise PluginError(
            "the starter Skill was returned without a local path",
            code=CODE_STARTER_SKILL_UNAVAILABLE,
        )
    label = result.get("candidate_label")
    if not isinstance(label, str) or not label:
        raise PluginError(
            "the starter Skill was returned without the label its comparison "
            "is filed under",
            code=CODE_STARTER_SKILL_UNAVAILABLE,
        )


def materialize_starter_skill(services: Any) -> dict[str, Any]:
    """Materialize starter Skill v1 and verify it against the release."""
    result: dict[str, Any] = services.assets.materialize(services)
    verify_starter_skill_result(result, services.release_core)
    return result
