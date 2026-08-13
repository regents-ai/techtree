"""Collect the plugin package directory without importing it."""

from __future__ import annotations

from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def pytest_collect_directory(
    path: Path, parent: pytest.Collector
) -> pytest.Collector | None:
    if path == REPOSITORY_ROOT:
        return pytest.Dir.from_parent(parent, path=path)
    return None
