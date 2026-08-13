"""What every command is allowed to assume. Spec section 12.1.

One object carries the four things a command needs before it can do anything:
where local state lives, what the user configured, whether the caller is a
person or a machine, and how much detail to put on stderr. It is built once, in
the root callback, and handed down through Typer's context.

Two rules are enforced here rather than repeated in every command.

Machine mode is derived, not merely requested. ``--json`` turns it on, and so
does an ``output_mode`` of ``json`` in settings, because a caller that has
configured machine output has already said which side of the boundary it is on.

Machine mode implies ``--no-input``. A prompt written to a host agent is a
hang, not a question, so the flags cannot disagree: asking for JSON is asking
for a CLI that never waits for a human.

No command-specific service is created here. This module knows about paths and
settings and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typer

from techtree.errors import PrerequisiteError, TechtreeError
from techtree.paths import (
    TechtreePaths,
    default_paths,
    ensure_path_layout,
    paths_from_root,
)
from techtree.settings import Settings, resolved_settings

__all__ = ["CliContext", "build_cli_context", "cli_context"]


@dataclass(frozen=True)
class CliContext:
    """Everything a command may assume about its invocation."""

    paths: TechtreePaths
    settings: Settings
    json_output: bool
    no_color: bool
    no_input: bool
    debug: bool


def build_cli_context(
    *,
    home: Path | None,
    json_output: bool,
    no_color: bool,
    no_input: bool,
    debug: bool,
) -> CliContext:
    """Resolve paths, create layout, load settings, and return context."""
    paths = (
        default_paths() if home is None else paths_from_root(Path(home).expanduser())
    )

    try:
        ensure_path_layout(paths)
    except OSError as error:
        raise PrerequisiteError(
            f"cannot create the Techtree home directory {paths.root}: {error.strerror}",
            code="techtree_home_unusable",
            details={"path": str(paths.root)},
        ) from error

    settings = resolved_settings(paths)
    machine = json_output or settings.output_mode == "json"

    return CliContext(
        paths=paths,
        settings=settings,
        json_output=machine,
        no_color=no_color or machine,
        no_input=no_input or machine,
        debug=debug,
    )


def cli_context(ctx: typer.Context) -> CliContext:
    """Return the context the root callback attached to this invocation."""
    context = ctx.obj
    if not isinstance(context, CliContext):
        raise TechtreeError(
            "the CLI context was never built for this invocation",
            code="internal_error",
        )
    return context
