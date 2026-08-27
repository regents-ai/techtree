"""The offer to publish, written once. Decisions document 0038.

Two surfaces make this offer — the finished result and the proof check — and
they are the two places somebody has just been told their run holds together.
An offer that read differently depending on which of them a person happened to
be looking at would be two offers, so it is one function and both call it.

It carries ``requires_user_confirmation``, which is not advisory. Publishing is
the one thing this product does that leaves the machine, and the flag is how a
host agent is told to ask rather than act. The plugin itself publishes nothing
and can open no network connection at all; what it may do is put this command in
front of a person.
"""

from __future__ import annotations

from techtree.models.cli import NextAction

__all__ = ["publish_action"]


def publish_action(run_id: str) -> NextAction:
    """Return the offer to publish one verified run."""
    return NextAction(
        id="publish_run",
        label="Publish this run to the public run log",
        reason=(
            "The proof just verified, so the run's own evidence travels with "
            "it. It shows what would be sent and asks before sending anything."
        ),
        cli=["techtree", "proof", "publish", run_id],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=True,
    )
