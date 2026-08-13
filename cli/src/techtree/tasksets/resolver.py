"""Turning a taskset reference into a lock. Spec section 21.3.

A ``TasksetLock`` is the answer to one question: given this engine and this
reference, which tasks *are* the Climb? The answer has to be the same for the
publisher and for every participant, so this module is built around three
refusals.

*Ask twice, in two fresh processes.* One inspection tells you what a taskset
loaded as; two tell you whether loading it is deterministic. A taskset that
draws from a random source, iterates a set, or depends on dictionary order will
usually agree with itself inside one process and disagree across two, which is
exactly why the second run is a new interpreter rather than a second call.

*Count and uniqueness are required, not observed.* A selection asking for 36
tasks and receiving 35 is not a smaller Climb, it is a different one; a
membership naming the same task twice would score it twice under one
commitment.

*The package the engine actually holds is what gets locked.* Decisions document
0003 A8 requires three values to be equal — the Campaign's
``taskset.ref.package.digest``, the engine descriptor's ``source_digest``, and
the lock's ``resolved_package_digest``. This module recomputes the digest from
the installed source tree rather than copying either declaration, so the
equality is a fact about the files on disk instead of a fact about two
documents agreeing with each other.

Nothing in the lock is a timestamp, a path, or a process detail. Resolving the
same reference against the same engine twice produces byte-identical bytes, and
that is what lets a participant's lock and the publisher's lock be compared by
digest instead of by narrative.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Final

from techtree.canonical import validate_digest
from techtree.constants import TASKSET_LOCK_SCHEMA_VERSION
from techtree.engines.bundle import (
    PACKAGES_DIRECTORY,
    package_source_digest,
    read_engine_descriptor,
)
from techtree.engines.registry import EngineRegistry
from techtree.engines.runner import EngineRunner
from techtree.errors import EngineError, ValidationError, VerificationError
from techtree.models.base import Digest
from techtree.models.campaign import TaskSelection, TasksetRef
from techtree.models.validation import TasksetLock
from techtree.tasksets.membership import (
    MEMBERSHIP_REPEATABILITY_CHECK,
    TasksetInspection,
    assert_unique_task_hashes,
    compare_membership,
    load_inspection_output,
    membership_digest,
)

__all__ = [
    "INSPECTION_TIMEOUT_SECONDS",
    "INSPECT_TASKSET_TOOL",
    "SUPPORTED_CONFIG_KEYS",
    "TasksetResolver",
]

#: The engine helper that reports task identity. It lives inside the digested
#: bundle (decisions document 0003 A3) and is addressed through the registry,
#: never as a path a caller supplies.
INSPECT_TASKSET_TOOL: Final = "inspect_taskset.py"

#: Loading a taskset imports Verifiers and the reference package, which is slow
#: on a cold filesystem cache and instant afterwards. The limit exists to end a
#: hung process, not to police performance.
INSPECTION_TIMEOUT_SECONDS: Final = 300.0

#: The only taskset configuration WP5 can honor. The helper takes the task count
#: as an argument, so a configuration may restate it and may say nothing else:
#: a key nothing applies would be a setting that silently does not happen.
SUPPORTED_CONFIG_KEYS: Final[tuple[str, ...]] = ("num_tasks",)

_OUTPUT_FILENAME: Final = "inspection.json"
_TEMPORARY_PREFIX: Final = "techtree-inspect-"


class TasksetResolver:
    """Resolves one taskset reference against one installed engine."""

    def __init__(
        self,
        registry: EngineRegistry,
        engine_digest: Digest,
        *,
        timeout_seconds: float = INSPECTION_TIMEOUT_SECONDS,
    ) -> None:
        self._registry = registry
        self._engine_digest = validate_digest(engine_digest)
        self._runner = EngineRunner(registry, self._engine_digest)
        self._timeout_seconds = timeout_seconds

    def resolve(
        self,
        *,
        taskset_ref: TasksetRef,
        selection: TaskSelection,
    ) -> TasksetLock:
        """Load the taskset twice, enforce determinism, and build the lock."""
        _require_supported_reference(taskset_ref, selection)
        resolved_package_digest = self._package_digest(taskset_ref)

        first = self._inspect(taskset_ref, selection)
        second = self._inspect(taskset_ref, selection)

        repeatability = compare_membership(
            second.ordered_task_hashes,
            first.ordered_task_hashes,
            check_id=MEMBERSHIP_REPEATABILITY_CHECK,
        )
        if repeatability.status != "passed":
            raise VerificationError(
                f"taskset {taskset_ref.id} produced a different membership on a "
                f"second load, so it cannot be locked: {repeatability.detail}",
                code="taskset_membership_unstable",
                details={
                    "taskset_id": taskset_ref.id,
                    "check": repeatability.id,
                    "detail": repeatability.detail,
                },
            )

        ordered_task_hashes = first.ordered_task_hashes
        if len(ordered_task_hashes) != selection.num_tasks:
            raise VerificationError(
                f"taskset {taskset_ref.id} resolved to "
                f"{len(ordered_task_hashes)} tasks but the selection asks for "
                f"{selection.num_tasks}",
                code="taskset_task_count_unexpected",
                details={
                    "taskset_id": taskset_ref.id,
                    "resolved": len(ordered_task_hashes),
                    "expected": selection.num_tasks,
                },
            )
        assert_unique_task_hashes(ordered_task_hashes)

        return TasksetLock(
            schema_version=TASKSET_LOCK_SCHEMA_VERSION,
            taskset_ref=taskset_ref,
            engine_digest=self._engine_digest,
            resolved_package_digest=resolved_package_digest,
            ordered_task_hashes=ordered_task_hashes,
            membership_digest=membership_digest(ordered_task_hashes),
            task_count=len(ordered_task_hashes),
        )

    # -- one inspection ----------------------------------------------------

    def _inspect(
        self, taskset_ref: TasksetRef, selection: TaskSelection
    ) -> TasksetInspection:
        """Run the engine helper once, in its own process, and read its report."""
        script = self._registry.tool_path(self._engine_digest, INSPECT_TASKSET_TOOL)

        with tempfile.TemporaryDirectory(prefix=_TEMPORARY_PREFIX) as directory:
            output = Path(directory) / _OUTPUT_FILENAME
            result = self._runner.run_python_script(
                script,
                [
                    "--taskset-id",
                    taskset_ref.id,
                    "--num-tasks",
                    str(selection.num_tasks),
                    "--output",
                    str(output),
                ],
                timeout=self._timeout_seconds,
            )
            if result.exit_code != 0:
                raise EngineError(
                    f"the engine could not inspect taskset {taskset_ref.id}: "
                    f"{_last_line(result.stderr)}",
                    code="taskset_inspection_failed",
                    details={
                        "taskset_id": taskset_ref.id,
                        "engine_digest": self._engine_digest,
                        "exit_code": result.exit_code,
                    },
                )
            inspection = load_inspection_output(output)

        if inspection.taskset_id != taskset_ref.id:
            raise VerificationError(
                f"the engine inspected {inspection.taskset_id} but "
                f"{taskset_ref.id} was asked for",
                code="taskset_identity_mismatch",
                details={
                    "requested": taskset_ref.id,
                    "inspected": inspection.taskset_id,
                },
            )
        return inspection

    # -- the package the engine holds --------------------------------------

    def _package_digest(self, taskset_ref: TasksetRef) -> Digest:
        """Return the source digest of the installed package, having checked it.

        Decisions document 0003 A8. Two of the three required equalities are
        settled here, against the recomputed tree: the engine descriptor's
        declaration and the Campaign's commitment. The third is the lock's own
        field, which is this return value.
        """
        engine_root = self._registry.path(self._engine_digest)
        package_name = taskset_ref.package.name
        package_root = engine_root / PACKAGES_DIRECTORY / package_name

        if not package_root.is_dir():
            raise EngineError(
                f"engine {self._engine_digest} ships no package named {package_name}",
                code="engine_package_missing",
                details={
                    "engine_digest": self._engine_digest,
                    "package": package_name,
                },
            )

        resolved = package_source_digest(package_root)
        declared = _declared_source_digest(engine_root, package_name)

        if declared != resolved:
            raise VerificationError(
                f"the {package_name} source tree inside engine "
                f"{self._engine_digest} hashes to {resolved}, but the engine "
                f"descriptor declares {declared}",
                code="engine_package_digest_mismatch",
                details={
                    "package": package_name,
                    "resolved": resolved,
                    "declared": declared,
                },
            )
        if taskset_ref.package.digest != resolved:
            raise VerificationError(
                f"the Campaign commits to {package_name} at "
                f"{taskset_ref.package.digest}, but this engine holds {resolved}",
                code="taskset_package_digest_mismatch",
                details={
                    "package": package_name,
                    "committed": taskset_ref.package.digest,
                    "resolved": resolved,
                },
            )
        return resolved


def _declared_source_digest(engine_root: Path, package_name: str) -> Digest:
    """Return what the installed engine's descriptor says one package hashes to."""
    descriptor = read_engine_descriptor(engine_root)
    for package in descriptor.packages:
        if package.name == package_name:
            return package.source_digest
    raise EngineError(
        f"the engine descriptor lists no package named {package_name}",
        code="engine_package_missing",
        details={
            "package": package_name,
            "available": [entry.name for entry in descriptor.packages],
        },
    )


def _require_supported_reference(
    taskset_ref: TasksetRef, selection: TaskSelection
) -> None:
    """Refuse a reference this work package cannot resolve honestly."""
    if taskset_ref.package.kind != "embedded":
        raise ValidationError(
            f"WP5 resolves the embedded reference package only, not a "
            f"{taskset_ref.package.kind} package",
            code="taskset_package_kind_unsupported",
            details={"kind": taskset_ref.package.kind, "package": taskset_ref.id},
        )

    unsupported = sorted(set(taskset_ref.config) - set(SUPPORTED_CONFIG_KEYS))
    if unsupported:
        raise ValidationError(
            "the taskset configuration sets "
            + ", ".join(unsupported)
            + ", and nothing in WP5 would apply it",
            code="taskset_config_unsupported",
            details={
                "unsupported_keys": list(unsupported),
                "supported_keys": list(SUPPORTED_CONFIG_KEYS),
            },
        )

    configured = taskset_ref.config.get("num_tasks")
    if configured is not None and configured != selection.num_tasks:
        raise ValidationError(
            f"the taskset configuration asks for {configured} tasks but the "
            f"selection asks for {selection.num_tasks}",
            code="taskset_config_conflict",
            details={"config": configured, "selection": selection.num_tasks},
        )


def _last_line(text: str) -> str:
    """Return the last meaningful line of a child process's diagnostics."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else "the engine reported no diagnostics"
