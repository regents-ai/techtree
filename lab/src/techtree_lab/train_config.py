"""The hosted RL training config for Prime: LoRA RL on NVIDIA Nemotron 3.5 Lightning
with the `regents/payment-terms` train split.

It is the prime-rl-native shape `prime train` 0.20.3 ships to Prime Hosted Training.
This module only writes the file; nothing here starts a run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tomli_w

from techtree_lab.runner import ENVIRONMENT

NAME = "payment-terms-nemotron-3.5-lightning"
MODEL = "nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16"
MAX_STEPS = 50


def config() -> dict[str, Any]:
    return {
        "mode": "rl",
        "name": NAME,
        "max_steps": MAX_STEPS,
        "model": {"name": MODEL},
        "deployment": {"type": "single_node", "num_train_gpus": 4, "num_infer_gpus": 4},
        "inference": {},
        "trainer": {"model": {"lora": {"rank": 16, "alpha": 32}}},
        "orchestrator": {
            "batch_size": 256,
            "rollouts_per_example": 8,
            "train": {
                "source": {
                    "taskset": {"id": ENVIRONMENT, "split": "train", "seed": 0},
                    "agent": {"harness": {"id": "null"}},
                }
            },
        },
    }


def write(path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = config()
    path.write_bytes(tomli_w.dumps(data).encode())
    return data
