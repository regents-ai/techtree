"""The bench's own Harbor agent adapters.

Harbor 0.24.0 has no adapter for oh-my-pi or DeepSeek Harness, and reaches Kilo Code only through its ACP bridge, so
those three are written here, each from the 1 October survey's working recipe (pinned version, model wiring through
the machine's translator, headless flags) and reusing Harbor's trajectory converter where the agent is a fork of one
Harbor already reads (Kilo of OpenCode, oh-my-pi of Pi). Hermes and Cline use Harbor's adapters with the survey's
pinned install and translator sign-in in place of Harbor's latest-release install.

An adapter that continues a conversation by its id reads `resume_session_id`, which the runner sets from the
controller before a later turn.
"""
import json
import re
import shlex
from pathlib import Path
from typing import Any

from harbor.agents.installed.base import BaseInstalledAgent
from harbor.agents.capabilities import AgentCapabilities
from harbor.agents.installed.cline.cline import ClineCli, ExecInput
from harbor.agents.installed.hermes import Hermes
from harbor.agents.installed.opencode import OpenCode
from harbor.agents.installed.pi import Pi
from harbor.agents.model_connection import ModelConnectionSpec
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext
from harbor.models.trajectories import (
    Agent,
    Observation,
    ObservationResult,
    Step,
    ToolCall,
    Trajectory,
)
from harbor.utils.trajectory_utils import format_trajectory_json

TRANSLATOR = "http://127.0.0.1:4000/v1"
MODEL = "gpt-6-luna"
TOKEN = "/home/bench/.model-token"
INSTRUCTION = "AWB_INSTRUCTION"


def _piped_instruction() -> str:
    """The prompt on the agent's stdin, from an environment variable rather than the command line."""
    return f'printf "%s" "${INSTRUCTION}" |'


class HermesAgent(Hermes):
    """Hermes Agent v0.21.5 (release v2026.9.24), installed from its pinned commit as in the survey."""

    COMMIT = "f97608f178d1ffeca59860195ab7da295f7c8e5f"
    resume_session_id: str | None = None

    async def install(self, environment: BaseEnvironment) -> None:
        await self.ensure_system_dependencies(environment, ("curl", "git", "ripgrep", "xz"))
        script = f"https://raw.githubusercontent.com/NousResearch/hermes-agent/{self.COMMIT}/scripts/install.sh"
        await self.exec_as_agent(
            environment,
            command=(
                "set -euo pipefail; "
                f"curl -fsSL {script} -o /tmp/hermes-install.sh && "
                f"bash /tmp/hermes-install.sh --commit {self.COMMIT} --non-interactive --skip-computer-use "
                "</dev/null && "
                'export PATH="$HOME/.local/bin:$PATH" && '
                "mkdir -p /tmp/hermes/sessions /tmp/hermes/skills /tmp/hermes/memories && "
                "hermes version"
            ),
        )

    async def resume(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        self._native_session_id = self.resume_session_id
        await super().resume(instruction, environment, context)


class ClineAgent(ClineCli):
    """Cline CLI 3.0.67, signed in to the translator as an OpenAI-compatible provider at baseline, as in the survey.

    Cline cannot continue a conversation from a script, so the bench gives it the install test only (Sean's 5 a).
    """

    async def install(self, environment: BaseEnvironment) -> None:
        await super().install(environment)
        await self.exec_as_agent(
            environment,
            command=(
                'export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"; '
                f'cline auth --provider openai-compatible --apikey "$(cat {TOKEN})" '
                f"--modelid {MODEL} --baseurl {TRANSLATOR}"
            ),
        )

    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        setup, run = super().create_run_agent_commands(instruction)
        signed_in = run.command.replace(" -P openai-compatible -k $API_KEY -m $MODELID", "")
        return [setup, ExecInput(command=signed_in.replace(" --yolo", " --auto-approve true"), env=run.env)]


class KiloCode(OpenCode):
    """Kilo Code CLI 7.8.1. Kilo is built on OpenCode and prints the same JSON events, so OpenCode's converter reads
    its turns. The translator is an OpenAI-compatible provider in Kilo's own config, as in the survey."""

    _OUTPUT_FILENAME = "kilo.txt"
    resume_session_id: str | None = None

    @staticmethod
    def name() -> str:
        return "kilo-code"

    def get_version_command(self) -> str | None:
        return "kilo --version"

    async def install(self, environment: BaseEnvironment) -> None:
        config = {
            "$schema": "https://app.kilo.ai/config.json",
            "provider": {
                "translator": {
                    "npm": "@ai-sdk/openai-compatible",
                    "name": "Local model translator",
                    "options": {"baseURL": TRANSLATOR, "apiKey": f"{{file:{TOKEN}}}"},
                    "models": {MODEL: {"name": MODEL}},
                }
            },
            "model": f"translator/{MODEL}",
            "small_model": f"translator/{MODEL}",
            "autoupdate": False,
            "share": "disabled",
        }
        await self.exec_as_agent(
            environment,
            command=(
                "set -euo pipefail; "
                'npm install --global --prefix "$HOME/.local" --no-audit --no-fund '
                f"--allow-scripts=@kilocode/cli @kilocode/cli@{self._version} && "
                "mkdir -p ~/.config/kilo && "
                f"echo {shlex.quote(json.dumps(config, indent=2))} > ~/.config/kilo/kilo.json && "
                "kilo --version"
            ),
        )

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        self._instruction = instruction
        resume = f"--session {shlex.quote(self.resume_session_id)} " if self._resume else ""
        output = (self.environment_logs_dir / self._OUTPUT_FILENAME).as_posix()
        await self.exec_as_agent(
            environment,
            command=(
                f"{_piped_instruction()} kilo run --format json --auto {resume}"
                f"2>&1 | stdbuf -oL tee {shlex.quote(output)}"
            ),
            env={
                INSTRUCTION: instruction,
                "KILO_TELEMETRY_LEVEL": "off",
                "XDG_DATA_HOME": (self.environment_logs_dir / "kilo" / "xdg-data").as_posix(),
                "XDG_STATE_HOME": (self.environment_logs_dir / "kilo" / "xdg-state").as_posix(),
            },
        )


class OhMyPi(Pi):
    """oh-my-pi v18.4.8, the release binary checked against its published digest, as in the survey. It is a fork of
    Pi and keeps Pi's session format, so Pi's converter reads its sessions once they are copied where Pi keeps them."""

    BINARY_SHA256 = "1b88f7a0da3f61edda915d836e11f63f20f2b56aeac2ddfa4ece0faa726f31c2"
    _OUTPUT_FILENAME = "omp.txt"
    resume_session_id: str | None = None

    @staticmethod
    def name() -> str:
        return "oh-my-pi"

    def get_version_command(self) -> str | None:
        return "omp --version"

    async def install(self, environment: BaseEnvironment) -> None:
        models = (
            "providers:\n"
            "  translator:\n"
            f"    baseUrl: {TRANSLATOR}\n"
            "    api: openai-completions\n"
            f'    apiKey: "!cat {TOKEN}"\n'
            "    models:\n"
            f"      - id: {MODEL}\n"
            "        reasoning: true\n"
            "        input: [text]\n"
        )
        await self.exec_as_agent(
            environment,
            command=(
                "set -euo pipefail; "
                "curl -fsSL https://omp.sh/install -o /tmp/omp-install.sh && "
                f"sh /tmp/omp-install.sh --binary --ref {self._version} && "
                f"echo '{self.BINARY_SHA256}  .local/bin/omp' | sha256sum -c - && "
                "mkdir -p ~/.omp/agent && "
                f"echo {shlex.quote(models)} > ~/.omp/agent/models.yml && "
                f"printf 'modelRoles:\\n  default: translator/{MODEL}\\n' > ~/.omp/agent/config.yml && "
                "omp --version"
            ),
        )

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        sessions = self.environment_logs_dir / self._SESSIONS_DIRECTORY
        self._session_usage_start = await self._session_positions(environment) if self._resume else {}
        resume = f"--resume {shlex.quote(self.resume_session_id)} " if self._resume else ""
        output = (self.environment_logs_dir / self._OUTPUT_FILENAME).as_posix()
        try:
            await self.exec_as_agent(
                environment,
                command=(
                    f"{_piped_instruction()} omp --mode json --allow-home --auto-approve {resume}"
                    "2>&1 | grep --line-buffered -v '\"type\":\"message_update\"' "
                    f"| stdbuf -oL tee {shlex.quote(output)}"
                ),
                env={INSTRUCTION: instruction},
            )
        finally:
            await self.exec_as_agent(
                environment,
                command=(
                    f"mkdir -p {shlex.quote(sessions.as_posix())} && "
                    'latest="$(ls -t ~/.omp/agent/sessions/*/*.jsonl | head -1)" && '
                    f'cp "$latest" {shlex.quote(sessions.as_posix())}/'
                ),
            )


class DeepSeekHarness(BaseInstalledAgent):
    """DeepSeek Harness (dsh) 0.2.0-rc.2 in its headless profile, as in the survey. Its `--json` events become an
    ATIF trajectory here; the stream carries no times or model name, so neither does the trajectory."""

    capabilities = AgentCapabilities(atif=True, resume=True)
    MODEL_CONNECTION = ModelConnectionSpec(passthrough=True)
    _OUTPUT_FILENAME = "dsh.txt"
    EXIT_CODE = re.compile(r"\[exit code: (\d+)\]\s*$")
    resume_session_id: str | None = None

    @staticmethod
    def name() -> str:
        return "deepseek-harness"

    def get_version_command(self) -> str | None:
        return "dsh --version"

    async def install(self, environment: BaseEnvironment) -> None:
        patch = (
            "- id: llm-pi-ai\n"
            "  config:\n"
            "    providers:\n"
            "      luna:\n"
            "        displayName: Local translator\n"
            "        api: openai-completions\n"
            f"        baseURL: {TRANSLATOR}\n"
            "        apiKeyEnv: LUNA_API_KEY\n"
            "        models:\n"
            f"          - id: {MODEL}\n"
            f"            name: {MODEL}\n"
            "- id: agent-default-model\n"
            "  config:\n"
            "    provider: luna\n"
            f"    model: {MODEL}\n"
        )
        await self.exec_as_agent(
            environment,
            command=(
                "set -euo pipefail; "
                "npm install --global --prefix ~/.local --no-audit --no-fund "
                f"@deepseek-ai/dsh@{self._version} && "
                f"mkdir -p ~/.dsh && echo {shlex.quote(patch)} > ~/.dsh/cordis.patch.yml && "
                "dsh --version"
            ),
        )

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        resume = f"--session-id {shlex.quote(self.resume_session_id)} " if self._resume else ""
        output = (self.environment_logs_dir / self._OUTPUT_FILENAME).as_posix()
        await self.exec_as_agent(
            environment,
            command=(
                f'export LUNA_API_KEY="$(cat {TOKEN})"; '
                f"{_piped_instruction()} dsh --profile headless --json {resume}"
                f"2>&1 | stdbuf -oL tee {shlex.quote(output)}"
            ),
            env={
                INSTRUCTION: instruction,
                "DSH_PERMISSION_MODE": "danger-full-access",
                "DSH_TELEMETRY_DISABLED": "1",
            },
        )

    def populate_context_post_run(self, context: AgentContext) -> None:
        events = []
        for line in (self.logs_dir / self._OUTPUT_FILENAME).read_text().splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        trajectory = self._trajectory(events)
        (self.logs_dir / "trajectory.json").write_text(format_trajectory_json(trajectory.to_json_dict()))

    def _trajectory(self, events: list[dict[str, Any]]) -> Trajectory:
        steps: list[Step] = []
        calls: dict[str, Step] = {}
        session_id = None

        def add(**fields: Any) -> Step:
            step = Step(step_id=len(steps) + 1, **fields)
            steps.append(step)
            return step

        for event in events:
            kind = event.get("type")
            if kind == "session":
                session_id = event["sessionId"]
            elif kind == "text" and event["text"].strip():
                add(source="agent", message=event["text"].strip())
            elif kind == "tool_call":
                call = ToolCall(tool_call_id=event["callId"], function_name=event["tool"], arguments=event["input"])
                calls[event["callId"]] = add(source="agent", message="", tool_calls=[call])
            elif kind == "tool_result" and event["callId"] in calls:
                result = event["result"] if isinstance(event["result"], str) else json.dumps(event["result"])
                failed = event["status"] != "completed" or self.EXIT_CODE.search(result) is not None
                calls[event["callId"]].observation = Observation(
                    results=[ObservationResult(source_call_id=event["callId"], content=result,
                                               extra={"is_error": failed})]
                )
            elif kind == "error":
                add(source="system", message=json.dumps(event))

        return Trajectory(
            session_id=session_id,
            agent=Agent(name=self.name(), version=self.version() or "unknown", model_name=MODEL),
            steps=steps,
        )
