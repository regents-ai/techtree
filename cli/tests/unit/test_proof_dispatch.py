"""Which verifier a stored proof is read through. Spec section 7.21.

Two generations of proof exist and each has its own verifier. The selector
reads one thing — the schema the signed report declares — and hands the proof
to that generation's verifier unchanged, so the outcome is the verifier's own.
A proof it cannot place is refused rather than guessed at.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from fixtures.publication.conformance import FIXTURE_PATH, materialize_proof
from fixtures.receipts.proof import signed_proof, write_proof
from techtree.canonical import canonical_json_bytes
from techtree.historical import verify_v01
from techtree.receipts import verify
from techtree.receipts.bundle import REPORT_FILENAME
from techtree.receipts.dispatch import verify_proof


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    return write_proof(signed_proof(tmp_path / "home"), tmp_path / "run")


def test_a_v02_proof_is_read_by_the_live_verifier(bundle: Path) -> None:
    whole = verify_proof(bundle, "bundle")
    report = verify_proof(bundle / REPORT_FILENAME, "report")

    assert whole.result == verify.verify_local_bundle(bundle)
    assert whole.result.verified is True
    assert report.result == verify.LocalProofVerifier().verify_report(
        bundle / REPORT_FILENAME
    )
    assert report.result.verified is True


def test_a_v01_proof_is_read_by_the_historical_verifier(tmp_path: Path) -> None:
    """The frozen v0.1 proof keeps the outcome it had, through the same door."""
    directory = materialize_proof(FIXTURE_PATH.read_bytes(), tmp_path / "proof")

    verification = verify_proof(directory, "bundle")

    assert verification.result == verify_v01.verify_local_bundle(directory)
    assert verification.result.verified is True


@pytest.mark.parametrize(
    ("damage", "detail"),
    [
        pytest.param(
            lambda path: path.unlink(), "has no uplift-report.json", id="absent"
        ),
        pytest.param(
            lambda path: path.write_bytes(b"not a document"),
            "is not a JSON document",
            id="not-json",
        ),
        pytest.param(
            lambda path: path.write_bytes(canonical_json_bytes({"payload": {}})),
            "not a signed report envelope",
            id="no-schema",
        ),
        pytest.param(
            lambda path: path.write_bytes(
                canonical_json_bytes(
                    {"payload": {"schema_version": "techtree.uplift-report.v9"}}
                )
            ),
            "declares techtree.uplift-report.v9, which this build has no verifier for",
            id="unknown-schema",
        ),
    ],
)
def test_a_proof_this_build_cannot_place_is_refused_not_guessed(
    bundle: Path, damage: Callable[[Path], None], detail: str
) -> None:
    damage(bundle / REPORT_FILENAME)

    verification = verify_proof(bundle, "bundle")

    assert verification.result.verified is False
    assert [message.id for message in verification.result.messages] == [
        "uplift-report.schema"
    ]
    assert detail in verification.result.messages[0].detail
    assert verification.summary == []
