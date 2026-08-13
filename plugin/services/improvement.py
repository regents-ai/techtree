"""The one improvement turn. Specification sections 8.10 to 8.12.

Techtree decides what a host model is allowed to know about a finished run.
It builds the sanitized context; this reads it, checks that it is what it
claims to be, and refuses it outright if anything from the exclusion list is
in there. The plugin never assembles its own view of a run, and never reaches
past what the context carries.

Then exactly one completion. Not one that succeeds — one that happens. A
failed or unusable answer still spends the turn, because the promise being
kept is "one agent reasoning turn", and a retry that only fires on failure is
a search dressed as an error path. A person can always leave the guided
introduction and use the ordinary tools; what cannot happen is the plugin
quietly trying again.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from ..errors import PluginError, contains_secret_material
from ..guards import validate_revised_skill
from ..llm import (
    HostLlmRequest,
    OneShotHostLlm,
    build_revision_provenance,
    digest_document,
)
from ..models import (
    DemoSessionState,
    DemoStage,
    ReleaseCore,
    SkillRevisionOutput,
    SkillRevisionProvenance,
)

CODE_CONTEXT_INVALID: Final = "improvement_context_invalid"
CODE_CONTEXT_FORBIDDEN: Final = "improvement_context_forbidden_material"
CODE_ATTEMPT_USED: Final = "improvement_attempt_already_used"
CODE_REVISION_INVALID: Final = "skill_revision_output_invalid"

SUPPORTED_CONTEXT_SCHEMA: Final = "techtree.skill-improvement-context.v1"

#: What decision 0007 R1 says a context may carry.
CONTEXT_FIELDS: Final[tuple[str, ...]] = (
    "schema_version",
    "source_run_id",
    "source_report_digest",
    "campaign_spec_digest",
    "parent_skill_digest",
    "parent_skill_entrypoint_digest",
    "data_policy_digest",
    "objective",
    "current_result",
    "examples",
    "constraints",
    "prohibited_material",
)

#: Field names that would mean hidden material travelled with the context.
#: Decision 0007 R1's exclusion list, as things to look for rather than
#: promises to trust.
FORBIDDEN_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "expected_answer",
        "expected_answers",
        "expected_output",
        "answer",
        "answers",
        "answer_key",
        "solution",
        "solutions",
        "grader",
        "grader_source",
        "grading_code",
        "hidden",
        "hidden_fields",
        "provider_request",
        "provider_payload",
        "raw_messages",
        "raw_tool_arguments",
        "api_key",
        "authorization",
        "private_key",
        "environment",
        "env",
    }
)

#: Absolute paths are private detail, and a model has no use for one.
_PRIVATE_PATH_PREFIXES: Final[tuple[str, ...]] = ("/Users/", "/home/", "/root/", "C:\\")

#: The one purpose the improvement completion is made for.
REVISION_PURPOSE: Final = "skill_revision"

#: How many attempts the guided introduction allows. Specification 8.11.
MAXIMUM_REVISION_ATTEMPTS: Final = 1


@dataclass(frozen=True)
class SourceSkill:
    """The verified text of the Skill a run measured, and its fingerprints."""

    run_id: str
    name: str
    root_digest: str
    entrypoint_digest: str
    text: str


@dataclass(frozen=True)
class RevisionProposal:
    """One proposal, and the record of exactly what it was made from."""

    output: SkillRevisionOutput
    provenance: SkillRevisionProvenance
    session: DemoSessionState

    def to_dict(self) -> dict[str, Any]:
        """Return the proposal in the shape a tool result carries it."""
        return {
            "proposal": self.output.to_dict(),
            "provenance": self.provenance.to_dict(),
        }


def revision_output_schema() -> dict[str, Any]:
    """Return the shape a proposal must take. Specification section 8.12."""
    return {
        "type": "object",
        "description": (
            "One proposed revision of a Skill: what you found, what you "
            "changed and why, the complete revised SKILL.md, and what it "
            "costs. No scores, and no answers."
        ),
        "properties": {
            "analysis_summary": {
                "type": "string",
                "maxLength": 2000,
                "description": "The one general rule that explains the failures.",
            },
            "change_rationale": {
                "type": "array",
                "maxItems": 6,
                "items": {"type": "string", "maxLength": 500},
                "description": "Why each change follows from that rule.",
            },
            "revised_skill_markdown": {
                "type": "string",
                "maxLength": 40000,
                "description": (
                    "The complete revised SKILL.md, whole. Not a patch, not a "
                    "fragment, and never a list of cases with their answers."
                ),
            },
            "expected_tradeoffs": {
                "type": "array",
                "maxItems": 6,
                "items": {"type": "string", "maxLength": 500},
                "description": "What this change might cost elsewhere.",
            },
            "confidence": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "How sure you are, in one of exactly three words.",
            },
        },
        "required": [
            "analysis_summary",
            "change_rationale",
            "revised_skill_markdown",
            "expected_tradeoffs",
            "confidence",
        ],
        "additionalProperties": False,
    }


class ImprovementService:
    """Reads what a run is willing to show, and asks for one revision."""

    def __init__(
        self,
        *,
        llm: Any,
        release: ReleaseCore,
        bridge: Any,
        temp_root: Path | None = None,
    ) -> None:
        self._llm = llm
        self._release = release
        self._bridge = bridge
        self._temp_root = temp_root

    # Reading what Techtree will show ------------------------------------------

    def get_context(self, source_run_id: str) -> dict[str, Any]:
        """Invoke ``techtree uplift context`` and check what came back.

        Raises:
            PluginError: when Techtree refused, when the document is not a
                context this plugin understands, or when anything from the
                exclusion list travelled with it.
        """
        envelope = self._bridge.invoke(["uplift", "context", source_run_id])
        if not envelope.get("ok"):
            raise PluginError(
                _cli_message(
                    envelope, "Techtree would not build an improvement context"
                ),
                code=CODE_CONTEXT_INVALID,
            )

        data = envelope.get("data")
        context = data.get("context") if isinstance(data, Mapping) else None
        if not isinstance(context, Mapping):
            raise PluginError(
                "that is not an improvement context", code=CODE_CONTEXT_INVALID
            )

        validate_context(context)
        return dict(context)

    def load_source_skill(self, context: Mapping[str, Any]) -> SourceSkill:
        """Read the verified Skill the run measured, and check it belongs here.

        Techtree reads it out of the run's own copy and reports its digests
        beside it; this checks those against the digests the context pinned,
        so the text handed to a model is provably the text the run measured.
        The path it came from is never part of what the model sees.
        """
        run_id = str(context["source_run_id"])
        envelope = self._bridge.invoke(["uplift", "skill-source", run_id])
        if not envelope.get("ok"):
            raise PluginError(
                _cli_message(envelope, "Techtree would not read the run's Skill"),
                code=CODE_CONTEXT_INVALID,
            )

        data = envelope.get("data")
        if not isinstance(data, Mapping):
            raise PluginError(
                "that is not a Skill source payload", code=CODE_CONTEXT_INVALID
            )

        text = data.get("entrypoint_text")
        if not isinstance(text, str) or not text.strip():
            raise PluginError(
                "the run's Skill came back with no text", code=CODE_CONTEXT_INVALID
            )

        mismatches = [
            name
            for name, reported, pinned in (
                (
                    "root digest",
                    data.get("skill_root_digest"),
                    context.get("parent_skill_digest"),
                ),
                (
                    "entrypoint digest",
                    data.get("entrypoint_digest"),
                    context.get("parent_skill_entrypoint_digest"),
                ),
                ("run", data.get("source_run_id"), context.get("source_run_id")),
            )
            if reported != pinned
        ]
        if mismatches:
            raise PluginError(
                "the Skill Techtree read is not the one this context pins: "
                + ", ".join(mismatches),
                code=CODE_CONTEXT_FORBIDDEN,
                repair="Rebuild the improvement context from the run.",
            )
        if contains_secret_material(text):
            raise PluginError(
                "the Skill carries something that looks like a credential, so it "
                "will not be read out to a model",
                code=CODE_CONTEXT_FORBIDDEN,
            )

        return SourceSkill(
            run_id=run_id,
            name=str(data.get("skill_name") or "skill"),
            root_digest=str(data.get("skill_root_digest")),
            entrypoint_digest=str(data.get("entrypoint_digest")),
            text=text,
        )

    # Asking for one revision ----------------------------------------------------

    def build_improver_input(
        self, *, context: Mapping[str, Any], source_skill_markdown: str
    ) -> HostLlmRequest:
        """Build the one request: the context, and the Skill, and nothing else."""
        return HostLlmRequest(
            system=IMPROVER_INSTRUCTIONS,
            user=json.dumps(
                {"improvement_context": dict(context)},
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            ),
            schema=revision_output_schema(),
            purpose=REVISION_PURPOSE,
            attachments={"source_skill": source_skill_markdown},
        )

    def propose_once(
        self,
        *,
        source_run_id: str,
        demo_session: DemoSessionState,
        skill_improver_digest: str,
    ) -> RevisionProposal:
        """Make exactly one structured completion, and spend the turn on it.

        Raises:
            PluginError: when the run is not a finished one, when the turn has
                already been spent, or when what came back cannot be used. The
                turn is spent either way: the returned session records the
                attempt whether the answer was usable or not.
        """
        # The turn limit is checked first, so a second attempt is told the
        # true reason — the turn is spent — rather than something about the
        # stage the first proposal moved the session into.
        require_unused_turn(demo_session)
        require_first_result(demo_session, source_run_id)

        context = self.get_context(source_run_id)
        skill = self.load_source_skill(context)
        request = self.build_improver_input(
            context=context, source_skill_markdown=skill.text
        )

        spent = _spend_attempt(demo_session)
        result = OneShotHostLlm(self._llm).complete(request)
        output = parse_revision_output(result.parsed)
        validate_revised_skill(
            output.revised_skill_markdown, task_inputs=public_prompts(context)
        )

        return RevisionProposal(
            output=output,
            provenance=build_revision_provenance(
                parent_skill_root_digest=skill.root_digest,
                parent_skill_entrypoint_digest=skill.entrypoint_digest,
                improvement_context_digest=digest_document(context),
                skill_improver_digest=skill_improver_digest,
                result=result,
                revision_attempt=spent.revision_attempts,
            ),
            session=spent,
        )


#: What the improver Skill is told, beside the founder Skill's own instructions.
IMPROVER_INSTRUCTIONS: Final = (
    "You are proposing exactly one revision of the Skill supplied to you. "
    "Find the single general rule that explains the failures in the context, "
    "make the smallest correction that fixes it, and return the complete "
    "revised SKILL.md. Preserve every rule that is already correct. Never "
    "copy a task or its answer into the Skill, never add a task-specific "
    "exception, and never write a table of cases and results: a Skill states "
    "a rule. State what your change might cost."
)


# Validation ------------------------------------------------------------------------


def validate_context(context: Mapping[str, Any]) -> None:
    """Check a context is one this plugin may read out. Section 8.10, R1.

    Raises:
        PluginError: when the schema is unknown, a required fingerprint is
            missing, a subject reply survived, or anything from the exclusion
            list is present anywhere in the document.
    """
    if context.get("schema_version") != SUPPORTED_CONTEXT_SCHEMA:
        raise PluginError(
            f"improvement context schema {context.get('schema_version')!r} is not "
            f"{SUPPORTED_CONTEXT_SCHEMA!r}",
            code=CODE_CONTEXT_INVALID,
        )

    missing = [name for name in CONTEXT_FIELDS if name not in context]
    if missing:
        raise PluginError(
            f"this improvement context is missing {missing}",
            code=CODE_CONTEXT_INVALID,
        )

    _forbid_hidden_material(context)

    for example in _examples(context):
        if example.get("subject_reply") is not None:
            raise PluginError(
                "this improvement context carries a subject's reply, which no "
                "revision may be based on",
                code=CODE_CONTEXT_FORBIDDEN,
            )

    document = json.dumps(context, default=str)
    if contains_secret_material(document):
        raise PluginError(
            "this improvement context carries something that looks like a credential",
            code=CODE_CONTEXT_FORBIDDEN,
        )
    for prefix in _PRIVATE_PATH_PREFIXES:
        if prefix in document:
            raise PluginError(
                "this improvement context carries a private path",
                code=CODE_CONTEXT_FORBIDDEN,
            )


def _forbid_hidden_material(value: Any, path: str = "context") -> None:
    """Walk the document refusing any key from the exclusion list."""
    if isinstance(value, Mapping):
        for name, item in value.items():
            if str(name).lower() in FORBIDDEN_FIELD_NAMES:
                raise PluginError(
                    f"this improvement context carries {path}.{name}, which is "
                    "hidden material a revision may never see",
                    code=CODE_CONTEXT_FORBIDDEN,
                )
            _forbid_hidden_material(item, f"{path}.{name}")
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for index, item in enumerate(value):
            _forbid_hidden_material(item, f"{path}[{index}]")


def public_prompts(context: Mapping[str, Any]) -> list[str]:
    """Return the public task prompts the context showed."""
    return [
        example["public_prompt"]
        for example in _examples(context)
        if isinstance(example.get("public_prompt"), str) and example["public_prompt"]
    ]


def parse_revision_output(value: Mapping[str, Any]) -> SkillRevisionOutput:
    """Read a proposal out of a structured answer, strictly."""
    if not isinstance(value, Mapping):
        raise PluginError("the proposal was not an object", code=CODE_REVISION_INVALID)

    known = set(revision_output_schema()["properties"])
    unknown = sorted(set(value) - known)
    if unknown:
        raise PluginError(
            f"the proposal carries fields it was not asked for: {unknown}",
            code=CODE_REVISION_INVALID,
        )

    for name in ("analysis_summary", "revised_skill_markdown"):
        if not isinstance(value.get(name), str) or not value[name].strip():
            raise PluginError(
                f"the proposal has no {name.replace('_', ' ')}",
                code=CODE_REVISION_INVALID,
            )

    confidence = value.get("confidence")
    if confidence not in ("low", "medium", "high"):
        raise PluginError(
            f"the proposal's confidence is {confidence!r}, which is not one of "
            "low, medium, or high",
            code=CODE_REVISION_INVALID,
        )

    return SkillRevisionOutput(
        analysis_summary=value["analysis_summary"].strip(),
        change_rationale=_bounded_strings(value.get("change_rationale"), "rationale"),
        revised_skill_markdown=value["revised_skill_markdown"],
        expected_tradeoffs=_bounded_strings(
            value.get("expected_tradeoffs"), "tradeoffs"
        ),
        confidence=confidence,
    )


def require_first_result(session: DemoSessionState, source_run_id: str) -> None:
    """Refuse a revision of anything but this session's finished first run."""
    if session.first_run_id != source_run_id:
        raise PluginError(
            "that is not the run this session compared first",
            code=CODE_CONTEXT_INVALID,
        )
    if session.stage not in (
        DemoStage.FIRST_RESULT_READY,
        DemoStage.REVISION_PROPOSAL_READY,
        DemoStage.SECOND_DRAFT_PREPARED,
    ):
        raise PluginError(
            "there is no finished first comparison to improve on yet",
            code=CODE_CONTEXT_INVALID,
            repair="Wait for the first run to finish, then read its result.",
        )


def require_unused_turn(session: DemoSessionState) -> None:
    """Refuse a second revision in the guided introduction."""
    if session.revision_attempts >= MAXIMUM_REVISION_ATTEMPTS:
        raise PluginError(
            "this guided introduction has already had its one revision; a "
            "further attempt is a decision for a person, with the ordinary "
            "tools",
            code=CODE_ATTEMPT_USED,
        )


def _spend_attempt(session: DemoSessionState) -> DemoSessionState:
    """Return the session with the turn spent, whatever happens next."""
    from dataclasses import replace
    from datetime import UTC, datetime

    return replace(
        session,
        revision_attempts=session.revision_attempts + 1,
        updated_at=datetime.now(UTC).isoformat(),
    )


def _bounded_strings(value: Any, described: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise PluginError(
            f"the proposal's {described} are not a list", code=CODE_REVISION_INVALID
        )
    items = []
    for item in value:
        if not isinstance(item, str):
            raise PluginError(
                f"the proposal's {described} contain something that is not text",
                code=CODE_REVISION_INVALID,
            )
        if item.strip():
            items.append(item.strip())
    return tuple(items[:6])


def _examples(context: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    examples = context.get("examples")
    if not isinstance(examples, Sequence):
        return []
    return [example for example in examples if isinstance(example, Mapping)]


def _cli_message(envelope: Mapping[str, Any], fallback: str) -> str:
    error = envelope.get("error")
    if isinstance(error, Mapping) and isinstance(error.get("message"), str):
        return str(error["message"])
    return fallback
