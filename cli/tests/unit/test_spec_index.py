"""The vendored specifications are exactly the bytes the index records.

A fresh checkout must be able to trust that "Spec §N" in a ticket
resolves to the same text the ticket's author read. This test recomputes
every digest in docs/spec/CHECKSUMS.json from the files on disk.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKSUMS = REPO_ROOT / "docs" / "spec" / "CHECKSUMS.json"


def test_every_vendored_spec_matches_its_recorded_digest() -> None:
    manifest = json.loads(CHECKSUMS.read_text(encoding="utf-8"))
    assert manifest["files"], "the spec manifest lists no files"
    for entry in manifest["files"]:
        path = REPO_ROOT / entry["path"]
        assert path.is_file(), f"vendored spec missing: {entry['path']}"
        data = path.read_bytes()
        assert len(data) == entry["bytes"], (
            f"{entry['path']}: {len(data)} bytes on disk, {entry['bytes']} recorded"
        )
        digest = hashlib.sha256(data).hexdigest()
        assert digest == entry["sha256"], (
            f"{entry['path']}: digest drifted from the recorded value"
        )


def test_the_index_document_exists_beside_the_manifest() -> None:
    index = CHECKSUMS.parent / "INDEX.md"
    assert index.is_file()
    text = index.read_text(encoding="utf-8")
    for entry in json.loads(CHECKSUMS.read_text(encoding="utf-8"))["files"]:
        name = Path(entry["path"]).name
        assert name.removesuffix(".md") in text or name in text, (
            f"INDEX.md does not mention {name}"
        )
