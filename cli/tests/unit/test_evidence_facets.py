"""The v0.2 evidence contract. Plan `docs/plan/v0.2.md`, "Evidence contract".

Three rules are what these tests exist for, and everything else here supports
them.

An uplift may headline only when artifact integrity is verified and comparison
validity is valid. Invalid and indeterminate comparisons are publishable
failure evidence and are never ranked as uplift.

A provider-hosted rerun by the same participant is not an independent
reproduction, and a participant's own capture of a provider run reference does
not become provider verification however well the bundle carrying it is signed.

A digest whose bytes the bundle does not carry is never described as
recomputable from the bundle.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from techtree.models.evidence import (
    ArtifactIntegrity,
    ArtifactIntegrityStatus,
    ComparisonValidity,
    ComparisonValidityStatus,
    EvidenceArtifactRef,
    EvidenceFacets,
    ExecutionLocation,
    ExecutionLocationKind,
    ExecutionObservation,
    ModelIdentity,
    ModelPinStrength,
    ParticipantAttestation,
    ParticipantAttestationStatus,
    ProviderAttestation,
    ProviderAttestationStatus,
    ProviderRecord,
    ProviderRecordStatus,
    ProviderVerificationClaim,
    ReproductionKind,
    ReproductionRef,
    TraceCoverage,
    TraceCoverageKind,
    independent_reproductions,
    is_independent_reproduction,
    may_headline_uplift,
    provider_verification_claim,
)

CAMPAIGN = f"sha256:{'11' * 32}"
DECLARED = f"sha256:{'22' * 32}"
OBSERVED = f"sha256:{'33' * 32}"
PROOF = f"sha256:{'44' * 32}"
OTHER_PROOF = f"sha256:{'55' * 32}"
RECORD = f"sha256:{'66' * 32}"
ATTESTATION = f"sha256:{'77' * 32}"
PROFILE = f"sha256:{'88' * 32}"


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def comparison(**overrides: object) -> ComparisonValidity:
    """Build a comparison-validity facet, valid unless told otherwise."""
    fields: dict[str, object] = {
        "status": ComparisonValidityStatus.VALID,
        "campaign_digest": CAMPAIGN,
        "mutation_axis": "skill",
        "declared_difference_digest": DECLARED,
        "observed_difference_digest": DECLARED,
        "reason_codes": (),
    }
    fields.update(overrides)
    return ComparisonValidity(**fields)  # type: ignore[arg-type]


def absent_observation(**overrides: object) -> ExecutionObservation:
    """Build the observation a v0.2.0 local run produces."""
    fields: dict[str, object] = {
        "participant_attestation": ParticipantAttestation(
            status=ParticipantAttestationStatus.VERIFIED,
            key_fingerprint="key-1",
        ),
        "provider_record": ProviderRecord(
            status=ProviderRecordStatus.ABSENT,
            provider=None,
            provider_run_ref=None,
            record_digest=None,
        ),
        "provider_attestation": ProviderAttestation(
            status=ProviderAttestationStatus.ABSENT,
            attestation_digest=None,
        ),
    }
    fields.update(overrides)
    return ExecutionObservation(**fields)  # type: ignore[arg-type]


def facets(**overrides: object) -> EvidenceFacets:
    """Build a full facet set that may headline, unless told otherwise."""
    fields: dict[str, object] = {
        "artifact_integrity": ArtifactIntegrity(
            status=ArtifactIntegrityStatus.VERIFIED
        ),
        "comparison_validity": comparison(),
        "execution_location": ExecutionLocation(kind=ExecutionLocationKind.LOCAL),
        "execution_observation": absent_observation(),
        "trace_coverage": TraceCoverage(
            kind=TraceCoverageKind.NOT_REQUESTED,
            coverage_profile_digest=None,
            reasons=(),
        ),
        "model_identity": ModelIdentity(pin_strength=ModelPinStrength.ARTIFACT_DIGEST),
        "reproductions": (),
    }
    fields.update(overrides)
    return EvidenceFacets(**fields)  # type: ignore[arg-type]


def reproduction(**overrides: object) -> ReproductionRef:
    """Build one reproduction entry, independent and exact unless told otherwise."""
    fields: dict[str, object] = {
        "proof_digest": PROOF,
        "kind": ReproductionKind.INDEPENDENT_REPRODUCTION,
        "compatibility": "exact_configuration",
        "executor_fingerprint": "somebody-else",
    }
    fields.update(overrides)
    return ReproductionRef(**fields)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# The headline rule
# ---------------------------------------------------------------------------


def test_verified_integrity_and_a_valid_comparison_may_headline() -> None:
    assert may_headline_uplift(facets())


@pytest.mark.parametrize(
    "status",
    [ComparisonValidityStatus.INVALID, ComparisonValidityStatus.INDETERMINATE],
)
def test_an_unsound_comparison_never_headlines(
    status: ComparisonValidityStatus,
) -> None:
    """Failure evidence is publishable; it is never ranked as uplift."""
    unsound = facets(
        comparison_validity=comparison(
            status=status,
            observed_difference_digest=OBSERVED,
            reason_codes=("undeclared_configuration_difference",),
        )
    )

    assert not may_headline_uplift(unsound)


def test_invalid_artifact_integrity_never_headlines() -> None:
    broken = facets(
        artifact_integrity=ArtifactIntegrity(status=ArtifactIntegrityStatus.INVALID)
    )

    assert not may_headline_uplift(broken)


def test_both_facets_failing_never_headlines() -> None:
    both = facets(
        artifact_integrity=ArtifactIntegrity(status=ArtifactIntegrityStatus.INVALID),
        comparison_validity=comparison(
            status=ComparisonValidityStatus.INVALID,
            observed_difference_digest=OBSERVED,
            reason_codes=("undeclared_configuration_difference",),
        ),
    )

    assert not may_headline_uplift(both)


def test_a_failing_facet_set_is_still_a_valid_document() -> None:
    """Refusing to headline is a presentation rule, not a validation rule."""
    published_failure = facets(
        artifact_integrity=ArtifactIntegrity(status=ArtifactIntegrityStatus.INVALID),
    )

    assert isinstance(published_failure, EvidenceFacets)


# ---------------------------------------------------------------------------
# Comparison validity
# ---------------------------------------------------------------------------


def test_a_valid_comparison_observed_what_it_declared() -> None:
    with pytest.raises(PydanticValidationError, match="exactly the difference"):
        comparison(observed_difference_digest=OBSERVED)


def test_a_valid_comparison_carries_no_reason_codes() -> None:
    with pytest.raises(PydanticValidationError, match="no reason codes"):
        comparison(reason_codes=("undeclared_configuration_difference",))


@pytest.mark.parametrize(
    "status",
    [ComparisonValidityStatus.INVALID, ComparisonValidityStatus.INDETERMINATE],
)
def test_an_unsound_comparison_must_say_why(
    status: ComparisonValidityStatus,
) -> None:
    with pytest.raises(PydanticValidationError, match="must say why"):
        comparison(status=status, observed_difference_digest=OBSERVED)


def test_an_indeterminate_comparison_may_still_agree_on_both_digests() -> None:
    """Indeterminate says the evidence settles nothing, not that it disagreed."""
    undecided = comparison(
        status=ComparisonValidityStatus.INDETERMINATE,
        reason_codes=("observed_difference_not_established",),
    )

    assert undecided.status is ComparisonValidityStatus.INDETERMINATE


# ---------------------------------------------------------------------------
# Cumulative execution observation
# ---------------------------------------------------------------------------


def test_a_local_run_observes_only_its_own_participant() -> None:
    assert (
        provider_verification_claim(absent_observation())
        is ProviderVerificationClaim.NONE
    )


def test_a_captured_run_reference_is_not_provider_verification() -> None:
    """Plan: rendered as "Prime run reference captured", never "Prime verified"."""
    captured = absent_observation(
        provider_record=ProviderRecord(
            status=ProviderRecordStatus.PARTICIPANT_CAPTURED,
            provider="prime",
            provider_run_ref="run-1",
            record_digest=None,
        )
    )

    assert (
        provider_verification_claim(captured)
        is ProviderVerificationClaim.RUN_REFERENCE_CAPTURED
    )


def test_an_independently_retrieved_record_establishes_provider_evidence() -> None:
    retrieved = absent_observation(
        provider_record=ProviderRecord(
            status=ProviderRecordStatus.PUBLICATION_SERVICE_RETRIEVED,
            provider="prime",
            provider_run_ref="run-1",
            record_digest=RECORD,
        )
    )

    assert (
        provider_verification_claim(retrieved)
        is ProviderVerificationClaim.INDEPENDENTLY_ESTABLISHED
    )


def test_a_verified_provider_attestation_establishes_provider_evidence() -> None:
    attested = absent_observation(
        provider_attestation=ProviderAttestation(
            status=ProviderAttestationStatus.VERIFIED,
            attestation_digest=ATTESTATION,
        )
    )

    assert (
        provider_verification_claim(attested)
        is ProviderVerificationClaim.INDEPENDENTLY_ESTABLISHED
    )


def test_an_invalid_provider_attestation_establishes_nothing() -> None:
    rejected = absent_observation(
        provider_attestation=ProviderAttestation(
            status=ProviderAttestationStatus.INVALID,
            attestation_digest=ATTESTATION,
        )
    )

    assert provider_verification_claim(rejected) is ProviderVerificationClaim.NONE


def test_an_absent_provider_record_carries_no_provider() -> None:
    with pytest.raises(PydanticValidationError, match="absent provider record"):
        ProviderRecord(
            status=ProviderRecordStatus.ABSENT,
            provider="prime",
            provider_run_ref=None,
            record_digest=None,
        )


def test_a_present_provider_record_names_the_run_it_refers_to() -> None:
    with pytest.raises(PydanticValidationError, match="names the provider"):
        ProviderRecord(
            status=ProviderRecordStatus.PARTICIPANT_CAPTURED,
            provider="prime",
            provider_run_ref=None,
            record_digest=None,
        )


def test_a_retrieved_provider_record_digests_what_was_retrieved() -> None:
    with pytest.raises(PydanticValidationError, match="digests the record"):
        ProviderRecord(
            status=ProviderRecordStatus.PUBLICATION_SERVICE_RETRIEVED,
            provider="prime",
            provider_run_ref="run-1",
            record_digest=None,
        )


def test_an_absent_provider_attestation_digests_nothing() -> None:
    with pytest.raises(PydanticValidationError, match="digests the assertion"):
        ProviderAttestation(
            status=ProviderAttestationStatus.ABSENT,
            attestation_digest=ATTESTATION,
        )


def test_a_participant_attestation_names_the_key_that_made_it() -> None:
    with pytest.raises(PydanticValidationError, match="names the key"):
        ParticipantAttestation(
            status=ParticipantAttestationStatus.VERIFIED,
            key_fingerprint=None,
        )


def test_a_locally_executed_run_has_no_provider_record() -> None:
    with pytest.raises(PydanticValidationError, match="no provider record"):
        facets(
            execution_observation=absent_observation(
                provider_record=ProviderRecord(
                    status=ProviderRecordStatus.PARTICIPANT_CAPTURED,
                    provider="prime",
                    provider_run_ref="run-1",
                    record_digest=None,
                )
            )
        )


def test_a_locally_executed_run_has_no_provider_attestation() -> None:
    with pytest.raises(PydanticValidationError, match="no provider to attest"):
        facets(
            execution_observation=absent_observation(
                provider_attestation=ProviderAttestation(
                    status=ProviderAttestationStatus.VERIFIED,
                    attestation_digest=ATTESTATION,
                )
            )
        )


# ---------------------------------------------------------------------------
# Trace coverage
# ---------------------------------------------------------------------------


def test_coverage_cannot_be_complete_for_an_unnamed_profile() -> None:
    with pytest.raises(PydanticValidationError, match="does not name"):
        TraceCoverage(
            kind=TraceCoverageKind.COMPLETE_FOR_PROFILE,
            coverage_profile_digest=None,
            reasons=(),
        )


def test_coverage_that_was_never_requested_names_no_profile() -> None:
    with pytest.raises(PydanticValidationError, match="never requested"):
        TraceCoverage(
            kind=TraceCoverageKind.NOT_REQUESTED,
            coverage_profile_digest=PROFILE,
            reasons=(),
        )


@pytest.mark.parametrize(
    "kind", [TraceCoverageKind.UNAVAILABLE, TraceCoverageKind.INCOMPLETE]
)
def test_short_coverage_says_what_is_missing(kind: TraceCoverageKind) -> None:
    with pytest.raises(PydanticValidationError, match="must say what is missing"):
        TraceCoverage(kind=kind, coverage_profile_digest=None, reasons=())


def test_complete_coverage_names_its_profile() -> None:
    complete = TraceCoverage(
        kind=TraceCoverageKind.COMPLETE_FOR_PROFILE,
        coverage_profile_digest=PROFILE,
        reasons=(),
    )

    assert complete.coverage_profile_digest == PROFILE


# ---------------------------------------------------------------------------
# Reproductions
# ---------------------------------------------------------------------------


def test_a_provider_hosted_rerun_is_never_an_independent_reproduction() -> None:
    """Plan boundary: a provider-hosted run is not called an independent
    reproduction."""
    rerun = reproduction(kind=ReproductionKind.SAME_PARTICIPANT_PROVIDER_RERUN)

    assert not is_independent_reproduction(rerun)


def test_an_incompatible_rerun_reproduced_something_else() -> None:
    drifted = reproduction(compatibility="incompatible")

    assert not is_independent_reproduction(drifted)


@pytest.mark.parametrize(
    "compatibility", ["exact_configuration", "compatible_with_declared_drift"]
)
def test_a_compatible_independent_rerun_reproduces_the_result(
    compatibility: str,
) -> None:
    assert is_independent_reproduction(reproduction(compatibility=compatibility))


def test_only_independent_entries_are_counted_as_reproductions() -> None:
    mixed = facets(
        reproductions=(
            reproduction(),
            reproduction(
                proof_digest=OTHER_PROOF,
                kind=ReproductionKind.SAME_PARTICIPANT_PROVIDER_RERUN,
            ),
        )
    )

    assert [entry.proof_digest for entry in independent_reproductions(mixed)] == [PROOF]


def test_one_proof_reproduces_this_one_once() -> None:
    with pytest.raises(PydanticValidationError, match="reproduces this one once"):
        facets(reproductions=(reproduction(), reproduction()))


def test_a_local_run_may_still_carry_a_provider_hosted_rerun() -> None:
    """The location facet describes this execution, not somebody's re-run."""
    reproduced = facets(
        reproductions=(
            reproduction(kind=ReproductionKind.SAME_PARTICIPANT_PROVIDER_RERUN),
        )
    )

    assert independent_reproductions(reproduced) == ()


# ---------------------------------------------------------------------------
# Evidence availability and proof closure
# ---------------------------------------------------------------------------


def reference(**overrides: object) -> EvidenceArtifactRef:
    """Build an availability statement for one digest."""
    fields: dict[str, object] = {
        "digest": PROOF,
        "media_type": "application/json",
        "size_bytes": 128,
        "availability": "embedded_in_proof",
        "verification": "recomputable_from_bundle",
    }
    fields.update(overrides)
    return EvidenceArtifactRef(**fields)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "availability",
    ["private_local_archive", "provider_retrievable", "not_retained"],
)
def test_a_missing_blob_is_never_recomputable_from_the_bundle(
    availability: str,
) -> None:
    with pytest.raises(PydanticValidationError, match="embeds its bytes"):
        reference(availability=availability)


@pytest.mark.parametrize(
    "availability",
    ["private_local_archive", "provider_retrievable", "not_retained"],
)
@pytest.mark.parametrize(
    "verification", ["verified_during_run_and_receipted", "commitment_only"]
)
def test_a_missing_blob_may_carry_a_receipt_or_a_commitment(
    availability: str, verification: str
) -> None:
    """A public verifier may check a commitment without claiming it rechecked
    the private bytes."""
    stated = reference(availability=availability, verification=verification)

    assert stated.availability == availability
    assert stated.verification == verification


def test_an_embedded_blob_is_recomputable() -> None:
    assert reference().verification == "recomputable_from_bundle"


def test_a_zero_byte_artifact_is_not_representable() -> None:
    """Matching ArtifactRef: there is no empty artifact worth proving."""
    with pytest.raises(PydanticValidationError):
        reference(size_bytes=0)


def test_a_blank_media_type_names_no_format() -> None:
    with pytest.raises(PydanticValidationError):
        reference(media_type="   ")
