"""Every tool handler, and the promises they all make.

Specification sections 7.11 and 7.15 (tool rows). The handlers are exercised
against a bridge double, so no benchmark, no Docker, no model, and no money
are involved anywhere in this file.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Sequence
from typing import Any

import pytest
from techtree_hermes.cli.release import load_embedded_release_core, release_core_digest
from techtree_hermes.host.schemas import all_tool_schemas
from techtree_hermes.host.state import SessionStore
from techtree_hermes.services.approvals import InstallPlanStore
from techtree_hermes.services.container import PluginServices
from techtree_hermes.services.models import DemoStage
from techtree_hermes.tools import TOOL_HANDLERS

CORE = load_embedded_release_core()
PUBLISHED = dataclasses.replace(
    CORE,
    starter_skill_digest="sha256:" + "7" * 64,
)
DIGEST = release_core_digest(CORE)
RUN_ID = "run_" + "0" * 32
DRAFT_ID = "draft_" + "0" * 32
DRAFT_DIGEST = "sha256:" + "d" * 64
POLICY = "sha256:" + "b" * 64


def _envelope(command: str, data: Any = None, ok: bool = True) -> dict[str, Any]:
    return {
        "schema_version": "techtree.cli.v1",
        "command": command,
        "ok": ok,
        "data": data,
        "error": None
        if ok
        else {"code": "x", "message": "y", "retryable": False, "details": {}},
        "messages": [],
        "warnings": [],
        "next_actions": [],
    }


class FakeBridge:
    """Records the argv it was asked for and answers from a script."""

    def __init__(self, answers: dict[str, dict[str, Any]] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.answers = answers or {}

    def invoke(self, arguments: Sequence[str]) -> dict[str, Any]:
        self.calls.append(list(arguments))
        key = " ".join(arguments[:2])
        return self.answers.get(key, _envelope(key, {"echo": list(arguments)}))

    def verify_release(self, expected: Any) -> dict[str, Any]:
        return {
            "compatible": True,
            "mismatches": [],
            "installed": {"release_id": PUBLISHED.release_id},
            "expected_release_core_digest": DIGEST,
        }

    def version(self) -> str:
        return "0.1.0"

    def call(self, arguments: Sequence[str], *, purpose: str = "") -> Any:
        raise AssertionError("no handler needs the exit code yet")

    def invoke_human(self, arguments: Sequence[str]) -> int:
        raise AssertionError("no handler may write to the terminal")

    def last_argv(self) -> list[str]:
        return self.calls[-1]


class StarterSkillDouble:
    """A release whose starter Skill exists and materializes cleanly."""

    def materialize(self, services: Any) -> dict[str, Any]:
        return {
            "skill_path": "/tmp/starter-skill/SKILL.md",
            "skill_root_digest": PUBLISHED.starter_skill_digest,
            "candidate_label": "hello-world-v1",
        }


def _services(
    *, release: Any = PUBLISHED, bridge: Any = None, assets: Any = None, ctx: Any = None
) -> PluginServices:
    from pathlib import Path

    return PluginServices(
        ctx=ctx,
        root=Path("."),
        release_core=release,
        release_core_digest=DIGEST,
        bridge=bridge or FakeBridge(),
        plans=InstallPlanStore(),
        sessions=SessionStore(),
        assets=assets or StarterSkillDouble(),
    )


def _call(name: str, services: Any, args: dict[str, Any]) -> dict[str, Any]:
    answer = TOOL_HANDLERS[name](services, args)
    assert isinstance(answer, str)
    parsed = json.loads(answer)
    assert isinstance(parsed, dict)
    return parsed


def _current(services: Any) -> Any:
    """Return the session there must be one of."""
    from techtree_hermes.host.state import latest_session

    session = latest_session(services)
    assert session is not None
    return session


# The shared contract ------------------------------------------------------------


def test_every_declared_tool_has_a_handler() -> None:
    assert set(TOOL_HANDLERS) == set(all_tool_schemas())


@pytest.mark.parametrize("name", sorted(TOOL_HANDLERS))
def test_every_handler_answers_with_json_even_when_it_fails(name: str) -> None:
    """No handler raises into the agent loop, whatever it is handed."""
    services = _services(bridge=FakeBridge())

    for args in ({}, {"run_id": "nonsense"}, {"unexpected": object()}):
        answer = TOOL_HANDLERS[name](services, dict(args))
        parsed = json.loads(answer)
        assert isinstance(parsed, dict)
        assert "ok" in parsed


@pytest.mark.parametrize("name", sorted(TOOL_HANDLERS))
def test_no_handler_emits_escape_codes(name: str) -> None:
    """Gateway-safe: a tool answer is text, never a terminal instruction."""
    services = _services(
        bridge=FakeBridge({"climb list": _envelope("climb list", {"note": "plain"})})
    )

    answer = TOOL_HANDLERS[name](services, {"run_id": RUN_ID, "reference": "demo@1"})

    assert "\x1b" not in answer
    assert "\x00" not in answer


def test_an_oversized_answer_is_capped_and_says_so() -> None:
    huge = {"rows": ["x" * 1000] * 1000}
    services = _services(
        bridge=FakeBridge({"climb list": _envelope("climb list", huge)})
    )

    result = _call("techtree_climb_list", services, {})

    assert result["truncated"] is True
    assert result["code"] == "tool_result_too_large"
    assert "too large" in result["message"]


# Reading tools --------------------------------------------------------------------


def test_the_catalog_is_read_through_the_cli() -> None:
    bridge = FakeBridge()
    services = _services(bridge=bridge)

    _call("techtree_climb_list", services, {})

    assert bridge.last_argv() == ["climb", "list"]


def test_inspecting_a_climb_passes_the_reference_through() -> None:
    bridge = FakeBridge()
    services = _services(bridge=bridge)

    _call("techtree_climb_inspect", services, {"reference": "procedure-transfer-dev@1"})

    assert bridge.last_argv() == ["climb", "show", "procedure-transfer-dev@1"]


@pytest.mark.parametrize("reference", ["--help", "climb; rm -rf /", "Not A Slug"])
def test_a_reference_that_is_not_a_reference_is_refused(reference: str) -> None:
    bridge = FakeBridge()
    services = _services(bridge=bridge)

    result = _call("techtree_climb_inspect", services, {"reference": reference})

    assert result["ok"] is False
    assert bridge.calls == []


def test_the_system_check_reports_the_release_beside_doctor() -> None:
    doctor = _envelope(
        "doctor",
        {
            "checks": [
                {
                    "id": "docker_daemon",
                    "label": "Docker",
                    "status": "pass",
                    "detail": "reachable",
                    "blocking": False,
                    "metadata": {},
                }
            ]
        },
    )
    services = _services(bridge=FakeBridge({"doctor": doctor}))

    result = _call("techtree_system_check", services, {})

    assert result["ok"] is True
    assert [check["id"] for check in result["checks"]] == [
        "cli_release",
        "docker_daemon",
    ]
    assert result["can_prepare_demo"] is True
    # Decision 0024 section 7: a successful answer names the one thing to do next.
    assert result["next_action"]["id"] == "inspect_climbs"
    assert result["next_action"]["label"] == "Inspect the Hello World Climb"


def test_a_blocked_system_check_names_the_blocking_step_instead() -> None:
    doctor = _envelope(
        "doctor",
        {
            "checks": [
                {
                    "id": "docker_daemon",
                    "label": "Docker",
                    "status": "fail",
                    "detail": "the Docker daemon is not reachable",
                    "blocking": True,
                    "metadata": {},
                }
            ]
        },
    )
    services = _services(bridge=FakeBridge({"doctor": doctor}))

    result = _call("techtree_system_check", services, {})

    assert result["ok"] is False
    assert result["next_action"]["id"] == "resolve_doctor_failures"
    assert "Docker daemon" in result["next_action"]["reason"]


# Long work ----------------------------------------------------------------------------


def test_starting_a_run_returns_a_run_identifier_and_does_not_wait() -> None:
    started = _envelope("climb start", {"run_id": RUN_ID, "phase": "created"})
    bridge = FakeBridge({"climb start": started})
    services = _services(bridge=bridge)

    result = _call("techtree_climb_start", services, {"draft_id": DRAFT_ID})

    assert result["data"]["run_id"] == RUN_ID
    assert bridge.last_argv() == [
        "climb",
        "start",
        DRAFT_ID,
        "--yes",
        "--reviewed-on",
        "host-agent",
    ]


def test_a_start_without_a_draft_is_refused() -> None:
    """The draft is the whole argument now; without it nothing runs."""
    bridge = FakeBridge()

    result = _call("techtree_climb_start", _services(bridge=bridge), {})

    assert result["ok"] is False
    assert bridge.calls == []


def test_a_missing_skill_path_says_how_to_repair_the_call() -> None:
    result = _call(
        "techtree_climb_prepare",
        _services(bridge=FakeBridge()),
        {"reference": "hello-world-climb@1"},
    )

    assert result["ok"] is False
    assert result["code"] == "tool_argument_missing"
    assert "skill_path" in result["next_actions"][0]["label"]


def test_a_start_names_a_draft_and_nothing_a_model_could_widen() -> None:
    """Decision 0019 s2: no token, no policy digest, no argument but the draft."""
    schema = all_tool_schemas()["techtree_climb_start"]

    assert set(schema["properties"]) == {"draft_id", "channel"}
    assert schema["required"] == ["draft_id"]


def test_status_returns_immediately_with_a_summary() -> None:
    status = _envelope(
        "run status",
        {
            "run_id": RUN_ID,
            "phase": "running_variants",
            "terminal": False,
            "result_available": False,
            "worker_alive": True,
        },
    )
    services = _services(bridge=FakeBridge({"run status": status}))

    result = _call("techtree_run_status", services, {"run_id": RUN_ID})

    assert result["summary"]["phase"] == "running_variants"
    assert result["summary"]["finished"] is False


def test_cancelling_is_explicit() -> None:
    bridge = FakeBridge()
    services = _services(bridge=bridge)

    _call("techtree_run_cancel", services, {"run_id": RUN_ID})

    assert bridge.last_argv() == ["run", "cancel", RUN_ID, "--confirm"]


def test_a_result_never_claims_independent_reproduction() -> None:
    services = _services(bridge=FakeBridge({"run result": _envelope("run result", {})}))

    result = _call("techtree_run_result", services, {"run_id": RUN_ID})

    assert "not been independently reproduced" in result["reproduction"]


# Paths --------------------------------------------------------------------------------


def test_preparing_requires_a_path_the_user_named() -> None:
    bridge = FakeBridge()

    result = _call(
        "techtree_climb_prepare",
        _services(bridge=bridge),
        {"reference": "procedure-transfer-dev@1"},
    )

    assert result["ok"] is False
    assert bridge.calls == []


@pytest.mark.parametrize("path", ["", "   ", "--skill"])
def test_a_path_that_reads_as_a_flag_is_refused(path: str) -> None:
    bridge = FakeBridge()

    result = _call(
        "techtree_climb_prepare",
        _services(bridge=bridge),
        {"reference": "demo@1", "skill_path": path},
    )

    assert result["ok"] is False
    assert bridge.calls == []


def test_a_named_path_is_passed_through_as_one_argument() -> None:
    bridge = FakeBridge()
    services = _services(bridge=bridge)

    _call(
        "techtree_climb_prepare",
        services,
        {"reference": "demo@1", "skill_path": "/home/me/my skill", "label": "mine"},
    )

    assert bridge.last_argv() == [
        "climb",
        "prepare",
        "demo@1",
        "--skill",
        "/home/me/my skill",
        "--label",
        "mine",
    ]


def test_proof_verification_takes_exactly_one_target() -> None:
    bridge = FakeBridge()
    services = _services(bridge=bridge)

    both = _call(
        "techtree_proof_verify",
        services,
        {"run_id": RUN_ID, "proof_path": "/tmp/proof"},
    )
    neither = _call("techtree_proof_verify", services, {})

    assert both["ok"] is False
    assert neither["ok"] is False
    assert bridge.calls == []


def test_proof_verification_accepts_a_run_or_a_path() -> None:
    bridge = FakeBridge()
    services = _services(bridge=bridge)

    _call("techtree_proof_verify", services, {"run_id": RUN_ID})
    _call("techtree_proof_verify", services, {"proof_path": "/tmp/proof-bundle"})

    assert bridge.calls == [
        ["proof", "verify", RUN_ID],
        ["proof", "verify", "/tmp/proof-bundle"],
    ]


# Uplift ------------------------------------------------------------------------------


def test_the_uplift_trio_bridges_the_committed_commands() -> None:
    bridge = FakeBridge()
    services = _services(bridge=bridge)

    _call("techtree_uplift_context", services, {"run_id": RUN_ID})
    assert bridge.last_argv() == ["uplift", "context", RUN_ID]

    _call(
        "techtree_uplift_prepare",
        services,
        {"run_id": RUN_ID, "revised_skill_path": "/tmp/skill-v2"},
    )
    assert bridge.last_argv() == [
        "uplift",
        "prepare",
        "--from-run",
        RUN_ID,
        "--candidate-skill",
        "/tmp/skill-v2",
    ]


def test_a_missing_guided_session_says_how_to_start_one() -> None:
    result = _call(
        "techtree_uplift_propose",
        _services(bridge=FakeBridge()),
        {"source_run_id": RUN_ID},
    )

    assert result["ok"] is False
    assert result["code"] == "demo_session_not_found"
    assert "techtree_demo_prepare" in result["next_actions"][0]["label"]


def _demo_bridge() -> FakeBridge:
    prepared = _envelope(
        "climb prepare",
        {
            "draft_id": DRAFT_ID,
            "draft_digest": DRAFT_DIGEST,
            "data_policy_digest": POLICY,
            "campaign_spec_digest": "sha256:" + "c" * 64,
            "skill_root_digest": PUBLISHED.starter_skill_digest,
            "estimated_episodes": 72,
        },
    )
    return FakeBridge(
        {
            "doctor": _envelope("doctor", {"checks": []}),
            "climb show": _envelope("climb show", {"reference": "demo@1"}),
            "climb prepare": prepared,
        }
    )


def test_the_demo_prepares_a_draft_and_stops_before_spending() -> None:
    bridge = _demo_bridge()
    services = _services(bridge=bridge)

    result = _call("techtree_demo_prepare", services, {})

    assert result["ok"] is True
    assert result["draft_id"] == DRAFT_ID
    assert result["data_policy_digest"] == POLICY
    assert result["estimated_episodes"] == 72
    assert result["next_action"]["requires_user_confirmation"] is True
    assert _current(services).stage is DemoStage.FIRST_DRAFT_PREPARED
    assert ["climb", "start"] not in [call[:2] for call in bridge.calls]


def test_the_demo_stops_when_doctor_blocks() -> None:
    bridge = _demo_bridge()
    bridge.answers["doctor"] = _envelope(
        "doctor",
        {
            "checks": [
                {
                    "id": "docker_daemon",
                    "label": "Docker",
                    "status": "fail",
                    "detail": "not running",
                    "blocking": True,
                    "metadata": {},
                }
            ]
        },
    )
    services = _services(bridge=bridge)

    result = _call("techtree_demo_prepare", services, {})

    assert result["ok"] is False
    assert result["blocked"] == "doctor_blocking_failure"
    assert ["climb", "prepare"] not in [call[:2] for call in bridge.calls]


def test_the_demo_prepares_the_candidate_under_the_release_label() -> None:
    """Ticket 06v: the guided path names the candidate rather than the cache."""
    bridge = _demo_bridge()
    services = _services(bridge=bridge)

    _call("techtree_demo_prepare", services, {})

    prepare = next(call for call in bridge.calls if call[:2] == ["climb", "prepare"])
    assert prepare == [
        "climb",
        "prepare",
        PUBLISHED.intro_climb_reference,
        "--skill",
        "/tmp/starter-skill/SKILL.md",
        "--label",
        "hello-world-v1",
    ]


def test_the_demo_stops_when_techtree_cannot_hand_over_the_starter_skill() -> None:
    """Ticket 06v: Techtree's own reason reaches the operator, and no other.

    The failure a new participant meets must describe what actually went
    wrong. It carries Techtree's code and Techtree's sentence, and it does not
    tell anybody to update a Techtree that is working.
    """
    from techtree_hermes.services.assets import ReleaseSkillProvider

    bridge = _demo_bridge()
    bridge.answers["skill starter"] = {
        **_envelope("skill starter", ok=False),
        "error": {
            "code": "starter_skill_source_refused",
            "message": "https://mirror.example does not serve the starter Skill",
            "retryable": False,
            "details": {},
        },
    }
    services = _services(bridge=bridge, assets=ReleaseSkillProvider())

    result = _call("techtree_demo_prepare", services, {})

    assert result["ok"] is False
    assert result["blocked"] == "starter_skill_unavailable"
    assert result["code"] == "starter_skill_source_refused"
    assert result["message"] == (
        "https://mirror.example does not serve the starter Skill"
    )
    assert result["repair"] is None
    assert ["climb", "prepare"] not in [call[:2] for call in bridge.calls]


def test_the_demo_records_the_run_it_started() -> None:
    bridge = _demo_bridge()
    bridge.answers["climb start"] = _envelope("climb start", {"run_id": RUN_ID})
    services = _services(bridge=bridge)

    _call("techtree_demo_prepare", services, {})
    _call(
        "techtree_climb_start",
        services,
        {
            "draft_id": DRAFT_ID,
            "draft_digest": DRAFT_DIGEST,
            "data_policy_digest": POLICY,
        },
    )

    session = _current(services)
    assert session.stage is DemoStage.FIRST_RUN_ACTIVE
    assert session.first_run_id == RUN_ID


def test_no_operator_skill_ever_reaches_the_subject() -> None:
    """The plugin's own Skills are for the host agent, never for the container."""
    bridge = _demo_bridge()
    services = _services(bridge=bridge)

    _call("techtree_demo_prepare", services, {})
    _call(
        "techtree_climb_prepare",
        services,
        {"reference": "demo@1", "skill_path": "/home/me/candidate"},
    )

    for call in bridge.calls:
        for argument in call:
            assert "skills/operator" not in argument
            assert "techtree:operator" not in argument


def test_no_handler_ever_returns_a_confirmation_token() -> None:
    """Decision 0019 s2 removed them; nothing may reintroduce one in a result."""
    services = _services(bridge=_demo_bridge())

    prepared = _call("techtree_demo_prepare", services, {})

    assert "confirmation_token" not in json.dumps(prepared)
    session = _current(services)
    assert session.first_draft_id == DRAFT_ID
