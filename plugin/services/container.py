"""The dependency container built during registration. Section 7.10."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..constants import PLUGIN_ROOT
from ..models import ReleaseCore
from ..release import load_embedded_release_core, release_core_digest


@dataclass(frozen=True)
class PluginServices:
    """Everything the tool, command, and hook layers are allowed to reach.

    The container is immutable and holds no client, socket, or subprocess. It
    is assembled from bytes that shipped inside the plugin, which is what
    keeps registration free of side effects.
    """

    ctx: Any
    root: Path
    release_core: ReleaseCore
    release_core_digest: str


def build_services(ctx: Any, *, root: Path = PLUGIN_ROOT) -> PluginServices:
    """Construct one immutable service container during registration.

    Reads the embedded release bytes and verifies them. Raises ``PluginError``
    when they are missing or invalid, so a plugin built wrong fails at load
    with a clear reason rather than halfway through an operator's demo.
    """
    release_core = load_embedded_release_core(root)
    return PluginServices(
        ctx=ctx,
        root=root,
        release_core=release_core,
        release_core_digest=release_core_digest(release_core),
    )
