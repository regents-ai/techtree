"""The nine agents the bench tests: each one's Harbor adapter, the survey's pinned version, and the model it is given.

Every agent talks to gpt-6-luna through the machine's translator (LiteLLM on 127.0.0.1:4000), which sets the reasoning
effort to high for every call, counts each call's cost and stops the attempt at $5. The agents only ever hold the
machine's local translator token, never the OpenAI key.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from harbor.agents.installed.base import BaseInstalledAgent
from harbor.agents.installed.claude_code import ClaudeCode
from harbor.agents.installed.codex import Codex
from harbor.agents.installed.opencode import OpenCode

from .agents import TOKEN, TRANSLATOR, ClineAgent, DeepSeekHarness, HermesAgent, KiloCode, OhMyPi, PiAgent

# Where every adapter keeps the agent's sessions and output on the machine, for the whole attempt.
LOGS = Path("/logs/agent")


@dataclass(frozen=True)
class Harness:
    name: str
    adapter: type[BaseInstalledAgent]
    version: str
    model: str
    # The agent's own output for one turn, under LOGS; it becomes the turn's stream.jsonl.
    output: str
    options: dict[str, Any] = field(default_factory=dict)


ROSTER = {
    "H04": Harness("Hermes Agent", HermesAgent, "0.21.5", "openai/gpt-6-luna", "hermes.txt"),
    "H05": Harness("Claude Code", ClaudeCode, "2.1.286", "anthropic/gpt-6-luna", "claude-code.txt"),
    "H06": Harness(
        "Cline", ClineAgent, "3.0.67", "openai-compatible:gpt-6-luna", "cline.txt", {"cline_version": "3.0.67"}
    ),
    "H07": Harness("Kilo Code", KiloCode, "7.8.1", "openai/gpt-6-luna", "kilo.txt"),
    "H08": Harness(
        "Pi", PiAgent, "1.0.0", "openai/gpt-6-luna", "pi.txt", {"model_api": "openai-completions", "thinking": "high"}
    ),
    "H09": Harness("oh-my-pi", OhMyPi, "v18.4.8", "openai/gpt-6-luna", "omp.txt"),
    "H10": Harness("Codex CLI", Codex, "0.159.3", "openai/gpt-6-luna", "codex.txt"),
    "H12": Harness("DeepSeek Harness", DeepSeekHarness, "0.2.0-rc.2", "openai/gpt-6-luna", "dsh.txt"),
    "H13": Harness(
        "OpenCode", OpenCode, "1.18.34", "openai/gpt-6-luna", "opencode.txt", {"opencode_config": {"autoupdate": False}}
    ),
}


def agent(harness_id: str) -> BaseInstalledAgent:
    """The harness's adapter, pointed at the translator with the machine's local token."""
    harness = ROSTER[harness_id]
    token = Path(TOKEN).read_text().strip()
    os.environ.update(
        OPENAI_API_KEY=token,
        OPENAI_BASE_URL=TRANSLATOR,
        ANTHROPIC_API_KEY=token,
        ANTHROPIC_BASE_URL=TRANSLATOR.removesuffix("/v1"),
        API_KEY=token,
    )
    return harness.adapter(
        logs_dir=LOGS,
        environment_logs_dir=PurePosixPath(LOGS),
        model_name=harness.model,
        version=harness.version,
        **harness.options,
    )
