"""Turn raw validator output into deterministic evidence. Decisions 0003 A1.

The Verifiers validator writes four files, and none of them is reproducible.
``results.jsonl`` is appended in completion order, so two identical runs put the
same rows in different orders. Every row carries an elapsed time. The log
carries wall-clock timestamps and the output directory is a temporary path.

The scientific claim inside all that is small and stable: for each task, in
membership order, did the gold check and the setup check pass, and why. This
helper extracts exactly that into ``validation-evidence.json``, which is the
artifact a ``TasksetValidationReceipt`` points at, ships publicly, and is
byte-compared between the publisher and a participant.

Normalization therefore drops elapsed times, timestamps, temporary paths, run
identifiers, process identifiers, hostnames, output directories, and log
prefixes, and sorts tasks by position rather than by whichever finished first.

It refuses rather than guesses. A run that did not record every task it
selected has nothing deterministic to normalize, and a run that skipped either
check is not the validation Techtree pins.

This helper lives inside the engine bundle and runs under the engine's own
interpreter (decisions document 0003 A3), which is also how it can report the
Verifiers commit that actually produced the output instead of trusting a
caller's claim about it.

Usage, from the host side::

    <engine-python> <engine-root>/tools/normalize_validation.py \\
        --results-dir <validate output dir> \\
        --taskset-lock-digest sha256:<hex> \\
        --output <path>
"""

from __future__ import annotations

import argparse
import json
import re
from importlib.metadata import distribution
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "techtree.validation-evidence.v1alpha1"

TECHTREE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
RAW_TASK_HASH = re.compile(r"^[0-9a-f]{64}$")

#: The one method Techtree pins: both checks, on the subprocess runtime.
VALIDATION_KIND = "verifiers_validate"
VALIDATION_MODE = "all"
VALIDATION_RUNTIME = "subprocess"

#: The five outcome counts the upstream summary nests under ``outcomes``.
OUTCOME_KEYS = ("valid", "invalid", "error", "timeout", "missing")


def parse_args() -> argparse.Namespace:
    """Parse the fixed helper arguments."""
    parser = argparse.ArgumentParser(
        description="Normalize raw Verifiers validation output.",
    )
    parser.add_argument("--results-dir", required=True, type=Path)
    parser.add_argument("--taskset-lock-digest", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def validator_revision() -> str:
    """Return the Verifiers commit installed in this engine.

    Read from the distribution's recorded VCS metadata, so the evidence names
    the code that actually ran.
    """
    recorded = distribution("verifiers").read_text("direct_url.json") or "{}"
    commit = json.loads(recorded).get("vcs_info", {}).get("commit_id")
    if not isinstance(commit, str) or not commit:
        raise SystemExit(
            "the installed Verifiers distribution does not record a commit; "
            "this engine was not installed from the pinned source"
        )
    return commit


def read_summary(results_dir: Path) -> dict[str, Any]:
    """Read ``summary.json`` and check it describes the pinned method."""
    document = json.loads((results_dir / "summary.json").read_text(encoding="utf-8"))

    if document.get("mode") != VALIDATION_MODE:
        raise SystemExit(
            f"validation ran in mode {document.get('mode')!r}; Techtree pins "
            f"mode {VALIDATION_MODE!r} and normalizes nothing else"
        )

    outcomes = document.get("outcomes")
    if not isinstance(outcomes, dict):
        raise SystemExit("summary.json has no outcomes object")

    counts = {key: _count(outcomes, key) for key in OUTCOME_KEYS}
    total = _count(document, "total")
    recorded = _count(document, "recorded")

    if counts["missing"] or recorded != total:
        raise SystemExit(
            f"validation recorded {recorded} of {total} tasks; a run that did "
            "not record every task has no deterministic evidence"
        )

    return {"total": total, **counts}


def read_rows(results_dir: Path) -> list[dict[str, Any]]:
    """Read ``results.jsonl`` into per-task records, sorted by position.

    Row order in the file is completion order and varies between identical
    runs, which is why position is read from the row rather than inferred from
    the line number.
    """
    text = (results_dir / "results.jsonl").read_text(encoding="utf-8")
    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    records = [_task_record(row) for row in rows]
    records.sort(key=lambda record: record["position"])

    positions = [record["position"] for record in records]
    if positions != list(range(len(records))):
        raise SystemExit(
            "validation rows do not cover positions 0.."
            f"{len(records) - 1} exactly once: {positions}"
        )
    return records


def normalize(
    results_dir: Path, *, taskset_lock_digest: str, revision: str
) -> dict[str, Any]:
    """Return the deterministic evidence document."""
    if TECHTREE_DIGEST.fullmatch(taskset_lock_digest) is None:
        raise SystemExit(
            f"--taskset-lock-digest {taskset_lock_digest!r} is not a Techtree digest"
        )

    summary = read_summary(results_dir)
    tasks = read_rows(results_dir)

    if len(tasks) != summary["total"]:
        raise SystemExit(
            f"summary reports {summary['total']} tasks but results.jsonl holds "
            f"{len(tasks)}"
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "taskset_lock_digest": taskset_lock_digest,
        "method": {
            "kind": VALIDATION_KIND,
            "mode": VALIDATION_MODE,
            "runtime": VALIDATION_RUNTIME,
            "validator_revision": revision,
        },
        "tasks": tasks,
        "summary": summary,
    }


def main() -> None:
    """Write one deterministic JSON object to the output path."""
    arguments = parse_args()
    document = normalize(
        Path(arguments.results_dir),
        taskset_lock_digest=arguments.taskset_lock_digest,
        revision=validator_revision(),
    )
    rendered = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False)

    output = Path(arguments.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(f"{rendered}\n", encoding="utf-8")


def _count(document: dict[str, Any], key: str) -> int:
    value = document.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise SystemExit(f"summary.json field {key!r} is not a count: {value!r}")
    return value


def _task_record(row: dict[str, Any]) -> dict[str, Any]:
    position = row.get("task_position")
    if not isinstance(position, int) or isinstance(position, bool) or position < 0:
        raise SystemExit(f"validation row has no usable task_position: {position!r}")

    task_key = row.get("task_key")
    if not isinstance(task_key, str) or RAW_TASK_HASH.fullmatch(task_key) is None:
        raise SystemExit(f"validation row at position {position} has no raw task hash")

    return {
        "position": position,
        "task_hash": f"sha256:{task_key}",
        "gold": _outcome(row, "gold", position),
        "setup": _outcome(row, "setup", position),
    }


def _outcome(row: dict[str, Any], check: str, position: int) -> dict[str, Any]:
    nested = row.get(check)
    if not isinstance(nested, dict):
        raise SystemExit(
            f"validation row at position {position} has no {check} check; "
            f"Techtree pins mode {VALIDATION_MODE!r}, which runs both"
        )

    valid = nested.get("valid")
    reason = nested.get("reason")
    if not isinstance(valid, bool) or not isinstance(reason, str) or not reason:
        raise SystemExit(
            f"the {check} check at position {position} reported no verdict"
        )
    return {"valid": valid, "reason": reason}


if __name__ == "__main__":
    main()
