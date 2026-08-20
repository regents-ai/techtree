"""Two real child processes, run as one comparison. Spec sections 6.15, 6.16.

The unit tests drive the scheduler with stubs, which is how its decisions get
provoked. This one gives it real processes — started for real, in their own
process groups, writing real files — and asks the questions a stub cannot
answer: were the two children genuinely alive at the same time, did the run's
journal end up describing that, and is the diagnostic record of what was
started good enough to clean up after a crash.

The children are shell scripts rather than evaluations. Everything this test is
about happens above the child: the scheduler cannot tell an ``eval`` from a
loop that appends lines to ``traces.jsonl``, and the difference costs a
container, forty minutes and real money to observe.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Final

import pytest

from fixtures.runs.support import run_harness
from techtree.canonical import sha256_digest_bytes
from techtree.models.campaign import VariantSchedule
from techtree.models.run import RunPhase, RunRequest
from techtree.paths import TechtreePaths, paths_from_root
from techtree.runs.child_registry import ChildRegistry, children_record_path
from techtree.runs.events import VARIANT_COMPLETED, VARIANT_PROGRESS, VARIANT_STARTED
from techtree.runs.executor import clear_local_cancellation
from techtree.runs.store import RunStore
from techtree.runs.variants import VariantPair, VariantScheduler
from techtree.verifiers.child import VerifiersChild
from techtree.verifiers.models import VariantExecutionPlan, VariantName
from techtree.verifiers.outputs import TRACES_FILENAME
from techtree.verifiers.supervisor import SUPERVISOR_FAILURE_EXIT_CODE

pytestmark = pytest.mark.integration

_TASK_COUNT: Final = 4

#: Each "episode" costs this long, so the two children overlap for most of
#: their lives and a poller gets several looks at each of them.
_EPISODE_SECONDS: Final = 0.3


def _script(episodes: int, *, exit_code: int = 0) -> str:
    """Return a shell child that appends whole episodes and then exits.

    Written the way the engine writes: one whole newline-terminated JSON object
    per finished episode, appended to a file in the working directory.
    """
    return (
        f": > {TRACES_FILENAME}; "
        f"for i in $(seq 1 {episodes}); do sleep {_EPISODE_SECONDS}; "
        f"printf '{{\"ok\": true}}\\n' >> {TRACES_FILENAME}; done; "
        f"exit {exit_code}"
    )


def _plan(variant: VariantName, root: Path) -> VariantExecutionPlan:
    """Build a plan whose inputs are all present on disk."""
    directory = root / variant.value
    directory.mkdir(parents=True, exist_ok=True)
    config = directory / "input.toml"
    config.write_text("num_tasks = 4\n")
    manifest = directory / "manifest.json"
    manifest.write_text("{}")
    return VariantExecutionPlan(
        variant=variant,
        experiment_manifest_digest=sha256_digest_bytes(variant.value.encode()),
        experiment_manifest_path=str(manifest),
        verifiers_input_config_path=str(config),
        verifiers_output_dir=str(directory / "run"),
        skill_paths=[],
        task_count=_TASK_COUNT,
        max_concurrent=2,
    )


def _child(
    plan: VariantExecutionPlan, paths: TechtreePaths, script: str
) -> VerifiersChild:
    """Build a real child process that behaves like a short evaluation."""
    output = Path(plan.verifiers_output_dir)
    return VerifiersChild(
        variant=plan.variant,
        argv=["/bin/sh", "-c", script],
        cwd=output,
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        stdout_path=output / "stdout.log",
        stderr_path=output / "stderr.log",
        supervision_record_path=output / "supervision.json",
    )


@pytest.fixture
def started(tmp_path: Path) -> tuple[TechtreePaths, RunStore, RunRequest, VariantPair]:
    """A real run, projected as far as the concurrent phase may be entered from."""
    clear_local_cancellation()
    home = tmp_path / "home"
    harness = run_harness(home)
    run_id = harness.start().state.run_id
    harness.run_store.append(run_id, phase=RunPhase.VALIDATING_TASKSET)
    pair = VariantPair(
        baseline=_plan(VariantName.BASELINE, tmp_path / "variants"),
        candidate=_plan(VariantName.CANDIDATE, tmp_path / "variants"),
    )
    return (
        paths_from_root(home),
        harness.run_store,
        harness.request(run_id),
        pair,
    )


def test_both_children_are_alive_at_the_same_time(
    started: tuple[TechtreePaths, RunStore, RunRequest, VariantPair],
) -> None:
    """Side by side is a scientific control, so it is checked on the clock."""
    paths, store, request, pair = started
    scheduler = VariantScheduler(
        run_store=store, child_registry=ChildRegistry(), poll_interval_seconds=0.05
    )

    outcome = scheduler.execute_parallel(
        run_id=request.run_id,
        run_root=paths.run_dir(request.run_id),
        pair=pair,
        baseline_child=_child(pair.baseline, paths, _script(_TASK_COUNT)),
        candidate_child=_child(pair.candidate, paths, _script(_TASK_COUNT)),
    )

    baseline, candidate = outcome.outcomes
    assert baseline.exit_code == 0
    assert candidate.exit_code == 0
    assert not baseline.cancelled
    assert not candidate.cancelled
    # Each child's own recorded interval overlaps the other's.
    assert baseline.started_at < candidate.finished_at
    assert candidate.started_at < baseline.finished_at

    assert outcome.schedule is VariantSchedule.PARALLEL
    assert outcome.skew is not None
    # The second launch waits for a process to be forked, not for an episode.
    assert outcome.skew.seconds < _EPISODE_SECONDS


def test_the_run_journal_describes_both_sides_of_the_comparison(
    started: tuple[TechtreePaths, RunStore, RunRequest, VariantPair],
) -> None:
    """A watcher reading the log alone can follow both variants."""
    paths, store, request, pair = started
    VariantScheduler(
        run_store=store, child_registry=ChildRegistry(), poll_interval_seconds=0.05
    ).execute_parallel(
        run_id=request.run_id,
        run_root=paths.run_dir(request.run_id),
        pair=pair,
        baseline_child=_child(pair.baseline, paths, _script(_TASK_COUNT)),
        candidate_child=_child(pair.candidate, paths, _script(_TASK_COUNT)),
    )

    events = _events(paths, request.run_id)
    kinds = [event["kind"] for event in events]
    assert kinds.count(VARIANT_STARTED) == 2
    assert kinds.count(VARIANT_COMPLETED) == 2
    assert VARIANT_PROGRESS in kinds

    for event in events:
        if event["kind"] in {VARIANT_STARTED, VARIANT_PROGRESS, VARIANT_COMPLETED}:
            assert event["phase"] == RunPhase.RUNNING_VARIANTS.value

    state = store.state(request.run_id)
    assert state.phase is RunPhase.RUNNING_VARIANTS
    for side in ("baseline", "candidate"):
        assert state.variant_progress[side].completed == _TASK_COUNT
        assert state.variant_progress[side].state == "completed"


def test_the_children_record_survives_the_run_for_manual_cleanup(
    started: tuple[TechtreePaths, RunStore, RunRequest, VariantPair],
) -> None:
    """A worker that died would leave this file and nothing else."""
    paths, store, request, pair = started
    run_root = paths.run_dir(request.run_id)
    VariantScheduler(
        run_store=store, child_registry=ChildRegistry(), poll_interval_seconds=0.05
    ).execute_parallel(
        run_id=request.run_id,
        run_root=run_root,
        pair=pair,
        baseline_child=_child(pair.baseline, paths, _script(_TASK_COUNT)),
        candidate_child=_child(pair.candidate, paths, _script(_TASK_COUNT)),
    )

    record = json.loads(children_record_path(run_root).read_text())
    assert record["schedule"] == "parallel_variants"
    assert [row["variant"] for row in record["children"]] == ["baseline", "candidate"]
    assert all(isinstance(row["pid"], int) for row in record["children"])
    assert record["launch_skew_seconds"] >= 0.0


def test_a_failed_variant_stops_its_sibling_and_keeps_both_partial_outputs(
    started: tuple[TechtreePaths, RunStore, RunRequest, VariantPair],
) -> None:
    """A pair is the unit of a comparison, and its evidence outlives its failure."""
    from techtree.errors import RunError

    paths, store, request, pair = started
    scheduler = VariantScheduler(
        run_store=store, child_registry=ChildRegistry(), poll_interval_seconds=0.05
    )

    with pytest.raises(RunError):
        scheduler.execute_parallel(
            run_id=request.run_id,
            run_root=paths.run_dir(request.run_id),
            pair=pair,
            baseline_child=_child(pair.baseline, paths, _script(1, exit_code=3)),
            candidate_child=_child(pair.candidate, paths, _script(400)),
        )

    for variant in (VariantName.BASELINE, VariantName.CANDIDATE):
        output = Path(pair.plan(variant).verifiers_output_dir)
        assert (output / TRACES_FILENAME).is_file()
        assert (output / "stdout.log").is_file()
        # Nothing the children wrote is removed to tidy a failure up.
        mode = stat.S_IMODE((output / "stdout.log").stat().st_mode)
        assert mode == 0o600


def test_an_evaluation_that_cannot_be_launched_never_leaves_its_sibling_running(
    started: tuple[TechtreePaths, RunStore, RunRequest, VariantPair],
) -> None:
    """One live side of a comparison is money spent on nothing.

    The evaluation that does not exist is now discovered by its supervisor
    rather than by the worker's own ``Popen``: what the worker starts is the
    supervisor, which starts the evaluation and reports 125 when it cannot.
    The property under test is unchanged — the sibling does not go on running —
    and the supervision record is what says which of the two failed.
    """
    from techtree.errors import RunError

    paths, store, request, pair = started
    candidate_output = Path(pair.candidate.verifiers_output_dir)
    baseline = _child(pair.baseline, paths, _script(400))
    candidate = VerifiersChild(
        variant=VariantName.CANDIDATE,
        argv=[str(tmp_missing := Path("/nonexistent/techtree-eval"))],
        cwd=candidate_output,
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        stdout_path=candidate_output / "stdout.log",
        stderr_path=candidate_output / "stderr.log",
        supervision_record_path=candidate_output / "supervision.json",
    )
    assert not tmp_missing.exists()

    scheduler = VariantScheduler(
        run_store=store,
        child_registry=ChildRegistry(),
        poll_interval_seconds=0.05,
        grace_seconds=2.0,
    )
    with pytest.raises(RunError):
        scheduler.execute_parallel(
            run_id=request.run_id,
            run_root=paths.run_dir(request.run_id),
            pair=pair,
            baseline_child=baseline,
            candidate_child=candidate,
        )
    assert baseline.poll() is not None
    assert candidate.poll() == SUPERVISOR_FAILURE_EXIT_CODE

    record = json.loads((candidate_output / "supervision.json").read_text())
    assert record["reason"] == "launch_failed"
    assert record["variant"] == VariantName.CANDIDATE.value


def _events(paths: TechtreePaths, run_id: str) -> list[dict[str, object]]:
    """Return one run's whole event log as plain dictionaries."""
    path = paths.run_dir(run_id) / "events.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


if sys.platform == "win32":  # pragma: no cover - the shell children are POSIX
    pytestmark = pytest.mark.skip(reason="the scheduler's children are POSIX shells")
