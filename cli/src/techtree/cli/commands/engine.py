"""``techtree engine install|status|verify``. Spec section 12.8.

The commands are plumbing. Which engine this build ships, what installing one
involves, and what counts as verified are the engine subsystem's decisions;
these three functions choose an engine, call it, and hand the result to the
envelope machinery.

Choosing an engine follows one rule: an explicit digest wins, then the active
engine, then the engine this build ships. That order is what makes
``techtree engine status`` answer the question a person actually asked —
"what am I about to run things with?" — without them having to name it.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from techtree.canonical import validate_digest
from techtree.cli.context import CliContext, cli_context
from techtree.cli.invoke import CommandResult, invoke_command
from techtree.engines.bundle import default_engine_digest
from techtree.engines.installer import EngineInstaller, find_uv
from techtree.engines.registry import EngineRegistry
from techtree.models.base import Digest
from techtree.models.cli import CliMessage, MessageLevel, NextAction
from techtree.models.engine import EngineStatus

__all__ = [
    "install_engine_command",
    "render_engine_status",
    "status_engine_command",
    "verify_engine_command",
]

DigestArgument = Annotated[
    str | None,
    typer.Argument(
        metavar="[DIGEST]",
        help="The engine to act on. Defaults to the active or shipped engine.",
    ),
]


def install_engine_command(ctx: typer.Context, digest: DigestArgument = None) -> None:
    """Install the selected or default embedded engine."""
    context = cli_context(ctx)

    def action() -> CommandResult[EngineStatus]:
        registry = EngineRegistry(context.paths, context.settings)
        installer = EngineInstaller(context.paths, registry, find_uv())
        status = installer.install(_requested(digest))

        return CommandResult(
            data=status,
            messages=[
                CliMessage(
                    level=MessageLevel.INFO,
                    code="engine_installed",
                    text=(
                        f"Evaluation engine {status.digest} is installed and "
                        f"verified at {status.path}."
                    ),
                )
            ],
            next_actions=[_activate_or_browse(registry, status)],
        )

    invoke_command(context, "engine install", action, render_data=_render)


def status_engine_command(ctx: typer.Context, digest: DigestArgument = None) -> None:
    """Return installation and activation status."""
    context = cli_context(ctx)

    def action() -> CommandResult[EngineStatus]:
        registry = EngineRegistry(context.paths, context.settings)
        status = registry.status(_selected(context, digest))

        return CommandResult(
            data=status,
            messages=[
                CliMessage(
                    level=MessageLevel.INFO,
                    code="engine_status",
                    text=f"Evaluation engine {status.digest} is {status.detail}.",
                )
            ],
            next_actions=[] if status.installed else [_install_action()],
        )

    invoke_command(context, "engine status", action, render_data=_render)


def verify_engine_command(ctx: typer.Context, digest: DigestArgument = None) -> None:
    """Recompute bundle and live-environment checks."""
    context = cli_context(ctx)

    def action() -> CommandResult[EngineStatus]:
        registry = EngineRegistry(context.paths, context.settings)
        installer = EngineInstaller(context.paths, registry, find_uv())
        status = installer.verify(_selected(context, digest))

        return CommandResult(
            data=status,
            messages=[
                CliMessage(
                    level=MessageLevel.INFO,
                    code="engine_verified",
                    text=(
                        f"Evaluation engine {status.digest} holds the files it "
                        "was installed with and runs the pinned validator."
                    ),
                )
            ],
        )

    invoke_command(context, "engine verify", action, render_data=_render)


def render_engine_status(status: EngineStatus, console: Console) -> None:
    """Print one engine's state for a person."""
    console.print(f"Engine:     {status.digest}")
    console.print(f"Location:   {status.path}")
    console.print(f"Installed:  {'yes' if status.installed else 'no'}")
    console.print(f"Verified:   {'yes' if status.verified else 'no'}")
    console.print(f"Active:     {'yes' if status.active else 'no'}")
    if status.python_executable is not None:
        console.print(f"Python:     {status.python_executable}")


def _render(data: object, console: Console) -> None:
    if isinstance(data, EngineStatus):
        render_engine_status(data, console)


def _requested(digest: str | None) -> Digest | None:
    """Validate an explicitly requested digest."""
    return None if digest is None else validate_digest(digest)


def _selected(context: CliContext, digest: str | None) -> Digest:
    """Return the engine a command without an argument is about."""
    explicit = _requested(digest)
    if explicit is not None:
        return explicit
    active = context.settings.active_engine_digest
    if active is not None:
        return active
    return default_engine_digest()


def _install_action() -> NextAction:
    return NextAction(
        id="install_engine",
        label="Install the managed evaluation engine",
        reason="Preparing or starting a Climb needs an installed, active engine.",
        cli=["techtree", "engine", "install"],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )


def _activate_or_browse(registry: EngineRegistry, status: EngineStatus) -> NextAction:
    """Offer setup when the new engine is not the active one, else browsing."""
    if registry.active_digest() == status.digest:
        return NextAction(
            id="list_climbs",
            label="Browse the available Climbs",
            reason="The evaluation engine is ready.",
            cli=["techtree", "climb", "list"],
            hermes_tool=None,
            hermes_args=None,
            requires_user_confirmation=False,
        )
    return NextAction(
        id="run_setup",
        label="Finish setting this machine up",
        reason="The engine is installed but is not the active one yet.",
        cli=["techtree", "setup"],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )
