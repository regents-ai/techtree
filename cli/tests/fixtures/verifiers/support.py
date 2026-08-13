"""A Campaign that can actually be executed, derived locally. Spec section 6.18.

The Campaign this build ships names ``development-placeholder`` as its model and
``techtree-development-placeholder:not-executed`` as its subject image. Both are
deliberate: WP0–WP5 compile and dry-run that Campaign and never execute it, and
:func:`techtree.doctor.execution_checks.check_live_campaign` refuses to let
anybody execute it by accident.

The real release coordinates are ratified by the founder at WP11h. Until then
the honest way to prove that a real execution works is to derive a *local*
Campaign that carries real coordinates and change nothing else, which is what
this module does. Every field except the subject's model, the subject's image
and the run budget comes from the shipped Campaign, so the taskset reference,
the committed membership, the mutation contract, the scoring rule and the data
policy digest are the shipped ones and the experiment being executed is the
shipped experiment.

The derivation goes through :class:`~techtree.models.campaign.CampaignSpec`
itself and the manifests go through :mod:`techtree.manifests.builder`, so the
local Campaign is validated by exactly the rules the shipped one is. Nothing
here writes to the packaged catalog, and nothing here is a second definition of
what a Campaign is.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Final

from techtree.canonical import digest_object
from techtree.catalog.repository import EmbeddedCatalogRepository
from techtree.manifests.builder import build_baseline_manifest
from techtree.models.base import Digest
from techtree.models.campaign import (
    SUBJECT_AGENT,
    AgentSpec,
    BudgetSpec,
    CampaignSpec,
    ModelSpec,
    RuntimeSpec,
)
from techtree.models.experiment import ExperimentManifest

__all__ = [
    "LOCAL_BUDGET_USD",
    "LOCAL_MAXIMUM_OUTPUT_TOKENS",
    "SUBJECT_IMAGE_REPOSITORY",
    "SUBJECT_MODEL_ID",
    "SUBJECT_MODEL_PROVIDER",
    "LocalCampaign",
    "local_campaign",
    "resolve_subject_image",
    "shipped_campaign",
]

#: The subject model WP6b selected empirically against the Prime models
#: endpoint: the cheapest of the candidates that could drive a two-step
#: tool-calling exchange. Provisional until WP11h; see decisions document 0006
#: and the ticket note that records the enumeration and the pricing.
SUBJECT_MODEL_PROVIDER: Final = "prime"
SUBJECT_MODEL_ID: Final = "Qwen/Qwen3.5-0.8B"

#: The subject container. Hermes Agent is installed into it at setup time from
#: a PEP 723 script, so the image needs a shell, ``pip`` and nothing else; the
#: agent's own interpreter is provisioned by ``uv`` inside the container.
SUBJECT_IMAGE_REPOSITORY: Final = "python"
SUBJECT_IMAGE_TAG: Final = "3.11-slim"

#: The per-run ceiling decisions document 0006 fixes. A hard cap, not a target.
LOCAL_BUDGET_USD: Final = 1.00

#: A per-rollout output-token ceiling, and the reason a Campaign needs one.
#:
#: The first real WP6b run left this unset and watched a small subject loop.
#: BranchCode cannot be recovered from its prompt, so an agent that will not
#: give up keeps taking turns; five of thirty-six rollouts ran to ninety-one
#: turns, and one grew a conversation past the model's context until the
#: provider refused it outright. That rollout produced no reward at all, which
#: fails the whole variant under spec section 6.17 — one runaway subject can
#: cost a Campaign its result.
#:
#: The cap is on *output* tokens on purpose. Verifiers' input counter measures
#: only tokens new to the conversation, so an input cap does not bound what a
#: provider bills for a prompt re-sent every turn. Output is counted once and
#: grows with exactly the thing that runs away: turns taken. A correct answer
#: needs a few hundred; the loops produced fifteen thousand and up.
#:
#: It is a budget, applied identically to both variants, so it constrains the
#: experiment without favouring either side of it. Provisional, like every
#: other coordinate here, until WP11h.
LOCAL_MAXIMUM_OUTPUT_TOKENS: Final = 8000

#: The public reference the shipped catalog carries.
_DEVELOPMENT_CLIMB: Final = "procedure-transfer-dev"


@dataclass(frozen=True)
class LocalCampaign:
    """A locally executable Campaign and the baseline manifest derived from it."""

    campaign: CampaignSpec
    campaign_digest: Digest
    baseline: ExperimentManifest

    @property
    def task_count(self) -> int:
        """How many tasks the committed membership holds."""
        return len(self.campaign.taskset.membership.ordered_task_hashes)


def shipped_campaign() -> CampaignSpec:
    """Load the Campaign this build ships, exactly as it ships it."""
    repository = EmbeddedCatalogRepository.packaged()
    climb = repository.load_climb(_DEVELOPMENT_CLIMB)
    return repository.load_campaign(climb.campaign_spec_digest)


def resolve_subject_image() -> str:
    """Return the subject image pinned by the digest Docker holds locally.

    A tag is a moving target and a Campaign that named one could not claim two
    variants ran on the same thing. The digest is read from the local daemon
    rather than written down, so this fixture describes the image that is
    actually present rather than one somebody hoped was.
    """
    reference = f"{SUBJECT_IMAGE_REPOSITORY}:{SUBJECT_IMAGE_TAG}"
    completed = subprocess.run(
        [
            "docker",
            "image",
            "inspect",
            reference,
            "--format",
            "{{index .RepoDigests 0}}",
        ],
        capture_output=True,
        text=True,
        check=False,
        stdin=subprocess.DEVNULL,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise RuntimeError(
            f"{reference} is not present locally; run `docker pull {reference}` "
            "before deriving a locally executable Campaign"
        )
    return completed.stdout.strip()


def local_campaign(*, image: str | None = None) -> LocalCampaign:
    """Derive a locally executable Campaign from the one this build ships.

    Exactly three things change, and each is named in decisions document 0006:
    the subject's model, the subject's runtime image, and the spend ceiling.
    """
    shipped = shipped_campaign()
    subject = shipped.agents[SUBJECT_AGENT]

    # Constructed rather than copied. ``model_copy`` does not re-run a model's
    # validators, and a locally derived Campaign that skipped them would not be
    # the same kind of object the shipped one is.
    runtime = RuntimeSpec(
        **{**dict(subject.runtime), "image": image or resolve_subject_image()}
    )
    executable_subject = AgentSpec(
        **{
            **dict(subject),
            "model": ModelSpec(
                provider=SUBJECT_MODEL_PROVIDER,
                model_id=SUBJECT_MODEL_ID,
                revision=None,
                credential_env="PRIME_API_KEY",
            ),
            "runtime": runtime,
        }
    )
    campaign = CampaignSpec(
        **{
            **dict(shipped),
            "agents": {SUBJECT_AGENT: executable_subject},
            "budgets": BudgetSpec(
                maximum_input_tokens=None,
                maximum_output_tokens=LOCAL_MAXIMUM_OUTPUT_TOKENS,
                maximum_model_calls=None,
                maximum_usd=LOCAL_BUDGET_USD,
            ),
        }
    )
    campaign_digest = digest_object(campaign)

    return LocalCampaign(
        campaign=campaign,
        campaign_digest=campaign_digest,
        baseline=build_baseline_manifest(
            campaign=campaign,
            campaign_digest=campaign_digest,
            public_context=None,
        ),
    )


def credential_is_present() -> bool:
    """Whether an evaluation credential can be resolved without reading it."""
    return bool(os.environ.get("PRIME_API_KEY"))
