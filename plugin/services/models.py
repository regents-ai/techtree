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

import base64
import binascii
import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final, Literal

from ..cli.constants import SUPPORTED_RELEASE_CORE_SCHEMA
from ..cli.errors import (
    CODE_CLI_OUTPUT_INVALID,
    CODE_PLUGIN_RELEASE_CORE_INVALID,
    BootstrapPlanError,
    CliAnswerError,
    PluginError,
)

# Value patterns --------------------------------------------------------------

DIGEST_PATTERN: Final = re.compile(r"^sha256:[0-9a-f]{64}$")

#: An https address with a host, an optional path, and nothing after it.
#: Matched rather than parsed: ``urllib`` is what a plugin module may not
#: import at all, because importing it is how this runtime would stop being
#: unable to open a connection, and the doctor proves that by reading the
#: imports rather than by trusting anybody.
HTTPS_ADDRESS_PATTERN: Final = re.compile(r"^https://[^/?#\s]+(?:/[^?#\s]*)?$")
#: Where a machine that does not hold the starter Skill's bytes may obtain
#: them. HTTPS only, and no userinfo in the authority: this coordinate is
#: copied verbatim into the plugin, the website, approval packets and support
#: transcripts, and `https://user:token@host/...` would carry a credential
#: through every one of them. Mirrors techtree-python's OBJECT_URL_PATTERN.
#: The address is also a content address: it ends in the digest of the file it
#: returns, which is what a fetcher checks a response against.
OBJECT_URL_PATTERN: Final = re.compile(r"^https://[^\s/@]+/[^\s]*sha256:[0-9a-f]{64}$")
VERSION_PATTERN: Final = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.+-]{0,63}$")
#: A Hermes release tag, as the release names the subject harness: ``v2026.7.20``.
HERMES_TAG_PATTERN: Final = re.compile(r"^v[0-9]+(?:\.[0-9]+){2,3}$")
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
    updated_at: str


# Release --------------------------------------------------------------------

#: The coordinates a publication travels to, and the key its answer is checked
#: against. Nested, unlike everything else here, because the key is three
#: values that only mean anything together — an algorithm, the digest that
#: names the key, and the key itself.
PUBLICATION_FIELDS: Final = (
    "submission_endpoint",
    "public_log_url",
    "network_key",
)

NETWORK_KEY_FIELDS: Final = (
    "algorithm",
    "key_id",
    "public_key",
)

RELEASE_CORE_FIELDS: Final = (
    "schema_version",
    "release_id",
    "cli_version",
    "protocol_version",
    "engine_digest",
    "catalog_digest",
    "intro_climb_reference",
    "starter_skill_digest",
    "starter_skill_object_url",
    "minimum_host_hermes_version",
    "maximum_tested_host_hermes_version",
    "subject_hermes_version",
    "publication",
)

#: Every field but the nested one. ``publication`` is an object and is checked
#: on its own terms below.
_RELEASE_CORE_STRING_FIELDS: Final = tuple(
    name for name in RELEASE_CORE_FIELDS if name != "publication"
)

_RELEASE_CORE_DIGEST_FIELDS: Final = (
    "engine_digest",
    "catalog_digest",
    "starter_skill_digest",
)

_RELEASE_CORE_VERSION_FIELDS: Final = (
    "cli_version",
    "protocol_version",
    "minimum_host_hermes_version",
    "maximum_tested_host_hermes_version",
)


@dataclass(frozen=True)
class NetworkKey:
    """The key a publication receipt is checked against. Section 6.6.

    The plugin never checks one — publishing is a command a person runs, and
    nothing here opens a network connection. It carries the key because a
    release document is a whole thing, and a reader of this module should be
    able to see what a release says rather than what this plugin happens to
    use.
    """

    algorithm: Literal["ed25519"]
    key_id: str
    public_key: str

    def to_dict(self) -> dict[str, Any]:
        """Return the key as JSON-ready values in declaration order."""
        return {name: getattr(self, name) for name in NETWORK_KEY_FIELDS}


@dataclass(frozen=True)
class PublicationCoordinates:
    """Where a published run goes, and where it can then be read."""

    submission_endpoint: str
    public_log_url: str
    network_key: NetworkKey

    def to_dict(self) -> dict[str, Any]:
        """Return the coordinates as JSON-ready values in declaration order."""
        return {
            "submission_endpoint": self.submission_endpoint,
            "public_log_url": self.public_log_url,
            "network_key": self.network_key.to_dict(),
        }


@dataclass(frozen=True)
class ReleaseCore:
    """The frozen release the plugin was built against. Section 6.6.

    These are the same bytes the installed regents-cli ships: a contract of
    coordinates a person chose, and nothing about any artifact built from it
    (Techtree decisions document 0026). Which commit a regents-cli wheel came
    from is stamped into that wheel and reported by ``regents techtree release
    info``; it is not in here, and the plugin never asks this document for it.

    Techtree owns verifying its own release document; the plugin reads it,
    repeats it, and compares digests.
    """

    schema_version: Literal["techtree.release-core.v2"]
    release_id: str
    cli_version: str
    protocol_version: str
    engine_digest: str
    catalog_digest: str
    intro_climb_reference: str
    starter_skill_digest: str
    starter_skill_object_url: str
    minimum_host_hermes_version: str
    maximum_tested_host_hermes_version: str
    subject_hermes_version: str
    publication: PublicationCoordinates

    def to_dict(self) -> dict[str, Any]:
        """Return the release as JSON-ready values in declaration order."""
        return {
            name: (
                self.publication.to_dict()
                if name == "publication"
                else getattr(self, name)
            )
            for name in RELEASE_CORE_FIELDS
        }


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

    for name in _RELEASE_CORE_DIGEST_FIELDS:
        if not DIGEST_PATTERN.match(decoded[name]):
            raise invalid(f"field {name!r} is not a sha256 digest")

    if not OBJECT_URL_PATTERN.match(decoded["starter_skill_object_url"]):
        raise invalid(
            "field 'starter_skill_object_url' is not an https content address "
            "without credentials in it"
        )

    for name in _RELEASE_CORE_VERSION_FIELDS:
        if not VERSION_PATTERN.match(decoded[name]):
            raise invalid(f"field {name!r} is not a version string")

    if not HERMES_TAG_PATTERN.match(decoded["subject_hermes_version"]):
        raise invalid("field 'subject_hermes_version' is not a Hermes release tag")

    if not IDENTIFIER_PATTERN.match(decoded["release_id"]):
        raise invalid("field 'release_id' is not a bounded identifier")

    if not CLIMB_REFERENCE_PATTERN.match(decoded["intro_climb_reference"]):
        raise invalid("field 'intro_climb_reference' is not a pinned slug@version")

    publication = _parse_publication(decoded["publication"], invalid)
    return ReleaseCore(**{**decoded, "publication": publication})


def _parse_publication(
    value: object, invalid: Callable[[str], PluginError]
) -> PublicationCoordinates:
    """Return the publication coordinates, or refuse the release document.

    Held to the same standard as everything above it: exactly the fields
    named, each one a non-empty string, the two addresses plain ``https``
    with nothing after the path, and the key identified by the digest of its
    own bytes. That last rule is what makes a receipt naming a key it does
    not carry catchable without looking anything up.
    """
    if not isinstance(value, dict):
        raise invalid("field 'publication' is not a JSON object")

    unknown = sorted(set(value) - set(PUBLICATION_FIELDS))
    if unknown:
        raise invalid(f"publication has unknown fields {unknown}")
    missing = sorted(set(PUBLICATION_FIELDS) - set(value))
    if missing:
        raise invalid(f"publication is missing fields {missing}")

    for name in ("submission_endpoint", "public_log_url"):
        address = value[name]
        if not isinstance(address, str) or not address:
            raise invalid(f"publication field {name!r} is not a non-empty string")
        if not HTTPS_ADDRESS_PATTERN.match(address):
            raise invalid(f"publication field {name!r} is not a plain https address")

    key = value["network_key"]
    if not isinstance(key, dict):
        raise invalid("publication field 'network_key' is not a JSON object")
    unknown = sorted(set(key) - set(NETWORK_KEY_FIELDS))
    if unknown:
        raise invalid(f"network_key has unknown fields {unknown}")
    missing = sorted(set(NETWORK_KEY_FIELDS) - set(key))
    if missing:
        raise invalid(f"network_key is missing fields {missing}")
    for name in NETWORK_KEY_FIELDS:
        if not isinstance(key[name], str) or not key[name]:
            raise invalid(f"network_key field {name!r} is not a non-empty string")
    if key["algorithm"] != "ed25519":
        raise invalid(f"network_key algorithm {key['algorithm']!r} is not 'ed25519'")
    if not DIGEST_PATTERN.match(key["key_id"]):
        raise invalid("network_key field 'key_id' is not a sha256 digest")

    try:
        material = base64.b64decode(key["public_key"], validate=True)
    except (ValueError, binascii.Error) as error:
        raise invalid("network_key field 'public_key' is not base64") from error
    computed = "sha256:" + hashlib.sha256(material).hexdigest()
    if computed != key["key_id"]:
        raise invalid("network_key identifier is not the digest of its own key")

    return PublicationCoordinates(
        submission_endpoint=value["submission_endpoint"],
        public_log_url=value["public_log_url"],
        network_key=NetworkKey(
            algorithm="ed25519", key_id=key["key_id"], public_key=key["public_key"]
        ),
    )


# regents boundary ------------------------------------------------------------


@dataclass(frozen=True)
class CliInvocation:
    """One planned ``regents techtree`` call.

    ``argv`` is complete and literal. The bridge runs it with ``shell=False``,
    so no quoting, expansion, or interpolation stands between this list and
    the process that runs.
    """

    argv: tuple[str, ...]
    timeout_seconds: float
    purpose: str


@dataclass(frozen=True)
class CliResponse:
    """The outcome of one ``regents techtree`` call."""

    invocation: CliInvocation
    exit_code: int
    answer: Mapping[str, Any]
    stderr_excerpt: str

    @property
    def ok(self) -> bool:
        """Whether regents answered with facts rather than an error."""
        return is_success(self.answer)


def is_success(answer: Mapping[str, Any]) -> bool:
    """Whether one regents answer is a success: every failure is ``{"error": ...}``."""
    return "error" not in answer


def answer_error(answer: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return a failed answer's ``error`` object, or an empty mapping on success."""
    error = answer.get("error")
    return error if isinstance(error, dict) else {}


def parse_cli_answer(raw: str) -> dict[str, Any]:
    """Parse exactly one regents JSON answer.

    ``--json`` promises one JSON object with no colour and no prompting. A
    success is the facts themselves, at the top level. A failure is an object
    whose one field is ``error``, carrying at least a ``code`` and a
    ``message``. Anything else — a second record, ANSI, a non-object, an error
    with no code — is a contract failure rather than something to salvage.

    Raises:
        CliAnswerError: when the output is not one valid answer.
    """
    if ANSI_PATTERN.search(raw):
        raise CliAnswerError(
            "regents machine output contained ANSI escapes",
            code=CODE_CLI_OUTPUT_INVALID,
        )
    if "\x00" in raw:
        raise CliAnswerError("regents machine output contained a NUL byte")

    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as error:
        raise CliAnswerError(
            f"regents machine output was not exactly one JSON document: {error}"
        ) from error

    if not isinstance(decoded, dict):
        raise CliAnswerError("regents machine output was not a JSON object")

    if "error" in decoded:
        _check_error(decoded)
    else:
        _check_success(decoded)

    result: dict[str, Any] = decoded
    return result


def _check_error(answer: Mapping[str, Any]) -> None:
    if set(answer) != {"error"}:
        raise CliAnswerError("a regents failure carries fields beside 'error'")
    error = answer["error"]
    if not isinstance(error, dict):
        raise CliAnswerError("a regents failure's 'error' is not an object")
    for name in ("code", "message"):
        if not isinstance(error.get(name), str) or not error[name]:
            raise CliAnswerError(f"a regents failure has no {name}")
    if "details" in error and not isinstance(error["details"], dict):
        raise CliAnswerError("a regents failure's details are not an object")


def _check_success(answer: Mapping[str, Any]) -> None:
    if "report" in answer and not isinstance(answer["report"], str):
        raise CliAnswerError("a regents answer's report is not text")
    warnings = answer.get("warnings", [])
    if not isinstance(warnings, list):
        raise CliAnswerError("a regents answer's warnings are not a list")
    for warning in warnings:
        if (
            not isinstance(warning, dict)
            or not isinstance(warning.get("id"), str)
            or not isinstance(warning.get("text"), str)
        ):
            raise CliAnswerError("a regents warning is not an {id, text} object")


# Bootstrap -------------------------------------------------------------------


@dataclass(frozen=True)
class BootstrapInstallPlan:
    """One pinned, expiring regents-cli installation plan. Specification section 7.6.

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


# Presentation -------------------------------------------------------------------


@dataclass(frozen=True)
class PresentationNarrative:
    """The words a host model chose about a result. Specification section 6.4.

    Four choices, and only those four: a headline, the observations worth
    emphasizing, the one verified caveat to foreground, and what to do next.
    Every number, verdict code, status, grade, and digest in a result comes
    from Techtree's deterministic payload and is rendered beside this, never
    through it.
    """

    headline: str
    observations: tuple[str, ...]
    caveats: tuple[str, ...]
    next_step: str | None
    selected_task_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return the narrative in the shape a result carries it."""
        return {
            "headline": self.headline,
            "observations": list(self.observations),
            "caveats": list(self.caveats),
            "next_step": self.next_step,
            "selected_task_refs": list(self.selected_task_refs),
        }

    def texts(self) -> tuple[str, ...]:
        """Return every piece of text the model wrote."""
        return (
            self.headline,
            *self.observations,
            *self.caveats,
            *((self.next_step,) if self.next_step else ()),
        )


# Actions ---------------------------------------------------------------------


@dataclass(frozen=True)
class PluginAction:
    """One next step offered back to the host conversation.

    Actions name a tool and its arguments so the operator agent does not have
    to invent either. An action that spends model tokens or changes the host is
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
