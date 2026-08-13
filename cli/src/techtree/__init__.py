"""Supported public Python import surface for Techtree.

Spec section 10.1. This module performs no filesystem access, no settings
loading, no CLI registration, and no resource extraction.

The protocol model exports defined by spec section 10.1 are added when the
protocol core lands; only the version surface exists today.
"""

from __future__ import annotations

from techtree.version import __version__

__all__ = ["__version__"]
