"""Admission binds provenance and exact bytes without granting execution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fixtures.forge.support import skill2env_task
from techtree.errors import RunError, ValidationError
from techtree.forge.content import commit_task_set, verify_task_set
from techtree.forge.models import ForgeBuildRecord
from techtree.forge.service import read_build_status
from techtree.forge.skill2env import MAX_TASK_BYTES, import_skill2env_task
from techtree.paths import paths_from_root

BUILD_ID = "build_" + "2" * 32


def admit(task: Path, destination: Path) -> ForgeBuildRecord:
    return import_skill2env_task(
        task,
        build_dir=destination,
        build_id=BUILD_ID,
        expected_source_skill="local/reconcile",
        expected_source_digest="sha256:" + "a" * 64,
        platform="linux/arm64",
    )


def test_import_commits_exact_bytes_and_remains_unqualified(tmp_path: Path) -> None:
    task = skill2env_task(tmp_path / "upstream")
    paths = paths_from_root(tmp_path / "home")
    destination = paths.forge_build_dir(BUILD_ID)
    original = commit_task_set(task.parent, [task.name])
    record = admit(task, destination)
    assert record.task_set == original
    verify_task_set(destination / "tasks", record.task_set)
    saved = json.loads((destination / "build.json").read_bytes())
    assert saved["source"]["source_skill_digest"] == "sha256:" + "a" * 64
    assert (
        saved["source"]["upstream_revision"]
        == "9beb0b64a70290f862c8374bbef21f2ac88992ab"
    )
    assert "repository" not in saved["source"] and "head_commit" not in saved["source"]
    status = read_build_status(paths, BUILD_ID)
    assert status.build == record and status.qualification is None
    with pytest.raises(ValidationError) as rejected:
        record.require_repository_source("qualification")
    assert rejected.value.code == "forge_source_unsupported"
    (destination / "tasks" / task.name / "instruction.md").write_bytes(b"changed")
    with pytest.raises(RunError) as drift:
        verify_task_set(destination / "tasks", record.task_set)
    assert drift.value.code == "forge_task_content_changed"


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
    assert not (destination / "build.json").exists()


@pytest.mark.parametrize(
    "dockerfile",
    [
        "# syntax=docker/dockerfile:1\nFROM scratch\n",
        "FROM python:3.12\n",
        "FROM ${BASE}\n",
        "FROM scratch\nCOPY ../tests /tests\n",
        "FROM scratch\nCOPY /etc/passwd /app/input\n",
        "FROM scratch\nCOPY --from=remote/image /data /app/input\n",
        "FROM scratch\nADD https://example.com/data /app/input\n",
        "FROM scratch\nRUN   --mount=type=secret,id=token cat /run/secrets/token\n",
        "FROM scratch\nRUN echo hi \\\u00a0\nADD https://example.com/data /app/input\n",
        "FROM scratch\nRUN -\\\n-mount=type=bind,from=alpine,target=/m cat /m/x\n",
        "FROM scratch\nRUN cat <\\\n<RUN\nRUN\n",
        "FROM scratch\nRUN echo hi \\\n\nADD https://example.com/data /app/input\n",
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
    assert not (destination / "build.json").exists()


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
    assert not (destination / "build.json").exists()


def test_nonempty_destination_is_preserved(tmp_path: Path) -> None:
    task = skill2env_task(tmp_path / "upstream")
    destination = tmp_path / "build"
    destination.mkdir()
    existing = destination / "retained.txt"
    existing.write_bytes(b"prior work")
    with pytest.raises(RunError):
        admit(task, destination)
    assert existing.read_bytes() == b"prior work"
    assert not (destination / "build.json").exists()
