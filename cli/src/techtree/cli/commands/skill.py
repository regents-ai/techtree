"""``techtree skill starter``. Spec section 10.5, decisions 0008.

One command, and it does one thing: put the starter Skill this release pins
on this machine, and say where it is. The guided first run needs a Skill
before it can prepare anything, and until this command existed the only way
to get one was for a person to already have the file.

What it returns is a path, and that path goes through ``climb prepare`` like
anybody else's Skill: the same scanner, the same policy, the same draft, the
same confirmation. There is no privileged route for a Skill because a release
named it — the release's authority is over *which* Skill, not over what
Techtree will accept.

The command writes only into the Techtree home. A materialized Skill is
cached under the home's own cache directory, in a directory named by the
digest it was verified against, so a second guided run reuses it and a cached
directory somebody edited is re-verified rather than trusted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Final, Literal

import typer
from rich.console import Console
from rich.table import Table

from techtree.cli.context import cli_context
from techtree.cli.invoke import CommandResult, invoke_command
from techtree.models.base import Digest, NonEmptyString, ProtocolModel
from techtree.models.cli import CliMessage, MessageLevel, NextAction
from techtree.release.document import packaged_release_core_bytes, parse_release_core
from techtree.skills.starter import MaterializedStarterSkill, StarterSkillService

__all__ = [
    "STARTER_COMMAND",
    "StarterSkillPayload",
    "starter_skill_command",
]

STARTER_COMMAND: Final = "skill starter"


class StarterSkillPayload(ProtocolModel):
    """Where the pinned starter Skill is, and what it was verified against."""

    release_id: NonEmptyString
    skill_root_digest: Digest
    path: NonEmptyString
    entrypoint_path: NonEmptyString
    file_count: int
    total_bytes: int
    origin: Literal["cache", "local_file", "download"]
    intro_climb_reference: NonEmptyString


def starter_skill_command(
    ctx: typer.Context,
    from_file: Annotated[
        Path | None,
        typer.Option(
            "--from-file",
            metavar="PATH",
            help="A local copy of the starter Skill: its directory or SKILL.md.",
        ),
    ] = None,
    from_url: Annotated[
        str | None,
        typer.Option(
            "--from-url",
            metavar="URL",
            help="Where to fetch the starter Skill from, if it is not here yet.",
        ),
    ] = None,
) -> None:
    """Put the starter Skill this release pins on this machine."""
    context = cli_context(ctx)

    def action() -> CommandResult[StarterSkillPayload]:
        release = parse_release_core(packaged_release_core_bytes())
        materialized = StarterSkillService(context.paths).materialize(
            release=release, local_file=from_file, url=from_url
        )
        payload = StarterSkillPayload(
            release_id=release.release_id,
            skill_root_digest=materialized.root_digest,
            path=str(materialized.root),
            entrypoint_path=str(materialized.entrypoint),
            file_count=materialized.file_count,
            total_bytes=materialized.total_bytes,
            origin=materialized.origin,
            intro_climb_reference=release.intro_climb_reference,
        )
        return CommandResult(
            data=payload,
            messages=[
                CliMessage(
                    level=MessageLevel.INFO,
                    code="starter_skill_ready",
                    text=_summary(materialized),
                )
            ],
            next_actions=[_prepare_action(payload)],
        )

    invoke_command(context, STARTER_COMMAND, action, render_data=_render)


def _summary(materialized: MaterializedStarterSkill) -> str:
    """Say in one sentence what happened and what was proved."""
    how = {
        "cache": "was already on this machine",
        "local_file": "was read from the file you named",
        "download": "was fetched from the source you named",
    }[materialized.origin]
    return (
        f"The starter Skill {how} and matches the digest this release pins. "
        "It is prepared the same way any other Skill is."
    )


def _prepare_action(payload: StarterSkillPayload) -> NextAction:
    """Point at the ordinary preparation path, because that is the only one."""
    return NextAction(
        id="prepare_starter_skill",
        label="Prepare the introductory Climb with the starter Skill",
        reason=(
            "The starter Skill is scanned, checked against the Climb's policy, "
            "and shown to you before anything runs."
        ),
        cli=[
            "techtree",
            "climb",
            "prepare",
            payload.intro_climb_reference,
            "--skill",
            payload.path,
        ],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=True,
    )


def _render(data: object, console: Console) -> None:
    """Print where the Skill is and what it was verified against."""
    if not isinstance(data, StarterSkillPayload):
        return
    table = Table(box=None, show_header=False, pad_edge=False, padding=(0, 2))
    table.add_column("label", no_wrap=True)
    table.add_column("value", overflow="fold")
    for label, value in [
        ("Release", data.release_id),
        ("Skill content digest", data.skill_root_digest),
        ("Skill directory", data.path),
        ("Files", str(data.file_count)),
        ("Size", f"{data.total_bytes} bytes"),
        ("Obtained", data.origin.replace("_", " ")),
    ]:
        table.add_row(label, value)
    console.print(table)
