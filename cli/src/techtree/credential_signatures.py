"""The one check for credential signatures in bytes that are about to leave.

Every place that hands a person's files to something outside this machine, or
admits files that will be built and run, asks this module the same question:
does anything here look like a credential? The answer is a list of findings
that say where and what kind, and never the matched text, so a finding can be
printed, logged and put in an error without repeating the secret it found.

The patterns are high-signal shapes only: a private key block, and the token
prefixes that the issuers themselves chose to make leaked keys recognisable.
There is no entropy rule; a generic "looks random" rule would stop ordinary
digests and identifiers, which the proof files are full of.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

__all__ = ["CredentialFinding", "credential_findings"]

#: Each kind of signature, named the way a person would recognise it.
_SIGNATURES: Final[tuple[tuple[str, re.Pattern[bytes]], ...]] = (
    (
        "private key block",
        re.compile(rb"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY(?: BLOCK)?-----"),
    ),
    ("secret API key (sk-)", re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("GitHub token", re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("GitHub token", re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("AWS access key", re.compile(rb"\bAKIA[A-Z0-9]{16}\b")),
    ("Slack token", re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
)


@dataclass(frozen=True, order=True)
class CredentialFinding:
    """Where one credential signature is, and what kind it is. Never the text."""

    path: str
    #: One-based, counted in ``\\n``-separated lines of the bytes checked.
    line: int
    kind: str

    def describe(self) -> str:
        """Say where the finding is and what it looks like, in one phrase."""
        return f"{self.path} line {self.line} ({self.kind})"


def credential_findings(data: bytes, path: str) -> list[CredentialFinding]:
    """Return every credential signature in ``data``, labelled with ``path``.

    Ordered by line, then kind; the same kind twice on one line is one finding.
    """
    found = {
        CredentialFinding(
            path=path, line=data.count(b"\n", 0, match.start()) + 1, kind=kind
        )
        for kind, pattern in _SIGNATURES
        for match in pattern.finditer(data)
    }
    return sorted(found)
