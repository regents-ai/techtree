"""One revision, reviewed before anything runs. Sections 8.15, 8.16, 8.21.

The CLI is a real process answering from a script; the host model is a stub.
No model is called, nothing is spent, and no run is ever started.
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
from techtree_hermes.models import DemoSessionState, DemoStage
from techtree_hermes.release import load_embedded_release_core, release_core_digest
from techtree_hermes.services.assets import ReleaseSkillProvider
from techtree_hermes.services.container import PluginServices
from techtree_hermes.state import SessionStore, latest_session, save_session
from techtree_hermes.tools import TOOL_HANDLERS

CORE = load_embedded_release_core()
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
    """Stands in for ctx.llm, counting completions."""

    def __init__(self, parsed: Any = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.parsed = PROPOSAL if parsed is None else parsed

    def complete_structured(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(
            parsed=self.parsed,
            text="{}",
            model="host-model-1",
            provider="host",
            usage=None,
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
        reviews=ReviewStore(),
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

    assert provenance["parent_skill_root_digest"] == ROOT_DIGEST
    assert provenance["parent_skill_entrypoint_digest"] == ENTRYPOINT_DIGEST
    assert provenance["revision_attempt"] == 1
    assert provenance["host_model_id"] == "host-model-1"


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

    restarted = dataclasses.replace(
        services, sessions=SessionStore(), reviews=ReviewStore()
    )

    assert latest_session(restarted) is None
    assert restarted.reviews.count() == 0
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


def test_the_second_run_never_starts_without_the_diff_being_shown(
    services: PluginServices,
) -> None:
    """Specification section 16, at the tool that would spend the money."""
    result = _call(
        services,
        "techtree_uplift_start",
        draft_id=DRAFT_ID,
        confirmation_token=TOKEN,
        data_policy_digest=POLICY,
    )

    assert result["ok"] is False
    assert result["code"] == "second_run_not_reviewed"


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


def test_accepting_a_policy_that_was_never_shown_is_refused(
    services: PluginServices,
) -> None:
    _propose(services)

    result = _call(
        services,
        "techtree_uplift_start",
        draft_id=DRAFT_ID,
        confirmation_token=TOKEN,
        data_policy_digest="sha256:" + "9" * 64,
    )

    assert result["ok"] is False
    assert result["code"] == "second_run_not_reviewed"


def test_the_approval_is_single_use(services: PluginServices) -> None:
    _propose(services)
    first = _call(
        services,
        "techtree_uplift_start",
        draft_id=DRAFT_ID,
        confirmation_token=TOKEN,
        data_policy_digest=POLICY,
    )
    assert first["ok"] is True

    again = _call(
        services,
        "techtree_uplift_start",
        draft_id=DRAFT_ID,
        confirmation_token=TOKEN,
        data_policy_digest=POLICY,
    )

    assert again["ok"] is False
    assert again["code"] == "second_run_not_reviewed"
