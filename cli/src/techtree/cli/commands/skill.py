"""``techtree skill starter``. Spec section 10.5, decisions 0008.

One command, and it does one thing: put the starter Skill this release pins
on this machine, and say where it is. The guided first run needs a Skill
before it can prepare anything, and until this command existed the only way
to get one was for a person to already have the file.

Run with no options it needs nothing from the caller at all: the release names
both which Skill it measured and the address that Skill is published at, so
``--from-file`` and ``--from-url`` are for the cases where somebody has a copy
of their own. Whichever route the bytes take, they are proved against the
release's digest before they are kept.

What it returns goes through ``climb prepare`` like anybody else's Skill: the
same scanner, the same policy, the same draft, the same confirmation. There is
no privileged route for a Skill because a release named it — the release's
authority is over *which* Skill, not over what Techtree will accept.

The command writes only into the Techtree home. A materialized Skill is
cached under the home's own cache directory, in a directory named by the
digest it was verified against, so a second guided run reuses it and a cached
directory somebody edited is re-verified rather than trusted.

Decisions document 0010 item 5 governs what comes back. Where the Skill *is*,
what it is *called*, and what a candidate carrying it is *labelled* are three
separate values, and the answer states all three separately. They are not
interchangeable and none of them is computed from another: a path is a fact
about this machine, a name is the Skill's own, and a label is a short public
string a comparison is filed under. Deriving any of the latter two from the
first is how a cache directory's digest, a temporary directory, or a download
URL ends up printed as the name of somebody's work.

The answer also says what the Skill is *for*. Decisions document 0010 item 2
rules that the starter Skill's own text stays silent about the gap it was
written with, and that the release metadata discloses instead — the public
Climb page, this command, and the calibration record all carry the same
sentence. So the purpose is printed beside the name here: nobody is handed the
starter Skill without being told it is an introductory one that is incomplete
on purpose.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import typer
from rich.console import Console

from techtree.cli.context import cli_context
from techtree.cli.invoke import CommandResult, invoke_command
from techtree.cli.output import render_pairs
from techtree.constants import (
    STARTER_SKILL_CANDIDATE_LABEL,
    STARTER_SKILL_NAME,
    STARTER_SKILL_PURPOSE,
)
from techtree.models.base import Digest, NonEmptyString, ProtocolModel
from techtree.models.cli import (
    DataEgress,
    NextAction,
    Operation,
    RetryClass,
    SideEffect,
    invocation,
)
from techtree.release.document import packaged_release_core_bytes, parse_release_core
from techtree.skills.starter import StarterSkillService

__all__ = [
    "StarterSkillPayload",
    "starter_skill_command",
]


class StarterSkillPayload(ProtocolModel):
    """Where the pinned starter Skill is, what it is called, and what it proved.

    ``skill_path`` is where the Skill's entry file sits on this machine.
    ``skill_name`` is what the Skill calls itself. ``candidate_label`` is what
    a comparison carrying it is filed under. Decisions document 0010 item 5
    keeps the three apart: a reader and a host agent both need to be able to
    take the label without ever looking at the path.

    ``skill_purpose`` is the fourth, and it is about the artifact rather than
    about this machine: decisions document 0010 item 2 puts the starter
    Skill's disclosure in the release metadata, so whoever is handed the Skill
    is told what it is for before they run it.
    """

    release_id: NonEmptyString
    skill_root_digest: Digest
    skill_path: NonEmptyString
    skill_name: NonEmptyString
    skill_purpose: NonEmptyString
    candidate_label: NonEmptyString
    file_count: int
    total_bytes: int
    origin: Literal["cache", "local_file", "download", "release"]
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
            help=(
                "Where to fetch the starter Skill from, instead of the address "
                "this release publishes it at."
            ),
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
            skill_path=str(materialized.entrypoint),
            skill_name=STARTER_SKILL_NAME,
            skill_purpose=STARTER_SKILL_PURPOSE,
            candidate_label=STARTER_SKILL_CANDIDATE_LABEL,
            file_count=materialized.file_count,
            total_bytes=materialized.total_bytes,
            origin=materialized.origin,
            intro_climb_reference=release.intro_climb_reference,
        )
        # No state digest, deliberately. Materializing writes into the cache,
        # but what it writes is addressed by the digest this release pins: the
        # same call produces the same bytes in the same place, so there is no
        # state here that moves between two answers and nothing for a later
        # action to be stale against. The Skill's own digest is a fact about
        # the Skill and is in the payload, where a reader needs it.
        return CommandResult(
            data=payload,
            next_actions=[_prepare_action(payload)],
        )

    invoke_command(context, Operation.PLAN_PREPARE, action, render_data=_render)


def _summary(origin: str) -> str:
    """Say in one sentence what happened and what was proved."""
    how = {
        "cache": "was already on this machine",
        "local_file": "was read from the file you named",
        "download": "was fetched from the source you named",
        "release": "was fetched from the address this release publishes it at",
    }[origin]
    return (
        f"The starter Skill {how} and matches the digest this release pins. "
        "It is prepared the same way any other Skill is."
    )


def _prepare_action(payload: StarterSkillPayload) -> NextAction:
    """Point at the ordinary preparation path, because that is the only one.

    The label is stated rather than left to default. ``climb prepare`` falls
    back to the skill directory's own name, and this Skill lives in a directory
    named by the digest it was verified against: seventy-one characters, longer
    than a label may be, and meaningless to a reader. Decisions document 0010
    item 5 rules that out for good — the label here is the release's own short
    name for the candidate, never anything read off the path beside it — and
    naming it is also what makes these arguments runnable exactly as printed.
    """
    return NextAction(
        operation=Operation.PLAN_PREPARE,
        prepared_arguments=invocation(
            "climb",
            "prepare",
            arguments=[payload.intro_climb_reference],
            options={
                "--skill": payload.skill_path,
                "--label": payload.candidate_label,
            },
        ),
        expected_state_digest=None,
        side_effect=SideEffect.LOCAL_STATE,
        # Preparing writes a draft and starts nothing; the person is asked at
        # the start, which the prepared draft offers in its turn.
        approval_required=False,
        retry_class=RetryClass.SAFE,
        estimated_cost=None,
        data_egress=DataEgress.NONE,
        reason=(
            "It prepares Techtree Hello World with the starter Skill. The "
            "Skill is scanned, checked against the Climb's policy, and shown "
            "to you before anything runs."
        ),
    )


def _render(data: object, console: Console) -> None:
    """Print how the Skill got here, then where it is and what it proved."""
    if not isinstance(data, StarterSkillPayload):
        return
    console.print(_summary(data.origin))
    console.print()
    render_pairs(
        [
            ("Release", data.release_id),
            ("Skill", data.skill_name),
            ("Purpose", data.skill_purpose),
            ("Candidate label", data.candidate_label),
            ("Skill content digest", data.skill_root_digest),
            ("Skill file", data.skill_path),
            ("Files", str(data.file_count)),
            ("Size", f"{data.total_bytes} bytes"),
            ("Obtained", data.origin.replace("_", " ")),
        ],
        console,
    )
