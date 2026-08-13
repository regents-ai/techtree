"""Proving that two variants differ only where permitted. Spec PR6 §6.5.

An uplift number is worth exactly as much as the claim that the two runs behind
it were the same experiment apart from the candidate skill. This module is that
claim, computed rather than asserted.

The check runs in two stages, and the order matters.

First the structural invariants are required outright: same Campaign, same
improvement program, same public context, same DataPolicy, same OutcomeContract,
same evaluation backend, the right variant on each side, no skill on the
baseline, exactly one on the candidate. These are stated as invariants rather
than discovered as differences because a diff can only say *that* two documents
disagree — it cannot say which disagreements were structurally impossible.

Then the two configurations are canonicalized to JSON and walked to their
leaves. A leaf that disagrees is reported as an RFC 6901 JSON Pointer, and the
pointers are checked against the Campaign's mutation contract, which in v0.1
permits exactly one root: ``/agents/subject/harness/skills``. A difference
anywhere else — a different model, a different image, a different task list, a
different ``use_bundled_skill`` — is a violation, and so is *no* difference at
all, because two identical configurations measure nothing.

Containment is compared segment by segment, so ``skills_extra`` is not inside
``skills``. A prefix test written with ``startswith`` alone would admit exactly
the field an attacker would add.

Two further choices are worth stating.

*The diff is over canonical JSON, not over Python objects.* Comparing models
would compare whatever Python decided equality means for each field type. The
protocol's own byte-level form is what two independent implementations agree
on, so it is what is compared.

*The invariants are checked here even where a model already enforces them.*
:class:`~techtree.models.experiment.ExperimentManifest` refuses a baseline with
a skill. This module refuses one again. The model protects documents that are
built; this function protects documents that are loaded, and the second is the
case that matters when a comparison is being audited rather than created.

:func:`compare_manifests` never raises: it reports what it found.
:func:`assert_controlled_comparison` is the separate step that turns an
uncontrolled finding into a refusal, so a caller can inspect a bad comparison
before deciding what to do about it.
"""

from __future__ import annotations

import json
from typing import Final

from techtree.canonical import canonical_json_bytes
from techtree.errors import VerificationError
from techtree.models.base import JsonValue
from techtree.models.campaign import MutationContract
from techtree.models.experiment import (
    ExperimentManifest,
    ExperimentVariant,
    JsonDifference,
    ManifestComparison,
)

__all__ = [
    "MANIFEST_COMPARISON_INVALID",
    "POINTER_SEPARATOR",
    "assert_controlled_comparison",
    "compare_manifests",
    "diff_values",
    "json_pointer_escape",
    "pointer_is_within",
]

#: RFC 6901 separates reference tokens with a solidus and gives it no other
#: meaning, which is why a token containing one has to be escaped.
POINTER_SEPARATOR: Final = "/"

#: The one error code an uncontrolled comparison reports. Spec PR6 §6.10.
MANIFEST_COMPARISON_INVALID: Final = "manifest_comparison_invalid"


def json_pointer_escape(segment: str) -> str:
    """Escape ``~`` as ``~0`` and ``/`` as ``~1``.

    In that order: escaping the solidus first would turn its replacement's
    tilde into a second escape.
    """
    return segment.replace("~", "~0").replace(POINTER_SEPARATOR, "~1")


def diff_values(
    baseline: JsonValue,
    candidate: JsonValue,
    *,
    pointer: str = "",
) -> list[JsonDifference]:
    """Recursively compare JSON values and return the leaves that disagree.

    The walk descends only where both sides are the same kind of container.
    Where they are not — an object against an array, a string against a number,
    a present element against a missing one — the disagreement is reported at
    that pointer and not decomposed further, because there is no shared
    structure left to attribute it to.

    Object keys are visited in sorted order and array elements in index order,
    so the same pair of documents always produces the same list.
    """
    if isinstance(baseline, dict) and isinstance(candidate, dict):
        return _diff_objects(baseline, candidate, pointer)
    if isinstance(baseline, list) and isinstance(candidate, list):
        return _diff_arrays(baseline, candidate, pointer)
    if _same_scalar(baseline, candidate):
        return []
    return [_difference(pointer, baseline, candidate)]


def pointer_is_within(pointer: str, allowed_root: str) -> bool:
    """Return whether a pointer is the allowed root or descends from it.

    ``/agents/subject/harness/skills_extra`` is not within
    ``/agents/subject/harness/skills``: containment is a boundary between
    reference tokens, not a string prefix.
    """
    return pointer == allowed_root or pointer.startswith(
        f"{allowed_root}{POINTER_SEPARATOR}"
    )


def compare_manifests(
    baseline: ExperimentManifest,
    candidate: ExperimentManifest,
    mutation: MutationContract,
) -> ManifestComparison:
    """Compare two variants' configurations and report whether it is controlled."""
    allowed = list(mutation.allowed_differences)

    violations = [
        *_variant_violations(baseline, candidate),
        *_shared_field_violations(baseline, candidate),
        *_skill_count_violations(baseline, candidate, mutation),
    ]

    differences = sorted(
        diff_values(
            _configuration_json(baseline),
            _configuration_json(candidate),
        ),
        key=lambda difference: difference.pointer,
    )

    if not differences:
        violations.append(
            "the candidate configuration is identical to the baseline, so the "
            "pair measures nothing"
        )
    violations.extend(_pointer_violations(differences, allowed))

    return ManifestComparison(
        baseline_configuration_digest=baseline.configuration_digest,
        candidate_configuration_digest=candidate.configuration_digest,
        differences=differences,
        allowed_differences=allowed,
        controlled=not violations,
        violations=violations,
    )


def assert_controlled_comparison(comparison: ManifestComparison) -> None:
    """Raise :class:`VerificationError` when the comparison is not controlled."""
    if comparison.controlled:
        return
    raise VerificationError(
        "the candidate differs from the baseline somewhere the Campaign does "
        "not permit, so the comparison would not measure the skill: "
        + "; ".join(comparison.violations),
        code=MANIFEST_COMPARISON_INVALID,
        details={
            "violations": list(comparison.violations),
            "differences": [
                difference.pointer for difference in comparison.differences
            ],
            "allowed_differences": list(comparison.allowed_differences),
        },
    )


# ---------------------------------------------------------------------------
# The diff
# ---------------------------------------------------------------------------


def _diff_objects(
    baseline: dict[str, JsonValue],
    candidate: dict[str, JsonValue],
    pointer: str,
) -> list[JsonDifference]:
    differences: list[JsonDifference] = []
    for key in sorted(baseline.keys() | candidate.keys()):
        child = f"{pointer}{POINTER_SEPARATOR}{json_pointer_escape(key)}"
        if key not in baseline:
            differences.append(_difference(child, None, candidate[key]))
        elif key not in candidate:
            differences.append(_difference(child, baseline[key], None))
        else:
            differences.extend(
                diff_values(baseline[key], candidate[key], pointer=child)
            )
    return differences


def _diff_arrays(
    baseline: list[JsonValue],
    candidate: list[JsonValue],
    pointer: str,
) -> list[JsonDifference]:
    differences: list[JsonDifference] = []
    for index in range(max(len(baseline), len(candidate))):
        child = f"{pointer}{POINTER_SEPARATOR}{index}"
        if index >= len(baseline):
            differences.append(_difference(child, None, candidate[index]))
        elif index >= len(candidate):
            differences.append(_difference(child, baseline[index], None))
        else:
            differences.extend(
                diff_values(baseline[index], candidate[index], pointer=child)
            )
    return differences


def _same_scalar(baseline: JsonValue, candidate: JsonValue) -> bool:
    """Compare two JSON scalars without letting Python widen the question.

    ``True == 1`` and ``1 == 1.0`` in Python, and neither is true of the JSON
    documents these came from, so the type has to agree before the value does.
    """
    if isinstance(baseline, bool) != isinstance(candidate, bool):
        return False
    if isinstance(baseline, int | float) != isinstance(candidate, int | float):
        return False
    return baseline == candidate


def _difference(
    pointer: str, baseline: JsonValue, candidate: JsonValue
) -> JsonDifference:
    # The document root is the empty pointer, which the model cannot hold; a
    # whole-configuration disagreement is reported at ``/`` instead.
    return JsonDifference(
        pointer=pointer or POINTER_SEPARATOR,
        baseline=baseline,
        candidate=candidate,
    )


def _configuration_json(manifest: ExperimentManifest) -> JsonValue:
    """Return the canonical JSON form of one manifest's configuration."""
    decoded: JsonValue = json.loads(
        canonical_json_bytes(manifest.configuration).decode("utf-8")
    )
    return decoded


# ---------------------------------------------------------------------------
# The invariants
# ---------------------------------------------------------------------------


def _variant_violations(
    baseline: ExperimentManifest, candidate: ExperimentManifest
) -> list[str]:
    violations: list[str] = []
    if baseline.variant is not ExperimentVariant.BASELINE:
        violations.append(
            f"the baseline side of the comparison is a {baseline.variant.value} "
            "manifest"
        )
    if candidate.variant is not ExperimentVariant.CANDIDATE:
        violations.append(
            f"the candidate side of the comparison is a {candidate.variant.value} "
            "manifest"
        )
    return violations


def _shared_field_violations(
    baseline: ExperimentManifest, candidate: ExperimentManifest
) -> list[str]:
    """Report every field the two variants are required to share."""
    return [
        f"the baseline and the candidate name a different {label}"
        for label, left, right in (
            ("Campaign", baseline.campaign_spec_digest, candidate.campaign_spec_digest),
            ("improvement program", baseline.program_ref, candidate.program_ref),
            ("public context", baseline.public_context, candidate.public_context),
            (
                "DataPolicy",
                baseline.configuration.data_policy_digest,
                candidate.configuration.data_policy_digest,
            ),
            (
                "OutcomeContract",
                baseline.configuration.outcome_contract_digest,
                candidate.configuration.outcome_contract_digest,
            ),
            (
                "evaluation backend",
                baseline.configuration.evaluation_backend,
                candidate.configuration.evaluation_backend,
            ),
        )
        if left != right
    ]


def _skill_count_violations(
    baseline: ExperimentManifest,
    candidate: ExperimentManifest,
    mutation: MutationContract,
) -> list[str]:
    target = mutation.target_agent
    baseline_agent = baseline.configuration.agents.get(target)
    candidate_agent = candidate.configuration.agents.get(target)

    if baseline_agent is None or candidate_agent is None:
        return [f"a variant defines no {target} agent to compare"]

    violations: list[str] = []
    if baseline_agent.harness.skills:
        violations.append(
            f"the baseline carries {len(baseline_agent.harness.skills)} candidate "
            "skills; a baseline carries none"
        )
    if len(candidate_agent.harness.skills) != 1:
        violations.append(
            f"the candidate carries {len(candidate_agent.harness.skills)} skills; "
            "v0.1 measures exactly one"
        )
    return violations


def _pointer_violations(
    differences: list[JsonDifference], allowed: list[str]
) -> list[str]:
    return [
        f"the candidate differs at {difference.pointer}, which the mutation "
        "contract does not permit"
        for difference in differences
        if not any(pointer_is_within(difference.pointer, root) for root in allowed)
    ]
