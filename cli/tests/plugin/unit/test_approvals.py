"""Approvals are carried, never manufactured. Specification section 7.7."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import pytest
from techtree_hermes.approvals import (
    DOCUMENTED_CONFIRMATION_KEYS,
    GUIDED_REVISION_DISCLOSURE,
    POLICY_ACKNOWLEDGEMENT_METHOD,
    REVIEWED_ON_HOST_AGENT,
    InstallPlanStore,
    issue_local_plan_id,
    require_install_plan,
    require_user_confirmed_tool_context,
    run_approved_event,
    start_arguments,
)
from techtree_hermes.errors import ApprovalRequiredError, BootstrapPlanError
from techtree_hermes.models import PLAN_ID_PATTERN, BootstrapInstallPlan

DIGEST = "sha256:" + "a" * 64
RUN_ID = "run_" + "0" * 32
DRAFT_ID = "draft_" + "0" * 32
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


# Starting a run a person already approved --------------------------------------------
#
# Decision 0019 s2 took the confirmation token and the policy digest off the
# command line. What the plugin passes now is the draft and an explicit flag,
# and the flag means "the review already happened, somewhere a model could not
# answer it".


def test_start_arguments_are_the_draft_the_flag_and_the_surface() -> None:
    assert start_arguments(DRAFT_ID) == [
        DRAFT_ID,
        "--yes",
        "--reviewed-on",
        "host-agent",
    ]


def test_the_run_records_the_surface_the_person_actually_answered_on() -> None:
    """One fact, two records, same meaning.

    Techtree writes the run's own PolicyAcknowledgement from the surface the
    plugin declares, and the plugin writes its own audit event from the same
    constant. Without the declaration the run would say `explicit_cli_review`
    — true of the flag the command line saw, false about the person.
    """
    assert "--reviewed-on" in start_arguments(DRAFT_ID)
    assert REVIEWED_ON_HOST_AGENT == "host-agent"
    assert POLICY_ACKNOWLEDGEMENT_METHOD == "host_agent_confirmation"

    event = run_approved_event(draft_id=DRAFT_ID, draft_digest=DIGEST)
    assert event["policy_acknowledgement_method"] == POLICY_ACKNOWLEDGEMENT_METHOD
    # The two spellings are the same fact in the two vocabularies: the flag
    # value Techtree takes, and the method name it records for it.
    assert REVIEWED_ON_HOST_AGENT.replace("-", "_") in POLICY_ACKNOWLEDGEMENT_METHOD


def test_a_run_cannot_start_without_a_draft() -> None:
    with pytest.raises(ApprovalRequiredError, match="without a draft"):
        start_arguments("")


def test_no_token_or_policy_digest_reaches_the_command_line() -> None:
    """The arguments that carried them are gone, not merely unused."""
    import techtree_hermes.approvals as approvals

    assert not hasattr(approvals, "policy_acceptance_args")
    for argument in start_arguments(DRAFT_ID):
        assert "--confirmation-token" not in argument
        assert "--accept-data-policy" not in argument


# The guided revision's disclosure ---------------------------------------------------
#
# Decision 0019 s2 replaced the token machinery with Hermes's native approval
# surface. The disclosure content survives verbatim, because what a person is
# told before the request is composed was never the part that was wrong.


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


def test_the_plugin_issues_no_approval_of_its_own() -> None:
    """Hard cutover: the token machinery is gone, not merely unused.

    A store the plugin can consult to decide whether a person agreed is a
    store a model can talk the plugin into consulting. Its absence is the
    property, so its absence is what is checked.
    """
    import techtree_hermes.approvals as approvals

    for removed in (
        "DisclosureStore",
        "OfferedDisclosure",
        "require_confirmed_disclosure",
        "ReviewStore",
        "DisplayedReview",
        "require_displayed_review",
    ):
        assert not hasattr(approvals, removed), removed


# The audit fact ----------------------------------------------------------------------


def test_the_approval_event_is_an_ordinary_run_event() -> None:
    """Decision 0019 s2: a fact about what happened, not an artifact to verify."""
    event = run_approved_event(draft_id=DRAFT_ID, draft_digest=DIGEST)

    assert event["kind"] == "run.approved"
    assert event["draft_id"] == DRAFT_ID
    assert event["draft_digest"] == DIGEST
    assert event["actor"] == "human_via_hermes"
    assert event["policy_acknowledgement_method"] == "host_agent_confirmation"
    datetime.fromisoformat(event["approved_at"])

    # Nothing in it is a secret, a signature, or a token.
    assert set(event) == {
        "kind",
        "draft_id",
        "draft_digest",
        "actor",
        "policy_acknowledgement_method",
        "approved_at",
    }


def test_an_unnamed_draft_digest_is_recorded_absent_not_invented() -> None:
    event = run_approved_event(draft_id=DRAFT_ID, draft_digest=None)

    assert event["draft_digest"] is None
    assert event["draft_id"] == DRAFT_ID
