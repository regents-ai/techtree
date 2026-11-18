"""The task-lease protocol: one shared store that grants leases on tasks and keeps results.

This is the reference implementation that `models/TaskLease.tla` describes. Every method that
changes the store is one indivisible step (in a real system, one database transaction) and
writes one line to the run's log, named after the model's action, with the values it changed.

With `fenced=False` the store accepts every commit. With `fenced=True` a commit names the lease
it was made under, and the store accepts it only when that lease is the task's newest and has
not ended.
"""

import json
from dataclasses import dataclass

NO_RESULT = {"agent": 0, "epoch": 0}


@dataclass(frozen=True)
class Lease:
    task: int
    epoch: int


class Log:
    """The run's log: one observation per step, in the order the store took them."""

    def __init__(self):
        self.lines = []

    def step(self, action, params, task, state, **extra):
        """A step of the model's `action`; `task` names the task it touched (ignored by the
        model, read when the log is split by task)."""
        self.lines.append({"action": action, "params": params, "state": state, "task": task, **extra})

    def text(self):
        return "".join(json.dumps(line, separators=(",", ":")) + "\n" for line in self.lines)


class LeaseStore:
    def __init__(self, tasks, max_epoch, ttl, fenced, log):
        self.tasks = list(tasks)
        self.max_epoch = max_epoch
        self.ttl = ttl
        self.fenced = fenced
        self.log = log
        self.now = 0
        self.epoch = {t: 0 for t in self.tasks}
        self.live = {t: False for t in self.tasks}
        self.expires = {t: 0 for t in self.tasks}
        self.result = {t: NO_RESULT for t in self.tasks}
        self.closed = set()  # tasks no longer offered: canceled

    # What a log line shows of task t after a step.
    def task_state(self, t):
        return {
            "epoch": {str(t): self.epoch[t], "...": 0},
            "live": {str(t): self.live[t], "...": 0},
            "result": {str(t): self.result[t], "...": 0},
        }

    def initial_state(self):
        return {
            "epoch": {str(t): 0 for t in self.tasks},
            "live": {str(t): False for t in self.tasks},
            "result": {str(t): NO_RESULT for t in self.tasks},
        }

    def claimable(self, t):
        return (
            t not in self.closed
            and self.result[t] == NO_RESULT
            and not self.live[t]
            and self.epoch[t] < self.max_epoch
        )

    def is_current(self, lease):
        return self.epoch[lease.task] == lease.epoch and self.live[lease.task]

    def claim(self, agent):
        """Grants agent the first task it can take, under the task's next lease, or None."""
        t = next((t for t in self.tasks if self.claimable(t)), None)
        if t is None:
            return None
        self.epoch[t] += 1
        self.live[t] = True
        self.expires[t] = self.now + self.ttl
        self.log.step("Claim", [agent, t], t, self.task_state(t))
        return Lease(t, self.epoch[t])

    def advance(self, ticks):
        """Moves the clock on and expires every lease whose time has run out."""
        self.now += ticks
        for t in self.tasks:
            if self.live[t] and self.expires[t] <= self.now:
                self.expire(t, "lease ran out")

    def expire(self, t, why):
        self.live[t] = False
        self.log.step("Expire", [t], t, self.task_state(t), why=why)

    def accepts(self, lease):
        return not self.fenced or self.is_current(lease)

    def commit(self, agent, lease):
        """Stores agent's result for its lease's task. Returns whether the store accepted it."""
        t = lease.task
        if not self.accepts(lease):
            self.log.step("Reject", [agent], t, self.task_state(t))
            return False
        self.result[t] = {"agent": agent, "epoch": lease.epoch}
        if lease.epoch == self.epoch[t]:
            self.live[t] = False
        self.log.step("Commit", [agent], t, self.task_state(t))
        return True

    def release(self, agent, lease):
        """Agent gives its lease back without a result."""
        t = lease.task
        if lease.epoch == self.epoch[t]:
            self.live[t] = False
        self.log.step("Release", [agent], t, self.task_state(t))
