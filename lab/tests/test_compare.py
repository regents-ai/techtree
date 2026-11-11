"""`techtree-lab compare` end to end through verifiers, against a stand-in Ollama that
answers every held-out task: exactly for the Skill arm, with the price in dollars
instead of base units for the baseline."""

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from payment_terms import offers
from techtree_lab import digests
from techtree_lab.cli import SKILL, SLUG, main
from tests.contract import check_contract

ITEMS = {item.prompt: item for item in offers.generate(0)["held_out"]}
WEIGHTS = "ab" * 32


def _reply(messages: list[dict[str, Any]]) -> str:
    answer = json.loads(json.dumps(ITEMS[messages[-1]["content"]].answer))
    if messages[0]["role"] != "system":
        amount = int(answer["accepts"][0]["amount"])
        answer["accepts"][0]["amount"] = offers.decimal(amount, 2)
    return f"Here it is:\n```json\n{json.dumps(answer, indent=2)}\n```"


class StandIn(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        assert self.path == "/api/tags"
        self._send("application/json", json.dumps(
            {"models": [{"name": "nemotron-3-nano:4b", "digest": WEIGHTS}]}
        ).encode())  # fmt: skip

    def do_POST(self) -> None:
        assert self.path == "/v1/chat/completions"
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert body["temperature"] == 0.0 and body["max_tokens"] == 512
        assert body["reasoning_effort"] == "none" and body["stream"] is True
        reply = _reply(body["messages"])
        base = {"id": "c", "object": "chat.completion.chunk", "created": 0, "model": body["model"]}
        chunks = [
            {**base, "choices": [{"index": 0, "delta": {"role": "assistant", "content": reply}}]},
            {**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
            {**base, "choices": [], "usage": {"prompt_tokens": 50, "completion_tokens": 9,
                                              "total_tokens": 59}},
        ]  # fmt: skip
        events = b"".join(b"data: " + json.dumps(c).encode() + b"\n\n" for c in chunks)
        self._send("text/event-stream", events + b"data: [DONE]\n\n")

    def _send(self, content_type: str, data: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:
        pass


@pytest.fixture
def ollama() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), StandIn)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def test_compare_writes_a_report_the_page_accepts(ollama: str, tmp_path: Path) -> None:
    main(["compare", "--ollama", ollama, "--out", str(tmp_path)])

    report = json.loads((tmp_path / f"{SLUG}.json").read_text())
    traces = (tmp_path / f"{SLUG}.traces.jsonl").read_bytes()
    check_contract(report, traces)

    spec = report["spec"]
    assert spec["environment"]["taskset_digest"] == digests.taskset(list(ITEMS.values()))
    assert spec["model"]["weights_digest"] == f"sha256:{WEIGHTS}"
    assert spec["arms"][1]["skill_digest"] == digests.of_bytes(SKILL.read_bytes())
    assert [t["task_id"] for t in spec["results"]["per_task"]] == [
        item.id for item in ITEMS.values()
    ]
    baseline, skill = spec["results"]["arms"]
    assert (baseline["mean_reward"], baseline["solved"]) == (0.9167, 0)
    assert (skill["mean_reward"], skill["solved"]) == (1.0, 64)
    assert baseline["tokens"] == {"prompt": 64 * 50, "completion": 64 * 9}
    assert spec["results"]["paired"]["wins"] == 64
    assert spec["results"]["outcome"] == "uplift"

    lines = [json.loads(line) for line in traces.decode().splitlines()]
    skill_line = lines[1]
    assert skill_line["arm"] == "skill"
    assert skill_line["messages"][0] == {"role": "system", "content": SKILL.read_text()}
    assert lines[0]["messages"][0]["role"] == "user"
