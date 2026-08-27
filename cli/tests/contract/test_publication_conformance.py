"""The committed conformance submission. Decisions document 0038.

The public run log and the CLI that publishes to it were built at the same time
from opposite ends, and they disagreed about the shape of what crosses between
them. Decisions 0038 fixed the contract in prose; this fixture is the same
contract as bytes, so that the receiving side can be tested against one real
submission rather than against a second careful reading of the paragraph.

These tests hold the fixture to the same standard the protocol goldens are
held to, and for the same reason: it is an artifact other people build against,
so it must change only when somebody meant to change it, and the change must be
visible.

* It regenerates. The fixture carries every byte of the proof it was built
  from, so the proof can be rebuilt out of it and the submission rebuilt out of
  the proof, through the one method the CLI's own request body comes from. A
  change to the wire shape, to the canonical encoding, or to which files travel
  fails here.
* It has the four members the contract names and no fifth.
* It is one real run's proof directory, whole, with the signed manifest in it.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from fixtures.publication.conformance import (
    CONFORMANCE_RUN_ID,
    FIXTURE_PATH,
    materialize_proof,
    submission_for_proof,
)
from techtree.publication.models import PublicationSubmission
from techtree.receipts.bundle import BUNDLE_MANIFEST_FILENAME

#: Decisions 0038's request document, member for member.
CONTRACT_MEMBERS = {"schema_version", "run_id", "bundle_digest", "files"}


def committed() -> bytes:
    """Return the fixture exactly as it is stored."""
    return FIXTURE_PATH.read_bytes()


def document() -> dict[str, Any]:
    """Return the fixture parsed as the receiving side would parse it."""
    parsed: dict[str, Any] = json.loads(committed())
    return parsed


def test_the_fixture_regenerates_byte_for_byte(tmp_path: Path) -> None:
    """The goldens' own property, over the artifact another codebase reads.

    The proof directory is rebuilt from the fixture's own files and the
    submission is rebuilt from that directory, so nothing outside this
    repository is needed to check that the committed bytes are the bytes this
    build produces.
    """
    proof = materialize_proof(committed(), tmp_path / "proof")

    rebuilt = submission_for_proof(proof, run_id=document()["run_id"])

    assert rebuilt == committed()


def test_the_fixture_has_exactly_the_members_the_contract_names() -> None:
    """A fifth member is caught here rather than by the run log refusing it."""
    assert set(document()) == CONTRACT_MEMBERS


def test_the_fixture_validates_as_a_submission() -> None:
    """It is loaded from bytes, which is how a stored document is loaded."""
    submission = PublicationSubmission.model_validate_json(committed())

    assert submission.run_id == CONFORMANCE_RUN_ID
    assert submission.bundle_digest.startswith("sha256:")


def test_the_fixture_carries_a_whole_proof_directory() -> None:
    """Including the signed manifest, which is what everything else checks against.

    The manifest does not commit to itself, so a submission that carried only
    the files it names would carry nothing a receiving side could check them
    against.
    """
    files = document()["files"]

    assert BUNDLE_MANIFEST_FILENAME in files
    assert len(files) > 1
    for path, content in files.items():
        assert isinstance(content, str), path
        assert base64.b64decode(content, validate=True), path


def test_no_file_in_the_fixture_travels_with_a_digest_or_a_size() -> None:
    """The mapping, held over the bytes the other side will actually receive.

    A digest beside the content is a claim the submitter wrote about the
    submitter's own bytes. Every digest the receiving side works with comes out
    of the bundle's own signed manifest, and the surest way to keep it that way
    is to send nothing else it could reach for. Base64 cannot contain a
    quotation mark, so a quoted key in this document is a key.
    """
    raw = committed()

    for gone in (b'"digest"', b'"size"', b'"content"', b'"path"'):
        assert gone not in raw, gone
