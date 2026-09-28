"""Following and controlling a run. Specification section 7.11.

None of these waits for a benchmark. A Climb takes minutes; a tool call that
sat waiting for one would hold the conversation hostage and time out anyway.
Status is asked for, not awaited.
"""

from __future__ import annotations

from typing import Any

from ..cli.errors import PluginError
from ..host.channels import is_gateway_safe_required
from ..host.state import (
    latest_session,
    reconcile_session_with_cli,
    save_session,
    session_payload,
)
from ..services.approvals import cancel_arguments
from ..services.models import is_success
from ..services.narrative import REPRODUCTION_STATEMENT
from ..services.presentation import PresentationService
from ..services.session import update_after_first_result
from . import channel_of, passthrough, require_argument, safe_tool, tool_result
from .arguments import require_run_id
from .publish import publication_offer


@safe_tool
def techtree_run_status(services: Any, args: dict[str, Any], **kwargs: Any) -> str:
    """Report how a run is progressing, and return straight away."""
    channel = channel_of(args, kwargs)
    run_id = require_run_id(require_argument(args, "run_id"))
    answer = services.bridge.invoke(["run", "status", run_id])

    session = latest_session(services)
    if session is not None:
        save_session(services, reconcile_session_with_cli(services, session))

    if not is_success(answer):
        return passthrough(answer, channel)
    return tool_result(
        {
            **answer,
            "summary": {
                "run_id": run_id,
                "phase": answer.get("phase"),
                "finished": bool(answer.get("terminal")),
                "result_available": bool(answer.get("result_available")),
                "worker_alive": answer.get("worker_alive"),
            },
        },
        channel,
    )


@safe_tool
def techtree_run_cancel(services: Any, args: dict[str, Any], **kwargs: Any) -> str:
    """Stop a run. Only ever called because the user asked for it."""
    channel = channel_of(args, kwargs)
    run_id = require_run_id(require_argument(args, "run_id"))
    return passthrough(
        services.bridge.invoke(["run", "cancel", *cancel_arguments(run_id)]), channel
    )


@safe_tool
def techtree_run_result(services: Any, args: dict[str, Any], **kwargs: Any) -> str:
    """Relay the finished report for a completed run, exactly as Techtree said it.

    Every number here is Techtree's, computed on this machine, and the wording
    around it is Techtree's too: no model is asked to describe a result. The
    result was not independently reproduced by anyone else, and must never be
    described as if it were.
    """
    channel = channel_of(args, kwargs)
    run_id = require_run_id(require_argument(args, "run_id"))
    answer = services.bridge.invoke(["run", "result", run_id])

    session = latest_session(services)
    if session is not None and session.first_run_id == run_id:
        session = update_after_first_result(session, answer)
        save_session(services, session)

    payload: dict[str, Any] = {**answer, "reproduction": REPRODUCTION_STATEMENT}
    # Techtree offers publishing on a result whose proof it checked in this
    # very reading and found sound. The offer is relayed here so a host agent
    # meets it beside the numbers, and it is read out of the answer rather
    # than composed: a result nobody verified carries no offer, so there is
    # none to relay.
    offer = publication_offer(answer, run_id)
    if offer is not None:
        payload["publication_offer"] = offer
    if is_gateway_safe_required(channel):
        # Techtree's answer carries the whole uplift report, the execution
        # record and every per-task row, which on a real Climb is several
        # times what a phone's answer may hold. An answer over that budget is
        # replaced whole by an apology, so leaving them in is how a phone ends
        # up with no result at all rather than a short one. The compact view
        # added below is this channel's copy, and the full one is one terminal
        # command away.
        for name in ("uplift_report", "execution_record", "report"):
            payload.pop(name, None)
    if is_success(answer):
        try:
            payload.update(
                PresentationService().deterministic_only(result=answer, channel=channel)
            )
        except PluginError as error:
            # Techtree answered with something this build cannot compose into a
            # presentation. Its own words are still the honest answer.
            payload["presentation_note"] = str(error)
    if session is not None:
        payload["demo"] = session_payload(session)
    return tool_result(payload, channel)
