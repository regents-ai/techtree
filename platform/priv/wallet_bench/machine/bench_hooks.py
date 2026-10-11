"""LiteLLM hooks for the bench's model translator.

Every request reaches OpenAI as gpt-6-luna at reasoning effort high, whatever the harness asked for (harnesses send
their own effort for side requests). Each request as sent is logged with its call id, model and effort, and each call's
charge with its call id, to /work/proxy/calls.jsonl.

The attempt's calls never cost more than BUDGET_USD. Each request holds RESERVE_USD, the most one call can be priced
at (922,000 input tokens all written to the cache and 128,000 output tokens, at the long-prompt prices in
proxy-install.sh), until it is charged. A request that would take the recorded cost plus every held amount past the
budget is refused, so calls made at the same moment cannot overshoot it together. A call is charged:

- answered: the price LiteLLM gives it;
- interrupted: RESERVE_USD, for a stream the harness stopped reading, because the model may have generated more than
  was delivered;
- failed: nothing when the model server answered with an error status, otherwise RESERVE_USD, because a call that
  lost its connection, timed out or failed after the answer arrived may have been billed.

LiteLLM enforces its own budgets only with a database, which the machine does not run. The total is read back from the
log when the translator starts, so a restart does not reset it, and a call sent before the restart but never charged
is charged as interrupted then. The log starts empty with each attempt, because each attempt starts from the baseline
disk.
"""
import json
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from litellm.integrations.custom_logger import CustomLogger

BUDGET_USD = 5.0
RESERVE_USD = 0.33
CALLS = "/work/proxy/calls.jsonl"
CHARGES = ("answered", "interrupted", "failed")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _log(entry: dict) -> None:
    with open(CALLS, "a") as f:
        f.write(json.dumps({"at": _now(), **entry}) + "\n")


def _spent() -> float:
    try:
        with open(CALLS) as f:
            entries = [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return 0.0
    charged = {entry["call_id"] for entry in entries if entry["event"] in CHARGES}
    for call_id in sorted({entry["call_id"] for entry in entries if entry["event"] == "sent"} - charged):
        _log({"event": "interrupted", "call_id": call_id, "cost": RESERVE_USD, "call_type": None})
        entries.append({"event": "interrupted", "cost": RESERVE_USD})
    return sum(entry["cost"] for entry in entries if entry["event"] in CHARGES)


def _error_status(exception) -> bool:
    """Whether the model server answered with an error status. LiteLLM wraps every failure, a lost connection too, in
    its own status-like error, so the chain is searched for the HTTP client's error from an actual response."""
    while exception is not None:
        if isinstance(exception, httpx.HTTPStatusError):
            return True
        exception = exception.__cause__ or exception.__context__
    return False


class BenchHooks(CustomLogger):
    def __init__(self):
        super().__init__()
        self.spent = _spent()
        self.seen = set()
        self.held = set()
        self.interrupted = set()

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        call_id = data["litellm_call_id"]
        # One answer per request: more choices would multiply a call's price past its hold.
        data.pop("n", None)
        if call_type in ("aresponses", "responses"):
            data["reasoning"] = {**(data.get("reasoning") or {}), "effort": "high"}
            data.pop("reasoning_effort", None)
        else:
            data["reasoning_effort"] = "high"
            data.pop("thinking", None)
        # Each call id belongs to one request, so a late event from an earlier request cannot settle a later one.
        if call_id in self.seen:
            raise HTTPException(status_code=400, detail={"error": "This call id has already been used."})
        if self.spent + RESERVE_USD * (len(self.held) + 1) > BUDGET_USD:
            raise HTTPException(status_code=400, detail={"error": f"This test's model budget of ${BUDGET_USD:.2f} is spent."})
        self.seen.add(call_id)
        self.held.add(call_id)
        return data

    def log_pre_api_call(self, model, messages, kwargs):
        body = (kwargs.get("additional_args") or {}).get("complete_input_dict") or {}
        # LiteLLM also calls this for requests it refuses before building a body; those are never sent.
        if not body:
            return
        effort = body.get("reasoning_effort") or (body.get("reasoning") or {}).get("effort")
        _log({"event": "sent", "call_id": kwargs["litellm_call_id"], "model": body.get("model"), "effort": effort,
              "call_type": kwargs.get("call_type")})

    async def async_post_call_streaming_iterator_hook(self, user_api_key_dict, response, request_data):
        finished = False
        try:
            async for chunk in response:
                yield chunk
            finished = True
        finally:
            if not finished:
                call_id = request_data["litellm_call_id"]
                if call_id in self.held:
                    self.held.discard(call_id)
                    self.interrupted.add(call_id)
                self._charge("interrupted", call_id, RESERVE_USD, request_data.get("call_type"))

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        call_id = kwargs["litellm_call_id"]
        if call_id in self.interrupted:
            self.interrupted.discard(call_id)
            return
        self.held.discard(call_id)
        # A call LiteLLM could not price counts at the most it could have cost.
        cost = kwargs.get("response_cost")
        self._charge("answered", call_id, RESERVE_USD if cost is None else float(cost), kwargs.get("call_type"))

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        # A request refused before reaching the model never held anything.
        if kwargs.get("litellm_no_upstream_llm_call"):
            return
        call_id = kwargs["litellm_call_id"]
        if call_id in self.interrupted:
            self.interrupted.discard(call_id)
            return
        self.held.discard(call_id)
        cost = 0.0 if _error_status(kwargs.get("exception")) else RESERVE_USD
        self._charge("failed", call_id, cost, kwargs.get("call_type"))

    def _charge(self, event, call_id, cost, call_type):
        self.spent += cost
        _log({"event": event, "call_id": call_id, "cost": cost, "call_type": call_type})


bench_hooks = BenchHooks()
