"""Estimates and the approvals that bind them. Plan `docs/plan/v0.2.md`,
"Paid remote execution" > "Estimate and approval".

The acceptance criterion these tests carry is one sentence: any changed plan,
budget, or account, or an expired estimate, invalidates the approval. Each of
the four triggers gets its own test, and so does the combination, because an
approval that failed for four reasons and reported one would send a caller
round the repair loop four times.

The rest is about the two things that make those four checks meaningful. An
amount has exactly one spelling, so an approval cannot be defeated by
respelling the number it approved. And every approval method is a person: the
model never approves paid inference.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError as PydanticValidationError

from techtree.approval import (
    ApprovalCheck,
    ApprovalInvalidation,
    check_execution_approval,
)
from techtree.canonical import digest_object
from techtree.errors import ValidationError
from techtree.models.approval import (
    ApprovalMethod,
    ArmCeilings,
    CeilingScope,
    ExecutionApproval,
    RemoteExecutionEstimate,
)

PLAN = f"sha256:{'aa' * 32}"
OTHER_PLAN = f"sha256:{'bb' * 32}"
ACCOUNT = "fixture billing principal"
CEILING = "12"
APPROVED_AT = datetime(2026, 1, 1, tzinfo=UTC)
EXPIRES_AT = APPROVED_AT + timedelta(hours=1)


def estimate(**overrides: object) -> RemoteExecutionEstimate:
    """Build an estimate for the approved plan unless told otherwise."""
    fields: dict[str, object] = {
        "execution_plan_digest": PLAN,
        "provider": "prime",
        "billing_principal_label": ACCOUNT,
        "currency": "USD",
        "estimated_cost": "7.4",
        "maximum_authorized_cost": CEILING,
        "ceiling_scope": CeilingScope.SINGLE_CEILING_FOR_BOTH_ARMS,
        "per_arm_ceilings": None,
        "estimate_source": "provider quote",
        "uncertainty_disclosure": "token counts vary between runs",
        "expires_at": EXPIRES_AT,
    }
    fields.update(overrides)
    return RemoteExecutionEstimate(**fields)  # type: ignore[arg-type]


def approval(quoted: RemoteExecutionEstimate, **overrides: object) -> ExecutionApproval:
    """Build the approval that binds one estimate."""
    fields: dict[str, object] = {
        "execution_plan_digest": quoted.execution_plan_digest,
        "estimate_digest": digest_object(quoted),
        "maximum_authorized_cost": quoted.maximum_authorized_cost,
        "billing_principal_label": quoted.billing_principal_label,
        "approved_at": APPROVED_AT,
        "approval_method": ApprovalMethod.TERMINAL_CONFIRMATION,
    }
    fields.update(overrides)
    return ExecutionApproval(**fields)  # type: ignore[arg-type]


def check(
    quoted: RemoteExecutionEstimate,
    given: ExecutionApproval,
    **overrides: object,
) -> ApprovalCheck:
    """Check one approval against the run a caller is about to start."""
    fields: dict[str, object] = {
        "approval": given,
        "estimate": quoted,
        "execution_plan_digest": PLAN,
        "maximum_authorized_cost": CEILING,
        "billing_principal_label": ACCOUNT,
        "at": APPROVED_AT + timedelta(minutes=1),
    }
    fields.update(overrides)
    return check_execution_approval(**fields)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# The approval holds
# ---------------------------------------------------------------------------


def test_an_unchanged_unexpired_approval_is_valid() -> None:
    quoted = estimate()

    verdict = check(quoted, approval(quoted))

    assert verdict.valid
    assert verdict.invalidations == ()


# ---------------------------------------------------------------------------
# Each invalidation trigger
# ---------------------------------------------------------------------------


def test_a_changed_plan_invalidates_the_approval() -> None:
    quoted = estimate()

    verdict = check(quoted, approval(quoted), execution_plan_digest=OTHER_PLAN)

    assert not verdict.valid
    assert ApprovalInvalidation.EXECUTION_PLAN_CHANGED in verdict.invalidations


@pytest.mark.parametrize("proposed", ["13", "11"])
def test_a_changed_budget_invalidates_the_approval_in_either_direction(
    proposed: str,
) -> None:
    """A ceiling is an exact authorization, not an upper bound to stay under."""
    quoted = estimate()

    verdict = check(quoted, approval(quoted), maximum_authorized_cost=proposed)

    assert not verdict.valid
    assert ApprovalInvalidation.BUDGET_CHANGED in verdict.invalidations


def test_a_changed_account_invalidates_the_approval() -> None:
    quoted = estimate()

    verdict = check(
        quoted, approval(quoted), billing_principal_label="somebody else's account"
    )

    assert not verdict.valid
    assert ApprovalInvalidation.BILLING_ACCOUNT_CHANGED in verdict.invalidations


def test_an_expired_estimate_invalidates_the_approval() -> None:
    quoted = estimate()

    verdict = check(quoted, approval(quoted), at=EXPIRES_AT + timedelta(seconds=1))

    assert not verdict.valid
    assert ApprovalInvalidation.ESTIMATE_EXPIRED in verdict.invalidations


def test_the_expiry_instant_is_outside_the_window() -> None:
    """An estimate is a statement about a window; the instant it closes is not
    inside it."""
    quoted = estimate()

    assert not check(quoted, approval(quoted), at=EXPIRES_AT).valid
    assert check(quoted, approval(quoted), at=EXPIRES_AT - timedelta(seconds=1)).valid


def test_every_trigger_is_reported_rather_than_the_first() -> None:
    quoted = estimate()

    verdict = check(
        quoted,
        approval(quoted),
        execution_plan_digest=OTHER_PLAN,
        maximum_authorized_cost="13",
        billing_principal_label="somebody else's account",
        at=EXPIRES_AT,
    )

    assert set(verdict.invalidations) == {
        ApprovalInvalidation.EXECUTION_PLAN_CHANGED,
        ApprovalInvalidation.BUDGET_CHANGED,
        ApprovalInvalidation.BILLING_ACCOUNT_CHANGED,
        ApprovalInvalidation.ESTIMATE_EXPIRED,
    }


def test_all_five_triggers_fire_together() -> None:
    """Nothing about the run, the approval, or the estimate is left standing."""
    quoted = estimate()
    unrelated = estimate(expires_at=APPROVED_AT - timedelta(hours=1))

    verdict = check(
        unrelated,
        approval(quoted),
        execution_plan_digest=OTHER_PLAN,
        maximum_authorized_cost="13",
        billing_principal_label="somebody else's account",
        at=APPROVED_AT,
    )

    assert set(verdict.invalidations) == set(ApprovalInvalidation)


# ---------------------------------------------------------------------------
# The approval and its estimate stay bound together
# ---------------------------------------------------------------------------


def test_a_different_estimate_does_not_carry_the_approval() -> None:
    """Otherwise expiry would be checked against whichever estimate was at hand."""
    quoted = estimate()
    replacement = estimate(expires_at=EXPIRES_AT + timedelta(days=30))

    verdict = check(replacement, approval(quoted))

    assert not verdict.valid
    assert ApprovalInvalidation.ESTIMATE_NOT_BOUND in verdict.invalidations


def test_a_refreshed_estimate_cannot_extend_an_hour_old_approval() -> None:
    """The digest is taken from the estimate handed in, never supplied beside it.

    A caller who refreshes a quote has a new estimate and needs a new approval.
    Presenting the refreshed document — whose own window is wide open — under an
    approval given against yesterday's hour-long estimate is the bypass this
    binding exists to stop, and two days later it is still refused.
    """
    quoted = estimate()
    refreshed = estimate(expires_at=EXPIRES_AT + timedelta(days=30))

    verdict = check(refreshed, approval(quoted), at=APPROVED_AT + timedelta(days=2))

    assert not verdict.valid
    assert verdict.invalidations == (ApprovalInvalidation.ESTIMATE_NOT_BOUND,)


def test_an_estimate_for_another_plan_does_not_carry_the_approval() -> None:
    quoted = estimate(execution_plan_digest=OTHER_PLAN)
    given = approval(quoted, execution_plan_digest=PLAN)

    verdict = check(quoted, given)

    assert not verdict.valid
    assert ApprovalInvalidation.ESTIMATE_NOT_BOUND in verdict.invalidations


def test_an_estimate_with_another_ceiling_does_not_carry_the_approval() -> None:
    quoted = estimate(maximum_authorized_cost="30")
    given = approval(quoted, maximum_authorized_cost=CEILING)

    verdict = check(quoted, given)

    assert not verdict.valid
    assert ApprovalInvalidation.ESTIMATE_NOT_BOUND in verdict.invalidations


def test_an_estimate_for_another_account_does_not_carry_the_approval() -> None:
    quoted = estimate(billing_principal_label="somebody else's account")
    given = approval(quoted, billing_principal_label=ACCOUNT)

    verdict = check(quoted, given, billing_principal_label=ACCOUNT)

    assert not verdict.valid
    assert ApprovalInvalidation.ESTIMATE_NOT_BOUND in verdict.invalidations


def test_a_naive_instant_is_refused_rather_than_compared() -> None:
    """ "Noon" is not a moment, so it cannot be before or after an expiry."""
    quoted = estimate()

    with pytest.raises(ValidationError, match="does not name one"):
        check(quoted, approval(quoted), at=datetime(2026, 1, 1, 0, 30))


# ---------------------------------------------------------------------------
# Exact amounts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("amount", ["0", "5", "5.5", "0.0025", "1234.75"])
def test_a_canonical_amount_is_accepted(amount: str) -> None:
    assert estimate(maximum_authorized_cost=amount, estimated_cost=None)


@pytest.mark.parametrize(
    "amount", ["5.00", "05", ".5", "5.", "-1", "1e3", "1,000", "12 ", "USD 12"]
)
def test_an_amount_with_no_canonical_spelling_is_rejected(amount: str) -> None:
    """One spelling per amount, so byte equality and amount equality agree."""
    with pytest.raises(PydanticValidationError):
        estimate(maximum_authorized_cost=amount)


def test_a_respelt_ceiling_is_not_a_way_around_the_approval() -> None:
    """``12.00`` is not an amount, and asking with it does not get a yes.

    The check compares strings, which is exactly why the canonical spelling
    matters: a caller that hands in a respelling has handed in something that
    is not the approved ceiling, and it is refused rather than quietly read as
    the same money.
    """
    quoted = estimate()

    verdict = check(quoted, approval(quoted), maximum_authorized_cost="12.00")

    assert not verdict.valid
    assert ApprovalInvalidation.BUDGET_CHANGED in verdict.invalidations


def test_an_estimate_above_its_own_ceiling_is_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="above its own authorized"):
        estimate(estimated_cost="12.5")


def test_an_estimate_at_its_own_ceiling_is_accepted() -> None:
    assert estimate(estimated_cost=CEILING).estimated_cost == CEILING


def test_a_provider_that_will_not_quote_is_a_real_answer() -> None:
    assert estimate(estimated_cost=None).estimated_cost is None


# ---------------------------------------------------------------------------
# Per-arm ceilings
# ---------------------------------------------------------------------------


def per_arm(**overrides: object) -> RemoteExecutionEstimate:
    """Build a separately priced estimate whose arms sum to the total."""
    fields: dict[str, object] = {
        "ceiling_scope": CeilingScope.PER_ARM_CEILING,
        "per_arm_ceilings": ArmCeilings(baseline="5", candidate="7"),
    }
    fields.update(overrides)
    return estimate(**fields)


def test_a_per_arm_estimate_carries_both_arms() -> None:
    quoted = per_arm()

    assert quoted.per_arm_ceilings is not None
    assert quoted.per_arm_ceilings.baseline == "5"
    assert quoted.per_arm_ceilings.candidate == "7"


def test_a_per_arm_scope_without_the_arms_is_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="ceiling for each arm"):
        per_arm(per_arm_ceilings=None)


def test_a_single_ceiling_that_carries_arms_is_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="ceiling for each arm"):
        estimate(
            ceiling_scope=CeilingScope.SINGLE_CEILING_FOR_BOTH_ARMS,
            per_arm_ceilings=ArmCeilings(baseline="5", candidate="7"),
        )


@pytest.mark.parametrize(
    "arms",
    [("5", "6"), ("5", "8"), ("0", "7")],
)
def test_arms_that_do_not_add_up_to_the_total_are_rejected(
    arms: tuple[str, str],
) -> None:
    """A total that is not the sum authorizes an amount nobody quoted."""
    baseline, candidate = arms

    with pytest.raises(PydanticValidationError, match="both arms together"):
        per_arm(per_arm_ceilings=ArmCeilings(baseline=baseline, candidate=candidate))


def test_arms_add_up_at_sub_cent_precision() -> None:
    """Exact decimals, so the sum is not decided by a binary approximation."""
    quoted = per_arm(
        maximum_authorized_cost="0.3",
        estimated_cost=None,
        per_arm_ceilings=ArmCeilings(baseline="0.1", candidate="0.2"),
    )

    assert quoted.maximum_authorized_cost == "0.3"


def test_the_ceiling_scope_is_stated() -> None:
    """The estimate says whether one ceiling covers both arms."""
    assert per_arm().ceiling_scope is CeilingScope.PER_ARM_CEILING


# ---------------------------------------------------------------------------
# Who approves
# ---------------------------------------------------------------------------


def test_every_approval_method_is_a_person() -> None:
    """Plan boundary: the model never approves paid inference."""
    assert {method.value for method in ApprovalMethod} == {
        "native_hermes",
        "native_codex",
        "terminal_confirmation",
    }


def test_a_verdict_cannot_disagree_with_its_own_reasons() -> None:
    with pytest.raises(PydanticValidationError, match="valid exactly when"):
        ApprovalCheck(
            valid=True,
            invalidations=(ApprovalInvalidation.BUDGET_CHANGED,),
        )


def test_a_failing_verdict_must_say_what_failed() -> None:
    with pytest.raises(PydanticValidationError, match="valid exactly when"):
        ApprovalCheck(valid=False, invalidations=())
