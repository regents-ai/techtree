"""Model-visible tool handlers. Specification section 7.11.

Every handler takes the tool arguments and returns one JSON string, on success
and on failure alike; none of them raises into the host agent loop, and none of
them runs an evaluation synchronously. Long work returns a run identifier.

``TOOL_HANDLERS`` is the seam registration reads. A handler appears here only
once it exists, and every name in it must have a declared schema in
``schemas.py``; the plugin doctor reports the difference between the two.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Protocol


class ToolHandler(Protocol):
    """The call shape every Techtree tool handler implements."""

    def __call__(self, args: dict[str, Any], **kwargs: Any) -> str:
        """Return one JSON string describing the outcome."""


TOOL_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType({})

__all__ = ["TOOL_HANDLERS", "ToolHandler"]
