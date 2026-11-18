# Swarm Verify

Models, in TLA+, of how a fleet of agents shares work through one store: who owns a
task, how a shared budget is spent, and how cancellation reaches every agent. Each
model is checked by machine with [Matt Carey's Everystate](https://github.com/mattzcarey/everystate)
and cross-checked with [TLC](https://github.com/tlaplus/tlaplus), the TLA+ model
checker. A small reference implementation and a seeded run of 128 workers write logs
of what they did, and Everystate checks each log against the models.

These are models of a design, not of any one fleet's code. They say which rules keep
a fleet's work and budget right, and show the run that breaks each rule when it is
left out. Tying them to a real fleet means recording that fleet's runs in the same
log format and checking them the same way.

Every number below was measured on Everystate 0.4.0 (npm, the newest release on 18
November 2026) and TLC 2.19 (tla2tools.jar 1.7.4) on Java 21, on a 16-core Mac with
48 GB of memory.

## Models

### TaskLease

`models/TaskLease.tla`. Agents claim tasks from one shared queue and hold each under a
lease. The queue numbers each task's leases (1, 2, 3, ...). A lease can expire at any
moment while it is out, which is how the model lets an agent pause (a long garbage
collection, a lost network, a slow tool call) for longer than its lease. Another agent
may then claim the task under the next lease. The paused agent is not told, and may
come back and commit its result.

- Unsafe (`Fenced = FALSE`): the store accepts every commit.
- Repaired (`Fenced = TRUE`): every commit names the lease it was made under, and the
  store accepts it only when that lease is the task's newest and has not ended,
  checked in the same step that writes the result.

What must hold:

- `OneOwnerPerEpoch`: no two agents hold the same lease.
- `NoStaleOverwrite`: a stored result is never replaced by one from an older lease.
- `ResultFromCurrentLease`: a stored result comes from the task's newest lease.

### BudgetReserve

`models/BudgetReserve.tla`. The same leases with the repaired commit, and a shared
budget of `Limit` units. Each lease's work costs one unit: the agent reserves it, spends
it on the paid step of the work (a model call, an email), commits, and gives back what
is left. The reply to any budget call can be lost, and the agent then sends the same
call again. Agents can pause or crash between any two steps. Three rules, each a
constant that is `TRUE` in the repaired design:

- `AtomicAdmit`: the budget is checked and the reservation written in one step.
  Unsafe: check, then reserve, in two steps.
- `Idempotent`: each call is keyed by its lease, so a repeated reserve returns the
  reservation the lease already holds and a repeated spend returns the earlier
  receipt. Unsafe: every call is new.
- `ReleaseOnExpiry`: the step that ends a lease also gives back its reservation.
  Unsafe: only the agent that made it can give it back.

What must hold:

- `WithinLimit`: reserved plus spent never passes the limit.
- `OnePerLease`: a lease holds at most one reservation and pays at most once.
- `NoReservationOutlivesLease`: no reservation is left on a lease that has ended.
- `LeaseSafe`: the three TaskLease properties still hold with the budget steps added.
- `EveryReservationEnds` (liveness): every reservation is eventually spent or given
  back, given that a lease left out eventually expires.

### Cancel

`models/Cancel.tla`. A parent task has child agents, each holding a lease and its share
of the budget while it runs. The parent cancels at any moment: the store records the
cancellation and a cancel message goes to every child. A message can be lost.

- Unsafe (`StoreCheck = FALSE`): a child stops only when its message arrives.
- Repaired (`StoreCheck = TRUE`): every step of a child's work, its heartbeat included,
  is a call to the store, which refuses it once the cancellation is recorded; a refused
  child stops and gives back what it holds, whether or not its message arrived.

What must hold:

- `NoWorkAfterCancel`: no child does work after the cancellation is recorded.
- `CancelStopsEveryChild` (liveness): after a cancellation every child eventually
  stops, given that a message not lost is eventually delivered.

## Results

Each configuration in `models/` states its bounds and the result it must give, and
`make check-swarm` fails when any gives another. "Leases" is leases per task. Times are
wall-clock seconds on one thread, from one run (they vary from run to run); TLC's
include about 0.6 s of Java start-up. "Same" means TLC gave the same outcome, the same
broken invariant, and exactly the same counts of generated and distinct states.

| Configuration | Design | Bounds | Outcome | Distinct states | Generated | Everystate | TLC | Same |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `TaskLease` | fenced | 3 agents, 3 tasks, 3 leases | holds | 283,204 | 2,240,443 | 1.34 | 4.41 | yes |
| `TaskLeaseUnfenced` | unfenced | 3 agents, 3 tasks, 3 leases | `NoStaleOverwrite` broken | 1,041 | 2,886 | 0.04 | 0.65 | yes |
| `TaskLeaseUnfencedCurrent` | unfenced | 3 agents, 3 tasks, 3 leases | `ResultFromCurrentLease` broken | 321 | 744 | 0.03 | 0.64 | yes |
| `BudgetReserve` | all three rules | 3 agents, 2 tasks, 2 leases, limit 1 | holds, liveness too | 14,781 | 102,871 | 0.27 | 2.54 | yes |
| `BudgetReserveLimit2` | all three rules | 3 agents, 2 tasks, 2 leases, limit 2 | holds, liveness too | 53,325 | 401,505 | 0.90 | 8.08 | yes |
| `BudgetReserveCheckThenReserve` | check, then reserve | 3 agents, 2 tasks, 2 leases, limit 1 | `WithinLimit` broken | 789 | 2,108 | 0.05 | 0.71 | yes |
| `BudgetReserveRetryTwice` | calls not keyed | 3 agents, 2 tasks, 2 leases, limit 2 | `OnePerLease` broken | 166 | 318 | 0.03 | 0.66 | yes |
| `BudgetReserveLeak` | no release on expiry | 3 agents, 2 tasks, 2 leases, limit 1 | `NoReservationOutlivesLease` broken | 46 | 68 | 0.04 | 0.64 | yes |
| `BudgetReserveLeakLiveness` | no release on expiry | 3 agents, 2 tasks, 2 leases, limit 1 | `EveryReservationEnds` broken | 9,625 | 58,029 | 0.12 | 1.63 | yes |
| `Cancel` | store check | 3 children | holds, liveness too | 217 | 869 | 0.03 | 0.64 | yes |
| `CancelMessageOnly` | message only | 3 children | `CancelStopsEveryChild` broken | 513 | 2,309 | 0.03 | 0.66 | yes |
| `CancelMessageOnlyLate` | message only | 3 children | `NoWorkAfterCancel` broken | 5 | 8 | 0.03 | 0.61 | yes |

A broken configuration stops at its first counterexample, so its counts are of the
states searched until then; both checkers search breadth first and stopped after the
same counts. For a broken liveness property, TLC's counterexample can be a different
run from Everystate's.

The counterexamples, in words:

- **Late commit** (`TaskLeaseUnfenced`, 5 steps). Agent 1 claims task 1 under lease 1.
  Agent 1 pauses and lease 1 expires. Another agent claims task 1 under lease 2, does
  the work and commits; the store holds its result. Agent 1 comes back, still believing
  it holds lease 1, and commits: the store accepts it and the newer result is
  overwritten by the older one. `TaskLeaseUnfencedCurrent` is the shorter version
  (4 steps): agent 1's late commit lands while the other agent still holds lease 2,
  before it commits.
- **Check, then reserve** (6 steps). Two agents each claim a task, both check the budget
  and see room for one unit, then both reserve it: two units against a limit of one.
- **Retry reserves twice** (4 steps). An agent reserves a unit, the reply is lost, and
  it sends the same call again: its lease now holds two reservations.
- **Leak** (3 steps). An agent reserves a unit and its lease expires: the reservation is
  still there on a lease that has ended. In `BudgetReserveLeakLiveness` the agent then
  crashes, and no one ever gives the unit back.
- **Lost cancel** (`CancelMessageOnly`). The parent cancels, two children get their
  message and stop, the third child's message is lost, and it works on forever.
  `CancelMessageOnlyLate` is the 2-step version: a child works after the cancellation is
  recorded, before its message arrives.

## Logs

A log is JSON Lines, one line per step the store took, in Everystate's
[conformance format](https://github.com/mattzcarey/everystate/blob/main/CONFORMANCE.md):
the model's action, its arguments, and the values the step changed. `everystate
conform` checks that the recorded run is a behavior of the model and names the first
line that is not.

### Reference implementation

`sim/lease.py` is the TaskLease store, in plain Python with no dependencies, with the
commit rule switched by `fenced`. `sim/late_commit.py` runs it with the injected fault:
two workers, one task, a lease of 3 ticks; worker 1 claims and pauses for 5 ticks,
worker 2 claims under the next lease and commits, then worker 1 commits late. Its two
logs are kept in `conformance/`, and the check fails when the code no longer writes
them byte for byte.

| Log | Model | Everystate says |
| --- | --- | --- |
| `late-commit-unfenced.jsonl` | `TaskLease`, fenced (`TaskLeaseRun.cfg`) | exit 20, does not conform: "line 6 (observation 6 of 6) cannot be matched ... Commit cannot happen here: the spec does not allow it in the state the trace has reached." The closest steps it allows are `Reject(1)`, `Release(1)` and `Crash(1)`, all of which keep agent 2's result. |
| `late-commit-fenced.jsonl` | `TaskLease`, fenced | exit 0: "Trace conforms: 6 observations matched." |
| `late-commit-unfenced.jsonl` | `TaskLease`, unfenced (`TaskLeaseRunUnfenced.cfg`) | exit 12: the run is one the unfenced model allows, and `NoStaleOverwrite` is broken at line 6. |

### 128 workers

`sim/swarm.py` runs 128 workers over 128 tasks and a shared budget of 128 units, in
one process and one seeded random sequence, so a seed gives the same run on every
machine (the check runs it twice and compares). Time is a counter, leases last 6
ticks, and each task has at most 4 leases. The store follows all three budget rules;
`fenced` switches the commit rule. The scheduler injects:

- pauses, often longer than the lease, after which the worker carries on where it was;
- crashes of workers holding a lease (the lease runs out later);
- lost replies to budget calls, after which the worker sends the same call again;
- cancellation of a running task: the store closes the task, ends its lease and gives
  back its budget, and a message goes to the worker holding it; each message has an
  even chance of being dropped, and then the worker learns from its next call, which
  the store refuses.

Seed 1, fenced: 620 log lines over 29 ticks, with 22 takeovers, 13 pauses past the
lease, 6 crashes, 16 lost replies, 27 reserve calls refused for lack of room and 5
cancellations (1 message dropped). The store refused 4 late commits; 123 tasks were
committed, 5 canceled, all 128 units spent and none left reserved. Unfenced: 617
lines, and the store accepted 4 late commits, on tasks 97, 91, 88 and 28.

Each log is checked against `BudgetReserve` at the run's own bounds (128 agents, 128
tasks, 4 leases, limit 128), two ways:

| Run | Checked | Result | Seconds | Peak memory |
| --- | --- | --- | ---: | ---: |
| fenced | the whole log | conforms | 9.2 | 191 MB |
| fenced | each task's own log, 128 checks side by side | all 128 conform | 0.5 | |
| unfenced | each task's own log | 124 conform; tasks 28, 88, 91 and 97 do not, each at its late commit | 2.8 | |
| unfenced | the whole log (in `check.sh measure`) | does not conform at line 547, the first accepted late commit | 57.3 | 191 MB |

A task's own log is its lines alone, renamed task 1, checked against the same model
with one task and 128 agents. That checks each task's leases and budget, not the
shared limit across tasks, which only the whole-log check covers.

## Limits

Measured with `swarm-verify/check.sh measure`.

**Model checking** grows fast with the bounds. TaskLease, fenced, on one thread:

| Agents | Tasks | Leases | Distinct states | Seconds | Peak memory |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 3 | 2 | 3 | 7,498 | 0.2 | 54 MB |
| 3 | 3 | 3 | 283,204 | 1.4 | 134 MB |
| 4 | 2 | 3 | 28,945 | 0.2 | 54 MB |
| 4 | 3 | 3 | 1,814,239 | 11.3 | 828 MB |
| 4 | 3 | 4 | 11,567,593 | 72.8 | 5,231 MB |

About 480 bytes per state. One more agent multiplied the states by about 4 to 6, one
more task by about 40 to 60, and one more lease per task by about 6, so on this Mac 4
agents and 3 tasks with 4 leases each is near the end of what is practical. Model
checking says nothing directly about 128 agents.

**Checking a log** is practical at fleet size. Fenced runs, seed 1:

| Workers | Tasks | Log lines | Whole log | Seconds | Peak memory | Each task's log | Seconds | Store lines only, `-hidden 1` | Seconds |
| ---: | ---: | ---: | --- | ---: | ---: | --- | ---: | --- | ---: |
| 128 | 64 | 332 | conforms | 2.4 | 95 MB | 64 of 64 conform | 0.3 | 64 of 64 | 1.4 |
| 128 | 128 | 620 | conforms | 9.3 | 191 MB | 128 of 128 | 0.6 | 128 of 128 | 1.3 |
| 128 | 256 | 1,291 | conforms | 38.4 | 477 MB | 256 of 256 | 1.0 | 256 of 256 | 2.4 |
| 128 | 512 | 2,538 | conforms | 196.8 | 1,432 MB | 512 of 512 | 2.2 | 512 of 512 | 5.0 |
| 256 | 128 | 589 | conforms | 21.1 | 477 MB | 128 of 128 | 0.8 | 128 of 128 | 2.7 |
| 512 | 128 | 687 | conforms | 63.5 | 1,433 MB | 128 of 128 | 2.9 | 128 of 128 | 23.6 |
| 512 | 512 | 2,650 | not run | | | 512 of 512 | 9.4 | 512 of 512 | 66.5 |

- The whole log grows with the number of lines times the size of the fleet: each line
  is matched in a state holding every task and every agent. Doubling both tasks and
  lines took about four times as long. It stays practical to a few hundred tasks and
  workers; at 512 tasks it takes over three minutes.
- Each task's own log stays cheap at every size measured, 512 workers on 512 tasks
  included, because each check holds one task. The 128 to 512 checks run side by side
  on 16 cores.
- Reporting a mismatch costs far more than finding one at this size. The unfenced
  128-task log conforms up to line 546 in 8.6 s, and the check that stops at line 547
  takes 57.3 s. The extra time comes after the mismatch is found; the report lists
  the 101 steps the model allows at that point.
- "Store lines only" drops the lines the scheduler writes (crashes and lost replies),
  as a fleet would log only its store's steps, and lets Everystate assume up to one
  unrecorded step before each line (`-hidden 1`). Each task's own log still conforms.
  The whole log does not get that far: with 128 agents, any of them may have taken the
  unrecorded step, and Everystate stops without a verdict (exit 22, more than 100,000
  candidate states) at line 2 for 8 and 16 tasks. A one-off run at 128 tasks gave no
  verdict in over 10 minutes and was stopped.

## Assumptions

- The store is one service and each of its steps is one indivisible transaction. The
  reference implementation gets this by running in one thread; a real store gets it
  from its database.
- A lease can expire at any moment while it is out. Real clocks, lease lengths and
  clock skew are not modeled; letting expiry happen at any time covers every timing.
- A lost reply loses only the reply: the store took the call. Lost replies are modeled
  on budget calls; a commit's reply is not lost.
- Each lease's work costs exactly one unit.
- A crash loses everything the agent knew; the store keeps its lease until it expires.
- Cancel is a separate, smaller model: "running" stands for holding a lease and budget.
  In the 128-worker run a cancellation is recorded as `Expire` with `"why":
  "canceled"`, and the store never offers the task again; the model allows offering it
  again and does not require it.
- Liveness rests on fairness: a lease left out eventually expires, a message not lost
  is eventually delivered, and a child able to stop eventually does.

## Not established

- **Nothing here is a proof about 128 agents.** Model checking covers every behavior,
  but only at the bounds stated: three agents and up to three tasks in the gate, four
  agents and three tasks at most in the measured limits. The 128-worker checks say that
  the runs recorded (seed 1, at the sizes above) are behaviors of the model, and nothing
  about runs not recorded.
- The paid step runs at most once per lease, not once per task. When a lease expires
  after its paid step and another agent takes the task over, the paid step runs again
  under the new lease. Whether an outside service treats a repeated call as one depends
  on that service.
- No property says every task is eventually finished.
- The Cancel model is not combined with the budget model, and the 128-worker run uses
  only the repaired design (a canceled task's calls are refused by the store).
- Each task's own log checks that task's leases and budget, not the shared limit across
  tasks.
- The models describe a design. No real fleet, queue or database has been checked; the
  reference implementation is a stand-in.
- Conformance has one checker. TLC cross-checks the model checking, not the logs.
- Everystate 0.4.0, the release that added `conform`, was published on 18 November
  2026, the day these numbers were measured.

## Writing a model a log can be checked against

A first draft of `BudgetReserve` let the model decide inside a step whether a reply was
lost, a choice no log line shows. Checking a whole 128-worker log against it stopped
without a verdict at line 49 of 154: each such choice multiplied the states consistent
with the log, and by then there were more than Everystate's limit of 100,000. Making the
lost reply its own action (`LoseReply`), written to the log by the code that injects
it, left one candidate state at every line. A model a log is checked against should
make every choice a step of its own that the log records.

## Rerun

From the repository root:

```sh
make check-swarm            # Everystate: every model, the two late-commit logs, the 128-worker run; about 20 s
make swarm-tlc              # also every model with TLC, compared with Everystate; needs Java 17 or later on PATH
swarm-verify/check.sh measure   # the limits above; about 10 minutes and over 5 GB of memory
swarm-verify/check.sh fixtures  # rewrites conformance/*.jsonl after a change to sim/lease.py
```

`make check` runs `check-swarm`. `swarm-verify/check.sh` installs the pinned
Everystate (`everystate@0.4.0`, MIT) into `swarm-verify/node_modules` with `npm ci`
from `swarm-verify/package-lock.json`, then runs `swarm-verify/check.py` with `uv`;
the Python has no dependencies. `make swarm-tlc` downloads `tla2tools.jar` 1.7.4
(TLC 2.19, MIT) from the TLA+ project's GitHub release into `swarm-verify/_build/` and
checks its SHA-256 before using it. Each run's logs and generated configurations are in
`swarm-verify/_build/`.
