"""Who orchestrated and attested to an evaluation. Spec section 11.3.

The evaluation backend and the subject runtime answer two different questions
and are deliberately separate objects:

``EvaluationBackendSpec``
    Who ran the comparison and whose word the result rests on.

``RuntimeSpec`` (in :mod:`techtree.models.campaign`)
    Where the evaluated agent's process actually executed.

Conflating them is how a self-reported local result quietly acquires the
authority of a platform-attested one. Each backend kind therefore fixes the
attestation it is allowed to claim, and the references that must or must not
accompany it.

The enum keeps the future backends so that stored documents and published
schemas do not need a version bump when they arrive. Services enforce the
narrower WP0–WP5 rule — only ``local_techtree`` — at the point of use, not
here, because a document that merely mentions a future backend must still be
parseable.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import model_validator

from techtree.models.base import NonEmptyString, ProtocolModel

__all__ = [
    "SUPPORTED_EVALUATION_BACKEND_KINDS",
    "AttestationKind",
    "EvaluationBackendKind",
    "EvaluationBackendSpec",
]


class EvaluationBackendKind(StrEnum):
    """Which system orchestrated the evaluation."""

    LOCAL_TECHTREE = "local_techtree"
    PRIME_LAB = "prime_lab"
    INDEPENDENT_REPRODUCER = "independent_reproducer"


class AttestationKind(StrEnum):
    """Whose attestation the recorded result carries."""

    PARTICIPANT = "participant"
    PLATFORM = "platform"
    INDEPENDENT = "independent"


#: The only backend kinds WP0–WP5 services accept. The schema is wider than
#: this on purpose; the runtime surface is not.
SUPPORTED_EVALUATION_BACKEND_KINDS: frozenset[EvaluationBackendKind] = frozenset(
    {EvaluationBackendKind.LOCAL_TECHTREE}
)


class EvaluationBackendSpec(ProtocolModel):
    """The orchestrating backend and the attestation it carries."""

    schema_version: Literal["techtree.evaluation-backend.v1alpha1"]
    kind: EvaluationBackendKind
    attestation: AttestationKind
    workspace_ref: NonEmptyString | None = None
    provider_run_ref: NonEmptyString | None = None
    executor_identity: NonEmptyString | None = None

    @model_validator(mode="after")
    def _check_kind_agrees_with_its_evidence(self) -> Self:
        """Reject attestation and reference combinations a kind cannot support."""
        if self.kind is EvaluationBackendKind.LOCAL_TECHTREE:
            if self.attestation is not AttestationKind.PARTICIPANT:
                raise ValueError(
                    "local_techtree evaluation is self-reported, so its "
                    "attestation must be participant"
                )
            if self.workspace_ref is not None:
                raise ValueError("local_techtree evaluation has no workspace_ref")
            if self.provider_run_ref is not None:
                raise ValueError("local_techtree evaluation has no provider_run_ref")
            # executor_identity stays optional: WP0-WP5 record no identity.
            return self

        if self.kind is EvaluationBackendKind.PRIME_LAB:
            if self.attestation is not AttestationKind.PLATFORM:
                raise ValueError(
                    "prime_lab evaluation is platform-attested, so its "
                    "attestation must be platform"
                )
            if self.workspace_ref is None and self.provider_run_ref is None:
                raise ValueError(
                    "prime_lab evaluation must carry a workspace_ref or a "
                    "provider_run_ref so the platform record can be found"
                )
            return self

        if self.attestation is not AttestationKind.INDEPENDENT:
            raise ValueError(
                "independent_reproducer evaluation must carry an independent "
                "attestation"
            )
        if self.executor_identity is None:
            raise ValueError(
                "independent_reproducer evaluation must name the executor_identity "
                "that stands behind it"
            )
        return self
