#!/usr/bin/env python3
"""Render one recorded turn as a readable transcript.md with timing (the survey's bin/transcript.py).

  transcript.py <turn_dir> <harness_id>

The harness's /work/bin/harness/<id>/parse.py turns the turn's stream.jsonl into the shared event list.
Writes <turn_dir>/transcript.md, <turn_dir>/turn-summary.json and <turn_dir>/tool-calls.json (each tool call
as a command entry). Timing comes from the stream's own timestamps and the
controller's start_utc/end_utc; tool time is tool_use -> its tool_result. Reasoning is counted, never printed.
"""
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

HARNESSES = Path("/work/bin/harness")
CLIP = 4000
EXCERPT = 600


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def clip(text: str) -> str:
    return text if len(text) <= CLIP else text[:CLIP] + f"\n… [{len(text) - CLIP} more characters in stream.jsonl]"


def excerpt(text: str) -> str:
    return text if len(text) <= EXCERPT else text[:EXCERPT] + f" … [truncated; {len(text)} characters in stream.jsonl]"


def parser(harness: str):
    spec = importlib.util.spec_from_file_location(f"parse_{harness}", HARNESSES / harness / "parse.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse


def command_entry(turn: Path, n: int, use: dict, result: dict, took: float | None) -> dict:
    """The harness's own tool call. Its shell process argv is not captured, so argv stays null (LABEL_ONLY)
    and the exact input the harness gave its tool is kept in `observed`."""
    text = use["input"].get("command") or json.dumps(use["input"])
    return {"command_id": f"{turn.name}-call-{n:02d}", "argv": None, "source_quality": "LABEL_ONLY",
            "exit_code": result["exit_code"],
            "wall_seconds": None if took is None else round(took, 3),
            "expected": f"{use['name']} tool call: {use['description']}".strip(),
            "observed": f"{'Error' if result['is_error'] else 'Completed'}. Exact {use['name']} input: {text}",
            "output_excerpt": excerpt(result["output"]), "working_directory": None,
            "environment_variable_names": [], "environment_capture_status": "UNKNOWN",
            "evidence_refs": ["stream.jsonl"]}


def main() -> None:
    turn = Path(sys.argv[1]).resolve()
    harness = sys.argv[2]
    events = parser(harness)(turn)
    start = ts((turn / "start_utc").read_text().strip())
    end = ts((turn / "end_utc").read_text().strip())
    out = [f"# Turn {turn.name}", "", f"- Controller start: {start.isoformat()}", f"- Controller end: {end.isoformat()}",
           f"- Exit code: {(turn / 'exit_code').read_text().strip()}", ""]
    uses: dict[str, tuple[dict, datetime]] = {}
    commands: list[dict] = []
    tool_seconds = 0.0
    tool_calls = 0
    reasoning_blocks = 0
    session_id = None
    result = None
    last_ts = start

    for e in events:
        if e["at"]:
            last_ts = ts(e["at"])
        when = last_ts.strftime("%H:%M:%S")
        if e["kind"] == "session":
            session_id = e["session_id"]
            out += [f"**{when} session** `{e['session_id']}` model `{e['model']}` cwd `{e['cwd']}`", ""]
        elif e["kind"] == "text":
            out += [f"**{when} assistant**", "", e["text"], ""]
        elif e["kind"] == "tool_use":
            tool_calls += 1
            uses[e["id"]] = (e, last_ts)
            body = e["input"].get("command") or json.dumps(e["input"], indent=1)
            out += [f"**{when} tool call {tool_calls}: {e['name']}** — {e['description']}", "", "```", clip(body), "```", ""]
        elif e["kind"] == "tool_result":
            use, began = uses[e["id"]]
            took = (last_ts - began).total_seconds()
            tool_seconds += took
            commands.append(command_entry(turn, len(commands) + 1, use, e, took))
            flag = " (error)" if e["is_error"] else ""
            out += [f"**{when} tool result{flag}** after {took:.1f} s", "", "```", clip(e["output"]), "```", ""]
        elif e["kind"] == "note":
            out += [f"**{when} harness note** ({e['source']})", "", "```", clip(e["text"]), "```", ""]
        elif e["kind"] == "reasoning":
            reasoning_blocks += 1
        elif e["kind"] == "result":
            result = e

    wall = (end - start).total_seconds()
    summary = {
        "turn_id": turn.name,
        "session_id": session_id,
        "controller_start_utc": start.isoformat(),
        "controller_end_utc": end.isoformat(),
        "wall_seconds": round(wall, 3),
        "tool_calls": tool_calls,
        "tool_seconds": round(tool_seconds, 3),
        "model_and_other_seconds": round(wall - tool_seconds, 3),
        "encrypted_reasoning_blocks": reasoning_blocks,
        "result_subtype": result and result["subtype"],
        "num_turns_reported": result and result["num_turns"],
        "duration_ms_reported": result and result["duration_ms"],
        "is_error": result and result["is_error"],
        "final_text": result and result["text"],
    }
    out += ["## Timing", "", "```json", json.dumps({k: v for k, v in summary.items() if k != "final_text"}, indent=1), "```"]
    (turn / "transcript.md").write_text("\n".join(out) + "\n")
    (turn / "turn-summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    (turn / "tool-calls.json").write_text(json.dumps(commands, indent=1) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "final_text"}))


if __name__ == "__main__":
    main()
