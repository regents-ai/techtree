"""Following and controlling a run. Specification section 7.11.

None of these waits for a benchmark. A Climb takes minutes; a tool call that
sat waiting for one would hold the conversation hostage and time out anyway.
Status is asked for, not awaited.
"""

from __future__ import annotations

from typing import Any

from ..channels import is_gateway_safe_required
from ..errors import PluginError, scrub_text
from ..narrative import REPRODUCTION_STATEMENT
from ..services.presentation import PresentationService
from ..services.session import update_after_first_result
from ..state import (
    latest_session,
    reconcile_session_with_cli,
    save_session,
    session_payload,
)
from . import channel_of, passthrough, require_argument, safe_tool, tool_result
from .arguments import require_run_id


@safe_tool
def techtree_run_status(services: Any, args: dict[str, Any], **kwargs: Any) -> str:
    """Report how a run is progressing, and return straight away."""
    channel = channel_of(args, kwargs)
    run_id = require_run_id(require_argument(args, "run_id"))
    envelope = services.bridge.invoke(["run", "status", run_id])

    session = latest_session(services)
    if session is not None:
        save_session(services, reconcile_session_with_cli(services, session))

    data = envelope.get("data") or {}
    return tool_result(
        {
            **envelope,
            "summary": {
                "run_id": run_id,
                "phase": data.get("phase"),
                "finished": bool(data.get("terminal")),
                "result_available": bool(data.get("result_available")),
                "worker_alive": data.get("worker_alive"),
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
        services.bridge.invoke(["run", "cancel", run_id, "--confirm"]), channel
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
    envelope = services.bridge.invoke(["run", "result", run_id])

    session = latest_session(services)
    if session is not None and session.first_run_id == run_id:
        session = update_after_first_result(session, envelope)
        save_session(services, session)

    payload: dict[str, Any] = {**envelope, "reproduction": REPRODUCTION_STATEMENT}
    if is_gateway_safe_required(channel):
        # Techtree's envelope carries the whole report and every per-task row,
        # which on a real Climb is several times what a phone's answer may
        # hold. An answer over that budget is replaced whole by an apology, so
        # leaving the raw envelope in is how a phone ends up with no result at
        # all rather than a short one. The compact view added below is this
        # channel's copy of it, and the full one is one terminal command away.
        payload["data"] = None
    if envelope.get("ok"):
        second = session is not None and session.second_run_id == run_id
        try:
            payload.update(
                PresentationService(release=services.release_core).deterministic_only(
                    result_envelope=envelope,
                    channel=channel,
                    comparison="second" if second else "first",
                    source_feedback_report_digest=(
                        _source_feedback_digest(services, session) if second else None
                    ),
                )
            )
        except PluginError as error:
            # Techtree answered with something this build cannot compose into a
            # presentation. Its own words are still the honest answer.
            payload["presentation_note"] = scrub_text(str(error))
    if session is not None:
        payload["demo"] = session_payload(session)
    return tool_result(payload, channel)


def _source_feedback_digest(services: Any, session: Any) -> str | None:
    """Return the digest of the report the revision was written from.

    Decision 0007: a second receipt names its own feedback source, which is
    what makes "the same task membership" a checkable claim rather than a
    disclaimer.
    """
    if session is None or not session.first_run_id:
        return None
    try:
        envelope = services.bridge.invoke(["uplift", "context", session.first_run_id])
    except PluginError:
        return None
    data = envelope.get("data") if isinstance(envelope, dict) else None
    context = data.get("context") if isinstance(data, dict) else None
    digest = context.get("source_report_digest") if isinstance(context, dict) else None
    return digest if isinstance(digest, str) else None
