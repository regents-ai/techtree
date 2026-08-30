"""One turn, one replying generation — checked, not assumed. Decisions 0029.

The compiler maps the Campaign's ``maximum_model_calls`` onto the engine's
``max_turns``. That mapping is a claim about the pinned profile, and decision
0029 fixes what it counts: one Verifiers turn is one subject-model generation
that produced a reply, while an exchange the provider rejected produced no
reply and no usage and is neither a turn nor a billed token. This module is
where the claim meets evidence.

Two kinds of evidence exist, and the tool must not confuse them. A raw
``traces.jsonl`` records every intercepted exchange and whether it errored, so
beside one the turn count can be checked strictly. A normalized episode alone
carries only totals, in which a rejection is invisible, so alone it supports
the bound ``num_turns <= model_calls`` and nothing stronger. The committed
canonical recording is of the second kind; the live probe against a fresh paid
comparison is of the first.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Final

import pytest

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[2]

#: The committed canonical evidence: one recorded comparison, both variants.
RECORDED: Final = REPOSITORY_ROOT / "tests" / "fixtures" / "receipts" / "recorded"


def tool() -> ModuleType:
    """Load the conformance tool the recertification phase will run for real."""
    name = "techtree_turn_conformance"
    location = REPOSITORY_ROOT / "tools" / "verify_turn_conformance.py"
    spec = importlib.util.spec_from_file_location(name, location)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered before it is executed: the module defines dataclasses, and a
    # dataclass resolves its own annotations through ``sys.modules``.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def verifier() -> ModuleType:
    return tool()


# ---------------------------------------------------------------------------
# Synthetic evidence, written the way the engine writes it
# ---------------------------------------------------------------------------


def _reply(usage: bool = True) -> dict[str, Any]:
    """Return one intercepted exchange that came back with a generation."""
    call: dict[str, Any] = {
        "node": 2,
        "endpoint": "/chat/completions",
        "finish_reason": "stop",
    }
    if usage:
        call["usage"] = {"prompt_tokens": 10, "completion_tokens": 3}
    return call


def _rejection(kind: str = "ProviderError") -> dict[str, Any]:
    """Return one exchange the provider refused: no reply, no usage."""
    return {
        "endpoint": "/chat/completions",
        "error": {"type": kind, "message": "upstream 429"},
    }


def _evidence(
    directory: Path,
    traces: list[tuple[str, str, int, list[dict[str, Any]]]],
    *,
    raw: bool = True,
) -> None:
    """Write one variant's normalized episodes, and its raw traces if asked.

    Each trace is given as its episode id, its trace id, the ``num_turns`` the
    normalized record claims, and the raw call list behind it. The two files
    are written in opposite orders on purpose: the tool matches them by id,
    and a tool that matched by position would pass this suite wrongly.
    """
    normalized = [
        json.dumps(
            {
                "episode_id": episode_id,
                "traces": [
                    {
                        "trace_id": trace_id,
                        "num_turns": num_turns,
                        "model_calls": len(calls),
                    }
                ],
            }
        )
        for episode_id, trace_id, num_turns, calls in traces
    ]
    (directory / "normalized-episodes.jsonl").write_text(
        "\n".join(normalized), encoding="utf-8"
    )
    if not raw:
        return
    records = [
        json.dumps(
            {
                "id": episode_id,
                "env": {"id": "procedure-transfer-v1"},
                "ok": True,
                "errors": [],
                "traces": [{"id": trace_id, "calls": calls}],
            }
        )
        for episode_id, trace_id, _, calls in reversed(traces)
    ]
    (directory / "traces.jsonl").write_text("\n".join(records), encoding="utf-8")


# ---------------------------------------------------------------------------
# The strict check, against the raw call list
# ---------------------------------------------------------------------------


def test_turns_that_equal_the_replying_generations_conform(
    verifier: ModuleType, tmp_path: Path
) -> None:
    _evidence(
        tmp_path,
        [
            ("ep-a", "tr-a", 3, [_reply(), _reply(), _reply()]),
            ("ep-b", "tr-b", 1, [_reply()]),
        ],
    )

    result = verifier.check([tmp_path])

    assert result.ok
    assert result.strict_traces == 2
    assert result.bounded_traces == 0
    assert result.disagreements == []
    assert "every turn is one subject generation that produced a reply" in (
        result.describe()
    )
    assert "unverifiable" not in result.describe()


def test_rejected_exchanges_are_reported_and_do_not_fail_the_check(
    verifier: ModuleType, tmp_path: Path
) -> None:
    # The delta the old tool failed on: three intercepted exchanges, two
    # generations, two turns. Decision 0029 counts the rejection as neither.
    _evidence(
        tmp_path,
        [("ep-a", "tr-a", 2, [_reply(), _rejection(), _reply()])],
    )

    result = verifier.check([tmp_path])
    report = result.describe()

    assert result.ok
    assert result.rejected == {"ProviderError": 1}
    assert "1 intercepted exchanges were rejected" in report
    assert "neither turns nor billed tokens" in report
    assert verifier.main([str(tmp_path)]) == 0


def test_rejections_are_reported_by_the_kind_of_failure_they_were(
    verifier: ModuleType, tmp_path: Path
) -> None:
    _evidence(
        tmp_path,
        [
            (
                "ep-a",
                "tr-a",
                1,
                [
                    _rejection(),
                    _rejection(),
                    _rejection("ClientConnectionResetError"),
                    _reply(),
                ],
            )
        ],
    )

    result = verifier.check([tmp_path])

    assert result.ok
    assert result.rejected == {"ProviderError": 2, "ClientConnectionResetError": 1}
    assert "3 intercepted exchanges were rejected" in result.describe()


def test_a_reply_the_provider_did_not_meter_is_still_a_turn(
    verifier: ModuleType, tmp_path: Path
) -> None:
    """Usage is not the predicate; a reply is.

    Real evidence holds generations that answered — a node, a finish reason,
    a message in the trace — whose usage the provider never reported. They
    cost tokens and they are turns, so a checker that counted usage records
    would call conforming evidence a disagreement. It is reported instead.
    """
    _evidence(
        tmp_path,
        [("ep-a", "tr-a", 2, [_reply(), _reply(usage=False)])],
    )

    result = verifier.check([tmp_path])

    assert result.ok
    assert result.unmetered == 1
    assert "1 generations produced a reply but carry no usage record" in (
        result.describe()
    )


def test_a_trace_that_generated_twice_in_one_turn_fails_the_check(
    verifier: ModuleType, tmp_path: Path
) -> None:
    # The failure this exists to catch: a cap the publisher set in model calls
    # that the engine would apply to twice as many of them. Every exchange
    # here produced a reply, so no rejection can explain the difference.
    _evidence(
        tmp_path,
        [
            ("ep-a", "tr-a", 3, [_reply(), _reply(), _reply()]),
            ("ep-b", "tr-b", 3, [_reply() for _ in range(6)]),
        ],
    )

    result = verifier.check([tmp_path])

    assert not result.ok
    assert [item.episode_id for item in result.disagreements] == ["ep-b"]
    assert "must not compile to max_turns" in result.describe()
    assert "made 6 generations that produced a reply across 3 turns" in (
        result.describe()
    )
    assert verifier.main([str(tmp_path)]) == 1


def test_a_normalized_trace_the_raw_file_does_not_hold_is_a_failure(
    verifier: ModuleType, tmp_path: Path
) -> None:
    # A raw file that is missing the trace under test cannot support it, and
    # silently skipping it would be a pass claimed over nothing.
    _evidence(tmp_path, [("ep-a", "tr-a", 3, [_reply(), _reply(), _reply()])])
    (tmp_path / "traces.jsonl").write_text(
        json.dumps({"id": "ep-a", "traces": [{"id": "tr-other", "calls": []}]}),
        encoding="utf-8",
    )

    result = verifier.check([tmp_path])

    assert not result.ok
    assert "has no trace of its own in traces.jsonl" in result.describe()


# ---------------------------------------------------------------------------
# The bounded check, where no raw evidence sits beside the episodes
# ---------------------------------------------------------------------------


def test_without_raw_evidence_only_the_bound_is_checked(
    verifier: ModuleType, tmp_path: Path
) -> None:
    _evidence(
        tmp_path,
        [
            ("ep-a", "tr-a", 3, [_reply(), _reply(), _reply()]),
            ("ep-b", "tr-b", 2, [_reply(), _reply(), _reply()]),
        ],
        raw=False,
    )

    result = verifier.check([tmp_path])
    report = result.describe()

    assert result.ok
    assert result.bounded_traces == 2
    assert result.strict_traces == 0
    assert "num_turns never exceeds model_calls" in report
    assert "unverifiable_without_raw" in report
    assert "1 intercepted exchanges beyond the turn count" in report
    # The one thing this mode must never say about the unaccounted exchange.
    assert "every turn is one subject generation" not in report


def test_more_turns_than_intercepted_exchanges_is_a_failure(
    verifier: ModuleType, tmp_path: Path
) -> None:
    # No reading of the mapping allows a turn that no exchange paid for.
    _evidence(tmp_path, [("ep-a", "tr-a", 5, [_reply(), _reply()])], raw=False)

    result = verifier.check([tmp_path])

    assert not result.ok
    assert "counted 5 turns over only 2 intercepted exchanges" in result.describe()
    assert verifier.main([str(tmp_path)]) == 1


def test_each_kind_of_file_is_checked_the_way_its_evidence_allows(
    verifier: ModuleType, tmp_path: Path
) -> None:
    """One run holding both kinds reports both, and passes on both."""
    strict = tmp_path / "candidate"
    bounded = tmp_path / "baseline"
    strict.mkdir()
    bounded.mkdir()
    _evidence(strict, [("ep-a", "tr-a", 2, [_reply(), _rejection(), _reply()])])
    _evidence(bounded, [("ep-b", "tr-b", 2, [_reply(), _reply()])], raw=False)

    result = verifier.check([tmp_path])
    report = result.describe()

    assert result.ok
    assert result.strict_traces == 1
    assert result.bounded_traces == 1
    assert "every turn is one subject generation that produced a reply" in report
    assert "num_turns never exceeds model_calls" in report
    assert "unverifiable_without_raw" in report


def test_evidence_that_does_not_exist_is_not_a_pass(
    verifier: ModuleType, tmp_path: Path
) -> None:
    # A live probe that found nothing to read has not confirmed anything, and
    # a checker that returned "fine" for an empty directory would be the way
    # the mapping goes unchecked.
    result = verifier.check([tmp_path])

    assert result.traces == 0
    assert not result.ok
    assert verifier.main([str(tmp_path)]) == 1


# ---------------------------------------------------------------------------
# The recorded canonical evidence
# ---------------------------------------------------------------------------


def test_the_recorded_evidence_holds_the_bound_on_every_trace(
    verifier: ModuleType,
) -> None:
    result = verifier.check([RECORDED])

    assert result.disagreements == []
    assert result.traces == 72, result.describe()
    assert result.ok


def test_the_recording_carries_no_raw_traces_so_it_claims_only_the_bound(
    verifier: ModuleType,
) -> None:
    """What the committed fixture can and cannot say, stated once.

    The recording keeps normalized episodes only, so the strict mapping is
    confirmed by the live probe against a real run's raw traces rather than
    here. The tool must label that limit rather than dress the bound up as a
    conformance result.
    """
    assert not list(RECORDED.rglob("traces.jsonl"))

    result = verifier.check([RECORDED])

    assert result.strict_traces == 0
    assert result.bounded_traces == 72
    assert len(result.unverifiable) == 2
    assert "unverifiable_without_raw" in result.describe()
    assert "0 intercepted exchanges beyond the turn count" in result.describe()


def test_the_recorded_evidence_covers_more_than_one_trace_length(
    verifier: ModuleType,
) -> None:
    """A conformance that only ever saw two-turn episodes would prove little.

    The recording holds episodes from two turns to thirty-one, so the claim is
    checked against short single-answer runs and long tool-using ones rather
    than against one shape of episode repeated.
    """
    lengths = {
        trace["num_turns"]
        for path in verifier.episode_files([RECORDED])
        for line in path.read_text(encoding="utf-8").splitlines()
        for trace in json.loads(line)["traces"]
    }

    assert len(lengths) > 5
    assert max(lengths) > 20


def test_the_tool_reports_success_over_the_recorded_evidence(
    verifier: ModuleType,
) -> None:
    assert verifier.main([str(RECORDED)]) == 0
