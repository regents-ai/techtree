"""``techtree forge build|status``. ``docs/plan/repo2rlenv-local-lane.md``.

``forge build`` takes a local repository and retains generated Harbor tasks and
their qualification evidence; ``forge status`` reads that directory
back without requiring build tools. Build execution belongs to
:class:`~techtree.forge.service.ForgeService`; inspection uses the separate
record reader. What to say about either operation is here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from techtree.cli.context import cli_context
from techtree.cli.invoke import CommandResult, invoke_command
from techtree.cli.output import render_pairs
from techtree.engines.installer import find_uv
from techtree.forge.models import ForgeBuildStatus, ForgeLanguage
from techtree.forge.process import run_command
from techtree.forge.service import ForgeService, read_build_status
from techtree.models.cli import (
    CliWarning,
    DataEgress,
    NextAction,
    Operation,
    RetryClass,
    SideEffect,
    invocation,
)

__all__ = ["build_forge_command", "render_forge_status", "status_forge_command"]


def build_forge_command(
    ctx: typer.Context,
    repo: Annotated[
        Path,
        typer.Option(
            "--repo",
            help="The local git repository to build tasks from.",
            metavar="PATH",
        ),
    ],
    test_cmd: Annotated[
        list[str],
        typer.Option(
            "--test-cmd",
            help="A command that runs the repository's tests in the image. Repeatable.",
            metavar="COMMAND",
        ),
    ],
    dockerfile: Annotated[
        Path | None,
        typer.Option(
            "--dockerfile",
            help="A Dockerfile that builds the repository at /workspace. "
            "Defaults to the shipped one for uv-managed Python projects.",
            metavar="PATH",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, help="How many candidate commits to consider."),
    ] = 10,
    language: Annotated[
        ForgeLanguage,
        typer.Option("--language", help="The language the test commands are run as."),
    ] = ForgeLanguage.PYTHON,
) -> None:
    """Build and qualify tasks from a local repository."""
    context = cli_context(ctx)

    def action() -> CommandResult[ForgeBuildStatus]:
        service = ForgeService(context.paths, run_command, find_uv())
        status = service.build(
            repository=repo,
            dockerfile=dockerfile,
            test_commands=test_cmd,
            limit=limit,
            language=language,
        )
        return CommandResult(
            data=status,
            warnings=_warnings(status),
            next_actions=[_status_action(status)],
        )

    invoke_command(context, Operation.ACTION_EXECUTE, action, render_data=_render_built)


def status_forge_command(
    ctx: typer.Context,
    build_id: Annotated[
        str, typer.Argument(metavar="BUILD_ID", help="The build to show.")
    ],
) -> None:
    """Show what one forge build made."""
    context = cli_context(ctx)

    def action() -> CommandResult[ForgeBuildStatus]:
        status = read_build_status(context.paths, build_id)
        return CommandResult(data=status, warnings=_warnings(status))

    invoke_command(context, Operation.PLAN_INSPECT, action, render_data=_render_status)


def render_forge_status(status: ForgeBuildStatus, console: Console) -> None:
    """Print one build for a person."""
    build = status.build
    qualification = status.qualification
    progress = status.progress
    facts = {True: "yes", False: "no", None: "unknown"}
    pairs = [
        ("Build", status.build_id),
        ("Generation finished", facts[status.generation_finished]),
        ("Qualification finished", facts[status.qualification_finished]),
        (
            "Usable tasks",
            str(status.usable_tasks) if status.usable_tasks is not None else "unknown",
        ),
        ("Evidence", status.path),
        ("Tasks", status.tasks_path),
    ]
    if progress is not None:
        pairs.extend(
            [
                (
                    "Last observed phase",
                    f"{progress.phase} at {progress.updated_at.isoformat()}",
                ),
                ("Recorded outcome", progress.state),
                ("Partial task records", str(len(progress.completed_tasks))),
            ]
        )
        if progress.current_task_id is not None:
            pairs.append(("Last observed task", progress.current_task_id))
    else:
        pairs.append(("Progress", "unknown; no progress receipt"))
    if build is not None:
        pairs.extend(
            [
                ("Repository", build.repository),
                ("Commit", build.head_commit),
                ("Image", build.bootstrap_image_tag),
                ("Tests", " && ".join(build.test_commands)),
                ("Candidates", str(build.generation.candidates)),
                ("Emitted", str(build.generation.emitted)),
            ]
        )
    elif progress is not None:
        pairs.append(("Repository", progress.repository))
    render_pairs(pairs, console)
    if progress is not None and progress.failure is not None:
        console.print(
            f"{progress.failure.code}: {progress.failure.message}", markup=False
        )
        console.print("Inspect the retained evidence before starting a new build.")
    if build is not None and build.generation.skip_reasons:
        console.print()
        console.print("Skipped candidates:")
        for reason, count in sorted(build.generation.skip_reasons.items()):
            console.print(f"  {count:>4}  {reason}")
    if qualification is not None:
        console.print()
        for task in qualification.tasks:
            verdict = "qualified" if task.qualified else "not qualified"
            console.print(f"{task.task_id}: {verdict}")
            for check in task.checks:
                if not check.passed:
                    console.print(f"  {check.name}: {check.detail}")
    elif progress is not None and progress.completed_tasks:
        console.print("Partial task evidence only; qualification has not finished.")
        for task in progress.completed_tasks:
            console.print(
                f"  {task.task_id}: checks recorded; not admitted for use", markup=False
            )


def _render_built(data: object, console: Console) -> None:
    if not isinstance(data, ForgeBuildStatus):
        return
    console.print(f"Forge build {data.build_id} finished; no model was called.")
    console.print()
    render_forge_status(data, console)


def _render_status(data: object, console: Console) -> None:
    if not isinstance(data, ForgeBuildStatus):
        return
    render_forge_status(data, console)


def _warnings(status: ForgeBuildStatus) -> list[CliWarning]:
    """Say when a build made nothing usable, in one line each."""
    warnings: list[CliWarning] = []
    if status.build is not None and status.build.generation.emitted == 0:
        warnings.append(
            CliWarning(
                id="forge_nothing_emitted",
                text=(
                    "No commit in the considered history yielded a task; the "
                    "skip reasons say why each candidate was passed over."
                ),
                resolvable_by=None,
            )
        )
    elif (
        status.qualification is not None and not status.qualification.qualified_task_ids
    ):
        warnings.append(
            CliWarning(
                id="forge_nothing_qualified",
                text=(
                    "Every emitted task failed qualification; the failed checks "
                    "are listed under each task."
                ),
                resolvable_by=None,
            )
        )
    return warnings


def _status_action(status: ForgeBuildStatus) -> NextAction:
    return NextAction(
        operation=Operation.PLAN_INSPECT,
        prepared_arguments=invocation("forge", "status", arguments=[status.build_id]),
        expected_state_digest=None,
        side_effect=SideEffect.NONE,
        approval_required=False,
        retry_class=RetryClass.SAFE,
        estimated_cost=None,
        data_egress=DataEgress.NONE,
        reason="The build's tasks and their qualification can be read back later.",
    )
