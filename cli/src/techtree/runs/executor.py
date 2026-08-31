"""What executes a run, and where it may be interrupted. Spec PR8 §8.5.

:class:`RunExecutor` is the seam the whole slice exists to establish. A future
real executor — Verifiers evaluation, a Hermes harness, a Docker subject —
implements this one method and inherits the entire lifecycle around it: the
request, the staged inputs, the validation provider, the event journal, the
cancellation boundaries, and the CLI that watches all of it. Only the body
changes.

Cancellation is cooperative and deliberately so. A worker that could be killed
mid-write would leave a run whose journal and artifacts disagreed, so the CLI
never kills it: it appends ``cancel.requested`` and signals the process, and
the executor notices at a boundary of its own choosing and unwinds. The two
things it notices are here.

:func:`raise_if_cancel_requested` reads the run's projected phase, which is how
a cancellation requested by a *different process* reaches this one.
:func:`request_local_cancellation` is the other direction: a signal handler in
this process cannot safely read a file or take a lock, so it sets a flag that
the same check consults. Either is enough to stop the run, and both funnel into
one :class:`~techtree.errors.CancellationError` so that no executor has to know
which of them happened.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Protocol

from techtree.errors import CancellationError
from techtree.models.run import RunPhase, RunRequest
from techtree.models.uplift_report import UpliftReport
from techtree.runs.artifacts import RunArtifactStore
from techtree.runs.store import RunStore
from techtree.runs.validation import TasksetValidationProvider

__all__ = [
    "DEFAULT_CANCELLATION_QUANTUM_SECONDS",
    "ExecutionContext",
    "RunExecutor",
    "clear_local_cancellation",
    "interruptible_sleep",
    "local_cancellation_requested",
    "raise_if_cancel_requested",
    "request_local_cancellation",
]

#: How often an interruptible delay looks up from what it is doing. Short
#: enough that a cancelled run stops promptly, long enough that waiting is not
#: itself the work.
DEFAULT_CANCELLATION_QUANTUM_SECONDS: Final = 0.05

#: Set by this process's signal handlers. Process-wide rather than passed
#: around because a signal arrives at the process, not at an object, and the
#: handler must do nothing but set it.
_LOCAL_CANCELLATION: Final[threading.Event] = threading.Event()


@dataclass(frozen=True)
class ExecutionContext:
    """Everything one execution of one run is given."""

    request: RunRequest
    run_store: RunStore
    artifact_store: RunArtifactStore
    validation_provider: TasksetValidationProvider
    clock: Callable[[], datetime]


class RunExecutor(Protocol):
    """Executes one run to a terminal scientific artifact."""

    def execute(self, context: ExecutionContext) -> UpliftReport:
        """Execute one run and return the report it produced."""
        ...


def request_local_cancellation() -> None:
    """Record that this process has been asked to stop.

    Safe to call from a signal handler: it sets an event and returns.
    """
    _LOCAL_CANCELLATION.set()


def clear_local_cancellation() -> None:
    """Forget any local cancellation request.

    A worker process handles exactly one run, so this exists for tests, which
    share one process across many runs.
    """
    _LOCAL_CANCELLATION.clear()


def local_cancellation_requested() -> bool:
    """Return whether this process has been signalled to stop."""
    return _LOCAL_CANCELLATION.is_set()


def raise_if_cancel_requested(run_store: RunStore, run_id: str) -> None:
    """Raise when this run has been asked to stop, from anywhere."""
    if local_cancellation_requested():
        raise CancellationError(
            f"run {run_id} was signalled to stop",
            details={"run_id": run_id, "requested_by": "signal"},
        )
    if run_store.state(run_id).phase is RunPhase.CANCEL_REQUESTED:
        raise CancellationError(
            f"run {run_id} was asked to stop",
            details={"run_id": run_id, "requested_by": "run_journal"},
        )


def interruptible_sleep(
    *,
    seconds: float,
    check: Callable[[], None],
    quantum: float = DEFAULT_CANCELLATION_QUANTUM_SECONDS,
) -> None:
    """Wait, looking up every ``quantum`` seconds to see whether to stop.

    ``check`` is called before the first wait and after every one of them, so
    a delay of zero still costs one check and a cancellation never has to wait
    out a whole interval to be noticed.
    """
    if quantum <= 0:
        raise ValueError("an interruptible delay needs a positive quantum")

    check()
    deadline = time.monotonic() + max(seconds, 0.0)
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(quantum, remaining))
        check()
