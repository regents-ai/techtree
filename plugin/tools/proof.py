"""Checking a local proof. Specification section 7.11.

The check itself is entirely local and entirely offline. It reads stored bytes,
recomputes digests and signatures from them, and fetches nothing; no remote URL
is fetched or accepted.

A check that passes may carry Techtree's offer to publish the run, and that
offer is relayed with the answer so a host agent can put it to the person.
Relayed, not composed: the offer exists only when Techtree put it there.
"""

from __future__ import annotations

from typing import Any

from ..cli.errors import PluginError
from . import channel_of, passthrough, safe_tool, tool_result
from .arguments import require_local_path, require_run_id
from .publish import publication_offer


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
    envelope = services.bridge.invoke(["proof", "verify", target])

    # Only a run has something to publish. A bundle somebody was handed on a
    # memory stick is checkable here and is not this machine's run, and
    # Techtree offers nothing for it — so there is nothing to read and nothing
    # is invented.
    offer = publication_offer(envelope, target) if run_id else None
    if offer is None:
        return passthrough(envelope, channel)
    return tool_result({**envelope, "publication_offer": offer}, channel)
