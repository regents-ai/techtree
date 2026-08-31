"""Shared pytest fixtures. Spec section 27.1.

No test writes to the real user home. Every fixture that needs Techtree state
derives it from ``temp_techtree_home``.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def temp_techtree_home(tmp_path: Path) -> Path:
    """Return an isolated Techtree home directory for a single test."""
    home = tmp_path / "techtree-home"
    home.mkdir()
    return home
