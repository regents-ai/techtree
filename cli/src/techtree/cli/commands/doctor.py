"""``techtree doctor``. Spec section 12.5.

The command decides nothing. It asks the Doctor service what it found, turns
warnings into messages, turns blocking failures into a typed prerequisite
error, and hands the whole thing to the envelope machinery. Whether a check
blocks, and which repairs are worth offering, are the service's calls.

A blocking failure is reported as a failure — non-zero exit, ``ok`` false — and
the report still travels in ``data``. A caller that asked what is wrong with
its machine should get the answer along with the verdict, not instead of it.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from techtree.cli.commands.climb import build_catalog_service
from techtree.cli.context import CliContext, cli_context
from techtree.cli.invoke import CommandResult, invoke_command
from techtree.doctor.service import DoctorReport, DoctorService
from techtree.errors import PrerequisiteError
from techtree.models.campaign import CampaignSpec
from techtree.models.cli import CheckStatus, CliMessage, DoctorCheck, MessageLevel

__all__ = ["doctor_command", "render_doctor_report"]

COMMAND = "doctor"

#: How each status is coloured for a person. Ignored entirely when colour is
#: off or stdout is not a terminal.
_STATUS_STYLE: dict[CheckStatus, str] = {
    CheckStatus.PASS: "green",
    CheckStatus.WARN: "yellow",
    CheckStatus.FAIL: "red",
    CheckStatus.SKIP: "dim",
}


def doctor_command(
    ctx: typer.Context,
    for_evaluation: bool = typer.Option(
        False,
        "--for-evaluation",
        help=(
            "Also check what running a Climb for real needs, and treat anything "
            "missing as a reason to stop rather than a note."
        ),
    ),
    climb: str | None = typer.Option(
        None,
        "--climb",
        metavar="REFERENCE",
        help=(
            "Check the subject a particular Climb would run: its model "
            "credential and its container image. Implies --for-evaluation."
        ),
    ),
) -> None:
    """Run DoctorService and emit checks plus repair actions."""
    context = cli_context(ctx)

    def action() -> CommandResult[DoctorReport]:
        service = DoctorService(context.paths, context.settings)
        checks = service.run(
            for_evaluation=for_evaluation or climb is not None,
            campaign=_campaign_for(context, climb),
        )
        blocking = service.blocking_failures(checks)

        return CommandResult(
            data=service.report(checks),
            messages=[
                CliMessage(
                    level=MessageLevel.INFO,
                    code="doctor_summary",
                    text=_summary(len(checks), len(blocking)),
                )
            ],
            warnings=[
                CliMessage(level=MessageLevel.WARNING, code=check.id, text=check.detail)
                for check in service.warnings(checks)
            ],
            next_actions=service.next_actions(checks),
            error=_blocking_error(blocking) if blocking else None,
        )

    invoke_command(context, COMMAND, action, render_data=_render)


def _campaign_for(context: CliContext, reference: str | None) -> CampaignSpec | None:
    """Resolve the Campaign a named Climb would execute, if one was named.

    Without a Climb, Doctor can only ask the machine-level questions. Which
    model a subject would authenticate as, and which image it would run in, are
    properties of a particular experiment rather than of the host.
    """
    if reference is None:
        return None
    return build_catalog_service(context).get_climb(reference).campaign


def render_doctor_report(report: DoctorReport, console: Console) -> None:
    """Print the environment facts and the check table."""
    console.print(f"Techtree {report.versions['package_version']}")
    console.print(f"Home:            {report.techtree_home}")
    console.print(f"Host platform:   {report.host_platform or 'unsupported'}")
    if report.docker_platform is not None:
        console.print(f"Docker platform: {report.docker_platform}")

    table = Table(box=None, pad_edge=False, padding=(0, 2))
    table.add_column("Status", no_wrap=True)
    table.add_column("Check", no_wrap=True)
    table.add_column("Detail", overflow="fold")

    for check in report.checks:
        table.add_row(
            Text(check.status.value, style=_STATUS_STYLE[check.status]),
            check.label,
            check.detail,
        )

    console.print()
    console.print(table)


def _render(data: object, console: Console) -> None:
    """Adapt the report to the renderer signature the envelope layer uses."""
    if isinstance(data, DoctorReport):
        render_doctor_report(data, console)


def _summary(total: int, blocking: int) -> str:
    if blocking:
        return f"{blocking} of {total} checks block Techtree from working here."
    return f"All {total} checks ran and none of them block Techtree."


def _blocking_error(blocking: list[DoctorCheck]) -> PrerequisiteError:
    identifiers = [check.id for check in blocking]
    return PrerequisiteError(
        "this host is not ready: " + ", ".join(identifiers),
        code="environment_not_ready",
        details={"failed_checks": list(identifiers)},
    )
