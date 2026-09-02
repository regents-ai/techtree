"""The frozen v0.1 evidence, read by the v0.2 projector. Plan V2-WP1.

``docs/plan/v0.2.md``, "v0.1 compatibility", promises two things about evidence
this project already wrote, and they are separate promises:

* the bytes are never rewritten, and
* they still verify with the same normalized outcome and the same claim
  semantics.

The frozen proof this repository carries is the certification run's own
publication submission, ``tests/fixtures/publication/conformance-submission.json``.
It is one real comparison's whole proof directory — a signed manifest, a
Campaign, a data policy, a taskset lock and its validation receipt, two
experiment manifests, two receipt sets, seventy-two signed episode receipts, a
signed operational record, and the signed report — carried base64 inside one
document. Every digest checked below comes out of that document's own signed
manifest, so nothing here depends on a value this test wrote down.

The two signed protocol goldens are frozen v0.1 documents too, and they are
projected for the same reason: a reader that could open a bundle but not a
single stored receipt would not be a reader of historical evidence.

The read-only tests are the other half. A projector that verified everything
and quietly rewrote a file would satisfy every check above on the first run and
none of them on the second, so the property is tested from four directions: the
module calls nothing that writes, it imports nothing that writes, a projected
directory is byte-for-byte and path-for-path what it was even when it could not
have been written to, and no writable v0.1 document comes back out — so there
is nothing a caller could take from a projection and store as a v0.1 shape.
"""

from __future__ import annotations

import ast
import base64
import json
import os
import stat
from collections.abc import Iterator
from dataclasses import fields, is_dataclass
from pathlib import Path
from types import FunctionType
from typing import Final

import pytest
from pydantic import BaseModel

from fixtures.publication.conformance import (
    CONFORMANCE_RUN_ID,
    FIXTURE_PATH,
    materialize_proof,
)
from techtree.canonical import sha256_digest_bytes
from techtree.historical import v01
from techtree.historical.v01 import (
    V01_PROJECTOR,
    ProjectedProof,
    ProjectedSubmission,
    project_proof_directory,
    project_publication_submission,
    project_signed_receipt,
    project_signed_report,
)
from techtree.identity.models import VerificationMessage, VerificationResult
from techtree.receipts.bundle import BUNDLE_MANIFEST_FILENAME
from techtree.receipts.verify import P1_MEANING, verify_local_bundle

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[2]
PACKAGE_ROOT: Final = REPOSITORY_ROOT / "src" / "techtree"
PROJECTOR_ROOT: Final = PACKAGE_ROOT / "historical"
GOLDEN_DIRECTORY: Final = REPOSITORY_ROOT / "tests" / "golden"

#: The frozen proof, as it sits in the repository. Read once: every test below
#: works from the same bytes, and one of them checks they are still those bytes
#: after everything else has run.
FROZEN_SUBMISSION: Final = FIXTURE_PATH.read_bytes()

#: What that run measured, recorded in ``release/certified-scientific-fingerprint.json``
#: and claimed by the signed report inside the frozen bundle. Written out here
#: rather than read back out of the projection, because a test that took its
#: expectations from the thing under test would pass whatever it was handed.
FROZEN_CLAIMS: Final = {
    "run_id": CONFORMANCE_RUN_ID,
    "proof_grade": "P1",
    "grade_meaning": P1_MEANING,
    "decision": "accepted",
    "execution_status": "completed",
    "score_status": "valid",
    "evidence_status": "complete",
    "comparison_status": "controlled_with_warnings",
    "publication_status": "not_requested",
    "publication_eligible": False,
}

#: The measurement, to the last recorded digit.
FROZEN_RESULT: Final = {
    "reward_name": "exact_match",
    "baseline_mean": 0.0,
    "candidate_mean": 0.6388888888888888,
    "absolute_delta": 0.6388888888888888,
    "relative_delta": None,
    "wins": 23,
    "losses": 0,
    "ties": 13,
    "task_count": 36,
}

#: How many files the frozen proof carries, and how many of them its signed
#: manifest commits to. They differ by exactly one: a manifest cannot carry its
#: own digest.
FROZEN_FILE_COUNT: Final = 84
FROZEN_COMMITTED_COUNT: Final = FROZEN_FILE_COUNT - 1

#: Names that place, move, or destroy bytes. ``open`` is here because the
#: projector reads through ``Path.read_bytes`` and has no reason to hold a mode
#: string at all, and ``copy``, ``dump``, ``remove``, ``rename`` and
#: ``replace`` are here because ``os.replace``, ``shutil.copy`` and
#: ``json.dump`` are how a writer that avoided every other name on this list
#: would still write. Those five are also ordinary method names elsewhere in
#: Python — on strings, dicts and lists — and that costs nothing here: a
#: projector opens files and compares digests, so it has no call for any
#: spelling of them.
WRITE_CALLS: Final = frozenset(
    {
        "NamedTemporaryFile",
        "TemporaryDirectory",
        "atomic_write_bytes",
        "chmod",
        "copy",
        "copy2",
        "copyfile",
        "copytree",
        "dump",
        "ensure_private_directory",
        "hardlink_to",
        "makedirs",
        "mkdir",
        "mkdtemp",
        "mkstemp",
        "move",
        "open",
        "remove",
        "removedirs",
        "rename",
        "replace",
        "rmdir",
        "rmtree",
        "symlink_to",
        "touch",
        "unlink",
        "write_bytes",
        "write_text",
    }
)

#: What a reader has no business importing. The modules place bytes, the named
#: objects sign or send them, and the bare function names are the same writes
#: reached for directly rather than through their module.
WRITE_IMPORTS: Final = frozenset(
    {
        "IdentityService",
        "IdentityStore",
        "PublicationService",
        "atomic_write_bytes",
        "build_local_bundle",
        "copy",
        "copy2",
        "dump",
        "remove",
        "rename",
        "replace",
        "shutil",
        "techtree.fs",
        "tempfile",
        "write_local_bundle",
    }
)


# ---------------------------------------------------------------------------
# Reading the frozen evidence
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def submission() -> ProjectedSubmission:
    """Project the frozen submission without unpacking it anywhere."""
    return project_publication_submission(FROZEN_SUBMISSION)


@pytest.fixture(scope="module")
def proof(tmp_path_factory: pytest.TempPathFactory) -> ProjectedProof:
    """Project the same proof as a directory, so it can be verified offline.

    The frozen document carries the directory; this puts a scratch copy of it
    somewhere the offline verifier can open it. The committed bytes are read
    and never written, which is what
    ``test_the_frozen_submission_is_the_same_bytes_after_every_reading``
    holds to at the end.
    """
    directory = materialize_proof(
        FROZEN_SUBMISSION, tmp_path_factory.mktemp("frozen") / "proof"
    )
    return project_proof_directory(directory)


def test_the_projection_names_the_release_whose_evidence_it_read(
    proof: ProjectedProof, submission: ProjectedSubmission
) -> None:
    """A reader holding a projection can say what it was read as."""
    assert proof.projector == V01_PROJECTOR == submission.projector


def test_the_frozen_submission_commits_to_a_whole_proof_directory(
    submission: ProjectedSubmission,
) -> None:
    assert len(submission.carried_paths) == FROZEN_FILE_COUNT
    assert len(submission.artifacts) == FROZEN_COMMITTED_COUNT
    assert BUNDLE_MANIFEST_FILENAME in submission.carried_paths


def test_the_frozen_submission_carries_nothing_nobody_signed(
    submission: ProjectedSubmission,
) -> None:
    """Every file that travels is either committed to or is the commitment."""
    assert submission.unsigned_paths == ()


def test_the_frozen_submission_is_addressed_by_the_manifest_it_carries(
    submission: ProjectedSubmission,
) -> None:
    """The digest the bundle is published under is its own manifest's.

    ``observed_bundle_digest`` is taken again from the carried manifest's
    payload, so this is the stated digest against a recomputed one rather than
    one document agreeing with itself.
    """
    assert submission.addresses_the_bundle_it_carries
    assert submission.seals_intact
    assert submission.recorded_bundle_digest.startswith("sha256:")
    assert submission.observed_bundle_digest == submission.recorded_bundle_digest


def tampered_manifest_payload() -> bytes:
    """Return the frozen submission with one field edited inside its manifest.

    Only the manifest's payload changes. Every artifact's bytes are left alone,
    every digest the manifest records is left alone, and the digest the
    submission is addressed by is left alone — and the manifest does not commit
    to itself, so nothing but a recomputed manifest digest is in a position to
    notice.
    """
    document = json.loads(FROZEN_SUBMISSION)
    manifest = json.loads(
        base64.b64decode(document["files"][BUNDLE_MANIFEST_FILENAME], validate=True)
    )
    manifest["payload"]["campaign_spec_digest"] = f"sha256:{'0' * 64}"
    document["files"][BUNDLE_MANIFEST_FILENAME] = base64.b64encode(
        json.dumps(manifest).encode("utf-8")
    ).decode("ascii")
    return json.dumps(document).encode("utf-8")


def test_a_tampered_manifest_payload_fails_the_submission_projection() -> None:
    """The counterexample the addressing check is worth nothing without."""
    projected = project_publication_submission(tampered_manifest_payload())

    # Every file the manifest commits to is untouched, which is the whole
    # difficulty: byte identity alone cannot see this edit.
    assert projected.bytes_intact
    assert projected.unsigned_paths == ()

    assert not projected.addresses_the_bundle_it_carries
    assert not projected.seals_intact
    assert not projected.manifest_seal.digest_intact
    assert projected.observed_bundle_digest != projected.recorded_bundle_digest


def test_the_same_tampered_manifest_fails_the_directory_projection(
    tmp_path: Path,
) -> None:
    """Both ways in reject the same edit, so neither is the weaker reading."""
    directory = materialize_proof(tampered_manifest_payload(), tmp_path / "proof")

    projected = project_proof_directory(directory)

    assert not projected.verified
    assert not projected.manifest_seal.digest_intact


def frozen_paths() -> list[str]:
    """Return every path the frozen manifest commits to, for parametrization."""
    return [
        artifact.relative_path
        for artifact in project_publication_submission(
            FIXTURE_PATH.read_bytes()
        ).artifacts
    ]


@pytest.mark.parametrize("relative_path", frozen_paths())
def test_every_frozen_file_is_byte_identical_to_its_recorded_digest(
    relative_path: str, submission: ProjectedSubmission
) -> None:
    """The promise, one file at a time.

    The recorded digest and size come from the bundle's own signed manifest and
    the observed ones are taken again from the stored bytes, so this fails if
    any file in the frozen proof is not the file that was signed.
    """
    artifact = next(
        item for item in submission.artifacts if item.relative_path == relative_path
    )

    assert artifact.present, relative_path
    assert artifact.observed_digest == artifact.recorded_digest, relative_path
    assert artifact.observed_size == artifact.recorded_size, relative_path
    assert artifact.byte_identical, relative_path


def test_every_frozen_file_is_byte_identical_after_the_directory_reading(
    proof: ProjectedProof,
) -> None:
    """The same commitments, checked against the bytes on disk this time."""
    assert proof.bytes_intact
    assert len(proof.artifacts) == FROZEN_COMMITTED_COUNT


def test_the_frozen_proof_verifies_through_the_reader(proof: ProjectedProof) -> None:
    """The whole point: v0.1 evidence still verifies under v0.2."""
    assert proof.verified
    assert proof.verification.failures == []


def test_the_reader_reports_the_verifier_s_own_normalized_outcome(
    proof: ProjectedProof, tmp_path: Path
) -> None:
    """The outcome is the offline verifier's, check for check and in its order.

    Equality of two results would also hold for a re-derivation that happened
    to agree, so the messages are compared as a sequence: a projector that
    renamed a check, dropped a warning, or reordered them would differ here
    even though the verdict matched.
    """
    directory = materialize_proof(FROZEN_SUBMISSION, tmp_path / "proof")
    expected = verify_local_bundle(directory)

    assert proof.verification == expected
    assert [
        (message.id, message.status, message.code, message.detail)
        for message in proof.verification.messages
    ] == [
        (message.id, message.status, message.code, message.detail)
        for message in expected.messages
    ]


def test_the_reader_hands_back_the_verifier_s_result_rather_than_deriving_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The projection delegates, established by replacing what it delegates to.

    With the offline verifier standing in for itself, the object the projector
    returns is the object the verifier produced. A projector that recomputed a
    verdict of its own would return something else, and
    :attr:`ProjectedProof.verified` would stop following the verifier.
    """
    directory = materialize_proof(FROZEN_SUBMISSION, tmp_path / "proof")
    stand_in = VerificationResult(
        verified=False,
        messages=[
            VerificationMessage(
                id="stand-in",
                status="failed",
                code="verification_error",
                detail="the offline verifier said so",
            )
        ],
    )
    monkeypatch.setattr(v01, "verify_local_bundle", lambda _: stand_in)

    projected = project_proof_directory(directory)

    assert projected.verification is stand_in
    assert projected.verified is False


def test_the_frozen_proof_carries_the_release_s_own_certified_coordinates(
    submission: ProjectedSubmission,
) -> None:
    """The recorded digests, taken from outside the bundle for once.

    ``release/certified-scientific-fingerprint.json`` is the release's own
    record of what the certification run measured, written when the release was
    made and never regenerated from the bundle. Four of its digests name files
    inside the frozen proof, so a proof whose Campaign, policy, lock or
    validation receipt had drifted would disagree with the release that shipped
    it, not merely with itself.
    """
    fingerprint = json.loads(
        (
            REPOSITORY_ROOT / "release" / "certified-scientific-fingerprint.json"
        ).read_bytes()
    )
    recorded = {
        "campaign.json": fingerprint["campaign_spec_digest"],
        "data-policy.json": fingerprint["data_policy_digest"],
        "taskset-lock.json": fingerprint["taskset_lock_digest"],
        "taskset-validation-receipt.json": fingerprint[
            "taskset_validation_receipt_digest"
        ],
    }

    for relative_path, digest in recorded.items():
        artifact = next(
            item for item in submission.artifacts if item.relative_path == relative_path
        )
        assert artifact.observed_digest == digest, relative_path


def test_the_frozen_proof_claims_exactly_what_it_claimed_in_v0_1(
    proof: ProjectedProof,
) -> None:
    """Claim semantics, field by field, against values written down here."""
    claims = proof.claims

    assert claims.run_id == FROZEN_CLAIMS["run_id"]
    assert claims.proof_grade == FROZEN_CLAIMS["proof_grade"]
    assert claims.grade_meaning == FROZEN_CLAIMS["grade_meaning"]
    assert claims.decision == FROZEN_CLAIMS["decision"]
    assert claims.execution_status == FROZEN_CLAIMS["execution_status"]
    assert claims.score_status == FROZEN_CLAIMS["score_status"]
    assert claims.evidence_status == FROZEN_CLAIMS["evidence_status"]
    assert claims.comparison_status == FROZEN_CLAIMS["comparison_status"]
    assert claims.publication_status == FROZEN_CLAIMS["publication_status"]
    assert claims.publication_eligible == FROZEN_CLAIMS["publication_eligible"]


def test_the_frozen_proof_measures_exactly_what_it_measured_in_v0_1(
    proof: ProjectedProof,
) -> None:
    """The numbers are copied out of the signed report and not recomputed."""
    result = proof.claims.result

    assert result.reward_name == FROZEN_RESULT["reward_name"]
    assert result.baseline_mean == FROZEN_RESULT["baseline_mean"]
    assert result.candidate_mean == FROZEN_RESULT["candidate_mean"]
    assert result.absolute_delta == FROZEN_RESULT["absolute_delta"]
    assert result.relative_delta == FROZEN_RESULT["relative_delta"]
    assert (result.wins, result.losses, result.ties) == (
        FROZEN_RESULT["wins"],
        FROZEN_RESULT["losses"],
        FROZEN_RESULT["ties"],
    )
    assert result.task_count == FROZEN_RESULT["task_count"]
    assert proof.receipt_counts == (
        ("baseline", FROZEN_RESULT["task_count"]),
        ("candidate", FROZEN_RESULT["task_count"]),
    )


def test_the_document_and_the_directory_read_the_same_proof(
    proof: ProjectedProof, submission: ProjectedSubmission
) -> None:
    """One proof, two ways in, one reading.

    The wire document and the directory it unpacks to are the same evidence, so
    a difference between these two projections would mean the encoding had
    started to carry meaning of its own.
    """
    assert submission.run_id == proof.run_id
    assert submission.recorded_bundle_digest == proof.bundle_digest
    assert submission.claims == proof.claims
    assert submission.artifacts == proof.artifacts


def test_the_frozen_bundle_manifest_and_report_are_sealed_to_their_payloads(
    proof: ProjectedProof,
) -> None:
    """Both signed documents still match the digests they were signed under."""
    assert proof.manifest_seal.digest_intact
    assert proof.manifest_seal.signed
    assert proof.report_seal.digest_intact
    assert proof.report_seal.signed
    assert proof.manifest_seal.signing_key_id == proof.executor_key_id
    assert proof.report_seal.signing_key_id == proof.executor_key_id
    assert proof.root_report_digest == proof.report_seal.recorded_payload_digest


def test_a_changed_byte_stops_being_byte_identical(tmp_path: Path) -> None:
    """The counterexample the checks above are worth nothing without."""
    directory = materialize_proof(FROZEN_SUBMISSION, tmp_path / "proof")
    edited = directory / "receipts" / "candidate" / "0000.json"
    edited.write_bytes(edited.read_bytes() + b"\n")

    projected = project_proof_directory(directory)

    assert not projected.bytes_intact
    assert not projected.verified
    broken = projected.artifact("receipts/candidate/0000.json")
    assert broken is not None
    assert not broken.byte_identical


# ---------------------------------------------------------------------------
# The frozen signed goldens
# ---------------------------------------------------------------------------


def test_the_frozen_report_golden_projects_with_its_seal_intact() -> None:
    projected = project_signed_report(
        (GOLDEN_DIRECTORY / "real-uplift-report.json").read_bytes()
    )

    assert projected.projector == V01_PROJECTOR
    assert projected.seal.digest_intact
    assert projected.seal.signed
    assert projected.claims.proof_grade == "P1"
    assert projected.claims.grade_meaning == P1_MEANING
    assert projected.claims.decision == "accepted"
    assert projected.claims.score_status == "valid"
    assert projected.claims.comparison_status == "controlled_with_warnings"
    assert projected.claims.publication_status == "not_requested"


def test_the_frozen_receipt_golden_projects_with_its_seal_intact() -> None:
    projected = project_signed_receipt(
        (GOLDEN_DIRECTORY / "real-episode-receipt.json").read_bytes()
    )

    assert projected.projector == V01_PROJECTOR
    assert projected.seal.digest_intact
    assert projected.seal.signed
    assert projected.execution_backend == "verifiers"
    assert projected.score_status == "valid"
    assert projected.evidence_status == "complete"


# ---------------------------------------------------------------------------
# Read-only by construction
# ---------------------------------------------------------------------------


def projector_modules() -> list[Path]:
    """Return every source file the v0.1 projector is made of."""
    return sorted(PROJECTOR_ROOT.rglob("*.py"))


def called_names(tree: ast.AST) -> Iterator[str]:
    """Yield the name of every call in one module, however it is spelled."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Attribute):
            yield function.attr
        elif isinstance(function, ast.Name):
            yield function.id


def imported_names(tree: ast.AST) -> Iterator[str]:
    """Yield every module and every name one module imports."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                yield node.module
            for alias in node.names:
                yield alias.name


def parsed(path: Path) -> ast.Module:
    """Return one source file's syntax tree."""
    return ast.parse(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", projector_modules(), ids=lambda path: str(path.name))
def test_the_projector_calls_nothing_that_writes(path: Path) -> None:
    """Read-only by construction, read off the construction."""
    assert WRITE_CALLS.isdisjoint(set(called_names(parsed(path))))


@pytest.mark.parametrize("path", projector_modules(), ids=lambda path: str(path.name))
def test_the_projector_imports_nothing_that_writes(path: Path) -> None:
    """A reader that could not reach a writer cannot become one by accident."""
    assert WRITE_IMPORTS.isdisjoint(set(imported_names(parsed(path))))


#: Writes spelled the ways a scan over names has to catch, including the three
#: spellings — ``os.replace``, ``json.dump`` and ``shutil.copy`` — an earlier
#: version of :data:`WRITE_CALLS` let through.
WRITE_SNIPPETS: Final = (
    "import os\nos.replace(source, destination)\n",
    "import os\nos.rename(source, destination)\n",
    "import os\nos.remove(path)\n",
    "path.replace(destination)\n",
    "path.rename(destination)\n",
    "import json\njson.dump(document, handle)\n",
    "import shutil\nshutil.copy(source, destination)\n",
    "import shutil\nshutil.copy2(source, destination)\n",
    "import shutil\nshutil.rmtree(directory)\n",
    "path.write_bytes(data)\n",
    "with path.open('w') as handle:\n    handle.write('')\n",
    "from techtree.fs import atomic_write_bytes\natomic_write_bytes(path, data)\n",
)

#: The same writes reached for through an import rather than through a call.
IMPORT_SNIPPETS: Final = (
    "import shutil\n",
    "import tempfile\n",
    "from os import replace\n",
    "from os import rename\n",
    "from shutil import copy2\n",
    "from json import dump\n",
    "from techtree.fs import atomic_write_bytes\n",
    "from techtree.receipts.bundle import write_local_bundle\n",
    "from techtree.identity.service import IdentityService\n",
)

#: Reading, so that the two scans above are shown to be selective rather than
#: merely alarmed.
READ_SNIPPETS: Final = (
    "data = path.read_bytes()\n",
    "document = json.loads(raw)\n",
    "digest = sha256_digest_bytes(data)\n",
    "for path in sorted(directory.rglob('*')):\n    pass\n",
)


@pytest.mark.parametrize("source", WRITE_SNIPPETS)
def test_the_call_scan_sees_a_write_however_it_is_spelled(source: str) -> None:
    """The guards are only guards if they fire."""
    assert not WRITE_CALLS.isdisjoint(set(called_names(ast.parse(source))))


@pytest.mark.parametrize("source", IMPORT_SNIPPETS)
def test_the_import_scan_sees_a_writer_being_imported(source: str) -> None:
    assert not WRITE_IMPORTS.isdisjoint(set(imported_names(ast.parse(source))))


@pytest.mark.parametrize("source", READ_SNIPPETS)
def test_the_call_scan_does_not_flag_reading(source: str) -> None:
    """A scan that flagged everything would pass the projector by accident."""
    assert WRITE_CALLS.isdisjoint(set(called_names(ast.parse(source))))


def modules_that_write() -> list[Path]:
    """Return every module in the package whose source places bytes on disk."""
    return [
        path
        for path in sorted(PACKAGE_ROOT.rglob("*.py"))
        if "resources" not in path.parts
        and not WRITE_CALLS.isdisjoint(set(called_names(parsed(path))))
    ]


def test_the_projector_is_not_one_of_the_modules_that_write() -> None:
    """The two scans above are only worth running if they can see a writer.

    The same scan is pointed at the whole package first, so a
    :data:`WRITE_CALLS` that had stopped matching anything would fail here
    rather than pass quietly over the projector.
    """
    writers = modules_that_write()

    assert writers, "no module in the package appears to write; the scan is broken"
    assert not any(PROJECTOR_ROOT in path.parents for path in writers)


def reachable(value: object) -> Iterator[object]:
    """Yield one projection and everything held inside it."""
    yield value
    if is_dataclass(value) and not isinstance(value, type):
        for field in fields(value):
            yield from reachable(getattr(value, field.name))
    elif isinstance(value, tuple):
        for item in value:
            yield from reachable(item)


def test_no_writable_v0_1_document_leaves_the_projector(
    proof: ProjectedProof, submission: ProjectedSubmission
) -> None:
    """No adapter on the write path, established at the reader's own edge.

    The projector parses v0.1 protocol documents in order to read them, and it
    hands none of them back. What comes out is frozen read models and the
    verification verdict, so a caller cannot take a projection, sign what is
    inside it, and store a v0.1 shape again — the old shape has no way out of
    this module, and policing the callers is therefore unnecessary.
    """
    projections: tuple[object, ...] = (
        proof,
        submission,
        project_signed_report(
            (GOLDEN_DIRECTORY / "real-uplift-report.json").read_bytes()
        ),
        project_signed_receipt(
            (GOLDEN_DIRECTORY / "real-episode-receipt.json").read_bytes()
        ),
    )

    for projection in projections:
        assert is_dataclass(projection)
        for held in reachable(projection):
            assert not isinstance(held, BaseModel) or isinstance(
                held, VerificationResult
            ), held


def test_the_projector_offers_reading_and_nothing_else() -> None:
    """One verb on the public surface, so there is no second mode to be in."""
    exported = [getattr(v01, name) for name in v01.__all__]
    functions = [
        value.__name__ for value in exported if isinstance(value, FunctionType)
    ]

    assert functions
    assert all(name.startswith("project_") for name in functions)


def snapshot(directory: Path) -> dict[str, tuple[str, int]]:
    """Return every file under a directory against its digest and its size."""
    return {
        path.relative_to(directory).as_posix(): (
            sha256_digest_bytes(path.read_bytes()),
            path.stat().st_size,
        )
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def test_projecting_a_proof_leaves_every_byte_and_every_path_where_it_was(
    tmp_path: Path,
) -> None:
    """The property, observed rather than argued."""
    directory = materialize_proof(FROZEN_SUBMISSION, tmp_path / "proof")
    before = snapshot(directory)

    projected = project_proof_directory(directory)

    assert projected.verified
    assert snapshot(directory) == before


def test_a_proof_directory_that_cannot_be_written_to_still_projects(
    tmp_path: Path,
) -> None:
    """Archived evidence is usually somewhere nobody can write, and should be.

    This and the snapshot above are complementary rather than duplicates. A
    directory with no write permission refuses anything that needs a directory
    entry — a scratch file, a temporary copy, a rename into place — so this
    catches a projector that created or moved something. Overwriting a file in
    place needs no directory entry and is invisible here, which is what the
    snapshot catches.
    """
    directory = materialize_proof(FROZEN_SUBMISSION, tmp_path / "proof")
    directories = [directory, *(path for path in directory.rglob("*") if path.is_dir())]
    for path in directories:
        path.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        projected = project_proof_directory(directory)
    finally:
        for path in directories:
            path.chmod(stat.S_IRWXU)

    assert projected.verified
    assert projected.bytes_intact


def test_the_frozen_submission_is_the_same_bytes_after_every_reading() -> None:
    """The committed fixture, re-read from disk once everything else has run."""
    assert FIXTURE_PATH.read_bytes() == FROZEN_SUBMISSION
    assert os.stat(FIXTURE_PATH).st_size == len(FROZEN_SUBMISSION)
