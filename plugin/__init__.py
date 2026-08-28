"""Techtree operator plugin for Hermes. Specification sections 7.1, 7.4.

Loading this plugin is inert by design. Registration verifies the release
bytes that shipped inside the plugin, assembles an immutable service
container, and tells the host which tools, commands, hooks, and Skills exist.
That is all it does.

In particular, registration never:

* reaches the network,
* installs a package,
* runs Docker,
* runs the Techtree CLI,
* calls a model,
* or writes to the user's files.

The reason is not tidiness. A plugin that installed software while being
loaded would take an action nobody approved, on a host whose owner may only
have been listing their plugins. Every installation this plugin can lead to
goes through an explicit, pinned plan and the host's own approval surface,
long after loading is over. The plugin therefore loads and answers questions
perfectly well on a machine where Techtree was never installed.
"""

from __future__ import annotations

from typing import Any

from .cli.constants import (
    PLUGIN_ROOT,
    SKILL_ENTRY_FILENAME,
    SKILLS_DIRNAME,
    TOOLSET_NAME,
)
from .cli.errors import PluginError
from .host.commands import (
    SLASH_ARGS_HINT,
    SLASH_COMMANDS,
    register_cli_subcommands,
    slash_handler,
)
from .host.hooks import SESSION_HOOKS, build_session_hooks
from .host.schemas import all_tool_schemas
from .services.container import PluginServices, build_services
from .tools import TOOL_HANDLERS, bind

__all__ = ["register"]


def register(ctx: Any) -> None:
    """Validate local static release assets and register the plugin surfaces.

    Must not: access the network, install a package, run Docker, run the
    Techtree CLI, call an LLM, or mutate user files.
    """
    services = build_services(ctx)
    _register_tools(ctx, services)
    _register_commands(ctx, services)
    _register_skills(ctx)
    _register_hooks(ctx, services)


def _register_tools(ctx: Any, services: PluginServices) -> None:
    """Register every declared model-visible tool."""
    schemas = all_tool_schemas()
    for name, handler in sorted(TOOL_HANDLERS.items()):
        schema = schemas.get(name)
        if schema is None:
            raise PluginError(
                f"tool {name!r} has a handler but no declared schema",
                code="plugin_tool_undeclared",
            )
        ctx.register_tool(
            name=name,
            toolset=TOOLSET_NAME,
            schema=schema,
            handler=bind(services, handler),
            description=schema["description"],
        )


def _register_commands(ctx: Any, services: PluginServices) -> None:
    """Register the `/techtree` and `hermes techtree ...` command surfaces."""
    handler = slash_handler(services)
    for name, description in sorted(SLASH_COMMANDS.items()):
        ctx.register_command(
            name=name,
            handler=handler,
            description=description,
            args_hint=SLASH_ARGS_HINT,
        )
    register_cli_subcommands(ctx, services)


def _register_skills(ctx: Any) -> None:
    """Register the namespaced read-only operator Skills bundled here.

    These Skills teach the host agent how to operate Techtree. They are never
    mounted into the evaluated Docker subject: the subject receives only what
    its own immutable manifest declares.
    """
    skills_root = PLUGIN_ROOT / SKILLS_DIRNAME
    if not skills_root.is_dir():
        return
    for entry in sorted(skills_root.iterdir()):
        if (entry / SKILL_ENTRY_FILENAME).is_file():
            ctx.register_skill(name=entry.name, path=entry)


def _register_hooks(ctx: Any, services: PluginServices) -> None:
    """Register the additive-signature session hooks."""
    callbacks = build_session_hooks(services)
    for name in sorted(SESSION_HOOKS):
        ctx.register_hook(name, callbacks[name])
