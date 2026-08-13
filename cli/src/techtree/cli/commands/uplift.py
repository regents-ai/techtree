"""``techtree uplift context``, ``prepare``, and ``start``. Spec section 7.21.

Three commands, and together they are the local half of the improvement loop:
say what a finished run showed, set up the comparison between the Skill it
measured and a revision of it, and start that comparison running.

What is deliberately *not* here is the revision itself. No command in this file
calls a model, asks anything to write a Skill, or reads one that a model wrote
without a person putting it there. ``uplift context`` produces the material a
host agent reasons over and stops; ``uplift prepare`` takes a directory a
person names and stops. Spec section 7.3 puts the reasoning turn in WP9+, and
the seam between the two is exactly this file's boundary.

Two things are kept as they are for public submissions, because the second run
is a real run and nothing about it is smaller.

*The rights policy is accepted again.* A second evaluation is a second use of
the participant's material, so ``uplift start`` collects acceptance the same
way ``climb start`` does: a person is shown the summary and answers, or a
program names the exact digest. Spec section 7.20 requires it explicitly.

*The comparison is stated before it runs.* ``uplift prepare`` returns both
Skill digests, the derived Campaign digest, the estimated episodes, and the
DataPolicy digest, because that is what spec section 11.5 says a person must
see before approving a second run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Final, Literal

import typer
from rich.console import Console
from rich.table import Table

from techtree.canonical import canonical_json_bytes
from techtree.cli.commands.climb import (
    acknowledge_data_policy,
    build_preparation_service,
)
from techtree.cli.commands.run import build_run_service
from techtree.cli.context import CliContext, cli_context
from techtree.cli.invoke import CommandResult, invoke_command
from techtree.drafts.confirmation import ConfirmationService
from techtree.drafts.store import DraftStore
from techtree.fs import atomic_write_bytes, ensure_private_directory
from techtree.models.base import Digest, NonEmptyString, ProtocolModel, UtcDateTime
from techtree.models.cli import CliMessage, MessageLevel, NextAction
from techtree.models.run import RunPhase
from techtree.models.skill import PolicyAcceptanceRequirement
from techtree.paths import TechtreePaths
from techtree.runs.artifacts import RunArtifactStore
from techtree.skills.service import PreparedDraft
from techtree.uplift.context import SkillImprovementContext
from techtree.uplift.service import UpliftService

__all__ = [
    "CONTEXT_COMMAND",
    "PREPARE_COMMAND",
    "START_COMMAND",
    "UpliftContextPayload",
    "UpliftPreparePayload",
    "UpliftStartPayload",
    "build_uplift_service",
    "context_uplift_command",
    "prepare_uplift_command",
    "start_uplift_command",
]

CONTEXT_COMMAND: Final = "uplift context"
PREPARE_COMMAND: Final = "uplift prepare"
START_COMMAND: Final = "uplift start"


class UpliftContextPayload(ProtocolModel):
    """The sanitized context, and where the same bytes were written."""

    context: SkillImprovementContext
    relative_path: NonEmptyString


class UpliftPreparePayload(ProtocolModel):
    """What ``uplift prepare`` returns, including the token, once."""

    draft_id: NonEmptyString
    draft_digest: Digest
    confirmation_token: NonEmptyString
    confirmation_expires_at: UtcDateTime
    source_run_id: NonEmptyString
    campaign_spec_digest: Digest
    data_policy_digest: Digest
    baseline_skill_digest: Digest
    candidate_skill_digest: Digest
    candidate_label: NonEmptyString
    included_files: list[NonEmptyString]
    estimated_episodes: int
    controlled: bool
    allowed_differences: list[NonEmptyString]
    differences: list[NonEmptyString]
    policy_acceptance: PolicyAcceptanceRequirement
    warnings: list[NonEmptyString]


class UpliftStartPayload(ProtocolModel):
    """What ``uplift start`` returns, as soon as the worker is running."""

    run_id: NonEmptyString
    draft_id: NonEmptyString
    phase: RunPhase
    worker_pid: int | None
    campaign_spec_digest: Digest
    data_policy_digest: Digest
    policy_acknowledgement_method: Literal[
        "interactive_cli",
        "explicit_cli_digest",
        "host_agent_confirmation",
    ]


def build_uplift_service(context: CliContext) -> UpliftService:
    """Construct the service the improvement commands act through."""
    return UpliftService(
        paths=context.paths,
        run_service=build_run_service(context),
        artifact_store=RunArtifactStore(context.paths),
        skill_service=build_preparation_service(context),
    )


# ---------------------------------------------------------------------------
# context
# ---------------------------------------------------------------------------


def context_uplift_command(
    ctx: typer.Context,
    run_id: Annotated[
        str,
        typer.Argument(
            metavar="RUN_ID",
            help="The finished run to build improvement context from.",
        ),
    ],
) -> None:
    """Export the sanitized local context for one finished run."""
    context = cli_context(ctx)

    def action() -> CommandResult[UpliftContextPayload]:
        improvement = build_uplift_service(context).improvement_context(run_id)
        path = _write_context(context.paths, run_id, improvement)
        payload = UpliftContextPayload(
            context=improvement,
            relative_path=path.relative_to(context.paths.run_dir(run_id)).as_posix(),
        )
        return CommandResult(
            data=payload,
            messages=[
                CliMessage(
                    level=MessageLevel.INFO,
                    code="improvement_context_ready",
                    text=(
                        f"Built improvement context for {run_id} from "
                        f"{len(improvement.examples)} of this run's tasks."
                    ),
                )
            ],
            warnings=[
                CliMessage(
                    level=MessageLevel.WARNING,
                    code="improvement_context_is_not_proof",
                    text=(
                        "This context is working material, not evidence. It is "
                        "not signed, nothing verifies it, and nothing uploads it."
                    ),
                )
            ],
            next_actions=[_prepare_replacement(run_id)],
        )

    invoke_command(context, CONTEXT_COMMAND, action, render_data=_render_context)


def _write_context(
    paths: TechtreePaths, run_id: str, context: SkillImprovementContext
) -> Path:
    """Write the context beside the run it describes, replacing any older one.

    A run can be revised from more than once, and the context is derived rather
    than evidence, so it is a file that may be rewritten — unlike everything
    the run's proof covers, which is written exactly once.
    """
    directory = paths.run_dir(run_id) / "improvement"
    ensure_private_directory(directory)
    path = directory / "context.json"
    atomic_write_bytes(path, canonical_json_bytes(context), mode=0o600)
    return path


# ---------------------------------------------------------------------------
# prepare
# ---------------------------------------------------------------------------


def prepare_uplift_command(
    ctx: typer.Context,
    from_run: Annotated[
        str,
        typer.Option(
            "--from-run",
            metavar="RUN_ID",
            help="The finished run whose Skill becomes the new baseline.",
        ),
    ],
    candidate_skill: Annotated[
        Path,
        typer.Option(
            "--candidate-skill",
            metavar="PATH",
            help="The revised skill directory, or its SKILL.md.",
        ),
    ],
    label: Annotated[
        str | None,
        typer.Option(
            "--label",
            metavar="LABEL",
            help="What to call the revision. Defaults to the directory name.",
        ),
    ] = None,
) -> None:
    """Prepare a Skill v1 against Skill v2 comparison from a finished run."""
    context = cli_context(ctx)

    def action() -> CommandResult[UpliftPreparePayload]:
        prepared = build_uplift_service(context).prepare_replacement(
            source_run_id=from_run,
            candidate_skill_path=candidate_skill,
            candidate_label=label,
        )
        payload = _prepare_payload(from_run, prepared)
        return CommandResult(
            data=payload,
            messages=[
                CliMessage(
                    level=MessageLevel.INFO,
                    code="replacement_prepared",
                    text=(
                        f"Prepared {payload.candidate_label} against the Skill "
                        f"run {from_run} measured. Nothing has run yet."
                    ),
                )
            ],
            warnings=[
                CliMessage(
                    level=MessageLevel.WARNING,
                    code="draft_warning",
                    text=warning,
                )
                for warning in payload.warnings
            ],
            next_actions=[_start_replacement(payload)],
        )

    invoke_command(context, PREPARE_COMMAND, action, render_data=_render_prepare)


def _prepare_payload(
    source_run_id: str, prepared: PreparedDraft
) -> UpliftPreparePayload:
    """Project a prepared replacement draft into the response a caller acts on."""
    draft = prepared.draft
    comparison = prepared.manifest_comparison
    subject = prepared.source.campaign.subject
    return UpliftPreparePayload(
        draft_id=draft.id,
        draft_digest=prepared.draft_digest,
        confirmation_token=prepared.confirmation_token,
        confirmation_expires_at=prepared.confirmation_expires_at,
        source_run_id=source_run_id,
        campaign_spec_digest=draft.campaign_spec_digest,
        data_policy_digest=draft.data_policy_digest,
        baseline_skill_digest=subject.harness.skills[0].digest,
        candidate_skill_digest=draft.skill_artifact.root_digest,
        candidate_label=draft.skill_artifact.name,
        included_files=list(draft.included_files),
        estimated_episodes=draft.estimated_episodes,
        controlled=comparison.controlled,
        allowed_differences=list(comparison.allowed_differences),
        differences=[difference.pointer for difference in comparison.differences],
        policy_acceptance=draft.policy_acceptance,
        warnings=list(draft.warnings),
    )


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------


def start_uplift_command(
    ctx: typer.Context,
    draft_id: Annotated[
        str,
        typer.Argument(metavar="DRAFT_ID", help="The prepared replacement to start."),
    ],
    confirmation_token: Annotated[
        str,
        typer.Option(
            "--confirmation-token",
            metavar="TOKEN",
            help="The token `techtree uplift prepare` returned.",
        ),
    ],
    accept_data_policy: Annotated[
        str | None,
        typer.Option(
            "--accept-data-policy",
            metavar="DIGEST",
            help=(
                "Accept the draft's DataPolicy by naming its exact digest. "
                "Required when nothing can be asked."
            ),
        ),
    ] = None,
) -> None:
    """Consume a confirmation and start the Skill v1 against Skill v2 run."""
    context = cli_context(ctx)

    def action() -> CommandResult[UpliftStartPayload]:
        service = build_run_service(context)
        draft = DraftStore(context.paths, ConfirmationService()).get(draft_id)
        acknowledgement = acknowledge_data_policy(
            context, draft=draft, accepted_digest=accept_data_policy
        )
        status = service.start(
            draft_id=draft_id,
            confirmation_token=confirmation_token,
            policy_acknowledgement=acknowledgement,
        )
        payload = UpliftStartPayload(
            run_id=status.state.run_id,
            draft_id=draft.id,
            phase=status.state.phase,
            worker_pid=status.state.worker_pid,
            campaign_spec_digest=draft.campaign_spec_digest,
            data_policy_digest=draft.data_policy_digest,
            policy_acknowledgement_method=acknowledgement.method,
        )
        return CommandResult(
            data=payload,
            messages=[
                CliMessage(
                    level=MessageLevel.INFO,
                    code="run_started",
                    text=(
                        f"Run {payload.run_id} is going. It continues whether "
                        "or not this command is still open."
                    ),
                )
            ],
            next_actions=[_watch_run(payload.run_id)],
        )

    invoke_command(context, START_COMMAND, action, render_data=_render_start)


# ---------------------------------------------------------------------------
# Next actions
# ---------------------------------------------------------------------------


def _prepare_replacement(run_id: str) -> NextAction:
    return NextAction(
        id="prepare_replacement",
        label="Compare a revised Skill against the one this run measured",
        reason=(
            "Point --candidate-skill at the revised skill directory. The "
            "baseline is pinned to the Skill this run actually evaluated."
        ),
        cli=[
            "techtree",
            "uplift",
            "prepare",
            "--from-run",
            run_id,
            "--candidate-skill",
            "PATH",
        ],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=True,
    )


def _start_replacement(payload: UpliftPreparePayload) -> NextAction:
    return NextAction(
        id="start_replacement",
        label=f"Start {payload.candidate_label} against the previous Skill",
        reason=(
            f"Runs {payload.estimated_episodes} episodes. Accepting the data "
            "policy is part of starting."
        ),
        cli=[
            "techtree",
            "uplift",
            "start",
            payload.draft_id,
            "--confirmation-token",
            payload.confirmation_token,
            "--accept-data-policy",
            payload.data_policy_digest,
        ],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=True,
    )


def _watch_run(run_id: str) -> NextAction:
    return NextAction(
        id="run_status",
        label="Check how the run is going",
        reason="The run continues after this command returns.",
        cli=["techtree", "run", "status", run_id],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )


# ---------------------------------------------------------------------------
# Human rendering
# ---------------------------------------------------------------------------


def _render_context(data: object, console: Console) -> None:
    """Print a short summary and where the full context was written."""
    if not isinstance(data, UpliftContextPayload):
        return
    improvement = data.context

    _print_pairs(
        console,
        [
            ("Run", improvement.source_run_id),
            ("Skill being revised", improvement.parent_skill_digest),
            ("Tasks included", str(len(improvement.examples))),
            ("Written to", data.relative_path),
        ],
    )
    console.print()
    console.print(improvement.objective)

    console.print()
    console.print("Tasks worth looking at")
    table = Table(box=None, pad_edge=False, padding=(0, 2))
    table.add_column("Task", no_wrap=True)
    table.add_column("Outcome", no_wrap=True)
    table.add_column("Reward", justify="right", no_wrap=True)
    for example in improvement.examples:
        table.add_row(
            example.task_label,
            example.outcome.replace("_", " "),
            f"{example.reward:.3f}",
        )
    console.print(table)

    console.print()
    console.print("Not included")
    for item in improvement.prohibited_material:
        console.print(f"  {item}")


def _render_prepare(data: object, console: Console) -> None:
    """Print everything a person needs before approving a second run."""
    if not isinstance(data, UpliftPreparePayload):
        return

    _print_pairs(
        console,
        [
            ("Draft", data.draft_id),
            ("From run", data.source_run_id),
            ("Campaign digest", data.campaign_spec_digest),
            ("DataPolicy digest", data.data_policy_digest),
            ("Baseline skill", data.baseline_skill_digest),
            ("Candidate skill", data.candidate_skill_digest),
            ("Candidate", data.candidate_label),
        ],
    )

    console.print()
    console.print(f"Included files ({len(data.included_files)})")
    for path in data.included_files:
        console.print(f"  {path}")

    console.print()
    console.print("The comparison")
    _print_pairs(
        console,
        [
            ("Allowed difference", ", ".join(data.allowed_differences)),
            ("Found difference", ", ".join(data.differences)),
            ("Controlled", "yes" if data.controlled else "no"),
            ("Estimated episodes", str(data.estimated_episodes)),
        ],
    )

    console.print()
    console.print(data.policy_acceptance.summary)
    console.print()
    console.print(
        "Confirmation expires "
        f"{data.confirmation_expires_at.isoformat().replace('+00:00', 'Z')}."
    )


def _render_start(data: object, console: Console) -> None:
    """Print what was started and where it can be followed."""
    if not isinstance(data, UpliftStartPayload):
        return
    _print_pairs(
        console,
        [
            ("Run", data.run_id),
            ("Draft", data.draft_id),
            ("Phase", data.phase.value),
            ("Worker", "not started" if data.worker_pid is None else "running"),
            ("Campaign digest", data.campaign_spec_digest),
            ("DataPolicy digest", data.data_policy_digest),
            ("Accepted by", data.policy_acknowledgement_method.replace("_", " ")),
        ],
    )


def _print_pairs(console: Console, pairs: list[tuple[str, str]]) -> None:
    table = Table(box=None, show_header=False, pad_edge=False, padding=(0, 2))
    table.add_column("label", no_wrap=True)
    table.add_column("value", overflow="fold")
    for label, value in pairs:
        table.add_row(label, value)
    console.print(table)
