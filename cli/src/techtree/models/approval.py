"""Estimates and the approvals that bind them. Plan `docs/plan/v0.2.md`,
"Paid remote execution" > "Estimate and approval".

No remote create request is sent without a valid unexpired approval, and the
approval is not a general permission to spend. It binds one exact execution
plan, one exact ceiling, and one exact non-secret billing-principal label, and
any change to the plan, the budget, or the account invalidates it, as does an
estimate that has expired underneath it.

Three decisions in this module are worth stating.

*Money is carried as an exact decimal string with one canonical spelling.*
Binary floating point cannot represent most decimal amounts exactly, and an
authorization ceiling that is approximately right is not an authorization. The
canonical spelling — no leading zeros, no trailing fractional zeros — is what
makes byte comparison and amount comparison the same comparison, so an approval
cannot be defeated by respelling the number it approved.

*The approval refers to the plan by digest and to nothing else.* The plan's own
model belongs to the execution-plan work; a provider, a model, or a task count
that changed is a plan whose digest changed, so those changes are caught by the
plan comparison rather than by a second list of fields to keep in step.

*A per-arm quote carries both arms.* When a provider prices the two arms
separately, the estimate says so and carries each arm's ceiling, and the total
has to be their sum. A scope that announced per-arm pricing without the arms
would be an announcement a reader could not act on.

*A person approves, never the model.* :class:`ApprovalMethod` has three
members, all of them a human acting in a host or a terminal. There is no member
an automated caller could select, because the plan's boundaries say the model
never approves paid inference.

These are documents. Whether one approval still covers the run a caller is
about to start is :mod:`techtree.approval`, which sits above this module
because answering it means digesting the estimate, and a model file never
hashes anything.

Design text for the hosted backend is kept in the binding plan for v0.2.x; the
approval model itself is v0.2.0 work, because a local run also authorizes spend
on model inference.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import StringConstraints, model_validator

from techtree.models.base import Digest, NonEmptyString, ProtocolModel, UtcDateTime

__all__ = [
    "MONETARY_AMOUNT_PATTERN",
    "ApprovalMethod",
    "ArmCeilings",
    "CeilingScope",
    "ExecutionApproval",
    "MonetaryAmount",
    "RemoteExecutionEstimate",
]

#: One spelling per amount: no sign, no leading zeros, and no trailing zero in
#: the fraction. ``5``, ``5.5`` and ``0.0025`` are amounts; ``05``, ``5.00``,
#: ``.5`` and ``-1`` are not. Without this, ``5`` and ``5.00`` would be two
#: different authorizations for the same money and two different digests for
#: the same estimate.
MONETARY_AMOUNT_PATTERN = r"^(0|[1-9][0-9]*)(\.[0-9]*[1-9])?$"

type MonetaryAmount = Annotated[str, StringConstraints(pattern=MONETARY_AMOUNT_PATTERN)]


class CeilingScope(StrEnum):
    """What the provider's quoted ceiling covers.

    A comparison has two arms, and a provider may price it either way. The
    estimate says which, because "the maximum is fifty dollars" means something
    different when it is a per-arm figure. ``maximum_authorized_cost`` is the
    total in both cases; this field says how the quote behind it was built.
    """

    SINGLE_CEILING_FOR_BOTH_ARMS = "single_ceiling_for_both_arms"
    PER_ARM_CEILING = "per_arm_ceiling"


class ArmCeilings(ProtocolModel):
    """The separately quoted ceiling of each arm of one comparison."""

    baseline: MonetaryAmount
    candidate: MonetaryAmount


class RemoteExecutionEstimate(ProtocolModel):
    """What one execution plan is expected to cost, and until when.

    ``estimated_cost`` is nullable because a provider that will not quote is a
    real answer; ``maximum_authorized_cost`` is not, because the ceiling is the
    whole point of the document. ``uncertainty_disclosure`` is required for the
    same reason: an estimate with no stated uncertainty reads as a promise.
    """

    execution_plan_digest: Digest
    provider: Literal["prime"]
    billing_principal_label: NonEmptyString
    currency: Literal["USD"]
    estimated_cost: MonetaryAmount | None
    maximum_authorized_cost: MonetaryAmount
    ceiling_scope: CeilingScope
    per_arm_ceilings: ArmCeilings | None
    estimate_source: NonEmptyString
    uncertainty_disclosure: NonEmptyString
    expires_at: UtcDateTime

    @model_validator(mode="after")
    def _check_the_estimate_sits_under_its_own_ceiling(self) -> Self:
        """An estimate above its ceiling authorizes a run it expects to exceed."""
        if self.estimated_cost is None:
            return self
        if Decimal(self.estimated_cost) > Decimal(self.maximum_authorized_cost):
            raise ValueError(
                "an estimate above its own authorized maximum asks for approval "
                "of a run it already expects to stop short"
            )
        return self

    @model_validator(mode="after")
    def _check_the_arms_are_carried_exactly_when_they_are_priced(self) -> Self:
        """A per-arm scope carries both arms, and they add up to the total."""
        per_arm = self.ceiling_scope is CeilingScope.PER_ARM_CEILING
        if per_arm != (self.per_arm_ceilings is not None):
            raise ValueError(
                "an estimate carries a ceiling for each arm exactly when it "
                f"says the arms are priced separately; got {self.ceiling_scope.value}"
            )
        arms = self.per_arm_ceilings
        if arms is None:
            return self
        if Decimal(arms.baseline) + Decimal(arms.candidate) != Decimal(
            self.maximum_authorized_cost
        ):
            raise ValueError(
                "the authorized maximum is what both arms together may spend, "
                f"and {arms.baseline} plus {arms.candidate} is not "
                f"{self.maximum_authorized_cost}"
            )
        return self


class ApprovalMethod(StrEnum):
    """How the person approved. Every member is a person."""

    NATIVE_HERMES = "native_hermes"
    NATIVE_CODEX = "native_codex"
    TERMINAL_CONFIRMATION = "terminal_confirmation"


class ExecutionApproval(ProtocolModel):
    """One person's authorization of one plan, one ceiling, one account."""

    execution_plan_digest: Digest
    estimate_digest: Digest
    maximum_authorized_cost: MonetaryAmount
    billing_principal_label: NonEmptyString
    approved_at: UtcDateTime
    approval_method: ApprovalMethod
