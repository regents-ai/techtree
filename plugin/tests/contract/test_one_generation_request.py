"""One completion means one outbound generation request. Decision 0015 s4.

The one-turn promise is not a promise about a method signature. It is a
promise about how many times a model is asked to generate, and the place that
has to hold is the provider boundary — `HermesHostLlm.complete_structured`,
the single point where this plugin hands work to the host's sampling stack.

What these tests lock is everything on this side of that boundary:

* a counting double that treats a second request as a failure never sees one,
  through the one-shot wrapper and through the improvement service;
* an unusable answer spends the attempt and returns a typed failure, without
  a repair completion;
* a transport failure spends the attempt and returns a typed failure, without
  a retry;
* the plugin owns no HTTP client, so there is no client-level retry setting
  to disable — proved statically rather than asserted.

What they cannot lock is what Hermes does inside the one call it is handed.
That is stated in `llm.py`, recorded per attempt as a request count, and left
to the host to account for. A test that claimed otherwise would be a test
making a promise this repository cannot keep.
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path
from typing import Any

import pytest
from techtree_hermes.constants import PLUGIN_ROOT
from techtree_hermes.errors import PluginError
from techtree_hermes.llm import HostLlmError, HostLlmRequest, OneShotHostLlm
from techtree_hermes.services.improvement import ImprovementService

# The double that refuses to be asked twice ------------------------------------------


class RefusesASecondRequest:
    """A host port that treats a second generation request as a defect.

    It does not merely count. Asking twice raises, so a plugin that retried
    would fail loudly here rather than quietly pass a weaker assertion.
    """

    def __init__(self, parsed: Any = None, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.parsed = parsed
        self.error = error

    def complete_structured(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if len(self.calls) > 1:
            raise AssertionError(
                "the guided flow made a second outbound generation request; "
                f"one turn allows one ({len(self.calls)} seen)"
            )
        if self.error is not None:
            raise self.error
        return {
            "parsed": self.parsed,
            "model": "host-model-1",
            "provider": "host",
            "request_id": "req_0123456789",
            "response_id": "resp_9876543210",
        }


def _request(purpose: str = "skill_revision") -> HostLlmRequest:
    return HostLlmRequest(
        system="Envelope.",
        user="Payload.",
        schema={"type": "object"},
        purpose=purpose,
    )


# The one-shot wrapper --------------------------------------------------------------


def test_one_completion_makes_one_outbound_request() -> None:
    port = RefusesASecondRequest(parsed={"ok": True})
    once = OneShotHostLlm(port)

    once.complete(_request())

    assert len(port.calls) == 1
    assert once.invocations == 1
    assert once.outbound_requests == 1


def test_a_second_ask_is_refused_before_it_reaches_the_provider() -> None:
    """The refusal has to happen on this side, or the count is already wrong."""
    port = RefusesASecondRequest(parsed={"ok": True})
    once = OneShotHostLlm(port)
    once.complete(_request())

    with pytest.raises(HostLlmError, match="already had its one completion") as raised:
        once.complete(_request())

    assert raised.value.code == "host_llm_already_completed"
    assert len(port.calls) == 1
    assert once.invocations == 2, "the second ask happened"
    assert once.outbound_requests == 1, "and did not leave the machine"


def test_a_transport_failure_is_counted_and_not_retried() -> None:
    """A request that failed in flight still happened, and happened once."""
    port = RefusesASecondRequest(error=TimeoutError("upstream 429"))
    once = OneShotHostLlm(port)

    with pytest.raises(HostLlmError) as raised:
        once.complete(_request())

    assert raised.value.code == "host_llm_unavailable"
    assert raised.value.retryable is False
    assert len(port.calls) == 1
    assert once.outbound_requests == 1


def test_an_unusable_answer_is_not_repaired_by_a_second_request() -> None:
    """A structured-repair completion is a second request wearing a hat."""
    port = RefusesASecondRequest(parsed=None)
    once = OneShotHostLlm(port)

    with pytest.raises(HostLlmError) as raised:
        once.complete(_request())

    assert raised.value.code == "host_proposal_generation_exhausted"
    assert len(port.calls) == 1
    assert once.outbound_requests == 1


def test_the_accounting_records_what_the_attempt_did() -> None:
    port = RefusesASecondRequest(parsed={"ok": True})
    once = OneShotHostLlm(port)
    result = once.complete(_request())

    accounting = once.accounting().to_dict()

    assert accounting == {
        "invocation_count": 1,
        "outbound_request_count": 1,
        "provider_request_id": "req_0123456789",
        "provider_response_id": "resp_9876543210",
        "complete_request_digest": result.request_digest,
        "host_response_digest": result.response_digest,
    }


def test_an_absent_provider_identifier_is_recorded_as_absent() -> None:
    """Hosts that report no identifier are not given an invented one."""

    class WithoutIdentifiers(RefusesASecondRequest):
        def complete_structured(self, **kwargs: Any) -> dict[str, Any]:
            answer = super().complete_structured(**kwargs)
            return {
                key: value
                for key, value in answer.items()
                if key not in ("request_id", "response_id")
            }

    once = OneShotHostLlm(WithoutIdentifiers(parsed={"ok": True}))
    once.complete(_request())

    accounting = once.accounting()
    assert accounting.provider_request_id is None
    assert accounting.provider_response_id is None
    assert accounting.outbound_request_count == 1


# The product path ------------------------------------------------------------------


def _service(host: Any, release: Any, plugin_root: Path, bridge: Any) -> Any:
    return ImprovementService(
        llm=host, release=release, bridge=bridge, plugin_root=plugin_root
    )


def test_the_guided_proposal_makes_exactly_one_request(
    improvement_case: Any,
) -> None:
    """The product path, end to end, against a double that refuses a second."""
    port = RefusesASecondRequest(parsed=improvement_case.proposal)
    service = _service(
        port,
        improvement_case.release,
        improvement_case.plugin_root,
        improvement_case.bridge,
    )

    proposal = service.propose_once(
        source_run_id=improvement_case.run_id, demo_session=improvement_case.session
    )

    assert len(port.calls) == 1
    assert proposal.accounting.invocation_count == 1
    assert proposal.accounting.outbound_request_count == 1
    assert proposal.accounting.provider_request_id == "req_0123456789"
    assert (
        proposal.accounting.complete_request_digest
        == proposal.provenance.complete_request_digest
    )


def test_a_failed_proposal_spends_the_attempt_with_one_request(
    improvement_case: Any,
) -> None:
    """Honest typed failure, attempt consumed, and no second call."""
    port = RefusesASecondRequest(error=RuntimeError("closed stream"))
    service = _service(
        port,
        improvement_case.release,
        improvement_case.plugin_root,
        improvement_case.bridge,
    )

    with pytest.raises(PluginError) as raised:
        service.propose_once(
            source_run_id=improvement_case.run_id,
            demo_session=improvement_case.session,
        )

    assert raised.value.code == "host_llm_unavailable"
    assert raised.value.retryable is False
    assert len(port.calls) == 1

    with pytest.raises(PluginError, match="already had its one revision"):
        service.propose_once(
            source_run_id=improvement_case.run_id,
            demo_session=dataclasses.replace(
                improvement_case.session, revision_attempts=1
            ),
        )
    assert len(port.calls) == 1, "the spent turn made no further request"


def test_an_invalid_proposal_spends_the_attempt_with_one_request(
    improvement_case: Any,
) -> None:
    """An answer the plugin cannot use is not an invitation to ask again."""
    port = RefusesASecondRequest(
        parsed={**improvement_case.proposal, "confidence": "certain"}
    )
    service = _service(
        port,
        improvement_case.release,
        improvement_case.plugin_root,
        improvement_case.bridge,
    )

    with pytest.raises(PluginError, match="confidence") as raised:
        service.propose_once(
            source_run_id=improvement_case.run_id,
            demo_session=improvement_case.session,
        )

    assert raised.value.code == "skill_revision_output_invalid"
    assert len(port.calls) == 1


# The absent transport --------------------------------------------------------------


def _runtime_sources() -> list[Path]:
    excluded = {"tests", "scripts", "skills"}
    return [
        path
        for path in PLUGIN_ROOT.rglob("*.py")
        if path.relative_to(PLUGIN_ROOT).parts[0] not in excluded
        and not any(
            part.startswith(".") for part in path.relative_to(PLUGIN_ROOT).parts
        )
    ]


#: Clients whose defaults retry a 429 or a timeout without being asked.
RETRYING_CLIENTS = {
    "openai",
    "anthropic",
    "httpx",
    "requests",
    "urllib",
    "urllib3",
    "http",
    "aiohttp",
    "tenacity",
    "backoff",
}


def test_the_plugin_holds_no_client_that_could_retry() -> None:
    """There is no `max_retries` to set to zero, because there is no client."""
    importers = []
    for source in _runtime_sources():
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            if set(names) & RETRYING_CLIENTS:
                importers.append(f"{source.relative_to(PLUGIN_ROOT)}: {names}")

    assert not importers, f"a runtime module imports an HTTP client: {importers}"


#: Names that would mean a retry was configured rather than merely discussed.
RETRY_SETTINGS = {"max_retries", "retry_policy", "num_retries", "backoff_factor"}


def test_no_runtime_module_configures_a_retry() -> None:
    """A retry setting appearing here would mean a client appeared with it.

    Read through the parser, not as text: `llm.py` documents that there is no
    `max_retries` to set, and a scan that could not tell an explanation from a
    setting would forbid saying so.
    """
    offenders = []
    for source in _runtime_sources():
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            named = None
            if isinstance(node, ast.keyword) and node.arg in RETRY_SETTINGS:
                named = node.arg
            elif isinstance(node, ast.Name) and node.id in RETRY_SETTINGS:
                named = node.id
            elif isinstance(node, ast.Attribute) and node.attr in RETRY_SETTINGS:
                named = node.attr
            if named:
                offenders.append(f"{source.relative_to(PLUGIN_ROOT)}: {named}")

    assert not offenders, f"a runtime module configures retries: {offenders}"


def test_only_one_place_calls_the_host_port() -> None:
    """One seam, so there is one thing to prove and one place to change it."""
    callers = [
        str(source.relative_to(PLUGIN_ROOT))
        for source in _runtime_sources()
        if "complete_structured(" in source.read_text(encoding="utf-8")
    ]

    assert callers == ["llm.py"], callers


def test_the_boundary_is_written_down_where_it_lives() -> None:
    """Decision 0015 s4 asks for the boundary documented, not just tested."""
    documentation = (PLUGIN_ROOT / "llm.py").read_text(encoding="utf-8")
    heading, _, rest = documentation.partition("Where the one-turn promise binds")

    assert heading, "llm.py no longer documents the provider boundary"
    for claim in (
        "one outbound model generation request",
        "no retry loop",
        "max_retries",
        "host's sampling stack",
    ):
        assert claim in rest, claim


# Fixtures -------------------------------------------------------------------------
#
# Self-contained on purpose. A contract test that borrowed another test
# module's helpers would be a contract test that fails for reasons belonging
# to a different file.


RUN_ID = "run_" + "0" * 32
ROOT_DIGEST = "sha256:" + "c" * 64
ENTRYPOINT_DIGEST = "sha256:" + "d" * 64

SOURCE_SKILL = """---
name: branchcode
description: How to work a BranchCode procedure.
---

# BranchCode

## Step 5

Add seven times the TOTAL number of characters in the identifier.
"""

GOOD_PROPOSAL: dict[str, Any] = {
    "analysis_summary": "Every failure is an identifier with a repeated character.",
    "change_rationale": ["Step 5 counts characters, and should count distinct ones."],
    "revised_skill_markdown": SOURCE_SKILL.replace(
        "TOTAL number", "number of DISTINCT"
    ),
    "expected_tradeoffs": ["Identifiers with no repeats behave exactly as before."],
    "confidence": "medium",
}


def _envelope(command: str, data: Any) -> dict[str, Any]:
    return {
        "schema_version": "techtree.cli.v1",
        "command": command,
        "ok": True,
        "data": data,
        "error": None,
        "messages": [],
        "warnings": [],
        "next_actions": [],
    }


class _Bridge:
    """Answers the two commands the improvement turn reads from."""

    def invoke(self, arguments: Any) -> dict[str, Any]:
        if list(arguments)[:2] == ["uplift", "context"]:
            return _envelope(
                "uplift context",
                {
                    "context": {
                        "schema_version": "techtree.skill-improvement-context.v1",
                        "source_run_id": RUN_ID,
                        "source_report_digest": "sha256:" + "f" * 64,
                        "campaign_spec_digest": "sha256:" + "1" * 64,
                        "parent_skill_digest": ROOT_DIGEST,
                        "parent_skill_entrypoint_digest": ENTRYPOINT_DIGEST,
                        "data_policy_digest": "sha256:" + "2" * 64,
                        "objective": "Improve the Skill on this Campaign.",
                        "current_result": {"decision": "improved"},
                        "examples": [],
                        "constraints": ["State a rule, not the cases."],
                        "prohibited_material": ["expected answers"],
                    },
                    "relative_path": "context.json",
                },
            )
        return _envelope(
            "uplift skill-source",
            {
                "source_run_id": RUN_ID,
                "skill_name": "branchcode",
                "skill_root_digest": ROOT_DIGEST,
                "entrypoint_path": "SKILL.md",
                "entrypoint_digest": ENTRYPOINT_DIGEST,
                "entrypoint_size": len(SOURCE_SKILL),
                "entrypoint_text": SOURCE_SKILL,
                "file_count": 1,
            },
        )


@dataclasses.dataclass(frozen=True)
class _Case:
    run_id: str
    release: Any
    plugin_root: Path
    bridge: Any
    session: Any
    proposal: dict[str, Any]


@pytest.fixture
def improvement_case() -> _Case:
    """A ready-to-propose session, with the founder Skill named by its release."""
    from techtree_hermes.models import DemoSessionState, DemoStage
    from techtree_hermes.release import load_embedded_release_core
    from techtree_hermes.services.assets import file_digest

    improver = (PLUGIN_ROOT / "skills" / "skill-improver" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    release = dataclasses.replace(
        load_embedded_release_core(),
        skill_improver_digest=file_digest(improver.encode("utf-8")),
    )
    session = DemoSessionState(
        demo_id="demo_" + "0" * 32,
        release_core_digest="sha256:" + "9" * 64,
        climb_reference="hello-world-climb@1",
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
    )
    return _Case(
        run_id=RUN_ID,
        release=release,
        plugin_root=PLUGIN_ROOT,
        bridge=_Bridge(),
        session=session,
        proposal=dict(GOOD_PROPOSAL),
    )
