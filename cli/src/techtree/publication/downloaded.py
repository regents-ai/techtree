"""Checking a Result bundle downloaded from the run log. Decisions document 0038.

The run log serves each published bundle back as the one document the
participant sent: a :class:`~techtree.publication.models.PublicationSubmission`
whose files are the proof directory, file by file. A sceptic who downloads it
should be able to check it with the same verifier a participant checks their
own run with, and without trusting the site that served it.

So the files are laid back out as a proof directory in a temporary folder, the
bundle verifier reads that directory exactly as it reads one on the machine
that ran it, and one more check is added: the digest the document says it
publishes has to be the digest of the signed manifest inside it. That is the
digest the site shows beside the entry, so a download that verified as a proof
but carried another bundle's name would be caught.

Nothing here contacts anything, and nothing is written outside the temporary
folder, which is gone when the check returns.
"""

from __future__ import annotations

import json
from base64 import b64decode
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Final

from pydantic import ValidationError as PydanticValidationError

from techtree.constants import PUBLICATION_SUBMISSION_SCHEMA_VERSION
from techtree.identity.models import (
    VerificationMessage,
    VerificationResult,
    VerificationStatus,
)
from techtree.models.base import ObjectEnvelope
from techtree.publication.models import PublicationSubmission
from techtree.receipts.bundle import (
    BUNDLE_MANIFEST_FILENAME,
    PROOF_BUNDLE_INVALID,
    LocalProofBundleManifest,
)
from techtree.receipts.dispatch import ProofVerification, verify_proof

__all__ = ["is_downloaded_bundle", "verify_downloaded_bundle"]

_DIGEST_CHECK: Final = "publication.bundle_digest"
_DOCUMENT_CHECK: Final = "publication.document"


def is_downloaded_bundle(path: Path) -> bool:
    """Return whether a file declares itself a published Result bundle."""
    try:
        document = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return False
    return (
        isinstance(document, dict)
        and document.get("schema_version") == PUBLICATION_SUBMISSION_SCHEMA_VERSION
    )


def verify_downloaded_bundle(path: Path) -> ProofVerification:
    """Verify a downloaded Result bundle as the proof directory it carries."""
    try:
        submission = PublicationSubmission.model_validate_json(path.read_bytes())
    except (OSError, PydanticValidationError):
        return _refused(f"{path.name} is not a readable Result bundle")

    with TemporaryDirectory(prefix="techtree-published-") as scratch:
        root = Path(scratch)
        for name, encoded in submission.files.items():
            relative = _relative(name)
            if relative is None:
                return _refused(f"{path.name} places a file outside its bundle: {name}")
            destination = root.joinpath(*relative.parts)
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b64decode(encoded, validate=True))
            except OSError:
                return _refused(f"{path.name} places two files at {name}")
        verification = verify_proof(root, "bundle")
        digest = _digest_check(root, submission)

    result = verification.result
    return ProofVerification(
        result=VerificationResult(
            verified=result.verified and digest.status == "passed",
            messages=[digest, *result.messages],
        ),
        summary=verification.summary,
    )


def _relative(name: str) -> PurePosixPath | None:
    """Return a file's place inside the bundle, or nothing if it escapes it."""
    relative = PurePosixPath(name)
    if relative.is_absolute() or str(relative) != name or ".." in relative.parts:
        return None
    return relative


def _digest_check(root: Path, submission: PublicationSubmission) -> VerificationMessage:
    """Check the document names the bundle it carries."""
    try:
        manifest = ObjectEnvelope[LocalProofBundleManifest].model_validate_json(
            (root / BUNDLE_MANIFEST_FILENAME).read_bytes()
        )
    except (OSError, PydanticValidationError):
        return _message(
            _DIGEST_CHECK,
            "failed",
            f"the bundle's {BUNDLE_MANIFEST_FILENAME} cannot be read",
        )
    if manifest.payload_digest != submission.bundle_digest:
        return _message(
            _DIGEST_CHECK,
            "failed",
            f"the document names bundle {submission.bundle_digest}, but the "
            f"files it carries are bundle {manifest.payload_digest}",
        )
    return _message(
        _DIGEST_CHECK,
        "passed",
        f"the files are the published bundle {submission.bundle_digest}",
    )


def _message(
    identifier: str, status: VerificationStatus, detail: str
) -> VerificationMessage:
    return VerificationMessage(
        id=identifier, status=status, code=PROOF_BUNDLE_INVALID, detail=detail
    )


def _refused(detail: str) -> ProofVerification:
    return ProofVerification(
        result=VerificationResult(
            verified=False, messages=[_message(_DOCUMENT_CHECK, "failed", detail)]
        ),
        summary=[],
    )
