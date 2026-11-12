import asyncio
import json
from pathlib import Path

import verifiers.v1 as vf

from payment_terms import offers
from payment_terms.taskset import PaymentTermsConfig, PaymentTermsTask, PaymentTermsTaskset

SKILL = Path(__file__).resolve().parents[1] / "skills" / "payment-terms" / "SKILL.md"


def _tasks(**config: object) -> list[PaymentTermsTask]:
    return list(PaymentTermsTaskset(PaymentTermsConfig(**config)))


def test_the_hub_id_loads_this_taskset() -> None:
    config = vf.resolve_env_config(
        {"taskset": {"id": "regents/payment-terms", "split": "held_out"}}
    )
    env = vf.load_environment(config)
    assert isinstance(env.taskset, PaymentTermsTaskset)
    assert len(list(env.taskset)) == 64


def test_tasks_carry_the_generated_items() -> None:
    items = offers.generate(0)["held_out"]
    tasks = _tasks(split="held_out")
    assert [t.key for t in tasks] == [i.id for i in items]
    assert [t.data.prompt for t in tasks] == [i.prompt for i in items]
    assert [t.data.answer for t in tasks] == [i.answer for i in items]
    assert all(t.data.system_prompt is None for t in tasks)


def test_train_split_is_the_default() -> None:
    assert len(_tasks()) == 1024


def test_skill_file_becomes_every_system_prompt() -> None:
    tasks = _tasks(split="held_out", system_prompt=SKILL)
    assert {t.data.system_prompt for t in tasks} == {SKILL.read_text()}


def test_gold_answers_validate() -> None:
    async def validate_all() -> list[bool]:
        return [await t.validate(runtime=None) for t in _tasks(split="held_out")]

    assert all(asyncio.run(validate_all()))


def test_task_data_round_trips() -> None:
    task = _tasks(split="held_out")[0]
    dumped = json.loads(task.data.model_dump_json())
    assert dumped["id"] == "payment-terms-held-out-0000"
    assert dumped["split"] == "held_out"
