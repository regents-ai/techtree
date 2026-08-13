"""Data rights, and the split between asking and being told. Spec 11.4, 27.2.

Two subjects live here. The first is the ``DataPolicy`` itself: whether the
development policy is valid, and whether a policy that permits a use it also
makes impossible is refused.

The second is decisions document 0003 A5 — the split between
``PolicyAcceptanceRequirement`` (what a draft says must be accepted) and
``PolicyAcknowledgement`` (what a run records was accepted). Keeping them apart
is what stops possession of a confirmation token from standing in for reading a
rights policy.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import sha256_digest_bytes
from techtree.errors import PolicyError
from techtree.models.climb import ClimbManifest, check_climb_policy_consistency
from techtree.models.data_policy import DataOwner, DataPolicy
from techtree.models.run import PolicyAcknowledgement
from techtree.models.skill import PolicyAcceptanceRequirement

GOLDEN_DIRECTORY = Path(__file__).resolve().parents[1] / "golden"

OTHER_DIGEST = sha256_digest_bytes(b"a different policy")


def golden(name: str) -> dict[str, Any]:
    """Load one committed golden fixture as a mutable JSON document."""
    text = (GOLDEN_DIRECTORY / f"{name}.json").read_text(encoding="utf-8")
    document: dict[str, Any] = json.loads(text)
    return document


def data_policy(document: dict[str, Any]) -> DataPolicy:
    """Validate a DataPolicy document the way stored bytes are validated."""
    return DataPolicy.model_validate_json(json.dumps(document))


def climb(document: dict[str, Any]) -> ClimbManifest:
    """Validate a Climb document the way stored bytes are validated."""
    return ClimbManifest.model_validate_json(json.dumps(document))


# ---------------------------------------------------------------------------
# The development policy
# ---------------------------------------------------------------------------


def test_development_policy_is_valid() -> None:
    policy = data_policy(golden("data-policy"))

    assert policy.owner.kind == "participant"
    assert policy.raw_episodes.server_upload == "prohibited"
    assert policy.raw_episodes.training_use == "prohibited"
    assert policy.candidate_skill.public_release == "required_for_climb"
    assert policy.derived_artifacts.uplift_report == "public"
    assert policy.revocation.future_use_revocable is True


def test_account_owned_policy_requires_an_account_reference() -> None:
    with pytest.raises(PydanticValidationError, match="account_ref"):
        DataOwner(kind="account", account_ref=None)


def test_account_owned_policy_accepts_an_account_reference() -> None:
    assert DataOwner(kind="account", account_ref="acct_123").account_ref == "acct_123"


def test_participant_owned_policy_rejects_an_account_reference() -> None:
    with pytest.raises(PydanticValidationError, match="must not name an account_ref"):
        DataOwner(kind="participant", account_ref="acct_123")


def test_shared_ownership_may_name_the_account_that_shares_it() -> None:
    assert DataOwner(kind="shared", account_ref="acct_123").account_ref == "acct_123"


@pytest.mark.parametrize(
    "value",
    ["allowed", "prohibited", "consent_required"],
)
def test_training_use_accepts_every_documented_value(value: str) -> None:
    document = golden("data-policy")
    document["raw_episodes"]["training_use"] = value
    document["raw_episodes"]["local_retention"] = "allowed"

    assert data_policy(document).raw_episodes.training_use == value


def test_training_use_rejects_an_undocumented_value() -> None:
    document = golden("data-policy")
    document["raw_episodes"]["training_use"] = "sometimes"

    with pytest.raises(PydanticValidationError):
        data_policy(document)


def test_policy_cannot_permit_a_use_it_makes_impossible() -> None:
    document = golden("data-policy")
    document["raw_episodes"]["local_retention"] = "prohibited"
    document["raw_episodes"]["training_use"] = "allowed"

    with pytest.raises(PydanticValidationError, match="nothing left to share"):
        data_policy(document)


# ---------------------------------------------------------------------------
# Public Climb contradictions
# ---------------------------------------------------------------------------


def test_development_climb_and_policy_agree() -> None:
    check_climb_policy_consistency(
        climb(golden("climb")), data_policy(golden("data-policy"))
    )


def test_public_candidate_skill_against_a_prohibiting_policy_is_rejected() -> None:
    document = golden("data-policy")
    document["candidate_skill"]["public_release"] = "prohibited"

    with pytest.raises(PolicyError, match="prohibits"):
        check_climb_policy_consistency(climb(golden("climb")), data_policy(document))


def test_private_candidate_skill_against_a_requiring_policy_is_rejected() -> None:
    climb_document = golden("climb")
    climb_document["candidate_policy"]["skill_visibility"] = "private"

    with pytest.raises(PolicyError, match="keeps them private"):
        check_climb_policy_consistency(
            climb(climb_document), data_policy(golden("data-policy"))
        )


def test_public_report_against_a_private_policy_is_rejected() -> None:
    document = golden("data-policy")
    document["derived_artifacts"]["uplift_report"] = "private"

    with pytest.raises(PolicyError, match="uplift report"):
        check_climb_policy_consistency(climb(golden("climb")), data_policy(document))


def test_published_trace_projection_against_a_private_policy_is_rejected() -> None:
    document = golden("data-policy")
    document["derived_artifacts"]["redacted_trace_projection"] = "prohibited"

    with pytest.raises(PolicyError, match="trace projection"):
        check_climb_policy_consistency(climb(golden("climb")), data_policy(document))


def test_policy_error_carries_machine_readable_detail() -> None:
    document = golden("data-policy")
    document["derived_artifacts"]["uplift_report"] = "prohibited"

    with pytest.raises(PolicyError) as caught:
        check_climb_policy_consistency(climb(golden("climb")), data_policy(document))

    assert caught.value.code == "policy_error"
    assert caught.value.details["uplift_report"] == "prohibited"


# ---------------------------------------------------------------------------
# Acceptance is not acknowledgement. Decisions 0003 A5.
# ---------------------------------------------------------------------------


def test_acceptance_requirement_states_what_must_be_accepted() -> None:
    document = golden("data-policy")
    digest = sha256_digest_bytes(json.dumps(document).encode())

    requirement = PolicyAcceptanceRequirement(
        data_policy_digest=digest,
        required=True,
        summary="Episodes stay on this machine. The candidate skill is published.",
    )

    assert requirement.required is True
    assert not hasattr(requirement, "acknowledged_at")
    assert not hasattr(requirement, "method")


def test_acknowledgement_records_who_accepted_and_how() -> None:
    acknowledgement = PolicyAcknowledgement(
        data_policy_digest=OTHER_DIGEST,
        method="explicit_cli_digest",
        acknowledged_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert acknowledgement.method == "explicit_cli_digest"
    assert not hasattr(acknowledgement, "required")


@pytest.mark.parametrize(
    "method",
    ["interactive_cli", "explicit_cli_digest", "host_agent_confirmation"],
)
def test_acknowledgement_accepts_every_documented_method(method: str) -> None:
    acknowledgement = PolicyAcknowledgement(
        data_policy_digest=OTHER_DIGEST,
        method=method,  # type: ignore[arg-type]
        acknowledged_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert acknowledgement.method == method


def test_acknowledgement_rejects_an_invented_method() -> None:
    with pytest.raises(PydanticValidationError):
        PolicyAcknowledgement(
            data_policy_digest=OTHER_DIGEST,
            method="implied_by_confirmation_token",  # type: ignore[arg-type]
            acknowledged_at=datetime(2026, 1, 1, tzinfo=UTC),
        )


def test_acknowledgement_requires_an_aware_timestamp() -> None:
    with pytest.raises(PydanticValidationError, match="timezone-aware"):
        PolicyAcknowledgement(
            data_policy_digest=OTHER_DIGEST,
            method="interactive_cli",
            acknowledged_at=datetime(2026, 1, 1),
        )
