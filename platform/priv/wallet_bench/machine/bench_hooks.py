"""LiteLLM hooks for the bench's model translator.

Every request reaches Anthropic as claude-opus-5-5 with adaptive thinking at effort high, whatever the harness asked
for (harnesses send their own effort for side requests). Each request as sent is logged with its call id, model and
effort, and each call's hold and charge with its call id, to /work/proxy/calls.jsonl.

The attempt's calls never cost more than BUDGET_USD. Each request holds the most it can be priced at until it is
charged: its input tokens, all priced as five-minute cache writes (the dearest input), and MAX_OUTPUT output tokens,
the cap every request is given. An Anthropic Messages request's input is counted by Anthropic's token counter, which
is free and runs no model, plus a tenth, because the counter is an estimate. A translated request's input is bounded
by its length in bytes, since no Claude token is shorter than a byte, plus TOOL_ALLOWANCE for the tool instructions
Anthropic adds and MEDIA_ALLOWANCE for each image. Files and documents are refused in translated requests, because a
short link or a small file can stand for many pages of input. No request is held for more input than the model's context
window. A request that would take the recorded cost plus every held amount past the budget is refused, so calls made
at the same moment cannot overshoot it together. A call is charged:

- answered: the price LiteLLM gives it;
- interrupted: its hold, for a stream the harness stopped reading, because the model may have generated more than was
  delivered;
- failed: nothing when the model server answered with an error status, otherwise its hold, because a call that lost
  its connection, timed out, failed inside a stream or failed after the answer arrived may have been billed.

Each call is charged once, by whichever of these comes first. Every request is sent once. LiteLLM would send one again
on a fresh connection when the first connection breaks, even after Anthropic has received it; to the address a 307 or
308 redirect names; and, for an Anthropic Messages request refused for an invalid thinking block, without its thinking.
All three are switched off: a broken connection fails the call and charges its hold, and a redirect or a refusal fails
it and charges nothing.

Only the harness's own tools reach the model, and nothing billed apart from tokens or above the list price: Anthropic's
server tools, MCP servers, containers and server-side context management are removed, and so are fast mode, the
priority tier, a pinned inference region and one-hour cache writes. The Responses WebSocket mode is refused, because a
session makes many calls after a single check, and so are LiteLLM's own retries, fallbacks and several-model requests,
Anthropic's model fallbacks and nested extras.

LiteLLM enforces its own budgets only with a database, which the machine does not run. The total, the holds and the
call ids already used are read back from the log when the translator starts, so a restart resets none of them, and a
call sent before the restart but never charged is charged its hold as interrupted then. The log starts empty with each
attempt, because each attempt starts from the baseline disk.
"""
import json
import math
import os
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from litellm.integrations.custom_logger import CustomLogger
from litellm.llms.base_llm.anthropic_messages.transformation import BaseAnthropicMessagesConfig
from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler

BUDGET_USD = 5.0
MODEL = "claude-opus-5-5"
MAX_OUTPUT = 32_000
CONTEXT = 1_000_000
# claude-opus-5-5 list prices per token: a five-minute cache write and output.
CACHE_WRITE_USD = 0.000005
OUTPUT_USD = 0.00002
TOOL_ALLOWANCE = 10_000
# Anthropic shrinks an image, a linked one too, to at most 4,784 tokens on Claude 4.7 and later models (Vision guide,
# platform.claude.com, read 12 Oct 2026).
MEDIA_ALLOWANCE = 10_000
COUNT_TOKENS = "https://api.anthropic.com/v1/messages/count_tokens"
CALLS = "/work/proxy/calls.jsonl"
CHARGES = ("answered", "interrupted", "failed")
# Tools the harness runs itself. LiteLLM turns a Responses custom tool (Codex's patch tool) into a function tool; the
# Responses shell tools have no Anthropic form and LiteLLM drops them.
TRANSLATED_TOOLS = ("function", "custom")
# The request fields that hold the conversation and its tools.
CONTENT = ("system", "messages", "input", "instructions", "tools")
MEDIA = ("image", "image_url", "input_image", "input_audio")
FILES = ("document", "file", "input_file")
# Request fields billed apart from tokens or above the list price, or that send one request to more than one model:
# LiteLLM's retries and fallbacks after a failure (directly, by retry policy or as router settings), the fastest of
# several models, and Anthropic's own model fallbacks, server tools and pricing options.
REMOVED = ("num_retries", "max_retries", "model_group_retry_policy", "fallbacks", "context_window_fallbacks",
           "content_policy_fallbacks", "context_window_fallback_dict", "router_settings_override", "fastest_response",
           "n", "background", "service_tier", "speed", "inference_geo", "web_search_options", "mcp_servers",
           "container", "context_management")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _log(entry: dict) -> None:
    with open(CALLS, "a") as f:
        f.write(json.dumps({"at": _now(), **entry}) + "\n")


def _ledger() -> tuple[float, dict]:
    """The amount charged so far and every call id already used with its hold, charging calls sent but never
    charged."""
    try:
        with open(CALLS) as f:
            entries = [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return 0.0, {}
    holds = {entry["call_id"]: entry["hold"] for entry in entries if entry["event"] == "held"}
    charged = {entry["call_id"] for entry in entries if entry["event"] in CHARGES}
    for call_id in sorted({entry["call_id"] for entry in entries if entry["event"] == "sent"} - charged):
        _log({"event": "interrupted", "call_id": call_id, "cost": holds[call_id], "call_type": None})
        entries.append({"event": "interrupted", "call_id": call_id, "cost": holds[call_id]})
    spent = sum(entry["cost"] for entry in entries if entry["event"] in CHARGES)
    return spent, holds


def _harness_tools(call_type, tools: list) -> list:
    """The tools the harness runs itself. An Anthropic Messages tool of the harness's own has a name and an input
    schema; every other type is one Anthropic runs."""
    if call_type == "anthropic_messages":
        return [tool for tool in tools if "input_schema" in tool and tool.get("type", "custom") == "custom"]
    return [tool for tool in tools if tool.get("type") in TRANSLATED_TOOLS]


def _five_minute_cache(value) -> None:
    """Removes every one-hour cache time, so each cache write is a five-minute one."""
    if isinstance(value, dict):
        if isinstance(value.get("cache_control"), dict):
            value["cache_control"].pop("ttl", None)
        for item in value.values():
            _five_minute_cache(item)
    elif isinstance(value, list):
        for item in value:
            _five_minute_cache(item)


def _capped(value) -> int:
    """The output cap a request asked for, never above MAX_OUTPUT."""
    return min(value, MAX_OUTPUT) if isinstance(value, int) and value > 0 else MAX_OUTPUT


def _parts(value, types: tuple) -> int:
    """How many parts of the given types a request carries."""
    if isinstance(value, dict):
        return (value.get("type") in types) + sum(_parts(item, types) for item in value.values())
    if isinstance(value, list):
        return sum(_parts(item, types) for item in value)
    return 0


def _hold(tokens: int) -> float:
    return min(tokens, CONTEXT) * CACHE_WRITE_USD + MAX_OUTPUT * OUTPUT_USD


async def _counted(data: dict) -> int:
    """An Anthropic Messages request's input tokens, from Anthropic's token counter, plus a tenth."""
    body = {"model": MODEL, "messages": data.get("messages") or [], "thinking": {"type": "adaptive"}}
    for field in ("system", "tools"):
        if data.get(field):
            body[field] = data[field]
    headers = {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(COUNT_TOKENS, json=body, headers=headers)
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail={"error": "The request's size could not be checked. Try again."})
    if response.status_code == 400:
        raise HTTPException(status_code=400, detail=response.json())
    if response.status_code != 200:
        raise HTTPException(status_code=503, detail={"error": "The request's size could not be checked. Try again."})
    return math.ceil(response.json()["input_tokens"] * 1.1)


def _bounded(data: dict) -> int:
    """A translated request's input tokens, at most: its length in bytes and the allowances."""
    content = {field: data.get(field) for field in CONTENT + ("response_format", "text")}
    if _parts(content, FILES):
        raise HTTPException(status_code=400, detail={"error": "Files and documents are not accepted; send text or "
                                                              "images."})
    size = len(json.dumps(content, ensure_ascii=False).encode())
    return size + TOOL_ALLOWANCE + MEDIA_ALLOWANCE * _parts(content, MEDIA)


def _error_status(exception) -> bool:
    """Whether the model server answered with an error status. LiteLLM wraps every failure, a lost connection too, in
    its own status-like error, so the chain is searched for the HTTP client's error from an actual response."""
    while exception is not None:
        if isinstance(exception, httpx.HTTPStatusError):
            return True
        exception = exception.__cause__ or exception.__context__
    return False


async def _not_sent_again(self, **kwargs):
    raise httpx.ConnectError("The connection broke; the request is not sent again.")


_post = AsyncHTTPHandler.post


async def _post_once(self, *args, **kwargs):
    # httpx sends a request again to wherever a 307 or 308 points; a redirect fails the call instead.
    self.client.follow_redirects = False
    return await _post(self, *args, **kwargs)


AsyncHTTPHandler.single_connection_post_request = _not_sent_again
AsyncHTTPHandler.post = _post_once
# An Anthropic Messages request that Anthropic refuses for an invalid thinking block is sent again without thinking.
BaseAnthropicMessagesConfig.max_retry_on_anthropic_messages_http_error = property(lambda self: 1)


class BenchHooks(CustomLogger):
    def __init__(self):
        super().__init__()
        self.spent, self.holds = _ledger()
        self.held = {}

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
        # The harness's own request headers, an anthropic-beta header among them, stay with the relay: a beta can switch
        # on billing that no body field shows.
        for field in ("headers", "extra_headers", "provider_specific_header"):
            data.pop(field, None)
        for field in REMOVED:
            data.pop(field, None)
        tools = data.pop("tools", None) or []
        if not isinstance(tools, list) or not all(isinstance(tool, dict) for tool in tools):
            raise HTTPException(status_code=400, detail={"error": "Send tools as a list of objects."})
        tools = _harness_tools(call_type, tools)
        if tools:
            data["tools"] = tools
        # The request-wide cache setting, then each block's.
        _five_minute_cache({field: data.get(field) for field in CONTENT + ("cache_control",)})
        if call_type == "anthropic_messages":
            thinking = data.get("thinking") if isinstance(data.get("thinking"), dict) else {}
            output_config = data.get("output_config") if isinstance(data.get("output_config"), dict) else {}
            display = {"display": thinking["display"]} if "display" in thinking else {}
            data["thinking"] = {"type": "adaptive", **display}
            data["output_config"] = {**output_config, "effort": "high"}
            data["max_tokens"] = _capped(data.get("max_tokens"))
        elif call_type in ("aresponses", "responses"):
            reasoning = data.get("reasoning") if isinstance(data.get("reasoning"), dict) else {}
            data["reasoning"] = {**reasoning, "effort": "high"}
            data.pop("reasoning_effort", None)
            data["max_output_tokens"] = _capped(data.get("max_output_tokens"))
        else:
            data["reasoning_effort"] = "high"
            data.pop("thinking", None)
            data.pop("output_config", None)
            asked = [value for value in (data.pop("max_completion_tokens", None), data.get("max_tokens")) if value]
            data["max_tokens"] = min(_capped(value) for value in asked or [None])
        hold = _hold(await _counted(data) if call_type == "anthropic_messages" else _bounded(data))
        # Each call id belongs to one request, so a late event from an earlier request cannot settle a later one. The
        # checks from here on run with no wait between them, so two requests cannot both pass them.
        if call_id in self.holds:
            raise HTTPException(status_code=400, detail={"error": "This call id has already been used."})
        if self.spent + sum(self.held.values()) + hold > BUDGET_USD:
            detail = {"error": f"This test's model budget of ${BUDGET_USD:.2f} is spent."}
            raise HTTPException(status_code=400, detail=detail)
        self.holds[call_id] = hold
        self.held[call_id] = hold
        _log({"event": "held", "call_id": call_id, "hold": hold, "call_type": call_type})
        return data

    def log_pre_api_call(self, model, messages, kwargs):
        body = (kwargs.get("additional_args") or {}).get("complete_input_dict") or {}
        # LiteLLM also calls this for requests it refuses before building a body; those are never sent.
        if not body:
            return
        _log({"event": "sent", "call_id": kwargs["litellm_call_id"], "model": body.get("model"),
              "effort": (body.get("output_config") or {}).get("effort"), "call_type": kwargs.get("call_type")})

    async def async_post_call_streaming_iterator_hook(self, user_api_key_dict, response, request_data):
        finished = False
        try:
            async for chunk in response:
                yield chunk
            finished = True
        finally:
            if not finished:
                call_id = request_data["litellm_call_id"]
                self._settle("interrupted", call_id, self.holds[call_id], request_data.get("call_type"))

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        call_id = kwargs["litellm_call_id"]
        # A call LiteLLM could not price counts at the most it could have cost.
        cost = kwargs.get("response_cost")
        self._settle("answered", call_id, self.holds[call_id] if cost is None else float(cost), kwargs.get("call_type"))

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        call_id = kwargs["litellm_call_id"]
        # A request refused before reaching the model is never billed; its hold, if it was given one, is released.
        if kwargs.get("litellm_no_upstream_llm_call"):
            self.held.pop(call_id, None)
            return
        cost = 0.0 if _error_status(kwargs.get("exception")) else self.holds[call_id]
        self._settle("failed", call_id, cost, kwargs.get("call_type"))

    def _settle(self, event, call_id, cost, call_type):
        """Charges a held call and releases its hold; a call already charged, or charged before a restart, is left
        as it is."""
        if self.held.pop(call_id, None) is None:
            return
        self.spent += cost
        _log({"event": event, "call_id": call_id, "cost": cost, "call_type": call_type})


bench_hooks = BenchHooks()
