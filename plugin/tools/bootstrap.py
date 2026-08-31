"""Readiness and installation tools. Specification section 7.11."""

from __future__ import annotations

from typing import Any

from ..cli.bootstrap import bootstrap_check, install_cli_with_approval
from ..services.approvals import require_user_confirmed_tool_context
from . import channel_of, require_argument, safe_tool, tool_result


@safe_tool
def techtree_bootstrap_check(services: Any, args: dict[str, Any], **kwargs: Any) -> str:
    """Report what this host has, and the one next step. Installs nothing."""
    channel = channel_of(args, kwargs)
    include_doctor = args.get("include_doctor", True)
    result = bootstrap_check(services, include_doctor=bool(include_doctor))
    return tool_result({"ok": True, "command": "bootstrap check", **result}, channel)


@safe_tool
def techtree_bootstrap_install(
    services: Any, args: dict[str, Any], **kwargs: Any
) -> str:
    """Install the pinned Techtree release, through the host's own approval."""
    channel = channel_of(args, kwargs)
    require_user_confirmed_tool_context(kwargs)
    plan_id = require_argument(args, "plan_id")
    result = install_cli_with_approval(services.ctx, services, plan_id=plan_id)
    return tool_result(
        {"ok": bool(result.get("installed")), "command": "bootstrap install", **result},
        channel,
    )
