"""From a repository to emitted tasks. ``docs/plan/repo2rlenv-local-lane.md``.

Three steps, each a command at the boundary. The repository is cloned so that
only committed history reaches the image; the bootstrap image is built from
that clone with the person's Dockerfile or the shipped one; and the Repo2RLEnv
driver is run inside the managed environment with a request that names the
clone, the image and the test commands. Repo2RLEnv walks the history, finds
commits whose tests it can turn into a fail-to-pass set, validates each one in
a container from the bootstrap image, and writes the Harbor tasks.

That validation container is started by the driver on the forge's terms: the
name chosen here, the image's content id, offline, under the same memory and
CPU bounds as qualification. The driver removes it when the pipeline ends;
when the driver fails, times out or is interrupted, this module attempts bounded
removal by name and records what the daemon said. An interruption preserves that
report as an exception note, not as proof that the container is gone.

No model is called anywhere in this module. The commit message becomes the
instruction as it is; Repo2RLEnv's rewriting of it is switched off.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Final

from techtree.errors import RunError, UsageError
from techtree.forge.bundle import ForgeEnvironment
from techtree.forge.docker import CONTAINER_CPUS, CONTAINER_MEMORY, Docker
from techtree.forge.models import ForgeLanguage, ForgePlatform, GenerationSummary
from techtree.forge.process import CommandRunner
from techtree.fs import atomic_write_json

__all__ = [
    "CLONE_TIMEOUT_SECONDS",
    "GENERATION_TIMEOUT_SECONDS",
    "bootstrap_image_tag",
    "clone_repository",
    "generate_tasks",
    "repository_slug",
]

CLONE_TIMEOUT_SECONDS: Final = 600.0
#: Every candidate commit is validated by running the tests twice in a
#: container, so a generous bound; the limit option is what keeps it short.
GENERATION_TIMEOUT_SECONDS: Final = 4 * 3600.0

_SLUG_CHARACTERS: Final = re.compile(r"[^a-z0-9]+")


def repository_slug(repository: Path) -> str:
    """Return the image-name-safe form of a repository directory's name."""
    slug = _SLUG_CHARACTERS.sub("-", repository.name.lower()).strip("-")
    return slug or "repository"


def bootstrap_image_tag(slug: str, head_commit: str, build_id: str) -> str:
    """Return a tag no other build shares, however many build the same commit."""
    return f"techtree-forge/{slug}:{head_commit[:12]}-{build_id[-12:]}"


def clone_repository(repository: Path, checkout: Path, run: CommandRunner) -> str:
    """Clone the committed history of ``repository`` and return its head commit."""
    completed = run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(repository), str(checkout)],
        CLONE_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        raise UsageError(
            f"{repository} could not be cloned: {completed.stderr.strip()[-500:]}",
            code="forge_repository_unusable",
            details={"repository": str(repository)},
        )
    head = run(["git", "-C", str(checkout), "rev-parse", "HEAD"], CLONE_TIMEOUT_SECONDS)
    if head.returncode != 0 or not head.stdout.strip():
        raise UsageError(
            f"{repository} has no commit to build from",
            code="forge_repository_empty",
            details={"repository": str(repository)},
        )
    return head.stdout.strip()


def generate_tasks(
    *,
    environment: ForgeEnvironment,
    run: CommandRunner,
    docker: Docker,
    checkout: Path,
    head_commit: str,
    image_tag: str,
    image_id: str,
    dockerfile_text: str,
    language: ForgeLanguage,
    platform: ForgePlatform,
    test_commands: list[str],
    limit: int,
    slug: str,
    tasks_dir: Path,
    work_dir: Path,
) -> GenerationSummary:
    """Run the Repo2RLEnv driver and return what it emitted."""
    container = f"techtree-forge-{uuid.uuid4().hex}"
    request = work_dir / "request.json"
    atomic_write_json(
        request,
        {
            "checkout": f"file://{checkout}",
            "head_commit": head_commit,
            "image_tag": image_tag,
            "image_id": image_id,
            "dockerfile": dockerfile_text,
            "language": language.value,
            "platform": platform,
            "test_commands": test_commands,
            "limit": limit,
            "org": "techtree-forge",
            "dataset": slug,
            "out_dir": str(tasks_dir),
            "container": {
                "name": container,
                "memory": CONTAINER_MEMORY,
                "cpus": CONTAINER_CPUS,
            },
        },
    )
    log = work_dir / "generate.log"
    try:
        completed = run(
            [str(environment.python), str(environment.driver), str(request)],
            GENERATION_TIMEOUT_SECONDS,
        )
    except KeyboardInterrupt as error:
        error.add_note(f"Container removal attempted: {docker.remove(container)}")
        raise
    except RunError as error:
        if error.code != "forge_command_timeout":
            raise
        removal = docker.remove(container)
        log.write_text(f"{error}\n{removal}\n", encoding="utf-8")
        raise RunError(
            f"Repo2RLEnv did not finish generating tasks within "
            f"{GENERATION_TIMEOUT_SECONDS:.0f}s; {removal}",
            code="forge_generation_failed",
            details={"log": str(log), "timed_out": True, "container": removal},
        ) from error
    if completed.returncode != 0:
        removal = docker.remove(container)
        log.write_text(f"{completed.stderr}\n{removal}\n", encoding="utf-8")
        raise RunError(
            f"Repo2RLEnv did not finish generating tasks; its log is at {log}",
            code="forge_generation_failed",
            details={
                "log": str(log),
                "exit_code": completed.returncode,
                "container": removal,
            },
        )
    log.write_text(completed.stderr, encoding="utf-8")
    return _summary(completed.stdout, log)


def _summary(stdout: str, log: Path) -> GenerationSummary:
    """Read the driver's one-line report."""
    lines = [line for line in stdout.splitlines() if line.strip()]
    try:
        document = json.loads(lines[-1])
        return GenerationSummary(
            candidates=int(document["candidates"]),
            emitted=int(document["emitted"]),
            skipped=int(document["skipped"]),
            skip_reasons={
                str(reason): int(count)
                for reason, count in dict(document["skip_reasons"]).items()
            },
            tasks=[str(task) for task in document["tasks"]],
        )
    except (IndexError, KeyError, TypeError, ValueError) as error:
        raise RunError(
            f"the Repo2RLEnv driver reported nothing readable: {error}",
            code="forge_generation_unreadable",
            details={"log": str(log)},
        ) from error
