"""The bytes of a release document, and the digest taken over them.

Spec sections 9.3.1 and 9.5.

Every other digest in Techtree is taken over the RFC 8785 canonical form of a
parsed object, because the object is what two independent builds have to agree
about. A ReleaseCore is different in one respect that decides this module: the
specification requires *identical bytes* in the CLI package, in the plugin
repository, and in the website wrapper, and two of those three consumers are
not Python. So the ReleaseCore digest is the SHA-256 of the file, exactly as
the file is stored, which is the same construction the website already uses for
the catalog index and is checkable with ``shasum`` in any repository.

That only works if the file has one spelling, so this module owns it: keys
sorted, two-space indent, no ASCII escaping, one trailing newline. It is the
house style of every other generated JSON document in the tree, and
:func:`is_canonical_document` lets a verification prove a stored file is
still in it — a hand-edit that changes nothing but whitespace still changes the
digest, and that has to be reported as tampering rather than tolerated.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from importlib.resources import files as resource_files
from importlib.resources.abc import Traversable
from typing import Final

from techtree.canonical import sha256_digest_bytes
from techtree.errors import ValidationError
from techtree.models.base import Digest, JsonValue
from techtree.release.models import ReleaseCore, ReleaseInputs

__all__ = [
    "RELEASE_CORE_FILENAME",
    "RELEASE_RESOURCE_DIRECTORY",
    "document_digest",
    "is_canonical_document",
    "packaged_release_core_bytes",
    "packaged_release_root",
    "parse_release_core",
    "parse_release_inputs",
    "render_document",
    "render_release_core",
]

#: The file, wherever it is stored. The plugin repository and the website use
#: the same name, so a person moving bytes between repositories never has to
#: translate.
RELEASE_CORE_FILENAME: Final = "release-core.json"

#: Where the shipped copy lives inside the installed distribution.
RELEASE_RESOURCE_DIRECTORY: Final = "release"


def render_document(payload: Mapping[str, JsonValue]) -> bytes:
    """Return the one byte spelling of a release document."""
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    return f"{text}\n".encode()


def is_canonical_document(raw: bytes) -> bool:
    """Return whether these bytes are already in the one stored spelling."""
    try:
        payload = json.loads(raw)
    except ValueError:
        return False
    if not isinstance(payload, dict):
        return False
    return render_document(payload) == raw


def document_digest(raw: bytes) -> Digest:
    """Return the digest a release document is published under."""
    return sha256_digest_bytes(raw)


def render_release_core(core: ReleaseCore) -> bytes:
    """Return the stored bytes of a ReleaseCore."""
    return render_document(core.model_dump(mode="json"))


def parse_release_core(raw: bytes) -> ReleaseCore:
    """Load and validate a ReleaseCore from stored bytes."""
    try:
        return ReleaseCore.model_validate_json(raw)
    except ValueError as error:
        raise ValidationError(
            f"this is not a valid ReleaseCore: {error}",
            code="release_core_invalid",
        ) from error


def parse_release_inputs(raw: bytes) -> ReleaseInputs:
    """Load and validate the founder-owned release inputs."""
    try:
        return ReleaseInputs.model_validate_json(raw)
    except ValueError as error:
        raise ValidationError(
            f"this is not a valid release input file: {error}",
            code="release_inputs_invalid",
        ) from error


def packaged_release_root() -> Traversable:
    """Return the release directory shipped inside the installed package."""
    return resource_files("techtree") / "resources" / RELEASE_RESOURCE_DIRECTORY


def packaged_release_core_bytes() -> bytes:
    """Return the exact ReleaseCore bytes this build ships.

    A build with no ReleaseCore is not a release, so the absence is a typed
    failure rather than an empty answer.
    """
    document = packaged_release_root() / RELEASE_CORE_FILENAME
    if not document.is_file():
        raise ValidationError(
            "this build ships no ReleaseCore; it was not produced by the "
            "release generator",
            code="release_core_missing",
            details={"file": RELEASE_CORE_FILENAME},
        )
    return document.read_bytes()
