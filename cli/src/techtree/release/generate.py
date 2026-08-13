"""Binding one release together. Spec sections 9.3.1, 9.3.3 and 9.4.

Generation is the step that turns "a source tree and a handful of founder
decisions" into one document every other repository copies. It runs *before*
the wheel is built and before the plugin is tagged, so nothing it reads may
depend on either — that ordering is the whole reason the cross-repository
binding has no cycle in it (spec section 9.3.3).

Two kinds of value meet here and they are kept strictly apart.

The founder's decisions arrive as :class:`~techtree.release.models.
ReleaseInputs`, read from a file a person edits. This module never invents one
and never guesses a default for one.

Everything else is *read out of the tree being released* — the protocol
version, the digest of the engine bundle, the digest of the catalog index, and
the subject harness version the introductory Climb's Campaign pins. Those are
facts about the source, so asking a person for them would only create a second
answer that could disagree with the first.

The introductory Climb reference sits on the seam: the founder chooses which
Climb the release leads with, and this module refuses the choice unless the
catalog actually ships it under exactly that reference. A release that
advertises a Climb nobody shipped is the failure this check exists for.

Generation is deterministic. The same source tree and the same inputs produce
the same bytes on any machine, at any time, which is what lets a drift check
regenerate the artifacts into a throwaway copy of the repository and compare.
Nothing here reads the clock, the environment, the network, or version control.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources.abc import Traversable
from typing import Final

from techtree.catalog.repository import (
    CATALOG_INDEX_FILENAME,
    EmbeddedCatalogRepository,
    packaged_catalog_root,
)
from techtree.engines.bundle import embedded_engine_root, engine_bundle_digest
from techtree.errors import ValidationError
from techtree.models.base import Digest, JsonValue
from techtree.release.document import document_digest
from techtree.release.models import (
    BUILD_INFO_SCHEMA_VERSION,
    RELEASE_CORE_SCHEMA_VERSION,
    ReleaseCore,
    ReleaseInputs,
    declared_placeholder_fields,
)
from techtree.version import PROTOCOL_VERSION

__all__ = [
    "GENERATOR_VERSION",
    "ReleaseSources",
    "build_info_document",
    "build_release_core",
    "packaged_sources",
]

#: Bumped when the generated shape changes, so a stored artifact can say which
#: generator produced it.
GENERATOR_VERSION: Final = "0.1.0"


@dataclass(frozen=True)
class ReleaseSources:
    """The part of a release that is read rather than decided."""

    catalog_root: Traversable
    engine_root: Traversable
    protocol_version: str

    def catalog_index_bytes(self) -> bytes:
        """Return the exact bytes of the catalog index."""
        return (self.catalog_root / CATALOG_INDEX_FILENAME).read_bytes()


def packaged_sources() -> ReleaseSources:
    """Return the sources of the build this process is running from."""
    return ReleaseSources(
        catalog_root=packaged_catalog_root(),
        engine_root=embedded_engine_root(),
        protocol_version=PROTOCOL_VERSION,
    )


def build_release_core(inputs: ReleaseInputs, sources: ReleaseSources) -> ReleaseCore:
    """Bind founder decisions and source facts into one ReleaseCore."""
    catalog = EmbeddedCatalogRepository(sources.catalog_root)
    reference = _exact_climb_reference(catalog, inputs.intro_climb_reference)
    climb = catalog.load_climb(reference)
    campaign = catalog.load_campaign(climb.campaign_spec_digest)

    values = {
        "cli_source_commit": inputs.cli_source_commit,
        "cli_version": inputs.cli_version,
        "maximum_tested_host_hermes_version": (
            inputs.maximum_tested_host_hermes_version
        ),
        "minimum_host_hermes_version": inputs.minimum_host_hermes_version,
        "release_id": inputs.release_id,
        "rich_output_skill_digest": inputs.rich_output_skill_digest,
        "skill_improver_digest": inputs.skill_improver_digest,
        "starter_skill_digest": inputs.starter_skill_digest,
    }
    placeholders = declared_placeholder_fields(values)

    return ReleaseCore(
        schema_version=RELEASE_CORE_SCHEMA_VERSION,
        placeholder_release=bool(placeholders),
        placeholder_fields=placeholders,
        protocol_version=sources.protocol_version,
        engine_digest=engine_bundle_digest(sources.engine_root),
        catalog_digest=document_digest(sources.catalog_index_bytes()),
        intro_climb_reference=reference,
        subject_hermes_version=campaign.subject.harness.version,
        **values,
    )


def build_info_document(
    *,
    inputs_digest: Digest,
    pyproject_version: str,
    core: ReleaseCore,
    artifacts: Mapping[str, Digest],
) -> dict[str, JsonValue]:
    """Return what was built, from what, without reading the clock.

    A build record normally starts with a timestamp. This one cannot: the
    artifacts it describes are regenerated in a throwaway copy of the
    repository and compared byte for byte, so anything that changes between two
    identical builds would turn every drift check into a false alarm. What
    matters for support is which inputs produced which bytes, and that is what
    is recorded.

    ``pyproject_version`` is recorded even though the ReleaseCore names the
    published CLI version separately. While a release is still a placeholder
    those two differ on purpose, and both a support conversation and the
    version check in :mod:`techtree.release.checks` need to see both.

    ``artifacts`` does not include this document. A build record cannot state
    its own digest, and pretending otherwise would only produce a value that
    could never be recomputed.
    """
    return {
        "schema_version": BUILD_INFO_SCHEMA_VERSION,
        "generator": "tools/build_release_core.py",
        "generator_version": GENERATOR_VERSION,
        "placeholder_release": core.placeholder_release,
        "placeholder_fields": list(core.placeholder_fields),
        "inputs": {
            "release_inputs_digest": inputs_digest,
            "pyproject_version": pyproject_version,
            "protocol_version": core.protocol_version,
            "engine_digest": core.engine_digest,
            "catalog_digest": core.catalog_digest,
            "intro_climb_reference": core.intro_climb_reference,
        },
        "artifacts": dict(sorted(artifacts.items())),
    }


def _exact_climb_reference(catalog: EmbeddedCatalogRepository, reference: str) -> str:
    """Return the reference, having proved the catalog ships exactly it.

    The repository resolves a bare slug to the newest version, which is right
    for a person browsing and wrong for a release document: a release names one
    immutable Climb, and it has to name it the way the catalog files it.
    """
    available = catalog.list_climb_references()
    if reference not in available:
        raise ValidationError(
            f"the release names {reference!r} as its introductory Climb, but "
            "this catalog does not ship that exact reference",
            code="intro_climb_not_in_catalog",
            details={"reference": reference, "available": list(available)},
        )
    return reference
