"""How one envelope reaches stdout. Spec section 12.2.

There are exactly two renderings of a response and they never mix. A machine
gets one compact JSON object and a newline. A person gets the command's own
summary of what it found, then what is in the way, what could not be
determined, what must still be seen, what bytes are referred to, and the
numbered next steps. Which one happens is decided by the context, once, so no
command can half-render.

The JSON spelling is the canonical one: sorted keys, no insignificant
whitespace. Nothing here is hashed, but a stable byte order is what makes an
envelope diffable in a test and in a bug report.

Operational logs go to stderr and only to stderr. That separation is the whole
reason a host agent can pipe stdout into a JSON parser without filtering it
first.

``techtree.cli.v2`` has no free-text message channel, so every sentence a
person reads here is built from the typed answer rather than carried beside it.
A command's own opening line is written by its renderer, out of the payload it
just produced; there is no way for the words a person sees to describe
something the machine answer does not contain.

``shell_display`` exists so a next action can be *shown* as a command line. It
uses ``shlex.join`` and its output is display-only: the prepared arguments are
the contract, the string is a courtesy. Nothing in Techtree ever executes a
displayed command string, which is exactly why an action carries a named
invocation rather than a line of shell.
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
    CliBlocker,
    CliEnvelope,
    CliError,
    CliUnknown,
    CliWarning,
    ContentRef,
    NextAction,
    command_line,
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
    """Render the payload, then everything the caller still has to know.

    The order is the order somebody acts in: what was found, what stops them,
    what nobody could establish, what they must see anyway, where the bytes
    are, what went wrong, and what to do next.
    """
    if envelope.facts is not None and render_data is not None:
        render_data(envelope.facts, console)

    _render_block(console, [_blocker_text(entry) for entry in envelope.blockers], "red")
    _render_block(console, [_unknown_text(entry) for entry in envelope.unknowns], None)
    _render_block(
        console, [_warning_text(entry) for entry in envelope.warnings], "yellow"
    )
    _render_content_refs(envelope.content_refs, console)

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


def _render_block(console: Console, lines: list[str], style: str | None) -> None:
    """Print one group of typed entries, or nothing when there are none."""
    if not lines:
        return
    console.print()
    for line in lines:
        console.print(line, style=style)


def _blocker_text(blocker: CliBlocker) -> str:
    """Say what is in the way.

    Which operations it forbids is not repeated here. That list is a machine
    identifier apiece, and a person reading a terminal is being told what is
    wrong and shown the step that fixes it, which is the same fact in the words
    they came for.
    """
    return f"Blocked: {blocker.text}"


def _unknown_text(unknown: CliUnknown) -> str:
    """Say what could not be established, never a zero in its place."""
    return f"Not determined: {unknown.reason}"


def _warning_text(warning: CliWarning) -> str:
    return f"Warning: {warning.text}"


def _render_content_refs(refs: list[ContentRef], console: Console) -> None:
    """Point at the bytes the answer refers to rather than carries."""
    if not refs:
        return
    console.print()
    console.print("Files")
    render_pairs(
        [(ref.kind, ref.path or ref.url or "") for ref in refs],
        console,
    )


def _step_text(action: NextAction) -> Text:
    """Return one next step with the line a person types set apart.

    A step is the command, then why it is offered. The command is the only one
    of them anybody retypes, so it is the one the eye should land on, and the
    reason is the one a reader who already knows why can pass over. Weight says
    that without moving anything or changing a word.

    The styles are carried by a :class:`~rich.text.Text` rather than by a
    marked-up string. Nothing this console prints is read for markup, so a
    label or a path that happens to contain square brackets is drawn as the
    characters it is made of and cannot choose a colour for itself.
    """
    step = Text()
    step.append(shell_display(command_line(action)), style="bold")
    step.append("\n")
    step.append(action.reason, style="dim")
    if action.approval_required:
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
