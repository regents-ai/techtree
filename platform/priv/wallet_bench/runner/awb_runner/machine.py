"""The attempt's own machine as a Harbor environment, seen from inside it.

The runner runs as root on the machine. Commands for the tested agent run as the tested account `bench` in a login
shell from its home; Harbor's root steps (system packages) run as root. Files are already on the one machine, so
copying in and out is a local copy. The machine is started, checkpointed and reset by the controller, never here.

A turn's wall cap holds across every command the adapter runs: each command gets what is left of it, and is
interrupted (then killed 30 seconds later) when that runs out, as the survey's watchdog did. Commands after that are
the adapter's own clean-up, such as copying the agent's session out, and each gets GRACE seconds.
"""
import asyncio
import shutil
import tempfile
import time
from pathlib import Path

from harbor.environments.base import BaseEnvironment, ExecResult
from harbor.models.task.config import EnvironmentConfig
from harbor.models.trial.paths import TrialPaths

AGENT_USER = "bench"
HOMES = {AGENT_USER: "/home/bench", "root": "/root"}
GRACE = 60


class Machine(BaseEnvironment):
    def __init__(self, wall_cap: int | None = None):
        self.deadline = time.monotonic() + wall_cap if wall_cap else None
        self.last_return_code: int | None = None
        scratch = Path(tempfile.mkdtemp(prefix="awb-runner-"))
        super().__init__(
            environment_dir=scratch,
            environment_name="agent-wallet-bench",
            session_id="agent-wallet-bench",
            trial_paths=TrialPaths(scratch),
            task_env_config=EnvironmentConfig(),
        )
        self.default_user = AGENT_USER

    @staticmethod
    def type() -> str:
        return "agent-wallet-bench-machine"

    def _validate_definition(self):
        """The machine is the environment; there is no definition to check."""

    async def start(self, force_build: bool) -> None:
        """The controller starts and restores the machine."""

    async def stop(self, delete: bool):
        """The controller checkpoints and resets the machine."""

    async def exec(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_sec: int | None = None,
        user: str | int | None = None,
    ) -> ExecResult:
        user = str(self._resolve_user(user) or "root")
        limit = self._limit(timeout_sec)
        pairs = [f"{key}={value}" for key, value in (env or {}).items()]
        if user == "root":
            argv = ["env", *pairs, "bash", "-c", command]
        else:
            argv = ["sudo", "-u", user, "-H", "env", *pairs, "bash", "-lc", command]
        if limit is not None:
            argv = ["timeout", "--signal=INT", "--kill-after=30", str(limit), *argv]

        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd or HOMES.get(user, "/"),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        self.last_return_code = process.returncode
        return ExecResult(
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
            return_code=process.returncode,
        )

    def _limit(self, timeout_sec: int | None) -> int | None:
        left = None if self.deadline is None else max(int(self.deadline - time.monotonic()), GRACE)
        limits = [limit for limit in (left, timeout_sec) if limit is not None]
        return min(limits) if limits else None

    async def upload_file(self, source_path: Path | str, target_path: str):
        Path(target_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source_path, target_path)

    async def upload_dir(self, source_dir: Path | str, target_dir: str):
        shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)

    async def download_file(self, source_path: str, target_path: Path | str):
        Path(target_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source_path, target_path)

    async def download_dir(self, source_dir: str, target_dir: Path | str):
        shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
