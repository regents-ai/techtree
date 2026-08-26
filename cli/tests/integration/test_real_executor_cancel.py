"""Stopping a concurrent comparison. Spec sections 6.15, 6.16, 6.22.

Cancelling a run that is evaluating two subjects at once has to reach two
process groups, not one, and it has to reach them in a way that lets each of
them tear its containers down before it dies. Those are the two claims here,
and both are made against real processes: a stub can be asked whether
``terminate`` was called, but only a real child can be asked whether it is
still in the process table afterwards.

The children are shell scripts. A process group and a ``SIGTERM`` behave the
same whether the process inside is a shell loop or an evaluation, and the
difference costs a container and real money to observe.

The cancellation itself comes from another thread, because in production it
comes from another *process*: the CLI appends ``cancel.requested`` to the run's
journal and the worker notices at a boundary it chose. Nothing in this test
signals the worker directly, so what is being checked is that the journal alone
is enough.
"""

from __future__ import annotations

import errno
import json
import os
import threading
import time
from pathlib import Path
from typing import Final

import pytest

from fixtures.runs.support import run_harness
from techtree.canonical import sha256_digest_bytes
from techtree.errors import CancellationError
from techtree.models.run import RunPhase, RunRequest
from techtree.paths import TechtreePaths, paths_from_root
from techtree.runs.child_registry import ChildRegistry
from techtree.runs.executor import clear_local_cancellation, request_local_cancellation
from techtree.runs.store import RunStore
from techtree.runs.variants import VariantPair, VariantScheduler
from techtree.verifiers.child import VerifiersChild
from techtree.verifiers.models import VariantExecutionPlan, VariantName
from techtree.verifiers.outputs import TRACES_FILENAME

pytestmark = pytest.mark.integration

_TASK_COUNT: Final = 6

#: Long enough that a cancellation always lands mid-run, short enough that a
#: broken test does not hang a suite.
_EPISODE_SECONDS: Final = 2.0

#: How long a terminated child is given to shut down. Real evaluations get
#: thirty seconds to tear a container down; a shell loop needs none of it, and
#: what is being checked is that the group dies, not how patiently.
_GRACE_SECONDS: Final = 5.0


def _script() -> str:
    """A child that keeps working, and would keep working for a long time."""
    return (
        f": > {TRACES_FILENAME}; "
        f"for i in $(seq 1 {_TASK_COUNT}); do sleep {_EPISODE_SECONDS}; "
        f"printf '{{\"ok\": true}}\\n' >> {TRACES_FILENAME}; done"
    )


def _plan(variant: VariantName, root: Path) -> VariantExecutionPlan:
    """Build a plan whose inputs are all present on disk."""
    directory = root / variant.value
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "input.json").write_text('{"num_tasks": 6}\n')
    (directory / "manifest.json").write_text("{}")
    return VariantExecutionPlan(
        variant=variant,
        experiment_manifest_digest=sha256_digest_bytes(variant.value.encode()),
        experiment_manifest_path=str(directory / "manifest.json"),
        verifiers_input_config_path=str(directory / "input.json"),
        verifiers_output_dir=str(directory / "run"),
        skill_paths=[],
        task_count=_TASK_COUNT,
        max_concurrent=2,
    )


def _child(plan: VariantExecutionPlan) -> VerifiersChild:
    """Build a real child process in its own process group."""
    output = Path(plan.verifiers_output_dir)
    return VerifiersChild(
        variant=plan.variant,
        argv=["/bin/sh", "-c", _script()],
        cwd=output,
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        stdout_path=output / "stdout.log",
        stderr_path=output / "stderr.log",
        supervision_record_path=output / "supervision.json",
    )


@pytest.fixture
def started(tmp_path: Path) -> tuple[TechtreePaths, RunStore, RunRequest, VariantPair]:
    """A real run, ready for the concurrent phase, with two plans to execute."""
    clear_local_cancellation()
    home = tmp_path / "home"
    harness = run_harness(home)
    run_id = harness.start().state.run_id
    harness.run_store.append(run_id, phase=RunPhase.VALIDATING_TASKSET)
    return (
        paths_from_root(home),
        harness.run_store,
        harness.request(run_id),
        VariantPair(
            baseline=_plan(VariantName.BASELINE, tmp_path / "variants"),
            candidate=_plan(VariantName.CANDIDATE, tmp_path / "variants"),
        ),
    )


def _alive(pid: int | None) -> bool:
    """Whether a process id still names a live process."""
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except OSError as error:
        return error.errno == errno.EPERM
    return True


def test_a_cancellation_in_the_journal_stops_both_process_groups(
    started: tuple[TechtreePaths, RunStore, RunRequest, VariantPair],
) -> None:
    """One line appended by another process ends both live evaluations."""
    paths, store, request, pair = started
    registry = ChildRegistry()
    baseline = _child(pair.baseline)
    candidate = _child(pair.candidate)

    def ask_to_stop() -> None:
        """Wait for both evaluations to be working, then cancel as the CLI does.

        Registration means the supervisor is up; the evaluation it supervises
        is one ``fork`` behind it. What this test is about is a cancellation
        that lands *mid-run*, so the trigger is both evaluations having started
        to write evidence rather than both children having been registered.
        """
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            if len(registry.children(request.run_id)) == 2 and all(
                (
                    Path(pair.plan(variant).verifiers_output_dir) / TRACES_FILENAME
                ).is_file()
                for variant in (VariantName.BASELINE, VariantName.CANDIDATE)
            ):
                store.request_cancel(request.run_id, requested_by="test")
                return
            time.sleep(0.05)
        raise AssertionError("both evaluations never started working")

    canceller = threading.Thread(target=ask_to_stop, name="canceller")
    canceller.start()
    try:
        with pytest.raises(CancellationError):
            VariantScheduler(
                run_store=store,
                child_registry=registry,
                poll_interval_seconds=0.05,
                grace_seconds=_GRACE_SECONDS,
            ).execute_parallel(
                run_id=request.run_id,
                run_root=paths.run_dir(request.run_id),
                pair=pair,
                baseline_child=baseline,
                candidate_child=candidate,
            )
    finally:
        canceller.join(timeout=30.0)

    # Both children are gone, and the registry is holding nothing.
    assert not _alive(baseline.pid)
    assert not _alive(candidate.pid)
    assert registry.children(request.run_id) == ()

    # Neither variant finished, and the partial evidence of both survives.
    for variant in (VariantName.BASELINE, VariantName.CANDIDATE):
        output = Path(pair.plan(variant).verifiers_output_dir)
        assert (output / TRACES_FILENAME).is_file()
        assert len((output / TRACES_FILENAME).read_text().splitlines()) < _TASK_COUNT

    assert store.state(request.run_id).phase is RunPhase.CANCEL_REQUESTED


def test_a_signal_to_this_process_stops_both_children_too(
    started: tuple[TechtreePaths, RunStore, RunRequest, VariantPair],
) -> None:
    """A worker signalled directly unwinds the same way a journal cancel does."""
    paths, store, request, pair = started
    registry = ChildRegistry()
    baseline = _child(pair.baseline)
    candidate = _child(pair.candidate)

    def signal_us() -> None:
        """Set the flag a signal handler would set, once both children are up."""
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            if len(registry.children(request.run_id)) == 2:
                request_local_cancellation()
                return
            time.sleep(0.05)

    watcher = threading.Thread(target=signal_us, name="signaller")
    watcher.start()
    try:
        with pytest.raises(CancellationError):
            VariantScheduler(
                run_store=store,
                child_registry=registry,
                poll_interval_seconds=0.05,
                grace_seconds=_GRACE_SECONDS,
            ).execute_parallel(
                run_id=request.run_id,
                run_root=paths.run_dir(request.run_id),
                pair=pair,
                baseline_child=baseline,
                candidate_child=candidate,
            )
    finally:
        watcher.join(timeout=30.0)
        clear_local_cancellation()

    assert not _alive(baseline.pid)
    assert not _alive(candidate.pid)
    # The run itself was never asked to stop, so its journal still says so: a
    # signalled worker records the cancellation on its way out, not here.
    assert store.state(request.run_id).phase is RunPhase.RUNNING_VARIANTS
    events = [
        json.loads(line)
        for line in (paths.run_dir(request.run_id) / "events.jsonl")
        .read_text()
        .splitlines()
    ]
    assert events[-1]["phase"] == RunPhase.RUNNING_VARIANTS.value
