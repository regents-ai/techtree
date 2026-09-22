"""Model-free qualification of emitted tasks. ``docs/plan/repo2rlenv-local-lane.md``.

Repo2RLEnv validated each task in a long-lived sandbox while it generated it.
Qualification repeats the two decisive observations from a fresh container of
the task's own image, the way a later evaluation will run it, and adds what a
generator has no reason to check about itself:

- the task image builds, and its workspace sits clean at the task's base
  commit;
- the image carries none of the verifier material (``/tests``, ``/solution``);
- the task names at least one fail-to-pass test;
- an unrepaired container scores ``0.0`` with every fail-to-pass test failing;
- a container with the reference patch applied scores ``1.0`` and is resolved.

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
from typing import Final

from techtree.errors import RunError
from techtree.forge.content import verify_task_set
from techtree.forge.docker import Docker, Mount
from techtree.forge.models import (
    FORGE_QUALIFICATION_SCHEMA_VERSION,
    ForgeBuildRecord,
    ForgePlatform,
    ForgeQualification,
    QualificationCheck,
    TaskQualification,
)
from techtree.fs import ensure_private_directory
from techtree.models.base import Digest

__all__ = [
    "TIMED_OUT_DETAIL",
    "TaskFacts",
    "Verdict",
    "build_task_image",
    "grade_task",
    "qualify_build",
    "read_task_facts",
    "task_image_tag",
]

#: Added to the task's own verifier timeout: container start and image load.
_RUN_MARGIN_SECONDS: Final = 120.0
_PROBE_TIMEOUT_SECONDS: Final = 120.0
#: The detail of a check whose verifier run hung; the CLI names it in words.
TIMED_OUT_DETAIL: Final = "the tests did not finish within the task's own timeout"
#: A reward file is a number or a small JSON document; anything larger is not
#: a verdict.
_REWARD_FILE_LIMIT: Final = 64 * 1024


@dataclass(frozen=True)
class TaskFacts:
    """What a task's ``task.toml`` says about itself."""

    base_commit: str
    fail_to_pass: list[str]
    pass_to_pass: list[str]
    agent_timeout: float
    verifier_timeout: float


@dataclass(frozen=True)
class Verdict:
    """The reward files one graded run left."""

    reward: float | None
    details: dict[str, object]


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
    """Qualify every task the build emitted and say which proved out."""
    build.require_repository_source("Repository qualification")
    verify_task_set(tasks_dir, build.task_set)
    ensure_private_directory(work_dir)
    tasks = []
    for task in build.task_set.tasks:
        if on_task is not None:
            on_task(task.task_id, None)
        result = _qualify_task(
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


def _qualify_task(
    docker: Docker,
    build: ForgeBuildRecord,
    task_dir: Path,
    work_dir: Path,
    content_digest: Digest,
) -> TaskQualification:
    task_id = task_dir.name
    facts = read_task_facts(task_dir)
    tag = task_image_tag(build, task_id)
    checks: list[QualificationCheck] = []
    control_reward: float | None = None
    reference_reward: float | None = None

    image_id = ""
    try:
        image_id = build_task_image(docker, build, task_dir, work_dir)
        checks.append(
            QualificationCheck(name="image_build", passed=True, detail=image_id)
        )
    except RunError as error:
        checks.append(
            QualificationCheck(name="image_build", passed=False, detail=str(error))
        )

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
            facts,
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
            facts,
            reference=True,
        )
        reference_reward = reference.reward
        checks.append(_reference_check(reference))

    return TaskQualification(
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


def read_task_facts(task_dir: Path) -> TaskFacts:
    """Read what one task's ``task.toml`` commits to."""
    document = tomllib.loads((task_dir / "task.toml").read_text(encoding="utf-8"))
    runtime = document["metadata"]["repo2env"]["commit_runtime"]
    return TaskFacts(
        base_commit=str(runtime["parent_sha"]),
        fail_to_pass=[str(name) for name in runtime["fail_to_pass"]],
        pass_to_pass=[str(name) for name in runtime["pass_to_pass"]],
        agent_timeout=float(document["agent"]["timeout_sec"]),
        verifier_timeout=float(document["verifier"]["timeout_sec"]),
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
    facts: TaskFacts,
    *,
    reference: bool,
    workspace: Path | None = None,
) -> Verdict:
    """Run the task's own test script once and read the verdict it leaves.

    Qualification grades the image's own workspace, unrepaired or with the
    reference patch applied; a forge run grades an agent's ``workspace``,
    mounted over the image's at ``/workspace``. Every container here runs
    from the image's content id, never its tag, so the run graded is the
    image this build made. The tests write into ``run_dir/verifier`` and
    nowhere else on the host; the transcript is kept beside it, where they
    cannot reach.
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
        timeout=facts.verifier_timeout + _RUN_MARGIN_SECONDS,
    )
    (run_dir / "container.log").write_text(
        f"exit {outcome.exit_code}, timed out {outcome.timed_out}\n"
        f"{outcome.stdout}\n{outcome.stderr}",
        encoding="utf-8",
    )
    # A run that did not finish has no verdict, whatever it wrote before it hung.
    if outcome.timed_out:
        return Verdict(reward=None, details={"timed_out": True})
    return _read_verdict(verifier_dir)


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
        if verdict.details.get("timed_out")
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
        if verdict.details.get("timed_out")
        else f"reward {verdict.reward}, resolved {resolved}",
    )
