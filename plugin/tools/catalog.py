"""Readiness and catalog reading tools. Specification section 7.11."""

from __future__ import annotations

from typing import Any

from ..bootstrap import doctor_summary
from ..errors import PluginError
from . import channel_of, passthrough, require_argument, safe_tool, tool_result
from .arguments import require_climb_reference


@safe_tool
def techtree_system_check(services: Any, args: dict[str, Any], **kwargs: Any) -> str:
    """Run Techtree's Doctor, and report the release check beside it."""
    channel = channel_of(args, kwargs)
    doctor = doctor_summary(services)
    try:
        release = services.bridge.verify_release(services.release_core)
        release_check = {
            "id": "cli_release",
            "label": "Techtree release",
            "status": "pass" if release["compatible"] else "fail",
            "detail": (
                "the installed Techtree belongs to this plugin's release"
                if release["compatible"]
                else "the installed Techtree belongs to a different release: "
                + ", ".join(release["mismatches"])
            ),
            "blocking": not release["compatible"],
            "metadata": {"mismatches": release["mismatches"]},
        }
    except PluginError as error:
        release_check = {
            "id": "cli_release",
            "label": "Techtree release",
            "status": "fail",
            "detail": str(error),
            "blocking": True,
            "metadata": {},
        }

    checks = [release_check, *doctor.get("checks", [])]
    blocking = [check for check in checks if check.get("blocking")]
    return tool_result(
        {
            "ok": not blocking,
            "command": "doctor",
            "checks": checks,
            "blocking_failures": blocking,
            "can_prepare_demo": not blocking,
            "messages": doctor.get("messages", []),
            "warnings": doctor.get("warnings", []),
            "next_action": (
                {
                    "id": "resolve_doctor_failures",
                    "label": "Resolve what Doctor reported before running a Climb",
                    "reason": "; ".join(str(check.get("detail")) for check in blocking),
                }
                if blocking
                else {
                    "id": "inspect_climbs",
                    "label": "Inspect the Hello World Climb",
                    "reason": "Nothing here blocks a Climb on this machine.",
                    "tool": "techtree_climbs_list",
                }
            ),
        },
        channel,
    )


@safe_tool
def techtree_climbs_list(services: Any, args: dict[str, Any], **kwargs: Any) -> str:
    """List the Climbs this Techtree build offers."""
    channel = channel_of(args, kwargs)
    return passthrough(services.bridge.invoke(["climb", "list"]), channel)


@safe_tool
def techtree_climb_inspect(services: Any, args: dict[str, Any], **kwargs: Any) -> str:
    """Show what one Climb measures, and whether this host can run it."""
    channel = channel_of(args, kwargs)
    reference = require_climb_reference(require_argument(args, "reference"))
    return passthrough(services.bridge.invoke(["climb", "show", reference]), channel)
