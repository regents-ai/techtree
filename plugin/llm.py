"""The host model seam. Specification section 8.4, decision 0007 R2.

The plugin asks the host's own model exactly one thing, ever: what one
revision of a Skill might be. It is one-shot, bounded by a schema, and may not
touch a number. Results are rendered by Techtree and relayed unchanged — no
model is asked to word one (decision 0009).

One completion means one. There is no retry here, no fallback model, no
"try again with a stricter prompt". A hidden second completion would quietly
turn one revision attempt into a search over attempts, and a search that keeps
the best result against the same tasks is how a controlled comparison becomes
an uncontrolled one. If a completion fails, the failure is returned to the
conversation, and asking again is a new thing a person decides to do.

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
    CODE_HOST_LLM_ALREADY_COMPLETED,
    CODE_HOST_LLM_OUTPUT_INVALID,
    CODE_HOST_LLM_UNAVAILABLE,
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

    def to_provenance(self) -> dict[str, Any]:
        """Return the operational metadata a proposal records about this call."""
        return {
            "complete_request_digest": self.request_digest,
            "host_response_digest": self.response_digest,
            "host_model_id": self.model,
            "host_provider": self.provider,
            "purpose": self.purpose,
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

    @property
    def used(self) -> bool:
        """Whether the one completion has been spent."""
        return self._used_for is not None

    def complete(self, request: HostLlmRequest) -> HostLlmResult:
        """Run the one completion this turn is allowed.

        Raises:
            HostLlmError: when a completion has already been made, when the
                request is malformed or oversized, when the host could not
                answer, or when what came back was not the shape that was
                asked for.
        """
        if self._used_for is not None:
            raise HostLlmError(
                "this turn has already had its one completion, for "
                f"{self._used_for!r}; asking again is a new decision for a "
                "person to make",
                code=CODE_HOST_LLM_ALREADY_COMPLETED,
            )
        _check_request(request)
        self._used_for = request.purpose

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
                f"the host model could not answer: {scrub_text(str(error))}",
                code=CODE_HOST_LLM_UNAVAILABLE,
                retryable=False,
            ) from error

        return _result_from(answer, request)


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
        raise HostLlmError(
            "the host model's answer was not the structured shape that was asked for",
            code=CODE_HOST_LLM_OUTPUT_INVALID,
        )

    return HostLlmResult(
        parsed=dict(parsed),
        request_digest=request.digest(),
        response_digest=_digest_object(dict(parsed)),
        model=str(answer.get("model") or "unknown"),
        provider=str(answer.get("provider") or "unknown"),
        purpose=request.purpose,
        usage=dict(answer["usage"]) if isinstance(answer.get("usage"), Mapping) else {},
    )


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
        """Call the host's structured completion exactly once."""
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
        }


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
