"""Shared construction for the starter-Skill tests. Decisions 0007 R10, 0008.

Two pieces both the unit tests and the fetch tests need.

:func:`tree_digest` computes a directory's Skill root digest here, from the
files' own bytes, rather than asking the code under test what it thinks. It is
the same construction the manifest builder uses, which is the definition
decisions document 0008 pins a starter Skill by.

:func:`release_pinning` builds a ReleaseCore around one starter Skill. The
tests pin the fixture Skill rather than the released one, so that what is being
exercised is the machinery and not the contents of this release.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from techtree.canonical import sha256_digest_bytes
from techtree.manifests.builder import skill_content_digest
from techtree.models.base import Digest
from techtree.models.skill import SkillFile
from techtree.release.models import ReleaseCore

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


def content_address(digest: Digest) -> str:
    """Return the address bytes of this digest are published at."""
    return f"https://techtree.sh/api/v1/objects/{digest}"


def release_pinning(starter: Digest, object_url: str | None = None) -> ReleaseCore:
    """Return a ReleaseCore that pins one starter Skill.

    ``object_url`` is the address the release publishes that Skill at. It
    defaults to the content address of the tree digest, which is not what a
    real release publishes — there the address is keyed by the *file* digest —
    so a test that actually fetches passes the address of the file it serves.
    """
    return ReleaseCore(
        schema_version="techtree.release-core.v1",
        release_id="climb-v0.1.0",
        cli_version="0.1.0",
        protocol_version="v1alpha1",
        engine_digest=f"sha256:{'e' * 64}",
        catalog_digest=f"sha256:{'c' * 64}",
        intro_climb_reference="hello-world-climb@1",
        starter_skill_digest=starter,
        starter_skill_object_url=object_url or content_address(starter),
        skill_improver_digest=f"sha256:{'a' * 64}",
        minimum_host_hermes_version="0.19.0",
        maximum_tested_host_hermes_version="0.19.3",
        subject_hermes_version="0.19.0",
    )
