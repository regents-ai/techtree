"""Two processes appending to one run journal. Spec sections 7.9, 18.3.

The run store's locking exists for a situation no in-process test reproduces:
a detached worker advancing a run while the CLI, in a different process
entirely, writes to the same directory. Threads would share the interpreter and
prove nothing about the file lock, so this module launches real interpreters and
lets them contend.

What must hold afterwards is exactly what a later reader depends on. Every
append that reported success is in the journal, once. The sequence numbers run
from zero without a gap or a repeat, which is also what proves no two writes
interleaved inside one line. And ``state.json``, written by whichever process
happened to append last, is the projection of the whole journal rather than of
the events that one process knew about.

Run with::

    uv run pytest tests/integration/test_run_store_concurrency.py -m integration
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pytest

from techtree.canonical import sha256_digest_bytes
from techtree.models.base import Digest
from techtree.models.campaign import ProgramRef, PublicContext
from techtree.models.evaluation_backend import (
    AttestationKind,
    EvaluationBackendKind,
    EvaluationBackendSpec,
)
from techtree.models.run import (
    PolicyAcknowledgement,
    RunPhase,
    RunRequest,
    RunState,
)
from techtree.paths import TechtreePaths, paths_from_root
from techtree.runs.events import (
    DETAIL_LABEL,
    PHASE_ENTERED,
    PROGRESS_UPDATED,
    RUN_CREATED,
    read_events,
)
from techtree.runs.machine import reduce_events
from techtree.runs.store import RunStore

pytestmark = pytest.mark.integration

RUN_ID = "run_00000000000000000000000000000001"
DRAFT_ID = "draft_0000000000000000000000000000000a"
FIXED_TIME = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

#: What the parent writes before the children start: the created event and the
#: two phase changes that bring the run to a phase with work to report.
OPENING_EVENTS = 3

#: Enough appends per process that the two are certain to overlap on the lock,
#: and few enough that the test stays under a second.
APPENDS_EACH = 15

WRITERS = ("baseline-writer", "candidate-writer")

#: The child process. It is a separate interpreter, so it shares nothing with
#: the test but the run directory and the lock inside it.
APPENDER_SOURCE = """
import sys
import time
from pathlib import Path

from techtree.models.run import RunPhase
from techtree.paths import paths_from_root
from techtree.runs.events import (
    DETAIL_CURRENT,
    DETAIL_LABEL,
    DETAIL_TOTAL,
    PROGRESS_UPDATED,
)
from techtree.runs.store import RunStore

root, run_id, label, count, barrier = sys.argv[1:6]
total = int(count)
store = RunStore(paths_from_root(Path(root)))

# Both children idle here until the parent releases them, so the appends
# genuinely collide rather than happening to run one after the other.
gate = Path(barrier)
deadline = time.monotonic() + 30
while not gate.exists():
    if time.monotonic() > deadline:
        raise SystemExit(f"{label} waited too long to start")
    time.sleep(0.005)

for position in range(1, total + 1):
    store.append(
        run_id,
        phase=RunPhase.RUNNING_BASELINE,
        kind=PROGRESS_UPDATED,
        details={
            DETAIL_CURRENT: position,
            DETAIL_TOTAL: total,
            DETAIL_LABEL: label,
        },
    )
"""


def digest_of(text: str) -> Digest:
    """Return a stable, distinct digest for a test fixture."""
    return sha256_digest_bytes(text.encode("utf-8"))


def build_request() -> RunRequest:
    """Return a complete run request for the run under test."""
    data_policy_digest = digest_of("data-policy")
    return RunRequest(
        run_id=RUN_ID,
        draft_id=DRAFT_ID,
        draft_digest=digest_of("draft"),
        campaign_spec_digest=digest_of("campaign"),
        program_ref=ProgramRef(id="procedure-transfer", version=1),
        public_context=PublicContext(kind="climb", climb_digest=digest_of("climb")),
        data_policy_digest=data_policy_digest,
        outcome_contract_digest=None,
        evaluation_backend=EvaluationBackendSpec(
            schema_version="techtree.evaluation-backend.v1alpha1",
            kind=EvaluationBackendKind.LOCAL_TECHTREE,
            attestation=AttestationKind.PARTICIPANT,
        ),
        taskset_lock_digest=digest_of("taskset-lock"),
        baseline_manifest_digest=digest_of("baseline"),
        candidate_manifest_digest=digest_of("candidate"),
        policy_acknowledgement=PolicyAcknowledgement(
            data_policy_digest=data_policy_digest,
            method="explicit_cli_digest",
            acknowledged_at=FIXED_TIME,
        ),
        executor_kind="fake",
        created_at=FIXED_TIME,
    )


@pytest.fixture
def paths(temp_techtree_home: Path) -> TechtreePaths:
    """Return a path layout rooted in an isolated home."""
    return paths_from_root(temp_techtree_home)


@pytest.fixture
def running_run(paths: TechtreePaths) -> RunStore:
    """Return a store holding one run part-way through the normal path."""
    store = RunStore(paths)
    store.create(build_request())
    store.append(RUN_ID, phase=RunPhase.VALIDATING_TASKSET)
    store.append(RUN_ID, phase=RunPhase.RUNNING_BASELINE)
    return store


def start_appender(
    script: Path,
    paths: TechtreePaths,
    label: str,
    barrier: Path,
) -> subprocess.Popen[str]:
    """Launch one appending process."""
    return subprocess.Popen(
        [
            sys.executable,
            str(script),
            str(paths.root),
            RUN_ID,
            label,
            str(APPENDS_EACH),
            str(barrier),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=os.environ.copy(),
    )


def test_two_processes_append_without_losing_or_corrupting_an_event(
    running_run: RunStore,
    paths: TechtreePaths,
    tmp_path: Path,
) -> None:
    script = tmp_path / "appender.py"
    script.write_text(APPENDER_SOURCE, encoding="utf-8")
    barrier = tmp_path / "go"

    processes = [start_appender(script, paths, label, barrier) for label in WRITERS]
    # Give both children time to reach the gate before releasing them.
    time.sleep(0.2)
    barrier.write_text("go", encoding="utf-8")
    results = [process.communicate(timeout=120) for process in processes]

    for process, (out, err) in zip(processes, results, strict=True):
        assert process.returncode == 0, f"appender failed: {out}\n{err}"

    journal = paths.run_dir(RUN_ID) / "events.jsonl"
    events = read_events(journal)

    # Every append that returned is in the log, once, in an unbroken sequence.
    assert len(events) == OPENING_EVENTS + len(WRITERS) * APPENDS_EACH
    assert [event.sequence for event in events] == list(range(len(events)))
    assert len({event.sequence for event in events}) == len(events)
    assert len(journal.read_bytes().splitlines()) == len(events)

    # Neither writer lost an append to the other.
    written = Counter(
        event.details[DETAIL_LABEL]
        for event in events
        if event.kind == PROGRESS_UPDATED
    )
    assert written == Counter({label: APPENDS_EACH for label in WRITERS})
    assert [event.kind for event in events[:OPENING_EVENTS]] == [
        RUN_CREATED,
        PHASE_ENTERED,
        PHASE_ENTERED,
    ]

    # The projection belongs to the whole journal, not to whichever process
    # wrote it last.
    projected = reduce_events(events)
    stored = RunState.model_validate_json(
        (paths.run_dir(RUN_ID) / "state.json").read_bytes()
    )
    assert stored.model_copy(update={"heartbeat_at": None}) == projected
    assert stored == running_run.state(RUN_ID)
    assert projected.phase is RunPhase.RUNNING_BASELINE
    assert projected.sequence == len(events) - 1
    assert projected.progress is not None
    assert projected.progress.label in WRITERS
