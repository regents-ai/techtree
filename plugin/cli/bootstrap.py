"""Installing Techtree, once a person has said yes. Section 7.6, decision 0007.

A plugin cannot install itself, and it must not install anything else behind
the user's back either. So this module never runs an installer. It reports
what is missing, builds one exact command out of release data, and hands that
command to the host, where the user's own approval surface decides.

Four rules hold the whole flow up:

* The command is generated, never authored. Package, version, and every flag
  come from the release document; there is no argument a model or a tool
  caller can supply that changes any of them.
* Nothing installs without a human. Installation goes through the host's
  ordinary terminal tool, which asks. When that path is unavailable the
  plugin prints the command for the user to run — it never falls back to
  running the command itself.
* What may be installed is settled by the release document being a valid one.
  Every coordinate in it is concrete (Techtree decisions document 0026), so
  there is no state in which the plugin holds a release it must refuse to
  install; the website's own bootstrap validation is what decides whether a
  release is published.
* Missing ``uv`` is a prerequisite the user resolves. The plugin does not pipe
  a remote script into a shell, and does not pick a package manager for them.

After an installation the plugin checks what actually landed: the CLI runs,
its release matches this build, and Techtree's own Doctor agrees the machine
is ready.
"""

from __future__ import annotations

import shlex
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from shutil import which
from typing import Any, Final

from ..services.approvals import (
    INSTALL_PLAN_KIND,
    issue_local_plan_id,
    require_install_plan,
)
from ..services.models import (
    INSTALLER_EXECUTABLE,
    BootstrapInstallPlan,
    PluginAction,
    ReleaseCore,
)
from .bridge import PathLookup, read_cli_version, resolve_techtree_binary
from .constants import (
    CLI_DISTRIBUTION_NAME,
    CLI_PYTHON_SERIES,
    INSTALL_PLAN_TTL_SECONDS,
    PLUGIN_VERSION,
)
from .errors import (
    CODE_BOOTSTRAP_POST_INSTALL_VERIFY_FAILED,
    CODE_BOOTSTRAP_TERMINAL_TOOL_UNAVAILABLE,
    CODE_TECHTREE_CLI_NOT_FOUND,
    CODE_UV_NOT_FOUND,
    BootstrapPlanError,
    PluginError,
)

#: The host tool that runs a command in front of the user, with the host's own
#: approval and redaction. The plugin dispatches to it and never around it.
TERMINAL_TOOL: Final = "terminal"

#: The fixed shape of the one installation command, filled in from the release.
#: The interpreter is named rather than left to the installer to choose, so
#: that Techtree lands on a Python it supports on a machine whose default is
#: newer than it supports.
INSTALL_ARGUMENTS: Final = ("tool", "install", "--python", CLI_PYTHON_SERIES)

#: Where a person learns to install uv. The plugin links; it does not fetch.
UV_DOCUMENTATION_URL: Final = "https://docs.astral.sh/uv/getting-started/installation/"

#: Ways to install uv that a person can choose between. The plugin never picks
#: one, never runs one, and never pipes a downloaded script into a shell.
UV_INSTALL_OPTIONS: Final = (
    "With Homebrew: brew install uv",
    "With pipx: pipx install uv",
    f"Any other platform: follow {UV_DOCUMENTATION_URL}",
)

# What is on this machine ------------------------------------------------------


def detect_uv(*, path_lookup: PathLookup = which) -> str | None:
    """Return where uv is, or None."""
    return path_lookup(INSTALLER_EXECUTABLE)


def uv_prerequisite() -> dict[str, Any]:
    """Return what to tell a user who has no uv.

    Instructions, not actions: the choice of package manager belongs to the
    person whose machine it is.
    """
    return {
        "code": CODE_UV_NOT_FOUND,
        "message": (
            "uv is not installed, and Techtree is installed with it. Install "
            "uv the way you normally install developer tools, then check again."
        ),
        "options": list(UV_INSTALL_OPTIONS),
        "documentation_url": UV_DOCUMENTATION_URL,
    }


# The plan -----------------------------------------------------------------------


def create_install_plan(
    release: ReleaseCore,
    *,
    uv_path: str,
    release_core_digest: str,
    now: datetime | None = None,
) -> BootstrapInstallPlan:
    """Construct one fixed argv from release data.

    ``uv_path`` proves uv was found before a plan was offered. The command
    still names ``uv`` rather than its resolved path, because the command is
    also what the user sees and may run themselves.
    """
    if not uv_path:
        raise BootstrapPlanError("no uv was found, so no plan can be offered")

    issued = now or datetime.now(UTC)
    requirement = f"{CLI_DISTRIBUTION_NAME}=={release.cli_version}"
    return BootstrapInstallPlan(
        plan_id=issue_local_plan_id(INSTALL_PLAN_KIND, release_core_digest),
        package=CLI_DISTRIBUTION_NAME,
        version=release.cli_version,
        argv=(INSTALLER_EXECUTABLE, *INSTALL_ARGUMENTS, requirement),
        release_core_digest=release_core_digest,
        requires_confirmation=True,
        created_at=issued.isoformat(),
        expires_at=(issued + timedelta(seconds=INSTALL_PLAN_TTL_SECONDS)).isoformat(),
    )


def display_command(plan: BootstrapInstallPlan) -> str:
    """Return the plan's command as one shell-quoted line, for display.

    The quoting is for the person reading the line and for the host tool that
    will run it. Every part comes from the validated argv; none of it comes
    from a caller, so there is nothing here that quoting has to defend
    against.
    """
    return shlex.join(plan.argv)


def plan_payload(plan: BootstrapInstallPlan) -> dict[str, Any]:
    """Return the plan in the shape a tool result carries it."""
    return {
        "plan_id": plan.plan_id,
        "package": plan.package,
        "version": plan.version,
        "argv": list(plan.argv),
        "command": display_command(plan),
        "requires_confirmation": True,
        "expires_at": plan.expires_at,
    }


def manual_install_response(plan: BootstrapInstallPlan) -> dict[str, Any]:
    """Return the exact command for a user to run themselves."""
    return {
        "installed": False,
        "approval": "manual",
        "code": CODE_BOOTSTRAP_TERMINAL_TOOL_UNAVAILABLE,
        "message": (
            "This session has no approval-bearing terminal, so the plugin will "
            "not run the installation. Run this command yourself, then check "
            "again."
        ),
        "plan": plan_payload(plan),
    }


# Checking, installing, verifying ---------------------------------------------------


def bootstrap_check(
    services: Any,
    *,
    include_doctor: bool = True,
    path_lookup: PathLookup = which,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Report what this host has, and what the one next step is.

    Installs nothing, calls no model, runs no Docker. When Techtree is already
    installed it reads the installed release and, when asked, runs Techtree's
    own Doctor. When Techtree is missing it offers one pinned plan.
    """
    release: ReleaseCore = services.release_core
    digest: str = services.release_core_digest
    uv_path = detect_uv(path_lookup=path_lookup)
    cli_path = resolve_techtree_binary(path_lookup=path_lookup)

    result: dict[str, Any] = {
        "plugin_version": PLUGIN_VERSION,
        "release_core_digest": digest,
        "release": {
            "release_id": release.release_id,
            "cli_version": release.cli_version,
        },
        "uv": {"installed": uv_path is not None, "path": uv_path},
        "cli": {"installed": cli_path is not None, "path": cli_path, "version": None},
        "release_compatibility": {
            "checked": False,
            "compatible": None,
            "mismatches": [],
        },
        "doctor": None,
        "install_plan": None,
    }
    if uv_path is None:
        result["uv"]["prerequisite"] = uv_prerequisite()

    if cli_path is not None:
        result.update(
            _installed_cli_facts(
                services, cli_path=cli_path, include_doctor=include_doctor
            )
        )
        result["next_action"] = _next_action_for_installed(result)
        return result

    if uv_path is None:
        result["next_action"] = PluginAction(
            id="install_uv",
            label="Install uv, then check again",
            reason="Techtree is installed with uv, which this machine does not have.",
            tool="techtree_bootstrap_check",
            requires_user_confirmation=False,
        ).to_dict()
        return result

    plan = create_install_plan(
        release, uv_path=uv_path, release_core_digest=digest, now=now
    )
    services.plans.save(plan)
    result["install_plan"] = plan_payload(plan)
    result["next_action"] = PluginAction(
        id="install_techtree",
        label=f"Install Techtree {plan.version} with: {display_command(plan)}",
        reason=(
            "Techtree is not installed. This command changes software on this "
            "machine, so the user has to approve it."
        ),
        tool="techtree_bootstrap_install",
        arguments={"plan_id": plan.plan_id},
        requires_user_confirmation=True,
    ).to_dict()
    return result


def install_cli_with_approval(
    ctx: Any,
    services: Any,
    *,
    plan_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run the stored plan through the host's own approval, then verify.

    The plan is looked up, not received: the caller supplies an identifier and
    nothing else, so the command that runs is the command that was offered.
    """
    plan = require_install_plan(
        services.plans,
        plan_id,
        release_core_digest=services.release_core_digest,
        now=now,
    )

    # A plan is spent the moment it is acted on, whether the host ran it or
    # handed it to the user. Replaying an identifier can never install twice.
    services.plans.discard(plan_id)

    dispatch = getattr(ctx, "dispatch_tool", None)
    if not callable(dispatch):
        return manual_install_response(plan)

    command = display_command(plan)
    try:
        dispatch(TERMINAL_TOOL, {"command": command})
    except Exception as error:  # the host declined, or has no terminal
        return {
            **manual_install_response(plan),
            "message": (
                "The installation did not run through this host's terminal: "
                f"{error}. Run this command yourself, then "
                "check again."
            ),
        }

    verification = verify_installation(services)
    return {
        "installed": bool(verification["verified"]),
        "approval": "host_terminal",
        "command": command,
        "verification": verification,
        "message": (
            f"Techtree {verification.get('version')} is installed and belongs "
            "to this plugin's release. Next: inspect the Hello World Climb."
            if verification["verified"]
            else "The installation did not verify; Techtree was not confirmed."
        ),
    }


def verify_installation(services: Any) -> dict[str, Any]:
    """Check what actually landed: it runs, it matches, and Doctor agrees."""
    result: dict[str, Any] = {
        "verified": False,
        "version": None,
        "release": None,
        "doctor": None,
        "code": None,
    }

    try:
        result["version"] = services.bridge.version()
    except PluginError as error:
        result["code"] = getattr(error, "code", CODE_TECHTREE_CLI_NOT_FOUND)
        result["message"] = str(error)
        return result

    try:
        release = services.bridge.verify_release(services.release_core)
    except PluginError as error:
        result["code"] = CODE_BOOTSTRAP_POST_INSTALL_VERIFY_FAILED
        result["message"] = str(error)
        return result

    result["release"] = release
    if not release["compatible"]:
        result["code"] = CODE_BOOTSTRAP_POST_INSTALL_VERIFY_FAILED
        result["message"] = (
            "the installed Techtree belongs to a different release: "
            + ", ".join(release["mismatches"])
        )
        return result

    doctor = doctor_summary(services)
    result["doctor"] = doctor
    result["verified"] = True
    return result


def doctor_summary(services: Any) -> dict[str, Any]:
    """Run Techtree's Doctor and summarize what it found.

    Doctor's own words are preserved. What is added is the one judgement the
    plugin needs downstream: whether anything blocking failed, because a
    blocking failure means no demo may be prepared.
    """
    try:
        envelope = services.bridge.invoke(["doctor"])
    except PluginError as error:
        return {
            "ran": False,
            "ok": False,
            "blocking_failures": [],
            "message": str(error),
            "code": getattr(error, "code", None),
        }

    data = envelope.get("data") or {}
    checks = data.get("checks") if isinstance(data, dict) else None
    checks = checks if isinstance(checks, list) else []
    blocking = [
        {
            "id": check.get("id"),
            "label": check.get("label"),
            "detail": check.get("detail"),
        }
        for check in checks
        if isinstance(check, dict) and check.get("blocking")
    ]

    return {
        "ran": True,
        "ok": bool(envelope.get("ok")) and not blocking,
        "checks": checks,
        "blocking_failures": blocking,
        "can_prepare_demo": not blocking,
        "messages": envelope.get("messages", []),
        "warnings": envelope.get("warnings", []),
    }


def _installed_cli_facts(
    services: Any, *, cli_path: str, include_doctor: bool
) -> dict[str, Any]:
    facts: dict[str, Any] = {"cli": {}, "release_compatibility": {}, "doctor": None}

    cli: dict[str, Any] = {"installed": True, "path": cli_path, "version": None}
    try:
        cli["version"] = read_cli_version()
    except PluginError as error:
        cli["message"] = str(error)
    facts["cli"] = cli

    try:
        release = services.bridge.verify_release(services.release_core)
        facts["release_compatibility"] = {
            "checked": True,
            "compatible": bool(release["compatible"]),
            "mismatches": list(release["mismatches"]),
            "installed": release["installed"],
        }
    except PluginError as error:
        facts["release_compatibility"] = {
            "checked": False,
            "compatible": None,
            "mismatches": [],
            "message": str(error),
        }

    if include_doctor:
        facts["doctor"] = doctor_summary(services)
    return facts


def _next_action_for_installed(result: Mapping[str, Any]) -> dict[str, Any]:
    compatibility = result["release_compatibility"]
    if compatibility.get("compatible") is False:
        return PluginAction(
            id="release_mismatch",
            label="Install the Techtree version this plugin release pins",
            reason=(
                "The installed Techtree belongs to a different release: "
                + ", ".join(compatibility.get("mismatches", []))
            ),
            requires_user_confirmation=True,
        ).to_dict()

    doctor = result.get("doctor")
    if isinstance(doctor, dict) and doctor.get("blocking_failures"):
        return PluginAction(
            id="resolve_doctor_failures",
            label="Resolve what Doctor reported before running a Climb",
            reason="; ".join(
                str(failure.get("detail")) for failure in doctor["blocking_failures"]
            ),
        ).to_dict()

    return PluginAction(
        id="inspect_climbs",
        label="Browse the Climbs this build offers",
        reason="Techtree is installed and belongs to this plugin's release.",
        tool="techtree_climb_list",
    ).to_dict()
