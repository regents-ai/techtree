"""Four public deterministic tasks for infrastructure conformance only."""

from __future__ import annotations

from collections.abc import Iterable

import verifiers.v1 as vf

from techtree_v02_conformance.scoring import normalized_exact_match

CASES: tuple[tuple[str, str], ...] = (
    ("amber-17", "AMBER-17"),
    ("cobalt-29", "COBALT-29"),
    ("teal-43", "TEAL-43"),
    ("titanium-61", "TITANIUM-61"),
)

PROMPT = "Return exactly this token and nothing else: {answer}"


class ConformanceData(vf.TaskData):
    """Public answer material for one deliberately trivial task."""

    answer: str


class ConformanceTask(vf.Task[ConformanceData]):
    """A task whose reward has no learned or external dependency."""

    def score_reply(self, reply: str) -> float:
        return normalized_exact_match(reply, self.data.answer)

    @vf.reward
    async def exact_match(self, trace: vf.Trace) -> float:
        return self.score_reply(trace.last_reply)

    async def validate(self, runtime: vf.Runtime) -> bool:
        del runtime
        return (
            bool(self.data.answer)
            and self.score_reply(self.data.answer) == 1.0
            and self.score_reply(self.data.answer.lower()) == 0.0
        )


class ConformanceTaskset(vf.Taskset[ConformanceTask, vf.TasksetConfig]):
    """Load the fixed membership in its only valid order."""

    def load(self) -> Iterable[ConformanceTask]:
        for idx, (name, answer) in enumerate(CASES):
            yield ConformanceTask(
                ConformanceData(
                    idx=idx,
                    name=name,
                    prompt=PROMPT.format(answer=answer),
                    answer=answer,
                ),
                self.config.task,
            )
