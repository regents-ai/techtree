"""Model-free qualification of committed tasks. ``docs/plan/repo2rlenv-local-lane.md``.

Both producers enter one committed task package, and one profile qualifies
it from a fresh container of the task's own image, the way a later
evaluation will run it. The checks every task gets:

- the task package still hashes to its commitment, before and after;
- the task image builds offline from exactly its ``environment/`` tree;
- the image carries none of the verifier material (``/tests``, ``/solution``);
- a run that does nothing scores ``0.0``;
- a run of the reference scores ``1.0``.

A repository task adds what Repo2RLEnv committed to: its workspace sits
clean at the base commit, at least one fail-to-pass test is named, and the
graded details agree with those names. A Skill task adds what an imported
package can hide: no file of ``tests/`` or ``solution/`` appears in the
instruction or the environment, and the verifier's output stays bounded. It
also adds its recipe cases (R31): the package's other correct solution,
``solution/alternative.sh``, must pass the tests as the reference does, and
its deliberately wrong one, ``solution/wrong.sh``, must finish and fail them,
so tests that accept only one way of working, or any answer shaped like the
right one, are caught here.

Grading follows the procedure Verifiers applies to a Harbor task: the task's
``tests/`` directory is mounted at ``/tests``, ``bash /tests/test.sh`` runs,
and the verdict is the reward file it leaves under ``/logs/verifier``. Nothing
in this module calls a model.
"""

from __future__ import annotations

import json
import os
import stat
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

from techtree.errors import RunError
from techtree.forge.content import verify_task_set
from techtree.forge.docker import Docker, Mount
from techtree.forge.models import (
    FORGE_QUALIFICATION_SCHEMA_VERSION,
    ForgeBuildRecord,
    ForgePlatform,
    ForgeQualification,
    QualificationCheck,
    RepositoryTaskQualification,
    SkillTaskQualification,
    TaskQualification,
)
from techtree.fs import ensure_private_directory
from techtree.models.base import Digest

__all__ = [
    "NOT_STARTED_DETAIL",
    "SOLUTION_FAILED_DETAIL",
    "SOLUTION_TIMED_OUT_DETAIL",
    "TIMED_OUT_DETAIL",
    "TaskFacts",
    "Verdict",
    "build_task_image",
    "grade_reference_solution",
    "grade_task",
    "qualify_build",
    "read_task_facts",
    "task_image_tag",
]

#: Added to the task's own time limit: container start and image load.
_RUN_MARGIN_SECONDS: Final = 120.0
#: Added to each step's own time limit in a started container: the step is
#: already running in it, so only ``docker exec`` itself needs the room.
_STEP_GRACE_SECONDS: Final = 10.0
_PROBE_TIMEOUT_SECONDS: Final = 120.0
#: The detail of a check whose verifier run hung; the CLI names it in words.
TIMED_OUT_DETAIL: Final = "the tests did not finish within the task's own timeout"
#: The detail of a Skill reference run whose solution used up the agent's time.
SOLUTION_TIMED_OUT_DETAIL: Final = (
    "the reference solution did not finish within the task's own agent timeout"
)
#: The detail of a Skill reference run whose solution ended in an error.
SOLUTION_FAILED_DETAIL: Final = (
    "the reference solution stopped with an error, so the tests did not run"
)
#: The detail of a Skill reference run whose container never started.
NOT_STARTED_DETAIL: Final = (
    "the task's image could not be started for the reference solution"
)
#: A reward file is a number or a small JSON document; anything larger is not
#: a verdict.
_REWARD_FILE_LIMIT: Final = 64 * 1024
#: Everything the tests leave under ``/logs/verifier`` across both graded runs
#: of a Skill task fits in these; a verifier that leaves more is not qualified.
_VERIFIER_OUTPUT_LIMIT: Final = 1024 * 1024
_VERIFIER_OUTPUT_ENTRIES: Final = 1024


@dataclass(frozen=True)
class TaskFacts:
    """What a repository task's ``task.toml`` says about itself."""

    base_commit: str
    fail_to_pass: list[str]
    pass_to_pass: list[str]
    agent_timeout: float
    verifier_timeout: float


@dataclass(frozen=True)
class SkillTaskFacts:
    """The time limits a Skill task's ``task.toml`` commits to."""

    agent_timeout: float
    verifier_timeout: float


#: Why a graded run left no verdict to read.
type Stop = Literal[
    "tests_timed_out", "solution_timed_out", "solution_failed", "not_started"
]

_STOP_DETAILS: Final[dict[Stop, str]] = {
    "tests_timed_out": TIMED_OUT_DETAIL,
    "solution_timed_out": SOLUTION_TIMED_OUT_DETAIL,
    "solution_failed": SOLUTION_FAILED_DETAIL,
    "not_started": NOT_STARTED_DETAIL,
}


@dataclass(frozen=True)
class Verdict:
    """The reward files one graded run left, or why it left none.

    ``details`` is what the tests wrote; ``stopped`` is set here, by the host,
    and nothing the tests write can set it.
    """

    reward: float | None
    details: dict[str, object]
    stopped: Stop | None = None


def task_image_tag(build: ForgeBuildRecord, task_id: str) -> str:
    """Return a tag no other build shares, under the producer's own name."""
    source = build.source
    namespace = source.slug if source.kind == "repository" else source.recipe
    return f"techtree-forge/{namespace}/{task_id.lower()}:{build.build_id[-12:]}"


def build_task_image(
    docker: Docker, build: ForgeBuildRecord, task_dir: Path, work_dir: Path
) -> str:
    """Build one task's image offline from exactly its ``environment/`` tree.

    The context is the committed directory and nothing else. The network is
    disabled for every ``RUN`` step, so a recipe that fetches fails here with
    its log retained at ``work_dir/image-build.log``; the base images come
    from the daemon's store, pulled by digest when the build was imported.
    """
    ensure_private_directory(work_dir)
    return docker.build(
        context=task_dir / "environment",
        dockerfile=task_dir / "environment" / "Dockerfile",
        tag=task_image_tag(build, task_dir.name),
        platform=build.platform,
        offline=True,
        log=work_dir / "image-build.log",
    )


def qualify_build(
    *,
    docker: Docker,
    build: ForgeBuildRecord,
    tasks_dir: Path,
    work_dir: Path,
    on_task: Callable[[str, TaskQualification | None], None] | None = None,
) -> ForgeQualification:
    """Qualify every task the build committed and say which proved out."""
    verify_task_set(tasks_dir, build.task_set)
    ensure_private_directory(work_dir)
    qualify_task = (
        _qualify_repository_task
        if build.source.kind == "repository"
        else _qualify_skill_task
    )
    tasks: list[TaskQualification] = []
    for task in build.task_set.tasks:
        if on_task is not None:
            on_task(task.task_id, None)
        result = qualify_task(
            docker,
            build,
            tasks_dir / task.task_id,
            work_dir / task.task_id,
            task.content_digest,
        )
        tasks.append(result)
        if on_task is not None:
            on_task(task.task_id, result)
    verify_task_set(tasks_dir, build.task_set)
    return ForgeQualification(
        schema_version=FORGE_QUALIFICATION_SCHEMA_VERSION,
        build_id=build.build_id,
        membership_digest=build.task_set.membership_digest,
        qualified_at=datetime.now(UTC),
        model_calls=0,
        tasks=tasks,
        qualified_task_ids=[task.task_id for task in tasks if task.qualified],
    )


def _image_build_check(
    docker: Docker, build: ForgeBuildRecord, task_dir: Path, work_dir: Path
) -> tuple[str, QualificationCheck]:
    """Build the task image; the id is empty when the build failed."""
    try:
        image_id = build_task_image(docker, build, task_dir, work_dir)
    except RunError as error:
        failed = QualificationCheck(name="image_build", passed=False, detail=str(error))
        return "", failed
    return image_id, QualificationCheck(
        name="image_build", passed=True, detail=image_id
    )


def _qualify_repository_task(
    docker: Docker,
    build: ForgeBuildRecord,
    task_dir: Path,
    work_dir: Path,
    content_digest: Digest,
) -> RepositoryTaskQualification:
    task_id = task_dir.name
    facts = read_task_facts(task_dir)
    tag = task_image_tag(build, task_id)
    control_reward: float | None = None
    reference_reward: float | None = None

    image_id, built = _image_build_check(docker, build, task_dir, work_dir)
    checks = [built]
    if image_id:
        checks.append(_workspace_check(docker, build, image_id, facts))
        checks.append(_material_check(docker, build, image_id))
        checks.append(
            QualificationCheck(
                name="tests_recognized",
                passed=bool(facts.fail_to_pass),
                detail=(
                    f"{len(facts.fail_to_pass)} fail-to-pass, "
                    f"{len(facts.pass_to_pass)} pass-to-pass"
                ),
            )
        )
        control = grade_task(
            docker,
            build.platform,
            image_id,
            task_dir,
            work_dir / "control",
            time_limit=facts.verifier_timeout,
            reference=False,
        )
        control_reward = control.reward
        checks.append(_control_check(control, facts))
        reference = grade_task(
            docker,
            build.platform,
            image_id,
            task_dir,
            work_dir / "reference",
            time_limit=facts.verifier_timeout,
            reference=True,
        )
        reference_reward = reference.reward
        checks.append(_reference_check(reference))

    return RepositoryTaskQualification(
        kind="repository",
        task_id=task_id,
        task_content_digest=content_digest,
        image_tag=tag,
        image_id=image_id,
        base_commit=facts.base_commit,
        fail_to_pass=len(facts.fail_to_pass),
        pass_to_pass=len(facts.pass_to_pass),
        control_reward=control_reward,
        reference_reward=reference_reward,
        checks=checks,
        qualified=all(check.passed for check in checks),
    )


def _qualify_skill_task(
    docker: Docker,
    build: ForgeBuildRecord,
    task_dir: Path,
    work_dir: Path,
    content_digest: Digest,
) -> SkillTaskQualification:
    """Qualify one imported package.

    The run that does nothing is graded with the task's verifier time; the
    reference run executes ``solution/solve.sh`` with the agent's time and
    then the tests with the verifier's, each bounded on its own, both times
    from the pinned ``task.toml``.
    """
    task_id = task_dir.name
    facts = read_skill_task_facts(task_dir)
    tag = task_image_tag(build, task_id)
    control_reward: float | None = None
    reference_reward: float | None = None
    alternative_reward: float | None = None
    wrong_reward: float | None = None

    checks = [_hidden_material_check(task_dir)]
    image_id, built = _image_build_check(docker, build, task_dir, work_dir)
    checks.append(built)
    if image_id:
        checks.append(_material_check(docker, build, image_id))
        control = grade_task(
            docker,
            build.platform,
            image_id,
            task_dir,
            work_dir / "control",
            time_limit=facts.verifier_timeout,
            reference=False,
        )
        control_reward = control.reward
        checks.append(
            QualificationCheck(
                name="no_op_fails",
                passed=control.reward == 0.0,
                detail=_STOP_DETAILS[control.stopped]
                if control.stopped
                else f"{_reward_words(control.reward)} with nothing done",
            )
        )
        graded = {
            case: grade_reference_solution(
                docker,
                build.platform,
                image_id,
                task_dir,
                work_dir / case,
                script=f"/solution/{script}",
                solution_time_limit=facts.agent_timeout,
                tests_time_limit=facts.verifier_timeout,
            )
            for case, script in _SOLUTIONS.items()
        }
        reference_reward = graded["reference"].reward
        alternative_reward = graded["alternative"].reward
        wrong_reward = graded["wrong"].reward
        checks.append(_reference_solution_check(graded["reference"]))
        checks.append(
            _case_check(
                "alternative_solution_passes",
                "the other correct solution",
                graded["alternative"],
                expected=1.0,
            )
        )
        checks.append(
            _case_check(
                "wrong_solution_fails",
                "the deliberately wrong solution",
                graded["wrong"],
                expected=0.0,
            )
        )
        checks.append(
            _verifier_output_check(
                [work_dir / run / "verifier" for run in ("control", *_SOLUTIONS)]
            )
        )

    return SkillTaskQualification(
        kind="skill",
        task_id=task_id,
        task_content_digest=content_digest,
        image_tag=tag,
        image_id=image_id,
        control_reward=control_reward,
        reference_reward=reference_reward,
        alternative_reward=alternative_reward,
        wrong_reward=wrong_reward,
        checks=checks,
        qualified=all(check.passed for check in checks),
    )


#: Each graded solution of a Skill task, by the run it is kept under.
_SOLUTIONS: Final = {
    "reference": "solve.sh",
    "alternative": "alternative.sh",
    "wrong": "wrong.sh",
}

#: Why a recipe case left no verdict, said of the solution it ran.
_CASE_STOP_WORDS: Final[dict[Stop, str]] = {
    "tests_timed_out": "the tests did not finish within the task's own timeout "
    "after {solution}",
    "solution_timed_out": "{solution} did not finish within the task's own agent "
    "timeout",
    "solution_failed": "{solution} stopped with an error, so the tests did not run",
    "not_started": "the task's image could not be started for {solution}",
}


def _case_check(
    name: str, solution: str, verdict: Verdict, *, expected: float
) -> QualificationCheck:
    """A recipe case passes when its solution ran and the tests gave ``expected``."""
    return QualificationCheck(
        name=name,
        passed=verdict.stopped is None and verdict.reward == expected,
        detail=_CASE_STOP_WORDS[verdict.stopped].format(solution=solution)
        if verdict.stopped
        else f"{_reward_words(verdict.reward)} after {solution}",
    )


def read_task_facts(task_dir: Path) -> TaskFacts:
    """Read what one repository task's ``task.toml`` commits to."""
    document = tomllib.loads((task_dir / "task.toml").read_text(encoding="utf-8"))
    runtime = document["metadata"]["repo2env"]["commit_runtime"]
    return TaskFacts(
        base_commit=str(runtime["parent_sha"]),
        fail_to_pass=[str(name) for name in runtime["fail_to_pass"]],
        pass_to_pass=[str(name) for name in runtime["pass_to_pass"]],
        agent_timeout=float(document["agent"]["timeout_sec"]),
        verifier_timeout=float(document["verifier"]["timeout_sec"]),
    )


def _reference_solution_check(verdict: Verdict) -> QualificationCheck:
    return QualificationCheck(
        name="reference_solution_passes",
        passed=verdict.reward == 1.0,
        detail=_STOP_DETAILS[verdict.stopped]
        if verdict.stopped
        else f"{_reward_words(verdict.reward)} after the reference solution",
    )


def _reward_words(reward: float | None) -> str:
    return "no reward" if reward is None else f"reward {reward}"


def read_skill_task_facts(task_dir: Path) -> SkillTaskFacts:
    """Read the time limits one Skill task's ``task.toml`` commits to."""
    document = tomllib.loads((task_dir / "task.toml").read_text(encoding="utf-8"))
    return SkillTaskFacts(
        agent_timeout=float(document["agent"]["timeout_sec"]),
        verifier_timeout=float(document["verifier"]["timeout_sec"]),
    )


def _hidden_material_check(task_dir: Path) -> QualificationCheck:
    """No file of ``tests/`` or ``solution/`` appears in what the subject sees.

    The subject sees the instruction and the ``environment/`` tree, and the
    image is built offline from that tree alone, so a hidden file whose bytes
    are inside neither cannot reach the subject. The package was committed
    from regular files only, so every path here is a regular file. A file
    that is empty or only whitespace says nothing and is not looked for; a
    very short one can match ordinary text, and the check says where.
    """
    hidden = [
        path
        for root in ("tests", "solution")
        for path in sorted((task_dir / root).rglob("*"))
        if path.is_file()
    ]
    visible = {
        path: path.read_bytes()
        for path in [
            task_dir / "instruction.md",
            *sorted(
                path for path in (task_dir / "environment").rglob("*") if path.is_file()
            ),
        ]
    }
    leaks = [
        f"{secret.relative_to(task_dir)} inside {seen.relative_to(task_dir)}"
        for secret in hidden
        if (data := secret.read_bytes()).strip()
        for seen, seen_bytes in visible.items()
        if data in seen_bytes
    ]
    return QualificationCheck(
        name="hidden_material_private",
        passed=not leaks,
        detail=", ".join(leaks)
        if leaks
        else "no tests or solution file appears in the instruction or environment",
    )


def _verifier_output_check(verifier_dirs: list[Path]) -> QualificationCheck:
    """The tests left regular files only, within the output limits, in total.

    Nothing is followed: a link, even one to a directory, is not a regular
    file, and anything the walk cannot read fails the check.
    """
    total = 0
    entries = 0
    irregular: list[str] = []
    for verifier_dir in verifier_dirs:
        unreadable: list[OSError] = []
        for directory, subdirectories, names in os.walk(
            verifier_dir, onerror=unreadable.append, followlinks=False
        ):
            for name in [*subdirectories, *names]:
                path = Path(directory) / name
                entries += 1
                try:
                    status = os.lstat(path)
                except OSError as error:
                    unreadable.append(error)
                    continue
                if stat.S_ISREG(status.st_mode):
                    total += status.st_size
                elif not stat.S_ISDIR(status.st_mode):
                    irregular.append(str(path.relative_to(verifier_dir)))
        irregular.extend(
            str(Path(error.filename).relative_to(verifier_dir)) for error in unreadable
        )
    passed = (
        not irregular
        and total <= _VERIFIER_OUTPUT_LIMIT
        and entries <= _VERIFIER_OUTPUT_ENTRIES
    )
    detail = f"{total} bytes across {entries} entries"
    if irregular:
        detail += f"; not regular files: {', '.join(irregular)}"
    return QualificationCheck(
        name="verifier_output_bounded", passed=passed, detail=detail
    )


def _workspace_check(
    docker: Docker, build: ForgeBuildRecord, image: str, facts: TaskFacts
) -> QualificationCheck:
    outcome = docker.run(
        image=image,
        platform=build.platform,
        argv=[
            "sh",
            "-c",
            "cd /workspace && git rev-parse HEAD && git status --porcelain",
        ],
        mounts=[],
        timeout=_PROBE_TIMEOUT_SECONDS,
    )
    lines = outcome.stdout.splitlines()
    head = lines[0].strip() if lines else ""
    dirty = [line for line in lines[1:] if line.strip()]
    passed = outcome.exit_code == 0 and head == facts.base_commit and not dirty
    detail = f"HEAD {head or '?'}, {len(dirty)} uncommitted paths"
    if outcome.exit_code != 0:
        detail = outcome.stderr.strip()[-300:] or f"exit {outcome.exit_code}"
    return QualificationCheck(
        name="workspace_at_base_commit", passed=passed, detail=detail
    )


def _material_check(
    docker: Docker, build: ForgeBuildRecord, image: str
) -> QualificationCheck:
    outcome = docker.run(
        image=image,
        platform=build.platform,
        argv=["sh", "-c", "test ! -e /tests && test ! -e /solution && test ! -e /logs"],
        mounts=[],
        timeout=_PROBE_TIMEOUT_SECONDS,
    )
    return QualificationCheck(
        name="verifier_material_absent",
        passed=outcome.exit_code == 0,
        detail="the image holds no /tests, /solution or /logs"
        if outcome.exit_code == 0
        else "the image already holds verifier material",
    )


def grade_task(
    docker: Docker,
    platform: ForgePlatform,
    image: str,
    task_dir: Path,
    run_dir: Path,
    *,
    time_limit: float,
    reference: bool,
    workspace: Path | None = None,
) -> Verdict:
    """Run the task's own test script once and read the verdict it leaves.

    Qualification grades the image's own workspace, unrepaired or with the
    reference applied; a forge run grades an agent's ``workspace``, mounted
    over the image's at ``/workspace``. ``time_limit`` is the task's own
    bound in seconds; the container gets it plus a fixed margin for starting.
    Every container here runs from the image's content id, never its tag, so
    the run graded is the image this build made. The tests write into
    ``run_dir/verifier`` and nowhere else on the host; the transcript is kept
    beside it, where they cannot reach.
    """
    ensure_private_directory(run_dir)
    verifier_dir = run_dir / "verifier"
    ensure_private_directory(verifier_dir)
    mounts = [Mount(source=task_dir / "tests", target="/tests", read_only=True)]
    script = "bash /tests/test.sh"
    if reference:
        mounts.append(
            Mount(source=task_dir / "solution", target="/solution", read_only=True)
        )
        script = "bash /solution/solve.sh && bash /tests/test.sh"
    if workspace is not None:
        mounts.append(Mount(source=workspace, target="/workspace", read_only=False))
    mounts.append(Mount(source=verifier_dir, target="/logs/verifier", read_only=False))

    outcome = docker.run(
        image=image,
        platform=platform,
        argv=["bash", "-c", script],
        mounts=mounts,
        timeout=time_limit + _RUN_MARGIN_SECONDS,
    )
    (run_dir / "container.log").write_text(
        f"exit {outcome.exit_code}, timed out {outcome.timed_out}\n"
        f"{outcome.stdout}\n{outcome.stderr}",
        encoding="utf-8",
    )
    # A run that did not finish has no verdict, whatever it wrote before it hung.
    if outcome.timed_out:
        return Verdict(reward=None, details={}, stopped="tests_timed_out")
    return _read_verdict(verifier_dir)


def grade_reference_solution(
    docker: Docker,
    platform: ForgePlatform,
    image: str,
    task_dir: Path,
    run_dir: Path,
    *,
    script: str,
    solution_time_limit: float,
    tests_time_limit: float,
) -> Verdict:
    """Run one of a Skill task's solutions, then its tests, and read the verdict.

    ``script`` is the solution's path in the container, under ``/solution``.

    Both run in one container started from the image, each by ``docker exec``
    under its own limit, and both limits are kept from the host: the image
    was built from the task's own recipe, so nothing inside it is trusted to
    keep time. A step still running at its limit ends with the container
    removed and leaves no verdict, and says which step it was; a solution
    that fails leaves no verdict either, since the tests never ran, and nor
    does an image that cannot be started.
    """
    ensure_private_directory(run_dir)
    verifier_dir = run_dir / "verifier"
    ensure_private_directory(verifier_dir)
    mounts = [
        Mount(source=task_dir / "tests", target="/tests", read_only=True),
        Mount(source=task_dir / "solution", target="/solution", read_only=True),
        Mount(source=verifier_dir, target="/logs/verifier", read_only=False),
    ]
    log: list[str] = []
    try:
        name = docker.start(image=image, platform=platform, mounts=mounts)
    except RunError as error:
        if error.code != "forge_container_unavailable":
            raise
        (run_dir / "container.log").write_text(
            f"{error}\n{error.details['removal']}\n", encoding="utf-8"
        )
        return Verdict(reward=None, details={}, stopped="not_started")
    try:
        verdict = _solve_then_test(
            docker, name, script, solution_time_limit, tests_time_limit, log
        )
    finally:
        log.append(docker.remove(name))
        (run_dir / "container.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    return _read_verdict(verifier_dir) if verdict is None else verdict


def _solve_then_test(
    docker: Docker,
    name: str,
    script: str,
    solution_time_limit: float,
    tests_time_limit: float,
    log: list[str],
) -> Verdict | None:
    """Why the run left no verdict, or ``None`` when both steps ran."""
    steps: tuple[tuple[str, str, float, Stop], ...] = (
        ("solution", script, solution_time_limit, "solution_timed_out"),
        ("tests", "/tests/test.sh", tests_time_limit, "tests_timed_out"),
    )
    for step, script, limit, out_of_time in steps:
        outcome = docker.exec(
            name, ["bash", script], timeout=limit + _STEP_GRACE_SECONDS
        )
        log.append(
            f"{step}: exit {outcome.exit_code}, timed out {outcome.timed_out}\n"
            f"{outcome.stdout}\n{outcome.stderr}"
        )
        if outcome.timed_out:
            return Verdict(reward=None, details={}, stopped=out_of_time)
        if step == "solution" and outcome.exit_code != 0:
            return Verdict(reward=None, details={}, stopped="solution_failed")
    return None


def _read_verdict(verifier_dir: Path) -> Verdict:
    """Read the reward the way Verifiers does: ``reward.json`` first, then text."""
    reward: float | None = None
    details: dict[str, object] = {}
    json_text = _reward_file(verifier_dir / "reward.json")
    text = _reward_file(verifier_dir / "reward.txt")
    details_text = _reward_file(verifier_dir / "reward-details.json")
    try:
        if json_text is not None:
            reward = float(json.loads(json_text)["reward"])
        elif text is not None:
            reward = float(text.strip())
        if details_text is not None:
            loaded = json.loads(details_text)
            if isinstance(loaded, dict):
                details = loaded
    except (KeyError, TypeError, ValueError):
        reward = None
    return Verdict(reward=reward, details=details)


def _reward_file(path: Path) -> str | None:
    """The text of a small regular file the tests left, or nothing.

    The tests wrote into this directory, so the name is followed no further
    than the file itself: a symlink, a directory, a pipe, an oversized or
    undecodable file is not a verdict. The open never waits on what it finds.
    """
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return None
    try:
        status = os.fstat(descriptor)
        if not stat.S_ISREG(status.st_mode) or status.st_size > _REWARD_FILE_LIMIT:
            return None
        return os.read(descriptor, _REWARD_FILE_LIMIT).decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    finally:
        os.close(descriptor)


def _control_check(verdict: Verdict, facts: TaskFacts) -> QualificationCheck:
    f2p_passed = verdict.details.get("f2p_passed")
    status = str(verdict.details.get("parse_status", "absent"))
    passed = (
        verdict.reward == 0.0
        and status != "test_patch_apply_failed"
        and f2p_passed == 0
        and verdict.details.get("f2p_total") == len(facts.fail_to_pass)
    )
    return QualificationCheck(
        name="control_fails",
        passed=passed,
        detail=TIMED_OUT_DETAIL
        if verdict.stopped == "tests_timed_out"
        else (
            f"reward {verdict.reward}, {f2p_passed} of {len(facts.fail_to_pass)} "
            f"fail-to-pass tests passed unrepaired, parse status {status}"
        ),
    )


def _reference_check(verdict: Verdict) -> QualificationCheck:
    resolved = verdict.details.get("resolved")
    passed = verdict.reward == 1.0 and resolved is True
    return QualificationCheck(
        name="reference_passes",
        passed=passed,
        detail=TIMED_OUT_DETAIL
        if verdict.stopped == "tests_timed_out"
        else f"reward {verdict.reward}, resolved {resolved}",
    )
