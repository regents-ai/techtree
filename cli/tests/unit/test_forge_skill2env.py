"""Admission binds provenance and exact bytes; qualification proves the package."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fixtures.forge.support import PYTHON_SLIM, FakeDocker, skill2env_task
from techtree.cli.app import create_app
from techtree.errors import RunError, ValidationError
from techtree.forge.content import commit_task_set, verify_task_set
from techtree.forge.docker import Docker
from techtree.forge.models import ForgeBuildRecord, ForgeQualification
from techtree.forge.qualify import build_task_image, qualify_build
from techtree.forge.report import first_failed_check, task_verdict
from techtree.forge.service import ForgeService, read_build_status
from techtree.forge.skill2env import (
    MAX_TASK_BYTES,
    Skill2EnvAdmission,
    admit_skill2env_task,
)
from techtree.paths import paths_from_root

SOURCE_DIGEST = "sha256:" + "a" * 64
AMD64_SLIM = (
    "python:3.12-slim@sha256:"
    "44ff437bba879d4941b710a369a8f19266aea34b29002807f0c487fabc9eec9b"
)
#: The deadlines the checks get: the material probe, the run that does nothing
#: (verifier time plus margin), then each step of the reference run (its own
#: time plus grace), kept on the host.
PROBE_BOUND = 120.0
NO_OP_BOUND = 600.0 + 120.0
SOLUTION_BOUND = 1800.0 + 10.0
TESTS_BOUND = 600.0 + 10.0


def admit(task: Path, destination: Path) -> Skill2EnvAdmission:
    return admit_skill2env_task(
        task,
        build_dir=destination,
        expected_source_skill="local/reconcile",
        expected_source_digest=SOURCE_DIGEST,
        platform="linux/arm64",
    )


def import_task(task: Path, home: Path, docker: FakeDocker) -> ForgeBuildRecord:
    service = ForgeService(paths_from_root(home), docker, Path("/fake/uv"))
    status = service.import_skill(
        task_dir=task, source_skill="local/reconcile", source_digest=SOURCE_DIGEST
    )
    assert status.build is not None
    return status.build


def mounts(call: list[str]) -> list[str]:
    return [call[index + 1] for index, part in enumerate(call) if part == "--volume"]


def test_import_commits_exact_bytes_and_qualifies_the_task_offline(
    tmp_path: Path,
) -> None:
    task = skill2env_task(tmp_path / "upstream")
    original = commit_task_set(task.parent, [task.name])
    docker = FakeDocker(reward=0.0, reference_reward=1.0)
    record = import_task(task, tmp_path / "home", docker)
    paths = paths_from_root(tmp_path / "home")
    build_dir = paths.forge_build_dir(record.build_id)
    task_dir = build_dir / "tasks" / task.name
    assert record.task_set == original
    verify_task_set(build_dir / "tasks", record.task_set)
    saved = json.loads((build_dir / "build.json").read_bytes())
    assert saved["source"]["source_skill_digest"] == SOURCE_DIGEST
    assert (
        saved["source"]["upstream_revision"]
        == "9beb0b64a70290f862c8374bbef21f2ac88992ab"
    )
    assert [image["reference"] for image in saved["source"]["base_images"]] == [
        PYTHON_SLIM
    ]
    assert "repository" not in saved["source"] and "head_commit" not in saved["source"]

    commands = [call[1] for call in docker.calls if call[1] != "version"]
    assert commands == [
        "pull",
        "image",
        "build",
        "image",
        "run",
        "run",
        "run",
        "exec",
        "exec",
        "rm",
    ]
    assert docker.calls[1] == [
        "docker",
        "pull",
        "--quiet",
        "--platform",
        "linux/arm64",
        PYTHON_SLIM,
    ]
    build_call = next(call for call in docker.calls if call[1] == "build")
    assert build_call[4:6] == ["--network", "none"]
    assert build_call[-1] == str(task_dir / "environment")
    probe, no_op, reference = [call for call in docker.calls if call[1] == "run"]
    assert probe[-1].startswith("test ! -e /tests") and mounts(probe) == []
    assert reference[2] == "--detach" and reference[-2:] == ["sleep", "infinity"]
    assert mounts(no_op) == [
        f"{task_dir / 'tests'}:/tests:ro",
        f"{build_dir / 'qualification' / task.name / 'control' / 'verifier'}"
        ":/logs/verifier",
    ]
    assert mounts(reference) == [
        f"{task_dir / 'tests'}:/tests:ro",
        f"{task_dir / 'solution'}:/solution:ro",
        f"{build_dir / 'qualification' / task.name / 'reference' / 'verifier'}"
        ":/logs/verifier",
    ]
    name = reference[reference.index("--name") + 1]
    solve, test, removal = docker.calls[-3:]
    assert solve == ["docker", "exec", name, "bash", "/solution/solve.sh"]
    assert test == ["docker", "exec", name, "bash", "/tests/test.sh"]
    assert removal == ["docker", "rm", "--force", name]
    assert all(
        call[call.index("--network") + 1] == "none" for call in (no_op, reference)
    )
    assert docker.timeouts == [PROBE_BOUND, NO_OP_BOUND, SOLUTION_BOUND, TESTS_BOUND]

    status = read_build_status(paths, record.build_id)
    qualification = status.qualification
    assert qualification is not None and status.usable_tasks == 1
    assert qualification.qualified_task_ids == [task.name]
    (evidence,) = qualification.tasks
    assert evidence.kind == "skill"
    assert [(check.name, check.passed) for check in evidence.checks] == [
        ("hidden_material_private", True),
        ("image_build", True),
        ("verifier_material_absent", True),
        ("no_op_fails", True),
        ("reference_solution_passes", True),
        ("verifier_output_bounded", True),
    ]
    assert evidence.control_reward == 0.0 and evidence.reference_reward == 1.0
    saved_task = json.loads((build_dir / "qualification.json").read_bytes())["tasks"][0]
    assert saved_task["kind"] == "skill" and saved_task["image_id"] == evidence.image_id
    assert "base_commit" not in saved_task and "fail_to_pass" not in saved_task
    assert status.progress is not None and status.progress.state == "completed"
    assert status.progress.phase == "completed"
    assert status.progress.membership_digest == record.task_set.membership_digest
    assert status.progress.origin == str(task)
    assert task_verdict(evidence) == f"{task.name}: qualified"
    for run in ("control", "reference"):
        run_dir = build_dir / "qualification" / task.name / run
        assert (run_dir / "container.log").is_file()
        assert (run_dir / "verifier" / "reward.txt").is_file()
    with pytest.raises(ValidationError) as rejected:
        record.require_repository_source("run")
    assert rejected.value.code == "forge_source_unsupported"


def test_a_changed_package_byte_fails_re_verification_before_anything_runs(
    tmp_path: Path,
) -> None:
    task = skill2env_task(tmp_path / "upstream")
    record = import_task(task, tmp_path / "home", FakeDocker(reward=0.0))
    paths = paths_from_root(tmp_path / "home")
    build_dir = paths.forge_build_dir(record.build_id)
    (build_dir / "tasks" / task.name / "instruction.md").write_bytes(b"changed")
    docker = FakeDocker(reward=0.0)
    with pytest.raises(RunError) as drift:
        qualify_build(
            docker=Docker(docker),
            build=record,
            tasks_dir=build_dir / "tasks",
            work_dir=tmp_path / "again",
        )
    assert drift.value.code == "forge_task_content_changed"
    assert not (tmp_path / "again").exists()
    assert docker.calls == []


@pytest.mark.parametrize(
    ("case", "check", "words"),
    [
        ("no_op_passes", "no_op_fails", "a run that did nothing did not score 0"),
        (
            "reference_fails",
            "reference_solution_passes",
            "the reference solution did not make the tests pass",
        ),
        (
            "reference_hangs",
            "reference_solution_passes",
            "its tests did not finish within the task's own time limit",
        ),
        (
            "solution_out_of_time",
            "reference_solution_passes",
            "its reference solution did not finish within the task's own time limit",
        ),
        (
            "solution_fails",
            "reference_solution_passes",
            "its reference solution stopped with an error",
        ),
        (
            "image_will_not_start",
            "reference_solution_passes",
            "its environment could not be started",
        ),
        (
            "planted",
            "hidden_material_private",
            "the instruction or the environment carries a file of the tests or the "
            "reference solution",
        ),
        (
            "material_in_image",
            "verifier_material_absent",
            "the image already carries the tests or the reference solution",
        ),
        ("build_fails", "image_build", "the task's environment image did not build"),
        (
            "verifier_floods",
            "verifier_output_bounded",
            "the tests left more output than a task may, or something other than "
            "plain files",
        ),
        (
            "verifier_links",
            "verifier_output_bounded",
            "the tests left more output than a task may, or something other than "
            "plain files",
        ),
        (
            "verifier_unreadable",
            "verifier_output_bounded",
            "the tests left more output than a task may, or something other than "
            "plain files",
        ),
    ],
)
def test_rejections_keep_their_evidence_and_are_said_in_words(
    tmp_path: Path, request: pytest.FixtureRequest, case: str, check: str, words: str
) -> None:
    task = skill2env_task(tmp_path / "upstream")
    docker = FakeDocker(reward=0.0, reference_reward=1.0)
    if case == "no_op_passes":
        docker.reward = 1.0
    elif case == "reference_fails":
        docker.reference_reward = 0.0
    elif case == "solution_out_of_time":
        docker.reference_reward = "solution_timeout"
    elif case == "solution_fails":
        docker.reference_reward = "solution_fails"
    elif case == "image_will_not_start":
        docker.start_error = "sleep: executable file not found"
    elif case == "reference_hangs":
        docker.reference_reward = "timeout"
    elif case == "verifier_links":
        docker.verifier_link = True
    elif case == "verifier_unreadable":
        docker.verifier_unreadable = True

        def unseal() -> None:
            """Let the directories be read again so the temporary tree can go."""
            for sealed in tmp_path.rglob("sealed"):
                sealed.chmod(0o700)

        request.addfinalizer(unseal)
    elif case == "planted":
        (task / "environment" / "notes.sh").write_bytes(
            (task / "tests" / "test.sh").read_bytes()
        )
    elif case == "material_in_image":
        docker.material_present = True
    elif case == "build_fails":
        docker.build_error = "RUN failed"
    else:
        docker.verifier_output = 1024 * 1024
    with pytest.raises(RunError) as rejected:
        import_task(task, tmp_path / "home", docker)
    assert rejected.value.code == "forge_no_usable_tasks"
    assert f"{task.name}: rejected, {words}" in str(rejected.value)

    paths = paths_from_root(tmp_path / "home")
    build_dir = Path(str(rejected.value.details["path"]))
    qualification = ForgeQualification.model_validate_json(
        (build_dir / "qualification.json").read_bytes()
    )
    (evidence,) = qualification.tasks
    assert qualification.qualified_task_ids == [] and evidence.qualified is False
    failed = first_failed_check(evidence)
    assert failed is not None and failed.name == check
    if case == "planted":
        assert failed.detail == "tests/test.sh inside environment/notes.sh"
    if case == "verifier_links":
        assert failed.detail.endswith("not regular files: elsewhere, elsewhere")
    if case == "verifier_unreadable":
        assert failed.detail.endswith("not regular files: sealed, sealed")
    reference_log = build_dir / "qualification" / task.name / "reference"
    if case in {"reference_hangs", "solution_out_of_time"}:
        # The container of a step that ran out of time is removed at once, and
        # what the step printed before then is kept.
        name = next(iter(docker.started))
        assert docker.calls.count(["docker", "rm", "--force", name]) == 2
        printed = "solving" if case == "solution_out_of_time" else "testing"
        transcript = (reference_log / "container.log").read_text(encoding="utf-8")
        assert f"timed out True\n{printed}\n" in transcript
    if case == "solution_fails":
        assert not any(call[3:] == ["bash", "/tests/test.sh"] for call in docker.calls)
    if case == "image_will_not_start":
        transcript = (reference_log / "container.log").read_text(encoding="utf-8")
        assert "sleep: executable file not found" in transcript
    if case == "build_fails":
        assert all(call[1] != "run" for call in docker.calls)
        log = build_dir / "qualification" / task.name / "image-build.log"
        assert "RUN failed" in log.read_text(encoding="utf-8")
    build_id = str(rejected.value.details["build_id"])
    status = read_build_status(paths, build_id)
    assert status.usable_tasks == 0 and status.qualification_finished is True
    assert status.progress is not None and status.progress.state == "completed"

    result = CliRunner().invoke(
        create_app(),
        ["--home", str(paths.root), "forge", "status", build_id],
    )
    assert result.exit_code == 0
    shown = " ".join(result.stdout.split())
    assert "0 of 1 imported task qualified" in shown
    assert f"{task.name}: rejected, {words}" in shown
    assert "Every imported task was rejected at qualification" in shown


@pytest.mark.parametrize(
    "base",
    [
        "python:3.12-slim@sha256:" + "b" * 64,
        AMD64_SLIM,
        "docker.io/library/" + PYTHON_SLIM,
        "python:3.11-slim@" + PYTHON_SLIM.split("@")[1],
    ],
)
def test_base_images_outside_the_release_allow_list_are_never_pulled(
    tmp_path: Path, base: str
) -> None:
    task = skill2env_task(tmp_path / "upstream")
    recipe = task / "environment" / "Dockerfile"
    recipe.write_text(recipe.read_text().replace(PYTHON_SLIM, base), encoding="utf-8")
    docker = FakeDocker()
    with pytest.raises(RunError) as refused:
        import_task(task, tmp_path / "home", docker)
    assert refused.value.code == "forge_task_content_invalid"
    assert "allow-list" in str(refused.value)
    assert all(call[1] != "pull" for call in docker.calls)
    build_dir = Path(str(refused.value.details["path"]))
    assert not (build_dir / "build.json").exists()
    progress = json.loads((build_dir / "progress.json").read_bytes())
    assert progress["state"] == "failed" and progress["phase"] == "admission"


def test_failed_base_pull_leaves_the_admitted_bytes_and_no_build_record(
    tmp_path: Path,
) -> None:
    task = skill2env_task(tmp_path / "upstream")
    original = commit_task_set(task.parent, [task.name])
    docker = FakeDocker(pull_error="Error response from daemon: manifest unknown")
    with pytest.raises(RunError) as failed:
        import_task(task, tmp_path / "home", docker)
    assert failed.value.code == "forge_base_image_unavailable"
    assert "manifest unknown" in str(failed.value)
    build_dir = Path(str(failed.value.details["path"]))
    assert not (build_dir / "build.json").exists()
    verify_task_set(build_dir / "tasks", original)
    progress = json.loads((build_dir / "progress.json").read_bytes())
    assert progress["state"] == "failed" and progress["phase"] == "bootstrap"
    assert progress["failure"]["code"] == "forge_base_image_unavailable"
    assert all(call[1] != "build" for call in docker.calls)


def test_task_image_builds_offline_and_a_fetching_recipe_fails_with_its_log(
    tmp_path: Path,
) -> None:
    task = skill2env_task(tmp_path / "upstream")
    record = import_task(task, tmp_path / "home", FakeDocker(reward=0.0))
    paths = paths_from_root(tmp_path / "home")
    task_dir = paths.forge_build_dir(record.build_id) / "tasks" / task.name
    work_dir = tmp_path / "qualification" / task.name

    docker = FakeDocker()
    image_id = build_task_image(Docker(docker), record, task_dir, work_dir)
    build_call = next(call for call in docker.calls if call[1] == "build")
    assert build_call[:5] == [
        "docker",
        "build",
        "--platform",
        "linux/arm64",
        "--network",
    ]
    assert build_call[5] == "none"
    assert build_call[-1] == str(task_dir / "environment")
    assert build_call[build_call.index("--file") + 1] == str(
        task_dir / "environment" / "Dockerfile"
    )
    assert build_call[build_call.index("--tag") + 1] == (
        f"techtree-forge/skill2env/{task.name}:{record.build_id[-12:]}"
    )
    assert image_id.startswith("sha256:")

    failing = FakeDocker(
        build_error="Temporary failure resolving 'deb.debian.org'\n"
        "E: Unable to fetch some archives"
    )
    with pytest.raises(RunError) as failed:
        build_task_image(Docker(failing), record, task_dir, tmp_path / "again")
    assert failed.value.code == "forge_image_build_failed"
    log = tmp_path / "again" / "image-build.log"
    assert "Temporary failure resolving" in log.read_text(encoding="utf-8")
    assert all(call[1] != "image" for call in failing.calls)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("a" * 64, "c" * 64),
        ('source_skill = "local/reconcile"', 'source_skill = "local/another"'),
        ('schema_version = "1.3"', 'version = "1.3"'),
        ('network_mode = "no-network"', 'network_mode = "public"'),
        ("allowed_hosts = []", 'allowed_hosts = ["example.com"]'),
        ("[environment.env]", '[environment.env]\nTOKEN = "${TOKEN}"'),
        (PYTHON_SLIM.split("@")[1], "sha256:" + "b" * 64),
    ],
)
def test_provenance_and_offline_contract_are_required(
    tmp_path: Path, old: str, new: str
) -> None:
    task = skill2env_task(tmp_path / "upstream")
    config = task / "task.toml"
    config.write_text(config.read_text().replace(old, new), encoding="utf-8")
    destination = tmp_path / "build"
    with pytest.raises(RunError) as rejected:
        admit(task, destination)
    assert rejected.value.code == "forge_task_content_invalid"
    assert not (destination / "tasks").exists()


@pytest.mark.parametrize(
    "dockerfile",
    [
        "# syntax=docker/dockerfile:1\nFROM scratch\n",
        "FROM python:3.12\n",
        "FROM ${BASE}\n",
        "FROM scratch\n",
        f"FROM {PYTHON_SLIM}\nCOPY ../tests /tests\n",
        f"FROM {PYTHON_SLIM}\nCOPY /etc/passwd /app/input\n",
        f"FROM {PYTHON_SLIM}\nCOPY --from=remote/image /data /app/input\n",
        f"FROM {PYTHON_SLIM}\nADD https://example.com/data /app/input\n",
        f"FROM {PYTHON_SLIM}\nRUN   --mount=type=secret,id=token cat /run/secrets/x\n",
        f"FROM {PYTHON_SLIM}\nRUN echo hi \\ \nADD https://example.com/d /app/i\n",
        f"FROM {PYTHON_SLIM}\nRUN -\\\n-mount=type=bind,from=a,target=/m cat /m/x\n",
        f"FROM {PYTHON_SLIM}\nRUN cat <\\\n<RUN\nRUN\n",
        f"FROM {PYTHON_SLIM}\nRUN echo hi \\\n\nADD https://example.com/d /app/i\n",
    ],
)
def test_fetching_or_escaping_image_recipes_are_rejected(
    tmp_path: Path, dockerfile: str
) -> None:
    task = skill2env_task(tmp_path / "upstream")
    (task / "environment" / "Dockerfile").write_text(dockerfile, encoding="utf-8")
    destination = tmp_path / "build"
    with pytest.raises(RunError):
        admit(task, destination)
    assert not (destination / "tasks").exists()


@pytest.mark.parametrize(
    "unsafe", ["symlink", "oversized", "private", "case", "entries", "fifo"]
)
def test_unsafe_or_unbounded_trees_never_create_a_build(
    tmp_path: Path, unsafe: str
) -> None:
    task = skill2env_task(tmp_path / "upstream")
    asset = task / "environment" / "input"
    if unsafe == "symlink":
        asset.symlink_to(tmp_path)
    elif unsafe == "oversized":
        with asset.open("wb") as stream:
            stream.truncate(MAX_TASK_BYTES + 1)
    elif unsafe == "private":
        (task / "environment" / "auth.json").write_bytes(b"{}")
    elif unsafe == "case":
        (task / "environment" / "dockerfile").write_bytes(b"FROM scratch\n")
        if (task / "environment" / "dockerfile").samefile(
            task / "environment" / "Dockerfile"
        ):
            pytest.skip("filesystem cannot represent case-colliding files")
    elif unsafe == "entries":
        for index in range(4097):
            (task / "environment" / f"asset{index}").touch()
    else:
        import os

        os.mkfifo(asset)
    destination = tmp_path / "build"
    with pytest.raises(RunError):
        admit(task, destination)
    assert not (destination / "tasks").exists()


def test_existing_task_tree_is_never_reused(tmp_path: Path) -> None:
    task = skill2env_task(tmp_path / "upstream")
    destination = tmp_path / "build"
    (destination / "tasks").mkdir(parents=True)
    existing = destination / "tasks" / "retained.txt"
    existing.write_bytes(b"prior work")
    with pytest.raises(RunError):
        admit(task, destination)
    assert existing.read_bytes() == b"prior work"
    assert list((destination / "tasks").iterdir()) == [existing]
