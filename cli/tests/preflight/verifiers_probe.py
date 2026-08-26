"""In-process probe of the pinned Verifiers library API.

Run with the *engine* interpreter (the venv holding the pinned commit), never
with the Techtree interpreter — Techtree itself never imports `verifiers`.
Prints one JSON object on stdout; `test_verifiers_contract.py` asserts on it.

    <engine-python> tests/preflight/verifiers_probe.py
"""

from __future__ import annotations

import asyncio
import json
import re

import verifiers.v1 as vf
from verifiers.v1 import Task, TaskData, Taskset
from verifiers.v1.utils.loaders import import_taskset

TASKSET_ID = "techtree-preflight-taskset"
RAW_HASH = re.compile(r"^[0-9a-f]{64}$")


class _BareData(TaskData):
    pass


def probe() -> dict:
    first = vf.load_taskset(vf.TasksetConfig(id=TASKSET_ID))
    second = vf.load_taskset(vf.TasksetConfig(id=TASKSET_ID))
    hashes = [task.hash for task in first]
    reloaded = [task.hash for task in second]
    tasks = list(first)
    task = tasks[0]

    trace = vf.Trace(
        task=vf.TraceTask(
            type=type(task).__name__,
            data=task.data,
            key=task.key,
            hash=task.hash,
        ),
        state=vf.State(),
        agent=vf.AgentInfo(config=vf.AgentConfig(), name="preflight", trainable=False),
    )
    asyncio.run(task.score(trace, None))

    return {
        "verifiers_version": vf.__dict__.get("__version__") or _installed_version(),
        # claim 2
        "imports": {
            "Task": f"{Task.__module__}.{Task.__qualname__}",
            "TaskData": f"{TaskData.__module__}.{TaskData.__qualname__}",
            "Taskset": f"{Taskset.__module__}.{Taskset.__qualname__}",
        },
        # claim 3
        "taskset_class": type(first).__name__,
        "is_taskset": isinstance(first, Taskset),
        "task_type": type(first).task_type().__name__,
        "infinite": type(first).INFINITE,
        "taskset_name": vf.TasksetConfig(id=TASKSET_ID).name,
        "taskset_module": import_taskset(TASKSET_ID).__name__,
        # claim 4 + hash format
        "hashes": hashes,
        "hashes_reloaded": reloaded,
        "hashes_are_raw_hex64": all(bool(RAW_HASH.match(h)) for h in hashes),
        "hash_wire_data": task.data.model_dump(mode="json", exclude_none=True),
        "key_equals_hash": task.key == task.hash,
        # iteration order / membership
        "head_two": [t.hash for t in first.head(2)],
        "head_two_idx": [t.data.idx for t in first.head(2)],
        "has_shuffle": hasattr(first, "shuffle"),
        # claim 5
        "base_validate_is_async": asyncio.iscoroutinefunction(Task.validate),
        "base_validate_result": asyncio.run(Task(_BareData(idx=0)).validate(None)),
        # spec 22.5 generics + @vf.reward
        "reward_hooks": [fn.__name__ for fn in task.hooks("reward")],
        "data_type": type(task).data_type().__name__,
        "config_type": type(task).config_type().__name__,
        "scored_rewards": {
            name: reward.score for name, reward in trace.rewards.items()
        },
        "score_reply_correct": task.score_reply(task.data.answer),
        "score_reply_wrong": task.score_reply("BRANCH-XX"),
    }


def _installed_version() -> str:
    from importlib.metadata import version

    return version("verifiers")


if __name__ == "__main__":
    print(json.dumps(probe(), indent=2, sort_keys=True))
