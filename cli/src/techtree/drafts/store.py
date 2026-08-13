"""The draft directory, and the only way anything writes to it. Spec PR6 §6.7.

A draft is a self-contained claim. Everything needed to check it — the public
Climb, the Campaign, the DataPolicy, the publisher's validation receipt, the
normalized evidence that receipt was issued from, both experiment variants, the
controlled comparison, and the candidate skill as both an archive and an
expanded tree — is copied in at prepare time. Nothing is left as a reference
into the catalog, because a draft that needed the catalog to be verifiable
would stop being verifiable the moment the build shipping that catalog changed.
Decisions document 0003 A4 states the rule; this module is where it is paid
for.

Three properties govern the layout.

*Nothing partial ever becomes a draft.* The whole tree is assembled in a
staging directory beside the drafts, verified there, and only then renamed into
place. A rename within one directory is atomic, so a crash at any point leaves
either no draft or a complete one, never a half-written graph that a later
command would have to guess about.

*Written once, or replaced atomically, never edited.* ``draft.json``,
``comparison.json``, the manifests, the public snapshot, and the skill artifact
are created with ``O_EXCL`` in canonical bytes: their digests are their
identities and a second write is a conflict, not an update. ``confirmation.json``
and ``start.json`` are mutable state and are replaced whole.

*The start is claimed exactly once.* :meth:`DraftStore.claim_start` verifies
the graph, verifies and consumes the confirmation, and creates the start record
under one lock hold. A second call returns the record the first one wrote — the
same run identifier, no second consumption — so a retried or duplicated start
cannot produce two runs from one draft.

Verification is offline and total. :meth:`DraftStore.verify_snapshot` recomputes
every digest in the graph and checks every edge between the objects, including
the ones the catalog already checked. It is deliberately redundant: the catalog
proved something about the bytes it shipped, and this proves something about
the bytes on this disk now.
"""

from __future__ import annotations

import os
import shutil
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Final

from filelock import FileLock, Timeout
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import canonical_json_bytes, digest_object, sha256_digest_bytes
from techtree.drafts.confirmation import ConfirmationService, utc_now
from techtree.errors import (
    ConflictError,
    NotFoundError,
    ValidationError,
    VerificationError,
)
from techtree.fs import (
    atomic_write_bytes,
    ensure_private_directory,
    fsync_directory,
    open_exclusive,
    remove_tree,
)
from techtree.ids import validate_id
from techtree.manifests.builder import skill_content_digest
from techtree.models.base import JsonValue, StateModel, UtcDateTime
from techtree.models.campaign import CampaignSpec
from techtree.models.climb import ClimbManifest, ResolvedClimb
from techtree.models.data_policy import DataPolicy
from techtree.models.experiment import ExperimentManifest, ManifestComparison
from techtree.models.skill import ConfirmationRecord, SkillArtifact, SubmissionDraft
from techtree.models.validation import TasksetValidationReceipt, ValidationEvidence
from techtree.paths import TechtreePaths
from techtree.skills.archive import verify_archive

__all__ = [
    "DRAFT_ALREADY_EXISTS",
    "DRAFT_WRITE_FAILED",
    "LOCK_TIMEOUT_SECONDS",
    "DraftSnapshot",
    "DraftStartRecord",
    "DraftStartStatus",
    "DraftStore",
]

#: Stable error codes this module reports. Spec PR6 §6.10.
DRAFT_ALREADY_EXISTS: Final = "draft_already_exists"
DRAFT_WRITE_FAILED: Final = "draft_write_failed"
_CATALOG_GRAPH_INVALID: Final = "catalog_graph_invalid"
_CAMPAIGN_DIGEST_MISMATCH: Final = "campaign_digest_mismatch"
_DATA_POLICY_DIGEST_MISMATCH: Final = "data_policy_digest_mismatch"
_PUBLISHER_VALIDATION_MISSING: Final = "publisher_validation_missing"
_PUBLISHER_EVIDENCE_MISSING: Final = "publisher_validation_evidence_missing"
_SKILL_INVALID: Final = "skill_invalid"
_MANIFEST_BUILD_FAILED: Final = "manifest_build_failed"
_MANIFEST_COMPARISON_INVALID: Final = "manifest_comparison_invalid"
_DRAFT_NOT_FOUND: Final = "draft_not_found"
_DRAFT_START_CONFLICT: Final = "draft_start_conflict"
_DRAFT_NOT_STARTED: Final = "draft_not_started"

#: A lock hold is a handful of file operations. Waiting longer than this means
#: the holder died with the lock, and failing beats hanging.
LOCK_TIMEOUT_SECONDS: Final = 30.0

_LOCK_FILE: Final = ".lock"
_DRAFT_FILE: Final = "draft.json"
_CONFIRMATION_FILE: Final = "confirmation.json"
_COMPARISON_FILE: Final = "comparison.json"
_START_FILE: Final = "start.json"

_PUBLIC_DIR: Final = "public"
_CLIMB_FILE: Final = "climb.json"
_CAMPAIGN_FILE: Final = "campaign.json"
_DATA_POLICY_FILE: Final = "data-policy.json"
_VALIDATION_FILE: Final = "publisher-validation.json"
_EVIDENCE_FILE: Final = "publisher-validation-evidence.json"

_MANIFESTS_DIR: Final = "manifests"
_BASELINE_FILE: Final = "baseline.json"
_CANDIDATE_FILE: Final = "candidate.json"

_SKILL_DIR: Final = "skill"
_ARTIFACT_FILE: Final = "artifact.json"
_BUNDLE_FILE: Final = "bundle.tar"
_FILES_DIR: Final = "files"

#: Staging directories live beside the drafts so that the final placement is a
#: rename within one directory, which is what makes it atomic.
_STAGING_PREFIX: Final = ".staging-"

_FILE_MODE: Final = 0o600


class DraftStartStatus(StrEnum):
    """How far the one-time handover from a draft to a run has got."""

    CLAIMED = "claimed"
    LAUNCHED = "launched"
    LAUNCH_FAILED = "launch_failed"


class DraftStartRecord(StateModel):
    """The single run this draft was spent on, and what became of the launch.

    Local operational state, not a protocol artifact. It exists so that a
    retried start returns the run that already exists rather than creating a
    second one, and so that a launch that failed after the confirmation was
    consumed is visible instead of silently lost.
    """

    draft_id: str
    run_id: str
    status: DraftStartStatus
    claimed_at: UtcDateTime
    launched_at: UtcDateTime | None = None
    launch_error_code: str | None = None


@dataclass(frozen=True)
class DraftSnapshot:
    """Everything one draft holds, loaded and ready to be checked together."""

    draft: SubmissionDraft
    resolved_climb: ResolvedClimb
    validation_evidence: ValidationEvidence
    baseline: ExperimentManifest
    candidate: ExperimentManifest
    comparison: ManifestComparison
    skill: SkillArtifact
    skill_archive: Path
    skill_files: Path


class DraftStore:
    """Persists and independently verifies complete draft graphs."""

    def __init__(
        self,
        paths: TechtreePaths,
        confirmation_service: ConfirmationService,
    ) -> None:
        self._paths = paths
        self._confirmation = confirmation_service

    # -- Placement ---------------------------------------------------------

    def draft_dir(self, draft_id: str) -> Path:
        """Return the directory one draft occupies."""
        return self._paths.draft_dir(draft_id)

    def skill_files_dir(self, draft_id: str) -> Path:
        """Return the immutable expanded candidate skill directory."""
        return self.draft_dir(draft_id) / _SKILL_DIR / _FILES_DIR

    def skill_archive_path(self, draft_id: str) -> Path:
        """Return the deterministic candidate skill archive."""
        return self.draft_dir(draft_id) / _SKILL_DIR / _BUNDLE_FILE

    # -- Creation ----------------------------------------------------------

    def create(
        self,
        *,
        draft: SubmissionDraft,
        confirmation: ConfirmationRecord,
        baseline: ExperimentManifest,
        candidate: ExperimentManifest,
        comparison: ManifestComparison,
        resolved_climb: ResolvedClimb,
        validation_evidence: ValidationEvidence,
        staged_skill_dir: Path,
        staged_skill_archive: Path,
    ) -> None:
        """Write a new draft graph, atomically, or write nothing at all."""
        final = self.draft_dir(draft.id)
        if final.exists():
            raise ConflictError(
                f"a draft called {draft.id} already exists",
                code=DRAFT_ALREADY_EXISTS,
                details={"draft_id": draft.id},
            )

        ensure_private_directory(self._paths.drafts_dir)
        staging = self._paths.drafts_dir / f"{_STAGING_PREFIX}{uuid.uuid4().hex}"

        try:
            self._assemble(
                staging,
                draft=draft,
                confirmation=confirmation,
                baseline=baseline,
                candidate=candidate,
                comparison=comparison,
                resolved_climb=resolved_climb,
                validation_evidence=validation_evidence,
                staged_skill_dir=staged_skill_dir,
                staged_skill_archive=staged_skill_archive,
            )
            self.verify_snapshot(
                DraftSnapshot(
                    draft=draft,
                    resolved_climb=resolved_climb,
                    validation_evidence=validation_evidence,
                    baseline=baseline,
                    candidate=candidate,
                    comparison=comparison,
                    skill=draft.skill_artifact,
                    skill_archive=staging / _SKILL_DIR / _BUNDLE_FILE,
                    skill_files=staging / _SKILL_DIR / _FILES_DIR,
                )
            )
            self._place(staging, final, draft.id)
        except BaseException:
            remove_tree(staging)
            raise

    def _assemble(
        self,
        staging: Path,
        *,
        draft: SubmissionDraft,
        confirmation: ConfirmationRecord,
        baseline: ExperimentManifest,
        candidate: ExperimentManifest,
        comparison: ManifestComparison,
        resolved_climb: ResolvedClimb,
        validation_evidence: ValidationEvidence,
        staged_skill_dir: Path,
        staged_skill_archive: Path,
    ) -> None:
        """Write the complete tree into a staging directory."""
        reference = resolved_climb.publisher_validation.normalized_evidence
        if reference is None:
            raise VerificationError(
                "the publisher's validation receipt names no normalized "
                "evidence, so this draft could not be checked offline",
                code=_PUBLISHER_EVIDENCE_MISSING,
                details={"draft_id": draft.id},
            )

        try:
            ensure_private_directory(staging)
            self._write_immutable(staging / _DRAFT_FILE, draft)
            self._write_state(staging / _CONFIRMATION_FILE, confirmation)
            self._write_immutable(staging / _COMPARISON_FILE, comparison)

            public = staging / _PUBLIC_DIR
            ensure_private_directory(public)
            self._write_immutable(public / _CLIMB_FILE, resolved_climb.climb)
            self._write_immutable(public / _CAMPAIGN_FILE, resolved_climb.campaign)
            self._write_immutable(
                public / _DATA_POLICY_FILE, resolved_climb.data_policy
            )
            self._write_immutable(
                public / _VALIDATION_FILE, resolved_climb.publisher_validation
            )
            self._write_immutable(public / _EVIDENCE_FILE, validation_evidence)

            manifests = staging / _MANIFESTS_DIR
            ensure_private_directory(manifests)
            self._write_immutable(manifests / _BASELINE_FILE, baseline)
            self._write_immutable(manifests / _CANDIDATE_FILE, candidate)

            skill = staging / _SKILL_DIR
            ensure_private_directory(skill)
            self._write_immutable(skill / _ARTIFACT_FILE, draft.skill_artifact)
            shutil.copyfile(staged_skill_archive, skill / _BUNDLE_FILE)
            os.chmod(skill / _BUNDLE_FILE, _FILE_MODE)
            self._copy_skill_files(
                staged_skill_dir, skill / _FILES_DIR, draft.skill_artifact
            )
        except OSError as error:
            raise ValidationError(
                f"the draft could not be written: {error.strerror or error}",
                code=DRAFT_WRITE_FAILED,
                details={"draft_id": draft.id},
            ) from error

    def _copy_skill_files(
        self, source: Path, destination: Path, artifact: SkillArtifact
    ) -> None:
        """Copy exactly the files the artifact lists, and nothing else."""
        ensure_private_directory(destination)
        for entry in artifact.files:
            target = destination / entry.path
            ensure_private_directory(target.parent)
            shutil.copyfile(source / entry.path, target)
            os.chmod(target, _FILE_MODE)

    def _place(self, staging: Path, final: Path, draft_id: str) -> None:
        """Move a fully written staging tree into its final name."""
        try:
            os.rename(staging, final)
        except OSError as error:
            raise ConflictError(
                f"a draft called {draft_id} already exists",
                code=DRAFT_ALREADY_EXISTS,
                details={"draft_id": draft_id},
            ) from error
        fsync_directory(self._paths.drafts_dir)

    # -- Loading -----------------------------------------------------------

    def get(self, draft_id: str) -> SubmissionDraft:
        """Load and validate ``draft.json``."""
        return self._load(draft_id, _DRAFT_FILE, SubmissionDraft)

    def get_confirmation(self, draft_id: str) -> ConfirmationRecord:
        """Load mutable confirmation state."""
        return self._load(draft_id, _CONFIRMATION_FILE, ConfirmationRecord)

    def get_manifests(
        self, draft_id: str
    ) -> tuple[ExperimentManifest, ExperimentManifest]:
        """Load immutable manifests."""
        return (
            self._load(
                draft_id, f"{_MANIFESTS_DIR}/{_BASELINE_FILE}", ExperimentManifest
            ),
            self._load(
                draft_id, f"{_MANIFESTS_DIR}/{_CANDIDATE_FILE}", ExperimentManifest
            ),
        )

    def get_comparison(self, draft_id: str) -> ManifestComparison:
        """Load prepared comparison."""
        return self._load(draft_id, _COMPARISON_FILE, ManifestComparison)

    def get_resolved_climb(self, draft_id: str) -> ResolvedClimb:
        """Load the snapshotted public graph.

        The digests are recomputed from the snapshotted bytes rather than read
        from anywhere, so assembling the graph is itself the check that the
        four objects still describe each other.
        """
        climb = self._load(draft_id, f"{_PUBLIC_DIR}/{_CLIMB_FILE}", ClimbManifest)
        campaign = self._load(draft_id, f"{_PUBLIC_DIR}/{_CAMPAIGN_FILE}", CampaignSpec)
        data_policy = self._load(
            draft_id, f"{_PUBLIC_DIR}/{_DATA_POLICY_FILE}", DataPolicy
        )
        receipt = self._load(
            draft_id, f"{_PUBLIC_DIR}/{_VALIDATION_FILE}", TasksetValidationReceipt
        )

        try:
            return ResolvedClimb(
                climb=climb,
                climb_digest=digest_object(climb),
                campaign=campaign,
                campaign_digest=digest_object(campaign),
                data_policy=data_policy,
                data_policy_digest=digest_object(data_policy),
                publisher_validation=receipt,
                publisher_validation_digest=digest_object(receipt),
            )
        except PydanticValidationError as error:
            raise VerificationError(
                "the public objects snapshotted in this draft no longer "
                f"describe each other: {_first_problem(error)}",
                code=_CATALOG_GRAPH_INVALID,
                details={"draft_id": draft_id},
            ) from error

    def get_validation_evidence(self, draft_id: str) -> ValidationEvidence:
        """Load evidence referenced by the publisher receipt."""
        return self._load(
            draft_id, f"{_PUBLIC_DIR}/{_EVIDENCE_FILE}", ValidationEvidence
        )

    def get_skill(self, draft_id: str) -> SkillArtifact:
        """Load the ``SkillArtifact`` and verify the files and the archive."""
        artifact = self._load(draft_id, f"{_SKILL_DIR}/{_ARTIFACT_FILE}", SkillArtifact)
        self._verify_skill(
            artifact,
            self.skill_archive_path(draft_id),
            self.skill_files_dir(draft_id),
        )
        return artifact

    def load_snapshot(self, draft_id: str) -> DraftSnapshot:
        """Load the complete graph and verify it before returning it."""
        baseline, candidate = self.get_manifests(draft_id)
        snapshot = DraftSnapshot(
            draft=self.get(draft_id),
            resolved_climb=self.get_resolved_climb(draft_id),
            validation_evidence=self.get_validation_evidence(draft_id),
            baseline=baseline,
            candidate=candidate,
            comparison=self.get_comparison(draft_id),
            skill=self._load(draft_id, f"{_SKILL_DIR}/{_ARTIFACT_FILE}", SkillArtifact),
            skill_archive=self.skill_archive_path(draft_id),
            skill_files=self.skill_files_dir(draft_id),
        )
        self.verify_snapshot(snapshot)
        return snapshot

    # -- Verification ------------------------------------------------------

    def verify_snapshot(self, snapshot: DraftSnapshot) -> None:
        """Verify every digest and cross-object invariant, offline."""
        draft = snapshot.draft
        resolved = snapshot.resolved_climb
        climb = resolved.climb
        campaign = resolved.campaign
        receipt = resolved.publisher_validation

        public_context = draft.public_context
        if public_context is None:
            raise VerificationError(
                "this draft names no public Climb, and it was prepared under one",
                code=_CATALOG_GRAPH_INVALID,
                details={"draft_id": draft.id},
            )

        climb_digest = digest_object(climb)
        _require(
            climb_digest == public_context.climb_digest,
            "the snapshotted Climb is not the Climb this draft was prepared for",
            _CATALOG_GRAPH_INVALID,
            expected=public_context.climb_digest,
            computed=climb_digest,
        )
        _require(
            climb_digest == resolved.climb_digest,
            "the snapshotted Climb does not match the digest it was resolved under",
            _CATALOG_GRAPH_INVALID,
        )

        campaign_digest = digest_object(campaign)
        _require(
            campaign_digest == climb.campaign_spec_digest,
            "the snapshotted Campaign is not the one the Climb wraps",
            _CAMPAIGN_DIGEST_MISMATCH,
            expected=climb.campaign_spec_digest,
            computed=campaign_digest,
        )
        _require(
            campaign_digest == draft.campaign_spec_digest,
            "this draft was prepared against a different Campaign than the one "
            "it snapshotted",
            _CAMPAIGN_DIGEST_MISMATCH,
            expected=draft.campaign_spec_digest,
            computed=campaign_digest,
        )

        policy_digest = digest_object(resolved.data_policy)
        _require(
            policy_digest == campaign.data_policy_digest,
            "the snapshotted DataPolicy is not the one the Campaign runs under",
            _DATA_POLICY_DIGEST_MISMATCH,
            expected=campaign.data_policy_digest,
            computed=policy_digest,
        )
        _require(
            policy_digest == draft.data_policy_digest,
            "this draft states rights from a different DataPolicy than the one "
            "it snapshotted",
            _DATA_POLICY_DIGEST_MISMATCH,
            expected=draft.data_policy_digest,
            computed=policy_digest,
        )
        _require(
            draft.policy_acceptance.data_policy_digest == policy_digest,
            "this draft asks for acceptance of a DataPolicy it did not snapshot",
            _DATA_POLICY_DIGEST_MISMATCH,
        )

        receipt_digest = digest_object(receipt)
        _require(
            receipt_digest == campaign.taskset.validation_receipt_digest,
            "the snapshotted publisher validation is not the one the Campaign "
            "commits to",
            _PUBLISHER_VALIDATION_MISSING,
            expected=campaign.taskset.validation_receipt_digest,
            computed=receipt_digest,
        )

        reference = receipt.normalized_evidence
        if reference is None:
            raise VerificationError(
                "the publisher's validation receipt names no normalized "
                "evidence, so this draft cannot be checked offline",
                code=_PUBLISHER_EVIDENCE_MISSING,
                details={"draft_id": draft.id},
            )
        evidence_digest = digest_object(snapshot.validation_evidence)
        _require(
            evidence_digest == reference.digest,
            "the snapshotted validation evidence is not what the publisher's "
            "receipt was issued from",
            _PUBLISHER_EVIDENCE_MISSING,
            expected=reference.digest,
            computed=evidence_digest,
        )

        _require(
            draft.outcome_contract_digest == campaign.context.outcome_contract_digest,
            "this draft names a different OutcomeContract than the Campaign",
            _CATALOG_GRAPH_INVALID,
        )
        _require(
            draft.program_ref == campaign.context.program_ref,
            "this draft names a different improvement program than the Campaign",
            _CATALOG_GRAPH_INVALID,
        )

        self._verify_manifests(snapshot)
        self._verify_skill(snapshot.skill, snapshot.skill_archive, snapshot.skill_files)
        _require(
            list(draft.included_files) == [file.path for file in snapshot.skill.files],
            "this draft lists different files than the candidate skill it snapshotted",
            _SKILL_INVALID,
        )
        _require(
            digest_object(draft.skill_artifact) == digest_object(snapshot.skill),
            "this draft carries a different skill artifact than the one "
            "snapshotted beside it",
            _SKILL_INVALID,
        )

    def _verify_manifests(self, snapshot: DraftSnapshot) -> None:
        draft = snapshot.draft
        baseline_digest = digest_object(snapshot.baseline)
        candidate_digest = digest_object(snapshot.candidate)

        _require(
            baseline_digest == draft.baseline_manifest_digest,
            "the snapshotted baseline manifest is not the one this draft names",
            _MANIFEST_BUILD_FAILED,
            expected=draft.baseline_manifest_digest,
            computed=baseline_digest,
        )
        _require(
            candidate_digest == draft.candidate_manifest_digest,
            "the snapshotted candidate manifest is not the one this draft names",
            _MANIFEST_BUILD_FAILED,
            expected=draft.candidate_manifest_digest,
            computed=candidate_digest,
        )

        comparison = snapshot.comparison
        _require(
            comparison.baseline_configuration_digest
            == snapshot.baseline.configuration_digest
            and comparison.candidate_configuration_digest
            == snapshot.candidate.configuration_digest,
            "the stored comparison was made between different configurations "
            "than the manifests in this draft",
            _MANIFEST_COMPARISON_INVALID,
        )
        _require(
            comparison.controlled,
            "the stored comparison says this candidate differs from its "
            "baseline somewhere the Campaign does not permit",
            _MANIFEST_COMPARISON_INVALID,
            violations=list(comparison.violations),
        )

    def _verify_skill(
        self, artifact: SkillArtifact, archive: Path, files: Path
    ) -> None:
        """Check the artifact against the bytes stored beside it."""
        recomputed = skill_content_digest(artifact.files)
        _require(
            recomputed == artifact.root_digest,
            "the candidate skill's root digest does not describe the files it lists",
            _SKILL_INVALID,
            expected=artifact.root_digest,
            computed=recomputed,
        )

        for entry in artifact.files:
            path = files / entry.path
            try:
                data = path.read_bytes()
            except OSError as error:
                raise VerificationError(
                    f"the candidate skill is missing {entry.path}",
                    code=_SKILL_INVALID,
                    details={"path": entry.path},
                ) from error
            _require(
                len(data) == entry.size and sha256_digest_bytes(data) == entry.digest,
                f"the snapshotted candidate skill file {entry.path} is not what "
                "the artifact says it is",
                _SKILL_INVALID,
                path=entry.path,
            )

        _require(
            verify_archive(archive, artifact),
            "the candidate skill archive does not match the artifact beside it",
            _SKILL_INVALID,
            archive_digest=artifact.archive_digest,
        )

    # -- Confirmation and the start claim ----------------------------------

    def consume_confirmation(
        self,
        *,
        draft_id: str,
        token: str,
    ) -> ConfirmationRecord:
        """Verify a token and write back the consumed record.

        The caller holds the draft lock. This method does not take it, because
        the only caller that needs it — :meth:`claim_start` — must consume and
        record the claim inside one uninterrupted hold.
        """
        record = self.get_confirmation(draft_id)
        self._confirmation.verify(
            token=token,
            record=record,
            expected_draft_digest=digest_object(self.get(draft_id)),
        )
        consumed = self._confirmation.consume(record)
        self._write_state(self.draft_dir(draft_id) / _CONFIRMATION_FILE, consumed)
        return consumed

    def claim_start(
        self,
        *,
        draft_id: str,
        token: str,
        run_id: str,
    ) -> DraftStartRecord:
        """Spend this draft on exactly one run, or return the run it was spent on."""
        validate_id(run_id, "run")
        self._require_draft(draft_id)

        with self._lock(draft_id):
            existing = self._read_start_record(draft_id)
            if existing is not None:
                # A retried start is not a second start. The confirmation was
                # already consumed by the first one, and consuming it again
                # would fail; returning the claim is what makes the operation
                # idempotent rather than merely safe.
                return existing

            self.load_snapshot(draft_id)
            self.consume_confirmation(draft_id=draft_id, token=token)

            record = DraftStartRecord(
                draft_id=draft_id,
                run_id=run_id,
                status=DraftStartStatus.CLAIMED,
                claimed_at=utc_now(),
                launched_at=None,
                launch_error_code=None,
            )
            self._write_immutable(self.draft_dir(draft_id) / _START_FILE, record)
            return record

    def mark_launched(
        self,
        *,
        draft_id: str,
        run_id: str,
        launched_at: datetime,
    ) -> DraftStartRecord:
        """Record that the claimed run is now running."""
        return self._update_start(
            draft_id,
            run_id,
            status=DraftStartStatus.LAUNCHED,
            launched_at=launched_at,
            launch_error_code=None,
        )

    def mark_launch_failed(
        self,
        *,
        draft_id: str,
        run_id: str,
        error_code: str,
    ) -> DraftStartRecord:
        """Record that the claimed run could not be launched."""
        return self._update_start(
            draft_id,
            run_id,
            status=DraftStartStatus.LAUNCH_FAILED,
            launched_at=None,
            launch_error_code=error_code,
        )

    def start_record(self, draft_id: str) -> DraftStartRecord | None:
        """Return the existing start claim, or ``None`` if there is not one."""
        self._require_draft(draft_id)
        return self._read_start_record(draft_id)

    def _update_start(
        self,
        draft_id: str,
        run_id: str,
        *,
        status: DraftStartStatus,
        launched_at: datetime | None,
        launch_error_code: str | None,
    ) -> DraftStartRecord:
        self._require_draft(draft_id)
        with self._lock(draft_id):
            record = self._read_start_record(draft_id)
            if record is None:
                raise NotFoundError(
                    f"draft {draft_id} has not been started, so there is no "
                    "claim to update",
                    code=_DRAFT_NOT_STARTED,
                    details={"draft_id": draft_id},
                )
            if record.run_id != run_id:
                raise ConflictError(
                    f"draft {draft_id} was already claimed by run {record.run_id}",
                    code=_DRAFT_START_CONFLICT,
                    details={
                        "draft_id": draft_id,
                        "claimed_run_id": record.run_id,
                        "requested_run_id": run_id,
                    },
                )

            updated = DraftStartRecord(
                draft_id=record.draft_id,
                run_id=record.run_id,
                status=status,
                claimed_at=record.claimed_at,
                launched_at=launched_at or record.launched_at,
                launch_error_code=launch_error_code,
            )
            self._write_state(self.draft_dir(draft_id) / _START_FILE, updated)
            return updated

    def _read_start_record(self, draft_id: str) -> DraftStartRecord | None:
        path = self.draft_dir(draft_id) / _START_FILE
        if not path.exists():
            return None
        return self._parse(path, DraftStartRecord, draft_id)

    # -- Internals ---------------------------------------------------------

    def _load[ModelT: BaseModel](
        self, draft_id: str, relative: str, model: type[ModelT]
    ) -> ModelT:
        self._require_draft(draft_id)
        return self._parse(self.draft_dir(draft_id) / relative, model, draft_id)

    def _parse[ModelT: BaseModel](
        self, path: Path, model: type[ModelT], draft_id: str
    ) -> ModelT:
        try:
            raw = path.read_bytes()
        except FileNotFoundError as error:
            raise NotFoundError(
                f"draft {draft_id} is missing {path.name}",
                code=_DRAFT_NOT_FOUND,
                details={"draft_id": draft_id, "file": path.name},
            ) from error

        try:
            return model.model_validate_json(raw)
        except PydanticValidationError as error:
            raise ValidationError(
                f"draft {draft_id} holds an invalid {path.name}: "
                f"{_first_problem(error)}",
                code=_CATALOG_GRAPH_INVALID,
                details={"draft_id": draft_id, "file": path.name},
            ) from error

    def _require_draft(self, draft_id: str) -> None:
        if not (self.draft_dir(draft_id) / _DRAFT_FILE).exists():
            raise NotFoundError(
                f"no such draft: {draft_id}",
                code=_DRAFT_NOT_FOUND,
                details={"draft_id": draft_id},
            )

    def _write_immutable(self, path: Path, value: object) -> None:
        """Create a write-once file holding one object's canonical bytes."""
        data = canonical_json_bytes(value)
        with open_exclusive(path, _FILE_MODE) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        fsync_directory(path.parent)

    def _write_state(self, path: Path, value: object) -> None:
        """Replace one mutable projection atomically, in canonical bytes."""
        atomic_write_bytes(path, canonical_json_bytes(value), mode=_FILE_MODE)

    @contextmanager
    def _lock(self, draft_id: str) -> Iterator[None]:
        """Hold the per-draft lock, or report the wait as a conflict."""
        lock = FileLock(
            self.draft_dir(draft_id) / _LOCK_FILE,
            timeout=LOCK_TIMEOUT_SECONDS,
            mode=_FILE_MODE,
        )
        try:
            lock.acquire()
        except Timeout as error:
            raise ConflictError(
                f"another process is holding the lock on draft {draft_id}",
                details={"draft_id": draft_id, "waited_seconds": LOCK_TIMEOUT_SECONDS},
            ) from error
        try:
            yield
        finally:
            lock.release()


def _require(
    condition: bool,
    message: str,
    code: str,
    **details: object,
) -> None:
    """Raise a typed verification failure unless the condition holds."""
    if condition:
        return
    raise VerificationError(
        message,
        code=code,
        details={key: _as_json(value) for key, value in details.items()},
    )


def _as_json(value: object) -> JsonValue:
    if isinstance(value, list):
        items: list[JsonValue] = [str(item) for item in value]
        return items
    return str(value)


def _first_problem(error: PydanticValidationError) -> str:
    first = error.errors()[0]
    location = ".".join(str(part) for part in first["loc"])
    return f"{location}: {first['msg']}" if location else str(first["msg"])
