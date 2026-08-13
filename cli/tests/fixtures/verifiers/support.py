"""A Campaign that can actually be executed, derived locally. Spec section 6.18.

The Campaign this build ships names ``development-placeholder`` as its subject
model, which is deliberate: WP0–WP5 compile and dry-run that Campaign and never
execute it, and
:func:`techtree.doctor.execution_checks.check_live_campaign` refuses to let
anybody execute it by accident.

The real release coordinates are ratified by the founder at WP11h. Until then
the honest way to prove that a real execution works is to derive a *local*
Campaign that carries real coordinates and change nothing else, which is what
this module does. Every field except the subject's model and the run budget
comes from the shipped Campaign, so the taskset reference, the subject image,
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

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from techtree.canonical import (
    canonical_json_bytes,
    digest_object,
    sha256_digest_bytes,
)
from techtree.catalog.repository import EmbeddedCatalogRepository, packaged_catalog_root
from techtree.constants import CATALOG_SCHEMA_VERSION
from techtree.engines.bundle import default_engine_digest
from techtree.manifests.builder import build_baseline_manifest
from techtree.models.base import Digest
from techtree.models.campaign import (
    SUBJECT_AGENT,
    AgentSpec,
    BudgetSpec,
    CampaignSpec,
    ExecutionSpec,
    ModelSpec,
    VariantSchedule,
)
from techtree.models.catalog import (
    CatalogClimbEntry,
    CatalogIndex,
    CatalogObjectLocation,
)
from techtree.models.climb import ClimbManifest
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
    "LOCAL_BUDGET_USD",
    "LOCAL_MAXIMUM_OUTPUT_TOKENS",
    "LOCAL_MAX_CONCURRENT",
    "SUBJECT_INPUT_USD_PER_MTOK",
    "SUBJECT_MODEL_ID",
    "SUBJECT_MODEL_PROVIDER",
    "SUBJECT_OUTPUT_USD_PER_MTOK",
    "LocalCampaign",
    "LocalRun",
    "link_installed_engine",
    "local_campaign",
    "local_catalog",
    "local_run",
    "shipped_campaign",
]

#: The subject model, selected empirically against the Prime models endpoint
#: under decisions document 0006 and revised once against real evidence.
#:
#: WP6b chose the cheapest model that could drive a two-step tool-calling
#: exchange, ``Qwen/Qwen3.5-0.8B``, and its own real run refuted the choice:
#: five of thirty-six rollouts ran to ninety-one turns and one grew its
#: conversation past the provider's limit, producing no reward at all. WP6c
#: measured it again against the thing the Climb actually asks of a subject —
#: read the Skill it was given, then apply it — and it failed that too: on a
#: paid two-task probe it never opened the Skill, invented ``BRANCH-ALDER``
#: shaped answers, and scored zero with the Skill exactly as it scored zero
#: without one. A subject that cannot read a Skill cannot demonstrate Skill
#: transfer, so there was nothing for the Campaign to measure.
#:
#: The next rung of the ladder decisions document 0006 and the WP6b ticket
#: both name is ``qwen/qwen3.7-flash``, and it is *cheaper* on the axis that
#: dominates an agentic run: 0.03 against 0.04 USD per million input tokens,
#: and an agentic rollout is overwhelmingly input. On the same two-task probe
#: it scored 2/2 with the Skill and 0/3 without it. It also reports no cached
#: input tokens at all, which retires WP6b's open question about how a cached
#: read is billed — for this model every prompt token is priced once, at the
#: published rate, so a run's cost is a number rather than a range.
#:
#: Provisional until the founder ratifies the release coordinates at WP11h.
SUBJECT_MODEL_PROVIDER: Final = "prime"
SUBJECT_MODEL_ID: Final = "qwen/qwen3.7-flash"

#: What the selected model costs, in USD per million tokens, read from the
#: Prime models endpoint. Used only to report what a run cost.
SUBJECT_INPUT_USD_PER_MTOK: Final = 0.03
SUBJECT_OUTPUT_USD_PER_MTOK: Final = 0.13

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

#: The Campaign-wide episode allowance a concurrent comparison is given, and
#: the reference figure spec section 3.2 states for the live Campaign. The
#: executor halves it, so each variant runs two rollouts at a time and four
#: subject containers exist at once. The shipped Campaign declares one, which
#: a parallel schedule cannot divide: one variant would be starved to zero.
LOCAL_MAX_CONCURRENT: Final = 4

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

_CAMPAIGN_PATH: Final = "campaigns/hello-world-climb.json"
_CLIMB_PATH: Final = "climbs/hello-world-climb.json"
_CATALOG_INDEX: Final = "catalog.json"
_JSON_MEDIA_TYPE: Final = "application/json"

#: The catalog objects a locally derived Campaign reuses byte for byte. None of
#: them changes when the subject's model, image, budget or schedule does.
_UNCHANGED_OBJECTS: Final[tuple[tuple[str, str], ...]] = (
    ("data-policies/hello-world-climb.json", "data_policy"),
    ("taskset-validations/hello-world-climb.json", "taskset_validation"),
    ("validation-evidence/hello-world-climb.json", "validation_evidence"),
)


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
    climb = repository.load_climb(DEVELOPMENT_CLIMB)
    return repository.load_campaign(climb.campaign_spec_digest)


def local_campaign(
    *, schedule: VariantSchedule = VariantSchedule.PARALLEL
) -> LocalCampaign:
    """Derive a locally executable Campaign from the one this build ships.

    Three things change and nothing else does. Two are named in decisions
    document 0006 — the subject's model and the spend ceiling — and the third is
    the execution schedule, because the shipped Campaign runs its variants one
    after the other and WP6c is about running them side by side.

    The subject's runtime is *not* one of them any more. Decisions document 0007
    R5 pins the container in the shipped Campaign itself, by content and per
    platform, so a locally executable Campaign inherits the real pin and a real
    run exercises the image the release ships rather than whatever this machine
    happened to have pulled. The taskset reference, the thirty-six committed
    task hashes, the membership digest, the mutation contract, the scoring rule
    and the data-policy digest are all the shipped Campaign's too, so what gets
    executed is the shipped experiment.
    """
    shipped = shipped_campaign()
    subject = shipped.agents[SUBJECT_AGENT]

    # Constructed rather than copied. ``model_copy`` does not re-run a model's
    # validators, and a locally derived Campaign that skipped them would not be
    # the same kind of object the shipped one is.
    executable_subject = AgentSpec(
        **{
            **dict(subject),
            "model": ModelSpec(
                provider=SUBJECT_MODEL_PROVIDER,
                model_id=SUBJECT_MODEL_ID,
                revision=None,
                credential_env="PRIME_API_KEY",
            ),
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
            "execution": ExecutionSpec(
                order=schedule,
                max_concurrent=(
                    LOCAL_MAX_CONCURRENT
                    if schedule is VariantSchedule.PARALLEL
                    else shipped.execution.max_concurrent
                ),
                timeout_seconds=shipped.execution.timeout_seconds,
                retry_limit=shipped.execution.retry_limit,
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


def local_catalog(destination: Path, campaign: CampaignSpec) -> Path:
    """Write a catalog that offers the locally derived Campaign, and nothing else.

    The shipped catalog is not edited and not regenerated. Three of its five
    objects — the DataPolicy, the publisher's taskset validation receipt and
    the normalized evidence it was issued from — are copied across byte for
    byte, because none of them depends on which model the subject is or how its
    variants are scheduled. Only the Campaign is replaced, and the Climb is
    rewritten to point at the new Campaign's digest.

    The result is a catalog a real draft can be prepared against, which is what
    lets the whole run lifecycle — prepare, start, stage, execute — be exercised
    against real subject coordinates instead of stopping at the executor's
    front door.
    """
    root = packaged_catalog_root()
    destination.mkdir(parents=True, exist_ok=True)

    campaign_digest = digest_object(campaign)
    shipped_climb = ClimbManifest.model_validate_json(
        (root / _CLIMB_PATH).read_text(encoding="utf-8")
    )
    climb = ClimbManifest(
        **{**dict(shipped_climb), "campaign_spec_digest": campaign_digest}
    )

    objects: dict[Digest, CatalogObjectLocation] = {
        campaign_digest: CatalogObjectLocation(
            kind="campaign", path=_CAMPAIGN_PATH, media_type=_JSON_MEDIA_TYPE
        )
    }
    _write_json(destination / _CAMPAIGN_PATH, canonical_json_bytes(campaign))
    _write_json(destination / _CLIMB_PATH, canonical_json_bytes(climb))

    for path, kind in _UNCHANGED_OBJECTS:
        raw = (root / path).read_bytes()
        _write_json(destination / path, raw)
        digest = sha256_digest_bytes(canonical_json_bytes(json.loads(raw)))
        objects[digest] = CatalogObjectLocation(
            kind=kind,  # type: ignore[arg-type]
            path=path,
            media_type=_JSON_MEDIA_TYPE,
        )

    index = CatalogIndex(
        schema_version=CATALOG_SCHEMA_VERSION,
        climbs=[
            CatalogClimbEntry(
                reference=(f"{climb.metadata.slug}@{climb.metadata.version}"),
                digest=digest_object(climb),
                path=_CLIMB_PATH,
            )
        ],
        objects=objects,
    )
    _write_json(destination / _CATALOG_INDEX, canonical_json_bytes(index))
    return destination


def _write_json(path: Path, data: bytes) -> None:
    """Write one catalog file, creating the directory it belongs in."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


@dataclass(frozen=True)
class LocalRun:
    """One created run over the locally derived Campaign, inputs staged."""

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
    campaign: CampaignSpec | None = None,
) -> LocalRun:
    """Prepare and start one real run of the locally derived Campaign.

    Everything a run normally goes through happens here: a catalog is written,
    a draft is prepared from a real skill directory through the real
    preparation service, the draft is confirmed, the policy is acknowledged,
    and the run's inputs are staged and verified. No worker is launched — the
    caller executes in this process, which is what lets an executor's own
    sequence be observed instead of inferred from a run directory afterwards.
    """
    from fixtures.drafts.support import preparation_service
    from fixtures.runs.support import RecordingLauncher, utc_now
    from techtree.drafts.confirmation import ConfirmationService
    from techtree.models.run import PolicyAcknowledgement
    from techtree.runs.service import RunService

    resolved = campaign or local_campaign().campaign
    paths = paths_from_root(home)
    link_installed_engine(home)
    catalog = local_catalog(home / "local-catalog", resolved)

    confirmations = ConfirmationService()
    preparation, drafts = preparation_service(
        paths, catalog_root=catalog, confirmation=confirmations
    )
    prepared = preparation.prepare(
        climb_reference=DEVELOPMENT_CLIMB,
        skill_path=skill_path,
        candidate_label="branch-code-v1",
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
        confirmation_token=prepared.confirmation_token,
        policy_acknowledgement=PolicyAcknowledgement(
            data_policy_digest=prepared.draft.data_policy_digest,
            method="explicit_cli_digest",
            acknowledged_at=utc_now(),
        ),
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
