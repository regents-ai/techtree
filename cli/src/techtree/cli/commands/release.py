"""``techtree release info|verify``. Spec section 9.5.

Two read-only commands, and read-only is a contract rather than an accident:
between them they open the ReleaseCore this build ships, the engine bundle it
ships, and the catalog it ships, and they write nothing, prompt for nothing,
contact nothing, and call no model. A host agent runs ``release verify``
immediately after installing the CLI, before anything has been set up, so
needing state would make the command useless exactly when it matters.

``release info`` answers "what is this build?" from the release document and
from the commit stamped into this artifact when it was built (decisions 0026).
``release verify`` answers "is it still that?" by comparing every coordinate
against the thing it names, and — when the caller supplies the digest the
website published — against that too.

The stamped commit is the one thing here that is not in the release document,
because it is the one thing the release document cannot honestly contain: it
is a fact about this artifact rather than about the release. A source checkout
carries no stamp, and ``release info`` says that rather than naming a commit
nobody stamped.
"""

from __future__ import annotations

from typing import Annotated, Final

import typer
from rich.console import Console
from rich.table import Table

from techtree.canonical import validate_digest
from techtree.cli.context import cli_context
from techtree.cli.invoke import CommandResult, invoke_command
from techtree.cli.output import render_pairs
from techtree.errors import VerificationError
from techtree.models.base import Digest, JsonValue, NonEmptyString, ProtocolModel
from techtree.models.cli import CliMessage, MessageLevel, NextAction
from techtree.release.checks import (
    ReleaseCheck,
    ReleaseVerification,
    local_release_facts,
    verify_release_core,
)
from techtree.release.document import (
    document_digest,
    packaged_release_core_bytes,
    parse_release_core,
)
from techtree.release.generate import packaged_sources
from techtree.release.provenance import (
    BuildProvenance,
    Commit,
    packaged_build_provenance,
)
from techtree.version import package_version

__all__ = [
    "INFO_COMMAND",
    "RELEASE_NOT_VERIFIED",
    "VERIFY_COMMAND",
    "ReleaseInfoPayload",
    "ReleaseVerificationPayload",
    "info_release_command",
    "verify_release_command",
]

INFO_COMMAND: Final = "release info"
VERIFY_COMMAND: Final = "release verify"

#: Stable error code for a release whose coordinates no longer agree.
RELEASE_NOT_VERIFIED: Final = "release_not_verified"


class ReleaseInfoPayload(ProtocolModel):
    """The coordinates of the release this build belongs to.

    ``source_commit`` is stamped into a built artifact and is absent from a
    source checkout, which is why it is the one field here that can be null.
    """

    release_id: NonEmptyString
    cli_version: NonEmptyString
    package_version: NonEmptyString
    source_commit: Commit | None
    protocol_version: NonEmptyString
    release_core_digest: Digest
    engine_digest: Digest
    catalog_digest: Digest
    intro_climb_reference: NonEmptyString


class ReleaseVerificationPayload(ProtocolModel):
    """What was verified about this build's release, check by check."""

    release_core_digest: Digest
    expected_digest: Digest | None
    verified: bool
    checks: list[ReleaseCheck]


def info_release_command(ctx: typer.Context) -> None:
    """Report the release coordinates this build was generated with."""
    context = cli_context(ctx)

    def action() -> CommandResult[ReleaseInfoPayload]:
        raw = packaged_release_core_bytes()
        core = parse_release_core(raw)
        stamp = packaged_build_provenance()
        payload = ReleaseInfoPayload(
            release_id=core.release_id,
            cli_version=core.cli_version,
            package_version=package_version(),
            source_commit=None if stamp is None else stamp.source_commit,
            protocol_version=core.protocol_version,
            release_core_digest=document_digest(raw),
            engine_digest=core.engine_digest,
            catalog_digest=core.catalog_digest,
            intro_climb_reference=core.intro_climb_reference,
        )
        return CommandResult(
            data=payload,
            warnings=_unstamped_warnings(stamp),
            next_actions=[_verify_action()],
        )

    invoke_command(context, INFO_COMMAND, action, render_data=_render_info)


def verify_release_command(
    ctx: typer.Context,
    expected: Annotated[
        str | None,
        typer.Option(
            "--expected",
            metavar="DIGEST",
            help="The ReleaseCore digest the website published for this release.",
        ),
    ] = None,
) -> None:
    """Check every release coordinate against the thing it names."""
    context = cli_context(ctx)

    def action() -> CommandResult[ReleaseVerificationPayload]:
        expected_digest = None if expected is None else validate_digest(expected)
        raw = packaged_release_core_bytes()
        result = verify_release_core(
            raw,
            local_release_facts(packaged_sources()),
            expected_digest=expected_digest,
        )
        payload = ReleaseVerificationPayload(
            release_core_digest=document_digest(raw),
            expected_digest=expected_digest,
            verified=result.verified,
            checks=list(result.checks),
        )
        return CommandResult(
            data=payload,
            messages=_verified_messages(result),
            warnings=_unstamped_warnings(packaged_build_provenance()),
            next_actions=[
                _check_environment() if result.verified else _inspect_action()
            ],
            error=None if result.verified else _failure(result),
        )

    invoke_command(context, VERIFY_COMMAND, action, render_data=_render_verification)


# ---------------------------------------------------------------------------
# Saying what happened
# ---------------------------------------------------------------------------


def _failure(result: ReleaseVerification) -> VerificationError:
    """Return the typed failure a drifted release reports."""
    first = result.failures[0]
    return VerificationError(
        f"this release does not verify: {first.detail}",
        code=RELEASE_NOT_VERIFIED,
        details={
            "failed_checks": _identifiers(result),
            "codes": _codes(result),
        },
    )


def _identifiers(result: ReleaseVerification) -> list[JsonValue]:
    """Return the failed checks in the shape a typed error's details carry."""
    return [check.id for check in result.failures]


def _codes(result: ReleaseVerification) -> list[JsonValue]:
    """Return the distinct codes a failed verification reports under."""
    return [code for code in sorted({check.code for check in result.failures})]


def _verified_messages(result: ReleaseVerification) -> list[CliMessage]:
    if not result.verified:
        return []
    return [
        CliMessage(
            level=MessageLevel.INFO,
            code="release_verified",
            text=(
                f"This release verifies: {len(result.checks)} checks, "
                f"{len(result.skipped)} of them not applicable to an installed "
                "CLI, with nothing fetched."
            ),
        )
    ]


def _unstamped_warnings(stamp: BuildProvenance | None) -> list[CliMessage]:
    """Say when this is not a built artifact, so nothing claims a commit."""
    if stamp is not None:
        return []
    return [
        CliMessage(
            level=MessageLevel.WARNING,
            code="release_source_commit_unstamped",
            text=(
                "This is running from a source checkout rather than an "
                "installed build, so no source commit was stamped into it and "
                "none is reported."
            ),
        )
    ]


def _inspect_action() -> NextAction:
    return NextAction(
        id="release_checks",
        label="See every release check, including the ones that passed",
        reason="Machine output lists each check with its own stable code.",
        cli=["techtree", "release", "verify", "--json"],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )


def _verify_action() -> NextAction:
    return NextAction(
        id="verify_release",
        label="Check this build against the release it names",
        reason="Every coordinate above is checked against the thing it points at.",
        cli=["techtree", "release", "verify"],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )


def _check_environment() -> NextAction:
    return NextAction(
        id="check_environment",
        label="Check that this machine is ready",
        reason="Doctor reports what is installed, what is missing, and what "
        "would block a run.",
        cli=["techtree", "doctor"],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )


def _render_info(data: object, console: Console) -> None:
    if not isinstance(data, ReleaseInfoPayload):
        return

    render_pairs(
        [
            ("Release", data.release_id),
            ("CLI version", data.cli_version),
            ("Installed package", data.package_version),
            (
                "Source commit",
                data.source_commit or "not stamped: this is a source checkout",
            ),
            ("Protocol", data.protocol_version),
            ("ReleaseCore", data.release_core_digest),
            ("Engine", data.engine_digest),
            ("Catalog", data.catalog_digest),
            ("Introductory Climb", data.intro_climb_reference),
        ],
        console,
    )


def _render_verification(data: object, console: Console) -> None:
    if not isinstance(data, ReleaseVerificationPayload):
        return

    console.print(f"ReleaseCore: {data.release_core_digest}")
    console.print()
    table = Table(box=None, show_header=False, pad_edge=False, padding=(0, 2))
    table.add_column("status", no_wrap=True)
    table.add_column("check", no_wrap=True)
    table.add_column("detail", overflow="fold")
    for check in data.checks:
        table.add_row(check.status.upper(), check.id, check.detail)
    console.print(table)
