"""Which commit a built artifact came from. Decisions document 0026.

An artifact never describes its own identity. The ReleaseCore is written before
the wheel exists and cannot name the commit the wheel is built from without
inventing it, so the commit is *stamped onto the wheel while the wheel is being
built* and read back out of it here.

The stamp is one small document, ``build-provenance.json``, written into the
package's release resources by the build hook in ``tools/stamp_provenance.py``
and never present in the committed tree. Two properties of that hook are what
make this module's answer worth anything, and both live there rather than here:
the commit it writes is the commit the packaged sources are, and a build that
cannot establish that fails instead of guessing.

Reading it back has three possible answers and only two of them are values. A
wheel carries the stamp. A source checkout — an editable install, the test
suite, ``uv run techtree`` — is not a built artifact and carries none, and says
so rather than reporting a commit nobody stamped.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Annotated, Final, Literal

from pydantic import StringConstraints

from techtree.errors import ValidationError
from techtree.models.base import ProtocolModel
from techtree.release.document import (
    packaged_release_root,
    render_document,
)

__all__ = [
    "BUILD_PROVENANCE_FILENAME",
    "BUILD_PROVENANCE_SCHEMA_VERSION",
    "COMMIT_PATTERN",
    "BuildProvenance",
    "Commit",
    "packaged_build_provenance",
    "parse_build_provenance",
    "render_build_provenance",
    "wheel_build_provenance",
]

#: Bumped only if the stamped shape changes. The website, the plugin, and the
#: bootstrap checker all read it.
BUILD_PROVENANCE_SCHEMA_VERSION: Final = "techtree.build-provenance.v1"

#: The stamped file, wherever it is read from: the installed package, or a
#: wheel that has not been installed yet.
BUILD_PROVENANCE_FILENAME: Final = "build-provenance.json"

#: A full git commit, lowercase, never abbreviated. Spec section 9.3.2 pins
#: exact commits, and an abbreviation is not one.
COMMIT_PATTERN: Final = r"^[0-9a-f]{40}$"

type Commit = Annotated[str, StringConstraints(pattern=COMMIT_PATTERN)]

#: Where the stamp sits inside a wheel, which stores the package tree flat
#: under its import name.
_WHEEL_MEMBER: Final = f"techtree/resources/release/{BUILD_PROVENANCE_FILENAME}"


class BuildProvenance(ProtocolModel):
    """The commit one built artifact was built from, and nothing else."""

    schema_version: Literal["techtree.build-provenance.v1"]
    source_commit: Commit


def render_build_provenance(provenance: BuildProvenance) -> bytes:
    """Return the one byte spelling of a stamp.

    The same commit produces the same bytes, which is what keeps two builds of
    one commit byte-identical.
    """
    return render_document(provenance.model_dump(mode="json"))


def parse_build_provenance(raw: bytes) -> BuildProvenance:
    """Load and validate a stamp from stored bytes."""
    try:
        return BuildProvenance.model_validate_json(raw)
    except ValueError as error:
        raise ValidationError(
            f"this is not a valid build provenance stamp: {error}",
            code="build_provenance_invalid",
        ) from error


def packaged_build_provenance() -> BuildProvenance | None:
    """Return what this build was stamped with, or None if it is not a build."""
    stamp = packaged_release_root() / BUILD_PROVENANCE_FILENAME
    if not stamp.is_file():
        return None
    return parse_build_provenance(stamp.read_bytes())


def wheel_build_provenance(wheel: Path) -> BuildProvenance | None:
    """Return what a wheel on disk was stamped with, without installing it."""
    with zipfile.ZipFile(wheel) as archive:
        try:
            raw = archive.read(_WHEEL_MEMBER)
        except KeyError:
            return None
    return parse_build_provenance(raw)
