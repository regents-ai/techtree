"""Inert admission of one pinned Skill2Env package; this does not qualify it.

Only the host-authored, single-task Harbor 1.3 shape is supported. No upstream
launcher, model, Docker command, credential resolution or dependency is used.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import stat
import tomllib
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import TypeAdapter

from techtree.canonical import sha256_digest_bytes
from techtree.errors import RunError
from techtree.forge.bundle import embedded_forge_root
from techtree.forge.content import commit_task_set, stat_signature
from techtree.forge.models import (
    FORGE_BUILD_SCHEMA_VERSION,
    ForgeBuildRecord,
    ForgePlatform,
    ForgeSkillSource,
    TaskContentEntry,
)
from techtree.fs import atomic_write_json, ensure_private_directory
from techtree.models.base import Digest

MAX_TASK_BYTES = 128 * 1024 * 1024
MAX_TASK_ENTRIES = 4096
MAX_TASK_DEPTH = 32
_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_PRIVATE_NAMES = {
    "auth.json",
    "credentials",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
    "skill.md",
    "agents.md",
    "skill-card.md",
    "creator-result.json",
    "creator-transcript.jsonl",
    "creator-prompt.md",
    "reward.txt",
    "reward.json",
}
_SECRET = re.compile(
    rb"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----|"
    rb"\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})\b"
)


@dataclass(frozen=True)
class _Entry:
    data: bytes | None
    executable: bool


def _snapshot(root: Path) -> dict[str, _Entry]:
    """Read bounded regular bytes through held, no-follow directory handles."""
    entries: dict[str, _Entry] = {}
    names_seen: set[str] = set()
    total = 0

    def walk(directory: int, prefix: str, depth: int) -> None:
        nonlocal total
        if depth > MAX_TASK_DEPTH:
            raise ValueError(f"task exceeds directory depth limit at {prefix}")
        before = os.fstat(directory)
        names = sorted(os.listdir(directory))
        if len(names) > MAX_TASK_ENTRIES - len(entries):
            raise ValueError(f"too many task entries at {prefix or '.'}")
        for name in names:
            relative = prefix + name
            TaskContentEntry.validate_path(relative)
            key = unicodedata.normalize("NFC", relative).casefold()
            if key in names_seen or len(entries) >= MAX_TASK_ENTRIES:
                raise ValueError(
                    f"duplicate/case-colliding path or too many entries: {relative}"
                )
            names_seen.add(key)
            # Refuse private filenames before opening their contents, including .env.
            if name.startswith(".") or name.casefold() in _PRIVATE_NAMES:
                raise ValueError(f"private or hidden task material: {relative}")
            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, _DIRECTORY_FLAGS, dir_fd=directory)
                try:
                    if stat_signature(info) != stat_signature(os.fstat(child)):
                        raise ValueError(f"directory changed: {relative}")
                    entries[relative] = _Entry(None, bool(info.st_mode & stat.S_IXUSR))
                    walk(child, relative + "/", depth + 1)
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode):
                if info.st_size > MAX_TASK_BYTES - total:
                    raise ValueError(f"task exceeds 128 MiB limit: {relative}")
                fd = os.open(
                    name,
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                    dir_fd=directory,
                )
                with os.fdopen(fd, "rb") as stream:
                    if stat_signature(info) != stat_signature(
                        os.fstat(stream.fileno())
                    ):
                        raise ValueError(f"file changed before reading: {relative}")
                    data = stream.read(MAX_TASK_BYTES - total + 1)
                    if len(data) != info.st_size or stat_signature(
                        info
                    ) != stat_signature(os.fstat(stream.fileno())):
                        raise ValueError(f"file changed while reading: {relative}")
                total += len(data)
                if _SECRET.search(data):
                    raise ValueError(f"credential material: {relative}")
                entries[relative] = _Entry(data, bool(info.st_mode & stat.S_IXUSR))
            else:
                raise ValueError(f"symlink or special file: {relative}")
        if names != sorted(os.listdir(directory)) or stat_signature(
            before
        ) != stat_signature(os.fstat(directory)):
            raise ValueError(f"directory changed while reading: {prefix or '.'}")

    descriptor = os.open(root, _DIRECTORY_FLAGS)
    try:
        walk(descriptor, "", 0)
    finally:
        os.close(descriptor)
    return entries


def _text(entries: dict[str, _Entry], path: str) -> str:
    entry = entries.get(path)
    if entry is None or entry.data is None:
        raise ValueError(f"required regular file missing: {path}")
    try:
        return entry.data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"required UTF-8 file is invalid: {path}") from error


def _config(
    text: str, task_name: str, source_skill: str, digest: str, contract: dict[str, Any]
) -> None:
    config = tomllib.loads(text)
    if set(config) != {
        "schema_version",
        "artifacts",
        "task",
        "metadata",
        *contract["fixed_sections"],
    }:
        raise ValueError("task.toml requires exactly the pinned single-task sections")
    if config["schema_version"] != contract["task_schema"]:
        raise ValueError(f"task.toml requires Harbor schema {contract['task_schema']}")
    for section, expected in contract["fixed_sections"].items():
        if config[section] != expected:
            raise ValueError(
                f"task.toml [{section}] differs from the pinned offline contract"
            )
    task = config["task"]
    if (
        not isinstance(task, dict)
        or set(task) != {"name", "description", "authors", "keywords"}
        or task["name"] != f"skill2env/{task_name}"
        or task["authors"] != [{"name": "skill2env"}]
        or not isinstance(task["description"], str)
        or not task["description"].strip()
        or not isinstance(task["keywords"], list)
        or not task["keywords"]
        or any(
            not isinstance(word, str) or not word.strip() for word in task["keywords"]
        )
    ):
        raise ValueError(
            "task.toml [task] must identify the authoritative Skill2Env package"
        )
    metadata = config["metadata"]
    axes = {
        "archetype",
        "primary_verifier_pattern",
        "complexity",
        "persona",
        "tone",
        "expertise",
    }
    if (
        not isinstance(metadata, dict)
        or set(metadata)
        - {"source_skill", "source_bundle_digest", "base_image_pins", *axes}
        or metadata.get("source_skill") != source_skill
        or metadata.get("source_bundle_digest") != digest
    ):
        raise ValueError(
            "task.toml Source Skill identity or bundle digest "
            "does not match expected provenance"
        )
    for key in axes & metadata.keys():
        if not isinstance(metadata[key], str) or not metadata[key].strip():
            raise ValueError(f"task.toml metadata.{key} must be a nonempty string")
    pins = metadata.get("base_image_pins", {})
    if not isinstance(pins, dict) or any(
        not isinstance(key, str)
        or not isinstance(value, str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", value)
        for key, value in pins.items()
    ):
        raise ValueError("task.toml metadata.base_image_pins is invalid")
    artifacts = config["artifacts"]
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("task.toml requires expected artifacts")
    paths: list[PurePosixPath] = []
    for artifact in artifacts:
        if (
            not isinstance(artifact, str)
            or not artifact.startswith("/")
            or any(char in artifact for char in "\\\x00*?[")
            or ".." in PurePosixPath(artifact).parts
        ):
            raise ValueError(
                "task.toml artifacts must be literal absolute container paths"
            )
        path = PurePosixPath(artifact)
        if (
            path == PurePosixPath("/")
            or path.is_relative_to("/logs")
            or any(
                path.is_relative_to(other) or other.is_relative_to(path)
                for other in paths
            )
        ):
            raise ValueError("task.toml artifacts overlap or use reserved paths")
        paths.append(path)


_DOCKERFILE_INSTRUCTIONS = frozenset(
    {
        "FROM",
        "RUN",
        "COPY",
        "WORKDIR",
        "ENV",
        "CMD",
        "ENTRYPOINT",
        "LABEL",
        "USER",
        "EXPOSE",
        "STOPSIGNAL",
        "SHELL",
        "HEALTHCHECK",
    }
)
# BuildKit continues a line only when a backslash is followed by spaces or tabs
# and the newline; it then appends the next raw line with no separator.
_CONTINUATION = re.compile(r"\\[ \t]*$")


def _logical_lines(text: str) -> list[str]:
    """Join continued lines exactly as BuildKit does, or refuse the file.

    Anything BuildKit would read differently from a byte-level reader (other
    whitespace after the backslash, non-ASCII, CR, blank or comment lines
    inside a continued instruction) is rejected rather than interpreted.
    """
    if not re.fullmatch(r"[\x20-\x7e\t\n]*", text):
        raise ValueError(
            "environment/Dockerfile must be printable ASCII with LF line endings"
        )
    lines: list[str] = []
    logical: str | None = None
    for raw in text.split("\n"):
        if logical is None:
            stripped = raw.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                if re.match(r"#\s*(syntax|escape)\s*=", stripped, re.I):
                    raise ValueError(
                        "environment/Dockerfile: parser directives are unsupported"
                    )
                continue
            logical = ""
            current = raw.lstrip()
        else:
            current = raw
            if not raw.strip() or raw.lstrip().startswith("#"):
                raise ValueError(
                    "environment/Dockerfile: blank or comment line inside a "
                    "continued instruction"
                )
        continued = _CONTINUATION.search(current)
        if continued is not None:
            logical += current[: continued.start()]
            continue
        lines.append(logical + current)
        logical = None
    if logical is not None:
        raise ValueError("environment/Dockerfile ends inside a continued instruction")
    return lines


def _dockerfile(text: str, entries: dict[str, _Entry], platform: ForgePlatform) -> None:
    """Fail closed on syntax that could bypass the local build context policy."""
    stages: set[str] = set()
    from_count = 0
    for logical in _logical_lines(text):
        parts = re.split(r"[ \t]+", logical.strip(), maxsplit=1)
        instruction = parts[0].upper()
        arguments = parts[1] if len(parts) > 1 else ""
        if "<<" in arguments or instruction not in _DOCKERFILE_INSTRUCTIONS:
            raise ValueError(
                f"environment/Dockerfile: unsupported instruction {instruction}"
            )
        if instruction == "FROM":
            match = re.fullmatch(
                r"(?:--platform=(\S+)\s+)?(\S+)(?:\s+[Aa][Ss]\s+([a-zA-Z0-9_-]+))?",
                arguments,
            )
            if match is None or (match[1] is not None and match[1] != platform):
                raise ValueError(
                    "environment/Dockerfile: invalid FROM or platform mismatch"
                )
            base = match[2]
            if (
                base.casefold() not in stages
                and base != "scratch"
                and not re.fullmatch(
                    r"[a-z0-9][a-z0-9._/:-]*@sha256:[0-9a-f]{64}", base
                )
            ):
                raise ValueError(
                    "environment/Dockerfile: external FROM requires a static sha256 pin"
                )
            if match[3]:
                if match[3].casefold() in stages:
                    raise ValueError("environment/Dockerfile: duplicate stage")
                stages.add(match[3].casefold())
            from_count += 1
        elif from_count == 0:
            raise ValueError("environment/Dockerfile must start with FROM")
        elif instruction == "RUN" and arguments.startswith("--"):
            raise ValueError("environment/Dockerfile: RUN flags/mounts are unsupported")
        elif instruction == "COPY":
            operands = (
                json.loads(arguments)
                if arguments.startswith("[")
                else shlex.split(arguments)
            )
            if (
                not isinstance(operands, list)
                or len(operands) < 2
                or any(not isinstance(x, str) for x in operands)
            ):
                raise ValueError("environment/Dockerfile: invalid COPY")
            for source in operands[:-1]:
                if (
                    not source
                    or source.startswith(("/", "--"))
                    or any(c in source for c in "$:*?[\\\x00")
                    or ".." in PurePosixPath(source).parts
                ):
                    raise ValueError(
                        "environment/Dockerfile: COPY requires literal local sources"
                    )
                path = PurePosixPath("environment") / source
                if path.as_posix() not in entries:
                    raise ValueError(
                        f"environment/Dockerfile: COPY source missing: {source}"
                    )
    if not from_count:
        raise ValueError("environment/Dockerfile is incomplete")


def import_skill2env_task(
    task_dir: Path,
    *,
    build_dir: Path,
    build_id: str,
    expected_source_skill: str,
    expected_source_digest: Digest,
    platform: ForgePlatform,
) -> ForgeBuildRecord:
    """Admit exact local bytes into a new build. Failures leave no build.json.

    The expected digest is the reviewed Skill2Env source bundle SHA-256, with
    Techtree's ``sha256:`` prefix. Source bytes stay private and are not copied.
    A partial directory is retained on failure and must not be reused.
    """
    try:
        TypeAdapter(Digest).validate_python(expected_source_digest)
        TypeAdapter(ForgePlatform).validate_python(platform)
        if not re.fullmatch(r"build_[0-9a-f]{32}", build_id):
            raise ValueError("invalid build id")
        if not re.fullmatch(r"[a-zA-Z0-9_-]+/[a-zA-Z0-9._-]+", expected_source_skill):
            raise ValueError("expected Source Skill must be an explicit provider/id")
        if not re.fullmatch(r"task_[a-z0-9-]+_[a-z0-9]{8}", task_dir.name):
            raise ValueError(
                "task directory must use the authoritative Skill2Env task name"
            )
        contract_bytes = (
            embedded_forge_root() / "skill2env" / "contract.json"
        ).read_bytes()
        contract = json.loads(contract_bytes)
        entries = _snapshot(task_dir)
        for path in contract["required_files"]:
            _text(entries, path)
        if "rubric.md" in entries:
            raise ValueError("root rubric.md is unsupported; use tests/rubric.md")
        for path, entry in entries.items():
            if path.split("/")[0] not in {
                "instruction.md",
                "task.toml",
                "environment",
                "tests",
                "solution",
            }:
                raise ValueError(f"unsupported task root member: {path}")
            if (
                entry.data is not None
                and path != "task.toml"
                and expected_source_digest.removeprefix("sha256:").encode()
                in entry.data
            ):
                raise ValueError(f"private source provenance in task material: {path}")
            if path.startswith("environment/") and Path(path).name.casefold() in {
                "docker-compose.yaml",
                "docker-compose.yml",
                "compose.yaml",
                "compose.yml",
                "instruction.md",
                "task.toml",
                "tests",
                "solution",
                "rubric.md",
            }:
                raise ValueError(
                    f"unsupported or privileged build context material: {path}"
                )
        _config(
            _text(entries, "task.toml"),
            task_dir.name,
            expected_source_skill,
            expected_source_digest.removeprefix("sha256:"),
            contract,
        )
        _dockerfile(_text(entries, "environment/Dockerfile"), entries, platform)
        if entries != _snapshot(task_dir):
            raise ValueError("task changed during admission")
        # The build id is fresh, so the destination is created exclusively; an
        # existing directory, file or symlink of that name is never reused.
        ensure_private_directory(build_dir.parent)
        build_dir.mkdir(mode=0o700)
        tasks_dir = build_dir / "tasks"
        tasks_dir.mkdir(mode=0o700)
        destination = tasks_dir / task_dir.name
        destination.mkdir(mode=0o700)
        for path, entry in entries.items():
            target = destination / path
            if entry.data is None:
                target.mkdir(mode=0o700)
            else:
                with target.open("xb") as output:
                    output.write(entry.data)
                target.chmod(0o700 if entry.executable else 0o600)
        for path, entry in reversed(entries.items()):
            if entry.data is None:
                (destination / path).chmod(0o700 if entry.executable else 0o600)
        # The commitment hashes the written bytes; comparing it with the
        # validated in-memory bytes is the one check that the copy is exact.
        task_set = commit_task_set(tasks_dir, [task_dir.name])
        for committed in task_set.tasks[0].entries:
            original = entries[committed.path]
            if original.data is not None and committed.digest != sha256_digest_bytes(
                original.data
            ):
                raise ValueError(f"copied task bytes changed: {committed.path}")
        record = ForgeBuildRecord(
            schema_version=FORGE_BUILD_SCHEMA_VERSION,
            build_id=build_id,
            created_at=datetime.now(UTC),
            platform=platform,
            task_set=task_set,
            source=ForgeSkillSource(
                kind="skill",
                source_skill_digest=expected_source_digest,
                recipe="skill2env",
                recipe_version=sha256_digest_bytes(contract_bytes),
                producer="skill2env",
                producer_version=contract["producer_version"],
                upstream_url=contract["upstream_url"],
                upstream_revision=contract["upstream_revision"],
                harbor_version=contract["harbor_version"],
            ),
        )
        atomic_write_json(build_dir / "build.json", record.model_dump(mode="json"))
        return record
    except (OSError, ValueError) as error:
        raise RunError(
            f"cannot import Skill2Env task {task_dir}: {error}",
            code="forge_task_content_invalid",
        ) from error
