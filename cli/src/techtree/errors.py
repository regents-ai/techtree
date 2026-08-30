"""Typed Techtree errors and the exit codes they map to. Spec section 10.5.

Every failure a user can provoke is one of the classes below. Each class fixes
a machine-stable ``code``, a documented process exit code, and whether retrying
the same command could plausibly succeed. Call sites override those defaults
only when they have something more specific to say.

Two rules shape this module:

* ``details`` is machine-facing and travels into JSON output, so it carries
  identifiers, counts, and paths. Nothing filters it: decision 0036 removed
  every secret-shaped-string detector from this project, so what a call site
  puts in ``details`` is what a caller reads, including when the call site is
  forwarding a subprocess's own words.
* Human-facing text is actionable. Tracebacks are debugging aids for stderr,
  not part of the contract, which is why
  :func:`stable_exception_message` exists for the unexpected-exception path.

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
    "stable_exception_message",
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
# Message stability
# ---------------------------------------------------------------------------

#: A memory address as CPython writes one into a repr. It changes on every
#: process, so an error quoting one would not compare equal to itself between
#: runs. Normalising it is about stability, not about secrecy: decision 0036
#: is explicit that this project detects no secret-shaped strings anywhere.
_MEMORY_ADDRESS = re.compile(r"\b0x[0-9a-fA-F]{6,}\b")
_WHITESPACE_RUN = re.compile(r"\s+")


def stable_exception_message(error: Exception) -> str:
    """Return one exception's message as a single stable line.

    Line structure is flattened so a message reads as one line wherever it is
    shown, and memory addresses are normalised so the same failure produces
    the same words twice. Nothing else is altered: whatever the exception
    said, including anything a subprocess said through it, is what comes out.
    """
    text = _WHITESPACE_RUN.sub(" ", str(error)).strip()
    if not text:
        return type(error).__name__
    return _MEMORY_ADDRESS.sub("0x<address>", text)


# ---------------------------------------------------------------------------
# CLI projection
# ---------------------------------------------------------------------------


def error_to_cli_error(error: TechtreeError) -> CliError:
    """Convert an internal typed error to CLI error data.

    The message is flattened by :func:`stable_exception_message`; ``details``
    travels exactly as the raising call site built it.

    ``next_actions`` is not part of ``CliError``; it belongs to the envelope,
    and the CLI reads it from the error directly.
    """
    from techtree.models.cli import CliError

    return CliError(
        code=error.code,
        message=stable_exception_message(error),
        retryable=error.retryable,
        details=dict(error.details),
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
