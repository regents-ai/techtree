"""A file an agent's install fetched, held to the SHA-256 its pin names.

The check is sha256sum's own, run as the tested account. Its line (`<path>: OK`) is printed, which puts it in the
baseline's harness-install.log, and written with the digest to /work/baseline/digest.json for the baseline's manifest.
A file that does not match stops the build: Harbor raises on the failed command. So does a pin that is not a SHA-256,
or an answer that is not sha256sum's OK: what sha256sum does with a line it cannot read differs between systems.
"""
import json
import re
from pathlib import Path

from harbor.agents.installed.base import BaseInstalledAgent
from harbor.environments.base import BaseEnvironment

RECORD = Path("/work/baseline/digest.json")


async def held(agent: BaseInstalledAgent, environment: BaseEnvironment, sha256: str, path: str) -> None:
    """`path` is a shell word, read in the tested account's login shell from its home."""
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise RuntimeError(f"the pin's SHA-256 is not 64 hex characters: {sha256!r}")
    result = await agent.exec_as_agent(environment, command=f'echo "{sha256}  {path}" | sha256sum -c -')
    line = result.stdout.strip()
    if not line.endswith(": OK"):
        raise RuntimeError(f"sha256sum did not answer OK for {path}: {line!r}")
    print(line)
    RECORD.write_text(json.dumps({"sha256": sha256, "checked": line}))
