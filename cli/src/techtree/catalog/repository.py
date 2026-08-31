"""Reading the embedded catalog. Spec section 14.2, decisions 0003 A7.

Everything in a Techtree catalog is addressed by what it contains. The index
maps a public reference, and every object digest that reference depends on, to
a file inside the package; nothing else in the system is allowed to name one of
those files directly. That indirection is what this module exists to enforce.

Three rules do the work.

*Recompute, never trust.* Every object is parsed into its protocol model and
re-digested from the model's canonical form. A file whose contents drifted from
the digest it is filed under is a :class:`~techtree.errors.VerificationError`,
not a warning, and not something a later stage discovers.

*Stay inside the root.* Index paths are relative, normalized, and non-escaping
— :class:`~techtree.models.catalog.CatalogIndex` rejects the spellings a
document can be checked for — and this module additionally refuses a resolved
path that leaves the catalog directory through a symlink, which no document
inspection could see.

*The kind is part of the address.* Asking for a Campaign at a digest the index
files as a DataPolicy fails on the index entry, before any bytes are parsed. A
caller therefore cannot be handed the wrong kind of object by a catalog that
merely points somewhere plausible.

Embedded objects are unsigned in WP0–WP5. A future remote catalog can wrap
these same objects in a signed envelope without changing anything here: the
graph is resolved from digests, and a signature would be checked before the
digests are believed, not instead of it.
"""

from __future__ import annotations

import json
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Final, Self

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import canonical_json_bytes, digest_object, sha256_digest_bytes
from techtree.errors import NotFoundError, ValidationError, VerificationError
from techtree.fs import realpath_within
from techtree.models.base import Digest, JsonValue
from techtree.models.campaign import CampaignSpec
from techtree.models.catalog import (
    CatalogClimbEntry,
    CatalogIndex,
    CatalogObjectLocation,
)
from techtree.models.climb import ClimbManifest
from techtree.models.data_policy import DataPolicy
from techtree.models.validation import TasksetValidationReceipt, ValidationEvidence

__all__ = [
    "CATALOG_INDEX_FILENAME",
    "EmbeddedCatalogRepository",
    "climb_reference",
    "packaged_catalog_root",
]

#: The one file in a catalog directory that is not content-addressed. It is the
#: entry point, so it is named rather than hashed.
CATALOG_INDEX_FILENAME: Final = "catalog.json"

#: What the index calls each kind of object, keyed by the model the caller asks
#: for. Keeping the mapping here rather than at each call site is what makes
#: "the kind is part of the address" a single rule instead of four.
_KIND_FOR_MODEL: Final[dict[type[BaseModel], str]] = {
    CampaignSpec: "campaign",
    DataPolicy: "data_policy",
    TasksetValidationReceipt: "taskset_validation",
    ValidationEvidence: "validation_evidence",
}

#: How a public reference is spelled: ``<slug>@<version>``.
_REFERENCE_SEPARATOR: Final = "@"

#: The identifier prefix a Climb's public ID carries. Used to decide whether a
#: reference that resolved to nothing is worth looking for by identity.
_CLIMB_ID_PREFIX: Final = "climb_"


def packaged_catalog_root() -> Traversable:
    """Return the catalog directory shipped inside the installed package."""
    return resources.files("techtree") / "resources" / "catalog"


def climb_reference(climb: ClimbManifest) -> str:
    """Return the public reference a Climb manifest spells out."""
    return f"{climb.metadata.slug}{_REFERENCE_SEPARATOR}{climb.metadata.version}"


class EmbeddedCatalogRepository:
    """Loads and verifies the objects one catalog directory contains."""

    def __init__(self, resource_root: Traversable) -> None:
        self._root = resource_root
        self._index: CatalogIndex | None = None

    @classmethod
    def packaged(cls) -> Self:
        """Return a repository over the catalog this build ships."""
        return cls(packaged_catalog_root())

    # -- The index ---------------------------------------------------------

    def index(self) -> CatalogIndex:
        """Return the validated catalog index, reading it at most once.

        Reading the index is also when the catalog is checked for the failures
        a document cannot state about itself: a path that names no file, or a
        path that leaves the catalog root. Both are defects in a generated
        artifact, so they are reported once, at the door, rather than by
        whichever command happened to need that object first.
        """
        if self._index is not None:
            return self._index

        raw = self._read_bytes(
            CATALOG_INDEX_FILENAME, self._resolve(CATALOG_INDEX_FILENAME)
        )
        try:
            index = CatalogIndex.model_validate_json(raw)
        except PydanticValidationError as error:
            raise ValidationError(
                f"the catalog index is not a valid catalog: {_first_problem(error)}",
                code="catalog_index_invalid",
                details={"path": CATALOG_INDEX_FILENAME},
            ) from error

        for entry in index.climbs:
            self._resolve(entry.path)
        for location in index.objects.values():
            self._resolve(location.path)

        self._index = index
        return index

    def catalog_metadata(self) -> dict[str, JsonValue]:
        """Return what the validated index says about itself."""
        index = self.index()
        return {
            "schema_version": index.schema_version,
            "climb_count": len(index.climbs),
            "object_count": len(index.objects),
        }

    def list_climb_references(self) -> list[str]:
        """Return the public references this catalog ships, in index order."""
        return [entry.reference for entry in self.index().climbs]

    # -- Climbs ------------------------------------------------------------

    def climb_entry(self, reference: str) -> CatalogClimbEntry:
        """Resolve a slug, a ``slug@version``, or an exact public ID.

        A bare slug resolves to the highest version the catalog ships, because
        a reader who did not name a version is asking for the current one. A
        public identifier costs a scan: identity lives inside the manifest, and
        the index deliberately addresses objects by digest rather than by name.
        """
        index = self.index()

        for entry in index.climbs:
            if entry.reference == reference:
                return entry

        by_slug = [
            entry
            for entry in index.climbs
            if _reference_slug(entry.reference) == reference
        ]
        if by_slug:
            return max(by_slug, key=lambda entry: _reference_version(entry.reference))

        if reference.startswith(_CLIMB_ID_PREFIX):
            for entry in index.climbs:
                if self._load_climb_entry(entry).metadata.id == reference:
                    return entry

        raise NotFoundError(
            f"this build ships no Climb called {reference!r}",
            code="climb_not_found",
            details={
                "reference": reference,
                "available": [entry.reference for entry in index.climbs],
            },
        )

    def load_climb(self, reference: str) -> ClimbManifest:
        """Load and verify one public Climb manifest."""
        return self._load_climb_entry(self.climb_entry(reference))

    # -- Content-addressed objects ----------------------------------------

    def load_object(self, digest: Digest) -> JsonValue:
        """Load the JSON document filed under one digest, verifying the digest.

        The verification is over the canonical form of what was parsed, which
        is the same form the typed loaders digest. A document that is only
        differently indented therefore verifies, and a document whose content
        changed does not.
        """
        location = self._object_location(digest)
        raw = self._read_bytes(location.path, self._resolve(location.path))
        document = _parse_json(raw, location.path)

        recomputed = sha256_digest_bytes(canonical_json_bytes(document))
        if recomputed != digest:
            raise self._digest_mismatch(digest, recomputed, location.path)
        return document

    def load_campaign(self, digest: Digest) -> CampaignSpec:
        """Load and verify one CampaignSpec."""
        return self._load_model(digest, CampaignSpec)

    def load_data_policy(self, digest: Digest) -> DataPolicy:
        """Load and verify one DataPolicy."""
        return self._load_model(digest, DataPolicy)

    def load_validation_receipt(self, digest: Digest) -> TasksetValidationReceipt:
        """Load and verify one publisher validation receipt."""
        return self._load_model(digest, TasksetValidationReceipt)

    def load_validation_evidence(self, digest: Digest) -> ValidationEvidence:
        """Load and verify one normalized validation evidence document."""
        return self._load_model(digest, ValidationEvidence)

    # -- Internals ---------------------------------------------------------

    def _load_climb_entry(self, entry: CatalogClimbEntry) -> ClimbManifest:
        """Load the manifest one index entry points at and check it agrees."""
        climb = self._parse_model(
            self._read_bytes(entry.path, self._resolve(entry.path)),
            ClimbManifest,
            entry.path,
        )

        recomputed = digest_object(climb)
        if recomputed != entry.digest:
            raise self._digest_mismatch(entry.digest, recomputed, entry.path)

        stated = climb_reference(climb)
        if stated != entry.reference:
            raise ValidationError(
                f"the catalog lists {entry.reference!r} but the manifest at that "
                f"path calls itself {stated!r}",
                code="catalog_reference_mismatch",
                details={"indexed": entry.reference, "manifest": stated},
            )
        return climb

    def _load_model[ModelT: BaseModel](
        self, digest: Digest, model: type[ModelT]
    ) -> ModelT:
        """Load, type-check, and digest-verify one content-addressed object."""
        location = self._object_location(digest)
        expected_kind = _KIND_FOR_MODEL[model]
        if location.kind != expected_kind:
            raise ValidationError(
                f"the catalog files {digest} as a {location.kind} object, and a "
                f"{expected_kind} object was asked for",
                code="catalog_kind_mismatch",
                details={
                    "digest": digest,
                    "indexed_kind": location.kind,
                    "requested_kind": expected_kind,
                },
            )

        raw = self._read_bytes(location.path, self._resolve(location.path))
        loaded = self._parse_model(raw, model, location.path)

        recomputed = digest_object(loaded)
        if recomputed != digest:
            raise self._digest_mismatch(digest, recomputed, location.path)
        return loaded

    def _object_location(self, digest: Digest) -> CatalogObjectLocation:
        location = self.index().objects.get(digest)
        if location is None:
            raise NotFoundError(
                f"the catalog has no object filed under {digest}",
                code="catalog_object_not_found",
                details={"digest": digest},
            )
        return location

    def _resolve(self, relative: str) -> Traversable:
        """Return the file one index path names, refusing anything outside.

        The path spelling was already checked when the index was validated.
        What is checked here is the resolved location: a link inside the
        catalog that points out of it is a valid-looking path to a file the
        package does not ship.
        """
        child = self._root
        for segment in relative.split("/"):
            if segment in ("", ".", ".."):
                raise ValidationError(
                    f"catalog path {relative!r} is not a normalized relative path",
                    code="catalog_path_traversal",
                    details={"path": relative},
                )
            child = child / segment

        if (
            isinstance(child, Path)
            and isinstance(self._root, Path)
            and not realpath_within(child, self._root)
        ):
            raise ValidationError(
                f"catalog path {relative!r} resolves outside the catalog",
                code="catalog_path_traversal",
                details={"path": relative},
            )

        if not child.is_file():
            raise NotFoundError(
                f"the catalog lists {relative!r}, and this build does not ship it",
                code="catalog_file_missing",
                details={"path": relative},
            )
        return child

    def _read_bytes(self, relative: str, source: Traversable) -> bytes:
        try:
            return source.read_bytes()
        except FileNotFoundError as error:
            raise NotFoundError(
                f"the catalog lists {relative!r}, and this build does not ship it",
                code="catalog_file_missing",
                details={"path": relative},
            ) from error
        except OSError as error:
            raise ValidationError(
                f"the catalog file {relative!r} could not be read: "
                f"{error.strerror or error}",
                code="catalog_file_unreadable",
                details={"path": relative},
            ) from error

    def _parse_model[ModelT: BaseModel](
        self, raw: bytes, model: type[ModelT], relative: str
    ) -> ModelT:
        try:
            return model.model_validate_json(raw)
        except PydanticValidationError as error:
            raise ValidationError(
                f"the catalog file {relative!r} is not a valid "
                f"{model.__name__}: {_first_problem(error)}",
                code="catalog_object_invalid",
                details={"path": relative, "expected": model.__name__},
            ) from error

    def _digest_mismatch(
        self, expected: Digest, recomputed: Digest, relative: str
    ) -> VerificationError:
        return VerificationError(
            f"the catalog file {relative!r} does not match the digest it is "
            "filed under",
            code="catalog_digest_mismatch",
            details={
                "path": relative,
                "expected_digest": expected,
                "computed_digest": recomputed,
            },
        )


def _parse_json(raw: bytes, relative: str) -> JsonValue:
    """Decode one catalog file as JSON, or say which file was not JSON."""
    try:
        document: JsonValue = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(
            f"the catalog file {relative!r} is not valid JSON",
            code="catalog_object_invalid",
            details={"path": relative},
        ) from error
    return document


def _reference_slug(reference: str) -> str:
    return reference.partition(_REFERENCE_SEPARATOR)[0]


def _reference_version(reference: str) -> int:
    _, _, version = reference.partition(_REFERENCE_SEPARATOR)
    return int(version) if version.isdigit() else 0


def _first_problem(error: PydanticValidationError) -> str:
    """Return the first validation problem in words a reader can act on."""
    first = error.errors()[0]
    location = ".".join(str(part) for part in first["loc"])
    return f"{location}: {first['msg']}" if location else str(first["msg"])
