"""Stamp the source commit into the wheel while the wheel is being built.

Decisions document 0026. The release document is a contract and says nothing
about the artifact built from it; the artifact's identity is stamped onto it
here, by the build, and is never present in the committed tree.

The mechanism is one git question asked of the tree being packaged:

```text
which commit is this?
```

and it is answered only when the answer is beyond doubt. ``git rev-parse HEAD``
gives a candidate, and every path this wheel packages is then required to be
exactly what that commit holds. If git is not there, if there is no commit, or
if one packaged file differs from it by a byte, the build FAILS and says which.
There is no "unknown", no abbreviation and no default: a wheel that cannot name
its source honestly is not built at all.

The one build that is not stamped is an editable install, which is not a
distributable artifact — it is the working tree, imported in place, and it has
no identity to stamp. ``techtree release info`` reports the absence rather than
inventing a commit for it.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Final

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

#: Everything a built wheel is made of: the package tree, and the metadata
#: files hatchling copies into ``.dist-info``. The stamp claims these are the
#: named commit's, so these are what is checked.
PACKAGED_PATHS: Final = ("src/techtree", "pyproject.toml", "README.md", "LICENSE")

#: Where the stamp is written. It is inside the package so the wheel carries
#: it, and it is in ``.gitignore`` so it is never committed.
STAMP_PATH: Final = "src/techtree/resources/release/build-provenance.json"

#: The build target that is the working tree rather than an artifact.
EDITABLE: Final = "editable"


class StampProvenanceHook(BuildHookInterface):  # type: ignore[type-arg]
    """Write the source commit into the package before the wheel is zipped."""

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Stamp the commit, or stop the build."""
        stamp = Path(self.root) / STAMP_PATH
        stamp.unlink(missing_ok=True)
        if version == EDITABLE:
            return
        stamp.write_bytes(_stamp_bytes(source_commit(Path(self.root))))

    def finalize(
        self, version: str, build_data: dict[str, Any], artifact_path: str
    ) -> None:
        """Leave the working tree as it was found."""
        (Path(self.root) / STAMP_PATH).unlink(missing_ok=True)


def source_commit(root: Path) -> str:
    """Return the commit this tree is, refusing anything less than certainty."""
    commit = _git(root, "rev-parse", "--verify", "HEAD^{commit}").strip()
    if len(commit) != 40 or not all(c in "0123456789abcdef" for c in commit):
        raise BuildProvenanceError(
            f"git named the source commit as {commit!r}, which is not a full "
            "40-character commit"
        )

    changed = _git(
        root, "status", "--porcelain", "--untracked-files=all", "--", *PACKAGED_PATHS
    )
    if changed:
        # Porcelain lines are two status characters, a space, then the path.
        paths = ", ".join(
            sorted(line.split(maxsplit=1)[-1] for line in changed.splitlines())
        )
        raise BuildProvenanceError(
            f"this wheel would be stamped {commit}, but it is not built from "
            f"that commit: {paths} differ from it. Commit the tree, then "
            "build; a wheel may only claim a commit it really holds."
        )
    return commit


class BuildProvenanceError(RuntimeError):
    """The build cannot establish which commit it is building."""


def _git(root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            # A fixed argument list, run without a shell.
            ["git", "-C", str(root), *arguments],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError as error:
        raise BuildProvenanceError(
            "git is not available, so this build cannot establish which commit "
            f"it is building from: {error}"
        ) from error
    if completed.returncode != 0:
        raise BuildProvenanceError(
            f"`git {' '.join(arguments)}` failed in {root}, so this build "
            "cannot establish which commit it is building from: "
            f"{completed.stderr.strip()}"
        )
    # Only the trailing newline is removed: porcelain status lines begin with
    # significant spaces, and eating them would misname the paths they carry.
    return completed.stdout.rstrip("\n")


def _stamp_bytes(commit: str) -> bytes:
    """Return the stamp exactly as the package will read it back."""
    document = {
        "schema_version": "techtree.build-provenance.v1",
        "source_commit": commit,
    }
    text = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False)
    return f"{text}\n".encode()
