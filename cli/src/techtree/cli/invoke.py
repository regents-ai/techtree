"""The error boundary every command runs inside. Spec section 12.3.

One invariant governs this module: an invocation that starts a command emits
exactly one envelope and exits with the code that envelope implies. ``ok`` and
the exit status never disagree — zero means ``ok`` is true, anything else means
``ok`` is false and an error is present. A host agent can therefore branch on
the exit code alone and only parse output when it wants the detail.

Three kinds of outcome funnel through :func:`invoke_command`.

A command can succeed, and say what it produced and what could sensibly happen
next. A command can fail by raising a typed :class:`~techtree.errors.
TechtreeError`, which carries its own code, exit status, and repair actions —
the code that knows why something failed is the code that says what to do about
it. And a command can *diagnose* a failure while still having a complete answer
to give: Doctor finds a broken environment, and the checks it ran are the most
useful thing it could return. That is what ``CommandResult.error`` is for, and
it is why a failing envelope may still carry data.

Anything else escaping a command is a defect, not a user error. It becomes an
``internal_error`` with a sanitized message and exit code 1; the traceback goes
to stderr under ``--debug``, never into the contract.
"""

from __future__ import annotations

import traceback
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import NoReturn

import typer

from techtree.cli.context import CliContext
from techtree.cli.output import (
    DataRenderer,
    emit_envelope,
    stderr_log,
    write_envelope,
)
from techtree.constants import CLI_SCHEMA_VERSION
from techtree.errors import (
    EXIT_ERROR,
    EXIT_OK,
    TechtreeError,
    error_to_cli_error,
    exit_code_for,
    sanitize_exception_message,
)
from techtree.models.cli import MAX_NEXT_ACTIONS, CliEnvelope, CliMessage, NextAction

__all__ = [
    "CommandResult",
    "emit_boundary_failure",
    "failure_envelope",
    "invoke_command",
    "not_implemented_error",
    "success_envelope",
]


@dataclass
class CommandResult[T]:
    """What a command produced, in the CLI's own vocabulary.

    ``error`` is set by a command that completed its work and still has to
    report failure. Raising is the ordinary way to fail; this is for the case
    where the diagnosis *is* the payload.
    """

    data: T
    messages: list[CliMessage] = field(default_factory=list)
    warnings: list[CliMessage] = field(default_factory=list)
    next_actions: list[NextAction] = field(default_factory=list)
    error: TechtreeError | None = None


def success_envelope[T](
    *,
    command: str,
    data: T,
    messages: list[CliMessage] | None = None,
    warnings: list[CliMessage] | None = None,
    next_actions: list[NextAction] | None = None,
) -> CliEnvelope[T]:
    """Construct a successful envelope."""
    return CliEnvelope[T](
        schema_version=CLI_SCHEMA_VERSION,
        ok=True,
        command=command,
        data=data,
        messages=list(messages or ()),
        warnings=list(warnings or ()),
        next_actions=_capped(next_actions or ()),
        error=None,
    )


def failure_envelope[T](
    *,
    command: str,
    error: TechtreeError,
    data: T | None = None,
    messages: list[CliMessage] | None = None,
    warnings: list[CliMessage] | None = None,
    next_actions: list[NextAction] | None = None,
) -> CliEnvelope[T]:
    """Construct a failed envelope.

    Repair actions default to the ones the error itself carries, so a raising
    call site never has to reach the CLI to be helpful.
    """
    actions = error.next_actions if next_actions is None else next_actions
    return CliEnvelope[T](
        schema_version=CLI_SCHEMA_VERSION,
        ok=False,
        command=command,
        data=data,
        messages=list(messages or ()),
        warnings=list(warnings or ()),
        next_actions=_capped(actions),
        error=error_to_cli_error(error),
    )


def invoke_command[T](
    context: CliContext,
    command: str,
    action: Callable[[], CommandResult[T]],
    *,
    render_data: DataRenderer | None = None,
) -> NoReturn:
    """Execute, emit exactly one envelope, and exit correctly."""
    if context.debug:
        stderr_log(f"techtree: running {command}")

    envelope: CliEnvelope[T]
    try:
        result = action()
    except TechtreeError as error:
        envelope = failure_envelope(command=command, error=error)
        exit_code = exit_code_for(error)
    except Exception as unexpected:
        if context.debug:
            stderr_log(traceback.format_exc().rstrip())
        envelope = failure_envelope(command=command, error=_internal(unexpected))
        exit_code = EXIT_ERROR
    else:
        if result.error is None:
            envelope = success_envelope(
                command=command,
                data=result.data,
                messages=result.messages,
                warnings=result.warnings,
                next_actions=result.next_actions,
            )
            exit_code = EXIT_OK
        else:
            envelope = failure_envelope(
                command=command,
                error=result.error,
                data=result.data,
                messages=result.messages,
                warnings=result.warnings,
                next_actions=result.next_actions,
            )
            exit_code = exit_code_for(result.error)

    emit_envelope(context, envelope, render_data=render_data)

    if context.debug:
        stderr_log(f"techtree: {command} exited with code {exit_code}")
    raise typer.Exit(exit_code)


def emit_boundary_failure(
    *,
    json_output: bool,
    no_color: bool,
    command: str,
    error: TechtreeError,
) -> NoReturn:
    """Report a failure that happened before any command could start."""
    write_envelope(
        failure_envelope(command=command, error=error),
        json_output=json_output,
        no_color=no_color,
    )
    raise typer.Exit(exit_code_for(error))


def not_implemented_error(command: str) -> TechtreeError:
    """Return the error a registered but unbuilt command reports.

    The command name is part of the CLI surface already, so a caller can
    discover it, script it, and be told plainly that this build does not
    implement it yet — which is more useful than the command not existing.
    """
    return TechtreeError(
        f"`techtree {command}` is not implemented in this build",
        code="not_implemented",
        details={"command": command},
    )


def _internal(error: Exception) -> TechtreeError:
    return TechtreeError(
        sanitize_exception_message(error),
        code="internal_error",
        details={"exception_type": type(error).__name__},
    )


def _capped(actions: Sequence[NextAction]) -> list[NextAction]:
    """Keep the highest-priority actions and drop the rest.

    Callers order actions by usefulness. Truncating here means a caller can
    offer everything it thought of without having to know the ceiling.
    """
    return list(actions[:MAX_NEXT_ACTIONS])
