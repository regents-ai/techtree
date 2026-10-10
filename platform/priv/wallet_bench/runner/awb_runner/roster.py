"""The ten agents the bench tests: each one's Harbor adapter, pinned version, and model.

Every agent talks to gpt-6-luna through the machine's translator (LiteLLM on 127.0.0.1:4000), which sets the reasoning
effort to high for every call, counts cost and refuses new calls once the attempt reaches $5. The agents only hold the
machine's local translator token, never the OpenAI key.
"""
import json
import os
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import Any

from harbor.agents.installed.base import BaseInstalledAgent
from harbor.agents.installed.claude_code import ClaudeCode
from harbor.agents.installed.codex import Codex
from harbor.agents.installed.opencode import OpenCode

from .agents import TOKEN, TRANSLATOR, ClineAgent, DeepSeekHarness, HermesAgent, KiloCode, OhMyPi, PiAgent
from .prime import PrimeAgent

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
    "H16": Harness("Prime Agent", PrimeAgent, "0.10.0", "bench/gpt-6-luna", "prime.txt"),
}

PINS = json.loads((Path(__file__).parents[1] / "harnesses.json").read_text())
ROSTER = {id: replace(harness, version=PINS[id]["version"]) for id, harness in ROSTER.items()}


def agent(harness_id: str) -> BaseInstalledAgent:
    """The harness's adapter, pointed at the translator with the machine's local token."""
    harness = ROSTER[harness_id]
    config_file = os.environ.get("AWB_HARNESS_CONFIG")
    pin = json.loads(Path(config_file).read_text()) if config_file else PINS[harness_id]
    options = dict(harness.options)
    if harness_id == "H06":
        options["cline_version"] = pin["version"]
    token = Path(TOKEN).read_text().strip()
    os.environ.update(
        OPENAI_API_KEY=token,
        OPENAI_BASE_URL=TRANSLATOR,
        ANTHROPIC_API_KEY=token,
        ANTHROPIC_BASE_URL=TRANSLATOR.removesuffix("/v1"),
        API_KEY=token,
    )
    tested = harness.adapter(
        logs_dir=LOGS,
        environment_logs_dir=PurePosixPath(LOGS),
        model_name=harness.model,
        version=pin["version"],
        **options,
    )
    if harness_id == "H04":
        tested.COMMIT = pin["source_ref"]
    if harness_id == "H09":
        tested.BINARY_SHA256 = pin["archive_sha256"]
    if harness_id == "H16":
        tested.archive_sha256 = pin["archive_sha256"]
    return tested
