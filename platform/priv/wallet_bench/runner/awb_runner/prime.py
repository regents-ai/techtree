"""Prime Agent's pinned Rust release, driven through its JSON/print interface.

Its durable session messages use the Pi wire format, so Harbor's Pi trajectory
reader handles transcripts and resumed-session accounting. Only the loopback
translator token is exposed to the tested account.
"""
import json
import shlex

from harbor.agents.capabilities import AgentCapabilities
from harbor.agents.installed.pi import Pi
from harbor.agents.model_connection import ModelConnectionSpec
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from . import digest
from .agents import INSTRUCTION, MODEL, TOKEN, TRANSLATOR, _piped_instruction


class PrimeAgent(Pi):
    capabilities = AgentCapabilities(atif=True, resume=True)
    MODEL_CONNECTION = ModelConnectionSpec(passthrough=True)
    _OUTPUT_FILENAME = "prime.txt"
    _SESSIONS_DIRECTORY = "prime-sessions"
    archive_sha256: str = ""
    resume_session_id: str | None = None

    @staticmethod
    def name() -> str:
        return "prime-agent"

    def get_version_command(self) -> str:
        return "prime-agent --version"

    def parse_version(self, stdout: str) -> str:
        return stdout.strip().split()[-1].removeprefix("v")

    async def install(self, environment: BaseEnvironment) -> None:
        version = self._version.removeprefix("v")
        url = ("https://github.com/PrimeIntellect-ai/prime-agent/releases/download/"
               f"v{version}/prime-agent-{version}-linux-x64.tar.gz")
        models = {"providers": {"bench": {
            "baseUrl": TRANSLATOR, "apiKey": "AWB_LOCAL_TOKEN", "api": "openai-completions",
            "models": [{"id": MODEL, "name": MODEL, "reasoning": True,
                        "input": ["text"], "contextWindow": 200000, "maxTokens": 16000}]
        }}}
        settings = {"autoUpdate": False, "defaultProvider": "bench", "defaultModel": MODEL,
                    "defaultThinkingLevel": "high", "telemetry": {"enabled": False}}
        await self.exec_as_agent(environment, command=(
            "set -euo pipefail; "
            'test "$(uname -m)" = x86_64; '
            'mkdir -p "$HOME/.local/share/prime-agent" "$HOME/.local/bin" "$HOME/.prime/agent"; '
            f"curl --proto '=https' --proto-redir '=https' -fsSL {shlex.quote(url)} -o /tmp/prime-agent.tgz"
        ))
        await digest.held(self, environment, self.archive_sha256, "/tmp/prime-agent.tgz")
        await self.exec_as_agent(environment, command=(
            "set -euo pipefail; "
            'tar -xzf /tmp/prime-agent.tgz -C "$HOME/.local/share/prime-agent"; '
            'ln -s "$HOME/.local/share/prime-agent/prime-agent" "$HOME/.local/bin/prime-agent"; '
            f"printf '%s\\n' {shlex.quote(json.dumps(models))} > ~/.prime/agent/models.json; "
            f"printf '%s\\n' {shlex.quote(json.dumps(settings))} > ~/.prime/agent/settings.json; "
            "prime-agent --version"
        ))

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        self._session_usage_start = await self._session_positions(environment) if self._resume else {}
        sessions = (self.environment_logs_dir / self._SESSIONS_DIRECTORY).as_posix()
        output = (self.environment_logs_dir / self._OUTPUT_FILENAME).as_posix()
        resume = f"--resume {shlex.quote(self.resume_session_id)} " if self._resume else ""
        await self.exec_as_agent(environment, command=(
            "set -euo pipefail; "
            f'export AWB_LOCAL_TOKEN="$(cat {TOKEN})"; '
            f"mkdir -p {shlex.quote(sessions)}; "
            f"{_piped_instruction()} prime-agent --offline --print --mode json "
            f"--provider bench --model {MODEL} --thinking high "
            f"--session-dir {shlex.quote(sessions)} {resume}"
            f"2>&1 | stdbuf -oL tee {shlex.quote(output)}"
        ), env={INSTRUCTION: instruction})
