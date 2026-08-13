"""The taskset validation seam. Spec PR8 §8.4, §8.17.

Two things are being protected. The provider must be *careful about what it
claims*: it re-checks a commitment somebody else made and says so, rather than
presenting it as a validation this machine performed. And it must be
*fail-closed*: a receipt that does not verify, a lock that cannot be derived,
and a build with no provider wired all stop the run instead of letting a score
be computed against an unvalidated taskset.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from fixtures.runs.support import RunHarness, run_harness
from techtree.canonical import digest_object
from techtree.errors import PrerequisiteError, VerificationError
from techtree.runs.artifacts import RunInputBundle
from techtree.runs.validation import (
    PublisherFixtureValidationProvider,
    TasksetValidationOutcome,
    TasksetValidationSource,
    UnconfiguredTasksetValidationProvider,
    derive_taskset_lock,
)


@pytest.fixture
def inputs(temp_techtree_home: Path) -> tuple[RunHarness, str, RunInputBundle]:
    """Return staged run inputs to validate."""
    harness = run_harness(temp_techtree_home)
    run_id = harness.start().state.run_id
    return harness, run_id, harness.inputs(run_id)


def _outcome(run_id: str, bundle: RunInputBundle) -> TasksetValidationOutcome:
    return PublisherFixtureValidationProvider().validate(run_id=run_id, inputs=bundle)


# ---------------------------------------------------------------------------
# What the development provider claims
# ---------------------------------------------------------------------------


def test_the_publisher_fixture_says_where_its_answer_came_from(
    inputs: tuple[RunHarness, str, RunInputBundle],
) -> None:
    _, run_id, bundle = inputs

    outcome = _outcome(run_id, bundle)

    assert outcome.source is TasksetValidationSource.PUBLISHER_FIXTURE
    assert outcome.execution_record is None
    assert outcome.receipt == bundle.resolved_climb.publisher_validation


def test_the_derived_lock_is_the_one_the_receipt_was_issued_under(
    inputs: tuple[RunHarness, str, RunInputBundle],
) -> None:
    _, run_id, bundle = inputs

    outcome = _outcome(run_id, bundle)

    assert digest_object(outcome.lock) == outcome.receipt.taskset_lock_digest
    assert outcome.lock.ordered_task_hashes == bundle.ordered_task_hashes
    assert outcome.lock.task_count == len(bundle.ordered_task_hashes)


def test_the_marker_carries_the_source_and_no_invented_execution(
    inputs: tuple[RunHarness, str, RunInputBundle],
) -> None:
    _, run_id, bundle = inputs

    marker = _outcome(run_id, bundle).marker_document()

    assert marker["source"] == "publisher_fixture"
    assert marker["execution_record"] is None
    assert marker["receipt_digest"] == digest_object(
        bundle.resolved_climb.publisher_validation
    )


# ---------------------------------------------------------------------------
# Failing closed
# ---------------------------------------------------------------------------


def test_a_receipt_the_campaign_does_not_commit_to_is_refused(
    inputs: tuple[RunHarness, str, RunInputBundle],
) -> None:
    _, run_id, bundle = inputs
    resolved = bundle.resolved_climb
    other = resolved.publisher_validation.model_copy(update={"status": "invalid"})
    tampered = dataclasses.replace(
        bundle,
        resolved_climb=resolved.model_copy(
            update={
                "publisher_validation": other,
                "publisher_validation_digest": digest_object(other),
            }
        ),
    )

    with pytest.raises(VerificationError) as raised:
        _outcome(run_id, tampered)

    assert raised.value.code == "taskset_validation_invalid"


def test_a_receipt_that_reports_invalid_stops_the_run(
    inputs: tuple[RunHarness, str, RunInputBundle],
) -> None:
    """The Campaign commits to it, and it still says the taskset is not valid."""
    _, run_id, bundle = inputs
    resolved = bundle.resolved_climb
    receipt = resolved.publisher_validation.model_copy(update={"status": "errored"})
    campaign = resolved.campaign.model_copy(
        update={
            "taskset": resolved.campaign.taskset.model_copy(
                update={"validation_receipt_digest": digest_object(receipt)}
            )
        }
    )
    tampered = dataclasses.replace(
        bundle,
        resolved_climb=resolved.model_copy(
            update={
                "publisher_validation": receipt,
                "publisher_validation_digest": digest_object(receipt),
                "campaign": campaign,
                "campaign_digest": digest_object(campaign),
            }
        ),
    )

    with pytest.raises(VerificationError) as raised:
        _outcome(run_id, tampered)

    assert raised.value.code == "taskset_validation_invalid"
    assert "errored" in str(raised.value)


def test_a_lock_that_does_not_reproduce_the_commitment_is_refused(
    inputs: tuple[RunHarness, str, RunInputBundle],
) -> None:
    """A derivation is only a proof while it reproduces the committed digest."""
    _, run_id, bundle = inputs
    resolved = bundle.resolved_climb
    receipt = resolved.publisher_validation.model_copy(
        update={"engine_digest": f"sha256:{'b' * 64}"}
    )
    campaign = resolved.campaign.model_copy(
        update={
            "taskset": resolved.campaign.taskset.model_copy(
                update={"validation_receipt_digest": digest_object(receipt)}
            )
        }
    )
    tampered = dataclasses.replace(
        bundle,
        resolved_climb=resolved.model_copy(
            update={
                "publisher_validation": receipt,
                "publisher_validation_digest": digest_object(receipt),
                "campaign": campaign,
                "campaign_digest": digest_object(campaign),
            }
        ),
    )

    assert digest_object(derive_taskset_lock(run_id, tampered)) != (
        receipt.taskset_lock_digest
    )
    with pytest.raises(VerificationError) as raised:
        _outcome(run_id, tampered)

    assert raised.value.code == "taskset_validation_invalid"


def test_evidence_that_is_not_what_the_receipt_names_is_refused(
    inputs: tuple[RunHarness, str, RunInputBundle],
) -> None:
    _, run_id, bundle = inputs
    evidence = bundle.validation_evidence
    tampered = dataclasses.replace(
        bundle,
        validation_evidence=evidence.model_copy(
            update={"taskset_lock_digest": f"sha256:{'c' * 64}"}
        ),
    )

    with pytest.raises(VerificationError) as raised:
        _outcome(run_id, tampered)

    assert raised.value.code == "taskset_validation_invalid"


def test_an_unconfigured_build_refuses_to_validate_anything(
    inputs: tuple[RunHarness, str, RunInputBundle],
) -> None:
    _, run_id, bundle = inputs

    with pytest.raises(PrerequisiteError) as raised:
        UnconfiguredTasksetValidationProvider().validate(run_id=run_id, inputs=bundle)

    assert raised.value.code == "taskset_validation_provider_unavailable"


def test_the_run_layer_depends_on_no_future_taskset_service() -> None:
    """Spec §8.4: PR12 replaces the provider; PR8 must not reach for it."""
    runs = Path(__file__).resolve().parents[2] / "src" / "techtree" / "runs"

    for name in ("artifacts", "executor", "fake", "launcher", "service", "validation"):
        source = (runs / f"{name}.py").read_text(encoding="utf-8")
        assert "LocalVerifiersValidationProvider" not in source
        assert "import verifiers" not in source
        assert "techtree.engines" not in source

    # The enum already names the source PR12 will add, so introducing it is a
    # new provider class and not a protocol change.
    assert TasksetValidationSource.LOCAL_VERIFIERS.value == "local_verifiers"
