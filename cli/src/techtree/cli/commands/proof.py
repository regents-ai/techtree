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

Two audiences read the same result and need opposite things from it. A machine
gets every check under its own stable identifier, and those identifiers are
named for the failure each check reports, because that is the vocabulary a
caller branches on. A person reading a proof that holds together does not need
three hundred rows each headed by the name of something that did not happen; a
check that passed is worth counting, and what a reader wants counted is the
kind of thing it confirmed. So the human rendering groups the checks under
headings it derives here, at the moment of printing, and prints the full list
only when it is asked for. A check that failed is the other way round entirely:
it keeps its exact identifier and its exact code, and gains the heading and the
subject that say where in the proof the trouble is.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Annotated, Final, Literal

import typer
from rich.console import Console
from rich.table import Table

from techtree.cli.context import cli_context
from techtree.cli.invoke import CommandResult, invoke_command
from techtree.cli.output import DataRenderer
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
    every_check: Annotated[
        bool,
        typer.Option(
            "--checks",
            help=(
                "List every check that ran and what it confirmed, instead of "
                "the counts."
            ),
        ),
    ] = False,
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
            next_actions=[_read_logs(target)],
            error=None if result.verified else _failure(payload, result),
        )

    invoke_command(
        context,
        VERIFY_COMMAND,
        action,
        render_data=_renderer(every_check=every_check),
    )


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


# ---------------------------------------------------------------------------
# Turning identifiers into headings, at the moment of printing
# ---------------------------------------------------------------------------

type _Selector = Callable[[str], bool]

#: The tail every envelope check carries. These are the only checks whose own
#: sentence does not say what it was about — thirty-six receipts report the
#: same sentence — so the thing checked is read back off the identifier's head.
_SIGNATURE_ASPECTS: Final = (
    ".payload_digest",
    ".signature",
    ".signature_key",
    ".signature_present",
)

_ARTIFACT_PREFIX: Final = "artifact."


def _about_a_missing_file(identifier: str) -> bool:
    return (
        identifier.endswith(".present")
        or identifier.startswith("document.")
        or identifier == "bundle.public_key"
    )


def _about_a_stored_digest(identifier: str) -> bool:
    return (
        identifier.startswith(_ARTIFACT_PREFIX)
        or identifier == "bundle.root_report_digest"
    )


def _about_linkage(identifier: str) -> bool:
    return identifier.startswith(("linkage.", "receipt_set.", "execution_record."))


def _about_a_signature(identifier: str) -> bool:
    return identifier.endswith(_SIGNATURE_ASPECTS)


#: The headings a person reads a verification under, in the order the checks
#: were run. Each one says what its checks confirmed rather than what they
#: would have reported had they failed. The last heading takes whatever the
#: others left, so the counts always add up to everything that ran.
_HEADINGS: Final[tuple[tuple[str, _Selector], ...]] = (
    ("Files and key present", _about_a_missing_file),
    ("Stored file digests", _about_a_stored_digest),
    ("Linkage and control", _about_linkage),
    ("Signatures", _about_a_signature),
    (
        "Aggregate recomputation",
        lambda identifier: identifier.startswith("aggregate."),
    ),
    ("Publication", lambda identifier: identifier.startswith("publication.")),
    ("Proof grade conditions", lambda identifier: identifier.startswith("p1.")),
    ("Other checks", lambda _identifier: True),
)


def _grouped(
    checks: Sequence[VerificationMessage],
) -> list[tuple[str, list[VerificationMessage]]]:
    """Return the checks under their headings, in reading order."""
    collected: dict[str, list[VerificationMessage]] = {
        heading: [] for heading, _ in _HEADINGS
    }
    for message in checks:
        for heading, belongs_here in _HEADINGS:
            if belongs_here(message.id):
                collected[heading].append(message)
                break
    return [
        (heading, collected[heading]) for heading, _ in _HEADINGS if collected[heading]
    ]


def _heading_of(identifier: str) -> str:
    """Return the heading one check is counted under."""
    for heading, belongs_here in _HEADINGS:
        if belongs_here(identifier):
            return heading
    raise AssertionError("the last heading takes every identifier")


def _subject_of(message: VerificationMessage) -> str:
    """Return what one check was about, or nothing when its own words say so."""
    for aspect in _SIGNATURE_ASPECTS:
        if message.id.endswith(aspect):
            return message.id[: -len(aspect)]
    if message.id.startswith(_ARTIFACT_PREFIX):
        return message.id[len(_ARTIFACT_PREFIX) :]
    return ""


def _named_beside(message: VerificationMessage) -> str:
    """Return the subject to print beside a check, or nothing if it repeats.

    Most checks open their own sentence with the thing they were about. The
    envelope checks do not, because thirty-six receipts report the identical
    sentence, and those are the ones worth naming.
    """
    subject = _subject_of(message)
    return "" if message.detail.startswith(subject) else subject


def _tally(checks: Sequence[VerificationMessage]) -> tuple[str, str]:
    """Return how one heading came out, and anything about it worth reading."""
    passed = sum(1 for message in checks if message.status == "passed")
    failed = sum(1 for message in checks if message.status == "failed")
    weaker = len(checks) - passed - failed
    if len(checks) == 1:
        return checks[0].status, ""
    notes = []
    if failed:
        notes.append(f"{failed} failed")
    if weaker:
        notes.append("1 warning" if weaker == 1 else f"{weaker} warnings")
    return f"{passed}/{len(checks)}", ", ".join(notes)


# ---------------------------------------------------------------------------
# Printing it
# ---------------------------------------------------------------------------


def _renderer(*, every_check: bool) -> DataRenderer:
    """Return the human rendering, with or without the full list of checks."""

    def render(data: object, console: Console) -> None:
        _render(data, console, every_check=every_check)

    return render


def _render(data: object, console: Console, *, every_check: bool) -> None:
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

    headings = _grouped(data.checks)
    _render_counts(headings, len(data.checks), console)
    if every_check:
        _render_every_check(headings, console)
    else:
        console.print()
        console.print("Add --checks to see every one of them and what it confirmed.")

    failures = [message for message in data.checks if message.status == "failed"]
    if failures:
        _render_failures(failures, len(data.checks), console)


def _render_counts(
    headings: Sequence[tuple[str, list[VerificationMessage]]],
    total: int,
    console: Console,
) -> None:
    console.print()
    console.print(f"What was checked, {total} checks in all")
    rows = [(heading, *_tally(checks)) for heading, checks in headings]
    table = Table(box=None, show_header=False, pad_edge=True, padding=(0, 2))
    table.add_column("heading", overflow="fold")
    table.add_column("outcome", justify="right", no_wrap=True)
    # The third column exists only when something is in it, so a proof that
    # holds together prints no column of blanks beside its counts.
    troubled = any(note for _, _, note in rows)
    if troubled:
        table.add_column("note", no_wrap=True)
    for heading, outcome, note in rows:
        cells = (heading, outcome, note) if troubled else (heading, outcome)
        table.add_row(*cells)
    console.print(table)


def _render_every_check(
    headings: Sequence[tuple[str, list[VerificationMessage]]], console: Console
) -> None:
    for heading, checks in headings:
        console.print()
        console.print(heading)
        rows = [
            (message.status.upper(), _named_beside(message), message.detail)
            for message in checks
        ]
        table = Table(box=None, show_header=False, pad_edge=True, padding=(0, 2))
        table.add_column("status", no_wrap=True)
        # Most checks say what they were about in their own words. The ones
        # that do not are named beside them rather than left to the reader.
        named = any(subject for _, subject, _ in rows)
        if named:
            table.add_column("subject", overflow="fold")
        table.add_column("confirmed", overflow="fold")
        for status, subject, detail in rows:
            cells = (status, subject, detail) if named else (status, detail)
            table.add_row(*cells)
        console.print(table)


def _render_failures(
    failures: Sequence[VerificationMessage], total: int, console: Console
) -> None:
    """Print every failure whole: where it is, what went wrong, and its code.

    Nothing here is grouped or shortened. A reader whose proof does not hold
    together is the one reader who needs all of it, and the identifier and the
    code are exactly the two strings they will quote to somebody else.
    """
    console.print()
    console.print(f"What failed, {len(failures)} of {total} checks")
    table = Table(box=None, show_header=False, pad_edge=False, padding=(0, 1))
    table.add_column("index", justify="right", no_wrap=True)
    table.add_column("failure", overflow="fold")
    for position, message in enumerate(failures, start=1):
        subject = _subject_of(message)
        where = _heading_of(message.id)
        table.add_row(
            f"{position}.",
            "\n".join(
                [
                    f"{where} — {subject}" if subject else where,
                    message.detail,
                    f"check {message.id}, reported as {message.code}",
                ]
            ),
        )
    console.print(table)
