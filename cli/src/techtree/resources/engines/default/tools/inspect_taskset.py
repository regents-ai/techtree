"""Report the identity of a taskset's first N tasks. Spec section 21.1.

This helper runs inside the managed engine, under the engine's own interpreter,
with the pinned Verifiers commit on its path. It is part of the engine bundle
and therefore part of the engine digest (decisions document 0003 A3): the code
that reads a taskset is pinned exactly as tightly as the library it reads it
with.

It prints identity and nothing else. Position, the raw Verifiers task hash, the
task's name, and its type are what a membership commitment is built from. The
prompt, the expected answer, and every other field of the task's wire data stay
inside the engine, because a helper that printed them would turn "freeze which
tasks are in the Climb" into "publish the answer key".

Membership is the first ``--num-tasks`` tasks in the taskset's own iteration
order (decisions document 0001). There is no shuffle option here, and there
never will be: ``Taskset.shuffle()`` is not called, not exposed, and not
reachable from this file.

Usage, from the host side::

    <engine-python> <engine-root>/tools/inspect_taskset.py \\
        --taskset-id procedure-transfer-v1 \\
        --num-tasks 20 \\
        --output <path>
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import verifiers.v1 as vf

SCHEMA_VERSION = "techtree.taskset-inspection.v1"
"""The shape host-side Techtree parses. Adding a field is safe; changing the
meaning of one is a new version."""

RAW_TASK_HASH = re.compile(r"^[0-9a-f]{64}$")
"""Verifiers emits unprefixed lowercase hexadecimal. The host normalizes it to
a Techtree digest at its own boundary; this file never guesses."""


def parse_args() -> argparse.Namespace:
    """Parse the fixed helper arguments."""
    parser = argparse.ArgumentParser(
        description="Report the identity of a taskset's first N tasks.",
    )
    parser.add_argument("--taskset-id", required=True)
    parser.add_argument("--num-tasks", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def load_tasks(taskset_id: str, *, num_tasks: int) -> tuple[vf.Taskset, list[vf.Task]]:
    """Load the taskset and take the first ``num_tasks`` tasks in load order."""
    if num_tasks < 1:
        raise SystemExit("--num-tasks must be at least 1")

    taskset = vf.load_taskset(vf.TasksetConfig(id=taskset_id))
    tasks = list(taskset.head(num_tasks))

    if len(tasks) != num_tasks:
        raise SystemExit(
            f"taskset {taskset_id} yielded {len(tasks)} tasks, "
            f"but {num_tasks} were requested"
        )
    return taskset, tasks


def task_record(position: int, task: vf.Task) -> dict[str, object]:
    """Return the identity of one task: position, raw hash, name, and type."""
    task_hash = task.hash
    if RAW_TASK_HASH.fullmatch(task_hash) is None:
        raise SystemExit(
            f"task at position {position} reported a hash that is not 64 "
            "lowercase hexadecimal characters"
        )

    return {
        "position": position,
        "task_hash": task_hash,
        "name": task.data.name,
        "task_type": type(task).__name__,
    }


def inspect_taskset(taskset_id: str, *, num_tasks: int) -> dict[str, object]:
    """Return the taskset's metadata and its ordered task records."""
    taskset, tasks = load_tasks(taskset_id, num_tasks=num_tasks)
    records = [task_record(position, task) for position, task in enumerate(tasks)]

    hashes = [str(record["task_hash"]) for record in records]
    if len(set(hashes)) != len(hashes):
        raise SystemExit(
            f"taskset {taskset_id} yielded two tasks with the same hash; "
            "membership would be ambiguous"
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "taskset_id": taskset_id,
        "taskset_class": type(taskset).__name__,
        "requested_num_tasks": num_tasks,
        "task_count": len(records),
        "tasks": records,
    }


def main() -> None:
    """Write one JSON object to the output path."""
    arguments = parse_args()
    document = inspect_taskset(arguments.taskset_id, num_tasks=arguments.num_tasks)
    rendered = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False)

    output = Path(arguments.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(f"{rendered}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
