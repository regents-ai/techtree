"""Docker as the forge uses it. ``docs/plan/repo2rlenv-local-lane.md``.

Five things and no more: build an image from a directory, ask the daemon what
an image's content id is, run one command in a fresh container from an image
with named directories mounted, copy an image's workspace out to the host, and
confirm the daemon answers at all. Nothing here pulls. The bootstrap image is
built from the person's own checkout, the task images from the bootstrap
image, and both live only in the local daemon.

Every container the forge starts is bounded and disconnected: a fixed memory
and CPU cap, no network, and a name the forge chose. Docker removes it on exit;
on timeout or interruption the forge attempts bounded removal and reports the
outcome. A task's tests are run to be graded, not to reach anything.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from techtree.errors import PrerequisiteError, RunError
from techtree.forge.models import ForgePlatform
from techtree.forge.process import CommandRunner

__all__ = [
    "BUILD_TIMEOUT_SECONDS",
    "CONTAINER_CPUS",
    "CONTAINER_MEMORY",
    "DAEMON_TIMEOUT_SECONDS",
    "Docker",
    "Mount",
    "RunOutcome",
]

#: A bootstrap build installs a whole toolchain and a task build resets one
#: checkout; the bound ends a hung build, not a slow one.
BUILD_TIMEOUT_SECONDS: Final = 1800.0
DAEMON_TIMEOUT_SECONDS: Final = 30.0
#: What every forge container gets. Decided once, recorded in the
#: qualification as the bound the tests ran under.
CONTAINER_MEMORY: Final = "4g"
CONTAINER_CPUS: Final = "2"


@dataclass(frozen=True)
class Mount:
    """One host directory a container sees."""

    source: Path
    target: str
    read_only: bool


@dataclass(frozen=True)
class RunOutcome:
    """What one container run produced."""

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool


class Docker:
    """The forge's Docker client."""

    def __init__(self, run: CommandRunner) -> None:
        self._run = run

    def require_daemon(self) -> str:
        """Return the daemon's platform, or say why nothing can be built."""
        completed = self._run(
            ["docker", "version", "--format", "{{.Server.Os}}/{{.Server.Arch}}"],
            DAEMON_TIMEOUT_SECONDS,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            raise PrerequisiteError(
                "the Docker daemon did not answer; start Docker and run the "
                "build again",
                code="forge_docker_unavailable",
                details={"detail": completed.stderr.strip()[-500:]},
            )
        return completed.stdout.strip()

    def build(
        self,
        *,
        context: Path,
        dockerfile: Path,
        tag: str,
        platform: ForgePlatform,
        log: Path,
    ) -> str:
        """Build ``tag`` from ``context`` and return the image's content id.

        The build's whole output is written to ``log`` whether it succeeded
        or not; a failed bootstrap build is the most common way a forge build
        ends and the log is what says why.
        """
        completed = self._run(
            [
                "docker",
                "build",
                "--platform",
                platform,
                "--file",
                str(dockerfile),
                "--tag",
                tag,
                str(context),
            ],
            BUILD_TIMEOUT_SECONDS,
        )
        log.write_text(f"{completed.stdout}\n{completed.stderr}", encoding="utf-8")
        if completed.returncode != 0:
            raise RunError(
                f"docker build of {tag} failed; the build log is at {log}",
                code="forge_image_build_failed",
                details={
                    "tag": tag,
                    "log": str(log),
                    "exit_code": completed.returncode,
                },
            )
        return self.image_id(tag)

    def image_id(self, tag: str) -> str:
        """Return the content id the daemon holds for ``tag``."""
        completed = self._run(
            ["docker", "image", "inspect", tag, "--format", "{{.Id}}"],
            DAEMON_TIMEOUT_SECONDS,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            raise RunError(
                f"the Docker daemon does not hold {tag}",
                code="forge_image_missing",
                details={"tag": tag},
            )
        return completed.stdout.strip()

    def run(
        self,
        *,
        image: str,
        platform: ForgePlatform,
        argv: list[str],
        mounts: list[Mount],
        timeout: float,
    ) -> RunOutcome:
        """Run ``argv`` once in a fresh, bounded, offline container.

        Timeout or interruption stops the client, not necessarily its container.
        Attempt bounded removal before returning or propagating the interrupt;
        the removal report is not proof that an unavailable daemon cleaned up.
        """
        name = f"techtree-forge-{uuid.uuid4().hex}"
        command = [
            "docker",
            "run",
            "--rm",
            "--name",
            name,
            "--platform",
            platform,
            "--network",
            "none",
            "--memory",
            CONTAINER_MEMORY,
            "--cpus",
            CONTAINER_CPUS,
        ]
        for mount in mounts:
            suffix = ":ro" if mount.read_only else ""
            command += ["--volume", f"{mount.source}:{mount.target}{suffix}"]
        command += [image, *argv]
        try:
            completed = self._run(command, timeout)
        except KeyboardInterrupt as error:
            error.add_note(f"Container removal attempted: {self.remove(name)}")
            raise
        except RunError as error:
            if error.code != "forge_command_timeout":
                raise
            return RunOutcome(
                exit_code=-1,
                stdout="",
                stderr=f"{error}\n{self.remove(name)}",
                timed_out=True,
            )
        return RunOutcome(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            timed_out=False,
        )

    def export_workspace(
        self, *, image: str, platform: ForgePlatform, destination: Path
    ) -> None:
        """Copy ``/workspace`` out of ``image`` into ``destination`` on the host.

        The container is created and never started: what is copied is the
        image's own workspace at the task's base commit, which is what an
        agent is then given to work in.
        """
        name = f"techtree-forge-{uuid.uuid4().hex}"
        try:
            created = self._run(
                ["docker", "create", "--name", name, "--platform", platform, image],
                DAEMON_TIMEOUT_SECONDS,
            )
            if created.returncode != 0:
                raise RunError(
                    f"a container from {image} could not be created: "
                    f"{created.stderr.strip()[-300:]}",
                    code="forge_workspace_export_failed",
                    details={"image": image},
                )
            copied = self._run(
                ["docker", "cp", f"{name}:/workspace/.", str(destination)],
                BUILD_TIMEOUT_SECONDS,
            )
            if copied.returncode != 0:
                raise RunError(
                    f"the workspace of {image} could not be copied out: "
                    f"{copied.stderr.strip()[-300:]}",
                    code="forge_workspace_export_failed",
                    details={"image": image, "destination": str(destination)},
                )
        finally:
            self.remove(name)

    def remove_labelled(self, label: str, value: str) -> list[str]:
        """Remove every container carrying ``label=value`` and say what happened.

        Hermes stops the sandbox it started for a one-shot run but leaves it
        on the daemon; it labels each with its profile, which is how the
        forge takes back exactly the containers its throwaway profile made.
        """
        listed = self._run(
            ["docker", "ps", "--all", "--quiet", "--filter", f"label={label}={value}"],
            DAEMON_TIMEOUT_SECONDS,
        )
        if listed.returncode != 0:
            return [f"containers labelled {label}={value} were not listed"]
        return [self.remove(name) for name in listed.stdout.split()]

    def remove(self, name: str) -> str:
        """Remove the container the forge named ``name`` and say what happened.

        The sentence returned is a report, not a promise: a daemon that has
        gone away or a removal that fails is said so, for the caller to record.
        """
        try:
            completed = self._run(
                ["docker", "rm", "--force", name], DAEMON_TIMEOUT_SECONDS
            )
        except RunError as error:
            return f"container {name} was not removed: {error}"
        if completed.returncode != 0:
            if "No such container" in completed.stderr:
                return f"container {name} was already gone"
            return (
                f"container {name} was not removed: {completed.stderr.strip()[-300:]}"
            )
        return f"container {name} removed"
