"""Shared test setup.

The plugin package is loaded here, once, the same way the repository tooling
loads it: by path, under a stable importable name. Test modules can then
import ``techtree_hermes.<module>`` normally. Importing the package runs
``__init__.py``, which defines functions and does nothing else.
"""

from __future__ import annotations

import pytest
from _plugin_package import load_plugin_package
from support import RecordingContext

load_plugin_package()


@pytest.fixture
def ctx() -> RecordingContext:
    """A fresh recording host context."""
    return RecordingContext()
