"""Approval artifacts and the rules that keep them honest. Section 7.7.

Two different approvals meet here, and neither one is the plugin's to give.

Installing the Techtree CLI changes software on the user's machine, so it
happens by handing the host a fixed command and letting the host's own
approval surface ask the human. The plugin's part is an install plan: an
opaque identifier, a short life, and one argv nobody can edit.

Starting a run spends money, so it happens on the host's own approval surface,
where a person answers for themselves. The plugin prepares the immutable draft,
says what starting it commits to, and marks the start as a step a human has to
confirm. It never treats a model's say-so as acceptance.
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final

from .errors import (
    CODE_BOOTSTRAP_INSTALL_PLAN_MISSING,
    ApprovalRequiredError,
    BootstrapPlanError,
)
from .models import DIGEST_PATTERN, BootstrapInstallPlan

CODE_BOOTSTRAP_INSTALL_PLAN_EXPIRED: Final = "bootstrap_install_plan_expired"
CODE_BOOTSTRAP_RELEASE_MISMATCH: Final = "bootstrap_release_mismatch"

#: The kind of approval artifact this module issues identifiers for.
INSTALL_PLAN_KIND: Final = "install"

#: Keys a host may use to tell a tool handler that the human confirmed this
#: particular call. Hermes 0.20.0 documents none, so this is empty on purpose:
#: inventing a callback field would mean inventing an approval. The real gate
#: is the host's own terminal approval, which the plugin cannot bypass.
DOCUMENTED_CONFIRMATION_KEYS: Final[tuple[str, ...]] = ()


def issue_local_plan_id(kind: str, digest: str) -> str:
    """Create a random opaque plan identifier.

    The identifier carries no meaning: not the release, not the command, and
    certainly not a secret. It is a lookup key for a plan the plugin already
    holds, so quoting it back proves only that the caller is answering the
    question that was asked.

    Raises:
        BootstrapPlanError: when the release digest it is minted against is
            not a digest, so a plan can never exist without a real release.
    """
    if not DIGEST_PATTERN.match(digest):
        raise BootstrapPlanError(
            "an install plan can only be issued against a release digest"
        )
    if not kind.isalpha():
        raise BootstrapPlanError(f"{kind!r} is not a plan kind")
    return f"{kind}_{secrets.token_hex(16)}"


@dataclass
class InstallPlanStore:
    """The install plans this Hermes session has offered.

    Plans live in memory for the life of the session, which is exactly as long
    as an offer to install something should stand. Nothing here is written to
    disk: a stored approval that outlives the conversation it was granted in
    is not the same approval.
    """

    _plans: dict[str, BootstrapInstallPlan] = field(default_factory=dict)

    def save(self, plan: BootstrapInstallPlan) -> None:
        """Record a plan under its identifier."""
        self._plans[plan.plan_id] = plan

    def get(self, plan_id: str) -> BootstrapInstallPlan | None:
        """Return a plan by identifier, without judging its age."""
        return self._plans.get(plan_id)

    def discard(self, plan_id: str) -> None:
        """Forget a plan, whether it was used or abandoned."""
        self._plans.pop(plan_id, None)

    def prune_expired(self, now: datetime | None = None) -> int:
        """Drop every plan whose offer has run out. Returns how many went."""
        moment = now or datetime.now(UTC)
        expired = [
            plan_id for plan_id, plan in self._plans.items() if _expiry(plan) <= moment
        ]
        for plan_id in expired:
            del self._plans[plan_id]
        return len(expired)

    def count(self) -> int:
        """How many plans are currently held."""
        return len(self._plans)


def require_install_plan(
    store: InstallPlanStore,
    plan_id: str,
    *,
    release_core_digest: str,
    now: datetime | None = None,
) -> BootstrapInstallPlan:
    """Return the one unexpired plan that identifier names.

    Raises:
        BootstrapPlanError: when no such plan was offered, when the offer has
            run out, or when the plan belongs to a different release than the
            one this plugin build carries.
    """
    plan = store.get(plan_id)
    if plan is None:
        raise BootstrapPlanError(
            "that installation plan was not offered by this session",
            code=CODE_BOOTSTRAP_INSTALL_PLAN_MISSING,
            repair="Run techtree_bootstrap_check again to get a fresh plan.",
        )

    moment = now or datetime.now(UTC)
    if _expiry(plan) <= moment:
        store.discard(plan_id)
        raise BootstrapPlanError(
            "that installation plan has expired",
            code=CODE_BOOTSTRAP_INSTALL_PLAN_EXPIRED,
            repair="Run techtree_bootstrap_check again to get a fresh plan.",
        )

    if plan.release_core_digest != release_core_digest:
        store.discard(plan_id)
        raise BootstrapPlanError(
            "that installation plan belongs to a different release",
            code=CODE_BOOTSTRAP_RELEASE_MISMATCH,
            repair="Run techtree_bootstrap_check again to get a fresh plan.",
        )

    return plan


def require_user_confirmed_tool_context(kwargs: Mapping[str, Any]) -> None:
    """Refuse a call the host says the human did not confirm.

    This applies only to indicators the host documents. Hermes 0.20.0 has
    none, so nothing is checked and nothing is assumed: the absence of an
    indicator is never read as approval, and a value that arrives from a model
    is never read as approval either. Installation is gated by the host's own
    terminal approval regardless of what this sees.

    Raises:
        ApprovalRequiredError: when a documented indicator says "not
            confirmed".
    """
    for key in DOCUMENTED_CONFIRMATION_KEYS:
        if key in kwargs and kwargs[key] is not True:
            raise ApprovalRequiredError(
                "the host reports that this call was not confirmed by a person"
            )


def start_arguments(draft_id: str) -> list[str]:
    """Build the exact start arguments for a run a person already approved.

    Decision 0019 section 2 removed the confirmation token and the policy
    digest from the command line. What is left is the draft and an explicit
    flag, and the chain behind that flag is worth stating plainly:

    1. The plugin prepares the immutable draft and shows the exact change,
       the policy summary, and how many episodes it commits to paying for.
    2. Hermes asks the person, on its own approval surface, because the tool
       that starts a run is declared as one a human must confirm.
    3. Only then does Hermes dispatch the call, and the plugin passes ``--yes``
       to say the review already happened.

    ``--yes`` is the non-interactive operator case, and this is that case: no
    one can answer a prompt inside a tool call. It is not a shortcut around
    the question, because the question was already asked somewhere a model
    cannot answer it.

    ``--reviewed-on host-agent`` says *where* it was asked. Without it the run
    would record `explicit_cli_review` — true of the flag the command line
    saw, and false about the person, who answered in a conversation. With it
    the run's own request and this plugin's `run.approved` event say the same
    thing in the same words: one fact, two records, no disagreement for
    anybody to have to reconcile later.

    Raises:
        ApprovalRequiredError: when there is no draft to start.
    """
    if not draft_id:
        raise ApprovalRequiredError("a run cannot start without a draft to start")
    return [draft_id, "--yes", "--reviewed-on", REVIEWED_ON_HOST_AGENT]


def _expiry(plan: BootstrapInstallPlan) -> datetime:
    try:
        return datetime.fromisoformat(plan.expires_at)
    except ValueError as error:
        raise BootstrapPlanError(
            "that installation plan has no readable expiry"
        ) from error


# The approvals the plugin surfaces --------------------------------------------------
#
# Decision 0019 section 2. The boundaries stay and the token machinery goes.
#
# What used to happen here: the plugin minted a one-time token, remembered it,
# and refused to act until the token came back. That put the plugin in the
# position of deciding whether a person had agreed — and a token that arrives
# in a tool call is just an argument, which a model can supply as easily as a
# human can. It was ceremony around a question the plugin cannot answer.
#
# What happens now: the plugin prepares the immutable thing, shows exactly
# what would change, what it commits to paying for, and where anything goes;
# and it marks the
# next step as one a human must confirm. Hermes owns that boundary, asks the
# person, and only then dispatches the call. The model cannot approve its own
# action because approving is not something a tool call can do.
#
# The plugin's remaining job is to make the decision an informed one — say
# what the step does before it is taken — and to record that it was taken.

#: What the person is told before the one revision request is composed.
#: Decision 0018 fixes the elements; the wording is ours, and it never
#: promises a result. Decision 0019 kept this content verbatim and replaced
#: only the mechanism that gated it.
GUIDED_REVISION_DISCLOSURE: Final[tuple[str, ...]] = (
    "This step sends the verified starter Skill and a sanitized summary of how "
    "it did to the model provider configured for Host Hermes — the agent you "
    "are talking to, not the one the evaluated run uses.",
    "It does not send raw Episodes, Traces, hidden answers, proof bundles, "
    "private keys, or provider credentials.",
    "It makes one model-generation request. There is no second attempt.",
    "Your Hermes model will propose one revision. Techtree will test it. A "
    "proposal may be unusable or may fail to improve the score.",
)

#: Who approved, in the one form this plugin can honestly report. The person
#: answered Hermes's own approval surface; the plugin saw the call arrive
#: after it, and says exactly that rather than implying it checked a signature.
APPROVAL_ACTOR: Final = "human_via_hermes"

#: The audit event kind. An ordinary run event — a fact about what happened,
#: not a cryptographic acceptance artifact (decision 0019 section 2).
RUN_APPROVED_EVENT: Final = "run.approved"

#: How the policy was acknowledged on this surface, and the value that tells
#: Techtree to record the same thing. The plugin declares the surface the
#: answer was actually given on, so the run's own PolicyAcknowledgement and
#: this plugin's audit event agree by construction rather than by luck.
POLICY_ACKNOWLEDGEMENT_METHOD: Final = "host_agent_confirmation"
REVIEWED_ON_HOST_AGENT: Final = "host-agent"


def run_approved_event(
    *, draft_id: str, draft_digest: str | None, now: datetime | None = None
) -> dict[str, Any]:
    """Return the audit fact that a human approved starting this exact draft.

    Recorded because it happened, at the moment the approved call arrives.
    ``draft_digest`` is None when Techtree named no digest for the draft: an
    absent value is reported absent rather than invented.
    """
    return {
        "kind": RUN_APPROVED_EVENT,
        "draft_id": draft_id,
        "draft_digest": draft_digest,
        "actor": APPROVAL_ACTOR,
        "policy_acknowledgement_method": POLICY_ACKNOWLEDGEMENT_METHOD,
        "approved_at": (now or datetime.now(UTC)).isoformat(),
    }
