"""Approvals are carried, never manufactured. Specification section 7.7."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import pytest
from techtree_hermes.approvals import (
    DOCUMENTED_CONFIRMATION_KEYS,
    GUIDED_REVISION_DISCLOSURE,
    DisclosureStore,
    InstallPlanStore,
    issue_local_plan_id,
    policy_acceptance_args,
    require_confirmed_disclosure,
    require_install_plan,
    require_user_confirmed_tool_context,
)
from techtree_hermes.errors import ApprovalRequiredError, BootstrapPlanError
from techtree_hermes.models import PLAN_ID_PATTERN, BootstrapInstallPlan

DIGEST = "sha256:" + "a" * 64
RUN_ID = "run_" + "0" * 32
POLICY_DIGEST = "sha256:" + "b" * 64


def _plan(
    *,
    plan_id: str | None = None,
    expires_in_seconds: int = 900,
    release_core_digest: str = DIGEST,
) -> BootstrapInstallPlan:
    issued = datetime.now(UTC)
    return BootstrapInstallPlan(
        plan_id=plan_id or issue_local_plan_id("install", DIGEST),
        package="techtree",
        version="0.1.0",
        argv=("uv", "tool", "install", "techtree==0.1.0"),
        release_core_digest=release_core_digest,
        requires_confirmation=True,
        created_at=issued.isoformat(),
        expires_at=(issued + timedelta(seconds=expires_in_seconds)).isoformat(),
    )


# Plan identifiers ------------------------------------------------------------------


def test_a_plan_identifier_is_random_and_opaque() -> None:
    first = issue_local_plan_id("install", DIGEST)
    second = issue_local_plan_id("install", DIGEST)

    assert PLAN_ID_PATTERN.match(first)
    assert first != second


def test_a_plan_identifier_encodes_nothing_about_the_release() -> None:
    """Quoting an identifier back proves nothing except that it was offered."""
    plan_id = issue_local_plan_id("install", DIGEST)

    assert DIGEST.removeprefix("sha256:") not in plan_id
    assert not re.search(r"techtree|0\.1\.0", plan_id)


def test_a_plan_cannot_be_minted_without_a_release() -> None:
    with pytest.raises(BootstrapPlanError, match="release digest"):
        issue_local_plan_id("install", "not-a-digest")


# The store ----------------------------------------------------------------------------


def test_a_stored_plan_can_be_required_back() -> None:
    store = InstallPlanStore()
    plan = _plan()
    store.save(plan)

    assert require_install_plan(store, plan.plan_id, release_core_digest=DIGEST) == plan


def test_an_unknown_identifier_is_refused() -> None:
    with pytest.raises(BootstrapPlanError) as raised:
        require_install_plan(
            InstallPlanStore(), "install_" + "0" * 32, release_core_digest=DIGEST
        )

    assert raised.value.code == "bootstrap_install_plan_missing"


def test_an_expired_plan_is_refused_and_forgotten() -> None:
    store = InstallPlanStore()
    plan = _plan(expires_in_seconds=-1)
    store.save(plan)

    with pytest.raises(BootstrapPlanError) as raised:
        require_install_plan(store, plan.plan_id, release_core_digest=DIGEST)

    assert raised.value.code == "bootstrap_install_plan_expired"
    assert store.get(plan.plan_id) is None


def test_a_plan_for_another_release_is_refused_and_forgotten() -> None:
    store = InstallPlanStore()
    plan = _plan(release_core_digest="sha256:" + "9" * 64)
    store.save(plan)

    with pytest.raises(BootstrapPlanError) as raised:
        require_install_plan(store, plan.plan_id, release_core_digest=DIGEST)

    assert raised.value.code == "bootstrap_release_mismatch"
    assert store.get(plan.plan_id) is None


def test_pruning_keeps_what_is_still_offered() -> None:
    store = InstallPlanStore()
    store.save(_plan(expires_in_seconds=-1))
    store.save(_plan())

    assert store.prune_expired(datetime.now(UTC)) == 1
    assert store.count() == 1


# Confirmation indicators --------------------------------------------------------------


def test_no_confirmation_indicator_is_invented() -> None:
    """Hermes 0.20.0 documents none, so the plugin claims none."""
    assert DOCUMENTED_CONFIRMATION_KEYS == ()


def test_a_forged_confirmation_field_is_simply_ignored() -> None:
    """A model writing "user_confirmed" does not make it so, or grant anything."""
    require_user_confirmed_tool_context({"user_confirmed": True})
    require_user_confirmed_tool_context({})


def test_a_documented_indicator_that_says_no_stops_the_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import techtree_hermes.approvals as approvals

    monkeypatch.setattr(approvals, "DOCUMENTED_CONFIRMATION_KEYS", ("confirmed",))

    approvals.require_user_confirmed_tool_context({"confirmed": True})
    with pytest.raises(ApprovalRequiredError):
        approvals.require_user_confirmed_tool_context({"confirmed": False})


# Run acceptance -----------------------------------------------------------------------


def test_start_arguments_carry_the_token_and_the_exact_policy() -> None:
    arguments = policy_acceptance_args(
        draft_id="draft_" + "0" * 32,
        confirmation_token="token-the-cli-issued",
        data_policy_digest=POLICY_DIGEST,
    )

    assert arguments == [
        "draft_" + "0" * 32,
        "--confirmation-token",
        "token-the-cli-issued",
        "--accept-data-policy",
        POLICY_DIGEST,
    ]


@pytest.mark.parametrize(
    "missing",
    ["draft_id", "confirmation_token", "data_policy_digest"],
)
def test_a_run_cannot_start_with_a_piece_of_the_approval_missing(
    missing: str,
) -> None:
    arguments = {
        "draft_id": "draft_" + "0" * 32,
        "confirmation_token": "token-the-cli-issued",
        "data_policy_digest": POLICY_DIGEST,
    }
    arguments[missing] = ""

    with pytest.raises(ApprovalRequiredError):
        policy_acceptance_args(**arguments)


def test_a_policy_must_be_named_by_its_exact_digest() -> None:
    """Never infer acceptance, and never accept a description of a policy."""
    with pytest.raises(ApprovalRequiredError, match="exact digest"):
        policy_acceptance_args(
            draft_id="draft_" + "0" * 32,
            confirmation_token="token-the-cli-issued",
            data_policy_digest="the one it showed me",
        )


# The guided revision's disclosure ---------------------------------------------------
#
# Decision 0018 section 5. Every other approval here gates something that
# changes the machine or spends money. This one gates text leaving for a model
# provider, which is quieter and easier to miss.


def test_the_disclosure_says_every_thing_it_has_to_say() -> None:
    """Decision 0018 fixes the elements; the wording is ours."""
    said = " ".join(GUIDED_REVISION_DISCLOSURE).lower()

    assert "verified starter skill" in said
    assert "model provider configured for host hermes" in said
    for withheld in (
        "raw episodes",
        "traces",
        "hidden answers",
        "proof bundles",
        "private keys",
        "provider credentials",
    ):
        assert withheld in said, withheld
    assert "one model-generation request" in said
    assert "may be unusable or may fail to improve the score" in said


def test_the_disclosure_never_promises_a_result() -> None:
    """The approved framing is may-fail. Never "will fix", never "closes"."""
    said = " ".join(GUIDED_REVISION_DISCLOSURE).lower()

    for promise in (
        "your agent will fix",
        "learns from its mistakes",
        "close the gap",
        "will improve",
        "guarantee",
    ):
        assert promise not in said, promise


def test_an_offer_carries_the_disclosure_and_a_token() -> None:
    store = DisclosureStore()

    offer = store.offer(RUN_ID).to_dict()

    assert offer["source_run_id"] == RUN_ID
    assert offer["disclosure"] == list(GUIDED_REVISION_DISCLOSURE)
    assert len(offer["confirmation_token"]) >= 16
    assert store.count() == 1


def test_nothing_is_confirmed_that_was_never_offered() -> None:
    """The first half of the gate: no offer, no request."""
    with pytest.raises(ApprovalRequiredError, match="nobody has been shown") as raised:
        require_confirmed_disclosure(DisclosureStore(), RUN_ID, token="x" * 32)

    assert raised.value.code == "guided_revision_not_confirmed"


def test_a_token_from_another_run_confirms_nothing() -> None:
    """An acceptance is for the run it was shown against, and no other."""
    store = DisclosureStore()
    offer = store.offer(RUN_ID)
    other = "run_" + "9" * 32

    with pytest.raises(ApprovalRequiredError, match="nobody has been shown"):
        require_confirmed_disclosure(store, other, token=offer.token)


def test_a_wrong_token_confirms_nothing() -> None:
    store = DisclosureStore()
    store.offer(RUN_ID)

    with pytest.raises(ApprovalRequiredError, match="not the confirmation"):
        require_confirmed_disclosure(store, RUN_ID, token="z" * 32)

    assert store.count() == 1, "a wrong guess must not consume the offer"


def test_the_acceptance_is_single_use() -> None:
    """A token cannot confirm two requests. Section 7.7's rule, applied here."""
    store = DisclosureStore()
    offer = store.offer(RUN_ID)

    assert require_confirmed_disclosure(store, RUN_ID, token=offer.token) == offer
    assert store.count() == 0

    with pytest.raises(ApprovalRequiredError, match="nobody has been shown"):
        require_confirmed_disclosure(store, RUN_ID, token=offer.token)


def test_a_fresh_offer_replaces_a_stale_one() -> None:
    """Showing it again invalidates the token nobody acted on."""
    store = DisclosureStore()
    stale = store.offer(RUN_ID)
    fresh = store.offer(RUN_ID)

    assert stale.token != fresh.token
    with pytest.raises(ApprovalRequiredError, match="not the confirmation"):
        require_confirmed_disclosure(store, RUN_ID, token=stale.token)


def test_offers_live_only_in_memory() -> None:
    """Two sessions do not share an acceptance."""
    first, second = DisclosureStore(), DisclosureStore()
    offer = first.offer(RUN_ID)

    with pytest.raises(ApprovalRequiredError, match="nobody has been shown"):
        require_confirmed_disclosure(second, RUN_ID, token=offer.token)
