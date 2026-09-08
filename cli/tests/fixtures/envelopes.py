"""Reading a ``techtree.cli.v2`` envelope the way a host agent would.

A test that has run the CLI holds JSON rather than models, and the one thing it
most often needs from a next action is the line that action would run. Building
it here, through the model, is what keeps a test from quietly agreeing with a
different reading of ``prepared_arguments`` than the CLI's own.
"""

from __future__ import annotations

import json
from typing import Any

from techtree.models.cli import NextAction, command_line

__all__ = ["command_line_of"]


def command_line_of(action: dict[str, Any]) -> list[str]:
    """Return the argv one next action, as JSON, would be invoked as."""
    return command_line(NextAction.model_validate_json(json.dumps(action)))
