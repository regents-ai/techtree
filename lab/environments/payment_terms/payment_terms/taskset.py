"""regents/payment-terms: turn a paid offer, written in words, into the exact x402 v2
payment requirements a server sends with its 402 response.

Single turn. The reward is the share of the twelve answer fields the reply gets
exactly right; the `solved` metric is 1 only when all twelve are right.
"""

from __future__ import annotations

import json
from typing import Any, Literal

import verifiers.v1 as vf

from payment_terms import offers, scoring


class PaymentTermsData(vf.TaskData):
    id: str
    split: Literal["train", "held_out"]
    answer: dict[str, Any]
    """The gold x402 v2 Payment Required body."""


class PaymentTermsTask(vf.Task[PaymentTermsData]):
    @property
    def key(self) -> str:
        return self.data.id

    @vf.stop
    async def single_turn(self, trace: vf.Trace) -> bool:
        return trace.num_turns >= 1

    @vf.reward(weight=1.0)
    async def fields(self, trace: vf.Trace) -> float:
        return scoring.reward(trace.last_reply or "", self.data.answer)

    @vf.metric
    async def solved(self, trace: vf.Trace) -> float:
        return float(scoring.solved(trace.last_reply or "", self.data.answer))

    async def validate(self, runtime: vf.Runtime) -> bool:
        """The gold answer, sent as a reply, solves the task."""
        return scoring.solved(json.dumps(self.data.answer), self.data.answer)


class PaymentTermsConfig(vf.TasksetConfig):
    split: Literal["train", "held_out"] = "train"
    seed: int = 0


class PaymentTermsTaskset(vf.Taskset[PaymentTermsTask, PaymentTermsConfig]):
    def load(self) -> list[PaymentTermsTask]:
        return [
            PaymentTermsTask(
                PaymentTermsData(
                    id=item.id,
                    prompt=item.prompt,
                    split=item.split,
                    answer=item.answer,
                ),
                self.config.task,
            )
            for item in offers.generate(self.config.seed)[self.config.split]
        ]
