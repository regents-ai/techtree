"""The environment spec section 6.5 asks the reference package to ship.

The seat is a field named ``subject``, and the field name is what Verifiers
stamps onto every trace as ``agent.name``. Nothing renames a role afterwards.
"""

from __future__ import annotations

import verifiers.v1 as vf


class SubjectEnvConfig(vf.EnvConfig):
    subject: vf.AgentConfig = vf.AgentConfig()


class SubjectEnv(vf.Env[SubjectEnvConfig]):
    async def run(self, task: vf.Task, agents: vf.Agents) -> None:
        await agents.subject.run(task)
