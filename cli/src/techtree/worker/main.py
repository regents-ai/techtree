"""Detached worker entry point. Spec section 19.1.

The command surface is final: ``techtree-worker execute --run-id <id>``.
``execute_run`` itself is delivered by the run/worker work package, so parsing
succeeds and execution reports that it is unavailable. No Rich output.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from techtree.version import package_version

EXIT_UNAVAILABLE = 70


def build_parser() -> argparse.ArgumentParser:
    """Create internal worker parser."""
    parser = argparse.ArgumentParser(
        prog="techtree-worker",
        description="Techtree detached run worker. Not a user-facing command.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=package_version(),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    execute = subparsers.add_parser(
        "execute",
        help="Execute a prepared run in this process.",
    )
    execute.add_argument(
        "--run-id",
        required=True,
        metavar="ID",
        help="Identifier of the prepared run to execute.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Parse and call execute_run."""
    parser = build_parser()
    arguments = parser.parse_args(argv)
    parser.exit(
        status=EXIT_UNAVAILABLE,
        message=(
            f"techtree-worker: cannot execute run {arguments.run_id}; "
            "the run executor is not part of this build.\n"
        ),
    )


if __name__ == "__main__":
    main()
