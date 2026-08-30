"""Four deterministic tasks, shaped like the reference taskset."""

from __future__ import annotations

from collections.abc import Iterable

import verifiers.v1 as vf

INPUTS: tuple[tuple[str, str], ...] = (
    ("alpha", "BRANCH-01"),
    ("beta", "BRANCH-02"),
    ("gamma", "BRANCH-03"),
    ("delta", "BRANCH-04"),
)

PROMPT = "Apply BranchCode v1 to this input:\n\n{input_text}\n"


class SubjectData(vf.TaskData):
    input_text: str
    answer: str


class SubjectTask(vf.Task[SubjectData]):
    def score_reply(self, reply: str) -> float:
        return 1.0 if reply.strip() == self.data.answer else 0.0

    @vf.reward
    async def exact_match(self, trace: vf.Trace) -> float:
        return self.score_reply(trace.last_reply)

    async def validate(self, runtime: vf.Runtime) -> bool:
        del runtime
        return bool(self.data.answer)


class SubjectTaskset(vf.Taskset[SubjectTask, vf.TasksetConfig]):
    def load(self) -> Iterable[SubjectTask]:
        for idx, (input_text, answer) in enumerate(INPUTS):
            yield SubjectTask(
                SubjectData(
                    idx=idx,
                    name=f"subject-{idx}",
                    prompt=PROMPT.format(input_text=input_text),
                    input_text=input_text,
                    answer=answer,
                ),
                self.config.task,
            )
