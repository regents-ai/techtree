"""Shared setup for the Hermes plugin's test suite.

These tests belong to the plugin, and they run from here. The plugin checkout
ships the runtime, the Skills and the release bytes and nothing else, so that
an install-time scanner reads only what the plugin actually does; the suite
that proves the guards work — including the fixtures written to look exactly
like the attacks they catch — lives in this repository, next to the CLI it
talks to.

So the two paths this file puts on ``sys.path`` are the halves of that split:
the plugin's tooling in ``tools/plugin``, and this directory, whose
``support`` module holds the host and CLI doubles. The plugin package itself
is loaded once, by path, under a stable importable name, the same way the
repository tooling and the host both load it. Test modules can then import
``techtree_hermes.<module>`` normally.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).resolve().parent
PLUGIN_TOOLING = TESTS_ROOT.parents[1] / "tools" / "plugin"

for path in (PLUGIN_TOOLING, TESTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from _plugin_package import load_plugin_package, plugin_checkout  # noqa: E402
from support import RecordingContext  # noqa: E402

#: The plugin checkout these tests read. Named here so that a test which has
#: to reach for a file of the plugin's — its README, its manifest — reads the
#: same checkout the package was loaded from.
PLUGIN_CHECKOUT = plugin_checkout()

load_plugin_package()


@pytest.fixture
def ctx() -> RecordingContext:
    """A fresh recording host context."""
    return RecordingContext()
