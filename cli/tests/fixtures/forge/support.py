"""A qualified forge build, a Skill, and stand-ins for Docker and Hermes.

The build is written the way the forge writes one — a build record, a
qualification, and one task directory — so the experiment and run code read
it through the real readers. Docker and Hermes are replaced at the two seams
the run code already has: the command runner every ``docker`` call goes
through, and the launcher that starts the ``hermes`` process. Each stand-in
does the little the real thing would do on the host (copy a workspace out,
leave a reward file, write a usage report) and records what it was asked.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from techtree.canonical import digest_object, sha256_digest_bytes
from techtree.errors import RunError
from techtree.forge.experiment import declare_run_spec
from techtree.forge.models import (
    ForgeArm,
    ForgeBuildRecord,
    ForgeLanguage,
    ForgeQualification,
    ForgeRunSpec,
    GenerationSummary,
    TaskContentEntry,
    TaskContentManifest,
    TaskQualification,
    TaskSetCommitment,
)
from techtree.forge.run import AgentOutcome
from techtree.fs import atomic_write_json
from techtree.paths import TechtreePaths, paths_from_root

__all__ = [
    "FakeDocker",
    "FakeHermes",
    "QualifiedBuild",
    "declare",
    "hermes_on_path",
    "qualified_build",
    "write_skill",
]

TASK_ID = "local__demo-000000000001"
IMAGE_ID = "sha256:" + "ab" * 32
BASE_COMMIT = "0123456789abcdef0123456789abcdef01234567"
INSTRUCTION = "Make the failing test pass.\n"
AGENT_TIMEOUT = 60.0
VERIFIER_TIMEOUT = 30.0
HERMES_VERSION_LINE = "Hermes Agent v0.21.3 (2026.9.14) · upstream 0.21.3\n"


@dataclass(frozen=True)
class QualifiedBuild:
    paths: TechtreePaths
    build_id: str
    task_id: str
    task_dir: Path


def qualified_build(home: Path, *, qualified: bool = True) -> QualifiedBuild:
    """Write one build with one task to ``home`` and return where it is."""
    paths = paths_from_root(home)
    build_id = "build_" + "1" * 32
    task_dir = paths.forge_build_dir(build_id) / "tasks" / TASK_ID
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "solution").mkdir()
    (task_dir / "task.toml").write_text(
        "[metadata.repo2env.commit_runtime]\n"
        f'parent_sha = "{BASE_COMMIT}"\n'
        'fail_to_pass = ["tests/test_demo.py::test_it"]\n'
        "pass_to_pass = []\n"
        f"[agent]\ntimeout_sec = {AGENT_TIMEOUT}\n"
        f"[verifier]\ntimeout_sec = {VERIFIER_TIMEOUT}\n",
        encoding="utf-8",
    )
    (task_dir / "instruction.md").write_text(INSTRUCTION, encoding="utf-8")
    (task_dir / "tests" / "test.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    (task_dir / "solution" / "solve.sh").write_text("#!/bin/bash\n", encoding="utf-8")

    entries = [
        TaskContentEntry(
            path="instruction.md",
            kind="file",
            executable=False,
            size=len(INSTRUCTION),
            digest=sha256_digest_bytes(INSTRUCTION.encode()),
        )
    ]
    manifest = TaskContentManifest(
        schema_version="techtree.forge-task-content.v1alpha1",
        task_id=TASK_ID,
        entries=entries,
        content_digest=digest_object(
            {
                "schema_version": "techtree.forge-task-content.v1alpha1",
                "entries": entries,
            }
        ),
    )
    task_set = TaskSetCommitment(
        schema_version="techtree.forge-task-set.v1alpha1",
        tasks=[manifest],
        membership_digest=digest_object(
            {
                "schema_version": "techtree.forge-task-set.v1alpha1",
                "tasks": [
                    {"task_id": TASK_ID, "content_digest": manifest.content_digest}
                ],
            }
        ),
    )
    now = datetime.now(UTC)
    build = ForgeBuildRecord(
        schema_version="techtree.forge-build.v1alpha2",
        build_id=build_id,
        created_at=now,
        repository="/repo/demo",
        head_commit=BASE_COMMIT,
        slug="demo",
        language=ForgeLanguage.PYTHON,
        platform="linux/arm64",
        dockerfile_digest=sha256_digest_bytes(b"FROM scratch\n"),
        test_commands=["uv run pytest"],
        limit=1,
        bootstrap_image_tag="techtree-forge/demo:bootstrap",
        bootstrap_image_id="sha256:" + "cd" * 32,
        repo2rlenv_version="0.0.0",
        generation=GenerationSummary(
            candidates=1, emitted=1, skipped=0, skip_reasons={}, tasks=[TASK_ID]
        ),
        task_set=task_set,
    )
    qualification = ForgeQualification(
        schema_version="techtree.forge-qualification.v1alpha2",
        build_id=build_id,
        membership_digest=task_set.membership_digest,
        qualified_at=now,
        model_calls=0,
        tasks=[
            TaskQualification(
                task_id=TASK_ID,
                task_content_digest=manifest.content_digest,
                image_tag="techtree-forge/demo/" + TASK_ID + ":111111111111",
                image_id=IMAGE_ID,
                base_commit=BASE_COMMIT,
                fail_to_pass=1,
                pass_to_pass=0,
                control_reward=0.0,
                reference_reward=1.0,
                checks=[],
                qualified=qualified,
            )
        ],
        qualified_task_ids=[TASK_ID] if qualified else [],
    )
    build_dir = paths.forge_build_dir(build_id)
    atomic_write_json(build_dir / "build.json", build.model_dump(mode="json"))
    atomic_write_json(
        build_dir / "qualification.json", qualification.model_dump(mode="json")
    )
    return QualifiedBuild(
        paths=paths, build_id=build_id, task_id=TASK_ID, task_dir=task_dir
    )


def write_skill(
    parent: Path, name: str = "demo-skill", body: str = "Run the tests first."
) -> Path:
    """Write a minimal instruction Skill and return its directory."""
    root = parent / name
    root.mkdir(parents=True)
    (root / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: A demo Skill for tests.\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return root


def hermes_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make declaration find a Hermes that answers ``--version``."""
    monkeypatch.setattr(
        "techtree.forge.experiment.shutil.which",
        lambda name: "/fake/bin/hermes" if name == "hermes" else None,
    )
    monkeypatch.setattr(
        "techtree.forge.experiment.run_command",
        lambda argv, timeout: subprocess.CompletedProcess(
            list(argv), 0, HERMES_VERSION_LINE, ""
        ),
    )


def declare(
    build: QualifiedBuild,
    monkeypatch: pytest.MonkeyPatch,
    *,
    arm: ForgeArm,
    skill_root: Path | None = None,
    repetitions: int = 1,
    task_ids: list[str] | None = None,
) -> ForgeRunSpec:
    hermes_on_path(monkeypatch)
    return declare_run_spec(
        build.paths,
        arm=arm,
        build_id=build.build_id,
        task_ids=task_ids,
        skill_root=skill_root,
        provider="openai-codex",
        model_id="gpt-5.3-codex",
        reasoning=None,
        repetitions=repetitions,
    )


@dataclass
class FakeDocker:
    """The command runner every ``docker`` call goes through.

    ``reward`` is what the tests leave: a number, ``None`` for no verdict, or
    ``"timeout"`` for a test run that hangs. ``export_error`` makes the
    workspace export fail the way a missing image would.
    """

    reward: float | str | None = 1.0
    patch: str = "diff --git a/x b/x\n"
    export_error: bool = False
    calls: list[list[str]] = field(default_factory=list)

    def __call__(
        self, argv: Sequence[str], timeout: float
    ) -> subprocess.CompletedProcess[str]:
        command = list(argv)
        self.calls.append(command)
        match command[:2]:
            case ["docker", "version"]:
                return _done(command, "linux/arm64\n")
            case ["docker", "create"]:
                if self.export_error:
                    return subprocess.CompletedProcess(command, 1, "", "no such image")
                return _done(command)
            case ["docker", "cp"]:
                destination = Path(command[-1])
                (destination / "README.md").write_text("base\n", encoding="utf-8")
                return _done(command)
            case ["docker", "rm"]:
                return _done(command)
            case ["docker", "run"]:
                return self._run(command, timeout)
        raise AssertionError(f"unexpected docker command {command}")

    def _run(
        self, command: list[str], timeout: float
    ) -> subprocess.CompletedProcess[str]:
        script = command[-1]
        if "git diff --cached" in script:
            return _done(command, self.patch)
        assert script == "bash /tests/test.sh", script
        assert not any(":/solution" in part for part in command), (
            "the reference solution reached a grading container"
        )
        verifier = next(
            Path(part.removesuffix(":/logs/verifier"))
            for part in command
            if part.endswith(":/logs/verifier")
        )
        if self.reward == "timeout":
            raise RunError("hung", code="forge_command_timeout")
        if self.reward is not None:
            (verifier / "reward.txt").write_text(f"{self.reward}\n", encoding="utf-8")
        return _done(command)

    def graded(self) -> bool:
        return any(call[-1] == "bash /tests/test.sh" for call in self.calls)


def _done(command: list[str], stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(command, 0, stdout, "")


@dataclass
class FakeHermes:
    """The launcher that would start ``hermes``.

    It writes the usage report Hermes writes, leaves a transcript database
    and an ``auth.json`` in the profile so the tests can check which one the
    run keeps, and records the command line, environment and profile contents
    it was started with.
    """

    exit_code: int | None = 0
    timed_out: bool = False
    usage: dict[str, object] | None = field(
        default_factory=lambda: dict[str, object](
            model="gpt-5.3-codex",
            provider="openai-codex",
            input_tokens=100,
            output_tokens=20,
            total_tokens=120,
            api_calls=2,
            estimated_cost_usd=None,
            cost_status="unavailable",
            cost_source="subscription",
            completed=True,
            failed=False,
        )
    )
    interrupt: bool = False
    launches: list[dict[str, object]] = field(default_factory=list)

    def __call__(
        self,
        argv: list[str],
        env: dict[str, str],
        cwd: Path,
        log: Path,
        timeout: float,
    ) -> AgentOutcome:
        profile = Path(env["HERMES_HOME"])
        assert profile.is_dir()
        self.launches.append(
            {
                "argv": argv,
                "env": env,
                "cwd": cwd,
                "timeout": timeout,
                "profile": profile,
                "profile_files": sorted(
                    path.relative_to(profile).as_posix()
                    for path in profile.rglob("*")
                    if path.is_file()
                ),
                "config": (profile / "config.yaml").read_bytes(),
            }
        )
        log.write_text("hermes ran\n", encoding="utf-8")
        (profile / "state.db").write_bytes(b"transcript")
        (profile / "auth.json").write_text("{}", encoding="utf-8")
        usage_file = Path(argv[argv.index("--usage-file") + 1])
        if self.usage is not None:
            usage_file.write_text(json.dumps(self.usage), encoding="utf-8")
        if self.interrupt:
            raise KeyboardInterrupt
        return AgentOutcome(
            exit_code=self.exit_code, timed_out=self.timed_out, seconds=1.5
        )
