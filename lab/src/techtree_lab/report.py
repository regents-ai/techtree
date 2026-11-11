"""The Train comparison report (`techtree.train.v1alpha1`, kind `Comparison`) and its
traces file, as `Techtree.Train.Comparisons` reads them.

Every reward and mean is rounded to 4 decimals before anything is counted, so the
page's own recount of wins, ties, losses and solved tasks agrees with the report.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from techtree_lab import digests
from techtree_lab.runner import TaskResult

SCHEMA_VERSION = "techtree.train.v1alpha1"
KIND = "Comparison"
RESAMPLES = 10_000
BOOTSTRAP_SEED = 0
METHOD = f"paired bootstrap, {RESAMPLES} resamples, seed {BOOTSTRAP_SEED}"


@dataclass(frozen=True)
class Arm:
    name: str
    change: str
    skill_digest: str | None
    results: list[TaskResult]


def round4(value: float) -> float:
    return round(value, 4)


def traces(baseline: Arm, changed: Arm) -> bytes:
    """One JSON line per task per arm, task by task, the baseline first."""
    lines = [
        json.dumps(
            {
                "task_id": result.task_id,
                "arm": arm.name,
                "messages": result.messages,
                "reply": result.reply,
                "reward": round4(result.reward),
                "solved": result.solved,
            },
            ensure_ascii=False,
        )
        for pair in zip(baseline.results, changed.results, strict=True)
        for arm, result in zip((baseline, changed), pair, strict=True)
    ]
    return "".join(line + "\n" for line in lines).encode()


def percentile(ordered: list[float], q: float) -> float:
    """The `q` quantile of sorted values, by linear interpolation between ranks."""
    position = q * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def bootstrap_ci95(differences: list[float]) -> tuple[float, float]:
    """The 95% interval of the mean paired difference, by resampling tasks."""
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(differences)
    means = sorted(sum(rng.choices(differences, k=n)) / n for _ in range(RESAMPLES))
    return round4(percentile(means, 0.025)), round4(percentile(means, 0.975))


def outcome(low: float, high: float, rewards: list[tuple[float, float]]) -> str:
    if low > 0:
        return "uplift"
    if high < 0:
        return "regression"
    if all(before == after for before, after in rewards):
        return "tie"
    return "inconclusive"


def results(baseline: Arm, changed: Arm) -> dict[str, Any]:
    ids = [result.task_id for result in baseline.results]
    if ids != [result.task_id for result in changed.results]:
        raise ValueError("the two arms ran different tasks")
    rewards = [
        (round4(before.reward), round4(after.reward))
        for before, after in zip(baseline.results, changed.results, strict=True)
    ]
    differences = [after - before for before, after in rewards]
    low, high = bootstrap_ci95(differences)
    return {
        "arms": [
            {
                "name": arm.name,
                "mean_reward": round4(sum(r[side] for r in rewards) / len(rewards)),
                "solved": sum(result.solved for result in arm.results),
                "tokens": {
                    "prompt": sum(result.prompt_tokens for result in arm.results),
                    "completion": sum(result.completion_tokens for result in arm.results),
                },
            }
            for side, arm in enumerate((baseline, changed))
        ],
        "per_task": [
            {
                "task_id": task_id,
                "rewards": [before, after],
                "solved": [b.solved, c.solved],
            }
            for task_id, (before, after), b, c in zip(
                ids, rewards, baseline.results, changed.results, strict=True
            )
        ],
        "paired": {
            "wins": sum(after > before for before, after in rewards),
            "ties": sum(after == before for before, after in rewards),
            "losses": sum(after < before for before, after in rewards),
            "mean_difference": round4(sum(differences) / len(differences)),
            "ci95": [low, high],
            "method": METHOD,
        },
        "outcome": outcome(low, high, rewards),
    }


def timestamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def comparison(
    *,
    title: str,
    environment: dict[str, Any],
    model: dict[str, Any],
    sampling: dict[str, Any],
    software: dict[str, str],
    baseline: Arm,
    changed: Arm,
    traces_bytes: bytes,
    started_at: datetime,
    finished_at: datetime,
) -> dict[str, Any]:
    """The whole report. `environment` carries `task_count`, the number of tasks each
    arm ran; `started_at` and `finished_at` are UTC, to the second."""
    spec = {
        "title": title,
        "environment": environment,
        "model": model,
        "sampling": sampling,
        "arms": [
            {"name": arm.name, "change": arm.change, "skill_digest": arm.skill_digest}
            for arm in (baseline, changed)
        ],
        "software": software,
        "results": results(baseline, changed),
        "traces_digest": digests.of_bytes(traces_bytes),
    }
    named = {"schema_version": SCHEMA_VERSION, "kind": KIND, "spec": spec}
    return {
        **named,
        "operational": {
            "started_at": timestamp(started_at),
            "finished_at": timestamp(finished_at),
            "host": "local",
            "cost_usd": "0.00",
            "duration_seconds": int((finished_at - started_at).total_seconds()),
        },
        "digest": digests.canonical(named),
    }
