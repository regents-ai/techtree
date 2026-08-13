"""What the engine bundle is, and what it hashes to. Spec section 20.2.

The bundle is the static half of the managed engine: a descriptor, a project
file pinning Verifiers to one commit, the lock that pins everything else, the
two helper tools that run inside the engine, and the reference package source.
It contains no Campaign, Climb, DataPolicy, catalog, golden, or schema, which
is what keeps Campaign generation free of a digest cycle (spec section 20.1).

Everything here is content-addressed by the same construction: enumerate the
files deterministically, describe each one by relative path, size, and content
digest, sort by path, and digest the canonical JSON manifest. The manifest
schema is named so that a digest can never be confused with the digest of some
other kind of tree — an engine bundle and a package tree hash differently even
if they somehow held identical files.

What is excluded from a digest is as much a part of the contract as what is
included. A virtual environment, a bytecode cache, and the local installation
marker are all things that appear *because* an engine was installed. Hashing
them would make an engine's digest change the moment it was used, which is the
opposite of what a content address is for.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from importlib.resources import files as resource_files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Final

from techtree.canonical import digest_object, sha256_digest_bytes
from techtree.errors import EngineError, ValidationError
from techtree.fs import ensure_private_directory
from techtree.models.base import Digest, JsonValue
from techtree.models.engine import EngineDescriptor

__all__ = [
    "BUNDLE_MANIFEST_SCHEMA",
    "DEFAULT_ENGINE_NAME",
    "DESCRIPTOR_FILENAME",
    "ENGINE_TOOLS",
    "INSTALLATION_FILENAME",
    "PACKAGES_DIRECTORY",
    "PACKAGE_MANIFEST_SCHEMA",
    "TOOLS_DIRECTORY",
    "BundleFile",
    "content_manifest",
    "copy_engine_bundle",
    "default_engine_descriptor",
    "default_engine_digest",
    "embedded_engine_root",
    "engine_bundle_digest",
    "enumerate_bundle_files",
    "package_source_digest",
    "read_engine_descriptor",
]

DEFAULT_ENGINE_NAME: Final = "default"
DESCRIPTOR_FILENAME: Final = "engine.json"
#: Written by the installer when an installation is complete, and therefore
#: never part of what the bundle hashes to.
INSTALLATION_FILENAME: Final = "installed.json"
PACKAGES_DIRECTORY: Final = "packages"
TOOLS_DIRECTORY: Final = "tools"

#: The helpers that run inside the managed engine. Decisions document 0003 A3
#: puts them inside the digested bundle: they are shipped, hashed, and copied
#: unchanged, so the code that inspects a taskset is pinned exactly as tightly
#: as the library it inspects it with.
ENGINE_TOOLS: Final[tuple[str, ...]] = (
    "inspect_taskset.py",
    "normalize_validation.py",
)

#: Manifest schema names. They are part of the hashed bytes, so a bundle digest
#: and a package-tree digest are different values by construction.
BUNDLE_MANIFEST_SCHEMA: Final = "techtree.engine-bundle.v1"
#: Decisions document 0003 A8.
PACKAGE_MANIFEST_SCHEMA: Final = "techtree.package-content.v1"

#: Directories that exist because an engine was built or used, never because it
#: was authored.
_EXCLUDED_DIRECTORIES: Final[frozenset[str]] = frozenset(
    {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__"}
)
#: Files that are local state or operating-system litter rather than content.
_EXCLUDED_FILENAMES: Final[frozenset[str]] = frozenset(
    {".DS_Store", INSTALLATION_FILENAME}
)
_EXCLUDED_SUFFIXES: Final[tuple[str, ...]] = (".pyc", ".pyo", ".tmp")

#: An engine name becomes a resource path segment, so it is restricted to a
#: shape that cannot escape the resources directory.
_ENGINE_NAME_RE: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class BundleFile:
    """One file in a hashed tree, described by content rather than by mtime."""

    relative_path: str
    size: int
    digest: Digest


def embedded_engine_root(name: str = DEFAULT_ENGINE_NAME) -> Traversable:
    """Locate one packaged engine bundle inside the installed distribution."""
    if _ENGINE_NAME_RE.fullmatch(name) is None:
        raise ValidationError(
            f"{name!r} is not a valid engine name",
            details={"name": name},
        )

    root = resource_files("techtree") / "resources" / "engines" / name
    if not root.is_dir():
        raise EngineError(
            f"this build does not ship an engine named {name!r}",
            code="engine_bundle_missing",
            details={"name": name},
        )
    return root


def enumerate_bundle_files(root: Traversable) -> list[BundleFile]:
    """Enumerate a tree deterministically, by relative path.

    Sorting is by the POSIX relative path, so the order does not depend on the
    filesystem, the platform, or the order the files were written in.
    """
    return sorted(_walk(root, prefix=""), key=lambda entry: entry.relative_path)


def content_manifest(
    schema_version: str, files: Sequence[BundleFile]
) -> dict[str, JsonValue]:
    """Return the canonical manifest that a tree digest is taken over."""
    return {
        "schema_version": schema_version,
        "files": [
            {
                "path": entry.relative_path,
                "size": entry.size,
                "digest": entry.digest,
            }
            for entry in files
        ],
    }


def engine_bundle_digest(root: Traversable) -> Digest:
    """Return the digest of one engine bundle's static contents."""
    return digest_object(
        content_manifest(BUNDLE_MANIFEST_SCHEMA, enumerate_bundle_files(root))
    )


def package_source_digest(package_root: Traversable) -> Digest:
    """Return the source-tree digest of one shipped package.

    Decisions document 0003 A8: this is a digest of the *source* the engine
    installs, not of a wheel and not of what lands in site-packages. It is one
    of the three values required to be equal — the Campaign's package digest,
    the engine descriptor's ``source_digest``, and the TasksetLock's
    ``resolved_package_digest``.
    """
    return digest_object(
        content_manifest(PACKAGE_MANIFEST_SCHEMA, enumerate_bundle_files(package_root))
    )


def read_engine_descriptor(root: Traversable) -> EngineDescriptor:
    """Load and validate ``engine.json`` from a bundle."""
    descriptor = root / DESCRIPTOR_FILENAME
    if not descriptor.is_file():
        raise EngineError(
            f"engine bundle has no {DESCRIPTOR_FILENAME}",
            code="engine_descriptor_missing",
            details={"file": DESCRIPTOR_FILENAME},
        )

    raw = descriptor.read_bytes()
    try:
        return EngineDescriptor.model_validate_json(raw)
    except ValueError as error:
        raise ValidationError(
            f"engine descriptor is not a valid EngineDescriptor: {error}",
            details={"file": DESCRIPTOR_FILENAME},
        ) from error


def copy_engine_bundle(root: Traversable, destination: Path) -> None:
    """Copy exactly the hashed files of a bundle into an empty directory.

    Only enumerated files are written, so an installed bundle contains the same
    bytes the digest was taken over and nothing else — no bytecode cache from
    the developer's machine, no stray editor file. Content is written rather
    than linked: an installed engine must not change because a source tree
    somewhere else did.
    """
    if destination.is_dir() and any(destination.iterdir()):
        raise EngineError(
            f"refusing to copy an engine bundle into a non-empty directory: "
            f"{destination}",
            code="engine_destination_not_empty",
            details={"path": str(destination)},
        )

    ensure_private_directory(destination)
    for entry in enumerate_bundle_files(root):
        target = destination / entry.relative_path
        ensure_private_directory(target.parent)
        source: Traversable = root
        for segment in entry.relative_path.split("/"):
            source = source / segment
        target.write_bytes(source.read_bytes())


def default_engine_descriptor() -> EngineDescriptor:
    """Return the descriptor of the engine this build ships."""
    return read_engine_descriptor(embedded_engine_root())


def default_engine_digest() -> Digest:
    """Return the digest of the engine bundle this build ships."""
    return engine_bundle_digest(embedded_engine_root())


def _walk(root: Traversable, *, prefix: str) -> Iterator[BundleFile]:
    """Yield every included file under ``root``, depth first."""
    for entry in root.iterdir():
        name = entry.name
        relative = f"{prefix}{name}"

        if entry.is_dir():
            if name in _EXCLUDED_DIRECTORIES:
                continue
            yield from _walk(entry, prefix=f"{relative}/")
            continue

        if name in _EXCLUDED_FILENAMES or name.endswith(_EXCLUDED_SUFFIXES):
            continue

        content = entry.read_bytes()
        yield BundleFile(
            relative_path=relative,
            size=len(content),
            digest=sha256_digest_bytes(content),
        )
