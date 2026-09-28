"""Plugin-local errors. Specification sections 7.4, 12.

The plugin does not restate Techtree's error taxonomy. When regents answered
with an error, that answer is preserved as-is; the codes here belong to the
bridge, bootstrap, release, and state layers that live on this side of the
boundary.

A plugin failure answers in the same shape regents does, ``{"error": {...}}``,
so a host agent reads one kind of failure whichever side of the boundary it
came from.

Borrowed text — regents stderr, an exception message, an installer quoting a
command line back — is repeated word for word. Decision 0036 removed the
scrubber that used to edit it: a value's shape is not evidence of what it is,
so nothing here guesses.
"""

from __future__ import annotations

from typing import Final

# Error codes -----------------------------------------------------------------
# Stable strings from specification section 12. Callers compare against these
# rather than against message text.

CODE_PLUGIN_RELEASE_CORE_INVALID: Final = "plugin_release_core_invalid"
CODE_PLUGIN_RELEASE_CORE_MISMATCH: Final = "plugin_release_core_mismatch"
CODE_PLUGIN_STATE_CORRUPT: Final = "plugin_state_corrupt"
CODE_REGENTS_CLI_NOT_FOUND: Final = "regents_cli_not_found"
CODE_REGENTS_CLI_RELEASE_MISMATCH: Final = "regents_cli_release_mismatch"
CODE_CLI_OUTPUT_INVALID: Final = "cli_output_invalid"
CODE_CLI_OUTPUT_TOO_LARGE: Final = "cli_output_too_large"
CODE_CLI_TIMEOUT: Final = "cli_timeout"
CODE_BOOTSTRAP_INSTALL_PLAN_MISSING: Final = "bootstrap_install_plan_missing"
CODE_BOOTSTRAP_INSTALL_NOT_APPROVED: Final = "bootstrap_install_not_approved"
CODE_BOOTSTRAP_TERMINAL_TOOL_UNAVAILABLE: Final = "bootstrap_terminal_tool_unavailable"
CODE_BOOTSTRAP_POST_INSTALL_VERIFY_FAILED: Final = (
    "bootstrap_post_install_verify_failed"
)
CODE_UV_NOT_FOUND: Final = "uv_not_found"
CODE_CHANNEL_INVALID: Final = "channel_invalid"
CODE_UNEXPECTED: Final = "plugin_unexpected_error"


class PluginError(Exception):
    """Base class for every failure the plugin raises on its own behalf.

    Subclasses carry the code, retryability, and repair action that fit their
    layer. A caller may override any of them per raise when one class covers
    several codes from the section 12 taxonomy.
    """

    code: str = CODE_UNEXPECTED
    retryable: bool = False
    repair: str | None = None

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        retryable: bool | None = None,
        repair: str | None = None,
    ) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
        if retryable is not None:
            self.retryable = retryable
        if repair is not None:
            self.repair = repair


class CliNotInstalledError(PluginError):
    """regents is not present on PATH."""

    code = CODE_REGENTS_CLI_NOT_FOUND
    repair = "Run techtree_bootstrap_check to obtain the pinned install plan."


class CliInvocationError(PluginError):
    """regents could not be run, or did not finish in time."""

    code = CODE_CLI_TIMEOUT
    retryable = True


class CliAnswerError(PluginError):
    """regents machine output was not exactly one well-formed JSON answer."""

    code = CODE_CLI_OUTPUT_INVALID
    repair = "Confirm the installed regents matches the pinned release."


class ReleaseMismatchError(PluginError):
    """Embedded release data disagrees with what is installed."""

    code = CODE_PLUGIN_RELEASE_CORE_MISMATCH
    repair = "Reinstall the regents-cli version pinned by this plugin release."


class BootstrapPlanError(PluginError):
    """An install plan is missing, expired, or does not match its identifier."""

    code = CODE_BOOTSTRAP_INSTALL_PLAN_MISSING
    repair = "Run techtree_bootstrap_check again to create a fresh plan."


class ApprovalRequiredError(PluginError):
    """A human approval that the plugin cannot supply for itself is missing."""

    code = CODE_BOOTSTRAP_INSTALL_NOT_APPROVED
    repair = "Approve the displayed command, or run it yourself."


class ChannelError(PluginError):
    """The requested output channel is unknown or unsafe for this result."""

    code = CODE_CHANNEL_INVALID


class PluginStateError(PluginError):
    """Stored plugin state is unreadable or fails its own contract."""

    code = CODE_PLUGIN_STATE_CORRUPT
    repair = "Report the preserved state file; do not delete it."


def safe_error_payload(error: Exception) -> dict[str, object]:
    """Return the ``error`` object: stable code, message, retryability, repair."""
    if isinstance(error, PluginError):
        code = error.code
        retryable = error.retryable
        repair = error.repair
    else:
        code = CODE_UNEXPECTED
        retryable = False
        repair = None

    message = str(error) or error.__class__.__name__
    payload: dict[str, object] = {
        "code": code,
        "message": message,
        "retryable": retryable,
    }
    if repair is not None:
        payload["repair"] = repair
    return payload
