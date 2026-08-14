"""Shared construction for the starter-Skill tests. Decisions 0007 R10, 0008.

Two pieces both the unit tests and the fetch tests need.

:func:`tree_digest` computes a directory's Skill root digest here, from the
files' own bytes, rather than asking the code under test what it thinks. It is
the same construction the manifest builder uses, which is the definition
decisions document 0008 pins a starter Skill by.

:func:`release_pinning` builds a ReleaseCore that has chosen a starter Skill.
This build's own release has not — every Skill digest in it is still a
placeholder — so a test that used the packaged document could only ever
exercise the refusal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from techtree.canonical import sha256_digest_bytes
from techtree.manifests.builder import skill_content_digest
from techtree.models.base import Digest
from techtree.models.skill import SkillFile
from techtree.release.models import (
    PLACEHOLDER_COMMIT,
    PLACEHOLDER_DIGEST,
    PLACEHOLDER_OBJECT_URL,
    PLACEHOLDER_VALUES,
    PLACEHOLDER_VERSION,
    ReleaseCore,
    declared_placeholder_fields,
)

REPOSITORY_ROOT: Final = Path(__file__).resolve().parent.parent
SKILL_FIXTURES: Final = REPOSITORY_ROOT / "fixtures" / "skills"

#: The single-file BranchCode Skill, which is the shape decisions 0007 R4
#: gives the starter Skill: one SKILL.md with one defect in it.
STARTER_FIXTURE: Final = SKILL_FIXTURES / "branch-code-v1"


def tree_digest(root: Path) -> Digest:
    """Return one directory's Skill root digest, computed independently."""
    entries = [
        SkillFile(
            path=path.relative_to(root).as_posix(),
            media_type="text/markdown",
            size=len(path.read_bytes()),
            digest=sha256_digest_bytes(path.read_bytes()),
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]
    return skill_content_digest(entries)


def release_pinning(starter: Digest, object_url: str | None = None) -> ReleaseCore:
    """Return a ReleaseCore that pins one starter Skill and invents nothing.

    Every other unchosen coordinate keeps its placeholder spelling, so the
    document declares exactly what it has decided — which is what makes it a
    legitimate stand-in for the release that will pin a real Skill.

    ``object_url`` is the address the release publishes that Skill at. It
    defaults to unchosen, because pinning which bytes count and publishing them
    are two separate decisions and most tests only need the first.
    """
    values = {
        "cli_source_commit": PLACEHOLDER_COMMIT,
        "cli_version": PLACEHOLDER_VERSION,
        "maximum_tested_host_hermes_version": PLACEHOLDER_VERSION,
        "minimum_host_hermes_version": "0.19.0",
        "release_id": PLACEHOLDER_VERSION,
        "skill_improver_digest": PLACEHOLDER_DIGEST,
        "starter_skill_digest": starter,
        "starter_skill_object_url": object_url or PLACEHOLDER_OBJECT_URL,
    }
    placeholders = declared_placeholder_fields(values)
    return ReleaseCore(
        schema_version="techtree.release-core.v1",
        placeholder_release=bool(placeholders),
        placeholder_fields=placeholders,
        protocol_version="v1alpha1",
        engine_digest=f"sha256:{'e' * 64}",
        catalog_digest=f"sha256:{'c' * 64}",
        intro_climb_reference="hello-world-climb@1",
        subject_hermes_version="0.19.0",
        **values,
    )


def is_placeholder(value: str) -> bool:
    """Return whether a value is one of the four placeholder spellings."""
    return value in PLACEHOLDER_VALUES
