"""The twelve agents the bench tests: each one's Harbor adapter and model. Their pinned releases are in harnesses.json.

Every agent talks to claude-opus-5-5 through the machine's translator (LiteLLM on 127.0.0.1:4000), which sends every
call to Anthropic with adaptive thinking at effort high, counts cost and refuses new calls once the attempt reaches $5.
Claude Code and Grok Build speak Anthropic's format; the others speak OpenAI's chat or Responses format, which the
translator turns into Anthropic's. Muse Code reaches the translator through the gate (muse_gate.py). The agents only hold the machine's local translator token, never the Claude key.
"""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from harbor.agents.installed.base import BaseInstalledAgent
from harbor.agents.installed.codex import Codex
from harbor.agents.installed.opencode import OpenCode

from .agents import (
    TOKEN,
    TRANSLATOR,
    ClaudeCodeAgent,
    ClineAgent,
    DeepSeekHarness,
    GrokBuildAgent,
    HermesAgent,
    KiloCode,
    MuseCodeAgent,
    OhMyPi,
    PiAgent,
)
from .muse_gate import GATE
from .prime import PrimeAgent

# Where every adapter keeps the agent's sessions and output on the machine, for the whole attempt.
LOGS = Path("/logs/agent")


@dataclass(frozen=True)
class Harness:
    name: str
    adapter: type[BaseInstalledAgent]
    model: str
    # The agent's own output for one turn, under LOGS; it becomes the turn's stream.jsonl.
    output: str
    options: dict[str, Any] = field(default_factory=dict)
    # The npm package the agent's installer installs, for the agents npm installs (npm.py).
    package: str | None = None


ROSTER = {
    "H01": Harness("Muse Code", MuseCodeAgent, "meta/claude-opus-5-5", "muse-code.jsonl", {"base_url": GATE}),
    "H02": Harness(
        "Grok Build", GrokBuildAgent, "anthropic/claude-opus-5-5", "grok-build.txt",
        {"grok_config": {"model": {"claude-opus-5-5": {"base_url": TRANSLATOR}}}},
        package="@xai-official/grok",
    ),
    "H04": Harness("Hermes Agent", HermesAgent, "openai/claude-opus-5-5", "hermes.txt"),
    "H05": Harness("Claude Code", ClaudeCodeAgent, "claude-opus-5-5", "claude-code.txt"),
    "H06": Harness("Cline", ClineAgent, "openai-compatible:claude-opus-5-5", "cline.txt", package="cline"),
    "H07": Harness("Kilo Code", KiloCode, "openai/claude-opus-5-5", "kilo.txt", package="@kilocode/cli"),
    "H08": Harness(
        "Pi", PiAgent, "openai/claude-opus-5-5", "pi.txt",
        {"model_api": "openai-completions", "thinking": "high"},
        package="@earendil-works/pi-coding-agent",
    ),
    "H09": Harness("oh-my-pi", OhMyPi, "openai/claude-opus-5-5", "omp.txt"),
    "H10": Harness("Codex CLI", Codex, "openai/claude-opus-5-5", "codex.txt", package="@openai/codex"),
    "H12": Harness(
        "DeepSeek Harness", DeepSeekHarness, "openai/claude-opus-5-5", "dsh.txt", package="@deepseek-ai/dsh"
    ),
    "H13": Harness(
        "OpenCode", OpenCode, "openai/claude-opus-5-5", "opencode.txt",
        {"opencode_config": {"autoupdate": False}},
        package="opencode-ai",
    ),
    "H16": Harness("Prime Agent", PrimeAgent, "bench/claude-opus-5-5", "prime.txt"),
}

PINS = json.loads((Path(__file__).parents[1] / "harnesses.json").read_text())


def pin(harness_id: str) -> dict:
    """The release this machine was asked to build: the batch's, written by the controller, else the default pin."""
    config_file = os.environ.get("AWB_HARNESS_CONFIG")
    return json.loads(Path(config_file).read_text()) if config_file else PINS[harness_id]


def agent(harness_id: str) -> BaseInstalledAgent:
    """The harness's adapter, pointed at the translator with the machine's local token."""
    harness = ROSTER[harness_id]
    release = pin(harness_id)
    options = dict(harness.options)
    if harness_id == "H06":
        options["cline_version"] = release["version"]
    token = Path(TOKEN).read_text().strip()
    os.environ.update(
        OPENAI_API_KEY=token,
        OPENAI_BASE_URL=TRANSLATOR,
        ANTHROPIC_API_KEY=token,
        ANTHROPIC_BASE_URL=TRANSLATOR.removesuffix("/v1"),
        API_KEY=token,
        META_API_KEY=token,
    )
    tested = harness.adapter(
        logs_dir=LOGS,
        environment_logs_dir=PurePosixPath(LOGS),
        model_name=harness.model,
        version=release["version"],
        **options,
    )
    if harness_id == "H04":
        tested.COMMIT = release["source_ref"]
    if harness_id in ("H01", "H05", "H09"):
        tested.BINARY_SHA256 = release["archive_sha256"]
    if harness_id == "H16":
        tested.archive_sha256 = release["archive_sha256"]
    return tested
