"""LiteLLM hooks for the bench's model translator.

Every request reaches OpenAI as gpt-6-luna at reasoning effort high, whatever the harness asked for (harnesses send
their own effort for side requests). Each request as sent is logged with its model and effort, and each answered call
with the cost LiteLLM priced it at, to /work/proxy/calls.jsonl.

Once the attempt's calls have cost BUDGET_USD, every further request is refused. LiteLLM enforces its own budgets
only with a database, which the machine does not run. The total is read back from the log when the translator
starts, so a restart does not reset it; the log starts empty with each attempt, because each attempt starts from the
baseline disk.
"""
import json
from datetime import datetime, timezone

from fastapi import HTTPException
from litellm.integrations.custom_logger import CustomLogger

BUDGET_USD = 5.0
CALLS = "/work/proxy/calls.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _log(entry: dict) -> None:
    with open(CALLS, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _spent() -> float:
    try:
        with open(CALLS) as f:
            entries = [json.loads(line) for line in f if line.strip()]
        return sum(entry["cost"] for entry in entries if entry["event"] == "answered")
    except FileNotFoundError:
        return 0.0


class BenchHooks(CustomLogger):
    def __init__(self):
        super().__init__()
        self.spent = _spent()

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        if self.spent >= BUDGET_USD:
            raise HTTPException(status_code=400, detail={"error": f"This test's model budget of ${BUDGET_USD:.2f} is spent."})
        if call_type in ("aresponses", "responses"):
            data["reasoning"] = {**(data.get("reasoning") or {}), "effort": "high"}
            data.pop("reasoning_effort", None)
        else:
            data["reasoning_effort"] = "high"
            data.pop("thinking", None)
        return data

    def log_pre_api_call(self, model, messages, kwargs):
        body = (kwargs.get("additional_args") or {}).get("complete_input_dict") or {}
        effort = body.get("reasoning_effort") or (body.get("reasoning") or {}).get("effort")
        _log({"at": _now(), "event": "sent", "model": body.get("model"), "effort": effort,
              "call_type": kwargs.get("call_type")})

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        cost = float(kwargs["response_cost"])
        self.spent += cost
        _log({"at": _now(), "event": "answered", "cost": cost, "call_type": kwargs.get("call_type")})


bench_hooks = BenchHooks()
