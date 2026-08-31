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
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from techtree.canonical import canonical_json_text
from techtree.cli.context import CliContext
from techtree.models.cli import (
    CliEnvelope,
    CliError,
    CliMessage,
    MessageLevel,
    NextAction,
)

__all__ = [
    "DataRenderer",
    "emit_envelope",
    "human_console",
    "json_stdout",
    "render_human",
    "render_next_actions",
    "render_pairs",
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
        _render_error(envelope.error, console)

    render_next_actions(envelope.next_actions, console)


def render_next_actions(actions: list[NextAction], console: Console) -> None:
    """Render ordered next steps with display-only shell quoting."""
    if not actions:
        return

    console.print()
    # Decision 0024 section 7: a successful response ends with one immediate
    # action, so the one-action case is headed the way that rule reads.
    console.print("Next:" if len(actions) == 1 else "Next steps:")
    table = Table(box=None, show_header=False, pad_edge=False, padding=(0, 1))
    table.add_column("index", justify="right", no_wrap=True)
    # Folded rather than truncated. A next step is meant to be typed, and a
    # command with an ellipsis in the middle of a path cannot be: a
    # materialized Skill's cache directory alone is seventy-one characters
    # (decisions document 0010 item 5), so the one place a reader most needs
    # the whole line is the place a narrow terminal would cut it.
    table.add_column("step", overflow="fold")

    # One step is not a list, so it is not numbered like one.
    numbered = len(actions) > 1
    for position, action in enumerate(actions, start=1):
        table.add_row(f"{position}." if numbered else "", _step_text(action))

    console.print(table)


def render_pairs(pairs: list[tuple[str, str]], console: Console) -> None:
    """Render labelled facts as one two-column table.

    Almost every command that shows a person what it found shows it this way:
    a short label on the left and the value beside it. They were built one at a
    time and drifted apart, and a reader moving between two commands should not
    have to notice that they are looking at the same thing drawn differently.

    The label is dimmed and the value is not, because the value is what the
    reader came for and the label is only there to say which value it is.

    The value column folds rather than truncates, for the reason given where
    next actions do the same: a folded digest or path can still be copied out
    of a narrow terminal and a shortened one cannot.
    """
    table = Table(box=None, show_header=False, pad_edge=False, padding=(0, 2))
    table.add_column("label", no_wrap=True, style="dim")
    table.add_column("value", overflow="fold")
    for label, value in pairs:
        table.add_row(label, value)
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


def _step_text(action: NextAction) -> Text:
    """Return one next step with the line a person types set apart.

    A step is up to three lines that used to look alike: what it is, the
    command, and why. The command is the only one of them anybody retypes, so
    it is the one the eye should land on, and the reason is the one a reader
    who already knows why can pass over. Weight says that without moving
    anything or changing a word, which is what was wanted here: the ordering
    and the wording are settled elsewhere and this changes neither.

    The styles are carried by a :class:`~rich.text.Text` rather than by a
    marked-up string. Nothing this console prints is read for markup, so a
    label or a path that happens to contain square brackets is drawn as the
    characters it is made of and cannot choose a colour for itself.
    """
    step = Text(action.label)
    if action.cli is not None:
        step.append("\n")
        step.append(shell_display(action.cli), style="bold")
    if action.reason is not None:
        step.append("\n")
        step.append(action.reason, style="dim")
    if action.requires_user_confirmation:
        step.append("\nRequires confirmation by a person before it runs.")
    return step


def _render_error(error: CliError, console: Console) -> None:
    """Draw a failure so that it cannot be scrolled past, when somebody is there.

    The message and the code were two ordinary lines among all the other
    ordinary lines a command prints, which is what a reader skimming a long
    response goes straight past. A frame around them says which part went
    wrong before any of the words have been read.

    The frame is drawn only for a terminal. Box-drawing characters are not
    colour: they are ordinary text and they survive a pipe, so framing a
    redirected response would push decoration into whatever reads it next.
    Redirected output stays the two plain lines it has always been, and the
    words are the same either way.

    The frame is drawn around the words rather than across the terminal.
    Nothing else in this product draws a box at all, so one that ran the full
    width would be by far the loudest thing on the screen, and a missing run
    identifier does not warrant that. Sized to its own contents it still marks
    the failure at a glance without shouting over the response it belongs to.
    """
    message = Text(f"Error: {error.message}", style="red")
    code = Text(f"Code: {error.code}")
    if not console.is_terminal:
        console.print(message)
        console.print(code)
        return

    framed = Text()
    framed.append_text(message)
    framed.append("\n")
    framed.append_text(code)
    console.print(Panel.fit(framed, border_style="red"))
