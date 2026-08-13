"""Test doubles for the host and for the Techtree CLI.

The recording context stands in for Hermes' ``PluginContext``. Its method
signatures match the host's, so a registration that works here works there,
and anything a real host would act on — dispatching a tool in particular —
fails loudly, because registration is not allowed to do it.

The fake CLI is a real executable named ``techtree``, written into a temporary
directory that a test puts on PATH. Using a real process rather than a patched
``subprocess`` is deliberate: it is the only way to prove the bridge builds the
argv it claims to, runs without a shell, and survives whatever the CLI writes.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VALID_ENVELOPE: dict[str, Any] = {
    "schema_version": "techtree.cli.v1",
    "command": "doctor",
    "ok": True,
    "data": {"checks": []},
    "error": None,
    "messages": [],
    "warnings": [],
    "next_actions": [],
}


@dataclass(frozen=True)
class RegisteredTool:
    """One tool the plugin asked the host to expose to the model."""

    name: str
    toolset: str
    schema: dict[str, Any]
    handler: Any
    description: str


@dataclass(frozen=True)
class RegisteredSkill:
    """One read-only Skill the plugin asked the host to make resolvable."""

    name: str
    path: Path
    description: str


@dataclass
class RecordingContext:
    """A host context that records what was registered and does nothing else."""

    tools: dict[str, RegisteredTool] = field(default_factory=dict)
    commands: dict[str, Any] = field(default_factory=dict)
    cli_commands: dict[str, Any] = field(default_factory=dict)
    hooks: dict[str, list[Any]] = field(default_factory=dict)
    skills: dict[str, RegisteredSkill] = field(default_factory=dict)

    def register_tool(
        self,
        name: str,
        toolset: str,
        schema: dict[str, Any],
        handler: Any,
        check_fn: Any = None,
        requires_env: list[Any] | None = None,
        is_async: bool = False,
        description: str = "",
        emoji: str = "",
        override: bool = False,
    ) -> None:
        assert not override, "the plugin must never override a built-in tool"
        self.tools[name] = RegisteredTool(
            name=name,
            toolset=toolset,
            schema=schema,
            handler=handler,
            description=description,
        )

    def register_command(
        self,
        name: str,
        handler: Any,
        description: str = "",
        args_hint: str = "",
    ) -> None:
        self.commands[name] = handler

    def register_cli_command(
        self,
        name: str,
        help: str,
        setup_fn: Any,
        handler_fn: Any = None,
        description: str = "",
    ) -> None:
        self.cli_commands[name] = handler_fn

    def register_hook(self, hook_name: str, callback: Any) -> None:
        self.hooks.setdefault(hook_name, []).append(callback)

    def register_skill(self, name: str, path: Path, description: str = "") -> None:
        self.skills[name] = RegisteredSkill(
            name=name, path=path, description=description
        )

    def dispatch_tool(self, tool_name: str, args: dict[str, Any], **kwargs: Any) -> str:
        raise AssertionError(f"registration dispatched the tool {tool_name!r}")


@dataclass(frozen=True)
class FakeCli:
    """A Techtree CLI stand-in installed on a temporary PATH."""

    directory: Path
    argv_log: Path

    def recorded_argv(self) -> list[list[str]]:
        """Return the argv of every call the fake CLI received."""
        if not self.argv_log.is_file():
            return []
        return [
            json.loads(line)
            for line in self.argv_log.read_text(encoding="utf-8").splitlines()
            if line
        ]


def install_fake_cli(
    directory: Path,
    *,
    body: str,
    monkeypatch: Any,
) -> FakeCli:
    """Write an executable named ``techtree`` and put it first on PATH.

    ``body`` is Python source run with the invocation's argv in ``argv``. It
    prints whatever the test wants the CLI to answer.
    """
    directory.mkdir(parents=True, exist_ok=True)
    argv_log = directory / "argv.jsonl"
    script = directory / "techtree"
    script.write_text(
        "#!"
        + sys.executable
        + "\n"
        + "import json, os, sys\n"
        + "argv = sys.argv[1:]\n"
        + f"log = {str(argv_log)!r}\n"
        + "open(log, 'a', encoding='utf-8').write(json.dumps(argv) + '\\n')\n"
        + body
        + "\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ.get('PATH', '')}")
    return FakeCli(directory=directory, argv_log=argv_log)


def print_envelope(**overrides: Any) -> str:
    """Return fake-CLI source that prints one valid envelope."""
    envelope = {**VALID_ENVELOPE, **overrides}
    return f"print(json.dumps({envelope!r}))"
