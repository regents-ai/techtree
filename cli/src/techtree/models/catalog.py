"""The packaged catalog and what it can tell a caller. Decisions 0003 A6/A7.

Three things live here.

The *index* is the map from a public Climb reference, and from every object
digest it depends on, to a file inside the package. It is generated, never
hand-edited, and it is typed and schema'd so that a hand-edit is caught rather
than shipped. Paths are relative and non-escaping; digests appear once; two
digests never claim the same file.

The *summary* is what ``techtree climb show`` needs in one object: identity,
what is being measured, and the rights the participant would be agreeing to.
``DataPolicySummary`` is a deliberate projection rather than the whole
``DataPolicy``, because a listing that reprinted the full policy tree would be
read by nobody.

The *compatibility result* is the honest answer to "could I actually run this
here?" — host platform, engine state, evaluation backend — as a list of typed
issues. ``compatible`` is derived from the blocking issues rather than asserted
alongside them, so a result cannot claim to be runnable while listing the
reason it is not. Before WP4 an absent engine blocks ``prepare`` while ``list``
and ``show`` still display the Climb.

The summary and the compatibility result each have a v0.2 sibling, on the
terms decision 0040 fixes for the two Campaign documents. Both v0.1 documents
read their execution and subject facts out of the Campaign: the evaluation
backend kind, and the harness the subject runs. Under v0.2 those facts belong
to the execution plane and the subject plane of the plan the Campaign binds,
so ``ClimbSummaryV2`` and ``CompatibilityResultV2`` state them from there and
:mod:`techtree.execution_facts` is the only place the projection is written.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from techtree.models.base import Digest, NonEmptyString, ProtocolModel
from techtree.models.evaluation_backend import EvaluationBackendKind
from techtree.models.execution_plan import ExecutionBackendKind, SubjectBackendKind

__all__ = [
    "CatalogClimbEntry",
    "CatalogIndex",
    "CatalogObjectLocation",
    "ClimbSummary",
    "ClimbSummaryV2",
    "CompatibilityIssue",
    "CompatibilityResult",
    "CompatibilityResultV2",
    "DataPolicySummary",
    "EngineCompatibilityStatus",
]


def _check_relative_catalog_path(value: str) -> str:
    """Reject absolute, escaping, or non-POSIX catalog paths."""
    if value != value.strip():
        raise ValueError(f"catalog path has surrounding whitespace: {value!r}")
    if value.startswith("/") or (len(value) > 1 and value[1] == ":"):
        raise ValueError(f"catalog paths are relative to the catalog root: {value!r}")
    if "\\" in value:
        raise ValueError(f"catalog paths use forward slashes: {value!r}")
    if any(segment in ("", ".", "..") for segment in value.split("/")):
        raise ValueError(f"catalog path is not a normalized relative path: {value!r}")
    return value


# ---------------------------------------------------------------------------
# The index
# ---------------------------------------------------------------------------


class CatalogClimbEntry(ProtocolModel):
    """One public Climb the package ships."""

    reference: NonEmptyString
    digest: Digest
    path: NonEmptyString

    @model_validator(mode="after")
    def _check_path(self) -> Self:
        """Reject a path that leaves the catalog root."""
        _check_relative_catalog_path(self.path)
        return self


class CatalogObjectLocation(ProtocolModel):
    """Where one content-addressed object lives, and what kind it is."""

    kind: Literal[
        "campaign",
        "data_policy",
        "taskset_validation",
        "validation_evidence",
    ]
    path: NonEmptyString
    media_type: NonEmptyString

    @model_validator(mode="after")
    def _check_path(self) -> Self:
        """Reject a path that leaves the catalog root."""
        _check_relative_catalog_path(self.path)
        return self


class CatalogIndex(ProtocolModel):
    """The generated map of everything the package ships.

    Decisions document 0003 A7. Path existence, digest verification, and the
    kind-matches-the-request check belong to the repository that loads these
    files; what can be decided from the document alone is decided here.
    """

    schema_version: Literal["techtree.catalog.v1alpha1"]
    climbs: list[CatalogClimbEntry]
    objects: dict[Digest, CatalogObjectLocation]

    @model_validator(mode="after")
    def _check_index_is_unambiguous(self) -> Self:
        """Reject repeated references, repeated digests, or shared paths."""
        references = [entry.reference for entry in self.climbs]
        if len(set(references)) != len(references):
            raise ValueError("each Climb reference appears once in the catalog")
        climb_digests = [entry.digest for entry in self.climbs]
        if len(set(climb_digests)) != len(climb_digests):
            raise ValueError("each Climb digest appears once in the catalog")

        paths = [entry.path for entry in self.climbs] + [
            location.path for location in self.objects.values()
        ]
        if len(set(paths)) != len(paths):
            raise ValueError(
                "two catalog entries claim the same file; a digest-to-path map "
                "that is not one-to-one cannot be verified"
            )
        return self


# ---------------------------------------------------------------------------
# Compatibility
# ---------------------------------------------------------------------------


class CompatibilityIssue(ProtocolModel):
    """One reason a Climb might not run here."""

    code: NonEmptyString
    severity: Literal["warning", "error"]
    message: NonEmptyString
    blocking: bool

    @model_validator(mode="after")
    def _check_blocking_implies_error(self) -> Self:
        """Reject a warning that also claims to block."""
        if self.blocking and self.severity != "error":
            raise ValueError("a blocking issue is an error, not a warning")
        return self


class EngineCompatibilityStatus(StrEnum):
    """What is known about the required engine on this host."""

    UNKNOWN = "unknown"
    NOT_INSTALLED = "not_installed"
    INSTALLED_UNVERIFIED = "installed_unverified"
    VERIFIED = "verified"


def _check_the_verdict_follows_from_the_issues(
    *,
    compatible: bool,
    issues: list[CompatibilityIssue],
) -> None:
    """Reject a verdict that disagrees with the issues beside it, either shape."""
    blocking = any(issue.blocking for issue in issues)
    if compatible and blocking:
        raise ValueError("compatible is true only when no listed issue is blocking")
    if not compatible and not blocking:
        raise ValueError(
            "an incompatible result must list the blocking issue that made "
            "it incompatible"
        )
    if len({issue.code for issue in issues}) != len(issues):
        raise ValueError("each compatibility issue is reported once")


class CompatibilityResult(ProtocolModel):
    """Whether this host can run this Climb, and what stands in the way."""

    compatible: bool
    host_platform: NonEmptyString
    host_supported: bool
    required_engine_digest: Digest
    engine_status: EngineCompatibilityStatus
    evaluation_backend_kind: EvaluationBackendKind
    evaluation_backend_supported: bool
    issues: list[CompatibilityIssue]

    @model_validator(mode="after")
    def _check_compatibility_follows_from_the_issues(self) -> Self:
        """Reject a verdict that disagrees with the issues it lists."""
        _check_the_verdict_follows_from_the_issues(
            compatible=self.compatible, issues=self.issues
        )
        return self


class CompatibilityResultV2(ProtocolModel):
    """Whether this host can run this v0.2 Campaign, and what stands in the way.

    A sibling of :class:`CompatibilityResult`, not a refinement of it. The
    question it answers is the same one, but under v0.2 the answer turns on
    the plan the Campaign binds rather than on a backend field the Campaign
    carried, so this document names the plan it judged and reports every plane
    a host can fail: which Verifiers build supplies task and reward truth, who
    orchestrates the comparison, and how the measured agent is reached. A plan
    naming a backend this release does not resolve is runnable nowhere,
    whatever the host has installed.

    ``required_engine_digest`` is not that first plane and never was. It is
    the engine the publisher validated the taskset against, carried here from
    the validation receipt, and it answers a different question from the wheel
    the plan pins. The two coordinates are reported side by side rather than
    collapsed, because a host that has the validated engine and not the
    planned one is in a state a reader has to be told about rather than have
    decided for them.
    """

    compatible: bool
    host_platform: NonEmptyString
    host_supported: bool
    required_engine_digest: Digest
    engine_status: EngineCompatibilityStatus
    execution_plan_digest: Digest
    evaluation_engine_source_commit: NonEmptyString
    evaluation_engine_wheel_digest: Digest
    execution_backend_kind: ExecutionBackendKind
    execution_backend_supported: bool
    subject_backend_kind: SubjectBackendKind
    subject_backend_supported: bool
    issues: list[CompatibilityIssue]

    @model_validator(mode="after")
    def _check_compatibility_follows_from_the_issues(self) -> Self:
        """Reject a verdict that disagrees with the issues it lists."""
        _check_the_verdict_follows_from_the_issues(
            compatible=self.compatible, issues=self.issues
        )
        return self


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------


class DataPolicySummary(ProtocolModel):
    """The four rights a participant most needs to see before starting."""

    raw_episode_server_upload: Literal["allowed", "prohibited", "consent_required"]
    raw_episode_training_use: Literal["allowed", "prohibited", "consent_required"]
    candidate_skill_public_release: Literal[
        "required_for_climb",
        "allowed",
        "prohibited",
        "consent_required",
    ]
    uplift_report_visibility: Literal["public", "private", "prohibited"]


class ClimbSummary(ProtocolModel):
    """Everything ``climb list`` and ``climb show`` display, in one object."""

    reference: NonEmptyString
    climb_digest: Digest
    campaign_spec_digest: Digest
    title: NonEmptyString
    summary: NonEmptyString
    status: Literal["open", "closed", "development"]
    purpose: NonEmptyString
    taskset_id: NonEmptyString
    task_count: int = Field(ge=1)
    subject_harness: NonEmptyString
    subject_harness_version: NonEmptyString
    mutation_kind: Literal["skill_insertion"]
    candidate_skill_visibility: Literal["public", "private"]
    evaluation_backend: EvaluationBackendKind
    proof_grade: Literal["development_only", "P1"]
    data_policy: DataPolicySummary
    compatibility: CompatibilityResult


class ClimbSummaryV2(ProtocolModel):
    """Everything ``climb list`` and ``climb show`` display for a v0.2 Climb.

    A sibling of :class:`ClimbSummary`, not a refinement of it. Three display
    facts move to the plan the Campaign binds: which harness is measured and at
    which version are the plan's subject plane, and who orchestrates the
    comparison is its execution plane, in place of the evaluation-backend kind
    the v0.1 summary read out of the Campaign.

    Which plan that is stays in the compatibility result below rather than
    being repeated here. A summary is a projection for display, and repeating
    a digest it already carries would give a reader two places to check and no
    rule for which one to believe.
    """

    reference: NonEmptyString
    climb_digest: Digest
    campaign_spec_digest: Digest
    title: NonEmptyString
    summary: NonEmptyString
    status: Literal["open", "closed", "development"]
    purpose: NonEmptyString
    taskset_id: NonEmptyString
    task_count: int = Field(ge=1)
    subject_harness: NonEmptyString
    subject_harness_version: NonEmptyString
    mutation_kind: Literal["skill_insertion"]
    candidate_skill_visibility: Literal["public", "private"]
    execution_backend_kind: ExecutionBackendKind
    proof_grade: Literal["development_only", "P1"]
    data_policy: DataPolicySummary
    compatibility: CompatibilityResultV2
