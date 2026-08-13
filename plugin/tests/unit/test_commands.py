"""The `/techtree` grammar and the session hooks. Sections 7.12, 7.13, 7.15."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from techtree_hermes.approvals import InstallPlanStore, ReviewStore
from techtree_hermes.bootstrap import create_install_plan
from techtree_hermes.channels import TRUNCATION_NOTE
from techtree_hermes.commands import (
    CLI_COMMAND_NAMES,
    SLASH_USAGE,
    build_cli_commands,
    handle_slash_command,
    parse_slash_args,
)
from techtree_hermes.hooks import SESSION_HOOKS, build_session_hooks
from techtree_hermes.models import DemoStage
from techtree_hermes.release import load_embedded_release_core, release_core_digest
from techtree_hermes.services.container import PluginServices
from techtree_hermes.services.session import create_demo_session
from techtree_hermes.state import SessionStore, save_session

CORE = load_embedded_release_core()
PUBLISHED = dataclasses.replace(
    CORE,
    placeholder_release=False,
    placeholder_fields=(),
    release_id="0.1.0",
    cli_version="0.1.0",
    starter_skill_digest="sha256:" + "7" * 64,
)
DIGEST = release_core_digest(CORE)
RUN_ID = "run_" + "0" * 32


def _envelope(command: str, data: Any = None, ok: bool = True) -> dict[str, Any]:
    return {
        "schema_version": "techtree.cli.v1",
        "command": command,
        "ok": ok,
        "data": data,
        "error": None
        if ok
        else {
            "code": "nope",
            "message": "Techtree said no",
            "retryable": False,
            "details": {},
        },
        "messages": [],
        "warnings": [],
        "next_actions": [],
    }


class FakeBridge:
    def __init__(self, answers: dict[str, dict[str, Any]] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.human_calls: list[list[str]] = []
        self.answers = answers or {}

    def invoke(self, arguments: Sequence[str]) -> dict[str, Any]:
        self.calls.append(list(arguments))
        key = " ".join(arguments[:2])
        return self.answers.get(key, _envelope(key, {"echo": list(arguments)}))

    def call(self, arguments: Sequence[str], *, purpose: str = "") -> Any:
        raise AssertionError("commands do not need exit codes from machine mode")

    def invoke_human(self, arguments: Sequence[str]) -> int:
        self.human_calls.append(list(arguments))
        return 0

    def verify_release(self, expected: Any) -> dict[str, Any]:
        return {
            "compatible": True,
            "mismatches": [],
            "installed": {},
            "placeholder_release": False,
            "expected_release_core_digest": DIGEST,
        }

    def version(self) -> str:
        return "0.1.0"


class SkillDouble:
    def materialize(self, services: Any) -> dict[str, Any]:
        return {"path": "/tmp/skill", "digest": PUBLISHED.starter_skill_digest}


def _services(*, release: Any = PUBLISHED, bridge: Any = None) -> PluginServices:
    return PluginServices(
        ctx=None,
        root=Path("."),
        release_core=release,
        release_core_digest=DIGEST,
        bridge=bridge or FakeBridge(),
        plans=InstallPlanStore(),
        reviews=ReviewStore(),
        sessions=SessionStore(),
        assets=SkillDouble(),
    )


# The grammar ---------------------------------------------------------------------


def test_the_grammar_is_split_not_passed_through() -> None:
    assert parse_slash_args("status run_123") == ("status", ["run_123"])
    assert parse_slash_args("  DEMO  ") == ("demo", [])
    assert parse_slash_args("") == ("", [])


def test_no_subcommand_lists_what_exists() -> None:
    answer = handle_slash_command("", _services())

    for name in SLASH_USAGE:
        assert f"/techtree {name}" in answer


def test_an_unknown_subcommand_is_refused_with_the_list() -> None:
    answer = handle_slash_command("rm -rf", _services())

    assert "There is no /techtree rm" in answer
    assert "/techtree setup" in answer


def test_nothing_a_user_types_becomes_a_command() -> None:
    bridge = FakeBridge()

    handle_slash_command(
        "status; techtree run cancel everything", _services(bridge=bridge)
    )

    for call in bridge.calls:
        assert all(";" not in argument for argument in call)


# Answers ---------------------------------------------------------------------------


def test_setup_reports_the_build_and_the_next_step() -> None:
    answer = handle_slash_command("setup", _services(bridge=FakeBridge()))

    assert "Plugin 0.1.0" in answer
    assert "Techtree CLI" in answer


def test_setup_says_when_the_build_is_a_development_one() -> None:
    answer = handle_slash_command("setup", _services(release=CORE))

    assert "development build" in answer


def test_climbs_lists_what_the_build_offers() -> None:
    listing = _envelope("climb list", [{"reference": "demo@1", "title": "A demo"}])
    answer = handle_slash_command(
        "climbs", _services(bridge=FakeBridge({"climb list": listing}))
    )

    assert "- demo@1 — A demo" in answer


def test_demo_says_it_has_not_spent_anything() -> None:
    prepared = _envelope(
        "climb prepare",
        {
            "draft_id": "draft_" + "0" * 32,
            "confirmation_token": "token-value",
            "data_policy_digest": "sha256:" + "b" * 64,
            "estimated_episodes": 72,
            "skill_root_digest": PUBLISHED.starter_skill_digest,
        },
    )
    bridge = FakeBridge(
        {
            "doctor": _envelope("doctor", {"checks": []}),
            "climb prepare": prepared,
            "climb show": _envelope("climb show", {}),
        }
    )

    answer = handle_slash_command("demo", _services(bridge=bridge))

    assert "Nothing has run yet" in answer
    assert "needs your explicit approval" in answer
    assert ["climb", "start"] not in [call[:2] for call in bridge.calls]


def test_status_without_an_identifier_uses_the_session() -> None:
    services = _services(
        bridge=FakeBridge(
            {
                "run status": _envelope(
                    "run status",
                    {
                        "run_id": RUN_ID,
                        "phase": "running_variants",
                        "terminal": False,
                        "result_available": False,
                    },
                )
            }
        )
    )
    session = create_demo_session(
        release=PUBLISHED, climb_reference="demo@1", release_core_digest=DIGEST
    )
    save_session(
        services,
        dataclasses.replace(
            session, stage=DemoStage.FIRST_RUN_ACTIVE, first_run_id=RUN_ID
        ),
    )

    answer = handle_slash_command("status", services)

    assert RUN_ID in answer
    assert "still going" in answer


def test_status_with_nothing_to_report_says_so() -> None:
    assert "No run to report on" in handle_slash_command("status", _services())


def test_cancel_needs_to_be_told_what_to_stop() -> None:
    bridge = FakeBridge()

    answer = handle_slash_command("cancel", _services(bridge=bridge))

    assert "Name the run to stop" in answer
    assert bridge.calls == []


def test_result_never_claims_reproduction() -> None:
    result = _envelope(
        "run result",
        {
            "presentation": {
                "baseline_score": 0.1,
                "candidate_score": 0.7,
                "wins": 20,
                "losses": 1,
                "ties": 15,
                "decision": "improved",
                "proof_grade": "P1",
            }
        },
    )
    services = _services(bridge=FakeBridge({"run result": result}))

    answer = handle_slash_command(f"result {RUN_ID}", services)

    assert "not independently reproduced" in answer
    assert "improved" in answer


def test_verify_reports_what_the_proof_said() -> None:
    proof = _envelope("proof verify", {"verified": True, "checks": [1, 2, 3]})
    services = _services(bridge=FakeBridge({"proof verify": proof}))

    answer = handle_slash_command(f"verify {RUN_ID}", services)

    assert "verified" in answer
    assert "offline" in answer


def test_improve_says_what_this_build_will_not_do() -> None:
    context = _envelope("uplift context", {"context": {}, "relative_path": "x.json"})
    services = _services(bridge=FakeBridge({"uplift context": context}))

    answer = handle_slash_command(f"improve {RUN_ID}", services)

    assert "not part of this build" in answer


def test_a_failure_is_reported_not_raised() -> None:
    services = _services(
        bridge=FakeBridge({"climb list": _envelope("climb list", None, ok=False)})
    )

    answer = handle_slash_command("climbs", services)

    assert "Techtree said no" in answer


def test_every_answer_is_bounded_and_free_of_control_characters() -> None:
    listing = _envelope(
        "climb list",
        [
            {"reference": f"climb-{n}@1", "title": "\x1b[31m" + "t" * 200}
            for n in range(200)
        ],
    )
    services = _services(bridge=FakeBridge({"climb list": listing}))

    answer = handle_slash_command("climbs", services)

    assert "\x1b" not in answer
    assert answer.endswith(TRUNCATION_NOTE)


# Terminal subcommands -----------------------------------------------------------------


def test_the_terminal_commands_are_the_declared_ones() -> None:
    assert set(build_cli_commands(_services())) == set(CLI_COMMAND_NAMES)


@pytest.mark.parametrize(
    ("name", "namespace", "expected"),
    [
        ("doctor", {}, ["doctor"]),
        ("status", {"run_id": RUN_ID}, ["run", "status", RUN_ID]),
        ("watch", {"run_id": RUN_ID}, ["run", "status", RUN_ID, "--watch"]),
        ("result", {"run_id": RUN_ID}, ["run", "result", RUN_ID]),
        ("verify", {"target": "/tmp/proof"}, ["proof", "verify", "/tmp/proof"]),
    ],
)
def test_a_terminal_command_runs_techtrees_own_human_output(
    name: str, namespace: dict[str, Any], expected: list[str]
) -> None:
    bridge = FakeBridge()
    services = _services(bridge=bridge)
    command = build_cli_commands(services)[name]

    code = command.handler(dataclasses.make_dataclass("N", namespace)(**namespace))

    assert code == 0
    assert bridge.human_calls == [expected]
    assert bridge.calls == []


def test_watch_is_never_available_to_a_model() -> None:
    """No model-visible tool may hold an open watch."""
    from techtree_hermes.schemas import all_tool_schemas

    for name, schema in all_tool_schemas().items():
        assert "watch" not in name
        assert "watch" not in json.dumps(schema).lower()
        assert "follow" not in json.dumps(schema).lower()


# Hooks ------------------------------------------------------------------------------


def test_the_declared_hooks_are_the_built_ones() -> None:
    assert set(build_session_hooks(_services())) == set(SESSION_HOOKS)


def test_session_start_prunes_what_has_run_out() -> None:
    services = _services()
    services.plans.save(
        create_install_plan(
            PUBLISHED,
            uv_path="/usr/local/bin/uv",
            release_core_digest=DIGEST,
            now=datetime.now(UTC) - timedelta(hours=2),
        )
    )
    stale = create_demo_session(
        release=PUBLISHED, climb_reference="demo@1", release_core_digest=DIGEST
    )
    save_session(
        services,
        dataclasses.replace(
            stale, updated_at=(datetime.now(UTC) - timedelta(days=30)).isoformat()
        ),
    )

    build_session_hooks(services)["on_session_start"](session_id="abc")

    assert services.plans.count() == 0
    assert services.sessions.latest() is None


def test_session_end_touches_no_techtree_artifact() -> None:
    """There is nothing on disk to flush, and nothing of Techtree's to remove."""
    bridge = FakeBridge()
    services = _services(bridge=bridge)

    build_session_hooks(services)["on_session_end"](session_id="abc")

    assert bridge.calls == []
    assert bridge.human_calls == []


def test_a_hook_never_breaks_a_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """Housekeeping that fails must not stop a session from starting."""
    import techtree_hermes.hooks as hooks_module

    def explode(services: Any, now: Any = None) -> int:
        raise RuntimeError("bookkeeping fell over")

    monkeypatch.setattr(hooks_module, "prune_expired_plans", explode)

    build_session_hooks(_services())["on_session_start"]()


def test_hooks_accept_whatever_a_host_passes() -> None:
    hooks = build_session_hooks(_services())

    hooks["on_session_start"](session_id="a", task_id="b", something_new=object())
    hooks["on_session_end"](session_id="a", reason="user quit")
