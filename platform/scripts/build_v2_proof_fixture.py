# Build the v0.2 proof bundle the publication tests publish, and the exact
# submission bytes the CLI would put on the wire for it.
#
#     uv run --project ../cli python scripts/build_v2_proof_fixture.py
#
# `test/support/fixtures/proof` is a real v0.1 run and stays as it was written:
# its Campaign is one the v0.2 catalog no longer publishes, so it can no longer
# be accepted here, and it remains the read-only fixture the canonical encoder
# is pinned against. The publication tests need a proof of the Campaign the
# v0.2 catalog *does* publish. No v0.2 certification fixture is committed here,
# so this writes
# one the way the CLI's own verifier tests write theirs: the real hello-world
# Campaign graph out of the packaged catalog, the real manifest builder, the
# real receipt-set and report aggregation, and a signing key made here — with
# synthetic rewards in place of evidence. It is a proof that verifies, of a
# comparison nobody ran. The site does not read the evidence, which is why the
# fixture may say so plainly and still exercise every check the site runs.
#
# Two things are written:
#
#   * `test/support/fixtures/proof-v2/` — the proof directory, as the CLI's
#     bundle writer lays it out and seals it.
#   * `test/support/fixtures/publication/v2-submission.json` — the submission
#     for that directory, produced by `PublicationService.submission_bytes`,
#     the one place the CLI builds its request body.
#
# The taskset lock is the one document the catalog does not ship. The
# hello-world validation receipt names the same lock the v0.1 run carried, so
# it is read from the v0.1 fixture and checked against the receipt before use.
#
# The key is generated per run, so rebuilding this fixture changes every
# signature in it. Nothing here opens a socket.

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

PLATFORM = Path(__file__).resolve().parent.parent
CLI = PLATFORM.parent / "cli"
FIXTURES = PLATFORM / "test" / "support" / "fixtures"

# The CLI's test fixtures are a package under its tests directory, not part of
# the installed distribution.
sys.path.insert(0, str(CLI / "tests"))

from fixtures.publication.conformance import submission_for_proof  # noqa: E402
from fixtures.receipts.proof import (  # noqa: E402
    _VARIANTS,
    PROOF_RUN_ID,
    RecordedProof,
    _manifest,
    _receipt,
    _report,
    _reward,
    execution_record,
    write_proof,
)
from techtree.canonical import digest_object  # noqa: E402
from techtree.catalog.repository import EmbeddedCatalogRepository  # noqa: E402
from techtree.identity.service import IdentityService  # noqa: E402
from techtree.identity.store import IdentityStore  # noqa: E402
from techtree.models.base import ArtifactRef  # noqa: E402
from techtree.models.episode_receipt import ScoreStatus  # noqa: E402
from techtree.models.experiment import ExperimentVariant  # noqa: E402
from techtree.models.uplift_report import ComparisonStatus, UpliftDecision  # noqa: E402
from techtree.models.validation import TasksetLock  # noqa: E402
from techtree.paths import paths_from_root  # noqa: E402
from techtree.receipts.set import build_receipt_set  # noqa: E402
from techtree.receipts.verify import LocalProofVerifier  # noqa: E402

CLIMB_REFERENCE = "hello-world-climb@1"
HISTORICAL_LOCK = FIXTURES / "proof" / "taskset-lock.json"
PROOF_DESTINATION = FIXTURES / "proof-v2"
SUBMISSION_DESTINATION = FIXTURES / "publication" / "v2-submission.json"

# The candidate Skill the comparison mounts: a digest with the shape of an
# archive and none of its bytes, exactly as the CLI's verifier fixture does.
SKILL = ArtifactRef(
    digest="sha256:" + "5c" * 32,
    media_type="application/zip",
    size=4096,
    relative_path=None,
)


def main() -> int:
    catalog = EmbeddedCatalogRepository.packaged()
    entry = catalog.climb_entry(CLIMB_REFERENCE)
    climb = catalog.load_climb(entry.reference)
    campaign = catalog.load_campaign(climb.campaign_spec_digest)
    execution_plan = catalog.load_execution_plan(campaign.execution_plan_digest)
    data_policy = catalog.load_data_policy(campaign.data_policy_digest)
    validation_receipt = catalog.load_validation_receipt(
        campaign.taskset.validation_receipt_digest
    )

    lock = TasksetLock.model_validate_json(HISTORICAL_LOCK.read_bytes())
    if digest_object(lock) != validation_receipt.taskset_lock_digest:
        raise SystemExit("the v0.1 taskset lock is not the lock the receipt validates")
    committed = list(campaign.taskset.membership.ordered_task_hashes)
    if lock.ordered_task_hashes != committed:
        raise SystemExit(
            "the taskset lock does not hold the tasks the Campaign commits to"
        )

    campaign_digest = climb.campaign_spec_digest
    data_policy_digest = campaign.data_policy_digest

    with tempfile.TemporaryDirectory() as scratch:
        home = Path(scratch) / "home"
        identity_service = IdentityService(IdentityStore(paths_from_root(home)))
        identity = identity_service.ensure()

        experiments = {
            ExperimentVariant.BASELINE: _manifest(
                campaign, campaign_digest, ExperimentVariant.BASELINE, skill=None
            ),
            ExperimentVariant.CANDIDATE: _manifest(
                campaign, campaign_digest, ExperimentVariant.CANDIDATE, skill=SKILL
            ),
        }
        receipts = {
            variant: [
                identity_service.sign_object(
                    _receipt(
                        campaign=campaign,
                        execution_plan=execution_plan,
                        campaign_digest=campaign_digest,
                        data_policy_digest=data_policy_digest,
                        experiment=experiments[variant],
                        variant=variant,
                        position=position,
                        task_hash=task_hash,
                        reward=_reward(variant, position),
                        score=ScoreStatus.VALID,
                    )
                )
                for position, task_hash in enumerate(committed)
            ]
            for variant in _VARIANTS
        }
        receipt_sets = {
            variant: build_receipt_set(
                run_id=PROOF_RUN_ID,
                variant=variant,
                experiment_manifest_digest=digest_object(experiments[variant]),
                signed_receipts=receipts[variant],
                ordered_task_hashes=committed,
            )
            for variant in _VARIANTS
        }
        report = _report(
            campaign=campaign,
            execution_plan=execution_plan,
            campaign_digest=campaign_digest,
            data_policy_digest=data_policy_digest,
            validation_receipt_digest=campaign.taskset.validation_receipt_digest,
            experiments=experiments,
            committed=committed,
            proof_grade="P1",
            decision=UpliftDecision.ACCEPTED,
            comparison=ComparisonStatus.CONTROLLED_WITH_WARNINGS,
            score=ScoreStatus.VALID,
        )
        proof = RecordedProof(
            identity=identity,
            identity_service=identity_service,
            campaign=campaign,
            execution_plan=execution_plan,
            data_policy=data_policy,
            taskset_lock=lock,
            validation_receipt=validation_receipt,
            experiments=experiments,
            receipts=receipts,
            receipt_sets=receipt_sets,
            report=identity_service.sign_object(report),
            execution_record=identity_service.sign_object(
                execution_record(
                    campaign_digest,
                    {
                        variant: digest_object(manifest)
                        for variant, manifest in experiments.items()
                    },
                )
            ),
        )

        directory = write_proof(proof, Path(scratch) / "run")

        verification = LocalProofVerifier().verify_bundle(directory)
        if not verification.verified:
            failures = ", ".join(message.id for message in verification.failures)
            raise SystemExit(f"the written proof does not verify: {failures}")

        submission = submission_for_proof(directory, run_id=PROOF_RUN_ID)

        if PROOF_DESTINATION.exists():
            shutil.rmtree(PROOF_DESTINATION)
        shutil.copytree(directory, PROOF_DESTINATION)
        SUBMISSION_DESTINATION.parent.mkdir(parents=True, exist_ok=True)
        SUBMISSION_DESTINATION.write_bytes(submission)

    print(f"proof {PROOF_DESTINATION}")
    print(f"submission {SUBMISSION_DESTINATION}")
    print(f"campaign {campaign_digest}")
    print(f"execution plan {campaign.execution_plan_digest}")
    print(f"checks {len(verification.messages)} verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
