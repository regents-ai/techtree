"""Admission binds provenance and exact bytes without granting execution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fixtures.forge.support import PYTHON_SLIM, FakeDocker, skill2env_task
from techtree.errors import RunError, ValidationError
from techtree.forge.content import commit_task_set, verify_task_set
from techtree.forge.docker import Docker
from techtree.forge.models import ForgeBuildRecord
from techtree.forge.qualify import build_task_image
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


def test_import_commits_exact_bytes_and_pulls_only_the_pinned_base(
    tmp_path: Path,
) -> None:
    task = skill2env_task(tmp_path / "upstream")
    original = commit_task_set(task.parent, [task.name])
    docker = FakeDocker()
    record = import_task(task, tmp_path / "home", docker)
    paths = paths_from_root(tmp_path / "home")
    build_dir = paths.forge_build_dir(record.build_id)
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
    assert [call[:2] for call in docker.calls if call[1] != "version"] == [
        ["docker", "pull"],
        ["docker", "image"],
    ]
    assert docker.calls[1] == [
        "docker",
        "pull",
        "--quiet",
        "--platform",
        "linux/arm64",
        PYTHON_SLIM,
    ]
    status = read_build_status(paths, record.build_id)
    assert status.build == record and status.qualification is None
    assert status.generation_finished is True
    assert status.qualification_finished is None and status.usable_tasks is None
    assert status.progress is not None and status.progress.state == "unfinished"
    assert status.progress.phase == "content"
    assert status.progress.membership_digest == record.task_set.membership_digest
    assert status.progress.origin == str(task)
    with pytest.raises(ValidationError) as rejected:
        record.require_repository_source("qualification")
    assert rejected.value.code == "forge_source_unsupported"
    (build_dir / "tasks" / task.name / "instruction.md").write_bytes(b"changed")
    with pytest.raises(RunError) as drift:
        verify_task_set(build_dir / "tasks", record.task_set)
    assert drift.value.code == "forge_task_content_changed"


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
    record = import_task(task, tmp_path / "home", FakeDocker())
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
