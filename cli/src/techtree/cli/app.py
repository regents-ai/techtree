"""The Typer application. Spec section 12.4.

This module wires and nothing else. It declares the global options, builds the
:class:`~techtree.cli.context.CliContext` once in the root callback, registers
the command groups, and closes the last gap in the error boundary: a typed
failure raised while the context is still being built still owes the caller one
envelope and one documented exit code.

``climb``, ``skill``, ``run``, ``engine``, ``proof``, ``release`` and
``uplift`` are registered with their real names even where this build
implements only some of what each will eventually hold. ``publish`` and
``withdraw`` are commands rather than groups, because each is one thing a
person does and neither has a second member to hold. A name
that exists and answers ``not_implemented`` is discoverable and scriptable; a
name that does not exist yet is indistinguishable from a typo. The reserved
namespaces — ``program``, ``blueprint``, ``forge``, ``verify``, ``trace``,
``lab`` — get no group at all, because an empty group in ``--help`` is a
promise about a shape that has not been decided. ``uplift`` left that list when
spec section 7.21's improvement commands landed and it stopped being a shape
nobody had decided.

Global options are accepted anywhere on the command line. ``techtree --json
doctor`` and ``techtree doctor --json`` mean the same thing, because a caller
scripting the boundary should not have to know that one of those flags belongs
to a group and the other to a command.

Argument parsing happens before any of this. A malformed command line is
reported by the parser with exit code 2, and a bare ``techtree`` prints help;
neither reaches a command, and the one-envelope rule covers every invocation
that does.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Annotated, Any, NoReturn

import typer
from typer.core import TyperGroup

from techtree.cli.commands.climb import (
    list_climbs_command,
    prepare_climb_command,
    show_climb_command,
    start_climb_command,
)
from techtree.cli.commands.doctor import doctor_command
from techtree.cli.commands.engine import (
    install_engine_command,
    status_engine_command,
    verify_engine_command,
)
from techtree.cli.commands.proof import verify_proof_command
from techtree.cli.commands.publish import publish_run_command
from techtree.cli.commands.release import (
    info_release_command,
    verify_release_command,
)
from techtree.cli.commands.run import (
    cancel_run_command,
    logs_run_command,
    result_run_command,
    status_run_command,
)
from techtree.cli.commands.setup import setup_command
from techtree.cli.commands.skill import starter_skill_command
from techtree.cli.commands.uplift import (
    context_uplift_command,
    prepare_uplift_command,
    skill_source_uplift_command,
    start_uplift_command,
)
from techtree.cli.commands.withdraw import withdraw_run_command
from techtree.cli.context import build_cli_context
from techtree.cli.invoke import emit_boundary_failure, failure_envelope
from techtree.cli.output import write_envelope
from techtree.errors import (
    TechtreeError,
    UsageError,
    exit_code_for,
    stable_exception_message,
)
from techtree.version import package_version

__all__ = ["create_app", "main", "root_callback"]

#: Namespaces that belong to Techtree but are not part of this product surface
#: yet. Listed so the choice is visible in code review rather than implied by
#: absence, and asserted by the CLI contract tests.
RESERVED_NAMESPACES: tuple[str, ...] = (
    "program",
    "blueprint",
    "forge",
    "verify",
    "trace",
    "lab",
)


#: Global switches, and the one global option that takes a value. Both lists
#: exist so a global option can be recognized wherever it appears.
GLOBAL_FLAGS: frozenset[str] = frozenset(
    {"--json", "--no-color", "--no-input", "--debug", "--version"}
)
GLOBAL_VALUE_OPTIONS: frozenset[str] = frozenset({"--home"})


def hoist_global_options(args: Sequence[str]) -> list[str]:
    """Move global options to the front of the command line.

    The parser binds an option to whichever command declares it, and the global
    options are declared once, on the root. Moving them forward is what lets
    them be written last, where a person naturally puts them. Everything after
    a literal ``--`` is left exactly where it is.
    """
    leading: list[str] = []
    trailing: list[str] = []
    index = 0

    while index < len(args):
        token = args[index]
        if token == "--":
            trailing.extend(args[index:])
            break
        if token in GLOBAL_FLAGS or any(
            token.startswith(f"{name}=") for name in GLOBAL_VALUE_OPTIONS
        ):
            leading.append(token)
        elif token in GLOBAL_VALUE_OPTIONS and index + 1 < len(args):
            leading.extend(args[index : index + 2])
            index += 1
        else:
            trailing.append(token)
        index += 1

    return [*leading, *trailing]


class TechtreeGroup(TyperGroup):
    """Root group that accepts global options anywhere on the command line."""

    def parse_args(self, ctx: Any, args: list[str]) -> list[str]:
        """Hoist global options, then parse normally."""
        return list(super().parse_args(ctx, hoist_global_options(args)))


def version_callback(value: bool) -> None:
    """Print the package version and exit when ``--version`` is given."""
    if not value:
        return
    typer.echo(package_version())
    raise typer.Exit()


def root_callback(
    ctx: typer.Context,
    home: Annotated[
        Path | None,
        typer.Option(
            "--home",
            help="Directory Techtree keeps its local state in.",
            metavar="PATH",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit one JSON envelope instead of human output."),
    ] = False,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Never colour human output."),
    ] = False,
    no_input: Annotated[
        bool,
        typer.Option("--no-input", help="Never prompt; fail instead of asking."),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Write operational detail to stderr."),
    ] = False,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=version_callback,
            is_eager=True,
            help="Show the Techtree version and exit.",
        ),
    ] = False,
) -> None:
    """Techtree Climb command-line interface."""
    if ctx.invoked_subcommand is None:
        emit_boundary_failure(
            json_output=json_output,
            no_color=no_color,
            command="techtree",
            error=UsageError(
                "no command was given; run `techtree --help` for the available "
                "commands",
                code="no_command",
            ),
        )

    try:
        ctx.obj = build_cli_context(
            home=home,
            json_output=json_output,
            no_color=no_color,
            no_input=no_input,
            debug=debug,
        )
    except TechtreeError as error:
        emit_boundary_failure(
            json_output=json_output,
            no_color=no_color,
            command=ctx.invoked_subcommand,
            error=error,
        )


def create_app() -> typer.Typer:
    """Construct and return the application."""
    app = typer.Typer(
        name="techtree",
        cls=TechtreeGroup,
        help="Techtree Climb command-line interface.",
        no_args_is_help=True,
        add_completion=False,
        pretty_exceptions_enable=False,
    )
    app.callback(invoke_without_command=True)(root_callback)
    app.command("doctor", help="Check that this machine is ready to run a Climb.")(
        doctor_command
    )
    app.command("setup", help="Prepare this machine to run a Climb.")(setup_command)
    # Publishing and withdrawing are top-level commands rather than members of
    # ``proof`` (decisions 0038's founder ruling of 2026-08-27). ``proof`` is
    # where a person checks evidence offline; these two are the only commands in
    # Techtree that send anything anywhere, and burying them one level down made
    # them read as a variation on checking a proof.
    app.command(
        "publish",
        help="Publish a verified run's proof to the public run log.",
    )(publish_run_command)
    app.command(
        "withdraw",
        help="Withdraw a published entry from the public run log.",
    )(withdraw_run_command)

    app.add_typer(_climb_app(), name="climb")
    app.add_typer(_skill_app(), name="skill")
    app.add_typer(_run_app(), name="run")
    app.add_typer(_engine_app(), name="engine")
    app.add_typer(_proof_app(), name="proof")
    app.add_typer(_release_app(), name="release")
    app.add_typer(_uplift_app(), name="uplift")
    return app


def main() -> None:
    """Run the application."""
    try:
        create_app()()
    except TechtreeError as error:
        _last_resort(error)
    except Exception as unexpected:
        _last_resort(
            TechtreeError(
                stable_exception_message(unexpected),
                code="internal_error",
                details={"exception_type": type(unexpected).__name__},
            )
        )


# ---------------------------------------------------------------------------
# Command groups
# ---------------------------------------------------------------------------


def _climb_app() -> typer.Typer:
    app = typer.Typer(help="Browse and enter Climbs.", no_args_is_help=True)

    app.command("list", help="Show the Climbs available in this build.")(
        list_climbs_command
    )
    app.command(
        "show",
        help="Show what a Climb measures, the data rights it carries, and "
        "whether this machine can run it.",
    )(show_climb_command)

    app.command("prepare", help="Prepare a skill for submission to a Climb.")(
        prepare_climb_command
    )
    app.command("start", help="Start a prepared submission running.")(
        start_climb_command
    )
    return app


def _run_app() -> typer.Typer:
    app = typer.Typer(help="Follow and control your runs.", no_args_is_help=True)

    app.command("status", help="Show how a run is progressing.")(status_run_command)
    app.command("logs", help="Show the log output of a run.")(logs_run_command)
    app.command("cancel", help="Stop a run that is still in progress.")(
        cancel_run_command
    )
    app.command("result", help="Show the finished report for a run.")(
        result_run_command
    )
    return app


def _skill_app() -> typer.Typer:
    app = typer.Typer(help="Obtain the Skills a release names.", no_args_is_help=True)

    app.command(
        "starter",
        help="Put the starter Skill this release pins on this machine.",
    )(starter_skill_command)
    return app


def _uplift_app() -> typer.Typer:
    app = typer.Typer(help="Improve a Skill from a finished run.", no_args_is_help=True)

    app.command(
        "context",
        help="Export the sanitized improvement context for a finished run.",
    )(context_uplift_command)
    app.command(
        "skill-source",
        help="Show the verified text of the Skill a finished run measured.",
    )(skill_source_uplift_command)
    app.command(
        "prepare",
        help="Prepare a comparison between a run's Skill and a revision of it.",
    )(prepare_uplift_command)
    app.command("start", help="Start a prepared Skill-against-Skill comparison.")(
        start_uplift_command
    )
    return app


def _proof_app() -> typer.Typer:
    app = typer.Typer(help="Check local proofs.", no_args_is_help=True)

    app.command(
        "verify",
        help="Check a local proof offline, from the bytes the run stored.",
    )(verify_proof_command)
    return app


def _release_app() -> typer.Typer:
    app = typer.Typer(
        help="Show and check the release this build belongs to.",
        no_args_is_help=True,
    )

    app.command("info", help="Show the release coordinates this build carries.")(
        info_release_command
    )
    app.command(
        "verify",
        help="Check that every release coordinate still names what it claims.",
    )(verify_release_command)
    return app


def _engine_app() -> typer.Typer:
    app = typer.Typer(
        help="Install and check the evaluation engine.", no_args_is_help=True
    )
    app.command("install", help="Install the evaluation engine on this machine.")(
        install_engine_command
    )
    app.command("status", help="Show which evaluation engine is installed and in use.")(
        status_engine_command
    )
    app.command("verify", help="Confirm the installed evaluation engine is intact.")(
        verify_engine_command
    )
    return app


# ---------------------------------------------------------------------------
# Last-resort boundary
# ---------------------------------------------------------------------------


def _last_resort(error: TechtreeError) -> NoReturn:
    """Report a failure that escaped every command's own boundary.

    Nothing here can consult a ``CliContext`` — the failure may be the reason
    there is not one — so the output mode is read straight off the command line
    and the environment. This path is for defects; every ordinary failure is
    handled where the context exists.
    """
    write_envelope(
        failure_envelope(command="techtree", error=error),
        json_output=_machine_mode(sys.argv[1:], os.environ),
        no_color=True,
    )
    raise SystemExit(exit_code_for(error))


def _machine_mode(argv: Sequence[str], environ: Mapping[str, str]) -> bool:
    """Decide the output mode without a parsed command line."""
    return "--json" in argv or environ.get("TECHTREE_OUTPUT_MODE") == "json"
