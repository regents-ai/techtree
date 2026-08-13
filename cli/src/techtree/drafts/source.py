"""What a draft is prepared against, with or without a public Climb.

Every draft this build produced before WP7d came from a
:class:`~techtree.models.climb.ResolvedClimb`: a public invitation wrapping a
Campaign. Spec section 7.19 asks for one that does not. A Skill-replacement
Campaign is derived locally from a run that already finished, and no Climb
wraps it — :class:`~techtree.models.climb.CandidatePolicy` can only require
``skill_insertion``, so a ``ResolvedClimb`` holding a replacement Campaign is
unrepresentable rather than merely unusual.

:class:`CampaignSource` is what the kernel carries instead. It holds the three
objects a run's science actually needs — the Campaign, the DataPolicy it runs
under, and the publisher's taskset validation receipt — and the public Climb
beside them when there is one. Preparation, the draft store, the run's staged
inputs, and the report stage all read it, so a local replacement travels the
same path as a public submission rather than a parallel one.

Two properties are deliberate.

*The Climb's own edge checks stay in one place.* When a source comes from a
Climb it comes through :meth:`CampaignSource.from_climb`, which takes an
already-validated ``ResolvedClimb``; when it is read back from disk the Climb
is reassembled into a ``ResolvedClimb`` first, so its validator runs on the
bytes. Nothing here re-implements those checks, and a Climb-free source is not
given a weaker version of them: it has no Climb to check.

*A source is a container, not an authority.* The Campaign-to-DataPolicy and
Campaign-to-receipt edges are verified where the bytes are — in
:meth:`~techtree.drafts.store.DraftStore.verify_snapshot` and in
:class:`~techtree.runs.artifacts.RunArtifactStore` — because those are the
places that know which digest a *request* said to expect.

:class:`StagedSkill` is the other half of the same generalization. An insertion
stages one Skill, the candidate's. A replacement stages two, because the
baseline variant carries the Skill being revised and the subject has to be
given its files, not just its digest.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from techtree.canonical import digest_object
from techtree.models.base import Digest
from techtree.models.campaign import CampaignSpec, MutationKind, PublicContext
from techtree.models.climb import ClimbManifest, ResolvedClimb
from techtree.models.data_policy import DataPolicy
from techtree.models.skill import SkillArtifact
from techtree.models.validation import TasksetValidationReceipt

__all__ = ["CampaignSource", "StagedSkill"]


@dataclass(frozen=True)
class StagedSkill:
    """One Skill as a draft or a run owns it: the artifact and its bytes."""

    artifact: SkillArtifact
    archive: Path
    files: Path


@dataclass(frozen=True)
class CampaignSource:
    """The Campaign graph a draft is prepared against.

    ``climb`` and ``climb_digest`` are present together or absent together: a
    Climb-free source is a local Campaign, which spec section 7.19 derives for
    a Skill replacement and which no public invitation wraps.
    """

    campaign: CampaignSpec
    campaign_digest: Digest
    data_policy: DataPolicy
    data_policy_digest: Digest
    publisher_validation: TasksetValidationReceipt
    publisher_validation_digest: Digest
    climb: ClimbManifest | None
    climb_digest: Digest | None

    def __post_init__(self) -> None:
        """Reject a half-present Climb, which no reader could interpret."""
        if (self.climb is None) != (self.climb_digest is None):
            raise ValueError(
                "a campaign source names a public Climb and the digest it was "
                "loaded under together, or neither"
            )

    @classmethod
    def from_climb(cls, resolved: ResolvedClimb) -> CampaignSource:
        """Return the source one resolved public Climb describes."""
        return cls(
            campaign=resolved.campaign,
            campaign_digest=resolved.campaign_digest,
            data_policy=resolved.data_policy,
            data_policy_digest=resolved.data_policy_digest,
            publisher_validation=resolved.publisher_validation,
            publisher_validation_digest=resolved.publisher_validation_digest,
            climb=resolved.climb,
            climb_digest=resolved.climb_digest,
        )

    @classmethod
    def local(
        cls,
        *,
        campaign: CampaignSpec,
        data_policy: DataPolicy,
        publisher_validation: TasksetValidationReceipt,
    ) -> CampaignSource:
        """Return a source for a locally derived Campaign that no Climb wraps."""
        return cls(
            campaign=campaign,
            campaign_digest=digest_object(campaign),
            data_policy=data_policy,
            data_policy_digest=digest_object(data_policy),
            publisher_validation=publisher_validation,
            publisher_validation_digest=digest_object(publisher_validation),
            climb=None,
            climb_digest=None,
        )

    @property
    def public_context(self) -> PublicContext | None:
        """Return the public context artifacts built from this source carry."""
        if self.climb_digest is None:
            return None
        return PublicContext(kind="climb", climb_digest=self.climb_digest)

    @property
    def title(self) -> str:
        """Return what to call this comparison in a result a person reads.

        A public Climb has a title written for readers. A locally derived
        Campaign has only its own identity, and saying so is better than
        inventing a name for it.
        """
        if self.climb is not None:
            return self.climb.metadata.title
        return f"{self.campaign.metadata.id} v{self.campaign.metadata.version}"

    @property
    def replaces_a_skill(self) -> bool:
        """Return whether this Campaign's baseline carries the Skill being revised."""
        return self.campaign.mutation_contract.kind is MutationKind.SKILL_REPLACEMENT
