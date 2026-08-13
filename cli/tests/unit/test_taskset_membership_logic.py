"""Membership identity, without an engine. Spec sections 21.2 and 27.2.

Everything here is pure: no subprocess, no installed engine, no Verifiers. The
real double inspection lives in ``tests/integration/test_taskset_membership.py``,
which is why this file carries the longer name — pytest and mypy both derive a
module name from the basename alone, so two test files may not share one.

What this file protects is the arithmetic and the boundary — the two places
where a membership commitment can be wrong in a way that still looks fine.

Three things are pinned deliberately.

*The digest is pinned to bytes, not to itself.* The expected value is computed
here from a hand-written canonical JSON string, so the test would fail if the
wrapping object, its key, the array order, or the canonicalization ever changed.
A test that recomputed the digest with the same helper would pass through any of
those changes.

*Every rejected hash spelling is a real one.* Uppercase hexadecimal, a truncated
digest, and an already-prefixed Techtree digest are what a well-meaning change
to the engine helper would actually emit, and each of them would put a value
into the protocol that no other implementation would agree on.

*The loader is not the uniqueness check.* Reading a document and deciding that
its membership is usable are separate steps, and the tests keep them separate,
because the resolver is where "this taskset yielded the same task twice" has to
become a refusal.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from techtree.canonical import digest_object
from techtree.errors import ValidationError, VerificationError
from techtree.models.base import Digest
from techtree.models.validation import REQUIRED_VALIDATION_CHECKS
from techtree.tasksets.membership import (
    INSPECTION_SCHEMA_VERSION,
    MEMBERSHIP_MATCH_CHECK,
    MEMBERSHIP_REPEATABILITY_CHECK,
    TasksetInspection,
    assert_unique_task_hashes,
    compare_membership,
    load_inspection_output,
    membership_digest,
)

TASKSET_ID = "procedure-transfer-v1"


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------


def raw_hash(seed: int) -> str:
    """Return a Verifiers task hash: 64 lowercase hexadecimal characters.

    Derived by hashing, not spelled out, so that the fixture hashes carry the
    letters ``a``–``f`` a real digest carries. A hash of nothing but zeros and
    ones is unchanged by ``upper()``, which would quietly turn the uppercase
    rejection tests into no-ops.
    """
    return hashlib.sha256(f"task/{seed}".encode()).hexdigest()


def task_digest(seed: int) -> Digest:
    """Return the Techtree digest the same task hash normalizes to."""
    return f"sha256:{raw_hash(seed)}"


def inspection_document(*, count: int = 3, **overrides: Any) -> dict[str, Any]:
    """Return the document the engine helper writes for a healthy taskset."""
    document: dict[str, Any] = {
        "schema_version": INSPECTION_SCHEMA_VERSION,
        "taskset_id": TASKSET_ID,
        "taskset_class": "ProcedureTransferTaskset",
        "requested_num_tasks": count,
        "task_count": count,
        "tasks": [
            {
                "position": position,
                "task_hash": raw_hash(position + 1),
                "name": f"branch-code-{position:03d}",
                "task_type": "ProcedureTransferTask",
            }
            for position in range(count)
        ],
    }
    document.update(overrides)
    return document


def write_document(directory: Path, document: object) -> Path:
    """Write one inspection document the way the engine helper would."""
    path = directory / "inspection.json"
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# The membership digest
# ---------------------------------------------------------------------------


def test_the_membership_digest_is_the_digest_of_the_named_ordered_object() -> None:
    """The hashed bytes carry the meaning of the array, not just its values."""
    hashes = [task_digest(1), task_digest(2)]
    canonical = f'{{"ordered_task_hashes":["{task_digest(1)}","{task_digest(2)}"]}}'
    expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    assert membership_digest(hashes) == f"sha256:{expected}"


def test_the_membership_digest_is_not_the_digest_of_a_bare_array() -> None:
    """A list of strings and a membership commitment hash differently."""
    hashes = [task_digest(1), task_digest(2)]

    assert membership_digest(hashes) != digest_object(hashes)


def test_the_membership_digest_depends_on_order() -> None:
    forward = membership_digest([task_digest(1), task_digest(2)])
    reversed_order = membership_digest([task_digest(2), task_digest(1)])

    assert forward != reversed_order


def test_the_membership_digest_is_stable_across_calls() -> None:
    hashes = [task_digest(index) for index in range(1, 37)]

    assert membership_digest(hashes) == membership_digest(list(hashes))


def test_an_empty_membership_has_no_digest() -> None:
    with pytest.raises(ValidationError) as failure:
        membership_digest([])

    assert failure.value.code == "membership_empty"


@pytest.mark.parametrize(
    "value",
    [
        raw_hash(1),
        f"sha256:{raw_hash(1).upper()}",
        "sha256:abc",
        "sha512:" + "a" * 64,
    ],
)
def test_a_membership_digest_revalidates_every_hash(value: str) -> None:
    """A type annotation is a claim about the caller, not a check on the value."""
    with pytest.raises(ValidationError):
        membership_digest([task_digest(1), value])


# ---------------------------------------------------------------------------
# Uniqueness
# ---------------------------------------------------------------------------


def test_a_membership_of_distinct_tasks_is_accepted() -> None:
    assert_unique_task_hashes([task_digest(index) for index in range(1, 37)])


def test_a_repeated_task_is_refused_with_both_positions() -> None:
    hashes = [task_digest(1), task_digest(2), task_digest(1)]

    with pytest.raises(VerificationError) as failure:
        assert_unique_task_hashes(hashes)

    assert failure.value.code == "taskset_task_hash_repeated"
    assert failure.value.details["first_position"] == 0
    assert failure.value.details["repeated_position"] == 2
    assert failure.value.details["task_hash"] == task_digest(1)


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def test_the_check_names_this_module_uses_are_receipt_checks() -> None:
    """A check a receipt cannot carry is a check nobody ever reads."""
    assert MEMBERSHIP_MATCH_CHECK in REQUIRED_VALIDATION_CHECKS
    assert MEMBERSHIP_REPEATABILITY_CHECK in REQUIRED_VALIDATION_CHECKS


def test_identical_memberships_pass_as_the_commitment_check() -> None:
    hashes = [task_digest(index) for index in range(1, 5)]

    check = compare_membership(hashes, list(hashes))

    assert check.id == MEMBERSHIP_MATCH_CHECK
    assert check.status == "passed"
    assert "4 task hashes" in check.detail


def test_a_comparison_can_answer_the_repeatability_check_instead() -> None:
    hashes = [task_digest(1)]

    check = compare_membership(
        hashes, list(hashes), check_id=MEMBERSHIP_REPEATABILITY_CHECK
    )

    assert check.id == MEMBERSHIP_REPEATABILITY_CHECK
    assert check.status == "passed"


def test_a_failed_comparison_names_the_first_difference_only() -> None:
    actual = [task_digest(1), task_digest(9), task_digest(8)]
    committed = [task_digest(1), task_digest(2), task_digest(3)]

    check = compare_membership(actual, committed)

    assert check.status == "failed"
    assert "position 1" in check.detail
    assert task_digest(9) in check.detail
    assert task_digest(2) in check.detail
    assert task_digest(8) not in check.detail


def test_a_shorter_membership_reports_both_counts_and_the_missing_task() -> None:
    committed = [task_digest(1), task_digest(2)]

    check = compare_membership([task_digest(1)], committed)

    assert check.status == "failed"
    assert "records 1 tasks but the commitment names 2" in check.detail
    assert "position 1" in check.detail
    assert "recorded nothing" in check.detail


def test_a_longer_membership_is_also_a_failure() -> None:
    check = compare_membership(
        [task_digest(1), task_digest(2)],
        [task_digest(1)],
    )

    assert check.status == "failed"
    assert "committed nothing" in check.detail


def test_comparing_two_empty_memberships_proves_nothing() -> None:
    check = compare_membership([], [])

    assert check.status == "failed"
    assert "nothing to compare" in check.detail


# ---------------------------------------------------------------------------
# Reading the engine's report
# ---------------------------------------------------------------------------


def test_a_healthy_report_loads_with_normalized_hashes(tmp_path: Path) -> None:
    path = write_document(tmp_path, inspection_document())

    inspection = load_inspection_output(path)

    assert isinstance(inspection, TasksetInspection)
    assert inspection.taskset_id == TASKSET_ID
    assert inspection.task_count == 3
    assert inspection.ordered_task_hashes == [task_digest(index) for index in (1, 2, 3)]
    assert [task.position for task in inspection.tasks] == [0, 1, 2]
    assert inspection.tasks[0].name == "branch-code-000"
    assert inspection.tasks[0].task_type == "ProcedureTransferTask"


def test_a_report_that_was_never_written_is_a_named_failure(tmp_path: Path) -> None:
    with pytest.raises(ValidationError) as failure:
        load_inspection_output(tmp_path / "absent.json")

    assert failure.value.code == "taskset_inspection_missing"


def test_a_report_that_is_not_json_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "inspection.json"
    path.write_text("not json at all\n", encoding="utf-8")

    with pytest.raises(ValidationError) as failure:
        load_inspection_output(path)

    assert failure.value.code == "taskset_inspection_invalid"


@pytest.mark.parametrize(
    "task_hash",
    [
        raw_hash(1).upper(),
        raw_hash(1)[:40],
        raw_hash(1) + "ab",
        f"sha256:{raw_hash(1)}",
        f" {raw_hash(1)} ",
        "",
    ],
)
def test_a_hash_the_boundary_does_not_recognize_is_refused(
    tmp_path: Path, task_hash: str
) -> None:
    """Uppercase, truncated, prefixed, padded: every one is a real mistake."""
    document = inspection_document(count=1)
    document["tasks"][0]["task_hash"] = task_hash
    path = write_document(tmp_path, document)

    with pytest.raises(ValidationError) as failure:
        load_inspection_output(path)

    assert failure.value.code == "taskset_inspection_invalid"


def test_a_report_carrying_task_content_is_refused(tmp_path: Path) -> None:
    """The helper reports identity; a prompt or an answer is not identity."""
    document = inspection_document(count=1)
    document["tasks"][0]["prompt"] = "Apply BranchCode v1 to this input:"
    path = write_document(tmp_path, document)

    with pytest.raises(ValidationError) as failure:
        load_inspection_output(path)

    assert failure.value.code == "taskset_inspection_invalid"


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"schema_version": "techtree.taskset-inspection.v2"}, id="schema"),
        pytest.param({"taskset_id": ""}, id="anonymous-taskset"),
        pytest.param({"task_count": 4}, id="count-disagrees-with-records"),
        pytest.param({"requested_num_tasks": 4}, id="request-disagrees-with-count"),
        pytest.param({"taskset_class": None}, id="no-class"),
    ],
)
def test_a_self_contradicting_report_is_refused(
    tmp_path: Path, overrides: dict[str, Any]
) -> None:
    path = write_document(tmp_path, inspection_document(**overrides))

    with pytest.raises(ValidationError) as failure:
        load_inspection_output(path)

    assert failure.value.code == "taskset_inspection_invalid"


def test_records_out_of_position_order_are_refused(tmp_path: Path) -> None:
    document = inspection_document()
    document["tasks"] = list(reversed(document["tasks"]))
    path = write_document(tmp_path, document)

    with pytest.raises(ValidationError) as failure:
        load_inspection_output(path)

    assert failure.value.code == "taskset_inspection_invalid"


def test_a_gap_in_the_positions_is_refused(tmp_path: Path) -> None:
    document = inspection_document()
    document["tasks"][2]["position"] = 7
    path = write_document(tmp_path, document)

    with pytest.raises(ValidationError):
        load_inspection_output(path)


def test_a_report_naming_the_same_task_twice_loads_but_does_not_pass_uniqueness(
    tmp_path: Path,
) -> None:
    """Reading a document and accepting its membership are separate steps."""
    document = inspection_document()
    document["tasks"][2]["task_hash"] = raw_hash(1)
    path = write_document(tmp_path, document)

    inspection = load_inspection_output(path)

    with pytest.raises(VerificationError) as failure:
        assert_unique_task_hashes(inspection.ordered_task_hashes)

    assert failure.value.code == "taskset_task_hash_repeated"
