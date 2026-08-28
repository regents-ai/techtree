"""Preparing a comparison, and starting it. Specification section 7.11.

Preparation is free and starts nothing. Starting spends model tokens on
inference, so it happens only with a draft the user was shown and the exact
data policy they accepted.
"""

from __future__ import annotations

from typing import Any

from ..cli.bootstrap import doctor_summary
from ..cli.errors import PluginError
from ..host.state import save_session, session_payload
from ..services.approvals import run_approved_event, start_arguments
from ..services.assets import materialize_starter_skill
from ..services.session import (
    create_demo_session,
    update_after_first_prepare,
    update_after_first_start,
)
from . import channel_of, passthrough, require_argument, safe_tool, tool_result
from .arguments import (
    require_climb_reference,
    require_draft_id,
    require_label,
    require_local_path,
)


@safe_tool
def techtree_demo_prepare(services: Any, args: dict[str, Any], **kwargs: Any) -> str:
    """Walk the introductory Climb up to the point where a person must decide.

    Everything before the approval happens here: the CLI is checked, Doctor
    runs, the founder's starter Skill is materialized and verified, the Climb
    is inspected, and a draft is prepared. Nothing is started, and no model is
    called.
    """
    channel = channel_of(args, kwargs)
    release = services.bridge.verify_release(services.release_core)
    if not release["compatible"]:
        return tool_result(
            {
                "ok": False,
                "command": "demo prepare",
                "blocked": "release_mismatch",
                "message": (
                    "The installed Techtree belongs to a different release: "
                    + ", ".join(release["mismatches"])
                ),
                "release": release,
            },
            channel,
        )

    doctor = doctor_summary(services)
    if not doctor.get("can_prepare_demo"):
        return tool_result(
            {
                "ok": False,
                "command": "demo prepare",
                "blocked": "doctor_blocking_failure",
                "message": "This machine is not ready to run a Climb yet.",
                "doctor": doctor,
            },
            channel,
        )

    try:
        skill = materialize_starter_skill(services)
    except PluginError as error:
        return tool_result(
            {
                "ok": False,
                "command": "demo prepare",
                "blocked": "starter_skill_unavailable",
                "message": str(error),
                "code": error.code,
                "repair": error.repair,
            },
            channel,
        )

    reference = services.release_core.intro_climb_reference
    inspection = services.bridge.invoke(["climb", "show", reference])
    # The label is stated rather than left to default. Techtree keeps a
    # materialized Skill in a directory named by the digest it was verified
    # against, and a candidate left unlabelled is filed under its directory's
    # name — which here is seventy-one characters of hash and means nothing to
    # a reader. The release's own short name for the candidate comes back with
    # the Skill, so it is used.
    prepared = services.bridge.invoke(
        [
            "climb",
            "prepare",
            reference,
            "--skill",
            skill["skill_path"],
            "--label",
            skill["candidate_label"],
        ]
    )
    if not prepared.get("ok"):
        return passthrough(prepared, channel)

    session = create_demo_session(
        release=services.release_core,
        climb_reference=reference,
        release_core_digest=services.release_core_digest,
    )
    session = update_after_first_prepare(session, prepared)
    save_session(services, session)

    data = prepared.get("data") or {}
    return tool_result(
        {
            "ok": True,
            "command": "demo prepare",
            "demo": session_payload(session),
            "climb": inspection.get("data"),
            "draft_id": data.get("draft_id"),
            "draft_digest": data.get("draft_digest"),
            "data_policy_digest": data.get("data_policy_digest"),
            "campaign_spec_digest": data.get("campaign_spec_digest"),
            "skill_root_digest": data.get("skill_root_digest"),
            "starter_skill_digest": skill["skill_root_digest"],
            "estimated_episodes": data.get("estimated_episodes"),
            # The most this Campaign declares it may cost, read off the draft
            # Techtree just prepared. Decision 0019 section 2 puts the budget in
            # this review; the figure belongs to the Campaign, so it is carried
            # here rather than written into the words that describe it.
            "campaign_maximum_usd": data.get("campaign_maximum_usd"),
            "changed_field": "the candidate Skill; everything else is identical",
            "next_action": {
                "id": "start_first_comparison",
                "label": "Start the first comparison",
                "reason": (
                    "This spends model tokens on inference, and no price is "
                    "worked out first. Show the policy, the declared maximum, "
                    "the episode count, and the Skill, and start only if the "
                    "user agrees. The data rights are the terms this Climb "
                    "sets for a published result. Nothing is published "
                    "unless the user publishes a finished run themselves, and "
                    "what travels then is the run's proof — the signed report "
                    "and its receipts — and never the episodes. Their Skill "
                    "and their episodes stay on their machine, and model calls "
                    "still go to the model provider they configured."
                ),
                "tool": "techtree_climb_start",
                "requires_user_confirmation": True,
            },
        },
        channel,
    )


@safe_tool
def techtree_climb_prepare(services: Any, args: dict[str, Any], **kwargs: Any) -> str:
    """Prepare any candidate Skill for a Climb. Free, and starts nothing."""
    channel = channel_of(args, kwargs)
    reference = require_climb_reference(require_argument(args, "reference"))
    skill_path = require_local_path(require_argument(args, "skill_path"), "skill_path")
    arguments = ["climb", "prepare", reference, "--skill", skill_path]
    label = args.get("label")
    if isinstance(label, str) and label:
        arguments += ["--label", require_label(label)]
    return passthrough(services.bridge.invoke(arguments), channel)


@safe_tool
def techtree_climb_start(services: Any, args: dict[str, Any], **kwargs: Any) -> str:
    """Start a prepared draft. Spends model tokens; returns a run identifier."""
    channel = channel_of(args, kwargs)
    draft_id = require_draft_id(require_argument(args, "draft_id"))

    envelope = services.bridge.invoke(
        [
            "climb",
            "start",
            *start_arguments(draft_id),
        ]
    )

    session = _session_for_draft(services, draft_id)
    if envelope.get("ok"):
        if session is not None:
            save_session(services, update_after_first_start(session, envelope))
        # Decision 0019 s2: one ordinary run event recording that a person
        # approved starting this exact draft. A fact about what happened, not
        # an acceptance artifact anybody has to verify.
        return tool_result(
            {
                **envelope,
                "approval": run_approved_event(
                    draft_id=draft_id, draft_digest=_draft_digest(envelope)
                ),
            },
            channel,
        )

    return passthrough(envelope, channel)


def _draft_digest(envelope: Any) -> str | None:
    """Return the digest Techtree named for this draft, or None if it named none."""
    data = envelope.get("data") if isinstance(envelope, dict) else None
    digest = data.get("draft_digest") if isinstance(data, dict) else None
    return digest if isinstance(digest, str) and digest else None


def _session_for_draft(services: Any, draft_id: str) -> Any:
    from ..host.state import load_sessions

    for session in load_sessions(services).values():
        if session.first_draft_id == draft_id:
            return session
    return None
