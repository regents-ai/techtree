"""Plugin-local data models and strict parsers. Specification sections 6, 7.4.

These are local UX and boundary objects. None of them is a signed Techtree
protocol object, and none of them is authoritative about a scientific result:
Techtree's own artifacts remain the only source of truth for that.

Parsing is deliberately unforgiving. Unknown schema versions, unknown fields,
shell-string install instructions, and non-argv commands are rejected rather
than coerced, because everything parsed here decides what the host is asked to
run or trust.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final, Literal

from .constants import SUPPORTED_CLI_SCHEMA, SUPPORTED_RELEASE_CORE_SCHEMA
from .errors import (
    CODE_CLI_OUTPUT_INVALID,
    CODE_PLUGIN_RELEASE_CORE_INVALID,
    BootstrapPlanError,
    CliEnvelopeError,
    PluginError,
)

# Value patterns --------------------------------------------------------------

DIGEST_PATTERN: Final = re.compile(r"^sha256:[0-9a-f]{64}$")
COMMIT_PATTERN: Final = re.compile(r"^[0-9a-f]{40}$")
VERSION_PATTERN: Final = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.+-]{0,63}$")
IDENTIFIER_PATTERN: Final = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._/-]{0,127}$")
# A released Climb reference always pins a version: slug@version.
CLIMB_REFERENCE_PATTERN: Final = re.compile(
    r"^[a-z0-9][a-z0-9-]{0,63}@[0-9A-Za-z.-]{1,16}$"
)
PLAN_ID_PATTERN: Final = re.compile(r"^install_[0-9a-f]{32}$")
ANSI_PATTERN: Final = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[@-Z\\-_]")

# The only installer the plugin will ever name in a plan. Specification
# section 7.6: the plugin does not choose a package manager and never accepts
# an executable name from a model, a tool argument, or release metadata.
INSTALLER_EXECUTABLE: Final = "uv"


# Channel and demo state ------------------------------------------------------


class ChannelKind(StrEnum):
    """Where a tool result is going to be read. Specification section 6.1."""

    TERMINAL = "terminal"
    GATEWAY = "gateway"
    UNKNOWN = "unknown"


class DemoStage(StrEnum):
    """Convenience progress marker. Specification section 6.2.

    This is never scientific truth; it only records how far the guided
    introduction has been walked so a later turn can pick it up.
    """

    PLUGIN_READY = "plugin_ready"
    CLI_INSTALL_REQUIRED = "cli_install_required"
    CLI_READY = "cli_ready"
    FIRST_DRAFT_PREPARED = "first_draft_prepared"
    FIRST_RUN_ACTIVE = "first_run_active"
    FIRST_RESULT_READY = "first_result_ready"
    REVISION_PROPOSAL_READY = "revision_proposal_ready"
    SECOND_DRAFT_PREPARED = "second_draft_prepared"
    SECOND_RUN_ACTIVE = "second_run_active"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class DemoSessionState:
    """Identifiers for one guided introduction. Specification section 6.3.

    Only IDs, digests, and local paths live here: no keys, no used
    confirmation tokens, no Skill text, no Episode data, no task content.
    """

    demo_id: str
    release_core_digest: str
    climb_reference: str
    stage: DemoStage
    first_draft_id: str | None
    first_run_id: str | None
    first_proof_path: str | None
    source_skill_v1_digest: str | None
    proposal_id: str | None
    second_draft_id: str | None
    second_run_id: str | None
    second_proof_path: str | None
    revision_attempts: int
    updated_at: str


# Release --------------------------------------------------------------------

RELEASE_CORE_FIELDS: Final = (
    "schema_version",
    "placeholder_release",
    "placeholder_fields",
    "release_id",
    "cli_version",
    "cli_source_commit",
    "protocol_version",
    "engine_digest",
    "catalog_digest",
    "intro_climb_reference",
    "starter_skill_digest",
    "rich_output_skill_digest",
    "skill_improver_digest",
    "minimum_host_hermes_version",
    "maximum_tested_host_hermes_version",
    "subject_hermes_version",
)

_RELEASE_CORE_STRING_FIELDS: Final = tuple(
    name
    for name in RELEASE_CORE_FIELDS
    if name not in {"placeholder_release", "placeholder_fields"}
)

_RELEASE_CORE_DIGEST_FIELDS: Final = (
    "engine_digest",
    "catalog_digest",
    "starter_skill_digest",
    "rich_output_skill_digest",
    "skill_improver_digest",
)

_RELEASE_CORE_VERSION_FIELDS: Final = (
    "cli_version",
    "protocol_version",
    "minimum_host_hermes_version",
    "maximum_tested_host_hermes_version",
    "subject_hermes_version",
)


@dataclass(frozen=True)
class ReleaseCore:
    """The frozen release the plugin was built against. Section 6.6.

    These are the same bytes the installed CLI ships. Two fields beyond the
    specification's list travel with the document — ``placeholder_release``
    and ``placeholder_fields`` — because a release is generated before a
    person has chosen every coordinate, and a document with plausible blanks
    in it must say so out loud rather than read as a finished release.

    The plugin does not re-derive that declaration. Techtree owns verifying
    its own release document; the plugin reads it, repeats it, and compares
    digests.
    """

    schema_version: Literal["techtree.release-core.v1"]
    placeholder_release: bool
    placeholder_fields: tuple[str, ...]
    release_id: str
    cli_version: str
    cli_source_commit: str
    protocol_version: str
    engine_digest: str
    catalog_digest: str
    intro_climb_reference: str
    starter_skill_digest: str
    rich_output_skill_digest: str
    skill_improver_digest: str
    minimum_host_hermes_version: str
    maximum_tested_host_hermes_version: str
    subject_hermes_version: str

    def to_dict(self) -> dict[str, Any]:
        """Return the release as JSON-ready values in declaration order."""
        document: dict[str, Any] = {}
        for name in RELEASE_CORE_FIELDS:
            value = getattr(self, name)
            document[name] = list(value) if isinstance(value, tuple) else value
        return document


def parse_release_core(raw: bytes) -> ReleaseCore:
    """Parse and fully validate embedded release bytes.

    Raises:
        PluginError: with code ``plugin_release_core_invalid`` when the bytes
            are not exactly one supported, complete, well-formed release.
    """

    def invalid(detail: str) -> PluginError:
        return PluginError(
            f"release-core.json is not usable: {detail}",
            code=CODE_PLUGIN_RELEASE_CORE_INVALID,
            repair="Reinstall the plugin at its published commit.",
        )

    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise invalid(str(error)) from error

    if not isinstance(decoded, dict):
        raise invalid("the document is not a JSON object")

    schema_version = decoded.get("schema_version")
    if schema_version != SUPPORTED_RELEASE_CORE_SCHEMA:
        raise invalid(
            f"schema version {schema_version!r} is not "
            f"{SUPPORTED_RELEASE_CORE_SCHEMA!r}"
        )

    unknown = sorted(set(decoded) - set(RELEASE_CORE_FIELDS))
    if unknown:
        raise invalid(f"unknown fields {unknown}")

    missing = sorted(set(RELEASE_CORE_FIELDS) - set(decoded))
    if missing:
        raise invalid(f"missing fields {missing}")

    for name in _RELEASE_CORE_STRING_FIELDS:
        value = decoded[name]
        if not isinstance(value, str) or not value:
            raise invalid(f"field {name!r} is not a non-empty string")

    if not isinstance(decoded["placeholder_release"], bool):
        raise invalid("field 'placeholder_release' is not a boolean")

    unbound = decoded["placeholder_fields"]
    if isinstance(unbound, str) or not isinstance(unbound, Sequence):
        raise invalid("field 'placeholder_fields' is not a list")
    for name in unbound:
        if not isinstance(name, str) or name not in RELEASE_CORE_FIELDS:
            raise invalid(f"field 'placeholder_fields' names {name!r}")

    for name in _RELEASE_CORE_DIGEST_FIELDS:
        if not DIGEST_PATTERN.match(decoded[name]):
            raise invalid(f"field {name!r} is not a sha256 digest")

    for name in _RELEASE_CORE_VERSION_FIELDS:
        if not VERSION_PATTERN.match(decoded[name]):
            raise invalid(f"field {name!r} is not a version string")

    if not COMMIT_PATTERN.match(decoded["cli_source_commit"]):
        raise invalid("field 'cli_source_commit' is not a full 40-character commit")

    if not IDENTIFIER_PATTERN.match(decoded["release_id"]):
        raise invalid("field 'release_id' is not a bounded identifier")

    if not CLIMB_REFERENCE_PATTERN.match(decoded["intro_climb_reference"]):
        raise invalid("field 'intro_climb_reference' is not a pinned slug@version")

    return ReleaseCore(**{**decoded, "placeholder_fields": tuple(unbound)})


# CLI boundary ---------------------------------------------------------------


@dataclass(frozen=True)
class CliInvocation:
    """One planned Techtree CLI call.

    ``argv`` is complete and literal. The bridge runs it with ``shell=False``,
    so no quoting, expansion, or interpolation stands between this list and
    the process that runs.
    """

    argv: tuple[str, ...]
    timeout_seconds: float
    purpose: str


@dataclass(frozen=True)
class CliResponse:
    """The outcome of one Techtree CLI call."""

    invocation: CliInvocation
    exit_code: int
    envelope: Mapping[str, Any]
    stderr_excerpt: str

    @property
    def ok(self) -> bool:
        """Whether the CLI reported success in its own envelope."""
        return bool(self.envelope.get("ok"))


_CLI_ENVELOPE_FIELDS: Final = (
    "schema_version",
    "command",
    "ok",
    "data",
    "error",
    "messages",
    "warnings",
    "next_actions",
)

_CLI_MESSAGE_FIELDS: Final = ("level", "code", "text")
_CLI_MESSAGE_LEVELS: Final = ("info", "warning", "error")
_CLI_ERROR_FIELDS: Final = ("code", "message", "retryable", "details")
_CLI_NEXT_ACTION_FIELDS: Final = (
    "id",
    "label",
    "reason",
    "cli",
    "hermes_tool",
    "hermes_args",
    "requires_user_confirmation",
)


def parse_cli_envelope(raw: str) -> dict[str, Any]:
    """Parse exactly one Techtree CLI JSON envelope.

    Machine mode promises one JSON object with no colour and no prompting.
    Anything else — a second record, ANSI, a missing field, a field the
    contract does not have — is a contract failure rather than something to
    salvage.

    Unknown fields are rejected on purpose. The published envelope schema is
    closed, so a field this plugin has never heard of means the CLI and the
    plugin no longer agree about the contract. That is a decision for a person
    to record, not something a bridge should quietly pass through.

    Raises:
        CliEnvelopeError: when the output is not one valid envelope.
    """
    if ANSI_PATTERN.search(raw):
        raise CliEnvelopeError(
            "CLI machine output contained ANSI escapes",
            code=CODE_CLI_OUTPUT_INVALID,
        )
    if "\x00" in raw:
        raise CliEnvelopeError("CLI machine output contained a NUL byte")

    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as error:
        raise CliEnvelopeError(
            f"CLI machine output was not exactly one JSON document: {error}"
        ) from error

    if not isinstance(decoded, dict):
        raise CliEnvelopeError("CLI machine output was not a JSON object")

    missing = sorted(set(_CLI_ENVELOPE_FIELDS) - set(decoded))
    if missing:
        raise CliEnvelopeError(f"CLI envelope is missing fields {missing}")

    unknown = sorted(set(decoded) - set(_CLI_ENVELOPE_FIELDS))
    if unknown:
        raise CliEnvelopeError(
            f"CLI envelope carries fields this plugin release does not know: {unknown}"
        )

    if decoded["schema_version"] != SUPPORTED_CLI_SCHEMA:
        raise CliEnvelopeError(
            f"CLI envelope schema {decoded['schema_version']!r} is not "
            f"{SUPPORTED_CLI_SCHEMA!r}"
        )
    if not isinstance(decoded["ok"], bool):
        raise CliEnvelopeError("CLI envelope field 'ok' is not a boolean")
    if not isinstance(decoded["command"], str) or not decoded["command"]:
        raise CliEnvelopeError("CLI envelope field 'command' is not a command name")

    for name in ("messages", "warnings"):
        _require_list(decoded, name)
        for entry in decoded[name]:
            _check_message(entry, name)

    _require_list(decoded, "next_actions")
    for entry in decoded["next_actions"]:
        _check_next_action(entry)

    _check_error(decoded["error"], reported_ok=decoded["ok"])

    result: dict[str, Any] = decoded
    return result


def _require_list(envelope: Mapping[str, Any], name: str) -> None:
    if not isinstance(envelope[name], list):
        raise CliEnvelopeError(f"CLI envelope field {name!r} is not a list")


def _check_fields(
    value: Any, expected: Sequence[str], description: str
) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise CliEnvelopeError(f"CLI envelope {description} is not an object")
    missing = sorted(set(expected) - set(value))
    unknown = sorted(set(value) - set(expected))
    if missing:
        raise CliEnvelopeError(f"CLI envelope {description} is missing {missing}")
    if unknown:
        raise CliEnvelopeError(f"CLI envelope {description} carries {unknown}")
    mapping: Mapping[str, Any] = value
    return mapping


def _check_message(value: Any, name: str) -> None:
    message = _check_fields(value, _CLI_MESSAGE_FIELDS, f"{name} entry")
    if message["level"] not in _CLI_MESSAGE_LEVELS:
        raise CliEnvelopeError(
            f"CLI envelope {name} entry has level {message['level']!r}"
        )
    if not isinstance(message["text"], str) or not message["text"]:
        raise CliEnvelopeError(f"CLI envelope {name} entry has no text")
    if message["code"] is not None and not isinstance(message["code"], str):
        raise CliEnvelopeError(f"CLI envelope {name} entry has a non-string code")


def _check_next_action(value: Any) -> None:
    action = _check_fields(value, _CLI_NEXT_ACTION_FIELDS, "next action")
    for name in ("id", "label", "reason"):
        if not isinstance(action[name], str) or not action[name]:
            raise CliEnvelopeError(f"CLI envelope next action has no {name}")
    if not isinstance(action["requires_user_confirmation"], bool):
        raise CliEnvelopeError(
            "CLI envelope next action does not say whether it needs confirmation"
        )
    command = action["cli"]
    if command is not None:
        if isinstance(command, str) or not isinstance(command, Sequence):
            raise CliEnvelopeError("CLI envelope next action 'cli' is not an argv list")
        for argument in command:
            if not isinstance(argument, str) or not argument:
                raise CliEnvelopeError(
                    "CLI envelope next action 'cli' holds an empty argument"
                )


def _check_error(value: Any, *, reported_ok: bool) -> None:
    if value is None:
        if not reported_ok:
            raise CliEnvelopeError("CLI envelope reports failure with no error")
        return
    if reported_ok:
        raise CliEnvelopeError("CLI envelope reports success and an error")

    error = _check_fields(value, _CLI_ERROR_FIELDS, "error")
    for name in ("code", "message"):
        if not isinstance(error[name], str) or not error[name]:
            raise CliEnvelopeError(f"CLI envelope error has no {name}")
    if not isinstance(error["retryable"], bool):
        raise CliEnvelopeError(
            "CLI envelope error does not say whether it is retryable"
        )
    if not isinstance(error["details"], dict):
        raise CliEnvelopeError("CLI envelope error details are not an object")


# Bootstrap -------------------------------------------------------------------


@dataclass(frozen=True)
class BootstrapInstallPlan:
    """One pinned, expiring CLI installation plan. Specification section 7.6.

    The plan is generated from release data alone. There is no field a model
    can fill in: not the package, not the version, not an index, not a flag.
    """

    plan_id: str
    package: str
    version: str
    argv: tuple[str, ...]
    release_core_digest: str
    requires_confirmation: bool
    created_at: str
    expires_at: str

    def display_command(self) -> str:
        """Return the argv joined for display only, never for a shell."""
        return " ".join(self.argv)


_INSTALL_PLAN_FIELDS: Final = (
    "plan_id",
    "package",
    "version",
    "argv",
    "release_core_digest",
    "requires_confirmation",
    "created_at",
    "expires_at",
)

# Fields whose presence means something tried to hand the plugin a command to
# run rather than a plan to display. Specification section 7.4.
_FORBIDDEN_PLAN_FIELDS: Final = (
    "command",
    "shell",
    "script",
    "executable",
    "install_command",
    "index_url",
    "extra_args",
    "env",
)


def parse_bootstrap_install_plan(value: Mapping[str, Any]) -> BootstrapInstallPlan:
    """Validate a stored install plan.

    Raises:
        BootstrapPlanError: when the plan is incomplete, carries an executable
            field it must not carry, or describes anything other than the one
            fixed ``uv`` argv for the pinned package and version.
    """

    def invalid(detail: str) -> BootstrapPlanError:
        return BootstrapPlanError(f"install plan is not usable: {detail}")

    present_forbidden = sorted(set(value) & set(_FORBIDDEN_PLAN_FIELDS))
    if present_forbidden:
        raise invalid(f"it carries executable fields {present_forbidden}")

    unknown = sorted(set(value) - set(_INSTALL_PLAN_FIELDS))
    if unknown:
        raise invalid(f"unknown fields {unknown}")

    missing = sorted(set(_INSTALL_PLAN_FIELDS) - set(value))
    if missing:
        raise invalid(f"missing fields {missing}")

    for name in ("plan_id", "package", "version", "release_core_digest"):
        if not isinstance(value[name], str) or not value[name]:
            raise invalid(f"field {name!r} is not a non-empty string")
    for name in ("created_at", "expires_at"):
        if not isinstance(value[name], str) or not value[name]:
            raise invalid(f"field {name!r} is not a timestamp")

    if not PLAN_ID_PATTERN.match(value["plan_id"]):
        raise invalid("field 'plan_id' is not a plugin-issued plan identifier")
    if not IDENTIFIER_PATTERN.match(value["package"]):
        raise invalid("field 'package' is not a bounded package name")
    if not VERSION_PATTERN.match(value["version"]):
        raise invalid("field 'version' is not a version string")
    if not DIGEST_PATTERN.match(value["release_core_digest"]):
        raise invalid("field 'release_core_digest' is not a sha256 digest")

    if value["requires_confirmation"] is not True:
        raise invalid("installation always requires confirmation")

    argv = value["argv"]
    if isinstance(argv, str) or not isinstance(argv, Sequence):
        raise invalid("field 'argv' is not an argument array")
    if not argv:
        raise invalid("field 'argv' is empty")
    for argument in argv:
        if not isinstance(argument, str) or not argument or "\x00" in argument:
            raise invalid("field 'argv' contains a non-string or empty argument")
    if argv[0] != INSTALLER_EXECUTABLE:
        raise invalid(f"the installer must be {INSTALLER_EXECUTABLE!r}")

    requirement = f"{value['package']}=={value['version']}"
    if requirement not in argv:
        raise invalid(f"argv does not install exactly {requirement!r}")

    return BootstrapInstallPlan(
        plan_id=value["plan_id"],
        package=value["package"],
        version=value["version"],
        argv=tuple(argv),
        release_core_digest=value["release_core_digest"],
        requires_confirmation=True,
        created_at=value["created_at"],
        expires_at=value["expires_at"],
    )


# Actions ---------------------------------------------------------------------


@dataclass(frozen=True)
class PluginAction:
    """One next step offered back to the host conversation.

    Actions name a tool and its arguments so the operator agent does not have
    to invent either. An action that costs money or changes the host is
    marked, and the mark is what the conversation must surface.
    """

    id: str
    label: str
    reason: str
    tool: str | None = None
    arguments: Mapping[str, Any] = field(default_factory=dict)
    requires_user_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return the action in the shape tool results carry it."""
        return {
            "id": self.id,
            "label": self.label,
            "reason": self.reason,
            "tool": self.tool,
            "arguments": dict(self.arguments),
            "requires_user_confirmation": self.requires_user_confirmation,
        }
