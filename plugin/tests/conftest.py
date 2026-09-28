"""Shared setup for the Hermes plugin's test suite.

This file puts two directories on ``sys.path``: the plugin's ``scripts``,
which loads the plugin package, and this directory, whose ``support`` module
holds the host and ``regents`` doubles. The plugin package is loaded once, by
path, under a stable importable name, the same way the scripts and the host
both load it. Test modules can then import ``techtree_hermes.<module>``
normally.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).resolve().parent
PLUGIN_SCRIPTS = TESTS_ROOT.parent / "scripts"

for path in (PLUGIN_SCRIPTS, TESTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from _plugin_package import load_plugin_package  # noqa: E402
from support import RecordingContext  # noqa: E402

load_plugin_package()


@pytest.fixture
def ctx() -> RecordingContext:
    """A fresh recording host context."""
    return RecordingContext()
