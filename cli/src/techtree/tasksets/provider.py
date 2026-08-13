"""Answering a run's validation question with a real Verifiers run.

Spec section 21.5, decisions document 0003 A1.

:class:`~techtree.runs.validation.PublisherFixtureValidationProvider` re-reads a
commitment somebody else made. This one does the work: it resolves the
Campaign's taskset against the managed engine, runs the pinned model-free
validation over every task, has the engine normalize the result, and issues a
receipt of its own.

Then it compares. Because the receipt is deterministic, "did this machine reach
the same conclusion as the publisher?" is answerable by equality rather than by
narrative: the local receipt's content digest must be exactly the digest the
Campaign commits to. Anything less would be two documents that merely resemble
each other.

The engine is not chosen locally. It is the engine the publisher's receipt was
issued under, so a disagreement between the two receipts can only ever be a
disagreement about the taskset — never about which Verifiers build ran.

:func:`worker_validation_provider` is the routing this build performs, and it
routes on a capability rather than on a preference. A Campaign whose taskset
lives in a package the engine bundle ships can be validated here, for real. A
Campaign whose taskset lives anywhere else cannot be — this build has no way to
obtain that package — and the only source left is the publisher's snapshotted
commitment, which the fake executor may use because everything it produces is
marked development-only. The run's validation marker records which of the two
spoke, so the difference is never invisible.
"""

from __future__ import annotations

from typing import Final

from techtree.canonical import digest_object
from techtree.engines.bundle import default_engine_descriptor
from techtree.engines.registry import EngineRegistry
from techtree.errors import PrerequisiteError, VerificationError
from techtree.models.base import Digest, JsonValue
from techtree.models.campaign import CampaignSpec
from techtree.paths import TechtreePaths
from techtree.runs.artifacts import RunInputBundle
from techtree.runs.validation import (
    TASKSET_VALIDATION_INVALID,
    PublisherFixtureValidationProvider,
    TasksetValidationOutcome,
    TasksetValidationProvider,
    TasksetValidationSource,
)
from techtree.settings import resolved_settings
from techtree.tasksets.service import TasksetService

__all__ = [
    "ENGINE_NOT_INSTALLED",
    "LocalVerifiersValidationProvider",
    "can_validate_locally",
    "locally_validatable_packages",
    "worker_validation_provider",
]

#: What a run reports when the engine its Campaign was validated under is not
#: installed on this machine. Local validation has no substitute, so this is a
#: prerequisite the operator can satisfy rather than a failure of the run.
ENGINE_NOT_INSTALLED: Final = "engine_not_installed"


def locally_validatable_packages() -> frozenset[str]:
    """Return the taskset packages this build can validate for itself.

    A package inside the engine bundle is one this machine already has the
    source of. Every other package would have to be fetched from somewhere,
    which WP0–WP5 does not do.
    """
    return frozenset(package.name for package in default_engine_descriptor().packages)


def can_validate_locally(campaign: CampaignSpec) -> bool:
    """Return whether this build ships the package this Campaign's taskset needs."""
    package = campaign.taskset.ref.package
    return package.kind == "embedded" and package.name in locally_validatable_packages()


class LocalVerifiersValidationProvider:
    """Validates a run's taskset here, with the pinned Verifiers build."""

    def __init__(self, paths: TechtreePaths) -> None:
        self._paths = paths

    def validate(
        self,
        *,
        run_id: str,
        inputs: RunInputBundle,
    ) -> TasksetValidationOutcome:
        """Run the real validation and require it to agree with the publisher."""
        campaign = inputs.campaign
        publisher = inputs.resolved_climb.publisher_validation
        committed_receipt_digest = campaign.taskset.validation_receipt_digest

        service = TasksetService(
            self._require_engine(run_id, publisher.engine_digest),
            publisher.engine_digest,
        )
        result = service.resolve_and_validate(
            campaign=campaign,
            run_dir=self._paths.run_dir(run_id),
        )
        receipt = result.receipt

        _require(
            receipt.status == "valid",
            f"validating this taskset here reported {receipt.status}, so "
            "nothing may be scored on it",
            run_id,
            status=receipt.status,
            failed_checks=[
                check.id for check in receipt.checks if check.status == "failed"
            ],
        )
        _require(
            receipt.taskset_lock_digest == publisher.taskset_lock_digest,
            "the taskset this machine locked is not the one the publisher's "
            "receipt was issued under",
            run_id,
            local=receipt.taskset_lock_digest,
            published=publisher.taskset_lock_digest,
        )
        _require(
            result.receipt_digest == committed_receipt_digest,
            "validating this taskset here did not reproduce the receipt the "
            "Campaign commits to",
            run_id,
            local=result.receipt_digest,
            committed=committed_receipt_digest,
        )
        _require(
            digest_object(result.evidence) == digest_object(inputs.validation_evidence),
            "the evidence this machine produced is not the evidence the Campaign ships",
            run_id,
        )

        return TasksetValidationOutcome(
            lock=result.lock,
            receipt=receipt,
            execution_record=result.execution_record,
            source=TasksetValidationSource.LOCAL_VERIFIERS,
        )

    def _require_engine(self, run_id: str, engine_digest: Digest) -> EngineRegistry:
        """Return the registry, having checked this engine is usable here."""
        registry = EngineRegistry(self._paths, resolved_settings(self._paths))
        installation = registry.installation(engine_digest)
        if installation is None or not installation.verified:
            raise PrerequisiteError(
                f"engine {engine_digest} is not installed and verified here, so "
                "this taskset cannot be validated locally",
                code=ENGINE_NOT_INSTALLED,
                details={"run_id": run_id, "engine_digest": engine_digest},
            )
        return registry


def worker_validation_provider(paths: TechtreePaths) -> TasksetValidationProvider:
    """Return the validation source available to a run on this machine.

    The decision cannot be made from a
    :class:`~techtree.models.run.RunRequest` alone — nothing in a request names
    the taskset's package — so the routing lives in a provider that reads the
    run's own inputs and then delegates. Both destinations are permanent: one
    is what a real Campaign gets, the other is the development source spec
    §21.5 leaves the fake executor.
    """
    return _AvailableValidationProvider(paths)


class _AvailableValidationProvider:
    """Delegates to whichever validation source this Campaign actually has."""

    def __init__(self, paths: TechtreePaths) -> None:
        self._paths = paths

    def validate(
        self,
        *,
        run_id: str,
        inputs: RunInputBundle,
    ) -> TasksetValidationOutcome:
        """Validate locally when this build ships the taskset's package."""
        if can_validate_locally(inputs.campaign):
            return LocalVerifiersValidationProvider(self._paths).validate(
                run_id=run_id, inputs=inputs
            )
        return PublisherFixtureValidationProvider().validate(
            run_id=run_id, inputs=inputs
        )


def _require(condition: bool, message: str, run_id: str, **details: object) -> None:
    """Raise a typed validation failure unless the condition holds."""
    if condition:
        return
    reported: dict[str, JsonValue] = {"run_id": run_id}
    for key, value in details.items():
        reported[key] = (
            [str(item) for item in value] if isinstance(value, list) else str(value)
        )
    raise VerificationError(message, code=TASKSET_VALIDATION_INVALID, details=reported)
