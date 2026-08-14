"""The fixed words a result carries. Specification section 8.6.

Techtree computed the result, so Techtree's deterministic payload is the only
source of every number, verdict, status, grade, and digest. What this module
adds is fixed text that never varies: the reproduction statement, the two
result labels, and the same-membership disclosure that travels with a second
comparison.

Decision 0009 removed presentation wording by a host model from the release.
The wording builders and answer schema below are kept for reference and are
reachable from nothing in the released flow: no released path asks a model to
word a result, and the release promises none.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final

from .channels import is_gateway_safe_required
from .errors import PluginError
from .models import ChannelKind, PresentationNarrative

CODE_NARRATIVE_INVALID: Final = "host_llm_output_invalid"

#: Fields of the deterministic payload the model may read. Everything else —
#: task rows, digests, raw skill summaries — is either not its business or
#: not something it can safely be tempted to restate.
ALLOWED_FACTS: Final[tuple[str, ...]] = (
    "campaign_title",
    "comparison_label",
    "baseline_score",
    "candidate_score",
    "absolute_delta",
    "relative_delta",
    "wins",
    "losses",
    "ties",
    "decision",
    "proof_grade",
    "verification_status",
)

#: How many task labels the model may be shown, and choose between.
MAXIMUM_TASK_REFS: Final = 40

#: Claims nobody may make about a local result, stated to the model as part of
#: its input so that refusing them later is not a surprise.
FORBIDDEN_CLAIMS: Final[tuple[str, ...]] = (
    "independently reproduced",
    "the website verified the execution",
    "sealed evaluation",
    "Prime-hosted execution",
    "training-ready data",
    "guaranteed improvement",
    "the agent universally learned the capability",
)

#: What the model is told about the shape of its answer, in its own words.
NARRATIVE_INSTRUCTIONS: Final = (
    "You are choosing how to word a comparison result that Techtree has "
    "already computed. Every number, verdict, status, proof grade, and digest "
    "is rendered separately from what you write, and is not yours to state, "
    "repeat, round, or change. Write plainly. If the result is a tie or a "
    "regression, say so first."
)

#: The one deterministic sentence a result must always carry.
REPRODUCTION_STATEMENT: Final = (
    "This comparison was run locally by Techtree. It has not been "
    "independently reproduced."
)

_MAXIMUM_HEADLINE_CHARACTERS: Final = 120
_MAXIMUM_TEXT_CHARACTERS: Final = 400
_MAXIMUM_ITEMS: Final = 5


def build_presentation_input(
    *,
    deterministic_payload: Mapping[str, Any],
    channel: ChannelKind,
) -> dict[str, Any]:
    """Construct the exact input the rich-output Skill is given.

    Only the facts it is allowed to reason over, the verified caveats, the
    task labels it may refer to, the claims it must not make, and how much
    room it has. Nothing hidden, nothing from inside a run, and nothing it
    could mistake for permission to invent a value.
    """
    facts = {
        name: deterministic_payload[name]
        for name in ALLOWED_FACTS
        if name in deterministic_payload
    }
    return {
        "instructions": NARRATIVE_INSTRUCTIONS,
        "facts": facts,
        "verified_caveats": [
            caveat.get("text")
            for caveat in _caveats(deterministic_payload)
            if isinstance(caveat.get("text"), str)
        ],
        "allowed_task_refs": sorted(allowed_task_refs(deterministic_payload)),
        "forbidden_claims": list(FORBIDDEN_CLAIMS),
        "channel": channel.value,
        "room": "short" if is_gateway_safe_required(channel) else "ordinary",
        "reproduction_statement": REPRODUCTION_STATEMENT,
    }


def allowed_task_refs(deterministic_payload: Mapping[str, Any]) -> set[str]:
    """Return the task labels a narrative may name."""
    rows = deterministic_payload.get("task_rows")
    if not isinstance(rows, Sequence):
        return set()
    labels = {
        str(row["task_label"])
        for row in rows
        if isinstance(row, Mapping) and isinstance(row.get("task_label"), str)
    }
    return set(sorted(labels)[:MAXIMUM_TASK_REFS])


def presentation_output_schema() -> dict[str, Any]:
    """Return the schema a narrative must fit.

    There is no numeric field here, and no field for a verdict code, a status,
    a grade, or a digest. The model cannot return one because there is nowhere
    to return it.
    """
    return {
        "type": "object",
        "description": (
            "Wording choices about a result that has already been computed. "
            "No scores, deltas, win counts, costs, timings, proof grades, "
            "statuses, digests, or commands."
        ),
        "properties": {
            "headline": {
                "type": "string",
                "maxLength": _MAXIMUM_HEADLINE_CHARACTERS,
                "description": "One plain sentence about what happened.",
            },
            "observations": {
                "type": "array",
                "maxItems": _MAXIMUM_ITEMS,
                "items": {"type": "string", "maxLength": _MAXIMUM_TEXT_CHARACTERS},
                "description": "Which of the given facts deserve emphasis.",
            },
            "caveats": {
                "type": "array",
                "maxItems": _MAXIMUM_ITEMS,
                "items": {"type": "string", "maxLength": _MAXIMUM_TEXT_CHARACTERS},
                "description": (
                    "Which verified caveat to foreground, in your own words."
                ),
            },
            "next_step": {
                "type": ["string", "null"],
                "maxLength": _MAXIMUM_TEXT_CHARACTERS,
                "description": "What the reader might reasonably do next.",
            },
            "selected_task_refs": {
                "type": "array",
                "maxItems": _MAXIMUM_ITEMS,
                "items": {"type": "string", "maxLength": 120},
                "description": "Task labels worth naming, from the allowed list.",
            },
        },
        "required": ["headline", "observations", "caveats"],
        "additionalProperties": False,
    }


def parse_presentation_narrative(value: Mapping[str, Any]) -> PresentationNarrative:
    """Read a narrative out of a structured answer, strictly.

    Raises:
        PluginError: when the answer is not the shape that was asked for, or
            carries a field the schema does not have — a model returning a
            "baseline_score" is a model that misunderstood its job, and its
            answer is not used.
    """
    if not isinstance(value, Mapping):
        raise PluginError(
            "the narrative was not an object", code=CODE_NARRATIVE_INVALID
        )

    known = set(presentation_output_schema()["properties"])
    unknown = sorted(set(value) - known)
    if unknown:
        raise PluginError(
            f"the narrative carries fields it was not asked for: {unknown}",
            code=CODE_NARRATIVE_INVALID,
        )

    if not isinstance(value.get("headline"), str) or not value["headline"].strip():
        raise PluginError("the narrative has no headline", code=CODE_NARRATIVE_INVALID)

    next_step = value.get("next_step")
    if next_step is not None and not isinstance(next_step, str):
        raise PluginError(
            "the narrative's next step is not text", code=CODE_NARRATIVE_INVALID
        )

    return PresentationNarrative(
        headline=value["headline"].strip(),
        observations=_strings(value.get("observations"), "observations"),
        caveats=_strings(value.get("caveats"), "caveats"),
        next_step=next_step.strip()
        if isinstance(next_step, str) and next_step
        else None,
        selected_task_refs=_strings(value.get("selected_task_refs"), "task refs"),
    )


def _strings(value: Any, described: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise PluginError(
            f"the narrative's {described} are not a list", code=CODE_NARRATIVE_INVALID
        )
    items = []
    for item in value:
        if not isinstance(item, str):
            raise PluginError(
                f"the narrative's {described} contain something that is not text",
                code=CODE_NARRATIVE_INVALID,
            )
        if item.strip():
            items.append(item.strip())
    return tuple(items)


def _caveats(deterministic_payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    caveats = deterministic_payload.get("caveats")
    if not isinstance(caveats, Sequence):
        return []
    return [caveat for caveat in caveats if isinstance(caveat, Mapping)]


# The second comparison ------------------------------------------------------------
#
# Decision 0007 fixes the words for this one, because it is the result most
# easily oversold. A revision proposed from a run's own feedback, measured
# again on that same task set, is a development iteration — useful, honest,
# and not evidence that anything generalizes. Decision 0009 fixes the two
# public labels these results are shown under.

#: What the first comparison's result is called.
FIRST_RESULT_LABEL: Final = "Hello World Uplift Receipt"

#: What the second comparison's result is called.
SECOND_RESULT_LABEL: Final = "Hello World — Iteration 2"

#: What kind of exercise it is.
SECOND_RESULT_ITERATION_LABEL: Final = "same-benchmark development iteration"

#: The sentence that has to travel with it.
SAME_MEMBERSHIP_DISCLOSURE: Final = (
    "The revision was written from this run's own feedback and measured again "
    "on the same task membership, so this is a development iteration rather "
    "than evidence that the Skill generalizes."
)

#: Words that would describe this result as something it is not.
SECOND_RESULT_FORBIDDEN_WORDS: Final[tuple[str, ...]] = (
    "sealed",
    "held-out",
    "held out",
    "generalization",
    "generalisation",
    "independent",
)


def second_result_receipt(
    *,
    source_feedback_report_digest: str | None,
    decision: str | None,
    verification_status: str | None,
) -> dict[str, Any]:
    """Return the fixed wording and provenance for a second comparison.

    The label and the disclosure are constants, not choices. The provenance
    names the report the revision was written from, which is what makes
    "the same membership" checkable rather than merely stated.
    """
    return {
        "label": SECOND_RESULT_LABEL,
        "iteration": SECOND_RESULT_ITERATION_LABEL,
        "disclosure": SAME_MEMBERSHIP_DISCLOSURE,
        "reproduction": REPRODUCTION_STATEMENT,
        "source_feedback_report_digest": source_feedback_report_digest,
        "decision": decision,
        "verification_status": verification_status,
    }
