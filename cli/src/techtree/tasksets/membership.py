"""What tasks a Climb is about, stated so two parties can compare it.

Spec section 21.2.

Membership is an ordered list of task hashes and nothing else. The order is the
taskset's own iteration order, the first ``num_tasks`` of it, with no shuffle
anywhere in WP0–WP5 (decisions document 0001). Two things follow.

*Identity crosses the boundary; content does not.* The engine helper reports a
position, a hash, a name, and a class name. It never reports a prompt or an
answer, so a membership commitment can be published without publishing the
taskset. :func:`load_inspection_output` is where that report becomes typed
Techtree data, and it is the only place raw Verifiers hashes — bare
64-character lowercase hexadecimal — turn into Techtree digests. The conversion
goes through :func:`~techtree.canonical.normalize_verifiers_task_hash`, which
accepts that one spelling and refuses everything else, including an
already-prefixed digest: a boundary that waved prefixed strings through would
be a place where unvalidated text could enter the protocol looking official.

*The digest is taken over a named object, not over a bare array.* Hashing the
list alone would give the same bytes to any other list of strings that happened
to hold the same values. Wrapping it in ``{"ordered_task_hashes": [...]}`` puts
the meaning of the array inside the hashed bytes, so a membership digest can
only ever be a membership digest.

:func:`compare_membership` reports; it does not decide. It returns the
``ValidationCheck`` a receipt carries, naming the first position where two
memberships disagree, because "these two lists differ" is not something an
operator can act on and "position 7 is a different task" is.
:func:`assert_unique_task_hashes` is the one function here that refuses, since a
membership that names the same task twice would score it twice under one
commitment and there is no reading of that which is merely a warning.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Final, Literal, Self

from pydantic import AfterValidator, Field, model_validator

from techtree.canonical import (
    digest_object,
    normalize_verifiers_task_hash,
    validate_digest,
)
from techtree.errors import ValidationError, VerificationError
from techtree.models.base import Digest, NonEmptyString, ProtocolModel
from techtree.models.validation import ValidationCheck

__all__ = [
    "INSPECTION_SCHEMA_VERSION",
    "MEMBERSHIP_DIGEST_KEY",
    "MEMBERSHIP_MATCH_CHECK",
    "MEMBERSHIP_REPEATABILITY_CHECK",
    "TaskInspection",
    "TasksetInspection",
    "VerifiersTaskHash",
    "assert_unique_task_hashes",
    "compare_membership",
    "load_inspection_output",
    "membership_digest",
]

#: The shape the engine helper writes. Owned by the engine bundle
#: (``tools/inspect_taskset.py``, decisions document 0003 A3); this module is
#: its reader, and reads exactly this version.
INSPECTION_SCHEMA_VERSION: Final = "techtree.taskset-inspection.v1"

#: The single key of the object a membership digest is taken over. Changing it
#: changes every membership digest in existence, which is why it is spelled
#: once, here.
MEMBERSHIP_DIGEST_KEY: Final = "ordered_task_hashes"

#: The check that two inspections of the same taskset agreed.
MEMBERSHIP_REPEATABILITY_CHECK: Final = "membership_repeatability"
#: The check that what was resolved is what the Campaign committed to.
MEMBERSHIP_MATCH_CHECK: Final = "committed_membership_match"


def _normalized_task_hash(value: str) -> Digest:
    """Normalize at the boundary, in the vocabulary Pydantic understands."""
    try:
        return normalize_verifiers_task_hash(value)
    except ValidationError as error:
        raise ValueError(error.message) from error


type VerifiersTaskHash = Annotated[str, AfterValidator(_normalized_task_hash)]
"""A raw Verifiers task hash on the way in, a Techtree digest once validated."""


class TaskInspection(ProtocolModel):
    """The identity of one task, as the engine reported it."""

    position: int = Field(ge=0)
    task_hash: VerifiersTaskHash
    name: NonEmptyString | None
    task_type: NonEmptyString


class TasksetInspection(ProtocolModel):
    """One engine inspection of one taskset."""

    schema_version: Literal["techtree.taskset-inspection.v1"]
    taskset_id: NonEmptyString
    taskset_class: NonEmptyString
    requested_num_tasks: int = Field(ge=1)
    task_count: int = Field(ge=1)
    tasks: list[TaskInspection]

    @model_validator(mode="after")
    def _check_records_are_a_dense_ordered_run(self) -> Self:
        """Reject gaps, repeats, or a count the records do not support.

        Position is what makes membership an *ordered* commitment, so a report
        whose positions are not ``0..n-1`` in order cannot be read as one.
        """
        positions = [task.position for task in self.tasks]
        if positions != list(range(len(self.tasks))):
            raise ValueError(
                "inspection records must be sorted by position and cover 0..n-1 "
                "without gaps"
            )
        if self.task_count != len(self.tasks):
            raise ValueError(
                f"inspection lists {len(self.tasks)} tasks but reports a "
                f"task_count of {self.task_count}"
            )
        if self.requested_num_tasks != self.task_count:
            raise ValueError(
                f"inspection reports {self.task_count} tasks for a request of "
                f"{self.requested_num_tasks}"
            )
        return self

    @property
    def ordered_task_hashes(self) -> list[Digest]:
        """Return the normalized task hashes in the order they were reported."""
        return [task.task_hash for task in self.tasks]


def membership_digest(ordered_task_hashes: list[Digest]) -> Digest:
    """Digest the canonical ordered-hash object.

    Every hash is revalidated on the way in. The parameter is typed as a list of
    digests, but a type annotation is a claim about the caller, not a check on
    the value, and this digest is a commitment other parties will be held to.
    """
    if not ordered_task_hashes:
        raise ValidationError(
            "a membership digest commits to at least one task",
            code="membership_empty",
            details={"task_count": 0},
        )
    return digest_object(
        {
            MEMBERSHIP_DIGEST_KEY: [
                validate_digest(value) for value in ordered_task_hashes
            ]
        }
    )


def assert_unique_task_hashes(hashes: list[Digest]) -> None:
    """Reject a membership that names the same task twice."""
    first_seen: dict[Digest, int] = {}
    for position, value in enumerate(hashes):
        earlier = first_seen.setdefault(value, position)
        if earlier != position:
            raise VerificationError(
                f"task {value} appears at positions {earlier} and {position}; a "
                "repeated task would be scored twice under one commitment",
                code="taskset_task_hash_repeated",
                details={
                    "task_hash": value,
                    "first_position": earlier,
                    "repeated_position": position,
                },
            )


def compare_membership(
    actual: list[Digest],
    committed: list[Digest],
    *,
    check_id: str = MEMBERSHIP_MATCH_CHECK,
) -> ValidationCheck:
    """Return pass or fail for two memberships, naming the first difference.

    ``check_id`` selects which of the receipt's required checks this comparison
    answers: the same comparison proves repeatability when it runs over two
    inspections and commitment match when it runs against a Campaign.
    """
    if not actual and not committed:
        return ValidationCheck(
            id=check_id,
            status="failed",
            detail="both memberships are empty, so there is nothing to compare",
        )

    mismatch = _first_difference(actual, committed)
    if mismatch is None and len(actual) == len(committed):
        return ValidationCheck(
            id=check_id,
            status="passed",
            detail=f"all {len(actual)} task hashes match in order",
        )

    return ValidationCheck(
        id=check_id,
        status="failed",
        detail=_mismatch_detail(actual, committed, mismatch),
    )


def load_inspection_output(path: Path) -> TasksetInspection:
    """Validate one engine inspection document and normalize its hashes."""
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ValidationError(
            f"the engine wrote no inspection output at {path}",
            code="taskset_inspection_missing",
            details={"path": str(path)},
        ) from error

    try:
        return TasksetInspection.model_validate_json(raw)
    except ValueError as error:
        raise ValidationError(
            f"the engine's inspection output is not a valid "
            f"{INSPECTION_SCHEMA_VERSION} document: {error}",
            code="taskset_inspection_invalid",
            details={"path": str(path)},
        ) from error


def _first_difference(
    actual: list[Digest], committed: list[Digest]
) -> tuple[int, Digest | None, Digest | None] | None:
    """Return the first position the two memberships disagree at, if any."""
    for position in range(max(len(actual), len(committed))):
        left = actual[position] if position < len(actual) else None
        right = committed[position] if position < len(committed) else None
        if left != right:
            return position, left, right
    return None


def _mismatch_detail(
    actual: list[Digest],
    committed: list[Digest],
    mismatch: tuple[int, Digest | None, Digest | None] | None,
) -> str:
    """Describe a failed comparison in terms an operator can act on."""
    parts: list[str] = []
    if len(actual) != len(committed):
        parts.append(
            f"membership records {len(actual)} tasks but the commitment names "
            f"{len(committed)}"
        )
    if mismatch is not None:
        position, left, right = mismatch
        parts.append(
            f"first difference at position {position}: "
            f"recorded {left or 'nothing'}, committed {right or 'nothing'}"
        )
    return "; ".join(parts)
