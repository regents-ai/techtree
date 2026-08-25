"""A result relayed end to end, through the tools. Sections 8.9, 8.21.

The CLI is a real process. A host model is offered and counted, and the point
of the file is that it is never used: decision 0009 removed the host-model
presentation completion from the release, so `techtree_run_result` relays what
Techtree said and nothing else.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from support import envelope, founder_result_payload, install_fake_cli
from techtree_hermes.approvals import InstallPlanStore
from techtree_hermes.bridge import CliBridge
from techtree_hermes.release import load_embedded_release_core, release_core_digest
from techtree_hermes.schemas import all_tool_schemas
from techtree_hermes.services.assets import ReleaseSkillProvider
from techtree_hermes.services.container import PluginServices
from techtree_hermes.state import SessionStore
from techtree_hermes.tools import TOOL_HANDLERS

CORE = load_embedded_release_core()
RUN_ID = "run_" + "0" * 32

PRESENTATION = {
    "run_id": RUN_ID,
    "campaign_title": "Hello World Skill Uplift",
    "comparison_label": "no Skill versus hello-world-starter-v1",
    "baseline_score": 2.0,
    "candidate_score": 24.0,
    "absolute_delta": 22.0,
    "wins": 22,
    "losses": 1,
    "ties": 13,
    "task_rows": [{"position": 0, "task_label": "task-01", "outcome": "win"}],
    "decision": "improved",
    "proof_grade": "P1",
    "verification_status": "verified",
    "caveats": [],
    "next_actions": [],
}


class CountingLlm:
    """Stands in for ctx.llm. Any call at all is a failure of the contract."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def complete_structured(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        raise AssertionError("a result must never be worded by a host model")


class StubCtx:
    def __init__(self, llm: Any) -> None:
        self.llm = llm


@pytest.fixture
def services(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PluginServices:
    answers = {
        "run result": envelope(
            command="run result",
            data={"report": {"run_id": RUN_ID}, "presentation": PRESENTATION},
        )
    }
    body = (
        f"answers = {answers!r}\n"
        "key = ' '.join(a for a in argv if not a.startswith('--'))\n"
        "for name in answers:\n"
        "    if key.startswith(name):\n"
        "        print(json.dumps(answers[name]))\n"
        "        break\n"
        "else:\n"
        "    sys.exit(2)\n"
    )
    install_fake_cli(tmp_path / "bin", body=body, monkeypatch=monkeypatch)
    return PluginServices(
        ctx=StubCtx(CountingLlm()),
        root=tmp_path,
        release_core=CORE,
        release_core_digest=release_core_digest(CORE),
        bridge=CliBridge(),
        plans=InstallPlanStore(),
        sessions=SessionStore(),
        assets=ReleaseSkillProvider(),
    )


def _result(services: PluginServices, **args: Any) -> dict[str, Any]:
    answer = json.loads(
        TOOL_HANDLERS["techtree_run_result"](services, {"run_id": RUN_ID, **args})
    )
    assert isinstance(answer, dict)
    return answer


def test_the_result_is_relayed_whole(services: PluginServices) -> None:
    result = _result(services, channel="terminal")

    assert result["presentation"]["candidate_score"] == 24.0
    assert result["presentation"]["wins"] == 22
    assert result["order"][0] == "scores"
    assert "not been independently reproduced" in result["reproduction"]


def test_no_host_completion_is_ever_made(services: PluginServices) -> None:
    """The one promise decision 0009 made about this path."""
    _result(services, channel="terminal")
    _result(services, channel="gateway")

    assert services.ctx.llm.calls == []


def test_the_result_carries_no_model_written_words(services: PluginServices) -> None:
    result = _result(services, channel="terminal")

    assert "narrative" not in result
    assert "narrative_note" not in result
    assert "narration_allowed" not in result
    assert result["result_label"] == "Hello World Uplift Receipt"


def test_the_tool_offers_no_way_to_ask_for_one() -> None:
    schema = all_tool_schemas()["techtree_run_result"]

    assert set(schema["properties"]) == {"run_id", "channel"}
    assert "host model" not in schema["description"]


def test_a_phone_gets_the_same_facts_in_its_own_order(
    services: PluginServices,
) -> None:
    result = _result(services, channel="gateway")

    assert result["order"][0] == "scores"
    assert "\x1b" not in json.dumps(result)
    assert result["presentation"]["candidate_score"] == 24.0


def test_nothing_in_the_released_flow_reaches_the_narration_code() -> None:
    """Decision 0009 lets the narration modules stay only while nothing calls them.

    Static, because reachability is the promise: a released path that could
    ask a model to word a result would be a release defect whether or not any
    particular test happened to walk it.
    """
    from techtree_hermes.constants import PLUGIN_ROOT

    narration = (
        "build_presentation_input",
        "presentation_output_schema",
        "parse_presentation_narrative",
        "validate_narrative",
        "bounded_narrative",
    )
    homes = {"narrative.py", "guards.py"}

    callers = {
        source.relative_to(PLUGIN_ROOT).as_posix()
        for source in PLUGIN_ROOT.rglob("*.py")
        if source.name not in homes
        and not any(
            part.startswith(".") for part in source.relative_to(PLUGIN_ROOT).parts
        )
        and any(f"{name}(" in source.read_text("utf-8") for name in narration)
    }

    assert callers == set()


# A real Climb's result, on a phone -----------------------------------------------


@pytest.fixture
def founder_services(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PluginServices:
    """A CLI answering with the comparison the founder's journey actually ran."""
    payload = founder_result_payload()
    answers = {
        "run result": envelope(
            command="run result",
            data={"report": {"run_id": payload["run_id"]}, "presentation": payload},
        )
    }
    body = (
        f"answers = {answers!r}\n"
        "key = ' '.join(a for a in argv if not a.startswith('--'))\n"
        "for name in answers:\n"
        "    if key.startswith(name):\n"
        "        print(json.dumps(answers[name]))\n"
        "        break\n"
        "else:\n"
        "    sys.exit(2)\n"
    )
    install_fake_cli(tmp_path / "bin", body=body, monkeypatch=monkeypatch)
    return PluginServices(
        ctx=StubCtx(CountingLlm()),
        root=tmp_path,
        release_core=CORE,
        release_core_digest=release_core_digest(CORE),
        bridge=CliBridge(),
        plans=InstallPlanStore(),
        sessions=SessionStore(),
        assets=ReleaseSkillProvider(),
    )


def test_a_phone_gets_the_result_and_not_an_apology_for_its_size(
    founder_services: PluginServices,
) -> None:
    """Ticket tzz. A thirty-six task result is the ordinary case, not an edge one.

    An answer over the channel's budget is replaced whole by a note saying so,
    which on a phone is the difference between a result and nothing at all. The
    compact view exists precisely so that this fits, so this asserts it does.
    """
    answer = json.loads(
        TOOL_HANDLERS["techtree_run_result"](
            founder_services,
            {"run_id": founder_result_payload()["run_id"], "channel": "gateway"},
        )
    )

    assert answer.get("truncated") is not True
    assert answer["presentation"]["baseline_tasks_scored_full"] == 0
    assert answer["presentation"]["candidate_tasks_scored_full"] == 24
    assert answer["presentation"]["task_count"] == 36
    assert answer["presentation"]["derived_cost"]["usd"] == 4.87
    assert answer["presentation"]["candidate_model_turns"] == 412
    assert answer["presentation"]["candidate_rate_limited_calls"] == 11
    assert "not provably the same model build" in json.dumps(answer)


def test_the_terminal_still_gets_every_task_row(
    founder_services: PluginServices,
) -> None:
    """The table is kept out of a phone's answer, not out of the terminal's."""
    answer = json.loads(
        TOOL_HANDLERS["techtree_run_result"](
            founder_services,
            {"run_id": founder_result_payload()["run_id"], "channel": "terminal"},
        )
    )

    assert len(answer["presentation"]["task_rows"]) == 36
    assert answer["data"]["presentation"]["candidate_tasks_scored_full"] == 24
