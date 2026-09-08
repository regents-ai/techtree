"""The offer to publish, written once. Decisions document 0038.

Two surfaces make this offer — the finished result and the proof check — and
they are the two places somebody has just been told their run holds together.
An offer that read differently depending on which of them a person happened to
be looking at would be two offers, so it is one function and both call it.

It carries ``approval_required``, which is not advisory. Publishing is the one
thing this product does that leaves the machine, and the flag is how a host
agent is told to ask rather than act. The plugin itself publishes nothing and
can open no network connection at all; what it may do is put this command in
front of a person.

It is also the one offer in Techtree whose retry class is not ``safe``. A
publication whose response was lost may already have been accepted, so the
answer to "did that work?" is read from the log rather than guessed at by
sending the proof a second time.
"""

from __future__ import annotations

from techtree.models.cli import (
    DataEgress,
    NextAction,
    Operation,
    RetryClass,
    SideEffect,
    invocation,
)

__all__ = ["publish_action"]


def publish_action(run_id: str) -> NextAction:
    """Return the offer to publish one verified run."""
    return NextAction(
        operation=Operation.ACTION_PREPARE,
        prepared_arguments=invocation("publish", arguments=[run_id]),
        expected_state_digest=None,
        side_effect=SideEffect.PUBLIC_PUBLICATION,
        approval_required=True,
        retry_class=RetryClass.RECONCILE_FIRST,
        estimated_cost=None,
        data_egress=DataEgress.PUBLICATION_SERVICE,
        reason=(
            "The proof just verified, so the run's own evidence travels with "
            "it. It shows what would be sent and asks before sending anything."
        ),
    )
