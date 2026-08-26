"""Reading a run's improvement context, and comparing a revision to it.

Specification section 7.11. These wrap what the CLI already does. The host
model's part — reading the verified Skill text and proposing one revision —
belongs to WP10 and is not exposed here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..approvals import run_approved_event, start_arguments
from ..channels import is_gateway_safe_required
from ..diff import build_skill_diff
from ..errors import PluginError
from ..llm import HermesHostLlm, HostCompletionTruncatedError
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
    # Decisions 0018 s5 and 0019 s2. The boundary is Hermes's, not the
    # plugin's: this tool is declared as one a human must confirm, so the call
    # only arrives after a person answered the host's own approval surface.
    # The plugin's job is to make that decision an informed one — the
    # disclosure is in this tool's description, where Hermes shows it — and
    # then to do exactly what was approved and nothing else.
    improvement = ImprovementService(
        llm=host, release=services.release_core, bridge=services.bridge
    )

    source_skill = improvement.load_source_skill(improvement.get_context(source_run_id))
    # The Skill that steers the turn is verified before the turn is spent. A
    # build whose bundled improver is not the one its release names has no
    # turn to offer (decision 0010), and must not consume the session's one
    # attempt saying so.
    improvement.load_skill_improver()

    try:
        proposal = improvement.propose_once(
            source_run_id=source_run_id, demo_session=session
        )
    except HostCompletionTruncatedError:
        # Nothing was written, so this turn produced nothing and measured
        # nothing. The session is left exactly as it was — not saved, not
        # spent — and the attempt is still there. Nothing asks again on the
        # user's behalf: what they get is an honest account of what happened
        # and a decision that is theirs.
        raise
    except PluginError as error:
        # A revision that was produced and cannot be used is still a
        # measurement, so the session has to be saved before the failure is
        # reported. Otherwise a refused proposal would quietly hand back the
        # attempt it just used.
        save_session(services, _spend(session))
        raise error

    # One revision now exists. It is not prepared, and nothing has run.
    session = update_after_proposal(
        proposal.session, proposal_id=proposal.provenance.host_response_digest
    )
    save_session(services, session)

    proposals = ProposalService(bridge=services.bridge)
    staged = proposals.write_temporary_skill(
        demo_id=proposal.session.demo_id, output=proposal.output
    )
    cleanup_failure: str | None = None
    try:
        prepared = proposals.prepare_replacement_draft(
            source_run_id=source_run_id, skill_path=staged.entrypoint
        )
    finally:
        # Techtree has its own snapshot, or it refused; either way the
        # plugin's copy has done its job. If it will not delete, the answer
        # says where it still is rather than leaving it there quietly.
        cleanup_failure = proposals.remove_temporary_skill(staged)

    difference = build_skill_diff(
        v1_text=source_skill.text,
        v2_text=proposal.output.revised_skill_markdown,
        channel=channel,
    )

    session = update_after_second_prepare(session, {"ok": True, "data": prepared})
    save_session(services, session)

    written = proposal.output.to_dict()
    # The request accounting is the record of what this attempt did at the
    # provider boundary (decision 0015 s4). A phone has no room for it and no
    # use for it: the one-request promise is kept by the code that made the
    # call, not by the answer that reports it, and a terminal shows the whole
    # record. So it travels where it fits, and is simply absent where it does
    # not — never trimmed into a half-record that reads like a full one.
    accounting: dict[str, Any] | None = proposal.accounting.to_dict()
    # The draft's digest is what makes "a person approved this exact draft"
    # checkable, and it is 71 characters. A phone starts the draft by its
    # identifier and reads the digest in a terminal; the record it belongs to
    # is the approval event, which is not bounded.
    reviewed: dict[str, Any] = {"draft_digest": prepared["draft_digest"]}
    if is_gateway_safe_required(channel):
        # The whole revised Skill will not fit in a chat message, and the diff
        # is what an approval actually turns on. The Skill itself is staged in
        # Techtree and readable in a terminal.
        written.pop("revised_skill_markdown", None)
        written["revised_skill_available_in_terminal"] = True
        accounting = None
        reviewed = {}

    # Reported only when there is something to report, on every channel: a
    # file of the participant's content left on disk is worth its bytes on a
    # phone, and the ordinary run says nothing because nothing was left.
    staging: dict[str, Any] = (
        {} if cleanup_failure is None else {"staging_cleanup_failed": cleanup_failure}
    )

    return tool_result(
        {
            "ok": True,
            "command": "uplift propose",
            **staging,
            "demo": session_payload(session),
            "proposal": written,
            "provenance": proposal.provenance.to_dict(),
            "request_accounting": accounting,
            "diff": difference.to_dict(),
            "draft_id": prepared["draft_id"],
            **reviewed,
            "data_policy_digest": prepared["data_policy_digest"],
            "estimated_episodes": prepared.get("estimated_episodes"),
            # The most this Campaign declares the second run may cost, read off
            # the replacement draft Techtree just prepared. Decision 0019
            # section 2 puts the budget in the review a paid run is approved
            # from, and this payload is that review for the second run. The
            # figure belongs to the Campaign, so it is carried here rather than
            # written into the words that describe it: a Campaign that declares
            # no maximum arrives with no figure, and none is invented for it.
            "campaign_maximum_usd": prepared.get("campaign_maximum_usd"),
            "scanner": prepared.get("scanner_findings"),
            "baseline_skill_digest": prepared.get("baseline_skill_digest"),
            "candidate_skill_digest": prepared.get("candidate_skill_digest"),
            "started": False,
            "next_action": {
                "id": "start_second_comparison",
                "label": "Start the second comparison",
                "reason": (
                    "Nothing has run. Show the difference above, the data "
                    "policy, and the declared maximum, and start only if the "
                    "user agrees to this exact comparison."
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
    """Start a prepared Skill-against-Skill comparison. Spends real money."""
    channel = channel_of(args, kwargs)
    draft_id = require_draft_id(require_argument(args, "draft_id"))
    # Specification section 16 asks that no second run start without the
    # difference and the policy having been shown. Decision 0019 puts that
    # boundary where it belongs: this tool is one Hermes confirms with a
    # person, naming this exact draft, and the plugin starts that draft and
    # no other. It no longer keeps a record of what it displayed, because a
    # record the plugin checks against itself was never the thing standing
    # between a model and a paid run.

    envelope = services.bridge.invoke(
        [
            "uplift",
            "start",
            *start_arguments(draft_id),
        ]
    )

    session = latest_session(services)
    if envelope.get("ok"):
        if session is not None:
            save_session(services, update_after_second_start(session, envelope))
        return tool_result(
            {
                **envelope,
                "approval": run_approved_event(
                    draft_id=draft_id,
                    draft_digest=_draft_digest(envelope),
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
