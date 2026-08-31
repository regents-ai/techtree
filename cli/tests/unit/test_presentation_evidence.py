"""Counts read back out of a finished run. Tickets bmk and vmp.

The reader exists because two facts a reader of a result wants — how many model
turns each side took, and how often the provider refused a call — are recorded
by every run and carried by none of its signed documents. Nothing is added to
any artifact to fix that: the signed execution record already commits both files
by digest, and these tests are about the reader refusing to report anything it
cannot check against those digests.

The evidence here is synthetic. The shapes are the engine's own — one normalized
episode per line, one raw record per line, one entry per model call with the
status a refused call carries — and the point under test is the checking rather
than the parsing of any particular run.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from techtree.canonical import sha256_digest_bytes
from techtree.models.base import Digest
from techtree.models.campaign import VariantSchedule
from techtree.models.experiment import ExperimentVariant
from techtree.presentation.evidence import (
    RATE_LIMIT_STATUS,
    read_recorded_evidence,
)
from techtree.receipts.execution import (
    COMPARISON_EXECUTION_SCHEMA_VERSION,
    ComparisonExecutionRecord,
    PairOutcome,
    UsageProvenance,
    VariantExecutionSummary,
    VariantUsage,
    unavailable_cost,
)
from techtree.verifiers.models import RunPaths, VariantName

STARTED = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)


def digest(label: str) -> Digest:
    return sha256_digest_bytes(label.encode("utf-8"))


def episode_line(*, turns: int, ok: bool = True) -> str:
    """Return one normalized episode carrying one rollout."""
    return json.dumps(
        {
            "episode_id": f"episode-{turns}-{ok}",
            "env_id": "procedure-transfer-v1",
            "task_hash": digest("task"),
            "task_position": 0,
            "ok": ok,
            "traces": [
                {
                    "trace_id": f"trace-{turns}-{ok}",
                    "agent_role": "subject",
                    "task_hash": digest("task"),
                    "ok": ok,
                    "verifiers_version": "0.3.1",
                    "verifiers_revision": "0" * 40,
                    "model_id": "qwen/qwen3.7-flash",
                    "sampling": {"temperature": 0.0},
                    "harness_id": "hermes-agent",
                    "harness_version": "0.19.0",
                    "use_bundled_skill": False,
                    "skill_root_digests": [],
                    "runtime": {
                        "kind": "docker",
                        "runtime_id": None,
                        "image": f"techtree/subject@{digest('image')}",
                        "image_index_digest": digest("image"),
                        "cpu": 2.0,
                        "memory_gb": 4.0,
                    },
                    "tools": [],
                    "rewards": [],
                    "metrics": {},
                    "usage": None,
                    "model_calls": turns,
                    "num_turns": turns,
                    "last_reply": None,
                    "errors": [],
                    "raw_trace_digest": digest("raw-trace"),
                }
            ],
            "errors": [],
            "raw_episode_digest": digest("raw-episode"),
        }
    )


def trace_line(*, calls: int, refused: int, other_failures: int = 0) -> str:
    """Return one raw record whose calls include the ones that were refused."""
    entries: list[dict[str, Any]] = [{"endpoint": "/chat/completions"}] * calls
    entries += [
        {
            "endpoint": "/chat/completions",
            "error": {
                "type": "ProviderError",
                "message": "upstream 429",
                "status_code": RATE_LIMIT_STATUS,
            },
        }
    ] * refused
    entries += [
        {
            "endpoint": "/chat/completions",
            "error": {
                "type": "ProviderError",
                "message": "upstream 500",
                "status_code": 500,
            },
        }
    ] * other_failures
    return json.dumps({"id": "episode", "ok": True, "traces": [{"calls": entries}]})


def write_run(
    root: Path,
    *,
    baseline: tuple[str, str],
    candidate: tuple[str, str],
) -> ComparisonExecutionRecord:
    """Lay one run's evaluation output out and return the record that signs it."""
    written: dict[VariantName, tuple[Digest, Digest]] = {}
    paths = RunPaths(root=root)
    for variant, (episodes, traces) in (
        (VariantName.BASELINE, baseline),
        (VariantName.CANDIDATE, candidate),
    ):
        output = paths.variant_output_dir(variant)
        output.mkdir(parents=True, exist_ok=True)
        episode_bytes = f"{episodes}\n".encode()
        trace_bytes = f"{traces}\n".encode()
        (output / "normalized-episodes.jsonl").write_bytes(episode_bytes)
        (output / "traces.jsonl").write_bytes(trace_bytes)
        written[variant] = (
            sha256_digest_bytes(episode_bytes),
            sha256_digest_bytes(trace_bytes),
        )
    return record(written)


def record(
    written: dict[VariantName, tuple[Digest, Digest]],
) -> ComparisonExecutionRecord:
    """Return the signed record that commits both sides' two files."""
    return ComparisonExecutionRecord(
        schema_version=COMPARISON_EXECUTION_SCHEMA_VERSION,
        run_id="run_" + "0" * 32,
        campaign_spec_digest=digest("campaign"),
        engine_digest=digest("engine"),
        execution_backend="verifiers",
        schedule=VariantSchedule.PARALLEL,
        started_at=STARTED,
        finished_at=STARTED,
        elapsed_seconds=0.0,
        launch_skew_seconds=None,
        first_launched=None,
        overlap_seconds=0.0,
        campaign_max_concurrent=4,
        outcome=PairOutcome.COMPLETED,
        baseline=_side(ExperimentVariant.BASELINE, written[VariantName.BASELINE]),
        candidate=_side(ExperimentVariant.CANDIDATE, written[VariantName.CANDIDATE]),
    )


def _side(
    variant: ExperimentVariant, digests: tuple[Digest, Digest]
) -> VariantExecutionSummary:
    return VariantExecutionSummary(
        variant=variant,
        started_at=STARTED,
        finished_at=STARTED,
        elapsed_seconds=0.0,
        exit_code=0,
        cancelled=False,
        episode_count=1,
        max_concurrent=2,
        usage=VariantUsage(
            provenance=UsageProvenance.UNAVAILABLE, traces_total=1, traces_with_usage=0
        ),
        cost=unavailable_cost("nothing reported one"),
        experiment_manifest_digest=digest(f"{variant.value}-manifest"),
        argv_digest=digest(f"{variant.value}-argv"),
        normalized_episodes_digest=digests[0],
        raw_traces_digest=digests[1],
        resolved_config_digest=digest(f"{variant.value}-config"),
    )


def test_turns_and_refusals_are_counted_from_the_run_s_own_files(
    tmp_path: Path,
) -> None:
    """The two numbers the founder's run had to be read out of raw logs for."""
    signed = write_run(
        tmp_path,
        baseline=(episode_line(turns=406), trace_line(calls=406, refused=4)),
        candidate=(episode_line(turns=73), trace_line(calls=73, refused=0)),
    )

    evidence = read_recorded_evidence(tmp_path, signed)

    assert evidence is not None
    assert evidence.baseline.model_turns == 406
    assert evidence.candidate.model_turns == 73
    assert evidence.baseline.rate_limited_calls == 4
    assert evidence.candidate.rate_limited_calls == 0
    assert evidence.every_rollout_completed is True


def test_a_failure_that_is_not_a_rate_limit_is_not_counted_as_one(
    tmp_path: Path,
) -> None:
    """Only the status a provider refuses too many requests with is counted."""
    signed = write_run(
        tmp_path,
        baseline=(
            episode_line(turns=10),
            trace_line(calls=10, refused=1, other_failures=3),
        ),
        candidate=(episode_line(turns=10), trace_line(calls=10, refused=0)),
    )

    evidence = read_recorded_evidence(tmp_path, signed)

    assert evidence is not None
    assert evidence.baseline.rate_limited_calls == 1


def test_a_rollout_that_did_not_finish_is_visible_as_one(tmp_path: Path) -> None:
    """A claim that every rollout completed is read, never assumed."""
    signed = write_run(
        tmp_path,
        baseline=(episode_line(turns=10, ok=False), trace_line(calls=10, refused=2)),
        candidate=(episode_line(turns=10), trace_line(calls=10, refused=0)),
    )

    evidence = read_recorded_evidence(tmp_path, signed)

    assert evidence is not None
    assert evidence.every_rollout_completed is False


@pytest.mark.parametrize(
    "filename",
    ["normalized-episodes.jsonl", "traces.jsonl"],
    ids=["episodes", "traces"],
)
def test_a_file_that_is_not_the_one_the_record_signed_is_not_read(
    tmp_path: Path, filename: str
) -> None:
    """An unchecked count would be worth less than saying the count is unknown."""
    signed = write_run(
        tmp_path,
        baseline=(episode_line(turns=406), trace_line(calls=406, refused=4)),
        candidate=(episode_line(turns=73), trace_line(calls=73, refused=0)),
    )
    target = RunPaths(root=tmp_path).variant_output_dir(VariantName.BASELINE) / filename
    target.write_bytes(target.read_bytes() + b"\n")

    assert read_recorded_evidence(tmp_path, signed) is None


def test_a_run_whose_output_is_gone_reports_nothing_rather_than_zero(
    tmp_path: Path,
) -> None:
    """A cleared-away evaluation makes the result say less, never say wrong."""
    signed = write_run(
        tmp_path,
        baseline=(episode_line(turns=406), trace_line(calls=406, refused=4)),
        candidate=(episode_line(turns=73), trace_line(calls=73, refused=0)),
    )
    traces = RunPaths(root=tmp_path).variant_output_dir(VariantName.CANDIDATE)
    (traces / "traces.jsonl").unlink()

    assert read_recorded_evidence(tmp_path, signed) is None


def test_a_raw_record_that_does_not_parse_reports_nothing(tmp_path: Path) -> None:
    """Half a reading is not offered: the digest holds, the content does not."""
    root = tmp_path
    paths = RunPaths(root=root)
    for variant in (VariantName.BASELINE, VariantName.CANDIDATE):
        output = paths.variant_output_dir(variant)
        output.mkdir(parents=True, exist_ok=True)
        (output / "normalized-episodes.jsonl").write_bytes(
            f"{episode_line(turns=4)}\n".encode()
        )
        (output / "traces.jsonl").write_bytes(b"{not json at all\n")
    written = {
        variant: (
            sha256_digest_bytes(
                (
                    paths.variant_output_dir(variant) / "normalized-episodes.jsonl"
                ).read_bytes()
            ),
            sha256_digest_bytes(
                (paths.variant_output_dir(variant) / "traces.jsonl").read_bytes()
            ),
        )
        for variant in (VariantName.BASELINE, VariantName.CANDIDATE)
    }

    assert read_recorded_evidence(root, record(written)) is None
