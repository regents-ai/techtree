"""Check the release artifacts, and optionally the website wrapper.

Spec sections 9.4, 9.5 and 9.7.

``techtree release verify`` answers the question an *installed* CLI can answer:
does the release document this build ships still agree with this build? That is
the question an operator asks, and it deliberately reaches for nothing outside
the wheel.

This tool answers the wider question a *repository* can answer, which is the
one the release process needs:

```text
does the shipped copy still equal the staged copy
are the generated release files the ones this tree produces
does the website's bootstrap document still name this release
```

The bootstrap check is opt-in through ``--bootstrap <path>``, because the
website lives in another repository that may or may not be checked out beside
this one. It requires ``--wheel <path>`` alongside it: the bootstrap document
names the source commit of the published CLI, the release document deliberately
does not (decisions 0026), and the only thing that can confirm that coordinate
is the wheel's own stamp. Nothing here writes, publishes, or fetches anything;
both files are read from local paths and nothing else.

Run it with ``uv run python tools/verify_release_core.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Final

from techtree.canonical import validate_digest
from techtree.release.bootstrap import verify_bootstrap_document
from techtree.release.checks import (
    ReleaseCheck,
    ReleaseVerification,
    local_release_facts,
    verify_release_core,
)
from techtree.release.document import (
    RELEASE_CORE_FILENAME,
    document_digest,
    parse_release_core,
)
from techtree.release.generate import packaged_sources
from techtree.release.provenance import wheel_build_provenance

# The generator holds the repository layout and this tool checks it, so the
# two share one definition of where the artifacts live. ``tools`` is a scripts
# directory rather than a package, so it is put on the path explicitly instead
# of relying on how this file was invoked.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_release_core import (
    PACKAGED_DIRECTORY,
    RELEASE_DIRECTORY,
    REPOSITORY_ROOT,
    drift,
    release_artifacts,
)

STAGED_COPY: Final = RELEASE_DIRECTORY / RELEASE_CORE_FILENAME
SHIPPED_COPY: Final = PACKAGED_DIRECTORY / RELEASE_CORE_FILENAME


def repository_checks() -> list[ReleaseCheck]:
    """Check the two things only a repository can see."""
    return [_embedded_copy_check(), _generated_artifacts_check()]


def main(argv: list[str] | None = None) -> int:
    """Verify the release, and report every check that ran."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expected",
        metavar="DIGEST",
        help="The ReleaseCore digest the website published for this release.",
    )
    parser.add_argument(
        "--bootstrap",
        metavar="PATH",
        type=Path,
        help="A website bootstrap document to check this release against.",
    )
    parser.add_argument(
        "--wheel",
        metavar="PATH",
        type=Path,
        help=(
            "The built CLI wheel the bootstrap document publishes. Required "
            "with --bootstrap: its stamp is what the document's source commit "
            "is checked against."
        ),
    )
    arguments = parser.parse_args(argv)
    if (arguments.bootstrap is None) != (arguments.wheel is None):
        parser.error("--bootstrap and --wheel are given together or not at all")

    expected = (
        None if arguments.expected is None else validate_digest(arguments.expected)
    )
    raw = SHIPPED_COPY.read_bytes()
    result = verify_release_core(
        raw,
        local_release_facts(packaged_sources()),
        expected_digest=expected,
    )
    checks = [*result.checks, *repository_checks()]

    if arguments.bootstrap is not None:
        stamp = wheel_build_provenance(arguments.wheel)
        if stamp is None:
            sys.stdout.write(
                f"release: {arguments.wheel} carries no build provenance, so "
                "the source commit the bootstrap document names cannot be "
                "checked against anything\n"
            )
            return 1
        core = parse_release_core(raw)
        wheel_sha256 = hashlib.sha256(arguments.wheel.read_bytes()).hexdigest()
        bootstrap = verify_bootstrap_document(
            core,
            arguments.bootstrap.read_bytes(),
            wheel=stamp,
            wheel_sha256=wheel_sha256,
        )
        checks.extend(bootstrap.checks)

    verification = ReleaseVerification(
        verified=not any(check.status == "failed" for check in checks),
        checks=checks,
    )
    for check in verification.checks:
        sys.stdout.write(f"{check.status:<7} {check.id}: {check.detail}\n")

    if not verification.verified:
        sys.stdout.write(
            f"release: {len(verification.failures)} of {len(checks)} checks failed\n"
        )
        return 1

    sys.stdout.write(
        f"release: {document_digest(raw)} verifies, {len(checks)} checks\n"
    )
    return 0


def _embedded_copy_check() -> ReleaseCheck:
    """The wheel's copy and the copy other repositories take must be equal."""
    staged = STAGED_COPY.read_bytes() if STAGED_COPY.is_file() else None
    shipped = SHIPPED_COPY.read_bytes() if SHIPPED_COPY.is_file() else None
    if staged is None or shipped is None:
        missing = STAGED_COPY if staged is None else SHIPPED_COPY
        return ReleaseCheck(
            id="release_core_embedded_copy",
            status="failed",
            code="release_core_missing",
            detail=(
                f"{missing.relative_to(REPOSITORY_ROOT).as_posix()} does not "
                "exist; run `make release-core`."
            ),
        )
    if staged == shipped:
        return ReleaseCheck(
            id="release_core_embedded_copy",
            status="passed",
            code="ok",
            detail=(
                "the copy the wheel ships and the copy other repositories take "
                "are byte-identical."
            ),
        )
    return ReleaseCheck(
        id="release_core_embedded_copy",
        status="failed",
        code="release_core_copy_drift",
        detail=(
            f"{STAGED_COPY.relative_to(REPOSITORY_ROOT).as_posix()} and "
            f"{SHIPPED_COPY.relative_to(REPOSITORY_ROOT).as_posix()} hold "
            "different bytes; run `make release-core`."
        ),
    )


def _generated_artifacts_check() -> ReleaseCheck:
    """Every generated release file must be the one this tree produces."""
    stale = drift(release_artifacts())
    if stale:
        return ReleaseCheck(
            id="release_artifacts_current",
            status="failed",
            code="release_artifacts_stale",
            detail="; ".join(stale) + "; run `make release-core`.",
        )
    return ReleaseCheck(
        id="release_artifacts_current",
        status="passed",
        code="ok",
        detail="every generated release file is the one this source tree produces.",
    )


if __name__ == "__main__":
    raise SystemExit(main())
