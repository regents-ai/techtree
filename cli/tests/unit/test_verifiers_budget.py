"""Declared limits that are limits, and a spend bound that is a bound.

Decisions document 0029, layer A. Two refusals live here and both of them are
about the same failure: a Campaign whose budget fields read like caps to
everybody looking at the document and cap nothing at all. The first refusal
says the fields are not enforceable; the second says that even enforced, they
allow more spending than the Campaign declares it may do.

The prices are a fact about a provider on a day rather than a protocol value,
so the last test here is the one that keeps the release record and the code
that computes with it from drifting apart.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import pytest

from fixtures.drafts.support import synthetic_graph
from fixtures.verifiers.support import (
    SUBJECT_INPUT_USD_PER_MTOK,
    SUBJECT_MODEL_ID,
    SUBJECT_OUTPUT_USD_PER_MTOK,
    shipped_campaign,
)
from techtree.errors import PrerequisiteError
from techtree.models.campaign import CampaignSpec
from techtree.verifiers.budget import (
    CAMPAIGN_BUDGET_NOT_ENFORCED,
    CAMPAIGN_COST_BOUND_EXCEEDED,
    PRICE_PROFILE_SCHEMA_VERSION,
    RELEASE_PRICE_PROFILES,
    SUBJECT_PRICE_PROFILE_MISSING,
    PriceProfile,
    calculate_release_cost_bound,
    price_profile_for,
    require_cost_bound,
    require_executable_budget,
)

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[2]

#: Round numbers, so the expected bound below is arithmetic a reader can do.
TEST_PROFILE: Final = PriceProfile(
    schema_version=PRICE_PROFILE_SCHEMA_VERSION,
    model_id="development-placeholder",
    input_usd_per_mtok=1.0,
    output_usd_per_mtok=2.0,
    context_window_tokens=1_000,
    source="a fixture, not a rate card",
    recorded_on="2026-08-20",
)

#: The synthetic Campaign runs 4 tasks per variant and samples at most 512
#: tokens per call. With the limits below:
#:
#:     input  ≤ 1000 + 1000 (context)  = 2000 tokens at $1.00/Mtok
#:     output ≤  500 +  512 (sampling) = 1012 tokens at $2.00/Mtok
#:     8 episodes × (0.002000 + 0.002024) = $0.032192
EXPECTED_BOUND: Final = 0.032192


def campaign(**budgets: object) -> CampaignSpec:
    """Return the synthetic Campaign with the given budget fields declared."""
    base = synthetic_graph().campaign
    declared: dict[str, object] = {
        "maximum_model_calls": 30,
        "maximum_input_tokens": 1_000,
        "maximum_output_tokens": 500,
        "maximum_usd": None,
    }
    declared.update(budgets)
    return base.model_copy(update={"budgets": base.budgets.model_copy(update=declared)})


# ---------------------------------------------------------------------------
# Limits that are enforced
# ---------------------------------------------------------------------------


def test_a_campaign_with_every_limit_declared_is_accepted() -> None:
    require_executable_budget(campaign())


@pytest.mark.parametrize(
    "field",
    [
        "maximum_model_calls",
        "maximum_input_tokens",
        "maximum_output_tokens",
    ],
)
def test_a_limit_the_engine_cannot_be_given_stops_the_run(field: str) -> None:
    with pytest.raises(PrerequisiteError) as caught:
        require_executable_budget(campaign(**{field: None}))

    assert caught.value.code == CAMPAIGN_BUDGET_NOT_ENFORCED
    assert caught.value.details["missing"] == [f"budgets.{field}"]


def test_every_missing_limit_is_named_at_once() -> None:
    # One refusal listing three fields is one thing to fix; three refusals in
    # sequence is three runs that each cost nothing and tell you a third.
    with pytest.raises(PrerequisiteError) as caught:
        require_executable_budget(
            campaign(
                maximum_model_calls=None,
                maximum_input_tokens=None,
                maximum_output_tokens=None,
            )
        )

    assert caught.value.details["missing"] == [
        "budgets.maximum_model_calls",
        "budgets.maximum_input_tokens",
        "budgets.maximum_output_tokens",
    ]


def test_the_shipped_campaign_declares_limits_the_engine_can_be_held_to() -> None:
    """The Campaign this build ships passes its own gate.

    Every field the validator asks for is present in the packaged catalog, so
    the public Campaign starts on the strength of limits that reach the engine
    rather than on limits nobody enforces. A regeneration that dropped one
    would fail here rather than at somebody's first real run.
    """
    shipped = shipped_campaign()

    require_executable_budget(shipped)

    assert shipped.budgets.maximum_model_calls == 44
    assert shipped.budgets.maximum_input_tokens == 900_000
    assert shipped.budgets.maximum_output_tokens == 16_000
    assert shipped.execution.timeout_seconds == 600


def test_the_shipped_campaign_cannot_outspend_what_it_declares() -> None:
    """The other half of the gate, at the prices this release recorded.

    The bound is deliberately pessimistic — the whole context window on top of
    the input allowance and one more sampled reply on top of the output one,
    charged for all 72 episodes — and it still lands under the declared
    maximum. A regeneration that raised a token limit far enough to break that
    would be refused here rather than by a run that already started.
    """
    shipped = shipped_campaign()

    bound = require_cost_bound(shipped, price_profile_for(SUBJECT_MODEL_ID))

    assert bound == pytest.approx(2.41521408)
    assert shipped.budgets.maximum_usd == 2.50


# ---------------------------------------------------------------------------
# What a bounded comparison can cost
# ---------------------------------------------------------------------------


def test_the_bound_charges_for_the_context_window_and_one_more_reply() -> None:
    # The pinned build checks its caps between turns, so the turn that crosses
    # one still completes: a bound that ignored the overshoot would be a
    # figure that is usually right, which is not a bound.
    assert calculate_release_cost_bound(campaign(), TEST_PROFILE) == pytest.approx(
        EXPECTED_BOUND
    )


def test_a_comparison_that_fits_its_declared_limit_starts() -> None:
    assert require_cost_bound(
        campaign(maximum_usd=0.04), TEST_PROFILE
    ) == pytest.approx(EXPECTED_BOUND)


def test_a_comparison_that_could_outspend_its_declared_limit_is_refused() -> None:
    with pytest.raises(PrerequisiteError) as caught:
        require_cost_bound(campaign(maximum_usd=0.03), TEST_PROFILE)

    assert caught.value.code == CAMPAIGN_COST_BOUND_EXCEEDED
    assert caught.value.details["maximum_usd"] == 0.03
    # Rounded up to the cent, so the figure quoted back is never below the
    # figure computed.
    assert caught.value.details["calculated_bound_usd"] == 0.04


def test_no_bound_is_computed_from_limits_that_are_not_enforced() -> None:
    # Otherwise the dollar figure would be arithmetic over fields the engine
    # never received, which is the decorative budget wearing a number.
    with pytest.raises(PrerequisiteError) as caught:
        calculate_release_cost_bound(campaign(maximum_input_tokens=None), TEST_PROFILE)

    assert caught.value.code == CAMPAIGN_BUDGET_NOT_ENFORCED


def test_a_model_this_release_recorded_no_prices_for_is_refused() -> None:
    with pytest.raises(PrerequisiteError) as caught:
        price_profile_for("some/model-nobody-priced")

    assert caught.value.code == SUBJECT_PRICE_PROFILE_MISSING


# ---------------------------------------------------------------------------
# The recorded prices
# ---------------------------------------------------------------------------


def test_the_release_records_prices_for_the_subject_model_it_ships() -> None:
    profile = price_profile_for(SUBJECT_MODEL_ID)

    assert profile.input_usd_per_mtok == SUBJECT_INPUT_USD_PER_MTOK
    assert profile.output_usd_per_mtok == SUBJECT_OUTPUT_USD_PER_MTOK


def test_the_committed_price_record_is_the_one_the_bound_is_computed_with() -> None:
    # The record is what a reader checks the published bound against, so a
    # release that computed with one set of prices and published another would
    # make the whole figure unverifiable.
    record = json.loads(
        (REPOSITORY_ROOT / "release" / "price-profile.json").read_text(encoding="utf-8")
    )

    assert [PriceProfile.model_validate(entry) for entry in record["profiles"]] == list(
        RELEASE_PRICE_PROFILES
    )
