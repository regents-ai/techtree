"""The Verifiers Taskset that scores BranchCode v1 procedure transfer.

Spec section 22.5. Shapes here were proven against the pinned Verifiers commit
`b2e4e8157783b2c0dffc7821044c87f29f1c3ccf` by the PI0 preflight; see
`docs/verifiers-pin-0.3.1.md`.

The prompt deliberately carries the *name* of the procedure and the *shape* of
the expected answer, and nothing else. BranchCode v1 itself — letter values,
positional weighting, the distinct-character term, the modulus — never appears
here. A subject that has not been given the procedure cannot recover it from
the prompt; that gap is exactly what the reference taskset measures.

This module is the only part of the package that imports Verifiers. It runs
inside the managed engine environment, never inside the ordinary Techtree
environment.
"""

from __future__ import annotations

from collections.abc import Iterable

import verifiers.v1 as vf

from procedure_transfer_v1.algorithm import (
    MODULUS,
    branch_code,
    branch_code_number,
)
from procedure_transfer_v1.dataset import proving_inputs, validate_dataset

__all__ = [
    "PROMPT_TEMPLATE",
    "TASK_NAME_TEMPLATE",
    "ProcedureTransferData",
    "ProcedureTransferTask",
    "ProcedureTransferTaskset",
]

PROMPT_TEMPLATE = (
    "Apply BranchCode v1 to this input:\n"
    "\n"
    "{input_text}\n"
    "\n"
    "Return only the final BRANCH-XX token."
)
"""Spec section 22.5, verbatim. Never add procedure detail to this string."""

TASK_NAME_TEMPLATE = "branch-code-{index:03d}"
"""Stable task names, one per proving input, in dataset order."""


def normalize_reply(reply: str) -> str:
    """Return the comparable form of a subject reply.

    A reply is trimmed and upper-cased before it is compared with the hidden
    answer. Nothing is extracted from surrounding prose: the prompt asks for
    the token alone, so a reply that buries the token in a sentence is wrong.

    Args:
        reply: Raw subject reply text.

    Returns:
        The trimmed, upper-cased reply.
    """
    return reply.strip().upper()


class ProcedureTransferData(vf.TaskData):
    """Wire data for one BranchCode task.

    ``answer`` is the oracle result. It is part of the task's content hash and
    is never placed in the prompt.
    """

    input_text: str
    answer: str


class ProcedureTransferTask(vf.Task[ProcedureTransferData]):
    """One proving input, scored by exact match against the hidden answer."""

    def score_reply(self, reply: str) -> float:
        """Return 1.0 for an exact match with the hidden answer, else 0.0.

        Args:
            reply: Raw subject reply text.

        Returns:
            ``1.0`` or ``0.0``.
        """
        return 1.0 if normalize_reply(reply) == self.data.answer else 0.0

    @vf.reward
    async def exact_match(self, trace: vf.Trace) -> float:
        """Score the last assistant reply in ``trace``.

        Args:
            trace: The rollout trace under evaluation.

        Returns:
            ``1.0`` or ``0.0``.
        """
        return self.score_reply(trace.last_reply)

    async def validate(self, runtime: vf.Runtime) -> bool:
        """Prove this task is well formed without consulting a model.

        Four independent conditions, all required:

        1. The oracle recomputed from ``input_text`` equals the stored answer.
        2. A stored answer exists at all.
        3. The correct answer scores 1.0.
        4. A well-formed but wrong token scores 0.0.

        Condition 4 uses the next code in the modular sequence rather than a
        malformed placeholder, so the negative control is a genuine near miss
        that only exact matching rejects.

        Args:
            runtime: The Verifiers runtime; unused, this check is model-free.

        Returns:
            True when every condition holds.
        """
        del runtime

        oracle = branch_code(self.data.input_text)
        near_miss_number = (branch_code_number(self.data.input_text) + 1) % MODULUS
        near_miss = f"BRANCH-{near_miss_number:02d}"

        return (
            bool(self.data.answer)
            and oracle == self.data.answer
            and self.score_reply(self.data.answer) == 1.0
            and self.score_reply(near_miss) == 0.0
        )


class ProcedureTransferTaskset(vf.Taskset[ProcedureTransferTask, vf.TasksetConfig]):
    """The frozen proving inputs, one deterministic task each, in dataset order."""

    def load(self) -> Iterable[ProcedureTransferTask]:
        """Yield one task per proving input.

        Yield order is the frozen dataset order, which is what the Campaign
        membership commitment pins.

        Yields:
            One :class:`ProcedureTransferTask` per proving input.
        """
        validate_dataset()

        for index, input_text in enumerate(proving_inputs()):
            yield ProcedureTransferTask(
                ProcedureTransferData(
                    idx=index,
                    name=TASK_NAME_TEMPLATE.format(index=index),
                    prompt=PROMPT_TEMPLATE.format(input_text=input_text),
                    input_text=input_text,
                    answer=branch_code(input_text),
                ),
                self.config.task,
            )
