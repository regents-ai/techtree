"""Locking the real taskset with the real engine. Spec sections 21.3 and 27.4.

Nothing here is simulated. The engine is installed from the bundle this build
ships, the reference package is the one inside it, and every task hash comes out
of the pinned Verifiers commit loading the taskset in a fresh process. The
install calls ``uv sync``, which reaches PyPI and GitHub on a cold cache, so the
whole module is marked ``integration`` and excluded from the default run::

    uv run pytest tests/integration/test_taskset_membership.py -m integration

The engine and the first lock are resolved once per session and shared. The
determinism test deliberately resolves again from scratch — four engine
processes across the module — because "the same object twice" is the claim, and
a cached result cannot make it.

Nothing here writes outside its own temporary Techtree home.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from techtree.canonical import digest_object
from techtree.constants import TASKSET_LOCK_SCHEMA_VERSION
from techtree.engines.bundle import (
    PACKAGES_DIRECTORY,
    default_engine_descriptor,
    embedded_engine_root,
    package_source_digest,
)
from techtree.engines.installer import EngineInstaller, find_uv
from techtree.engines.registry import EngineRegistry
from techtree.engines.runner import EngineRunner
from techtree.errors import EngineError, ValidationError, VerificationError
from techtree.models.base import Digest
from techtree.models.campaign import (
    PackageRef,
    TaskMembershipCommitment,
    TaskSelection,
    TasksetRef,
)
from techtree.models.engine import EngineStatus
from techtree.models.validation import TasksetLock
from techtree.paths import TechtreePaths, ensure_path_layout, paths_from_root
from techtree.settings import Settings
from techtree.tasksets.membership import (
    MEMBERSHIP_REPEATABILITY_CHECK,
    compare_membership,
    load_inspection_output,
    membership_digest,
)
from techtree.tasksets.resolver import INSPECT_TASKSET_TOOL, TasksetResolver

pytestmark = pytest.mark.integration

REFERENCE_PACKAGE = "procedure-transfer-v1"
TASKSET_ID = "procedure-transfer-v1"

#: Spec section 22. The reference taskset ships one task per frozen proving
#: input, and there are 36 of them. The count is written here rather than
#: derived so that a change to the dataset has to be a deliberate change to the
#: committed membership too.
EXPECTED_TASK_COUNT = 36

RAW_HASH_CHARACTERS = set("0123456789abcdef")


# ---------------------------------------------------------------------------
# The reference the Campaign would carry
# ---------------------------------------------------------------------------


def reference_package_digest() -> Digest:
    """Return the source digest of the packaged reference taskset."""
    return package_source_digest(
        embedded_engine_root() / PACKAGES_DIRECTORY / REFERENCE_PACKAGE
    )


def reference_taskset_ref() -> TasksetRef:
    """Return the taskset reference a Campaign commits to."""
    descriptor = default_engine_descriptor()
    package = next(
        entry for entry in descriptor.packages if entry.name == REFERENCE_PACKAGE
    )
    return TasksetRef(
        kind="verifiers",
        id=TASKSET_ID,
        package=PackageRef(
            kind="embedded",
            name=REFERENCE_PACKAGE,
            revision=package.version,
            digest=package.source_digest,
        ),
        config={},
    )


def selection(num_tasks: int = EXPECTED_TASK_COUNT) -> TaskSelection:
    """Return the task selection. Decisions document 0001: never shuffled."""
    return TaskSelection(num_tasks=num_tasks, num_rollouts=1, shuffle=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def installed_paths(tmp_path_factory: pytest.TempPathFactory) -> TechtreePaths:
    """A Techtree home used by every test in this module."""
    paths = paths_from_root(tmp_path_factory.mktemp("techtree-home"))
    ensure_path_layout(paths)
    return paths


@pytest.fixture(scope="session")
def installed_engine(installed_paths: TechtreePaths) -> EngineStatus:
    """Install the shipped engine once, for real."""
    registry = EngineRegistry(installed_paths, Settings())
    return EngineInstaller(installed_paths, registry, find_uv()).install()


@pytest.fixture(scope="session")
def resolver(
    installed_paths: TechtreePaths, installed_engine: EngineStatus
) -> TasksetResolver:
    """A resolver over the session's installed engine."""
    return TasksetResolver(
        EngineRegistry(installed_paths, Settings()), installed_engine.digest
    )


@pytest.fixture(scope="session")
def lock(resolver: TasksetResolver) -> TasksetLock:
    """The lock the reference taskset resolves to. Two engine processes."""
    return resolver.resolve(taskset_ref=reference_taskset_ref(), selection=selection())


# ---------------------------------------------------------------------------
# What the engine reported
# ---------------------------------------------------------------------------


def test_the_reference_taskset_locks_to_its_whole_frozen_dataset(
    lock: TasksetLock, installed_engine: EngineStatus
) -> None:
    assert lock.schema_version == TASKSET_LOCK_SCHEMA_VERSION
    assert lock.task_count == EXPECTED_TASK_COUNT
    assert len(lock.ordered_task_hashes) == EXPECTED_TASK_COUNT
    assert lock.engine_digest == installed_engine.digest
    assert lock.taskset_ref == reference_taskset_ref()


def test_every_task_hash_crossed_the_boundary_normalized(lock: TasksetLock) -> None:
    """Raw Verifiers hexadecimal on one side, Techtree digests on the other."""
    for task_hash in lock.ordered_task_hashes:
        algorithm, separator, hexadecimal = task_hash.partition(":")
        assert (algorithm, separator) == ("sha256", ":")
        assert len(hexadecimal) == 64
        assert set(hexadecimal) <= RAW_HASH_CHARACTERS


def test_no_task_is_locked_twice(lock: TasksetLock) -> None:
    assert len(set(lock.ordered_task_hashes)) == EXPECTED_TASK_COUNT


def test_the_lock_commits_to_the_membership_digest_of_its_own_hashes(
    lock: TasksetLock,
) -> None:
    assert lock.membership_digest == membership_digest(lock.ordered_task_hashes)


def test_the_locked_membership_satisfies_a_campaign_commitment(
    lock: TasksetLock,
) -> None:
    """The comparison the resolver leaves to its caller, made for real."""
    commitment = TaskMembershipCommitment(
        mode="committed",
        ordered_task_hashes=lock.ordered_task_hashes,
        membership_digest=lock.membership_digest,
    )

    check = compare_membership(lock.ordered_task_hashes, commitment.ordered_task_hashes)

    assert check.status == "passed"
    assert commitment.membership_digest == membership_digest(
        commitment.ordered_task_hashes
    )


def test_a_commitment_to_a_different_task_is_caught_at_its_position(
    lock: TasksetLock,
) -> None:
    tampered = list(lock.ordered_task_hashes)
    tampered[17] = "sha256:" + "f" * 64

    check = compare_membership(lock.ordered_task_hashes, tampered)

    assert check.status == "failed"
    assert "position 17" in check.detail


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_resolving_the_same_reference_again_produces_the_same_bytes(
    resolver: TasksetResolver, lock: TasksetLock
) -> None:
    """Four engine processes, one answer. No timestamp, no path, no ordering luck."""
    again = resolver.resolve(taskset_ref=reference_taskset_ref(), selection=selection())

    assert again == lock
    assert digest_object(again) == digest_object(lock)


def test_two_direct_inspections_agree_on_every_position(
    installed_paths: TechtreePaths, installed_engine: EngineStatus, tmp_path: Path
) -> None:
    """The same claim one level down, against the helper's own output."""
    registry = EngineRegistry(installed_paths, Settings())
    runner = EngineRunner(registry, installed_engine.digest)
    script = registry.tool_path(installed_engine.digest, INSPECT_TASKSET_TOOL)

    hashes = []
    for attempt in range(2):
        output = tmp_path / f"inspection-{attempt}.json"
        result = runner.run_python_script(
            script,
            [
                "--taskset-id",
                TASKSET_ID,
                "--num-tasks",
                str(EXPECTED_TASK_COUNT),
                "--output",
                str(output),
            ],
            timeout=300.0,
        )
        assert result.exit_code == 0, result.stderr
        hashes.append(load_inspection_output(output).ordered_task_hashes)

    check = compare_membership(
        hashes[1], hashes[0], check_id=MEMBERSHIP_REPEATABILITY_CHECK
    )
    assert check.status == "passed"
    assert len(hashes[0]) == EXPECTED_TASK_COUNT


def test_the_engine_reports_identity_and_never_task_content(
    installed_paths: TechtreePaths, installed_engine: EngineStatus, tmp_path: Path
) -> None:
    """A published membership must not publish the answer key."""
    registry = EngineRegistry(installed_paths, Settings())
    runner = EngineRunner(registry, installed_engine.digest)
    output = tmp_path / "inspection.json"

    result = runner.run_python_script(
        registry.tool_path(installed_engine.digest, INSPECT_TASKSET_TOOL),
        ["--taskset-id", TASKSET_ID, "--num-tasks", "4", "--output", str(output)],
        timeout=300.0,
    )
    assert result.exit_code == 0, result.stderr

    document = json.loads(output.read_text(encoding="utf-8"))
    assert sorted(document["tasks"][0]) == [
        "name",
        "position",
        "task_hash",
        "task_type",
    ]
    text = output.read_text(encoding="utf-8")
    assert "BRANCH-" not in text
    assert "BranchCode" not in text


# ---------------------------------------------------------------------------
# The required triple equality
# ---------------------------------------------------------------------------


def test_the_locked_package_digest_is_the_source_tree_the_engine_holds(
    lock: TasksetLock, installed_paths: TechtreePaths, installed_engine: EngineStatus
) -> None:
    """Decisions document 0003 A8, all three legs at once."""
    descriptor_digest = next(
        package.source_digest
        for package in default_engine_descriptor().packages
        if package.name == REFERENCE_PACKAGE
    )
    installed_tree = (
        EngineRegistry(installed_paths, Settings()).path(installed_engine.digest)
        / PACKAGES_DIRECTORY
        / REFERENCE_PACKAGE
    )

    assert lock.resolved_package_digest == lock.taskset_ref.package.digest
    assert lock.resolved_package_digest == descriptor_digest
    assert lock.resolved_package_digest == package_source_digest(installed_tree)
    assert lock.resolved_package_digest == reference_package_digest()


def test_a_campaign_committed_to_a_different_package_is_refused(
    resolver: TasksetResolver,
) -> None:
    """The commitment leg of the equality, broken on purpose."""
    reference = reference_taskset_ref()
    wrong = reference.model_copy(
        update={
            "package": reference.package.model_copy(
                update={"digest": "sha256:" + "1" * 64}
            )
        }
    )

    with pytest.raises(VerificationError) as failure:
        resolver.resolve(taskset_ref=wrong, selection=selection())

    assert failure.value.code == "taskset_package_digest_mismatch"


# ---------------------------------------------------------------------------
# Typed refusals
# ---------------------------------------------------------------------------


def test_asking_for_more_tasks_than_the_taskset_holds_fails_by_name(
    resolver: TasksetResolver,
) -> None:
    with pytest.raises(EngineError) as failure:
        resolver.resolve(
            taskset_ref=reference_taskset_ref(),
            selection=selection(EXPECTED_TASK_COUNT + 1),
        )

    assert failure.value.code == "taskset_inspection_failed"
    assert failure.value.details["taskset_id"] == TASKSET_ID


def test_a_taskset_configuration_nothing_would_apply_is_refused(
    resolver: TasksetResolver,
) -> None:
    reference = reference_taskset_ref()
    configured = reference.model_copy(update={"config": {"shuffle_seed": 7}})

    with pytest.raises(ValidationError) as failure:
        resolver.resolve(taskset_ref=configured, selection=selection())

    assert failure.value.code == "taskset_config_unsupported"
    assert failure.value.details["unsupported_keys"] == ["shuffle_seed"]


def test_a_configuration_that_contradicts_the_selection_is_refused(
    resolver: TasksetResolver,
) -> None:
    reference = reference_taskset_ref()
    configured = reference.model_copy(update={"config": {"num_tasks": 12}})

    with pytest.raises(ValidationError) as failure:
        resolver.resolve(taskset_ref=configured, selection=selection())

    assert failure.value.code == "taskset_config_conflict"


def test_an_unknown_taskset_is_an_engine_failure_not_a_crash(
    resolver: TasksetResolver,
) -> None:
    reference = reference_taskset_ref()
    absent = reference.model_copy(update={"id": "no-such-taskset"})

    with pytest.raises(EngineError) as failure:
        resolver.resolve(taskset_ref=absent, selection=selection(2))

    assert failure.value.code == "taskset_inspection_failed"
