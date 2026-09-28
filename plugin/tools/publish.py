"""Offering to publish a finished run, and publishing it once somebody agrees.

Decisions document 0038, founder additions of 2026-08-27.

Publishing is the one thing in this product whose result is public, and the
plugin's part in it is deliberately small: it relays an offer Techtree made,
and — after Hermes has asked the person — it runs the command they agreed to.

*The offer is Techtree's, not the plugin's.* ``regents techtree run result``
and ``regents techtree proof verify`` put a ``publication_offer`` in their
answer when, and only when, a run's proof was checked in that very reading and
held together. :func:`publication_offer` reads that offer and hands it on. It
never composes one, so a run whose proof did not verify cannot be offered here:
there is nothing to read. This is the same rule the rest of the plugin lives by
— offers shown to a person come from Techtree's own answers, never from a
sentence somebody wrote.

*The asking is Hermes's.* Publishing needs a person's agreement — without
``--yes`` regents answers ``approval_required`` — so this plugin marks the
offer with the ``requires_user_confirmation`` its own next steps carry, and the
tool that acts on it is declared the same way — so the host asks on its own
approval surface where a model cannot answer for anybody.

*The publishing is regents'.* This plugin can open no network connection at
all — the doctor proves it by reading every runtime module's imports rather
than by promising — and this module opens none either. What it does is run the
pinned ``regents`` command, which is a separate program, and which reaches the
run log only once the person has said yes. Those are two different facts about
two different programs and copy that merges them is a defect.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..services.approvals import (
    PUBLICATION_DISCLOSURE,
    publication_approved_event,
    publish_arguments,
)
from ..services.models import is_success
from . import channel_of, passthrough, require_argument, safe_tool, tool_result
from .arguments import require_run_id

#: What this plugin calls the offer, in its own answer to the host.
PUBLISH_ACTION_ID = "publish_run"

#: What the offer says, in the plugin's own words. Techtree's offer carries a
#: reason and no label; a person reading a conversation needs a line
#: that says what they are being offered before the reason it is offered.
PUBLISH_ACTION_LABEL = "Publish this run to the public run log"

#: The tool a host agent calls once the person has answered.
PUBLISH_TOOL = "techtree_publish_run"


def publication_offer(answer: Mapping[str, Any], run_id: str) -> dict[str, Any] | None:
    """Return the offer to publish this run, if Techtree made one.

    ``None`` whenever Techtree's answer carries no ``publication_offer``, which
    is every case where the proof was not checked and passed just now. The
    reason is Techtree's own words, carried across unchanged; what the plugin
    adds is the tool that acts on it and the disclosure a person is owed before
    they answer.
    """
    offer = answer.get("publication_offer")
    if not isinstance(offer, Mapping):
        return None
    return {
        "id": PUBLISH_ACTION_ID,
        "label": PUBLISH_ACTION_LABEL,
        "reason": offer.get("reason"),
        "tool": PUBLISH_TOOL,
        "run_id": run_id,
        "requires_user_confirmation": True,
        "disclosure": list(PUBLICATION_DISCLOSURE),
    }


@safe_tool
def techtree_publish_run(services: Any, args: dict[str, Any], **kwargs: Any) -> str:
    """Publish a verified run's proof, for a person who has already agreed.

    Every call is made with ``--yes --reviewed-on host-agent``, which is how
    the publication records that the agreement was given in a conversation
    rather than at a terminal. There is no other way to call it: the flags are
    built by :func:`~techtree_hermes.services.approvals.publish_arguments` and nothing
    in the arguments can change them, so a publication this plugin causes
    always carries the record of where it was approved.

    No Ethereum address is sent. The command asks a person at a terminal
    whether they want to leave one and nothing is offered in exchange for it;
    an address arriving as a tool argument would have passed through a model
    first, which is not where a private detail about somebody belongs.
    """
    channel = channel_of(args, kwargs)
    run_id = require_run_id(require_argument(args, "run_id"))

    answer = services.bridge.invoke(["publish", *publish_arguments(run_id)])
    if not is_success(answer):
        return passthrough(answer, channel)

    return tool_result(
        {**answer, "approval": publication_approved_event(run_id=run_id)},
        channel,
    )
