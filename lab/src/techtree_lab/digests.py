"""The `sha256:` digests the Train reports name things by."""

from __future__ import annotations

import hashlib
from typing import Any

import rfc8785

from payment_terms.offers import Item


def of_bytes(data: bytes) -> str:
    """`sha256:` and the hex SHA-256 of `data`."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> str:
    """The digest of `value`'s RFC 8785 canonical JSON, as `Techtree.Canonical` encodes it."""
    return of_bytes(rfc8785.dumps(value))


def taskset(items: list[Item]) -> str:
    """The digest of a split: each task's id, prompt and answer, in order."""
    return canonical([{"id": i.id, "prompt": i.prompt, "answer": i.answer} for i in items])
