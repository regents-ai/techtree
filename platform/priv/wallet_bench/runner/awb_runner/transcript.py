"""One turn's readable record, from the agent's ATIF trajectory: transcript.md, turn-summary.json and tool-calls.json.

Timing comes from the controller's start_utc and end_utc around the whole turn, and from step timestamps where the
agent records them. Reasoning is counted, never printed.
"""
import json
from datetime import datetime
from pathlib import Path

CLIP = 4000
EXCERPT = 600


def clip(text: str) -> str:
    return text if len(text) <= CLIP else text[:CLIP] + f"\n… [{len(text) - CLIP} more characters in trajectory.json]"


def excerpt(text: str) -> str:
    return text if len(text) <= EXCERPT else text[:EXCERPT] + f" … [truncated; {len(text)} characters]"


def text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return "\n".join(part.get("text") or f"[{part.get('type')}]" for part in content)


def moment(turn: Path, name: str) -> datetime:
    return datetime.fromisoformat((turn / name).read_text().strip().replace("Z", "+00:00"))


def write(turn: Path) -> dict:
    start, end = moment(turn, "start_utc"), moment(turn, "end_utc")
    trajectory_path = turn / "trajectory.json"
    trajectory = json.loads(trajectory_path.read_text()) if trajectory_path.exists() else None
    out = [f"# Turn {turn.name}", "", f"- Controller start: {start.isoformat()}", f"- Controller end: {end.isoformat()}",
           f"- Exit code: {(turn / 'exit_code').read_text().strip()}", ""]
    commands: list[dict] = []
    reasoning_steps = 0
    final_text = None

    if trajectory is None:
        out += ["The agent left no trajectory for this turn; its own output is in stream.jsonl.", ""]
    else:
        agent = trajectory["agent"]
        out += [f"**session** `{trajectory.get('session_id')}` agent `{agent['name']} {agent['version']}` "
                f"model `{agent.get('model_name')}`", ""]
        for step in trajectory["steps"]:
            when = f"{step['timestamp'][11:19]} " if step.get("timestamp") else ""
            if step.get("reasoning_content"):
                reasoning_steps += 1
            message = text(step.get("message")).strip()
            if message:
                out += [f"**{when}{step['source']}**", "", clip(message), ""]
                if step["source"] == "agent":
                    final_text = message
            results = {r.get("source_call_id"): r for r in (step.get("observation") or {}).get("results", [])}
            for call in step.get("tool_calls") or []:
                arguments = call["arguments"]
                body = arguments.get("command") if isinstance(arguments.get("command"), str) else json.dumps(arguments, indent=1)
                result = results.get(call["tool_call_id"])
                output = text(result and result.get("content"))
                failed = bool(result and (result.get("extra") or {}).get("is_error"))
                commands.append({
                    "command_id": f"{turn.name}-call-{len(commands) + 1:02d}", "argv": None, "source_quality": "LABEL_ONLY",
                    "exit_code": None, "wall_seconds": None, "expected": f"{call['function_name']} tool call",
                    "observed": f"{'Error' if failed else 'Completed'}. Exact {call['function_name']} input: {body}",
                    "output_excerpt": excerpt(output), "working_directory": None, "environment_variable_names": [],
                    "environment_capture_status": "UNKNOWN", "evidence_refs": ["trajectory.json"],
                })
                flag = " (error)" if failed else ""
                out += [f"**{when}tool call {len(commands)}: {call['function_name']}**", "", "```", clip(body), "```", "",
                        f"**tool result{flag}**", "", "```", clip(output), "```", ""]

    summary = {
        "turn_id": turn.name,
        "session_id": trajectory and trajectory.get("session_id"),
        "controller_start_utc": start.isoformat(),
        "controller_end_utc": end.isoformat(),
        "wall_seconds": round((end - start).total_seconds(), 3),
        "steps": trajectory and len(trajectory["steps"]),
        "tool_calls": len(commands),
        "reasoning_steps": reasoning_steps,
        "final_text": final_text,
    }
    out += ["## Timing", "", "```json", json.dumps({k: v for k, v in summary.items() if k != "final_text"}, indent=1), "```"]
    (turn / "transcript.md").write_text("\n".join(out) + "\n")
    (turn / "turn-summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    (turn / "tool-calls.json").write_text(json.dumps(commands, indent=1) + "\n")
    return summary
