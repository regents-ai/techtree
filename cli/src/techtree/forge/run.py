"""Running one arm of a forge experiment with the person's own Hermes.

A run executes a :class:`~techtree.forge.models.ForgeRunSpec` and nothing
else: the specification was declared first, and every attempt here is what
it says. Its tasks come from a repository build, or from an accepted Skill
collection that is checked byte for byte against what a person accepted
before anything starts. Before the first attempt, every Skill task's working
directory is checked: it must hold all the task's required outputs, lie
where the sandbox does not cover it with empty folders of its own, and be
readable within the declared bounds as the image left it, so that no model
is paid for an attempt whose outputs could never be taken. For each named
task and each repetition, in order:

1. the directory the agent works in is copied out of the task image to the
   host, so the agent works in a real directory Techtree can read and grade:
   a repository task's ``/workspace`` at its base commit, a Skill task's
   working directory as its image was built, read once before the agent
   starts;
2. the person's ``techtree`` Hermes profile is emptied of everything but its
   sign-in and given a ``config.yaml`` Techtree wrote — Docker sandbox from
   the task image with that directory mounted back where it came from, no
   network, memory off, no title generation — and, on an arm that carries a
   Skill, that Skill under ``skills/<name>`` from the run's own copy;
3. the person's ``hermes`` runs one-shot in that profile, in the directory,
   with the task's instruction, the arm's Skill preloaded if it has one, and
   the task's own agent timeout as its run budget and as Techtree's deadline;
4. what the agent left is recorded before any grading: a repository task's
   workspace is diffed against the base commit inside a fresh container and
   the patch kept; a Skill task's directory is read again and every entry
   added, modified or deleted is written to a manifest, with the bytes of the
   files it left, within the bounds the specification declared
   (:mod:`techtree.forge.capture`);
5. the task's own tests grade the directory the way qualification graded the
   reference, and the reward files are read the same way. A Skill task whose
   outputs could not be taken as they are is not graded; one that is only
   missing a required output still is, and the tests decide.

On an arm that carries a Skill the run takes its own copy of it under ``skill/``
before the first attempt, once the directory it was declared from still
hashes to what the specification says; every attempt is served from that
copy, and it is what ``uplift skill-source`` reads back afterwards.

The profile is one the person made and signed in once
(:mod:`techtree.forge.profile`): Hermes keeps each profile's sign-ins to
itself, which is what lets Techtree copy no credential. The run holds the
profile from its first attempt to its last. After each attempt the profile's
transcript database is kept beside the evidence, the profile is emptied again
but for the sign-in, and the sandbox containers Hermes stopped but left on the
daemon are removed by the profile label Hermes gave them; nothing under the
profile is read but that one file.

Every outcome is its own kind: a graded attempt has a reward, and an agent
that timed out or failed, outputs that were rejected, a verifier that timed
out, or a verifier that left no readable verdict are recorded as exactly
that, never as zero.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path, PurePosixPath
from typing import Final

from pydantic import ValidationError as ModelValidationError

from techtree.canonical import canonical_json_bytes, sha256_digest_bytes
from techtree.errors import NotFoundError, RunError, TechtreeError, ValidationError
from techtree.forge.capture import capture_outputs, take_snapshot
from techtree.forge.collection import verify_collection
from techtree.forge.docker import Docker, Mount
from techtree.forge.experiment import run_spec_digest
from techtree.forge.hermes import AgentLauncher, launch_agent, read_usage
from techtree.forge.models import (
    FORGE_RUN_SCHEMA_VERSION,
    ForgeAttemptOutcome,
    ForgeAttemptRecord,
    ForgeBuildFailure,
    ForgeBuildRecord,
    ForgeBuildTasks,
    ForgeCollectionTasks,
    ForgeEvidence,
    ForgeOutputLimits,
    ForgeOutputs,
    ForgeQualification,
    ForgeRunRecord,
    ForgeRunSpec,
    ForgeRunStatus,
)
from techtree.forge.process import CommandRunner
from techtree.forge.profile import (
    PROFILE_NAME,
    hold_profile,
    profile_dir,
    require_signed_in,
    reset_profile,
)
from techtree.forge.qualify import (
    grade_task,
    read_skill_task_facts,
    read_task_facts,
)
from techtree.forge.service import read_build_status
from techtree.forge.skill import SKILL_DIRNAME, scan_skill_spec, snapshot_skill
from techtree.fs import atomic_write_bytes, atomic_write_json
from techtree.ids import new_id, validate_id
from techtree.models.base import Digest, JsonValue
from techtree.paths import TechtreePaths

__all__ = [
    "AGENT_MARGIN_SECONDS",
    "ForgeRunner",
    "hermes_config",
    "read_run_status",
]

_SPEC_FILENAME: Final = "spec.json"
_RUN_FILENAME: Final = "run.json"
#: Added to the task's agent timeout before Techtree stops Hermes itself;
#: Hermes is given the timeout as its own budget and should stop first.
AGENT_MARGIN_SECONDS: Final = 120.0
_PATCH_TIMEOUT_SECONDS: Final = 120.0
_WORKSPACE: Final = "/workspace"
_STATE_DB: Final = "state.db"
_PROFILE_LABEL: Final = "hermes-profile"


@dataclass(frozen=True)
class _TaskOutputs:
    """A Skill task's required outputs, and the bounds its capture keeps to."""

    artifacts: tuple[str, ...]
    limits: ForgeOutputLimits


@dataclass(frozen=True)
class _RunTask:
    """One task a run names, read once before the first attempt.

    ``outputs`` is set for a Skill task, whose outputs are captured; a
    repository task leaves a patch instead.
    """

    task_id: str
    build: ForgeBuildRecord
    image: str
    task_dir: Path
    agent_timeout: float
    verifier_timeout: float
    outputs: _TaskOutputs | None


def hermes_config(
    spec: ForgeRunSpec,
    image: str,
    agent_timeout: float,
    workspace: Path,
    directory: str,
) -> bytes:
    """Return the ``config.yaml`` Techtree writes for one attempt, as bytes.

    The exported ``workspace`` is mounted back at ``directory``, where it was
    copied from, as an explicit volume and the shell starts there: Hermes
    binds its own working directory only for a shared container, and the
    sandbox here is per session. JSON is YAML, and the canonical encoder is
    what makes the digest of this file the fact the evidence records.
    """
    return canonical_json_bytes(
        {
            "terminal": {
                "backend": "docker",
                "docker_image": image,
                "docker_volumes": [f"{workspace}:{directory}"],
                "cwd": directory,
                "docker_network": spec.limits.network,
                "container_persistent": False,
                "docker_persist_across_processes": False,
                "docker_orphan_reaper": False,
                "container_cpu": spec.limits.container_cpus,
                "container_memory": spec.limits.container_memory_mb,
            },
            "memory": {
                "memory_enabled": spec.initial_state.memory_enabled,
                "user_profile_enabled": False,
            },
            "agent": {"run_budget_seconds": agent_timeout},
            "auxiliary": {"title_generation": {"enabled": False}},
            "skills": {"external_dirs": []},
        }
    )


class ForgeRunner:
    """Executes run specifications in one Techtree home."""

    def __init__(
        self,
        paths: TechtreePaths,
        run: CommandRunner,
        *,
        launch: AgentLauncher = launch_agent,
        profiles_root: Path | None = None,
    ) -> None:
        self._paths = paths
        self._run = run
        self._docker = Docker(run)
        self._launch = launch
        self._profile = profile_dir(profiles_root)

    def run(self, spec: ForgeRunSpec, skill_root: Path | None) -> ForgeRunStatus:
        """Execute every attempt the specification names and record each one."""
        skill_files = self._skill_files(spec, skill_root)
        match spec.tasks_from:
            case ForgeBuildTasks() as tasks_from:
                tasks = self._build_tasks(spec, tasks_from)
            case ForgeCollectionTasks() as tasks_from:
                tasks = self._collection_tasks(spec, tasks_from)
        with hold_profile(self._profile):
            return self._recorded_run(spec, skill_files, tasks)

    def _build_tasks(
        self, spec: ForgeRunSpec, tasks_from: ForgeBuildTasks
    ) -> list[_RunTask]:
        """Read a repository build's named tasks, once it is still as declared."""
        status = read_build_status(self._paths, tasks_from.build_id)
        if status.build is not None:
            status.build.require_repository_source("A run on a build")
        if status.build is None or status.qualification is None:
            raise RunError(
                f"build {tasks_from.build_id} no longer has a complete record",
                code="forge_build_not_qualified",
                details={"build_id": tasks_from.build_id},
            )
        build, qualification = status.build, status.qualification
        self._require_signed_in(spec)
        if qualification.membership_digest != tasks_from.membership_digest:
            raise ValidationError(
                "the build's tasks are not the ones the specification was declared on",
                code="forge_membership_mismatch",
                details={
                    "build_id": tasks_from.build_id,
                    "declared": tasks_from.membership_digest,
                    "stored": qualification.membership_digest,
                },
            )
        tasks = []
        for task_id in spec.task_ids:
            task_dir = self._paths.forge_build_dir(build.build_id) / "tasks" / task_id
            facts = read_task_facts(task_dir)
            tasks.append(
                _RunTask(
                    task_id=task_id,
                    build=build,
                    image=_image(qualification, task_id),
                    task_dir=task_dir,
                    agent_timeout=facts.agent_timeout,
                    verifier_timeout=facts.verifier_timeout,
                    outputs=None,
                )
            )
        return tasks

    def _collection_tasks(
        self, spec: ForgeRunSpec, tasks_from: ForgeCollectionTasks
    ) -> list[_RunTask]:
        """Read an accepted collection's named tasks, once it is still as accepted.

        The collection is verified byte for byte against its acceptance, and
        must be the very version the specification was declared on.
        """
        status = verify_collection(self._paths, tasks_from.collection_id)
        self._require_signed_in(spec)
        if status.record.collection_digest != tasks_from.collection_digest:
            raise ValidationError(
                "the collection is not the one the specification was declared on",
                code="forge_membership_mismatch",
                details={
                    "collection_id": tasks_from.collection_id,
                    "declared": tasks_from.collection_digest,
                    "stored": status.record.collection_digest,
                },
            )
        limits = spec.limits.outputs
        # The specification's own validator pairs a collection with its limits.
        assert limits is not None
        members = {member.task_id: member for member in status.record.review.members}
        tasks = []
        for task_id in spec.task_ids:
            member = members[task_id]
            built = read_build_status(self._paths, member.build_id)
            if built.build is None or built.qualification is None:
                raise RunError(
                    f"build {member.build_id} no longer has a complete record",
                    code="forge_build_not_qualified",
                    details={"build_id": member.build_id},
                )
            task_dir = self._paths.forge_build_dir(member.build_id) / "tasks" / task_id
            facts = read_skill_task_facts(task_dir)
            tasks.append(
                _RunTask(
                    task_id=task_id,
                    build=built.build,
                    image=_image(built.qualification, task_id),
                    task_dir=task_dir,
                    agent_timeout=facts.agent_timeout,
                    verifier_timeout=facts.verifier_timeout,
                    outputs=_TaskOutputs(artifacts=facts.artifacts, limits=limits),
                )
            )
        return tasks

    def _require_signed_in(self, spec: ForgeRunSpec) -> None:
        require_signed_in(
            self._run, Path(spec.agent.executable), spec.model.provider, self._profile
        )

    def _recorded_run(
        self,
        spec: ForgeRunSpec,
        skill_files: list[tuple[Path, str]],
        tasks: list[_RunTask],
    ) -> ForgeRunStatus:
        """Record the run and every attempt; the caller holds the profile."""
        run_id = new_id("forgerun")
        run_dir = self._paths.forge_run_dir(run_id)
        run_dir.mkdir(parents=True, mode=0o700)
        atomic_write_bytes(run_dir / _SPEC_FILENAME, canonical_json_bytes(spec))
        snapshot_skill(skill_files, run_dir / SKILL_DIRNAME)
        now = datetime.now(UTC)
        record = ForgeRunRecord(
            schema_version=FORGE_RUN_SCHEMA_VERSION,
            run_id=run_id,
            spec_digest=run_spec_digest(spec),
            started_at=now,
            updated_at=now,
            state="unfinished",
            attempts=[],
            failure=None,
        )

        def persist(updated: ForgeRunRecord) -> None:
            nonlocal record
            atomic_write_json(run_dir / _RUN_FILENAME, updated.model_dump(mode="json"))
            record = updated

        status_command = shlex.join(
            ["techtree", "--home", str(self._paths.root), "forge", "status", run_id]
        )
        try:
            persist(record)
            self._docker.require_daemon()
            directories = [self._directory(spec, task, run_dir) for task in tasks]
            for task, directory in zip(tasks, directories, strict=True):
                for attempt in range(1, spec.sampling.repetitions + 1):
                    result = self._attempt(
                        spec=spec,
                        task=task,
                        directory=directory,
                        run_dir=run_dir,
                        attempt=attempt,
                    )
                    persist(
                        record.model_copy(
                            update={
                                "updated_at": datetime.now(UTC),
                                "attempts": [*record.attempts, result],
                            }
                        )
                    )
            persist(
                record.model_copy(
                    update={"updated_at": datetime.now(UTC), "state": "completed"}
                )
            )
        except (Exception, KeyboardInterrupt) as error:
            failure = _run_failure(error)
            receipt_written = True
            try:
                persist(
                    record.model_copy(
                        update={
                            "updated_at": datetime.now(UTC),
                            "failure": failure,
                            "state": "cancelled"
                            if isinstance(error, KeyboardInterrupt)
                            else "failed",
                        }
                    )
                )
            except Exception:
                receipt_written = False
            raise RunError(
                f"{failure.message}. Inspect: {status_command}"
                + (
                    "; final failure receipt could not be written"
                    if not receipt_written
                    else ""
                ),
                code=failure.code,
                details={
                    "run_id": run_id,
                    "path": str(run_dir),
                    "attempts_recorded": len(record.attempts),
                    "failure_recorded": receipt_written,
                },
            ) from error
        return ForgeRunStatus(
            run_id=run_id, path=str(run_dir), spec=spec, record=record
        )

    def _skill_files(
        self, spec: ForgeRunSpec, skill_root: Path | None
    ) -> list[tuple[Path, str]]:
        """Return the Skill's files to copy, once they are the declared ones."""
        if spec.skill is None:
            if skill_root is not None:
                raise ValidationError(
                    "this run was declared without a Skill, so it takes none",
                    code="forge_skill_not_declared",
                )
            return []
        if skill_root is None:
            raise ValidationError(
                "this run needs the Skill directory it was declared with",
                code="forge_skill_not_given",
            )
        found, files = scan_skill_spec(skill_root, name=spec.skill.name)
        if found.root_digest != spec.skill.root_digest:
            raise ValidationError(
                "the Skill directory no longer matches the Skill the "
                "specification declared; declare it again",
                code="forge_skill_changed",
                details={
                    "declared": spec.skill.root_digest,
                    "found": found.root_digest,
                },
            )
        return files

    def _directory(self, spec: ForgeRunSpec, task: _RunTask, run_dir: Path) -> str:
        """Return where the task's agent works, in the task's containers.

        A repository task works in ``/workspace``. A Skill task works in its
        image's working directory: every output it must leave has to be
        inside it, and it must be readable within the declared bounds as the
        image left it, or no attempt runs.
        """
        if task.outputs is None:
            return _WORKSPACE
        directory = self._docker.working_dir(task.image)
        base = PurePosixPath(directory)
        outside = [
            artifact
            for artifact in task.outputs.artifacts
            if not PurePosixPath(artifact).is_relative_to(base)
        ]
        if base == PurePosixPath("/"):
            reason = "the whole filesystem cannot be read back as its outputs"
        elif outside:
            reason = f"its required outputs {', '.join(outside)} are outside it"
        else:
            self._require_readable(task, task.outputs.limits, directory, run_dir)
            return directory
        raise ValidationError(
            f"task {task.task_id} cannot be run: its image works in "
            f"{directory}, and {reason}",
            code="forge_work_dir_unusable",
            details={
                "task_id": task.task_id,
                "work_dir": directory,
                "artifacts": list(task.outputs.artifacts),
            },
        )

    def _require_readable(
        self,
        task: _RunTask,
        limits: ForgeOutputLimits,
        directory: str,
        run_dir: Path,
    ) -> None:
        """Refuse a working directory the image leaves past the declared bounds."""
        with tempfile.TemporaryDirectory(dir=run_dir) as scratch:
            self._docker.export_directory(
                image=task.image,
                platform=task.build.platform,
                source=directory,
                destination=Path(scratch),
            )
            start = take_snapshot(Path(scratch), limits)
        if start.incomplete:
            raise ValidationError(
                f"task {task.task_id} cannot be run: its image leaves {directory} "
                "past what can be read back as its outputs ("
                + "; ".join(failure.detail for failure in start.incomplete)
                + ")",
                code="forge_work_dir_unreadable",
                details={"task_id": task.task_id, "work_dir": directory},
            )

    def _attempt(
        self,
        *,
        spec: ForgeRunSpec,
        task: _RunTask,
        directory: str,
        run_dir: Path,
        attempt: int,
    ) -> ForgeAttemptRecord:
        started = datetime.now(UTC)
        build, image = task.build, task.image
        attempt_dir = run_dir / "tasks" / task.task_id / str(attempt)
        workspace = attempt_dir / "workspace"
        workspace.mkdir(parents=True, mode=0o700)
        self._docker.export_directory(
            image=image,
            platform=build.platform,
            source=directory,
            destination=workspace,
        )
        capture = self._capture(task, workspace, directory, attempt_dir)

        config = hermes_config(spec, image, task.agent_timeout, workspace, directory)
        atomic_write_bytes(attempt_dir / "config.yaml", config)
        profile = self._profile
        reset_profile(profile)
        (profile / "skills").mkdir(mode=0o700)
        atomic_write_bytes(profile / "config.yaml", config)
        if spec.skill is not None:
            snapshot_skill(
                [
                    (run_dir / SKILL_DIRNAME / file.path, file.path)
                    for file in spec.skill.files
                ],
                profile / "skills" / spec.skill.name,
            )

        usage_file = attempt_dir / "usage.json"
        instruction = (task.task_dir / "instruction.md").read_text(encoding="utf-8")
        argv = [
            spec.agent.executable,
            "--yolo",
            "--in",
            str(workspace),
            "-m",
            spec.model.model_id,
            "--provider",
            spec.model.provider,
            *(("--reasoning", spec.model.reasoning) if spec.model.reasoning else ()),
            "-t",
            ",".join(spec.toolsets),
            "--usage-file",
            str(usage_file),
            *(("-s", spec.skill.name) if spec.skill is not None else ()),
            "-z",
            instruction,
        ]
        env = {
            **os.environ,
            "HERMES_HOME": str(profile),
            "HERMES_YOLO_MODE": "1",
            "HERMES_ACCEPT_HOOKS": "1",
        }
        try:
            agent = self._launch(
                argv,
                env,
                workspace,
                attempt_dir / "agent.log",
                task.agent_timeout + AGENT_MARGIN_SECONDS,
            )
        finally:
            transcript = profile / _STATE_DB
            if transcript.is_file() and not transcript.is_symlink():
                shutil.copyfile(transcript, attempt_dir / _STATE_DB)
            reset_profile(profile)
            self._docker.remove_labelled(_PROFILE_LABEL, PROFILE_NAME)

        usage = read_usage(usage_file)
        patch_digest: Digest | None = None
        outputs: ForgeOutputs | None = None
        if capture is None:
            patch_digest = self._patch(build, image, workspace, attempt_dir)
        else:
            outputs = capture()
        evidence = [
            kind
            for kind, present in (
                (ForgeEvidence.USAGE_REPORT, usage is not None),
                (ForgeEvidence.AGENT_TRANSCRIPT, (attempt_dir / _STATE_DB).is_file()),
                (ForgeEvidence.WORKSPACE_PATCH, patch_digest is not None),
                (ForgeEvidence.OUTPUT_MANIFEST, outputs is not None),
            )
            if present
        ]

        reward: float | None = None
        details: dict[str, JsonValue] = {}
        verifier_timed_out = False
        agent_failed = (
            agent.exit_code != 0 or usage is None or usage.failed or not usage.completed
        )
        if agent.timed_out:
            outcome = ForgeAttemptOutcome.AGENT_TIMED_OUT
        elif agent_failed:
            outcome = ForgeAttemptOutcome.AGENT_FAILED
        elif outputs is not None and any(
            failure.kind != "artifact_missing" for failure in outputs.failures
        ):
            outcome = ForgeAttemptOutcome.OUTPUTS_REJECTED
        else:
            verdict = grade_task(
                self._docker,
                build.platform,
                image,
                task.task_dir,
                attempt_dir / "grading",
                time_limit=task.verifier_timeout,
                reference=False,
                workspace=Mount(source=workspace, target=directory, read_only=False),
            )
            verifier_timed_out = verdict.stopped == "tests_timed_out"
            if verifier_timed_out:
                outcome = ForgeAttemptOutcome.VERIFIER_TIMED_OUT
            elif verdict.reward is None:
                outcome = ForgeAttemptOutcome.NO_VERDICT
            else:
                outcome = ForgeAttemptOutcome.GRADED
                reward = verdict.reward
                details = _json_details(verdict.details)
                evidence.append(ForgeEvidence.VERIFIER_VERDICT)

        return ForgeAttemptRecord(
            task_id=task.task_id,
            attempt=attempt,
            started_at=started,
            finished_at=datetime.now(UTC),
            config_digest=sha256_digest_bytes(config),
            hermes_arguments=[
                "instruction.md" if item == instruction else item for item in argv[1:]
            ],
            agent_exit_code=agent.exit_code,
            agent_timed_out=agent.timed_out,
            agent_seconds=agent.seconds,
            usage=usage,
            patch_digest=patch_digest,
            outputs=outputs,
            verifier_timed_out=verifier_timed_out,
            reward=reward,
            reward_details=details,
            outcome=outcome,
            evidence=evidence,
        )

    def _capture(
        self, task: _RunTask, workspace: Path, directory: str, attempt_dir: Path
    ) -> Callable[[], ForgeOutputs] | None:
        """Read a Skill task's directory before the agent starts.

        Return what reads it again afterwards and records the difference; a
        repository task has no such reading.
        """
        if task.outputs is None:
            return None
        return partial(
            capture_outputs,
            workspace,
            take_snapshot(workspace, task.outputs.limits),
            work_dir=directory,
            artifacts=list(task.outputs.artifacts),
            limits=task.outputs.limits,
            destination=attempt_dir / "outputs",
        )

    def _patch(
        self, build: ForgeBuildRecord, image: str, workspace: Path, attempt_dir: Path
    ) -> Digest | None:
        """Diff the workspace against the base commit and keep the patch."""
        outcome = self._docker.run(
            image=image,
            platform=build.platform,
            argv=[
                "sh",
                "-c",
                f"git config --global --add safe.directory {_WORKSPACE} && "
                f"cd {_WORKSPACE} && git add -A && git diff --cached --binary HEAD",
            ],
            mounts=[Mount(source=workspace, target=_WORKSPACE, read_only=False)],
            timeout=_PATCH_TIMEOUT_SECONDS,
        )
        if outcome.exit_code != 0 or outcome.timed_out:
            (attempt_dir / "patch.log").write_text(
                f"exit {outcome.exit_code}, timed out {outcome.timed_out}\n"
                f"{outcome.stderr}",
                encoding="utf-8",
            )
            return None
        patch = outcome.stdout.encode("utf-8")
        atomic_write_bytes(attempt_dir / "patch.diff", patch)
        return sha256_digest_bytes(patch)


def read_run_status(paths: TechtreePaths, run_id: str) -> ForgeRunStatus:
    """Read one run's specification and record back from its directory."""
    run_dir = paths.forge_run_dir(validate_id(run_id, "forgerun"))
    spec_file = run_dir / _SPEC_FILENAME
    record_file = run_dir / _RUN_FILENAME
    if not spec_file.is_file() or not record_file.is_file():
        raise NotFoundError(
            f"no recorded forge run {run_id}",
            code="forge_run_not_found",
            details={"run_id": run_id, "path": str(run_dir)},
        )
    try:
        spec = ForgeRunSpec.model_validate_json(spec_file.read_bytes())
        record = ForgeRunRecord.model_validate_json(record_file.read_bytes())
    except ModelValidationError as error:
        issue = error.errors(include_input=False, include_url=False)[0]
        raise ValidationError(
            f"invalid forge run evidence: {issue['msg']}",
            code="forge_evidence_invalid",
            details={"run_id": run_id, "path": str(run_dir)},
        ) from error
    return ForgeRunStatus(run_id=run_id, path=str(run_dir), spec=spec, record=record)


def _image(qualification: ForgeQualification, task_id: str) -> str:
    """Return the image qualification built for a task."""
    return next(
        task.image_id for task in qualification.tasks if task.task_id == task_id
    )


def _json_details(details: dict[str, object]) -> dict[str, JsonValue]:
    """Keep the verifier's details only where they are plain JSON."""
    try:
        return {key: json.loads(json.dumps(value)) for key, value in details.items()}
    except (TypeError, ValueError):
        return {}


def _run_failure(error: Exception | KeyboardInterrupt) -> ForgeBuildFailure:
    if isinstance(error, KeyboardInterrupt):
        code, message = "forge_run_cancelled", "run cancelled by Ctrl-C"
    elif isinstance(error, TechtreeError):
        code, message = error.code, error.message
    else:
        code, message = (
            "forge_run_failed",
            f"unexpected {type(error).__name__}; inspect the run's evidence",
        )
    return ForgeBuildFailure(
        code=code, message=message[:512], error_type=type(error).__name__
    )
