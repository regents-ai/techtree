"""``forge build`` and ``forge status`` as operations.

Design: ``docs/plan/repo2rlenv-local-lane.md``.

A build directory under the Techtree home holds everything one build made:

    forge/builds/<build_id>/
        build.json            what was built, from what, and what was emitted
        qualification.json    which tasks proved out, with the evidence
        progress.json         last observed phase, partial task evidence, failures
        checkout/<name>/      the cloned history the bootstrap image was built from
        tasks/<task_id>/      the Harbor tasks Repo2RLEnv emitted
        log/                  the bootstrap build log and the generation log
        qualification/        per-task image build logs and graded run output

``progress.json`` is written before dependency setup. ``build.json`` records
finished generation/content commitment; ``qualification.json`` records all-task
grading. Last observed progress never asserts that a process is still running.
"""

from __future__ import annotations

import platform
import shlex
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from pydantic import ValidationError as ModelValidationError

from techtree.canonical import sha256_digest_bytes
from techtree.errors import (
    NotFoundError,
    RunError,
    TechtreeError,
    UsageError,
    ValidationError,
)
from techtree.forge.bundle import (
    REPO2RLENV_VERSION,
    embedded_forge_root,
    ensure_forge_environment,
)
from techtree.forge.content import commit_task_set
from techtree.forge.docker import Docker
from techtree.forge.generate import (
    bootstrap_image_tag,
    clone_repository,
    generate_tasks,
    repository_slug,
)
from techtree.forge.models import (
    FORGE_BUILD_SCHEMA_VERSION,
    FORGE_PROGRESS_SCHEMA_VERSION,
    ForgeBuildFailure,
    ForgeBuildPhase,
    ForgeBuildProgress,
    ForgeBuildRecord,
    ForgeBuildStatus,
    ForgeLanguage,
    ForgePlatform,
    ForgeQualification,
    TaskQualification,
)
from techtree.forge.process import CommandRunner
from techtree.forge.qualify import qualify_build
from techtree.fs import atomic_write_json, ensure_private_directory
from techtree.ids import new_id, validate_id
from techtree.models.engine import normalize_host_platform
from techtree.paths import TechtreePaths

__all__ = [
    "ForgeService",
    "default_dockerfile",
    "host_docker_platform",
    "read_build_status",
]

_BUILD_FILENAME: Final = "build.json"
_QUALIFICATION_FILENAME: Final = "qualification.json"
_PROGRESS_FILENAME: Final = "progress.json"
_DEFAULT_DOCKERFILE: Final = "Dockerfile.python-uv"


def default_dockerfile() -> str:
    """Return the shipped Dockerfile for a uv-managed Python repository."""
    return (embedded_forge_root() / _DEFAULT_DOCKERFILE).read_text(encoding="utf-8")


def host_docker_platform() -> ForgePlatform:
    """Return the Docker platform matching this machine's architecture."""
    host = normalize_host_platform(sys.platform, platform.machine())
    return "linux/arm64" if host.endswith("/arm64") else "linux/amd64"


def _dockerfile_text(dockerfile: Path | None) -> str:
    """Return the person's Dockerfile, or the shipped one when they gave none."""
    if dockerfile is None:
        return default_dockerfile()
    resolved = dockerfile.expanduser().resolve()
    if not resolved.is_file():
        raise UsageError(
            f"{resolved} is not a file",
            code="forge_dockerfile_missing",
            details={"dockerfile": str(resolved)},
        )
    return resolved.read_text(encoding="utf-8")


class ForgeService:
    """Builds and reports forge builds in one Techtree home."""

    def __init__(
        self, paths: TechtreePaths, run: CommandRunner, uv_executable: Path
    ) -> None:
        self._paths = paths
        self._run = run
        self._uv = uv_executable
        self._docker = Docker(run)

    def build(
        self,
        *,
        repository: Path,
        dockerfile: Path | None,
        test_commands: list[str],
        limit: int,
        language: ForgeLanguage,
    ) -> ForgeBuildStatus:
        """Generate tasks from ``repository`` and qualify every one of them."""
        repository = repository.expanduser().resolve()
        if not (repository / ".git").exists():
            raise UsageError(
                f"{repository} is not a git repository",
                code="forge_repository_not_git",
                details={"repository": str(repository)},
            )
        dockerfile_text = _dockerfile_text(dockerfile)
        docker_platform = host_docker_platform()

        build_id = new_id("build")
        build_dir = self._paths.forge_build_dir(build_id)
        now = datetime.now(UTC)
        progress = ForgeBuildProgress(
            schema_version=FORGE_PROGRESS_SCHEMA_VERSION,
            build_id=build_id,
            repository=str(repository),
            started_at=now,
            updated_at=now,
            phase="preparing",
            state="unfinished",
            membership_digest=None,
            current_task_id=None,
            completed_tasks=[],
            failure=None,
        )

        def persist(updated: ForgeBuildProgress) -> None:
            nonlocal progress
            updated = ForgeBuildProgress.model_validate(updated.model_dump())
            atomic_write_json(
                build_dir / _PROGRESS_FILENAME, updated.model_dump(mode="json")
            )
            progress = updated

        def phase_changed(
            phase: ForgeBuildPhase, record: ForgeBuildRecord | None = None
        ) -> None:
            persist(
                progress.model_copy(
                    update={
                        "phase": phase,
                        "updated_at": datetime.now(UTC),
                        "state": "completed" if phase == "completed" else "unfinished",
                        "current_task_id": None,
                        "membership_digest": record.task_set.membership_digest
                        if record
                        else progress.membership_digest,
                    }
                )
            )

        def task_changed(task_id: str, task: TaskQualification | None) -> None:
            persist(
                progress.model_copy(
                    update={
                        "updated_at": datetime.now(UTC),
                        "current_task_id": task_id if task is None else None,
                        "completed_tasks": progress.completed_tasks
                        if task is None
                        else [*progress.completed_tasks, task],
                    }
                )
            )

        status_command = shlex.join(
            ["techtree", "--home", str(self._paths.root), "forge", "status", build_id]
        )
        try:
            persist(progress)
            status = self._build(
                repository=repository,
                dockerfile_text=dockerfile_text,
                test_commands=test_commands,
                limit=limit,
                language=language,
                docker_platform=docker_platform,
                build_id=build_id,
                on_phase=phase_changed,
                on_task=task_changed,
            )
        except (Exception, KeyboardInterrupt) as error:
            failure = _build_failure(error)
            receipt_written = True
            try:
                persist(
                    progress.model_copy(
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
                # Preserve the primary failure, but never claim an unwritten receipt.
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
                    "build_id": build_id,
                    "path": str(build_dir),
                    "phase": progress.phase,
                    "failure_recorded": receipt_written,
                },
            ) from error
        if status.usable_tasks == 0:
            reasons = status.build.generation.skip_reasons if status.build else {}
            raise RunError(
                "qualification finished with no usable tasks; "
                f"skip reasons: {reasons}. "
                f"Inspect: {status_command}",
                code="forge_no_usable_tasks",
                details={
                    "build_id": build_id,
                    "path": str(build_dir),
                    "usable_tasks": 0,
                },
            )
        return status

    def _build(
        self,
        *,
        repository: Path,
        dockerfile_text: str,
        test_commands: list[str],
        limit: int,
        language: ForgeLanguage,
        docker_platform: ForgePlatform,
        build_id: str,
        on_phase: Callable[[ForgeBuildPhase, ForgeBuildRecord | None], None],
        on_task: Callable[[str, TaskQualification | None], None],
    ) -> ForgeBuildStatus:
        self._docker.require_daemon()
        environment = ensure_forge_environment(self._paths, self._run, self._uv)

        build_dir = self._paths.forge_build_dir(build_id)
        # Repo2RLEnv names tasks after the cloned directory, so the clone is
        # named after the repository rather than after its role here.
        checkout = build_dir / "checkout" / repository_slug(repository)
        tasks_dir = build_dir / "tasks"
        log_dir = build_dir / "log"
        for directory in (build_dir, checkout.parent, tasks_dir, log_dir):
            ensure_private_directory(directory)

        # The Dockerfile that was used is kept beside what it built, whichever
        # of the two it came from.
        used_dockerfile = build_dir / "Dockerfile"
        used_dockerfile.write_text(dockerfile_text, encoding="utf-8")

        on_phase("cloning", None)
        head_commit = clone_repository(repository, checkout, self._run)
        slug = repository_slug(repository)
        image_tag = bootstrap_image_tag(slug, head_commit, build_id)
        on_phase("bootstrap", None)
        image_id = self._docker.build(
            context=checkout,
            dockerfile=used_dockerfile,
            tag=image_tag,
            platform=docker_platform,
            log=log_dir / "bootstrap-build.log",
        )
        on_phase("generation", None)
        generation = generate_tasks(
            environment=environment,
            run=self._run,
            docker=self._docker,
            checkout=checkout,
            head_commit=head_commit,
            image_tag=image_tag,
            image_id=image_id,
            dockerfile_text=dockerfile_text,
            language=language,
            platform=docker_platform,
            test_commands=test_commands,
            limit=limit,
            slug=slug,
            tasks_dir=tasks_dir,
            work_dir=log_dir,
        )
        on_phase("content", None)
        record = ForgeBuildRecord(
            schema_version=FORGE_BUILD_SCHEMA_VERSION,
            build_id=build_id,
            created_at=datetime.now(UTC),
            repository=str(repository),
            head_commit=head_commit,
            slug=slug,
            language=language,
            platform=docker_platform,
            dockerfile_digest=sha256_digest_bytes(dockerfile_text.encode("utf-8")),
            test_commands=test_commands,
            limit=limit,
            bootstrap_image_tag=image_tag,
            bootstrap_image_id=image_id,
            repo2rlenv_version=REPO2RLENV_VERSION,
            generation=generation,
            task_set=commit_task_set(tasks_dir, generation.tasks),
        )
        atomic_write_json(build_dir / _BUILD_FILENAME, record.model_dump(mode="json"))

        on_phase("qualification", record)
        qualification = qualify_build(
            docker=self._docker,
            build=record,
            tasks_dir=tasks_dir,
            work_dir=build_dir / "qualification",
            on_task=on_task,
        )
        atomic_write_json(
            build_dir / _QUALIFICATION_FILENAME, qualification.model_dump(mode="json")
        )
        on_phase("completed", record)
        return read_build_status(self._paths, build_id)


def read_build_status(paths: TechtreePaths, build_id: str) -> ForgeBuildStatus:
    """Report stored build evidence without constructing an execution service."""
    build_dir = paths.forge_build_dir(validate_id(build_id, "build"))
    record_file = build_dir / _BUILD_FILENAME
    progress_file = build_dir / _PROGRESS_FILENAME
    if not record_file.is_file() and not progress_file.is_file():
        raise NotFoundError(
            f"no recorded forge build {build_id}"
            + (
                "; the directory exists but has no readable build or progress receipt"
                if build_dir.is_dir()
                else ""
            ),
            code="forge_build_not_found",
            details={"build_id": build_id, "path": str(build_dir)},
        )
    evidence_file = progress_file
    try:
        progress = (
            ForgeBuildProgress.model_validate_json(progress_file.read_bytes())
            if progress_file.is_file()
            else None
        )
        evidence_file = record_file
        record = (
            ForgeBuildRecord.model_validate_json(record_file.read_bytes())
            if record_file.is_file()
            else None
        )
        qualification_file = build_dir / _QUALIFICATION_FILENAME
        evidence_file = qualification_file
        qualification = (
            ForgeQualification.model_validate_json(qualification_file.read_bytes())
            if qualification_file.is_file()
            else None
        )
        return ForgeBuildStatus(
            build_id=build_id,
            build=record,
            path=str(build_dir),
            tasks_path=str(build_dir / "tasks"),
            qualification=qualification,
            progress=progress,
            generation_finished=(
                True
                if record is not None
                else False
                if progress is not None and progress.state in {"failed", "cancelled"}
                else None
            ),
            qualification_finished=(
                True
                if qualification is not None
                else False
                if progress is not None and progress.state in {"failed", "cancelled"}
                else None
            ),
            usable_tasks=len(qualification.qualified_task_ids)
            if qualification is not None
            else None,
        )
    except ModelValidationError as error:
        reason = _validation_reason(error)
        if reason.startswith(
            (
                "progress ",
                "partial ",
                "current task ",
                "completed progress ",
                "qualification phase ",
            )
        ):
            evidence_file = progress_file
        raise ValidationError(
            f"invalid forge evidence: {reason}",
            code="forge_evidence_invalid",
            details={"build_id": build_id, "file": str(evidence_file)},
        ) from error


def _validation_reason(error: ModelValidationError) -> str:
    issue = error.errors(include_input=False, include_context=False, include_url=False)[
        0
    ]
    return (
        "unsupported forge schema version"
        if "schema_version" in issue["loc"]
        else issue["msg"].removeprefix("Value error, ")
    )


def _build_failure(error: Exception | KeyboardInterrupt) -> ForgeBuildFailure:
    if isinstance(error, KeyboardInterrupt):
        code, message = "forge_build_cancelled", "build cancelled by Ctrl-C"
    elif isinstance(error, TechtreeError):
        code, message = error.code, error.message
    elif isinstance(error, ModelValidationError):
        code, message = "forge_evidence_invalid", _validation_reason(error)
    else:
        code, message = (
            "forge_build_failed",
            f"unexpected {type(error).__name__}; inspect the build logs",
        )
    return ForgeBuildFailure(
        code=code, message=message[:512], error_type=type(error).__name__
    )
