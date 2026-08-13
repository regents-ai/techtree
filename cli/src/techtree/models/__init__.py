"""Techtree protocol models. Spec section 11.1.

This package exports only stable model classes. It never imports services, CLI
code, resources, or settings, and no model file reaches back into
:mod:`techtree.canonical` — models describe documents, they do not hash them.

Exports are grouped the way the protocol is layered:

Campaign and public wrapper
    The scientific contract and the public invitation that wraps it.

Execution artifacts
    Everything one run produces, all of it anchored to a Campaign digest.

Taskset validation
    The lock, the deterministic receipt, and the local execution record.

Catalog, CLI, and local state
    What the packaged catalog ships and what the CLI hands back.
"""

from __future__ import annotations

from techtree.models.base import (
    ArtifactRef,
    Digest,
    JsonScalar,
    JsonValue,
    NonEmptyString,
    ObjectEnvelope,
    ProtocolModel,
    PublicKeyRef,
    SignatureEnvelope,
    StateModel,
    UtcDateTime,
)

# --- Campaign and public wrapper -------------------------------------------
from techtree.models.campaign import (
    AgentSpec,
    BudgetSpec,
    CampaignContext,
    CampaignMetadata,
    CampaignSpec,
    CampaignTaskset,
    EnvironmentSpec,
    EvidenceRequirements,
    ExecutionSpec,
    HarnessSpec,
    ModelSpec,
    MutationContract,
    PackageRef,
    ProgramRef,
    PublicContext,
    RuntimeSpec,
    SamplingSpec,
    ScoringSpec,
    TaskMembershipCommitment,
    TaskSelection,
    TasksetRef,
)
from techtree.models.catalog import (
    CatalogClimbEntry,
    CatalogIndex,
    CatalogObjectLocation,
    ClimbSummary,
    CompatibilityIssue,
    CompatibilityResult,
    DataPolicySummary,
    EngineCompatibilityStatus,
)

# --- Catalog, CLI, and local state -----------------------------------------
from techtree.models.cli import (
    CheckStatus,
    CliEnvelope,
    CliError,
    CliMessage,
    DoctorCheck,
    MessageLevel,
    NextAction,
)
from techtree.models.climb import (
    CandidateConstraints,
    CandidatePolicy,
    ClimbManifest,
    ClimbMetadata,
    LeaderboardPolicy,
    PublicationPolicy,
    ResolvedClimb,
    check_climb_policy_consistency,
)
from techtree.models.data_policy import (
    CandidateSkillPolicy,
    DataOwner,
    DataPolicy,
    DerivedArtifactPolicy,
    RawEpisodePolicy,
    RevocationPolicy,
)
from techtree.models.engine import (
    EngineDescriptor,
    EngineInstallation,
    EnginePackage,
    EngineStatus,
    HostPlatform,
    normalize_host_platform,
)

# --- Execution artifacts ---------------------------------------------------
from techtree.models.episode_receipt import (
    EpisodeReceipt,
    EvidenceStatus,
    NamedTraceReceipt,
    ScoreStatus,
    SubjectRuntimeReceipt,
)
from techtree.models.evaluation_backend import (
    AttestationKind,
    EvaluationBackendKind,
    EvaluationBackendSpec,
)
from techtree.models.experiment import (
    ExperimentConfiguration,
    ExperimentManifest,
    ExperimentVariant,
    JsonDifference,
    ManifestComparison,
)
from techtree.models.run import (
    PolicyAcknowledgement,
    RunEvent,
    RunPhase,
    RunProgress,
    RunRequest,
    RunState,
    RunStatus,
)
from techtree.models.skill import (
    ConfirmationRecord,
    PolicyAcceptanceRequirement,
    SecretFinding,
    SkillArtifact,
    SkillFile,
    SubmissionDraft,
)
from techtree.models.uplift_report import (
    ComparisonStatus,
    ExecutionStatus,
    PrimaryUpliftResult,
    PublicationStatus,
    TaskDelta,
    UpliftDecision,
    UpliftReport,
    UpliftStatuses,
)

# --- Taskset validation ----------------------------------------------------
from techtree.models.validation import (
    TasksetLock,
    TasksetValidationReceipt,
    UpstreamValidationSummary,
    ValidationCheck,
    ValidationEvidence,
    ValidationEvidenceSummary,
    ValidationEvidenceTask,
    ValidationExecutionRecord,
    ValidationMethod,
    ValidationTaskOutcome,
    validation_display_id,
)

__all__ = [
    "AgentSpec",
    "ArtifactRef",
    "AttestationKind",
    "BudgetSpec",
    "CampaignContext",
    "CampaignMetadata",
    "CampaignSpec",
    "CampaignTaskset",
    "CandidateConstraints",
    "CandidatePolicy",
    "CandidateSkillPolicy",
    "CatalogClimbEntry",
    "CatalogIndex",
    "CatalogObjectLocation",
    "CheckStatus",
    "CliEnvelope",
    "CliError",
    "CliMessage",
    "ClimbManifest",
    "ClimbMetadata",
    "ClimbSummary",
    "ComparisonStatus",
    "CompatibilityIssue",
    "CompatibilityResult",
    "ConfirmationRecord",
    "DataOwner",
    "DataPolicy",
    "DataPolicySummary",
    "DerivedArtifactPolicy",
    "Digest",
    "DoctorCheck",
    "EngineCompatibilityStatus",
    "EngineDescriptor",
    "EngineInstallation",
    "EnginePackage",
    "EngineStatus",
    "EnvironmentSpec",
    "EpisodeReceipt",
    "EvaluationBackendKind",
    "EvaluationBackendSpec",
    "EvidenceRequirements",
    "EvidenceStatus",
    "ExecutionSpec",
    "ExecutionStatus",
    "ExperimentConfiguration",
    "ExperimentManifest",
    "ExperimentVariant",
    "HarnessSpec",
    "HostPlatform",
    "JsonDifference",
    "JsonScalar",
    "JsonValue",
    "LeaderboardPolicy",
    "ManifestComparison",
    "MessageLevel",
    "ModelSpec",
    "MutationContract",
    "NamedTraceReceipt",
    "NextAction",
    "NonEmptyString",
    "ObjectEnvelope",
    "PackageRef",
    "PolicyAcceptanceRequirement",
    "PolicyAcknowledgement",
    "PrimaryUpliftResult",
    "ProgramRef",
    "ProtocolModel",
    "PublicContext",
    "PublicKeyRef",
    "PublicationPolicy",
    "PublicationStatus",
    "RawEpisodePolicy",
    "ResolvedClimb",
    "RevocationPolicy",
    "RunEvent",
    "RunPhase",
    "RunProgress",
    "RunRequest",
    "RunState",
    "RunStatus",
    "RuntimeSpec",
    "SamplingSpec",
    "ScoreStatus",
    "ScoringSpec",
    "SecretFinding",
    "SignatureEnvelope",
    "SkillArtifact",
    "SkillFile",
    "StateModel",
    "SubjectRuntimeReceipt",
    "SubmissionDraft",
    "TaskDelta",
    "TaskMembershipCommitment",
    "TaskSelection",
    "TasksetLock",
    "TasksetRef",
    "TasksetValidationReceipt",
    "UpliftDecision",
    "UpliftReport",
    "UpliftStatuses",
    "UpstreamValidationSummary",
    "UtcDateTime",
    "ValidationCheck",
    "ValidationEvidence",
    "ValidationEvidenceSummary",
    "ValidationEvidenceTask",
    "ValidationExecutionRecord",
    "ValidationMethod",
    "ValidationTaskOutcome",
    "check_climb_policy_consistency",
    "normalize_host_platform",
    "validation_display_id",
]
