"""A credential finding says where and what kind, and never repeats the secret.

Findings are printed, put in errors and handed to host agents, so the one
property that matters is that none of that ever carries the text that matched.
The secrets are assembled at run time so this file holds no token-shaped text.
"""

from __future__ import annotations

import pytest

from techtree.credential_signatures import credential_findings

_SECRETS = [
    "-----BEGIN " + "OPENSSH PRIVATE KEY-----",
    "sk-" + "proj-" + "Q7" * 16,
    "ghp" + "_" + "Z9" * 12,
    "github_pat" + "_" + "11" + "Ab" * 12,
    "AKIA" + "QWERTYUIOP123456",
    "xoxb" + "-" + "1234567890-abcdefghij",
]


@pytest.mark.parametrize("secret", _SECRETS)
def test_a_finding_never_contains_the_secret(secret: str) -> None:
    data = f"first line\nexport TOKEN={secret}\n".encode()

    findings = credential_findings(data, "notes/setup.txt")

    assert findings
    for finding in findings:
        assert finding.line == 2
        for text in (repr(finding), finding.describe(), finding.kind, finding.path):
            assert secret not in text
