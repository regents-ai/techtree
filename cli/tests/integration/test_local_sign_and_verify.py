"""A real run signs itself, and the proof checks out offline.

Spec sections 7.5, 7.11 and 7.12; decisions document 0005 section 3.4.

The run is the same one ``test_real_result_to_report`` drives: a real catalog, a
real draft, a real staged run, and the two paid probes' own evidence replayed
where a finished evaluation would have left it. What is added here is the half
WP7c owns — the key, the envelopes, the bundle, and a verification that reads
nothing but the bytes the run wrote.

The claim being made is bounded and worth stating exactly. A verified bundle
says these files have not changed since the participant's own key signed them,
and that they agree with each other and with the report's numbers. It does not
say who ran the evaluation, and nobody else has reproduced it.
"""

from __future__ import annotations

import json
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from fixtures.receipts.staged import (
    RecordedEvidenceExecutor,
    StagedRecordedRun,
    staged_recorded_run,
)
from techtree.canonical import canonical_json_bytes, digest_object
from techtree.identity.service import verify_signed_object
from techtree.identity.store import IdentityStore
from techtree.models.base import ObjectEnvelope
from techtree.models.episode_receipt import EpisodeReceipt
from techtree.models.experiment import ExperimentVariant
from techtree.models.uplift_report import UpliftDecision, UpliftReport
from techtree.receipts.bundle import (
    BUNDLE_MANIFEST_FILENAME,
    P1_CONDITIONS,
    PUBLIC_IDENTITY_FILENAME,
    REPORT_FILENAME,
    LocalProofBundleManifest,
    proof_bundle_dir,
    receipt_filename,
)
from techtree.receipts.execution import (
    EXECUTION_RECORD_FILENAME,
    ComparisonExecutionRecord,
    CostProvenance,
    PairOutcome,
    UsageProvenance,
    read_execution_record,
)
from techtree.receipts.verify import LocalProofVerifier, verify_local_bundle
from techtree.runs.validation import PublisherFixtureValidationProvider
from techtree.worker.execute import execute_run

pytestmark = pytest.mark.integration


def completed_run(home: Path) -> StagedRecordedRun:
    """Drive one real run to completion over the recorded evidence."""
    run = staged_recorded_run(home)
    exit_code = execute_run(
        run.run_id,
        paths=run.paths,
        executor_factory=lambda request: RecordedEvidenceExecutor(
            pair=run.pair, paths=run.paths
        ),
        validation_provider_factory=lambda request: (
            PublisherFixtureValidationProvider()
        ),
    )
    assert exit_code == 0
    return run


@pytest.fixture
def run(tmp_path: Path) -> StagedRecordedRun:
    return completed_run(tmp_path / "home")


def bundle_of(run: StagedRecordedRun) -> Path:
    return proof_bundle_dir(run.paths.run_dir(run.run_id))


def report_of(run: StagedRecordedRun) -> UpliftReport:
    return UpliftReport.model_validate_json(
        run.run_store.result_path(run.run_id).read_bytes()
    )


def rewrite(path: Path, mutate: Callable[[dict[str, Any]], None]) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    path.write_bytes(canonical_json_bytes(document))


# ---------------------------------------------------------------------------
# The run signs itself
# ---------------------------------------------------------------------------


def test_the_run_creates_a_local_identity_and_keeps_it_private(
    run: StagedRecordedRun,
) -> None:
    store = IdentityStore(run.paths)

    assert store.exists() is True
    assert store.verify_pair() is True
    assert stat.S_IMODE(store.private_key_path.stat().st_mode) == 0o600


def test_a_signed_run_reaches_p1_and_states_a_verdict(
    run: StagedRecordedRun,
) -> None:
    """The one argument WP7b left: signed evidence turns the verdict on."""
    report = report_of(run)

    assert report.proof_grade == "P1"
    assert report.decision is UpliftDecision.ACCEPTED
    assert report.statuses.publication.value == "not_requested"
    assert report.publication_eligible is False


def test_every_receipt_travels_signed(run: StagedRecordedRun) -> None:
    bundle = bundle_of(run)
    identity = LocalProofBundleManifest.model_validate_json(
        json.dumps(
            json.loads((bundle / BUNDLE_MANIFEST_FILENAME).read_text())["payload"]
        )
    ).executor_identity

    for variant in (ExperimentVariant.BASELINE, ExperimentVariant.CANDIDATE):
        for position in range(2):
            envelope = ObjectEnvelope[EpisodeReceipt].model_validate_json(
                (bundle / receipt_filename(variant, position)).read_bytes()
            )
            assert envelope.signature is not None
            assert verify_signed_object(identity=identity, envelope=envelope).verified


def test_the_report_in_the_bundle_is_the_report_the_run_recorded(
    run: StagedRecordedRun,
) -> None:
    sealed = ObjectEnvelope[UpliftReport].model_validate_json(
        (bundle_of(run) / REPORT_FILENAME).read_bytes()
    )

    assert sealed.payload == report_of(run)
    assert sealed.payload_digest == digest_object(report_of(run))
    assert run.run_store.state(run.run_id).result_digest == sealed.payload_digest


# ---------------------------------------------------------------------------
# The proof verifies offline
# ---------------------------------------------------------------------------


def test_the_bundle_verifies_from_the_bytes_the_run_wrote(
    run: StagedRecordedRun,
) -> None:
    result = verify_local_bundle(bundle_of(run))

    assert result.verified is True
    assert result.failures == []


def test_every_section_3_4_condition_is_established_by_the_stored_bytes(
    run: StagedRecordedRun,
) -> None:
    result = verify_local_bundle(bundle_of(run))
    conditions = {
        message.id.removeprefix("p1."): message.status
        for message in result.messages
        if message.id.startswith("p1.")
    }

    assert all(conditions[condition] == "passed" for condition in P1_CONDITIONS)


def test_the_bundle_verifies_after_being_copied_somewhere_else(
    run: StagedRecordedRun, tmp_path: Path
) -> None:
    """Portable: nothing in a proof depends on the machine that made it."""
    import shutil

    elsewhere = tmp_path / "carried-away"
    shutil.copytree(bundle_of(run), elsewhere)

    assert verify_local_bundle(elsewhere).verified is True


def test_a_verified_run_still_says_it_was_not_independently_reproduced(
    run: StagedRecordedRun,
) -> None:
    summary = LocalProofVerifier().explain(verify_local_bundle(bundle_of(run)))
    by_id = {message.id: message for message in summary}

    assert by_id["participant_attestation"].status == "passed"
    assert by_id["independent_reproduction"].status == "warning"
    assert "integrity-bound, participant-attested local execution" in (
        by_id["participant_attestation"].detail
    )


# ---------------------------------------------------------------------------
# Tampering with what the run wrote
# ---------------------------------------------------------------------------


def test_editing_a_receipt_after_the_run_is_detected(
    run: StagedRecordedRun,
) -> None:
    path = bundle_of(run) / receipt_filename(ExperimentVariant.BASELINE, 0)
    rewrite(
        path,
        lambda document: document["payload"]["named_traces"]["subject"][0][
            "rewards"
        ].update({"exact_match": 1.0}),
    )

    assert verify_local_bundle(bundle_of(run)).verified is False


def test_editing_the_report_after_the_run_is_detected(
    run: StagedRecordedRun,
) -> None:
    rewrite(
        bundle_of(run) / REPORT_FILENAME,
        lambda document: document["payload"]["primary_result"].update(
            {"absolute_delta": 99.0}
        ),
    )

    assert verify_local_bundle(bundle_of(run)).verified is False


def test_removing_the_public_key_leaves_nothing_to_check_against(
    run: StagedRecordedRun,
) -> None:
    (bundle_of(run) / PUBLIC_IDENTITY_FILENAME).unlink()

    assert verify_local_bundle(bundle_of(run)).verified is False


def test_the_private_key_is_nowhere_in_the_run_directory(
    run: StagedRecordedRun,
) -> None:
    """It lives in the identities directory and is never copied out of it."""
    secret = IdentityStore(run.paths).private_key_path.read_bytes()

    for path in run.paths.run_dir(run.run_id).rglob("*"):
        if path.is_file():
            assert secret not in path.read_bytes()


def test_two_runs_on_one_machine_share_the_same_identity(tmp_path: Path) -> None:
    home = tmp_path / "home"
    first = completed_run(home)
    second = completed_run(home)

    identity = IdentityStore(first.paths).load_public()

    assert verify_local_bundle(bundle_of(first)).verified is True
    assert verify_local_bundle(bundle_of(second)).verified is True
    assert (
        LocalProofBundleManifest.model_validate_json(
            json.dumps(
                json.loads((bundle_of(second) / BUNDLE_MANIFEST_FILENAME).read_text())[
                    "payload"
                ]
            )
        ).executor_identity
        == identity
    )


# ---------------------------------------------------------------------------
# The comparison's operational record. Decisions document 0007 R6+R8.
# ---------------------------------------------------------------------------


def test_a_real_run_signs_an_execution_record_into_its_proof(
    run: StagedRecordedRun,
) -> None:
    """The record is written by the run, signed by the run's own key.

    It describes the same comparison the report does, and its numbers come
    from the run's own evidence: the child processes' recorded start and
    finish, and the token usage the engine's normalized traces carry.
    """
    bundle = bundle_of(run)
    envelope = ObjectEnvelope[ComparisonExecutionRecord].model_validate_json(
        (bundle / EXECUTION_RECORD_FILENAME).read_bytes()
    )
    record = envelope.payload
    identity = IdentityStore(run.paths).load_public()

    assert verify_signed_object(
        identity=identity, envelope=envelope, subject="execution-record"
    ).verified
    assert record.run_id == run.run_id
    assert record.campaign_spec_digest == report_of(run).campaign_spec_digest
    assert record.execution_backend == "verifiers"
    assert record.baseline.elapsed_seconds > 0.0
    assert record.candidate.elapsed_seconds > 0.0
    assert record.outcome is PairOutcome.COMPLETED
    # The recorded probes carry real usage, so the record carries real totals.
    assert record.baseline.usage.provenance is UsageProvenance.NORMALIZED_TRACES
    assert record.baseline.usage.total_tokens is not None
    assert record.baseline.usage.traces_with_usage == (
        record.baseline.usage.traces_total
    )


def test_a_real_runs_record_reports_no_cost_and_says_why(
    run: StagedRecordedRun,
) -> None:
    """Decisions 0007 R6: no price feed, so no figure, and no pretending."""
    record = read_execution_record(bundle_of(run))
    assert record is not None

    assert record.baseline.cost.provenance is CostProvenance.UNAVAILABLE
    assert record.baseline.cost.cost_usd is None
    assert record.total_cost.provenance is CostProvenance.UNAVAILABLE
    assert record.total_cost.cost_usd is None


def test_the_record_is_in_the_signed_index_and_verified_with_the_bundle(
    run: StagedRecordedRun,
) -> None:
    """Nothing binds a record to a run except the manifest that names it."""
    bundle = bundle_of(run)
    manifest = (
        ObjectEnvelope[LocalProofBundleManifest]
        .model_validate_json((bundle / BUNDLE_MANIFEST_FILENAME).read_bytes())
        .payload
    )

    assert manifest.artifact(EXECUTION_RECORD_FILENAME) is not None
    result = verify_local_bundle(bundle)
    assert result.verified
    assert [
        message.status
        for message in result.messages
        if message.id.startswith("execution_record.")
    ] == ["passed", "passed"]


def test_an_edited_record_fails_the_runs_own_proof(run: StagedRecordedRun) -> None:
    """The operational record is held to the same standard as the rest.

    The edited field is the pair's elapsed time, which the two recorded probes
    make plainly non-zero: they ran back to back rather than side by side, so
    the overlap this fixture records is a true zero and rewriting it to zero
    would change no bytes at all.
    """
    bundle = bundle_of(run)
    rewrite(
        bundle / EXECUTION_RECORD_FILENAME,
        lambda document: document["payload"].update({"elapsed_seconds": 0.0}),
    )

    result = verify_local_bundle(bundle)

    assert not result.verified
    assert f"artifact.{EXECUTION_RECORD_FILENAME}" in [
        message.id for message in result.failures
    ]
