"""Rights and permitted future uses of Campaign artifacts. Spec section 11.4.

A ``DataPolicy`` is required before any episode exists, because rights cannot
be retrofitted honestly. Once a participant has run a comparison, asking them
afterwards whether the transcripts may be used for training is asking a
question whose answer was already assumed.

The policy is a plain statement of permissions. It is immutable by digest:
changing any permission produces a different policy, which produces a
different ``CampaignSpec``, which is exactly the visibility the rule exists to
create. Nothing here grants Techtree the ability to do anything — WP0–WP5
upload no artifact regardless of what a policy allows.

Contradiction checks between a public Climb and its policy live in
:mod:`techtree.models.climb`, where both objects are in scope.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from techtree.models.base import NonEmptyString, ProtocolModel

__all__ = [
    "CandidateSkillPolicy",
    "DataOwner",
    "DataPolicy",
    "DerivedArtifactPolicy",
    "RawEpisodePolicy",
    "RevocationPolicy",
]


type Permission = Literal["allowed", "prohibited", "consent_required"]
"""Whether a use is permitted outright, forbidden, or gated on fresh consent."""

type Visibility = Literal["public", "private", "prohibited"]
"""Whether a derived artifact may be published, kept, or not produced at all."""


class DataOwner(ProtocolModel):
    """Who owns the artifacts a Campaign produces."""

    kind: Literal["participant", "account", "shared"]
    account_ref: NonEmptyString | None = None

    @model_validator(mode="after")
    def _check_account_reference_matches_ownership(self) -> Self:
        """Require an account reference exactly where ownership implies one."""
        if self.kind == "account" and self.account_ref is None:
            raise ValueError("account-owned data must name the owning account_ref")
        if self.kind == "participant" and self.account_ref is not None:
            raise ValueError(
                "participant-owned data must not name an account_ref; use the "
                "shared owner kind when an account also holds rights"
            )
        return self


class RawEpisodePolicy(ProtocolModel):
    """What may happen to raw episode transcripts."""

    local_retention: Literal["allowed", "prohibited", "required"]
    server_upload: Permission
    public_release: Permission
    reproduction_access: Permission
    training_use: Permission


class DerivedArtifactPolicy(ProtocolModel):
    """What may happen to everything computed from the episodes."""

    aggregate_scores: Visibility
    uplift_report: Visibility
    redacted_trace_projection: Visibility
    anonymized_product_analytics: Permission


class CandidateSkillPolicy(ProtocolModel):
    """Who owns the submitted skill and whether it can be published."""

    ownership: Literal["participant", "account", "shared"]
    public_release: Literal[
        "required_for_climb",
        "allowed",
        "prohibited",
        "consent_required",
    ]
    training_use: Permission


class RevocationPolicy(ProtocolModel):
    """What a participant can withdraw later, and what stays published."""

    future_use_revocable: bool
    immutable_published_proofs_remain: bool


class DataPolicy(ProtocolModel):
    """The complete rights statement a Campaign runs under."""

    schema_version: Literal["techtree.data-policy.v1alpha1"]
    id: NonEmptyString
    version: int = Field(ge=1)
    owner: DataOwner
    raw_episodes: RawEpisodePolicy
    derived_artifacts: DerivedArtifactPolicy
    candidate_skill: CandidateSkillPolicy
    revocation: RevocationPolicy

    @model_validator(mode="after")
    def _check_internal_consistency(self) -> Self:
        """Reject a policy that permits a use it also makes impossible."""
        if self.raw_episodes.local_retention == "prohibited":
            for name in (
                "server_upload",
                "public_release",
                "reproduction_access",
                "training_use",
            ):
                if getattr(self.raw_episodes, name) != "prohibited":
                    raise ValueError(
                        f"raw_episodes.{name} cannot be permitted while "
                        "local_retention is prohibited; there would be nothing "
                        "left to share"
                    )
        return self
