"""One turn, one model call — checked, not assumed. Decisions document 0029.

The compiler maps the Campaign's ``maximum_model_calls`` onto the engine's
``max_turns``. That mapping is a claim about the pinned profile: that the
Hermes harness makes exactly one subject generation per Verifiers turn. This
module is where the claim meets evidence.

The evidence is the committed canonical recording — one real calibration
comparison, both variants, every episode — and the two numbers it carries come
from different places. ``model_calls`` is the length of the interception
layer's own call list; ``num_turns`` is what the trace computed for itself.
Neither is derived from the other, so their agreement is a measurement rather
than a tautology.

The live probe against a fresh paid comparison belongs to the recertification
phase, and runs the same tool over that run's normalized output.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

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
# The recorded canonical evidence
# ---------------------------------------------------------------------------


def test_every_recorded_subject_trace_made_one_model_call_per_turn(
    verifier: ModuleType,
) -> None:
    result = verifier.check([RECORDED])

    assert result.disagreements == []
    assert result.traces == 72, result.describe()
    assert result.ok


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


# ---------------------------------------------------------------------------
# What the tool does with evidence that does not conform
# ---------------------------------------------------------------------------


def _episode(episode_id: str, model_calls: int, num_turns: int) -> str:
    """Return one normalized episode line with the two counts under test."""
    return json.dumps(
        {
            "episode_id": episode_id,
            "traces": [{"model_calls": model_calls, "num_turns": num_turns}],
        }
    )


def test_a_trace_that_generated_twice_in_one_turn_fails_the_check(
    verifier: ModuleType, tmp_path: Path
) -> None:
    # The failure this exists to catch: a cap the publisher set in model calls
    # that the engine would apply to twice as many of them.
    path = tmp_path / "normalized-episodes.jsonl"
    path.write_text(
        "\n".join([_episode("a", 3, 3), _episode("b", 6, 3)]), encoding="utf-8"
    )

    result = verifier.check([tmp_path])

    assert not result.ok
    assert [item.episode_id for item in result.disagreements] == ["b"]
    assert "must not compile to max_turns" in result.describe()


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


def test_the_tool_reports_success_over_the_recorded_evidence(
    verifier: ModuleType,
) -> None:
    assert verifier.main([str(RECORDED)]) == 0
