"""Checking a local proof. Specification section 7.11.

Entirely local and entirely offline: nothing is uploaded, and no remote URL is
fetched or accepted.
"""

from __future__ import annotations

from typing import Any

from ..errors import PluginError
from . import channel_of, passthrough, safe_tool
from .arguments import require_local_path, require_run_id


@safe_tool
def techtree_proof_verify(services: Any, args: dict[str, Any], **kwargs: Any) -> str:
    """Verify a run's stored proof, or one the user pointed at."""
    channel = channel_of(args, kwargs)
    run_id = args.get("run_id")
    proof_path = args.get("proof_path")

    if bool(run_id) == bool(proof_path):
        raise PluginError(
            "give either a run identifier or a proof path the user named, "
            "not both and not neither",
            code="tool_argument_invalid",
        )

    target = (
        require_run_id(str(run_id).strip())
        if run_id
        else require_local_path(str(proof_path), "proof_path")
    )
    return passthrough(services.bridge.invoke(["proof", "verify", target]), channel)
