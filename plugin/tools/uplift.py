"""Reading a run's improvement context, and comparing a revision to it.

Specification section 7.11. These wrap what the CLI already does. The host
model's part — reading the verified Skill text and proposing one revision —
belongs to WP10 and is not exposed here.
"""

from __future__ import annotations

from typing import Any

from ..approvals import policy_acceptance_args
from ..services.session import update_after_second_start
from ..state import latest_session, save_session
from . import passthrough, require_argument, safe_tool
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
    run_id = require_run_id(require_argument(args, "run_id"))
    return passthrough(services.bridge.invoke(["uplift", "context", run_id]))


@safe_tool
def techtree_uplift_prepare(services: Any, args: dict[str, Any], **kwargs: Any) -> str:
    """Prepare a run's Skill against a revision of it. Starts nothing."""
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
    return passthrough(services.bridge.invoke(arguments))


@safe_tool
def techtree_uplift_start(services: Any, args: dict[str, Any], **kwargs: Any) -> str:
    """Start a prepared Skill-against-Skill comparison. Spends model budget."""
    draft_id = require_draft_id(require_argument(args, "draft_id"))
    token = require_confirmation_token(require_argument(args, "confirmation_token"))
    policy = require_digest(
        require_argument(args, "data_policy_digest"), "a data policy digest"
    )

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
    if session is not None and envelope.get("ok"):
        save_session(services, update_after_second_start(session, envelope))

    return passthrough(envelope)
