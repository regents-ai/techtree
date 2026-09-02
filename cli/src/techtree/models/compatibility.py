"""Declaring where two Campaigns may differ, and what was found.

Plan ``docs/plan/v0.2.md``, "Configuration compatibility".

A v0.2 Campaign is immutable and binds one execution plan, so a provider rerun
and a backend-parity study are never one Campaign observed twice: they are two
Campaigns, and the question is whether the second is the same experiment as the
first. One policy model answers it for both purposes.

:class:`ConfigurationCompatibilityPolicy`
    Written before the comparison. It names the source Campaign, the paths that
    must be identical, and the paths that are permitted to drift. It is a
    hashed protocol object, so the claim "this rerun was judged under these
    rules" points at bytes rather than at an intention.

:class:`ConfigurationComparison`
    Written by the comparison. It names the policy it was judged under, the two
    Campaigns, every pointer at which they actually differed, and the verdict.

Three properties are enforced here rather than left to the function that
computes them, because a stored document is read by people who did not watch it
being produced:

*Paths are RFC 6901 pointers naming at least one reference token.* The whole
document is not a path a policy may declare; a policy that named it would
declare an entire Campaign either frozen or free.

*Path lists are sorted and carry no repeats.* Two spellings of the same policy
would be two digests of the same rules, and the plan requires drift paths to be
sorted and unique before hashing.

*The two path sets do not overlap.* Overlap is tested by containment and not by
string equality, so declaring drift at ``/agents`` while requiring
``/agents/subject/model`` to be equal is refused as the contradiction it is.

That last rule is what makes ``required_equal_paths`` binding, and it is the
reason the comparison in :mod:`techtree.compatibility` needs no separate test of
those paths. Because no required-equal path may lie inside a declared drift path
or contain one, a difference falling on a required-equal path can never lie
inside a declared drift path either — so the rule that rejects an undeclared
difference already rejects it. The list is enforced here, on the document, once,
rather than restated as a branch no input could reach.

The verdict and the drift list are held in agreement for the same reason: a
document that called itself an exact configuration while listing differences
would leave a reader unable to tell which half to believe.
"""

from __future__ import annotations

from typing import Annotated, Final, Literal, Self

from pydantic import StringConstraints, model_validator

from techtree.models.base import Digest, ProtocolModel
from techtree.pointers import JSON_POINTER_PATTERN, pointer_is_within

__all__ = [
    "COMPARISON_ALGORITHM",
    "CompatibilityVerdict",
    "ConfigurationComparison",
    "ConfigurationCompatibilityPolicy",
    "JsonPointer",
]

#: The one comparison algorithm v0.2 defines: walk both canonical Campaign
#: documents to their leaves and report every disagreement as an RFC 6901
#: pointer. Naming it in the policy is what lets a later algorithm exist
#: without silently rejudging a policy written under this one.
COMPARISON_ALGORITHM: Final = "rfc6901_json_pointer_v1"

type JsonPointer = Annotated[str, StringConstraints(pattern=JSON_POINTER_PATTERN)]
"""One RFC 6901 pointer naming at least one reference token."""

type CompatibilityVerdict = Literal[
    "exact_configuration",
    "compatible_with_declared_drift",
    "incompatible",
]
"""What a comparison concluded about the candidate Campaign."""


def _require_sorted_and_unique(label: str, paths: tuple[str, ...]) -> None:
    """Reject a path list that has more than one spelling of the same rules."""
    if len(set(paths)) != len(paths):
        raise ValueError(f"{label} must not repeat a pointer")
    if list(paths) != sorted(paths):
        raise ValueError(f"{label} must be sorted, so one rule set has one digest")


class ConfigurationCompatibilityPolicy(ProtocolModel):
    """The declared rules a candidate Campaign is judged against."""

    purpose: Literal["reproduction", "backend_parity"]
    source_campaign_digest: Digest
    required_equal_paths: tuple[JsonPointer, ...]
    allowed_drift_paths: tuple[JsonPointer, ...]
    comparison_algorithm: Literal["rfc6901_json_pointer_v1"]

    @model_validator(mode="after")
    def _check_the_path_lists_are_canonical(self) -> Self:
        """Reject repeated or unsorted paths on either list."""
        _require_sorted_and_unique("required_equal_paths", self.required_equal_paths)
        _require_sorted_and_unique("allowed_drift_paths", self.allowed_drift_paths)
        return self

    @model_validator(mode="after")
    def _check_the_path_lists_do_not_overlap(self) -> Self:
        """Reject a policy that both fixes and frees the same place."""
        for required in self.required_equal_paths:
            for allowed in self.allowed_drift_paths:
                if pointer_is_within(required, allowed) or pointer_is_within(
                    allowed, required
                ):
                    raise ValueError(
                        f"{required!r} must be equal and {allowed!r} may drift, "
                        "but one contains the other, so the policy contradicts "
                        "itself"
                    )
        return self


class ConfigurationComparison(ProtocolModel):
    """What comparing two Campaigns under one policy found."""

    policy_digest: Digest
    source_campaign_digest: Digest
    candidate_campaign_digest: Digest
    observed_drift_paths: tuple[JsonPointer, ...]
    compatibility: CompatibilityVerdict

    @model_validator(mode="after")
    def _check_the_drift_list_is_canonical(self) -> Self:
        """Reject repeated or unsorted drift pointers."""
        _require_sorted_and_unique("observed_drift_paths", self.observed_drift_paths)
        return self

    @model_validator(mode="after")
    def _check_the_verdict_agrees_with_the_drift(self) -> Self:
        """Reject a verdict the recorded drift contradicts."""
        if self.compatibility == "exact_configuration" and self.observed_drift_paths:
            raise ValueError(
                "an exact configuration has no observed drift; listing both "
                "leaves a reader unable to tell which one is true"
            )
        if (
            self.compatibility == "compatible_with_declared_drift"
            and not self.observed_drift_paths
        ):
            raise ValueError(
                "a comparison compatible with declared drift must say which "
                "declared paths actually drifted"
            )
        return self
