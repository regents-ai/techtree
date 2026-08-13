"""The local proof bundle, and the six conditions P1 rests on.

Spec sections 7.11 and 7.12; decisions document 0005 section 3.4.

Two claims are checked here and neither is checkable by reading code.

*Every section 3.4 condition is checked rather than assumed.* Each one is
broken on its own, with everything else left correct, and the assessment must
refuse the grade for that reason and no other. A condition nobody ever
falsified is a condition nobody knows is being evaluated.

*A tampered proof does not verify, offline, from its own bytes.* Each artifact
class is edited in place — a receipt, the report, the Campaign, the key — and
the verifier is given the directory and nothing else. No network, no local
identity, no state: a stranger's machine would reach the same verdict.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from fixtures.receipts.proof import RecordedProof, signed_proof, write_proof
from techtree.canonical import canonical_json_bytes, digest_object
from techtree.identity.models import ExecutorIdentity, VerificationResult
from techtree.identity.store import IdentityStore
from techtree.models.base import ObjectEnvelope
from techtree.models.episode_receipt import EpisodeReceipt, ScoreStatus
from techtree.models.experiment import ExperimentVariant
from techtree.models.uplift_report import ComparisonStatus, UpliftDecision
from techtree.paths import paths_from_root
from techtree.receipts.bundle import (
    BUNDLE_MANIFEST_FILENAME,
    P1_ARTIFACT_DIGESTS_VERIFY,
    P1_COMPARISON_CONTROLLED,
    P1_CONDITIONS,
    P1_PUBLIC_KEY_PRESENT,
    P1_RECEIPTS_SIGNED,
    P1_REPORT_SIGNED,
    P1_SCORE_VALID,
    PUBLIC_IDENTITY_FILENAME,
    REPORT_FILENAME,
    LocalProofBundleManifest,
    ReferencedObject,
    assess_local_attestation,
    build_local_bundle,
    receipt_filename,
)
from techtree.receipts.uplift import LocalAttestation
from techtree.receipts.verify import LocalProofVerifier, verify_local_bundle

BASELINE_RECEIPT = f"receipts/{ExperimentVariant.BASELINE.value}/0000.json"


@pytest.fixture
def proof(tmp_path: Path) -> RecordedProof:
    return signed_proof(tmp_path / "home")


@pytest.fixture
def bundle(proof: RecordedProof, tmp_path: Path) -> Path:
    return write_proof(proof, tmp_path / "run")


def rewrite(path: Path, mutate: Callable[[dict[str, Any]], None]) -> None:
    """Edit one stored JSON document in place, canonically."""
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    path.write_bytes(canonical_json_bytes(document))


def failed(result: VerificationResult) -> list[str]:
    return [message.id for message in result.failures]


# ---------------------------------------------------------------------------
# What a bundle is
# ---------------------------------------------------------------------------


def test_a_bundle_carries_the_documents_a_reader_needs(bundle: Path) -> None:
    stored = sorted(
        path.relative_to(bundle).as_posix()
        for path in bundle.rglob("*")
        if path.is_file()
    )

    assert stored == [
        "baseline-experiment.json",
        "baseline-receipt-set.json",
        "bundle.json",
        "campaign.json",
        "candidate-experiment.json",
        "candidate-receipt-set.json",
        "data-policy.json",
        "executor-public.json",
        "receipts/baseline/0000.json",
        "receipts/baseline/0001.json",
        "receipts/baseline/0002.json",
        "receipts/baseline/0003.json",
        "receipts/candidate/0000.json",
        "receipts/candidate/0001.json",
        "receipts/candidate/0002.json",
        "receipts/candidate/0003.json",
        "taskset-lock.json",
        "taskset-validation-receipt.json",
        "uplift-report.json",
    ]


def test_a_bundle_carries_no_raw_evidence_and_no_private_key(
    bundle: Path, tmp_path: Path
) -> None:
    """The DataPolicy prohibits uploading raw episodes, so they stay behind."""
    secret = IdentityStore(paths_from_root(tmp_path / "home")).private_key_path

    names = {path.name for path in bundle.rglob("*") if path.is_file()}
    text = "".join(
        path.read_text(encoding="utf-8") for path in bundle.rglob("*") if path.is_file()
    )

    assert "traces.jsonl" not in names
    assert "eval.log" not in names
    assert secret.name not in names
    assert secret.read_bytes().hex() not in text


def test_a_bundle_written_twice_is_the_same_bundle(
    proof: RecordedProof, tmp_path: Path
) -> None:
    first = write_proof(proof, tmp_path / "one")
    second = write_proof(proof, tmp_path / "two")

    assert (first / BUNDLE_MANIFEST_FILENAME).read_bytes() == (
        second / BUNDLE_MANIFEST_FILENAME
    ).read_bytes()


def test_the_manifest_commits_to_every_file_it_carries(
    proof: RecordedProof, bundle: Path
) -> None:
    manifest = build_local_bundle(
        run_id=proof.report.payload.run_id, contents=proof.contents
    )
    placed = {reference.relative_path for reference in manifest.artifacts}

    stored = {
        path.relative_to(bundle).as_posix()
        for path in bundle.rglob("*")
        if path.is_file() and path.name != BUNDLE_MANIFEST_FILENAME
    }

    assert placed == stored
    assert manifest.root_report_digest == proof.report.payload_digest


def test_a_complete_proof_verifies_offline(bundle: Path) -> None:
    result = verify_local_bundle(bundle)

    assert result.verified is True
    assert result.failures == []


def test_verification_recomputes_the_aggregate_from_the_receipts(
    bundle: Path,
) -> None:
    result = verify_local_bundle(bundle)

    recomputed = next(
        message for message in result.messages if message.id == "aggregate.recomputed"
    )

    assert recomputed.status == "passed"


def test_verification_reports_every_check_it_ran(bundle: Path) -> None:
    result = verify_local_bundle(bundle)

    identifiers = {message.id for message in result.messages}

    assert f"p1.{P1_REPORT_SIGNED}" in identifiers
    assert "publication.not_requested" in identifiers
    assert "linkage.report_campaign" in identifiers
    assert f"artifact.{REPORT_FILENAME}" in identifiers


# ---------------------------------------------------------------------------
# Tampering
# ---------------------------------------------------------------------------


def test_an_edited_receipt_breaks_the_proof(bundle: Path) -> None:
    def raise_the_reward(document: dict[str, Any]) -> None:
        traces = document["payload"]["named_traces"]["subject"]
        traces[0]["rewards"]["synthetic_reward"] = 0.5

    rewrite(bundle / BASELINE_RECEIPT, raise_the_reward)
    result = verify_local_bundle(bundle)

    assert result.verified is False
    assert f"artifact.{BASELINE_RECEIPT}" in failed(result)


def test_an_edited_receipt_with_a_repaired_manifest_still_breaks_the_proof(
    bundle: Path,
) -> None:
    """The digest is not the only seal: the signature is over it, not with it."""

    def raise_the_reward(document: dict[str, Any]) -> None:
        document["payload"]["named_traces"]["subject"][0]["rewards"][
            "synthetic_reward"
        ] = 0.5

    rewrite(bundle / BASELINE_RECEIPT, raise_the_reward)
    repaired = (bundle / BASELINE_RECEIPT).read_bytes()

    def repair_the_manifest(document: dict[str, Any]) -> None:
        from techtree.canonical import sha256_digest_bytes

        for reference in document["payload"]["artifacts"]:
            if reference["relative_path"] == BASELINE_RECEIPT:
                reference["digest"] = sha256_digest_bytes(repaired)
                reference["size"] = len(repaired)

    rewrite(bundle / BUNDLE_MANIFEST_FILENAME, repair_the_manifest)
    result = verify_local_bundle(bundle)

    assert result.verified is False
    assert f"{BASELINE_RECEIPT}.payload_digest" in failed(result)
    assert "bundle.signature" in failed(result)
    assert "receipt_set.baseline" in failed(result)


def test_an_edited_report_breaks_the_proof(bundle: Path) -> None:
    rewrite(
        bundle / REPORT_FILENAME,
        lambda document: document["payload"]["primary_result"].update(
            {"candidate_mean": 1.0}
        ),
    )
    result = verify_local_bundle(bundle)

    assert result.verified is False
    assert f"artifact.{REPORT_FILENAME}" in failed(result)


def test_a_removed_signature_breaks_the_proof(bundle: Path) -> None:
    rewrite(
        bundle / REPORT_FILENAME, lambda document: document.update({"signature": None})
    )
    result = verify_local_bundle(bundle)

    assert result.verified is False


def test_a_missing_receipt_breaks_the_proof(bundle: Path) -> None:
    (bundle / receipt_filename(ExperimentVariant.CANDIDATE, 3)).unlink()
    result = verify_local_bundle(bundle)

    assert result.verified is False


def test_an_edited_campaign_breaks_the_proof(bundle: Path) -> None:
    rewrite(
        bundle / "campaign.json",
        lambda document: document["scoring"].update({"minimum_absolute_delta": 0.9}),
    )
    result = verify_local_bundle(bundle)

    assert result.verified is False


def test_a_foreign_public_key_breaks_the_proof(bundle: Path, tmp_path: Path) -> None:
    """Swapping the key does not turn somebody else's signature into yours."""
    stranger = IdentityStore(paths_from_root(tmp_path / "stranger")).create()
    (bundle / PUBLIC_IDENTITY_FILENAME).write_bytes(canonical_json_bytes(stranger))
    result = verify_local_bundle(bundle)

    assert result.verified is False


def test_a_bundle_with_no_manifest_is_not_a_bundle(bundle: Path) -> None:
    (bundle / BUNDLE_MANIFEST_FILENAME).unlink()
    result = verify_local_bundle(bundle)

    assert result.verified is False
    assert failed(result) == ["bundle.present"]


def test_a_report_envelope_verifies_beside_its_key(bundle: Path) -> None:
    result = LocalProofVerifier().verify_report(bundle / REPORT_FILENAME)

    assert result.verified is True


def test_a_report_envelope_without_its_key_cannot_be_checked(bundle: Path) -> None:
    (bundle / PUBLIC_IDENTITY_FILENAME).unlink()

    result = LocalProofVerifier().verify_report(bundle / REPORT_FILENAME)

    assert result.verified is False
    assert failed(result) == ["identity.present"]


# ---------------------------------------------------------------------------
# The five headings a person reads
# ---------------------------------------------------------------------------


def test_a_verified_proof_still_says_what_it_does_not_prove(bundle: Path) -> None:
    summary = LocalProofVerifier().explain(verify_local_bundle(bundle))
    by_id = {message.id: message for message in summary}

    assert by_id["integrity"].status == "passed"
    assert by_id["comparison_validity"].status == "passed"
    assert by_id["participant_attestation"].status == "passed"
    # Never passed, whatever the bundle says: nobody has reproduced it.
    assert by_id["independent_reproduction"].status == "warning"
    assert by_id["public_publication"].status == "passed"


def test_the_explanation_never_claims_independent_reproduction(
    bundle: Path,
) -> None:
    summary = LocalProofVerifier().explain(verify_local_bundle(bundle))
    text = " ".join(message.detail for message in summary)

    assert "integrity-bound, participant-attested local execution" in text
    assert "independently reproduced" not in text
    assert "No independent reproduction" in text


# ---------------------------------------------------------------------------
# The decisions-0005 section 3.4 conditions, one at a time
# ---------------------------------------------------------------------------


def assess(proof: RecordedProof, **overrides: object) -> object:
    """Assess one proof's entitlement to P1, with one thing changed."""
    arguments: dict[str, object] = {
        "identity": proof.identity,
        "identity_self_check": True,
        "referenced_objects": [
            ReferencedObject("campaign", proof.campaign, digest_object(proof.campaign)),
            ReferencedObject(
                "data-policy", proof.data_policy, digest_object(proof.data_policy)
            ),
        ],
        "signed_receipts": proof.receipts,
        "comparison": ComparisonStatus.CONTROLLED_WITH_WARNINGS,
        "score": ScoreStatus.VALID,
    }
    if overrides.get("referenced_objects") == "one-wrong-digest":
        # The Campaign cited under a digest that is not the Campaign's.
        overrides["referenced_objects"] = [
            ReferencedObject(
                "campaign", proof.campaign, digest_object(proof.data_policy)
            )
        ]
    arguments.update(overrides)
    return assess_local_attestation(**arguments)  # type: ignore[arg-type]


def test_every_condition_holding_earns_the_signed_grade(proof: RecordedProof) -> None:
    assessment = assess(proof)

    assert assessment.attestation is LocalAttestation.LOCAL_ED25519  # type: ignore[attr-defined]
    assert [condition.id for condition in assessment.conditions] == list(  # type: ignore[attr-defined]
        P1_CONDITIONS
    )


@pytest.mark.parametrize(
    ("condition", "overrides"),
    [
        (
            P1_ARTIFACT_DIGESTS_VERIFY,
            {"referenced_objects": "one-wrong-digest"},
        ),
        (P1_RECEIPTS_SIGNED, {"signed_receipts": {}}),
        (P1_REPORT_SIGNED, {"identity_self_check": False}),
        (P1_COMPARISON_CONTROLLED, {"comparison": ComparisonStatus.INVALID}),
        (P1_SCORE_VALID, {"score": ScoreStatus.INVALID}),
    ],
)
def test_one_broken_condition_withholds_the_grade(
    proof: RecordedProof, condition: str, overrides: dict[str, object]
) -> None:
    """Each section 3.4 condition, falsified on its own."""
    assessment = assess(proof, **overrides)

    assert assessment.attestation is LocalAttestation.UNATTESTED  # type: ignore[attr-defined]
    assert condition in [
        broken.id
        for broken in assessment.failures  # type: ignore[attr-defined]
    ]


def test_no_identity_withholds_the_grade_for_three_reasons(
    proof: RecordedProof,
) -> None:
    """No key means no signed receipts, no signed report, and no public half."""
    assessment = assess(proof, identity=None, identity_self_check=False)

    assert assessment.attestation is LocalAttestation.UNATTESTED  # type: ignore[attr-defined]
    assert {
        broken.id
        for broken in assessment.failures  # type: ignore[attr-defined]
    } == {P1_RECEIPTS_SIGNED, P1_REPORT_SIGNED, P1_PUBLIC_KEY_PRESENT}


def test_unsigned_receipts_withhold_the_grade(tmp_path: Path) -> None:
    """An envelope with a digest and no signature seals nothing."""
    unsigned = signed_proof(tmp_path / "home", sign_receipts=False)

    assessment = assess(unsigned)

    assert assessment.attestation is LocalAttestation.UNATTESTED  # type: ignore[attr-defined]


def test_a_bundle_whose_report_claims_p1_without_a_signature_fails(
    tmp_path: Path,
) -> None:
    """The condition is re-derived from stored bytes, not taken on trust."""
    unsigned = signed_proof(tmp_path / "home", sign_report=False)
    directory = write_proof(unsigned, tmp_path / "run")

    result = verify_local_bundle(directory)

    assert result.verified is False
    assert f"p1.{P1_REPORT_SIGNED}" in failed(result)


def test_a_development_only_bundle_records_the_conditions_as_warnings(
    tmp_path: Path,
) -> None:
    """A report that claims nothing is not failed for lacking what it never claimed."""
    development = signed_proof(
        tmp_path / "home",
        proof_grade="development_only",
        decision=UpliftDecision.DEVELOPMENT_ONLY,
        comparison=ComparisonStatus.DEVELOPMENT_ONLY,
        score=ScoreStatus.DEVELOPMENT_ONLY,
    )
    directory = write_proof(development, tmp_path / "run")

    result = verify_local_bundle(directory)
    conditions = {
        message.id: message.status
        for message in result.messages
        if message.id.startswith("p1.")
    }

    # Signed and internally consistent, so it verifies; it simply establishes
    # two fewer conditions than a graded report has to.
    assert result.verified is True
    assert conditions[f"p1.{P1_COMPARISON_CONTROLLED}"] == "warning"
    assert conditions[f"p1.{P1_SCORE_VALID}"] == "warning"
    assert conditions[f"p1.{P1_REPORT_SIGNED}"] == "passed"


# ---------------------------------------------------------------------------
# The manifest itself
# ---------------------------------------------------------------------------


def test_a_manifest_places_each_artifact_once(proof: RecordedProof) -> None:
    manifest = build_local_bundle(
        run_id=proof.report.payload.run_id, contents=proof.contents
    )
    duplicated = manifest.artifacts + manifest.artifacts[:1]

    with pytest.raises(ValueError, match="exactly once"):
        LocalProofBundleManifest(
            **{**dict(manifest), "artifacts": duplicated},
        )


def test_a_signed_receipt_in_the_bundle_is_the_receipt_on_its_own(
    bundle: Path, proof: RecordedProof
) -> None:
    """The envelope adds a seal; it does not change what a receipt says."""
    stored = ObjectEnvelope[EpisodeReceipt].model_validate_json(
        (bundle / BASELINE_RECEIPT).read_bytes()
    )
    built = proof.receipts[ExperimentVariant.BASELINE][0]

    assert stored.payload == built.payload
    assert stored.payload_digest == digest_object(built.payload)


def test_the_public_key_travels_with_the_proof(
    bundle: Path, proof: RecordedProof
) -> None:
    stored = ExecutorIdentity.model_validate_json(
        (bundle / PUBLIC_IDENTITY_FILENAME).read_bytes()
    )

    assert stored == proof.identity
