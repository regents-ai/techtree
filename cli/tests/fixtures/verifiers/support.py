"""The Campaign this build ships, executed for real. Spec section 6.18.

This module used to derive a *local* Campaign: the shipped one carried a
``development-placeholder`` subject and no budgets, so a fixture put the real
model and the real spend ceiling on top of it and that overlay was what every
paid run actually executed. The overlay is gone. Decisions document 0025 moved
those values into the product, so the Campaign in the packaged catalog is now
the Campaign the certification measured, and there is nothing left for a
fixture to add.

What remains here is staging, not derivation: a throwaway Techtree home, the
engine on this machine borrowed into it, a draft prepared from a real Skill
directory through the real preparation service against the **packaged**
catalog, and a run started through the real run service. Nothing here builds
the Campaign a paid run executes, so nothing here can quietly execute a
different experiment from the one the build ships.

:func:`with_placeholder_subject` goes the other way, and is the only Campaign
this module constructs: a development fixture, for the tests that are about a
run being *refused* rather than executed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from techtree.canonical import digest_object
from techtree.catalog.repository import EmbeddedCatalogRepository, packaged_catalog_root
from techtree.engines.bundle import default_engine_digest
from techtree.manifests.builder import build_baseline_manifest
from techtree.models.base import Digest
from techtree.models.campaign import (
    SUBJECT_AGENT,
    AgentSpec,
    CampaignSpec,
    ModelSpec,
)
from techtree.models.experiment import ExperimentManifest
from techtree.models.run import RunRequest
from techtree.paths import TechtreePaths, default_paths, paths_from_root
from techtree.runs.artifacts import RunArtifactStore
from techtree.runs.executor import ExecutionContext
from techtree.runs.store import RunStore
from techtree.runs.validation import TasksetValidationProvider

__all__ = [
    "CANDIDATE_SKILL",
    "DEVELOPMENT_CLIMB",
    "SUBJECT_INPUT_USD_PER_MTOK",
    "SUBJECT_MODEL_ID",
    "SUBJECT_OUTPUT_USD_PER_MTOK",
    "ExecutableCampaign",
    "LocalRun",
    "executable_campaign",
    "link_installed_engine",
    "local_run",
    "shipped_campaign",
    "with_placeholder_subject",
]

#: The public reference the shipped catalog carries.
DEVELOPMENT_CLIMB: Final = "hello-world-climb"

#: The candidate Skill the concurrent comparison inserts.
#:
#: The founder-supplied starter Skill does not exist yet and workers must not
#: invent it (decisions document 0005), so this is a *fixture* skill and it is
#: named as one. It exists because a comparison whose candidate teaches nothing
#: measures nothing: the other skill fixtures in this tree are shaped like
#: instruction skills but describe generic tidy-code advice, and a subject
#: given one of those scores exactly what the baseline scores. This one writes
#: BranchCode v1 out as a procedure — the same procedure the reference taskset
#: scores — using only the three inputs the taskset package reserves for
#: documentation and never proves against.
CANDIDATE_SKILL: Final = (
    Path(__file__).resolve().parents[1] / "skills" / "branch-code-v1"
)

#: The Skill the committed recorded evidence was produced with. The evidence
#: under ``fixtures/receipts/recorded`` is one real calibration comparison, and
#: its candidate variant mounted the release's starter Skill, so anything that
#: stages a run over that evidence has to declare the same Skill or the
#: comparison is correctly refused as uncontrolled.
RECORDED_SKILL: Final = (
    Path(__file__).resolve().parents[3]
    / "release"
    / "skills"
    / "hello-world-starter-v1"
)


def shipped_campaign() -> CampaignSpec:
    """Load the Campaign this build ships, exactly as it ships it."""
    repository = EmbeddedCatalogRepository.packaged()
    climb = repository.load_climb(DEVELOPMENT_CLIMB)
    return repository.load_campaign(climb.campaign_spec_digest)


#: The subject model this build ships, and what it costs.
#:
#: The identifier is read from the packaged Campaign rather than restated, so a
#: test that asserts on it is asserting on the released coordinate and cannot
#: quietly go on passing against a second copy of the string. The prices are
#: not in the Campaign — they are facts about the provider's published rate
#: card, read from the Prime models endpoint — and they are used only to report
#: what a run cost.
SUBJECT_MODEL_ID: Final = shipped_campaign().agents[SUBJECT_AGENT].model.model_id
SUBJECT_INPUT_USD_PER_MTOK: Final = 0.03
SUBJECT_OUTPUT_USD_PER_MTOK: Final = 0.13


@dataclass(frozen=True)
class ExecutableCampaign:
    """The shipped Campaign and the baseline manifest built from it."""

    campaign: CampaignSpec
    campaign_digest: Digest
    baseline: ExperimentManifest

    @property
    def task_count(self) -> int:
        """How many tasks the committed membership holds."""
        return len(self.campaign.taskset.membership.ordered_task_hashes)


def executable_campaign() -> ExecutableCampaign:
    """Return the shipped Campaign, with the baseline manifest it produces.

    Nothing is derived. Decisions document 0025 put the subject model, the
    sampling cap, the budget contract and the concurrent schedule into the
    packaged Campaign, so the object loaded here is the object the release
    ships and the experiment a paid run executes is the shipped experiment by
    construction rather than by comparison.
    """
    campaign = shipped_campaign()
    campaign_digest = digest_object(campaign)
    return ExecutableCampaign(
        campaign=campaign,
        campaign_digest=campaign_digest,
        baseline=build_baseline_manifest(
            campaign=campaign,
            campaign_digest=campaign_digest,
            public_context=None,
        ),
    )


def with_placeholder_subject(campaign: CampaignSpec) -> CampaignSpec:
    """Return the same Campaign with a development-placeholder subject model.

    Decisions document 0025 named the subject model in the product, so every
    Campaign built from the shipped generator now routes to a real evaluation
    that provisions containers and spends money. A test about what happens
    *before* any of that — a refusal, a failed precondition, the development
    executor — needs a Campaign that cannot be executed for real, and this is
    how one is made. It is the only Campaign this module builds, and it is
    deliberately the unexecutable kind.
    """
    subject = campaign.agents[SUBJECT_AGENT]
    return CampaignSpec(
        **{
            **dict(campaign),
            "agents": {
                SUBJECT_AGENT: AgentSpec(
                    **{
                        **dict(subject),
                        "model": ModelSpec(
                            provider="development",
                            model_id="development-placeholder",
                            revision=None,
                            credential_env="TECHTREE_MODEL_API_KEY",
                        ),
                    }
                )
            },
        }
    )


@dataclass(frozen=True)
class LocalRun:
    """One created run over the shipped Campaign, inputs staged."""

    paths: TechtreePaths
    run_store: RunStore
    artifacts: RunArtifactStore
    run_id: str
    campaign: CampaignSpec

    @property
    def request(self) -> RunRequest:
        """Return the run's immutable request."""
        return self.run_store.get_request(self.run_id)

    def context(
        self, provider: TasksetValidationProvider | None = None
    ) -> ExecutionContext:
        """Return the context an executor is handed for this run."""
        from techtree.tasksets.provider import worker_validation_provider

        return ExecutionContext(
            request=self.request,
            run_store=self.run_store,
            artifact_store=self.artifacts,
            validation_provider=(
                worker_validation_provider(self.paths) if provider is None else provider
            ),
            clock=_utc_now,
        )


def link_installed_engine(home: Path) -> Path | None:
    """Make the engine installed on this machine visible inside a test home.

    An engine installation is a virtual environment with a pinned Verifiers
    build in it and takes minutes to create, so a test home borrows the real
    one rather than building a second. Only the engine's own directory is
    linked, never the ``engines/`` directory that holds it: everything else a
    run writes has to land inside the temporary home and not in the operator's.

    Returns the link, or ``None`` when nothing is installed to link.
    """
    installed = default_paths().engine_dir(default_engine_digest())
    if not installed.is_dir():
        return None
    engines = paths_from_root(home).engines_dir
    engines.mkdir(parents=True, exist_ok=True)
    link = paths_from_root(home).engine_dir(default_engine_digest())
    if not link.exists():
        link.symlink_to(installed, target_is_directory=True)
    return link


def local_run(
    home: Path,
    *,
    skill_path: Path = CANDIDATE_SKILL,
    candidate_label: str = "branch-code-v1",
) -> LocalRun:
    """Prepare and start one real run of the shipped Campaign.

    Everything a run normally goes through happens here: the packaged catalog
    is read, a draft is prepared from a real skill directory through the real
    preparation service, the run is approved, the policy is acknowledged,
    and the run's inputs are staged and verified. No worker is launched — the
    caller executes in this process, which is what lets an executor's own
    sequence be observed instead of inferred from a run directory afterwards.

    The catalog is the packaged one, not a copy written here. That is the whole
    of decisions document 0025 made operational: the Climb resolved, the
    Campaign executed and the objects committed to are the ones in the wheel.
    """
    from fixtures.drafts.support import preparation_service
    from fixtures.runs.support import RecordingLauncher, utc_now
    from techtree.models.run import PolicyAcknowledgement
    from techtree.runs.service import RunService

    resolved = shipped_campaign()
    paths = paths_from_root(home)
    link_installed_engine(home)

    preparation, drafts = preparation_service(
        paths, catalog_root=packaged_catalog_root()
    )
    prepared = preparation.prepare(
        climb_reference=DEVELOPMENT_CLIMB,
        skill_path=skill_path,
        candidate_label=candidate_label,
    )

    run_store = RunStore(paths)
    artifacts = RunArtifactStore(paths)
    service = RunService(
        paths=paths,
        draft_store=drafts,
        run_store=run_store,
        artifact_store=artifacts,
        launcher=RecordingLauncher(run_store),
        clock=utc_now,
    )
    status = service.start(
        draft_id=prepared.draft.id,
        policy_acknowledgement=PolicyAcknowledgement(
            data_policy_digest=prepared.draft.data_policy_digest,
            method="explicit_cli_review",
            acknowledged_at=utc_now(),
        ),
        approved_by="human_via_cli",
    )
    return LocalRun(
        paths=paths,
        run_store=run_store,
        artifacts=artifacts,
        run_id=status.state.run_id,
        campaign=resolved,
    )


def _utc_now() -> datetime:
    """Return the current instant in UTC."""
    return datetime.now(UTC)


def credential_is_present() -> bool:
    """Whether an evaluation credential can be resolved without reading it."""
    return bool(os.environ.get("PRIME_API_KEY"))
