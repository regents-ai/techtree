"""The v0.2 evidence contract. Plan `docs/plan/v0.2.md`, "Evidence contract".

A proof answers several independent questions, and the plan's central rule is
that it must answer them *separately*. Whether the stored bytes still hash to
what the proof says is one question. Whether the two arms differed only where
the Campaign declared they could is a second. Where the work ran is a third,
who observed it a fourth, how much of its trace survived a fifth, how tightly
the model was pinned a sixth, and who has re-run it a seventh. Collapsing any
of them into a single "verified" word would let a strong answer to one question
stand in for a missing answer to another, which is the exact failure the facets
exist to prevent.

Three things in this module are load-bearing.

*The facets are orthogonal, and the only coupling is a presentation rule.*
:func:`may_headline_uplift` is the plan's headline rule and it lives here as a
pure function rather than as a validator, because an invalid comparison is a
perfectly valid document — it is failure evidence, and failure evidence is
publishable. What it may never be is ranked as uplift.

*Observation is cumulative.* :class:`ExecutionObservation` carries three
independent observations of the same execution, and
:func:`provider_verification_claim` reduces them to the strongest sentence the
evidence supports. A Prime run reference copied into a participant-signed
bundle establishes that a reference was captured. It does not establish that
Prime verified anything, and no amount of participant signing turns the first
into the second.

*A missing blob is never silently verified.* :class:`EvidenceArtifactRef` says
both where a digest's bytes are and what an offline reader can prove about
them, and it refuses to claim recomputability for bytes the bundle does not
carry. Its two scalars are tightened past the plan's ``str`` and ``int``: the
media type must contain a visible character, because a blank one names no
format, and the size must be positive, matching
:class:`~techtree.models.base.ArtifactRef` — there is no zero-byte artifact
worth committing a proof to, and admitting one would make "the bytes are
there" unfalsifiable.

The hosted values here — ``prime_hosted``, the whole provider record and
provider attestation blocks, and ``same_participant_provider_rerun`` — are in
the protocol so that WP1 cuts it once. v0.2.0 emits ``local``, ``absent``, and
an empty reproduction list; nothing populates the rest until WP4 in v0.2.x.

This module is self-contained by design. It names an execution plan and a
Campaign by digest and it spells compatibility outcomes as the literal values
the plan gives them, so it imports neither the execution-plan model nor the
configuration-compatibility model.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from techtree.models.base import Digest, NonEmptyString, ProtocolModel

__all__ = [
    "ArtifactIntegrity",
    "ArtifactIntegrityStatus",
    "ComparisonValidity",
    "ComparisonValidityStatus",
    "EvidenceArtifactRef",
    "EvidenceFacets",
    "ExecutionLocation",
    "ExecutionLocationKind",
    "ExecutionObservation",
    "ModelIdentity",
    "ModelPinStrength",
    "ParticipantAttestation",
    "ParticipantAttestationStatus",
    "ProviderAttestation",
    "ProviderAttestationStatus",
    "ProviderRecord",
    "ProviderRecordStatus",
    "ProviderVerificationClaim",
    "ReproductionKind",
    "ReproductionRef",
    "TraceCoverage",
    "TraceCoverageKind",
    "independent_reproductions",
    "is_independent_reproduction",
    "may_headline_uplift",
    "provider_verification_claim",
]


# ---------------------------------------------------------------------------
# Artifact integrity
# ---------------------------------------------------------------------------


class ArtifactIntegrityStatus(StrEnum):
    """Whether every artifact still hashes to the digest the proof recorded."""

    VERIFIED = "verified"
    INVALID = "invalid"


class ArtifactIntegrity(ProtocolModel):
    """The integrity facet: do these bytes still say what they said?"""

    status: ArtifactIntegrityStatus


# ---------------------------------------------------------------------------
# Comparison validity
# ---------------------------------------------------------------------------


class ComparisonValidityStatus(StrEnum):
    """Whether the two arms differed only where the Campaign declared.

    ``indeterminate`` is not a softer ``invalid``. It says the evidence does
    not establish either answer, which is a different thing to tell a reader
    than "the comparison broke its own contract".
    """

    VALID = "valid"
    INVALID = "invalid"
    INDETERMINATE = "indeterminate"


class ComparisonValidity(ProtocolModel):
    """The comparison facet, bound to the Campaign it is a comparison of.

    Both difference digests are carried because either one alone proves
    nothing. The declared digest is what the Campaign permitted; the observed
    digest is what the two arms actually differed by. A comparison is valid
    when they are the same digest, and when they are not, the reason codes say
    what went wrong rather than leaving a reader to diff two hashes.
    """

    status: ComparisonValidityStatus
    campaign_digest: Digest
    mutation_axis: Literal["skill"]
    declared_difference_digest: Digest
    observed_difference_digest: Digest
    reason_codes: tuple[NonEmptyString, ...]

    @model_validator(mode="after")
    def _check_the_status_and_its_evidence_agree(self) -> Self:
        """Reject a verdict its own fields contradict."""
        agree = self.declared_difference_digest == self.observed_difference_digest
        valid = self.status is ComparisonValidityStatus.VALID
        if valid and not agree:
            raise ValueError(
                "a valid comparison observed exactly the difference it "
                "declared; carrying two digests and calling them valid leaves "
                "a reader unable to tell which one is true"
            )
        if valid and self.reason_codes:
            raise ValueError("a valid comparison has no reason codes")
        if not valid and not self.reason_codes:
            raise ValueError(
                f"a {self.status.value} comparison must say why it is "
                f"{self.status.value}"
            )
        return self


# ---------------------------------------------------------------------------
# Execution location
# ---------------------------------------------------------------------------


class ExecutionLocationKind(StrEnum):
    """Where the work ran. v0.2.0 emits ``local`` and nothing else."""

    LOCAL = "local"
    PRIME_HOSTED = "prime_hosted"


class ExecutionLocation(ProtocolModel):
    """The location facet."""

    kind: ExecutionLocationKind


# ---------------------------------------------------------------------------
# Cumulative execution observation
# ---------------------------------------------------------------------------


class ParticipantAttestationStatus(StrEnum):
    """Whether the participant's own signature over the run checks out."""

    VERIFIED = "verified"
    INVALID = "invalid"
    ABSENT = "absent"


class ParticipantAttestation(ProtocolModel):
    """What the participant asserted, and which key asserted it."""

    status: ParticipantAttestationStatus
    key_fingerprint: NonEmptyString | None

    @model_validator(mode="after")
    def _check_an_attestation_names_its_key(self) -> Self:
        """An assertion, sound or not, was made by a key; an absent one was not."""
        attested = self.status is not ParticipantAttestationStatus.ABSENT
        if attested != (self.key_fingerprint is not None):
            raise ValueError(
                "a participant attestation names the key that made it, and an "
                "absent attestation names none"
            )
        return self


class ProviderRecordStatus(StrEnum):
    """How a provider's own record of the run reached this proof.

    ``participant_captured`` means a run reference was copied into the
    participant-signed bundle. It is rendered as "Prime run reference
    captured", never "Prime verified this run".
    """

    ABSENT = "absent"
    PARTICIPANT_CAPTURED = "participant_captured"
    PUBLICATION_SERVICE_RETRIEVED = "publication_service_retrieved"


class ProviderRecord(ProtocolModel):
    """The provider's record of the run, and how it was come by."""

    status: ProviderRecordStatus
    provider: Literal["prime"] | None
    provider_run_ref: NonEmptyString | None
    record_digest: Digest | None

    @model_validator(mode="after")
    def _check_the_record_carries_what_its_status_claims(self) -> Self:
        """Reject a record that names a provider it says it does not have."""
        present = self.status is not ProviderRecordStatus.ABSENT
        if not present:
            if (
                self.provider is not None
                or self.provider_run_ref is not None
                or self.record_digest is not None
            ):
                raise ValueError(
                    "an absent provider record carries no provider, no run "
                    "reference, and no record digest"
                )
            return self
        if self.provider is None or self.provider_run_ref is None:
            raise ValueError(
                "a provider record names the provider and the run it refers to"
            )
        retrieved = self.status is ProviderRecordStatus.PUBLICATION_SERVICE_RETRIEVED
        if retrieved and self.record_digest is None:
            raise ValueError(
                "a retrieved provider record digests the record that was "
                "retrieved; without it nothing was independently established"
            )
        return self


class ProviderAttestationStatus(StrEnum):
    """Whether the provider made a verifiable assertion about the run."""

    ABSENT = "absent"
    VERIFIED = "verified"
    INVALID = "invalid"


class ProviderAttestation(ProtocolModel):
    """A provider-signed assertion, absent until a real one exists."""

    status: ProviderAttestationStatus
    attestation_digest: Digest | None

    @model_validator(mode="after")
    def _check_an_attestation_names_what_was_checked(self) -> Self:
        """A verdict on an assertion implies an assertion to have a verdict on."""
        asserted = self.status is not ProviderAttestationStatus.ABSENT
        if asserted != (self.attestation_digest is not None):
            raise ValueError(
                "a provider attestation digests the assertion it judges, and "
                "an absent attestation digests none"
            )
        return self


class ExecutionObservation(ProtocolModel):
    """Every independent observation of one execution, accumulated.

    The three blocks are not ranked against each other by the model, because
    they are not alternatives: a run can be participant-attested and
    provider-recorded and provider-attested at once, and each says something
    the other two do not. :func:`provider_verification_claim` is where the
    accumulation is reduced to a sentence.
    """

    participant_attestation: ParticipantAttestation
    provider_record: ProviderRecord
    provider_attestation: ProviderAttestation


class ProviderVerificationClaim(StrEnum):
    """The strongest sentence a proof's provider evidence supports."""

    #: Nothing from the provider reached this proof.
    NONE = "none"
    #: A run reference was captured by the participant. Rendered as
    #: "Prime run reference captured", never as provider verification.
    RUN_REFERENCE_CAPTURED = "run_reference_captured"
    #: An independently retrieved record or a verifiable provider assertion.
    INDEPENDENTLY_ESTABLISHED = "independently_established"


def provider_verification_claim(
    observation: ExecutionObservation,
) -> ProviderVerificationClaim:
    """Reduce cumulative observation to what may honestly be said of it.

    Independent establishment requires either a record the publication service
    retrieved itself or a provider attestation that verified. A participant's
    own capture of a run reference never reaches it, however well signed the
    bundle carrying it is.
    """
    record = observation.provider_record.status
    attestation = observation.provider_attestation.status
    if (
        record is ProviderRecordStatus.PUBLICATION_SERVICE_RETRIEVED
        or attestation is ProviderAttestationStatus.VERIFIED
    ):
        return ProviderVerificationClaim.INDEPENDENTLY_ESTABLISHED
    if record is ProviderRecordStatus.PARTICIPANT_CAPTURED:
        return ProviderVerificationClaim.RUN_REFERENCE_CAPTURED
    return ProviderVerificationClaim.NONE


# ---------------------------------------------------------------------------
# Trace coverage
# ---------------------------------------------------------------------------


class TraceCoverageKind(StrEnum):
    """How much of the requested trace evidence exists."""

    #: The Campaign selected native-only evidence.
    NOT_REQUESTED = "not_requested"
    #: Trace evidence was requested and produced nothing usable.
    UNAVAILABLE = "unavailable"
    #: Some of the requested coverage exists.
    INCOMPLETE = "incomplete"
    #: Everything the named coverage profile requires exists.
    COMPLETE_FOR_PROFILE = "complete_for_profile"


class TraceCoverage(ProtocolModel):
    """The trace facet, measured against a named profile or not at all."""

    kind: TraceCoverageKind
    coverage_profile_digest: Digest | None
    reasons: tuple[NonEmptyString, ...]

    @model_validator(mode="after")
    def _check_coverage_names_its_profile_and_its_shortfall(self) -> Self:
        """Completeness needs a profile, and a shortfall needs a reason."""
        if (
            self.kind is TraceCoverageKind.COMPLETE_FOR_PROFILE
            and self.coverage_profile_digest is None
        ):
            raise ValueError(
                "coverage cannot be complete for a profile it does not name"
            )
        if (
            self.kind is TraceCoverageKind.NOT_REQUESTED
            and self.coverage_profile_digest is not None
        ):
            raise ValueError(
                "coverage that was never requested was measured against no profile"
            )
        short = self.kind in {
            TraceCoverageKind.UNAVAILABLE,
            TraceCoverageKind.INCOMPLETE,
        }
        if short and not self.reasons:
            raise ValueError(f"{self.kind.value} coverage must say what is missing")
        return self


# ---------------------------------------------------------------------------
# Model identity
# ---------------------------------------------------------------------------


class ModelPinStrength(StrEnum):
    """How tightly the subject model was pinned.

    Ordered by what it lets a reader conclude, weakest first: an alias can move
    under a Campaign, a provider revision cannot but is still the provider's
    word for it, and an artifact digest names bytes.
    """

    MUTABLE_ALIAS = "mutable_alias"
    PROVIDER_REVISION = "provider_revision"
    ARTIFACT_DIGEST = "artifact_digest"


class ModelIdentity(ProtocolModel):
    """The model-identity facet."""

    pin_strength: ModelPinStrength


# ---------------------------------------------------------------------------
# Reproductions
# ---------------------------------------------------------------------------


class ReproductionKind(StrEnum):
    """What kind of re-run one entry is.

    A same-participant run on the provider is a provider-hosted rerun. It is
    never an independent reproduction, and there is no status that would let it
    be described as one.
    """

    SAME_PARTICIPANT_PROVIDER_RERUN = "same_participant_provider_rerun"
    INDEPENDENT_REPRODUCTION = "independent_reproduction"


class ReproductionRef(ProtocolModel):
    """One proof that re-ran this one, and under what configuration.

    ``compatibility`` carries the plan's literal compatibility outcomes rather
    than importing the comparison model, so a proof can be read without the
    policy that produced the verdict.
    """

    proof_digest: Digest
    kind: ReproductionKind
    compatibility: Literal[
        "exact_configuration",
        "compatible_with_declared_drift",
        "incompatible",
    ]
    executor_fingerprint: NonEmptyString


def is_independent_reproduction(entry: ReproductionRef) -> bool:
    """Return whether one entry independently reproduced the result.

    Two things have to hold. The re-run was somebody else's, which rules out a
    provider-hosted rerun by the same participant. And it ran a configuration
    the compatibility policy admits, because a run under an undeclared
    configuration difference reproduced something, but not this.
    """
    return (
        entry.kind is ReproductionKind.INDEPENDENT_REPRODUCTION
        and entry.compatibility != "incompatible"
    )


# ---------------------------------------------------------------------------
# The facets together
# ---------------------------------------------------------------------------


class EvidenceFacets(ProtocolModel):
    """Every evidence facet of one proof."""

    artifact_integrity: ArtifactIntegrity
    comparison_validity: ComparisonValidity
    execution_location: ExecutionLocation
    execution_observation: ExecutionObservation
    trace_coverage: TraceCoverage
    model_identity: ModelIdentity
    reproductions: tuple[ReproductionRef, ...]

    @model_validator(mode="after")
    def _check_the_facets_do_not_contradict_each_other(self) -> Self:
        """Reject the two combinations that cannot both be true.

        Facets are orthogonal, so there is very little here on purpose. A
        locally executed run has no provider to have recorded or attested it,
        and one proof cannot be reproduced twice by the same proof.
        """
        if self.execution_location.kind is ExecutionLocationKind.LOCAL:
            observation = self.execution_observation
            if observation.provider_record.status is not ProviderRecordStatus.ABSENT:
                raise ValueError(
                    "a locally executed run has no provider record to carry"
                )
            if (
                observation.provider_attestation.status
                is not ProviderAttestationStatus.ABSENT
            ):
                raise ValueError("a locally executed run has no provider to attest it")
        digests = [entry.proof_digest for entry in self.reproductions]
        if len(set(digests)) != len(digests):
            raise ValueError(
                "one proof reproduces this one once; a repeated entry would "
                "count the same reproduction twice"
            )
        return self


def may_headline_uplift(facets: EvidenceFacets) -> bool:
    """Return whether this evidence may be presented and ranked as uplift.

    The plan's rule, and the whole of it: artifact integrity verified and
    comparison validity valid. Invalid and indeterminate comparisons may be
    published — they are evidence of a failure, and suppressing them would make
    the record dishonest in the other direction — but they are never presented
    or ranked as uplift.
    """
    return (
        facets.artifact_integrity.status is ArtifactIntegrityStatus.VERIFIED
        and facets.comparison_validity.status is ComparisonValidityStatus.VALID
    )


def independent_reproductions(facets: EvidenceFacets) -> tuple[ReproductionRef, ...]:
    """Return only the entries that independently reproduced the result."""
    return tuple(
        entry for entry in facets.reproductions if is_independent_reproduction(entry)
    )


# ---------------------------------------------------------------------------
# Evidence availability and proof closure
# ---------------------------------------------------------------------------


class EvidenceArtifactRef(ProtocolModel):
    """Where a digest's bytes are, and what an offline verifier can prove.

    Availability and verification are separate because they answer separate
    questions. A blob can be retrievable from a provider and still have been
    checked only by the participant during the run; a blob can be gone and
    still have a signed commitment a public verifier can check without ever
    claiming it rechecked the bytes.
    """

    digest: Digest
    media_type: NonEmptyString
    size_bytes: int = Field(gt=0)
    availability: Literal[
        "embedded_in_proof",
        "private_local_archive",
        "provider_retrievable",
        "not_retained",
    ]
    verification: Literal[
        "recomputable_from_bundle",
        "verified_during_run_and_receipted",
        "commitment_only",
    ]

    @model_validator(mode="after")
    def _check_a_missing_blob_is_not_treated_as_verified(self) -> Self:
        """Only bytes the bundle carries can be recomputed from the bundle."""
        if (
            self.verification == "recomputable_from_bundle"
            and self.availability != "embedded_in_proof"
        ):
            raise ValueError(
                "a digest is recomputable from the bundle only when the bundle "
                f"embeds its bytes; these are {self.availability}"
            )
        return self
