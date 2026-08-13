"""The evaluation backend and the attestation it may claim. Spec 11.3, 27.2.

Every test here is about one thing: a self-reported result must not be able to
dress itself up as an attested one, and an attested one must name the record
that backs it.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from techtree.constants import EVALUATION_BACKEND_SCHEMA_VERSION
from techtree.models.evaluation_backend import (
    SUPPORTED_EVALUATION_BACKEND_KINDS,
    AttestationKind,
    EvaluationBackendKind,
    EvaluationBackendSpec,
)


def backend(**overrides: object) -> EvaluationBackendSpec:
    """Build a backend spec, defaulting to the only combination v0.1 permits."""
    fields: dict[str, object] = {
        "schema_version": EVALUATION_BACKEND_SCHEMA_VERSION,
        "kind": EvaluationBackendKind.LOCAL_TECHTREE,
        "attestation": AttestationKind.PARTICIPANT,
    }
    fields.update(overrides)
    return EvaluationBackendSpec(**fields)  # type: ignore[arg-type]


def test_local_participant_is_valid() -> None:
    spec = backend()

    assert spec.kind is EvaluationBackendKind.LOCAL_TECHTREE
    assert spec.attestation is AttestationKind.PARTICIPANT
    assert spec.workspace_ref is None
    assert spec.provider_run_ref is None


def test_local_may_omit_executor_identity() -> None:
    assert backend(executor_identity=None).executor_identity is None


def test_local_platform_attestation_is_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="must be participant"):
        backend(attestation=AttestationKind.PLATFORM)


@pytest.mark.parametrize("field", ["workspace_ref", "provider_run_ref"])
def test_local_rejects_platform_references(field: str) -> None:
    with pytest.raises(PydanticValidationError, match=f"has no {field}"):
        backend(**{field: "workspace/abc"})


def test_prime_lab_without_any_reference_is_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="workspace_ref or a"):
        backend(
            kind=EvaluationBackendKind.PRIME_LAB,
            attestation=AttestationKind.PLATFORM,
        )


def test_prime_lab_with_a_workspace_reference_is_valid() -> None:
    spec = backend(
        kind=EvaluationBackendKind.PRIME_LAB,
        attestation=AttestationKind.PLATFORM,
        workspace_ref="workspace/abc",
    )

    assert spec.workspace_ref == "workspace/abc"


def test_prime_lab_must_be_platform_attested() -> None:
    with pytest.raises(PydanticValidationError, match="must be platform"):
        backend(
            kind=EvaluationBackendKind.PRIME_LAB,
            attestation=AttestationKind.PARTICIPANT,
            workspace_ref="workspace/abc",
        )


def test_independent_reproducer_without_executor_is_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="executor_identity"):
        backend(
            kind=EvaluationBackendKind.INDEPENDENT_REPRODUCER,
            attestation=AttestationKind.INDEPENDENT,
        )


def test_independent_reproducer_must_be_independently_attested() -> None:
    with pytest.raises(PydanticValidationError, match="independent attestation"):
        backend(
            kind=EvaluationBackendKind.INDEPENDENT_REPRODUCER,
            attestation=AttestationKind.PARTICIPANT,
            executor_identity="reproducer@example.org",
        )


def test_future_kinds_parse_but_are_not_supported_by_services() -> None:
    """The schema is wider than the runtime surface, and stays that way."""
    spec = backend(
        kind=EvaluationBackendKind.INDEPENDENT_REPRODUCER,
        attestation=AttestationKind.INDEPENDENT,
        executor_identity="reproducer@example.org",
    )

    assert spec.kind not in SUPPORTED_EVALUATION_BACKEND_KINDS
    assert set(SUPPORTED_EVALUATION_BACKEND_KINDS) == {
        EvaluationBackendKind.LOCAL_TECHTREE
    }


def test_backend_forbids_unknown_fields() -> None:
    with pytest.raises(PydanticValidationError, match="Extra inputs"):
        backend(relay_endpoint="https://example.invalid")
