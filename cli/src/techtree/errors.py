"""Typed Techtree errors and the exit codes they map to. Spec section 10.5.

Every failure a user can provoke is one of the classes below. Each class fixes
a machine-stable ``code``, a documented process exit code, and whether retrying
the same command could plausibly succeed. Call sites override those defaults
only when they have something more specific to say.

Two rules shape this module:

* ``details`` is machine-facing and travels into JSON output, so it carries
  identifiers, counts, and paths — never secret values. Call sites keep to
  that, and :func:`sanitize_details` enforces it at the boundary anyway,
  because some of what reaches ``details`` was authored by a subprocess
  rather than by anyone here.
* Human-facing text is actionable. Tracebacks are debugging aids for stderr,
  not part of the contract, which is why
  :func:`sanitize_exception_message` exists for the unexpected-exception path.

An error can also carry the ``NextAction`` list the CLI should offer, so that
the code which knows *why* something failed is the code that says what to do
about it. The shapes those actions and the projected ``CliError`` are spelled
in belong to :mod:`techtree.models.cli`. That module is imported only for
typing, and inside :func:`error_to_cli_error`, because the model package
imports this one: errors sit underneath models, and speaking a model's
vocabulary must not invert that.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, ClassVar, Final

if TYPE_CHECKING:
    from techtree.models.base import JsonValue
    from techtree.models.cli import CliError, NextAction

__all__ = [
    "REDACTED",
    "AuthenticationError",
    "CancellationError",
    "ConflictError",
    "EngineError",
    "NotFoundError",
    "PolicyError",
    "PrerequisiteError",
    "RunError",
    "TechtreeError",
    "UsageError",
    "ValidationError",
    "VerificationError",
    "error_to_cli_error",
    "exit_code_for",
    "sanitize_details",
    "sanitize_exception_message",
    "sanitize_text",
]


# ---------------------------------------------------------------------------
# Exit codes
#
# These are part of the CLI contract: a host agent branches on them without
# parsing output. Values are append-only; never reuse a retired number.
# ---------------------------------------------------------------------------

EXIT_OK: Final = 0
EXIT_ERROR: Final = 1
EXIT_USAGE: Final = 2
EXIT_VALIDATION: Final = 3
EXIT_PREREQUISITE: Final = 4
EXIT_NOT_FOUND: Final = 5
EXIT_CONFLICT: Final = 6
EXIT_AUTHENTICATION: Final = 7
EXIT_POLICY: Final = 8
EXIT_ENGINE: Final = 9
EXIT_RUN: Final = 10
EXIT_VERIFICATION: Final = 11
#: The shell convention for "terminated by SIGINT", which is what a cancelled
#: run is from the caller's point of view.
EXIT_CANCELLED: Final = 130


# ---------------------------------------------------------------------------
# Hierarchy
# ---------------------------------------------------------------------------


class TechtreeError(Exception):
    """Base class for every failure Techtree reports on purpose."""

    default_code: ClassVar[str] = "techtree_error"
    default_exit_code: ClassVar[int] = EXIT_ERROR
    default_retryable: ClassVar[bool] = False

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        exit_code: int | None = None,
        retryable: bool | None = None,
        details: Mapping[str, JsonValue] | None = None,
        next_actions: Sequence[NextAction] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = self.default_code if code is None else code
        self.exit_code = self.default_exit_code if exit_code is None else exit_code
        self.retryable = self.default_retryable if retryable is None else retryable
        self.details: dict[str, JsonValue] = dict(details or {})
        #: What the caller could do about this, in the CLI's own vocabulary.
        #: Raising code fills this in when it knows; the CLI never invents it.
        self.next_actions: list[NextAction] = list(next_actions or ())

    def __str__(self) -> str:
        return self.message


class UsageError(TechtreeError):
    """The command, its options, or their combination is not valid."""

    default_code: ClassVar[str] = "usage_error"
    default_exit_code: ClassVar[int] = EXIT_USAGE


class ValidationError(TechtreeError):
    """Input data or a stored document failed protocol validation."""

    default_code: ClassVar[str] = "validation_error"
    default_exit_code: ClassVar[int] = EXIT_VALIDATION


class PrerequisiteError(TechtreeError):
    """Something that had to be done first has not been done."""

    default_code: ClassVar[str] = "prerequisite_error"
    default_exit_code: ClassVar[int] = EXIT_PREREQUISITE


class NotFoundError(TechtreeError):
    """A named object does not exist."""

    default_code: ClassVar[str] = "not_found"
    default_exit_code: ClassVar[int] = EXIT_NOT_FOUND


class ConflictError(TechtreeError):
    """The requested change collides with existing immutable state."""

    default_code: ClassVar[str] = "conflict"
    default_exit_code: ClassVar[int] = EXIT_CONFLICT


class AuthenticationError(TechtreeError):
    """A credential is missing, rejected, or expired."""

    default_code: ClassVar[str] = "authentication_error"
    default_exit_code: ClassVar[int] = EXIT_AUTHENTICATION


class EngineError(TechtreeError):
    """The managed engine could not be installed, resolved, or invoked."""

    default_code: ClassVar[str] = "engine_error"
    default_exit_code: ClassVar[int] = EXIT_ENGINE


class RunError(TechtreeError):
    """A run failed, or a run operation is illegal in the current phase."""

    default_code: ClassVar[str] = "run_error"
    default_exit_code: ClassVar[int] = EXIT_RUN


class VerificationError(TechtreeError):
    """A digest, signature, or membership commitment did not verify."""

    default_code: ClassVar[str] = "verification_error"
    default_exit_code: ClassVar[int] = EXIT_VERIFICATION


class CancellationError(TechtreeError):
    """Work stopped because it was cancelled."""

    default_code: ClassVar[str] = "cancelled"
    default_exit_code: ClassVar[int] = EXIT_CANCELLED


class PolicyError(TechtreeError):
    """A data-rights or publication policy forbids the request.

    Data-policy contradictions raise this and nothing else, so a caller can
    distinguish "your inputs disagree about rights" from "your inputs are
    malformed".
    """

    default_code: ClassVar[str] = "policy_error"
    default_exit_code: ClassVar[int] = EXIT_POLICY


# ---------------------------------------------------------------------------
# Message sanitization
# ---------------------------------------------------------------------------

#: The single placeholder that replaces anything secret-looking, so redaction
#: is obvious in output and greppable in tests.
REDACTED: Final = "[redacted]"

_SECRET_NAME = (
    r"[A-Za-z0-9_.-]*"
    r"(?:api[_-]?key|access[_-]?key|secret|token|password|passwd|"
    r"credential|authorization)"
    r"[A-Za-z0-9_.-]*"
)
#: An unquoted value, when it is a credential rather than the next word of a
#: sentence. Prose puts ordinary words after a colon — "no credential: the
#: Prime CLI configuration on this machine holds no key" — and redacting those
#: turns a sentence somebody has to act on into noise. A credential is not a
#: word: it is long, and it carries a digit, a capital, or one of the
#: characters tokens are built from.
_BARE_TOKEN_VALUE = r"(?=\S{8,})\S*[^a-z]\S*"
#: A secret-looking name, then a separator, then its value. The name may carry
#: a closing quote because these often appear inside JSON. The value may carry
#: an authentication scheme so that ``Authorization: Bearer <token>`` redacts
#: the token rather than the word ``Bearer``.
_SECRET_ASSIGNMENT = re.compile(
    rf"(?i)\b({_SECRET_NAME}[\"']?)"
    r"(\s*[:=]\s*)"
    rf"(\"[^\"]*\"|'[^']*'|(?:bearer|basic|token)\s+\S+|{_BARE_TOKEN_VALUE})"
)
#: Names that merely contain a secret-sounding word but never carry one. Every
#: entry here is a real Techtree field, so redacting it would hide useful
#: configuration detail without protecting anything.
_SAFE_NAMES: Final[frozenset[str]] = frozenset(
    {
        "credential_env",
        # Every usage field NormalizedUsage defines: these counts are exactly
        # what an operator needs when a run's spend is being questioned.
        "cached_input_tokens",
        "input_tokens",
        "max_tokens",
        "num_tokens",
        "output_tokens",
        "token_count",
        "tokens",
        "total_tokens",
    }
)
#: The userinfo of a URL — ``https://user:token@host/path``. The whole of it
#: goes, both halves, because which half holds the credential depends on the
#: index: a private package index is as likely to be
#: ``https://<token>@host`` as ``https://__token__:<token>@host``, and a
#: username is not worth a leaked password. The host and path survive, which
#: is the part an operator needs in order to see which index refused them.
#:
#: This one runs before the assignment rule so that the host stays readable:
#: the assignment rule's value pattern is greedy and would take the rest of
#: the URL with it.
_URL_USERINFO = re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://)[^/?#\s@]+@")
_BEARER_VALUE = re.compile(r"(?i)\b(bearer|basic)\s+\S+")
_PREFIXED_TOKEN = re.compile(
    r"\b(?:sk|pk|rk|ghp|gho|ghu|ghs|github_pat|xox[abprs])[-_][A-Za-z0-9_-]{8,}"
)
#: A long unbroken run of key-ish characters. ``/`` is excluded on purpose: it
#: is what separates this heuristic from filesystem paths, which are useful
#: diagnostic detail and must survive.
_OPAQUE_RUN = re.compile(r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+_-]{40,}={0,2}")
#: Hexadecimal runs are digests and Verifiers task hashes, which are exactly
#: the identifiers an operator needs to see, so they survive redaction too.
_PURE_HEX = re.compile(r"[0-9a-fA-F]+")
_MEMORY_ADDRESS = re.compile(r"\b0x[0-9a-fA-F]{6,}\b")
_WHITESPACE_RUN = re.compile(r"\s+")


def _redact_assignment(match: re.Match[str]) -> str:
    name, separator, value = match.group(1), match.group(2), match.group(3)
    if name.strip("\"'").lower() in _SAFE_NAMES:
        return f"{name}{separator}{value}"
    return f"{name}{separator}{REDACTED}"


def _redact_opaque_run(match: re.Match[str]) -> str:
    token = match.group(0)
    if _PURE_HEX.fullmatch(token):
        return token
    # Techtree's own prefixed identifiers (campaign_<32 hex>, run_<32 hex>,
    # ...) are the names an error needs in order to say which thing failed.
    # They are random, not secret. Imported at call time: ids sits on top of
    # this module, so the import must not run at load time.
    from techtree.ids import validate_id

    try:
        validate_id(token)
    except TechtreeError:
        return REDACTED
    return token


def sanitize_text(text: str) -> str:
    """Remove secret-looking values from one piece of arbitrary text.

    Whitespace and line structure are left alone, because the other caller of
    this is the worker log, where a line is a record and indentation is
    meaning. :func:`sanitize_exception_message` flattens first and then calls
    this.
    """
    text = _URL_USERINFO.sub(rf"\g<1>{REDACTED}@", text)
    text = _SECRET_ASSIGNMENT.sub(_redact_assignment, text)
    text = _BEARER_VALUE.sub(rf"\1 {REDACTED}", text)
    text = _PREFIXED_TOKEN.sub(REDACTED, text)
    text = _OPAQUE_RUN.sub(_redact_opaque_run, text)
    return _MEMORY_ADDRESS.sub("0x<address>", text)


def sanitize_exception_message(error: Exception) -> str:
    """Remove secret-looking values and unstable traceback detail."""
    text = _WHITESPACE_RUN.sub(" ", str(error)).strip()
    if not text:
        return type(error).__name__
    return sanitize_text(text)


# ---------------------------------------------------------------------------
# CLI projection
# ---------------------------------------------------------------------------


def sanitize_details(value: JsonValue) -> JsonValue:
    """Scrub every string inside an error's ``details``, however deep it sits.

    ``details`` is documented as machine-facing identifiers, counts and paths,
    and authored call sites keep to that. The trouble is the call sites that
    forward something they did not author: a subprocess's output, a parser's
    complaint, a value read out of the environment. Those arrive as strings
    and travel to the same envelope the message does, so they go through the
    same scrubber the message does.

    The walk is over values rather than keys. A key in ``details`` is always
    an authored field name — that is what makes ``details`` machine-facing —
    and scrubbing keys could collapse two of them into one, which would lose
    information without protecting anything.
    """
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, dict):
        return {key: sanitize_details(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_details(item) for item in value]
    return value


def error_to_cli_error(error: TechtreeError) -> CliError:
    """Convert an internal typed error to machine-safe CLI error data.

    Both halves are scrubbed on the way out — the message through
    :func:`sanitize_exception_message`, the details through
    :func:`sanitize_details`. Authored text is not supposed to contain
    secrets, but this is the one place every failure funnels through before it
    becomes output, and a scrubber that only runs on the paths someone
    remembered is not a scrubber.

    ``next_actions`` is not part of ``CliError``; it belongs to the envelope,
    and the CLI reads it from the error directly.
    """
    from techtree.models.cli import CliError

    return CliError(
        code=error.code,
        message=sanitize_exception_message(error),
        retryable=error.retryable,
        details={key: sanitize_details(item) for key, item in error.details.items()},
    )


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------


def exit_code_for(error: Exception) -> int:
    """Return documented CLI exit code.

    Anything that is not a typed Techtree error is an internal defect, and
    every internal defect exits ``1``.
    """
    if isinstance(error, TechtreeError):
        return error.exit_code
    return EXIT_ERROR
