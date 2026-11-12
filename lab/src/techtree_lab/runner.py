"""One arm of the payment-terms tasks against a model, run through verifiers.

The arm runs the `regents/payment-terms` taskset with the null harness (a plain chat
program) in local subprocesses. A Skill arm sends the Skill's text as the system
message, through the taskset's own `system_prompt` setting.
"""

from __future__ import annotations

import asyncio
import json
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import verifiers.v1 as vf

from payment_terms.offers import Split

ENVIRONMENT = "regents/payment-terms"

TEMPERATURE = 0.0
MAX_TOKENS = 512
THINKING = False
NO_THINKING: dict[str, Any] = {"reasoning_effort": "none"}
"""What the request carries to keep the model from thinking before it answers."""


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    messages: list[dict[str, Any]]
    """The messages sent to the model."""
    reply: str
    """The model's reply, as scored."""
    reward: float
    solved: bool
    completion_tokens: int


class LabError(Exception):
    """A run that cannot give an honest result."""


class RunFailed(LabError):
    """Some task's rollout ended in an error, so the arm has no honest result."""


def run_arm(
    *,
    base_url: str,
    model: str,
    split: Split,
    seed: int,
    skill: Path | None,
    concurrency: int,
    on_task: Callable[[], None],
) -> list[TaskResult]:
    """Every task of `split` once, in the split's order. `on_task` is called as each
    task finishes."""
    return asyncio.run(
        _run_arm(
            base_url=base_url,
            model=model,
            split=split,
            seed=seed,
            skill=skill,
            concurrency=concurrency,
            on_task=on_task,
        )
    )


async def _run_arm(
    *,
    base_url: str,
    model: str,
    split: Split,
    seed: int,
    skill: Path | None,
    concurrency: int,
    on_task: Callable[[], None],
) -> list[TaskResult]:
    taskset: dict[str, Any] = {"id": ENVIRONMENT, "split": split, "seed": seed}
    if skill is not None:
        taskset["system_prompt"] = str(skill)
    env = vf.load_environment(
        vf.resolve_env_config(
            {
                "taskset": taskset,
                "agent": {
                    "harness": {"id": "null"},
                    "runtime": {"type": "subprocess"},
                    "network_notice": False,
                    "max_turns": 1,
                },
            }
        )
    )
    ctx = vf.ModelContext(
        model=model,
        client=vf.EvalClientConfig(base_url=base_url, api_key_var="OLLAMA_API_KEY"),
        sampling=vf.SamplingConfig(temperature=TEMPERATURE, max_tokens=MAX_TOKENS, **NO_THINKING),
    )
    semaphore = asyncio.Semaphore(concurrency)

    async def on_complete(episode: vf.Episode) -> None:
        on_task()

    async with env.serving():
        rollouts = [
            asyncio.ensure_future(env.run_slot(slot, ctx, semaphore, on_complete))
            for task in env.taskset
            for slot in env.slots(task, 1)
        ]
        try:
            episodes = await asyncio.gather(*rollouts)
        except BaseException:
            # Unwind every rollout before `serving()` tears down what they use.
            for rollout in rollouts:
                rollout.cancel()
            await asyncio.gather(*rollouts, return_exceptions=True)
            raise

    traces = [trace for episode in episodes for trace in episode.traces]
    failed = [trace for trace in traces if not trace.ok]
    if failed:
        errors = "; ".join(
            f"{trace.task.key}: {trace.last_error.message if trace.last_error else 'not ok'}"
            for trace in failed
        )
        raise RunFailed(f"{len(failed)} of {len(traces)} tasks failed: {errors}")
    return [_result(trace) for trace in traces]


def _result(trace: vf.Trace) -> TaskResult:
    *sent, _reply = trace.messages
    fields = trace.rewards["fields"]
    usage = trace.usage
    if fields is None or usage is None:
        raise RunFailed(f"{trace.task.key}: no reward or no token usage was recorded")
    return TaskResult(
        task_id=trace.task.key,
        messages=[{"role": m.role, "content": m.content} for m in sent],
        reply=trace.last_reply,
        reward=fields.score,
        solved=trace.metrics["solved"] == 1.0,
        completion_tokens=usage.completion_tokens,
    )


def weights_digest(ollama: str, model: str) -> str:
    """The `sha256:` digest Ollama reports for `model`'s weights."""
    with urllib.request.urlopen(f"{ollama}/api/tags", timeout=10) as response:
        models = json.load(response)["models"]
    digests: list[str] = [entry["digest"] for entry in models if entry["name"] == model]
    if len(digests) != 1:
        raise LabError(f"Ollama at {ollama} has no model {model}")
    return "sha256:" + digests[0]
