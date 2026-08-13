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
