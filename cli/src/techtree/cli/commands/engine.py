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
from techtree.errors import EngineError
from techtree.models.base import Digest
from techtree.models.cli import (
    CliWarning,
    DataEgress,
    NextAction,
    Operation,
    RetryClass,
    SideEffect,
    invocation,
)
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
        # Reported before the install, which is what discards it. Decisions
        # 0004, ratified as 0007 R7.
        interrupted = installer.interrupted_installs()
        status = installer.install(_requested(digest))

        return CommandResult(
            data=status,
            warnings=[
                CliWarning(
                    id="engine_install_interrupted",
                    text=(
                        f"An earlier install of evaluation engine "
                        f"{install.digest} did not finish. What it left behind "
                        "was removed and the engine was installed again."
                    ),
                    resolvable_by=None,
                )
                for install in interrupted
            ],
            next_actions=[_activate_or_browse(registry, status)],
        )

    invoke_command(
        context, Operation.ACTION_EXECUTE, action, render_data=_render_installed
    )


def status_engine_command(ctx: typer.Context, digest: DigestArgument = None) -> None:
    """Return installation and activation status."""
    context = cli_context(ctx)

    def action() -> CommandResult[EngineStatus]:
        registry = EngineRegistry(context.paths, context.settings)
        status = registry.status(_selected(context, digest))

        return CommandResult(
            data=status,
            next_actions=[
                _activate_or_browse(registry, status)
                if status.installed
                else _install_action()
            ],
        )

    invoke_command(context, Operation.PLAN_INSPECT, action, render_data=_render_status)


def verify_engine_command(ctx: typer.Context, digest: DigestArgument = None) -> None:
    """Recompute bundle and live-environment checks."""
    context = cli_context(ctx)

    def action() -> CommandResult[EngineStatus]:
        registry = EngineRegistry(context.paths, context.settings)
        installer = EngineInstaller(context.paths, registry, find_uv())
        try:
            status = installer.verify(_selected(context, digest))
        except EngineError as error:
            # Verifying an engine that is not there has one repair, and it is
            # not verifying it again. The installer knows the engine is
            # missing; what to do about it is this command's call.
            if error.code == "engine_not_installed" and not error.next_actions:
                error.next_actions = [_install_action()]
            raise

        return CommandResult(
            data=status,
            next_actions=[_activate_or_browse(registry, status)],
        )

    invoke_command(
        context, Operation.PLAN_INSPECT, action, render_data=_render_verified
    )


def render_engine_status(status: EngineStatus, console: Console) -> None:
    """Print one engine's state for a person."""
    console.print(f"Engine:     {status.digest}")
    console.print(f"Location:   {status.path}")
    console.print(f"Installed:  {'yes' if status.installed else 'no'}")
    console.print(f"Verified:   {'yes' if status.verified else 'no'}")
    console.print(f"Active:     {'yes' if status.active else 'no'}")
    if status.python_executable is not None:
        console.print(f"Python:     {status.python_executable}")


def _render_installed(data: object, console: Console) -> None:
    """Say what was installed, then show the engine it left."""
    if not isinstance(data, EngineStatus):
        return
    console.print(
        f"Evaluation engine {data.digest} is installed and verified at {data.path}."
    )
    console.print()
    render_engine_status(data, console)


def _render_status(data: object, console: Console) -> None:
    """Say where this engine stands, then show it."""
    if not isinstance(data, EngineStatus):
        return
    console.print(f"Evaluation engine {data.digest} is {data.detail}.")
    console.print()
    render_engine_status(data, console)


def _render_verified(data: object, console: Console) -> None:
    """Say what verifying proved, then show the engine it proved it of."""
    if not isinstance(data, EngineStatus):
        return
    console.print(
        f"Evaluation engine {data.digest} holds the files it was installed "
        "with and runs the pinned validator."
    )
    console.print()
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
        operation=Operation.ACTION_EXECUTE,
        prepared_arguments=invocation("engine", "install"),
        expected_state_digest=None,
        side_effect=SideEffect.LOCAL_STATE,
        approval_required=False,
        retry_class=RetryClass.SAFE,
        estimated_cost=None,
        data_egress=DataEgress.PACKAGE_INDEX,
        reason="Preparing or starting a Climb needs an installed, active engine.",
    )


def _activate_or_browse(registry: EngineRegistry, status: EngineStatus) -> NextAction:
    """Offer setup when the new engine is not the active one, else browsing."""
    if registry.active_digest() == status.digest:
        return NextAction(
            operation=Operation.PLAN_INSPECT,
            prepared_arguments=invocation("climb", "list"),
            expected_state_digest=None,
            side_effect=SideEffect.NONE,
            approval_required=False,
            retry_class=RetryClass.SAFE,
            estimated_cost=None,
            data_egress=DataEgress.NONE,
            reason="The evaluation engine is ready; these are the Climbs it runs.",
        )
    return NextAction(
        operation=Operation.ACTION_EXECUTE,
        prepared_arguments=invocation("setup"),
        expected_state_digest=None,
        side_effect=SideEffect.LOCAL_STATE,
        approval_required=False,
        retry_class=RetryClass.SAFE,
        estimated_cost=None,
        data_egress=DataEgress.PACKAGE_INDEX,
        reason="The engine is installed but is not the active one yet.",
    )
