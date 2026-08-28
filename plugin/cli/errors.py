"""Plugin-local errors. Specification sections 7.4, 12.

The plugin does not restate Techtree's error taxonomy. When the CLI produced a
failure, its envelope is preserved as-is; the codes here belong to the bridge,
bootstrap, release, and state layers that live on this side of the boundary.

Borrowed text — CLI stderr, an exception message, an installer quoting a
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
CODE_TECHTREE_CLI_NOT_FOUND: Final = "techtree_cli_not_found"
CODE_TECHTREE_CLI_RELEASE_MISMATCH: Final = "techtree_cli_release_mismatch"
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
CODE_HOST_LLM_UNAVAILABLE: Final = "host_llm_unavailable"
CODE_HOST_LLM_OUTPUT_INVALID: Final = "host_llm_output_invalid"
CODE_HOST_PROPOSAL_GENERATION_EXHAUSTED: Final = "host_proposal_generation_exhausted"
#: The host answered, and what came back carried nothing at all: the model
#: reached the end of what it was allowed to write before it wrote a byte.
#: This is not "the host offered no model" and it is not "what the model wrote
#: cannot be used" — it is its own outcome, and the only one where the turn
#: produced nothing to count.
CODE_HOST_COMPLETION_TRUNCATED: Final = "host_completion_truncated"
#: The request left the machine and no answer ever came back. Not "the
#: host offered no model": the host was there and the request was sent.
#: Nothing reached the user either way, so the guided introduction leaves
#: its one attempt where it was, and the wording never claims the
#: provider did not charge — from here that cannot be known.
CODE_HOST_ANSWER_NEVER_ARRIVED: Final = "host_answer_never_arrived"
#: A second completion inside one improvement turn. Decision 0007 and spec
#: section 8.11: the turn is one shot, and a retry would be a hidden second.
CODE_HOST_LLM_ALREADY_COMPLETED: Final = "host_llm_already_completed"
CODE_FOUNDER_SKILL_MISSING: Final = "founder_skill_missing"
CODE_FOUNDER_SKILL_DIGEST_MISMATCH: Final = "founder_skill_digest_mismatch"
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
    """The Techtree CLI is not present on PATH."""

    code = CODE_TECHTREE_CLI_NOT_FOUND
    repair = "Run techtree_bootstrap_check to obtain the pinned install plan."


class CliInvocationError(PluginError):
    """The Techtree CLI could not be run, or did not finish in time."""

    code = CODE_CLI_TIMEOUT
    retryable = True


class CliEnvelopeError(PluginError):
    """CLI machine output was not exactly one well-formed JSON envelope."""

    code = CODE_CLI_OUTPUT_INVALID
    repair = "Confirm the installed CLI matches the pinned release."


class ReleaseMismatchError(PluginError):
    """Embedded release data disagrees with what is installed."""

    code = CODE_PLUGIN_RELEASE_CORE_MISMATCH
    repair = "Reinstall the CLI version pinned by this plugin release."


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
    """Return stable code, safe message, retryability, and repair action."""
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
        payload["next_actions"] = [{"id": code, "label": repair}]
    return payload
