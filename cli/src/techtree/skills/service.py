"""Turning a directory into a prepared submission. Spec PR6 §6.8.

This is the only place where a participant's working directory becomes a
scientific input, and it is written on the assumption that everything about
that directory is provisional until it has been copied and hashed.

The order of operations is the safety property. Nothing is written where a
later command could find it until every check has passed: the Climb is
resolved, its status and this machine's compatibility are confirmed, the skill
is scanned, the files are copied into a staging directory and re-verified
against what was scanned, both manifests are derived from the Campaign, the
comparison is required to be controlled, the draft is built and digested, and
only then is the whole tree renamed into place by the draft store. A failure
anywhere leaves the drafts directory exactly as it was.

Three things this module deliberately does not do.

It does not re-implement the scanner. PR5 already decides what a skill may
contain and what a credential looks like; duplicating that logic here would
create two answers to one question.

It does not call a model, start a process, or open a socket. Preparation is
pure local computation, and the integration test asserts it.

It does not ask anyone to accept anything. The draft states the rights that
will have to be accepted — decisions document 0003 A5's
``PolicyAcceptanceRequirement`` — and the acceptance itself happens at start,
after the review of what the run would do has been shown, recorded as a
deliberate act.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Final, assert_never

from techtree.canonical import (
    canonical_json_bytes,
    digest_object,
    sha256_digest_bytes,
)
from techtree.catalog.service import CatalogService
from techtree.constants import SKILL_SCHEMA_VERSION, SUBMISSION_DRAFT_SCHEMA_VERSION
from techtree.drafts.source import CampaignSource, StagedSkill
from techtree.drafts.store import DraftStore, utc_now
from techtree.errors import (
    PolicyError,
    PrerequisiteError,
    ValidationError,
    VerificationError,
)
from techtree.fs import atomic_write_bytes, ensure_private_directory, remove_tree
from techtree.ids import new_id
from techtree.manifests.builder import (
    build_baseline_manifest,
    build_candidate_manifest,
    skill_content_digest,
)
from techtree.manifests.compare import assert_controlled_comparison, compare_manifests
from techtree.models.base import Digest
from techtree.models.campaign import CampaignSpec, PublicContext, VariantSchedule
from techtree.models.climb import ResolvedClimb
from techtree.models.data_policy import DataPolicy
from techtree.models.experiment import ExperimentManifest, ManifestComparison
from techtree.models.skill import (
    PolicyAcceptanceRequirement,
    SkillArtifact,
    SkillFile,
    SubmissionDraft,
)
from techtree.models.uplift_report import UpliftReport
from techtree.models.validation import TasksetValidationReceipt, ValidationEvidence
from techtree.paths import TechtreePaths
from techtree.runs.real import executor_kind_for
from techtree.skills.archive import build_deterministic_tar
from techtree.skills.policy import SkillPolicy, default_instruction_skill_policy
from techtree.skills.scanner import ScannedFile, SkillScanResult, scan_skill
from techtree.uplift.derive import (
    derive_replacement_manifests,
    derive_skill_replacement_campaign,
)

__all__ = [
    "PreparedDraft",
    "ResolvedClimbBundle",
    "SkillPreparationService",
]

#: Stable error codes. Spec PR6 §6.10.
_CLIMB_NOT_PREPARABLE: Final = "climb_not_preparable"
_CANDIDATE_POLICY_VIOLATION: Final = "candidate_policy_violation"
_SKILL_INVALID: Final = "skill_invalid"
_SKILL_SECRET_DETECTED: Final = "skill_secret_detected"
_SKILL_SNAPSHOT_FAILED: Final = "skill_snapshot_failed"
_PUBLISHER_EVIDENCE_MISSING: Final = "publisher_validation_evidence_missing"

#: Which Climbs accept submissions. A closed Climb is still readable; it is
#: simply not something a new candidate can be entered into.
_PREPARABLE_STATUSES: Final[frozenset[str]] = frozenset({"open", "development"})

#: Every variant runs the whole taskset once per rollout, and there are two
#: variants.
_VARIANTS: Final = 2

#: What a candidate label may be made of. Deliberately narrow: the label is
#: carried in a public artifact, so it holds a name and nothing that could be
#: read as a path, a flag, or markup.
_LABEL_PATTERN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}$")

#: Staging lives beside the drafts so the draft store's final placement is a
#: rename within one directory.
_STAGING_PREFIX: Final = ".prepare-"

_SKILL_DIR: Final = "skill"
_ARTIFACT_FILE: Final = "artifact.json"
_BUNDLE_FILE: Final = "bundle.tar"
_FILES_DIR: Final = "files"


@dataclass(frozen=True)
class ResolvedClimbBundle:
    """A resolved Climb together with the evidence a draft has to carry."""

    resolved: ResolvedClimb
    validation_evidence: ValidationEvidence


@dataclass(frozen=True)
class PreparedDraft:
    """What preparation produced, and what it was prepared against."""

    draft: SubmissionDraft
    draft_digest: Digest
    manifest_comparison: ManifestComparison
    source: CampaignSource


class SkillPreparationService:
    """Builds one complete, immutable, offline-verifiable submission draft."""

    def __init__(
        self,
        *,
        paths: TechtreePaths,
        catalog: CatalogService,
        draft_store: DraftStore,
        skill_policy: SkillPolicy | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._paths = paths
        self._catalog = catalog
        self._drafts = draft_store
        self._policy = skill_policy or default_instruction_skill_policy()
        self._clock = clock

    def prepare(
        self,
        *,
        climb_reference: str,
        skill_path: Path,
        candidate_label: str | None = None,
    ) -> PreparedDraft:
        """Resolve, snapshot, derive, compare, and persist one draft."""
        created_at = self._clock()

        bundle = self._resolve(climb_reference)
        resolved = bundle.resolved
        self._require_preparable(resolved)

        scan = self._scan(skill_path)
        self._validate_candidate_policy(resolved, scan)

        ensure_private_directory(self._paths.drafts_dir)
        staging = self._paths.drafts_dir / f"{_STAGING_PREFIX}{uuid.uuid4().hex}"

        source = CampaignSource.from_climb(resolved)
        try:
            ensure_private_directory(staging)
            staged = self._snapshot_skill(
                skill_dir=staging / _SKILL_DIR,
                scan=scan,
                candidate_label=candidate_label,
            )
            public_context = PublicContext(
                kind="climb", climb_digest=resolved.climb_digest
            )
            baseline = build_baseline_manifest(
                campaign=resolved.campaign,
                campaign_digest=resolved.campaign_digest,
                public_context=public_context,
                created_at=created_at,
            )
            candidate = build_candidate_manifest(
                campaign=resolved.campaign,
                campaign_digest=resolved.campaign_digest,
                skill=staged.artifact,
                public_context=public_context,
                created_at=created_at,
            )
            comparison = self._require_controlled(
                baseline, candidate, resolved.campaign
            )
            draft = self._build_draft(
                source=source,
                skill=staged.artifact,
                baseline=baseline,
                candidate=candidate,
                policy=self._build_policy_requirement(resolved.data_policy),
                created_at=created_at,
                warnings=self._warnings(resolved, scan),
            )
            draft_digest = digest_object(draft)

            self._drafts.create(
                draft=draft,
                baseline=baseline,
                candidate=candidate,
                comparison=comparison,
                source=source,
                validation_evidence=bundle.validation_evidence,
                staged_candidate_skill=staged,
            )
        finally:
            # The store renames its own staging tree into place; this one is
            # always scratch, so it always goes away.
            remove_tree(staging)

        return PreparedDraft(
            draft=draft,
            draft_digest=draft_digest,
            manifest_comparison=comparison,
            source=source,
        )

    def prepare_replacement(
        self,
        *,
        source_campaign: CampaignSpec,
        data_policy: DataPolicy,
        publisher_validation: TasksetValidationReceipt,
        validation_evidence: ValidationEvidence,
        source_report: UpliftReport,
        baseline_skill: StagedSkill,
        candidate_skill_path: Path,
        candidate_label: str | None = None,
    ) -> PreparedDraft:
        """Prepare a Skill v1 against Skill v2 draft. Spec sections 7.19, 7.20.

        Everything a public submission goes through happens here too, in the
        same order and through the same store: the new Skill is scanned by the
        same scanner, snapshotted by the same snapshotter, and compared by the
        same comparison. Only two things differ, and both come from the
        Campaign rather than from a caller.

        *The Campaign is derived, not resolved.* Spec section 7.19 fixes every
        scientific field to the source run's and changes exactly the mutation
        contract and the Skill the baseline carries, so no public Climb wraps
        it and the draft names no public context.

        *The baseline carries a Skill.* ``baseline_skill`` is Skill v1 exactly
        as it was evaluated, taken from the source run's own verified inputs
        rather than rescanned from a directory that may have changed since,
        and it is snapshotted beside the candidate because the subject has to
        be handed its files.
        """
        created_at = self._clock()
        scan = self._scan(candidate_skill_path)
        self._require_candidate_files(scan)

        ensure_private_directory(self._paths.drafts_dir)
        staging = self._paths.drafts_dir / f"{_STAGING_PREFIX}{uuid.uuid4().hex}"

        try:
            ensure_private_directory(staging)
            staged = self._snapshot_skill(
                skill_dir=staging / _SKILL_DIR,
                scan=scan,
                candidate_label=candidate_label,
                parent_skill_digest=baseline_skill.artifact.root_digest,
            )
            campaign = derive_skill_replacement_campaign(
                source_campaign=source_campaign,
                source_run=source_report,
                baseline_skill=baseline_skill.artifact,
                candidate_skill=staged.artifact,
            )
            source = CampaignSource.local(
                campaign=campaign,
                data_policy=data_policy,
                publisher_validation=publisher_validation,
            )
            baseline, candidate, comparison = derive_replacement_manifests(
                campaign=campaign,
                candidate_skill=staged.artifact,
                campaign_digest=source.campaign_digest,
                created_at=created_at,
            )
            draft = self._build_draft(
                source=source,
                skill=staged.artifact,
                baseline=baseline,
                candidate=candidate,
                policy=self._build_policy_requirement(data_policy),
                created_at=created_at,
                warnings=self._replacement_warnings(scan),
            )
            draft_digest = digest_object(draft)

            self._drafts.create(
                draft=draft,
                baseline=baseline,
                candidate=candidate,
                comparison=comparison,
                source=source,
                validation_evidence=validation_evidence,
                staged_candidate_skill=staged,
                staged_baseline_skill=baseline_skill,
            )
        finally:
            remove_tree(staging)

        return PreparedDraft(
            draft=draft,
            draft_digest=draft_digest,
            manifest_comparison=comparison,
            source=source,
        )

    # -- Resolution and eligibility ----------------------------------------

    def _resolve(self, climb_reference: str) -> ResolvedClimbBundle:
        """Resolve Climb, Campaign, DataPolicy, receipt, and evidence."""
        resolved = self._catalog.get_climb(climb_reference)
        reference = resolved.publisher_validation.normalized_evidence
        if reference is None:
            raise VerificationError(
                "this Climb's publisher validation names no normalized "
                "evidence, so a draft prepared from it could not be checked "
                "offline",
                code=_PUBLISHER_EVIDENCE_MISSING,
                details={"climb_reference": climb_reference},
            )
        return ResolvedClimbBundle(
            resolved=resolved,
            validation_evidence=self._catalog.validation_evidence(resolved),
        )

    def _require_preparable(self, resolved: ResolvedClimb) -> None:
        """Refuse a Climb that is closed, or that this machine cannot run."""
        status = resolved.climb.metadata.status
        if status not in _PREPARABLE_STATUSES:
            raise PolicyError(
                f"this Climb is {status}, so it is not accepting submissions",
                code=_CLIMB_NOT_PREPARABLE,
                details={"status": status},
            )

        compatibility = self._catalog.compatibility(resolved)
        blocking = [issue for issue in compatibility.issues if issue.blocking]
        if blocking:
            raise PrerequisiteError(
                "this machine cannot run this Climb yet: "
                + " ".join(issue.message for issue in blocking),
                code=_CLIMB_NOT_PREPARABLE,
                details={"blocking_issues": [issue.code for issue in blocking]},
            )

    def _validate_candidate_policy(
        self, resolved: ResolvedClimb, scan: SkillScanResult
    ) -> None:
        """Enforce Climb candidate constraints and DataPolicy."""
        constraints = resolved.climb.candidate_policy.constraints
        if not constraints.min_skills <= 1 <= constraints.max_skills:
            raise PolicyError(
                "this Climb does not accept a single candidate skill; it asks "
                f"for {constraints.min_skills} to {constraints.max_skills}",
                code=_CANDIDATE_POLICY_VIOLATION,
                details={
                    "min_skills": constraints.min_skills,
                    "max_skills": constraints.max_skills,
                },
            )

        release = resolved.data_policy.candidate_skill.public_release
        if release == "prohibited":
            raise PolicyError(
                "this Climb's DataPolicy prohibits releasing a candidate skill, "
                "so there is nothing a submission could be entered as",
                code=_CANDIDATE_POLICY_VIOLATION,
                details={"candidate_skill_public_release": release},
            )

        self._require_candidate_files(scan)

    def _require_candidate_files(self, scan: SkillScanResult) -> None:
        """Enforce the file-count ceiling every candidate is held to.

        The Climb's own constraints and its public-release rule are checked
        beside this one when a Climb is what invited the submission. A locally
        derived replacement has neither, and inventing a public rule for a
        private comparison would be inventing a policy nobody stated.
        """
        if len(scan.files) > self._policy.maximum_files:
            raise PolicyError(
                f"this candidate has {len(scan.files)} files and the limit is "
                f"{self._policy.maximum_files}",
                code=_CANDIDATE_POLICY_VIOLATION,
                details={"file_count": len(scan.files)},
            )

    # -- The snapshot ------------------------------------------------------

    def _scan(self, skill_path: Path) -> SkillScanResult:
        """Run the PR5 scanner and report its refusals in PR6's vocabulary."""
        try:
            return scan_skill(skill_path, self._policy)
        except ValidationError as error:
            # The scanner already redacted anything secret-looking out of both
            # the message and the details; only the code is added here.
            secret = "findings" in error.details
            raise ValidationError(
                error.message,
                code=_SKILL_SECRET_DETECTED if secret else _SKILL_INVALID,
                details=error.details,
            ) from error

    def _snapshot_skill(
        self,
        *,
        skill_dir: Path,
        scan: SkillScanResult,
        candidate_label: str | None,
        parent_skill_digest: Digest | None = None,
    ) -> StagedSkill:
        """Create ``artifact.json``, ``bundle.tar``, and ``files/`` in staging.

        Each file is read once, checked against what the scan recorded, and
        written into the snapshot. The archive is then built from the copies
        rather than from the originals, so the expanded tree and the archive
        cannot disagree even if the source directory changes underneath us.

        The staged ``artifact.json`` makes the staging skill directory complete
        and self-describing. The draft store writes its own copy from
        ``draft.skill_artifact`` rather than moving this one, because the only
        artifact document a draft may hold is the one the draft's own digest
        commits to.

        ``parent_skill_digest`` names the Skill this one revises. It is set
        for a replacement candidate and absent for an insertion, which is the
        only lineage a ``SkillArtifact`` records.
        """
        files_dir = skill_dir / _FILES_DIR
        archive_path = skill_dir / _BUNDLE_FILE
        ensure_private_directory(skill_dir)
        ensure_private_directory(files_dir)

        copied = [self._copy_one(item, files_dir) for item in scan.files]
        archive_digest = build_deterministic_tar(copied, archive_path)

        entries = [
            SkillFile(
                path=item.relative_path.as_posix(),
                media_type=item.media_type,
                size=item.size,
                digest=item.digest,
            )
            for item in copied
        ]
        artifact = SkillArtifact(
            schema_version=SKILL_SCHEMA_VERSION,
            name=_candidate_name(candidate_label, scan.root),
            root_digest=skill_content_digest(entries),
            archive_digest=archive_digest,
            files=entries,
            source_kind="manual",
            parent_skill_digest=parent_skill_digest,
        )
        atomic_write_bytes(skill_dir / _ARTIFACT_FILE, canonical_json_bytes(artifact))
        return StagedSkill(artifact=artifact, archive=archive_path, files=files_dir)

    def _copy_one(self, item: ScannedFile, files_dir: Path) -> ScannedFile:
        """Copy one scanned file into the snapshot, or refuse the snapshot."""
        try:
            data = item.source_path.read_bytes()
        except OSError as error:
            raise VerificationError(
                "a candidate skill file could not be read while it was being "
                f"snapshotted: {item.relative_path}",
                code=_SKILL_SNAPSHOT_FAILED,
                details={"path": item.relative_path.as_posix()},
            ) from error

        if len(data) != item.size or sha256_digest_bytes(data) != item.digest:
            raise VerificationError(
                "a candidate skill file changed while it was being "
                f"snapshotted, so the draft was abandoned: {item.relative_path}",
                code=_SKILL_SNAPSHOT_FAILED,
                details={"path": item.relative_path.as_posix()},
            )

        target = files_dir / item.relative_path
        ensure_private_directory(target.parent)
        atomic_write_bytes(target, data)
        return ScannedFile(
            source_path=target,
            relative_path=PurePosixPath(item.relative_path),
            size=item.size,
            media_type=item.media_type,
            digest=item.digest,
        )

    # -- The science -------------------------------------------------------

    def _require_controlled(
        self,
        baseline: ExperimentManifest,
        candidate: ExperimentManifest,
        campaign: CampaignSpec,
    ) -> ManifestComparison:
        """Compare both variants and refuse a pair that measures more than one thing."""
        comparison = compare_manifests(baseline, candidate, campaign.mutation_contract)
        assert_controlled_comparison(comparison)
        return comparison

    def _build_policy_requirement(
        self, data_policy: DataPolicy
    ) -> PolicyAcceptanceRequirement:
        """State the rights a participant will be asked to accept."""
        return PolicyAcceptanceRequirement(
            data_policy_digest=digest_object(data_policy),
            required=True,
            summary=rights_summary(data_policy),
        )

    def _build_draft(
        self,
        *,
        source: CampaignSource,
        skill: SkillArtifact,
        baseline: ExperimentManifest,
        candidate: ExperimentManifest,
        policy: PolicyAcceptanceRequirement,
        created_at: datetime,
        warnings: list[str],
    ) -> SubmissionDraft:
        """Construct the immutable protocol draft."""
        return SubmissionDraft(
            schema_version=SUBMISSION_DRAFT_SCHEMA_VERSION,
            id=new_id("draft"),
            campaign_spec_digest=source.campaign_digest,
            program_ref=source.campaign.context.program_ref,
            public_context=source.public_context,
            data_policy_digest=source.data_policy_digest,
            outcome_contract_digest=source.campaign.context.outcome_contract_digest,
            skill_artifact=skill,
            baseline_manifest_digest=digest_object(baseline),
            candidate_manifest_digest=digest_object(candidate),
            included_files=[file.path for file in skill.files],
            estimated_episodes=self._estimate_episodes(source.campaign),
            policy_acceptance=policy,
            warnings=warnings,
            created_at=created_at,
        )

    def _estimate_episodes(self, campaign: CampaignSpec) -> int:
        """Return tasks × rollouts × two variants."""
        selection = campaign.taskset.selection
        return selection.num_tasks * selection.num_rollouts * _VARIANTS

    def _warnings(self, resolved: ResolvedClimb, scan: SkillScanResult) -> list[str]:
        """Say everything a participant should know before confirming."""
        warnings: list[str] = []

        if resolved.climb.publication.proof_grade == "development_only":
            warnings.append(
                "This is a development Climb. Its results are for trying the "
                "flow out and are not comparable evidence."
            )

        warnings.append(
            "Results are attested by this machine only. Nobody else has "
            "verified that this run happened as described."
        )
        warnings.append(_comparison_warning(resolved.campaign))
        if executor_kind_for(resolved.campaign) == "fake":
            warnings.append(
                "Nothing produced here is a public proof. No agent is "
                "evaluated and no model is called on this Climb's runs."
            )
        else:
            warnings.append(
                "Nothing produced here is a public proof. Starting this run "
                "evaluates the agent for real and spends money on model calls."
            )

        release = resolved.data_policy.candidate_skill.public_release
        if release == "required_for_climb":
            warnings.append(
                "Entering this Climb requires releasing the candidate skill publicly."
            )
        elif release == "consent_required":
            warnings.append(
                "Releasing the candidate skill publicly needs your separate consent."
            )

        warnings.extend(scan.warnings)
        return warnings

    def _replacement_warnings(self, scan: SkillScanResult) -> list[str]:
        """Say what a local Skill-against-Skill comparison is, and is not.

        None of the public warnings apply: there is no Climb to enter, nothing
        is released, and no leaderboard is involved. What a reader has to know
        instead is that the baseline is no longer "no Skill" — a candidate that
        loses here lost to a Skill that already worked.
        """
        return [
            # First, because the rights summary this draft carries is the
            # policy of the Climb the first run entered, and read on its own it
            # would describe a public submission this is not.
            "The data rights stated for this run are the ones the run it was "
            "prepared from was carried out under. They still govern what "
            "happens to this run's material, and they are why acceptance is "
            "asked for again.",
            "This comparison is local. No Climb wraps it, nothing is entered "
            "anywhere, nothing is published, and nothing is uploaded. Model "
            "inference still goes to the model provider you configured, under "
            "that provider's policies.",
            "This compares one Skill against another Skill, not against no "
            "Skill. The baseline is the version measured by the run this was "
            "prepared from.",
            "Results are attested by this machine only. Nobody else has "
            "verified that this run happened as described.",
            *scan.warnings,
        ]


# ---------------------------------------------------------------------------
# How the comparison is run
# ---------------------------------------------------------------------------


def _comparison_warning(campaign: CampaignSpec) -> str:
    """Say how this Campaign runs its two sides, reading it off the Campaign.

    The approval screen is where a person decides to spend money on a
    comparison, so the sentence describing how that comparison is controlled
    has to be the one this Campaign will actually produce. It is therefore
    derived from ``execution.order`` — the same field the executor dispatches
    on when it picks between running the two sides side by side and running one
    after the other (``runs/real.py``). Writing the sentence out by hand is how
    it came to describe an order the Campaign had not asked for since the day
    side-by-side execution arrived.

    Exhaustive on purpose: a Campaign that grows a third way of running its two
    sides fails to typecheck here rather than quietly inheriting a sentence
    written for a different one.
    """
    match campaign.execution.order:
        case VariantSchedule.PARALLEL:
            return (
                "The baseline and the candidate launch in parallel against the "
                "same committed task set, under matched configuration, so the "
                "two are compared and not merely reported."
            )
        case VariantSchedule.SEQUENTIAL:
            return (
                "The baseline runs first and the candidate second, on the same "
                "committed tasks, so the two are compared and not merely "
                "reported."
            )
    assert_never(campaign.execution.order)


# ---------------------------------------------------------------------------
# The rights summary
# ---------------------------------------------------------------------------

#: How each permission is said in a sentence. Fixed strings: the summary is
#: stored in a protocol artifact and must read the same way every time the same
#: policy is prepared against.
_PERMISSION_PHRASE: Final[dict[str, str]] = {
    "allowed": "allowed",
    "prohibited": "prohibited",
    "consent_required": "only with your separate consent",
}

_RELEASE_PHRASE: Final[dict[str, str]] = {
    "required_for_climb": "required in order to enter this Climb",
    "allowed": "allowed",
    "prohibited": "prohibited",
    "consent_required": "only with your separate consent",
}

_OWNER_PHRASE: Final[dict[str, str]] = {
    "participant": "You own",
    "account": "Your account owns",
    "shared": "You and Techtree jointly own",
}

_VISIBILITY_PHRASE: Final[dict[str, str]] = {
    "public": "published",
    "private": "kept private",
    "prohibited": "not produced",
}


def rights_summary(data_policy: DataPolicy) -> str:
    """Return the stable sentence-per-right summary shown before confirming.

    Derived entirely from the policy, so it cannot describe rights the policy
    does not grant, and worded from fixed phrases, so the same policy always
    produces the same bytes.
    """
    owner = _OWNER_PHRASE[data_policy.owner.kind]
    raw = data_policy.raw_episodes
    return " ".join(
        [
            f"{owner} the candidate skill and everything this run produces.",
            "Publishing the candidate skill is "
            f"{_RELEASE_PHRASE[data_policy.candidate_skill.public_release]}.",
            "Uploading raw episodes to a server is "
            f"{_PERMISSION_PHRASE[raw.server_upload]}.",
            f"Training on raw episodes is {_PERMISSION_PHRASE[raw.training_use]}.",
            "The uplift report is "
            f"{_VISIBILITY_PHRASE[data_policy.derived_artifacts.uplift_report]}.",
            (
                "You can withdraw future uses later."
                if data_policy.revocation.future_use_revocable
                else "Future uses cannot be withdrawn later."
            ),
        ]
    )


def _candidate_name(candidate_label: str | None, root: Path) -> str:
    """Return the name this candidate is filed under."""
    label = (candidate_label or root.name).strip()
    if _LABEL_PATTERN.fullmatch(label) is None:
        raise ValidationError(
            "a candidate label is up to 64 letters, digits, spaces, dots, "
            "dashes, or underscores, and starts with a letter or a digit",
            code=_SKILL_INVALID,
            details={"label": label},
        )
    return label
