"""One revision, reviewed before anything runs. Sections 8.15, 8.16, 8.21.

The CLI is a real process answering from a script; the host model is a stub.
No model is called, nothing is spent, and no run is ever started.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from support import envelope, install_fake_cli
from techtree_hermes.approvals import InstallPlanStore
from techtree_hermes.bridge import CliBridge
from techtree_hermes.constants import PLUGIN_ROOT
from techtree_hermes.models import DemoSessionState, DemoStage
from techtree_hermes.release import load_embedded_release_core, release_core_digest
from techtree_hermes.schemas import all_tool_schemas
from techtree_hermes.services.assets import ReleaseSkillProvider, file_digest
from techtree_hermes.services.container import PluginServices
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
RUN_ID = "run_" + "0" * 32
SECOND_RUN_ID = "run_" + "2" * 32
DRAFT_ID = "draft_" + "0" * 32
TOKEN = "confirmation-token-value"
POLICY = "sha256:" + "3" * 64
ROOT_DIGEST = "sha256:" + "c" * 64
ENTRYPOINT_DIGEST = "sha256:" + "d" * 64

V1 = """---
name: branchcode
description: A procedure.
---

# BranchCode

## Step 5

Add seven times the TOTAL number of characters.
"""

V2 = V1.replace("TOTAL number", "number of DISTINCT")

PROPOSAL: dict[str, Any] = {
    "analysis_summary": "Every failure is an identifier with a repeated character.",
    "change_rationale": ["Step 5 should count distinct characters."],
    "revised_skill_markdown": V2,
    "expected_tradeoffs": ["Identifiers with no repeats behave as before."],
    "confidence": "medium",
}

CONTEXT: dict[str, Any] = {
    "schema_version": "techtree.skill-improvement-context.v1",
    "source_run_id": RUN_ID,
    "source_report_digest": "sha256:" + "f" * 64,
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
    """Stands in for ctx.llm, and refuses to be asked twice.

    Decision 0015 s4: one completion means one outbound generation request.
    Raising on the second ask means a retry anywhere in the tool path fails
    here loudly, instead of passing a count nobody looked at.
    """

    def __init__(self, parsed: Any = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.parsed = PROPOSAL if parsed is None else parsed

    def complete_structured(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if len(self.calls) > 1:
            raise AssertionError(
                "the guided flow made a second outbound generation request; "
                f"one turn allows one ({len(self.calls)} seen)"
            )
        return SimpleNamespace(
            parsed=self.parsed,
            text="{}",
            model="host-model-1",
            provider="host",
            usage=None,
            request_id="req_0123456789",
            response_id="resp_9876543210",
        )


def _answers() -> dict[str, dict[str, Any]]:
    return {
        "uplift context": envelope(
            command="uplift context",
            data={"context": CONTEXT, "relative_path": "context.json"},
        ),
        "uplift skill-source": envelope(
            command="uplift skill-source",
            data={
                "source_run_id": RUN_ID,
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
                "draft_id": DRAFT_ID,
                "draft_digest": "sha256:" + "1" * 64,
                "confirmation_token": TOKEN,
                "confirmation_expires_at": "2026-08-13T12:00:00Z",
                "source_run_id": RUN_ID,
                "campaign_spec_digest": "sha256:" + "2" * 64,
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
            data={"run_id": SECOND_RUN_ID, "draft_id": DRAFT_ID, "phase": "created"},
        ),
    }


@pytest.fixture
def services(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PluginServices:
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
        sessions=SessionStore(),
        assets=ReleaseSkillProvider(),
    )
    save_session(
        container,
        DemoSessionState(
            demo_id="demo_" + "0" * 32,
            release_core_digest=release_core_digest(CORE),
            climb_reference="procedure-transfer-dev@1",
            stage=DemoStage.FIRST_RESULT_READY,
            first_draft_id=None,
            first_run_id=RUN_ID,
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


def _propose(services: PluginServices, **args: Any) -> dict[str, Any]:
    """Call the tool Hermes only dispatches after a person confirmed it."""
    return _call(services, "techtree_uplift_propose", source_run_id=RUN_ID, **args)


# The proposal stops for review ------------------------------------------------


def test_a_proposal_prepares_a_comparison_and_starts_nothing(
    services: PluginServices,
) -> None:
    result = _propose(services, channel="terminal")

    assert result["ok"] is True
    assert result["started"] is False
    assert result["draft_id"] == DRAFT_ID
    assert result["next_action"]["requires_user_confirmation"] is True
    assert len(services.ctx.llm.calls) == 1


def test_the_diff_is_shown_with_the_policy_and_the_estimate(
    services: PluginServices,
) -> None:
    result = _propose(services)

    assert "DISTINCT" in result["diff"]["unified"]
    assert result["diff"]["changed_lines"] == 2
    assert result["data_policy_digest"] == POLICY
    assert result["estimated_episodes"] == 72
    assert result["proposal"]["confidence"] == "medium"


def test_the_proposal_records_what_it_was_made_from(
    services: PluginServices,
) -> None:
    provenance = _propose(services)["provenance"]

    assert provenance["source_skill_root_digest"] == ROOT_DIGEST
    assert provenance["source_skill_entrypoint_digest"] == ENTRYPOINT_DIGEST
    assert provenance["skill_improver_digest"] == CORE.skill_improver_digest
    assert provenance["revision_attempt"] == 1
    assert provenance["host_model_id"] == "host-model-1"
    for name in (
        "improvement_context_digest",
        "output_schema_digest",
        "complete_request_digest",
        "host_response_digest",
    ):
        assert provenance[name].startswith("sha256:")


def test_the_plugin_keeps_no_copy_of_the_proposed_skill(
    services: PluginServices, tmp_path: Path
) -> None:
    """Techtree owns the snapshot; the plugin's staging file is gone."""
    _propose(services)

    staged = list(tmp_path.glob("**/techtree-proposal-*"))
    assert staged == []


def test_what_survives_a_restart_is_techtrees_draft_not_plugin_memory(
    services: PluginServices,
) -> None:
    """The plugin remembers nothing durable; the draft identifier is the thread."""
    result = _propose(services)

    restarted = dataclasses.replace(services, sessions=SessionStore())

    assert latest_session(restarted) is None
    # And the draft is still Techtree's to start, by identifier.
    assert result["draft_id"] == DRAFT_ID


# Turn accounting ----------------------------------------------------------------


def test_a_second_proposal_is_refused(services: PluginServices) -> None:
    _propose(services)

    second = _propose(services)

    assert second["ok"] is False
    assert second["code"] == "improvement_attempt_already_used"
    assert len(services.ctx.llm.calls) == 1


def test_an_unusable_proposal_still_uses_the_turn(
    services: PluginServices,
) -> None:
    """The trap: a refused proposal must not hand the attempt back."""
    services = dataclasses.replace(
        services,
        ctx=SimpleNamespace(
            llm=StubLlm({**PROPOSAL, "revised_skill_markdown": "Apply this patch."})
        ),
    )

    first = _propose(services)
    assert first["ok"] is False

    session = latest_session(services)
    assert session is not None
    assert session.revision_attempts == 1

    second = _propose(services)
    assert second["code"] == "improvement_attempt_already_used"
    assert len(services.ctx.llm.calls) == 1


# The second run ---------------------------------------------------------------------


def test_the_second_run_starts_once_the_diff_and_policy_were_shown(
    services: PluginServices,
) -> None:
    _propose(services)

    started = _call(
        services,
        "techtree_uplift_start",
        draft_id=DRAFT_ID,
        confirmation_token=TOKEN,
        data_policy_digest=POLICY,
    )

    assert started["ok"] is True
    assert started["data"]["run_id"] == SECOND_RUN_ID
    session = latest_session(services)
    assert session is not None
    assert session.stage is DemoStage.SECOND_RUN_ACTIVE


def test_a_build_whose_release_named_no_improver_keeps_its_turn(
    services: PluginServices,
) -> None:
    """Decision 0010: the verified Skill steers the turn, or there is no turn.

    A build that never chose the Skill says so, and the session's one revision
    is still there afterwards — a release coordinate nobody bound is not a
    reason to spend someone's attempt.
    """
    embedded = load_embedded_release_core()
    placeholder = dataclasses.replace(
        services,
        release_core=dataclasses.replace(
            embedded,
            placeholder_release=True,
            placeholder_fields=(
                *embedded.placeholder_fields,
                "skill_improver_digest",
            ),
            skill_improver_digest="sha256:" + "0" * 64,
        ),
    )
    started = latest_session(services)
    assert started is not None
    save_session(placeholder, dataclasses.replace(started, revision_attempts=0))

    answer = json.loads(
        TOOL_HANDLERS["techtree_uplift_propose"](placeholder, {"source_run_id": RUN_ID})
    )

    assert answer["ok"] is False
    assert answer["code"] == "founder_skill_missing"
    assert "has not chosen its skill-improver" in answer["message"]
    unspent = latest_session(placeholder)
    assert unspent is not None
    assert unspent.revision_attempts == 0
    assert placeholder.ctx.llm.calls == []


# One outbound generation request -----------------------------------------------------


def test_the_tool_makes_exactly_one_outbound_request(
    services: PluginServices,
) -> None:
    """Decision 0015 s4, through `techtree_uplift_propose` itself."""
    answer = _propose(services, channel="terminal")

    assert len(services.ctx.llm.calls) == 1
    accounting = answer["request_accounting"]
    assert accounting["invocation_count"] == 1
    assert accounting["outbound_request_count"] == 1
    assert accounting["provider_request_id"] == "req_0123456789"
    assert accounting["provider_response_id"] == "resp_9876543210"
    assert (
        accounting["complete_request_digest"]
        == answer["provenance"]["complete_request_digest"]
    )
    assert (
        accounting["host_response_digest"]
        == answer["provenance"]["host_response_digest"]
    )


def test_a_spent_turn_issues_no_further_request(services: PluginServices) -> None:
    """The second call is refused by the session, before any provider call."""
    _propose(services, channel="terminal")

    # Confirmed again, so the refusal is the spent turn and not the gate.
    answer = _propose(services, channel="terminal")

    assert answer["ok"] is False
    assert answer["code"] == "improvement_attempt_already_used"
    assert len(services.ctx.llm.calls) == 1


def test_a_phone_gets_the_proposal_without_the_request_accounting(
    services: PluginServices,
) -> None:
    """A bounded channel drops the record whole rather than trimming it."""
    answer = _propose(services, channel="gateway")

    assert answer["ok"] is True
    assert answer["request_accounting"] is None
    assert answer["provenance"]["complete_request_digest"].startswith("sha256:")
    assert len(services.ctx.llm.calls) == 1


# The approval boundary ----------------------------------------------------------------
#
# Decision 0019 s2. The boundary is Hermes's: this tool is declared as one a
# human confirms, so the call only arrives after a person answered the host's
# own approval surface. What the plugin owes is that the decision was
# informed, and that the approved call does exactly what was described.


def test_the_tool_declares_itself_as_one_a_human_must_confirm() -> None:
    """The whole mechanism now: Hermes reads this and asks before dispatching."""
    described = all_tool_schemas()["techtree_uplift_propose"]["description"]

    assert "REQUIRES USER CONFIRMATION" in described


def test_the_declaration_carries_the_disclosure_it_has_to_carry() -> None:
    """Decision 0018's four elements, in the place Hermes shows before asking."""
    described = " ".join(
        all_tool_schemas()["techtree_uplift_propose"]["description"].split()
    ).lower()

    assert "model provider configured for host hermes" in described
    for withheld in (
        "raw episodes",
        "traces",
        "hidden answers",
        "proof bundles",
        "private keys",
        "provider credentials",
    ):
        assert withheld in described, withheld
    assert "one model-generation request" in described
    assert "may be unusable or may fail to improve the score" in described


def test_the_plugin_mints_no_approval_of_its_own(services: PluginServices) -> None:
    """A model cannot approve its own action, because approving is not an argument.

    There is no token to supply, no store to satisfy, and no argument whose
    presence makes the plugin proceed. The tool takes the run to revise and
    nothing else, so the only thing standing between a model and this call is
    the host's approval surface — which the model does not answer.
    """
    schema = all_tool_schemas()["techtree_uplift_propose"]

    assert set(schema["properties"]) == {"source_run_id", "channel"}
    assert schema["required"] == ["source_run_id"]
    assert not hasattr(services, "disclosures")
    assert not hasattr(services, "reviews")


def test_the_approved_call_does_exactly_what_was_described(
    services: PluginServices,
) -> None:
    """One request, one proposal, nothing started."""
    answer = _propose(services, channel="terminal")

    assert answer["ok"] is True
    assert answer["started"] is False
    assert len(services.ctx.llm.calls) == 1
    assert answer["request_accounting"]["outbound_request_count"] == 1


def test_the_second_run_approval_names_the_exact_draft(
    services: PluginServices,
) -> None:
    """Decision 0019 s2: the human approves a draft, and that draft is started."""
    proposal = _propose(services, channel="terminal")
    draft_id = proposal["draft_id"]

    assert proposal["next_action"]["tool"] == "techtree_uplift_start"
    assert proposal["next_action"]["requires_user_confirmation"] is True

    started = _call(
        services,
        "techtree_uplift_start",
        draft_id=draft_id,
        confirmation_token=proposal["confirmation_token"],
        data_policy_digest=proposal["data_policy_digest"],
        channel="terminal",
    )

    assert started["ok"] is True
    approval = started["approval"]
    assert approval["kind"] == "run.approved"
    assert approval["draft_id"] == draft_id
    assert approval["actor"] == "human_via_hermes"
    datetime.fromisoformat(approval["approved_at"])
