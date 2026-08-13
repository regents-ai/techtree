"""Where a run's taskset validation comes from. Spec PR8 §8.4.

An executor has to know that the taskset it is about to score is the taskset
the Campaign committed to, and that somebody mechanically validated it. Who
answers that question changes over the life of the product: today it is the
publisher's own receipt, snapshotted into the draft and re-checked offline;
later it is a local Verifiers run that recomputes the same receipt on the
participant's machine.

This module is the seam between the two. The executor depends on
:class:`TasksetValidationProvider` and nothing else, so the later change
replaces one object at wiring time and touches no run lifecycle code.

:class:`PublisherFixtureValidationProvider` is the development answer. It is
careful about what it claims: it verifies the snapshotted publisher commitment
and says so — ``source = publisher_fixture``, ``execution_record = None`` —
rather than presenting a re-read commitment as a validation this machine
performed. Nothing downstream is entitled to treat it as one, which is
consistent with the fake executor's reports being development-only throughout.

The lock the receipt was issued under is not shipped in the public catalog;
only its digest is. The provider therefore *derives* the lock from what the
draft does carry — the Campaign's taskset reference and committed membership,
and the receipt's engine digest — and requires the derived lock to digest to
exactly the value the receipt names. A derivation that does not reproduce the
committed digest is a failure, never a warning.

:class:`UnconfiguredTasksetValidationProvider` is the fail-closed default for
any wiring that has no provider yet. It answers every request with
``taskset_validation_provider_unavailable``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final, NoReturn, Protocol

from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import digest_object, to_json_value
from techtree.constants import TASKSET_LOCK_SCHEMA_VERSION
from techtree.errors import PrerequisiteError, VerificationError
from techtree.models.base import JsonValue
from techtree.models.validation import (
    TasksetLock,
    TasksetValidationReceipt,
    ValidationExecutionRecord,
)
from techtree.runs.artifacts import (
    VALIDATION_MARKER_SCHEMA_VERSION,
    RunInputBundle,
)

__all__ = [
    "TASKSET_VALIDATION_INVALID",
    "TASKSET_VALIDATION_PROVIDER_UNAVAILABLE",
    "PublisherFixtureValidationProvider",
    "TasksetValidationOutcome",
    "TasksetValidationProvider",
    "TasksetValidationSource",
    "UnconfiguredTasksetValidationProvider",
    "derive_taskset_lock",
]

#: Stable error codes. Spec PR8 §8.16.
TASKSET_VALIDATION_INVALID: Final = "taskset_validation_invalid"
TASKSET_VALIDATION_PROVIDER_UNAVAILABLE: Final = (
    "taskset_validation_provider_unavailable"
)


class TasksetValidationSource(StrEnum):
    """Where a validation outcome came from."""

    PUBLISHER_FIXTURE = "publisher_fixture"
    LOCAL_VERIFIERS = "local_verifiers"


@dataclass(frozen=True)
class TasksetValidationOutcome:
    """The validation artifacts an executor needs, and their provenance."""

    lock: TasksetLock
    receipt: TasksetValidationReceipt
    execution_record: ValidationExecutionRecord | None
    source: TasksetValidationSource

    def marker_document(self) -> dict[str, JsonValue]:
        """Return the JSON projection persisted beside the run.

        The source is carried explicitly so that a reader of a run directory
        can tell a re-checked publisher commitment from a locally executed
        validation without inferring it from which fields are absent.
        """
        return {
            "schema_version": VALIDATION_MARKER_SCHEMA_VERSION,
            "source": self.source.value,
            "lock": to_json_value(self.lock),
            "lock_digest": digest_object(self.lock),
            "receipt": to_json_value(self.receipt),
            "receipt_digest": digest_object(self.receipt),
            "execution_record": (
                None
                if self.execution_record is None
                else to_json_value(self.execution_record)
            ),
        }


class TasksetValidationProvider(Protocol):
    """Answers what a run may assume about its taskset's validation."""

    def validate(
        self,
        *,
        run_id: str,
        inputs: RunInputBundle,
    ) -> TasksetValidationOutcome:
        """Return the validation artifacts required by the executor."""
        ...


class PublisherFixtureValidationProvider:
    """Re-checks the snapshotted publisher commitment. Development only.

    It does not claim to have rerun validation locally, and it never
    fabricates a :class:`~techtree.models.validation.ValidationExecutionRecord`
    for work that did not happen.
    """

    def validate(
        self,
        *,
        run_id: str,
        inputs: RunInputBundle,
    ) -> TasksetValidationOutcome:
        """Verify the publisher's receipt and return it as this run's outcome."""
        campaign = inputs.campaign
        resolved = inputs.resolved_climb
        receipt = resolved.publisher_validation

        _require(
            resolved.publisher_validation_digest
            == campaign.taskset.validation_receipt_digest,
            "the publisher validation receipt this run owns is not the one the "
            "Campaign commits to",
            run_id,
        )

        reference = receipt.normalized_evidence
        _require(
            reference is not None
            and reference.digest == digest_object(inputs.validation_evidence),
            "the normalized evidence this run owns is not what the publisher's "
            "receipt was issued from",
            run_id,
        )

        _require(
            receipt.status == "valid",
            f"the publisher's validation receipt reports {receipt.status}, so "
            "this taskset is not fit to be scored",
            run_id,
            status=receipt.status,
        )

        lock = derive_taskset_lock(run_id, inputs)
        _require(
            digest_object(lock) == receipt.taskset_lock_digest,
            "the taskset lock derived from this Campaign is not the lock the "
            "publisher's receipt was issued under",
            run_id,
        )
        _require(
            lock.ordered_task_hashes
            == list(campaign.taskset.membership.ordered_task_hashes)
            and lock.membership_digest == campaign.taskset.membership.membership_digest
            and lock.task_count == campaign.taskset.selection.num_tasks,
            "the locked task membership is not the membership the Campaign commits to",
            run_id,
        )
        _require(
            inputs.validation_evidence.taskset_lock_digest
            == receipt.taskset_lock_digest,
            "the normalized evidence was produced under a different taskset "
            "lock than the receipt",
            run_id,
        )

        return TasksetValidationOutcome(
            lock=lock,
            receipt=receipt,
            execution_record=None,
            source=TasksetValidationSource.PUBLISHER_FIXTURE,
        )


class UnconfiguredTasksetValidationProvider:
    """The fail-closed provider for a build with no validation source wired."""

    def validate(
        self,
        *,
        run_id: str,
        inputs: RunInputBundle,
    ) -> NoReturn:
        """Refuse to let a run proceed without a validation source."""
        raise PrerequisiteError(
            "this build has no taskset validation source configured, so no run "
            "may claim its taskset was validated",
            code=TASKSET_VALIDATION_PROVIDER_UNAVAILABLE,
            details={"run_id": run_id},
        )


def derive_taskset_lock(run_id: str, inputs: RunInputBundle) -> TasksetLock:
    """Rebuild the lock the publisher's receipt was issued under.

    Every field comes from something the run already owns and has verified:
    the taskset reference and committed membership from the Campaign, and the
    engine digest from the receipt. The caller checks the result against the
    digest the receipt names, which is what makes the derivation a proof
    rather than a guess.
    """
    campaign = inputs.campaign
    receipt = inputs.resolved_climb.publisher_validation
    membership = campaign.taskset.membership

    try:
        return TasksetLock(
            schema_version=TASKSET_LOCK_SCHEMA_VERSION,
            taskset_ref=campaign.taskset.ref,
            engine_digest=receipt.engine_digest,
            resolved_package_digest=campaign.taskset.ref.package.digest,
            ordered_task_hashes=list(membership.ordered_task_hashes),
            membership_digest=membership.membership_digest,
            task_count=len(membership.ordered_task_hashes),
        )
    except PydanticValidationError as error:
        raise VerificationError(
            "no taskset lock can be derived from this Campaign: "
            f"{error.errors()[0]['msg']}",
            code=TASKSET_VALIDATION_INVALID,
            details={"run_id": run_id},
        ) from error


def _require(condition: bool, message: str, run_id: str, **details: str) -> None:
    """Raise a typed validation failure unless the condition holds."""
    if condition:
        return
    reported: dict[str, JsonValue] = {"run_id": run_id}
    reported.update(details)
    raise VerificationError(
        message,
        code=TASKSET_VALIDATION_INVALID,
        details=reported,
    )
