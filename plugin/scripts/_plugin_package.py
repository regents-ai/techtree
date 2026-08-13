"""Import the plugin package from this checkout.

Hermes loads a plugin by path, so the repository directory itself is the
package. Repository tooling cannot rely on that: `techtree-hermes` is not a
Python identifier, so `import techtree-hermes` can never work. Everything here
loads the same directory under one stable importable name instead.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

PACKAGE_NAME = "techtree_hermes"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def load_plugin_package(
    *, name: str = PACKAGE_NAME, root: Path = REPOSITORY_ROOT
) -> ModuleType:
    """Import the plugin package and return it.

    Importing it runs ``__init__.py``, which by contract only defines
    registration functions: no side effect happens until a host calls
    ``register``.
    """
    loaded = sys.modules.get(name)
    if loaded is not None:
        return loaded

    spec = importlib.util.spec_from_file_location(
        name, root / "__init__.py", submodule_search_locations=[str(root)]
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"no plugin package at {root}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    return module
