"""Which evaluation children a run currently owns. Spec section 6.16.

Two variants running side by side turn a single question — "stop this run" —
into two answers, and neither of them is reachable from the run's journal. The
journal records that a run was asked to stop; only the process that started the
children knows which processes those are. This module is that knowledge, and it
is deliberately the smallest thing that can hold it: an in-memory map from run
identifier to the live children, guarded by a lock because the poller and a
signal-driven wind-down touch it from different threads.

Nothing here is scientific truth. A registry entry says a process exists, not
that an experiment happened, and the registry is discarded when the worker
exits. What survives the worker is one diagnostic file,
``execution/children.json``, written once both children are up: if the worker
dies without unwinding, that file is the only record of which process groups
were left holding Docker containers, and an operator cleaning up by hand has
nothing else to go on.

The file is written after both children start rather than after each one,
because a write between the two launches would land inside the interval the
run is measuring as launch skew.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, Protocol, runtime_checkable

from techtree.canonical import to_json_value
from techtree.fs import atomic_write_json, ensure_private_directory
from techtree.models.base import Digest, JsonValue
from techtree.models.campaign import VariantSchedule
from techtree.verifiers.models import ChildProcessOutcome, VariantName

__all__ = [
    "CHILDREN_FILENAME",
    "CHILDREN_RECORD_SCHEMA_VERSION",
    "EXECUTION_DIRECTORY",
    "ChildRegistry",
    "EvaluationChild",
    "LaunchedChild",
    "children_record_path",
    "execution_dir",
    "write_children_record",
]

#: Where a run keeps what its execution did, as opposed to what it was given.
#: Spec section 6.19.
EXECUTION_DIRECTORY: Final = "execution"

#: The diagnostic record of which processes a run started. Spec sections 6.16
#: and 6.19.
CHILDREN_FILENAME: Final = "children.json"

#: A local operational document, not a protocol object. It is named and
#: versioned anyway so that a file found after a crash says what it is.
CHILDREN_RECORD_SCHEMA_VERSION: Final = "techtree.run-children.v1"

#: Variants always appear in comparison order, never in start order, so that a
#: registry listing reads the same way whichever child happened to be quicker.
_VARIANT_ORDER: Final[tuple[VariantName, ...]] = (
    VariantName.BASELINE,
    VariantName.CANDIDATE,
)


@runtime_checkable
class EvaluationChild(Protocol):
    """The part of one evaluation child process a run's control path uses.

    :class:`~techtree.verifiers.child.VerifiersChild` is the implementation.
    Stating the surface as a protocol is what lets the scheduler's own
    behaviour — the start barrier, sibling termination, the launch-skew
    measurement — be tested without a subprocess, a container, or a provider.
    """

    @property
    def variant(self) -> VariantName:
        """Which side of the comparison this child is running."""
        ...

    @property
    def pid(self) -> int | None:
        """The child's process id once it has started."""
        ...

    @property
    def argv_digest(self) -> Digest:
        """The digest of this child's invocation."""
        ...

    def start(self) -> int:
        """Start the child and return its pid."""
        ...

    def poll(self) -> int | None:
        """Return the exit code, or ``None`` while the child is still running."""
        ...

    def terminate(self, grace_seconds: float = ...) -> None:
        """Stop the child's process group, allowing runtime teardown first."""
        ...

    def outcome(self) -> ChildProcessOutcome:
        """Describe the finished child."""
        ...


@dataclass(frozen=True)
class LaunchedChild:
    """One child as it was at the moment the run started it.

    The start time is the parent's observation of the launch rather than the
    child's own, because it is taken the instant ``start`` returns and the
    child's is only readable once the process has exited. The two bracket each
    other within the cost of a ``fork``.
    """

    variant: VariantName
    pid: int | None
    argv_digest: Digest
    started_at: datetime


class ChildRegistry:
    """The live evaluation children of every run this process is executing.

    Registration is by variant, so a run holds at most one child per side and
    re-registering a variant replaces it rather than accumulating a second
    entry that nothing would ever terminate.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._children: dict[str, dict[VariantName, EvaluationChild]] = {}

    def register(self, run_id: str, child: EvaluationChild) -> None:
        """Record that this run owns one child process."""
        with self._lock:
            self._children.setdefault(run_id, {})[child.variant] = child

    def children(self, run_id: str) -> tuple[EvaluationChild, ...]:
        """Return this run's live children, in comparison order."""
        with self._lock:
            registered = dict(self._children.get(run_id, {}))
        return tuple(
            registered[variant] for variant in _VARIANT_ORDER if variant in registered
        )

    def terminate_all(self, run_id: str, grace_seconds: float) -> None:
        """Stop every child this run owns, then forget them.

        Each child is given the same grace period rather than sharing one, so
        the second variant's containers get as long to tear down as the first
        variant's did. Every child is attempted even if an earlier one raised:
        a run that failed to stop one process group must still stop the other.
        """
        failures: list[BaseException] = []
        for child in self.children(run_id):
            try:
                child.terminate(grace_seconds)
            except BaseException as error:
                failures.append(error)
            finally:
                self.unregister(run_id, child.variant)
        if failures:
            raise failures[0]

    def unregister(self, run_id: str, variant: VariantName) -> None:
        """Forget one child, and the run itself once it owns none."""
        with self._lock:
            registered = self._children.get(run_id)
            if registered is None:
                return
            registered.pop(variant, None)
            if not registered:
                del self._children[run_id]


def execution_dir(run_root: Path) -> Path:
    """Return where one run records what its execution did."""
    return run_root / EXECUTION_DIRECTORY


def children_record_path(run_root: Path) -> Path:
    """Return where one run's diagnostic child record lives."""
    return execution_dir(run_root) / CHILDREN_FILENAME


def write_children_record(
    *,
    run_root: Path,
    run_id: str,
    schedule: VariantSchedule,
    children: Sequence[LaunchedChild],
    launch_skew_seconds: float | None,
) -> Path:
    """Write the diagnostic record of what this run started.

    ``launch_skew_seconds`` is the gap between the two launches under a
    parallel schedule and ``None`` under a sequential one, where the second
    child does not exist yet and a gap would be a measurement of the first
    variant's duration rather than of a launch.
    """
    path = children_record_path(run_root)
    ensure_private_directory(path.parent)
    rows: list[JsonValue] = [
        {
            "variant": child.variant.value,
            "pid": child.pid,
            "argv_digest": child.argv_digest,
            "started_at": to_json_value(child.started_at),
        }
        for child in children
    ]
    document: dict[str, JsonValue] = {
        "schema_version": CHILDREN_RECORD_SCHEMA_VERSION,
        "run_id": run_id,
        "schedule": schedule.value,
        "launch_skew_seconds": launch_skew_seconds,
        "children": rows,
    }
    atomic_write_json(path, document)
    return path
