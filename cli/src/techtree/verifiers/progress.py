"""How far one variant has got, read from its own evidence. Spec section 6.11.

Progress is derived from the file the engine is already writing rather than
from anything the child says on its way past. ``traces.jsonl`` is append-only:
upstream serializes one whole Episode, appends it under a run-wide lock in a
shielded worker thread, and ends every record with a newline
(``docs/verifiers-eval.md``). Counting the records that are complete is
therefore an exact, cheap, read-only measurement that a concurrent writer cannot
be disturbed by — provided the reader ignores a final line that has not been
terminated yet, and never writes to the file to "repair" it.

One rule governs how the number may be used. **Line position is never task
position.** Records land in completion order, and the preflight watched four
tasks arrive in exactly reverse order (``docs/verifiers-eval.md``, finding E4).
A count of finished episodes is honest; an inference from line seven to task
seven is not. Pairing happens later, by task hash, in the engine's own
normalizer.

The file's absence means *pending*, not broken. Upstream truncates
``traces.jsonl`` to empty only after the taskset package has imported and the
environment has been constructed, roughly a second and a half in on a trivial
taskset, so a poller that treated "no file yet" as failure would fail every run
it watched.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Literal

from techtree.models.run import VariantProgress
from techtree.runs.events import (
    DETAIL_COMPLETED,
    DETAIL_ERRORED,
    DETAIL_RUNNING,
    DETAIL_STATE,
    DETAIL_TOTAL,
    DETAIL_VARIANT,
    VARIANT_PROGRESS,
)
from techtree.runs.store import RunStore
from techtree.verifiers.child import CANCELLATION_EXIT_CODE
from techtree.verifiers.models import VariantName

__all__ = [
    "count_complete_jsonl_records",
    "emit_progress_if_changed",
    "inspect_progress",
    "pending_progress",
]

#: Reading the tail of a growing file is done in whole chunks rather than line
#: by line so that one poll is one pass, however many episodes have landed.
_READ_CHUNK_BYTES: Final = 1 << 20

type _VariantLiteral = Literal["baseline", "candidate"]
type _StateLiteral = Literal["pending", "running", "completed", "failed", "cancelled"]

#: ``VariantProgress`` is a projection model and names its variants as literals.
#: Spelling the correspondence out keeps the enum the single source of the two
#: names while still handing the model the exact type it declares.
_VARIANT_LITERALS: Final[dict[VariantName, _VariantLiteral]] = {
    VariantName.BASELINE: "baseline",
    VariantName.CANDIDATE: "candidate",
}


def count_complete_jsonl_records(path: Path) -> int:
    """Count the whole, valid JSON object records in an append-only JSONL file.

    A final line without its newline is a record still being written, and is not
    counted. Neither is a line that is newline-terminated but not yet a valid
    JSON object, which is what a partial write looks like on a filesystem that
    reorders. Nothing is rewritten: the file belongs to the child, and a reader
    that repaired it would be destroying the evidence it came to measure.

    A missing file counts as zero, because the engine creates it a moment after
    the child starts and before the first rollout.
    """
    try:
        handle = path.open("rb")
    except FileNotFoundError:
        return 0
    except OSError:
        return 0

    complete = 0
    remainder = b""
    with handle:
        while chunk := handle.read(_READ_CHUNK_BYTES):
            remainder += chunk
            *lines, remainder = remainder.split(b"\n")
            complete += sum(1 for line in lines if _is_complete_record(line))
    return complete


def _is_complete_record(line: bytes) -> bool:
    """Whether one newline-terminated line is a whole JSON object."""
    if not line.strip():
        return False
    try:
        return isinstance(json.loads(line), dict)
    except (ValueError, UnicodeDecodeError):
        return False


def pending_progress(variant: VariantName, total: int) -> VariantProgress:
    """The progress of a variant whose child has not been started yet."""
    return VariantProgress(
        variant=_VARIANT_LITERALS[variant],
        completed=0,
        total=total,
        running=0,
        errored=0,
        state="pending",
    )


def inspect_progress(
    *,
    variant: VariantName,
    traces_path: Path,
    total: int,
    child_exit_code: int | None,
    max_concurrent: int = 1,
) -> VariantProgress:
    """Measure one variant without interpreting any reward.

    ``completed`` is the number of episodes the engine has finished writing.
    ``running`` is how many can be in flight given what is left and how many
    permits the variant was compiled with — the file records finished episodes
    only, so an exact in-flight count is not observable and a bound that cannot
    exceed the truth is the honest answer.

    ``errored`` stays zero here. Whether an episode is scientifically usable is
    settled by :mod:`techtree.verifiers.verify` against the normalized
    projection, and a progress line that guessed at it early would be reporting
    a verdict the run has not reached.
    """
    completed = min(count_complete_jsonl_records(traces_path), total)
    remaining = max(total - completed, 0)

    state: _StateLiteral
    if child_exit_code is None:
        state = "running" if traces_path.exists() else "pending"
        running = min(remaining, max(max_concurrent, 0))
    elif child_exit_code == CANCELLATION_EXIT_CODE:
        state, running = "cancelled", 0
    elif child_exit_code == 0 and remaining == 0:
        state, running = "completed", 0
    else:
        state, running = "failed", 0

    return VariantProgress(
        variant=_VARIANT_LITERALS[variant],
        completed=completed,
        total=total,
        running=running,
        errored=0,
        state=state,
    )


def emit_progress_if_changed(
    *,
    run_store: RunStore,
    run_id: str,
    previous: VariantProgress | None,
    current: VariantProgress,
) -> None:
    """Append one ``variant.progress`` event only when something moved.

    A poller runs several times a second and a run's event log is the record
    other processes rebuild their picture of the run from. Appending an
    unchanged projection would grow that log without adding a fact to it.
    """
    if previous is not None and previous == current:
        return
    run_store.append(
        run_id,
        phase=None,
        kind=VARIANT_PROGRESS,
        details={
            DETAIL_VARIANT: current.variant,
            DETAIL_COMPLETED: current.completed,
            DETAIL_TOTAL: current.total,
            DETAIL_RUNNING: current.running,
            DETAIL_ERRORED: current.errored,
            DETAIL_STATE: current.state,
        },
    )
