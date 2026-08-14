"""Both journeys, end to end. Specification sections 8.18, 8.19, 8.20, 8.21.

Everything here is real except the two things that would cost money: the host
model is a stub, and the Techtree CLI is a fake executable answering from a
script. Every step where a person would have to approve something is asserted
to stop, rather than being driven through.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from support import envelope, install_fake_cli
from techtree_hermes.approvals import InstallPlanStore, ReviewStore
from techtree_hermes.bridge import CliBridge
from techtree_hermes.constants import PLUGIN_ROOT
from techtree_hermes.errors import PluginError
from techtree_hermes.models import ChannelKind, DemoStage
from techtree_hermes.narrative import (
    FIRST_RESULT_LABEL,
    SAME_MEMBERSHIP_DISCLOSURE,
    SECOND_RESULT_ITERATION_LABEL,
    SECOND_RESULT_LABEL,
)
from techtree_hermes.release import load_embedded_release_core, release_core_digest
from techtree_hermes.services.assets import ReleaseSkillProvider, file_digest
from techtree_hermes.services.container import PluginServices
from techtree_hermes.services.presentation import forbidden_second_result_words
from techtree_hermes.services.session import ALLOWED_TRANSITIONS, require_transition
from techtree_hermes.state import SessionStore, latest_session, save_session
from techtree_hermes.tools import TOOL_HANDLERS

#: The committed release leaves its skill-improver coordinate unchosen, and the
#: guided revision refuses to run without one. These journeys are about the
#: flow, so they use a release that names the Skill this build bundles.
IMPROVER_TEXT = (PLUGIN_ROOT / "skills" / "skill-improver" / "SKILL.md").read_text(
    encoding="utf-8"
)
CORE = dataclasses.replace(
    load_embedded_release_core(),
    placeholder_release=False,
    placeholder_fields=(),
    skill_improver_digest=file_digest(IMPROVER_TEXT.encode("utf-8")),
)
FIRST_RUN = "run_" + "1" * 32
SECOND_RUN = "run_" + "2" * 32
FIRST_DRAFT = "draft_" + "1" * 32
SECOND_DRAFT = "draft_" + "2" * 32
TOKEN = "confirmation-token-value"
POLICY = "sha256:" + "3" * 64
ROOT_DIGEST = "sha256:" + "c" * 64
ENTRYPOINT_DIGEST = "sha256:" + "d" * 64
REPORT_DIGEST = "sha256:" + "f" * 64

V1 = (
    "---\nname: branchcode\ndescription: A procedure.\n---\n\n"
    "# BranchCode\n\nAdd seven times the TOTAL characters.\n"
)
V2 = V1.replace("TOTAL characters", "number of DISTINCT characters")

PROPOSAL: dict[str, Any] = {
    "analysis_summary": "Every failure repeats a character.",
    "change_rationale": ["Count distinct characters, not all of them."],
    "revised_skill_markdown": V2,
    "expected_tradeoffs": ["Identifiers with no repeats are unchanged."],
    "confidence": "medium",
}


def _presentation(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "run_id": SECOND_RUN,
        "campaign_title": "Procedure transfer",
        "comparison_label": "Skill v1 versus Skill v2",
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
        "caveats": [],
        "next_actions": [],
    }
    payload.update(overrides)
    return payload


CONTEXT: dict[str, Any] = {
    "schema_version": "techtree.skill-improvement-context.v1",
    "source_run_id": FIRST_RUN,
    "source_report_digest": REPORT_DIGEST,
    "campaign_spec_digest": "sha256:" + "1" * 64,
    "parent_skill_digest": ROOT_DIGEST,
    "parent_skill_entrypoint_digest": ENTRYPOINT_DIGEST,
    "data_policy_digest": POLICY,
    "objective": "Improve the Skill on this Campaign.",
    "current_result": {"decision": "improved"},
    "examples": [
        {
            "task_hash": "sha256:" + "3" * 64,
            "task_label": "task-01",
            "public_prompt": "Compute the BranchCode total for identifier aabbcc.",
            "subject_reply": None,
            "reward": 0.0,
            "outcome": "regressed",
            "public_metrics": {},
            "error_summary": None,
        }
    ],
    "constraints": ["State a rule, not the cases."],
    "prohibited_material": ["expected answers"],
}


class StubLlm:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def complete_structured(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        assert kwargs.get("purpose") == "skill_revision", (
            "the revision proposal is the only host completion in the release"
        )
        return SimpleNamespace(
            parsed=PROPOSAL,
            text="{}",
            model="host-model-1",
            provider="host",
            usage=None,
        )


def _answers(**overrides: dict[str, Any]) -> dict[str, dict[str, Any]]:
    answers = {
        "doctor": envelope(command="doctor", data={"checks": []}),
        "climb list": envelope(command="climb list", data=[{"reference": "x@1"}]),
        "climb show": envelope(
            command="climb show", data={"climb": {"reference": "x@1"}}
        ),
        "run status": envelope(
            command="run status",
            data={
                "run_id": FIRST_RUN,
                "phase": "completed",
                "terminal": True,
                "result_available": True,
                "worker_alive": False,
            },
        ),
        "run result": envelope(
            command="run result",
            data={"report": {"run_id": FIRST_RUN}, "presentation": _presentation()},
        ),
        "uplift context": envelope(
            command="uplift context",
            data={"context": CONTEXT, "relative_path": "context.json"},
        ),
        "uplift skill-source": envelope(
            command="uplift skill-source",
            data={
                "source_run_id": FIRST_RUN,
                "skill_name": "branchcode",
                "skill_root_digest": ROOT_DIGEST,
                "entrypoint_path": "SKILL.md",
                "entrypoint_digest": ENTRYPOINT_DIGEST,
                "entrypoint_size": len(V1),
                "entrypoint_text": V1,
                "file_count": 1,
            },
        ),
        "uplift prepare": envelope(
            command="uplift prepare",
            data={
                "draft_id": SECOND_DRAFT,
                "draft_digest": "sha256:" + "7" * 64,
                "confirmation_token": TOKEN,
                "confirmation_expires_at": "2026-08-13T12:00:00Z",
                "source_run_id": FIRST_RUN,
                "campaign_spec_digest": "sha256:" + "1" * 64,
                "data_policy_digest": POLICY,
                "baseline_skill_digest": ROOT_DIGEST,
                "candidate_skill_digest": "sha256:" + "5" * 64,
                "candidate_label": "revision",
                "included_files": ["SKILL.md"],
                "estimated_episodes": 72,
            },
        ),
        "uplift start": envelope(
            command="uplift start",
            data={"run_id": SECOND_RUN, "draft_id": SECOND_DRAFT, "phase": "created"},
        ),
        "proof verify": envelope(
            command="proof verify",
            data={
                "target": SECOND_RUN,
                "kind": "bundle",
                "verified": True,
                "summary": [],
                "checks": [{"id": "signature", "status": "passed"}],
            },
        ),
    }
    answers.update(overrides)
    return answers


@pytest.fixture
def journey(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PluginServices:
    """A container wired to a fake CLI and a stub host, mid-journey."""
    answers = _answers()
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
        reviews=ReviewStore(),
        sessions=SessionStore(),
        assets=ReleaseSkillProvider(),
    )
    from techtree_hermes.models import DemoSessionState

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
            proposal_id=None,
            second_draft_id=None,
            second_run_id=None,
            second_proof_path=None,
            revision_attempts=0,
            updated_at="2026-08-13T00:00:00+00:00",
        ),
    )
    return container


def _call(services: PluginServices, name: str, **args: Any) -> dict[str, Any]:
    parsed = json.loads(TOOL_HANDLERS[name](services, dict(args)))
    assert isinstance(parsed, dict)
    return parsed


def _stage(services: PluginServices) -> DemoStage:
    session = latest_session(services)
    assert session is not None
    return session.stage


# The terminal journey ---------------------------------------------------------


def test_the_terminal_journey_from_first_result_to_second_receipt(
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

    proposal = _call(
        journey, "techtree_uplift_propose", source_run_id=FIRST_RUN, channel=channel
    )
    assert proposal["started"] is False
    assert "DISTINCT" in proposal["diff"]["unified"]
    assert proposal["data_policy_digest"] == POLICY
    assert _stage(journey) is DemoStage.SECOND_DRAFT_PREPARED

    started = _call(
        journey,
        "techtree_uplift_start",
        draft_id=SECOND_DRAFT,
        confirmation_token=TOKEN,
        data_policy_digest=POLICY,
        channel=channel,
    )
    assert started["data"]["run_id"] == SECOND_RUN
    assert _stage(journey) is DemoStage.SECOND_RUN_ACTIVE

    second = _call(journey, "techtree_run_result", run_id=SECOND_RUN, channel=channel)
    receipt = second["receipt"]
    assert receipt["label"] == SECOND_RESULT_LABEL
    assert receipt["iteration"] == SECOND_RESULT_ITERATION_LABEL
    assert receipt["disclosure"] == SAME_MEMBERSHIP_DISCLOSURE
    assert receipt["source_feedback_report_digest"] == REPORT_DIGEST
    assert second["comparison_labels"] == {
        "baseline": "Skill v1",
        "candidate": "Skill v2",
    }

    proof = _call(journey, "techtree_proof_verify", run_id=SECOND_RUN, channel=channel)
    assert proof["data"]["verified"] is True

    # The revision proposal is the only host completion the journey makes.
    assert len(journey.ctx.llm.calls) == 1
    assert journey.ctx.llm.calls[0]["purpose"] == "skill_revision"


def test_the_second_receipt_never_oversells_itself(journey: PluginServices) -> None:
    """Decision 0007: no sealed, held-out, generalization, or independent wording."""
    _call(journey, "techtree_run_status", run_id=FIRST_RUN)
    _call(journey, "techtree_uplift_propose", source_run_id=FIRST_RUN)
    _call(
        journey,
        "techtree_uplift_start",
        draft_id=SECOND_DRAFT,
        confirmation_token=TOKEN,
        data_policy_digest=POLICY,
    )

    second = _call(journey, "techtree_run_result", run_id=SECOND_RUN)

    words = forbidden_second_result_words(json.dumps(second["receipt"]))
    assert words == []
    assert "not been independently reproduced" in second["receipt"]["reproduction"]


def test_usage_is_reported_with_where_it_came_from(journey: PluginServices) -> None:
    """Decision 0007 R6: never an unsourced number, never a guessed cost."""
    result = _call(journey, "techtree_run_result", run_id=FIRST_RUN)

    usage = result["usage"]
    assert usage["source"] == "run_report"
    assert usage["baseline_tokens"] == 1000
    assert usage["cost_usd"] is None
    assert usage["cost_provenance"] == "unavailable"


# The phone journey ---------------------------------------------------------------


def test_the_phone_journey_is_compact_and_free_of_terminal_codes(
    journey: PluginServices,
) -> None:
    channel = ChannelKind.GATEWAY.value

    for name, args in (
        ("techtree_run_status", {"run_id": FIRST_RUN}),
        ("techtree_run_result", {"run_id": FIRST_RUN}),
        ("techtree_uplift_propose", {"source_run_id": FIRST_RUN}),
    ):
        answer = TOOL_HANDLERS[name](journey, {**args, "channel": channel})
        assert "\x1b" not in answer
        assert "\x00" not in answer
        assert len(answer) <= 4000


def test_the_phone_gets_a_bounded_diff_that_says_it_was_cut(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, journey: PluginServices
) -> None:
    _call(journey, "techtree_run_status", run_id=FIRST_RUN)
    long_v2 = V2 + "".join(f"\n## Rule {n}\n\nDo the thing.\n" for n in range(200))
    journey = dataclasses.replace(
        journey,
        ctx=SimpleNamespace(
            llm=_ScriptedLlm({**PROPOSAL, "revised_skill_markdown": long_v2})
        ),
    )

    proposal = _call(
        journey,
        "techtree_uplift_propose",
        source_run_id=FIRST_RUN,
        channel=ChannelKind.GATEWAY.value,
    )

    assert proposal["diff"]["truncated"] is True
    assert "not shown here" in proposal["diff"]["unified"]
    assert proposal["diff"]["changed_lines"] > 10


class _ScriptedLlm:
    def __init__(self, parsed: dict[str, Any]) -> None:
        self.calls: list[dict[str, Any]] = []
        self.parsed = parsed

    def complete_structured(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(
            parsed=self.parsed,
            text="{}",
            model="host-model-1",
            provider="host",
            usage=None,
        )


def test_a_run_identifier_always_comes_back(journey: PluginServices) -> None:
    _call(journey, "techtree_run_status", run_id=FIRST_RUN)
    _call(journey, "techtree_uplift_propose", source_run_id=FIRST_RUN)

    started = _call(
        journey,
        "techtree_uplift_start",
        draft_id=SECOND_DRAFT,
        confirmation_token=TOKEN,
        data_policy_digest=POLICY,
        channel=ChannelKind.GATEWAY.value,
    )

    assert started["data"]["run_id"] == SECOND_RUN


# Nothing advances itself ------------------------------------------------------------


@pytest.mark.parametrize(
    ("current", "forbidden"),
    [
        (DemoStage.CLI_INSTALL_REQUIRED, DemoStage.FIRST_DRAFT_PREPARED),
        (DemoStage.FIRST_DRAFT_PREPARED, DemoStage.FIRST_RESULT_READY),
        (DemoStage.FIRST_RESULT_READY, DemoStage.SECOND_DRAFT_PREPARED),
        (DemoStage.REVISION_PROPOSAL_READY, DemoStage.SECOND_RUN_ACTIVE),
        (DemoStage.SECOND_RUN_ACTIVE, DemoStage.REVISION_PROPOSAL_READY),
        (DemoStage.COMPLETE, DemoStage.SECOND_RUN_ACTIVE),
    ],
)
def test_the_journey_never_skips_a_human_decision(
    current: DemoStage, forbidden: DemoStage
) -> None:
    """Specification section 10.4: these jumps are nobody's to make but a person's."""
    with pytest.raises(PluginError, match="does not go from"):
        require_transition(current, forbidden)


def test_every_allowed_step_is_one_the_specification_lists() -> None:
    assert ALLOWED_TRANSITIONS[DemoStage.FIRST_RESULT_READY] == frozenset(
        {DemoStage.REVISION_PROPOSAL_READY}
    )
    assert ALLOWED_TRANSITIONS[DemoStage.SECOND_DRAFT_PREPARED] == frozenset(
        {DemoStage.SECOND_RUN_ACTIVE}
    )
    assert ALLOWED_TRANSITIONS[DemoStage.COMPLETE] == frozenset()


def test_a_result_that_did_not_verify_is_never_called_an_improvement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A negative or unverified second result is an honest product outcome."""
    answers = _answers(
        **{
            "run result": envelope(
                command="run result",
                data={
                    "report": {"run_id": SECOND_RUN},
                    "presentation": _presentation(
                        decision="rejected", verification_status="proof_invalid"
                    ),
                },
            )
        }
    )
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
    from techtree_hermes.models import DemoSessionState

    services = PluginServices(
        ctx=SimpleNamespace(llm=StubLlm()),
        root=tmp_path,
        release_core=CORE,
        release_core_digest=release_core_digest(CORE),
        bridge=CliBridge(),
        plans=InstallPlanStore(),
        reviews=ReviewStore(),
        sessions=SessionStore(),
        assets=ReleaseSkillProvider(),
    )
    save_session(
        services,
        DemoSessionState(
            demo_id="demo_" + "1" * 32,
            release_core_digest=release_core_digest(CORE),
            climb_reference="procedure-transfer-dev@1",
            stage=DemoStage.SECOND_RUN_ACTIVE,
            first_draft_id=FIRST_DRAFT,
            first_run_id=FIRST_RUN,
            first_proof_path=None,
            source_skill_v1_digest=ROOT_DIGEST,
            proposal_id=None,
            second_draft_id=SECOND_DRAFT,
            second_run_id=SECOND_RUN,
            second_proof_path=None,
            revision_attempts=1,
            updated_at="2026-08-13T00:00:00+00:00",
        ),
    )

    result = _call(services, "techtree_run_result", run_id=SECOND_RUN)

    assert result["outcome"]["candidate_improved"] is None
    assert "did not verify" in result["outcome"]["summary"]
    assert result["leads_with"] == "verification_failure"
    assert "narrative" not in result
    assert services.ctx.llm.calls == []
