"""Detached worker entry point. Spec sections 19.1 and PR8 §8.9.

The command surface is one line: ``techtree-worker execute --run-id <id>``.
It is not a user-facing program — the CLI launches it, and a person reading
``techtree --help`` will never see it — so it has none of the CLI's apparatus.
No Rich console, no envelope, no next actions. Its stdout and stderr are the
run's ``worker.log``, and its exit code is the only thing a caller reads.

Everything the worker actually does is in :mod:`techtree.worker.execute`. This
module parses one argument and gets out of the way.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from techtree.version import package_version
from techtree.worker.execute import execute_run

__all__ = ["build_parser", "main"]


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
    """Parse and execute one run, then exit with the code it reports."""
    arguments = build_parser().parse_args(argv)
    sys.exit(execute_run(arguments.run_id))


if __name__ == "__main__":
    main()
