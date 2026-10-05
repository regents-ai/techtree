"""The translator's calls that belong to one turn (the survey's bin/model-calls.py). Prints the lines of
/work/proxy/calls.jsonl (bench_hooks.py: each request as sent, with its model and effort, and each answered call with
its cost) whose time falls between the turn's start_utc and end_utc.

Usage: calls.py <turn_dir> > <turn_dir>/model-calls.jsonl
"""
import json
import sys
from datetime import datetime
from pathlib import Path

turn = Path(sys.argv[1])


def moment(text: str) -> datetime:
    return datetime.fromisoformat(text.strip().replace("Z", "+00:00"))


start, end = moment((turn / "start_utc").read_text()), moment((turn / "end_utc").read_text())
calls = Path("/work/proxy/calls.jsonl")
for line in calls.read_text().splitlines() if calls.exists() else []:
    if line.strip() and start <= datetime.fromisoformat(json.loads(line)["at"]) <= end:
        print(line)
