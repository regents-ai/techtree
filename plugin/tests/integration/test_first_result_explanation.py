"""A result explained end to end, through the tools. Sections 8.9, 8.21.

The CLI is a real process; the host model is a stub. Nothing is spent, and no
model is called.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest
from support import envelope, install_fake_cli
from techtree_hermes.approvals import InstallPlanStore
from techtree_hermes.bridge import CliBridge
from techtree_hermes.release import load_embedded_release_core, release_core_digest
from techtree_hermes.services.assets import ReleaseSkillProvider
from techtree_hermes.services.container import PluginServices
from techtree_hermes.state import SessionStore
from techtree_hermes.tools import TOOL_HANDLERS

CORE = load_embedded_release_core()
RUN_ID = "run_" + "0" * 32

NARRATIVE = {
    "headline": "The Skill helped on the tasks it was measured on.",
    "verdict": "A clear improvement, on this task set only.",
    "observations": ["Most of the change came from one rule."],
    "caveats": ["The provider does not expose an immutable model revision."],
    "next_step": "Verify the proof before relying on it.",
    "selected_task_refs": ["task-01"],
}

PRESENTATION = {
    "run_id": RUN_ID,
    "campaign_title": "Procedure transfer",
    "comparison_label": "no Skill versus starter Skill v1",
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


class StubLlm:
    """Stands in for ctx.llm, counting completions."""

    def __init__(self, parsed: Any = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.parsed = NARRATIVE if parsed is None else parsed

    def complete_structured(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        from types import SimpleNamespace

        return SimpleNamespace(
            parsed=self.parsed,
            text="{}",
            model="host-model-1",
            provider="host",
            usage=None,
        )


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
        ctx=StubCtx(StubLlm()),
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


def test_a_result_without_an_explanation_is_still_complete(
    services: PluginServices,
) -> None:
    result = _result(services)

    assert result["presentation"]["candidate_score"] == 24.0
    assert result["narrative"] is None
    assert "not been independently reproduced" in result["reproduction"]
    assert services.ctx.llm.calls == []


def test_asking_for_an_explanation_makes_exactly_one_completion(
    services: PluginServices,
) -> None:
    result = _result(services, include_host_explanation=True, channel="terminal")

    assert len(services.ctx.llm.calls) == 1
    assert result["narrative"]["headline"] == NARRATIVE["headline"]
    assert result["presentation"]["wins"] == 22
    assert result["order"][0] == "scores"


def test_the_numbers_are_never_the_models_to_state(services: PluginServices) -> None:
    """Even a well-behaved narrative sits beside the payload, never inside it."""
    result = _result(services, include_host_explanation=True)

    assert result["presentation"]["candidate_score"] == 24.0
    for text in result["narrative"].values():
        assert "24" not in json.dumps(text)


def test_a_narrative_that_invents_a_score_is_dropped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, services: PluginServices
) -> None:
    services = dataclasses.replace(
        services,
        ctx=StubCtx(StubLlm({**NARRATIVE, "headline": "It scored 30/36 overall."})),
    )

    result = _result(services, include_host_explanation=True)

    assert result["narrative"] is None
    assert result["presentation"]["candidate_score"] == 24.0
    assert result["narrative_code"] == "presentation_claim_forbidden"


def test_a_phone_gets_the_same_facts_in_its_own_order(
    services: PluginServices,
) -> None:
    result = _result(services, include_host_explanation=True, channel="gateway")

    assert result["order"][0] == "scores"
    assert "\x1b" not in json.dumps(result)
    assert result["presentation"]["candidate_score"] == 24.0
