"""What the detached worker does with a run. Spec PR8 §8.10.

This is the only code that runs in the worker process, and it is written for
the two facts that make that process unusual: nobody is watching it, and it may
be asked to stop at any moment.

Nobody is watching, so everything it learns has to be written down. Its process
id goes into the run's journal as its first act — spec §9.5 depends on that,
because a launcher that crashed before recording the pid must still leave a run
that can be found and signalled. A heartbeat thread then refreshes one file
every couple of seconds, which is what lets a later reader distinguish "still
working" from "died holding the run open" without a supervisor.

It may be asked to stop, so the signal handlers do the least possible work: set
a flag, return. Everything else — appending the cancellation, winding down the
executor, writing the terminal event — happens on the main thread at a boundary
the executor chose. A handler that took the run lock could deadlock against the
work it interrupted, and a handler that wrote a file could tear it.

Every exit is terminal for the run and specific for the caller. A cancelled run
exits 130, the shell's convention for interruption. A typed failure exits its
own documented code. Anything else is a defect: the message is scrubbed before
it is stored, the run is recorded as failed, and the process exits 5. In no
case does a raw traceback reach ``RunState.error``, which is a protocol-visible
field that a host agent will read back.
"""

from __future__ import annotations

import os
import signal
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import FrameType
from typing import Final

from techtree.canonical import digest_object, to_json_value
from techtree.constants import DEFAULT_WORKER_HEARTBEAT_SECONDS
from techtree.engines.registry import EngineRegistry
from techtree.errors import (
    CancellationError,
    RunError,
    TechtreeError,
    error_to_cli_error,
    exit_code_for,
    sanitize_exception_message,
    sanitize_text,
)
from techtree.models.run import RunPhase, RunRequest
from techtree.models.uplift_report import UpliftReport
from techtree.paths import TechtreePaths, default_paths, paths_from_root
from techtree.runs.artifacts import RunArtifactStore
from techtree.runs.child_registry import ChildRegistry
from techtree.runs.events import DETAIL_ERROR, RUN_CANCELLED, RUN_FAILED
from techtree.runs.executor import (
    ExecutionContext,
    RunExecutor,
    request_local_cancellation,
)
from techtree.runs.fake import FakeRunExecutor
from techtree.runs.machine import is_terminal
from techtree.runs.real import (
    RealVerifiersExecutor,
    campaign_is_executable,
    real_execution_result_path,
)
from techtree.runs.store import RunStore
from techtree.runs.validation import TasksetValidationProvider
from techtree.settings import load_settings
from techtree.tasksets.provider import worker_validation_provider

__all__ = [
    "EXIT_CANCELLED",
    "EXIT_UNEXPECTED",
    "REPORT_STAGE_UNAVAILABLE",
    "TECHTREE_HOME_VARIABLE",
    "ExecutorFactory",
    "ValidationProviderFactory",
    "execute_run",
    "executor_for",
    "handle_worker_cancelled",
    "handle_worker_failure",
    "heartbeat_loop",
    "install_signal_handlers",
    "validation_provider_for",
    "worker_log",
    "worker_paths",
]

type AnyExecutor = RunExecutor | RealVerifiersExecutor
type ExecutorFactory = Callable[[RunRequest], AnyExecutor]
type ValidationProviderFactory = Callable[[RunRequest], TasksetValidationProvider]

#: The shell's convention for "terminated by an interrupt", which is what a
#: cancelled run is from the caller's point of view.
EXIT_CANCELLED: Final = 130

#: What an unexpected exception exits with. Spec PR8 §8.10 fixes the value.
EXIT_UNEXPECTED: Final = 5

#: How the launcher tells the worker where Techtree keeps its state. The
#: worker inherits nothing else that could point at a run directory.
TECHTREE_HOME_VARIABLE: Final = "TECHTREE_HOME"

#: What a real execution that reached the end of WP6 reports. The evaluation
#: itself succeeded and its evidence is complete on disk; turning that evidence
#: into signed receipts and a comparison is WP7's work, and until it exists a
#: real run has no report to finish with. Spec section 6.22 fixes the boundary:
#: WP6 returns a ``RealExecutionResult`` and does not invent final uplift.
REPORT_STAGE_UNAVAILABLE: Final = "run_report_stage_unavailable"

_HEARTBEAT_SECONDS: Final = float(DEFAULT_WORKER_HEARTBEAT_SECONDS)


def worker_log(message: str) -> None:
    """Write one operational line to the run's log.

    The worker's stdout *is* ``worker.log``, so this is the whole logging
    apparatus. Every line goes through the scrubber on the way out rather
    than on the way to a reader: a credential that reached the file would be
    at rest on disk whether or not anything ever displayed it.
    """
    moment = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    print(f"{moment} {sanitize_text(message)}", flush=True)


def worker_paths() -> TechtreePaths:
    """Resolve where this worker's run lives.

    The launcher passes ``TECHTREE_HOME`` explicitly rather than letting the
    worker guess, so a run started against a temporary home is executed
    against that home and not against the operator's real one.
    """
    home = os.environ.get(TECHTREE_HOME_VARIABLE)
    if home:
        return paths_from_root(Path(home))
    return default_paths()


def executor_for(
    request: RunRequest,
    *,
    paths: TechtreePaths | None = None,
) -> RunExecutor | RealVerifiersExecutor:
    """Return the executor this run's Campaign is entitled to.

    The Campaign decides, not the request. Spec section 16 requires that the
    development executor stop being what a real Campaign gets, and a request
    cannot express the difference: it names the Climb it entered, and whether
    that Climb's subject is a real model on a real image or the placeholder
    pair this build ships is a fact about the Campaign. So the run's own staged
    Campaign is read and :func:`~techtree.runs.real.campaign_is_executable`
    answers it — the same predicate ``techtree doctor --for-evaluation`` uses,
    so an operator's pre-flight and the worker's choice can never disagree.
    """
    resolved = worker_paths() if paths is None else paths
    inputs = RunArtifactStore(resolved).load_inputs(request.run_id, request)
    if campaign_is_executable(inputs.campaign):
        return RealVerifiersExecutor(
            paths=resolved,
            engine_registry=EngineRegistry(resolved, load_settings(resolved)),
            child_registry=ChildRegistry(),
        )
    if request.executor_kind == "fake":
        return FakeRunExecutor()
    raise RunError(
        f"this build has no {request.executor_kind} executor",
        code="run_executor_unavailable",
        details={"run_id": request.run_id, "executor_kind": request.executor_kind},
    )


def validation_provider_for(
    request: RunRequest,
    *,
    paths: TechtreePaths | None = None,
) -> TasksetValidationProvider:
    """Return the validation source this run's Campaign actually has here.

    A Campaign whose taskset lives in a package the engine bundle ships is
    validated for real, with the pinned Verifiers build, before anything is
    scored on it. A Campaign whose taskset this build cannot obtain has only
    the publisher's snapshotted commitment, which a fake run may re-check
    because it produces nothing that could be mistaken for evidence. The
    routing reads the run's own inputs, so it lives in the provider rather
    than here; what happens is recorded in the run's validation marker either
    way.
    """
    if request.executor_kind == "fake":
        return worker_validation_provider(worker_paths() if paths is None else paths)
    raise RunError(
        "this build has no taskset validation source for a "
        f"{request.executor_kind} run",
        code="taskset_validation_provider_unavailable",
        details={"run_id": request.run_id},
    )


def install_signal_handlers(cancellation_event: threading.Event) -> None:
    """Make ``SIGTERM`` and ``SIGINT`` record a request and nothing else."""

    def handle(number: int, frame: FrameType | None) -> None:
        cancellation_event.set()

    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, handle)


def heartbeat_loop(
    *,
    stop_event: threading.Event,
    run_store: RunStore,
    run_id: str,
    interval_seconds: float,
) -> None:
    """Refresh the run's heartbeat until asked to stop.

    A heartbeat that cannot be written is not worth ending a run over — the
    run itself may be completing at that moment, and the store refuses to
    touch a run that has ended. The loop stops instead of failing the work.
    """
    while not stop_event.is_set():
        try:
            run_store.write_heartbeat(run_id, run_store.state(run_id).phase)
        except TechtreeError:
            return
        stop_event.wait(interval_seconds)


def execute_run(
    run_id: str,
    *,
    paths: TechtreePaths | None = None,
    executor_factory: ExecutorFactory | None = None,
    validation_provider_factory: ValidationProviderFactory | None = None,
) -> int:
    """Execute one run in this process and return the exit code."""
    resolved = worker_paths() if paths is None else paths
    run_store = RunStore(resolved)
    artifact_store = RunArtifactStore(resolved)

    try:
        request = run_store.get_request(run_id)
    except TechtreeError as error:
        # Nothing can be recorded against a run that cannot be read, so the
        # exit code is the only report available.
        return exit_code_for(error)

    worker_log(
        f"worker {os.getpid()} taking on run {run_id} with the "
        f"{request.executor_kind} executor"
    )

    try:
        _announce_worker(run_store, run_id)
    except TechtreeError as error:
        # A run that has already ended does not take on a second worker, and
        # there is nothing to record against it either.
        return exit_code_for(error)

    cancellation = threading.Event()
    install_signal_handlers(cancellation)
    _watch_for_signals(cancellation)

    stop_heartbeat = threading.Event()
    heartbeat = threading.Thread(
        target=heartbeat_loop,
        kwargs={
            "stop_event": stop_heartbeat,
            "run_store": run_store,
            "run_id": run_id,
            "interval_seconds": _HEARTBEAT_SECONDS,
        },
        name=f"techtree-heartbeat-{run_id}",
        daemon=True,
    )
    heartbeat.start()

    try:
        executor = (
            executor_for(request, paths=resolved)
            if executor_factory is None
            else executor_factory(request)
        )
        provider = (
            validation_provider_for(request, paths=resolved)
            if validation_provider_factory is None
            else validation_provider_factory(request)
        )
        produced = executor.execute(
            ExecutionContext(
                request=request,
                run_store=run_store,
                artifact_store=artifact_store,
                validation_provider=provider,
                clock=_utc_now,
            )
        )
        report = _require_report(produced, run_id=run_id, paths=resolved)
        _verify_recorded_result(run_store, run_id, digest_object(report))
    except CancellationError:
        worker_log(f"run {run_id} stopped because it was asked to")
        handle_worker_cancelled(run_store=run_store, run_id=run_id)
        return EXIT_CANCELLED
    except TechtreeError as error:
        worker_log(f"run {run_id} failed: {error.code}: {error.message}")
        handle_worker_failure(run_store=run_store, run_id=run_id, error=error)
        return exit_code_for(error)
    except Exception as unexpected:
        worker_log(
            f"run {run_id} failed unexpectedly: "
            f"{sanitize_exception_message(unexpected)}"
        )
        handle_worker_failure(run_store=run_store, run_id=run_id, error=unexpected)
        return EXIT_UNEXPECTED
    finally:
        stop_heartbeat.set()
        heartbeat.join(timeout=_HEARTBEAT_SECONDS)

    worker_log(f"run {run_id} completed and its report was recorded")
    return 0


def _require_report(
    produced: object,
    *,
    run_id: str,
    paths: TechtreePaths,
) -> UpliftReport:
    """Return the report the run finishes with, or say why there is none.

    A real evaluation produces complete evidence and no report: building
    receipts, checking the observed configurations against the declared ones
    and aggregating a result are WP7's, and WP6 deliberately stops short of
    inventing any of them (spec section 6.22). The evidence is written and
    named here rather than discarded, because it is exactly what the next
    stage reads and it is the expensive part of the run.
    """
    if isinstance(produced, UpliftReport):
        return produced
    raise RunError(
        "the evaluation finished and its results were recorded, but this "
        "build cannot yet turn them into a comparison report",
        code=REPORT_STAGE_UNAVAILABLE,
        details={
            "run_id": run_id,
            "results": str(real_execution_result_path(paths.run_dir(run_id))),
        },
    )


def handle_worker_failure(
    *,
    run_store: RunStore,
    run_id: str,
    error: Exception,
) -> None:
    """Record a scrubbed failure against the run, if it can still record one."""
    if isinstance(error, TechtreeError):
        cli_error = error_to_cli_error(error)
    else:
        cli_error = error_to_cli_error(
            TechtreeError(
                sanitize_exception_message(error),
                code="internal_error",
                details={"exception_type": type(error).__name__},
            )
        )

    try:
        if is_terminal(run_store.state(run_id).phase):
            return
        run_store.append(
            run_id,
            phase=RunPhase.FAILED,
            kind=RUN_FAILED,
            details={DETAIL_ERROR: to_json_value(cli_error)},
        )
    except TechtreeError:
        # The run's journal is unwritable. The exit code is then the only
        # thing the worker can still say, and it has already been decided.
        return


def handle_worker_cancelled(*, run_store: RunStore, run_id: str) -> None:
    """Record that the run stopped because it was asked to.

    A run signalled directly may not yet carry the request that a CLI
    cancellation would have appended, so the request is made first. It is
    idempotent, which is what lets both paths end the same way.
    """
    try:
        state = run_store.state(run_id)
        if is_terminal(state.phase):
            return
        if state.phase is not RunPhase.CANCEL_REQUESTED:
            run_store.request_cancel(run_id, requested_by="worker")
        run_store.append(run_id, phase=RunPhase.CANCELLED, kind=RUN_CANCELLED)
    except TechtreeError:
        return


def _announce_worker(run_store: RunStore, run_id: str) -> None:
    """Record this process as the run's worker, unless one is already named."""
    if run_store.state(run_id).worker_pid is not None:
        return
    run_store.write_pid(run_id, os.getpid())


def _watch_for_signals(cancellation: threading.Event) -> None:
    """Turn a signalled event into the executor's cancellation flag.

    The handler itself may only set an event. A tiny daemon thread waits on
    that event and does the one unsafe-in-a-handler thing that is needed:
    telling the executor, wherever it is, that this process is stopping.
    """

    def wait() -> None:
        cancellation.wait()
        request_local_cancellation()

    threading.Thread(target=wait, name="techtree-cancellation", daemon=True).start()


def _verify_recorded_result(run_store: RunStore, run_id: str, expected: str) -> None:
    """Require the journal to name the report the executor just produced."""
    recorded = run_store.state(run_id).result_digest
    if recorded == expected:
        return
    raise RunError(
        f"run {run_id} finished with a report its journal does not name",
        code="run_result_digest_mismatch",
        details={"run_id": run_id, "expected": expected, "recorded": recorded},
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)
