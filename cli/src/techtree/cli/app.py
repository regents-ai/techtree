"""Typer application entry point. Spec section 12.4.

Only ``--version`` is wired today. The remaining global options, the
``CliContext`` construction in ``root_callback``, and the ``climb`` / ``run`` /
``engine`` sub-apps arrive with the CLI foundation work package; empty Typer
groups are deliberately not created ahead of their commands.
"""

from __future__ import annotations

from typing import Annotated

import typer

from techtree.version import package_version


def version_callback(value: bool) -> None:
    """Print the package version and exit when ``--version`` is given."""
    if not value:
        return
    typer.echo(package_version())
    raise typer.Exit()


def root_callback(
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


def create_app() -> typer.Typer:
    """Construct and return the application."""
    app = typer.Typer(
        name="techtree",
        help="Techtree Climb command-line interface.",
        no_args_is_help=True,
        add_completion=False,
    )
    app.callback(invoke_without_command=True)(root_callback)
    return app


def main() -> None:
    """Run the application."""
    create_app()()


if __name__ == "__main__":
    main()
