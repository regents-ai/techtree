"""Run-owned inputs and execution outputs. Spec PR8 §8.3.

A run does not read the draft it came from. Everything the executor needs is
copied into ``runs/<run-id>/inputs/`` before the worker is launched, verified
there against the run's own :class:`~techtree.models.run.RunRequest`, and read
back from that copy for the rest of the run's life. Spec §10.4 is the reason:
the draft directory, the participant's source skill, and the packaged catalog
are all mutable from the worker's point of view, and a run that consulted them
mid-flight would be measuring whatever the disk happened to hold at the time.

Three properties follow from that.

*Nothing partial ever becomes ``inputs/``.* The tree is assembled under a
staging name inside the run directory, verified there, and renamed into place.
A rename within one directory is atomic, so a crash leaves either no ``inputs/``
or a complete and checked one — which is also what makes re-staging after the
crash windows in spec §9 a no-op rather than a second copy.

*Bytes are copied, never linked.* A hard link to a user-controlled file is the
same file; editing the original would edit the run's input. Every file is read
and written afresh, and every digest is recomputed from what landed on disk.

*Verification is anchored on the request.* The draft store already proved the
graph held together when the draft was written. This module proves something
different and later: that the bytes this run owns are the bytes the run's
immutable request names. It never constructs a
:class:`~techtree.drafts.store.DraftStore` to do it.

Two files of a run belong elsewhere and are deliberately not duplicated here.
``request.json`` and ``report/uplift.json`` are owned by
:class:`~techtree.runs.store.RunStore`, because writing the report is the same
act as appending the ``result.written`` event that announces its digest.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import canonical_json_bytes, digest_object, sha256_digest_bytes
from techtree.drafts.store import DraftSnapshot
from techtree.errors import NotFoundError, ValidationError, VerificationError
from techtree.fs import (
    ensure_private_directory,
    fsync_directory,
    open_exclusive,
    remove_tree,
)
from techtree.manifests.builder import skill_content_digest
from techtree.models.base import ArtifactRef, Digest, JsonValue
from techtree.models.campaign import CampaignSpec
from techtree.models.climb import ClimbManifest, ResolvedClimb
from techtree.models.data_policy import DataPolicy
from techtree.models.episode_receipt import EpisodeReceipt
from techtree.models.experiment import (
    ExperimentManifest,
    ExperimentVariant,
    ManifestComparison,
)
from techtree.models.run import RunRequest
from techtree.models.skill import SkillArtifact, SubmissionDraft
from techtree.models.validation import TasksetValidationReceipt, ValidationEvidence
from techtree.paths import TechtreePaths
from techtree.skills.archive import verify_archive

__all__ = [
    "RUN_INPUT_STAGING_FAILED",
    "VALIDATION_MARKER_SCHEMA_VERSION",
    "RunArtifactStore",
    "RunInputBundle",
]

#: The one code every staged-input problem reports. Spec PR8 §8.16.
RUN_INPUT_STAGING_FAILED: Final = "run_input_staging_failed"

#: The local development artifact recording what the validation provider
#: answered. Not a protocol object: it exists so an operator can see which
#: provider spoke and what it returned.
VALIDATION_MARKER_SCHEMA_VERSION: Final = "techtree.taskset-validation-outcome.v1"

_JSON_MEDIA_TYPE: Final = "application/json"

_INPUTS_DIR: Final = "inputs"
_STAGING_PREFIX: Final = ".staging-inputs-"

_DRAFT_FILE: Final = "draft.json"
_COMPARISON_FILE: Final = "comparison.json"

_PUBLIC_DIR: Final = "public"
_CLIMB_FILE: Final = "climb.json"
_CAMPAIGN_FILE: Final = "campaign.json"
_DATA_POLICY_FILE: Final = "data-policy.json"
_VALIDATION_RECEIPT_FILE: Final = "publisher-validation.json"
_EVIDENCE_FILE: Final = "publisher-validation-evidence.json"

_MANIFESTS_DIR: Final = "manifests"
_BASELINE_FILE: Final = "baseline.json"
_CANDIDATE_FILE: Final = "candidate.json"

_SKILL_DIR: Final = "skill"
_ARTIFACT_FILE: Final = "artifact.json"
_BUNDLE_FILE: Final = "bundle.tar"
_FILES_DIR: Final = "files"

_VALIDATION_DIR: Final = "validation"
_VALIDATION_MARKER_FILE: Final = "development.json"
_FAKE_DIR: Final = "fake"
_RECEIPTS_DIR: Final = "receipts"

#: Four digits order a run's artifacts lexicographically for every task count
#: v0.1 permits, so directory order is Campaign order without a second index.
_POSITION_WIDTH: Final = 4

_FILE_MODE: Final = 0o600


@dataclass(frozen=True)
class RunInputBundle:
    """Everything one run executes, loaded from the run's own copies."""

    request: RunRequest
    draft: SubmissionDraft
    resolved_climb: ResolvedClimb
    validation_evidence: ValidationEvidence
    baseline: ExperimentManifest
    candidate: ExperimentManifest
    comparison: ManifestComparison
    skill: SkillArtifact
    skill_archive: Path
    skill_files: Path

    @property
    def campaign(self) -> CampaignSpec:
        """Return the Campaign this run's science comes from."""
        return self.resolved_climb.campaign

    @property
    def ordered_task_hashes(self) -> list[Digest]:
        """Return the Campaign's committed task membership, in order."""
        return list(self.campaign.taskset.membership.ordered_task_hashes)


class RunArtifactStore:
    """Stages a run's immutable inputs and persists its execution outputs."""

    def __init__(self, paths: TechtreePaths) -> None:
        self._paths = paths

    # -- inputs -------------------------------------------------------------

    def stage_inputs(
        self,
        *,
        run_id: str,
        request: RunRequest,
        snapshot: DraftSnapshot,
    ) -> RunInputBundle:
        """Copy the draft's immutable graph into this run's ``inputs/``.

        Staging is idempotent. A run whose directory already holds a complete
        ``inputs/`` — the ordinary result of retrying a start that crashed
        after the run was created — is verified and returned rather than
        copied over, which is what spec §9.4 requires of the repair path.
        """
        inputs = self._inputs_dir(run_id)
        if inputs.exists():
            return self.load_inputs(run_id, request)

        ensure_private_directory(self._run_dir(run_id))
        staging = self._run_dir(run_id) / f"{_STAGING_PREFIX}{uuid.uuid4().hex}"
        try:
            self._assemble(staging, snapshot)
            self._verify(run_id, self._read_bundle(staging, request))
            os.rename(staging, inputs)
        except BaseException:
            remove_tree(staging)
            raise
        fsync_directory(self._run_dir(run_id))
        return self.load_inputs(run_id, request)

    def load_inputs(self, run_id: str, request: RunRequest) -> RunInputBundle:
        """Load and verify the run-owned inputs, consulting no draft."""
        root = self._inputs_dir(run_id)
        if not root.exists():
            raise NotFoundError(
                f"run {run_id} has no staged inputs",
                code=RUN_INPUT_STAGING_FAILED,
                details={"run_id": run_id},
            )
        bundle = self._read_bundle(root, request)
        self._verify(run_id, bundle)
        return bundle

    # -- execution outputs --------------------------------------------------

    def write_validation_marker(
        self,
        run_id: str,
        marker: Mapping[str, JsonValue],
    ) -> ArtifactRef:
        """Persist what the validation provider answered.

        The marker is the JSON projection a
        :class:`~techtree.runs.validation.TasksetValidationOutcome` produces of
        itself. Taking the projection rather than the outcome keeps the
        direction of dependency one way: providers know about run inputs, and
        this module does not know about providers.
        """
        directory = self._run_dir(run_id) / _VALIDATION_DIR
        ensure_private_directory(directory)
        return self._write_artifact(
            directory / _VALIDATION_MARKER_FILE,
            marker,
            run_id=run_id,
            media_type=_JSON_MEDIA_TYPE,
        )

    def write_fake_trace(
        self,
        run_id: str,
        *,
        variant: ExperimentVariant,
        position: int,
        payload: BaseModel,
    ) -> ArtifactRef:
        """Persist one canonical fake trace payload."""
        directory = self._run_dir(run_id) / _FAKE_DIR / variant.value
        ensure_private_directory(directory)
        return self._write_artifact(
            directory / _position_file(position),
            payload,
            run_id=run_id,
            media_type=_JSON_MEDIA_TYPE,
        )

    def write_episode_receipt(
        self,
        run_id: str,
        *,
        position: int,
        receipt: EpisodeReceipt,
    ) -> ArtifactRef:
        """Write one immutable receipt under its variant directory.

        The position is the receipt's place in the Campaign's committed task
        order and becomes its filename, so reading the directory back in name
        order reads the receipts back in Campaign order.
        """
        directory = self._run_dir(run_id) / _RECEIPTS_DIR / receipt.variant.value
        ensure_private_directory(directory)
        return self._write_artifact(
            directory / _position_file(position),
            receipt,
            run_id=run_id,
            media_type=_JSON_MEDIA_TYPE,
        )

    def episode_receipts(
        self,
        run_id: str,
        variant: ExperimentVariant,
    ) -> list[EpisodeReceipt]:
        """Load one variant's receipts in Campaign task order."""
        directory = self._run_dir(run_id) / _RECEIPTS_DIR / variant.value
        if not directory.exists():
            return []
        return [
            self._parse(path, EpisodeReceipt, run_id)
            for path in sorted(directory.iterdir())
            if path.is_file()
        ]

    # -- placement ----------------------------------------------------------

    def inputs_dir(self, run_id: str) -> Path:
        """Return the directory holding this run's own copy of its inputs."""
        return self._inputs_dir(run_id)

    def skill_files_dir(self, run_id: str) -> Path:
        """Return the run-owned expanded candidate skill directory."""
        return self._inputs_dir(run_id) / _SKILL_DIR / _FILES_DIR

    def skill_archive_path(self, run_id: str) -> Path:
        """Return the run-owned deterministic candidate skill archive."""
        return self._inputs_dir(run_id) / _SKILL_DIR / _BUNDLE_FILE

    # -- assembly -----------------------------------------------------------

    def _assemble(self, staging: Path, snapshot: DraftSnapshot) -> None:
        """Write the complete input tree under a staging name."""
        resolved = snapshot.resolved_climb
        try:
            ensure_private_directory(staging)
            self._write_immutable(staging / _DRAFT_FILE, snapshot.draft)
            self._write_immutable(staging / _COMPARISON_FILE, snapshot.comparison)

            public = staging / _PUBLIC_DIR
            ensure_private_directory(public)
            self._write_immutable(public / _CLIMB_FILE, resolved.climb)
            self._write_immutable(public / _CAMPAIGN_FILE, resolved.campaign)
            self._write_immutable(public / _DATA_POLICY_FILE, resolved.data_policy)
            self._write_immutable(
                public / _VALIDATION_RECEIPT_FILE, resolved.publisher_validation
            )
            self._write_immutable(public / _EVIDENCE_FILE, snapshot.validation_evidence)

            manifests = staging / _MANIFESTS_DIR
            ensure_private_directory(manifests)
            self._write_immutable(manifests / _BASELINE_FILE, snapshot.baseline)
            self._write_immutable(manifests / _CANDIDATE_FILE, snapshot.candidate)

            skill = staging / _SKILL_DIR
            ensure_private_directory(skill)
            self._write_immutable(skill / _ARTIFACT_FILE, snapshot.skill)
            self._copy_bytes(snapshot.skill_archive, skill / _BUNDLE_FILE)
            files = skill / _FILES_DIR
            ensure_private_directory(files)
            for entry in snapshot.skill.files:
                target = files / entry.path
                ensure_private_directory(target.parent)
                self._copy_bytes(snapshot.skill_files / entry.path, target)
        except OSError as error:
            raise ValidationError(
                f"this run's inputs could not be staged: {error.strerror or error}",
                code=RUN_INPUT_STAGING_FAILED,
            ) from error

    def _copy_bytes(self, source: Path, destination: Path) -> None:
        """Copy one file's contents into a newly created run-owned file.

        Read and written rather than linked or cloned: a hard link would make
        the run's input the same file as the draft's, and spec §8.3 requires
        that a user-controlled source can never be one of a run's inputs.
        """
        with open_exclusive(destination, _FILE_MODE) as handle:
            handle.write(source.read_bytes())
            handle.flush()
            os.fsync(handle.fileno())

    # -- reading and verification -------------------------------------------

    def _read_bundle(self, root: Path, request: RunRequest) -> RunInputBundle:
        """Load every staged object from one input tree."""
        run_id = request.run_id
        public = root / _PUBLIC_DIR
        climb = self._parse(public / _CLIMB_FILE, ClimbManifest, run_id)
        campaign = self._parse(public / _CAMPAIGN_FILE, CampaignSpec, run_id)
        data_policy = self._parse(public / _DATA_POLICY_FILE, DataPolicy, run_id)
        receipt = self._parse(
            public / _VALIDATION_RECEIPT_FILE, TasksetValidationReceipt, run_id
        )

        try:
            resolved = ResolvedClimb(
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
                "the public objects this run owns no longer describe each "
                f"other: {error.errors()[0]['msg']}",
                code=RUN_INPUT_STAGING_FAILED,
                details={"run_id": run_id},
            ) from error

        return RunInputBundle(
            request=request,
            draft=self._parse(root / _DRAFT_FILE, SubmissionDraft, run_id),
            resolved_climb=resolved,
            validation_evidence=self._parse(
                public / _EVIDENCE_FILE, ValidationEvidence, run_id
            ),
            baseline=self._parse(
                root / _MANIFESTS_DIR / _BASELINE_FILE, ExperimentManifest, run_id
            ),
            candidate=self._parse(
                root / _MANIFESTS_DIR / _CANDIDATE_FILE, ExperimentManifest, run_id
            ),
            comparison=self._parse(root / _COMPARISON_FILE, ManifestComparison, run_id),
            skill=self._parse(
                root / _SKILL_DIR / _ARTIFACT_FILE, SkillArtifact, run_id
            ),
            skill_archive=root / _SKILL_DIR / _BUNDLE_FILE,
            skill_files=root / _SKILL_DIR / _FILES_DIR,
        )

    def _verify(self, run_id: str, bundle: RunInputBundle) -> None:
        """Prove the staged bytes are the ones this run's request names."""
        request = bundle.request
        draft = bundle.draft
        resolved = bundle.resolved_climb
        campaign = resolved.campaign

        _require(
            digest_object(draft) == request.draft_digest,
            "the staged draft is not the draft this run was created from",
            run_id,
            expected=request.draft_digest,
            computed=digest_object(draft),
        )
        _require(
            draft.id == request.draft_id,
            "the staged draft carries a different identifier than the request",
            run_id,
        )
        _require(
            resolved.campaign_digest
            == request.campaign_spec_digest
            == draft.campaign_spec_digest
            == resolved.climb.campaign_spec_digest,
            "the staged Campaign is not the Campaign this run executes",
            run_id,
            expected=request.campaign_spec_digest,
            computed=resolved.campaign_digest,
        )
        _require(
            resolved.data_policy_digest
            == request.data_policy_digest
            == draft.data_policy_digest
            == campaign.data_policy_digest,
            "the staged DataPolicy is not the one this run executes under",
            run_id,
            expected=request.data_policy_digest,
            computed=resolved.data_policy_digest,
        )
        _require(
            draft.public_context == request.public_context
            and draft.program_ref == request.program_ref
            and draft.outcome_contract_digest == request.outcome_contract_digest,
            "the staged draft names a different public context, improvement "
            "program, or OutcomeContract than the request",
            run_id,
        )
        _require(
            campaign.evaluation_backend == request.evaluation_backend,
            "the staged Campaign names a different evaluation backend than the request",
            run_id,
        )

        self._verify_validation(run_id, bundle)
        self._verify_manifests(run_id, bundle)
        self._verify_skill(run_id, bundle)

    def _verify_validation(self, run_id: str, bundle: RunInputBundle) -> None:
        resolved = bundle.resolved_climb
        receipt = resolved.publisher_validation
        _require(
            resolved.publisher_validation_digest
            == resolved.campaign.taskset.validation_receipt_digest,
            "the staged publisher validation is not the one the Campaign commits to",
            run_id,
            expected=resolved.campaign.taskset.validation_receipt_digest,
            computed=resolved.publisher_validation_digest,
        )
        reference = receipt.normalized_evidence
        if reference is None:
            raise VerificationError(
                "the publisher's validation receipt names no normalized "
                "evidence, so this run could not be checked offline",
                code=RUN_INPUT_STAGING_FAILED,
                details={"run_id": run_id},
            )
        evidence_digest = digest_object(bundle.validation_evidence)
        _require(
            evidence_digest == reference.digest,
            "the staged validation evidence is not what the publisher's "
            "receipt was issued from",
            run_id,
            expected=reference.digest,
            computed=evidence_digest,
        )

    def _verify_manifests(self, run_id: str, bundle: RunInputBundle) -> None:
        baseline_digest = digest_object(bundle.baseline)
        candidate_digest = digest_object(bundle.candidate)
        request = bundle.request

        _require(
            baseline_digest
            == request.baseline_manifest_digest
            == bundle.draft.baseline_manifest_digest,
            "the staged baseline manifest is not the one this run compares",
            run_id,
            expected=request.baseline_manifest_digest,
            computed=baseline_digest,
        )
        _require(
            candidate_digest
            == request.candidate_manifest_digest
            == bundle.draft.candidate_manifest_digest,
            "the staged candidate manifest is not the one this run compares",
            run_id,
            expected=request.candidate_manifest_digest,
            computed=candidate_digest,
        )

        comparison = bundle.comparison
        _require(
            comparison.baseline_configuration_digest
            == bundle.baseline.configuration_digest
            and comparison.candidate_configuration_digest
            == bundle.candidate.configuration_digest,
            "the staged comparison was made between different configurations "
            "than the staged manifests",
            run_id,
        )
        _require(
            comparison.controlled,
            "the staged comparison says this candidate differs from its "
            "baseline somewhere the Campaign does not permit",
            run_id,
            violations=list(comparison.violations),
        )

    def _verify_skill(self, run_id: str, bundle: RunInputBundle) -> None:
        skill = bundle.skill
        _require(
            digest_object(skill) == digest_object(bundle.draft.skill_artifact),
            "the staged skill artifact is not the one the staged draft names",
            run_id,
        )
        recomputed = skill_content_digest(skill.files)
        _require(
            recomputed == skill.root_digest,
            "the staged skill's root digest does not describe the files it lists",
            run_id,
            expected=skill.root_digest,
            computed=recomputed,
        )
        for entry in skill.files:
            path = bundle.skill_files / entry.path
            try:
                data = path.read_bytes()
            except OSError as error:
                raise VerificationError(
                    f"this run's copy of the candidate skill is missing {entry.path}",
                    code=RUN_INPUT_STAGING_FAILED,
                    details={"run_id": run_id, "path": entry.path},
                ) from error
            _require(
                len(data) == entry.size and sha256_digest_bytes(data) == entry.digest,
                f"this run's copy of the candidate skill file {entry.path} is "
                "not what the artifact says it is",
                run_id,
                path=entry.path,
            )
        _require(
            verify_archive(bundle.skill_archive, skill),
            "this run's copy of the candidate skill archive does not match "
            "the artifact beside it",
            run_id,
        )

    # -- bytes --------------------------------------------------------------

    def _write_artifact(
        self,
        path: Path,
        value: object,
        *,
        run_id: str,
        media_type: str,
    ) -> ArtifactRef:
        """Write one immutable output and return the reference to it."""
        data = canonical_json_bytes(value)
        self._write_bytes(path, data)
        return ArtifactRef(
            digest=sha256_digest_bytes(data),
            media_type=media_type,
            size=len(data),
            relative_path=path.relative_to(self._run_dir(run_id)).as_posix(),
        )

    def _write_immutable(self, path: Path, value: object) -> None:
        """Create a write-once file holding one object's canonical bytes."""
        self._write_bytes(path, canonical_json_bytes(value))

    def _write_bytes(self, path: Path, data: bytes) -> None:
        with open_exclusive(path, _FILE_MODE) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        fsync_directory(path.parent)

    def _parse[ModelT: BaseModel](
        self, path: Path, model: type[ModelT], run_id: str
    ) -> ModelT:
        try:
            raw = path.read_bytes()
        except FileNotFoundError as error:
            raise NotFoundError(
                f"run {run_id} is missing {path.name}",
                code=RUN_INPUT_STAGING_FAILED,
                details={"run_id": run_id, "file": path.name},
            ) from error

        try:
            return model.model_validate_json(raw)
        except PydanticValidationError as error:
            raise ValidationError(
                f"run {run_id} holds an invalid {path.name}: "
                f"{error.errors()[0]['msg']}",
                code=RUN_INPUT_STAGING_FAILED,
                details={"run_id": run_id, "file": path.name},
            ) from error

    def _run_dir(self, run_id: str) -> Path:
        return self._paths.run_dir(run_id)

    def _inputs_dir(self, run_id: str) -> Path:
        return self._run_dir(run_id) / _INPUTS_DIR


def _position_file(position: int) -> str:
    """Return the filename one Campaign position's artifact occupies."""
    if position < 0:
        raise ValidationError(
            f"a task position is not negative, and this one is {position}",
            code=RUN_INPUT_STAGING_FAILED,
            details={"position": position},
        )
    return f"{position:0{_POSITION_WIDTH}d}.json"


def _require(condition: bool, message: str, run_id: str, **details: object) -> None:
    """Raise a typed verification failure unless the condition holds."""
    if condition:
        return
    reported: dict[str, JsonValue] = {"run_id": run_id}
    for key, value in details.items():
        reported[key] = (
            [str(item) for item in value] if isinstance(value, list) else str(value)
        )
    raise VerificationError(
        message,
        code=RUN_INPUT_STAGING_FAILED,
        details=reported,
    )
