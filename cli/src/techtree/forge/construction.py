"""Building task packages from one reviewed proposal: review, approval, one pass.

``docs/plan/v0.3.0-skill-environments.md`` (U3, R24-R27, KTD3-KTD5).

A construction is prepared before anything leaves the machine. Preparing
reads the proposal and the Source Skill's kept copy and writes, for each task,
the exact prompt the creator would be sent: Techtree's building instructions,
the task as proposed, and the Skill's files. What an approval covers is
recorded beside them and bound by one digest: the proposal and the
corrections it had, those prompts, the instructions and package contract, the
Hermes and model that would answer, the Docker platform the packages are built
for, what the creator may do (answer in text, nothing else) and the limits
(one call per task, a wall time and an answer size per call).

Starting a construction makes the review again from what is on disk now; a
changed Skill copy, instruction text, Hermes, model, platform, or a new
correction of the proposal refuses the old approval. A construction is
started at most once. The pass is recorded before the first call, and each
call before it is launched and again when it ends, exactly as a planner call
is (:mod:`techtree.forge.planning`). A call that answers with a usable package
has the package written by Techtree, ``task.toml`` included from the pinned
contract as Skill2Env's host writes it, and the package goes through the same
import, build and qualification as any Skill2Env task
(:meth:`techtree.forge.service.ForgeService.import_skill`). A call that fails,
is rejected or is stopped at its time limit is kept and the pass goes on to
the next task; Ctrl-C ends the pass. Nothing is retried: trying again is a
new construction naming the old one, covering only its tasks that have no
usable package.
"""

from __future__ import annotations

import json
import os
import shlex
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, cast

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
from techtree.forge.docker import Docker
from techtree.forge.hermes import read_usage
from techtree.forge.models import (
    FORGE_CONSTRUCTION_APPROVAL_SCHEMA_VERSION,
    FORGE_CONSTRUCTION_CALL_SCHEMA_VERSION,
    FORGE_CONSTRUCTION_PACKAGE_SCHEMA_VERSION,
    FORGE_CONSTRUCTION_RUN_SCHEMA_VERSION,
    FORGE_CONSTRUCTION_SCHEMA_VERSION,
    ForgeAuthoringCapabilities,
    ForgeBuildFailure,
    ForgeBuildStatus,
    ForgeConstructionApproval,
    ForgeConstructionCall,
    ForgeConstructionCallReview,
    ForgeConstructionCallState,
    ForgeConstructionDisclosure,
    ForgeConstructionLimits,
    ForgeConstructionPackage,
    ForgeConstructionRecord,
    ForgeConstructionReview,
    ForgeConstructionRun,
    ForgeConstructionState,
    ForgeConstructionStatus,
    ForgeConstructionTaskStatus,
    ForgeCreatedPackage,
    ForgeCreatorRecipe,
    ForgePlatform,
    ForgeProposalRecord,
    ForgeProposedTask,
)
from techtree.forge.planning import read_proposal_status
from techtree.forge.process import CommandRunner
from techtree.forge.profile import hold_profile, profile_dir, require_signed_in
from techtree.forge.service import host_docker_platform
from techtree.forge.source import read_source_status
from techtree.fs import atomic_write_bytes, atomic_write_json
from techtree.ids import new_id, validate_id
from techtree.models.base import Digest
from techtree.paths import TechtreePaths

__all__ = [
    "CALL_ANSWER_BYTES",
    "CALL_WALL_SECONDS",
    "Qualifier",
    "check_construction",
    "prepare_construction",
    "read_construction_status",
    "start_construction",
]

CONSTRUCTION_FILENAME: Final = "construction.json"
APPROVAL_FILENAME: Final = "approval.json"
RUN_FILENAME: Final = "run.json"
CALL_FILENAME: Final = "call.json"
PACKAGE_FILENAME: Final = "package.json"
ANSWER_FILENAME: Final = "answer.txt"
PROMPTS_DIR: Final = "prompts"
CALLS_DIR: Final = "calls"

#: How long one creator call may take, from launch to answer.
CALL_WALL_SECONDS: Final = 900
#: The largest answer read as a package.
CALL_ANSWER_BYTES: Final = 512 * 1024
_INSTRUCTIONS: Final = "creator-prompt.md"
#: The one base image the creator is told to build from.
_BASE_IMAGE: Final = "python:3.12-slim"
#: Where a package's files may be; ``task.toml`` is Techtree's to write.
_ROOTS: Final = frozenset({"instruction.md", "environment", "tests", "solution"})

#: Admits, builds and qualifies one written package; ForgeService.import_skill.
type Qualifier = Callable[[Path, str, Digest], ForgeBuildStatus]


# ---------------------------------------------------------------------------
# Preparing and checking
# ---------------------------------------------------------------------------


def prepare_construction(
    paths: TechtreePaths,
    *,
    proposal_id: str,
    provider: str,
    model_id: str,
    reasoning: str | None,
    retry_of: str | None,
) -> ForgeConstructionStatus:
    """Write the review of one construction, sending nothing."""
    proposal = read_proposal_status(paths, proposal_id).record
    task_names = (
        [task.name for task in proposal.tasks]
        if retry_of is None
        else _unfinished_tasks(paths, retry_of, proposal_id)
    )
    construction_id = new_id("forgecon")
    review, prompts = _review(
        paths,
        construction_id=construction_id,
        proposal=proposal,
        task_names=task_names,
        executable=hermes_executable(),
        provider=provider,
        model_id=model_id,
        reasoning=reasoning,
        platform=host_docker_platform(),
        retry_of=retry_of,
    )
    directory = paths.forge_construction_dir(construction_id)
    directory.mkdir(parents=True, mode=0o700)
    (directory / PROMPTS_DIR).mkdir(mode=0o700)
    for name, prompt in prompts.items():
        atomic_write_bytes(directory / PROMPTS_DIR / f"{name}.md", prompt)
    record = ForgeConstructionRecord(
        schema_version=FORGE_CONSTRUCTION_SCHEMA_VERSION,
        construction_id=construction_id,
        created_at=datetime.now(UTC),
        review=review,
        construction_digest=digest_object(review),
    )
    atomic_write_json(directory / CONSTRUCTION_FILENAME, record.model_dump(mode="json"))
    return read_construction_status(paths, construction_id)


def check_construction(
    paths: TechtreePaths, construction_id: str
) -> ForgeConstructionStatus:
    """Refuse a construction already started, or whose review has changed."""
    status = read_construction_status(paths, construction_id)
    if status.approval is not None or status.run is not None:
        raise ConflictError(
            f"construction {construction_id} was already started once, and an "
            "approval covers one pass. To try its unfinished tasks again, "
            "prepare a new construction with --retry-of "
            f"{construction_id}",
            code="forge_construction_attempted",
            details={"construction_id": construction_id, "state": status.state},
        )
    stored = status.record.review
    current, _ = _review(
        paths,
        construction_id=construction_id,
        proposal=read_proposal_status(paths, stored.proposal_id).record,
        task_names=[call.task_name for call in stored.disclosure.calls],
        executable=hermes_executable(),
        provider=stored.model.provider,
        model_id=stored.model.model_id,
        reasoning=stored.model.reasoning,
        platform=host_docker_platform(),
        retry_of=stored.retry_of,
    )
    found = digest_object(current)
    if found != status.record.construction_digest:
        changed = [
            name
            for name in ForgeConstructionReview.model_fields
            if getattr(current, name) != getattr(stored, name)
        ]
        raise ValidationError(
            f"construction {construction_id} is no longer what was reviewed: "
            + ", ".join(_CHANGED_WORDS.get(name, name) for name in changed)
            + " changed since it was prepared. The creator was not called; "
            "prepare it again and review the new construction",
            code="forge_construction_stale",
            details={
                "construction_id": construction_id,
                "reviewed": status.record.construction_digest,
                "found": found,
                "changed": list(changed),
            },
        )
    return status


_CHANGED_WORDS: Final = {
    "corrected_by": "the proposal's corrections (it was corrected)",
    "recipe": "the building instructions",
    "agent": "the Hermes that would answer",
    "platform": "the Docker platform",
    "disclosure": "what would be sent",
}


def _review(
    paths: TechtreePaths,
    *,
    construction_id: str,
    proposal: ForgeProposalRecord,
    task_names: list[str],
    executable: Path,
    provider: str,
    model_id: str,
    reasoning: str | None,
    platform: ForgePlatform,
    retry_of: str | None,
) -> tuple[ForgeConstructionReview, dict[str, bytes]]:
    """Make the review and each call's prompt from what is on disk now."""
    source = read_source_status(paths, proposal.source_id)
    if source.record.admitted_digest != proposal.source_digest:
        raise ValidationError(
            f"proposal {proposal.proposal_id} was made from a different "
            f"record of Source Skill {proposal.source_id}",
            code="forge_evidence_invalid",
            details={"proposal_id": proposal.proposal_id},
        )
    declaration = source.record.declaration
    assert declaration is not None  # an admitted source carries its declaration
    kept = kept_files(source, called="The creator")
    forge_root = embedded_forge_root() / "skill2env"
    instructions = (forge_root / _INSTRUCTIONS).read_bytes()
    contract_bytes = (forge_root / "contract.json").read_bytes()
    contract = json.loads(contract_bytes)
    base_image = (
        f"{_BASE_IMAGE}@"
        + json.loads((forge_root / "base-images.json").read_bytes())[_BASE_IMAGE][
            "index"
        ]
    )
    tasks = {task.name: task for task in proposal.tasks}
    suffix = construction_id.split("_", 1)[1][:8]
    skill = skill_text(kept)
    prompts: dict[str, bytes] = {}
    calls: list[ForgeConstructionCallReview] = []
    for name in task_names:
        prompt = (
            instructions.replace(b"{base_image}", base_image.encode())
            + _task_text(tasks[name])
            + skill
        )
        if len(prompt) > PROMPT_LIMIT:
            raise ValidationError(
                f"task {name} and this Skill's files make a building prompt of "
                f"{len(prompt)} bytes, and the creator is handed at most "
                f"{PROMPT_LIMIT}; a smaller copy of the Skill is a different "
                "Skill, looked at with forge inspect-skill --derived-from "
                f"{proposal.source_id}",
                code="forge_construction_too_large",
                details={"task_name": name, "prompt_bytes": len(prompt)},
            )
        prompts[name] = prompt
        calls.append(
            ForgeConstructionCallReview(
                task_name=name,
                package_name=f"task_{name}_{suffix}",
                prompt_bytes=len(prompt),
                prompt_digest=sha256_digest_bytes(prompt),
            )
        )
    review = ForgeConstructionReview(
        proposal_id=proposal.proposal_id,
        proposal_digest=proposal.proposal_digest,
        corrected_by=_corrections(paths, proposal.proposal_id),
        source_id=proposal.source_id,
        source_digest=proposal.source_digest,
        source_skill=f"local/{declaration.name}",
        retry_of=retry_of,
        recipe=ForgeCreatorRecipe(
            name="skill2env-creator",
            instructions_digest=sha256_digest_bytes(instructions),
            contract_digest=sha256_digest_bytes(contract_bytes),
            base_image=base_image,
            upstream_url=contract["upstream_url"],
            upstream_revision=contract["upstream_revision"],
        ),
        agent=agent_spec(executable),
        model=model_spec(provider, model_id, reasoning),
        platform=platform,
        disclosure=ForgeConstructionDisclosure(
            files=[file for file, _ in kept], calls=calls
        ),
        egress="model-provider",
        capabilities=ForgeAuthoringCapabilities(
            tools="none", toolset=TEXT_ONLY_TOOLSET, memory_enabled=False
        ),
        limits=ForgeConstructionLimits(
            calls=len(calls),
            attempts_per_call=1,
            wall_seconds_per_call=CALL_WALL_SECONDS,
            answer_bytes_per_call=CALL_ANSWER_BYTES,
        ),
    )
    return review, prompts


def _task_text(task: ForgeProposedTask) -> bytes:
    """Return the one task, as the proposal has it, between two marker lines."""
    return (
        b"\n===== the task =====\n"
        + json.dumps(
            task.model_dump(mode="json"), indent=2, ensure_ascii=False
        ).encode()
        + b"\n===== end of the task =====\n"
    )


def _corrections(paths: TechtreePaths, proposal_id: str) -> list[str]:
    """Return the proposals made as corrections of this one, in id order."""
    directory = paths.forge_proposals_dir
    if not directory.is_dir():
        return []
    return sorted(
        child.name
        for child in directory.iterdir()
        if child.name != proposal_id
        and (parent := read_proposal_status(paths, child.name).record.parent)
        is not None
        and parent.proposal_id == proposal_id
    )


def _unfinished_tasks(
    paths: TechtreePaths, construction_id: str, proposal_id: str
) -> list[str]:
    """Return the tasks an earlier construction left without a usable package."""
    earlier = read_construction_status(paths, construction_id)
    if earlier.record.review.proposal_id != proposal_id:
        raise ValidationError(
            f"construction {construction_id} built proposal "
            f"{earlier.record.review.proposal_id}, not {proposal_id}; a retry "
            "builds the same proposal",
            code="forge_retry_other_proposal",
            details={"construction_id": construction_id, "proposal_id": proposal_id},
        )
    if earlier.state not in {"finished", "stopped"}:
        raise ValidationError(
            f"construction {construction_id} is {_STATE_WORDS[earlier.state]}, "
            "so there is nothing to retry yet",
            code="forge_retry_not_needed",
            details={"construction_id": construction_id, "state": earlier.state},
        )
    names = [
        task.task_name
        for task in earlier.tasks
        if task.package is None or task.package.usable_tasks == 0
    ]
    if not names:
        raise ValidationError(
            f"every task of construction {construction_id} has a usable "
            "package, so there is nothing to retry",
            code="forge_retry_not_needed",
            details={"construction_id": construction_id, "state": earlier.state},
        )
    return names


_STATE_WORDS: Final = {
    "prepared": "not yet approved",
    "running": "still running",
    "finished": "finished",
    "stopped": "stopped",
}


# ---------------------------------------------------------------------------
# The one pass
# ---------------------------------------------------------------------------


def start_construction(
    paths: TechtreePaths,
    construction_id: str,
    *,
    reviewed_on: ReviewedOn,
    answered_with: AnsweredWith,
    run: CommandRunner,
    qualify: Qualifier,
    launch: Launcher = launch_one_shot,
    profiles_root: Path | None = None,
) -> ForgeConstructionStatus:
    """Record the approval, call the creator once per task, and build what it made.

    Docker is asked first, so no call is made whose package could not be
    built.
    """
    review = check_construction(paths, construction_id).record.review
    Docker(run).require_daemon()
    profile = profile_dir(profiles_root)
    require_signed_in(
        run, Path(review.agent.executable), review.model.provider, profile
    )
    with hold_profile(profile):
        status = check_construction(paths, construction_id)
        _pass(paths, status, reviewed_on, answered_with, qualify, launch, profile)
    return read_construction_status(paths, construction_id)


def _pass(
    paths: TechtreePaths,
    status: ForgeConstructionStatus,
    reviewed_on: ReviewedOn,
    answered_with: AnsweredWith,
    qualify: Qualifier,
    launch: Launcher,
    profile: Path,
) -> None:
    record = status.record
    directory = Path(status.path)
    now = datetime.now(UTC)
    approval = ForgeConstructionApproval(
        schema_version=FORGE_CONSTRUCTION_APPROVAL_SCHEMA_VERSION,
        construction_id=record.construction_id,
        construction_digest=record.construction_digest,
        approved_at=now,
        reviewed_on=reviewed_on,
        answered_with=answered_with,
    )
    atomic_write_json(directory / APPROVAL_FILENAME, approval.model_dump(mode="json"))
    run = ForgeConstructionRun(
        schema_version=FORGE_CONSTRUCTION_RUN_SCHEMA_VERSION,
        construction_id=record.construction_id,
        process_id=os.getpid(),
        started_at=now,
        ended_at=None,
        stopped=None,
    )
    atomic_write_json(directory / RUN_FILENAME, run.model_dump(mode="json"))

    def end(*, stopped: bool) -> None:
        atomic_write_json(
            directory / RUN_FILENAME,
            run.model_copy(
                update={
                    "ended_at": datetime.now(UTC),
                    "stopped": "person" if stopped else None,
                }
            ).model_dump(mode="json"),
        )

    inspect = shlex.join(
        [
            "techtree",
            "--home",
            str(paths.root),
            "forge",
            "status",
            record.construction_id,
        ]
    )
    interrupted = RunError(
        "building was stopped with Ctrl-C; a call that was under way may or "
        "may not have been answered or charged, and the tasks after it were "
        f"not called. Nothing is retried. Inspect: {inspect}",
        code="forge_construction_interrupted",
        details={"construction_id": record.construction_id, "path": str(directory)},
    )
    (directory / CALLS_DIR).mkdir(mode=0o700)
    for call_review in record.review.disclosure.calls:
        call_dir = directory / CALLS_DIR / call_review.task_name
        call_dir.mkdir(mode=0o700)
        try:
            call = _call(record, call_review, call_dir, launch, profile)
            package = (
                _qualify(record, call_review, call_dir, qualify)
                if call.state == "succeeded"
                else None
            )
        except KeyboardInterrupt as interrupt:
            end(stopped=True)
            raise interrupted from interrupt
        except TechtreeError:
            end(stopped=False)
            raise
        # Ctrl-C while a package was being checked is recorded by the build.
        if (
            package is not None
            and package.failure is not None
            and package.failure.code == "forge_build_cancelled"
        ):
            end(stopped=True)
            raise interrupted
    end(stopped=False)


def _call(
    record: ForgeConstructionRecord,
    call_review: ForgeConstructionCallReview,
    call_dir: Path,
    launch: Launcher,
    profile: Path,
) -> ForgeConstructionCall:
    """Make one creator call and write its package when the answer is usable.

    Ctrl-C is raised again once the call is recorded as of unknown outcome.
    """
    review = record.review
    construction_dir = call_dir.parent.parent
    prompt = (
        construction_dir / PROMPTS_DIR / f"{call_review.task_name}.md"
    ).read_bytes()
    workspace = call_dir / "workspace"
    workspace.mkdir(mode=0o700)
    usage_file = call_dir / "usage.json"
    config = hermes_config(review.limits.wall_seconds_per_call)
    atomic_write_bytes(call_dir / "config.yaml", config)
    argv = one_shot_argv(
        review.agent,
        review.model,
        toolset=review.capabilities.toolset,
        workspace=workspace,
        usage_file=usage_file,
        prompt=prompt,
    )
    now = datetime.now(UTC)
    started = ForgeConstructionCall(
        schema_version=FORGE_CONSTRUCTION_CALL_SCHEMA_VERSION,
        construction_id=record.construction_id,
        construction_digest=record.construction_digest,
        task_name=call_review.task_name,
        process_id=os.getpid(),
        started_at=now,
        updated_at=now,
        state="started",
        hermes_arguments=[*argv[1:-1], f"{PROMPTS_DIR}/{call_review.task_name}.md"],
        config_digest=sha256_digest_bytes(config),
        exit_code=None,
        stopped=None,
        seconds=None,
        usage=None,
        answer_bytes=None,
        answer_digest=None,
        package_name=None,
        failure=None,
    )
    call_file = call_dir / CALL_FILENAME
    atomic_write_json(call_file, started.model_dump(mode="json"))

    def finish(**update: object) -> ForgeConstructionCall:
        answer = call_dir / ANSWER_FILENAME
        data = answer.read_bytes() if answer.is_file() else None
        ended = ForgeConstructionCall.model_validate(
            started.model_copy(
                update={
                    "updated_at": datetime.now(UTC),
                    "usage": read_usage(usage_file),
                    "answer_bytes": None if data is None else len(data),
                    "answer_digest": None
                    if data is None
                    else sha256_digest_bytes(data),
                    **update,
                }
            )
        )
        atomic_write_json(call_file, ended.model_dump(mode="json"))
        return ended

    try:
        outcome = run_one_shot(
            launch,
            argv,
            profile=profile,
            config=config,
            workspace=workspace,
            answer=call_dir / ANSWER_FILENAME,
            log=call_dir / "hermes.log",
            wall_seconds=review.limits.wall_seconds_per_call,
            keep_in=call_dir,
        )
    except KeyboardInterrupt:
        finish(state="outcome_unknown", stopped="person")
        raise
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
        return finish(
            state="outcome_unknown", stopped="wall_time", seconds=outcome.seconds
        )
    failure = call_failure(
        outcome, usage_file, code="forge_creator_failed", error_type="CreatorFailure"
    )
    if failure is not None:
        return finish(
            state="failed",
            exit_code=outcome.exit_code,
            seconds=outcome.seconds,
            failure=failure,
        )
    answer = (call_dir / ANSWER_FILENAME).read_bytes()
    try:
        created = _created(answer, review.limits)
    except ValidationError as rejection:
        return finish(
            state="rejected",
            exit_code=outcome.exit_code,
            seconds=outcome.seconds,
            failure=ForgeBuildFailure(
                code=rejection.code,
                message=rejection.message[:512],
                error_type="CreatorAnswer",
            ),
        )
    _write_package(call_dir / call_review.package_name, created, review, call_review)
    return finish(
        state="succeeded",
        exit_code=outcome.exit_code,
        seconds=outcome.seconds,
        package_name=call_review.package_name,
    )


def _qualify(
    record: ForgeConstructionRecord,
    call_review: ForgeConstructionCallReview,
    call_dir: Path,
    qualify: Qualifier,
) -> ForgeConstructionPackage:
    """Import, build and qualify one written package, and record where it went."""
    review = record.review
    try:
        built = qualify(
            call_dir / call_review.package_name,
            review.source_skill,
            review.source_digest,
        )
        # A returned build finished qualifying with at least one usable task.
        assert built.usable_tasks is not None
        build_id, usable, failure = built.build_id, built.usable_tasks, None
    except RunError as error:
        build = error.details.get("build_id")
        if not isinstance(build, str):
            raise
        build_id, usable = build, 0
        failure = ForgeBuildFailure(
            code=error.code,
            message=error.message[:512],
            error_type=type(error).__name__,
        )
    package = ForgeConstructionPackage(
        schema_version=FORGE_CONSTRUCTION_PACKAGE_SCHEMA_VERSION,
        construction_id=record.construction_id,
        task_name=call_review.task_name,
        package_name=call_review.package_name,
        build_id=build_id,
        usable_tasks=usable,
        failure=failure,
    )
    atomic_write_json(call_dir / PACKAGE_FILENAME, package.model_dump(mode="json"))
    return package


# ---------------------------------------------------------------------------
# The creator's answer and the package written from it
# ---------------------------------------------------------------------------


def _created(answer: bytes, limits: ForgeConstructionLimits) -> ForgeCreatedPackage:
    """Read the creator's answer as a package Techtree can write."""
    if len(answer) > limits.answer_bytes_per_call:
        raise ValidationError(
            f"the creator's answer is {len(answer)} bytes, over the "
            f"{limits.answer_bytes_per_call} the construction allowed",
            code="forge_creator_answer_too_large",
        )
    try:
        loaded = json.loads(answer.decode("utf-8"))
        # A JSON escape can spell a lone surrogate, which is not text.
        json.dumps(loaded, ensure_ascii=False).encode("utf-8")
    except (UnicodeError, ValueError) as error:
        raise ValidationError(
            "the creator's answer is not one JSON object of UTF-8 text",
            code="forge_creator_answer_invalid",
        ) from error
    try:
        created = ForgeCreatedPackage.model_validate(loaded, strict=True)
    except ModelValidationError as error:
        issue = error.errors(include_input=False, include_url=False)[0]
        place = ".".join(
            f"file {item + 1}" if isinstance(item, int) else str(item)
            for item in issue["loc"]
        )
        raise ValidationError(
            f"the creator's answer cannot be used: {place}: {issue['msg']}",
            code="forge_creator_answer_invalid",
        ) from error
    seen: set[str] = set()
    paths = {file.path for file in created.files}
    for file in created.files:
        path = file.path
        parts = path.split("/")
        if (
            "\\" in path
            or "\x00" in path
            or any(part in {"", ".", ".."} or part.startswith(".") for part in parts)
            or parts[0] not in _ROOTS
            or (parts[0] == "instruction.md") != (path == "instruction.md")
        ):
            raise ValidationError(
                f"the creator's answer has a file Techtree does not write: {path}",
                code="forge_creator_answer_invalid",
            )
        key = unicodedata.normalize("NFC", path).casefold()
        if key in seen or any(
            "/".join(parts[:end]) in paths for end in range(1, len(parts))
        ):
            raise ValidationError(
                f"the creator's answer has {path} twice, or inside a file",
                code="forge_creator_answer_invalid",
            )
        seen.add(key)
    missing = sorted(_required_files() - paths)
    if missing:
        raise ValidationError(
            "the creator's answer leaves out " + ", ".join(missing),
            code="forge_creator_answer_invalid",
        )
    return created


def _required_files() -> set[str]:
    contract = json.loads(
        (embedded_forge_root() / "skill2env" / "contract.json").read_bytes()
    )
    return set(contract["required_files"]) - {"task.toml"}


def _write_package(
    package_dir: Path,
    created: ForgeCreatedPackage,
    review: ForgeConstructionReview,
    call_review: ForgeConstructionCallReview,
) -> None:
    """Write the creator's files and Techtree's ``task.toml``, all new."""
    package_dir.mkdir(mode=0o700)
    for file in created.files:
        parts = file.path.split("/")
        for depth in range(1, len(parts)):
            (package_dir / "/".join(parts[:depth])).mkdir(mode=0o700, exist_ok=True)
        target = package_dir / file.path
        with target.open("xb") as output:
            output.write(file.text.encode("utf-8"))
        target.chmod(0o700 if file.executable else 0o600)
    contract = json.loads(
        (embedded_forge_root() / "skill2env" / "contract.json").read_bytes()
    )
    document = {
        "schema_version": contract["task_schema"],
        "artifacts": created.artifacts,
        "task": {
            "name": f"skill2env/{call_review.package_name}",
            "description": created.description,
            "keywords": created.keywords,
            "authors": [{"name": "skill2env"}],
        },
        "metadata": {
            "source_skill": review.source_skill,
            "source_bundle_digest": review.source_digest.removeprefix("sha256:"),
        },
        **contract["fixed_sections"],
    }
    with (package_dir / "task.toml").open("xb") as output:
        output.write(_toml(document).encode("utf-8"))


def _toml(document: dict[str, object]) -> str:
    """Write the few TOML shapes a ``task.toml`` has: tables, strings, numbers."""
    lines: list[str] = []
    _table_body(lines, [], document)
    return "\n".join(lines).lstrip("\n") + "\n"


def _is_table(value: object) -> bool:
    return isinstance(value, dict) or (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, dict) for item in value)
    )


def _table_body(lines: list[str], path: list[str], table: dict[str, object]) -> None:
    for key, value in table.items():
        if not _is_table(value):
            lines.append(f"{_toml_key(key)} = {_toml_value(value)}")
    for key, value in table.items():
        if not _is_table(value):
            continue
        name = ".".join(_toml_key(part) for part in [*path, key])
        items = value if isinstance(value, list) else [value]
        for item in items:
            lines.append("")
            lines.append(f"[[{name}]]" if isinstance(value, list) else f"[{name}]")
            _table_body(lines, [*path, key], cast(dict[str, object], item))


def _toml_key(key: str) -> str:
    return key if key and all(c.isalnum() or c in "_-" for c in key) else _toml_str(key)


def _toml_str(value: str) -> str:
    # A JSON string is a TOML basic string once DEL, which TOML requires
    # escaped and JSON leaves alone, is escaped too.
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007f")


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return repr(value)
    if isinstance(value, str):
        return _toml_str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(f"task.toml has no value of type {type(value).__name__}")


# ---------------------------------------------------------------------------
# Reading back
# ---------------------------------------------------------------------------


def read_construction_status(
    paths: TechtreePaths, construction_id: str
) -> ForgeConstructionStatus:
    """Read a construction and every call and package back, and say where it stands."""
    directory = paths.forge_construction_dir(validate_id(construction_id, "forgecon"))
    if not (directory / CONSTRUCTION_FILENAME).is_file():
        raise NotFoundError(
            f"no prepared construction {construction_id}",
            code="forge_construction_not_found",
            details={"construction_id": construction_id, "path": str(directory)},
        )
    try:
        record = ForgeConstructionRecord.model_validate_json(
            (directory / CONSTRUCTION_FILENAME).read_bytes()
        )
        approval = _optional(directory / APPROVAL_FILENAME, ForgeConstructionApproval)
        run = _optional(directory / RUN_FILENAME, ForgeConstructionRun)
        tasks = [
            _task_status(directory / CALLS_DIR / call.task_name, call)
            for call in record.review.disclosure.calls
        ]
    except ModelValidationError as error:
        issue = error.errors(include_input=False, include_url=False)[0]
        raise ValidationError(
            f"invalid construction evidence: {issue['msg']}",
            code="forge_evidence_invalid",
            details={"construction_id": construction_id, "path": str(directory)},
        ) from error
    state: ForgeConstructionState
    if run is None:
        state = "prepared" if approval is None else "stopped"
    elif run.ended_at is None:
        state = "running" if alive(run.process_id) else "stopped"
    else:
        state = "stopped" if run.stopped is not None else "finished"
    return ForgeConstructionStatus(
        construction_id=construction_id,
        path=str(directory),
        state=state,
        record=record,
        approval=approval,
        run=run,
        tasks=tasks,
    )


def _task_status(
    call_dir: Path, call_review: ForgeConstructionCallReview
) -> ForgeConstructionTaskStatus:
    call = _optional(call_dir / CALL_FILENAME, ForgeConstructionCall)
    state: ForgeConstructionCallState
    if call is None:
        state = "not_called"
    elif call.state == "started":
        state = "running" if alive(call.process_id) else "outcome_unknown"
    else:
        state = call.state
    return ForgeConstructionTaskStatus(
        task_name=call_review.task_name,
        package_name=call_review.package_name,
        state=state,
        call=call,
        package=_optional(call_dir / PACKAGE_FILENAME, ForgeConstructionPackage),
    )


def _optional[
    M: (
        ForgeConstructionApproval,
        ForgeConstructionRun,
        ForgeConstructionCall,
        ForgeConstructionPackage,
    )
](path: Path, model: type[M]) -> M | None:
    return model.model_validate_json(path.read_bytes()) if path.is_file() else None
