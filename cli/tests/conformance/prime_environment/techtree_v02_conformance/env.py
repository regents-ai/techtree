"""The one-seat environment used by every v0.2 conformance path."""

from __future__ import annotations

import verifiers.v1 as vf


class SubjectEnvConfig(vf.EnvConfig):
    """One explicitly named evaluated subject."""

    subject: vf.AgentConfig = vf.AgentConfig()


class SubjectEnv(vf.Env[SubjectEnvConfig]):
    """Run the fixed task through the subject seat exactly once."""

    async def run(self, task: vf.Task, agents: vf.Agents) -> None:
        await agents.subject.run(task)
