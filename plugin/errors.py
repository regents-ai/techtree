"""Plugin-local errors and output scrubbing. Specification sections 7.4, 12.

The plugin does not restate Techtree's error taxonomy. When the CLI produced a
failure, its envelope is preserved as-is; the codes here belong to the bridge,
bootstrap, release, and state layers that live on this side of the boundary.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Final

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


# Scrubbing -------------------------------------------------------------------

_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    re.DOTALL,
)
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_QUOTED_SECRET = re.compile(
    r"(?i)(\"[A-Za-z0-9_.-]*"
    r"(?:api[_-]?key|secret|token|password|passphrase|credential)"
    r"[A-Za-z0-9_.-]*\"\s*:\s*)\"[^\"]*\""
)
_ENV_SECRET = re.compile(
    r"(?i)\b([A-Z0-9_]*"
    r"(?:API_KEY|APIKEY|SECRET|TOKEN|PASSWORD|PASSPHRASE|CREDENTIAL)"
    r"[A-Z0-9_]*)\s*=\s*\S+"
)
_PROVIDER_TOKEN = re.compile(
    r"\b(?:sk|rk|pk)-[A-Za-z0-9_-]{12,}"
    r"|\bgh[pousr]_[A-Za-z0-9]{16,}"
    r"|\bxox[abprs]-[A-Za-z0-9-]{10,}"
)
#: Credentials written into a URL. A private package index is the way this
#: actually reaches a log: `https://user:token@index.example/simple` appears
#: verbatim in an installer's own output, and the token in it is a real one
#: however ordinary the line around it looks.
_URL_CREDENTIALS = re.compile(r"(?i)(\b[a-z][a-z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@")

REDACTED: Final = "[redacted]"


def scrub_text(value: str) -> str:
    """Remove Bearer tokens, quoted secret keys, provider tokens, private keys.

    Scrubbing is applied to every piece of borrowed text the plugin repeats:
    CLI stderr, exception messages, error detail, and diagnostics. It replaces
    the value and keeps the surrounding shape, so an operator can still see
    which credential was involved without seeing the credential.
    """
    scrubbed = _PRIVATE_KEY_BLOCK.sub("[redacted private key]", value)
    scrubbed = _BEARER.sub(f"Bearer {REDACTED}", scrubbed)
    scrubbed = _QUOTED_SECRET.sub(rf'\1"{REDACTED}"', scrubbed)
    scrubbed = _ENV_SECRET.sub(rf"\1={REDACTED}", scrubbed)
    scrubbed = _URL_CREDENTIALS.sub(rf"\1{REDACTED}@", scrubbed)
    return _PROVIDER_TOKEN.sub(REDACTED, scrubbed)


def scrub_borrowed(value: Any) -> Any:
    """Return a document with every string in it scrubbed, structure intact.

    Used on text the plugin did not write and is about to repeat. Techtree
    sanitizes its own error messages, and this does not assume it: an error's
    ``details`` is a free-shaped object built from whatever failed, and the
    thing that failed is often an installer quoting a command line back.
    """
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, Mapping):
        return {key: scrub_borrowed(item) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub_borrowed(item) for item in value]
    return value


def contains_secret_material(value: str) -> bool:
    """Whether this text carries something that looks like a credential.

    Used on files the plugin is about to read out to a model or ship in a
    release. It is deliberately the same set of patterns the scrubber uses:
    one definition of "this looks like a secret", checked in both directions.
    """
    return scrub_text(value) != value


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

    message = scrub_text(str(error)) or error.__class__.__name__
    payload: dict[str, object] = {
        "code": code,
        "message": message,
        "retryable": retryable,
    }
    if repair is not None:
        payload["next_actions"] = [{"id": code, "label": repair}]
    return payload
