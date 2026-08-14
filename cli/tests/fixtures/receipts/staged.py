"""A run whose evaluation already happened, staged from recorded evidence.

``fixtures.receipts.pair`` joins the two paid probes into one controlled
comparison. This module puts that comparison inside a *run*: a real catalog, a
real draft prepared from the real ``branch-code-v1`` Skill directory, a real
run created and staged through the run service, and the probes' own evidence
laid out exactly where a finished evaluation would have left it.

What that makes testable is the last thing WP6 could not do: a run reaching
``completed`` with a real report in it. Nothing here starts a container, calls a
provider, or spends anything — the expensive half already happened, on
2026-08-13, and its output is committed under ``recorded/``.

Two things are re-issued and both are named where they are built.

*The publisher's validation documents.* The shipped receipt and evidence
validate thirty-six tasks and this comparison covers the two both probes
scored, so the lock, the normalized evidence and the receipt are re-issued over
those two — from the shipped documents' own method, engine digest and per-task
verdicts, with the two tasks' records kept verbatim. The catalog service checks
the whole chain when the draft is prepared, and the publisher-fixture validation
provider re-derives the lock and requires it to reproduce the receipt's digest,
so the re-issued graph is verified rather than asserted.

*The child process envelope.* Each probe's ``ChildProcessOutcome`` is the
operational record ``fixtures.receipts.support`` reconstructed from the child's
own capture files. It says when a process ran, not what it measured.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from fixtures.receipts.pair import RecordedPair, recorded_pair, trimmed_campaign
from fixtures.receipts.support import (
    NORMALIZED_EPISODES_FILE,
    RESOLVED_CONFIG_FILE,
    recorded_root,
)
from techtree.canonical import canonical_json_bytes, digest_object
from techtree.catalog.repository import EmbeddedCatalogRepository, packaged_catalog_root
from techtree.constants import CATALOG_SCHEMA_VERSION, TASKSET_LOCK_SCHEMA_VERSION
from techtree.models.base import ArtifactRef, Digest
from techtree.models.campaign import CampaignSpec, CampaignTaskset
from techtree.models.catalog import (
    CatalogClimbEntry,
    CatalogIndex,
    CatalogObjectLocation,
)
from techtree.models.climb import ClimbManifest
from techtree.models.run import RunPhase
from techtree.models.validation import (
    TasksetLock,
    TasksetValidationReceipt,
    UpstreamValidationSummary,
    ValidationCheck,
    ValidationEvidence,
    ValidationEvidenceSummary,
)
from techtree.paths import TechtreePaths, paths_from_root
from techtree.runs.artifacts import RunArtifactStore
from techtree.runs.executor import ExecutionContext
from techtree.runs.real import TASKSET_LOCK_FILENAME
from techtree.runs.store import RunStore
from techtree.verifiers.models import (
    RealExecutionResult,
    RunPaths,
    VariantName,
)

__all__ = [
    "RecordedEvidenceExecutor",
    "StagedRecordedRun",
    "recorded_catalog",
    "staged_recorded_run",
]

#: The public reference the shipped catalog carries, reused so that the draft
#: is prepared through the same Climb the probes were run under.
_CLIMB_REFERENCE: Final = "hello-world-climb"

_CAMPAIGN_PATH: Final = "campaigns/hello-world-climb.json"
_CLIMB_PATH: Final = "climbs/hello-world-climb.json"
_DATA_POLICY_PATH: Final = "data-policies/hello-world-climb.json"
_RECEIPT_PATH: Final = "taskset-validations/hello-world-climb.json"
_EVIDENCE_PATH: Final = "validation-evidence/hello-world-climb.json"
_CATALOG_INDEX: Final = "catalog.json"
_JSON_MEDIA_TYPE: Final = "application/json"


@dataclass(frozen=True)
class StagedRecordedRun:
    """One created run over the recorded comparison, with its inputs staged."""

    paths: TechtreePaths
    run_store: RunStore
    artifacts: RunArtifactStore
    run_id: str
    campaign: CampaignSpec
    pair: RecordedPair


def recorded_catalog(destination: Path) -> tuple[Path, CampaignSpec]:
    """Write a catalog offering the recorded comparison's Campaign.

    The DataPolicy is the shipped one, byte for byte. The Campaign is the
    locally derived one narrowed to the two tasks both probes scored, and the
    publisher's lock, evidence and receipt are re-issued over the same two.
    """
    repository = EmbeddedCatalogRepository.packaged()
    shipped_climb = repository.load_climb(_CLIMB_REFERENCE)
    shipped_campaign = repository.load_campaign(shipped_climb.campaign_spec_digest)
    shipped_receipt = repository.load_validation_receipt(
        shipped_campaign.taskset.validation_receipt_digest
    )
    reference = shipped_receipt.normalized_evidence
    assert reference is not None, "the shipped receipt names its normalized evidence"
    shipped_evidence = repository.load_validation_evidence(reference.digest)

    narrowed = trimmed_campaign()
    committed = list(narrowed.taskset.membership.ordered_task_hashes)
    lock = _reissued_lock(narrowed, shipped_receipt.engine_digest)
    evidence = _reissued_evidence(shipped_evidence, lock)
    receipt = _reissued_receipt(shipped_receipt, lock, evidence)

    campaign = CampaignSpec(
        **{
            **dict(narrowed),
            "taskset": CampaignTaskset(
                **{
                    **dict(narrowed.taskset),
                    "validation_receipt_digest": digest_object(receipt),
                }
            ),
        }
    )
    campaign_digest = digest_object(campaign)
    climb = ClimbManifest(
        **{**dict(shipped_climb), "campaign_spec_digest": campaign_digest}
    )

    destination.mkdir(parents=True, exist_ok=True)
    _write(destination / _CAMPAIGN_PATH, canonical_json_bytes(campaign))
    _write(destination / _CLIMB_PATH, canonical_json_bytes(climb))
    _write(destination / _RECEIPT_PATH, canonical_json_bytes(receipt))
    _write(destination / _EVIDENCE_PATH, canonical_json_bytes(evidence))

    data_policy = (packaged_catalog_root() / _DATA_POLICY_PATH).read_bytes()
    _write(destination / _DATA_POLICY_PATH, data_policy)
    policy_digest = digest_object(json.loads(data_policy))

    index = CatalogIndex(
        schema_version=CATALOG_SCHEMA_VERSION,
        climbs=[
            CatalogClimbEntry(
                reference=f"{climb.metadata.slug}@{climb.metadata.version}",
                digest=digest_object(climb),
                path=_CLIMB_PATH,
            )
        ],
        objects={
            campaign_digest: _location("campaign", _CAMPAIGN_PATH),
            policy_digest: _location("data_policy", _DATA_POLICY_PATH),
            digest_object(receipt): _location("taskset_validation", _RECEIPT_PATH),
            digest_object(evidence): _location("validation_evidence", _EVIDENCE_PATH),
        },
    )
    _write(destination / _CATALOG_INDEX, canonical_json_bytes(index))
    assert len(committed) == receipt.upstream_summary.total
    return destination, campaign


def staged_recorded_run(home: Path) -> StagedRecordedRun:
    """Prepare, start and stage one run of the recorded comparison.

    Everything a run normally goes through happens: the catalog is read, a
    draft is prepared from the real Skill directory through the real
    preparation service, the run is approved, the DataPolicy is
    acknowledged, and the run's inputs are staged and verified against its own
    request. No worker is launched; the caller drives the worker entry point in
    this process.
    """
    from fixtures.drafts.support import preparation_service
    from fixtures.runs.support import RecordingLauncher, utc_now
    from fixtures.verifiers.support import RECORDED_SKILL
    from techtree.models.run import PolicyAcknowledgement
    from techtree.runs.service import RunService

    paths = paths_from_root(home)
    catalog, campaign = recorded_catalog(home / "recorded-catalog")

    preparation, drafts = preparation_service(paths, catalog_root=catalog)
    prepared = preparation.prepare(
        climb_reference=_CLIMB_REFERENCE,
        skill_path=RECORDED_SKILL,
        candidate_label="hello-world-v1",
    )

    run_store = RunStore(paths)
    artifacts = RunArtifactStore(paths)
    status = RunService(
        paths=paths,
        draft_store=drafts,
        run_store=run_store,
        artifact_store=artifacts,
        launcher=RecordingLauncher(run_store),
        clock=utc_now,
    ).start(
        draft_id=prepared.draft.id,
        policy_acknowledgement=PolicyAcknowledgement(
            data_policy_digest=prepared.draft.data_policy_digest,
            method="explicit_cli_review",
            acknowledged_at=utc_now(),
        ),
        approved_by="human_via_cli",
    )

    run_id = status.state.run_id
    request = run_store.get_request(run_id)
    inputs = artifacts.load_inputs(run_id, request)
    return StagedRecordedRun(
        paths=paths,
        run_store=run_store,
        artifacts=artifacts,
        run_id=run_id,
        campaign=campaign,
        pair=recorded_pair(
            campaign=campaign,
            baseline_manifest=inputs.baseline,
            candidate_manifest=inputs.candidate,
            request=request,
        ),
    )


class RecordedEvidenceExecutor:
    """Lays the recorded probes' evidence out where an evaluation would have.

    It walks the same phases the real executor walks and performs the same two
    acts the report stage depends on — the taskset is validated through the
    run's own provider, and the validated lock is written into the run's inputs
    — and then, instead of starting two children, copies the evidence those
    children already produced. What it returns is exactly what
    :class:`~techtree.runs.real.RealVerifiersExecutor` returns.
    """

    def __init__(self, *, pair: RecordedPair, paths: TechtreePaths) -> None:
        self._pair = pair
        self._paths = paths

    def execute(self, context: ExecutionContext) -> RealExecutionResult:
        """Validate, lay out the recorded evidence, and hand back the result."""
        run_id = context.request.run_id
        run_paths = RunPaths.for_run(self._paths, run_id)
        inputs = context.artifact_store.load_inputs(run_id, context.request)

        context.run_store.append(run_id, phase=RunPhase.VALIDATING_TASKSET)
        validation = context.validation_provider.validate(run_id=run_id, inputs=inputs)
        context.artifact_store.write_validation_marker(
            run_id, validation.marker_document()
        )
        lock_path = run_paths.inputs_dir / TASKSET_LOCK_FILENAME
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_bytes(validation.lock.model_dump_json().encode("utf-8"))

        context.run_store.append(run_id, phase=RunPhase.RUNNING_VARIANTS)
        for variant in (VariantName.BASELINE, VariantName.CANDIDATE):
            output = run_paths.variant_output_dir(variant)
            output.mkdir(parents=True, exist_ok=True)
            for name in (NORMALIZED_EPISODES_FILE, RESOLVED_CONFIG_FILE):
                shutil.copyfile(recorded_root() / variant.value / name, output / name)

        return RealExecutionResult(
            execution_backend="verifiers",
            engine_digest=validation.lock.engine_digest,
            verifiers_revision=validation.receipt.method.validator_revision,
            schedule=self._pair.campaign.execution.order,
            baseline=self._pair.results[VariantName.BASELINE],
            candidate=self._pair.results[VariantName.CANDIDATE],
        )


# ---------------------------------------------------------------------------
# Re-issuing the publisher's documents over the two shared tasks
# ---------------------------------------------------------------------------


def _reissued_lock(campaign: CampaignSpec, engine_digest: Digest) -> TasksetLock:
    """Return the lock ``derive_taskset_lock`` will rebuild from this Campaign."""
    committed = list(campaign.taskset.membership.ordered_task_hashes)
    return TasksetLock(
        schema_version=TASKSET_LOCK_SCHEMA_VERSION,
        taskset_ref=campaign.taskset.ref,
        engine_digest=engine_digest,
        resolved_package_digest=campaign.taskset.ref.package.digest,
        ordered_task_hashes=committed,
        membership_digest=campaign.taskset.membership.membership_digest,
        task_count=len(committed),
    )


def _reissued_evidence(
    shipped: ValidationEvidence, lock: TasksetLock
) -> ValidationEvidence:
    """Keep the shipped per-task verdicts for the tasks this lock commits to."""
    committed = list(lock.ordered_task_hashes)
    by_task = {task.task_hash: task for task in shipped.tasks}
    kept = [
        by_task[task_hash].model_copy(update={"position": position})
        for position, task_hash in enumerate(committed)
    ]
    valid = sum(1 for task in kept if task.gold.valid and task.setup.valid)
    return ValidationEvidence(
        schema_version=shipped.schema_version,
        taskset_lock_digest=digest_object(lock),
        method=shipped.method,
        tasks=kept,
        summary=ValidationEvidenceSummary(
            total=len(kept),
            valid=valid,
            invalid=len(kept) - valid,
            error=0,
            timeout=0,
            missing=0,
        ),
    )


def _reissued_receipt(
    shipped: TasksetValidationReceipt,
    lock: TasksetLock,
    evidence: ValidationEvidence,
) -> TasksetValidationReceipt:
    """Return the shipped receipt's verdict, restated over the narrowed lock."""
    total = evidence.summary.total
    return TasksetValidationReceipt(
        schema_version=shipped.schema_version,
        taskset_lock_digest=digest_object(lock),
        engine_digest=shipped.engine_digest,
        method=shipped.method,
        status=shipped.status,
        upstream_summary=UpstreamValidationSummary(
            mode=shipped.upstream_summary.mode,
            total=total,
            recorded=total,
            valid=evidence.summary.valid,
            invalid=evidence.summary.invalid,
            error=0,
            timeout=0,
            missing=0,
            valid_rate=None if not total else evidence.summary.valid / total,
        ),
        checks=[
            ValidationCheck(
                id=check.id,
                status=check.status,
                detail=f"{check.detail} (restated over {total} tasks)",
            )
            for check in shipped.checks
        ],
        normalized_evidence=ArtifactRef(
            digest=digest_object(evidence),
            media_type=_JSON_MEDIA_TYPE,
            size=len(canonical_json_bytes(evidence)),
            relative_path=None,
        ),
    )


def _location(kind: str, path: str) -> CatalogObjectLocation:
    """Return one catalog object entry."""
    return CatalogObjectLocation.model_validate(
        {"kind": kind, "path": path, "media_type": _JSON_MEDIA_TYPE}
    )


def _write(path: Path, data: bytes) -> None:
    """Write one catalog file, creating the directory it belongs in."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
