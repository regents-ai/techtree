"""Running one arm of a forge experiment with the person's own Hermes.

A run executes a :class:`~techtree.forge.models.ForgeRunSpec` and nothing
else: the specification was declared first, and every attempt here is what
it says. For each named task and each repetition, in order:

1. the task image's ``/workspace`` is copied out to the host at the base
   commit, so the agent works in a real directory Techtree can diff and grade;
2. a throwaway Hermes profile is created under the person's own Hermes root
   with a ``config.yaml`` Techtree wrote — Docker sandbox from the task image,
   no network, memory off, no title generation — and, on the candidate arm,
   the Skill copied under ``skills/<name>`` exactly as declared;
3. the person's ``hermes`` runs one-shot in that profile, in the workspace,
   with the task's instruction, the Skill preloaded on the candidate arm and
   the task's own agent timeout as its run budget and as Techtree's deadline;
4. the workspace is diffed against the base commit inside a fresh container
   and the patch kept;
5. the task's own tests grade the workspace the way qualification graded the
   reference repair, and the reward files are read the same way.

The profile is a profile rather than a bare directory on purpose: Hermes
reads the root's sign-ins from a profile and writes refreshed tokens back to
the root, which is what lets Techtree copy no credential. After the attempt
the profile's transcript database is kept beside the evidence and the profile
is removed; nothing under it is read but that one file.

Every outcome is its own kind: a graded attempt has a reward, and an agent
that timed out or failed, a verifier that timed out, or a verifier that left
no readable verdict are recorded as exactly that, never as zero.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import signal
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from pydantic import ValidationError as ModelValidationError

from techtree.canonical import canonical_json_bytes, sha256_digest_bytes
from techtree.errors import NotFoundError, RunError, TechtreeError, ValidationError
from techtree.forge.docker import Docker, Mount
from techtree.forge.experiment import run_spec_digest
from techtree.forge.models import (
    FORGE_RUN_SCHEMA_VERSION,
    ForgeAttemptOutcome,
    ForgeAttemptRecord,
    ForgeBuildFailure,
    ForgeBuildRecord,
    ForgeEvidence,
    ForgeQualification,
    ForgeRunRecord,
    ForgeRunSpec,
    ForgeRunStatus,
    ForgeUsage,
)
from techtree.forge.process import CommandRunner
from techtree.forge.qualify import grade_task, read_task_facts
from techtree.forge.service import read_build_status
from techtree.fs import atomic_write_bytes, atomic_write_json, remove_tree
from techtree.ids import new_id, validate_id
from techtree.manifests.builder import skill_content_digest
from techtree.models.base import Digest, JsonValue
from techtree.models.skill import SkillFile
from techtree.paths import TechtreePaths
from techtree.skills.policy import default_instruction_skill_policy
from techtree.skills.scanner import scan_skill

__all__ = [
    "AgentLauncher",
    "AgentOutcome",
    "ForgeRunner",
    "hermes_config",
    "hermes_root",
    "launch_agent",
    "read_run_status",
]

_SPEC_FILENAME: Final = "spec.json"
_RUN_FILENAME: Final = "run.json"
#: The Hermes toolsets the sandbox routes: shell, files, code, Skills. No web,
#: no browser, no memory, no delegation — the host process must not reach
#: what the container cannot.
_TOOLSETS: Final = "terminal,file,code_execution,skills"
#: Added to the task's agent timeout before Techtree stops Hermes itself;
#: Hermes is given the timeout as its own budget and should stop first.
_AGENT_MARGIN_SECONDS: Final = 120.0
#: After an interrupt Hermes writes its usage report and exits; then it is killed.
_INTERRUPT_GRACE_SECONDS: Final = 30.0
_PATCH_TIMEOUT_SECONDS: Final = 120.0
_STATE_DB: Final = "state.db"
_USAGE_KEYS: Final = (
    "model",
    "provider",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "api_calls",
    "estimated_cost_usd",
    "cost_status",
    "cost_source",
    "completed",
    "failed",
    "failure",
)


@dataclass(frozen=True)
class AgentOutcome:
    """What one Hermes process did."""

    exit_code: int | None
    timed_out: bool
    seconds: float


type AgentLauncher = Callable[
    [list[str], dict[str, str], Path, Path, float], AgentOutcome
]


def hermes_root() -> Path:
    """Return the person's Hermes root, the way Hermes itself resolves it.

    ``HERMES_HOME`` names the root, or a profile under ``<root>/profiles``;
    otherwise the root is ``~/.hermes``.
    """
    configured = os.environ.get("HERMES_HOME", "")
    if not configured:
        return Path.home() / ".hermes"
    home = Path(configured).expanduser()
    return home.parent.parent if home.parent.name == "profiles" else home


def hermes_config(spec: ForgeRunSpec, image: str, agent_timeout: float) -> bytes:
    """Return the ``config.yaml`` Techtree writes for one attempt, as bytes.

    JSON is YAML, and the canonical encoder is what makes the digest of this
    file a fact two runs can compare.
    """
    return canonical_json_bytes(
        {
            "terminal": {
                "backend": "docker",
                "docker_image": image,
                "docker_mount_cwd_to_workspace": True,
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


def launch_agent(
    argv: list[str], env: dict[str, str], cwd: Path, log: Path, timeout: float
) -> AgentOutcome:
    """Run Hermes once, its output to ``log``, and stop it at ``timeout``.

    A timed-out Hermes is interrupted first so it can write its usage report,
    and killed only if it does not exit in time.
    """
    started = time.monotonic()
    with log.open("wb") as output:
        try:
            process = subprocess.Popen(
                argv,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
            )
        except OSError as error:
            raise RunError(
                f"{argv[0]} could not be started: {error.strerror or error}",
                code="hermes_unusable",
                details={"executable": argv[0]},
            ) from error
        try:
            exit_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=_INTERRUPT_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            return AgentOutcome(
                exit_code=None, timed_out=True, seconds=time.monotonic() - started
            )
        except KeyboardInterrupt:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=_INTERRUPT_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise
    return AgentOutcome(
        exit_code=exit_code, timed_out=False, seconds=time.monotonic() - started
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
        self._docker = Docker(run)
        self._launch = launch
        self._profiles_root = (
            profiles_root if profiles_root is not None else hermes_root() / "profiles"
        )

    def run(self, spec: ForgeRunSpec, skill_root: Path | None) -> ForgeRunStatus:
        """Execute every attempt the specification names and record each one."""
        skill_files = self._skill_files(spec, skill_root)
        status = read_build_status(self._paths, spec.build_id)
        if status.build is None or status.qualification is None:
            raise RunError(
                f"build {spec.build_id} no longer has a complete record",
                code="forge_build_not_qualified",
                details={"build_id": spec.build_id},
            )
        build, qualification = status.build, status.qualification
        if qualification.membership_digest != spec.membership_digest:
            raise ValidationError(
                "the build's tasks are not the ones the specification was declared on",
                code="forge_membership_mismatch",
                details={
                    "build_id": spec.build_id,
                    "declared": spec.membership_digest,
                    "stored": qualification.membership_digest,
                },
            )

        run_id = new_id("forgerun")
        run_dir = self._paths.forge_run_dir(run_id)
        run_dir.mkdir(parents=True, mode=0o700)
        atomic_write_bytes(run_dir / _SPEC_FILENAME, canonical_json_bytes(spec))
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
            counter = 0
            for task_id in spec.task_ids:
                for attempt in range(1, spec.sampling.repetitions + 1):
                    counter += 1
                    result = self._attempt(
                        spec=spec,
                        build=build,
                        qualification=qualification,
                        skill_files=skill_files,
                        run_dir=run_dir,
                        profile_name=f"techtree-{run_id[-12:]}-{counter}",
                        task_id=task_id,
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
        """Return the Skill's files to deliver, once they are the declared ones."""
        if spec.skill is None:
            if skill_root is not None:
                raise ValidationError(
                    "the baseline arm runs without a Skill",
                    code="forge_baseline_with_skill",
                )
            return []
        if skill_root is None:
            raise ValidationError(
                "the candidate arm needs the Skill directory it declared",
                code="forge_candidate_without_skill",
            )
        scan = scan_skill(skill_root, default_instruction_skill_policy())
        digest = skill_content_digest(
            [
                SkillFile(
                    path=item.relative_path.as_posix(),
                    media_type=item.media_type,
                    size=item.size,
                    digest=item.digest,
                )
                for item in scan.files
            ]
        )
        if digest != spec.skill.root_digest:
            raise ValidationError(
                "the Skill directory no longer matches the Skill the "
                "specification declared; declare it again",
                code="forge_skill_changed",
                details={"declared": spec.skill.root_digest, "found": digest},
            )
        return [
            (item.source_path, item.relative_path.as_posix()) for item in scan.files
        ]

    def _attempt(
        self,
        *,
        spec: ForgeRunSpec,
        build: ForgeBuildRecord,
        qualification: ForgeQualification,
        skill_files: list[tuple[Path, str]],
        run_dir: Path,
        profile_name: str,
        task_id: str,
        attempt: int,
    ) -> ForgeAttemptRecord:
        started = datetime.now(UTC)
        task_dir = self._paths.forge_build_dir(spec.build_id) / "tasks" / task_id
        facts = read_task_facts(task_dir)
        image = next(
            task.image_id for task in qualification.tasks if task.task_id == task_id
        )
        attempt_dir = run_dir / "tasks" / task_id / str(attempt)
        workspace = attempt_dir / "workspace"
        workspace.mkdir(parents=True, mode=0o700)
        self._docker.export_workspace(
            image=image, platform=build.platform, destination=workspace
        )

        config = hermes_config(spec, image, facts.agent_timeout)
        atomic_write_bytes(attempt_dir / "config.yaml", config)
        profile = self._profiles_root / profile_name
        if profile.exists():
            raise RunError(
                f"a Hermes profile named {profile_name} already exists",
                code="forge_profile_exists",
                details={"profile": str(profile)},
            )
        (profile / "skills").mkdir(parents=True, mode=0o700)
        atomic_write_bytes(profile / "config.yaml", config)
        if spec.skill is not None:
            for source, relative in skill_files:
                target = profile / "skills" / spec.skill.name / relative
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                shutil.copyfile(source, target)

        usage_file = attempt_dir / "usage.json"
        instruction = (task_dir / "instruction.md").read_text(encoding="utf-8")
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
            _TOOLSETS,
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
                facts.agent_timeout + _AGENT_MARGIN_SECONDS,
            )
        finally:
            transcript = profile / _STATE_DB
            if transcript.is_file() and not transcript.is_symlink():
                shutil.copyfile(transcript, attempt_dir / _STATE_DB)
            remove_tree(profile)

        usage = _read_usage(usage_file)
        patch_digest = self._patch(build, image, workspace, attempt_dir)
        evidence = [
            kind
            for kind, present in (
                (ForgeEvidence.USAGE_REPORT, usage is not None),
                (ForgeEvidence.AGENT_TRANSCRIPT, (attempt_dir / _STATE_DB).is_file()),
                (ForgeEvidence.WORKSPACE_PATCH, patch_digest is not None),
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
        else:
            verdict = grade_task(
                self._docker,
                build.platform,
                image,
                task_dir,
                attempt_dir / "grading",
                facts,
                reference=False,
                workspace=workspace,
            )
            verifier_timed_out = bool(verdict.details.get("timed_out"))
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
            task_id=task_id,
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
            verifier_timed_out=verifier_timed_out,
            reward=reward,
            reward_details=details,
            outcome=outcome,
            evidence=evidence,
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
                "git config --global --add safe.directory /workspace && "
                "cd /workspace && git add -A && git diff --cached --binary HEAD",
            ],
            mounts=[Mount(source=workspace, target="/workspace", read_only=False)],
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


def _read_usage(usage_file: Path) -> ForgeUsage | None:
    """Read Hermes' usage report as it reported it, or nothing."""
    try:
        loaded = json.loads(usage_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(loaded, dict):
        return None
    try:
        return ForgeUsage.model_validate({key: loaded.get(key) for key in _USAGE_KEYS})
    except ModelValidationError:
        return None


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
