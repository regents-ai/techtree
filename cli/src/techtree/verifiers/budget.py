"""Whether a Campaign's declared budgets are budgets. Decisions document 0029.

Two questions, asked before a run of an executable public Campaign starts and
never after.

*Is every declared limit enforceable?* A Campaign that names an output ceiling
and nothing else is not bounded in turns, in input, or in time, and the fields
it left empty read like caps to anybody looking at the document.
:func:`require_executable_budget` refuses that Campaign by name rather than
letting the run discover it as a bill. The three declared fields are the three
publisher decisions — turns, input, output; the total is derived from the last
two in the compiler and is not a fourth thing anyone chooses.

*Does the declared spending limit hold, given those limits?* The token exposure
of a comparison is a finite number the moment the limits are finite, so the
dollar exposure is that number times a price. :func:`calculate_release_cost_bound`
computes it deliberately high — the whole context window on top of the declared
input allowance, one more sampled reply on top of the declared output allowance
— because a bound that is only usually right is not a bound. If the result is
above what the Campaign says it may spend, the run does not start.

The prices are not protocol values. They are a fact about a provider's rate
card on a particular day, so they live in a small record written at release
time (``release/price-profile.json``) whose numbers this module carries and a
test compares. Decision 0029 says the honest form of the published claim out
loud: token exposure is protocol-bounded, and the dollar figure uses provider
pricing recorded at release time.
"""

from __future__ import annotations

import math
from typing import Final

from pydantic import Field

from techtree.errors import PrerequisiteError
from techtree.models.base import JsonValue, NonEmptyString, ProtocolModel
from techtree.models.campaign import CampaignSpec

__all__ = [
    "CAMPAIGN_BUDGET_NOT_ENFORCED",
    "CAMPAIGN_COST_BOUND_EXCEEDED",
    "PRICE_PROFILE_SCHEMA_VERSION",
    "RELEASE_PRICE_PROFILES",
    "SUBJECT_PRICE_PROFILE_MISSING",
    "PriceProfile",
    "calculate_release_cost_bound",
    "price_profile_for",
    "require_cost_bound",
    "require_executable_budget",
]

#: Stable error codes. Decisions document 0029, layer A.
CAMPAIGN_BUDGET_NOT_ENFORCED: Final = "campaign_budget_not_enforced"
CAMPAIGN_COST_BOUND_EXCEEDED: Final = "campaign_cost_bound_exceeded"
SUBJECT_PRICE_PROFILE_MISSING: Final = "subject_price_profile_missing"

PRICE_PROFILE_SCHEMA_VERSION: Final = "techtree.price-profile.v1"

#: How many sides one comparison executes. Both variants run the same taskset,
#: so the comparison's exposure is twice one variant's.
_VARIANTS_PER_COMPARISON: Final = 2

_TOKENS_PER_MILLION: Final = 1_000_000.0


class PriceProfile(ProtocolModel):
    """What one subject model costs, and how much of it can be sent at once.

    ``context_window_tokens`` is not a price; it is the other half of the input
    bound. Verifiers' ``max_input_tokens`` is checked between turns, so a single
    turn may still carry a whole context window of prompt on top of whatever
    the allowance had already accounted for. Charging for that overshoot is
    what makes the bound a bound.
    """

    schema_version: NonEmptyString
    model_id: NonEmptyString
    input_usd_per_mtok: float = Field(gt=0.0)
    output_usd_per_mtok: float = Field(gt=0.0)
    context_window_tokens: int = Field(ge=1)
    source: NonEmptyString
    recorded_on: NonEmptyString


#: The prices this release was bounded with, recorded on the day they were
#: read. The same numbers are committed as ``release/price-profile.json``, and
#: a test fails if the two ever disagree.
#:
#: ``context_window_tokens`` is deliberately conservative. The pinned provider
#: publishes no context ceiling for this model in anything this repository
#: carries, so the release uses 131072 — the largest window in common use for
#: models of this class — rather than a number nobody can point at. It only
#: ever makes the computed bound larger, so an unrecorded larger window would
#: be visible as a run that reached a limit, never as an underestimate that
#: passed unnoticed.
RELEASE_PRICE_PROFILES: Final[tuple[PriceProfile, ...]] = (
    PriceProfile(
        schema_version=PRICE_PROFILE_SCHEMA_VERSION,
        model_id="qwen/qwen3.7-flash",
        input_usd_per_mtok=0.03,
        output_usd_per_mtok=0.13,
        context_window_tokens=131072,
        source="Prime Intellect published rate card for qwen/qwen3.7-flash",
        recorded_on="2026-08-20",
    ),
)


def price_profile_for(model_id: str) -> PriceProfile:
    """Return the recorded prices for one subject model, or refuse.

    A missing profile is a refusal rather than a default. Guessing a price
    would produce a dollar bound nobody could check, which is the one thing the
    published claim may not be.
    """
    for profile in RELEASE_PRICE_PROFILES:
        if profile.model_id == model_id:
            return profile
    raise PrerequisiteError(
        f"this release records no provider prices for {model_id}, so no "
        "spending bound can be computed for it",
        code=SUBJECT_PRICE_PROFILE_MISSING,
        details={"model_id": model_id},
    )


def require_executable_budget(campaign: CampaignSpec) -> None:
    """Refuse a Campaign whose declared execution limits are not enforced.

    The four values here are the four the engine can be made to enforce: the
    rollout timeout, and the three token and turn allowances. A public Campaign
    that leaves any of them empty is asking to be run without a bound on
    something it appears to bound.
    """
    missing: list[str] = []
    if campaign.execution.timeout_seconds <= 0:
        missing.append("execution.timeout_seconds")
    if campaign.budgets.maximum_model_calls is None:
        missing.append("budgets.maximum_model_calls")
    if campaign.budgets.maximum_input_tokens is None:
        missing.append("budgets.maximum_input_tokens")
    if campaign.budgets.maximum_output_tokens is None:
        missing.append("budgets.maximum_output_tokens")
    if missing:
        raise PrerequisiteError(
            "this public Campaign has unenforced or missing execution limits",
            code=CAMPAIGN_BUDGET_NOT_ENFORCED,
            details={
                "campaign_id": campaign.metadata.id,
                "missing": list(missing),
            },
        )


def calculate_release_cost_bound(
    campaign: CampaignSpec, price_profile: PriceProfile
) -> float:
    """Return the most one comparison of this Campaign can cost, in dollars.

    Per episode and per variant, with ``I`` and ``O`` the declared input and
    output allowances, ``C`` the context window and ``S`` the per-call sampling
    cap::

        input  ≤ I + C          output ≤ O + S
        bound  = tasks × 2 × ((I + C)·Pᵢ + (O + S)·Pₒ)

    The two overshoot terms are the one-turn soft overshoot. The pinned build
    states the rule itself: the caps are checked between turns, so the turn
    that crosses one still completes. One turn's worth is at most a whole
    context window in and one sampled reply out. The rates are the highest
    uncached ones the profile records.
    """
    require_executable_budget(campaign)
    budgets = campaign.budgets
    assert budgets.maximum_input_tokens is not None
    assert budgets.maximum_output_tokens is not None

    episodes = campaign.taskset.selection.num_tasks * _VARIANTS_PER_COMPARISON
    input_tokens = budgets.maximum_input_tokens + price_profile.context_window_tokens
    output_tokens = budgets.maximum_output_tokens + campaign.subject.sampling.max_tokens
    per_episode = (
        input_tokens * price_profile.input_usd_per_mtok
        + output_tokens * price_profile.output_usd_per_mtok
    ) / _TOKENS_PER_MILLION
    return episodes * per_episode


def require_cost_bound(campaign: CampaignSpec, price_profile: PriceProfile) -> float:
    """Refuse a Campaign that can cost more than it says it may.

    Returns the computed bound so a caller can record it. A Campaign that
    declares no spending limit has no precondition to check here; what bounds
    it is the token exposure above, and that is finite either way.
    """
    bound = calculate_release_cost_bound(campaign, price_profile)
    ceiling = campaign.budgets.maximum_usd
    if ceiling is None or bound <= ceiling:
        return bound
    details: dict[str, JsonValue] = {
        "campaign_id": campaign.metadata.id,
        "calculated_bound_usd": _rounded(bound),
        "maximum_usd": ceiling,
        "model_id": price_profile.model_id,
        "prices_recorded_on": price_profile.recorded_on,
    }
    raise PrerequisiteError(
        "the most this comparison can cost under its own enforced limits — "
        f"${_rounded(bound):.2f} at the prices this release recorded — is "
        f"above the ${ceiling:.2f} the Campaign declares it may spend",
        code=CAMPAIGN_COST_BOUND_EXCEEDED,
        details=details,
    )


def _rounded(amount: float) -> float:
    """Round a dollar figure up to the cent, so a bound is never reported low."""
    return math.ceil(amount * 100.0) / 100.0
