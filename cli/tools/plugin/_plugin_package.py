"""Import the Hermes plugin package from this monorepo or a sibling checkout.

Hermes loads a plugin by path, so the plugin repository's own directory is the
package. Its tests and its tooling live here instead, in the Techtree
repository, because a plugin checkout that ships adversarial fixtures — fake
private keys, destructive command strings written to prove the guards catch
them — is a checkout an install-time scanner is right to call dangerous.

Both sides of that split still need one importable name for the package:
`techtree-plugin` is not a Python identifier, so `import techtree-plugin` can
never work. Everything here loads that directory under the stable name
`techtree_hermes`, exactly as the host loads it under a name of its own.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

PACKAGE_NAME = "techtree_hermes"

#: The CLI repository root. In the monorepo, its parent is the repository root.
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

#: Supported layouts, in preference order: the monorepo and the frozen v0.1
#: sibling-repository checkout.
PLUGIN_CHECKOUT_CANDIDATES = (
    REPOSITORY_ROOT.parent / "plugin",
    REPOSITORY_ROOT.parent / "techtree-plugin",
)


def plugin_checkout() -> Path:
    """Return the plugin checkout, or say exactly what is missing and where."""
    for checkout in PLUGIN_CHECKOUT_CANDIDATES:
        if (checkout / "__init__.py").is_file():
            return checkout

    searched = ", ".join(str(path) for path in PLUGIN_CHECKOUT_CANDIDATES)
    raise FileNotFoundError(
        "no Hermes plugin checkout found. The plugin's tests and tooling read "
        f"the plugin package from one of these locations: {searched}."
    )


def load_plugin_package() -> ModuleType:
    """Import the plugin package from that checkout and return it.

    Importing it runs ``__init__.py``, which by contract only defines
    registration functions: no side effect happens until a host calls
    ``register``.
    """
    loaded = sys.modules.get(PACKAGE_NAME)
    if loaded is not None:
        return loaded

    root = plugin_checkout()
    spec = importlib.util.spec_from_file_location(
        PACKAGE_NAME, root / "__init__.py", submodule_search_locations=[str(root)]
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"no plugin package at {root}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[PACKAGE_NAME]
        raise
    return module
