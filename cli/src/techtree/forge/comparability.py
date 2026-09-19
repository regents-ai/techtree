"""Whether two forge run specifications may be compared at all.

A Skill-effect claim rests on the two arms having been the same experiment
apart from the Skill. That is the same claim :mod:`techtree.manifests.compare`
computes for a Climb, and it is computed the same way here: the arms are
required to be a baseline without a Skill and a candidate with one, then their
canonical JSON is walked to its leaves and every disagreement is reported as a
JSON Pointer. Only ``/arm`` and ``/skill`` may differ. A different build, task
list, model, Hermes version, starting state, limit or repetition count is a
violation, and the pair is not compared.

:func:`compare_run_specs` never raises: it reports what it found.
:func:`assert_comparable_run_specs` turns an uncontrolled finding into a
refusal, so a caller can inspect a bad pair before deciding what to do.
"""

from __future__ import annotations

from typing import Final

from techtree.canonical import to_json_value
from techtree.errors import VerificationError
from techtree.forge.experiment import run_spec_digest
from techtree.forge.models import ForgeArm, ForgeRunSpec
from techtree.manifests.compare import diff_values
from techtree.models.experiment import ManifestComparison
from techtree.pointers import pointer_is_within

__all__ = [
    "ALLOWED_RUN_SPEC_DIFFERENCES",
    "FORGE_COMPARISON_INVALID",
    "assert_comparable_run_specs",
    "compare_run_specs",
]

#: The error code an incomparable pair reports.
FORGE_COMPARISON_INVALID: Final = "forge_comparison_invalid"

#: The only pointers two comparable specifications may disagree at.
ALLOWED_RUN_SPEC_DIFFERENCES: Final[tuple[str, ...]] = ("/arm", "/skill")


def compare_run_specs(
    baseline: ForgeRunSpec, candidate: ForgeRunSpec
) -> ManifestComparison:
    """Compare two arms and report whether the pair measures the Skill alone."""
    violations: list[str] = []
    if baseline.arm is not ForgeArm.BASELINE:
        violations.append("the first specification is not the baseline arm")
    if candidate.arm is not ForgeArm.CANDIDATE:
        violations.append("the second specification is not the candidate arm")

    differences = sorted(
        diff_values(to_json_value(baseline), to_json_value(candidate)),
        key=lambda difference: difference.pointer,
    )
    violations.extend(
        f"{difference.pointer} differs between the arms"
        for difference in differences
        if not any(
            pointer_is_within(difference.pointer, allowed)
            for allowed in ALLOWED_RUN_SPEC_DIFFERENCES
        )
    )

    return ManifestComparison(
        baseline_configuration_digest=run_spec_digest(baseline),
        candidate_configuration_digest=run_spec_digest(candidate),
        differences=differences,
        allowed_differences=list(ALLOWED_RUN_SPEC_DIFFERENCES),
        controlled=not violations,
        violations=violations,
    )


def assert_comparable_run_specs(comparison: ManifestComparison) -> None:
    """Raise :class:`VerificationError` when the pair is not comparable."""
    if comparison.controlled:
        return
    raise VerificationError(
        "the two arms differ somewhere other than the Skill, so comparing "
        "them would not measure the Skill: " + "; ".join(comparison.violations),
        code=FORGE_COMPARISON_INVALID,
        details={
            "violations": list(comparison.violations),
            "differences": [
                difference.pointer for difference in comparison.differences
            ],
            "allowed_differences": list(comparison.allowed_differences),
        },
    )
