"""The founder-supplied starter Skill. Specification section 7.10.

The introductory comparison runs a Skill the founder wrote, materialized by
Techtree from the pinned public release and checked against the digest the
release names. The plugin never downloads it, never accepts a URL for it, and
never treats a Skill it cannot verify as the starter Skill.

Every release names both founder Skills concretely (Techtree decisions
document 0026), so there is no "not chosen yet" state to handle here — what is
left is the check that matters: the bytes on disk must be the bytes the release
pinned, or they are not read out to anybody.

Obtaining one is Techtree's job and is asked for by name: ``skill starter``,
across the ordinary CLI boundary, with no options. Techtree resolves it from
the address its own release publishes, reuses a copy already on the machine,
scans it, and proves it against the digest that release pins. What comes back
is then proved a second time here, against the release *this build* carries,
because a Skill that satisfied some other release is not the one this
comparison is about.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, Protocol

from ..constants import (
    MAX_STARTER_SKILL_BYTES,
    PLUGIN_ROOT,
    SKILL_ENTRY_FILENAME,
    SKILLS_DIRNAME,
)
from ..errors import (
    CODE_FOUNDER_SKILL_DIGEST_MISMATCH,
    CODE_FOUNDER_SKILL_MISSING,
    PluginError,
    contains_secret_material,
)
from ..models import ReleaseCore

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
        envelope = services.bridge.invoke(list(STARTER_SKILL_ARGUMENTS))
        if not envelope.get("ok"):
            raise PluginError(_cli_message(envelope), code=_cli_code(envelope))

        data = envelope.get("data")
        if not isinstance(data, dict):
            raise PluginError(
                "Techtree answered the starter Skill command with nothing to read",
                code=CODE_STARTER_SKILL_UNAVAILABLE,
            )
        return dict(data)


def _cli_message(envelope: Mapping[str, Any]) -> str:
    """Return Techtree's own words about a failure, when it wrote any."""
    error = envelope.get("error")
    if isinstance(error, Mapping) and isinstance(error.get("message"), str):
        return str(error["message"])
    return "Techtree could not put the starter Skill this release pins on this machine"


def _cli_code(envelope: Mapping[str, Any]) -> str:
    """Return Techtree's own code for a failure, when it named one."""
    error = envelope.get("error")
    code = error.get("code") if isinstance(error, Mapping) else None
    if isinstance(code, str) and code:
        return code
    return CODE_STARTER_SKILL_UNAVAILABLE


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
            repair="Reinstall the pinned Techtree release.",
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


# Founder Skills ---------------------------------------------------------------
#
# One Skill the founder writes and the release pins: the one that proposes a
# revision. It is read-only, namespaced, and used only after its bytes have
# been checked against the digest the release names.
#
# Nothing here reads whatever happens to be on disk under that name: the bytes
# are hashed and compared against the release's digest first. Test fixtures
# follow the same contract and live with the suite, in the Techtree
# repository, where they cannot be mistaken for the real thing.

FounderSkillName = Literal["skill-improver"]

#: Which release coordinate names each founder Skill's digest.
FOUNDER_SKILL_DIGEST_FIELDS: Final[dict[str, str]] = {
    "skill-improver": "skill_improver_digest",
}


def founder_skill_path(name: str, root: Path = PLUGIN_ROOT) -> Path:
    """Return where a bundled founder Skill lives."""
    return root / SKILLS_DIRNAME / name / SKILL_ENTRY_FILENAME


def file_digest(raw: bytes) -> str:
    """Return the digest a Skill file is named by."""
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def load_bundled_skill_text(name: str, root: Path = PLUGIN_ROOT) -> str:
    """Return one bundled Skill's text, refusing anything unusable.

    Raises:
        PluginError: when the file is absent, empty, larger than the reviewed
            size, or carries something that looks like a credential.
    """
    if name not in FOUNDER_SKILL_DIGEST_FIELDS:
        raise PluginError(
            f"{name!r} is not a founder Skill", code=CODE_FOUNDER_SKILL_MISSING
        )

    path = founder_skill_path(name, root)
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise PluginError(
            f"this build does not bundle the {name} Skill",
            code=CODE_FOUNDER_SKILL_MISSING,
            repair="Use a published release of the plugin.",
        ) from error

    if not raw.strip():
        raise PluginError(
            f"the bundled {name} Skill is empty",
            code=CODE_FOUNDER_SKILL_MISSING,
        )
    if len(raw) > MAX_STARTER_SKILL_BYTES:
        raise PluginError(
            f"the bundled {name} Skill is {len(raw)} bytes, larger than the "
            f"{MAX_STARTER_SKILL_BYTES} that were reviewed",
            code=CODE_FOUNDER_SKILL_MISSING,
        )

    text = raw.decode("utf-8", errors="replace")
    if contains_secret_material(text):
        raise PluginError(
            f"the bundled {name} Skill carries something that looks like a "
            "credential, so it will not be read out to a model",
            code=CODE_FOUNDER_SKILL_MISSING,
        )
    return text


def bundled_skill_digest(name: str, root: Path = PLUGIN_ROOT) -> str:
    """Return the digest of the bundled Skill's bytes."""
    load_bundled_skill_text(name, root)
    return file_digest(founder_skill_path(name, root).read_bytes())


def expected_founder_skill_digest(release: ReleaseCore, name: str) -> str:
    """Return the digest the release names for one founder Skill."""
    field = FOUNDER_SKILL_DIGEST_FIELDS.get(name)
    if field is None:
        raise PluginError(
            f"{name!r} is not a founder Skill", code=CODE_FOUNDER_SKILL_MISSING
        )
    return str(getattr(release, field))


def load_verified_founder_skill(
    release: ReleaseCore, name: str, root: Path = PLUGIN_ROOT
) -> str:
    """Return a founder Skill's text, only if it is the one the release names.

    Raises:
        PluginError: when the bundled bytes are not the bytes the release
            pinned.
    """
    text = load_bundled_skill_text(name, root)
    actual = file_digest(founder_skill_path(name, root).read_bytes())
    expected = expected_founder_skill_digest(release, name)
    if actual != expected:
        raise PluginError(
            f"the bundled {name} Skill is not the one this release names",
            code=CODE_FOUNDER_SKILL_DIGEST_MISMATCH,
            repair="Reinstall the plugin at its published commit.",
        )
    return text


def verify_founder_skill_digests(
    release: ReleaseCore, root: Path = PLUGIN_ROOT
) -> None:
    """Check every founder Skill before a release may be used.

    Raises:
        PluginError: naming the first Skill that is missing, altered, empty,
            oversized, or carrying credential-like content.
    """
    for name in sorted(FOUNDER_SKILL_DIGEST_FIELDS):
        load_verified_founder_skill(release, name, root)


# The Skill a run was measured with ------------------------------------------------


@dataclass(frozen=True)
class VerifiedSkill:
    """One Skill's text, and what was checked before it was read out."""

    name: str
    entrypoint: Path
    text: str
    entrypoint_digest: str
    root_digest: str


def read_verified_skill(
    directory: Path, *, expected_entrypoint_digest: str, root_digest: str
) -> VerifiedSkill:
    """Read a Skill from a snapshot, refusing bytes that are not the ones named.

    Decision 0007 R2: the improvement context pins the Skill by digest, and the
    text itself is supplied separately. This is the step in between — the bytes
    are read, hashed, and compared before anything is shown to a model, so the
    text a proposal was made against is provably the text the run measured.
    """
    entrypoint = directory / SKILL_ENTRY_FILENAME
    try:
        raw = entrypoint.read_bytes()
    except OSError as error:
        raise PluginError(
            "the run's own copy of its Skill has no SKILL.md to read",
            code=CODE_FOUNDER_SKILL_MISSING,
        ) from error

    actual = file_digest(raw)
    if not expected_entrypoint_digest:
        raise PluginError(
            "a Skill cannot be read out without the digest that says which Skill it is",
            code=CODE_FOUNDER_SKILL_DIGEST_MISMATCH,
        )
    if actual != expected_entrypoint_digest:
        raise PluginError(
            "the Skill in this snapshot is not the Skill the run measured",
            code=CODE_FOUNDER_SKILL_DIGEST_MISMATCH,
            repair="Rebuild the improvement context from the run.",
        )

    text = raw.decode("utf-8", errors="replace")
    if contains_secret_material(text):
        raise PluginError(
            "this Skill carries something that looks like a credential, so it "
            "will not be read out to a model",
            code=CODE_FOUNDER_SKILL_MISSING,
        )
    return VerifiedSkill(
        name=directory.name,
        entrypoint=entrypoint,
        text=text,
        entrypoint_digest=actual,
        root_digest=root_digest,
    )


#: What the improvement context pins about the Skill a run measured.
CODE_SOURCE_SKILL_UNAVAILABLE: Final = "source_skill_snapshot_unavailable"


@dataclass(frozen=True)
class SourceSkillReference:
    """The Skill a finished run measured, named by digest rather than by path."""

    source_run_id: str
    parent_skill_digest: str
    campaign_spec_digest: str
    data_policy_digest: str


def source_skill_reference(envelope: Any) -> SourceSkillReference:
    """Read what the improvement context pins about the Skill it describes.

    Decision 0007 R2: the context carries digests, not Skill text. This is the
    half of the protocol Techtree already answers.
    """
    if isinstance(envelope, dict) and envelope.get("ok") is False:
        error = envelope.get("error")
        message = (
            error.get("message")
            if isinstance(error, dict)
            else "Techtree could not build an improvement context"
        )
        raise PluginError(str(message), code=CODE_SOURCE_SKILL_UNAVAILABLE)

    data = envelope.get("data") if isinstance(envelope, dict) else None
    context = data.get("context") if isinstance(data, dict) else None
    if not isinstance(context, dict):
        raise PluginError(
            "this is not an improvement context",
            code=CODE_SOURCE_SKILL_UNAVAILABLE,
        )

    missing = [
        name
        for name in (
            "source_run_id",
            "parent_skill_digest",
            "campaign_spec_digest",
            "data_policy_digest",
        )
        if not isinstance(context.get(name), str) or not context[name]
    ]
    if missing:
        raise PluginError(
            f"this improvement context does not pin {missing}",
            code=CODE_SOURCE_SKILL_UNAVAILABLE,
        )

    return SourceSkillReference(
        source_run_id=context["source_run_id"],
        parent_skill_digest=context["parent_skill_digest"],
        campaign_spec_digest=context["campaign_spec_digest"],
        data_policy_digest=context["data_policy_digest"],
    )


def resolve_source_skill(services: Any, run_id: str) -> VerifiedSkill:
    """Return the verified text of the Skill a finished run measured.

    Decision 0007 R2 asks the plugin to resolve the run's own copy of its
    Skill, re-verify it, and read SKILL.md. The first step is the one Techtree
    has to answer: the run owns that copy, and no committed machine command
    reports where it is or what its entrypoint digest should be. Constructing
    the path from Techtree's internal layout would be a second implementation
    of something Techtree owns, and one that breaks silently the day the
    layout changes.

    Raises:
        PluginError: naming exactly what the CLI would have to expose.
    """
    reference = source_skill_reference(
        services.bridge.invoke(["uplift", "context", run_id])
    )
    raise PluginError(
        "Techtree does not yet report where this run keeps its own verified "
        f"copy of the Skill it measured ({reference.parent_skill_digest}), so "
        "the text cannot be read out and checked",
        code=CODE_SOURCE_SKILL_UNAVAILABLE,
        repair=(
            "Needs a machine-readable snapshot path and entrypoint digest from "
            "the Techtree CLI."
        ),
    )
