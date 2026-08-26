"""The host model seam. Specification section 8.4, decision 0007 R2.

The plugin asks the host's own model exactly one thing, ever: what one
revision of a Skill might be. It is one-shot, bounded by a schema, and may not
touch a number. Results are rendered by Techtree and relayed unchanged — no
model is asked to word one (decision 0009).

Where the one-turn promise binds
--------------------------------

Decision 0015 s4: one completion means one outbound model generation request,
at the provider boundary rather than at this method's signature. The boundary
runs through ``HermesHostLlm.complete_structured``, and the two sides of it
are not the same kind of promise:

* **Inside the plugin, and proved by test.** ``OneShotHostLlm`` calls the port
  once and then refuses, whatever happened — success, refusal, malformed
  answer, transport failure. There is no retry loop, no repair completion, no
  fallback model, and no exception handler that calls again. The plugin owns
  no HTTP client at all: the runtime is standard library only and cannot open
  a socket, which is checked separately, so there is no transport-level retry
  setting for this repository to disable. ``max_retries`` does not exist here
  because no client does.
* **Beyond the boundary, and Hermes's to answer for.** What ``ctx.llm`` does
  with the one call it is given — which provider SDK it holds, whether that
  SDK retries a 429 or a timeout, whether it repairs a structured answer — is
  the host's sampling stack, not this plugin's. The plugin cannot observe it
  and does not claim to. What it can do is make exactly one call, count it,
  and record the count beside the digests, so a run's own record says how many
  requests this side of the boundary issued.

Every attempt therefore carries a ``RequestAccounting``: how many times the
one-shot wrapper was invoked, how many outbound requests it actually made, and
the provider's request and response identifiers when the host exposes them.

One completion means one. There is no retry here, no fallback model, no
"try again with a stricter prompt". A hidden second completion would quietly
turn one revision attempt into a search over attempts, and a search that keeps
the best result against the same tasks is how a controlled comparison becomes
an uncontrolled one. If a completion fails, the failure is returned to the
conversation, and asking again is a new thing a person decides to do.

A completion that wrote nothing is its own outcome
--------------------------------------------------

A model can reach the end of what it is allowed to write before it writes
anything: the host answers, the provider charges, and no part of an answer
comes back. ``HostCompletionTruncatedError`` says so in its own words and with
its own code, and it is the one failure the guided introduction does not count
as its attempt — there is no candidate, so there is nothing the turn measured.
Restoring the attempt is not a retry: nothing here asks again, and whether to
spend a fresh one is a decision a person makes knowing it costs money.

The line is exactly "nothing was produced". An answer the model did write and
that cannot be used is still an answer, and spending an attempt on it is what
measuring costs.

Everything sent is bound by a digest — the instructions, the payload, the
schema, and any text attached to the request, such as the Skill being revised.
Everything returned is bound by a digest too. A Skill proposed by this seam
therefore carries a record of exactly what was asked and exactly what came
back, which is what makes the proposal auditable rather than merely plausible.

The host's model identity is recorded as local operational metadata. It is
never the evaluated subject's identity, and the host's authentication is never
the evaluation's authentication.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final, Protocol

from .errors import (
    CODE_HOST_COMPLETION_TRUNCATED,
    CODE_HOST_LLM_ALREADY_COMPLETED,
    CODE_HOST_LLM_OUTPUT_INVALID,
    CODE_HOST_LLM_UNAVAILABLE,
    CODE_HOST_PROPOSAL_GENERATION_EXHAUSTED,
    PluginError,
    scrub_text,
)
from .models import SkillRevisionProvenance

#: How much text one request may carry. A request larger than this is a defect
#: in whoever built it, not something to send and hope.
MAX_REQUEST_CHARACTERS: Final = 200_000

#: What decision 0010 requires the single improvement request to commit to
#: about its own inputs. The request carries them, and the proposal's
#: provenance repeats them beside the digests of the call itself.
REQUEST_COMMITMENT_FIELDS: Final[tuple[str, ...]] = (
    "skill_improver_digest",
    "improvement_context_digest",
    "source_skill_root_digest",
    "source_skill_entrypoint_digest",
    "output_schema_digest",
)


class HostLlmError(PluginError):
    """The host model could not be used, or did not answer usably."""

    code = CODE_HOST_LLM_UNAVAILABLE


class HostCompletionTruncatedError(HostLlmError):
    """The host answered, and the answer carried nothing the model wrote.

    Its own outcome, and its own code, because the three it would otherwise be
    confused with are three different things to tell somebody. The host was
    there and it charged. What came back is not a poor revision. And nothing
    was produced, so there is nothing this turn measured — which is why the
    guided introduction leaves its one attempt where it was.
    """

    code = CODE_HOST_COMPLETION_TRUNCATED


class HostLlmPort(Protocol):
    """The narrow host interface the plugin is allowed to use."""

    def complete_structured(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        purpose: str,
    ) -> dict[str, Any]:
        """Return one structured completion. Called at most once per request."""


@dataclass(frozen=True)
class HostLlmRequest:
    """Everything sent to the host model for one purpose.

    ``attachments`` carries text supplied alongside the payload — the verified
    Skill being revised, above all. It is part of the request and therefore
    part of the request digest: a proposal cannot later be said to have been
    made against a different Skill than the one that was actually sent.
    """

    system: str
    user: str
    schema: Mapping[str, Any]
    purpose: str
    attachments: Mapping[str, str] = field(default_factory=dict)

    def canonical_document(self) -> dict[str, Any]:
        """Return the request as the object its digest is taken over."""
        return {
            "system": self.system,
            "user": self.user,
            "schema": dict(self.schema),
            "purpose": self.purpose,
            "attachments": dict(self.attachments),
        }

    def digest(self) -> str:
        """Return the digest binding this complete request."""
        return _digest_object(self.canonical_document())

    def character_count(self) -> int:
        """Return how much text this request carries in total."""
        return (
            len(self.system)
            + len(self.user)
            + sum(len(text) for text in self.attachments.values())
        )

    def combined_user_text(self) -> str:
        """Return the payload and its attachments as one ordered message.

        Attachments are labelled and ordered by name so that two builds of the
        same request produce the same bytes, which is what makes the digest
        mean anything.
        """
        sections = [self.user]
        for name in sorted(self.attachments):
            sections.append(f"\n\n<{name}>\n{self.attachments[name]}\n</{name}>")
        return "".join(sections)


@dataclass(frozen=True)
class HostLlmResult:
    """One structured answer, and the digests that bind it to its request."""

    parsed: Mapping[str, Any]
    request_digest: str
    response_digest: str
    model: str
    provider: str
    purpose: str
    usage: Mapping[str, Any] = field(default_factory=dict)
    provider_request_id: str | None = None
    provider_response_id: str | None = None

    def to_provenance(self) -> dict[str, Any]:
        """Return the operational metadata a proposal records about this call."""
        return {
            "complete_request_digest": self.request_digest,
            "host_response_digest": self.response_digest,
            "host_model_id": self.model,
            "host_provider": self.provider,
            "purpose": self.purpose,
        }


@dataclass(frozen=True)
class RequestAccounting:
    """How many outbound generation requests one attempt actually made.

    Decision 0015 s4 asks for this per attempt. It is deliberately separate
    from ``SkillRevisionProvenance``, whose nine fields decision 0010 fixed:
    this is the operational record of the call, not a claim about what the
    candidate Skill was derived from.

    ``invocation_count`` counts every time the one-shot wrapper was asked for
    a completion, including a refused second ask. ``outbound_request_count``
    counts only the requests that actually reached the host port. The two
    differing is the evidence that a second request was refused rather than
    merely not attempted.
    """

    invocation_count: int
    outbound_request_count: int
    provider_request_id: str | None
    provider_response_id: str | None
    complete_request_digest: str | None
    host_response_digest: str | None

    def to_dict(self) -> dict[str, Any]:
        """Return the accounting in the shape a tool result carries it."""
        return {
            "invocation_count": self.invocation_count,
            "outbound_request_count": self.outbound_request_count,
            "provider_request_id": self.provider_request_id,
            "provider_response_id": self.provider_response_id,
            "complete_request_digest": self.complete_request_digest,
            "host_response_digest": self.host_response_digest,
        }


class OneShotHostLlm:
    """A host port that will answer once, and then refuse.

    Held for the length of one improvement turn. The refusal is not a safety
    net for a caller that lost track: it is the rule, and a second call is a
    defect the tests are written to catch.
    """

    def __init__(self, port: HostLlmPort) -> None:
        self._port = port
        self._used_for: str | None = None
        self._invocations = 0
        self._outbound_requests = 0
        self._last: HostLlmResult | None = None

    @property
    def used(self) -> bool:
        """Whether the one completion has been spent."""
        return self._used_for is not None

    @property
    def invocations(self) -> int:
        """How many times a completion was asked of this wrapper."""
        return self._invocations

    @property
    def outbound_requests(self) -> int:
        """How many generation requests actually reached the host port."""
        return self._outbound_requests

    def accounting(self) -> RequestAccounting:
        """Return what this attempt did at the provider boundary."""
        return RequestAccounting(
            invocation_count=self._invocations,
            outbound_request_count=self._outbound_requests,
            provider_request_id=(
                self._last.provider_request_id if self._last else None
            ),
            provider_response_id=(
                self._last.provider_response_id if self._last else None
            ),
            complete_request_digest=self._last.request_digest if self._last else None,
            host_response_digest=self._last.response_digest if self._last else None,
        )

    def complete(self, request: HostLlmRequest) -> HostLlmResult:
        """Run the one completion this turn is allowed.

        Exactly one outbound request leaves here, and the counter is raised
        before the call rather than after it: a request that failed in
        transport still happened, and a record that forgot it would be a
        record that under-counts the very thing it exists to count.

        Raises:
            HostLlmError: when a completion has already been made, when the
                request is malformed or oversized, when the host could not
                answer, or when what came back was not the shape that was
                asked for.
        """
        self._invocations += 1
        if self._used_for is not None:
            raise HostLlmError(
                "this turn has already had its one completion, for "
                f"{self._used_for!r}; asking again is a new decision for a "
                "person to make",
                code=CODE_HOST_LLM_ALREADY_COMPLETED,
            )
        _check_request(request)
        self._used_for = request.purpose
        self._outbound_requests += 1

        try:
            answer = self._port.complete_structured(
                system=request.system,
                user=request.combined_user_text(),
                schema=dict(request.schema),
                purpose=request.purpose,
            )
        except HostLlmError:
            raise
        except Exception as error:
            raise HostLlmError(
                "the request was sent but no answer came back from the host "
                "model; the provider may still charge for the attempt, and "
                f"this run's one revision is used: {scrub_text(str(error))}",
                code=CODE_HOST_LLM_UNAVAILABLE,
                retryable=False,
            ) from error

        self._last = _result_from(answer, request)
        return self._last


def _check_request(request: HostLlmRequest) -> None:
    if not request.purpose.strip():
        raise HostLlmError("a host completion needs a stated purpose")
    if not request.system.strip() or not request.user.strip():
        raise HostLlmError("a host completion needs instructions and a payload")
    if not request.schema:
        raise HostLlmError(
            "a host completion needs the schema its answer must fit",
            code=CODE_HOST_LLM_OUTPUT_INVALID,
        )
    if request.character_count() > MAX_REQUEST_CHARACTERS:
        raise HostLlmError(
            f"this request carries {request.character_count()} characters, more "
            f"than the {MAX_REQUEST_CHARACTERS} a host completion may carry"
        )


def _result_from(answer: Any, request: HostLlmRequest) -> HostLlmResult:
    if not isinstance(answer, Mapping):
        raise HostLlmError(
            "the host model did not answer with a structured result",
            code=CODE_HOST_LLM_OUTPUT_INVALID,
        )

    parsed = answer.get("parsed")
    if not isinstance(parsed, Mapping):
        if _wrote_nothing(answer):
            raise HostCompletionTruncatedError(
                "The model ran out of room before it wrote anything. Your "
                "attempt has not been used. Raising your model's completion "
                "limit makes this less likely — each attempt costs money at "
                "your provider."
            )
        raise HostLlmError(
            "The Host Hermes model reached the configured generation limit "
            "before returning a usable Skill proposal. The provider may have "
            "billed the request. This run's single guided-revision attempt "
            "has been used.",
            code=CODE_HOST_PROPOSAL_GENERATION_EXHAUSTED,
        )

    return HostLlmResult(
        parsed=dict(parsed),
        request_digest=request.digest(),
        response_digest=_digest_object(dict(parsed)),
        model=str(answer.get("model") or "unknown"),
        provider=str(answer.get("provider") or "unknown"),
        purpose=request.purpose,
        usage=dict(answer["usage"]) if isinstance(answer.get("usage"), Mapping) else {},
        provider_request_id=_identifier(answer.get("request_id")),
        provider_response_id=_identifier(answer.get("response_id")),
    )


def _wrote_nothing(answer: Mapping[str, Any]) -> bool:
    """Whether the model wrote no part of an answer at all.

    The distinction the guided introduction turns on, so it is drawn from what
    the host actually reports rather than from why it happened. A completion
    that stopped before its first written byte comes back with no structured
    object and no text beside it. Anything the model did write — an object of
    the wrong shape, a list, prose where a schema was asked for — is something
    it produced, however unusable, and is judged as an answer rather than as
    an absence.
    """
    text = answer.get("text")
    written = isinstance(text, str) and bool(text.strip())
    return answer.get("parsed") is None and not written


def _identifier(value: Any) -> str | None:
    """Return a provider identifier, or None when the host reports none."""
    return str(value) if isinstance(value, str) and value.strip() else None


class HermesHostLlm:
    """The host's own one-shot structured completion, as this plugin uses it.

    Hermes exposes a bounded facade at ``ctx.llm``: the user's active model,
    the user's authentication, the host's own budget and audit. The plugin
    brings no provider key of its own and never chooses a model.
    """

    def __init__(self, ctx: Any) -> None:
        self._ctx = ctx

    def complete_structured(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        purpose: str,
    ) -> dict[str, Any]:
        """Call the host's structured completion exactly once.

        This is the provider boundary. One call goes out, its answer is
        returned whatever it says, and nothing here inspects it and calls
        again: there is no retry, no repair pass, and no second model. What
        the host does inside this one call is the host's to account for.
        """
        llm = getattr(self._ctx, "llm", None)
        if llm is None:
            raise HostLlmError(
                "this host does not offer a model to the plugin",
                code=CODE_HOST_LLM_UNAVAILABLE,
            )

        answer = llm.complete_structured(
            instructions=system,
            input=[{"type": "text", "text": user}],
            json_schema=schema,
            schema_name=purpose,
            purpose=purpose,
        )
        return {
            "parsed": getattr(answer, "parsed", None),
            "text": getattr(answer, "text", ""),
            "model": getattr(answer, "model", ""),
            "provider": getattr(answer, "provider", ""),
            "usage": _usage_of(answer),
            "request_id": _first_identifier(answer, ("request_id", "id")),
            "response_id": _first_identifier(answer, ("response_id", "completion_id")),
        }


def _first_identifier(answer: Any, names: tuple[str, ...]) -> str | None:
    """Return the first identifier this host happens to expose, if any.

    Hosts name these differently and some name them not at all. An absent
    identifier is recorded as absent rather than invented.
    """
    for name in names:
        value = getattr(answer, name, None)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _usage_of(answer: Any) -> dict[str, Any]:
    usage = getattr(answer, "usage", None)
    if usage is None:
        return {}
    return {
        name: getattr(usage, name)
        for name in (
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cost_usd",
        )
        if getattr(usage, name, None) is not None
    }


def digest_document(document: Mapping[str, Any]) -> str:
    """Return the digest of one JSON document, over its canonical bytes.

    Used to bind the sanitized improvement context into a proposal's
    provenance: the context is Techtree's, and the digest says which one was
    read without copying any of it.
    """
    return _digest_object(document)


def build_revision_provenance(
    *,
    commitments: Mapping[str, str],
    result: HostLlmResult,
    revision_attempt: int = 1,
) -> SkillRevisionProvenance:
    """Record what one proposed revision was made from. Decisions 0007 R2, 0010.

    ``commitments`` are the input digests the request itself carried, so the
    record and the request cannot disagree: every value here was computed from
    something the plugin actually read or sent.
    """
    if revision_attempt < 1:
        raise HostLlmError("a revision attempt is counted from one")

    missing = sorted(set(REQUEST_COMMITMENT_FIELDS) - set(commitments))
    if missing:
        raise HostLlmError(f"this request commits to nothing about {missing}")

    return SkillRevisionProvenance(
        skill_improver_digest=commitments["skill_improver_digest"],
        improvement_context_digest=commitments["improvement_context_digest"],
        source_skill_root_digest=commitments["source_skill_root_digest"],
        source_skill_entrypoint_digest=commitments["source_skill_entrypoint_digest"],
        output_schema_digest=commitments["output_schema_digest"],
        complete_request_digest=result.request_digest,
        host_model_id=result.model,
        host_response_digest=result.response_digest,
        revision_attempt=revision_attempt,
    )


def _digest_object(document: Mapping[str, Any]) -> str:
    """Return the digest of one object, over its canonical bytes."""
    canonical = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"
