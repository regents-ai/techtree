"""What registration hands the host is a complete tool contract.

Specification sections 7.4 and 7.15.

A reviewer once called two of these tools with no arguments, read the
refusals as evidence of missing schemas, and lost an hour to a defect that
was not there. The schemas were complete. Nothing proved it about the object
the plugin actually hands over, and "correct in source" is exactly the
assumption that cost the hour, so it is proved here.

The boundary is deliberate and narrow. This file asserts what leaves the
plugin at registration, and stops. What a host's tool-discovery bridge does
with a schema afterwards belongs to that host; simulating it here would test
the simulation and nothing else.

Nothing in this file is listed by name. The tools come from the registration
record, the arguments a tool insists on are discovered by asking its handler,
and each schema is judged against what its own handler demands. A tool added
without a schema, or with an empty one, fails here without anybody having
remembered to extend a list.

The unit suite makes similar statements about the schema mapping the plugin
declares. These are about the object registration puts in the host's hands,
which is a different thing to be sure of.
"""

from __future__ import annotations

import json
import re
from typing import Any, cast

import pytest
import techtree_hermes
from support import RecordingContext, RegisteredTool
from techtree_hermes.schemas import all_tool_schemas
from techtree_hermes.services.container import PluginServices
from techtree_hermes.tools import TOOL_HANDLERS

#: The stable code a handler answers with when a required argument is absent.
ARGUMENT_MISSING = "tool_argument_missing"

#: How that answer names the argument it wanted.
_QUOTED_NAME = re.compile(r"'([A-Za-z_][A-Za-z0-9_]*)'")

#: Any non-empty string counts as supplied, which is what lets the probe walk
#: past one argument to see whether the handler insists on another.
_SUPPLIED = "x"


class SealedServiceError(AssertionError):
    """Raised when a probe reaches for a service instead of refusing first."""


class _Sealed:
    """A service that refuses every use."""

    def __init__(self, what: str) -> None:
        self._what = what

    def __getattr__(self, name: str) -> Any:
        raise SealedServiceError(f"a probe reached {self._what}.{name}")


def _sealed_services(ctx: Any) -> PluginServices:
    """Return a container nothing can be done through.

    The probes below call the real handlers with arguments deliberately
    missing. A handler that answers before it looks at anything is the case
    under test; a handler that would instead reach the CLI, the filesystem or
    the host must not actually get there, so nothing in this container works.
    """
    return PluginServices(
        ctx=_Sealed("ctx"),
        root=cast(Any, _Sealed("root")),
        release_core=cast(Any, _Sealed("release_core")),
        release_core_digest="sha256:" + "0" * 64,
        bridge=cast(Any, _Sealed("bridge")),
        plans=cast(Any, _Sealed("plans")),
        sessions=cast(Any, _Sealed("sessions")),
        assets=cast(Any, _Sealed("assets")),
    )


@pytest.fixture
def registered(
    ctx: RecordingContext, monkeypatch: pytest.MonkeyPatch
) -> RecordingContext:
    """Register the plugin against a recording host, and record what it said."""
    monkeypatch.setattr(techtree_hermes, "build_services", _sealed_services)

    techtree_hermes.register(ctx)

    return ctx


def _answer(tool: RegisteredTool, args: dict[str, Any]) -> dict[str, Any]:
    """Call a registered tool the way the host would, and read its answer."""
    parsed = json.loads(tool.handler(dict(args)))
    assert isinstance(parsed, dict), f"{tool.name} answered with something else"
    return parsed


def _arguments_insisted_on(tool: RegisteredTool) -> list[str]:
    """Ask a handler which arguments it will not work without.

    It is called with nothing, then again with each argument it named already
    supplied, until it stops asking for another. Nothing is listed here: what
    comes back is whatever that handler demands, so a tool written tomorrow is
    covered the day it is written.
    """
    demanded: list[str] = []
    args: dict[str, Any] = {}
    while True:
        answer = _answer(tool, args)
        if answer.get("code") != ARGUMENT_MISSING:
            return demanded
        message = str(answer.get("message", ""))
        named = _QUOTED_NAME.search(message)
        assert named, (
            f"{tool.name} refused a call for a missing argument without "
            f"naming it: {message!r}"
        )
        argument = named.group(1)
        assert argument not in demanded, (
            f"{tool.name} kept asking for {argument!r} after it was supplied"
        )
        demanded.append(argument)
        args[argument] = _SUPPLIED


def test_registration_hands_the_host_at_least_one_tool(
    registered: RecordingContext,
) -> None:
    """Every assertion below is vacuous if registration handed over nothing."""
    assert registered.tools


def test_every_registered_tool_carries_a_complete_schema(
    registered: RecordingContext,
) -> None:
    """A host reading only what it was handed can tell how to call each tool."""
    for name, tool in sorted(registered.tools.items()):
        schema = tool.schema

        assert schema["type"] == "object", f"{name} is not described as an object"

        description = schema.get("description")
        assert isinstance(description, str) and description.strip(), (
            f"{name} was handed over with no description"
        )
        assert tool.description == description, (
            f"{name} was announced with a description its schema does not carry"
        )

        properties = schema.get("properties")
        assert isinstance(properties, dict), f"{name} declares no properties object"

        required = schema.get("required")
        assert isinstance(required, list), (
            f"{name} declares no explicit list of required arguments"
        )
        assert set(required) <= set(properties), (
            f"{name} requires an argument it never declares"
        )

        assert schema.get("additionalProperties") is False, (
            f"{name} does not refuse arguments it never declared"
        )

        for argument, definition in sorted(properties.items()):
            assert isinstance(definition, dict), f"{name}.{argument} is not described"
            assert str(definition.get("description", "")).strip(), (
                f"{name}.{argument} was handed over with no description"
            )


def test_every_argument_a_handler_insists_on_is_declared_required(
    registered: RecordingContext,
) -> None:
    """Nothing a handler refuses to work without is left out of its schema."""
    checked = 0
    for name, tool in sorted(registered.tools.items()):
        schema = tool.schema
        properties = schema.get("properties") or {}
        required = schema.get("required") or []

        for argument in _arguments_insisted_on(tool):
            assert argument in properties, (
                f"{name} refuses a call without {argument!r}, "
                f"which its schema never declares"
            )
            assert argument in required, (
                f"{name} refuses a call without {argument!r}, "
                f"but its schema does not require it"
            )
            checked += 1

    assert checked, "no handler was found to insist on any argument"


def test_the_registered_names_the_schemas_and_the_handlers_are_one_set(
    registered: RecordingContext,
) -> None:
    """A tool exists in all three places or in none of them."""
    assert set(registered.tools) == set(all_tool_schemas()) == set(TOOL_HANDLERS)
