"""Import the Hermes plugin package under an importable name.

Hermes loads a plugin by path, so this directory is the package. Its name is
not a Python identifier, so the tests and the scripts here load it under the
stable name `techtree_hermes`, exactly as the host loads it under a name of
its own.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

PACKAGE_NAME = "techtree_hermes"

#: The plugin package directory: the parent of this scripts directory.
PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def load_plugin_package() -> ModuleType:
    """Import the plugin package and return it.

    Importing it runs ``__init__.py``, which by contract only defines
    registration functions: no side effect happens until a host calls
    ``register``.
    """
    loaded = sys.modules.get(PACKAGE_NAME)
    if loaded is not None:
        return loaded

    spec = importlib.util.spec_from_file_location(
        PACKAGE_NAME,
        PLUGIN_ROOT / "__init__.py",
        submodule_search_locations=[str(PLUGIN_ROOT)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"no plugin package at {PLUGIN_ROOT}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[PACKAGE_NAME]
        raise
    return module
