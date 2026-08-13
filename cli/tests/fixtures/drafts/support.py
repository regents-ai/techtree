"""Shared construction for the PR6 draft tests. Spec PR6 §6.2.

Everything here builds on the complete synthetic catalog fixture rather than
inventing a second one. That fixture already holds a Climb, a Campaign, a
DataPolicy, a publisher receipt, and the normalized evidence the receipt was
issued from, with every digest computed from the real bytes — which is exactly
the graph preparation consumes.

The helpers come in two layers. :func:`synthetic_graph` assembles the resolved
objects in memory, which is what the manifest tests need. :func:`prepare_draft`
runs the real preparation service against the fixture on disk, which is what
the draft-store tests need: a store test that built its own draft by hand would
be testing the test.

Nothing here reaches the network, starts a process, or writes outside the
directory it is given.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Final

from techtree.canonical import digest_object
from techtree.catalog.repository import EmbeddedCatalogRepository
from techtree.catalog.service import CatalogService, HostInfo
from techtree.drafts.confirmation import ConfirmationService
from techtree.drafts.store import DraftStore
from techtree.models.base import Digest
from techtree.models.campaign import CampaignSpec, PublicContext
from techtree.models.catalog import EngineCompatibilityStatus
from techtree.models.climb import ClimbManifest, ResolvedClimb
from techtree.models.validation import ValidationEvidence
from techtree.paths import TechtreePaths, paths_from_root
from techtree.skills.service import PreparedDraft, SkillPreparationService

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[2]
CATALOG_FIXTURES: Final = REPOSITORY_ROOT / "fixtures" / "catalog"
COMPLETE_CATALOG: Final = CATALOG_FIXTURES / "complete"
SKILL_FIXTURES: Final = REPOSITORY_ROOT / "fixtures" / "skills"
VALID_SKILL: Final = SKILL_FIXTURES / "valid-procedure"

#: A host Techtree supports, stated rather than detected so that what these
#: tests assert does not depend on the machine running them.
SUPPORTED_HOST: Final = HostInfo(
    operating_system="linux", architecture="x86_64", python_version="3.12.0"
)


class InstalledEngine:
    """An engine source that reports whatever the test needs it to."""

    def __init__(
        self, status: EngineCompatibilityStatus = EngineCompatibilityStatus.VERIFIED
    ) -> None:
        self._status = status

    def status_for(self, engine_digest: Digest) -> EngineCompatibilityStatus:
        """Return the status this stub was constructed with."""
        return self._status


@dataclass(frozen=True)
class SyntheticGraph:
    """The resolved objects a draft is prepared from."""

    resolved: ResolvedClimb
    evidence: ValidationEvidence

    @property
    def campaign(self) -> CampaignSpec:
        """Return the Campaign the Climb wraps."""
        return self.resolved.campaign

    @property
    def campaign_digest(self) -> Digest:
        """Return the digest the Campaign was resolved under."""
        return self.resolved.campaign_digest

    @property
    def public_context(self) -> PublicContext:
        """Return the public context a manifest built from this carries."""
        return PublicContext(kind="climb", climb_digest=self.resolved.climb_digest)


def catalog_fixture_builder() -> ModuleType:
    """Import the catalog fixture builder from the fixtures tree.

    ``tests/fixtures`` is data rather than an importable package, so the
    builder is loaded by path — the same way the catalog contract tests load
    it. Importing it is what lets a test compose a variant of the fixture out
    of the same pieces the committed one is made of.
    """
    name = "techtree_catalog_fixture"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing

    location = CATALOG_FIXTURES / "build_complete.py"
    spec = importlib.util.spec_from_file_location(name, location)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def synthetic_graph(
    *,
    status: str = "development",
    proof_grade: str = "development_only",
    slug: str = "synthetic-development",
) -> SyntheticGraph:
    """Return the resolved synthetic Climb graph, assembled in memory."""
    builder: Any = catalog_fixture_builder()

    data_policy = builder.build_data_policy()
    lock = builder.build_taskset_lock()
    evidence = builder.build_validation_evidence(lock)
    receipt = builder.build_validation_receipt(lock, evidence)
    campaign = builder.build_campaign(
        lock=lock,
        validation_receipt_digest=digest_object(receipt),
        data_policy_digest=digest_object(data_policy),
    )
    climb: ClimbManifest = builder.build_climb(
        campaign_digest=digest_object(campaign),
        slug=slug,
        status=status,
        proof_grade=proof_grade,
    )

    return SyntheticGraph(
        resolved=ResolvedClimb(
            climb=climb,
            climb_digest=digest_object(climb),
            campaign=campaign,
            campaign_digest=digest_object(campaign),
            data_policy=data_policy,
            data_policy_digest=digest_object(data_policy),
            publisher_validation=receipt,
            publisher_validation_digest=digest_object(receipt),
        ),
        evidence=evidence,
    )


def catalog_service(
    paths: TechtreePaths,
    *,
    catalog_root: Path = COMPLETE_CATALOG,
    engine: EngineCompatibilityStatus = EngineCompatibilityStatus.VERIFIED,
) -> CatalogService:
    """Return a catalog service over the complete fixture on a supported host."""
    return CatalogService(
        EmbeddedCatalogRepository(catalog_root),
        SUPPORTED_HOST,
        InstalledEngine(engine),
    )


def preparation_service(
    paths: TechtreePaths,
    *,
    catalog_root: Path = COMPLETE_CATALOG,
    engine: EngineCompatibilityStatus = EngineCompatibilityStatus.VERIFIED,
    confirmation: ConfirmationService | None = None,
) -> tuple[SkillPreparationService, DraftStore]:
    """Return a preparation service and the store it writes through."""
    confirmations = confirmation or ConfirmationService()
    store = DraftStore(paths, confirmations)
    service = SkillPreparationService(
        paths=paths,
        catalog=catalog_service(paths, catalog_root=catalog_root, engine=engine),
        draft_store=store,
        confirmation_service=confirmations,
    )
    return service, store


def prepare_draft(
    home: Path,
    *,
    skill_path: Path = VALID_SKILL,
    climb_reference: str = "synthetic-development",
    label: str | None = "candidate-under-test",
) -> tuple[DraftStore, PreparedDraft, TechtreePaths]:
    """Prepare one real draft in a temporary home and return the pieces."""
    paths = paths_from_root(home)
    service, store = preparation_service(paths)
    prepared = service.prepare(
        climb_reference=climb_reference,
        skill_path=skill_path,
        candidate_label=label,
    )
    return store, prepared, paths
