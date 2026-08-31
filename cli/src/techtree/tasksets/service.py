"""Locking a taskset and proving it valid. Spec section 21.5.

One question runs through this module: *is the thing about to be scored the
thing that was committed to, and is it mechanically sound?* Answering it takes
two independent halves, and the shape of the code follows that split.

The first half is identity. :class:`~techtree.tasksets.resolver.TasksetResolver`
loads the taskset twice in fresh processes and produces a
:class:`~techtree.models.validation.TasksetLock`; this module compares that lock
with the membership a Campaign committed to.

The second half is soundness. The pinned Verifiers validator runs every task's
gold and setup check with no model anywhere, the engine normalizes its output
into deterministic evidence, and the counts become the mechanical checks a
:class:`~techtree.models.validation.TasksetValidationReceipt` carries.

**Nothing that varies between two correct runs enters the receipt.** Decisions
document 0003 A1 made the receipt deterministic so that the publisher's receipt
and a participant's recomputed receipt are *equal*, and that equality is the
comparison. Everything a real execution also produces — when it started, on
which host, under which command, and the raw files it left behind — goes into a
:class:`~techtree.models.validation.ValidationExecutionRecord` instead, which is
local, never shipped, and never byte-compared.

The consequence for callers is worth stating plainly: this service is used
unchanged by the publisher's catalog generator and by a participant's worker.
There is no publisher mode. If the two ever produced different receipts for the
same taskset, that would be the finding, not a detail to reconcile.
"""

from __future__ import annotations

import os
import platform
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

from techtree.canonical import canonical_json_bytes, digest_object, sha256_digest_bytes
from techtree.constants import (
    TASKSET_VALIDATION_SCHEMA_VERSION,
    VALIDATION_EXECUTION_SCHEMA_VERSION,
)
from techtree.engines.registry import EngineRegistry
from techtree.errors import PrerequisiteError, VerificationError
from techtree.fs import atomic_write_bytes, ensure_private_directory
from techtree.models.base import ArtifactRef, Digest
from techtree.models.campaign import CampaignSpec, TaskSelection, TasksetRef
from techtree.models.engine import normalize_host_platform
from techtree.models.validation import (
    REQUIRED_VALIDATION_CHECKS,
    TasksetLock,
    TasksetValidationReceipt,
    UpstreamValidationSummary,
    ValidationCheck,
    ValidationEvidence,
    ValidationExecutionRecord,
    ValidationMethod,
    validation_display_id,
)
from techtree.tasksets.membership import (
    MEMBERSHIP_MATCH_CHECK,
    MEMBERSHIP_REPEATABILITY_CHECK,
    compare_membership,
)
from techtree.tasksets.resolver import TasksetResolver
from techtree.tasksets.verifiers_cli import (
    GOLD_CHECK,
    SETUP_CHECK,
    UpstreamCheckCounts,
    VerifiersValidationRunner,
)

__all__ = [
    "EVIDENCE_FILENAME",
    "EXECUTION_RECORD_FILENAME",
    "LOCK_FILENAME",
    "RECEIPT_FILENAME",
    "TASKSET_DIRECTORY",
    "VALIDATION_DIRECTORY",
    "TasksetService",
    "TasksetValidationRun",
]

#: Where a run keeps everything about its taskset. Spec section 28.
TASKSET_DIRECTORY: Final = "taskset"
VALIDATION_DIRECTORY: Final = "validation"

LOCK_FILENAME: Final = "lock.json"
RECEIPT_FILENAME: Final = "receipt.json"
#: Decisions document 0003 A1 added the normalized evidence and the execution
#: record after spec section 28 was written. Both live beside the receipt: the
#: evidence because the receipt points at it, the record because it is the raw
#: provenance of the same execution.
EVIDENCE_FILENAME: Final = "evidence.json"
EXECUTION_RECORD_FILENAME: Final = "execution.json"

_JSON_MEDIA_TYPE: Final = "application/json"

#: The two mechanical checks that come from the validator itself.
_UPSTREAM_GOLD_CHECK: Final = "upstream_gold"
_UPSTREAM_SETUP_CHECK: Final = "upstream_setup"
_UNIQUENESS_CHECK: Final = "task_hash_uniqueness"
_TASK_COUNT_CHECK: Final = "expected_task_count"


@dataclass(frozen=True)
class TasksetValidationRun:
    """Everything one validation produced, scientific and operational.

    Spec section 21.5 has ``resolve_and_validate`` return a lock and a receipt.
    Decisions document 0003 A1 added two more objects with distinct lifetimes —
    the shipped evidence a receipt points at, and the local record of the
    execution — so they are returned together rather than fetched afterwards
    from paths a caller would have to reconstruct.
    """

    lock: TasksetLock
    receipt: TasksetValidationReceipt
    evidence: ValidationEvidence
    execution_record: ValidationExecutionRecord

    @property
    def receipt_digest(self) -> Digest:
        """Return the receipt's content digest, which is its identity."""
        return digest_object(self.receipt)


class TasksetService:
    """Resolves, validates, and issues a receipt for one taskset.

    The service is bound to one installed engine. Which engine that is comes
    from the caller — a participant uses the one the publisher's receipt names,
    so that a difference in receipts can only ever be a difference in the
    taskset.
    """

    def __init__(
        self,
        registry: EngineRegistry,
        engine_digest: Digest,
    ) -> None:
        self._registry = registry
        self._engine_digest = engine_digest
        self._resolver = TasksetResolver(registry, engine_digest)
        self._validator = VerifiersValidationRunner(registry, engine_digest)

    # -- the two halves, and the whole -------------------------------------

    def resolve(
        self,
        *,
        taskset_ref: TasksetRef,
        selection: TaskSelection,
    ) -> TasksetLock:
        """Return what this reference resolves to against this engine.

        Exposed separately because the publisher has nothing to compare a lock
        with yet: the Campaign that will commit to a membership is built from
        this lock, not the other way round.
        """
        return self._resolver.resolve(taskset_ref=taskset_ref, selection=selection)

    def validate(
        self,
        *,
        lock: TasksetLock,
        committed_task_hashes: Sequence[Digest],
        expected_task_count: int,
        run_dir: Path,
    ) -> TasksetValidationRun:
        """Run the pinned validation against an already-resolved lock."""
        taskset = run_dir / TASKSET_DIRECTORY
        output_dir = taskset / VALIDATION_DIRECTORY
        ensure_private_directory(taskset)
        ensure_private_directory(output_dir)

        self._write_lock(run_dir, lock)

        started_at = datetime.now(UTC)
        process = self._validator.run(
            taskset_id=lock.taskset_ref.id,
            num_tasks=lock.task_count,
            output_dir=output_dir,
        )
        finished_at = datetime.now(UTC)

        summary = self._validator.parse_summary(output_dir)
        check_counts = self._validator.parse_check_counts(output_dir)
        evidence = self._validator.normalize(
            output_dir, taskset_lock_digest=digest_object(lock)
        )

        checks = self._build_checks(
            lock=lock,
            committed_task_hashes=committed_task_hashes,
            expected_task_count=expected_task_count,
            check_counts=check_counts,
        )
        receipt = TasksetValidationReceipt(
            schema_version=TASKSET_VALIDATION_SCHEMA_VERSION,
            taskset_lock_digest=digest_object(lock),
            engine_digest=lock.engine_digest,
            method=ValidationMethod(
                kind="verifiers_validate",
                mode="all",
                runtime="subprocess",
                validator_revision=evidence.method.validator_revision,
            ),
            status=self._receipt_status(checks, summary),
            upstream_summary=summary,
            checks=checks,
            normalized_evidence=_evidence_reference(evidence),
        )

        self._write_evidence(run_dir, evidence)
        self._write_receipt(run_dir, receipt)

        command = [str(part) for part in process.argv]
        record = ValidationExecutionRecord(
            schema_version=VALIDATION_EXECUTION_SCHEMA_VERSION,
            id=validation_display_id(digest_object(receipt)),
            receipt_digest=digest_object(receipt),
            started_at=started_at,
            finished_at=finished_at,
            command=command,
            command_digest=digest_object({"command": command}),
            host_platform=_host_platform(),
            worker_pid=os.getpid(),
            raw_artifacts=self._validator.validation_artifacts(output_dir),
        )
        self._write_execution_record(run_dir, record)

        return TasksetValidationRun(
            lock=lock,
            receipt=receipt,
            evidence=evidence,
            execution_record=record,
        )

    def resolve_and_validate(
        self,
        *,
        campaign: CampaignSpec,
        run_dir: Path,
    ) -> TasksetValidationRun:
        """Resolve this Campaign's taskset, validate it, and issue a receipt."""
        lock = self.resolve(
            taskset_ref=campaign.taskset.ref,
            selection=campaign.taskset.selection,
        )
        return self.validate(
            lock=lock,
            committed_task_hashes=campaign.taskset.membership.ordered_task_hashes,
            expected_task_count=campaign.taskset.selection.num_tasks,
            run_dir=run_dir,
        )

    # -- the mechanical checks ---------------------------------------------

    def _build_checks(
        self,
        *,
        lock: TasksetLock,
        committed_task_hashes: Sequence[Digest],
        expected_task_count: int,
        check_counts: dict[str, UpstreamCheckCounts],
    ) -> list[ValidationCheck]:
        """Build every check a receipt is required to report.

        Every detail string is a function of the taskset alone. A path, a
        duration, or a host name in any of them would make two correct receipts
        for the same taskset differ, which is the one thing decisions document
        0003 A1 set out to prevent.
        """
        checks = [
            _upstream_check(_UPSTREAM_GOLD_CHECK, check_counts.get(GOLD_CHECK)),
            _upstream_check(_UPSTREAM_SETUP_CHECK, check_counts.get(SETUP_CHECK)),
            ValidationCheck(
                id=MEMBERSHIP_REPEATABILITY_CHECK,
                status="passed",
                detail=(
                    f"two independent inspections agreed on all {lock.task_count} "
                    "task hashes, in order"
                ),
            ),
            _uniqueness_check(lock),
            compare_membership(
                list(lock.ordered_task_hashes),
                list(committed_task_hashes),
                check_id=MEMBERSHIP_MATCH_CHECK,
            ),
            _task_count_check(lock, expected_task_count),
        ]

        reported = {check.id for check in checks}
        missing = [name for name in REQUIRED_VALIDATION_CHECKS if name not in reported]
        if missing:
            raise VerificationError(
                "this validation reported no result for " + ", ".join(missing),
                code="taskset_validation_incomplete",
                details={"missing": list(missing)},
            )
        return checks

    def _receipt_status(
        self,
        checks: Sequence[ValidationCheck],
        summary: UpstreamValidationSummary,
    ) -> Literal["valid", "invalid", "errored"]:
        """Decide what the receipt claims about this taskset.

        ``errored`` and ``invalid`` are different findings. A task whose check
        raised, timed out, or never recorded a row says the validation did not
        reach a verdict; a task that returned False says it reached one and the
        answer was no. Reporting the first as the second would present an
        unfinished run as a scientific result.
        """
        if summary.error or summary.timeout or summary.missing:
            return "errored"
        if summary.recorded != summary.total:
            return "errored"
        if summary.invalid or summary.valid != summary.total:
            return "invalid"
        if any(check.status == "failed" for check in checks):
            return "invalid"
        return "valid"

    # -- persistence -------------------------------------------------------

    def _write_lock(self, run_dir: Path, lock: TasksetLock) -> ArtifactRef:
        """Persist the lock this run was issued under."""
        return _write_object(run_dir / TASKSET_DIRECTORY / LOCK_FILENAME, lock, run_dir)

    def _write_receipt(
        self, run_dir: Path, receipt: TasksetValidationReceipt
    ) -> ArtifactRef:
        """Persist the receipt in exactly the bytes its digest is taken over."""
        return _write_object(
            run_dir / TASKSET_DIRECTORY / VALIDATION_DIRECTORY / RECEIPT_FILENAME,
            receipt,
            run_dir,
        )

    def _write_evidence(
        self, run_dir: Path, evidence: ValidationEvidence
    ) -> ArtifactRef:
        """Persist the normalized evidence the receipt points at."""
        return _write_object(
            run_dir / TASKSET_DIRECTORY / VALIDATION_DIRECTORY / EVIDENCE_FILENAME,
            evidence,
            run_dir,
        )

    def _write_execution_record(
        self, run_dir: Path, record: ValidationExecutionRecord
    ) -> ArtifactRef:
        """Persist the local provenance of this execution."""
        return _write_object(
            run_dir
            / TASKSET_DIRECTORY
            / VALIDATION_DIRECTORY
            / EXECUTION_RECORD_FILENAME,
            record,
            run_dir,
        )


# ---------------------------------------------------------------------------
# Check construction
# ---------------------------------------------------------------------------


def _upstream_check(
    check_id: str, counts: UpstreamCheckCounts | None
) -> ValidationCheck:
    """Turn one of the validator's per-check breakdowns into a receipt check."""
    if counts is None:
        return ValidationCheck(
            id=check_id,
            status="failed",
            detail=(
                "the validator reported no per-check breakdown, so this check "
                "cannot be read as either passed or failed"
            ),
        )
    if counts.passed:
        return ValidationCheck(
            id=check_id,
            status="passed",
            detail=f"all {counts.valid} tasks passed this check",
        )
    return ValidationCheck(id=check_id, status="failed", detail=counts.summary())


def _uniqueness_check(lock: TasksetLock) -> ValidationCheck:
    """Report whether any task appears twice in the locked membership."""
    hashes = list(lock.ordered_task_hashes)
    repeated = len(hashes) - len(set(hashes))
    if repeated == 0:
        return ValidationCheck(
            id=_UNIQUENESS_CHECK,
            status="passed",
            detail=f"all {len(hashes)} task hashes are distinct",
        )
    return ValidationCheck(
        id=_UNIQUENESS_CHECK,
        status="failed",
        detail=(
            f"{repeated} of {len(hashes)} task hashes repeat, and a repeated "
            "task would be scored twice under one commitment"
        ),
    )


def _task_count_check(lock: TasksetLock, expected: int) -> ValidationCheck:
    """Report whether the lock holds as many tasks as were asked for."""
    if lock.task_count == expected:
        return ValidationCheck(
            id=_TASK_COUNT_CHECK,
            status="passed",
            detail=f"{expected} tasks, as the selection asks for",
        )
    return ValidationCheck(
        id=_TASK_COUNT_CHECK,
        status="failed",
        detail=(
            f"the taskset resolved to {lock.task_count} tasks and the selection "
            f"asks for {expected}"
        ),
    )


# ---------------------------------------------------------------------------
# Bytes
# ---------------------------------------------------------------------------


def _evidence_reference(evidence: ValidationEvidence) -> ArtifactRef:
    """Return the reference a receipt carries to its normalized evidence.

    No relative path. The receipt is a public object that travels inside a
    content-addressed catalog, where an artifact is found by digest; a path
    would be one machine's answer to a question the catalog answers for
    everyone, and it would make the publisher's receipt and a participant's
    differ over nothing.
    """
    data = canonical_json_bytes(evidence)
    return ArtifactRef(
        digest=sha256_digest_bytes(data),
        media_type=_JSON_MEDIA_TYPE,
        size=len(data),
        relative_path=None,
    )


def _write_object(path: Path, value: object, run_dir: Path) -> ArtifactRef:
    """Write one object as the canonical bytes its digest is taken over."""
    data = canonical_json_bytes(value)
    ensure_private_directory(path.parent)
    atomic_write_bytes(path, data)
    return ArtifactRef(
        digest=sha256_digest_bytes(data),
        media_type=_JSON_MEDIA_TYPE,
        size=len(data),
        relative_path=path.relative_to(run_dir).as_posix(),
    )


def _host_platform() -> str:
    """Return this host in the protocol's vocabulary, or say it is unsupported.

    Decisions document 0003 A9. An unsupported host still records *something*:
    the execution record exists to say what happened, and refusing to write one
    because the platform string is unfamiliar would lose the very provenance it
    is for.
    """
    try:
        return normalize_host_platform(sys.platform, platform.machine())
    except PrerequisiteError:
        return f"{sys.platform}/{platform.machine()}"
