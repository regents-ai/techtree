"""A file an agent's install fetched, held to the SHA-256 its pin names.

The check is sha256sum's own, run as the tested account. Its line (`<path>: OK`) is printed, which puts it in the
baseline's harness-install.log, and written with the digest to /work/baseline/digest.json for the baseline's manifest.
A file that does not match stops the build: Harbor raises on the failed command.
"""
import json
from pathlib import Path

from harbor.agents.installed.base import BaseInstalledAgent
from harbor.environments.base import BaseEnvironment

RECORD = Path("/work/baseline/digest.json")


async def held(agent: BaseInstalledAgent, environment: BaseEnvironment, sha256: str, path: str) -> None:
    """`path` is a shell word, read in the tested account's login shell from its home."""
    result = await agent.exec_as_agent(environment, command=f'echo "{sha256}  {path}" | sha256sum -c -')
    line = result.stdout.strip()
    print(line)
    RECORD.write_text(json.dumps({"sha256": sha256, "checked": line}))
