"""Reading progress out of an append-only trace file. Spec section 6.11.

Nothing here calls a model or starts an engine. A ``traces.jsonl`` is written by
hand, one record at a time, including the half-written last line a poller will
see on a real run, because that partial line is the one case the counter exists
to get right.
"""

from __future__ import annotations

import json
from pathlib import Path

from fixtures.runs.support import run_harness
from techtree.models.run import RunPhase, VariantProgress
from techtree.runs.events import (
    DETAIL_COMPLETED,
    DETAIL_STATE,
    DETAIL_VARIANT,
    VARIANT_PROGRESS,
)
from techtree.verifiers.models import VariantName
from techtree.verifiers.progress import (
    count_complete_jsonl_records,
    emit_progress_if_changed,
    inspect_progress,
    pending_progress,
)


def episode(index: int) -> str:
    """One whole episode record, as upstream would serialize it."""
    return json.dumps(
        {"id": f"ep-{index}", "env": "procedure-transfer-v1", "ok": True, "traces": []}
    )


def write_records(path: Path, count: int, *, trailing: str = "") -> Path:
    """Write ``count`` whole records, plus an optional unterminated tail."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(f"{episode(index)}\n" for index in range(count))
    path.write_text(body + trailing)
    return path


# ---------------------------------------------------------------------------
# Counting
# ---------------------------------------------------------------------------


def test_a_file_that_does_not_exist_yet_counts_as_nothing(tmp_path: Path) -> None:
    # The engine creates traces.jsonl a second or so after the child starts.
    # A poller that treated its absence as failure would fail every run.
    assert count_complete_jsonl_records(tmp_path / "traces.jsonl") == 0


def test_an_empty_file_counts_as_nothing(tmp_path: Path) -> None:
    # Upstream truncates the file to empty before the first rollout, so empty
    # means "started, nothing finished".
    path = write_records(tmp_path / "traces.jsonl", 0)
    assert count_complete_jsonl_records(path) == 0


def test_whole_records_are_counted(tmp_path: Path) -> None:
    path = write_records(tmp_path / "traces.jsonl", 5)
    assert count_complete_jsonl_records(path) == 5


def test_a_half_written_last_line_is_not_counted(tmp_path: Path) -> None:
    path = write_records(tmp_path / "traces.jsonl", 3, trailing='{"id": "ep-3", "ok')
    assert count_complete_jsonl_records(path) == 3


def test_a_terminated_line_that_is_not_json_is_not_counted(tmp_path: Path) -> None:
    path = write_records(tmp_path / "traces.jsonl", 2, trailing="not json at all\n")
    assert count_complete_jsonl_records(path) == 2


def test_a_json_value_that_is_not_an_object_is_not_an_episode(tmp_path: Path) -> None:
    path = write_records(tmp_path / "traces.jsonl", 2, trailing="[1, 2, 3]\n")
    assert count_complete_jsonl_records(path) == 2


def test_counting_never_touches_the_file(tmp_path: Path) -> None:
    # The file belongs to the child. Repairing a partial line would destroy the
    # evidence the reader came to measure.
    path = write_records(tmp_path / "traces.jsonl", 2, trailing='{"id": "ep-2"')
    before = path.read_bytes()

    count_complete_jsonl_records(path)

    assert path.read_bytes() == before


def test_a_record_longer_than_one_read_is_still_one_record(tmp_path: Path) -> None:
    # Real traces carry whole transcripts and easily exceed a single read.
    path = tmp_path / "traces.jsonl"
    path.write_text(json.dumps({"id": "ep-0", "pad": "x" * (4 << 20)}) + "\n")

    assert count_complete_jsonl_records(path) == 1


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------


def test_no_trace_file_yet_is_pending_rather_than_broken(tmp_path: Path) -> None:
    progress = inspect_progress(
        variant=VariantName.BASELINE,
        traces_path=tmp_path / "traces.jsonl",
        total=36,
        child_exit_code=None,
    )

    assert progress.state == "pending"
    assert progress.completed == 0


def test_a_live_child_with_finished_episodes_is_running(tmp_path: Path) -> None:
    path = write_records(tmp_path / "traces.jsonl", 7)

    progress = inspect_progress(
        variant=VariantName.BASELINE,
        traces_path=path,
        total=36,
        child_exit_code=None,
    )

    assert progress.state == "running"
    assert progress.completed == 7


def test_the_in_flight_count_never_exceeds_what_is_left(tmp_path: Path) -> None:
    path = write_records(tmp_path / "traces.jsonl", 35)

    progress = inspect_progress(
        variant=VariantName.BASELINE,
        traces_path=path,
        total=36,
        child_exit_code=None,
        max_concurrent=8,
    )

    assert progress.running == 1


def test_a_clean_exit_with_every_task_done_is_completed(tmp_path: Path) -> None:
    path = write_records(tmp_path / "traces.jsonl", 36)

    progress = inspect_progress(
        variant=VariantName.CANDIDATE,
        traces_path=path,
        total=36,
        child_exit_code=0,
    )

    assert progress.state == "completed"
    assert progress.running == 0


def test_a_clean_exit_that_left_tasks_undone_is_a_failure(tmp_path: Path) -> None:
    # A zero exit code is never sufficient on its own; the output decides.
    path = write_records(tmp_path / "traces.jsonl", 30)

    progress = inspect_progress(
        variant=VariantName.BASELINE,
        traces_path=path,
        total=36,
        child_exit_code=0,
    )

    assert progress.state == "failed"


def test_the_graceful_stop_code_reads_as_cancellation(tmp_path: Path) -> None:
    # A run somebody stopped did not produce a wrong answer; it produced none.
    path = write_records(tmp_path / "traces.jsonl", 4)

    progress = inspect_progress(
        variant=VariantName.BASELINE,
        traces_path=path,
        total=36,
        child_exit_code=130,
    )

    assert progress.state == "cancelled"


def test_a_nonzero_exit_is_a_failure(tmp_path: Path) -> None:
    path = write_records(tmp_path / "traces.jsonl", 4)

    progress = inspect_progress(
        variant=VariantName.BASELINE,
        traces_path=path,
        total=36,
        child_exit_code=1,
    )

    assert progress.state == "failed"


def test_more_records_than_tasks_never_reports_past_the_total(tmp_path: Path) -> None:
    path = write_records(tmp_path / "traces.jsonl", 40)

    progress = inspect_progress(
        variant=VariantName.BASELINE,
        traces_path=path,
        total=36,
        child_exit_code=None,
    )

    assert progress.completed == 36


def test_line_position_is_never_reported_as_task_position(tmp_path: Path) -> None:
    # Records land in completion order, so the projection counts and says
    # nothing at all about which tasks those lines were.
    path = write_records(tmp_path / "traces.jsonl", 3)

    progress = inspect_progress(
        variant=VariantName.BASELINE,
        traces_path=path,
        total=36,
        child_exit_code=None,
    )

    assert "task" not in progress.model_dump_json()


def test_a_variant_that_has_not_started_is_pending() -> None:
    progress = pending_progress(VariantName.CANDIDATE, 36)

    assert progress.variant == "candidate"
    assert progress.state == "pending"
    assert progress.total == 36


# ---------------------------------------------------------------------------
# Emitting
# ---------------------------------------------------------------------------


def test_an_unchanged_projection_is_not_appended_again() -> None:
    calls: list[str] = []

    class Recorder:
        def append(self, run_id: str, **_: object) -> None:
            calls.append(run_id)

    current = pending_progress(VariantName.BASELINE, 36)

    emit_progress_if_changed(
        run_store=Recorder(),  # type: ignore[arg-type]
        run_id="run_1",
        previous=current,
        current=current,
    )

    assert calls == []


def test_the_first_projection_is_always_appended() -> None:
    seen: list[dict[str, object]] = []

    class Recorder:
        def append(self, run_id: str, **kwargs: object) -> None:
            seen.append(kwargs)

    emit_progress_if_changed(
        run_store=Recorder(),  # type: ignore[arg-type]
        run_id="run_1",
        previous=None,
        current=pending_progress(VariantName.BASELINE, 36),
    )

    assert len(seen) == 1
    assert seen[0]["kind"] == VARIANT_PROGRESS
    assert seen[0]["phase"] is None


def test_a_moved_projection_is_appended_with_every_detail() -> None:
    seen: list[dict[str, object]] = []

    class Recorder:
        def append(self, run_id: str, **kwargs: object) -> None:
            seen.append(kwargs)

    emit_progress_if_changed(
        run_store=Recorder(),  # type: ignore[arg-type]
        run_id="run_1",
        previous=pending_progress(VariantName.BASELINE, 36),
        current=VariantProgress(
            variant="baseline",
            completed=4,
            total=36,
            running=1,
            errored=0,
            state="running",
        ),
    )

    details = seen[0]["details"]
    assert isinstance(details, dict)
    assert details[DETAIL_VARIANT] == "baseline"
    assert details[DETAIL_COMPLETED] == 4
    assert details[DETAIL_STATE] == "running"


def test_the_event_a_real_store_accepts_rebuilds_the_projection(
    temp_techtree_home: Path,
) -> None:
    """The details this module emits are the ones a run journal replays."""
    harness = run_harness(temp_techtree_home)
    run_id = harness.start().state.run_id
    store = harness.run_store
    for phase in (RunPhase.VALIDATING_TASKSET, RunPhase.RUNNING_VARIANTS):
        store.append(run_id, phase=phase)

    emit_progress_if_changed(
        run_store=store,
        run_id=run_id,
        previous=None,
        current=VariantProgress(
            variant="baseline",
            completed=2,
            total=36,
            running=1,
            errored=0,
            state="running",
        ),
    )

    state = store.state(run_id)
    assert state.variant_progress["baseline"].completed == 2
    assert state.variant_progress["baseline"].state == "running"
