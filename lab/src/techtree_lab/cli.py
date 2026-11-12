"""`techtree-lab`: run the payment-terms tasks, compare a model with and without the
Skill, and write the hosted training config."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
from collections.abc import Callable
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markup import escape
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

from payment_terms import offers
from payment_terms.offers import Split
from techtree_lab import digests, report, runner, train_config

LAB = Path(__file__).resolve().parents[2]
"""The lab project folder."""

SKILL = LAB / "skills" / "payment-terms" / "SKILL.md"
REPORTS = LAB.parent / "platform" / "priv" / "train"
TRAIN_CONFIG = LAB / "configs" / "hosted" / f"{train_config.NAME}.toml"

OLLAMA = "http://localhost:11434"
MODEL = "nemotron-3-nano:4b"
FAMILY = "Nemotron 3 Nano"
TITLE = "Skill on Nemotron 3 Nano 4B"
SLUG = "payment-terms-nemotron-3-nano-4b-skill"

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

    compare = commands.add_parser(
        "compare", help=f"{MODEL} without and with the Skill on the held-out tasks"
    )
    compare.add_argument("--ollama", default=OLLAMA, help="Ollama server")
    compare.add_argument("--skill", type=Path, default=SKILL)
    compare.add_argument("--concurrency", type=_concurrency, default=4)
    compare.add_argument("--out", type=Path, default=REPORTS, help="folder for the report")

    train = commands.add_parser("train-config", help="write the hosted RL training config")
    train.add_argument("--out", type=Path, default=TRAIN_CONFIG)

    for command in (eval_, compare, train):
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
        "mean_reward": report.round4(sum(r.reward for r in results) / len(results)),
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
            {"task_id": r.task_id, "reward": report.round4(r.reward), "solved": r.solved}
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


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _compare(args: argparse.Namespace) -> None:
    skill: Path = args.skill.resolve()
    skill_digest = digests.of_bytes(skill.read_bytes())
    items = offers.generate(0)["held_out"]
    weights = runner.weights_digest(args.ollama, MODEL)
    started_at = _now()
    arms = []
    for name, change, skill_file, digest in (
        ("baseline", "none", None, None),
        ("skill", "skill", skill, skill_digest),
    ):
        results = _run(
            name,
            base_url=f"{args.ollama}/v1",
            model=MODEL,
            split="held_out",
            seed=0,
            skill=skill_file,
            concurrency=args.concurrency,
            total=len(items),
        )
        arms.append(report.Arm(name, change, digest, results))
    finished_at = _now()
    baseline, changed = arms
    traces = report.traces(baseline, changed)
    comparison = report.comparison(
        title=TITLE,
        environment={
            "id": runner.ENVIRONMENT,
            "version": version("payment-terms"),
            "split": "held_out",
            "seed": 0,
            "task_count": len(items),
            "taskset_digest": digests.taskset(items),
        },
        model={"family": FAMILY, "name": MODEL, "provider": "ollama", "weights_digest": weights},
        sampling={
            "temperature": runner.TEMPERATURE,
            "max_tokens": runner.MAX_TOKENS,
            "thinking": runner.THINKING,
        },
        software={"verifiers": version("verifiers"), "techtree_lab": version("techtree-lab")},
        baseline=baseline,
        changed=changed,
        traces_bytes=traces,
        started_at=started_at,
        finished_at=finished_at,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    report_path = args.out / f"{SLUG}.json"
    traces_path = args.out / f"{SLUG}.traces.jsonl"
    traces_path.write_bytes(traces)
    report_path.write_text(json.dumps(comparison, indent=2, ensure_ascii=False) + "\n")
    if args.json:
        print(
            json.dumps(
                {"report": str(report_path), "traces": str(traces_path), "comparison": comparison},
                indent=2,
            )
        )
        return
    _print_comparison(comparison, report_path, traces_path)


def _print_comparison(comparison: dict[str, Any], report_path: Path, traces_path: Path) -> None:
    results = comparison["spec"]["results"]
    table = Table(title=TITLE)
    for column in ("Arm", "Mean reward", "Solved", "Completion tokens"):
        table.add_column(column, justify="left" if column == "Arm" else "right")
    task_count = comparison["spec"]["environment"]["task_count"]
    for arm in results["arms"]:
        table.add_row(
            arm["name"],
            f"{arm['mean_reward']:.4f}",
            f"{arm['solved']}/{task_count}",
            str(arm["completion_tokens"]),
        )
    out.print(table)
    paired = results["paired"]
    low, high = paired["ci95"]
    out.print(
        f"Wins {paired['wins']}, ties {paired['ties']}, losses {paired['losses']}. "
        f"Mean difference {paired['mean_difference']:+.4f}, 95% interval "
        f"[{low:+.4f}, {high:+.4f}]. Outcome: [bold]{results['outcome']}[/bold]."
    )
    operational = comparison["operational"]
    out.print(f"Took {operational['duration_seconds']} s. Digest {comparison['digest']}")
    out.print(f"Report  {escape(str(report_path))}\nTraces  {escape(str(traces_path))}")


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
        "compare": _compare,
        "train-config": _train_config,
    }[args.command]
    try:
        command(args)
    except (runner.LabError, urllib.error.URLError) as error:
        err.print(f"[red]Error:[/red] {escape(str(error))}")
        sys.exit(1)
