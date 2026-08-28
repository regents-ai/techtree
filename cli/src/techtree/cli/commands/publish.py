"""``techtree publish``. Decisions document 0038.

This is the one command in Techtree that sends anything anywhere, and every
decision in it is about making that fact impossible to arrive at by accident.

*The proof is checked before the question is asked.* ``plan`` verifies the run's
bundle offline, from its stored bytes, and refuses everything that does not hold
together. A result whose own proof fails is never offered as something that
could be published, because a published number whose evidence does not check out
is the one outcome this product exists to prevent.

*Everything that will be sent is shown first.* How many files, how many bytes,
and the address they go to. The proof directory carries no transcripts — an
episode receipt holds digests, task hashes and scores, and the raw episodes are
outside it entirely — and the summary says so rather than leaving a reader to
wonder what is in three hundred kilobytes.

*Somebody has to say yes.* The prompt is the shared one, its default is no, and
where nobody can be asked the command stops and names the flag instead of
inventing an answer. ``--yes`` with ``--reviewed-on host-agent`` is how an agent
records that the person answered in the conversation, which is the same surface
``climb start`` already uses and the one decisions 0038 names for this.

*The address question is asked once, and promises nothing.* It defaults to no,
what is typed is checked and canonicalised before it goes anywhere, and it
travels in the ``x-techtree-contributor-address`` request header — beside the
submission and never inside it, because the run log serves a stored submission
back at a public address — and it is written down nowhere. The wording says what
is true: an address can be left, it is kept in case contributors can be
recognised later, and nothing is being offered in exchange today.

*Nothing is written down that was not checked.* The receipt the run log answers
with is verified against the network key this release pins — not against the key
the receipt carries, which a server that wanted to lie would simply invent —
before it becomes a file. An unverified receipt is not written at all.

The run's own files are not touched. The countersigned receipt is a new file in
the run directory and the outcome goes into a publication journal of the run's
own, which is what append-only permits and the whole of what it permits.
"""

from __future__ import annotations

from typing import Annotated, Final

import typer
from rich.console import Console

from techtree.cli.commands.climb import ReviewSurface
from techtree.cli.confirm import confirmed
from techtree.cli.context import CliContext, cli_context
from techtree.cli.invoke import CommandResult, invoke_command
from techtree.cli.output import human_console, render_pairs
from techtree.drafts.store import utc_now
from techtree.errors import UsageError
from techtree.models.base import Digest, NonEmptyString, ProtocolModel, UtcDateTime
from techtree.models.cli import CliMessage, MessageLevel, NextAction
from techtree.models.uplift_report import PublicationStatus
from techtree.publication.address import (
    canonical_contributor_address,
    canonical_skill_github_url,
)
from techtree.publication.coordinates import packaged_publication_coordinates
from techtree.publication.service import (
    PublicationPlan,
    PublicationService,
)
from techtree.publication.transport import HttpsPublicationTransport

__all__ = [
    "ADDRESS_QUESTION",
    "NOTHING_IS_OFFERED",
    "PUBLICATION_CONFIRMATION_REQUIRED",
    "PUBLISH_COMMAND",
    "PublicationPayload",
    "publish_run_command",
]

#: The command's own name, in the envelope and in every message about it.
#: Decisions 0038's founder ruling makes it a top-level command: ``proof`` keeps
#: ``verify`` and nothing else, and nothing has been released, so this is a hard
#: cut with no alias.
PUBLISH_COMMAND: Final = "publish"

#: Stable error code for "nobody said to publish this".
PUBLICATION_CONFIRMATION_REQUIRED: Final = "publication_confirmation_required"

#: The hard boundary, stated in the copy rather than only in the guard that
#: enforces it. Nothing is promised in return for an address; the intention to
#: be able to recognise contributors later is an intention, and an intention is
#: not a commitment. Decisions 0038.
NOTHING_IS_OFFERED: Final = (
    "Nothing is being offered in exchange today. It is kept only so that "
    "contributors can be recognised later, if that becomes possible."
)

#: What a person is asked, once, at publish time. It is the whole question:
#: what the address is for, that it is optional, and that leaving one buys
#: nothing.
ADDRESS_QUESTION: Final = (
    "You can leave an Ethereum address with this run if you want to. "
    f"It is optional, it is never shown on the log, and nobody checks that it "
    f"is yours. {NOTHING_IS_OFFERED}"
)

_ADDRESS_PROMPT: Final = "Leave an address with this run?"
_PUBLISH_PROMPT: Final = "Publish this run to the public log?"

#: What the proof directory holds, said where somebody is deciding whether to
#: send it. Each episode receipt carries digests, task hashes and scores; the
#: episodes themselves are not in the directory at all.
_WHAT_TRAVELS: Final = (
    "These are the run's proof files: the signed report, the receipts, and the "
    "documents they cite. No prompts and no replies are among them — a receipt "
    "records a task's digest and its score, and the episodes themselves are "
    "not in this directory."
)


class PublicationPayload(ProtocolModel):
    """What ``techtree publish`` returns once the log has accepted a run."""

    run_id: NonEmptyString
    bundle_digest: Digest
    endpoint: NonEmptyString
    file_count: int
    byte_count: int
    publication: PublicationStatus
    log_sequence: int
    entry_url: NonEmptyString
    accepted_at: UtcDateTime
    receipt_path: NonEmptyString
    #: Whether an address was sent. The address is not here, and is not
    #: anywhere else this machine can be read: it went into the
    #: ``x-techtree-contributor-address`` request header and into nothing
    #: else.
    contributor_address_sent: bool
    #: Metadata read from the verified prepared Skill and optionally supplied
    #: at publication time. These are headers beside, never members of, the
    #: fixed four-member proof submission.
    skill_name: NonEmptyString | None = None
    skill_github_url: NonEmptyString | None = None


def publish_run_command(
    ctx: typer.Context,
    run_id: Annotated[
        str,
        typer.Argument(
            metavar="RUN_ID",
            help="The finished run whose proof should be published.",
        ),
    ],
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            help=(
                "Publish without being asked. For an operator running Techtree "
                "where nobody can answer a prompt; it is never a shortcut for "
                "an agent to take on a person's behalf."
            ),
        ),
    ] = False,
    reviewed_on: Annotated[
        ReviewSurface,
        typer.Option(
            "--reviewed-on",
            help=(
                "Where the person who agreed to publish answered. Pass "
                "host-agent when what would be sent was shown in a "
                "conversation and agreed there. Like --yes, and for the same "
                "reason, it states what a person already did."
            ),
        ),
    ] = ReviewSurface.CLI,
    address: Annotated[
        str | None,
        typer.Option(
            "--address",
            metavar="ADDRESS",
            help=(
                "An Ethereum address to send with this run. Optional, never "
                "shown on the log, and nothing is offered in exchange for it."
            ),
        ),
    ] = None,
    github_url: Annotated[
        str | None,
        typer.Option(
            "--github-url",
            metavar="URL",
            help=(
                "An optional canonical https://github.com/owner/repo URL for "
                "the Skill. It is public descriptive metadata, not proof of "
                "ownership."
            ),
        ),
    ] = None,
) -> None:
    """Publish a verified run's proof to the public run log."""
    context = cli_context(ctx)

    def action() -> CommandResult[PublicationPayload]:
        service = build_publication_service(context)
        skill_github_url = (
            canonical_skill_github_url(github_url) if github_url is not None else None
        )
        plan = service.plan(run_id)
        # The order a person meets this in is the order it is written in: what
        # would be sent, then the one optional question, then the answer that
        # covers both. An address asked for before the review would be asked
        # of somebody who does not yet know what they are being asked about.
        asking = _require_an_answer_is_possible(
            context, plan, assume_yes=yes, reviewed_on=reviewed_on
        )
        if asking:
            _show_what_would_be_sent(
                context, plan, skill_github_url=skill_github_url
            )
        contributor = _contributor_address(context, typed=address, asking=asking)
        if asking:
            _require_publication_confirmation(context, plan)

        outcome = service.publish(
            plan,
            contributor_address=contributor,
            skill_github_url=skill_github_url,
        )
        receipt = outcome.receipt
        payload = PublicationPayload(
            run_id=outcome.run_id,
            bundle_digest=plan.bundle_digest,
            endpoint=plan.endpoint,
            file_count=plan.file_count,
            byte_count=plan.byte_count,
            publication=outcome.status,
            log_sequence=receipt.log_sequence,
            entry_url=receipt.entry_url,
            accepted_at=receipt.accepted_at,
            receipt_path=str(outcome.receipt_path),
            contributor_address_sent=outcome.contributor_address_sent,
            skill_name=plan.skill_name,
            skill_github_url=skill_github_url,
        )
        return CommandResult(
            data=payload,
            messages=[
                CliMessage(
                    level=MessageLevel.INFO,
                    code="run_published",
                    text=(
                        f"Run {payload.run_id} is entry {payload.log_sequence} "
                        f"of the public log, at {payload.entry_url}. The log "
                        "records arrivals in order and ranks nothing."
                    ),
                )
            ],
            next_actions=[_verify_proof(payload.run_id)],
        )

    invoke_command(context, PUBLISH_COMMAND, action, render_data=_render)


def build_publication_service(context: CliContext) -> PublicationService:
    """Construct the service this command publishes through.

    The transport is the only substitutable part and it is chosen here, at the
    edge, so that everything below it is the same code whether it is a test or
    a person running it.

    The address is the pinned one unless a development override is set, and the
    pinned network key is never overridable: an address a person can point
    somewhere else is a convenience, and a key a person can point somewhere else
    is the removal of the only thing that makes a receipt mean anything.
    """
    return PublicationService(
        runs_dir=context.paths.runs_dir,
        coordinates=packaged_publication_coordinates(),
        endpoint_override=context.settings.publication_endpoint,
        transport=HttpsPublicationTransport(),
        clock=utc_now,
    )


# ---------------------------------------------------------------------------
# The asking
#
# Three steps, in the order somebody meets them: find out whether there is
# anybody to ask, show them what would be sent, and take the one answer that
# covers all of it. They are separate functions because the middle one has to
# happen between the other two — an address asked for before the review would
# be asked of somebody who does not yet know what they are agreeing to.
# ---------------------------------------------------------------------------


def _require_an_answer_is_possible(
    context: CliContext,
    plan: PublicationPlan,
    *,
    assume_yes: bool,
    reviewed_on: ReviewSurface,
) -> bool:
    """Return whether a person is about to be asked, or refuse to go on.

    The shape is ``climb start``'s rather than ``run cancel``'s, because this is
    the same kind of decision: something a person has to be shown before they
    can meaningfully agree to it, and something a host agent may show in its own
    conversation instead. ``--confirm`` on its own would record that a flag was
    passed; ``--yes --reviewed-on host-agent`` records where somebody answered.
    """
    if assume_yes:
        return False

    if reviewed_on is not ReviewSurface.CLI:
        raise UsageError(
            "--reviewed-on says where an agreement was already given, so it "
            "goes with --yes; without it what would be sent is shown here and "
            "answered here",
            code=PUBLICATION_CONFIRMATION_REQUIRED,
            details={"run_id": plan.run_id, "reviewed_on": reviewed_on.value},
        )

    if context.no_input:
        raise UsageError(
            "publishing sends this run's proof to the public run log, and a "
            "published entry is withdrawn rather than deleted, so somebody has "
            "to agree to it. Nothing here can be asked, so say so with --yes",
            code=PUBLICATION_CONFIRMATION_REQUIRED,
            details={"run_id": plan.run_id},
        )
    return True


def _show_what_would_be_sent(
    context: CliContext,
    plan: PublicationPlan,
    *,
    skill_github_url: str | None,
) -> None:
    """Print the review, before anything is asked about it."""
    console = human_console(no_color=context.no_color)
    for line in publication_review_lines(plan, skill_github_url=skill_github_url):
        console.print(line)


def _contributor_address(
    context: CliContext, *, typed: str | None, asking: bool
) -> str | None:
    """Return the canonical address to send, or nothing at all.

    The default is nothing, in every direction. Somebody who passed the option
    has answered; somebody who is not being asked has not been asked, and no
    address is sent; and a person at a terminal is asked once, with the answer
    defaulting to no.
    """
    if typed is not None:
        return canonical_contributor_address(typed)
    if not asking:
        return None

    console = human_console(no_color=context.no_color)
    console.print()
    console.print(ADDRESS_QUESTION)
    if not confirmed(_ADDRESS_PROMPT):
        return None
    return canonical_contributor_address(typer.prompt("Address"))


def _require_publication_confirmation(
    context: CliContext, plan: PublicationPlan
) -> None:
    """Take the answer, or send nothing."""
    console = human_console(no_color=context.no_color)
    console.print()
    if not confirmed(_PUBLISH_PROMPT):
        raise UsageError(
            f"run {plan.run_id} was not published; its proof did not leave "
            "this machine",
            code=PUBLICATION_CONFIRMATION_REQUIRED,
            details={"run_id": plan.run_id},
        )


def publication_review_lines(
    plan: PublicationPlan, *, skill_github_url: str | None = None
) -> list[str]:
    """Return what a person reads before they answer.

    Exactly what would leave this machine, in the order somebody would ask it:
    what it is, how much of it there is, where it is going, and what it does not
    contain.
    """
    return [
        f"Publishing run {plan.run_id}",
        "",
        f"{plan.file_count} files, {plan.byte_count} bytes, to {plan.endpoint}",
        f"Proof {plan.bundle_digest}",
        f"Skill {plan.skill_name or 'candidate Skill'}",
        f"GitHub {skill_github_url or 'none'}",
        "",
        _WHAT_TRAVELS,
        "",
        "The log shows arrivals in the order they arrive and ranks nothing. "
        "An entry that is published stays published: it can be withdrawn, "
        "which is recorded, and it is not deleted.",
    ]


# ---------------------------------------------------------------------------
# Saying what happened
# ---------------------------------------------------------------------------


def _verify_proof(run_id: str) -> NextAction:
    return NextAction(
        id="verify_proof",
        label="Verify this run's local proof again",
        reason="It checks offline, from the bytes the run stored.",
        cli=["techtree", "proof", "verify", run_id],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )


def _render(data: object, console: Console) -> None:
    if not isinstance(data, PublicationPayload):
        return

    render_pairs(
        [
            ("Run", data.run_id),
            ("Entry", data.entry_url),
            ("Log sequence", str(data.log_sequence)),
            ("Accepted", data.accepted_at.isoformat()),
            ("Sent", f"{data.file_count} files, {data.byte_count} bytes"),
            ("Proof", data.bundle_digest),
            ("Receipt", data.receipt_path),
        ],
        console,
    )
    console.print()
    console.print(
        "The log holds what was sent and the receipt holds what it answered. "
        "Neither changes this run's own files, which are final."
    )
