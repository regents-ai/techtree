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
import subprocess
import sys
from dataclasses import dataclass, field
from functools import cache
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


@cache
def platform_environment_names() -> frozenset[str]:
    """Return the variable names this platform puts into a child by itself.

    macOS adds ``__CF_USER_TEXT_ENCODING`` to every process it starts, and a
    Python child given no locale sets its own ``LC_CTYPE``. Neither came from
    the parent's environment, so neither is evidence that anything was
    inherited — but both would break a comparison that assumed a child's
    environment is exactly what it was handed.

    The answer is measured rather than listed, by starting a child with an
    empty environment and asking it what it has, so this stays true on a
    platform that adds something else.
    """
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json, os; print(json.dumps(sorted(os.environ)))",
        ],
        env={},
        capture_output=True,
        text=True,
        check=True,
    )
    return frozenset(json.loads(completed.stdout))


def envelope(**overrides: Any) -> dict[str, Any]:
    """Return one valid envelope with the given fields replaced."""
    return {**VALID_ENVELOPE, **overrides}


def print_envelope(**overrides: Any) -> str:
    """Return fake-CLI source that prints one valid envelope."""
    return f"print(json.dumps({envelope(**overrides)!r}))"


# The founder's run shape ---------------------------------------------------------

#: The comparison the founder's journey actually ran: no Skill against the
#: starter Skill, over thirty-six toy tasks, with a cost worked out while
#: rendering because the provider reported none. Two suites relay it — the copy
#: scan and the end-to-end tool journey — so it is built once, here, and built
#: through Techtree's own presentation models rather than written out as a
#: dictionary, so a field renamed in Techtree fails a test rather than quietly
#: emptying a line in somebody's chat window.


def founder_result_payload(**overrides: Any) -> dict[str, Any]:
    """Return the founder's run shape: no Skill against the starter Skill.

    Built through :class:`UpliftPresentationPayload` rather than written out as
    a dictionary, so the fixture cannot drift away from the payload the CLI
    actually emits.
    """
    from techtree.models.cli import NextAction
    from techtree.presentation.models import (
        DerivedCost,
        PresentationCaveat,
        SkillSummary,
        TaskResultRow,
        UpliftPresentationPayload,
    )
    from techtree.receipts.execution import CostProvenance

    run_id = "run_" + "0" * 32
    rows = [
        TaskResultRow(
            position=index,
            task_label=f"task-{index + 1:02d}",
            baseline_score=0.0,
            candidate_score=1.0 if index < 24 else 0.0,
            delta=1.0 if index < 24 else 0.0,
            outcome="win" if index < 24 else "tie",
        )
        for index in range(36)
    ]
    payload = UpliftPresentationPayload(
        schema_version="techtree.presentation.uplift.v1",
        run_id=run_id,
        campaign_title="Techtree Hello World",
        comparison_label="Hello World Uplift Receipt",
        change_label="No tested Skill → Skill v1",
        baseline_skill=SkillSummary(
            label="No tested Skill", root_digest=None, file_count=0, total_bytes=0
        ),
        candidate_skill=SkillSummary(
            label="hello-world-starter",
            root_digest="sha256:" + "b" * 64,
            file_count=2,
            total_bytes=3072,
        ),
        baseline_score=0.0,
        candidate_score=24 / 36,
        absolute_delta=24 / 36,
        relative_delta=None,
        wins=24,
        losses=0,
        ties=12,
        task_rows=rows,
        baseline_tasks_scored_full=0,
        candidate_tasks_scored_full=24,
        baseline_tokens=1_211_350,
        candidate_tokens=1_230_775,
        baseline_seconds=612.0,
        candidate_seconds=598.4,
        baseline_model_turns=388,
        candidate_model_turns=412,
        baseline_rate_limited_calls=3,
        candidate_rate_limited_calls=11,
        every_rollout_completed=True,
        economics_source="comparison_execution_record",
        cost_usd=None,
        cost_provenance=CostProvenance.UNAVAILABLE,
        derived_cost=DerivedCost(
            usd=4.87,
            input_tokens=1_900_000,
            output_tokens=542_125,
            cached_input_tokens=410_000,
            prices_name_a_cached_rate=False,
            model_id="a-pinned-model",
            input_usd_per_mtok=3.0,
            output_usd_per_mtok=15.0,
            prices_recorded_on="2026-08-01",
        ),
        cost_unavailable_reason=None,
        decision="accepted",
        proof_grade="P1",
        verification_status="verified_offline",
        caveats=[
            PresentationCaveat(
                code="comparison_controlled_with_warnings",
                severity="warning",
                text=(
                    "The comparison is controlled with warnings, which means one "
                    "coordinate is attested more weakly than the rest. Your provider "
                    "publishes no immutable build identifier for a-pinned-model, so "
                    "both sides provably used the same model name but not provably "
                    "the same model build. No mismatch was found; a mismatch would "
                    "have made the comparison invalid."
                ),
            ),
            PresentationCaveat(
                code="no_independent_reproduction",
                severity="warning",
                text=(
                    "Nobody has independently reproduced this comparison, and no "
                    "platform witnessed it."
                ),
            ),
            PresentationCaveat(
                code="provider_rate_limiting",
                severity="warning",
                text=(
                    "The provider refused 3 model calls with a rate limit on the "
                    "baseline side and 11 on the candidate side. Every rollout "
                    "still ran to completion."
                ),
            ),
            PresentationCaveat(
                code="no_external_evidence_service",
                severity="info",
                text="No external evidence service is required, used, or contacted.",
            ),
        ],
        next_actions=[
            NextAction(
                id="show_every_task",
                label="Show every task",
                reason="The per-task table is one command away.",
                cli=["techtree", "run", "result", run_id, "--show-tasks", "all"],
                hermes_tool=None,
                hermes_args=None,
                requires_user_confirmation=False,
            )
        ],
    )
    return {**json.loads(payload.model_dump_json()), **overrides}
