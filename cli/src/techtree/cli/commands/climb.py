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

``prepare`` writes the draft and stops. The start action it offers names the
draft and nothing else, and is marked as requiring a person's confirmation,
because starting a run commits to both rights and work.

``start`` is where that commitment is collected. Decisions document 0019
section 2 makes it one gesture rather than two handles: the five things a
person has to weigh — how much work this is, the most the Campaign declares it
may cost, that the Skill is the only scientific change, where the model calls
go, and what is never uploaded — are printed, the rights summary is printed
under them, and the
answer is a plain ``y``. An operator who cannot be asked passes ``--yes``
instead, which is an explicit act by a person configuring a machine and never a
shortcut a model may take on somebody's behalf.

The same review can also be answered somewhere else. When the plugin starts a
draft, Hermes has already shown the review and taken the person's confirmation
through its own dispatch gate, and this command is only the thing that writes
the record; ``--reviewed-on host-agent`` is how that is said, so the run
records the surface the answer was really given on rather than the surface the
writing happened on. Either way the run records that the review was shown and
accepted, and its ``run.approved`` event records who gave the answer.

The command returns as soon as the worker is launched. The run continues after
this process exits, which is the whole point, and the response says where to
look rather than waiting to find out.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Final, Literal

import typer
from pydantic import PositiveFloat
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
from techtree.drafts.source import CampaignSource
from techtree.drafts.store import DraftStore, utc_now
from techtree.errors import (
    NotFoundError,
    PolicyError,
    PrerequisiteError,
    UsageError,
)
from techtree.models.base import (
    Digest,
    NonEmptyString,
    ProtocolModel,
)
from techtree.models.campaign import CampaignSpec, ModelSpec, RuntimeSpec
from techtree.models.catalog import (
    ClimbSummary,
    CompatibilityResult,
    EngineCompatibilityStatus,
)
from techtree.models.cli import CliMessage, MessageLevel, NextAction
from techtree.models.climb import ResolvedClimb
from techtree.models.run import (
    PolicyAcknowledgement,
    RunPhase,
    RunRequest,
    RunStatus,
)
from techtree.models.skill import PolicyAcceptanceRequirement, SubmissionDraft
from techtree.runs.service import POLICY_ACCEPTANCE_REQUIRED, ApprovalActor
from techtree.skills.service import PreparedDraft, SkillPreparationService

__all__ = [
    "LIST_COMMAND",
    "PREPARE_COMMAND",
    "REVIEW_SURFACE_NOT_APPROVED",
    "SHOW_COMMAND",
    "START_COMMAND",
    "ClimbPreparePayload",
    "ClimbShowPayload",
    "ClimbStartPayload",
    "PreparedComparison",
    "ReviewSurface",
    "RunApproval",
    "abbreviated_digest",
    "approve_run",
    "build_catalog_service",
    "build_preparation_service",
    "list_climbs_command",
    "phrase",
    "prepare_climb_command",
    "review_lines",
    "show_climb_command",
    "start_climb_command",
]

LIST_COMMAND: Final = "climb list"
SHOW_COMMAND: Final = "climb show"
PREPARE_COMMAND: Final = "climb prepare"
START_COMMAND: Final = "climb start"

#: What a reader is told when the build ships no Climbs at all. The packaged
#: catalog is generated, so an empty one means this build was assembled without
#: running the generator rather than that there is nothing to run.
_NO_CLIMBS = "This build does not include any Climbs yet."


#: What a start says when a surface was declared but nothing was approved.
REVIEW_SURFACE_NOT_APPROVED: Final = "review_surface_not_approved"


class ReviewSurface(StrEnum):
    """Where the person who approved this run answered.

    Decisions document 0019 section 2 keeps two approval surfaces: this command
    line, and the host agent's own confirmation UI. The process that writes the
    run's record is not always the process that asked the question — when the
    plugin starts a draft, Hermes asked and the CLI writes — so which surface
    it was is declared rather than inferred from the fact that a flag was used.
    """

    CLI = "cli"
    HOST_AGENT = "host-agent"


class ClimbShowPayload(ProtocolModel):
    """What ``climb show`` returns: the summary, plus the Campaign facts.

    The five extra fields are read straight off the resolved graph. They are
    carried here rather than added to ``ClimbSummary`` because the summary is a
    published protocol object with an exported schema, and this is one
    command's response shape.

    Decisions document 0007 R3 asks that a machine reader get both complete
    digests. The Campaign's is on the summary, where it has always been and
    where ``climb list`` also carries it; the DataPolicy's is here, because
    the summary describes the rights in words but never named the document
    they come from. Neither is ever abbreviated in the JSON — the shortening
    is a courtesy to a terminal, and a caller comparing digests needs all of
    both.
    """

    climb: ClimbSummary
    data_policy_digest: Digest
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
    """What ``climb prepare`` returns: the draft, and what it commits to."""

    draft_id: NonEmptyString
    draft_digest: Digest
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
    # Read off the Campaign this draft was prepared against, so a caller that
    # renders a review shows the maximum this run is held to and never a figure
    # from somewhere else. ``None`` is a Campaign that declares no maximum, and
    # says so: there is then no figure to hold it to. Decision 0019 section 2
    # puts the budget in the plugin's review the way it is already in the
    # terminal's, and a review that has to invent the number is a review that
    # would be wrong for the next Campaign.
    campaign_maximum_usd: PositiveFloat | None
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
        "explicit_cli_review",
        "host_agent_confirmation",
    ]
    approved_by: ApprovalActor
    #: Whether this run used the fake executor, and so called no model at all.
    #: It is not the Climb's proof grade: a Climb whose results may never be
    #: published is still run for real, against a real model, at real cost.
    fake_executor: bool


def build_catalog_service(context: CliContext) -> CatalogService:
    """Construct the service every command reads the catalog through."""
    return CatalogService(
        EmbeddedCatalogRepository.packaged(),
        current_host_info(),
        InstalledEngineStatus(context.paths),
    )


def build_preparation_service(context: CliContext) -> SkillPreparationService:
    """Construct the service ``prepare`` builds a draft through."""
    return SkillPreparationService(
        paths=context.paths,
        catalog=build_catalog_service(context),
        draft_store=DraftStore(context.paths),
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
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            help=(
                "Approve this run without being asked. For an operator running "
                "Techtree where nobody can answer a prompt; it is never a "
                "shortcut for an agent to take on a person's behalf."
            ),
        ),
    ] = False,
    reviewed_on: Annotated[
        ReviewSurface,
        typer.Option(
            "--reviewed-on",
            help=(
                "Where the person who approved this run answered. Pass "
                "host-agent when the review was shown in a conversation and "
                "confirmed there before the run was dispatched, so the run "
                "records the surface the answer was actually given on. Like "
                "--yes, and for the same reason, it states what a person "
                "already did and is never a shortcut a model may take."
            ),
        ),
    ] = ReviewSurface.CLI,
) -> None:
    """Review a prepared draft, approve it, and start a detached run."""
    context = cli_context(ctx)

    def action() -> CommandResult[ClimbStartPayload]:
        service = build_run_service(context)
        store = DraftStore(context.paths)
        draft = store.get(draft_id)
        source = store.get_source(draft_id)
        approval = approve_run(
            context,
            draft=draft,
            campaign=source.campaign,
            assume_yes=yes,
            reviewed_on=reviewed_on,
        )

        status = service.start(
            draft_id=draft_id,
            policy_acknowledgement=approval.acknowledgement,
            approved_by=approval.actor,
        )
        request = service.request(status.state.run_id)
        payload = _start_payload(draft, status, approval, request)

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
            warnings=_start_warnings(payload, source=source),
            next_actions=[_watch_run(payload.run_id)],
        )

    invoke_command(context, START_COMMAND, action, render_data=_render_start)


@dataclass(frozen=True)
class RunApproval:
    """The answer a start was given, and who gave it."""

    acknowledgement: PolicyAcknowledgement
    actor: ApprovalActor


#: The one scientific claim the whole comparison rests on, said in the words a
#: reader can check it in. Decisions document 0019 section 3, statement 2.
ONLY_CHANGE_LINE: Final = "The Skill is the only scientific change."

#: What Techtree keeps to itself, and what it cannot. Decision 0013 section 1.4
#: fixes both halves; they are two lines because a reader meets them as two
#: facts, and the second is what stops the first from being read as "nothing
#: leaves this machine".
NO_UPLOAD_LINE: Final = (
    "Techtree does not upload your episodes, traces, receipts, proof bundles, "
    "or Skill proposals."
)

#: What a DataPolicy's publication terms mean in this build, shown wherever
#: those terms are shown.
#:
#: A Climb's DataPolicy describes a result that has been published: it says
#: that entering requires releasing the candidate Skill and that the uplift
#: report is public. Read on its own, next to the raw-episode terms that
#: prohibit upload outright, that reads as a plan to publish somebody's Skill
#: and their numbers — and two readers stopped and refused to start a run over
#: exactly that. Nothing in this build can publish anything: there is no upload
#: path, no result is publication-eligible, and every proof is graded
#: development_only. So the terms are shown unchanged, and this is shown with
#: them.
#:
#: The last clause is not decoration. Decision 0013 section 1.4: a sentence
#: about what stays here is read as a claim that nothing goes anywhere, and
#: model calls do.
PUBLICATION_TERMS_LINE: Final = (
    "These are the terms this Climb sets for a published result. Nothing is "
    "published from this build: your Skill, the episodes and the report stay "
    "on this machine, and model calls still go to the model provider you "
    "configured."
)


def review_lines(*, draft: SubmissionDraft, campaign: CampaignSpec) -> list[str]:
    """Return the five things a person weighs before a run starts.

    Decisions document 0019 section 2 fixes the list and the order: how much
    work this is, the most the Campaign declares it may cost, what is being
    changed, where the model calls go, and what is never uploaded. Every value
    is read off the draft or the Campaign it was prepared against, so the
    review describes this run and cannot describe a different one.

    The cost line says what is actually done about the spend. Since decisions
    document 0029 there is a real check before a run starts: the most the
    comparison can cost under the Campaign's enforced per-episode limits is
    computed, and a Campaign that could amount to more than its declared
    maximum is refused instead of started. What there still is not is a meter —
    nothing counts the spend while a run is under way and nothing ends a run
    part-way through over it — so the line says what the check is, and
    decision 0025 still forbids any wording that would leave a reader expecting
    a running total or a mid-run cut-off.
    """
    return [
        f"This runs {draft.estimated_episodes} episodes: the same tasks once "
        "for each side of the comparison.",
        _cost_line(campaign),
        ONLY_CHANGE_LINE,
        f"Model calls go to {campaign.subject.model.provider}, under that "
        "provider's policies.",
        NO_UPLOAD_LINE,
    ]


def _cost_line(campaign: CampaignSpec) -> str:
    """Say what is checked about the spend before the run starts, and what is not.

    The declared maximum stays a US-dollar figure, because that is what the
    Campaign declares. What the sentence around it may not do is read as though
    everybody gets a bill: the run spends model tokens on inference, and only a
    provider that charges for tokens turns that into money.
    """
    ceiling = campaign.budgets.maximum_usd
    if ceiling is None:
        return (
            "This run spends model tokens on inference. This Campaign declares "
            "no maximum, so there is no figure for "
            "Techtree to hold it to. Each episode still has enforced turn, "
            "token, and time limits. Nothing keeps a running total while the "
            "run is under way and nothing ends it part-way through: a provider "
            "that charges for tokens bills the episodes above to your own "
            "account, and a model you run yourself sends no bill."
        )
    return (
        "This run spends model tokens on inference. Before anything starts, "
        "Techtree checks that this Campaign's enforced "
        f"per-episode limits cannot add up past the ${ceiling:.2f} maximum it "
        "declares, and refuses to run it if they could. Each "
        "episode has enforced turn, token, and time limits. Nothing keeps a "
        "running total while the run is under way and nothing ends it part-way "
        "through: a provider that charges for tokens bills the episodes above "
        "to your own account, and a model you run yourself sends no bill."
    )


def approve_run(
    context: CliContext,
    *,
    draft: SubmissionDraft,
    campaign: CampaignSpec,
    assume_yes: bool,
    reviewed_on: ReviewSurface = ReviewSurface.CLI,
) -> RunApproval:
    """Show the review, collect the answer, or refuse to start.

    Somebody who passed ``--yes`` has answered already, and ``--reviewed-on``
    says where. Otherwise a person is shown the review and the rights summary
    and answers here; where nobody can be asked, the command stops and names
    the flag rather than inventing an approval nobody gave.
    """
    if assume_yes:
        if reviewed_on is ReviewSurface.HOST_AGENT:
            return _approved(draft, "host_agent_confirmation", "human_via_hermes")
        return _approved(draft, "explicit_cli_review", "operator_via_flag")

    if reviewed_on is not ReviewSurface.CLI:
        # The answer is about to be given here, so a run that recorded it as
        # given somewhere else would name a surface nobody used.
        raise UsageError(
            "--reviewed-on says where an approval was already given, so it "
            "goes with --yes; without it the review is shown here and answered "
            "here",
            code=REVIEW_SURFACE_NOT_APPROVED,
            details={"draft_id": draft.id, "reviewed_on": reviewed_on.value},
        )

    if context.no_input:
        raise PolicyError(
            "starting this draft accepts its data policy and spends the run it "
            "describes, so somebody has to approve it. Nothing here can be "
            "asked, so say so with --yes",
            code=POLICY_ACCEPTANCE_REQUIRED,
            details={
                "draft_id": draft.id,
                "data_policy_digest": draft.policy_acceptance.data_policy_digest,
            },
        )

    console = human_console(no_color=context.no_color)
    for line in review_lines(draft=draft, campaign=campaign):
        console.print(line)
    console.print()
    console.print(draft.policy_acceptance.summary)
    console.print(PUBLICATION_TERMS_LINE)
    console.print()
    if not typer.confirm("Start this run?", default=False):
        raise PolicyError(
            "the run was not approved, so nothing was started",
            code=POLICY_ACCEPTANCE_REQUIRED,
            details={"draft_id": draft.id},
        )
    return _approved(draft, "explicit_cli_review", "human_via_cli")


def _approved(
    draft: SubmissionDraft,
    method: Literal["explicit_cli_review", "host_agent_confirmation"],
    actor: ApprovalActor,
) -> RunApproval:
    """Return the acknowledgement and the actor one approval produced."""
    return RunApproval(
        acknowledgement=PolicyAcknowledgement(
            data_policy_digest=draft.policy_acceptance.data_policy_digest,
            method=method,
            acknowledged_at=utc_now(),
        ),
        actor=actor,
    )


def _start_payload(
    draft: SubmissionDraft,
    status: RunStatus,
    approval: RunApproval,
    request: RunRequest,
) -> ClimbStartPayload:
    """Project the run that was just created, reading its own record for what it is.

    ``fake_executor`` is the run's executor and nothing else, read from the
    request the start just wrote — the same source ``run status`` answers from,
    so the two can never disagree about the same run.
    """
    return ClimbStartPayload(
        run_id=status.state.run_id,
        draft_id=draft.id,
        phase=status.state.phase,
        worker_pid=status.state.worker_pid,
        campaign_spec_digest=draft.campaign_spec_digest,
        data_policy_digest=draft.data_policy_digest,
        policy_acknowledgement_method=approval.acknowledgement.method,
        approved_by=approval.actor,
        fake_executor=request.executor_kind == "fake",
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
    """Offer the start, and say what answering it commits to.

    The action names the draft and nothing else. What the run would do is shown
    when the start is run, and answering it is what accepts the rights policy,
    so this is marked as needing a person rather than carrying anything a
    caller could pass instead of one.
    """
    return NextAction(
        id="start_climb",
        label=f"Start {payload.candidate_label} on {payload.climb_reference}",
        reason=(
            f"Runs {payload.estimated_episodes} episodes. It shows you the "
            "spending limit the Campaign declares and what this changes, and "
            "starts only if you say yes."
        ),
        cli=["techtree", "climb", "start", payload.draft_id],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=True,
    )


def _start_warnings(
    payload: ClimbStartPayload, *, source: CampaignSource
) -> list[CliMessage]:
    """Say plainly, in both output modes, what this run is going to produce.

    Two separate facts, each read off the run rather than stated here. Whether
    a model is called at all is the executor the run's own request records.
    Whether the report may be published is the Climb's proof grade. They are
    independent: the Climb this build ships is a real evaluation that is paid
    for and is still not publication eligible, and a single sentence that
    assumed one from the other is how this surface came to tell people no
    model would be called on the screen where they had just agreed to pay for
    the calls.
    """
    warnings: list[CliMessage] = []

    if payload.fake_executor:
        warnings.append(
            CliMessage(
                level=MessageLevel.WARNING,
                code="fake_executor_run",
                text=(
                    "No agent is evaluated and no model is called on this run. "
                    "The numbers in the report it produces are invented."
                ),
            )
        )
    else:
        warnings.append(
            CliMessage(
                level=MessageLevel.WARNING,
                code="paid_evaluation_run",
                text=(
                    "This run evaluates the agent for real and spends model "
                    "tokens on inference with "
                    f"{source.campaign.subject.model.provider}. If that "
                    "provider charges for tokens, what you pay is whatever it "
                    "charges; a model you run yourself sends no bill."
                ),
            )
        )

    if source.climb is not None and (
        source.climb.publication.proof_grade == "development_only"
    ):
        warnings.append(
            CliMessage(
                level=MessageLevel.WARNING,
                code="not_publication_eligible",
                text=(
                    f"{climb_reference(source.climb)} is a development Climb. "
                    "Its report is not publication eligible, and its result is "
                    "not comparable evidence."
                ),
            )
        )

    return warnings


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
            ("Purpose", phrase(summary.purpose)),
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
            ("Allowed change", phrase(summary.mutation_kind)),
            ("Proof grade", phrase(summary.proof_grade)),
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
                phrase(summary.data_policy.candidate_skill_public_release),
            ),
            (
                "Raw episode upload",
                phrase(summary.data_policy.raw_episode_server_upload),
            ),
            ("Training use", phrase(summary.data_policy.raw_episode_training_use)),
            ("Uplift report", phrase(summary.data_policy.uplift_report_visibility)),
        ],
    )
    console.print(PUBLICATION_TERMS_LINE)

    console.print()
    console.print("This machine")
    _print_pairs(
        console,
        [
            ("Host platform", summary.compatibility.host_platform),
            ("Engine", phrase(summary.compatibility.engine_status.value)),
            ("Runs here", "yes" if summary.compatibility.compatible else "no"),
        ],
    )

    console.print()
    console.print("Technical IDs")
    _print_pairs(
        console,
        [
            ("Campaign digest", abbreviated_digest(summary.campaign_spec_digest)),
            ("Data policy digest", abbreviated_digest(data.data_policy_digest)),
        ],
    )
    console.print(
        "  Shortened to fit. Run this command with --json for the complete digests."
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
            ("Data policy digest", data.data_policy_digest),
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
            ("Proof grade", phrase(data.proof_grade)),
        ],
    )

    console.print()
    console.print("Data rights")
    _print_pairs(
        console,
        [
            ("Candidate ownership", data.candidate_ownership),
            ("Public release", phrase(data.candidate_public_release)),
            ("Raw episode upload", phrase(data.raw_episode_server_upload)),
            ("Training use", phrase(data.raw_episode_training_use)),
            (
                "Acceptance",
                "required before starting"
                if data.policy_acceptance.required
                else "not required",
            ),
        ],
    )
    console.print(data.policy_acceptance.summary)
    console.print(PUBLICATION_TERMS_LINE)


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
            ("Data policy digest", data.data_policy_digest),
            ("Approved", phrase(data.policy_acknowledgement_method)),
            ("Approved by", phrase(data.approved_by)),
        ],
    )


#: How much of a digest a person is shown when the point is recognition
#: rather than comparison. Twelve hexadecimal characters distinguish every
#: object a build could plausibly hold, and the full value is one --json away.
ABBREVIATED_DIGEST_CHARACTERS: Final = 12


def abbreviated_digest(digest: str) -> str:
    """Shorten one digest for a terminal, visibly.

    Decisions document 0007 R3 puts abbreviated digests in ``climb show``'s
    human output and complete ones in its JSON. The ellipsis is what keeps
    that honest: a shortened digest that looked whole would be copied into a
    comparison and quietly fail it.
    """
    algorithm, _, hexadecimal = digest.partition(":")
    return f"{algorithm}:{hexadecimal[:ABBREVIATED_DIGEST_CHARACTERS]}…"


def phrase(value: str) -> str:
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
        data_policy_digest=resolved.data_policy_digest,
        subject_model=subject.model,
        subject_runtime=subject.runtime,
        primary_reward=resolved.campaign.scoring.primary_reward,
        candidate_skill_ownership=resolved.data_policy.candidate_skill.ownership,
    )


def _prepare_payload(reference: str, prepared: PreparedDraft) -> ClimbPreparePayload:
    """Project a prepared draft into the response a caller acts on."""
    draft = prepared.draft
    source = prepared.source
    # ``climb prepare`` only ever prepares against a public Climb; the local
    # Climb-free flow is ``uplift prepare`` and returns its own payload.
    assert source.climb is not None and source.climb_digest is not None
    data_policy = source.data_policy
    comparison = prepared.manifest_comparison

    return ClimbPreparePayload(
        draft_id=draft.id,
        draft_digest=prepared.draft_digest,
        climb_reference=climb_reference(source.climb),
        climb_digest=source.climb_digest,
        campaign_spec_digest=draft.campaign_spec_digest,
        data_policy_digest=draft.data_policy_digest,
        candidate_label=draft.skill_artifact.name,
        skill_root_digest=draft.skill_artifact.root_digest,
        included_files=list(draft.included_files),
        # Read off the Campaign rather than assumed. Decisions document 0019
        # section 1: a baseline is a role, and how many Skills it carries is
        # something the Campaign says, not something the count of a public
        # submission happens to be today.
        baseline_skill_count=len(source.campaign.subject.harness.skills),
        candidate_skill_count=1,
        estimated_episodes=draft.estimated_episodes,
        campaign_maximum_usd=source.campaign.budgets.maximum_usd,
        candidate_ownership=data_policy.candidate_skill.ownership,
        candidate_public_release=data_policy.candidate_skill.public_release,
        raw_episode_server_upload=data_policy.raw_episodes.server_upload,
        raw_episode_training_use=data_policy.raw_episodes.training_use,
        proof_grade=source.climb.publication.proof_grade,
        policy_acceptance=draft.policy_acceptance,
        comparison=PreparedComparison(
            controlled=comparison.controlled,
            differences=[difference.pointer for difference in comparison.differences],
            allowed_differences=list(comparison.allowed_differences),
        ),
        warnings=list(draft.warnings),
    )
