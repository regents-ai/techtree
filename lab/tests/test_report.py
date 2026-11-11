from datetime import UTC, datetime
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from techtree_lab import digests, report
from techtree_lab.runner import TaskResult
from tests.contract import check_contract

STARTED = datetime(2026, 11, 11, 9, 0, 0, tzinfo=UTC)
FINISHED = datetime(2026, 11, 11, 9, 40, 0, tzinfo=UTC)
SKILL_DIGEST = digests.of_bytes(b"skill")


def _result(task_id: str, correct: int) -> TaskResult:
    return TaskResult(
        task_id=task_id,
        messages=[{"role": "user", "content": f"offer {task_id}"}],
        reply=f"reply {correct}",
        reward=correct / 12,
        solved=correct == 12,
        prompt_tokens=100,
        completion_tokens=20 + correct,
    )


def _arms(scores: list[tuple[int, int]]) -> tuple[report.Arm, report.Arm]:
    ids = [f"payment-terms-held-out-{n:04d}" for n in range(len(scores))]
    return (
        report.Arm(
            "baseline", "none", None, [_result(i, b) for i, (b, _) in zip(ids, scores, strict=True)]
        ),
        report.Arm(
            "skill",
            "skill",
            SKILL_DIGEST,
            [_result(i, c) for i, (_, c) in zip(ids, scores, strict=True)],
        ),
    )


def _comparison(scores: list[tuple[int, int]]) -> tuple[dict[str, Any], bytes]:
    baseline, changed = _arms(scores)
    traces = report.traces(baseline, changed)
    comparison = report.comparison(
        title="Skill on Nemotron 3 Nano 4B",
        environment={
            "id": "regents/payment-terms",
            "version": "0.1.0",
            "split": "held_out",
            "seed": 0,
            "task_count": len(scores),
            "taskset_digest": digests.of_bytes(b"tasks"),
        },
        model={
            "family": "Nemotron 3 Nano",
            "name": "nemotron-3-nano:4b",
            "provider": "ollama",
            "weights_digest": digests.of_bytes(b"weights"),
        },
        sampling={"temperature": 0.0, "max_tokens": 512, "thinking": False},
        software={"verifiers": "0.4.1", "techtree_lab": "0.1.0"},
        baseline=baseline,
        changed=changed,
        traces_bytes=traces,
        started_at=STARTED,
        finished_at=FINISHED,
    )
    return comparison, traces


SCORES = st.lists(st.tuples(st.integers(0, 12), st.integers(0, 12)), min_size=1, max_size=64)


@settings(max_examples=30, deadline=None)
@given(SCORES)
def test_every_report_keeps_the_contract(scores: list[tuple[int, int]]) -> None:
    comparison, traces = _comparison(scores)
    check_contract(comparison, traces)


@settings(max_examples=30, deadline=None)
@given(SCORES)
def test_outcome_follows_the_interval(scores: list[tuple[int, int]]) -> None:
    results = _comparison(scores)[0]["spec"]["results"]
    low, high = results["paired"]["ci95"]
    expected = (
        "uplift" if low > 0
        else "regression" if high < 0
        else "tie" if all(b == c for b, c in scores)
        else "inconclusive"
    )  # fmt: skip
    assert results["outcome"] == expected


def test_report_is_reproducible() -> None:
    scores = [(n % 13, (n * 7) % 13) for n in range(64)]
    assert _comparison(scores) == _comparison(scores)


@pytest.mark.parametrize(
    ("scores", "outcome", "ci95"),
    [
        ([(6, 6)] * 64, "tie", [0.0, 0.0]),
        ([(0, 12)] * 64, "uplift", [1.0, 1.0]),
        ([(12, 0)] * 64, "regression", [-1.0, -1.0]),
        ([(0, 12), (12, 0)] * 32, "inconclusive", None),
    ],
)
def test_clear_outcomes(
    scores: list[tuple[int, int]], outcome: str, ci95: list[float] | None
) -> None:
    results = _comparison(scores)[0]["spec"]["results"]
    assert results["outcome"] == outcome
    if ci95 is not None:
        assert results["paired"]["ci95"] == ci95


def test_rewards_round_to_four_places() -> None:
    results = _comparison([(11, 7)])[0]["spec"]["results"]
    assert results["per_task"][0]["rewards"] == [0.9167, 0.5833]
    assert results["paired"]["mean_difference"] == -0.3334
    assert results["arms"][0]["tokens"] == {"prompt": 100, "completion": 31}


def test_arms_must_run_the_same_tasks() -> None:
    baseline, changed = _arms([(1, 2), (3, 4)])
    swapped = report.Arm("skill", "skill", SKILL_DIGEST, list(reversed(changed.results)))
    with pytest.raises(ValueError, match="different tasks"):
        report.results(baseline, swapped)
