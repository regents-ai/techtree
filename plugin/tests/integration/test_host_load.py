"""The plugin loads the way the host loads it.

Hermes imports a plugin directory by path, under a module name derived from
the manifest rather than from the checkout directory, and hands ``register``
its own context. This test reproduces that import exactly, so a checkout whose
directory name is not a Python identifier is proven to be irrelevant to
loading, and so registration is exercised through the real entry point.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from collections.abc import Iterator
from pathlib import Path

import pytest
from support import RecordingContext

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
NAMESPACE = "hermes_plugins_test_load"
MODULE_NAME = f"{NAMESPACE}.techtree"


@pytest.fixture
def host_loaded_plugin() -> Iterator[types.ModuleType]:
    """Import the plugin exactly as Hermes' plugin loader does."""
    namespace = types.ModuleType(NAMESPACE)
    namespace.__path__ = []
    namespace.__package__ = NAMESPACE
    sys.modules[NAMESPACE] = namespace

    spec = importlib.util.spec_from_file_location(
        MODULE_NAME,
        REPOSITORY_ROOT / "__init__.py",
        submodule_search_locations=[str(REPOSITORY_ROOT)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    module.__package__ = MODULE_NAME
    module.__path__ = [str(REPOSITORY_ROOT)]
    sys.modules[MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        for name in [
            name
            for name in sys.modules
            if name == NAMESPACE or name.startswith(f"{NAMESPACE}.")
        ]:
            del sys.modules[name]


def test_the_plugin_imports_under_a_host_chosen_module_name(
    host_loaded_plugin: types.ModuleType,
) -> None:
    assert host_loaded_plugin.__name__ == MODULE_NAME
    assert callable(host_loaded_plugin.register)


def test_registration_through_the_host_entry_point(
    host_loaded_plugin: types.ModuleType, ctx: RecordingContext
) -> None:
    host_loaded_plugin.register(ctx)

    assert set(ctx.tools) == set(host_loaded_plugin.TOOL_HANDLERS)
    assert set(ctx.hooks) == set(host_loaded_plugin.SESSION_HOOKS)
