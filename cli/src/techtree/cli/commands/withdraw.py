"""``techtree withdraw``. Decisions document 0038.

The founder chose to implement withdrawal rather than to promise it: a public
promise with no executable path would be worse than neither. This is the path.

*An entry is addressed by its bundle digest.* That is how the log addresses a
run — ``/runs/sha256:…`` — so it is what a person copies off the page they are
looking at, and it works whether or not the run is still on this machine.

*The request is signed with the key that signed the run.* The identity store
holds it and it is the only signing key this machine has. The network verifies
it against the participant key inside the publication it already accepted, which
is why nothing here sends a public key: a key that travelled with the request
would be a key the requester chose.

*There is no reason field.* Nothing a submitter writes appears on the site, and
a free-text reason attached to a public entry would be the one string that did.

*Withdrawn is not deleted.* The entry stays where it is, marked, and what comes
back names where it still lives. The wording says that rather than implying an
erasure this release does not perform.

Somebody has to say so. Withdrawal changes a public page, so it is asked for the
same way publishing is asked for, and where nobody can be asked the command
stops and names the flag instead of deciding on their behalf.
"""

from __future__ import annotations

from typing import Annotated, Final

import typer
from rich.console import Console

from techtree.canonical import validate_digest
from techtree.cli.confirm import confirmed
from techtree.cli.context import CliContext, cli_context
from techtree.cli.invoke import CommandResult, invoke_command
from techtree.cli.output import human_console, render_pairs
from techtree.drafts.store import utc_now
from techtree.errors import UsageError
from techtree.identity.service import IdentityService
from techtree.identity.store import IdentityStore
from techtree.models.base import Digest, NonEmptyString, ProtocolModel, UtcDateTime
from techtree.models.cli import CliMessage, MessageLevel
from techtree.publication.coordinates import packaged_publication_coordinates
from techtree.publication.transport import (
    HttpsPublicationTransport,
    resolved_endpoint,
)
from techtree.publication.withdraw import WithdrawalService

__all__ = [
    "WITHDRAWAL_CONFIRMATION_REQUIRED",
    "WITHDRAW_COMMAND",
    "WithdrawalPayload",
    "build_withdrawal_service",
    "withdraw_run_command",
    "withdrawal_review_lines",
]

WITHDRAW_COMMAND: Final = "withdraw"

#: Stable error code for "nobody said to withdraw this".
WITHDRAWAL_CONFIRMATION_REQUIRED: Final = "withdrawal_confirmation_required"

_WITHDRAW_PROMPT: Final = "Withdraw this entry from the public log?"

#: What withdrawal is and is not, said where somebody is deciding. It is the
#: honest claim rather than the comfortable one: the entry stays, marked, and
#: nothing about backups is implied.
_WHAT_WITHDRAWAL_DOES: Final = (
    "Withdrawing marks the entry withdrawn. It is not a deletion: the entry "
    "stays at the address it already has, the log records the withdrawal as "
    "another event, and anyone who already has the proof still has it."
)


class WithdrawalPayload(ProtocolModel):
    """What ``techtree withdraw`` returns once the log has marked an entry."""

    bundle_digest: Digest
    endpoint: NonEmptyString
    entry_url: NonEmptyString
    withdrawn_at: UtcDateTime
    #: The participant key the request was signed with. It is the identity the
    #: log checked against the publication it accepted, so a person can see that
    #: the entry was withdrawn by the identity that published it.
    key_id: NonEmptyString


def withdraw_run_command(
    ctx: typer.Context,
    bundle_digest: Annotated[
        str,
        typer.Argument(
            metavar="BUNDLE_DIGEST",
            help="The published entry's bundle digest, as the log addresses it.",
        ),
    ],
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            help=(
                "Withdraw without being asked. For an operator running Techtree "
                "where nobody can answer a prompt."
            ),
        ),
    ] = False,
) -> None:
    """Withdraw a published run from the public run log."""
    context = cli_context(ctx)

    def action() -> CommandResult[WithdrawalPayload]:
        digest = validate_digest(bundle_digest)
        service = build_withdrawal_service(context)
        if not yes:
            _require_withdrawal_confirmation(context, digest, service.endpoint)

        outcome = service.withdraw(digest)
        payload = WithdrawalPayload(
            bundle_digest=outcome.bundle_digest,
            endpoint=service.endpoint,
            entry_url=outcome.entry_url,
            withdrawn_at=outcome.withdrawn_at,
            key_id=outcome.key_id,
        )
        return CommandResult(
            data=payload,
            messages=[
                CliMessage(
                    level=MessageLevel.INFO,
                    code="entry_withdrawn",
                    text=(
                        f"The entry at {payload.entry_url} is marked withdrawn. "
                        "It stays where it is: the log appended the withdrawal "
                        "rather than removing anything."
                    ),
                )
            ],
        )

    invoke_command(context, WITHDRAW_COMMAND, action, render_data=_render)


def build_withdrawal_service(context: CliContext) -> WithdrawalService:
    """Construct the service this command withdraws through.

    The same pinned coordinates and the same development override publishing
    uses, and for the same reasons — one address for the whole of this feature,
    and one key whose countersignature is worth having.
    """
    coordinates = packaged_publication_coordinates()
    return WithdrawalService(
        coordinates=coordinates,
        endpoint=resolved_endpoint(coordinates, context.settings.publication_endpoint),
        identity=IdentityService(IdentityStore(context.paths)),
        transport=HttpsPublicationTransport(),
        clock=utc_now,
    )


def _require_withdrawal_confirmation(
    context: CliContext, bundle_digest: Digest, endpoint: str
) -> None:
    """Show what would happen, take the answer, or send nothing."""
    if context.no_input:
        raise UsageError(
            "withdrawing changes a public page, so somebody has to agree to "
            "it. Nothing here can be asked, so say so with --yes",
            code=WITHDRAWAL_CONFIRMATION_REQUIRED,
            details={"bundle_digest": bundle_digest},
        )

    console = human_console(no_color=context.no_color)
    for line in withdrawal_review_lines(bundle_digest, endpoint):
        console.print(line)
    console.print()
    if not confirmed(_WITHDRAW_PROMPT):
        raise UsageError(
            f"entry {bundle_digest} was not withdrawn; no request left this machine",
            code=WITHDRAWAL_CONFIRMATION_REQUIRED,
            details={"bundle_digest": bundle_digest},
        )


def withdrawal_review_lines(bundle_digest: Digest, endpoint: str) -> list[str]:
    """Return what a person reads before they answer."""
    return [
        f"Withdrawing entry {bundle_digest}",
        "",
        f"A signed request goes to {endpoint}. It is signed with this "
        "machine's own key, which is the key that signed the run.",
        "",
        _WHAT_WITHDRAWAL_DOES,
    ]


def _render(data: object, console: Console) -> None:
    if not isinstance(data, WithdrawalPayload):
        return

    render_pairs(
        [
            ("Entry", data.entry_url),
            ("Proof", data.bundle_digest),
            ("Withdrawn", data.withdrawn_at.isoformat()),
            ("Signed by", data.key_id),
        ],
        console,
    )
