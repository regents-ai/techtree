"""The environment that gives the evaluated role its real name. Spec 6.5.

Verifiers' default ``SingleAgentEnv`` seats its one agent in a field called
``agent``, and the field name is what every trace records as ``agent.name``.
Techtree's scientific model calls the evaluated role ``subject``, and receipts
group traces by declared role, so the choice is between renaming a recorded
role afterwards for presentation and making the role real where it is
recorded. Renaming after the fact would mean a receipt describing something the
raw evidence never said. This environment makes it real instead: the seat is a
field named ``subject``, so every trace this package produces records
``agent.name == "subject"`` and no trace anywhere records ``agent``.

That the package can export a Taskset and an Env together is not a trick.
Verifiers resolves plugins by requested base type, so the taskset loader sees
exactly one Taskset and the environment loader sees exactly one Env. The
behaviour was proven against the pinned commit before this file was written;
``docs/verifiers-eval.md`` records it.

The environment does one thing and holds no policy. Everything about how the
subject is configured — model, harness, runtime, skills — arrives through the
compiled configuration, because a knob here would be a second place an
experiment could differ.
"""

from __future__ import annotations

import verifiers.v1 as vf

__all__ = ["ProcedureTransferEnv", "ProcedureTransferEnvConfig"]


class ProcedureTransferEnvConfig(vf.EnvConfig):
    """The one seat, named for the role it plays."""

    subject: vf.AgentConfig = vf.AgentConfig()


class ProcedureTransferEnv(vf.Env[ProcedureTransferEnvConfig]):
    """One episode is the subject attempting one task."""

    async def run(self, task: vf.Task, agents: vf.Agents) -> None:
        """Play one task through the subject seat.

        Args:
            task: The task this episode is seeded from.
            agents: The episode's agents, addressed by seat name.
        """
        await agents.subject.run(task)
