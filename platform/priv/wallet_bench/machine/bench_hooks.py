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

Only the harness's own tools reach the model, and no request runs in the background: OpenAI's hosted tools and
background responses are billed apart from the answer and could cost more than a hold. The Responses WebSocket mode is
refused, because a session makes many calls after a single check, and so are LiteLLM's own retries, fallbacks and
several-model requests, the priority tier and nested extras.

LiteLLM enforces its own budgets only with a database, which the machine does not run. The total and the call ids
already used are read back from the log when the translator starts, so a restart resets neither, and a call sent
before the restart but never charged is charged as interrupted then. The log starts empty with each attempt, because
each attempt starts from the baseline disk.
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
# Tools OpenAI runs itself (web search, file search, code containers, image generation, remote MCP) are billed apart
# from tokens and can cost more than a hold, so only tools the harness runs itself reach the model.
RESPONSES_TOOLS = ("function", "custom", "local_shell", "shell", "apply_patch")
CHAT_TOOLS = ("function", "custom")
# LiteLLM's own request fields that would send one request to the model more than once: retries and fallbacks after a
# failure (directly, by retry policy or as router settings), and the fastest of several models.
REPEATS = ("num_retries", "max_retries", "model_group_retry_policy", "fallbacks", "context_window_fallbacks",
           "content_policy_fallbacks", "context_window_fallback_dict", "router_settings_override", "fastest_response")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _log(entry: dict) -> None:
    with open(CALLS, "a") as f:
        f.write(json.dumps({"at": _now(), **entry}) + "\n")


def _ledger() -> tuple[float, set]:
    """The amount charged so far and every call id already used, charging calls sent but never charged."""
    try:
        with open(CALLS) as f:
            entries = [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return 0.0, set()
    charged = {entry["call_id"] for entry in entries if entry["event"] in CHARGES}
    for call_id in sorted({entry["call_id"] for entry in entries if entry["event"] == "sent"} - charged):
        _log({"event": "interrupted", "call_id": call_id, "cost": RESERVE_USD, "call_type": None})
        entries.append({"event": "interrupted", "call_id": call_id, "cost": RESERVE_USD})
    spent = sum(entry["cost"] for entry in entries if entry["event"] in CHARGES)
    return spent, {entry["call_id"] for entry in entries}


def _harness_tools(call_type, tools: list) -> list:
    """The tools the harness runs itself. An Anthropic Messages tool of the harness's own has a name and an input
    schema; LiteLLM forwards the others, and turns Anthropic's web search into OpenAI's."""
    if call_type == "anthropic_messages":
        return [tool for tool in tools if "input_schema" in tool and tool.get("type", "custom") == "custom"]
    allowed = RESPONSES_TOOLS if call_type in ("aresponses", "responses") else CHAT_TOOLS
    # The shell tool runs on the harness's machine only with a local environment; otherwise OpenAI starts a container.
    return [tool for tool in tools if tool.get("type") in allowed
            and (tool.get("type") != "shell" or (tool.get("environment") or {"type": "local"}).get("type") == "local")]


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
        self.spent, self.seen = _ledger()
        self.held = set()
        self.interrupted = set()

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        # A Responses WebSocket session makes a call for every message it receives, all after this one check.
        if call_type == "_aresponses_websocket":
            raise HTTPException(status_code=400, detail={"error": "Send each request over HTTP."})
        # LiteLLM sends a chat request naming several models, separated by commas, to each of them.
        if "," in str(data.get("model") or ""):
            raise HTTPException(status_code=400, detail={"error": "Name one model."})
        call_id = data["litellm_call_id"]
        # LiteLLM merges extra_body over the request after this hook, so it could put back anything removed here.
        data.pop("extra_body", None)
        # One answer per request: more choices would multiply a call's price past its hold. A background response
        # keeps running and billing after its first answer, so every request is answered in the foreground.
        data.pop("n", None)
        data.pop("background", None)
        for field in REPEATS:
            data.pop(field, None)
        # The priority tier costs more than the list price the hold is worked out from.
        data.pop("service_tier", None)
        data.pop("web_search_options", None)
        tools = _harness_tools(call_type, data.pop("tools", None) or [])
        if tools:
            data["tools"] = tools
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
