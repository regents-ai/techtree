"""Comparing two Campaigns under a declared compatibility policy.

Plan ``docs/plan/v0.2.md``, "Configuration compatibility".

A provider rerun and a backend-parity study both ask the same question of two
immutable Campaigns: is the second one the same experiment as the first, apart
from the differences somebody declared in advance? This module answers it, and
the answer is a list of RFC 6901 pointers rather than a judgement.

The walk is the one :mod:`techtree.manifests.compare` already performs for the
v0.1 baseline/candidate pair. Reusing it is not a convenience. Two comparators
would be two definitions of "these documents differ here", and the whole value
of a compatibility verdict is that anybody can re-derive it from the same two
documents and get the same pointers.

What differs from the v0.1 comparison is what the pointers are checked against.
There the permitted difference is fixed by the Campaign's mutation contract and
is always the subject's skill list. Here it is whatever the policy declared, and
the rules are the plan's:

* Every observed difference must lie inside a declared drift path. An
  undeclared difference makes the pair incompatible — this is the rule that
  stops a rerun with a quietly different model from being called a
  reproduction.
* A pair with no differences at all is an exact configuration. Unlike the v0.1
  variant comparison, that is the *best* outcome here rather than a fault: two
  variants that measure nothing are useless, but a rerun that reproduces a
  Campaign byte for byte is the strongest result a reproduction can have.

That is the whole of the check, and the policy's ``required_equal_paths`` is
deliberately not a third rule here. The policy already refuses to let a
required-equal path and a declared drift path contain one another, and that
refusal is what makes the list binding: a difference on a required-equal path
cannot also lie inside a declared drift path, so the undeclared-difference rule
above already rejects it. A separate test of the same paths would be a branch
no input can reach, and the invariant it would restate is enforced where it
belongs — on the policy document, before any comparison is made.

The comparison is computed over canonical Campaign bytes, not over summaries
and not over Python objects, because the protocol's byte form is what two
independent implementations agree on.

:func:`compare_campaign_configurations` never raises: it reports what it found.
:func:`assert_comparison_binds_its_policy` is the separate step that refuses a
stored comparison whose policy is not the policy it names.
"""

from __future__ import annotations

import json
from typing import Final

from techtree.canonical import canonical_json_bytes, digest_object
from techtree.errors import VerificationError
from techtree.manifests.compare import diff_values
from techtree.models.base import Digest, JsonValue
from techtree.models.campaign import CampaignSpec
from techtree.models.compatibility import (
    CompatibilityVerdict,
    ConfigurationComparison,
    ConfigurationCompatibilityPolicy,
)
from techtree.pointers import pointer_is_within

__all__ = [
    "CONFIGURATION_COMPARISON_INVALID",
    "assert_comparison_binds_its_policy",
    "compare_campaign_configurations",
    "observed_drift_paths",
]

#: The one error code a comparison that does not describe its own policy
#: reports.
CONFIGURATION_COMPARISON_INVALID: Final = "configuration_comparison_invalid"


def observed_drift_paths(
    source: CampaignSpec, candidate: CampaignSpec
) -> tuple[str, ...]:
    """Return every pointer at which the two canonical Campaigns disagree.

    Sorted and unique, which is the form the plan hashes and the form the
    comparison model stores.
    """
    differences = diff_values(_campaign_json(source), _campaign_json(candidate))
    return tuple(sorted({difference.pointer for difference in differences}))


def compare_campaign_configurations(
    policy: ConfigurationCompatibilityPolicy,
    source: CampaignSpec,
    candidate: CampaignSpec,
) -> ConfigurationComparison:
    """Compare two Campaigns and report the drift and the verdict."""
    source_digest = digest_object(source)
    candidate_digest = digest_object(candidate)
    drift = observed_drift_paths(source, candidate)

    return ConfigurationComparison(
        policy_digest=digest_object(policy),
        source_campaign_digest=source_digest,
        candidate_campaign_digest=candidate_digest,
        observed_drift_paths=drift,
        compatibility=_verdict(policy, source_digest, drift),
    )


def assert_comparison_binds_its_policy(
    comparison: ConfigurationComparison,
    policy: ConfigurationCompatibilityPolicy,
) -> None:
    """Raise :class:`VerificationError` when the pair does not describe itself.

    A comparison names its policy by digest, and a reader who was handed both
    documents has to be able to check that the rules in front of them are the
    rules the verdict was reached under. A swapped policy — one with a wider
    drift list, or one written for a different source Campaign — is exactly how
    an incompatible pair would be made to look compatible.
    """
    policy_digest = digest_object(policy)
    faults: list[str] = []
    if policy_digest != comparison.policy_digest:
        faults.append(
            f"the policy digests to {policy_digest}, and the comparison was "
            f"reached under {comparison.policy_digest}"
        )
    if policy.source_campaign_digest != comparison.source_campaign_digest:
        faults.append(
            f"the policy names source Campaign {policy.source_campaign_digest}, "
            f"and the comparison names {comparison.source_campaign_digest}"
        )
    if not faults:
        return
    raise VerificationError(
        "the comparison does not describe this compatibility policy, so its "
        "verdict says nothing about these rules: " + "; ".join(faults),
        code=CONFIGURATION_COMPARISON_INVALID,
        details={"faults": list(faults)},
    )


# ---------------------------------------------------------------------------
# The rules
# ---------------------------------------------------------------------------


def _verdict(
    policy: ConfigurationCompatibilityPolicy,
    source_digest: Digest,
    drift: tuple[str, ...],
) -> CompatibilityVerdict:
    """Apply the plan's rules, in the order a reader would ask them."""
    # A policy is written for one source Campaign. Judging a different one
    # under it would answer a question nobody asked.
    if policy.source_campaign_digest != source_digest:
        return "incompatible"
    if any(not _is_declared(pointer, policy.allowed_drift_paths) for pointer in drift):
        return "incompatible"
    return "compatible_with_declared_drift" if drift else "exact_configuration"


def _is_declared(pointer: str, allowed_drift_paths: tuple[str, ...]) -> bool:
    """Return whether a difference lies inside some declared drift path.

    Containment runs one way only. A difference reported above a declared path
    means something outside the declared subtree changed as well, and that is
    undeclared.
    """
    return any(pointer_is_within(pointer, root) for root in allowed_drift_paths)


def _campaign_json(campaign: CampaignSpec) -> JsonValue:
    """Return one Campaign's canonical JSON form."""
    decoded: JsonValue = json.loads(canonical_json_bytes(campaign).decode("utf-8"))
    return decoded
