"""Reading a run's improvement context, and comparing a revision to it.

Specification section 7.11. These wrap what the CLI already does. The host
model's part — reading the verified Skill text and proposing one revision —
belongs to WP10 and is not exposed here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..approvals import (
    DisplayedReview,
    policy_acceptance_args,
    require_displayed_review,
)
from ..channels import is_gateway_safe_required
from ..diff import build_skill_diff
from ..errors import CODE_FOUNDER_SKILL_MISSING, PluginError
from ..llm import HermesHostLlm
from ..services.assets import names_a_founder_skill
from ..services.improvement import ImprovementService
from ..services.proposal import ProposalService
from ..services.session import (
    update_after_proposal,
    update_after_second_prepare,
    update_after_second_start,
)
from ..state import latest_session, save_session, session_payload
from . import channel_of, passthrough, require_argument, safe_tool, tool_result
from .arguments import (
    require_confirmation_token,
    require_digest,
    require_draft_id,
    require_label,
    require_local_path,
    require_run_id,
)


@safe_tool
def techtree_uplift_context(services: Any, args: dict[str, Any], **kwargs: Any) -> str:
    """Export the sanitized improvement context for a finished run."""
    channel = channel_of(args, kwargs)
    run_id = require_run_id(require_argument(args, "run_id"))
    return passthrough(services.bridge.invoke(["uplift", "context", run_id]), channel)


@safe_tool
def techtree_uplift_propose(services: Any, args: dict[str, Any], **kwargs: Any) -> str:
    """Propose one revision, have Techtree prepare it, and stop for review.

    This is where the guided introduction pauses on purpose. Everything up to
    the approval happens here — one host completion, Techtree's own scan and
    preparation, and the deterministic difference between the two Skills — and
    then nothing else happens until a person says yes.
    """
    channel = channel_of(args, kwargs)
    source_run_id = require_run_id(require_argument(args, "source_run_id"))

    session = latest_session(services)
    if session is None:
        raise PluginError(
            "there is no guided comparison in this conversation to improve on",
            code="demo_session_not_found",
        )

    host = _host_model(services)
    if host is None:
        raise PluginError(
            "this host offers no model, so it cannot propose a revision",
            code="host_llm_unavailable",
        )
    # Asked before anything is read or spent. The verified skill-improver text
    # is what steers the one turn (decision 0010), so a build whose release
    # never named that Skill has no turn to offer — and must not consume the
    # session's one attempt saying so.
    if not names_a_founder_skill(services.release_core, "skill-improver"):
        raise PluginError(
            "this plugin build's release has not chosen its skill-improver "
            "Skill yet, so no revision can be proposed",
            code=CODE_FOUNDER_SKILL_MISSING,
            repair="Use a published release of the plugin.",
        )
    improvement = ImprovementService(
        llm=host, release=services.release_core, bridge=services.bridge
    )

    source_skill = improvement.load_source_skill(improvement.get_context(source_run_id))

    try:
        proposal = improvement.propose_once(
            source_run_id=source_run_id, demo_session=session
        )
    except PluginError as error:
        # The turn is spent even when the answer was unusable, so the session
        # has to be saved before the failure is reported. Otherwise a refused
        # proposal would quietly hand back the attempt it just used.
        save_session(services, _spend(session))
        raise error

    # One revision now exists. It is not prepared, and nothing has run.
    session = update_after_proposal(
        proposal.session, proposal_id=proposal.provenance.host_response_digest
    )
    save_session(services, session)

    staged = ProposalService(bridge=services.bridge).write_temporary_skill(
        demo_id=proposal.session.demo_id, output=proposal.output
    )
    try:
        prepared = ProposalService(bridge=services.bridge).prepare_replacement_draft(
            source_run_id=source_run_id, skill_path=staged.entrypoint
        )
    finally:
        # Techtree has its own snapshot, or it refused; either way the
        # plugin's copy has done its job.
        ProposalService(bridge=services.bridge).remove_temporary_skill(staged)

    difference = build_skill_diff(
        v1_text=source_skill.text,
        v2_text=proposal.output.revised_skill_markdown,
        channel=channel,
    )

    session = update_after_second_prepare(session, {"ok": True, "data": prepared})
    save_session(services, session)

    services.reviews.save(
        DisplayedReview(
            draft_id=str(prepared["draft_id"]),
            diff_digest=difference.diff_digest,
            data_policy_digest=str(prepared["data_policy_digest"]),
            displayed_at=datetime.now(UTC).isoformat(),
        )
    )

    written = proposal.output.to_dict()
    # The request accounting is the record of what this attempt did at the
    # provider boundary (decision 0015 s4). A phone has no room for it and no
    # use for it: the one-request promise is kept by the code that made the
    # call, not by the answer that reports it, and a terminal shows the whole
    # record. So it travels where it fits, and is simply absent where it does
    # not — never trimmed into a half-record that reads like a full one.
    accounting: dict[str, Any] | None = proposal.accounting.to_dict()
    if is_gateway_safe_required(channel):
        # The whole revised Skill will not fit in a chat message, and the diff
        # is what an approval actually turns on. The Skill itself is staged in
        # Techtree and readable in a terminal.
        written.pop("revised_skill_markdown", None)
        written["revised_skill_available_in_terminal"] = True
        accounting = None

    return tool_result(
        {
            "ok": True,
            "command": "uplift propose",
            "demo": session_payload(session),
            "proposal": written,
            "provenance": proposal.provenance.to_dict(),
            "request_accounting": accounting,
            "diff": difference.to_dict(),
            "draft_id": prepared["draft_id"],
            "confirmation_token": prepared["confirmation_token"],
            "data_policy_digest": prepared["data_policy_digest"],
            "estimated_episodes": prepared.get("estimated_episodes"),
            "scanner": prepared.get("scanner_findings"),
            "baseline_skill_digest": prepared.get("baseline_skill_digest"),
            "candidate_skill_digest": prepared.get("candidate_skill_digest"),
            "started": False,
            "next_action": {
                "id": "start_second_comparison",
                "label": "Start the second comparison",
                "reason": (
                    "Nothing has run. Show the difference above and the data "
                    "policy, and start only if the user agrees to this exact "
                    "comparison."
                ),
                "tool": "techtree_uplift_start",
                "requires_user_confirmation": True,
            },
        },
        channel,
    )


def _spend(session: Any) -> Any:
    """Return the session with the improvement turn counted as used."""
    from dataclasses import replace

    return replace(
        session,
        revision_attempts=session.revision_attempts + 1,
        updated_at=datetime.now(UTC).isoformat(),
    )


def _host_model(services: Any) -> Any:
    """Return the host's model seam, or None when this host offers none."""
    ctx = getattr(services, "ctx", None)
    return HermesHostLlm(ctx) if getattr(ctx, "llm", None) is not None else None


@safe_tool
def techtree_uplift_prepare(services: Any, args: dict[str, Any], **kwargs: Any) -> str:
    """Prepare a run's Skill against a revision of it. Starts nothing."""
    channel = channel_of(args, kwargs)
    run_id = require_run_id(require_argument(args, "run_id"))
    skill_path = require_local_path(
        require_argument(args, "revised_skill_path"), "revised_skill_path"
    )
    arguments = [
        "uplift",
        "prepare",
        "--from-run",
        run_id,
        "--candidate-skill",
        skill_path,
    ]
    label = args.get("label")
    if isinstance(label, str) and label:
        arguments += ["--label", require_label(label)]
    return passthrough(services.bridge.invoke(arguments), channel)


@safe_tool
def techtree_uplift_start(services: Any, args: dict[str, Any], **kwargs: Any) -> str:
    """Start a prepared Skill-against-Skill comparison. Spends model budget."""
    channel = channel_of(args, kwargs)
    draft_id = require_draft_id(require_argument(args, "draft_id"))
    token = require_confirmation_token(require_argument(args, "confirmation_token"))
    policy = require_digest(
        require_argument(args, "data_policy_digest"), "a data policy digest"
    )
    # Specification section 16: no second run starts without the difference
    # and the policy having been shown. The plugin remembers what it showed.
    require_displayed_review(services.reviews, draft_id, data_policy_digest=policy)

    envelope = services.bridge.invoke(
        [
            "uplift",
            "start",
            *policy_acceptance_args(
                draft_id=draft_id,
                confirmation_token=token,
                data_policy_digest=policy,
            ),
        ]
    )

    session = latest_session(services)
    if envelope.get("ok"):
        services.reviews.discard(draft_id)
        if session is not None:
            save_session(services, update_after_second_start(session, envelope))

    return passthrough(envelope, channel)
