"""``techtree release info|verify``. Spec section 9.5.

Two read-only commands, and read-only is a contract rather than an accident:
between them they open the ReleaseCore this build ships, the engine bundle it
ships, and the catalog it ships, and they write nothing, prompt for nothing,
contact nothing, and call no model. A host agent runs ``release verify``
immediately after installing the CLI, before anything has been set up, so
needing state would make the command useless exactly when it matters.

``release info`` answers "what is this build?" from the release document alone.
``release verify`` answers "is it still that?" by comparing every coordinate
against the thing it names, and — when the caller supplies the digest the
website published — against that too.

A build whose release is still a placeholder says so in both commands, in the
data and in a warning. It is the single most important thing a reader can learn
about a pre-release build, and it must not depend on anyone noticing that a
version string looks odd.
"""

from __future__ import annotations

from typing import Annotated, Final

import typer
from rich.console import Console
from rich.table import Table

from techtree.canonical import validate_digest
from techtree.cli.context import cli_context
from techtree.cli.invoke import CommandResult, invoke_command
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
    """The coordinates of the release this build belongs to."""

    release_id: NonEmptyString
    cli_version: NonEmptyString
    package_version: NonEmptyString
    cli_source_commit: NonEmptyString
    protocol_version: NonEmptyString
    release_core_digest: Digest
    engine_digest: Digest
    catalog_digest: Digest
    intro_climb_reference: NonEmptyString
    placeholder_release: bool
    placeholder_fields: list[str]


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
        payload = ReleaseInfoPayload(
            release_id=core.release_id,
            cli_version=core.cli_version,
            package_version=package_version(),
            cli_source_commit=core.cli_source_commit,
            protocol_version=core.protocol_version,
            release_core_digest=document_digest(raw),
            engine_digest=core.engine_digest,
            catalog_digest=core.catalog_digest,
            intro_climb_reference=core.intro_climb_reference,
            placeholder_release=core.placeholder_release,
            placeholder_fields=list(core.placeholder_fields),
        )
        return CommandResult(
            data=payload,
            warnings=_placeholder_warnings(
                core.placeholder_release, payload.placeholder_fields
            ),
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
        core = parse_release_core(raw)
        payload = ReleaseVerificationPayload(
            release_core_digest=document_digest(raw),
            expected_digest=expected_digest,
            verified=result.verified,
            checks=list(result.checks),
        )
        return CommandResult(
            data=payload,
            messages=_verified_messages(result),
            warnings=_placeholder_warnings(
                core.placeholder_release, list(core.placeholder_fields)
            ),
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


def _placeholder_warnings(
    placeholder_release: bool, fields: list[str]
) -> list[CliMessage]:
    if not placeholder_release:
        return []
    return [
        CliMessage(
            level=MessageLevel.WARNING,
            code="release_placeholder",
            text=(
                "This build belongs to a placeholder release: "
                f"{', '.join(fields)} have not been chosen yet. It is a "
                "development build, not a published one."
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

    table = Table(box=None, show_header=False, pad_edge=False, padding=(0, 2))
    table.add_column("field", no_wrap=True)
    table.add_column("value", overflow="fold")
    table.add_row("Release", data.release_id)
    table.add_row("CLI version", data.cli_version)
    table.add_row("Installed package", data.package_version)
    table.add_row("Source commit", data.cli_source_commit)
    table.add_row("Protocol", data.protocol_version)
    table.add_row("ReleaseCore", data.release_core_digest)
    table.add_row("Engine", data.engine_digest)
    table.add_row("Catalog", data.catalog_digest)
    table.add_row("Introductory Climb", data.intro_climb_reference)
    console.print(table)


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
