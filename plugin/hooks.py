"""Session lifecycle hooks. Specification section 7.13.

Both hooks do local bookkeeping only — pruning expired install plans, tidying
plugin-owned temporary files, reconciling convenience state against run
identifiers the CLI already knows about. Neither reaches the network, installs
anything, runs Docker, or calls a model, and neither ever deletes a Techtree
run, Skill, report, or proof bundle.

Every callback takes ``**kwargs`` so that a host which starts passing more
context does not break this plugin.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Protocol


class SessionHook(Protocol):
    """The call shape of a session lifecycle callback."""

    def __call__(self, **kwargs: Any) -> None:
        """Handle the session event. Never raises into the host."""


SESSION_HOOKS: Mapping[str, SessionHook] = MappingProxyType({})

__all__ = ["SESSION_HOOKS", "SessionHook"]
