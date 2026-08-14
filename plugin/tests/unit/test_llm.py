"""The host model seam. Specification section 8.4, decision 0007 R2.

No model is called anywhere in this file: the port is exercised with stubs
that record what they were asked and answer from a script.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from techtree_hermes.llm import (
    MAX_REQUEST_CHARACTERS,
    HermesHostLlm,
    HostLlmError,
    HostLlmRequest,
    OneShotHostLlm,
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"headline": {"type": "string"}},
    "required": ["headline"],
    "additionalProperties": False,
}


class StubPort:
    """A host port that counts its calls and answers from a script."""

    def __init__(self, answer: Any = None, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.answer = answer
        self.error = error

    def complete_structured(
        self, *, system: str, user: str, schema: dict[str, Any], purpose: str
    ) -> dict[str, Any]:
        self.calls.append(
            {"system": system, "user": user, "schema": schema, "purpose": purpose}
        )
        if self.error is not None:
            raise self.error
        return self.answer or {
            "parsed": {"headline": "It improved"},
            "text": '{"headline": "It improved"}',
            "model": "host-model-1",
            "provider": "host-provider",
            "usage": {"input_tokens": 10, "output_tokens": 4},
        }


def _request(**overrides: Any) -> HostLlmRequest:
    values: dict[str, Any] = {
        "system": "Choose how to word a result you were given.",
        "user": "baseline 2/36, candidate 24/36",
        "schema": SCHEMA,
        "purpose": "result_narrative",
    }
    values.update(overrides)
    return HostLlmRequest(**values)


# One completion, and only one -----------------------------------------------


def test_one_request_makes_exactly_one_completion() -> None:
    port = StubPort()

    OneShotHostLlm(port).complete(_request())

    assert len(port.calls) == 1


def test_a_second_completion_in_one_turn_is_refused() -> None:
    """A hidden retry would turn one revision attempt into a search."""
    port = StubPort()
    host = OneShotHostLlm(port)
    host.complete(_request())

    with pytest.raises(HostLlmError, match="already had its one completion") as raised:
        host.complete(_request())

    assert raised.value.code == "host_llm_already_completed"
    assert len(port.calls) == 1


def test_a_failed_completion_still_spends_the_turn() -> None:
    """Failure is reported to the person; it is not retried behind their back."""
    port = StubPort(error=RuntimeError("provider is down"))
    host = OneShotHostLlm(port)

    with pytest.raises(HostLlmError) as first:
        host.complete(_request())
    with pytest.raises(HostLlmError) as second:
        host.complete(_request())

    assert first.value.code == "host_llm_unavailable"
    assert first.value.retryable is False
    assert second.value.code == "host_llm_already_completed"
    assert len(port.calls) == 1


def test_the_turn_is_spent_even_when_the_answer_was_unusable() -> None:
    port = StubPort(answer={"parsed": "not an object", "model": "m"})
    host = OneShotHostLlm(port)

    with pytest.raises(HostLlmError) as raised:
        host.complete(_request())

    assert raised.value.code == "host_llm_output_invalid"
    assert host.used is True


# Typed failures ----------------------------------------------------------------


def test_a_provider_failure_is_typed_and_scrubbed() -> None:
    port = StubPort(error=RuntimeError("Bearer abc123DEF456ghi rejected"))

    with pytest.raises(HostLlmError) as raised:
        OneShotHostLlm(port).complete(_request())

    assert raised.value.code == "host_llm_unavailable"
    assert "abc123DEF456ghi" not in str(raised.value)


@pytest.mark.parametrize(
    "answer",
    [
        {"parsed": None, "model": "m"},
        {"model": "m"},
        "just text",
        {"parsed": ["a", "list"]},
    ],
)
def test_an_answer_that_is_not_the_shape_asked_for_is_refused(answer: Any) -> None:
    with pytest.raises(HostLlmError) as raised:
        OneShotHostLlm(StubPort(answer=answer)).complete(_request())

    assert raised.value.code == "host_llm_output_invalid"


@pytest.mark.parametrize(
    "overrides",
    [
        {"purpose": "  "},
        {"system": ""},
        {"user": ""},
        {"schema": {}},
    ],
)
def test_a_malformed_request_is_never_sent(overrides: dict[str, Any]) -> None:
    port = StubPort()

    with pytest.raises(HostLlmError):
        OneShotHostLlm(port).complete(_request(**overrides))

    assert port.calls == []


def test_an_oversized_request_is_never_sent() -> None:
    port = StubPort()
    request = _request(user="x" * (MAX_REQUEST_CHARACTERS + 1))

    with pytest.raises(HostLlmError, match="more than"):
        OneShotHostLlm(port).complete(request)

    assert port.calls == []


# Digests -------------------------------------------------------------------------


def test_the_request_digest_is_deterministic() -> None:
    assert _request().digest() == _request().digest()


def test_the_request_digest_covers_everything_that_was_sent() -> None:
    base = _request()

    assert base.digest() != _request(system="different instructions").digest()
    assert base.digest() != _request(user="different payload").digest()
    assert base.digest() != _request(purpose="something_else").digest()
    assert base.digest() != _request(schema={"type": "object"}).digest()


def test_the_skill_text_is_part_of_the_request_digest() -> None:
    """A proposal cannot later be said to be about a different Skill."""
    one = _request(attachments={"source_skill": "# Skill\nStep 5: total"})
    two = _request(attachments={"source_skill": "# Skill\nStep 5: distinct"})

    assert one.digest() != two.digest()
    assert one.digest() != _request().digest()


def test_attachments_are_sent_labelled_and_in_a_fixed_order() -> None:
    port = StubPort()
    request = _request(attachments={"source_skill": "SKILL TEXT", "context": "CONTEXT"})

    OneShotHostLlm(port).complete(request)

    sent = port.calls[0]["user"]
    assert sent.index("<context>") < sent.index("<source_skill>")
    assert "SKILL TEXT" in sent
    assert request.combined_user_text() == sent


def test_the_response_digest_is_over_the_structured_answer() -> None:
    first = OneShotHostLlm(StubPort()).complete(_request())
    second = OneShotHostLlm(StubPort()).complete(_request())
    other = OneShotHostLlm(
        StubPort(answer={"parsed": {"headline": "It did not"}, "model": "m"})
    ).complete(_request())

    assert first.response_digest == second.response_digest
    assert first.response_digest != other.response_digest


def test_the_result_records_the_host_model_as_operational_metadata() -> None:
    result = OneShotHostLlm(StubPort()).complete(_request())

    provenance = result.to_provenance()
    assert provenance["host_model_id"] == "host-model-1"
    assert provenance["complete_request_digest"] == _request().digest()
    assert provenance["purpose"] == "result_narrative"
    assert "subject" not in provenance


def test_usage_is_carried_but_never_required() -> None:
    with_usage = OneShotHostLlm(StubPort()).complete(_request())
    without = OneShotHostLlm(
        StubPort(answer={"parsed": {"headline": "x"}, "model": "m"})
    ).complete(_request())

    assert with_usage.usage["input_tokens"] == 10
    assert without.usage == {}


# The Hermes adapter ------------------------------------------------------------------


class FakeHermesLlm:
    """Stands in for ctx.llm, with the host's own keyword names."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def complete_structured(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)

        return SimpleNamespace(
            parsed={"headline": "It improved"},
            text="{}",
            model="host-model-1",
            provider="host-provider",
            usage=SimpleNamespace(input_tokens=3, output_tokens=1),
        )


class FakeCtx:
    def __init__(self, llm: Any) -> None:
        self.llm = llm


def test_the_adapter_calls_the_host_once_with_its_own_names() -> None:
    llm = FakeHermesLlm()

    result = OneShotHostLlm(HermesHostLlm(FakeCtx(llm))).complete(_request())

    assert len(llm.calls) == 1
    call = llm.calls[0]
    assert call["instructions"] == _request().system
    assert call["input"] == [{"type": "text", "text": _request().user}]
    assert call["json_schema"] == SCHEMA
    assert call["purpose"] == "result_narrative"
    assert result.model == "host-model-1"


def test_a_host_without_a_model_says_so() -> None:
    class Bare:
        llm = None

    with pytest.raises(HostLlmError) as raised:
        OneShotHostLlm(HermesHostLlm(Bare())).complete(_request())

    assert raised.value.code == "host_llm_unavailable"


# What a proposal records about itself ---------------------------------------------


def test_a_proposal_records_everything_it_was_made_from() -> None:
    """Decision 0007 R2's provenance, assembled from things actually read."""
    from techtree_hermes.llm import build_revision_provenance, digest_document

    result = OneShotHostLlm(StubPort()).complete(_request(purpose="skill_revision"))
    context_digest = digest_document({"schema_version": "x", "source_run_id": "run_1"})

    provenance = build_revision_provenance(
        commitments={
            "skill_improver_digest": "sha256:" + "e" * 64,
            "improvement_context_digest": context_digest,
            "source_skill_root_digest": "sha256:" + "c" * 64,
            "source_skill_entrypoint_digest": "sha256:" + "d" * 64,
            "output_schema_digest": "sha256:" + "b" * 64,
        },
        result=result,
    )

    assert provenance.to_dict() == {
        "skill_improver_digest": "sha256:" + "e" * 64,
        "improvement_context_digest": context_digest,
        "source_skill_root_digest": "sha256:" + "c" * 64,
        "source_skill_entrypoint_digest": "sha256:" + "d" * 64,
        "output_schema_digest": "sha256:" + "b" * 64,
        "complete_request_digest": result.request_digest,
        "host_model_id": "host-model-1",
        "host_response_digest": result.response_digest,
        "revision_attempt": 1,
    }


def test_a_proposal_cannot_record_a_commitment_the_request_never_made() -> None:
    """Decision 0010 fixes nine values; eight is a defect, not a variation."""
    from techtree_hermes.llm import build_revision_provenance

    result = OneShotHostLlm(StubPort()).complete(_request(purpose="skill_revision"))

    with pytest.raises(HostLlmError, match="output_schema_digest"):
        build_revision_provenance(
            commitments={
                "skill_improver_digest": "sha256:" + "e" * 64,
                "improvement_context_digest": "sha256:" + "f" * 64,
                "source_skill_root_digest": "sha256:" + "c" * 64,
                "source_skill_entrypoint_digest": "sha256:" + "d" * 64,
            },
            result=result,
        )


def test_a_context_digest_is_deterministic_and_specific() -> None:
    from techtree_hermes.llm import digest_document

    one = digest_document({"a": 1, "b": [2, 3]})
    same = digest_document({"b": [2, 3], "a": 1})
    other = digest_document({"a": 1, "b": [2, 4]})

    assert one == same
    assert one != other


def test_a_revision_attempt_is_counted_from_one() -> None:
    from techtree_hermes.llm import build_revision_provenance

    result = OneShotHostLlm(StubPort()).complete(_request())

    with pytest.raises(HostLlmError, match="counted from one"):
        build_revision_provenance(
            commitments={
                "skill_improver_digest": "sha256:" + "e" * 64,
                "improvement_context_digest": "sha256:" + "f" * 64,
                "source_skill_root_digest": "sha256:" + "c" * 64,
                "source_skill_entrypoint_digest": "sha256:" + "d" * 64,
                "output_schema_digest": "sha256:" + "b" * 64,
            },
            result=result,
            revision_attempt=0,
        )
