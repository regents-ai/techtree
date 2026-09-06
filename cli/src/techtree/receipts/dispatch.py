"""Choosing which verifier a stored proof is read through. Spec section 7.21.

Two verifiers exist and neither reads the other's documents. The live one,
:mod:`techtree.receipts.verify`, checks a proof written under a v0.2 Campaign;
:mod:`techtree.historical.verify_v01` is the v0.1 release's verifier, kept so
a v0.1 proof keeps verifying with the outcome it had. Which one a proof is
read through is decided by the one thing every proof carries in the same
place: the ``schema_version`` its signed report declares.

The choice is strict. A report that declares a version this build has no
verifier for, a report whose bytes are not a signed envelope at all, and a
proof with no report are all reported as failures rather than guessed at:
verifying a document under a protocol it does not claim would be a verdict
about nothing.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, Protocol

from techtree.constants import UPLIFT_SCHEMA_VERSION, UPLIFT_V2_SCHEMA_VERSION
from techtree.historical import verify_v01
from techtree.identity.models import VerificationMessage, VerificationResult
from techtree.receipts import verify
from techtree.receipts.bundle import PROOF_BUNDLE_INVALID, REPORT_FILENAME

__all__ = [
    "ProofKind",
    "ProofVerification",
    "ProofVerifier",
    "verify_proof",
]

type ProofKind = Literal["bundle", "report"]


class ProofVerifier(Protocol):
    """What both generations' verifiers answer."""

    def verify_report(self, path: Path) -> VerificationResult:
        """Verify one signed report envelope against the key beside it."""

    def verify_bundle(self, path: Path) -> VerificationResult:
        """Verify a whole proof bundle."""

    def explain(self, result: VerificationResult) -> list[VerificationMessage]:
        """Summarize a verification under the headings a reader needs."""


#: One verifier per report schema this build reads. A version absent here is
#: a version this build does not verify, and it says so.
_VERIFIERS: Final[Mapping[str, ProofVerifier]] = {
    UPLIFT_SCHEMA_VERSION: verify_v01.LocalProofVerifier(),
    UPLIFT_V2_SCHEMA_VERSION: verify.LocalProofVerifier(),
}

_FAILED: Final = "failed"


@dataclass(frozen=True)
class ProofVerification:
    """One proof's verification and its reader-facing summary."""

    result: VerificationResult
    summary: list[VerificationMessage]


def verify_proof(path: Path, kind: ProofKind) -> ProofVerification:
    """Verify a proof through the verifier its report's schema names."""
    report_path = path / REPORT_FILENAME if kind == "bundle" else path
    verifier, refusal = _select(report_path)
    if verifier is None:
        assert refusal is not None
        return ProofVerification(
            result=VerificationResult(verified=False, messages=[refusal]),
            summary=[],
        )
    result = (
        verifier.verify_bundle(path)
        if kind == "bundle"
        else verifier.verify_report(path)
    )
    return ProofVerification(result=result, summary=verifier.explain(result))


def _select(
    report_path: Path,
) -> tuple[ProofVerifier | None, VerificationMessage | None]:
    """Read the report's declared schema and return the verifier for it."""
    try:
        raw = report_path.read_bytes()
    except OSError:
        return None, _refusal(f"this proof has no {report_path.name}")
    try:
        document = json.loads(raw)
    except ValueError:
        return None, _refusal(f"{report_path.name} is not a JSON document")
    payload = document.get("payload") if isinstance(document, dict) else None
    schema = payload.get("schema_version") if isinstance(payload, dict) else None
    if not isinstance(schema, str):
        return None, _refusal(
            f"{report_path.name} is not a signed report envelope declaring a "
            "schema version"
        )
    verifier = _VERIFIERS.get(schema)
    if verifier is None:
        return None, _refusal(
            f"{report_path.name} declares {schema}, which this build has no "
            "verifier for"
        )
    return verifier, None


def _refusal(detail: str) -> VerificationMessage:
    return VerificationMessage(
        id="uplift-report.schema",
        status=_FAILED,
        code=PROOF_BUNDLE_INVALID,
        detail=detail,
    )
