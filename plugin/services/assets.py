"""The founder-supplied starter Skill. Specification section 7.10.

The introductory comparison runs a Skill the founder wrote, materialized by
Techtree from the pinned public release and checked against the digest the
release names. The plugin never downloads it, never accepts a URL for it, and
never treats a Skill it cannot verify as the starter Skill.

Today no release names one. The two founder Skills are the last unchosen
release coordinates, so this build's release carries placeholder digests for
them, and the installed Techtree ships no command that would hand one over.
Rather than guess at either, this says so exactly: the guided introduction
stops with a reason a person can act on.
"""

from __future__ import annotations

import hashlib
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

#: The digest a release carries where a Skill has not been chosen yet.
PLACEHOLDER_DIGEST: Final = "sha256:" + "0" * 64

#: The address a release carries where nobody has published the starter Skill
#: yet. `.invalid` is reserved by RFC 2606 so it can never resolve: the value
#: is well formed, obviously unchosen, and unfetchable by design.
PLACEHOLDER_OBJECT_URL: Final = "https://placeholder.invalid/unchosen"

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
    """Whether this release has chosen its starter Skill.

    Both halves of the coordinate have to be bound. The digest says which
    Skill the release measured; the URL says where a machine that does not
    already hold those bytes obtains them. A digest with no address names a
    Skill nobody can fetch, and an address with no digest is an invitation to
    run whatever is served — so neither on its own is a chosen starter Skill.
    """
    return (
        not release.placeholder_release
        and release.starter_skill_digest != PLACEHOLDER_DIGEST
        and "starter_skill_digest" not in release.placeholder_fields
        and release.starter_skill_object_url != PLACEHOLDER_OBJECT_URL
        and "starter_skill_object_url" not in release.placeholder_fields
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


# Founder Skills ---------------------------------------------------------------
#
# One Skill the founder writes and the release pins: the one that proposes a
# revision. It is read-only, namespaced, and used only after its bytes have
# been checked against the digest the release names.
#
# This build's release carries a placeholder digest for it (decision 0007 R10),
# so every function here refuses rather than reading whatever happens to be on
# disk under that name. Test fixtures follow the same contract and live under
# tests/, where they cannot be mistaken for the real thing.

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


def names_a_founder_skill(release: ReleaseCore, name: str) -> bool:
    """Whether the release has chosen this Skill yet."""
    field = FOUNDER_SKILL_DIGEST_FIELDS[name]
    return (
        expected_founder_skill_digest(release, name) != PLACEHOLDER_DIGEST
        and field not in release.placeholder_fields
    )


def load_verified_founder_skill(
    release: ReleaseCore, name: str, root: Path = PLUGIN_ROOT
) -> str:
    """Return a founder Skill's text, only if it is the one the release names.

    Raises:
        PluginError: when the release names no such Skill yet, or when the
            bundled bytes are not the bytes the release pinned.
    """
    if not names_a_founder_skill(release, name):
        raise PluginError(
            f"this release has not chosen its {name} Skill yet",
            code=CODE_FOUNDER_SKILL_MISSING,
            repair="Use a published release of the plugin.",
        )

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
