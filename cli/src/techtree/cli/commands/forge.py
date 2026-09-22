"""``techtree forge build|run|compare|inspect-skill|status``.

``docs/plan/repo2rlenv-local-lane.md``; Source Skill inspection is
``docs/plan/v0.3.0-skill-environments.md`` (U3a).

``forge build`` takes a local repository and retains generated Harbor tasks and
their qualification evidence; ``forge run`` declares one arm of an experiment
on those tasks and runs it with the person's own Hermes; ``forge compare``
pairs a baseline run with a candidate run and writes the record and the
report; ``forge inspect-skill`` looks at a Source Skill without running any
of it and records what it holds; ``forge status`` reads any of them, or a
Skill revision made through ``uplift``, back without requiring build
tools. Build execution belongs to
:class:`~techtree.forge.service.ForgeService`, run execution to
:class:`~techtree.forge.run.ForgeRunner`, comparison to
:mod:`techtree.forge.compare`, Source Skill inspection to
:mod:`techtree.forge.source`; inspection uses the separate record readers.
What to say about each operation is here.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

import typer
from rich.console import Console
from rich.padding import Padding
from rich.text import Text

from techtree.canonical import digest_object
from techtree.cli.commands.climb import (
    ReviewSurface,
    require_the_review_surface_was_answered,
)
from techtree.cli.confirm import confirmed
from techtree.cli.context import CliContext, cli_context
from techtree.cli.invoke import CommandResult, approval_operation, invoke_command
from techtree.cli.output import human_console, render_pairs
from techtree.engines.installer import find_uv
from techtree.errors import PolicyError, RunError, TechtreeError, ValidationError
from techtree.forge.compare import VERDICT_WORDS, compare_runs, read_comparison_status
from techtree.forge.experiment import declare_run_spec
from techtree.forge.models import (
    MAX_PLANNED_TASKS,
    ForgeArm,
    ForgeArmTotals,
    ForgeAttemptOutcome,
    ForgeBuildStatus,
    ForgeComparisonStatus,
    ForgeLanguage,
    ForgePlanRecord,
    ForgePlanStatus,
    ForgeProposalStatus,
    ForgeRevisionStatus,
    ForgeRunSpec,
    ForgeRunStatus,
    ForgeSourceStatus,
    ForgeTaskRegression,
    ForgeUsage,
)
from techtree.forge.planning import (
    check_plan,
    correct_proposal,
    prepare_plan,
    read_plan_status,
    read_proposal_status,
    start_plan,
)
from techtree.forge.process import run_command
from techtree.forge.profile import PROFILE_NAME
from techtree.forge.report import (
    FEW_TASKS,
    OUTCOME_WORDS,
    build_summary,
    first_failed_check,
    import_summary,
    task_verdict,
)
from techtree.forge.revision import read_revision_status
from techtree.forge.run import ForgeRunner, read_run_status
from techtree.forge.service import ForgeService, read_build_status
from techtree.forge.source import (
    UNSUPPORTED_WORDS,
    inspect_source_skill,
    read_source_status,
)
from techtree.ids import id_prefix
from techtree.models.base import Digest, NonEmptyString, ProtocolModel
from techtree.models.cli import (
    CliWarning,
    DataEgress,
    NextAction,
    Operation,
    RetryClass,
    SideEffect,
    invocation,
)

__all__ = [
    "ForgeRunReview",
    "HermesReasoning",
    "ask_to_start",
    "build_forge_command",
    "compare_forge_command",
    "correct_proposal_forge_command",
    "inspect_skill_forge_command",
    "plan_forge_command",
    "plan_next_actions",
    "plan_start_forge_command",
    "plan_warnings",
    "planning_review_lines",
    "proposal_status_action",
    "render_forge_comparison",
    "render_forge_plan",
    "render_forge_proposal",
    "render_forge_revision",
    "render_forge_run",
    "render_forge_source",
    "render_forge_status",
    "review_run_spec",
    "revision_status_action",
    "revision_warnings",
    "run_forge_command",
    "run_status_action",
    "run_warnings",
    "source_status_action",
    "source_warnings",
    "status_forge_command",
]

#: Why an experiment is refused without a person's answer, said the same way
#: a Climb start says it.
RUN_NOT_APPROVED = "forge_run_not_approved"


class HermesReasoning(StrEnum):
    """The reasoning settings Hermes accepts on its command line."""

    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    MAX = "max"
    ULTRA = "ultra"


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


def run_forge_command(
    ctx: typer.Context,
    arm: Annotated[
        ForgeArm,
        typer.Option(
            "--arm",
            help="Which side of the comparison this run is: the baseline runs "
            "without the Skill, the candidate with it.",
        ),
    ],
    build_id: Annotated[
        str,
        typer.Option(
            "--build", metavar="BUILD_ID", help="A build that finished qualification."
        ),
    ],
    provider: Annotated[
        str,
        typer.Option(
            "--provider",
            help="The provider Hermes will be asked for, by the name Hermes uses.",
        ),
    ],
    model: Annotated[
        str, typer.Option("--model", help="The model Hermes will be asked for.")
    ],
    tasks: Annotated[
        str | None,
        typer.Option(
            "--tasks",
            metavar="TASK_ID[,TASK_ID...]",
            help="The qualified tasks to run, in order. Every qualified task "
            "when omitted.",
        ),
    ] = None,
    skill: Annotated[
        Path | None,
        typer.Option(
            "--skill",
            metavar="PATH",
            help="The Skill directory the candidate arm measures. Refused on "
            "the baseline arm.",
        ),
    ] = None,
    reasoning: Annotated[
        HermesReasoning | None,
        typer.Option("--reasoning", help="Hermes' reasoning setting, if one."),
    ] = None,
    repetitions: Annotated[
        int,
        typer.Option("--repetitions", min=1, help="Attempts per task."),
    ] = 1,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            help=(
                "Start without being asked. For an operator running Techtree "
                "where nobody can answer a prompt; it is never a shortcut for "
                "an agent to take on a person's behalf."
            ),
        ),
    ] = False,
) -> None:
    """Run one arm of an experiment on qualified tasks with your own Hermes."""
    context = cli_context(ctx)

    def action() -> CommandResult[ForgeRunStatus | ForgeRunReview]:
        spec = declare_run_spec(
            context.paths,
            arm=arm,
            build_id=build_id,
            task_ids=tasks.split(",") if tasks is not None else None,
            skill_root=skill,
            provider=provider,
            model_id=model,
            reasoning=reasoning.value if reasoning is not None else None,
            repetitions=repetitions,
        )
        review = review_run_spec(spec)
        if not yes and context.no_input:
            return CommandResult(
                data=review,
                state_digest=review.spec_digest,
                next_actions=[_run_when_approved(review, ctx.params)],
            )
        if not yes:
            ask_to_start(context, review)
        status = ForgeRunner(context.paths, run_command).run(spec, skill)
        return CommandResult(
            data=status,
            warnings=run_warnings(status),
            next_actions=[run_status_action(status)],
        )

    invoke_command(
        context,
        approval_operation(context, assume_yes=yes),
        action,
        render_data=_render_run,
    )


def compare_forge_command(
    ctx: typer.Context,
    baseline_run: Annotated[
        str,
        typer.Argument(metavar="BASELINE_RUN_ID", help="The run without the Skill."),
    ],
    candidate_run: Annotated[
        str,
        typer.Argument(metavar="CANDIDATE_RUN_ID", help="The run with the Skill."),
    ],
) -> None:
    """Compare a baseline run with a candidate run and write the report."""
    context = cli_context(ctx)

    def action() -> CommandResult[ForgeComparisonStatus]:
        status = compare_runs(context.paths, baseline_run, candidate_run)
        return CommandResult(
            data=status,
            warnings=_comparison_warnings(status),
            next_actions=[_comparison_status_action(status)],
        )

    invoke_command(
        context, Operation.RESULT_INSPECT, action, render_data=_render_compared
    )


def inspect_skill_forge_command(
    ctx: typer.Context,
    skill: Annotated[
        Path,
        typer.Argument(
            metavar="PATH",
            help="The Skill's directory, or its SKILL.md.",
        ),
    ],
    derived_from: Annotated[
        str | None,
        typer.Option(
            "--derived-from",
            metavar="SOURCE_ID",
            help="The Skill this one is a reduced copy of, as an earlier look "
            "recorded it.",
        ),
    ] = None,
) -> None:
    """Look at a Skill without running any of it, and record what it holds."""
    context = cli_context(ctx)

    def action() -> CommandResult[ForgeSourceStatus]:
        status = inspect_source_skill(context.paths, skill, derived_from=derived_from)
        record = status.record
        if record.state == "refused":
            raise ValidationError(
                "Techtree cannot use this Skill as it is: "
                + "; ".join(refusal.message for refusal in record.refusals)
                + ". Nothing in it was run and no model was asked about it. A copy "
                "without these is a different Skill; look at that copy with "
                f"--derived-from {status.source_id} so it records where it came "
                "from.",
                code="forge_skill_unsupported",
                details={
                    "source_id": status.source_id,
                    "path": status.path,
                    "refusals": [
                        refusal.model_dump(mode="json") for refusal in record.refusals
                    ],
                },
                next_actions=[source_status_action(status)],
            )
        return CommandResult(
            data=status,
            warnings=source_warnings(status),
            next_actions=[source_status_action(status)],
        )

    invoke_command(context, Operation.PLAN_PREPARE, action, render_data=_render_source)


def status_forge_command(
    ctx: typer.Context,
    record_id: Annotated[
        str,
        typer.Argument(
            metavar="BUILD_ID|RUN_ID|COMPARISON_ID|REVISION_ID|SOURCE_ID|PLAN_ID"
            "|PROPOSAL_ID",
            help="The build, run, comparison, Skill revision, looked-at Skill, "
            "plan or proposal to show.",
        ),
    ],
) -> None:
    """Show a forge build, run, comparison, revision, Skill, plan or proposal."""
    context = cli_context(ctx)

    def action() -> CommandResult[
        ForgeBuildStatus
        | ForgeRunStatus
        | ForgeComparisonStatus
        | ForgeRevisionStatus
        | ForgeSourceStatus
        | ForgePlanStatus
        | ForgeProposalStatus
    ]:
        match id_prefix(record_id):
            case "forgeplan":
                plan = read_plan_status(context.paths, record_id)
                return CommandResult(
                    data=plan,
                    warnings=plan_warnings(plan),
                    next_actions=plan_next_actions(plan),
                )
            case "forgeprop":
                proposal = read_proposal_status(context.paths, record_id)
                return CommandResult(data=proposal)
            case "forgesrc":
                source = read_source_status(context.paths, record_id)
                return CommandResult(data=source, warnings=source_warnings(source))
            case "forgerun":
                run = read_run_status(context.paths, record_id)
                return CommandResult(data=run, warnings=run_warnings(run))
            case "forgecmp":
                comparison = read_comparison_status(context.paths, record_id)
                return CommandResult(
                    data=comparison, warnings=_comparison_warnings(comparison)
                )
            case "forgerev":
                revision = read_revision_status(context.paths, record_id)
                return CommandResult(
                    data=revision, warnings=revision_warnings(revision)
                )
        status = read_build_status(context.paths, record_id)
        return CommandResult(data=status, warnings=_warnings(status))

    invoke_command(context, Operation.PLAN_INSPECT, action, render_data=_render_status)


def plan_forge_command(
    ctx: typer.Context,
    source_id: Annotated[
        str,
        typer.Argument(
            metavar="SOURCE_ID",
            help="A Skill that forge inspect-skill recorded as usable.",
        ),
    ],
    provider: Annotated[
        str,
        typer.Option(
            "--provider",
            help="The provider Hermes will be asked for, by the name Hermes uses.",
        ),
    ],
    model: Annotated[
        str, typer.Option("--model", help="The model Hermes will be asked for.")
    ],
    reasoning: Annotated[
        HermesReasoning | None,
        typer.Option("--reasoning", help="Hermes' reasoning setting, if one."),
    ] = None,
    tasks: Annotated[
        int,
        typer.Option(
            "--tasks",
            min=1,
            max=MAX_PLANNED_TASKS,
            help="The most tasks the planner may propose.",
        ),
    ] = 3,
    retry_of: Annotated[
        str | None,
        typer.Option(
            "--retry-of",
            metavar="PLAN_ID",
            help="An earlier plan of the same Skill that failed, was rejected "
            "or whose outcome is unknown, which this one tries again.",
        ),
    ] = None,
) -> None:
    """Prepare the planning of tasks from a Skill, without calling the planner."""
    context = cli_context(ctx)

    def action() -> CommandResult[ForgePlanStatus]:
        status = prepare_plan(
            context.paths,
            source_id=source_id,
            provider=provider,
            model_id=model,
            reasoning=reasoning.value if reasoning is not None else None,
            max_tasks=tasks,
            retry_of=retry_of,
        )
        return CommandResult(
            data=status,
            state_digest=status.record.planning_digest,
            next_actions=[_plan_when_approved(status)],
        )

    invoke_command(context, Operation.PLAN_PREPARE, action, render_data=_render_plan)


def plan_start_forge_command(
    ctx: typer.Context,
    plan_id: Annotated[
        str,
        typer.Argument(metavar="PLAN_ID", help="The prepared plan to send."),
    ],
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            help=(
                "Send without being asked. For an operator running Techtree "
                "where nobody can answer a prompt; it is never a shortcut for "
                "an agent to take on a person's behalf."
            ),
        ),
    ] = False,
    reviewed_on: Annotated[
        ReviewSurface,
        typer.Option(
            "--reviewed-on",
            help=(
                "Where the person who approved this plan answered. Pass "
                "host-agent when the review was shown in a conversation and "
                "confirmed there, so the approval records the surface the "
                "answer was actually given on. Like --yes, it states what a "
                "person already did and is never a shortcut a model may take."
            ),
        ),
    ] = ReviewSurface.CLI,
) -> None:
    """Review a prepared plan, approve it, and send it to the planner once."""
    context = cli_context(ctx)

    def action() -> CommandResult[ForgePlanStatus]:
        require_the_review_surface_was_answered(
            draft_id=plan_id, assume_yes=yes, reviewed_on=reviewed_on
        )
        status = check_plan(context.paths, plan_id)
        if not yes and context.no_input:
            return CommandResult(
                data=status,
                state_digest=status.record.planning_digest,
                next_actions=[_plan_when_approved(status)],
            )
        if not yes:
            _ask_to_plan(context, status.record)
        started = start_plan(
            context.paths,
            plan_id,
            reviewed_on="host-agent"
            if reviewed_on is ReviewSurface.HOST_AGENT
            else "cli",
            answered_with="yes-flag" if yes else "prompt",
            run=run_command,
        )
        return CommandResult(
            data=started,
            warnings=plan_warnings(started),
            next_actions=plan_next_actions(started),
            error=_plan_error(started),
        )

    invoke_command(
        context,
        approval_operation(context, assume_yes=yes),
        action,
        render_data=_render_plan,
    )


def correct_proposal_forge_command(
    ctx: typer.Context,
    proposal_id: Annotated[
        str,
        typer.Argument(metavar="PROPOSAL_ID", help="The proposal you corrected."),
    ],
    tasks_file: Annotated[
        Path,
        typer.Argument(
            metavar="FILE",
            help='Your corrected tasks, as {"tasks": [...]}: a copy of the '
            "proposal's tasks.json, edited.",
        ),
    ],
) -> None:
    """Record your corrections to proposed tasks as a new proposal."""
    context = cli_context(ctx)

    def action() -> CommandResult[ForgeProposalStatus]:
        status = correct_proposal(context.paths, proposal_id, tasks_file)
        return CommandResult(
            data=status,
            state_digest=status.record.proposal_digest,
            next_actions=[proposal_status_action(status)],
        )

    invoke_command(
        context, Operation.PLAN_PREPARE, action, render_data=_render_proposal
    )


class ForgeRunReview(ProtocolModel):
    """What running this arm would do, for a caller that has to show it.

    The machine reading of what a terminal prints before it asks: which
    tasks, how many attempts, which Hermes and model, where the model calls
    go, and what is not known about the cost. Nothing here is an approval
    and nothing has started.
    """

    spec_digest: Digest
    spec: ForgeRunSpec
    attempts: int
    review: list[NonEmptyString]


#: What every experiment says about money before it asks: nothing is quoted
#: in advance; what each attempt used is recorded afterwards from Hermes' own
#: usage report, and a subscription Hermes cannot put a figure on is recorded
#: as exactly that.
COST_LINE = (
    "Cost: nothing is quoted in advance. What each attempt used is recorded "
    "afterwards from Hermes' own usage report, including whether Hermes could "
    "put a dollar figure on it."
)


def review_run_spec(spec: ForgeRunSpec) -> ForgeRunReview:
    attempts = len(spec.task_ids) * spec.sampling.repetitions
    lines = [
        f"Arm: {spec.arm.value}"
        + (
            f", with Skill {spec.skill.name} ({spec.skill.root_digest[:12]})"
            if spec.skill is not None
            else ", without a Skill"
        ),
        f"Build: {spec.build_id}",
        f"Tasks: {len(spec.task_ids)} ({', '.join(spec.task_ids)})",
        f"Attempts: {attempts} ({spec.sampling.repetitions} per task)",
        f"Agent: {spec.agent.executable} (Hermes Agent v{spec.agent.version})",
        f"Model: {spec.model.model_id} from {spec.model.provider}"
        + (f", reasoning {spec.model.reasoning}" if spec.model.reasoning else ""),
        f"Model calls go to that provider on the sign-in of your Hermes profile "
        f"{PROFILE_NAME}; Techtree copies no credential and reads none.",
        "Each attempt empties that profile of everything but the sign-in, so "
        "it starts from a fresh Hermes state with memory off, in a "
        "sandbox with no network, "
        f"{spec.limits.container_cpus} CPUs and "
        f"{spec.limits.container_memory_mb} MB, for the task's own time limit.",
        COST_LINE,
    ]
    return ForgeRunReview(
        spec_digest=digest_object(spec), spec=spec, attempts=attempts, review=lines
    )


def ask_to_start(context: CliContext, review: ForgeRunReview) -> None:
    console = human_console(no_color=context.no_color)
    for line in review.review:
        console.print(line, markup=False)
    console.print()
    if not confirmed("Start this experiment?"):
        raise PolicyError(
            "the experiment was not approved, so nothing was started",
            code=RUN_NOT_APPROVED,
            details={"spec_digest": review.spec_digest},
        )


def _run_when_approved(review: ForgeRunReview, params: dict[str, object]) -> NextAction:
    """Return the same run with ``--yes``, bound to the specification shown.

    A machine cannot take it: ``approval_required`` says so, and the
    ``expected_state_digest`` is the specification the review was about, so
    a different build, model or Skill is not started on this answer.
    """
    options: dict[str, str | Literal[True]] = {"--yes": True}
    for name, value in params.items():
        if name == "yes" or value is None:
            continue
        flag = "--build" if name == "build_id" else f"--{name}"
        options[flag] = value.value if isinstance(value, StrEnum) else str(value)
    return NextAction(
        operation=Operation.ACTION_EXECUTE,
        prepared_arguments=invocation("forge", "run", options=options),
        expected_state_digest=review.spec_digest,
        side_effect=SideEffect.LOCAL_EXECUTION,
        approval_required=True,
        retry_class=RetryClass.HUMAN_DECISION_REQUIRED,
        estimated_cost=None,
        data_egress=DataEgress.MODEL_PROVIDER,
        reason="A person approves the model calls this experiment makes on "
        "their own account.",
    )


def render_forge_run(status: ForgeRunStatus, console: Console) -> None:
    """Print one run for a person."""
    spec = status.spec
    record = status.record
    pairs = [
        ("Run", status.run_id),
        ("Outcome", record.state),
        (
            "Arm",
            spec.arm.value
            + (f" with Skill {spec.skill.name}" if spec.skill is not None else ""),
        ),
        ("Build", spec.build_id),
        ("Model", f"{spec.model.model_id} from {spec.model.provider}"),
        ("Agent", f"Hermes Agent v{spec.agent.version}"),
        (
            "Attempts",
            f"{len(record.attempts)} of "
            f"{len(spec.task_ids) * spec.sampling.repetitions} recorded",
        ),
        ("Evidence", status.path),
    ]
    render_pairs(pairs, console)
    if record.failure is not None:
        console.print(f"{record.failure.code}: {record.failure.message}", markup=False)
    if record.attempts:
        console.print()
    for attempt in record.attempts:
        usage = attempt.usage
        words = OUTCOME_WORDS[attempt.outcome]
        parts = [f"{attempt.task_id} #{attempt.attempt}: {words}"]
        if attempt.reward is not None:
            parts.append(f"reward {attempt.reward:g}")
        parts.append(f"{attempt.agent_seconds:.0f}s")
        if usage is not None and usage.total_tokens is not None:
            parts.append(f"{usage.total_tokens} tokens")
        parts.append(_cost_words(usage))
        console.print(", ".join(parts), markup=False)


def _cost_words(usage: ForgeUsage | None) -> str:
    if usage is None:
        return "no usage report"
    if usage.estimated_cost_usd is None:
        return "no dollar figure"
    status = f" ({usage.cost_status})" if usage.cost_status else ""
    return f"about ${usage.estimated_cost_usd:.4f}{status}"


def _render_run(data: object, console: Console) -> None:
    if isinstance(data, ForgeRunReview):
        for line in data.review:
            console.print(line, markup=False)
        console.print()
        console.print("Nothing has started. Run again with --yes to start it.")
        return
    if isinstance(data, ForgeRunStatus):
        console.print(f"Forge run {data.run_id} {data.record.state}.")
        console.print()
        render_forge_run(data, console)


def run_warnings(status: ForgeRunStatus) -> list[CliWarning]:
    """Say when attempts ended without a verdict, in one line."""
    ungraded = [
        attempt
        for attempt in status.record.attempts
        if attempt.outcome is not ForgeAttemptOutcome.GRADED
    ]
    if not ungraded:
        return []
    return [
        CliWarning(
            id="forge_attempts_ungraded",
            text=(
                f"{len(ungraded)} of {len(status.record.attempts)} attempts ended "
                "without a verdict; each says why in the run's evidence."
            ),
            resolvable_by=None,
        )
    ]


def run_status_action(status: ForgeRunStatus) -> NextAction:
    return NextAction(
        operation=Operation.PLAN_INSPECT,
        prepared_arguments=invocation("forge", "status", arguments=[status.run_id]),
        expected_state_digest=None,
        side_effect=SideEffect.NONE,
        approval_required=False,
        retry_class=RetryClass.SAFE,
        estimated_cost=None,
        data_egress=DataEgress.NONE,
        reason="The run's attempts and their evidence can be read back later.",
    )


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
        source = build.source
        if source.kind == "repository":
            pairs.extend(
                [
                    ("Repository", source.repository),
                    ("Commit", source.head_commit),
                    ("Image", source.bootstrap_image_tag),
                    ("Tests", " && ".join(source.test_commands)),
                    ("Candidates", str(source.generation.candidates)),
                    ("Emitted", str(source.generation.emitted)),
                ]
            )
        else:
            pairs.extend(
                [
                    ("Source Skill", source.source_skill_digest),
                    ("Recipe", f"{source.recipe} {source.recipe_version}"),
                    ("Producer", f"{source.producer} {source.producer_version}"),
                    (
                        "Base images",
                        ", ".join(image.reference for image in source.base_images),
                    ),
                    ("Committed tasks", str(len(build.task_set.tasks))),
                ]
            )
    elif progress is not None:
        pairs.append(("Origin", progress.origin))
    render_pairs(pairs, console)
    if progress is not None and progress.failure is not None:
        console.print(
            f"{progress.failure.code}: {progress.failure.message}", markup=False
        )
        console.print("Inspect the retained evidence before starting a new build.")
    if build is not None:
        console.print()
        console.print(
            build_summary(build.source.generation, qualification)
            if build.source.kind == "repository"
            else import_summary(len(build.task_set.tasks), qualification),
            markup=False,
        )
    if qualification is not None:
        for task in qualification.tasks:
            console.print(task_verdict(task), markup=False)
            failed = first_failed_check(task)
            if failed is not None:
                console.print(f"  ({failed.name}: {failed.detail})", markup=False)
    elif progress is not None and progress.completed_tasks:
        console.print("Partial task evidence only; qualification has not finished.")
        for task in progress.completed_tasks:
            console.print(
                f"  {task.task_id}: checks recorded; not admitted for use", markup=False
            )


def _plural(count: int, one: str, many: str) -> str:
    return one if count == 1 else many


def _render_built(data: object, console: Console) -> None:
    if not isinstance(data, ForgeBuildStatus):
        return
    console.print(f"Forge build {data.build_id} finished; no model was called.")
    console.print()
    render_forge_status(data, console)


def render_forge_comparison(status: ForgeComparisonStatus, console: Console) -> None:
    """Print one comparison for a person: the verdict, the totals, the pairs."""
    record = status.record
    pairs = [
        ("Comparison", status.comparison_id),
        ("Skill", f"{record.skill_name} ({record.skill_digest[:19]})"),
        ("Baseline run", record.baseline_run_id),
        ("Candidate run", record.candidate_run_id),
        ("Build", record.build_id),
        ("Result", "complete" if record.complete else "partial"),
        ("Verdict", VERDICT_WORDS[record.verdict]),
        (
            "Pairs",
            f"{record.wins} won, {record.losses} lost, {record.ties} tied, "
            f"{record.unresolved} unresolved of {record.pairs_planned} planned",
        ),
        (
            "Mean reward",
            _arm_pair(record.baseline.mean_reward, record.candidate.mean_reward),
        ),
        (
            "Agent time",
            _arm_pair(
                record.baseline.agent_seconds, record.candidate.agent_seconds, "s"
            ),
        ),
        (
            "Model calls",
            _arm_pair(record.baseline.api_calls, record.candidate.api_calls),
        ),
        (
            "Tokens",
            _arm_pair(record.baseline.total_tokens, record.candidate.total_tokens),
        ),
        ("Cost", f"{_totals_cost(record.baseline)} → {_totals_cost(record.candidate)}"),
        ("Report", status.report_path),
        ("Record", status.path),
    ]
    render_pairs(pairs, console)
    console.print()
    console.print(record.summary, markup=False)
    console.print()
    if record.regressions:
        console.print("Where the Skill lost:")
        for regression in record.regressions:
            console.print(f"  {_regression_words(regression)}", markup=False)
    else:
        console.print("The Skill lost no graded pair.")
    console.print()
    if record.repetitions == 1:
        console.print(
            "One attempt per task; consistency across attempts was not measured."
        )
    else:
        console.print("Across attempts:")
        for task in record.consistency:
            both = "; went both ways" if task.went_both_ways else ""
            console.print(
                f"  {task.task_id}: {task.wins} won, {task.losses} lost, "
                f"{task.ties} tied, {task.unresolved} unresolved{both}",
                markup=False,
            )
    console.print()
    for pair in record.pairs:
        baseline = _side_words(pair.baseline_outcome, pair.baseline_reward)
        candidate = _side_words(pair.candidate_outcome, pair.candidate_reward)
        console.print(
            f"{pair.task_id} #{pair.attempt}: {pair.result.value}"
            + (f" ({pair.delta:+g})" if pair.delta is not None else "")
            + f"; baseline {baseline}, candidate {candidate}",
            markup=False,
        )


def _regression_words(regression: ForgeTaskRegression) -> str:
    lost = _attempts(regression.attempts_lost)
    if not regression.attempts_won:
        return f"{regression.task_id}: lost {lost}"
    return (
        f"{regression.task_id}: lost {lost}; won {_attempts(regression.attempts_won)}"
    )


def _attempts(attempts: list[int]) -> str:
    word = "attempt" if len(attempts) == 1 else "attempts"
    return f"{word} {', '.join(str(a) for a in attempts)}"


def _arm_pair(baseline: float | None, candidate: float | None, unit: str = "") -> str:
    def one(value: float | None) -> str:
        if value is None:
            return "unknown"
        return f"{value:g}{unit}" if isinstance(value, int) else f"{value:.3g}{unit}"

    return f"{one(baseline)} → {one(candidate)}"


def _totals_cost(totals: ForgeArmTotals) -> str:
    statuses = f" ({', '.join(totals.cost_statuses)})" if totals.cost_statuses else ""
    if totals.cost_usd is None:
        return "no dollar figure" + statuses
    return f"${totals.cost_usd:.4f}{statuses}"


def _side_words(outcome: ForgeAttemptOutcome | None, reward: float | None) -> str:
    if outcome is None:
        return "not attempted"
    return f"reward {reward:g}" if reward is not None else OUTCOME_WORDS[outcome]


def _render_compared(data: object, console: Console) -> None:
    if not isinstance(data, ForgeComparisonStatus):
        return
    console.print(
        f"Forge comparison {data.comparison_id} written; no model was called."
    )
    console.print()
    render_forge_comparison(data, console)


def _comparison_warnings(status: ForgeComparisonStatus) -> list[CliWarning]:
    """Say when the comparison is partial, in one line."""
    record = status.record
    if record.complete:
        return []
    return [
        CliWarning(
            id="forge_comparison_partial",
            text=(
                f"{record.unresolved} of {record.pairs_planned} planned pairs have "
                "no verdict on both arms; the counts are over the graded pairs "
                "only and this is not a complete result."
            ),
            resolvable_by=None,
        )
    ]


def _comparison_status_action(status: ForgeComparisonStatus) -> NextAction:
    return NextAction(
        operation=Operation.PLAN_INSPECT,
        prepared_arguments=invocation(
            "forge", "status", arguments=[status.comparison_id]
        ),
        expected_state_digest=None,
        side_effect=SideEffect.NONE,
        approval_required=False,
        retry_class=RetryClass.SAFE,
        estimated_cost=None,
        data_egress=DataEgress.NONE,
        reason="The comparison and where its report is can be read back later.",
    )


def render_forge_revision(status: ForgeRevisionStatus, console: Console) -> None:
    """Print one Skill revision for a person: what it revises, and how it did."""
    record = status.record
    pairs = [
        ("Revision", status.revision_id),
        ("State", record.state),
        ("Revised Skill", f"{record.skill.name} ({record.skill.root_digest[:19]})"),
        ("Revises", f"{record.parent_skill_digest[:19]} from {record.comparison_id}"),
        ("Baseline run", record.baseline_run_id),
        ("Build", record.build_id),
        ("Controlled", "yes" if record.comparability.controlled else "no"),
        (
            "Screening",
            f"{len(record.screening)} shared "
            f"{'line' if len(record.screening) == 1 else 'lines'} with hidden "
            "material"
            if record.screening
            else "no line shared with hidden material",
        ),
    ]
    if record.measured_run_id is not None:
        pairs.append(("Measured run", record.measured_run_id))
    if record.measured_comparison_id is not None:
        pairs.append(("Comparison", record.measured_comparison_id))
    pairs.append(("Evidence", status.path))
    render_pairs(pairs, console)
    for finding in record.screening:
        console.print(
            f"  {finding.skill_path}:{finding.line} matches the "
            f"{finding.material.replace('_', ' ')} of {finding.task_id}: "
            f"{finding.excerpt}",
            markup=False,
        )
    if record.verdict is not None:
        console.print()
        console.print(record.verdict, markup=False)


def revision_warnings(status: ForgeRevisionStatus) -> list[CliWarning]:
    """Say when the revised Skill shares lines with hidden material."""
    if not status.record.screening:
        return []
    return [
        CliWarning(
            id="forge_revision_shares_hidden_material",
            text=(
                f"{len(status.record.screening)} line(s) of the revised Skill "
                "also occur in a task's reference fix or tests; a result with "
                "it may measure recall rather than method. Each is listed on "
                "the revision."
            ),
            resolvable_by=None,
        )
    ]


def revision_status_action(status: ForgeRevisionStatus) -> NextAction:
    return NextAction(
        operation=Operation.PLAN_INSPECT,
        prepared_arguments=invocation(
            "forge", "status", arguments=[status.revision_id]
        ),
        expected_state_digest=None,
        side_effect=SideEffect.NONE,
        approval_required=False,
        retry_class=RetryClass.SAFE,
        estimated_cost=None,
        data_egress=DataEgress.NONE,
        reason="The revision, its screening and its measurement can be read "
        "back later.",
    )


def render_forge_source(status: ForgeSourceStatus, console: Console) -> None:
    """Print one looked-at Skill: what it declares, what is kept, what is not."""
    record = status.record
    declaration = record.declaration
    kept = [entry for entry in record.entries if entry.disposition == "admitted"]
    pairs = [
        ("Skill", status.source_id),
        ("State", "can be used" if record.state == "admitted" else "cannot be used"),
        ("From", record.origin),
    ]
    if record.lineage is not None:
        pairs.append(
            (
                "Derived from",
                f"{record.lineage.parent_source_id} "
                f"({record.lineage.parent_admitted_digest[:19]})",
            )
        )
    if declaration is not None:
        pairs.append(("Name", declaration.name))
        pairs.append(("Description", declaration.description))
        if declaration.allowed_tools:
            pairs.append(
                (
                    "Asks for tools",
                    f"{' '.join(declaration.allowed_tools)} (asked for, not granted)",
                )
            )
    pairs.append(
        (
            "Kept",
            f"{len(kept)} {_plural(len(kept), 'file', 'files')} "
            f"({record.admitted_digest[:19]})"
            if record.state == "admitted"
            else "nothing, because the Skill cannot be used as it is",
        )
    )
    pairs.append(("Evidence", status.path))
    render_pairs(pairs, console)
    for entry in record.entries:
        if entry.reason is not None and not entry.required:
            console.print(
                f"  left out {entry.path}: {UNSUPPORTED_WORDS[entry.reason]}",
                markup=False,
            )
    for refusal in record.refusals:
        console.print(f"  cannot use: {refusal.message}", markup=False)


def _render_source(data: object, console: Console) -> None:
    if isinstance(data, ForgeSourceStatus):
        render_forge_source(data, console)


def source_warnings(status: ForgeSourceStatus) -> list[CliWarning]:
    """Say which files an admitted Skill leaves out because nothing needs them."""
    if status.record.state != "admitted":
        return []
    left_out = [
        entry.path
        for entry in status.record.entries
        if entry.disposition == "unsupported"
    ]
    if not left_out:
        return []
    return [
        CliWarning(
            id="forge_source_files_left_out",
            text=(
                f"{len(left_out)} {_plural(len(left_out), 'file', 'files')} "
                "the instructions never name "
                f"{_plural(len(left_out), 'is', 'are')} left out: "
                + ", ".join(left_out)
                + ". Each is listed with the reason."
            ),
            resolvable_by=None,
        )
    ]


def source_status_action(status: ForgeSourceStatus) -> NextAction:
    return NextAction(
        operation=Operation.PLAN_INSPECT,
        prepared_arguments=invocation("forge", "status", arguments=[status.source_id]),
        expected_state_digest=None,
        side_effect=SideEffect.NONE,
        approval_required=False,
        retry_class=RetryClass.SAFE,
        estimated_cost=None,
        data_egress=DataEgress.NONE,
        reason="What the Skill holds and what was kept can be read back later.",
    )


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------

#: Why a plan is refused without a person's answer.
PLAN_NOT_APPROVED = "forge_planning_not_approved"

_PLAN_STATE_WORDS: dict[str, str] = {
    "prepared": "prepared; the planner has not been called",
    "running": "the planner is working",
    "succeeded": "answered; the proposed tasks wait for your review",
    "rejected": "answered, but not with tasks Techtree can use",
    "failed": "failed",
    "outcome_unknown": "outcome unknown",
}


def planning_review_lines(record: ForgePlanRecord) -> list[str]:
    """What sending this plan would do, in the words a person approves."""
    review = record.review
    disclosure = review.disclosure
    limits = review.limits
    files = len(disclosure.files)
    file_bytes = sum(file.size for file in disclosure.files)
    lines = [
        f"Skill: {review.source_id}, {files} {_plural(files, 'file', 'files')} "
        f"({file_bytes} bytes)",
    ]
    if review.retry_of is not None:
        lines.append(f"Tries again: {review.retry_of}")
    lines += [
        f"What the model is sent: those files, word for word, inside "
        f"Techtree's planning instructions; {disclosure.prompt_bytes} bytes in "
        "all, kept beside the plan as prompt.md.",
        *(f"  {file.path}, {file.size} bytes" for file in disclosure.files),
        f"Model: {review.model.model_id} from {review.model.provider}"
        + (f", reasoning {review.model.reasoning}" if review.model.reasoning else ""),
        f"The model call goes to that provider only, on the sign-in of your "
        f"Hermes profile {PROFILE_NAME} (Hermes Agent v{review.agent.version}); "
        "Techtree copies no credential and reads none.",
        "What the planner can do: answer in text. It has no tools, so it "
        "cannot run commands, read or change files, search the web or "
        "remember anything.",
        f"Limits: one attempt, at most {limits.max_tasks} proposed "
        f"{_plural(limits.max_tasks, 'task', 'tasks')}, {limits.wall_seconds} "
        f"seconds, an answer of at most {limits.answer_bytes} bytes. Nothing "
        "is retried; trying again needs a new approval.",
        "Afterwards: the proposed tasks wait for you to review or correct. "
        "Nothing is built from them without a further approval.",
        "Cost: nothing is quoted in advance. What the call used is recorded "
        "afterwards from Hermes' own usage report.",
        f"This approval covers exactly this: {record.planning_digest[:19]}",
    ]
    return lines


def _ask_to_plan(context: CliContext, record: ForgePlanRecord) -> None:
    console = human_console(no_color=context.no_color)
    for line in planning_review_lines(record):
        console.print(line, markup=False)
    console.print()
    if not confirmed("Send this to the planner?"):
        raise PolicyError(
            "the plan was not approved, so the planner was not called",
            code=PLAN_NOT_APPROVED,
            details={"plan_id": record.plan_id},
        )


def _plan_when_approved(status: ForgePlanStatus) -> NextAction:
    """Return the start of exactly this plan, for after a person agreed."""
    return NextAction(
        operation=Operation.ACTION_EXECUTE,
        prepared_arguments=invocation(
            "forge",
            "plan-start",
            arguments=[status.plan_id],
            options={"--yes": True, "--reviewed-on": ReviewSurface.HOST_AGENT.value},
        ),
        expected_state_digest=status.record.planning_digest,
        side_effect=SideEffect.LOCAL_EXECUTION,
        approval_required=True,
        retry_class=RetryClass.HUMAN_DECISION_REQUIRED,
        estimated_cost=None,
        data_egress=DataEgress.MODEL_PROVIDER,
        reason="It sends the Skill's files to the planner once, on the "
        "person's own account. A person approves exactly the plan shown; a "
        "changed Skill, model or Hermes is refused and prepared again.",
    )


def _plan_error(status: ForgePlanStatus) -> TechtreeError | None:
    """Say why a finished attempt made no proposal, as the command's error."""
    attempt = status.attempt
    if attempt is None or status.state == "succeeded":
        return None
    if attempt.failure is not None:
        return RunError(
            f"{attempt.failure.message}. The planner is not called again; "
            f"to try again, prepare a new plan with --retry-of {status.plan_id}",
            code=attempt.failure.code,
            details={"plan_id": status.plan_id, "path": status.path},
        )
    return RunError(
        "the planner was stopped at its time limit, so the provider may or "
        "may not have answered or charged. It is not called again; to try "
        f"again, prepare a new plan with --retry-of {status.plan_id}",
        code="forge_planning_outcome_unknown",
        details={"plan_id": status.plan_id, "path": status.path},
    )


def plan_warnings(status: ForgePlanStatus) -> list[CliWarning]:
    """Say when an attempt's outcome is not known."""
    if status.state != "outcome_unknown":
        return []
    return [
        CliWarning(
            id="forge_planning_outcome_unknown",
            text=(
                "The planner call began and its end was never seen, so the "
                "provider may or may not have answered or charged. Techtree "
                "does not call it again on its own."
            ),
            resolvable_by=None,
        )
    ]


def plan_next_actions(status: ForgePlanStatus) -> list[NextAction]:
    """What can follow a plan: its proposal, or a new plan that tries again."""
    attempt = status.attempt
    if status.state == "prepared":
        return [_plan_when_approved(status)]
    if attempt is not None and attempt.proposal_id is not None:
        return [
            NextAction(
                operation=Operation.PLAN_INSPECT,
                prepared_arguments=invocation(
                    "forge", "status", arguments=[attempt.proposal_id]
                ),
                expected_state_digest=None,
                side_effect=SideEffect.NONE,
                approval_required=False,
                retry_class=RetryClass.SAFE,
                estimated_cost=None,
                data_egress=DataEgress.NONE,
                reason="The proposed tasks wait for a person's review.",
            )
        ]
    if status.state in {"rejected", "failed", "outcome_unknown"}:
        review = status.record.review
        options: dict[str, str | Literal[True]] = {
            "--provider": review.model.provider,
            "--model": review.model.model_id,
            "--tasks": str(review.limits.max_tasks),
            "--retry-of": status.plan_id,
        }
        if review.model.reasoning is not None:
            options["--reasoning"] = review.model.reasoning
        return [
            NextAction(
                operation=Operation.PLAN_PREPARE,
                prepared_arguments=invocation(
                    "forge", "plan", arguments=[review.source_id], options=options
                ),
                expected_state_digest=None,
                side_effect=SideEffect.LOCAL_STATE,
                approval_required=False,
                retry_class=RetryClass.HUMAN_DECISION_REQUIRED,
                estimated_cost=None,
                data_egress=DataEgress.NONE,
                reason="Trying again is a new plan that names this one, and it "
                "needs its own approval before the planner is called.",
            )
        ]
    return []


def render_forge_plan(status: ForgePlanStatus, console: Console) -> None:
    """Print one plan: what it covers, whether it was approved, how it went."""
    pairs = [
        ("Plan", status.plan_id),
        ("State", _PLAN_STATE_WORDS[status.state]),
    ]
    approval = status.approval
    if approval is not None:
        pairs.append(
            (
                "Approved",
                f"{approval.approved_at:%Y-%m-%d %H:%M:%S} UTC, "
                + (
                    "answered at the prompt"
                    if approval.answered_with == "prompt"
                    else f"answered on {approval.reviewed_on} and passed with --yes"
                ),
            )
        )
    attempt = status.attempt
    if attempt is not None:
        if attempt.seconds is not None:
            pairs.append(("Took", f"{attempt.seconds:.0f} seconds"))
        if attempt.stopped is not None:
            pairs.append(
                (
                    "Stopped",
                    "at its time limit"
                    if attempt.stopped == "wall_time"
                    else "with Ctrl-C",
                )
            )
        pairs.append(("Cost", _cost_words(attempt.usage)))
        if attempt.failure is not None:
            pairs.append(("Why", attempt.failure.message))
        if attempt.proposal_id is not None:
            pairs.append(("Proposal", attempt.proposal_id))
    pairs.append(("Evidence", status.path))
    render_pairs(pairs, console)
    console.print()
    for line in planning_review_lines(status.record):
        console.print(line, markup=False)


def _render_plan(data: object, console: Console) -> None:
    if isinstance(data, ForgePlanStatus):
        render_forge_plan(data, console)


def render_forge_proposal(status: ForgeProposalStatus, console: Console) -> None:
    """Print one proposal: its tasks and the checks each is graded by."""
    record = status.record
    pairs = [
        ("Proposal", status.proposal_id),
        (
            "From",
            f"the planner, plan {record.plan_id}"
            if record.parent is None
            else f"your correction of {record.parent.proposal_id}",
        ),
        ("Skill", record.source_id),
        ("Tasks", str(len(record.tasks))),
        ("Digest", record.proposal_digest[:19]),
        ("To correct", f"edit a copy of {Path(status.path) / 'tasks.json'}"),
    ]
    render_pairs(pairs, console)
    for task in record.tasks:
        console.print()
        console.print(f"{task.name}: {task.summary}", markup=False)
        for line in (
            f"Starts from: {task.scenario}",
            *(f"- {criterion}" for criterion in task.success_criteria),
            f"Checked by: {task.verifier_strategy}",
        ):
            console.print(Padding(Text(line), (0, 0, 0, 2)))


def _render_proposal(data: object, console: Console) -> None:
    if isinstance(data, ForgeProposalStatus):
        render_forge_proposal(data, console)


def proposal_status_action(status: ForgeProposalStatus) -> NextAction:
    return NextAction(
        operation=Operation.PLAN_INSPECT,
        prepared_arguments=invocation(
            "forge", "status", arguments=[status.proposal_id]
        ),
        expected_state_digest=None,
        side_effect=SideEffect.NONE,
        approval_required=False,
        retry_class=RetryClass.SAFE,
        estimated_cost=None,
        data_egress=DataEgress.NONE,
        reason="The corrected tasks can be read back and corrected again.",
    )


def _render_status(data: object, console: Console) -> None:
    if isinstance(data, ForgePlanStatus):
        render_forge_plan(data, console)
    elif isinstance(data, ForgeProposalStatus):
        render_forge_proposal(data, console)
    elif isinstance(data, ForgeSourceStatus):
        render_forge_source(data, console)
    elif isinstance(data, ForgeRunStatus):
        render_forge_run(data, console)
    elif isinstance(data, ForgeComparisonStatus):
        render_forge_comparison(data, console)
    elif isinstance(data, ForgeRevisionStatus):
        render_forge_revision(data, console)
    elif isinstance(data, ForgeBuildStatus):
        render_forge_status(data, console)


def _warnings(status: ForgeBuildStatus) -> list[CliWarning]:
    """Say when a build made nothing usable, in one line each."""
    warnings: list[CliWarning] = []
    imported = status.build is not None and status.build.source.kind == "skill"
    if status.build is not None and not status.build.task_set.tasks:
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
                    f"Every {'imported' if imported else 'generated'} task was "
                    "rejected at qualification; each task says why."
                ),
                resolvable_by=None,
            )
        )
    elif (
        status.qualification is not None
        and len(status.qualification.qualified_task_ids) < FEW_TASKS
    ):
        usable = len(status.qualification.qualified_task_ids)
        warnings.append(
            CliWarning(
                id="forge_few_tasks",
                text=(
                    f"Only {usable} {_plural(usable, 'task', 'tasks')} qualified. "
                    "A comparison on so few can say how one attempt went, not "
                    "whether a Skill helps"
                    + (
                        "."
                        if imported
                        else (
                            "; a repository with more recent bug-fix commits, or "
                            "a higher --limit, gives more."
                        )
                    )
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
