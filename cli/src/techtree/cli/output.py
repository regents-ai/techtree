"""How one envelope reaches stdout. Spec section 12.2.

There are exactly two renderings of a response and they never mix. A machine
gets one compact JSON object and a newline. A person gets messages, a data
summary, warnings, and numbered next steps. Which one happens is decided by the
context, once, so no command can half-render.

The JSON spelling is the canonical one: sorted keys, no insignificant
whitespace. Nothing here is hashed, but a stable byte order is what makes an
envelope diffable in a test and in a bug report.

Operational logs go to stderr and only to stderr. That separation is the whole
reason a host agent can pipe stdout into a JSON parser without filtering it
first.

``shell_display`` exists so a next action can be *shown* as a command line. It
uses ``shlex.join`` and its output is display-only: the argv list is the
contract, the string is a courtesy. Nothing in Techtree ever executes a
displayed command string, which is exactly why next actions are arrays.
"""

from __future__ import annotations

import shlex
import sys
from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.table import Table

from techtree.canonical import canonical_json_text
from techtree.cli.context import CliContext
from techtree.models.cli import CliEnvelope, CliMessage, MessageLevel, NextAction

__all__ = [
    "DataRenderer",
    "emit_envelope",
    "human_console",
    "json_stdout",
    "render_human",
    "render_next_actions",
    "shell_display",
    "stderr_log",
    "write_envelope",
]

type DataRenderer = Callable[[Any, Console], None]
"""Renders one command's payload for a person. Machine mode never calls it."""

#: How each message level is introduced in human output. Plain words rather
#: than symbols, so the text survives a terminal that cannot draw them.
_LEVEL_PREFIX: dict[MessageLevel, str] = {
    MessageLevel.INFO: "",
    MessageLevel.WARNING: "Warning: ",
    MessageLevel.ERROR: "Error: ",
}

_LEVEL_STYLE: dict[MessageLevel, str] = {
    MessageLevel.INFO: "",
    MessageLevel.WARNING: "yellow",
    MessageLevel.ERROR: "red",
}


def human_console(*, no_color: bool) -> Console:
    """Return the console human output is written to.

    Rich already emits no escape sequences when stdout is not a terminal, so a
    piped human rendering is plain text without anyone asking for it.
    """
    return Console(
        file=sys.stdout,
        no_color=no_color,
        highlight=False,
        emoji=False,
        markup=False,
    )


def emit_envelope(
    context: CliContext,
    envelope: CliEnvelope[Any],
    *,
    render_data: DataRenderer | None = None,
) -> None:
    """Write one JSON object or render human output."""
    write_envelope(
        envelope,
        json_output=context.json_output,
        no_color=context.no_color,
        render_data=render_data,
    )


def write_envelope(
    envelope: CliEnvelope[Any],
    *,
    json_output: bool,
    no_color: bool,
    render_data: DataRenderer | None = None,
) -> None:
    """Write one envelope without needing a fully built context.

    The error boundary reaches this directly: a failure while the context is
    still being built still owes the caller exactly one response.
    """
    if json_output:
        json_stdout(envelope)
        return
    render_human(envelope, human_console(no_color=no_color), render_data=render_data)


def render_human(
    envelope: CliEnvelope[Any],
    console: Console,
    *,
    render_data: DataRenderer | None = None,
) -> None:
    """Render messages, typed data summaries, warnings, and next actions."""
    for message in envelope.messages:
        _render_message(message, console)

    if envelope.data is not None and render_data is not None:
        if envelope.messages:
            console.print()
        render_data(envelope.data, console)

    if envelope.warnings:
        console.print()
        for warning in envelope.warnings:
            _render_message(warning, console)

    if envelope.error is not None:
        console.print()
        console.print(f"Error: {envelope.error.message}", style="red")
        console.print(f"Code: {envelope.error.code}")

    render_next_actions(envelope.next_actions, console)


def render_next_actions(actions: list[NextAction], console: Console) -> None:
    """Render ordered next steps with display-only shell quoting."""
    if not actions:
        return

    console.print()
    console.print("Next steps:")
    table = Table(box=None, show_header=False, pad_edge=False, padding=(0, 1))
    table.add_column("index", justify="right", no_wrap=True)
    # Folded rather than truncated. A next step is meant to be typed, and a
    # command with an ellipsis in the middle of a path cannot be: a
    # materialized Skill's cache directory alone is seventy-one characters
    # (decisions document 0010 item 5), so the one place a reader most needs
    # the whole line is the place a narrow terminal would cut it.
    table.add_column("step", overflow="fold")

    for position, action in enumerate(actions, start=1):
        lines = [action.label]
        if action.cli is not None:
            lines.append(shell_display(action.cli))
        if action.reason is not None:
            lines.append(action.reason)
        if action.requires_user_confirmation:
            lines.append("Requires confirmation by a person before it runs.")
        table.add_row(f"{position}.", "\n".join(lines))

    console.print(table)


def shell_display(argv: list[str]) -> str:
    """Use shlex.join for display only."""
    return shlex.join(argv)


def json_stdout(envelope: CliEnvelope[Any]) -> None:
    """Write one compact JSON object and one newline."""
    sys.stdout.write(canonical_json_text(envelope))
    sys.stdout.write("\n")
    sys.stdout.flush()


def stderr_log(message: str) -> None:
    """Write operational logs to stderr."""
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()


def _render_message(message: CliMessage, console: Console) -> None:
    prefix = _LEVEL_PREFIX[message.level]
    console.print(f"{prefix}{message.text}", style=_LEVEL_STYLE[message.level] or None)
