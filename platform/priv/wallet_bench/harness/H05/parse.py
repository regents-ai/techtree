"""Claude Code `--output-format stream-json --verbose` lines -> shared event list (see harness/README.md)."""
import json
import re
from pathlib import Path


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(c.get("text", f"[{c.get('type')}]") for c in content)


def parse(turn: Path) -> list[dict]:
    events = []
    at = None
    for line in (turn / "stream.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        at = e.get("timestamp") or at
        if e["type"] == "system" and e.get("subtype") == "init":
            events.append({"kind": "session", "session_id": e["session_id"], "model": e.get("model"), "cwd": e.get("cwd"), "at": at})
        elif e["type"] == "assistant":
            for c in e["message"]["content"]:
                if c["type"] == "text" and c["text"].strip():
                    events.append({"kind": "text", "text": c["text"].strip(), "at": at})
                elif c["type"] == "tool_use":
                    events.append({"kind": "tool_use", "id": c["id"], "name": c["name"], "input": c["input"],
                                   "description": c["input"].get("description") or c["input"].get("prompt", ""), "at": at})
                elif c["type"] in ("thinking", "redacted_thinking"):
                    events.append({"kind": "reasoning", "at": at})
        elif e["type"] == "user" and isinstance(e["message"]["content"], list):
            for c in e["message"]["content"]:
                if c.get("type") == "tool_result":
                    output = _text(c["content"])
                    # Claude Code prints "Exit code N" only on a failed shell command.
                    exit_code = re.match(r"Exit code (\d+)\n", output)
                    events.append({"kind": "tool_result", "id": c["tool_use_id"], "output": output,
                                   "is_error": bool(c.get("is_error")), "exit_code": exit_code and int(exit_code[1]), "at": at})
        elif e["type"] == "result":
            events.append({"kind": "result", "subtype": e.get("subtype"), "is_error": e.get("is_error"), "text": e.get("result"),
                           "num_turns": e.get("num_turns"), "duration_ms": e.get("duration_ms"), "at": at})
    return events
