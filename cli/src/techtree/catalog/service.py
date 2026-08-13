"""What a Climb is, and whether you could run it. Spec 14.3, decisions 0003.

The repository can prove that a file is the object it claims to be. It cannot
say whether four such objects, each individually valid, tell one consistent
story. That is this module's job, and it is the reason the graph is assembled
in one place instead of wherever a command happens to need a piece of it.

:class:`~techtree.models.climb.ResolvedClimb` performs the edge checks the
moment the four objects are put together: the Climb points at the Campaign that
was loaded, the Campaign at the DataPolicy and the receipt that were loaded, and
the candidate policy matches the mutation contract. It also runs the rights
comparison, which raises :class:`~techtree.errors.PolicyError` rather than a
validation error — a Climb that promises to publish something its DataPolicy
forbids is not malformed, it is dishonest, and a caller should be able to tell
those two failures apart.

Three checks sit outside that model because they need more than the four
objects it holds:

* the shipped validation evidence must resolve through the catalog and describe
  the same taskset lock the receipt was issued for (decisions 0003 A4: a public
  catalog has no dangling references);
* the validated tasks must be exactly the tasks the Campaign committed to, in
  order;
* a development Climb and a development-only proof grade imply each other, so a
  fixture cannot be dressed up as evidence or a real Climb quietly demoted.

Compatibility is answered separately and never conflated with validity. A Climb
can be perfectly well-formed and still not runnable here, and before the managed
engine exists that is the ordinary case: the absent engine blocks preparing a
submission while ``list`` and ``show`` continue to display the Climb.
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass
from typing import Final, Protocol

from techtree.catalog.repository import EmbeddedCatalogRepository, climb_reference
from techtree.errors import NotFoundError, PolicyError, PrerequisiteError, UsageError
from techtree.models.base import Digest
from techtree.models.catalog import (
    ClimbSummary,
    CompatibilityIssue,
    CompatibilityResult,
    DataPolicySummary,
    EngineCompatibilityStatus,
)
from techtree.models.climb import ResolvedClimb, check_climb_policy_consistency
from techtree.models.data_policy import DataPolicy
from techtree.models.engine import normalize_host_platform
from techtree.models.evaluation_backend import SUPPORTED_EVALUATION_BACKEND_KINDS
from techtree.models.validation import ValidationEvidence
from techtree.paths import TechtreePaths

__all__ = [
    "CLIMB_LIST_STATUSES",
    "CatalogService",
    "EngineStatusSource",
    "HostInfo",
    "InstalledEngineStatus",
    "current_host_info",
    "data_policy_summary",
]

#: What ``list_climbs`` accepts. ``available`` is the default because a reader
#: browsing Climbs wants the ones they could enter, and in a build whose only
#: Climbs are development fixtures that has to include them.
CLIMB_LIST_STATUSES: Final[frozenset[str]] = frozenset(
    {"available", "all", "open", "closed", "development"}
)

_AVAILABLE_STATUSES: Final[frozenset[str]] = frozenset({"open", "development"})


@dataclass(frozen=True)
class HostInfo:
    """The three facts about this machine a compatibility answer rests on."""

    operating_system: str
    architecture: str
    python_version: str


def current_host_info() -> HostInfo:
    """Return the host Techtree is running on, unnormalized.

    The raw values are carried rather than the normalized platform string so
    that an unsupported machine can still be named in the answer it gets.
    """
    return HostInfo(
        operating_system=sys.platform,
        architecture=platform.machine(),
        python_version=platform.python_version(),
    )


class EngineStatusSource(Protocol):
    """Whatever can say what is known about one engine bundle on this host."""

    def status_for(self, engine_digest: Digest) -> EngineCompatibilityStatus:
        """Return what is known about that engine here."""
        ...


class InstalledEngineStatus:
    """Answers the engine question from what the filesystem can prove.

    An engine directory that exists is an engine that was installed. Whether
    its contents still hash to the digest they were installed under is a
    question only the managed engine subsystem can answer, so this reports
    ``installed_unverified`` and lets the caller decide what that is worth.
    """

    def __init__(self, paths: TechtreePaths) -> None:
        self._paths = paths

    def status_for(self, engine_digest: Digest) -> EngineCompatibilityStatus:
        """Return whether that engine bundle is installed on this host."""
        if not self._paths.engine_dir(engine_digest).is_dir():
            return EngineCompatibilityStatus.NOT_INSTALLED
        return EngineCompatibilityStatus.INSTALLED_UNVERIFIED


class CatalogService:
    """Resolves, checks, and summarizes the Climbs a build ships."""

    def __init__(
        self,
        repository: EmbeddedCatalogRepository,
        host_info: HostInfo,
        engine_status: EngineStatusSource,
    ) -> None:
        self._repository = repository
        self._host_info = host_info
        self._engine_status = engine_status

    def list_climbs(self, *, status: str = "available") -> list[ClimbSummary]:
        """Return one summary per Climb, in catalog order.

        Every listed Climb is fully resolved first. Listing a Climb that cannot
        be resolved would be advertising something no reader could enter, and
        the failure would then surface at ``prepare`` instead of here.
        """
        if status not in CLIMB_LIST_STATUSES:
            raise UsageError(
                f"unknown Climb status {status!r}; choose one of "
                + ", ".join(sorted(CLIMB_LIST_STATUSES)),
                code="unknown_climb_status",
                details={"status": status},
            )

        summaries: list[ClimbSummary] = []
        for reference in self._repository.list_climb_references():
            resolved = self.get_climb(reference)
            if _status_matches(resolved.climb.metadata.status, status):
                summaries.append(self.climb_summary(resolved))
        return summaries

    def get_climb(self, reference: str) -> ResolvedClimb:
        """Resolve one Climb into its complete, cross-checked object graph."""
        entry = self._repository.climb_entry(reference)
        climb = self._repository.load_climb(entry.reference)
        campaign = self._repository.load_campaign(climb.campaign_spec_digest)
        data_policy = self._repository.load_data_policy(campaign.data_policy_digest)
        receipt = self._repository.load_validation_receipt(
            campaign.taskset.validation_receipt_digest
        )

        resolved = ResolvedClimb(
            climb=climb,
            climb_digest=entry.digest,
            campaign=campaign,
            campaign_digest=climb.campaign_spec_digest,
            data_policy=data_policy,
            data_policy_digest=campaign.data_policy_digest,
            publisher_validation=receipt,
            publisher_validation_digest=campaign.taskset.validation_receipt_digest,
        )

        self._check_validation_evidence(resolved)
        self.validate_public_policy(resolved)
        return resolved

    def compatibility(self, resolved: ResolvedClimb) -> CompatibilityResult:
        """Report whether this host could run this Climb, and what is missing."""
        issues: list[CompatibilityIssue] = []

        host_platform, host_supported = self._host_platform()
        if not host_supported:
            issues.append(
                CompatibilityIssue(
                    code="host_unsupported",
                    severity="error",
                    message=(
                        f"Techtree does not support {host_platform}; it runs on "
                        "macOS and Linux, on arm64 and amd64."
                    ),
                    blocking=True,
                )
            )

        engine_digest = resolved.publisher_validation.engine_digest
        engine_status = self._engine_status.status_for(engine_digest)
        engine_issue = _engine_issue(engine_status)
        if engine_issue is not None:
            issues.append(engine_issue)

        backend_kind = resolved.campaign.evaluation_backend.kind
        backend_supported = backend_kind in SUPPORTED_EVALUATION_BACKEND_KINDS
        if not backend_supported:
            issues.append(
                CompatibilityIssue(
                    code="evaluation_backend_unsupported",
                    severity="error",
                    message=(
                        f"This Climb is evaluated by {backend_kind.value}, which "
                        "this version of Techtree cannot run."
                    ),
                    blocking=True,
                )
            )

        return CompatibilityResult(
            compatible=not any(issue.blocking for issue in issues),
            host_platform=host_platform,
            host_supported=host_supported,
            required_engine_digest=engine_digest,
            engine_status=engine_status,
            evaluation_backend_kind=backend_kind,
            evaluation_backend_supported=backend_supported,
            issues=issues,
        )

    def validation_evidence(self, resolved: ResolvedClimb) -> ValidationEvidence:
        """Return the normalized evidence this Climb's receipt was issued from.

        Preparing a submission copies the evidence into the draft so that the
        draft stays verifiable when the catalog that shipped it does not
        (decisions document 0003 A4). The graph was already checked when it was
        resolved, so a receipt with no evidence here is a caller asking for
        something this Climb does not have.
        """
        reference = resolved.publisher_validation.normalized_evidence
        if reference is None:
            raise NotFoundError(
                "this Climb's publisher validation names no normalized evidence",
                code="publisher_validation_evidence_missing",
                details={"climb": climb_reference(resolved.climb)},
            )
        return self._repository.load_validation_evidence(reference.digest)

    def validate_public_policy(self, resolved: ResolvedClimb) -> None:
        """Reject contradictions among the Climb, Campaign, and DataPolicy.

        The rights comparison already ran when the graph was assembled; running
        it again costs nothing and means a caller holding a ``ResolvedClimb``
        from anywhere can ask the question directly.
        """
        check_climb_policy_consistency(resolved.climb, resolved.data_policy)

        status = resolved.climb.metadata.status
        proof_grade = resolved.climb.publication.proof_grade
        if (status == "development") != (proof_grade == "development_only"):
            raise PolicyError(
                f"this Climb is {status} and claims a {proof_grade} proof grade; "
                "a development Climb produces development-only results and "
                "nothing else does",
                code="proof_grade_contradiction",
                details={"status": status, "proof_grade": proof_grade},
            )

    def climb_summary(self, resolved: ResolvedClimb) -> ClimbSummary:
        """Project a resolved graph into what ``list`` and ``show`` display."""
        campaign = resolved.campaign
        climb = resolved.climb

        return ClimbSummary(
            reference=climb_reference(climb),
            climb_digest=resolved.climb_digest,
            campaign_spec_digest=resolved.campaign_digest,
            title=climb.metadata.title,
            summary=climb.metadata.summary,
            status=climb.metadata.status,
            purpose=campaign.metadata.purpose,
            taskset_id=campaign.taskset.ref.id,
            task_count=campaign.taskset.selection.num_tasks,
            subject_harness=campaign.subject.harness.id,
            subject_harness_version=campaign.subject.harness.version,
            # Read off the Climb rather than the Campaign: a public Climb still
            # requires skill_insertion, and ``ResolvedClimb`` refuses to exist
            # unless the Campaign's mutation kind is the one the Climb names.
            mutation_kind=climb.candidate_policy.required_mutation,
            candidate_skill_visibility=climb.candidate_policy.skill_visibility,
            evaluation_backend=campaign.evaluation_backend.kind,
            proof_grade=climb.publication.proof_grade,
            data_policy=data_policy_summary(resolved.data_policy),
            compatibility=self.compatibility(resolved),
        )

    # -- Internals ---------------------------------------------------------

    def _host_platform(self) -> tuple[str, bool]:
        """Return the normalized host platform, or the raw pair and False."""
        try:
            return (
                normalize_host_platform(
                    self._host_info.operating_system, self._host_info.architecture
                ),
                True,
            )
        except PrerequisiteError:
            return (
                f"{self._host_info.operating_system}/{self._host_info.architecture}",
                False,
            )

    def _check_validation_evidence(self, resolved: ResolvedClimb) -> None:
        """Resolve the receipt's evidence and check it describes this taskset.

        Decisions document 0003 A4: an artifact a public object references is
        resolvable through the catalog, or it is not referenced at all. The
        evidence is also the only shipped record of which tasks were actually
        validated, so it is compared against the Campaign's commitment here.
        """
        reference = resolved.publisher_validation.normalized_evidence
        if reference is None:
            return

        evidence = self._repository.load_validation_evidence(reference.digest)

        if evidence.taskset_lock_digest != (
            resolved.publisher_validation.taskset_lock_digest
        ):
            raise PolicyError(
                "the shipped validation evidence was produced for a different "
                "taskset than the receipt it belongs to",
                code="validation_evidence_mismatch",
                details={
                    "receipt_taskset_lock_digest": (
                        resolved.publisher_validation.taskset_lock_digest
                    ),
                    "evidence_taskset_lock_digest": evidence.taskset_lock_digest,
                },
            )

        validated = [task.task_hash for task in evidence.tasks]
        committed = list(resolved.campaign.taskset.membership.ordered_task_hashes)
        if validated != committed:
            raise PolicyError(
                "the Campaign commits to different tasks than the ones the "
                "publisher validated",
                code="validated_membership_mismatch",
                details={
                    "committed_task_count": len(committed),
                    "validated_task_count": len(validated),
                },
            )


def data_policy_summary(data_policy: DataPolicy) -> DataPolicySummary:
    """Project a DataPolicy into the four rights a reader most needs."""
    return DataPolicySummary(
        raw_episode_server_upload=data_policy.raw_episodes.server_upload,
        raw_episode_training_use=data_policy.raw_episodes.training_use,
        candidate_skill_public_release=data_policy.candidate_skill.public_release,
        uplift_report_visibility=data_policy.derived_artifacts.uplift_report,
    )


def _status_matches(climb_status: str, requested: str) -> bool:
    if requested == "all":
        return True
    if requested == "available":
        return climb_status in _AVAILABLE_STATUSES
    return climb_status == requested


def _engine_issue(status: EngineCompatibilityStatus) -> CompatibilityIssue | None:
    """Turn what is known about the engine into what it means for this Climb."""
    if status is EngineCompatibilityStatus.VERIFIED:
        return None
    if status is EngineCompatibilityStatus.INSTALLED_UNVERIFIED:
        return CompatibilityIssue(
            code="engine_not_verified",
            severity="warning",
            message=(
                "The evaluation engine is installed but has not been checked "
                "since. Run `techtree engine verify` before you rely on a result."
            ),
            blocking=False,
        )
    if status is EngineCompatibilityStatus.NOT_INSTALLED:
        return CompatibilityIssue(
            code="engine_not_installed",
            severity="error",
            message=(
                "The evaluation engine this Climb needs is not installed yet. "
                "Run `techtree engine install` before preparing a submission."
            ),
            blocking=True,
        )
    return CompatibilityIssue(
        code="engine_status_unknown",
        severity="error",
        message=(
            "Techtree cannot tell whether the evaluation engine this Climb "
            "needs is available on this machine."
        ),
        blocking=True,
    )
