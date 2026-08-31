"""Checking what a caller asked for, before it becomes a command line.

Specification sections 7.4 and 7.11. Arguments arrive from a model, so they
are treated as claims rather than facts. Two rules matter most: an identifier
has a shape, and nothing may look like an option — a value beginning with a
dash would be read by the CLI as a flag rather than as the thing it names.
"""

from __future__ import annotations

import re
from typing import Final

from ..cli.errors import PluginError

CODE_TOOL_ARGUMENT_INVALID: Final = "tool_argument_invalid"

RUN_ID: Final = re.compile(r"^run_[0-9a-f]{32}$")
DRAFT_ID: Final = re.compile(r"^draft_[0-9a-f]{32}$")
CLIMB_REFERENCE: Final = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}(@[0-9A-Za-z.-]{1,16})?$")
LABEL: Final = re.compile(r"^[0-9A-Za-z][0-9A-Za-z ._-]{0,63}$")
TOKEN: Final = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
DIGEST: Final = re.compile(r"^sha256:[0-9a-f]{64}$")

MAXIMUM_PATH_CHARACTERS: Final = 4096


def _require(value: str, pattern: re.Pattern[str], description: str) -> str:
    if not pattern.match(value):
        raise PluginError(
            f"{value!r} is not {description}", code=CODE_TOOL_ARGUMENT_INVALID
        )
    return value


def require_run_id(value: str) -> str:
    """Return a well-formed run identifier."""
    return _require(value, RUN_ID, "a run identifier")


def require_draft_id(value: str) -> str:
    """Return a well-formed draft identifier."""
    return _require(value, DRAFT_ID, "a prepared draft identifier")


def require_climb_reference(value: str) -> str:
    """Return a well-formed Climb reference."""
    return _require(value, CLIMB_REFERENCE, "a Climb reference")


def require_label(value: str) -> str:
    """Return a label safe to carry through to a report."""
    return _require(value, LABEL, "a label")


def require_digest(value: str, description: str = "a sha256 digest") -> str:
    """Return a well-formed digest."""
    return _require(value, DIGEST, description)


def require_local_path(value: str, name: str) -> str:
    """Return a path the user named, refusing anything that reads as a flag.

    The plugin never invents a path, never completes one, and never reuses a
    path it returned for something else. A path that begins with a dash would
    be read by the CLI as an option, so it is refused outright.
    """
    path = value.strip()
    if not path:
        raise PluginError(
            f"{name} must be a path the user named", code=CODE_TOOL_ARGUMENT_INVALID
        )
    if path.startswith("-"):
        raise PluginError(
            f"{name} may not begin with a dash", code=CODE_TOOL_ARGUMENT_INVALID
        )
    if "\x00" in path or len(path) > MAXIMUM_PATH_CHARACTERS:
        raise PluginError(
            f"{name} is not a usable path", code=CODE_TOOL_ARGUMENT_INVALID
        )
    return path
