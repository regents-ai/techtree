"""``techtree proof verify``. Spec sections 7.12 and 7.21.

One command, and it answers one question about a directory of files: does this
proof still hold together? It reads, hashes, and checks signatures, and it
writes nothing, contacts nothing, and needs no Techtree state of its own — a
person handed a proof bundle on a memory stick can check it on a machine that
has never run a Climb.

The human rendering keeps five things apart, because collapsing them is how
"the signature verifies" turns into "the result is proven":

```text
cryptographic integrity      the files still match what was signed
scientific validity          the documents describe one controlled comparison
participant attestation      whose key vouched for them, and what that means
independent reproduction     nobody has done it
public publication           nothing was uploaded, and none was requested
```

A failed verification is a typed failure with exit code 11 and the failed
checks in the envelope, not a printed warning, because a caller that scripts
this is deciding whether to believe a number.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Final, Literal

import typer
from rich.console import Console
from rich.table import Table

from techtree.cli.context import cli_context
from techtree.cli.invoke import CommandResult, invoke_command
from techtree.errors import NotFoundError, ValidationError, VerificationError
from techtree.identity.models import VerificationMessage, VerificationResult
from techtree.ids import validate_id
from techtree.models.base import JsonValue, NonEmptyString, ProtocolModel
from techtree.models.cli import CliMessage, MessageLevel, NextAction
from techtree.receipts.bundle import (
    BUNDLE_MANIFEST_FILENAME,
    PROOF_BUNDLE_INVALID,
    proof_bundle_dir,
)
from techtree.receipts.verify import LocalProofVerifier

__all__ = [
    "PROOF_TARGET_NOT_FOUND",
    "VERIFY_COMMAND",
    "ProofVerificationPayload",
    "resolve_proof_target",
    "verify_proof_command",
]

VERIFY_COMMAND: Final = "proof verify"

#: Stable error code for "there is nothing at that name to verify". Distinct
#: from a bundle that exists and does not hold together, which is the section
#: 15 ``proof_bundle_invalid``.
PROOF_TARGET_NOT_FOUND: Final = "proof_target_not_found"


class ProofVerificationPayload(ProtocolModel):
    """What was verified, and every check that was run on it."""

    target: NonEmptyString
    kind: Literal["bundle", "report"]
    verified: bool
    summary: list[VerificationMessage]
    checks: list[VerificationMessage]


def verify_proof_command(
    ctx: typer.Context,
    target: Annotated[
        str,
        typer.Argument(
            metavar="TARGET",
            help=(
                "A run identifier, a proof bundle directory, or a signed "
                "uplift-report file."
            ),
        ),
    ],
) -> None:
    """Check a local proof, offline, from the bytes it stored."""
    context = cli_context(ctx)

    def action() -> CommandResult[ProofVerificationPayload]:
        path, kind = resolve_proof_target(target, runs_dir=context.paths.runs_dir)
        verifier = LocalProofVerifier()
        result = (
            verifier.verify_bundle(path)
            if kind == "bundle"
            else verifier.verify_report(path)
        )
        payload = ProofVerificationPayload(
            target=target,
            kind=kind,
            verified=result.verified,
            summary=verifier.explain(result),
            checks=list(result.messages),
        )
        return CommandResult(
            data=payload,
            messages=_messages(payload),
            warnings=_warnings(result),
            next_actions=[] if result.verified else [_read_logs(target)],
            error=None if result.verified else _failure(payload, result),
        )

    invoke_command(context, VERIFY_COMMAND, action, render_data=_render)


def resolve_proof_target(
    target: str, *, runs_dir: Path
) -> tuple[Path, Literal["bundle", "report"]]:
    """Turn what a caller typed into a directory or a file to verify.

    Three spellings are accepted (spec section 7.21) and each one is decided by
    what is actually there rather than by how it looks: a directory is a
    bundle, a file is a signed report, and anything else is read as a run
    identifier and looked up in this machine's runs.
    """
    candidate = Path(target).expanduser()
    if candidate.is_dir():
        return candidate, "bundle"
    if candidate.is_file():
        if candidate.name == BUNDLE_MANIFEST_FILENAME:
            return candidate.parent, "bundle"
        return candidate, "report"

    missing = NotFoundError(
        f"there is no proof to verify for {target}: no such run, directory or file",
        code=PROOF_TARGET_NOT_FOUND,
        details={"target": target},
    )
    try:
        run_id = validate_id(target, "run")
    except ValidationError as error:
        raise missing from error

    directory = proof_bundle_dir(runs_dir / run_id)
    if directory.is_dir():
        return directory, "bundle"
    raise missing


# ---------------------------------------------------------------------------
# Saying what happened
# ---------------------------------------------------------------------------


def _failure(
    payload: ProofVerificationPayload, result: VerificationResult
) -> VerificationError:
    """Return the typed failure a broken proof reports."""
    return VerificationError(
        f"this local proof does not verify: {result.failures[0].detail}",
        code=PROOF_BUNDLE_INVALID,
        details={
            "target": payload.target,
            "failed_checks": _identifiers(result),
            "codes": _codes(result),
        },
    )


def _identifiers(result: VerificationResult) -> list[JsonValue]:
    """Return the failed checks in the shape a typed error's details carry."""
    return [message.id for message in result.failures]


def _codes(result: VerificationResult) -> list[JsonValue]:
    """Return the distinct section 15 codes a failed verification reports under."""
    return [code for code in sorted({message.code for message in result.failures})]


def _messages(payload: ProofVerificationPayload) -> list[CliMessage]:
    if not payload.verified:
        return []
    return [
        CliMessage(
            level=MessageLevel.INFO,
            code="proof_verified",
            text=(
                f"This proof verifies: {len(payload.checks)} checks, all from "
                "the stored bytes, with nothing fetched."
            ),
        )
    ]


def _warnings(result: VerificationResult) -> list[CliMessage]:
    return [
        CliMessage(
            level=MessageLevel.WARNING,
            code=message.code,
            text=message.detail,
        )
        for message in result.warnings
    ]


def _read_logs(target: str) -> NextAction:
    return NextAction(
        id="proof_checks",
        label="See every check, including the ones that passed",
        reason="Machine output lists each check with its own stable code.",
        cli=["techtree", "proof", "verify", target, "--json"],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )


def _render(data: object, console: Console) -> None:
    if not isinstance(data, ProofVerificationPayload):
        return

    console.print(f"Proof: {data.target}")
    console.print()
    table = Table(box=None, show_header=False, pad_edge=False, padding=(0, 2))
    table.add_column("status", no_wrap=True)
    table.add_column("detail", overflow="fold")
    for message in data.summary:
        table.add_row(message.status.upper(), message.detail)
    console.print(table)

    failures = [message for message in data.checks if message.status == "failed"]
    if not failures:
        return
    console.print()
    console.print("Failed checks")
    for message in failures:
        console.print(f"  {message.id}: {message.detail}")
