"""The four-plane execution plan a Campaign binds. Plan v0.2 section 4.

Every run resolves four independent contracts, and the plan is the single
object that states all four together:

1. Evaluation engine — Verifiers supplies task and reward truth.
2. Execution backend — who orchestrates the comparison.
3. Subject backend — how the measured agent is integrated.
4. Evidence backend — which evidence the run must produce.

No plane implies another. Provider-hosted execution does not imply a Fabric
subject, a Fabric subject does not imply provider-hosted execution, and
requested trace coverage does not imply provider attestation. That
independence is expressed here by the absence of cross-plane validators: each
plane validates only its own internal consistency, and nothing in this module
derives one plane from another. Two planes that constrained each other would
be one plane wearing two names.

A plan is immutable and content-addressed. A Campaign carries its digest, not
the plan itself, so selecting a different execution, subject, or evidence
backend produces a different plan digest, which produces a different Campaign
digest. That is the whole mechanism by which a backend change cannot silently
reinterpret an existing Campaign.

The hosted vocabulary is present and unimplemented on purpose. ``prime_hosted``
and its provider are in the enums so the protocol is cut once; v0.2.0 resolves
``local`` only, and :data:`SUPPORTED_EXECUTION_BACKEND_KINDS` is what services
enforce that with. The narrower rule lives at the point of use rather than in
the model, because a document that merely names a future backend must still be
parseable — the same division :mod:`techtree.models.evaluation_backend` makes.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal, Self

from pydantic import model_validator

from techtree.models.base import Digest, NonEmptyString, ProtocolModel

__all__ = [
    "SUPPORTED_EXECUTION_BACKEND_KINDS",
    "SUPPORTED_SUBJECT_BACKEND_KINDS",
    "EvaluationEngineRef",
    "EvidenceBackendSpec",
    "ExecutionBackendKind",
    "ExecutionBackendSpec",
    "ExecutionProvider",
    "ResolvedExecutionPlan",
    "SubjectBackendKind",
    "SubjectBackendSpec",
]

#: An upstream engine is pinned to a commit, never to a branch or a tag, for
#: the same reason a subject image is pinned to a digest: a moving name cannot
#: say what ran.
_SOURCE_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


# ---------------------------------------------------------------------------
# Plane 1: the evaluation engine
# ---------------------------------------------------------------------------


class EvaluationEngineRef(ProtocolModel):
    """Which Verifiers build supplies task identity, task results, and reward.

    Verifiers stays authoritative for all three, so the plan names the exact
    build rather than a range. The wheel digest is what an offline reader can
    check; the version and the commit are what a person can read.
    """

    kind: Literal["verifiers"]
    api_generation: Literal["v1"]
    package_version: NonEmptyString
    source_commit: NonEmptyString
    wheel_digest: Digest

    @model_validator(mode="after")
    def _check_the_engine_is_pinned_to_content(self) -> Self:
        """Reject a commit that is not a full lowercase Git object name."""
        if _SOURCE_COMMIT_RE.fullmatch(self.source_commit) is None:
            raise ValueError(
                "source_commit must be a full 40-character lowercase commit "
                f"hash, never a branch or a tag; got {self.source_commit!r}"
            )
        return self


# ---------------------------------------------------------------------------
# Plane 2: the execution backend
# ---------------------------------------------------------------------------


class ExecutionBackendKind(StrEnum):
    """Where the comparison is orchestrated.

    These are the two values the proof's ``execution_location`` facet carries.
    ``prime_hosted`` is protocol vocabulary in v0.2.0 and behavior in v0.2.x.
    """

    LOCAL = "local"
    PRIME_HOSTED = "prime_hosted"


class ExecutionProvider(StrEnum):
    """The hosted provider, for the kinds that have one."""

    PRIME = "prime"


#: The only execution kind v0.2.0 services resolve. The schema is wider than
#: this on purpose; the runtime surface is not.
SUPPORTED_EXECUTION_BACKEND_KINDS: frozenset[ExecutionBackendKind] = frozenset(
    {ExecutionBackendKind.LOCAL}
)


class ExecutionBackendSpec(ProtocolModel):
    """Who runs the comparison, and on whose infrastructure."""

    kind: ExecutionBackendKind
    provider: ExecutionProvider | None
    provider_environment_coordinate: NonEmptyString | None

    @model_validator(mode="after")
    def _check_the_kind_agrees_with_its_provider(self) -> Self:
        """Reject a provider a kind cannot have, and a hosted kind without one."""
        if self.kind is ExecutionBackendKind.LOCAL:
            if self.provider is not None:
                raise ValueError(
                    "local execution runs on the participant's own machine and "
                    "has no provider"
                )
            if self.provider_environment_coordinate is not None:
                raise ValueError(
                    "local execution has no provider environment coordinate"
                )
            return self

        if self.provider is not ExecutionProvider.PRIME:
            raise ValueError("prime_hosted execution must name the prime provider")
        if self.provider_environment_coordinate is None:
            raise ValueError(
                "prime_hosted execution must name the public environment "
                "coordinate it runs, so the plan says what was selected"
            )
        return self


# ---------------------------------------------------------------------------
# Plane 3: the subject backend
# ---------------------------------------------------------------------------


class SubjectBackendKind(StrEnum):
    """How the measured agent is reached.

    ``direct`` is Techtree's own integration with the harness. ``fabric``
    reaches it through a Fabric adapter. ``verifiers_native`` lets the
    evaluation engine's own harness drive the subject.
    """

    DIRECT = "direct"
    FABRIC = "fabric"
    VERIFIERS_NATIVE = "verifiers_native"


#: The subject kinds that are implemented today. Fabric arrives inside v0.2.0
#: with WP2 and the Verifiers-native harness later still; both are protocol
#: vocabulary now and neither is a release boundary.
SUPPORTED_SUBJECT_BACKEND_KINDS: frozenset[SubjectBackendKind] = frozenset(
    {SubjectBackendKind.DIRECT}
)


class SubjectBackendSpec(ProtocolModel):
    """The harness that is measured, and the adapter that reaches it.

    The harness is named on every kind, because the harness is what is being
    measured and it does not stop mattering when an adapter sits in front of
    it. The adapter coordinates exist only on the kind that has an adapter.
    """

    kind: SubjectBackendKind
    harness_id: NonEmptyString
    harness_version: NonEmptyString
    adapter_id: NonEmptyString | None
    adapter_version: NonEmptyString | None
    adapter_contract_version: NonEmptyString | None

    @model_validator(mode="after")
    def _check_adapter_coordinates_match_the_kind(self) -> Self:
        """Require the adapter exactly where the kind has one."""
        coordinates = {
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "adapter_contract_version": self.adapter_contract_version,
        }
        if self.kind is SubjectBackendKind.FABRIC:
            missing = sorted(
                name for name, value in coordinates.items() if value is None
            )
            if missing:
                raise ValueError(
                    "a fabric subject backend is identified by its adapter; "
                    f"{', '.join(missing)} must be named"
                )
            return self

        named = sorted(name for name, value in coordinates.items() if value is not None)
        if named:
            raise ValueError(
                f"a {self.kind.value} subject backend has no adapter; "
                f"{', '.join(named)} must be null"
            )
        return self


# ---------------------------------------------------------------------------
# Plane 4: the evidence backend
# ---------------------------------------------------------------------------


class EvidenceBackendSpec(ProtocolModel):
    """Which evidence the run must produce.

    Native evidence is never optional: it is the receipted record the score
    rests on. Trace coverage is the supplementary observation a Campaign may
    ask for, and it is requested against one versioned coverage profile, whose
    digest is the same value the proof's ``trace_coverage`` facet reports
    against. Naming the profile rather than the observer is deliberate — the
    plan states what coverage is owed, and the profile states how it is
    obtained.

    Requesting coverage is a request, not a promise. What the run actually
    achieved is an evidence outcome and is never written back into the plan;
    a plan that recorded an outcome would change after the Campaign froze.
    """

    native_evidence: Literal["required"]
    trace_coverage: Literal["not_requested", "requested"]
    coverage_profile_digest: Digest | None

    @model_validator(mode="after")
    def _check_coverage_names_a_profile(self) -> Self:
        """Require a profile exactly when coverage is requested."""
        if self.trace_coverage == "requested":
            if self.coverage_profile_digest is None:
                raise ValueError(
                    "requested trace coverage must name the coverage profile it "
                    "is measured against; coverage with no profile is unfalsifiable"
                )
            return self

        if self.coverage_profile_digest is not None:
            raise ValueError(
                "a Campaign that did not request trace coverage must not name a "
                "coverage profile"
            )
        return self


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------


class ResolvedExecutionPlan(ProtocolModel):
    """All four planes, resolved, immutable, and digestible as one object."""

    schema_version: Literal["techtree.execution-plan.v1"]
    kind: Literal["ResolvedExecutionPlan"]
    evaluation: EvaluationEngineRef
    execution: ExecutionBackendSpec
    subject: SubjectBackendSpec
    evidence: EvidenceBackendSpec
