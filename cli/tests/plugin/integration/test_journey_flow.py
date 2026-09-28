"""The journey, end to end. Specification sections 8.18, 8.20, 8.21.

Everything here is real except the two things that would cost money: the host
model is a stub, and the Techtree CLI is a fake executable answering from a
script. Every step where a person would have to approve something is asserted
to stop, rather than being driven through.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from support import envelope, install_fake_cli, operation_for
from techtree_hermes.cli.bridge import CliBridge
from techtree_hermes.cli.errors import PluginError
from techtree_hermes.cli.release import load_embedded_release_core, release_core_digest
from techtree_hermes.host.state import SessionStore, latest_session, save_session
from techtree_hermes.services.approvals import InstallPlanStore
from techtree_hermes.services.assets import ReleaseSkillProvider
from techtree_hermes.services.container import PluginServices
from techtree_hermes.services.models import ChannelKind, DemoSessionState, DemoStage
from techtree_hermes.services.narrative import FIRST_RESULT_LABEL
from techtree_hermes.services.session import ALLOWED_TRANSITIONS, require_transition
from techtree_hermes.tools import TOOL_HANDLERS

CORE = load_embedded_release_core()
FIRST_RUN = "run_" + "1" * 32
FIRST_DRAFT = "draft_" + "1" * 32
ROOT_DIGEST = "sha256:" + "c" * 64


def _presentation(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "run_id": FIRST_RUN,
        "campaign_title": "Procedure transfer",
        "comparison_label": "No tested Skill versus Skill v1",
        "baseline_score": 24.0,
        "candidate_score": 32.0,
        "absolute_delta": 8.0,
        "wins": 9,
        "losses": 1,
        "ties": 26,
        "task_rows": [{"position": 0, "task_label": "task-01", "outcome": "win"}],
        "decision": "improved",
        "proof_grade": "P1",
        "verification_status": "verified",
        "baseline_tokens": 1000,
        "candidate_tokens": 1100,
        "baseline_seconds": 30.0,
        "candidate_seconds": 31.0,
        "economics_source": "episode_receipts",
        "cost_usd": None,
        "cost_provenance": "unavailable",
        "derived_cost": None,
        "cost_unavailable_reason": (
            "This run wrote no signed execution record, so there is no signed "
            "token total to work a cost out from."
        ),
        "caveats": [],
        "next_actions": [],
    }
    payload.update(overrides)
    return payload


class StubLlm:
    """A host model that records every request, so a test can see there were none."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def complete_structured(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        raise AssertionError("the journey makes no host completion")


def _answers(**overrides: dict[str, Any]) -> dict[str, dict[str, Any]]:
    answers = {
        "doctor": envelope(operation=operation_for("doctor"), facts={"checks": []}),
        "climb list": envelope(
            operation=operation_for("climb list"),
            facts={"climbs": [{"reference": "x@1"}]},
        ),
        "climb show": envelope(
            operation=operation_for("climb show"), facts={"climb": {"reference": "x@1"}}
        ),
        "run status": envelope(
            operation=operation_for("run status"),
            facts={
                "run_id": FIRST_RUN,
                "phase": "completed",
                "terminal": True,
                "result_available": True,
                "worker_alive": False,
            },
        ),
        "run result": envelope(
            operation=operation_for("run result"),
            facts={"report": {"run_id": FIRST_RUN}, "presentation": _presentation()},
        ),
        "proof verify": envelope(
            operation=operation_for("proof verify"),
            facts={
                "target": FIRST_RUN,
                "kind": "bundle",
                "verified": True,
                "summary": [],
                "checks": [{"id": "signature", "status": "passed"}],
            },
        ),
    }
    answers.update(overrides)
    return answers


def _services(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    answers: dict[str, dict[str, Any]],
) -> PluginServices:
    """A container wired to a fake CLI and a stub host, mid-journey."""
    body = (
        f"answers = {answers!r}\n"
        "key = ' '.join(a for a in argv if not a.startswith('--'))\n"
        "for name in sorted(answers, key=len, reverse=True):\n"
        "    if key.startswith(name):\n"
        "        print(json.dumps(answers[name]))\n"
        "        break\n"
        "else:\n"
        "    sys.exit(2)\n"
    )
    install_fake_cli(tmp_path / "bin", body=body, monkeypatch=monkeypatch)

    container = PluginServices(
        ctx=SimpleNamespace(llm=StubLlm()),
        root=tmp_path,
        release_core=CORE,
        release_core_digest=release_core_digest(CORE),
        bridge=CliBridge(),
        plans=InstallPlanStore(),
        sessions=SessionStore(),
        assets=ReleaseSkillProvider(),
    )
    save_session(
        container,
        DemoSessionState(
            demo_id="demo_" + "0" * 32,
            release_core_digest=release_core_digest(CORE),
            climb_reference="procedure-transfer-dev@1",
            stage=DemoStage.FIRST_RUN_ACTIVE,
            first_draft_id=FIRST_DRAFT,
            first_run_id=FIRST_RUN,
            first_proof_path=None,
            source_skill_v1_digest=ROOT_DIGEST,
            updated_at="2026-08-13T00:00:00+00:00",
        ),
    )
    return container


@pytest.fixture
def journey(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PluginServices:
    return _services(tmp_path, monkeypatch, _answers())


def _call(services: PluginServices, name: str, **args: Any) -> dict[str, Any]:
    parsed = json.loads(TOOL_HANDLERS[name](services, dict(args)))
    assert isinstance(parsed, dict)
    return parsed


def _stage(services: PluginServices) -> DemoStage:
    session = latest_session(services)
    assert session is not None
    return session.stage


# The terminal journey ---------------------------------------------------------


def test_the_terminal_journey_from_status_to_checked_proof(
    journey: PluginServices,
) -> None:
    channel = ChannelKind.TERMINAL.value

    status = _call(journey, "techtree_run_status", run_id=FIRST_RUN, channel=channel)
    assert status["summary"]["finished"] is True
    assert _stage(journey) is DemoStage.FIRST_RESULT_READY

    first = _call(
        journey,
        "techtree_run_result",
        run_id=FIRST_RUN,
        channel=channel,
    )
    assert first["order"][0] == "scores"
    assert first["presentation"]["candidate_score"] == 32.0
    assert first["result_label"] == FIRST_RESULT_LABEL
    assert "narrative" not in first
    assert "receipt" not in first

    proof = _call(journey, "techtree_proof_verify", run_id=FIRST_RUN, channel=channel)
    assert proof["facts"]["verified"] is True

    assert journey.ctx.llm.calls == []


def test_usage_is_reported_with_where_it_came_from(journey: PluginServices) -> None:
    """Decision 0007 R6: never an unsourced number, never a guessed cost."""
    result = _call(journey, "techtree_run_result", run_id=FIRST_RUN)

    usage = result["usage"]
    assert usage["source"] == "episode_receipts"
    assert usage["baseline_tokens"] == 1000
    assert usage["cost_usd"] is None
    assert usage["derived_cost"] is None
    assert usage["cost_provenance"] == "unavailable"
    assert "no signed execution record" in usage["cost_unavailable_reason"]


# The phone journey ---------------------------------------------------------------


def test_the_phone_journey_is_compact_and_free_of_terminal_codes(
    journey: PluginServices,
) -> None:
    channel = ChannelKind.GATEWAY.value

    for name, args in (
        ("techtree_run_status", {"run_id": FIRST_RUN}),
        ("techtree_run_result", {"run_id": FIRST_RUN}),
    ):
        answer = TOOL_HANDLERS[name](journey, {**args, "channel": channel})
        assert "\x1b" not in answer
        assert "\x00" not in answer
        assert len(answer) <= 4000


# Nothing advances itself ------------------------------------------------------------


@pytest.mark.parametrize(
    ("current", "forbidden"),
    [
        (DemoStage.CLI_INSTALL_REQUIRED, DemoStage.FIRST_DRAFT_PREPARED),
        (DemoStage.FIRST_DRAFT_PREPARED, DemoStage.FIRST_RESULT_READY),
    ],
)
def test_the_journey_never_skips_a_human_decision(
    current: DemoStage, forbidden: DemoStage
) -> None:
    """Specification section 10.4: these jumps are nobody's to make but a person's."""
    with pytest.raises(PluginError, match="does not go from"):
        require_transition(current, forbidden)


def test_every_allowed_step_is_one_the_specification_lists() -> None:
    assert ALLOWED_TRANSITIONS[DemoStage.FIRST_RESULT_READY] == frozenset()


def test_a_result_that_did_not_verify_is_never_called_an_improvement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A negative or unverified result is an honest product outcome."""
    answers = _answers(
        **{
            "run result": envelope(
                operation=operation_for("run result"),
                facts={
                    "report": {"run_id": FIRST_RUN},
                    "presentation": _presentation(
                        decision="rejected", verification_status="proof_invalid"
                    ),
                },
            )
        }
    )
    services = _services(tmp_path, monkeypatch, answers)

    result = _call(services, "techtree_run_result", run_id=FIRST_RUN)

    assert result["outcome"]["candidate_improved"] is None
    assert "did not verify" in result["outcome"]["summary"]
    assert result["leads_with"] == "verification_failure"
    assert "narrative" not in result
    assert services.ctx.llm.calls == []
