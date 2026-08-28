"""The submission bytes the other half of this feature is tested against.

Decisions 0038 fixes one wire contract for two implementations that were built
at the same time from opposite ends. A contract written in prose is a contract
both sides read, and two careful readings of the same paragraph is how they
disagreed in the first place. So the contract is also an artifact:
``conformance-submission.json`` beside this module is one real submission,
byte for byte, and the receiving side's tests are pointed at it.

Three properties make it worth having.

*It is produced by the real code path.* :meth:`~techtree.publication.service.
PublicationService.submission_bytes` builds it, which is the same method and
the only method the CLI's own request body comes out of. A fixture assembled by
hand would pin what somebody believed the CLI sends.

*It is a real run's proof.* Every file in it is the signed evidence a real
comparison wrote — a manifest, two experiment manifests, two receipt sets,
seventy-two signed episode receipts, and the signed report — so a receiving
side that parses this fixture has parsed the thing it will actually be given,
including its sizes and its nesting.

*It regenerates.* ``test_publication_conformance_fixture.py`` decodes the
fixture back into a proof directory, rebuilds the submission from it through
the same function below, and compares bytes. The fixture carries every byte it
was built from, so the check needs nothing that is not committed, and a change
anywhere in the submission's shape or its canonical encoding shows up as a
failing test rather than as a run log refusing somebody's publication.

The proof directory this was first built from is a certification run on the
machine that made it, named by :data:`CONFORMANCE_RUN_ID`, and is not in this
repository. Rebuilding from that run is what :func:`main` is for; the committed
fixture is what everything else reads.

Run it with::

    uv run python tests/fixtures/publication/conformance.py [PROOF_DIRECTORY]
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from techtree.publication.service import PublicationService
from techtree.publication.transport import HttpsPublicationTransport
from techtree.receipts.verify import LocalProofVerifier
from techtree.release.document import packaged_release_core_bytes, parse_release_core

__all__ = [
    "CONFORMANCE_RUN_ID",
    "FIXTURE_PATH",
    "materialize_proof",
    "submission_for_proof",
]

#: Where the committed submission lives. The site's tests are pointed here.
FIXTURE_PATH: Final = Path(__file__).resolve().parent / "conformance-submission.json"

#: The run the committed fixture is a submission for. A real certification
#: execution; ``release/certified-scientific-fingerprint.json`` records what it
#: measured.
CONFORMANCE_RUN_ID: Final = "run_c4758ddb5bba4023aa3530b47f4582e9"

#: Where that run's proof sits on the machine that produced it. Only
#: :func:`main` reads it, and only when somebody rebuilds the fixture.
DEFAULT_PROOF_DIRECTORY: Final = (
    Path.home()
    / "Library"
    / "Application Support"
    / "techtree"
    / "runs"
    / CONFORMANCE_RUN_ID
    / "proof"
)

#: The clock and the address the service is built with. Neither reaches the
#: submission — its bytes are the run's own proof and nothing about when or
#: where it was built — and they are constants here so that nothing about this
#: module's output can depend on the host it ran on.
_FIXED_INSTANT: Final = datetime(2026, 8, 27, tzinfo=UTC)


def submission_for_proof(proof_directory: Path, *, run_id: str) -> bytes:
    """Return the exact bytes the CLI would put on the wire for this proof.

    The proof is copied into a throwaway run directory rather than read where
    it lies, because a completed run's files are final and a generator that
    pointed the service at somebody's real run directory would be one edit away
    from writing into it.

    The service is built with this build's own release coordinates and a
    transport that is never reached. Building a submission is not sending one:
    the coordinates are the address a publication *would* go to and nothing in
    this module opens a socket to it, or to anywhere else.
    """
    with tempfile.TemporaryDirectory() as scratch:
        runs_dir = Path(scratch) / "runs"
        (runs_dir / run_id).mkdir(parents=True)
        shutil.copytree(proof_directory, runs_dir / run_id / "proof")
        service = PublicationService(
            runs_dir=runs_dir,
            coordinates=parse_release_core(packaged_release_core_bytes()).publication,
            endpoint_override=None,
            transport=HttpsPublicationTransport(),
            clock=lambda: _FIXED_INSTANT,
        )
        return service.submission_bytes(run_id)


def materialize_proof(submission: bytes, destination: Path) -> Path:
    """Write a submission's files back out as a proof directory.

    The inverse of the encoding, and the reason the fixture can be checked
    without the run it came from: it carries every byte of that proof, so the
    directory can be rebuilt from it exactly and the submission rebuilt from
    the directory.
    """
    document = json.loads(submission)
    for path, content in document["files"].items():
        written = destination / path
        written.parent.mkdir(parents=True, exist_ok=True)
        written.write_bytes(base64.b64decode(content, validate=True))
    return destination


def main(argv: list[str] | None = None) -> int:
    """Rebuild the committed fixture from a proof directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "proof_directory",
        nargs="?",
        default=DEFAULT_PROOF_DIRECTORY,
        type=Path,
        help="the proof directory to build a submission for",
    )
    parser.add_argument(
        "--run-id",
        default=CONFORMANCE_RUN_ID,
        help="the run that proof directory belongs to",
    )
    arguments = parser.parse_args(argv)

    directory: Path = arguments.proof_directory
    if not directory.is_dir():
        print(f"no proof directory at {directory}", file=sys.stderr)
        return 1

    submission = submission_for_proof(directory, run_id=arguments.run_id)
    FIXTURE_PATH.write_bytes(submission)

    document = json.loads(submission)
    print(
        f"wrote {len(submission)} bytes for {arguments.run_id}: "
        f"{len(document['files'])} files, "
        f"{sum(len(base64.b64decode(value)) for value in document['files'].values())} "
        f"bytes of proof, to {FIXTURE_PATH}"
    )

    # Said out loud rather than assumed. The fixture pins the wire shape; what
    # the receiving side will make of the bundle inside it is a separate
    # question, and the answer this build gives is worth seeing before the
    # fixture is committed.
    verdict = LocalProofVerifier().verify_bundle(directory)
    print(f"this build's offline verification of that proof: {verdict.verified}")
    for failure in verdict.failures:
        print(f"  failed {failure.id}: {failure.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
