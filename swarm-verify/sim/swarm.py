"""A seeded, deterministic run of 128 workers over one shared store of tasks and budget.

No model is called and nothing touches the network: each worker's work is the store calls the
workflow makes under its lease (claim a task, reserve a unit of the shared budget, spend it on the
paid step, commit the result), and time is a counter. A scheduler drawing from one seeded random
sequence decides which worker moves next and injects the faults:

- pause: a worker stops for a while, often for longer than its lease, then carries on where it was;
- crash: a worker holding a lease restarts with nothing, and its lease runs out later;
- lost reply: the store makes a reservation or a payment, the reply never reaches the worker, and
  the worker sends the same call again (the store answers it from the first);
- lease expiry: the store ends every lease whose time has run out;
- cancellation: a running task is closed in the store, which ends its lease and gives back its
  budget, and a cancel message goes to the worker holding it; some messages are dropped.

The store follows the three budget rules of `models/BudgetReserve.tla` (a reservation checked and
written in one step, calls keyed by lease, the budget given back when a lease ends). `fenced`
switches the commit rule of `models/TaskLease.tla`. Every step the store takes, and every crash and
lost reply the scheduler injects, is one line of the run's log, named after the model's action.
"""

from collections import Counter
from dataclasses import dataclass, field

from sim.lease import NO_RESULT, Lease, LeaseStore, Log

MASK = (1 << 64) - 1


class Random:
    """SplitMix64: the same seed gives the same run on every machine and Python version."""

    def __init__(self, seed):
        self.state = seed & MASK

    def next(self):
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
        return z ^ (z >> 31)

    def below(self, n):
        return self.next() % n

    def chance(self, per_thousand):
        return self.below(1000) < per_thousand

    def shuffle(self, items):
        for i in range(len(items) - 1, 0, -1):
            j = self.below(i + 1)
            items[i], items[j] = items[j], items[i]


@dataclass(frozen=True)
class Settings:
    """The fleet, its store and its faults. Chances are per thousand."""

    workers: int = 128
    tasks: int = 128
    max_epoch: int = 4  # attempts per task: the model's MaxEpoch
    limit: int = 128  # units of the shared budget; each lease's paid step costs one
    ttl: int = 6  # ticks a lease lasts
    pause: int = 40  # chance, at each step of a worker holding a lease, that it pauses
    longest_pause: int = 18  # ticks
    crash: int = 8  # chance, at each step of a worker holding a lease, that it crashes
    lost_reply: int = 60  # chance that the reply to a budget call is lost
    cancel: int = 150  # chance, each tick, that one running task is canceled
    dropped_cancel: int = 500  # chance that the cancel message never arrives


@dataclass
class Outcome:
    """What a run did: its log, its counts, and each late commit the store accepted, as the
    log line it is on and its task."""

    log: Log
    tally: Counter = field(default_factory=Counter)
    late_accepted: list = field(default_factory=list)


class SwarmStore(LeaseStore):
    """The lease store with the shared budget: res[t][e] reserved and paid[t][e] spent units."""

    def __init__(self, settings, fenced, log):
        super().__init__(range(1, settings.tasks + 1), settings.max_epoch, settings.ttl, fenced, log)
        self.limit = settings.limit
        epochs = range(1, settings.max_epoch + 1)
        self.res = {t: {e: 0 for e in epochs} for t in self.tasks}
        self.paid = {t: {e: 0 for e in epochs} for t in self.tasks}
        self.in_use = 0  # reserved plus spent, over every lease

    def task_state(self, t):
        state = super().task_state(t)
        state["res"] = {str(t): {str(e): n for e, n in self.res[t].items()}, "...": 0}
        state["paid"] = {str(t): {str(e): n for e, n in self.paid[t].items()}, "...": 0}
        return state

    def give_back(self, t, e):
        self.in_use -= self.res[t][e]
        self.res[t][e] = 0

    def expire(self, t, why):
        self.give_back(t, self.epoch[t])
        super().expire(t, why)

    def commit(self, agent, lease):
        if self.accepts(lease):
            self.give_back(lease.task, lease.epoch)
        return super().commit(agent, lease)

    def release(self, agent, lease):
        self.give_back(lease.task, lease.epoch)
        super().release(agent, lease)

    def cancel(self, t):
        """Closes a running task: no one may claim it again, and its lease ends now."""
        self.closed.add(t)
        self.expire(t, "canceled")

    def reserve(self, agent, lease):
        """One unit for the lease: "granted" (new, or the one it already holds), "no room", or
        "refused" when the lease has ended. Only a granted call is a step of the store."""
        t, e = lease.task, lease.epoch
        if not self.is_current(lease):
            return "refused"
        if self.res[t][e] == 0:
            if self.in_use >= self.limit:
                return "no room"
            self.res[t][e] = 1
            self.in_use += 1
        self.log.step("Reserve", [agent], t, self.task_state(t))
        return "granted"

    def spend(self, agent, lease):
        """The paid step against the lease's reservation: "paid" (now, or the earlier receipt),
        or "refused" when the lease has ended."""
        t, e = lease.task, lease.epoch
        if not self.is_current(lease):
            return "refused"
        if self.paid[t][e] == 0:
            self.res[t][e] -= 1
            self.paid[t][e] += 1
        self.log.step("Spend", [agent], t, self.task_state(t))
        return "paid"

    def finished(self, t):
        return (
            self.result[t] != NO_RESULT
            or t in self.closed
            or (self.epoch[t] == self.max_epoch and not self.live[t])
        )


class Worker:
    def __init__(self, agent):
        self.agent = agent
        self.lease = None
        self.stage = "idle"  # then "claimed", "reserved", "paid", as in the model
        self.awake_at = 0
        self.told_to_stop = False

    def drop(self):
        self.lease = None
        self.stage = "idle"
        self.told_to_stop = False

    def maybe_lose_reply(self, store, rng, settings, outcome):
        """The injected fault: the store took the call, the reply never arrives, and the worker
        goes back a stage to send the same call again. The scheduler records it in the log."""
        if rng.chance(settings.lost_reply):
            store.log.step("LoseReply", [self.agent], self.lease.task, {})
            outcome.tally["lost replies"] += 1
            self.stage = "claimed" if self.stage == "reserved" else "reserved"

    def step(self, store, rng, settings, outcome):
        """One store call: the next one the workflow makes under this worker's lease."""
        if self.stage == "idle":
            self.lease = store.claim(self.agent)
            if self.lease is not None:
                self.stage = "claimed"
                outcome.tally["takeovers"] += self.lease.epoch > 1
        elif self.told_to_stop:
            store.release(self.agent, self.lease)
            outcome.tally["stopped by a cancel message"] += 1
            self.drop()
        elif self.stage == "claimed":
            answer = store.reserve(self.agent, self.lease)
            if answer == "granted":
                self.stage = "reserved"
                self.maybe_lose_reply(store, rng, settings, outcome)
            elif answer == "no room":
                outcome.tally["reserve calls with no room"] += 1
            else:
                store.release(self.agent, self.lease)
                outcome.tally["stopped by a refused call"] += 1
                self.drop()
        elif self.stage == "reserved":
            if store.spend(self.agent, self.lease) == "paid":
                self.stage = "paid"
                self.maybe_lose_reply(store, rng, settings, outcome)
            else:
                store.release(self.agent, self.lease)
                outcome.tally["stopped by a refused call"] += 1
                self.drop()
        else:
            late = not store.is_current(self.lease)
            if store.commit(self.agent, self.lease):
                if late:
                    outcome.late_accepted.append((len(store.log.lines), self.lease.task))
            else:
                outcome.tally["late commits refused"] += 1
            self.drop()


def run(settings, seed, fenced):
    """Runs the fleet until every task is finished and no worker holds a lease."""
    rng = Random(seed)
    outcome = Outcome(Log())
    tally = outcome.tally
    store = SwarmStore(settings, fenced, outcome.log)
    workers = [Worker(a) for a in range(1, settings.workers + 1)]
    while not all(store.finished(t) for t in store.tasks) or any(w.lease for w in workers):
        store.advance(1)
        tally["ticks"] += 1
        running = [t for t in store.tasks if store.live[t]]
        if running and rng.chance(settings.cancel):
            t = running[rng.below(len(running))]
            holder = next((w for w in workers if w.lease == Lease(t, store.epoch[t])), None)
            store.cancel(t)
            tally["cancels"] += 1
            if holder is not None:
                if rng.chance(settings.dropped_cancel):
                    tally["cancel messages dropped"] += 1
                else:
                    holder.told_to_stop = True
        order = list(workers)
        rng.shuffle(order)
        for w in order:
            if w.awake_at > store.now:
                continue
            if w.lease is not None and rng.chance(settings.crash):
                outcome.log.step("Crash", [w.agent], w.lease.task, {})
                tally["crashes"] += 1
                w.drop()
                w.awake_at = store.now + 1 + rng.below(settings.longest_pause)
            elif w.lease is not None and rng.chance(settings.pause):
                ticks = 1 + rng.below(settings.longest_pause)
                tally["pauses"] += 1
                past = store.is_current(w.lease) and store.now + ticks >= store.expires[w.lease.task]
                tally["pauses past the lease"] += past
                w.awake_at = store.now + ticks
            else:
                w.step(store, rng, settings, outcome)
    tally["late commits accepted"] = len(outcome.late_accepted)
    tally["tasks committed"] = sum(store.result[t] != NO_RESULT for t in store.tasks)
    tally["tasks canceled"] = len(store.closed)
    tally["units spent"] = sum(sum(store.paid[t].values()) for t in store.tasks)
    tally["units still reserved"] = sum(sum(store.res[t].values()) for t in store.tasks)
    tally["log lines"] = len(outcome.log.lines)
    return outcome
