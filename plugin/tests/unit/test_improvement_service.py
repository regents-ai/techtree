"""Reading a context, and spending the one turn. Sections 8.10 to 8.12, 8.21.

The host model is a stub and the CLI is a double: no model is called, no run
is touched, and nothing is spent.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import pytest
from techtree_hermes.errors import PluginError
from techtree_hermes.models import DemoSessionState, DemoStage
from techtree_hermes.release import load_embedded_release_core
from techtree_hermes.services.improvement import (
    ImprovementService,
    parse_revision_output,
    public_prompts,
    revision_output_schema,
    validate_context,
)

CORE = load_embedded_release_core()
RUN_ID = "run_" + "0" * 32
ROOT_DIGEST = "sha256:" + "c" * 64
ENTRYPOINT_DIGEST = "sha256:" + "d" * 64
IMPROVER_DIGEST = "sha256:" + "e" * 64

SKILL_TEXT = """---
name: branchcode
description: How to work a BranchCode procedure.
---

# BranchCode

## Step 5

Add seven times the TOTAL number of characters in the identifier.
"""

REVISED_SKILL = SKILL_TEXT.replace("TOTAL number", "number of DISTINCT")

GOOD_PROPOSAL: dict[str, Any] = {
    "analysis_summary": "Every failure is an identifier with a repeated character.",
    "change_rationale": ["Step 5 counts characters, and should count distinct ones."],
    "revised_skill_markdown": REVISED_SKILL,
    "expected_tradeoffs": ["Identifiers with no repeats behave exactly as before."],
    "confidence": "medium",
}


def _context(**overrides: Any) -> dict[str, Any]:
    context: dict[str, Any] = {
        "schema_version": "techtree.skill-improvement-context.v1",
        "source_run_id": RUN_ID,
        "source_report_digest": "sha256:" + "f" * 64,
        "campaign_spec_digest": "sha256:" + "1" * 64,
        "parent_skill_digest": ROOT_DIGEST,
        "parent_skill_entrypoint_digest": ENTRYPOINT_DIGEST,
        "data_policy_digest": "sha256:" + "2" * 64,
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
    context.update(overrides)
    return context


def _skill_source(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "source_run_id": RUN_ID,
        "skill_name": "branchcode",
        "skill_root_digest": ROOT_DIGEST,
        "entrypoint_path": "SKILL.md",
        "entrypoint_digest": ENTRYPOINT_DIGEST,
        "entrypoint_size": len(SKILL_TEXT),
        "entrypoint_text": SKILL_TEXT,
        "file_count": 1,
    }
    payload.update(overrides)
    return payload


def _envelope(command: str, data: Any, ok: bool = True) -> dict[str, Any]:
    return {
        "schema_version": "techtree.cli.v1",
        "command": command,
        "ok": ok,
        "data": data,
        "error": None
        if ok
        else {
            "code": "run_not_found",
            "message": "no such run",
            "retryable": False,
            "details": {},
        },
        "messages": [],
        "warnings": [],
        "next_actions": [],
    }


class FakeBridge:
    """Answers the two improvement commands from a script."""

    def __init__(
        self,
        context: dict[str, Any] | None = None,
        skill_source: dict[str, Any] | None = None,
        context_ok: bool = True,
        skill_ok: bool = True,
    ) -> None:
        self.calls: list[list[str]] = []
        self.context = _context() if context is None else context
        self.skill_source = _skill_source() if skill_source is None else skill_source
        self.context_ok = context_ok
        self.skill_ok = skill_ok

    def invoke(self, arguments: Sequence[str]) -> dict[str, Any]:
        self.calls.append(list(arguments))
        if arguments[:2] == ["uplift", "context"]:
            return _envelope(
                "uplift context",
                {"context": self.context, "relative_path": "context.json"}
                if self.context_ok
                else None,
                ok=self.context_ok,
            )
        return _envelope(
            "uplift skill-source",
            self.skill_source if self.skill_ok else None,
            ok=self.skill_ok,
        )


class StubHost:
    """A host model that answers once, from a script."""

    def __init__(self, parsed: Any = None, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.parsed = GOOD_PROPOSAL if parsed is None else parsed
        self.error = error

    def complete_structured(
        self, *, system: str, user: str, schema: dict[str, Any], purpose: str
    ) -> dict[str, Any]:
        self.calls.append(
            {"system": system, "user": user, "schema": schema, "purpose": purpose}
        )
        if self.error is not None:
            raise self.error
        return {"parsed": self.parsed, "model": "host-model-1", "provider": "host"}


def _session(**overrides: Any) -> DemoSessionState:
    session = DemoSessionState(
        demo_id="demo_" + "0" * 32,
        release_core_digest="sha256:" + "9" * 64,
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
        updated_at=datetime.now(UTC).isoformat(),
    )
    return dataclasses.replace(session, **overrides)


def _service(bridge: Any = None, host: Any = None) -> ImprovementService:
    return ImprovementService(
        llm=host or StubHost(), release=CORE, bridge=bridge or FakeBridge()
    )


def _propose(
    service: ImprovementService, session: DemoSessionState | None = None
) -> Any:
    return service.propose_once(
        source_run_id=RUN_ID,
        demo_session=session or _session(),
        skill_improver_digest=IMPROVER_DIGEST,
    )


# The context ------------------------------------------------------------------


def test_a_sanitized_context_is_read_through_the_cli() -> None:
    bridge = FakeBridge()

    context = _service(bridge).get_context(RUN_ID)

    assert bridge.calls[0] == ["uplift", "context", RUN_ID]
    assert context["source_run_id"] == RUN_ID


def test_a_context_techtree_refused_reports_its_own_reason() -> None:
    with pytest.raises(PluginError, match="no such run"):
        _service(FakeBridge(context_ok=False)).get_context(RUN_ID)


@pytest.mark.parametrize(
    "hidden",
    [
        {"expected_answer": "42"},
        {"answers": ["42"]},
        {"grader_source": "def grade(): ..."},
        {"hidden_fields": {"answer": "42"}},
        {"provider_request": {"messages": []}},
        {"api_key": "sk-live-abcdefghijklmnop"},
        {"private_key": "-----BEGIN PRIVATE KEY-----"},
    ],
)
def test_a_context_carrying_hidden_material_is_refused(hidden: dict[str, Any]) -> None:
    """Decision 0007 R1's exclusion list, checked rather than trusted."""
    with pytest.raises(PluginError, match="hidden material") as raised:
        validate_context(_context(**hidden))

    assert raised.value.code == "improvement_context_forbidden_material"


def test_hidden_material_nested_inside_an_example_is_refused() -> None:
    example = {**_context()["examples"][0], "expected_output": "42"}

    with pytest.raises(PluginError, match="hidden material"):
        validate_context(_context(examples=[example]))


def test_a_context_carrying_a_subject_reply_is_refused() -> None:
    """R1: the reply is null for correct and incorrect episodes alike."""
    example = {**_context()["examples"][0], "subject_reply": "The answer is 42."}

    with pytest.raises(PluginError, match="subject's reply") as raised:
        validate_context(_context(examples=[example]))

    assert raised.value.code == "improvement_context_forbidden_material"


def test_a_context_carrying_a_credential_is_refused() -> None:
    with pytest.raises(PluginError, match="credential"):
        validate_context(
            _context(objective="Use OPENAI_API_KEY=sk-live-abcdefghijklmnop")
        )


def test_a_context_carrying_a_private_path_is_refused() -> None:
    with pytest.raises(PluginError, match="private path"):
        validate_context(_context(objective="See /Users/sean/runs/run_1 for detail."))


def test_a_context_of_an_unknown_schema_is_refused() -> None:
    with pytest.raises(PluginError, match="schema"):
        validate_context(_context(schema_version="techtree.skill-improvement.v2"))


def test_a_context_missing_a_fingerprint_is_refused() -> None:
    context = _context()
    del context["parent_skill_entrypoint_digest"]

    with pytest.raises(PluginError, match="missing"):
        validate_context(context)


def test_the_public_prompts_are_what_a_revision_may_not_copy() -> None:
    assert public_prompts(_context()) == [
        "Compute the BranchCode total for identifier aabbcc."
    ]


# The Skill the run measured -------------------------------------------------------


def test_the_source_skill_is_read_and_checked_against_the_context() -> None:
    bridge = FakeBridge()
    service = _service(bridge)

    skill = service.load_source_skill(service.get_context(RUN_ID))

    assert bridge.calls[1] == ["uplift", "skill-source", RUN_ID]
    assert skill.text == SKILL_TEXT
    assert skill.entrypoint_digest == ENTRYPOINT_DIGEST


@pytest.mark.parametrize(
    "wrong",
    [
        {"skill_root_digest": "sha256:" + "9" * 64},
        {"entrypoint_digest": "sha256:" + "9" * 64},
        {"source_run_id": "run_" + "9" * 32},
    ],
)
def test_a_skill_that_does_not_match_the_context_is_refused(
    wrong: dict[str, Any],
) -> None:
    bridge = FakeBridge(skill_source=_skill_source(**wrong))
    service = _service(bridge)

    with pytest.raises(PluginError, match="not the one this context pins"):
        service.load_source_skill(service.get_context(RUN_ID))


def test_a_skill_carrying_a_credential_is_never_read_out() -> None:
    bridge = FakeBridge(
        skill_source=_skill_source(
            entrypoint_text=SKILL_TEXT + "\nOPENAI_API_KEY=sk-live-abcdefghijklmnop\n"
        )
    )
    service = _service(bridge)

    with pytest.raises(PluginError, match="credential"):
        service.load_source_skill(service.get_context(RUN_ID))


def test_the_skills_path_is_never_shown_to_the_model() -> None:
    host = StubHost()
    service = _service(FakeBridge(), host)

    _propose(service)

    sent = host.calls[0]["system"] + host.calls[0]["user"]
    assert "entrypoint_path" not in sent
    assert "/Users/" not in sent


# Exactly one turn -------------------------------------------------------------------


def test_one_proposal_makes_exactly_one_completion() -> None:
    host = StubHost()

    proposal = _propose(_service(FakeBridge(), host))

    assert len(host.calls) == 1
    assert host.calls[0]["purpose"] == "skill_revision"
    assert proposal.output.confidence == "medium"
    assert proposal.session.revision_attempts == 1


def test_a_failed_completion_still_spends_the_turn() -> None:
    """The promise is one reasoning turn, not one successful one."""
    host = StubHost(error=RuntimeError("provider down"))
    service = _service(FakeBridge(), host)
    session = _session()

    with pytest.raises(PluginError):
        _propose(service, session)

    with pytest.raises(PluginError, match="already had its one revision"):
        _propose(service, dataclasses.replace(session, revision_attempts=1))
    assert len(host.calls) == 1


def test_an_unusable_answer_still_spends_the_turn() -> None:
    host = StubHost(parsed={**GOOD_PROPOSAL, "confidence": "certain"})

    with pytest.raises(PluginError, match="confidence"):
        _propose(_service(FakeBridge(), host))

    assert len(host.calls) == 1


def test_a_second_revision_is_refused() -> None:
    host = StubHost()

    with pytest.raises(PluginError, match="already had its one revision") as raised:
        _propose(_service(FakeBridge(), host), _session(revision_attempts=1))

    assert raised.value.code == "improvement_attempt_already_used"
    assert host.calls == []


def test_a_run_that_is_not_this_sessions_first_is_refused() -> None:
    host = StubHost()

    with pytest.raises(PluginError, match="not the run this session compared first"):
        _propose(_service(FakeBridge(), host), _session(first_run_id="run_" + "9" * 32))

    assert host.calls == []


@pytest.mark.parametrize(
    "stage", [DemoStage.FIRST_RUN_ACTIVE, DemoStage.FIRST_DRAFT_PREPARED]
)
def test_a_run_that_has_not_finished_is_refused(stage: DemoStage) -> None:
    host = StubHost()

    with pytest.raises(PluginError, match="no finished first comparison"):
        _propose(_service(FakeBridge(), host), _session(stage=stage))

    assert host.calls == []


# What the proposal records ------------------------------------------------------------


def test_the_proposal_records_what_it_was_made_from() -> None:
    proposal = _propose(_service())

    provenance = proposal.provenance.to_dict()
    assert provenance["parent_skill_root_digest"] == ROOT_DIGEST
    assert provenance["parent_skill_entrypoint_digest"] == ENTRYPOINT_DIGEST
    assert provenance["skill_improver_digest"] == IMPROVER_DIGEST
    assert provenance["host_model_id"] == "host-model-1"
    assert provenance["revision_attempt"] == 1
    assert provenance["improvement_context_digest"].startswith("sha256:")
    assert provenance["host_request_digest"].startswith("sha256:")
    assert provenance["host_response_digest"].startswith("sha256:")


def test_the_skill_text_is_bound_into_the_request_digest() -> None:
    """The proposal cannot be re-described as being about another Skill."""
    one = _propose(_service())
    other_bridge = FakeBridge(
        skill_source=_skill_source(entrypoint_text=SKILL_TEXT + "\nAn extra rule.\n")
    )
    other_bridge.context = _context()
    two = _propose(_service(other_bridge))

    assert one.provenance.host_request_digest != two.provenance.host_request_digest


# The proposal shape -------------------------------------------------------------------


def test_the_schema_asks_for_a_whole_skill_and_no_numbers() -> None:
    schema = revision_output_schema()

    assert set(schema["properties"]) == {
        "analysis_summary",
        "change_rationale",
        "revised_skill_markdown",
        "expected_tradeoffs",
        "confidence",
    }
    assert schema["additionalProperties"] is False
    assert schema["properties"]["confidence"]["enum"] == ["low", "medium", "high"]
    assert "number" not in str(schema).lower()


def test_a_well_formed_proposal_parses() -> None:
    output = parse_revision_output(GOOD_PROPOSAL)

    assert output.confidence == "medium"
    assert output.revised_skill_markdown == REVISED_SKILL
    assert output.change_rationale[0].startswith("Step 5 counts")


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ({**GOOD_PROPOSAL, "baseline_score": 2.0}, "fields it was not asked for"),
        ({**GOOD_PROPOSAL, "revised_skill_markdown": "  "}, "revised skill markdown"),
        ({**GOOD_PROPOSAL, "analysis_summary": ""}, "analysis summary"),
        ({**GOOD_PROPOSAL, "confidence": "certain"}, "confidence"),
        ({**GOOD_PROPOSAL, "change_rationale": "not a list"}, "not a list"),
        ({**GOOD_PROPOSAL, "expected_tradeoffs": [1, 2]}, "not text"),
    ],
)
def test_a_malformed_proposal_is_refused(answer: dict[str, Any], expected: str) -> None:
    with pytest.raises(PluginError, match=expected):
        parse_revision_output(answer)


def test_a_proposal_that_smuggles_an_answer_table_is_refused() -> None:
    table = (
        REVISED_SKILL
        + "\n| input | expected |\n| --- | --- |\n| aabbcc | 42 |\n| abcdef | 42 |\n"
    )
    host = StubHost(parsed={**GOOD_PROPOSAL, "revised_skill_markdown": table})

    with pytest.raises(PluginError, match="rule, not the"):
        _propose(_service(FakeBridge(), host))


def test_a_proposal_that_copies_the_task_it_was_shown_is_refused() -> None:
    copied = (
        REVISED_SKILL
        + "\nWorked example: Compute the BranchCode total for identifier aabbcc.\n"
    )
    host = StubHost(parsed={**GOOD_PROPOSAL, "revised_skill_markdown": copied})

    with pytest.raises(PluginError, match="copies a task"):
        _propose(_service(FakeBridge(), host))


def test_a_proposal_that_is_a_patch_is_refused() -> None:
    host = StubHost(
        parsed={
            **GOOD_PROPOSAL,
            "revised_skill_markdown": "Apply this patch to step 5: use distinct.",
        }
    )

    with pytest.raises(PluginError, match=r"complete SKILL\.md"):
        _propose(_service(FakeBridge(), host))
