"""``techtree uplift context``, ``skill-source``, ``prepare``, ``start``.

Spec section 7.21. Four commands, and together they are the local half of the
improvement loop: say what a finished run showed, hand over the verified text
of the Skill it measured, set up the comparison between that Skill and a
revision of it, and start that comparison running.

``skill-source`` exists so that verification stays inside Techtree. Decisions
document 0007 R2 has a host agent read the run-owned snapshot of SKILL.md and
re-verify it; this is the surface it reads through, so nothing outside has to
compose a path into a run directory or reimplement the digest check.

What is deliberately *not* here is the revision itself. No command in this file
calls a model, asks anything to write a Skill, or reads one that a model wrote
without a person putting it there. ``uplift context`` produces the material a
host agent reasons over and stops; ``uplift prepare`` takes a directory a
person names and stops. Spec section 7.3 puts the reasoning turn in WP9+, and
the seam between the two is exactly this file's boundary.

Two things are kept as they are for public submissions, because the second run
is a real run and nothing about it is smaller.

*The rights policy is accepted again.* A second evaluation is a second use of
the participant's material, so ``uplift start`` collects approval the same way
``climb start`` does: the review of what the run would do is shown, the rights
summary is shown under it, and a person answers — or an operator who cannot be
asked passes ``--yes``. Spec section 7.20 requires it explicitly.

*The comparison is stated before it runs.* ``uplift prepare`` returns both
Skill digests, the derived Campaign digest, the estimated episodes, and the
DataPolicy digest, because that is what spec section 11.5 says a person must
see before approving a second run.

The same four verbs revise a Skill a forge experiment measured. The identifier
says which loop a call is in: a forge comparison to ``context`` and to
``prepare --from-run``, a forge run to ``skill-source``, a forge revision to
``start``. The forge half writes its context beside the comparison, keeps the
revised Skill under ``forge/revisions/<id>/``, and ``start`` runs the new arm
with the person's own Hermes and compares it against the same baseline; the
revision is kept whether it improved or regressed. What these commands answer
may be read by the agent that wrote the revision, so on a collection they
count the held-out tasks and never name them, say nothing of how the revised
Skill screened against them, and report a failure on one without saying
which; ``forge status`` shows a person everything.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated, Literal

import typer
from pydantic import Field, PositiveFloat
from rich.console import Console
from rich.table import Table

from techtree.canonical import canonical_json_bytes, digest_object
from techtree.cli.commands.climb import (
    PUBLICATION_TERMS_LINE,
    ReviewSurface,
    StartReviewPayload,
    approve_run,
    build_preparation_service,
    declared_maximum,
    phrase,
    require_the_review_surface_was_answered,
    start_review,
    start_when_approved,
    unknown_maximum,
)
from techtree.cli.commands.forge import (
    ask_to_start,
    revision_warnings,
    run_review_lines,
    run_warnings,
)
from techtree.cli.commands.run import build_run_service, wait_for_change_action
from techtree.cli.context import CliContext, cli_context
from techtree.cli.invoke import CommandResult, approval_operation, invoke_command
from techtree.cli.output import render_pairs
from techtree.drafts.store import DraftStore
from techtree.errors import RunError, TechtreeError, ValidationError
from techtree.forge.collection import (
    changed_member_files,
    read_collection_status,
    verify_collection,
)
from techtree.forge.improvement import (
    ForgeImprovementCollection,
    ForgeImprovementContext,
    ForgeImprovementRepository,
    build_forge_improvement_context,
)
from techtree.forge.models import (
    ForgeBuildTasks,
    ForgeCollectionMember,
    ForgeCollectionTasks,
    ForgeRevisionStatus,
    ForgeScreeningFinding,
    ForgeSkillSpec,
    ForgeTaskId,
)
from techtree.forge.process import run_command
from techtree.forge.revision import (
    measure_revision,
    prepare_revision,
    read_revision_status,
)
from techtree.forge.run import ForgeRunner, read_run_status
from techtree.forge.service import read_build_status
from techtree.forge.skill import SKILL_DIRNAME, read_owned_skill
from techtree.fs import atomic_write_bytes, ensure_private_directory
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
from techtree.models.run import RunPhase
from techtree.models.skill import PolicyAcceptanceRequirement
from techtree.paths import TechtreePaths
from techtree.runs.artifacts import RunArtifactStore
from techtree.runs.service import ApprovalActor
from techtree.skills.service import PreparedDraft
from techtree.uplift.context import SkillImprovementContext
from techtree.uplift.offer import revision_not_written_yet
from techtree.uplift.service import UpliftService

__all__ = [
    "ForgeRevisionReview",
    "ForgeRevisionShown",
    "ForgeUpliftContextPayload",
    "ForgeUpliftStartPayload",
    "UpliftContextPayload",
    "UpliftPreparePayload",
    "UpliftSkillSourcePayload",
    "UpliftStartPayload",
    "build_uplift_service",
    "context_uplift_command",
    "prepare_uplift_command",
    "skill_source_uplift_command",
    "start_uplift_command",
]


class UpliftContextPayload(ProtocolModel):
    """The sanitized context, and where the same bytes were written."""

    context: SkillImprovementContext
    relative_path: NonEmptyString


class ForgeUpliftContextPayload(ProtocolModel):
    """The sanitized forge context, and where the same bytes were written."""

    context: ForgeImprovementContext
    relative_path: NonEmptyString


class ForgeRevisionShown(ProtocolModel):
    """A forge revision as ``uplift`` shows it, to a caller that may be the
    agent that wrote it.

    ``task_ids`` are the tasks that agent could see: every task of a build,
    the study tasks of a collection. A collection's held-out tasks are only
    counted, and ``screening`` holds the findings on the tasks it could see
    alone; the verdict says how the revision did on the held-out tasks
    together. ``forge status`` shows a person the whole revision.
    """

    revision_id: NonEmptyString
    state: Literal["prepared", "measured"]
    skill: ForgeSkillSpec
    parent_skill_digest: Digest
    comparison_id: NonEmptyString
    baseline_run_id: NonEmptyString
    tasks_from: Annotated[
        ForgeBuildTasks | ForgeCollectionTasks, Field(discriminator="kind")
    ]
    task_ids: list[ForgeTaskId] = Field(min_length=1)
    held_out_tasks: int = Field(ge=0)
    spec_digest: Digest
    controlled: bool
    screening: list[ForgeScreeningFinding]
    measured_run_id: NonEmptyString | None
    measured_comparison_id: NonEmptyString | None
    verdict: NonEmptyString | None
    study_verdict: NonEmptyString | None


class ForgeRevisionReview(ProtocolModel):
    """What measuring a revision would do, as ``uplift start`` shows it before
    it asks; held-out tasks are counted, not named. Nothing has started."""

    revision_id: NonEmptyString
    spec_digest: Digest
    attempts: int
    review: list[NonEmptyString]


class ForgeUpliftStartPayload(ProtocolModel):
    """What measuring a forge revision left, as the revision now reads."""

    revision: ForgeRevisionShown


class UpliftSkillSourcePayload(ProtocolModel):
    """The verified text of the Skill a run measured, with its fingerprints.

    The digests are repeated beside the text on purpose. A caller that reads
    this payload has everything the improvement context pins, so it can check
    that the text it is about to send to a model belongs to the run the
    context describes without resolving anything itself.

    ``entrypoint_text`` is a plain string rather than a non-empty one. What
    makes it legitimate is that it hashes to a digest the run measured, and a
    response shape that second-guessed verified bytes would turn a Skill
    somebody really ran into an internal error rather than into an answer.
    """

    source_run_id: NonEmptyString
    skill_name: NonEmptyString
    skill_root_digest: Digest
    entrypoint_path: NonEmptyString
    entrypoint_digest: Digest
    entrypoint_size: int
    entrypoint_text: str
    file_count: int


class UpliftPreparePayload(ProtocolModel):
    """What ``uplift prepare`` returns: the draft, and what it commits to.

    It discloses what ``climb prepare`` discloses. Decisions document 0019
    section 1 makes the two comparisons the same kind of thing — one Skill
    replaced by another, one Skill added where there was none — so the screen a
    person approves the second run from states the same facts as the screen
    they approved the first from: how many Skills each side carries, and which
    data rights govern what this run produces.

    The draft's own digest is not here, for the reason it is not on
    ``climb prepare``'s payload either: the envelope's ``state_digest`` is the
    identity of the state this preparation wrote, and one value has one home.
    """

    draft_id: NonEmptyString
    source_run_id: NonEmptyString
    campaign_spec_digest: Digest
    data_policy_digest: Digest
    baseline_skill_digest: Digest
    candidate_skill_digest: Digest
    candidate_label: NonEmptyString
    included_files: list[NonEmptyString]
    baseline_skill_count: int
    candidate_skill_count: int
    estimated_episodes: int
    # Read off the Campaign this replacement was prepared against, so a caller
    # that renders a review shows the maximum this second run is held to and
    # never a figure from somewhere else. ``None`` is a Campaign that declares
    # no maximum, and says so: there is then no figure to hold it to. Decision
    # 0019 section 2 asks the same of both comparisons, and ``climb prepare``
    # already carries it for the first.
    campaign_maximum_usd: PositiveFloat | None
    candidate_ownership: Literal["participant", "account", "shared"]
    candidate_public_release: Literal[
        "required_for_climb", "allowed", "prohibited", "consent_required"
    ]
    raw_episode_server_upload: Literal["allowed", "prohibited", "consent_required"]
    raw_episode_training_use: Literal["allowed", "prohibited", "consent_required"]
    controlled: bool
    allowed_differences: list[NonEmptyString]
    differences: list[NonEmptyString]
    policy_acceptance: PolicyAcceptanceRequirement
    warnings: list[NonEmptyString]


class UpliftStartPayload(ProtocolModel):
    """What ``uplift start`` returns, as soon as the worker is running."""

    run_id: NonEmptyString
    draft_id: NonEmptyString
    draft_digest: Digest
    phase: RunPhase
    worker_pid: int | None
    campaign_spec_digest: Digest
    data_policy_digest: Digest
    policy_acknowledgement_method: Literal[
        "explicit_cli_review",
        "host_agent_confirmation",
    ]
    approved_by: ApprovalActor


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
            metavar="RUN_ID|COMPARISON_ID",
            help="The finished run, or the forge comparison, to build "
            "improvement context from.",
        ),
    ],
) -> None:
    """Export the sanitized local context for one finished run or comparison."""
    context = cli_context(ctx)

    def action() -> CommandResult[UpliftContextPayload | ForgeUpliftContextPayload]:
        if id_prefix(run_id) == "forgecmp":
            forge = build_forge_improvement_context(context.paths, run_id)
            base = context.paths.forge_comparison_dir(run_id)
            forge_path = _write_context(base, forge)
            return CommandResult(
                data=ForgeUpliftContextPayload(
                    context=forge, relative_path=forge_path.relative_to(base).as_posix()
                ),
                state_digest=digest_object(forge),
                unknowns=[revision_not_written_yet()],
                warnings=[_context_is_not_proof()],
                next_actions=[read_the_measured_skill(forge.candidate_run_id)],
            )
        improvement = build_uplift_service(context).improvement_context(run_id)
        base = context.paths.run_dir(run_id)
        path = _write_context(base, improvement)
        payload = UpliftContextPayload(
            context=improvement, relative_path=path.relative_to(base).as_posix()
        )
        return CommandResult(
            data=payload,
            # What this call wrote, by its own identity. The context is derived
            # rather than evidence and is rewritten on every call, so a caller
            # comparing two answers is comparing two real states.
            state_digest=digest_object(improvement),
            unknowns=[revision_not_written_yet()],
            warnings=[_context_is_not_proof()],
            next_actions=[read_the_measured_skill(run_id)],
        )

    invoke_command(context, Operation.PLAN_PREPARE, action, render_data=_render_context)


def _context_is_not_proof() -> CliWarning:
    return CliWarning(
        id="improvement_context_is_not_proof",
        text=(
            "This context is working material, not evidence. It is "
            "not signed, nothing verifies it, and nothing uploads it."
        ),
        resolvable_by=None,
    )


def _write_context(
    base: Path, context: SkillImprovementContext | ForgeImprovementContext
) -> Path:
    """Write the context beside what it describes, replacing any older one.

    A run can be revised from more than once, and the context is derived rather
    than evidence, so it is a file that may be rewritten — unlike everything
    the run's proof covers, which is written exactly once.
    """
    directory = base / "improvement"
    ensure_private_directory(directory)
    path = directory / "context.json"
    atomic_write_bytes(path, canonical_json_bytes(context), mode=0o600)
    return path


# ---------------------------------------------------------------------------
# skill-source
# ---------------------------------------------------------------------------


def skill_source_uplift_command(
    ctx: typer.Context,
    run_id: Annotated[
        str,
        typer.Argument(
            metavar="RUN_ID",
            help="The finished run, or the forge run, whose Skill text to read.",
        ),
    ],
) -> None:
    """Show the verified text of the Skill a finished run measured."""
    context = cli_context(ctx)

    def action() -> CommandResult[UpliftSkillSourcePayload]:
        if id_prefix(run_id) == "forgerun":
            run = read_run_status(context.paths, run_id)
            if run.spec.skill is None:
                raise ValidationError(
                    "this run carried no Skill, so there is no text to read; "
                    "name a run that carried one",
                    code="forge_run_without_skill",
                    details={"run_id": run_id},
                )
            skill = read_owned_skill(
                run.spec.skill, Path(run.path) / SKILL_DIRNAME, owner_id=run_id
            )
        else:
            skill = build_uplift_service(context).verified_source_skill(run_id)
        payload = UpliftSkillSourcePayload(
            source_run_id=skill.run_id,
            skill_name=skill.name,
            skill_root_digest=skill.root_digest,
            entrypoint_path=skill.entrypoint_path,
            entrypoint_digest=skill.entrypoint_digest,
            entrypoint_size=skill.entrypoint_size,
            entrypoint_text=skill.entrypoint_text,
            file_count=skill.file_count,
        )
        # This reads the run's own snapshot and writes nothing, so there is no
        # durable state for the envelope to name. What comes next is a person
        # writing a revision, which is why it is an unknown and not a step.
        return CommandResult(data=payload, unknowns=[revision_not_written_yet()])

    invoke_command(
        context, Operation.PLAN_INSPECT, action, render_data=_render_skill_source
    )


# ---------------------------------------------------------------------------
# prepare
# ---------------------------------------------------------------------------


def prepare_uplift_command(
    ctx: typer.Context,
    from_run: Annotated[
        str,
        typer.Option(
            "--from-run",
            metavar="RUN_ID|COMPARISON_ID",
            help="The finished run whose Skill becomes the new baseline, or "
            "the forge comparison whose candidate Skill is being revised.",
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

    def action() -> CommandResult[UpliftPreparePayload | ForgeRevisionShown]:
        if id_prefix(from_run) == "forgecmp":
            revision = prepare_revision(
                context.paths,
                comparison_id=from_run,
                skill_root=candidate_skill,
                label=label,
            )
            return CommandResult(
                data=(shown := _shown(context.paths, revision)),
                state_digest=revision.record.spec_digest,
                warnings=revision_warnings(shown.screening, held_out=False),
                next_actions=[_measure_when_approved(revision)],
            )
        prepared = build_uplift_service(context).prepare_replacement(
            source_run_id=from_run,
            candidate_skill_path=candidate_skill,
            candidate_label=label,
        )
        payload = _prepare_payload(from_run, prepared)
        return CommandResult(
            data=payload,
            state_digest=prepared.draft_digest,
            unknowns=unknown_maximum(payload.campaign_maximum_usd),
            warnings=[
                CliWarning(id="draft_warning", text=warning, resolvable_by=None)
                for warning in payload.warnings
            ],
            next_actions=[
                start_when_approved(
                    "uplift",
                    draft_id=payload.draft_id,
                    draft_digest=prepared.draft_digest,
                    estimated_cost=declared_maximum(prepared.source.campaign),
                    reason=(
                        f"It starts {payload.candidate_label} against the "
                        f"previous Skill, running {payload.estimated_episodes} "
                        "episodes. Invoke it once a person has agreed on your "
                        "own approval surface; --reviewed-on records which "
                        "surface that was."
                    ),
                )
            ],
        )

    invoke_command(context, Operation.PLAN_PREPARE, action, render_data=_render_prepare)


def _prepare_payload(
    source_run_id: str, prepared: PreparedDraft
) -> UpliftPreparePayload:
    """Project a prepared replacement draft into the response a caller acts on."""
    draft = prepared.draft
    comparison = prepared.manifest_comparison
    campaign = prepared.source.campaign
    subject = campaign.subject
    data_policy = prepared.source.data_policy
    return UpliftPreparePayload(
        draft_id=draft.id,
        source_run_id=source_run_id,
        campaign_spec_digest=draft.campaign_spec_digest,
        data_policy_digest=draft.data_policy_digest,
        baseline_skill_digest=subject.harness.skills[0].digest,
        candidate_skill_digest=draft.skill_artifact.root_digest,
        candidate_label=draft.skill_artifact.name,
        included_files=list(draft.included_files),
        baseline_skill_count=len(subject.harness.skills),
        candidate_skill_count=1,
        estimated_episodes=draft.estimated_episodes,
        campaign_maximum_usd=campaign.budgets.maximum_usd,
        candidate_ownership=data_policy.candidate_skill.ownership,
        candidate_public_release=data_policy.candidate_skill.public_release,
        raw_episode_server_upload=data_policy.raw_episodes.server_upload,
        raw_episode_training_use=data_policy.raw_episodes.training_use,
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
        typer.Argument(
            metavar="DRAFT_ID|REVISION_ID",
            help="The prepared replacement, or the forge revision, to start.",
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
    """Review the prepared revision, approve it, and start the second run."""
    context = cli_context(ctx)

    def forge_action() -> CommandResult[ForgeUpliftStartPayload | ForgeRevisionReview]:
        require_the_review_surface_was_answered(
            draft_id=draft_id, assume_yes=yes, reviewed_on=reviewed_on
        )
        return _measure(context, draft_id, assume_yes=yes)

    def action() -> CommandResult[UpliftStartPayload | StartReviewPayload]:
        service = build_run_service(context)
        store = DraftStore(context.paths)
        draft = store.get(draft_id)
        campaign = store.get_source(draft_id).campaign
        require_the_review_surface_was_answered(
            draft_id=draft_id, assume_yes=yes, reviewed_on=reviewed_on
        )
        if not yes and context.no_input:
            return start_review("uplift", draft=draft, campaign=campaign)

        approval = approve_run(
            context,
            draft=draft,
            campaign=campaign,
            assume_yes=yes,
            reviewed_on=reviewed_on,
        )
        status = service.start(
            draft_id=draft_id,
            policy_acknowledgement=approval.acknowledgement,
            approved_by=approval.actor,
        )
        request = service.request(status.state.run_id)
        payload = UpliftStartPayload(
            run_id=status.state.run_id,
            draft_id=draft.id,
            draft_digest=request.draft_digest,
            phase=status.state.phase,
            worker_pid=status.state.worker_pid,
            campaign_spec_digest=draft.campaign_spec_digest,
            data_policy_digest=draft.data_policy_digest,
            policy_acknowledgement_method=approval.acknowledgement.method,
            approved_by=approval.actor,
        )
        return CommandResult(
            data=payload,
            state_digest=service.state_digest(payload.run_id),
            next_actions=[
                wait_for_change_action(
                    payload.run_id, service.state_digest(payload.run_id)
                )
            ],
        )

    # Routed on the spelling alone, so a malformed identifier is refused inside
    # the envelope by the reader it reaches rather than before one exists.
    operation = approval_operation(context, assume_yes=yes)
    if draft_id.startswith("forgerev_"):
        invoke_command(context, operation, forge_action, render_data=_render_start)
    else:
        invoke_command(context, operation, action, render_data=_render_start)


def _measure(
    context: CliContext, revision_id: str, *, assume_yes: bool
) -> CommandResult[ForgeUpliftStartPayload | ForgeRevisionReview]:
    """Show what measuring the revision would do, ask, run it, compare it."""
    revision = read_revision_status(context.paths, revision_id)
    held_out = _held_out(context.paths, revision)
    markers = frozenset(
        marker
        for member in held_out
        for marker in (member.task_id, member.task_name, member.build_id)
    )
    match revision.spec.tasks_from:
        case ForgeBuildTasks(build_id=build_id):
            read_build_status(context.paths, build_id)
        case ForgeCollectionTasks(collection_id=collection_id):
            try:
                verify_collection(context.paths, collection_id)
            except TechtreeError as error:
                if not _names(error, markers):
                    raise
                raise _held_out_changed(
                    context.paths, collection_id, held_out
                ) from None
    shown = _shown(context.paths, revision)
    review = _revision_review(revision, shown)
    warnings = revision_warnings(shown.screening, held_out=False)
    if not assume_yes and context.no_input:
        return CommandResult(
            data=review,
            state_digest=revision.record.spec_digest,
            warnings=warnings,
            next_actions=[_measure_when_approved(revision)],
        )
    if not assume_yes:
        ask_to_start(context, review.review, review.spec_digest)
    try:
        measured = measure_revision(
            context.paths, revision_id, ForgeRunner(context.paths, run_command)
        )
    except TechtreeError as error:
        if not _names(error, markers):
            raise
        run_id = error.details.get("run_id")
        raise RunError(
            "a held-out task failed while the revised Skill was measured, so the "
            "revision was not measured. A person can see which task and why with "
            + (f"forge status {run_id}" if run_id else "forge status on the run"),
            code="forge_held_out_task_failed",
            exit_code=error.exit_code,
        ) from None
    return CommandResult(
        data=ForgeUpliftStartPayload(revision=_shown(context.paths, measured.revision)),
        warnings=[*warnings, *run_warnings(measured.run)],
        next_actions=[_next_round(measured.comparison.comparison_id)],
    )


def _names(error: TechtreeError, markers: frozenset[str]) -> bool:
    """Whether an error names a held-out task, by its id, name or build."""
    said = error.message + " " + json.dumps(error.details)
    return any(
        re.search(rf"(?<![a-z0-9_-]){re.escape(marker)}(?![a-z0-9_-])", said)
        for marker in markers
    )


def _held_out_changed(
    paths: TechtreePaths,
    collection_id: str,
    held_out: list[ForgeCollectionMember],
) -> ValidationError:
    """The error for a collection whose held-out tasks changed since it was
    accepted: how many of their files, never which."""
    changed = unreadable = 0
    for member in held_out:
        try:
            changed += len(changed_member_files(paths, member))
        except TechtreeError:
            unreadable += 1
    found = [
        *(
            (
                f"{changed} {'file' if changed == 1 else 'files'} of its held-out "
                f"tasks {'differs' if changed == 1 else 'differ'} from what was "
                "accepted",
            )
            if changed
            else ()
        ),
        *(
            (
                f"{unreadable} of its held-out "
                f"{'task' if unreadable == 1 else 'tasks'} can no longer be read",
            )
            if unreadable
            else ()
        ),
    ]
    return ValidationError(
        f"collection {collection_id} changed after its acceptance: "
        + (
            ", and ".join(found)
            if found
            else "the records of its held-out tasks differ from what was accepted"
        )
        + ", so the revision cannot be measured on it. A person can see what "
        f"changed with forge verify {collection_id}",
        code="forge_collection_changed",
        details={
            "collection_id": collection_id,
            "held_out_files_changed": changed,
            "held_out_tasks_unreadable": unreadable,
        },
    )


def _held_out(
    paths: TechtreePaths, revision: ForgeRevisionStatus
) -> list[ForgeCollectionMember]:
    """The held-out tasks of a revision's collection; none on a build."""
    match revision.record.tasks_from:
        case ForgeBuildTasks():
            return []
        case ForgeCollectionTasks(collection_id=collection_id):
            members = read_collection_status(paths, collection_id).record.review.members
            return [member for member in members if member.part == "held_out"]


def _shown(paths: TechtreePaths, revision: ForgeRevisionStatus) -> ForgeRevisionShown:
    """The revision without anything that names a held-out task."""
    record = revision.record
    held_out = {member.task_id for member in _held_out(paths, revision)}
    return ForgeRevisionShown(
        revision_id=revision.revision_id,
        state=record.state,
        skill=record.skill,
        parent_skill_digest=record.parent_skill_digest,
        comparison_id=record.comparison_id,
        baseline_run_id=record.baseline_run_id,
        tasks_from=record.tasks_from,
        task_ids=[
            task_id for task_id in revision.spec.task_ids if task_id not in held_out
        ],
        held_out_tasks=len(held_out),
        spec_digest=record.spec_digest,
        controlled=record.comparability.controlled,
        screening=[
            finding for finding in record.screening if finding.task_id not in held_out
        ],
        measured_run_id=record.measured_run_id,
        measured_comparison_id=record.measured_comparison_id,
        verdict=record.verdict,
        study_verdict=record.study_verdict,
    )


def _revision_review(
    revision: ForgeRevisionStatus, shown: ForgeRevisionShown
) -> ForgeRevisionReview:
    """The forge run review, headed by what this run is a revision of; it
    counts held-out tasks and says nothing of how they screened."""
    spec = revision.spec
    record = revision.record
    on_collection = isinstance(record.tasks_from, ForgeCollectionTasks)
    hidden = (
        "the reference answer or tests of a task the improving agent could see"
        if on_collection
        else "a task's reference answer or tests"
    )
    screening = (
        f"Screening: {len(shown.screening)} line(s) of the revised Skill also "
        f"occur in {hidden}; see the revision."
        if shown.screening
        else f"Screening: no line of the revised Skill occurs in {hidden}."
    )
    judged = (
        [
            "Every task runs, but the revision's verdict is worked out on the "
            "held-out tasks alone, which the agent that wrote it never saw."
        ]
        if on_collection
        else []
    )
    return ForgeRevisionReview(
        revision_id=revision.revision_id,
        spec_digest=record.spec_digest,
        attempts=len(spec.task_ids) * spec.sampling.repetitions,
        review=[
            f"Revision: {revision.revision_id} of Skill "
            f"{record.parent_skill_digest[:12]} measured by "
            f"{record.comparison_id}",
            *run_review_lines(
                spec, held_out=frozenset(spec.task_ids) - set(shown.task_ids)
            ),
            "Afterwards the run is compared against the same baseline, "
            f"{record.baseline_run_id}, and the revision is kept whether "
            "it improved or regressed.",
            *judged,
            screening,
        ],
    )


# ---------------------------------------------------------------------------
# Next actions
# ---------------------------------------------------------------------------


def _measure_when_approved(revision: ForgeRevisionStatus) -> NextAction:
    """Return the start a person's agreement turns into a measured revision."""
    return NextAction(
        operation=Operation.ACTION_EXECUTE,
        prepared_arguments=invocation(
            "uplift",
            "start",
            arguments=[revision.revision_id],
            options={"--yes": True, "--reviewed-on": ReviewSurface.HOST_AGENT.value},
        ),
        expected_state_digest=revision.record.spec_digest,
        side_effect=SideEffect.LOCAL_EXECUTION,
        approval_required=True,
        retry_class=RetryClass.HUMAN_DECISION_REQUIRED,
        estimated_cost=None,
        data_egress=DataEgress.MODEL_PROVIDER,
        reason=(
            f"It runs {revision.record.skill.name} on the same tasks with your "
            "own Hermes and compares it against the same baseline. A person "
            "approves the model calls it makes on their own account."
        ),
    )


def _next_round(comparison_id: str) -> NextAction:
    """Return the read that starts the next revision: what the measured run
    showed, on the tasks the improving agent may see."""
    return NextAction(
        operation=Operation.PLAN_INSPECT,
        prepared_arguments=invocation("uplift", "context", arguments=[comparison_id]),
        expected_state_digest=None,
        side_effect=SideEffect.NONE,
        approval_required=False,
        retry_class=RetryClass.SAFE,
        estimated_cost=None,
        data_egress=DataEgress.NONE,
        reason=(
            "It says what the revised Skill's run showed, which is where a "
            "further revision starts."
        ),
    )


def read_the_measured_skill(run_id: str) -> NextAction:
    """Return the read that hands over the text a revision is written from."""
    return NextAction(
        operation=Operation.PLAN_INSPECT,
        prepared_arguments=invocation("uplift", "skill-source", arguments=[run_id]),
        expected_state_digest=None,
        side_effect=SideEffect.NONE,
        approval_required=False,
        retry_class=RetryClass.SAFE,
        estimated_cost=None,
        data_egress=DataEgress.NONE,
        reason=(
            "It hands over this run's own copy of the Skill it measured, "
            "re-verified as it is read, which is the text a revision starts "
            "from."
        ),
    )


# ---------------------------------------------------------------------------
# Human rendering
# ---------------------------------------------------------------------------


def _render_context(data: object, console: Console) -> None:
    """Print a short summary and where the full context was written."""
    if isinstance(data, ForgeUpliftContextPayload):
        _render_forge_context(data, console)
        return
    if not isinstance(data, UpliftContextPayload):
        return
    improvement = data.context

    console.print(
        f"Built improvement context for {improvement.source_run_id} from "
        f"{len(improvement.examples)} of this run's tasks."
    )
    console.print()
    render_pairs(
        [
            ("Run", improvement.source_run_id),
            ("Skill being revised", improvement.parent_skill_digest),
            ("Tasks included", str(len(improvement.examples))),
            ("Written to", data.relative_path),
        ],
        console,
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


def _improvement_tasks_pair(improvement: ForgeImprovementContext) -> tuple[str, str]:
    match improvement.tasks_from:
        case ForgeImprovementRepository(repository=repository, head_commit=commit):
            return ("Repository", f"{repository} at {commit[:12]}")
        case ForgeImprovementCollection(
            collection_id=collection_id, version=version, held_out_tasks=held_out
        ):
            return (
                "Collection",
                f"{collection_id} (version {version}); {held_out} held-out "
                f"{'task' if held_out == 1 else 'tasks'} not shown",
            )


def _render_forge_context(data: ForgeUpliftContextPayload, console: Console) -> None:
    improvement = data.context
    result = improvement.current_result
    console.print(
        f"Built improvement context for {improvement.comparison_id} from "
        f"{len(improvement.examples)} of its task attempts."
    )
    console.print()
    render_pairs(
        [
            ("Comparison", improvement.comparison_id),
            _improvement_tasks_pair(improvement),
            (
                "Skill being revised",
                f"{improvement.parent_skill_name} "
                f"({improvement.parent_skill_digest[:19]})",
            ),
            (
                "Pairs",
                f"{result.wins} won, {result.losses} lost, {result.ties} tied, "
                f"{result.unresolved} unresolved of {result.pairs_planned}",
            ),
            ("Written to", data.relative_path),
        ],
        console,
    )
    console.print()
    console.print(improvement.objective)
    console.print()
    console.print("Task attempts worth looking at")
    table = Table(box=None, pad_edge=False, padding=(0, 2))
    table.add_column("Task", no_wrap=True)
    table.add_column("Result", no_wrap=True)
    table.add_column("Reward", justify="right", no_wrap=True)
    for example in improvement.examples:
        table.add_row(
            f"{example.task_id} #{example.attempt}",
            example.result.value,
            f"{example.candidate_reward:.3f}"
            if example.candidate_reward is not None
            else "none",
        )
    console.print(table)
    console.print()
    console.print("Not included")
    for item in improvement.prohibited_material:
        console.print(f"  {item}")


def _render_skill_source(data: object, console: Console) -> None:
    """Print what the text was verified against, then the text itself."""
    if not isinstance(data, UpliftSkillSourcePayload):
        return

    console.print(
        f"This is run {data.source_run_id}'s own copy of {data.entrypoint_path}, "
        "re-verified against the Skill the run measured as it was read."
    )
    console.print()
    render_pairs(
        [
            ("Run", data.source_run_id),
            ("Skill", data.skill_name),
            ("Skill content digest", data.skill_root_digest),
            ("Entry file", data.entrypoint_path),
            ("Entry file digest", data.entrypoint_digest),
            ("Files in this Skill", str(data.file_count)),
        ],
        console,
    )

    console.print()
    console.print(f"{data.entrypoint_path} ({data.entrypoint_size} bytes)")
    console.print()
    console.print(data.entrypoint_text)


def _render_prepare(data: object, console: Console) -> None:
    """Print everything a person needs before approving a second run."""
    if isinstance(data, ForgeRevisionShown):
        console.print(
            f"Prepared {data.skill.name} against the Skill comparison "
            f"{data.comparison_id} measured. Nothing has run yet."
        )
        console.print()
        _render_revision(data, console)
        return
    if not isinstance(data, UpliftPreparePayload):
        return

    console.print(
        f"Prepared {data.candidate_label} against the Skill run "
        f"{data.source_run_id} measured. Nothing has run yet."
    )
    console.print()
    render_pairs(
        [
            ("Draft", data.draft_id),
            ("From run", data.source_run_id),
            ("Campaign digest", data.campaign_spec_digest),
            ("Data policy digest", data.data_policy_digest),
            ("Baseline skill", data.baseline_skill_digest),
            ("Candidate skill", data.candidate_skill_digest),
            ("Candidate", data.candidate_label),
        ],
        console,
    )

    console.print()
    console.print(f"Included files ({len(data.included_files)})")
    for path in data.included_files:
        console.print(f"  {path}")

    console.print()
    console.print("The comparison")
    render_pairs(
        [
            ("Allowed difference", ", ".join(data.allowed_differences)),
            ("Found difference", ", ".join(data.differences)),
            ("Baseline skills", str(data.baseline_skill_count)),
            ("Candidate skills", str(data.candidate_skill_count)),
            ("Controlled", "yes" if data.controlled else "no"),
            ("Estimated episodes", str(data.estimated_episodes)),
        ],
        console,
    )

    console.print()
    console.print("Data rights")
    render_pairs(
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
        console,
    )
    console.print(data.policy_acceptance.summary)
    console.print(PUBLICATION_TERMS_LINE)


def _render_revision(revision: ForgeRevisionShown, console: Console) -> None:
    """Print a revision as the agent that wrote it may read it."""
    match revision.tasks_from:
        case ForgeBuildTasks(build_id=build_id):
            tasks_from = ("Build", build_id)
        case ForgeCollectionTasks(collection_id=collection_id, version=version):
            tasks_from = ("Collection", f"{collection_id} (version {version})")
    held_out = revision.held_out_tasks
    pairs = [
        ("Revision", revision.revision_id),
        ("State", revision.state),
        (
            "Revised Skill",
            f"{revision.skill.name} ({revision.skill.root_digest[:19]})",
        ),
        (
            "Revises",
            f"{revision.parent_skill_digest[:19]} from {revision.comparison_id}",
        ),
        ("Baseline run", revision.baseline_run_id),
        tasks_from,
        (
            "Tasks",
            ", ".join(revision.task_ids)
            + (
                f", and {held_out} held-out {'task' if held_out == 1 else 'tasks'} "
                "the improving agent never sees"
                if held_out
                else ""
            ),
        ),
        ("Controlled", "yes" if revision.controlled else "no"),
    ]
    shared = len(revision.screening)
    pairs.append(
        (
            "Screening",
            f"{shared} shared {'line' if shared == 1 else 'lines'} with hidden material"
            if shared
            else "no line shared with hidden material",
        )
    )
    if revision.measured_run_id is not None:
        pairs.append(("Measured run", revision.measured_run_id))
    if revision.measured_comparison_id is not None:
        pairs.append(("Comparison", revision.measured_comparison_id))
    render_pairs(pairs, console)
    for finding in revision.screening:
        console.print(
            f"  {finding.skill_path}:{finding.line} matches the "
            f"{finding.material.replace('_', ' ')} of {finding.task_id}: "
            f"{finding.excerpt}",
            markup=False,
        )
    if revision.verdict is not None:
        console.print()
        console.print(revision.verdict, markup=False)
    if revision.study_verdict is not None:
        console.print(revision.study_verdict, markup=False)


def _render_start(data: object, console: Console) -> None:
    """Print what was started, or what starting it would do."""
    if isinstance(data, StartReviewPayload):
        for line in data.review:
            console.print(line)
        return
    if isinstance(data, ForgeRevisionReview):
        for line in data.review:
            console.print(line, markup=False)
        console.print()
        console.print("Nothing has started. Run again with --yes to start it.")
        return
    if isinstance(data, ForgeUpliftStartPayload):
        revision = data.revision
        console.print(
            f"Revision {revision.revision_id} measured as run "
            f"{revision.measured_run_id} and compared as "
            f"{revision.measured_comparison_id}."
        )
        console.print()
        _render_revision(revision, console)
        return
    if not isinstance(data, UpliftStartPayload):
        return
    console.print(
        f"Run {data.run_id} is going. It continues whether or not this command "
        "is still open."
    )
    console.print()
    render_pairs(
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
        console,
    )
