"""The hosted RL training config for Prime: LoRA RL on NVIDIA Nemotron 3 Nano 30B-A3B
with the `regents/payment-terms` train split, measured on the 64 held-out tasks before
the first step and after the last.

It is the prime-rl shape `prime train` 0.20.3 ships to Prime Hosted Training: one
96 GB card trains and one serves. This module only writes the file; nothing here
starts a run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tomli_w

from techtree_lab.runner import ENVIRONMENT, MAX_TOKENS, TEMPERATURE

NAME = "payment-terms-nemotron-3-nano-30b"
MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16"
GPU_TYPE = "RTX_PRO_6000B_96GB"
MAX_STEPS = 50

AGENT: dict[str, Any] = {
    "harness": {"id": "null"},
    "sampling": {"max_tokens": MAX_TOKENS, "chat_template_kwargs": {"enable_thinking": False}},
}
"""The one seat, the same for training and the held-out measure: the reply is scored
as it is, at most 512 tokens, without thinking first."""


def _env(split: str) -> dict[str, Any]:
    return {"taskset": {"id": ENVIRONMENT, "split": split, "seed": 0}, "agent": AGENT}


def config() -> dict[str, Any]:
    return {
        "mode": "rl",
        "name": NAME,
        "gpu_type": GPU_TYPE,
        "max_steps": MAX_STEPS,
        "model": {"name": MODEL},
        "deployment": {"type": "single_node", "num_train_gpus": 1, "num_infer_gpus": 1},
        "inference": {},
        "trainer": {"model": {"lora": {"rank": 16, "alpha": 32}}},
        "orchestrator": {
            "batch_size": 64,
            "train": {"group_size": 8, "source": [{"env": _env("train")}]},
            "eval": {
                "interval": MAX_STEPS,
                "sampling": {"temperature": TEMPERATURE},
                "source": [{"name": "held-out", "env": _env("held_out")}],
            },
        },
    }


def write(path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = config()
    path.write_bytes(tomli_w.dumps(data).encode())
    return data
