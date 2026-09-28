"""The read-only tools, against the regents-cli that is actually installed.

Specification section 7.15. These run only when ``REGENTS_CLI_ARGV`` names a
regents-cli, and only the commands that read: readiness, the catalog, one
Climb, and a proof verification that is expected to fail because the run does
not exist. Nothing here prepares a draft, starts a run, calls a model, or
spends anything.
"""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path
from typing import Any

import pytest
from support import install_regents_from_argv
from techtree_hermes.cli.bridge import CliBridge
from techtree_hermes.cli.release import load_embedded_release_core, release_core_digest
from techtree_hermes.host.state import SessionStore
from techtree_hermes.services.approvals import InstallPlanStore
from techtree_hermes.services.assets import ReleaseSkillProvider
from techtree_hermes.services.container import PluginServices
from techtree_hermes.tools import TOOL_HANDLERS

REGENTS_CLI_ARGV = os.environ.get("REGENTS_CLI_ARGV", "")

pytestmark = [
    pytest.mark.real_cli,
    pytest.mark.skipif(
        not REGENTS_CLI_ARGV,
        reason="REGENTS_CLI_ARGV does not name a regents-cli to ask",
    ),
]

RUN_ID = "run_" + "0" * 32


@pytest.fixture
def services(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PluginServices:
    install_regents_from_argv(
        tmp_path / "bin", shlex.split(REGENTS_CLI_ARGV), monkeypatch=monkeypatch
    )
    core = load_embedded_release_core()
    return PluginServices(
        ctx=None,
        root=Path("."),
        release_core=core,
        release_core_digest=release_core_digest(core),
        bridge=CliBridge(),
        plans=InstallPlanStore(),
        sessions=SessionStore(),
        assets=ReleaseSkillProvider(),
    )


def _call(name: str, services: PluginServices, args: dict[str, Any]) -> dict[str, Any]:
    parsed = json.loads(TOOL_HANDLERS[name](services, args))
    assert isinstance(parsed, dict)
    return parsed


def test_the_readiness_tool_answers_from_the_real_doctor(
    services: PluginServices,
) -> None:
    result = _call("techtree_system_check", services, {})

    identifiers = {check["id"] for check in result["checks"]}
    assert "cli_release" in identifiers
    assert identifiers & {"docker_daemon", "active_engine", "techtree_home"}


def test_the_catalog_tool_lists_the_real_catalog(services: PluginServices) -> None:
    result = _call("techtree_climb_list", services, {})

    assert "error" not in result
    assert result["count"] == len(result["climbs"]) > 0


def test_inspecting_the_introductory_climb_returns_its_policy(
    services: PluginServices,
) -> None:
    reference = services.release_core.intro_climb_reference

    result = _call("techtree_climb_inspect", services, {"reference": reference})

    climb = result["climb"]
    assert "error" not in result
    assert climb["data_policy"]
    assert climb["campaign_spec_digest"].startswith("sha256:")
    assert climb["proof_grade"]
    assert climb["task_count"]


def test_an_unknown_climb_comes_back_as_techtrees_own_error(
    services: PluginServices,
) -> None:
    result = _call("techtree_climb_inspect", services, {"reference": "no-such-climb@1"})

    assert result["error"]["code"] == "climb_not_found"


def test_verifying_a_proof_that_does_not_exist_fails_in_band(
    services: PluginServices,
) -> None:
    result = _call("techtree_proof_verify", services, {"run_id": RUN_ID})

    assert result["error"]["code"]


def test_no_read_only_tool_emits_escape_codes(services: PluginServices) -> None:
    for name, args in (
        ("techtree_system_check", {}),
        ("techtree_climb_list", {}),
        (
            "techtree_climb_inspect",
            {"reference": services.release_core.intro_climb_reference},
        ),
    ):
        answer = TOOL_HANDLERS[name](services, dict(args))
        assert "\x1b" not in answer
