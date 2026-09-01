"""WP0.8's frozen proposed lock and the founder approval packet that binds it.

The packet asks for approval of one exact lock digest. Nothing here hard-codes
that digest: every figure is recomputed from the committed bytes, so a one-byte
edit to either document fails this suite rather than silently voiding the
approval request.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from techtree.canonical import sha256_digest_bytes

CLI_ROOT = Path(__file__).parents[2]
MONOREPO_ROOT = CLI_ROOT.parent
DOCS_ROOT = MONOREPO_ROOT / "docs" / "v0.2"
LOCK_PATH = DOCS_ROOT / "UPSTREAM_CONTRACT_LOCK.json"
MATRIX_PATH = DOCS_ROOT / "FABRIC_CAPABILITY_MATRIX.json"
PACKET_PATH = DOCS_ROOT / "WP0_FOUNDER_PACKET.md"

DECISION_NUMBERS = tuple(range(1, 17))

DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
LOCK_DIGEST_LINE = re.compile(r"^- Lock digest: `(sha256:[0-9a-f]{64})`$", re.MULTILINE)
MATRIX_DIGEST_LINE = re.compile(
    r"^- Matrix digest: `(sha256:[0-9a-f]{64})`$", re.MULTILINE
)
DECISION_HEADING = re.compile(r"^### Decision (\d+) — .+$", re.MULTILINE)
PACKET_DECISION_REFERENCE = re.compile(r"packet decision (\d+)")

#: A lock value that still reads as unsettled in any of these ways has to be
#: answerable by a numbered decision in the packet.
UNSETTLED_VALUE = re.compile(r"pending|blocked|proposed|unresolved", re.IGNORECASE)


def packet_text() -> str:
    return PACKET_PATH.read_text(encoding="utf-8")


def load_lock() -> dict[str, Any]:
    document = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def walk(value: object, path: str = "") -> list[tuple[str, object, object]]:
    """Yield ``(path, container, value)`` for every node under ``value``."""

    found: list[tuple[str, object, object]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            found.append((f"{path}.{key}", value, child))
            found.extend(walk(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.append((f"{path}[{index}]", value, child))
            found.extend(walk(child, f"{path}[{index}]"))
    return found


def test_the_packet_requests_one_lock_digest_and_it_is_the_lock_file() -> None:
    text = packet_text()
    lock_digest = sha256_digest_bytes(LOCK_PATH.read_bytes())
    matrix_digest = sha256_digest_bytes(MATRIX_PATH.read_bytes())

    named = LOCK_DIGEST_LINE.findall(text)
    assert named == [lock_digest]

    #: Exactly one lock digest is named. The packet may repeat that one digest
    #: for the reader, but no second, different lock digest may appear, so the
    #: distinct digests in the document are the lock's and the matrix's.
    assert set(DIGEST_PATTERN.findall(text)) == {lock_digest, matrix_digest}

    assert MATRIX_DIGEST_LINE.findall(text) == [matrix_digest]
    assert lock_digest != matrix_digest

    #: The packet says which bytes it is talking about and where they sit.
    assert "docs/v0.2/UPSTREAM_CONTRACT_LOCK.json" in text
    assert "docs/v0.2/FABRIC_CAPABILITY_MATRIX.json" in text
    assert "3355bff7fcd80ee493c8384a0ba23bf4951ab2d5" in text

    #: The lock pins the matrix, so the pair is approved together.
    lock = load_lock()
    assert lock["nemo_fabric"]["capability_matrix_sha256"] == matrix_digest


def test_the_lock_has_no_null_and_no_unexplained_pending_field() -> None:
    lock = load_lock()
    nodes = walk(lock)

    nulls = [path for path, _container, value in nodes if value is None]
    assert nulls == []

    for path, container, value in nodes:
        if not isinstance(value, str) or not UNSETTLED_VALUE.search(value):
            continue
        assert isinstance(container, dict), path
        #: A field that still reads as unsettled has to be answerable by a
        #: numbered decision in the packet, and the pointer has to come from a
        #: key that says it is a decision — not from prose that happens to
        #: mention one.
        pointers = " ".join(
            sibling
            for key, sibling in container.items()
            if "decision" in key.lower() and isinstance(sibling, str)
        )
        referenced = [
            int(number) for number in PACKET_DECISION_REFERENCE.findall(pointers)
        ]
        assert referenced, path
        assert set(referenced) <= set(DECISION_NUMBERS), path

    #: Every decision the lock points at is a decision the packet actually asks.
    cited = {
        int(number) for number in PACKET_DECISION_REFERENCE.findall(json.dumps(lock))
    }
    assert cited
    assert cited <= set(DECISION_NUMBERS)


def test_the_lock_is_proposed_and_its_approval_is_only_requested() -> None:
    lock = load_lock()
    approval = lock["approval"]

    assert lock["status"] == "proposed_awaiting_founder_approval_of_this_exact_digest"
    assert approval["status"] == "requested"
    assert approval["status"] != "approved"
    assert approval["approved_at"] == "not_yet_approved"
    assert approval["packet"] == "docs/v0.2/WP0_FOUNDER_PACKET.md"
    assert PACKET_PATH.exists()

    #: The freeze policy survives the freeze.
    assert lock["freeze_policy"] == {
        "frozen_after_commit": True,
        "replacement_requires_founder_decision": True,
        "replacement_requires_fixture_regeneration": True,
        "replacement_requires_affected_conformance_rerun": True,
    }


def test_the_packet_asks_all_sixteen_decisions_once_and_leaves_them_blank() -> None:
    text = packet_text()

    headings = [int(number) for number in DECISION_HEADING.findall(text)]
    assert headings == list(DECISION_NUMBERS)

    sections = re.split(r"^### Decision \d+ — ", text, flags=re.MULTILINE)[1:]
    assert len(sections) == len(DECISION_NUMBERS)
    for number, section in zip(DECISION_NUMBERS, sections, strict=True):
        answers = re.findall(r"^Answer:(.*)$", section, flags=re.MULTILINE)
        assert len(answers) == 1, number
        remainder = answers[0].strip()
        #: Decision 16 is answered by the approval line in section 2 and says
        #: so. Every other slot is blank, waiting for the founder.
        if number == 16:
            assert remainder.rstrip(".") == "see section 2"
        else:
            assert remainder == "", number

    #: The single approval request is unfilled too.
    assert "**Approve / Change:**\n" in text
    assert "**Signature line:**\n" in text


def test_no_changed_v02_document_carries_private_or_internal_material() -> None:
    provider_id = re.compile(r"(?<![0-9a-z])[0-9a-z]{24,25}(?![0-9a-z])")
    for path in (PACKET_PATH, LOCK_PATH, MATRIX_PATH):
        text = path.read_text(encoding="utf-8")
        assert re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text) is None, path.name
        assert "/Users/" not in text, path.name
        assert re.search(r"Bearer [A-Za-z0-9_-]{20,}", text) is None, path.name
        assert "sk-ant-" not in text, path.name
        assert "sk-proj-" not in text, path.name
        assert "PRIME_API_KEY=" not in text, path.name
        assert provider_id.findall(text) == [], path.name

    #: The public coordinate stands in for the withheld provider identifiers.
    prime = load_lock()["prime_hosted_evaluations"]
    identity = prime["environment_identity"]
    assert identity["provider_internal_identifiers"] == "withheld_by_policy"
    assert identity["public_coordinate"] == "techtree/techtree-v02-conformance@0.1.0"
    assert (
        identity["published_wheel_sha256"]
        == (prime["environment_published_wheel_sha256"])
    )
    assert "environment_id" not in prime
    assert "environment_version_id" not in prime
