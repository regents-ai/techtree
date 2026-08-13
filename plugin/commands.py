"""Operator command surfaces. Specification section 7.12.

Two surfaces, one grammar. ``/techtree <subcommand>`` works in any session,
including a phone gateway, and answers with compact text. ``hermes techtree
...`` is terminal-only and is where Techtree's own human output belongs, so a
long watch never runs inside a model tool call.

Both registries are read at registration time. A command appears here only
once its handler exists; the grammar is fixed and nothing is passed through to
a shell.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any, NamedTuple, Protocol


class SlashCommandHandler(Protocol):
    """The call shape of an in-session ``/techtree`` handler."""

    def __call__(self, raw_args: str) -> str:
        """Return the text to show for this invocation."""


class CliCommand(NamedTuple):
    """One ``hermes techtree ...`` terminal subcommand."""

    help: str
    setup: Callable[[Any], None]
    handler: Callable[[Any], int]


SLASH_COMMANDS: Mapping[str, SlashCommandHandler] = MappingProxyType({})

CLI_COMMANDS: Mapping[str, CliCommand] = MappingProxyType({})

__all__ = ["CLI_COMMANDS", "SLASH_COMMANDS", "CliCommand", "SlashCommandHandler"]
