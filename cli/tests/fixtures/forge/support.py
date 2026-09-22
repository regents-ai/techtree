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
from techtree.forge.content import commit_task_set
from techtree.forge.experiment import declare_run_spec
from techtree.forge.models import (
    ForgeArm,
    ForgeBaseImage,
    ForgeBuildRecord,
    ForgeLanguage,
    ForgeQualification,
    ForgeRepositorySource,
    ForgeRunSpec,
    ForgeSkillSource,
    GenerationSummary,
    RepositoryTaskQualification,
    TaskContentEntry,
    TaskContentManifest,
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
    "signed_in_profile",
    "skill_build",
    "write_skill",
]

TASK_ID = "local__demo-000000000001"
IMAGE_ID = "sha256:" + "ab" * 32
BASE_COMMIT = "0123456789abcdef0123456789abcdef01234567"
INSTRUCTION = "Make the failing test pass.\n"
AGENT_TIMEOUT = 60.0
VERIFIER_TIMEOUT = 30.0
HERMES_VERSION_LINE = "Hermes Agent v0.21.3 (2026.9.14) · upstream 6d712cf8\n"


#: The release's python:3.12-slim pin by its multi-platform index digest.
PYTHON_SLIM = (
    "python:3.12-slim@sha256:"
    "2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9"
)


def skill2env_task(parent: Path) -> Path:
    """A local reconciliation task using pinned Skill2Env/Harbor serialization.

    The source identity is synthetic; no actual contributor Skill is selected.
    The recipe builds offline from the release's allow-listed base image.
    """
    task = parent / "task_reconcile_1234abcd"
    for directory in ("environment", "tests", "solution"):
        (task / directory).mkdir(parents=True)
    (task / "task.toml").write_text(
        'schema_version = "1.3"\nartifacts = ["/app/result.txt"]\n\n'
        '[task]\nname = "skill2env/task_reconcile_1234abcd"\n'
        'description = "Sum the supplied amounts."\nkeywords = ["reconcile"]\n'
        '[[task.authors]]\nname = "skill2env"\n\n'
        '[metadata]\nsource_skill = "local/reconcile"\n'
        f'source_bundle_digest = "{"a" * 64}"\n'
        "[metadata.base_image_pins]\n"
        f'"python:3.12-slim" = "{PYTHON_SLIM.split("@")[1]}"\n\n'
        '[verifier]\nnetwork_mode = "no-network"\nallowed_hosts = []\n'
        "timeout_sec = 600.0\ncollect = []\n[verifier.env]\n\n"
        '[agent]\nnetwork_mode = "no-network"\nallowed_hosts = []\n'
        "timeout_sec = 1800.0\n\n"
        '[environment]\nnetwork_mode = "no-network"\nallowed_hosts = []\n'
        'build_timeout_sec = 1200.0\nos = "linux"\ncpus = 2\n'
        "memory_mb = 4096\nstorage_mb = 4096\nmcp_servers = []\n"
        "[environment.env]\n\n[solution.env]\n",
        encoding="utf-8",
    )
    (task / "instruction.md").write_text(
        "Sum /app/amounts.txt and write the integer to /app/result.txt.\n",
        encoding="utf-8",
    )
    (task / "environment" / "Dockerfile").write_text(
        f"FROM {PYTHON_SLIM}\n"
        "WORKDIR /app\nCOPY amounts.txt /app/amounts.txt\n"
        "RUN printf 'ready' \\\n    > /app/ready.txt\n",
        encoding="utf-8",
    )
    (task / "environment" / "amounts.txt").write_bytes(b"2\n3\n")
    (task / "tests" / "rubric.md").write_text(
        "The result equals the sum of the supplied amounts.\n", encoding="utf-8"
    )
    for relative, script in {
        "solution/solve.sh": "#!/bin/sh\nprintf '5\\n' > /app/result.txt\n",
        "tests/test.sh": "#!/bin/sh\nmkdir -p /logs/verifier\n"
        'if [ "$(cat /app/result.txt 2>/dev/null)" = 5 ]; then\n'
        "  echo 1 > /logs/verifier/reward.txt\nelse\n"
        "  echo 0 > /logs/verifier/reward.txt\nfi\n",
    }.items():
        path = task / relative
        path.write_text(script, encoding="utf-8")
        path.chmod(0o700)
    return task


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
        schema_version="techtree.forge-build.v1alpha3",
        build_id=build_id,
        created_at=now,
        source=ForgeRepositorySource(
            kind="repository",
            repository="/repo/demo",
            head_commit=BASE_COMMIT,
            slug="demo",
            language=ForgeLanguage.PYTHON,
            dockerfile_digest=sha256_digest_bytes(b"FROM scratch\n"),
            test_commands=["uv run pytest"],
            limit=1,
            bootstrap_image_tag="techtree-forge/demo:bootstrap",
            bootstrap_image_id="sha256:" + "cd" * 32,
            repo2rlenv_version="0.0.0",
            generation=GenerationSummary(
                candidates=1, emitted=1, skipped=0, skip_reasons={}, tasks=[TASK_ID]
            ),
        ),
        platform="linux/arm64",
        task_set=task_set,
    )
    qualification = ForgeQualification(
        schema_version="techtree.forge-qualification.v1alpha3",
        build_id=build_id,
        membership_digest=task_set.membership_digest,
        qualified_at=now,
        model_calls=0,
        tasks=[
            RepositoryTaskQualification(
                kind="repository",
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


def skill_build(home: Path) -> ForgeBuildRecord:
    """Persist an unqualified Skill package with no repository task metadata."""
    paths = paths_from_root(home)
    build_id = "build_" + "2" * 32
    directory = paths.forge_build_dir(build_id)
    task = directory / "tasks" / "reconcile-ledger"
    task.mkdir(parents=True)
    (task / "instruction.md").write_text("Reconcile the supplied ledger.\n")
    snapshot = b"Check every ledger entry against its receipt.\n"
    (directory / "source-skill.md").write_bytes(snapshot)
    build = ForgeBuildRecord(
        schema_version="techtree.forge-build.v1alpha3",
        build_id=build_id,
        created_at=datetime.now(UTC),
        source=ForgeSkillSource(
            kind="skill",
            source_skill_digest=sha256_digest_bytes(snapshot),
            recipe="ledger-reconciliation",
            recipe_version="fixture-v1",
            producer="fixture-importer",
            producer_version="fixture-v1",
            upstream_url="https://example.org/fixture-producer",
            upstream_revision="a" * 40,
            harbor_version="fixture-v1",
            base_images=[
                ForgeBaseImage(
                    reference="fixture/base@sha256:" + "e" * 64,
                    image_id="sha256:" + "ef" * 32,
                )
            ],
        ),
        platform="linux/arm64",
        task_set=commit_task_set(directory / "tasks", [task.name]),
    )
    atomic_write_json(directory / "build.json", build.model_dump(mode="json"))
    return build


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
    ``"timeout"`` for a test run that hangs; ``reference_reward`` is the same
    for the tests after the reference solution, which may also be
    ``"solution_timeout"`` for a ``solve.sh`` that hangs or
    ``"solution_fails"`` for one that exits 2. ``start_error`` is the stderr
    of a container that will not start. ``verifier_output``
    is how many extra bytes the tests leave beside the reward;
    ``verifier_link`` makes them leave a link to a directory and
    ``verifier_unreadable`` a directory nobody may read. ``material_present``
    makes the image probe find verifier material. ``export_error`` makes the
    workspace export fail the way a missing image would; ``build_error`` and
    ``pull_error`` are the stderr of an image build or a base pull that fails.
    ``left_behind`` is what ``docker ps`` lists for any label filter: the
    stopped containers
    Hermes leaves on the daemon. The one ``hermes`` command that comes through
    here is the sign-in question, answered from ``signed_in``. ``timeouts``
    holds the deadline of every command run in a container, in order.
    """

    reward: float | str | None = 1.0
    reference_reward: float | str | None = 1.0
    verifier_output: int = 0
    verifier_link: bool = False
    verifier_unreadable: bool = False
    material_present: bool = False
    patch: str = "diff --git a/x b/x\n"
    export_error: bool = False
    build_error: str | None = None
    start_error: str | None = None
    pull_error: str | None = None
    left_behind: list[str] = field(default_factory=list)
    signed_in: bool = True
    calls: list[list[str]] = field(default_factory=list)
    timeouts: list[float] = field(default_factory=list)
    started: dict[str, list[str]] = field(default_factory=dict)

    def __call__(
        self, argv: Sequence[str], timeout: float
    ) -> subprocess.CompletedProcess[str]:
        command = list(argv)
        self.calls.append(command)
        if command[1:5] == ["-p", "techtree", "auth", "status"]:
            state = "logged in" if self.signed_in else "logged out (no credentials)"
            return _done(command, f"{command[5]}: {state}\n")
        match command[:2]:
            case ["docker", "version"]:
                return _done(command, "linux/arm64\n")
            case ["docker", "pull"]:
                if self.pull_error is not None:
                    return subprocess.CompletedProcess(command, 1, "", self.pull_error)
                return _done(command, f"{command[-1]}\n")
            case ["docker", "image"]:
                return _done(command, "sha256:" + command[3].encode().hex()[:64] + "\n")
            case ["docker", "build"]:
                if self.build_error is not None:
                    return subprocess.CompletedProcess(command, 1, "", self.build_error)
                return _done(command)
            case ["docker", "ps"]:
                return _done(command, "".join(f"{c}\n" for c in self.left_behind))
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
            case ["docker", "run"] if command[2] == "--detach":
                if self.start_error is not None:
                    return subprocess.CompletedProcess(
                        command, 125, "", self.start_error
                    )
                name = command[command.index("--name") + 1]
                self.started[name] = command
                return _done(command, f"{name}\n")
            case ["docker", "run"]:
                return self._run(command, timeout)
            case ["docker", "exec"]:
                return self._exec(command, timeout)
        raise AssertionError(f"unexpected docker command {command}")

    def _run(
        self, command: list[str], timeout: float
    ) -> subprocess.CompletedProcess[str]:
        script = command[-1]
        self.timeouts.append(timeout)
        if "git diff --cached" in script:
            return _done(command, self.patch)
        if script.startswith("test ! -e /tests"):
            found = int(self.material_present)
            return subprocess.CompletedProcess(command, found, "", "")
        if "bash /solution/solve.sh" in script:
            return self._graded(command, command, self.reference_reward)
        assert script == "bash /tests/test.sh", script
        assert not any(":/solution" in part for part in command), (
            "the reference solution reached a grading container"
        )
        return self._graded(command, command, self.reward)

    def _exec(
        self, command: list[str], timeout: float
    ) -> subprocess.CompletedProcess[str]:
        """A step of the reference run, in the container ``start`` named."""
        self.timeouts.append(timeout)
        container = self.started[command[2]]
        match command[3:]:
            case ["bash", "/solution/solve.sh"]:
                if self.reference_reward == "solution_timeout":
                    raise _timeout("solving\n")
                if self.reference_reward == "solution_fails":
                    return subprocess.CompletedProcess(command, 2, "", "no such file\n")
                return _done(command)
            case ["bash", "/tests/test.sh"]:
                return self._graded(command, container, self.reference_reward)
        raise AssertionError(f"unexpected docker exec {command}")

    def _graded(
        self, command: list[str], container: list[str], reward: float | str | None
    ) -> subprocess.CompletedProcess[str]:
        """What the tests leave in the verifier directory ``container`` mounts."""
        verifier = next(
            Path(part.removesuffix(":/logs/verifier"))
            for part in container
            if part.endswith(":/logs/verifier")
        )
        if reward == "timeout":
            raise _timeout("testing\n")
        if reward is not None:
            (verifier / "reward.txt").write_text(f"{reward}\n", encoding="utf-8")
        if self.verifier_output:
            (verifier / "output.log").write_bytes(b"x" * self.verifier_output)
        if self.verifier_link:
            (verifier / "elsewhere").symlink_to("/", target_is_directory=True)
        if self.verifier_unreadable:
            (verifier / "sealed").mkdir()
            (verifier / "sealed").chmod(0)
        return _done(command)

    def graded(self) -> bool:
        return any(call[-1] == "bash /tests/test.sh" for call in self.calls)


def signed_in_profile(profiles: Path) -> Path:
    """Make the ``techtree`` Hermes profile a person created and signed in."""
    profile = profiles / "techtree"
    profile.mkdir(parents=True)
    (profile / "auth.json").write_text("{}", encoding="utf-8")
    return profile


def _done(command: list[str], stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(command, 0, stdout, "")


def _timeout(printed: str) -> RunError:
    """The error ``run_command`` raises for a command still printing at its limit."""
    return RunError(
        "hung",
        code="forge_command_timeout",
        details={"stdout": printed, "stderr": ""},
    )


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
