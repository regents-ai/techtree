"""Approval artifacts and the rules that keep them honest. Section 7.7.

Two different approvals meet here, and neither one is the plugin's to give.

Installing the Techtree CLI changes software on the user's machine, so it
happens by handing the host a fixed command and letting the host's own
approval surface ask the human. The plugin's part is an install plan: an
opaque identifier, a short life, and one argv nobody can edit.

Starting a run spends money, so Techtree itself demands a one-time
confirmation token and an exact DataPolicy digest. The plugin passes both
through unchanged. It never invents them, never remembers them after use, and
never treats a model's say-so as acceptance.
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


def policy_acceptance_args(
    *,
    draft_id: str,
    confirmation_token: str,
    data_policy_digest: str,
) -> list[str]:
    """Build the exact start arguments for explicit machine-mode acceptance.

    Techtree enforces this, not the plugin: a start without the one-time token
    and the exact DataPolicy digest is refused by the CLI. These arguments
    carry what the user was shown and agreed to, and nothing else.
    """
    if not draft_id or not confirmation_token or not data_policy_digest:
        raise ApprovalRequiredError(
            "a run cannot start without a draft, its confirmation token, and "
            "the exact data policy the user accepted"
        )
    if not DIGEST_PATTERN.match(data_policy_digest):
        raise ApprovalRequiredError(
            "the accepted data policy must be named by its exact digest"
        )
    return [
        draft_id,
        "--confirmation-token",
        confirmation_token,
        "--accept-data-policy",
        data_policy_digest,
    ]


def _expiry(plan: BootstrapInstallPlan) -> datetime:
    try:
        return datetime.fromisoformat(plan.expires_at)
    except ValueError as error:
        raise BootstrapPlanError(
            "that installation plan has no readable expiry"
        ) from error


# Second-run review ----------------------------------------------------------------
#
# Specification section 16's binding rule: no second run starts without the
# diff and the policy having been displayed. That is enforced the same way
# installation is — the plugin remembers what it actually showed, and starting
# requires quoting it back.


CODE_SECOND_RUN_NOT_REVIEWED: Final = "second_run_not_reviewed"


@dataclass(frozen=True)
class DisplayedReview:
    """What was put in front of a person before a second comparison."""

    draft_id: str
    diff_digest: str
    data_policy_digest: str
    displayed_at: str


@dataclass
class ReviewStore:
    """The reviews this conversation has actually shown.

    In memory, for the life of the session, for the same reason install offers
    are: a diff shown in a conversation last week is not a diff this
    conversation showed, and starting a run that spends money on the strength
    of it would be a lie about what the person agreed to.
    """

    _reviews: dict[str, DisplayedReview] = field(default_factory=dict)

    def save(self, review: DisplayedReview) -> None:
        """Record that this draft's diff and policy were displayed."""
        self._reviews[review.draft_id] = review

    def get(self, draft_id: str) -> DisplayedReview | None:
        """Return what was displayed for this draft, if anything was."""
        return self._reviews.get(draft_id)

    def discard(self, draft_id: str) -> None:
        """Forget a review once it has been acted on."""
        self._reviews.pop(draft_id, None)

    def count(self) -> int:
        """How many reviews are currently held."""
        return len(self._reviews)


def require_displayed_review(
    store: ReviewStore, draft_id: str, *, data_policy_digest: str
) -> DisplayedReview:
    """Return the review that was shown for this draft, or refuse the start.

    Raises:
        ApprovalRequiredError: when nothing was displayed for this draft, or
            when the policy being accepted is not the policy that was shown.
    """
    review = store.get(draft_id)
    if review is None:
        raise ApprovalRequiredError(
            "nobody has been shown the difference between the two Skills and "
            "the data policy for this comparison yet",
            code=CODE_SECOND_RUN_NOT_REVIEWED,
            repair="Run techtree_uplift_propose and show its diff first.",
        )
    if review.data_policy_digest != data_policy_digest:
        raise ApprovalRequiredError(
            "the data policy being accepted is not the one that was shown",
            code=CODE_SECOND_RUN_NOT_REVIEWED,
            repair="Show the policy from the proposal, and accept that digest.",
        )
    return review


# The guided revision's disclosure ---------------------------------------------------
#
# Decision 0018 section 5. Every other approval in this file gates something
# that changes the machine or spends money. This one gates something quieter
# and easier to miss: text leaving for a model provider. The Skill being
# revised and a summary of how it did go to whatever provider Host Hermes is
# configured with — a different provider from the one the evaluated run uses,
# and one the person may not have thought about at all.
#
# So it is gated the way the second run is: the plugin composes the
# disclosure, hands it back, remembers that it did, and refuses to compose or
# send anything until that offer is quoted back to it. The offer is single-use
# and dies with the session.
#
# What this cannot prove is that a human read it. No plugin can. What it does
# prove is that the disclosure reached the conversation before the request
# did, and that a second revision cannot ride in on the first one's consent.

CODE_REVISION_NOT_CONFIRMED: Final = "guided_revision_not_confirmed"

#: What the person is told before the one request is composed. Decision 0018
#: fixes the elements; the wording is ours, and it never promises a result.
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


@dataclass(frozen=True)
class OfferedDisclosure:
    """A guided-revision disclosure this conversation actually showed."""

    source_run_id: str
    token: str
    offered_at: str

    def to_dict(self) -> dict[str, Any]:
        """Return the offer in the shape a tool result carries it."""
        return {
            "source_run_id": self.source_run_id,
            "confirmation_token": self.token,
            "offered_at": self.offered_at,
            "disclosure": list(GUIDED_REVISION_DISCLOSURE),
        }


@dataclass
class DisclosureStore:
    """The guided-revision disclosures this session has put in front of a person.

    In memory and single-use, for the same reason the other two stores are: an
    acceptance given in an earlier conversation is not an acceptance in this
    one, and an acceptance already spent is not an acceptance again.
    """

    _offers: dict[str, OfferedDisclosure] = field(default_factory=dict)

    def offer(self, source_run_id: str) -> OfferedDisclosure:
        """Record that the disclosure was shown for this run, and return it."""
        offer = OfferedDisclosure(
            source_run_id=source_run_id,
            token=secrets.token_urlsafe(24),
            offered_at=datetime.now(UTC).isoformat(),
        )
        self._offers[source_run_id] = offer
        return offer

    def get(self, source_run_id: str) -> OfferedDisclosure | None:
        """Return the offer standing for this run, if one is."""
        return self._offers.get(source_run_id)

    def discard(self, source_run_id: str) -> None:
        """Forget an offer, whether it was accepted or abandoned."""
        self._offers.pop(source_run_id, None)

    def count(self) -> int:
        """How many offers are currently held."""
        return len(self._offers)


def require_confirmed_disclosure(
    store: DisclosureStore, source_run_id: str, *, token: str
) -> OfferedDisclosure:
    """Consume the acceptance for this run, or refuse to compose a request.

    The offer is spent whether or not what follows succeeds, so a token cannot
    confirm two requests.

    Raises:
        ApprovalRequiredError: when nothing was offered for this run, or when
            the token quoted back is not the one that was offered.
    """
    offer = store.get(source_run_id)
    if offer is None:
        raise ApprovalRequiredError(
            "nobody has been shown what this step sends to the model provider "
            "for this run yet",
            code=CODE_REVISION_NOT_CONFIRMED,
            repair="Call techtree_uplift_propose without a token to see it.",
        )
    if not secrets.compare_digest(offer.token, token):
        raise ApprovalRequiredError(
            "that is not the confirmation this session offered for this run",
            code=CODE_REVISION_NOT_CONFIRMED,
            repair="Call techtree_uplift_propose without a token to see it.",
        )
    store.discard(source_run_id)
    return offer
