"""`techtree-lab`: run the payment-terms tasks against a model, and write the hosted
training config."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markup import escape
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

from payment_terms import offers
from payment_terms.offers import Split
from techtree_lab import runner, train_config

LAB = Path(__file__).resolve().parents[2]
"""The lab project folder."""

TRAIN_CONFIG = LAB / "configs" / "hosted" / f"{train_config.NAME}.toml"

OLLAMA = "http://localhost:11434"
MODEL = "nemotron-3-nano:4b"

out = Console(soft_wrap=True)
err = Console(stderr=True)


def _concurrency(text: str) -> int:
    value = int(text)
    if not 1 <= value <= 4:
        raise argparse.ArgumentTypeError("concurrency is 1 to 4")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="techtree-lab", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    eval_ = commands.add_parser("eval", help="run one arm over a split and print its scores")
    eval_.add_argument("--base-url", default=f"{OLLAMA}/v1", help="OpenAI-compatible endpoint")
    eval_.add_argument("--model", default=MODEL)
    eval_.add_argument("--split", choices=["train", "held_out"], default="held_out")
    eval_.add_argument("--seed", type=int, default=0)
    eval_.add_argument("--skill", type=Path, help="send this Skill file as the system message")
    eval_.add_argument("--concurrency", type=_concurrency, default=4)

    train = commands.add_parser("train-config", help="write the hosted RL training config")
    train.add_argument("--out", type=Path, default=TRAIN_CONFIG)

    for command in (eval_, train):
        command.add_argument("--json", action="store_true", help="print JSON instead of tables")
    return parser


def _run(
    label: str,
    *,
    base_url: str,
    model: str,
    split: Split,
    seed: int,
    skill: Path | None,
    concurrency: int,
    total: int,
) -> list[runner.TaskResult]:
    columns = (
        TextColumn("{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    )
    with Progress(*columns, console=err) as progress:
        task = progress.add_task(label, total=total)

        def advance() -> None:
            progress.advance(task)

        return runner.run_arm(
            base_url=base_url,
            model=model,
            split=split,
            seed=seed,
            skill=skill,
            concurrency=concurrency,
            on_task=advance,
        )


def _summary(results: list[runner.TaskResult]) -> dict[str, Any]:
    return {
        "task_count": len(results),
        "mean_reward": round(sum(r.reward for r in results) / len(results), 4),
        "solved": sum(r.solved for r in results),
        "completion_tokens": sum(r.completion_tokens for r in results),
    }


def _eval(args: argparse.Namespace) -> None:
    split: Split = args.split
    total = len(offers.generate(args.seed)[split])
    results = _run(
        f"{args.model} on {split}",
        base_url=args.base_url,
        model=args.model,
        split=split,
        seed=args.seed,
        skill=args.skill,
        concurrency=args.concurrency,
        total=total,
    )
    summary = _summary(results)
    if args.json:
        tasks = [
            {"task_id": r.task_id, "reward": round(r.reward, 4), "solved": r.solved}
            for r in results
        ]
        print(
            json.dumps(
                {
                    "model": args.model,
                    "split": split,
                    "seed": args.seed,
                    "skill": str(args.skill) if args.skill else None,
                    **summary,
                    "tasks": tasks,
                },
                indent=2,
            )
        )
        return
    table = Table(title=f"{escape(args.model)} on {split}")
    for column in ("Tasks", "Mean reward", "Solved", "Completion tokens"):
        table.add_column(column, justify="right")
    table.add_row(
        str(summary["task_count"]),
        f"{summary['mean_reward']:.4f}",
        str(summary["solved"]),
        str(summary["completion_tokens"]),
    )
    out.print(table)


def _train_config(args: argparse.Namespace) -> None:
    data = train_config.write(args.out)
    if args.json:
        print(json.dumps({"path": str(args.out), "config": data}, indent=2))
        return
    out.print(f"Wrote {escape(str(args.out))}")
    out.print(
        f"{data['model']['name']}, LoRA RL, {data['max_steps']} steps, "
        f"{runner.ENVIRONMENT} train split. Nothing was sent to Prime."
    )


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    command: Callable[[argparse.Namespace], None] = {
        "eval": _eval,
        "train-config": _train_config,
    }[args.command]
    try:
        command(args)
    except runner.LabError as error:
        err.print(f"[red]Error:[/red] {escape(str(error))}")
        sys.exit(1)
