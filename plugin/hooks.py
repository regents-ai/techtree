"""Session lifecycle hooks. Specification section 7.13.

Both hooks do local bookkeeping and nothing else. Neither reaches the network,
installs anything, runs Docker, or calls a model, and neither ever deletes a
Techtree run, Skill, report, or proof bundle — the plugin owns none of those,
and a tidy-up that removed someone's evidence would be a catastrophe dressed
as housekeeping.

Both take ``**kwargs`` so a host that starts passing more context does not
break this plugin, and neither raises: a session must not fail to start
because bookkeeping did.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Protocol

from .errors import scrub_text
from .state import prune_expired_plans, prune_expired_sessions


class SessionHook(Protocol):
    """The call shape of a session lifecycle callback."""

    def __call__(self, **kwargs: Any) -> None:
        """Handle the session event. Never raises into the host."""


def build_session_hooks(services: Any) -> Mapping[str, SessionHook]:
    """Return the lifecycle callbacks bound to this session's services."""

    def on_session_start(**kwargs: Any) -> None:
        """Drop offers and sessions that have run out.

        An installation offer older than its few minutes, or a demo session
        nobody has touched in a week, is not something to act on. Nothing here
        asks Techtree anything: a session start must be instant, and a run's
        state is read when someone actually asks about it.
        """
        _quietly(lambda: prune_expired_plans(services))
        _quietly(lambda: prune_expired_sessions(services))

    def on_session_end(**kwargs: Any) -> None:
        """Forget the offers this session made.

        Plugin state lives in memory, so there is nothing to flush and no file
        to remove. What matters is what is *not* touched: every Techtree run,
        Skill, report, and proof bundle is left exactly where it is.
        """
        _quietly(lambda: prune_expired_plans(services))

    return MappingProxyType(
        {"on_session_start": on_session_start, "on_session_end": on_session_end}
    )


#: The hooks this plugin declares. The callbacks themselves are built per
#: session by :func:`build_session_hooks`.
SESSION_HOOKS: Mapping[str, str] = {
    "on_session_start": "prune expired installation offers and stale sessions",
    "on_session_end": "forget this session's offers, and touch nothing else",
}


def _quietly(work: Any) -> None:
    """Run bookkeeping that must never break a session."""
    try:
        work()
    except Exception as error:
        import logging

        logging.getLogger(__name__).debug(
            "techtree plugin housekeeping skipped: %s", scrub_text(str(error))
        )


__all__ = ["SESSION_HOOKS", "SessionHook", "build_session_hooks"]
