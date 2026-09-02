"""Whether one approval still covers the run about to be started.

Plan ``docs/plan/v0.2.md``, "Paid remote execution" > "Estimate and approval".

An approval is not a general permission to spend. It authorizes one exact
execution plan, one exact ceiling, and one exact non-secret billing-principal
label, against one exact estimate, and the plan's rule is that any change to
the plan, the budget, or the account invalidates it, as does an estimate that
has expired underneath it.

This lives above :mod:`techtree.models.approval` for one reason: answering the
question means digesting the estimate document, and a model file never hashes
anything. The digest is taken here, from the estimate the caller actually
handed in, because an approval that trusted a digest supplied alongside a
document would check expiry against whichever estimate happened to be at hand.
A refreshed estimate presented under the original estimate's digest would then
pass, which is the whole failure the binding exists to prevent.

:func:`check_execution_approval` never raises for a failed check. It reports
every trigger that fired, because a caller repairing an approval wants to know
everything that moved rather than the first thing that moved. It does raise for
an ``at`` that is not an instant: a naive datetime does not name a moment, and
comparing one against an expiry would be answering a question nobody asked.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Final, Self

from pydantic import model_validator

from techtree.canonical import digest_object
from techtree.errors import ValidationError
from techtree.models.approval import (
    ExecutionApproval,
    MonetaryAmount,
    RemoteExecutionEstimate,
)
from techtree.models.base import Digest, ProtocolModel

__all__ = [
    "APPROVAL_CHECK_INVALID",
    "ApprovalCheck",
    "ApprovalInvalidation",
    "check_execution_approval",
]

#: The one error code a check that cannot be performed at all reports.
APPROVAL_CHECK_INVALID: Final = "approval_check_invalid"


class ApprovalInvalidation(StrEnum):
    """Why an approval does not cover the run that is about to be started."""

    #: The plan is not the plan that was approved. A different provider, model,
    #: task count, subject, or evidence backend is a different plan digest.
    EXECUTION_PLAN_CHANGED = "execution_plan_changed"
    #: The ceiling is not the ceiling that was approved, in either direction.
    BUDGET_CHANGED = "budget_changed"
    #: The account that would bear the usage is not the approved one.
    BILLING_ACCOUNT_CHANGED = "billing_account_changed"
    #: The estimate the approval rests on has expired.
    ESTIMATE_EXPIRED = "estimate_expired"
    #: The estimate offered is not the estimate the approval was given against,
    #: or does not describe the plan, ceiling, or account the approval names.
    ESTIMATE_NOT_BOUND = "estimate_not_bound"


class ApprovalCheck(ProtocolModel):
    """The verdict on one approval, and every reason it failed."""

    valid: bool
    invalidations: tuple[ApprovalInvalidation, ...]

    @model_validator(mode="after")
    def _check_the_verdict_agrees_with_its_reasons(self) -> Self:
        """A valid approval lists no triggers, and an invalid one must."""
        if self.valid != (not self.invalidations):
            raise ValueError("an approval is valid exactly when nothing invalidated it")
        return self


def check_execution_approval(
    *,
    approval: ExecutionApproval,
    estimate: RemoteExecutionEstimate,
    execution_plan_digest: Digest,
    maximum_authorized_cost: MonetaryAmount,
    billing_principal_label: str,
    at: datetime,
) -> ApprovalCheck:
    """Return whether one approval still covers the run being prepared.

    Expiry is exclusive. An approval resting on an estimate that expires at
    noon is not valid at noon, because an estimate is a statement about a
    window and the instant it closes is outside it.
    """
    if at.tzinfo is None or at.tzinfo.utcoffset(at) is None:
        raise ValidationError(
            "an approval is checked against an instant, and a naive datetime "
            "does not name one",
            code=APPROVAL_CHECK_INVALID,
            details={"at": at.isoformat()},
        )

    invalidations: list[ApprovalInvalidation] = []

    if approval.execution_plan_digest != execution_plan_digest:
        invalidations.append(ApprovalInvalidation.EXECUTION_PLAN_CHANGED)
    if approval.maximum_authorized_cost != maximum_authorized_cost:
        invalidations.append(ApprovalInvalidation.BUDGET_CHANGED)
    if approval.billing_principal_label != billing_principal_label:
        invalidations.append(ApprovalInvalidation.BILLING_ACCOUNT_CHANGED)
    if (
        approval.estimate_digest != digest_object(estimate)
        or estimate.execution_plan_digest != approval.execution_plan_digest
        or estimate.maximum_authorized_cost != approval.maximum_authorized_cost
        or estimate.billing_principal_label != approval.billing_principal_label
    ):
        invalidations.append(ApprovalInvalidation.ESTIMATE_NOT_BOUND)
    if at >= estimate.expires_at:
        invalidations.append(ApprovalInvalidation.ESTIMATE_EXPIRED)

    return ApprovalCheck(valid=not invalidations, invalidations=tuple(invalidations))
