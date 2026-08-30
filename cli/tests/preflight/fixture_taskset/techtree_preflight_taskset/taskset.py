"""Smallest taskset that exercises every Verifiers API surface Techtree depends on.

Shaped exactly like the reference taskset sketched in spec 22.5 (typed `TaskData`,
a `Task` subclass with `score_reply`, an `@vf.reward` coroutine, and an async
`validate` hook), so the preflight proves the sketch against the pinned commit.

`TECHTREE_PREFLIGHT_INVALID` makes every task's `validate` hook fail; the
preflight uses it to observe what the runner persists on a failing taskset.
"""

from __future__ import annotations

import os
from collections.abc import Iterable

import verifiers.v1 as vf

INPUTS: tuple[tuple[str, str], ...] = (
    ("alpha", "BRANCH-01"),
    ("beta", "BRANCH-02"),
    ("gamma", "BRANCH-03"),
    ("delta", "BRANCH-04"),
)

PROMPT = (
    "Apply BranchCode v1 to this input:\n\n{input_text}\n\n"
    "Return only the final BRANCH-XX token."
)


class PreflightData(vf.TaskData):
    input_text: str
    answer: str


class PreflightTask(vf.Task[PreflightData]):
    def score_reply(self, reply: str) -> float:
        return 1.0 if reply.strip() == self.data.answer else 0.0

    @vf.reward
    async def exact_match(self, trace: vf.Trace) -> float:
        return self.score_reply(trace.last_reply)

    async def validate(self, runtime: vf.Runtime) -> bool:
        if os.environ.get("TECHTREE_PREFLIGHT_INVALID"):
            return False
        return (
            bool(self.data.answer)
            and self.score_reply(self.data.answer) == 1.0
            and self.score_reply("BRANCH-XX") == 0.0
        )


class PreflightTaskset(vf.Taskset[PreflightTask, vf.TasksetConfig]):
    def load(self) -> Iterable[PreflightTask]:
        for idx, (input_text, answer) in enumerate(INPUTS):
            yield PreflightTask(
                PreflightData(
                    idx=idx,
                    name=f"preflight-{idx}",
                    prompt=PROMPT.format(input_text=input_text),
                    input_text=input_text,
                    answer=answer,
                ),
                self.config.task,
            )
