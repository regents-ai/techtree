"""Planning tasks from an inspected Source Skill: review, approval, one call.

``docs/plan/v0.3.0-skill-environments.md`` (U3, R21-R27, KTD3, KTD5).

A plan is prepared before anything leaves the machine. Preparing reads the
Source Skill's kept copy, checks every file still hashes to its record,
writes the exact prompt that would be sent, and records what an approval
would cover: that prompt and the files in it, the planning instructions, the
Hermes and model that would answer, where the call goes, what the planner
may do (answer in text, nothing else) and the limits (one attempt, a task
count, a wall time, an answer size). The digest of that review is the
approval.

Starting a plan makes the review again from what is on disk now. A changed
Skill copy, instruction text, Hermes, model or limit gives a different
digest, and the approval of the old one does not carry over. A plan is
started at most once: the approval is written, then the attempt is written
as ``started`` before Hermes is launched, and written again when it ends. An
attempt stopped mid-call, or left ``started`` by a process that has gone, has
an unknown outcome: the provider may or may not have answered or charged.
Nothing is retried; trying again is a new plan that names the old one.

The call is made as :mod:`techtree.forge.authoring` makes every authoring
call: Hermes one-shot, no tools, the person's ``techtree`` profile emptied to
its sign-in, in the plan's own empty workspace.

A planner answer that is a usable set of tasks becomes a proposal record and
stops there for the contributor. A contributor's correction is a new
proposal naming its parent; no proposal is ever changed.
"""

from __future__ import annotations

import json
import os
import shlex
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from pydantic import TypeAdapter
from pydantic import ValidationError as ModelValidationError

from techtree.canonical import digest_object, sha256_digest_bytes
from techtree.errors import (
    ConflictError,
    NotFoundError,
    RunError,
    TechtreeError,
    ValidationError,
)
from techtree.forge.authoring import (
    PROMPT_LIMIT,
    TEXT_ONLY_TOOLSET,
    AnsweredWith,
    Launcher,
    ReviewedOn,
    agent_spec,
    alive,
    call_failure,
    hermes_config,
    hermes_executable,
    kept_files,
    launch_one_shot,
    model_spec,
    one_shot_argv,
    run_one_shot,
    skill_text,
)
from techtree.forge.bundle import embedded_forge_root
from techtree.forge.hermes import read_usage
from techtree.forge.models import (
    FORGE_PLAN_APPROVAL_SCHEMA_VERSION,
    FORGE_PLAN_ATTEMPT_SCHEMA_VERSION,
    FORGE_PLAN_SCHEMA_VERSION,
    FORGE_PROPOSAL_SCHEMA_VERSION,
    ForgeAuthoringCapabilities,
    ForgeBuildFailure,
    ForgePlanApproval,
    ForgePlanAttempt,
    ForgePlanDisclosure,
    ForgePlanLimits,
    ForgePlanningRecipe,
    ForgePlanRecord,
    ForgePlanReview,
    ForgePlanState,
    ForgePlanStatus,
    ForgeProposalParent,
    ForgeProposalRecord,
    ForgeProposalStatus,
    ForgeProposedTask,
    proposal_content,
)
from techtree.forge.process import CommandRunner
from techtree.forge.profile import hold_profile, profile_dir, require_signed_in
from techtree.forge.source import read_source_status
from techtree.fs import atomic_write_bytes, atomic_write_json
from techtree.ids import new_id, validate_id
from techtree.models.base import Digest
from techtree.paths import TechtreePaths

__all__ = [
    "ANSWER_BYTES",
    "PLAN_WALL_SECONDS",
    "check_plan",
    "correct_proposal",
    "prepare_plan",
    "read_plan_status",
    "read_proposal_status",
    "start_plan",
]

PLAN_FILENAME: Final = "plan.json"
PROMPT_FILENAME: Final = "prompt.md"
APPROVAL_FILENAME: Final = "approval.json"
ATTEMPT_FILENAME: Final = "attempt.json"
ANSWER_FILENAME: Final = "answer.txt"
PROPOSAL_FILENAME: Final = "proposal.json"
#: The proposal's tasks alone, in the shape a correction is written in.
TASKS_FILENAME: Final = "tasks.json"

#: How long the planner may take, from launch to answer.
PLAN_WALL_SECONDS: Final = 600
#: The largest answer read as a proposal.
ANSWER_BYTES: Final = 64 * 1024
_INSTRUCTIONS: Final = "planner-prompt.md"
_TASKS_ADAPTER: Final = TypeAdapter(list[ForgeProposedTask])

# ---------------------------------------------------------------------------
# Preparing and checking
# ---------------------------------------------------------------------------


def prepare_plan(
    paths: TechtreePaths,
    *,
    source_id: str,
    provider: str,
    model_id: str,
    reasoning: str | None,
    max_tasks: int,
    retry_of: str | None,
) -> ForgePlanStatus:
    """Write the review of one planning call, sending nothing."""
    if retry_of is not None:
        _require_ended_without_proposal(paths, retry_of, source_id)
    review, prompt = _review(
        paths,
        source_id=source_id,
        executable=hermes_executable(),
        provider=provider,
        model_id=model_id,
        reasoning=reasoning,
        max_tasks=max_tasks,
        retry_of=retry_of,
    )
    plan_id = new_id("forgeplan")
    directory = paths.forge_plan_dir(plan_id)
    directory.mkdir(parents=True, mode=0o700)
    atomic_write_bytes(directory / PROMPT_FILENAME, prompt)
    record = ForgePlanRecord(
        schema_version=FORGE_PLAN_SCHEMA_VERSION,
        plan_id=plan_id,
        created_at=datetime.now(UTC),
        review=review,
        planning_digest=digest_object(review),
    )
    atomic_write_json(directory / PLAN_FILENAME, record.model_dump(mode="json"))
    return read_plan_status(paths, plan_id)


def check_plan(paths: TechtreePaths, plan_id: str) -> ForgePlanStatus:
    """Refuse a plan that was already started, or whose review has changed."""
    status = read_plan_status(paths, plan_id)
    if status.approval is not None or status.attempt is not None:
        raise ConflictError(
            f"plan {plan_id} was already sent to the planner once, and an "
            "approval covers one attempt. To try again, prepare a new plan "
            f"with --retry-of {plan_id}",
            code="forge_planning_attempted",
            details={"plan_id": plan_id, "state": status.state},
        )
    stored = status.record.review
    current, _ = _review(
        paths,
        source_id=stored.source_id,
        executable=hermes_executable(),
        provider=stored.model.provider,
        model_id=stored.model.model_id,
        reasoning=stored.model.reasoning,
        max_tasks=stored.limits.max_tasks,
        retry_of=stored.retry_of,
    )
    found = digest_object(current)
    if found != status.record.planning_digest:
        changed = [
            name
            for name in ForgePlanReview.model_fields
            if getattr(current, name) != getattr(stored, name)
        ]
        raise ValidationError(
            f"plan {plan_id} is no longer what was reviewed: "
            + ", ".join(_CHANGED_WORDS.get(name, name) for name in changed)
            + " changed since it was prepared. The planner was not called; "
            "prepare it again and review the new plan",
            code="forge_planning_stale",
            details={
                "plan_id": plan_id,
                "reviewed": status.record.planning_digest,
                "found": found,
                "changed": list(changed),
            },
        )
    return status


_CHANGED_WORDS: Final = {
    "recipe": "the planning instructions",
    "agent": "the Hermes that would answer",
    "disclosure": "what would be sent",
}


def _review(
    paths: TechtreePaths,
    *,
    source_id: str,
    executable: Path,
    provider: str,
    model_id: str,
    reasoning: str | None,
    max_tasks: int,
    retry_of: str | None,
) -> tuple[ForgePlanReview, bytes]:
    """Make the review and the prompt from what is on disk now."""
    source = read_source_status(paths, source_id)
    kept = kept_files(source, called="The planner")
    forge_root = embedded_forge_root() / "skill2env"
    instructions = (forge_root / _INSTRUCTIONS).read_bytes()
    contract = json.loads((forge_root / "contract.json").read_bytes())
    prompt = instructions.replace(b"{max_tasks}", str(max_tasks).encode()) + skill_text(
        kept
    )
    if len(prompt) > PROMPT_LIMIT:
        raise ValidationError(
            f"this Skill's files make a planning prompt of {len(prompt)} bytes, "
            f"and the planner is handed at most {PROMPT_LIMIT}; a smaller "
            "copy of the Skill is a different Skill, looked at with "
            f"forge inspect-skill --derived-from {source_id}",
            code="forge_planning_too_large",
            details={"source_id": source_id, "prompt_bytes": len(prompt)},
        )
    review = ForgePlanReview(
        source_id=source_id,
        source_digest=source.record.admitted_digest,
        retry_of=retry_of,
        recipe=ForgePlanningRecipe(
            name="skill2env-planner",
            instructions_digest=sha256_digest_bytes(instructions),
            upstream_url=contract["upstream_url"],
            upstream_revision=contract["upstream_revision"],
        ),
        agent=agent_spec(executable),
        model=model_spec(provider, model_id, reasoning),
        disclosure=ForgePlanDisclosure(
            files=[file for file, _ in kept],
            prompt_bytes=len(prompt),
            prompt_digest=sha256_digest_bytes(prompt),
        ),
        egress="model-provider",
        capabilities=ForgeAuthoringCapabilities(
            tools="none", toolset=TEXT_ONLY_TOOLSET, memory_enabled=False
        ),
        limits=ForgePlanLimits(
            max_tasks=max_tasks,
            attempts=1,
            wall_seconds=PLAN_WALL_SECONDS,
            answer_bytes=ANSWER_BYTES,
        ),
    )
    return review, prompt


def _require_ended_without_proposal(
    paths: TechtreePaths, plan_id: str, source_id: str
) -> None:
    earlier = read_plan_status(paths, plan_id)
    if earlier.record.review.source_id != source_id:
        raise ValidationError(
            f"plan {plan_id} planned Source Skill "
            f"{earlier.record.review.source_id}, not {source_id}; a retry "
            "plans the same Skill",
            code="forge_retry_other_source",
            details={"plan_id": plan_id, "source_id": source_id},
        )
    if earlier.state not in {"rejected", "failed", "outcome_unknown"}:
        raise ValidationError(
            f"plan {plan_id} is {_STATE_WORDS[earlier.state]}, so there is "
            "nothing to retry",
            code="forge_retry_not_needed",
            details={"plan_id": plan_id, "state": earlier.state},
        )


_STATE_WORDS: Final = {
    "prepared": "not yet approved",
    "running": "still running",
    "succeeded": "already answered with a proposal",
    "rejected": "rejected",
    "failed": "failed",
    "outcome_unknown": "of unknown outcome",
}


# ---------------------------------------------------------------------------
# The one planner call
# ---------------------------------------------------------------------------


def start_plan(
    paths: TechtreePaths,
    plan_id: str,
    *,
    reviewed_on: ReviewedOn,
    answered_with: AnsweredWith,
    run: CommandRunner,
    launch: Launcher = launch_one_shot,
    profiles_root: Path | None = None,
) -> ForgePlanStatus:
    """Record the approval, make the one planner call, and keep what it left."""
    review = check_plan(paths, plan_id).record.review
    profile = profile_dir(profiles_root)
    require_signed_in(
        run, Path(review.agent.executable), review.model.provider, profile
    )
    with hold_profile(profile):
        status = check_plan(paths, plan_id)
        _call(paths, status, reviewed_on, answered_with, launch, profile)
    return read_plan_status(paths, plan_id)


def _call(
    paths: TechtreePaths,
    status: ForgePlanStatus,
    reviewed_on: ReviewedOn,
    answered_with: AnsweredWith,
    launch: Launcher,
    profile: Path,
) -> None:
    plan = status.record
    review = plan.review
    directory = Path(status.path)
    now = datetime.now(UTC)
    approval = ForgePlanApproval(
        schema_version=FORGE_PLAN_APPROVAL_SCHEMA_VERSION,
        plan_id=plan.plan_id,
        planning_digest=plan.planning_digest,
        approved_at=now,
        reviewed_on=reviewed_on,
        answered_with=answered_with,
    )
    atomic_write_json(directory / APPROVAL_FILENAME, approval.model_dump(mode="json"))

    prompt = (directory / PROMPT_FILENAME).read_bytes()
    workspace = directory / "workspace"
    workspace.mkdir(mode=0o700)
    usage_file = directory / "usage.json"
    config = hermes_config(review.limits.wall_seconds)
    atomic_write_bytes(directory / "config.yaml", config)
    argv = one_shot_argv(
        review.agent,
        review.model,
        toolset=review.capabilities.toolset,
        workspace=workspace,
        usage_file=usage_file,
        prompt=prompt,
    )
    attempt = ForgePlanAttempt(
        schema_version=FORGE_PLAN_ATTEMPT_SCHEMA_VERSION,
        plan_id=plan.plan_id,
        planning_digest=plan.planning_digest,
        process_id=os.getpid(),
        started_at=now,
        updated_at=now,
        state="started",
        hermes_arguments=[*argv[1:-1], PROMPT_FILENAME],
        config_digest=sha256_digest_bytes(config),
        exit_code=None,
        stopped=None,
        seconds=None,
        usage=None,
        answer_bytes=None,
        answer_digest=None,
        proposal_id=None,
        failure=None,
    )
    attempt_file = directory / ATTEMPT_FILENAME
    atomic_write_json(attempt_file, attempt.model_dump(mode="json"))

    def finish(**update: object) -> None:
        answer = directory / ANSWER_FILENAME
        data = answer.read_bytes() if answer.is_file() else None
        ended = attempt.model_copy(
            update={
                "updated_at": datetime.now(UTC),
                "usage": read_usage(usage_file),
                "answer_bytes": None if data is None else len(data),
                "answer_digest": None if data is None else sha256_digest_bytes(data),
                **update,
            }
        )
        atomic_write_json(
            attempt_file, ForgePlanAttempt.model_validate(ended).model_dump(mode="json")
        )

    inspect = shlex.join(
        ["techtree", "--home", str(paths.root), "forge", "status", plan.plan_id]
    )
    try:
        outcome = run_one_shot(
            launch,
            argv,
            profile=profile,
            config=config,
            workspace=workspace,
            answer=directory / ANSWER_FILENAME,
            log=directory / "hermes.log",
            wall_seconds=review.limits.wall_seconds,
            keep_in=directory,
        )
    except KeyboardInterrupt as interrupt:
        finish(state="outcome_unknown", stopped="person")
        raise RunError(
            "planning was stopped with Ctrl-C while the planner was working, "
            "so the provider may or may not have answered or charged. It is "
            f"not retried. Inspect: {inspect}",
            code="forge_planning_interrupted",
            details={"plan_id": plan.plan_id, "path": str(directory)},
        ) from interrupt
    except TechtreeError as error:
        finish(
            state="failed",
            failure=ForgeBuildFailure(
                code=error.code,
                message=error.message[:512],
                error_type=type(error).__name__,
            ),
        )
        raise

    if outcome.timed_out:
        finish(
            state="outcome_unknown",
            stopped="wall_time",
            seconds=outcome.seconds,
        )
        return
    failure = call_failure(
        outcome, usage_file, code="forge_planner_failed", error_type="PlannerFailure"
    )
    if failure is not None:
        finish(
            state="failed",
            exit_code=outcome.exit_code,
            seconds=outcome.seconds,
            failure=failure,
        )
        return
    answer = (directory / ANSWER_FILENAME).read_bytes()
    try:
        tasks = _planner_tasks(answer, review.limits)
    except ValidationError as rejection:
        finish(
            state="rejected",
            exit_code=outcome.exit_code,
            seconds=outcome.seconds,
            failure=ForgeBuildFailure(
                code=rejection.code,
                message=rejection.message[:512],
                error_type="PlannerAnswer",
            ),
        )
        return
    proposal = _write_proposal(
        paths,
        source_id=review.source_id,
        source_digest=review.source_digest,
        plan_id=plan.plan_id,
        parent=None,
        tasks=tasks,
    )
    finish(
        state="succeeded",
        exit_code=outcome.exit_code,
        seconds=outcome.seconds,
        proposal_id=proposal.proposal_id,
    )


def _planner_tasks(answer: bytes, limits: ForgePlanLimits) -> list[ForgeProposedTask]:
    """Read the planner's answer as proposed tasks within the plan's limits."""
    if len(answer) > limits.answer_bytes:
        raise ValidationError(
            f"the planner's answer is {len(answer)} bytes, over the "
            f"{limits.answer_bytes} the plan allowed",
            code="forge_planner_answer_too_large",
        )
    tasks = _tasks(answer, who="the planner's answer")
    if len(tasks) > limits.max_tasks:
        raise ValidationError(
            f"the planner proposed {len(tasks)} tasks, over the "
            f"{limits.max_tasks} the plan allowed",
            code="forge_planner_too_many_tasks",
        )
    return tasks


def _tasks(data: bytes, *, who: str) -> list[ForgeProposedTask]:
    """Read ``{"tasks": [...]}`` and nothing else."""
    try:
        loaded = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise ValidationError(
            f"{who} is not one JSON object",
            code="forge_proposal_invalid",
        ) from error
    if not isinstance(loaded, dict) or set(loaded) != {"tasks"}:
        raise ValidationError(
            f'{who} is not one JSON object with "tasks" and nothing else',
            code="forge_proposal_invalid",
        )
    try:
        tasks = _TASKS_ADAPTER.validate_python(loaded["tasks"], strict=True)
    except ModelValidationError as error:
        issue = error.errors(include_input=False, include_url=False)[0]
        place = ".".join(
            f"task {item + 1}" if isinstance(item, int) else str(item)
            for item in issue["loc"]
        )
        raise ValidationError(
            f"{who} has a task that cannot be used: {place}: {issue['msg']}",
            code="forge_proposal_invalid",
        ) from error
    if not tasks:
        raise ValidationError(f"{who} proposes no task", code="forge_proposal_invalid")
    names = [task.name for task in tasks]
    if len(set(names)) != len(names):
        raise ValidationError(
            f"{who} names two tasks the same", code="forge_proposal_invalid"
        )
    return tasks


# ---------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------


def correct_proposal(
    paths: TechtreePaths, proposal_id: str, tasks_file: Path
) -> ForgeProposalStatus:
    """Record a contributor's correction as a new proposal naming its parent."""
    parent = read_proposal_status(paths, proposal_id).record
    try:
        data = tasks_file.read_bytes()
    except OSError as error:
        raise NotFoundError(
            f"cannot read {tasks_file}",
            code="forge_proposal_file_unreadable",
            details={"path": str(tasks_file)},
        ) from error
    tasks = _tasks(data, who=str(tasks_file))
    if digest_object(proposal_content(parent.source_digest, tasks)) == (
        parent.proposal_digest
    ):
        raise ValidationError(
            f"{tasks_file} proposes exactly the tasks of {proposal_id}; a "
            "correction has to change something",
            code="forge_proposal_unchanged",
            details={"proposal_id": proposal_id},
        )
    return _write_proposal(
        paths,
        source_id=parent.source_id,
        source_digest=parent.source_digest,
        plan_id=parent.plan_id,
        parent=ForgeProposalParent(
            proposal_id=parent.proposal_id, proposal_digest=parent.proposal_digest
        ),
        tasks=tasks,
    )


def _write_proposal(
    paths: TechtreePaths,
    *,
    source_id: str,
    source_digest: Digest,
    plan_id: str,
    parent: ForgeProposalParent | None,
    tasks: list[ForgeProposedTask],
) -> ForgeProposalStatus:
    proposal_id = new_id("forgeprop")
    directory = paths.forge_proposal_dir(proposal_id)
    directory.mkdir(parents=True, mode=0o700)
    record = ForgeProposalRecord(
        schema_version=FORGE_PROPOSAL_SCHEMA_VERSION,
        proposal_id=proposal_id,
        created_at=datetime.now(UTC),
        source_id=source_id,
        source_digest=source_digest,
        plan_id=plan_id,
        origin="planner" if parent is None else "contributor",
        parent=parent,
        tasks=tasks,
        proposal_digest=digest_object(proposal_content(source_digest, tasks)),
    )
    atomic_write_json(
        directory / TASKS_FILENAME,
        {"tasks": [task.model_dump(mode="json") for task in tasks]},
    )
    atomic_write_json(directory / PROPOSAL_FILENAME, record.model_dump(mode="json"))
    return ForgeProposalStatus(
        proposal_id=proposal_id, path=str(directory), record=record
    )


# ---------------------------------------------------------------------------
# Reading back
# ---------------------------------------------------------------------------


def read_plan_status(paths: TechtreePaths, plan_id: str) -> ForgePlanStatus:
    """Read a plan, its approval and its attempt back, and say where it stands."""
    directory = paths.forge_plan_dir(validate_id(plan_id, "forgeplan"))
    if not (directory / PLAN_FILENAME).is_file():
        raise NotFoundError(
            f"no prepared plan {plan_id}",
            code="forge_plan_not_found",
            details={"plan_id": plan_id, "path": str(directory)},
        )
    try:
        record = ForgePlanRecord.model_validate_json(
            (directory / PLAN_FILENAME).read_bytes()
        )
        approval = _optional(directory / APPROVAL_FILENAME, ForgePlanApproval)
        attempt = _optional(directory / ATTEMPT_FILENAME, ForgePlanAttempt)
    except ModelValidationError as error:
        issue = error.errors(include_input=False, include_url=False)[0]
        raise ValidationError(
            f"invalid plan evidence: {issue['msg']}",
            code="forge_evidence_invalid",
            details={"plan_id": plan_id, "path": str(directory)},
        ) from error
    state: ForgePlanState
    if attempt is None:
        state = "prepared"
    elif attempt.state == "started":
        state = "running" if alive(attempt.process_id) else "outcome_unknown"
    else:
        state = attempt.state
    return ForgePlanStatus(
        plan_id=plan_id,
        path=str(directory),
        state=state,
        record=record,
        approval=approval,
        attempt=attempt,
    )


def read_proposal_status(paths: TechtreePaths, proposal_id: str) -> ForgeProposalStatus:
    """Read one proposal back from its directory."""
    directory = paths.forge_proposal_dir(validate_id(proposal_id, "forgeprop"))
    record_file = directory / PROPOSAL_FILENAME
    if not record_file.is_file():
        raise NotFoundError(
            f"no recorded proposal {proposal_id}",
            code="forge_proposal_not_found",
            details={"proposal_id": proposal_id, "path": str(directory)},
        )
    try:
        record = ForgeProposalRecord.model_validate_json(record_file.read_bytes())
    except ModelValidationError as error:
        issue = error.errors(include_input=False, include_url=False)[0]
        raise ValidationError(
            f"invalid proposal evidence: {issue['msg']}",
            code="forge_evidence_invalid",
            details={"proposal_id": proposal_id, "path": str(directory)},
        ) from error
    return ForgeProposalStatus(
        proposal_id=proposal_id, path=str(directory), record=record
    )


def _optional[M: (ForgePlanApproval, ForgePlanAttempt)](
    path: Path, model: type[M]
) -> M | None:
    return model.model_validate_json(path.read_bytes()) if path.is_file() else None
