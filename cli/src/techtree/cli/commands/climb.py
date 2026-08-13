"""``techtree climb list``, ``show``, and ``prepare``. Spec 12.6 and PR6 §6.9.

No command here decides anything about a Climb. The catalog service resolves
the graph and answers whether this machine could run it; the preparation
service turns a directory into an immutable draft. These functions turn those
answers into one envelope, some warnings, and at most three next steps.

Four translations are worth naming.

A compatibility issue becomes a next action only when something runnable would
address it. An absent engine has an install command; an unsupported machine has
nothing Techtree could offer to run, so it is stated and no action is invented.

A development Climb is announced as a warning in both output modes rather than
only in the human rendering. A host agent reading JSON is exactly the caller
most likely to treat a fixture result as evidence, so the caveat travels with
the data.

``show`` returns a payload rather than a bare summary. Four facts a reader
needs before entering a Climb — which model answers, where it runs, which
reward decides the comparison, and who owns a submitted skill — have no field
on :class:`~techtree.models.catalog.ClimbSummary`, and a host agent should not
have to read them out of a rendered table.

``prepare`` returns its confirmation token exactly once, in the response, and
nothing writes it anywhere else. The start action it offers carries the draft,
the token, and the DataPolicy digest that will have to be accepted, and is
marked as requiring a person's confirmation, because starting a run commits to
both rights and work.

``start`` is where those two commitments are collected, and it keeps them
apart. The confirmation token proves that the thing being started is the thing
that was prepared. It proves nothing about consent, so acceptance of the data
policy is asked for separately: a person is shown the rights summary and has to
answer ``y``, and a program has to name the exact policy digest with
``--accept-data-policy``. Decisions document 0003 A5 is explicit that
possession of a token may never be read as agreement, and the two methods are
recorded distinguishably — ``interactive_cli`` and ``explicit_cli_digest`` — so
that a later reader of a run can tell how the acceptance was made.

The command returns as soon as the worker is launched. The run continues after
this process exits, which is the whole point, and the response says where to
look rather than waiting to find out.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Final, Literal

import typer
from rich.console import Console
from rich.table import Table

from techtree.catalog.repository import EmbeddedCatalogRepository, climb_reference
from techtree.catalog.service import (
    CatalogService,
    InstalledEngineStatus,
    current_host_info,
)
from techtree.cli.commands.run import build_run_service
from techtree.cli.context import CliContext, cli_context
from techtree.cli.invoke import CommandResult, invoke_command
from techtree.cli.output import human_console
from techtree.drafts.confirmation import ConfirmationService, utc_now
from techtree.drafts.store import DraftStore
from techtree.errors import NotFoundError, PolicyError, PrerequisiteError
from techtree.models.base import (
    Digest,
    NonEmptyString,
    ProtocolModel,
    UtcDateTime,
)
from techtree.models.campaign import ModelSpec, RuntimeSpec
from techtree.models.catalog import (
    ClimbSummary,
    CompatibilityResult,
    EngineCompatibilityStatus,
)
from techtree.models.cli import CliMessage, MessageLevel, NextAction
from techtree.models.climb import ResolvedClimb
from techtree.models.run import PolicyAcknowledgement, RunPhase, RunStatus
from techtree.models.skill import PolicyAcceptanceRequirement, SubmissionDraft
from techtree.runs.service import (
    POLICY_ACCEPTANCE_DIGEST_MISMATCH,
    POLICY_ACCEPTANCE_REQUIRED,
)
from techtree.skills.service import PreparedDraft, SkillPreparationService

__all__ = [
    "LIST_COMMAND",
    "PREPARE_COMMAND",
    "SHOW_COMMAND",
    "START_COMMAND",
    "ClimbPreparePayload",
    "ClimbShowPayload",
    "ClimbStartPayload",
    "PreparedComparison",
    "build_catalog_service",
    "build_preparation_service",
    "list_climbs_command",
    "prepare_climb_command",
    "show_climb_command",
    "start_climb_command",
]

LIST_COMMAND: Final = "climb list"
SHOW_COMMAND: Final = "climb show"
PREPARE_COMMAND: Final = "climb prepare"
START_COMMAND: Final = "climb start"

#: What a reader is told when the build ships no Climbs at all. This is the
#: normal state of a development build: the packaged catalog is valid and
#: empty until the Climb it will carry has been generated end to end.
_NO_CLIMBS = "This build does not include any Climbs yet."


class ClimbShowPayload(ProtocolModel):
    """What ``climb show`` returns: the summary, plus the Campaign facts.

    The four extra fields are read straight off the resolved graph. They are
    carried here rather than added to ``ClimbSummary`` because the summary is a
    published protocol object with an exported schema, and this is one
    command's response shape.
    """

    climb: ClimbSummary
    subject_model: ModelSpec
    subject_runtime: RuntimeSpec
    primary_reward: NonEmptyString
    candidate_skill_ownership: Literal["participant", "account", "shared"]


class PreparedComparison(ProtocolModel):
    """The controlled-comparison result, as a reader needs to check it."""

    controlled: bool
    differences: list[NonEmptyString]
    allowed_differences: list[NonEmptyString]


class ClimbPreparePayload(ProtocolModel):
    """What ``climb prepare`` returns, including the token, once."""

    draft_id: NonEmptyString
    draft_digest: Digest
    confirmation_token: NonEmptyString
    confirmation_expires_at: UtcDateTime
    climb_reference: NonEmptyString
    climb_digest: Digest
    campaign_spec_digest: Digest
    data_policy_digest: Digest
    candidate_label: NonEmptyString
    skill_root_digest: Digest
    included_files: list[NonEmptyString]
    baseline_skill_count: int
    candidate_skill_count: int
    estimated_episodes: int
    candidate_ownership: Literal["participant", "account", "shared"]
    candidate_public_release: Literal[
        "required_for_climb", "allowed", "prohibited", "consent_required"
    ]
    raw_episode_server_upload: Literal["allowed", "prohibited", "consent_required"]
    raw_episode_training_use: Literal["allowed", "prohibited", "consent_required"]
    proof_grade: Literal["development_only", "P1"]
    policy_acceptance: PolicyAcceptanceRequirement
    comparison: PreparedComparison
    warnings: list[NonEmptyString]


class ClimbStartPayload(ProtocolModel):
    """What ``climb start`` returns, as soon as the worker is running."""

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
    development_only: bool


def build_catalog_service(context: CliContext) -> CatalogService:
    """Construct the service every command reads the catalog through."""
    return CatalogService(
        EmbeddedCatalogRepository.packaged(),
        current_host_info(),
        InstalledEngineStatus(context.paths),
    )


def build_preparation_service(context: CliContext) -> SkillPreparationService:
    """Construct the service ``prepare`` builds a draft through."""
    confirmation = ConfirmationService()
    return SkillPreparationService(
        paths=context.paths,
        catalog=build_catalog_service(context),
        draft_store=DraftStore(context.paths, confirmation),
        confirmation_service=confirmation,
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

    def action() -> CommandResult[ClimbShowPayload]:
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

        return CommandResult(
            data=_show_payload(resolved, summary),
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

    invoke_command(context, SHOW_COMMAND, action, render_data=_render_show)


def prepare_climb_command(
    ctx: typer.Context,
    reference: Annotated[
        str,
        typer.Argument(
            metavar="REFERENCE",
            help="A Climb slug, slug@version, or public identifier.",
        ),
    ],
    skill: Annotated[
        Path,
        typer.Option(
            "--skill",
            metavar="PATH",
            help="The candidate skill directory, or its SKILL.md.",
        ),
    ],
    label: Annotated[
        str | None,
        typer.Option(
            "--label",
            metavar="LABEL",
            help="What to call this candidate. Defaults to the directory name.",
        ),
    ] = None,
) -> None:
    """Resolve the Climb graph and prepare one candidate skill draft."""
    context = cli_context(ctx)

    def action() -> CommandResult[ClimbPreparePayload]:
        service = build_preparation_service(context)
        try:
            prepared = service.prepare(
                climb_reference=reference,
                skill_path=skill,
                candidate_label=label,
            )
        except NotFoundError as error:
            if error.code == "climb_not_found":
                error.next_actions = _unknown_climb_actions(error)
            raise
        except PrerequisiteError as error:
            # An absent engine has a command that fixes it. An unsupported
            # machine does not, and inventing one would waste the caller's
            # time; the reason is already in the error message.
            blocking = error.details.get("blocking_issues")
            if isinstance(blocking, list) and "engine_not_installed" in blocking:
                error.next_actions = [_install_engine()]
            raise

        payload = _prepare_payload(reference, prepared)
        return CommandResult(
            data=payload,
            messages=[
                CliMessage(
                    level=MessageLevel.INFO,
                    code="draft_prepared",
                    text=(
                        f"Prepared {payload.candidate_label} for "
                        f"{payload.climb_reference}. Nothing has run yet."
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
            next_actions=[_start_draft(payload)],
        )

    invoke_command(context, PREPARE_COMMAND, action, render_data=_render_prepare)


def start_climb_command(
    ctx: typer.Context,
    draft_id: Annotated[
        str,
        typer.Argument(
            metavar="DRAFT_ID",
            help="The prepared draft to start.",
        ),
    ],
    confirmation_token: Annotated[
        str,
        typer.Option(
            "--confirmation-token",
            metavar="TOKEN",
            help="The token `techtree climb prepare` returned.",
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
    """Consume a confirmation and start a detached run."""
    context = cli_context(ctx)

    def action() -> CommandResult[ClimbStartPayload]:
        service = build_run_service(context)
        draft = DraftStore(context.paths, ConfirmationService()).get(draft_id)
        acknowledgement = _acknowledge_data_policy(
            context,
            draft=draft,
            accepted_digest=accept_data_policy,
        )

        status = service.start(
            draft_id=draft_id,
            confirmation_token=confirmation_token,
            policy_acknowledgement=acknowledgement,
        )
        payload = _start_payload(draft, status, acknowledgement)

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
            warnings=_start_warnings(payload),
            next_actions=[_watch_run(payload.run_id)],
        )

    invoke_command(context, START_COMMAND, action, render_data=_render_start)


def _acknowledge_data_policy(
    context: CliContext,
    *,
    draft: SubmissionDraft,
    accepted_digest: str | None,
) -> PolicyAcknowledgement:
    """Collect acceptance of this draft's rights policy, or refuse to start.

    A named digest is the machine spelling and is checked exactly: an
    acceptance of some other policy is not an acceptance of this one. When
    nothing was named and nobody can be asked, the command stops and says
    which digest would have to be named, because inferring consent from a
    confirmation token is the one thing decisions document 0003 A5 forbids.
    """
    required = draft.policy_acceptance
    if accepted_digest is not None:
        if accepted_digest != required.data_policy_digest:
            raise PolicyError(
                "that is not the DataPolicy this draft runs under, so it "
                "cannot be the one being accepted",
                code=POLICY_ACCEPTANCE_DIGEST_MISMATCH,
                details={
                    "draft_id": draft.id,
                    "expected_digest": required.data_policy_digest,
                    "accepted_digest": accepted_digest,
                },
            )
        return _acknowledgement(required.data_policy_digest, "explicit_cli_digest")

    if context.no_input:
        raise PolicyError(
            "starting this draft accepts its data policy, and acceptance is "
            "stated explicitly: pass --accept-data-policy "
            f"{required.data_policy_digest}",
            code=POLICY_ACCEPTANCE_REQUIRED,
            details={
                "draft_id": draft.id,
                "data_policy_digest": required.data_policy_digest,
            },
        )

    console = human_console(no_color=context.no_color)
    console.print(required.summary)
    console.print()
    if not typer.confirm(
        f"Accept DataPolicy {required.data_policy_digest}?", default=False
    ):
        raise PolicyError(
            "the data policy was not accepted, so nothing was started",
            code=POLICY_ACCEPTANCE_REQUIRED,
            details={"draft_id": draft.id},
        )
    return _acknowledgement(required.data_policy_digest, "interactive_cli")


def _acknowledgement(
    digest: Digest,
    method: Literal["interactive_cli", "explicit_cli_digest"],
) -> PolicyAcknowledgement:
    return PolicyAcknowledgement(
        data_policy_digest=digest,
        method=method,
        acknowledged_at=utc_now(),
    )


def _start_payload(
    draft: SubmissionDraft,
    status: RunStatus,
    acknowledgement: PolicyAcknowledgement,
) -> ClimbStartPayload:
    return ClimbStartPayload(
        run_id=status.state.run_id,
        draft_id=draft.id,
        phase=status.state.phase,
        worker_pid=status.state.worker_pid,
        campaign_spec_digest=draft.campaign_spec_digest,
        data_policy_digest=draft.data_policy_digest,
        policy_acknowledgement_method=acknowledgement.method,
        development_only=True,
    )


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


def _start_draft(payload: ClimbPreparePayload) -> NextAction:
    """Offer the start, carrying everything a start has to be given.

    The DataPolicy digest is spelled out because possessing the confirmation
    token has never implied accepting the rights policy — decisions document
    0003 A5 — and a machine caller has to state the acceptance explicitly.
    """
    return NextAction(
        id="start_climb",
        label=f"Start {payload.candidate_label} on {payload.climb_reference}",
        reason=(
            f"Runs {payload.estimated_episodes} episodes, baseline first. "
            "Accepting the data policy is part of starting."
        ),
        cli=[
            "techtree",
            "climb",
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


def _start_warnings(payload: ClimbStartPayload) -> list[CliMessage]:
    """Say plainly, in both output modes, what this run is going to produce."""
    if not payload.development_only:
        return []
    return [
        CliMessage(
            level=MessageLevel.WARNING,
            code="development_only_run",
            text=(
                "This run is executed by the development fake executor. No "
                "agent will be evaluated and no model will be called; the "
                "report it produces is not publication eligible."
            ),
        )
    ]


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


def _render_show(data: object, console: Console) -> None:
    """Print everything a person needs before entering a Climb."""
    if not isinstance(data, ClimbShowPayload):
        return
    summary = data.climb
    runtime = data.subject_runtime
    platforms = ", ".join(runtime.supported_platforms)

    console.print(summary.title)
    console.print(summary.summary)
    console.print()

    _print_pairs(
        console,
        [
            ("Climb", summary.reference),
            ("Status", summary.status),
            ("Campaign", summary.campaign_spec_digest),
            ("Purpose", _phrase(summary.purpose)),
            ("Taskset", f"{summary.taskset_id} ({summary.task_count} tasks)"),
            (
                "Subject harness",
                f"{summary.subject_harness} {summary.subject_harness_version}",
            ),
            (
                "Subject model",
                f"{data.subject_model.provider}/{data.subject_model.model_id}",
            ),
            ("Subject runtime", f"{runtime.type} {runtime.image} ({platforms})"),
            ("Primary reward", data.primary_reward),
            ("Candidate ownership", data.candidate_skill_ownership),
            ("Evaluated by", summary.evaluation_backend.value),
            ("Allowed change", _phrase(summary.mutation_kind)),
            ("Proof grade", _phrase(summary.proof_grade)),
        ],
    )

    console.print()
    console.print("Data rights")
    _print_pairs(
        console,
        [
            ("Candidate skills", summary.candidate_skill_visibility),
            (
                "Public release",
                _phrase(summary.data_policy.candidate_skill_public_release),
            ),
            (
                "Raw episode upload",
                _phrase(summary.data_policy.raw_episode_server_upload),
            ),
            ("Training use", _phrase(summary.data_policy.raw_episode_training_use)),
            ("Uplift report", _phrase(summary.data_policy.uplift_report_visibility)),
        ],
    )

    console.print()
    console.print("This machine")
    _print_pairs(
        console,
        [
            ("Host platform", summary.compatibility.host_platform),
            ("Engine", _phrase(summary.compatibility.engine_status.value)),
            ("Runs here", "yes" if summary.compatibility.compatible else "no"),
        ],
    )


def _render_prepare(data: object, console: Console) -> None:
    """Print everything spec PR6 §6.9 requires before a person confirms."""
    if not isinstance(data, ClimbPreparePayload):
        return

    _print_pairs(
        console,
        [
            ("Draft", data.draft_id),
            ("Climb", data.climb_reference),
            ("Climb digest", data.climb_digest),
            ("Campaign digest", data.campaign_spec_digest),
            ("DataPolicy digest", data.data_policy_digest),
            ("Candidate", data.candidate_label),
            ("Skill content digest", data.skill_root_digest),
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
            ("Allowed difference", ", ".join(data.comparison.allowed_differences)),
            ("Found difference", ", ".join(data.comparison.differences)),
            ("Baseline skills", str(data.baseline_skill_count)),
            ("Candidate skills", str(data.candidate_skill_count)),
            ("Controlled", "yes" if data.comparison.controlled else "no"),
            ("Estimated episodes", str(data.estimated_episodes)),
            ("Proof grade", _phrase(data.proof_grade)),
        ],
    )

    console.print()
    console.print("Data rights")
    _print_pairs(
        console,
        [
            ("Candidate ownership", data.candidate_ownership),
            ("Public release", _phrase(data.candidate_public_release)),
            ("Raw episode upload", _phrase(data.raw_episode_server_upload)),
            ("Training use", _phrase(data.raw_episode_training_use)),
            (
                "Acceptance",
                "required before starting"
                if data.policy_acceptance.required
                else "not required",
            ),
        ],
    )
    console.print(data.policy_acceptance.summary)

    console.print()
    console.print(
        "Confirmation expires "
        f"{data.confirmation_expires_at.isoformat().replace('+00:00', 'Z')}."
    )


def _render_start(data: object, console: Console) -> None:
    """Print what was started and where it can be followed."""
    if not isinstance(data, ClimbStartPayload):
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
            ("Accepted by", _phrase(data.policy_acknowledgement_method)),
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


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------


def _show_payload(resolved: ResolvedClimb, summary: ClimbSummary) -> ClimbShowPayload:
    """Return the summary plus the Campaign facts it has no field for."""
    subject = resolved.campaign.subject
    return ClimbShowPayload(
        climb=summary,
        subject_model=subject.model,
        subject_runtime=subject.runtime,
        primary_reward=resolved.campaign.scoring.primary_reward,
        candidate_skill_ownership=resolved.data_policy.candidate_skill.ownership,
    )


def _prepare_payload(reference: str, prepared: PreparedDraft) -> ClimbPreparePayload:
    """Project a prepared draft into the response a caller acts on."""
    draft = prepared.draft
    resolved = prepared.resolved_climb
    data_policy = resolved.data_policy
    comparison = prepared.manifest_comparison

    return ClimbPreparePayload(
        draft_id=draft.id,
        draft_digest=prepared.draft_digest,
        confirmation_token=prepared.confirmation_token,
        confirmation_expires_at=prepared.confirmation_expires_at,
        climb_reference=climb_reference(resolved.climb),
        climb_digest=resolved.climb_digest,
        campaign_spec_digest=draft.campaign_spec_digest,
        data_policy_digest=draft.data_policy_digest,
        candidate_label=draft.skill_artifact.name,
        skill_root_digest=draft.skill_artifact.root_digest,
        included_files=list(draft.included_files),
        baseline_skill_count=0,
        candidate_skill_count=1,
        estimated_episodes=draft.estimated_episodes,
        candidate_ownership=data_policy.candidate_skill.ownership,
        candidate_public_release=data_policy.candidate_skill.public_release,
        raw_episode_server_upload=data_policy.raw_episodes.server_upload,
        raw_episode_training_use=data_policy.raw_episodes.training_use,
        proof_grade=resolved.climb.publication.proof_grade,
        policy_acceptance=draft.policy_acceptance,
        comparison=PreparedComparison(
            controlled=comparison.controlled,
            differences=[difference.pointer for difference in comparison.differences],
            allowed_differences=list(comparison.allowed_differences),
        ),
        warnings=list(draft.warnings),
    )
