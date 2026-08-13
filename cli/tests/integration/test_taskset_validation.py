"""Real model-free validation, end to end. Spec sections 21.4, 21.5, and 27.4.

Nothing here is simulated. The engine this build ships is installed for real,
the reference taskset is loaded by the pinned Verifiers commit, and every one of
its 36 tasks has its gold and setup check run in a subprocess. No model is
called and no container starts, which is what "model-free" means: the taskset
proves itself against its own oracle.

The claim these tests exist for is the one decisions document 0003 A1 made
possible. A ``TasksetValidationReceipt`` carries no identifier, no timestamp,
and no path, so the publisher's receipt and a participant's recomputed receipt
are not merely consistent — they are the same bytes. This module runs the
participant's half and requires it to reproduce, digest for digest, the receipt
this build ships in its packaged catalog.

The last two tests are the negative half. One tampers with a published
membership and shows the receipt turns invalid rather than quietly agreeing;
the other runs a whole detached worker against that tampered catalog and shows
the run fails before a single fake episode is scored.

    uv run pytest tests/integration/test_taskset_validation.py -m integration

Nothing here writes outside its own temporary Techtree home.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pytest

from fixtures.drafts.support import VALID_SKILL, preparation_service
from fixtures.runs.support import run_cli, start_through_the_cli, wait_for_terminal
from techtree.canonical import canonical_json_bytes, digest_object
from techtree.catalog.repository import EmbeddedCatalogRepository
from techtree.engines.installer import EngineInstaller, find_uv
from techtree.engines.registry import EngineRegistry
from techtree.engines.runner import EngineRunner
from techtree.models.base import ArtifactRef
from techtree.models.campaign import CampaignSpec
from techtree.models.climb import ClimbManifest
from techtree.models.data_policy import DataPolicy
from techtree.models.engine import EngineStatus
from techtree.models.validation import (
    REQUIRED_VALIDATION_CHECKS,
    TasksetLock,
    TasksetValidationReceipt,
    ValidationEvidence,
)
from techtree.paths import TechtreePaths, ensure_path_layout, paths_from_root
from techtree.settings import Settings
from techtree.tasksets.membership import membership_digest
from techtree.tasksets.service import (
    EXECUTION_RECORD_FILENAME,
    LOCK_FILENAME,
    RECEIPT_FILENAME,
    TASKSET_DIRECTORY,
    VALIDATION_DIRECTORY,
    TasksetService,
    TasksetValidationRun,
)
from techtree.tasksets.verifiers_cli import VALIDATION_FILENAMES

pytestmark = pytest.mark.integration

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[2]

CLIMB_REFERENCE: Final = "hello-world-climb"

#: Spec section 22: one task per frozen proving input. Written here rather than
#: derived, so that changing the dataset has to be a deliberate change to what
#: this build commits to.
EXPECTED_TASK_COUNT: Final = 36


# ---------------------------------------------------------------------------
# What this build published
# ---------------------------------------------------------------------------


def published_campaign() -> CampaignSpec:
    """Return the Campaign the packaged catalog ships."""
    packaged = EmbeddedCatalogRepository.packaged()
    climb = packaged.load_climb(CLIMB_REFERENCE)
    return packaged.load_campaign(climb.campaign_spec_digest)


def published_receipt() -> TasksetValidationReceipt:
    """Return the publisher validation receipt the Campaign commits to."""
    packaged = EmbeddedCatalogRepository.packaged()
    return packaged.load_validation_receipt(
        published_campaign().taskset.validation_receipt_digest
    )


def published_evidence() -> ValidationEvidence:
    """Return the normalized evidence the publisher receipt was issued from."""
    reference = published_receipt().normalized_evidence
    assert reference is not None
    return EmbeddedCatalogRepository.packaged().load_validation_evidence(
        reference.digest
    )


# ---------------------------------------------------------------------------
# Fixtures: one real engine, one real validation
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def home(tmp_path_factory: pytest.TempPathFactory) -> TechtreePaths:
    """A Techtree home used by every test in this module."""
    paths = paths_from_root(tmp_path_factory.mktemp("techtree-home"))
    ensure_path_layout(paths)
    return paths


@pytest.fixture(scope="module")
def engine(home: TechtreePaths) -> EngineStatus:
    """Install the shipped engine once, for real."""
    registry = EngineRegistry(home, Settings())
    return EngineInstaller(home, registry, find_uv()).install()


@pytest.fixture(scope="module")
def service(home: TechtreePaths, engine: EngineStatus) -> TasksetService:
    """A taskset service over the session's installed engine."""
    return TasksetService(EngineRegistry(home, Settings()), engine.digest)


@pytest.fixture(scope="module")
def run_directory(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Where the module's one validation writes its artifacts."""
    return tmp_path_factory.mktemp("techtree-validation-run")


@pytest.fixture(scope="module")
def validated(service: TasksetService, run_directory: Path) -> TasksetValidationRun:
    """Resolve and validate the reference taskset once, against the Campaign.

    Two inspections and one validation of 36 tasks. Every test below reads the
    same result, because they are all properties of one validation rather than
    of one validation each.
    """
    return service.resolve_and_validate(
        campaign=published_campaign(), run_dir=run_directory
    )


# ---------------------------------------------------------------------------
# The validation itself
# ---------------------------------------------------------------------------


def test_every_task_passes_gold_and_setup(validated: TasksetValidationRun) -> None:
    summary = validated.receipt.upstream_summary

    assert summary.mode == "all"
    assert summary.total == EXPECTED_TASK_COUNT
    assert summary.valid == EXPECTED_TASK_COUNT
    assert summary.valid_rate == 1.0


def test_nothing_errored_timed_out_or_went_missing(
    validated: TasksetValidationRun,
) -> None:
    summary = validated.receipt.upstream_summary

    assert (summary.invalid, summary.error, summary.timeout, summary.missing) == (
        0,
        0,
        0,
        0,
    )
    assert summary.recorded == summary.total


def test_the_receipt_reports_every_required_check_as_passed(
    validated: TasksetValidationRun,
) -> None:
    reported = {check.id: check.status for check in validated.receipt.checks}

    assert set(reported) == set(REQUIRED_VALIDATION_CHECKS)
    assert set(reported.values()) == {"passed"}
    assert validated.receipt.status == "valid"


def test_the_method_names_the_pinned_validator(
    validated: TasksetValidationRun,
) -> None:
    """Decisions 0001: the revision comes from the engine, never from a caller."""
    method = validated.receipt.method

    assert method.kind == "verifiers_validate"
    assert method.mode == "all"
    assert method.runtime == "subprocess"
    assert method.validator_revision == published_receipt().method.validator_revision


def test_the_evidence_covers_every_task_in_membership_order(
    validated: TasksetValidationRun,
) -> None:
    evidence = validated.evidence

    assert [task.position for task in evidence.tasks] == list(
        range(EXPECTED_TASK_COUNT)
    )
    assert [task.task_hash for task in evidence.tasks] == list(
        validated.lock.ordered_task_hashes
    )
    assert all(task.gold.valid and task.setup.valid for task in evidence.tasks)


# ---------------------------------------------------------------------------
# Agreement with the publisher
# ---------------------------------------------------------------------------


def test_the_local_receipt_is_the_published_receipt(
    validated: TasksetValidationRun,
) -> None:
    """Decisions 0003 A1: equality is the comparison, not resemblance."""
    assert validated.receipt_digest == digest_object(published_receipt())
    assert validated.receipt == published_receipt()
    assert (
        validated.receipt_digest
        == published_campaign().taskset.validation_receipt_digest
    )


def test_the_local_evidence_is_the_published_evidence(
    validated: TasksetValidationRun,
) -> None:
    assert digest_object(validated.evidence) == digest_object(published_evidence())


def test_the_local_lock_is_the_lock_the_publisher_receipt_names(
    validated: TasksetValidationRun,
) -> None:
    assert digest_object(validated.lock) == published_receipt().taskset_lock_digest
    assert validated.receipt.engine_digest == published_receipt().engine_digest


def test_the_membership_matches_what_the_campaign_commits_to(
    validated: TasksetValidationRun,
) -> None:
    committed = published_campaign().taskset.membership

    assert list(validated.lock.ordered_task_hashes) == list(
        committed.ordered_task_hashes
    )
    assert validated.lock.membership_digest == committed.membership_digest
    assert validated.lock.task_count == EXPECTED_TASK_COUNT


# ---------------------------------------------------------------------------
# What is written down, and where
# ---------------------------------------------------------------------------


def test_validation_writes_the_layout_the_spec_describes(
    validated: TasksetValidationRun, run_directory: Path
) -> None:
    """Spec section 28, plus the two files decisions 0003 A1 added."""
    taskset = run_directory / TASKSET_DIRECTORY
    validation = taskset / VALIDATION_DIRECTORY

    assert (taskset / LOCK_FILENAME).read_bytes() == canonical_json_bytes(
        validated.lock
    )
    assert (validation / RECEIPT_FILENAME).read_bytes() == canonical_json_bytes(
        validated.receipt
    )
    for name in VALIDATION_FILENAMES:
        assert (validation / name).is_file()


def test_the_execution_record_holds_what_the_receipt_refuses_to(
    validated: TasksetValidationRun, run_directory: Path
) -> None:
    """Decisions 0003 A1: raw provenance is local and is never the commitment."""
    record = validated.execution_record

    assert record.receipt_digest == validated.receipt_digest
    assert record.finished_at >= record.started_at
    assert record.command[0].endswith("/validate")
    assert "--rich" in record.command and "false" in record.command
    assert {artifact.relative_path for artifact in record.raw_artifacts} == set(
        VALIDATION_FILENAMES
    )
    assert (
        run_directory
        / TASKSET_DIRECTORY
        / VALIDATION_DIRECTORY
        / EXECUTION_RECORD_FILENAME
    ).is_file()

    # None of it reaches the shipped receipt, which is why the digests match.
    shipped = json.loads(canonical_json_bytes(validated.receipt))
    assert "raw_artifacts" not in shipped
    assert "created_at" not in shipped
    assert shipped["normalized_evidence"]["relative_path"] is None


# ---------------------------------------------------------------------------
# The negative control the taskset itself provides
# ---------------------------------------------------------------------------


def test_the_taskset_rejects_a_known_wrong_answer(
    home: TechtreePaths, engine: EngineStatus, tmp_path: Path
) -> None:
    """Spec section 26 WP5: the negative control is ``Task.validate`` itself.

    ``validate`` returning True for every task only means something if it can
    return False. This builds the same task with a wrong stored answer, inside
    the engine that produced the shipped receipt, and requires the check that
    passed 36 times to fail.
    """
    probe = tmp_path / "probe.py"
    probe.write_text(
        "\n".join(
            [
                "import asyncio, json",
                "import verifiers.v1 as vf",
                "taskset = vf.load_taskset(",
                "    vf.TasksetConfig(id='procedure-transfer-v1')",
                ")",
                "task = next(iter(taskset))",
                "wrong = type(task)(",
                "    task.data.model_copy(update={'answer': 'BRANCH-99'}),",
                "    task.config,",
                ")",
                "print(json.dumps({",
                "    'honest': asyncio.run(task.validate(None)),",
                "    'corrupted': asyncio.run(wrong.validate(None)),",
                "}))",
            ]
        ),
        encoding="utf-8",
    )

    runner = EngineRunner(EngineRegistry(home, Settings()), engine.digest)
    result = runner.run_python_script(probe, [], timeout=300.0)

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout.strip().splitlines()[-1]) == {
        "honest": True,
        "corrupted": False,
    }


# ---------------------------------------------------------------------------
# A published membership that is not the taskset's
# ---------------------------------------------------------------------------


def tampered_catalog(destination: Path, validated: TasksetValidationRun) -> Path:
    """Write a catalog that commits to the right tasks in the wrong order.

    Two positions are swapped everywhere at once — lock, evidence, receipt,
    Campaign, Climb, index — so the graph is internally consistent and passes
    preparation. What it no longer agrees with is the taskset, which is the
    disagreement local validation exists to find.
    """
    builder = _fixture_catalog_builder()

    swapped = list(validated.lock.ordered_task_hashes)
    swapped[0], swapped[1] = swapped[1], swapped[0]

    lock: TasksetLock = validated.lock.model_copy(
        update={
            "ordered_task_hashes": swapped,
            "membership_digest": membership_digest(swapped),
        }
    )
    evidence: ValidationEvidence = validated.evidence.model_copy(
        update={
            "taskset_lock_digest": digest_object(lock),
            "tasks": [
                task.model_copy(update={"task_hash": swapped[position]})
                for position, task in enumerate(validated.evidence.tasks)
            ],
        }
    )
    receipt: TasksetValidationReceipt = validated.receipt.model_copy(
        update={
            "taskset_lock_digest": digest_object(lock),
            "normalized_evidence": ArtifactRef(
                digest=digest_object(evidence),
                media_type="application/json",
                size=len(canonical_json_bytes(evidence)),
                relative_path=None,
            ),
        }
    )

    data_policy: DataPolicy = builder.build_development_data_policy()
    campaign = builder.build_hello_world_campaign(
        taskset_lock=lock,
        validation_receipt_digest=digest_object(receipt),
        data_policy_digest=digest_object(data_policy),
    )
    climb: ClimbManifest = builder.build_hello_world_climb(
        campaign_digest=digest_object(campaign)
    )

    builder.write_catalog(
        climbs={builder.CLIMB_PATH: climb},
        objects=[
            builder.CatalogFile(
                kind="campaign", path=builder.CAMPAIGN_PATH, model=campaign
            ),
            builder.CatalogFile(
                kind="data_policy", path=builder.DATA_POLICY_PATH, model=data_policy
            ),
            builder.CatalogFile(
                kind="taskset_validation", path=builder.RECEIPT_PATH, model=receipt
            ),
            builder.CatalogFile(
                kind="validation_evidence", path=builder.EVIDENCE_PATH, model=evidence
            ),
        ],
        destination=destination,
    )
    return destination


def test_a_tampered_membership_makes_the_receipt_invalid(
    service: TasksetService,
    validated: TasksetValidationRun,
    tmp_path: Path,
) -> None:
    """The mechanical check names the position, so an operator can act on it."""
    swapped = list(validated.lock.ordered_task_hashes)
    swapped[0], swapped[1] = swapped[1], swapped[0]

    result = service.validate(
        lock=validated.lock,
        committed_task_hashes=swapped,
        expected_task_count=EXPECTED_TASK_COUNT,
        run_dir=tmp_path / "tampered",
    )

    failed = {
        check.id: check.detail
        for check in result.receipt.checks
        if check.status == "failed"
    }
    assert set(failed) == {"committed_membership_match"}
    assert "position 0" in failed["committed_membership_match"]
    assert result.receipt.status == "invalid"
    assert result.receipt_digest != validated.receipt_digest


def test_validation_failure_blocks_the_fake_phases(
    validated: TasksetValidationRun,
    tmp_path: Path,
) -> None:
    """Spec section 26 WP5: nothing is scored on a taskset that did not check out.

    A whole detached worker runs, against a real engine, on a catalog whose
    published membership does not describe the taskset. The run has to fail in
    ``validating_taskset`` and leave no episode receipts behind.
    """
    home_root = tmp_path / "home"
    home_root.mkdir()
    paths = paths_from_root(home_root)
    ensure_path_layout(paths)
    EngineInstaller(paths, EngineRegistry(paths, Settings()), find_uv()).install()

    catalog = tampered_catalog(tmp_path / "catalog", validated)
    preparation, _ = preparation_service(paths, catalog_root=catalog)
    prepared = preparation.prepare(
        climb_reference=CLIMB_REFERENCE,
        skill_path=VALID_SKILL,
        candidate_label="candidate-under-test",
    )

    started = start_through_the_cli(home_root, prepared)
    run_id = started.data()["run_id"]
    final = wait_for_terminal(home_root, run_id, timeout=600.0)

    assert final["phase"] == "failed"
    assert final["error"]["code"] == "taskset_validation_invalid"
    assert final["result_available"] is False
    assert not (paths.run_dir(run_id) / "receipts").exists()

    logs = run_cli(home_root, "run", "logs", run_id).data()["lines"]
    assert any("taskset_validation_invalid" in line for line in logs)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fixture_catalog_builder() -> Any:
    """Import the publisher generator from the tools tree.

    ``tools`` is a scripts directory rather than an installed package, so it is
    loaded by path. Importing it is what lets a test build a *variant* of the
    shipped catalog with the same code that shipped it, instead of a second
    hand-written graph that could drift away from the first.
    """
    import importlib.util
    import sys

    location = REPOSITORY_ROOT / "tools" / "build_fixture_catalog.py"
    spec = importlib.util.spec_from_file_location("techtree_fixture_catalog", location)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered before execution because a dataclass defined in the module
    # resolves its own annotations through ``sys.modules``.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
