"""``techtree climb list`` and ``techtree climb show``. Spec section 12.6.

Neither command decides anything about a Climb. The catalog service resolves
the graph, checks it, and answers whether this machine could run it; these
functions turn that answer into one envelope, some warnings, and at most three
next steps.

Two of those translations are worth naming.

A compatibility issue becomes a next action only when something runnable would
address it. An absent engine has an install command; an unsupported machine has
nothing Techtree could offer to run, so it is stated and no action is invented.

A development Climb is announced as a warning in both output modes rather than
only in the human rendering. A host agent reading JSON is exactly the caller
most likely to treat a fixture result as evidence, so the caveat travels with
the data.

``prepare`` and ``start`` are not part of this build and remain registered
stubs; nothing here reads a candidate path, starts a process, or reaches the
network.
"""

from __future__ import annotations

from typing import Annotated, Final

import typer
from rich.console import Console
from rich.table import Table

from techtree.catalog.repository import EmbeddedCatalogRepository
from techtree.catalog.service import (
    CatalogService,
    InstalledEngineStatus,
    current_host_info,
)
from techtree.cli.context import CliContext, cli_context
from techtree.cli.invoke import CommandResult, invoke_command
from techtree.errors import NotFoundError
from techtree.models.catalog import (
    ClimbSummary,
    CompatibilityResult,
    EngineCompatibilityStatus,
)
from techtree.models.cli import CliMessage, MessageLevel, NextAction
from techtree.models.climb import ResolvedClimb

__all__ = [
    "LIST_COMMAND",
    "SHOW_COMMAND",
    "build_catalog_service",
    "list_climbs_command",
    "show_climb_command",
]

LIST_COMMAND: Final = "climb list"
SHOW_COMMAND: Final = "climb show"

#: What a reader is told when the build ships no Climbs at all. This is the
#: normal state of a development build: the packaged catalog is valid and
#: empty until the Climb it will carry has been generated end to end.
_NO_CLIMBS = "This build does not include any Climbs yet."


def build_catalog_service(context: CliContext) -> CatalogService:
    """Construct the service both commands read the catalog through."""
    return CatalogService(
        EmbeddedCatalogRepository.packaged(),
        current_host_info(),
        InstalledEngineStatus(context.paths),
    )


def list_climbs_command(ctx: typer.Context) -> None:
    """List public wrappers with resolved Campaign compatibility."""
    context = cli_context(ctx)

    def action() -> CommandResult[list[ClimbSummary]]:
        summaries = build_catalog_service(context).list_climbs()

        if not summaries:
            return CommandResult(
                data=summaries,
                messages=[
                    CliMessage(
                        level=MessageLevel.INFO,
                        code="no_climbs_available",
                        text=_NO_CLIMBS,
                    )
                ],
                next_actions=[_check_environment()],
            )

        return CommandResult(
            data=summaries,
            messages=[
                CliMessage(
                    level=MessageLevel.INFO,
                    code="climbs_available",
                    text=_available_summary(len(summaries)),
                )
            ],
            warnings=_development_warnings(summaries),
            next_actions=[_show_climb(summaries[0].reference)],
        )

    invoke_command(context, LIST_COMMAND, action, render_data=_render_list)


def show_climb_command(
    ctx: typer.Context,
    reference: Annotated[
        str,
        typer.Argument(
            metavar="REFERENCE",
            help="A Climb slug, slug@version, or public identifier.",
        ),
    ],
) -> None:
    """Show public policy, Campaign summary, data rights, and compatibility."""
    context = cli_context(ctx)

    # The Campaign facts a ClimbSummary has no field for — the subject model,
    # its runtime, the reward being compared, and who owns a submitted skill —
    # are kept here by the command so the human rendering can show all of spec
    # section 26 without resolving the graph a second time.
    details: list[tuple[str, str]] = []

    def action() -> CommandResult[ClimbSummary]:
        service = build_catalog_service(context)
        try:
            resolved = service.get_climb(reference)
        except NotFoundError as error:
            # The repository knows which Climbs exist; what to do about a name
            # that is not one of them is the CLI's call. A catalog that is
            # itself broken is a different failure and keeps its own repair.
            if error.code == "climb_not_found":
                error.next_actions = _unknown_climb_actions(error)
            raise
        summary = service.climb_summary(resolved)
        details.extend(_resolved_details(resolved))

        return CommandResult(
            data=summary,
            warnings=_development_warnings([summary])
            + [
                CliMessage(
                    level=MessageLevel.WARNING,
                    code=issue.code,
                    text=issue.message,
                )
                for issue in summary.compatibility.issues
            ],
            next_actions=_show_next_actions(summary.compatibility),
        )

    def render(data: object, console: Console) -> None:
        _render_show(data, console, details)

    invoke_command(context, SHOW_COMMAND, action, render_data=render)


# ---------------------------------------------------------------------------
# Messages, warnings, and next actions
# ---------------------------------------------------------------------------


def _available_summary(count: int) -> str:
    if count == 1:
        return "One Climb is available in this build."
    return f"{count} Climbs are available in this build."


def _development_warnings(summaries: list[ClimbSummary]) -> list[CliMessage]:
    """Warn once per development Climb that its results prove nothing."""
    return [
        CliMessage(
            level=MessageLevel.WARNING,
            code="development_climb",
            text=(
                f"{summary.reference} is a development Climb. Its results are "
                "for trying the flow out and are not comparable evidence."
            ),
        )
        for summary in summaries
        if summary.status == "development"
    ]


def _show_next_actions(compatibility: CompatibilityResult) -> list[NextAction]:
    """Offer the one step that moves this Climb forward on this machine."""
    if not compatibility.host_supported:
        # Nothing Techtree can run fixes the wrong machine, so nothing is
        # offered. The reason is already in the compatibility warning.
        return []
    if compatibility.engine_status is EngineCompatibilityStatus.NOT_INSTALLED:
        return [_install_engine()]
    if compatibility.engine_status is EngineCompatibilityStatus.INSTALLED_UNVERIFIED:
        return [_verify_engine()]
    return [_check_environment()]


def _unknown_climb_actions(error: NotFoundError) -> list[NextAction]:
    """Offer the listing when there is one, and Doctor when there is not."""
    available = error.details.get("available")
    if isinstance(available, list) and available:
        return [_browse_climbs()]
    return [_check_environment()]


def _browse_climbs() -> NextAction:
    return NextAction(
        id="list_climbs",
        label="See which Climbs this build ships",
        reason="A Climb is named by its slug, or by slug and version.",
        cli=["techtree", "climb", "list"],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )


def _show_climb(reference: str) -> NextAction:
    return NextAction(
        id="show_climb",
        label=f"Look at {reference} in detail",
        reason="Shows what it measures, the data rights it carries, and "
        "whether this machine can run it.",
        cli=["techtree", "climb", "show", reference],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )


def _install_engine() -> NextAction:
    return NextAction(
        id="install_engine",
        label="Install the evaluation engine",
        reason="Preparing a submission for this Climb needs it.",
        cli=["techtree", "engine", "install"],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )


def _verify_engine() -> NextAction:
    return NextAction(
        id="verify_engine",
        label="Check that the installed evaluation engine is intact",
        reason="A result is only worth as much as the engine that produced it.",
        cli=["techtree", "engine", "verify"],
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


# ---------------------------------------------------------------------------
# Human rendering
# ---------------------------------------------------------------------------


def _render_list(data: object, console: Console) -> None:
    """Print one row per Climb, or nothing when there are none."""
    if not isinstance(data, list) or not data:
        return

    table = Table(box=None, pad_edge=False, padding=(0, 2))
    table.add_column("Climb", no_wrap=True)
    table.add_column("Title", overflow="fold")
    table.add_column("Status", no_wrap=True)
    table.add_column("Tasks", justify="right", no_wrap=True)
    table.add_column("Runs here", no_wrap=True)

    for summary in data:
        table.add_row(
            summary.reference,
            summary.title,
            summary.status,
            str(summary.task_count),
            "yes" if summary.compatibility.compatible else "no",
        )

    console.print(table)


def _render_show(
    data: object, console: Console, details: list[tuple[str, str]]
) -> None:
    """Print everything a person needs before entering a Climb."""
    if not isinstance(data, ClimbSummary):
        return

    console.print(data.title)
    console.print(data.summary)
    console.print()

    _print_pairs(
        console,
        [
            ("Climb", data.reference),
            ("Status", data.status),
            ("Campaign", data.campaign_spec_digest),
            ("Purpose", _phrase(data.purpose)),
            ("Taskset", f"{data.taskset_id} ({data.task_count} tasks)"),
            (
                "Subject harness",
                f"{data.subject_harness} {data.subject_harness_version}",
            ),
            *details,
            ("Evaluated by", data.evaluation_backend.value),
            ("Allowed change", _phrase(data.mutation_kind)),
            ("Proof grade", _phrase(data.proof_grade)),
        ],
    )

    console.print()
    console.print("Data rights")
    _print_pairs(
        console,
        [
            ("Candidate skills", data.candidate_skill_visibility),
            (
                "Public release",
                _phrase(data.data_policy.candidate_skill_public_release),
            ),
            (
                "Raw episode upload",
                _phrase(data.data_policy.raw_episode_server_upload),
            ),
            ("Training use", _phrase(data.data_policy.raw_episode_training_use)),
            ("Uplift report", _phrase(data.data_policy.uplift_report_visibility)),
        ],
    )

    console.print()
    console.print("This machine")
    _print_pairs(
        console,
        [
            ("Host platform", data.compatibility.host_platform),
            ("Engine", _phrase(data.compatibility.engine_status.value)),
            ("Runs here", "yes" if data.compatibility.compatible else "no"),
        ],
    )


def _phrase(value: str) -> str:
    """Render a protocol value as words rather than as an identifier.

    The machine payload keeps the exact spelling; a person reading a terminal
    is better served by "required for climb" than by the same string with an
    underscore in it.
    """
    return value.replace("_", " ")


def _print_pairs(console: Console, pairs: list[tuple[str, str]]) -> None:
    table = Table(box=None, show_header=False, pad_edge=False, padding=(0, 2))
    table.add_column("label", no_wrap=True)
    table.add_column("value", overflow="fold")
    for label, value in pairs:
        table.add_row(label, value)
    console.print(table)


def _resolved_details(resolved: ResolvedClimb) -> list[tuple[str, str]]:
    """Return the Campaign facts a summary has no field for."""
    subject = resolved.campaign.subject
    platforms = ", ".join(subject.runtime.supported_platforms)
    return [
        ("Subject model", f"{subject.model.provider}/{subject.model.model_id}"),
        (
            "Subject runtime",
            f"{subject.runtime.type} {subject.runtime.image} ({platforms})",
        ),
        ("Primary reward", resolved.campaign.scoring.primary_reward),
        ("Candidate ownership", resolved.data_policy.candidate_skill.ownership),
    ]
