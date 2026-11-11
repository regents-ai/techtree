"""What `Techtree.Train.Comparisons` checks when it reads a report, in Python."""

import json
import re
from typing import Any

from techtree_lab import digests

DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


def check_contract(comparison: dict[str, Any], traces: bytes) -> None:
    """Every check the page makes on a report and its traces, and the traces layout."""
    assert set(comparison) == {"schema_version", "kind", "spec", "operational", "digest"}
    assert comparison["schema_version"] == "techtree.train.v1alpha1"
    assert comparison["kind"] == "Comparison"
    named = {k: comparison[k] for k in ("schema_version", "kind", "spec")}
    assert comparison["digest"] == digests.canonical(named)

    spec = comparison["spec"]
    assert set(spec) == {
        "title", "environment", "model", "sampling", "arms", "software", "results",
        "traces_digest",
    }  # fmt: skip
    assert spec["traces_digest"] == digests.of_bytes(traces)
    environment = spec["environment"]
    assert environment["split"] == "held_out"
    assert DIGEST.fullmatch(environment["taskset_digest"])
    assert DIGEST.fullmatch(spec["model"]["weights_digest"])
    assert spec["arms"][0] == {"name": "baseline", "change": "none", "skill_digest": None}
    assert spec["arms"][1]["change"] == "skill"
    assert DIGEST.fullmatch(spec["arms"][1]["skill_digest"])

    results = spec["results"]
    per_task = results["per_task"]
    assert environment["task_count"] == len(per_task) > 0
    assert len({t["task_id"] for t in per_task}) == len(per_task)
    assert [a["name"] for a in results["arms"]] == [a["name"] for a in spec["arms"]]
    for task in per_task:
        assert all(0 <= r <= 1 and r == round(r, 4) for r in task["rewards"])
        assert all(isinstance(s, bool) for s in task["solved"])
    for side, arm in enumerate(results["arms"]):
        assert arm["solved"] == sum(t["solved"][side] for t in per_task)
        assert 0 <= arm["mean_reward"] <= 1 and arm["mean_reward"] == round(arm["mean_reward"], 4)
        assert all(isinstance(n, int) and n >= 0 for n in arm["tokens"].values())
    paired = results["paired"]
    pairs = [t["rewards"] for t in per_task]
    assert paired["wins"] == sum(c > b for b, c in pairs)
    assert paired["ties"] == sum(c == b for b, c in pairs)
    assert paired["losses"] == sum(c < b for b, c in pairs)
    low, high = paired["ci95"]
    assert low <= high
    assert paired["method"] == "paired bootstrap, 10000 resamples, seed 0"
    assert results["outcome"] in {"uplift", "tie", "regression", "inconclusive"}

    operational = comparison["operational"]
    for key in ("started_at", "finished_at"):
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", operational[key])
    assert re.fullmatch(r"\d+\.\d+", operational["cost_usd"])
    assert operational["duration_seconds"] >= 0

    lines = [json.loads(line) for line in traces.decode().splitlines()]
    assert len(lines) == 2 * len(per_task)
    for line, (task, side) in zip(lines, [(t, s) for t in per_task for s in (0, 1)], strict=True):
        assert set(line) == {"task_id", "arm", "messages", "reply", "reward", "solved"}
        assert line["task_id"] == task["task_id"]
        assert line["arm"] == spec["arms"][side]["name"]
        assert line["reward"] == task["rewards"][side]
        assert line["solved"] == task["solved"][side]
