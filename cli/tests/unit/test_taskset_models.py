"""Taskset locking and validation receipts. Spec 11.9, decisions 0003 A1.

The property that matters most here is the one decisions document 0003
introduced: a publisher's receipt and a participant's locally recomputed
receipt, given the same lock, engine, method, and normalized results, must be
*equal* — same content, same digest. The old shape carried an identifier and a
timestamp, so two correct receipts could never be equal and the comparison had
to be done by reading. These tests hold that property in place.

The operational record is tested for the opposite property: it varies, it is
allowed to, and it is not part of the Campaign graph.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import digest_object, sha256_digest_bytes
from techtree.constants import (
    PINNED_VERIFIERS_REVISION,
    VALIDATION_EVIDENCE_SCHEMA_VERSION,
    VALIDATION_EXECUTION_SCHEMA_VERSION,
)
from techtree.models.base import ArtifactRef
from techtree.models.validation import (
    REQUIRED_VALIDATION_CHECKS,
    TasksetLock,
    TasksetValidationReceipt,
    ValidationEvidence,
    ValidationEvidenceSummary,
    ValidationEvidenceTask,
    ValidationExecutionRecord,
    ValidationMethod,
    ValidationTaskOutcome,
    validation_display_id,
)

GOLDEN_DIRECTORY = Path(__file__).resolve().parents[1] / "golden"

TASK_COUNT = 4


def golden(name: str) -> dict[str, Any]:
    """Load one committed golden fixture as a mutable JSON document."""
    text = (GOLDEN_DIRECTORY / f"{name}.json").read_text(encoding="utf-8")
    document: dict[str, Any] = json.loads(text)
    return document


def lock(document: dict[str, Any]) -> TasksetLock:
    """Validate a lock the way stored bytes are validated."""
    return TasksetLock.model_validate_json(json.dumps(document))


def receipt(document: dict[str, Any]) -> TasksetValidationReceipt:
    """Validate a receipt the way stored bytes are validated."""
    return TasksetValidationReceipt.model_validate_json(json.dumps(document))


def method() -> ValidationMethod:
    """Return the pinned validation method."""
    return ValidationMethod(
        kind="verifiers_validate",
        mode="all",
        runtime="subprocess",
        validator_revision=PINNED_VERIFIERS_REVISION,
    )


def evidence(task_count: int = TASK_COUNT) -> ValidationEvidence:
    """Return normalized evidence for a fully valid taskset."""
    return ValidationEvidence(
        schema_version=VALIDATION_EVIDENCE_SCHEMA_VERSION,
        taskset_lock_digest=sha256_digest_bytes(b"lock"),
        method=method(),
        tasks=[
            ValidationEvidenceTask(
                position=position,
                task_hash=sha256_digest_bytes(f"task/{position}".encode()),
                gold=ValidationTaskOutcome(valid=True, reason="valid"),
                setup=ValidationTaskOutcome(valid=True, reason="valid"),
            )
            for position in range(task_count)
        ],
        summary=ValidationEvidenceSummary(
            total=task_count,
            valid=task_count,
            invalid=0,
            error=0,
            timeout=0,
            missing=0,
        ),
    )


# ---------------------------------------------------------------------------
# The lock
# ---------------------------------------------------------------------------


def test_development_lock_is_valid() -> None:
    resolved = lock(golden("taskset-lock"))

    assert resolved.task_count == len(resolved.ordered_task_hashes)
    assert resolved.taskset_ref.package.kind == "embedded"


def test_lock_rejects_a_count_that_disagrees_with_its_hashes() -> None:
    document = golden("taskset-lock")
    document["task_count"] = 19

    with pytest.raises(PydanticValidationError, match="task hashes but"):
        lock(document)


def test_lock_rejects_a_repeated_task_hash() -> None:
    document = golden("taskset-lock")
    document["ordered_task_hashes"][1] = document["ordered_task_hashes"][0]

    with pytest.raises(PydanticValidationError, match="must be unique"):
        lock(document)


def test_lock_rejects_a_raw_verifiers_hash() -> None:
    document = golden("taskset-lock")
    document["ordered_task_hashes"][0] = "ab" * 32

    with pytest.raises(PydanticValidationError):
        lock(document)


# ---------------------------------------------------------------------------
# The deterministic receipt
# ---------------------------------------------------------------------------


def test_development_receipt_is_valid() -> None:
    parsed = receipt(golden("taskset-validation-receipt"))

    assert parsed.status == "valid"
    assert parsed.method.validator_revision == PINNED_VERIFIERS_REVISION
    assert parsed.normalized_evidence is not None


def test_receipt_carries_no_identity_or_timing_fields() -> None:
    """Decisions 0003 A1 removed everything that varies between two runs."""
    fields = set(TasksetValidationReceipt.model_fields)

    assert fields.isdisjoint({"id", "created_at", "artifacts", "duration_seconds"})


@pytest.mark.parametrize("field", ["id", "created_at", "artifacts"])
def test_receipt_rejects_the_fields_that_were_removed(field: str) -> None:
    document = golden("taskset-validation-receipt")
    document[field] = "anything"

    with pytest.raises(PydanticValidationError, match="Extra inputs"):
        receipt(document)


def test_publisher_and_local_receipts_have_the_same_digest() -> None:
    """The A1 equality: agreeing parties produce byte-identical receipts."""
    document = golden("taskset-validation-receipt")
    publisher = receipt(document)
    local = receipt(document)

    assert publisher == local
    assert digest_object(publisher) == digest_object(local)


def test_a_different_engine_changes_the_receipt_digest() -> None:
    document = golden("taskset-validation-receipt")
    document["engine_digest"] = sha256_digest_bytes(b"another engine")

    assert digest_object(receipt(document)) != digest_object(
        receipt(golden("taskset-validation-receipt"))
    )


def test_receipt_requires_every_documented_check() -> None:
    for name in REQUIRED_VALIDATION_CHECKS:
        document = golden("taskset-validation-receipt")
        document["checks"] = [
            check for check in document["checks"] if check["id"] != name
        ]

        with pytest.raises(PydanticValidationError, match=f"missing required.*{name}"):
            receipt(document)


def test_receipt_rejects_a_repeated_check() -> None:
    document = golden("taskset-validation-receipt")
    document["checks"].append(document["checks"][0])

    with pytest.raises(PydanticValidationError, match="exactly once"):
        receipt(document)


def test_a_valid_receipt_cannot_contain_a_failed_check() -> None:
    document = golden("taskset-validation-receipt")
    document["checks"][0]["status"] = "failed"

    with pytest.raises(PydanticValidationError, match="failed check is not valid"):
        receipt(document)


def test_receipt_summary_counts_must_add_up() -> None:
    document = golden("taskset-validation-receipt")
    document["upstream_summary"]["valid"] = 19

    with pytest.raises(PydanticValidationError, match="accounts for"):
        receipt(document)


def test_display_id_is_derived_and_not_stored() -> None:
    parsed = receipt(golden("taskset-validation-receipt"))
    digest = digest_object(parsed)

    display = validation_display_id(digest)

    assert display.startswith("validation_")
    assert display == f"validation_{digest.removeprefix('sha256:')[:24]}"
    assert "id" not in parsed.model_dump()


# ---------------------------------------------------------------------------
# Normalized evidence
# ---------------------------------------------------------------------------


def test_evidence_is_valid_and_deterministic() -> None:
    assert digest_object(evidence()) == digest_object(evidence())


def test_evidence_rejects_unordered_tasks() -> None:
    document = json.loads(evidence().model_dump_json())
    document["tasks"].reverse()

    with pytest.raises(PydanticValidationError, match="sorted by position"):
        ValidationEvidence.model_validate_json(json.dumps(document))


def test_evidence_rejects_a_gap_in_positions() -> None:
    document = json.loads(evidence().model_dump_json())
    document["tasks"][-1]["position"] = TASK_COUNT + 1

    with pytest.raises(PydanticValidationError, match="without gaps"):
        ValidationEvidence.model_validate_json(json.dumps(document))


def test_evidence_rejects_a_summary_that_does_not_match_the_tasks() -> None:
    document = json.loads(evidence().model_dump_json())
    document["summary"]["total"] = TASK_COUNT + 1
    document["summary"]["missing"] = 1

    with pytest.raises(PydanticValidationError, match="but its summary reports"):
        ValidationEvidence.model_validate_json(json.dumps(document))


def test_evidence_carries_no_wall_clock_or_path_detail() -> None:
    fields = set(ValidationEvidence.model_fields) | set(
        ValidationEvidenceTask.model_fields
    )

    assert fields.isdisjoint({"elapsed", "started_at", "output_dir", "log_path"})


# ---------------------------------------------------------------------------
# The local execution record
# ---------------------------------------------------------------------------


def execution_record(**overrides: Any) -> ValidationExecutionRecord:
    """Build a local operational record for one validation execution."""
    fields: dict[str, Any] = {
        "schema_version": VALIDATION_EXECUTION_SCHEMA_VERSION,
        "id": "validation-run-1",
        "receipt_digest": sha256_digest_bytes(b"receipt"),
        "started_at": datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        "finished_at": datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
        "command": ["uv", "run", "vf-eval", "--validate"],
        "command_digest": sha256_digest_bytes(b"command"),
        "host_platform": "darwin/arm64",
        "worker_pid": 4242,
        "raw_artifacts": [
            ArtifactRef(
                digest=sha256_digest_bytes(b"validate.log"),
                media_type="text/plain",
                size=1024,
                relative_path="validate.log",
            )
        ],
    }
    fields.update(overrides)
    return ValidationExecutionRecord(**fields)


def test_execution_record_holds_what_the_receipt_refuses_to() -> None:
    record = execution_record()

    assert record.worker_pid == 4242
    assert record.host_platform == "darwin/arm64"
    assert record.raw_artifacts[0].relative_path == "validate.log"


def test_execution_record_is_mutable_local_state() -> None:
    record = execution_record()

    record.worker_pid = 99

    assert record.worker_pid == 99


def test_execution_record_rejects_a_window_that_ends_before_it_starts() -> None:
    with pytest.raises(PydanticValidationError, match="cannot precede"):
        execution_record(finished_at=datetime(2025, 1, 1, tzinfo=UTC))


def test_execution_record_requires_the_command_it_ran() -> None:
    with pytest.raises(PydanticValidationError, match="records the command"):
        execution_record(command=[])


def test_execution_records_differ_between_runs_and_that_is_fine() -> None:
    first = execution_record(worker_pid=1)
    second = execution_record(worker_pid=2)

    assert digest_object(first) != digest_object(second)
    assert first.receipt_digest == second.receipt_digest
