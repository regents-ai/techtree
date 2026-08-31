"""Model-visible tool handlers. Specification section 7.11.

Every handler obeys the same contract, and it is enforced here rather than
repeated fifteen times:

* it takes the tool arguments and returns one JSON string, on success and on
  failure alike;
* it never raises into the host agent loop — an exception becomes a safe error
  payload with a stable code;
* it never blocks on a benchmark: work that takes minutes returns a run
  identifier and the conversation carries on;
* it never emits unbounded output, and when a result is too large to carry it
  says so plainly instead of silently cutting it off.

Handlers are written against the service container and bound to it during
registration, so a handler cannot reach the host, the CLI, or the filesystem
except through services it was given.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import wraps
from types import MappingProxyType
from typing import Any, Protocol

from ..cli.constants import MAX_TOOL_RESULT_BYTES
from ..cli.errors import PluginError, safe_error_payload
from ..host.channels import (
    resolve_channel,
)
from ..services.models import ChannelKind

#: Stable code for a result that will not fit in a model-visible answer.
CODE_TOOL_RESULT_TOO_LARGE = "tool_result_too_large"


class ToolHandler(Protocol):
    """The call shape the host invokes."""

    def __call__(self, args: dict[str, Any], **kwargs: Any) -> str:
        """Return one JSON string describing the outcome."""


class ServiceHandler(Protocol):
    """The call shape a handler is written in, before it is bound."""

    def __call__(self, services: Any, args: dict[str, Any], **kwargs: Any) -> str:
        """Return one JSON string describing the outcome."""


def bind(services: Any, handler: ServiceHandler) -> ToolHandler:
    """Return the handler with its services already supplied."""

    @wraps(handler)
    def call(args: dict[str, Any], **kwargs: Any) -> str:
        return handler(services, args, **kwargs)

    return call


def channel_of(args: Mapping[str, Any], kwargs: Mapping[str, Any]) -> ChannelKind:
    """Return the channel this call should be answered for."""
    return resolve_channel(args.get("channel"), kwargs)


def tool_result(
    payload: Mapping[str, Any], channel: ChannelKind = ChannelKind.UNKNOWN
) -> str:
    """Return one bounded JSON string, safe for the channel reading it.

    A payload too large to carry is replaced by an honest account of that,
    naming the command that shows the whole thing, rather than by a truncated
    document that would parse as if it were complete.

    One budget, whatever is reading. There used to be a much smaller one for
    anything not explicitly a terminal, which was every call that did not say
    so, and it was a guess: no host documents a size at which it splits a
    message. What it bought was a review that vanished at a threshold nobody
    could point at, and what it cost was the diff, the episode count and the
    declared maximum in the one case where the diff was worth showing. A host
    that splits a long message shows a split message; that is the host's
    business, and it is not a reason to throw the answer away here.
    """
    limit = MAX_TOOL_RESULT_BYTES
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    if len(text.encode("utf-8")) <= limit:
        return text

    reduced: dict[str, Any] = {
        "ok": payload.get("ok"),
        "command": payload.get("command"),
        "truncated": True,
        "code": CODE_TOOL_RESULT_TOO_LARGE,
        "message": (
            "The full answer is too large to return here. Nothing was lost: "
            "run the Techtree command yourself to see all of it."
        ),
        "bytes": len(text.encode("utf-8")),
        "limit_bytes": limit,
        "channel": channel.value,
    }
    for key in (
        "run_id",
        "draft_id",
        "next_action",
        "next_actions",
        "publication_offer",
        "completion_summary",
        "error",
    ):
        if key in payload:
            reduced[key] = payload[key]
    return json.dumps(reduced, ensure_ascii=False, sort_keys=True, default=str)


def passthrough(
    envelope: Mapping[str, Any], channel: ChannelKind = ChannelKind.UNKNOWN
) -> str:
    """Return the CLI's own envelope as the answer, bounded and unchanged.

    Techtree's words about a Techtree result are the honest ones, so a
    read-only tool repeats them rather than paraphrasing.
    """
    return tool_result(dict(envelope), channel)


def failed(error: Exception, **extra: Any) -> str:
    """Return the safe JSON answer for a failure."""
    payload: dict[str, Any] = {"ok": False, **safe_error_payload(error), **extra}
    return tool_result(payload)


def safe_tool(handler: Any) -> Any:
    """Wrap a handler so no failure ever reaches the host as an exception."""

    @wraps(handler)
    def call(services: Any, args: dict[str, Any], **kwargs: Any) -> str:
        try:
            answer: str = handler(services, args, **kwargs)
            return answer
        except PluginError as error:
            return failed(error)
        except Exception:  # a defect here must not break the session
            return failed(PluginError("Techtree could not answer that."))

    return call


def require_argument(
    args: Mapping[str, Any], name: str, *, repair: str | None = None
) -> str:
    """Return a required string argument, or say which one was missing."""
    value = args.get(name)
    if not isinstance(value, str) or not value.strip():
        raise PluginError(
            f"this tool needs {name!r}",
            code="tool_argument_missing",
            repair=repair,
        )
    return value.strip()


from .bootstrap import (  # noqa: E402
    techtree_bootstrap_check,
    techtree_bootstrap_install,
)
from .catalog import (  # noqa: E402
    techtree_climb_inspect,
    techtree_climb_list,
    techtree_system_check,
)
from .demo import (  # noqa: E402
    techtree_climb_prepare,
    techtree_climb_start,
    techtree_demo_prepare,
)
from .proof import techtree_proof_verify  # noqa: E402
from .publish import techtree_publish_run  # noqa: E402
from .run import (  # noqa: E402
    techtree_run_cancel,
    techtree_run_result,
    techtree_run_status,
)
from .uplift import (  # noqa: E402
    techtree_uplift_context,
    techtree_uplift_prepare,
    techtree_uplift_propose,
    techtree_uplift_start,
)

TOOL_HANDLERS: Mapping[str, ServiceHandler] = MappingProxyType(
    {
        "techtree_bootstrap_check": techtree_bootstrap_check,
        "techtree_bootstrap_install": techtree_bootstrap_install,
        "techtree_system_check": techtree_system_check,
        "techtree_climb_list": techtree_climb_list,
        "techtree_climb_inspect": techtree_climb_inspect,
        "techtree_climb_prepare": techtree_climb_prepare,
        "techtree_demo_prepare": techtree_demo_prepare,
        "techtree_climb_start": techtree_climb_start,
        "techtree_run_status": techtree_run_status,
        "techtree_run_cancel": techtree_run_cancel,
        "techtree_run_result": techtree_run_result,
        "techtree_proof_verify": techtree_proof_verify,
        "techtree_publish_run": techtree_publish_run,
        "techtree_uplift_context": techtree_uplift_context,
        "techtree_uplift_propose": techtree_uplift_propose,
        "techtree_uplift_prepare": techtree_uplift_prepare,
        "techtree_uplift_start": techtree_uplift_start,
    }
)

__all__ = ["TOOL_HANDLERS", "ServiceHandler", "ToolHandler", "bind"]
