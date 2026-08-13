# Run state machine

Spec sections §9.10, §11.12, §18.1–§18.3, §19, §28. Decisions 0001, 0002, 0003.

A run is executed by a detached worker process and watched by a CLI process
that comes and goes. The two never share memory, so a run's history on disk is
the only thing they can both trust. Every fact about a run is appended to
`events.jsonl` first and only then projected into `state.json`.

**The log is the truth. The projection is a cache.** Any disagreement between
them is resolved in favour of the log, always, by recomputing.

Implemented by `src/techtree/runs/events.py` (bytes),
`src/techtree/runs/machine.py` (meaning), and `src/techtree/runs/store.py`
(placement and mutual exclusion).

---

## 1. Phases

`RunPhase` (`models/run.py`). The names are part of the CLI's machine-facing
contract; they are not display strings and are never translated.

| Phase | Meaning |
| --- | --- |
| `created` | The run exists and its request is fixed. No worker has started. |
| `validating_taskset` | Resolving the taskset and checking it against the Campaign's membership commitment. |
| `running_baseline` | Producing baseline episodes. |
| `running_candidate` | Producing candidate episodes. |
| `running_variants` | Producing both sides' episodes at once. |
| `building_receipts` | Persisting `EpisodeReceipt` objects for both sides. |
| `verifying_comparison` | Checking that the candidate differs from the baseline only where the Campaign permits. |
| `building_report` | Building and persisting the `UpliftReport`. |
| `completed` | The run finished and produced a result. |
| `failed` | The run stopped because something went wrong. |
| `cancel_requested` | Someone asked the run to stop; the worker has not finished winding down. |
| `cancelled` | The run stopped because it was asked to. |

## 2. Transitions

The normal path is a straight line:

```text
created
→ validating_taskset
→ running_baseline
→ running_candidate
→ building_receipts
→ verifying_comparison
→ building_report
→ completed
```

One branch leaves it and comes back. A Campaign whose `execution.order` is
`parallel_variants` runs both sides at once, so it takes `running_variants`
instead of the sequential pair and rejoins the line at `building_receipts`:

```text
validating_taskset
→ running_variants
→ building_receipts
```

The sequential phases stay exactly as they were (spec §3.3): the fake executor
walks them, and a run takes one route or the other and never both.

Two escapes leave it:

- **Failure.** Any phase that is still working may move to `failed`.
- **Cancellation.** Any phase that is still working may move to
  `cancel_requested`, and from there to `cancelled` (wound down cleanly) or
  `failed` (broke while winding down).

`running_variants` is a working phase in both respects: it may fail and it may
be cancelled, on exactly the same terms as every other.

`cancel_requested` never rejoins the normal path. A run that was asked to stop
does not quietly complete instead.

The complete table is `ALLOWED_TRANSITIONS` in `runs/machine.py`, derived from
`NORMAL_PATH` and those two escapes and checked edge by edge — every ordered
pair of phases — in `tests/unit/test_run_machine.py`.

**No phase has an edge to itself.** A run that reports without moving is not
making a transition, and the table does not pretend otherwise.

### Events that do not change the phase

A run does have things to say while it stays where it is, and there are exactly
six of them:

| Kind | Where | What it reports |
| --- | --- | --- |
| `worker.started` | `created` | The process id of the worker that took the run on. |
| `progress.updated` | any phase doing work | Position within the current phase. |
| `result.written` | `building_report` | The digest of the report just persisted. |
| `variant.started` | `running_variants` | One side of the concurrent comparison began. |
| `variant.progress` | `running_variants` | How far one side has got. |
| `variant.completed` | `running_variants` | One side stopped, whichever way it stopped. |

`validate_same_phase_event` (`runs/machine.py`) admits those six and refuses
everything else, including a second cancellation request and any event at all
once the run has ended. `phase_progress_allowed` is the narrower rule inside it:
`created` is a run that exists rather than a run doing something, so it has no
progress to report.

Recording these as events is what keeps the projection derivable from the log.
A fact written only into `state.json` would be a fact the log could not rebuild.

### Terminal states

`completed`, `failed`, and `cancelled` have no outgoing edges at all. A
terminal run's log is closed: `validate_transition` refuses every further phase
change and `validate_same_phase_event` refuses everything else. `is_terminal`
reads this straight off the table.

`can_cancel` is "has an edge to `cancel_requested`", which is now exactly the
right answer: a run that has already been asked to stop has no such edge, so it
is not asked twice.

## 3. Event format

One event is one line of RFC 8785 canonical JSON in
`runs/<run-id>/events.jsonl`. `RunEvent` (`models/run.py`):

| Field | Meaning |
| --- | --- |
| `sequence` | Position in the log. Starts at 0 and increases by exactly 1. |
| `timestamp` | When the event was recorded, UTC. |
| `run_id` | The run this event belongs to. |
| `previous_phase` | The phase left. `null` only on the created event. |
| `phase` | The phase entered, or the phase retained. |
| `kind` | What happened. One of twelve names; see below. |
| `details` | JSON, free-form except for the keys the kind is defined to carry. |

Both `previous_phase` and `phase` are recorded so that a reader reconstructing
a run never has to infer where it came from — which matters most for
`cancel_requested`, where the phase the run was interrupted in is otherwise
lost.

### The twelve kinds

`kind` is a string in the frozen model and a closed set in the local store
(`runs/events.py`). Each name fixes the phases it may sit between and the
details it carries:

| Kind | From | To | Details |
| --- | --- | --- | --- |
| `run.created` | — (sequence 0) | `created` | `request_digest` |
| `worker.started` | `created` | `created` | `worker_pid` |
| `phase.entered` | any phase | a different phase | optional `label` |
| `progress.updated` | current phase | the same phase | `current`, `total`, `label` |
| `cancel.requested` | any working phase | `cancel_requested` | `requested_by` |
| `run.failed` | any non-terminal phase | `failed` | `error` |
| `run.cancelled` | `cancel_requested` | `cancelled` | — |
| `result.written` | `building_report` | `building_report` | `result_digest` |
| `run.completed` | `building_report` | `completed` | `result_digest` |
| `variant.started` | `running_variants` | `running_variants` | the six below |
| `variant.progress` | `running_variants` | `running_variants` | the six below |
| `variant.completed` | `running_variants` | `running_variants` | the six below |

The three `variant.*` kinds each carry the whole of `VariantProgress` —
`variant`, `completed`, `total`, `running`, `errored`, `state` — because an
event that reported only part of it would leave the projection guessing at the
rest. They are valid in `running_variants` and in no other phase, which is the
existing one-phase rule applied to three more names rather than a new rule.

`validate_event_kind` enforces the whole table and refuses an unknown name, a
kind whose phases contradict it, or a kind missing a detail it is defined to
carry. The four phases that end a run or begin ending it — `cancel_requested`,
`failed`, `cancelled`, `completed` — each belong to exactly one kind in both
directions, so no generic `phase.entered` can quietly end a run.

A malformed value under an interpreted key is a typed `ValidationError`, not a
silently ignored annotation. A run that failed without saying why leaves the
caller nothing to act on, so the error is part of the transition.

Writing is append-only: one `O_APPEND` write of one line, then `fsync`. A crash
can therefore lose a whole trailing event but can never interleave two events'
bytes. `event_digest` digests the exact bytes of the log, so a run's history has
an identity.

### Sequence discontinuity is fatal

`read_events` rejects a log whose sequence numbers do not start at 0 and
increase by exactly 1. A log that skips is a log that lost something, and a
state projected from it would be quietly wrong. The same check catches a
truncated final line, because a half-written event fails to parse before its
sequence is ever considered.

## 4. State projection

`reduce_events` folds the log into one `RunState`. It is a pure function: no
filesystem, no clock, no process table. `apply_event` applies a single event and
refuses one that names another run, arrives out of sequence, disagrees about the
phase it is leaving, or asks for a transition the table forbids.

Which fields an event touches follows from its kind, which is the point of the
kind being a closed set: a reader never has to guess whether a detail was meant
to be interpreted.

| `RunState` field | Where it comes from |
| --- | --- |
| `run_id`, `phase`, `sequence`, `updated_at` | The most recent event. |
| `worker_pid`, `worker_started_at` | `worker.started`; carried forward after that. |
| `cancel_requested_at` | The timestamp of `cancel.requested`, which a run records at most once. |
| `error` | The `error` detail of `run.failed`. |
| `progress` | The most recent `progress.updated` **within the current phase**. Entering a new phase clears it. |
| `variant_progress` | One entry per variant, each the most recent `variant.*` event that named it, **within the current phase**. Entering a new phase clears it. |
| `result_digest` | The `result_digest` detail of `result.written` or `run.completed`; carried forward. |
| `heartbeat_at` | Not from events. See below. |

The projection is written to `runs/<run-id>/state.json` and always recomputed
from the log rather than patched in place, so a stale or damaged projection
heals at the next append, heartbeat, or explicit `rebuild_state`.

`RunStore.state` reads the cache and rebuilds when it is missing or will not
parse. `RunStore.rebuild_state` always recomputes. `RunStatus` wraps the state
with the three liveness facts only the host can determine — `worker_alive`,
`heartbeat_stale`, `result_available` — and those are never stored.

## 5. Locking and file layout

```text
runs/<run-id>/
├── .lock            per-run FileLock; every writer passes through it
├── request.json     written once, canonical bytes, O_EXCL
├── events.jsonl     append-only
├── state.json       projection, atomically replaced
├── heartbeat.json   liveness, atomically replaced
├── pid              worker process id, atomically replaced
├── worker.log       worker stdout and stderr
├── taskset/         WP5 lock and validation artifacts
├── receipts/        baseline and candidate episode receipts
└── report/uplift.json   written once, canonical bytes, O_EXCL
```

Appending an event and rewriting the projection happen inside **one** lock
hold, so the two files can never disagree about which event was last. Waiting
longer than `LOCK_TIMEOUT_SECONDS` is reported as a typed `ConflictError`;
failing beats hanging.

`request.json` and `report/uplift.json` are written with `O_EXCL` in canonical
bytes, so the file's SHA-256 is the object's digest and a second write is a
conflict rather than a silent replacement of evidence.

## 6. Heartbeat semantics

The worker refreshes `heartbeat.json` every
`DEFAULT_WORKER_HEARTBEAT_SECONDS` (2) seconds through
`RunStore.write_heartbeat`, which also refreshes the projection. A heartbeat
older than `DEFAULT_STALE_HEARTBEAT_SECONDS` (15) is stale, and the CLI reports
`RunStatus.heartbeat_stale`.

The heartbeat is deliberately **not** an event. A liveness signal appended
every two seconds would bury a run's actual history under thousands of lines
that mean nothing after the fact, so it is a single overwritten file and
`reduce_events` always leaves `heartbeat_at` unset; the store merges it in.
This is the one field of `RunState` that the log alone cannot rebuild, and it
is the only one whose value stops being interesting the moment it is read.

A stale heartbeat is not itself a phase change. It says the worker stopped
reporting, not that the run failed; nothing moves a run to `failed` except an
event.

## 7. PID semantics

`RunStore.write_pid` does two things under the lock: it writes the process id
to `pid`, which is what a signal-sender reads, and it appends a
`worker.started` event carrying `worker_pid`, which is what makes the worker's
start part of the rebuildable history. `worker_started_at` is that event's
timestamp. A worker announces itself before the run starts working, so this is
a `created`-phase event and nothing else.

A recorded pid is not proof of life. `WorkerLauncher.is_alive` checks the
process, and pid reuse means the check is a strong hint rather than a
guarantee; the heartbeat is the corroborating signal.

## 8. Cancellation semantics

1. `techtree run cancel <run-id>` calls `RunStore.request_cancel`, which appends
   a `cancel.requested` event, and signals the worker's process group
   (`WorkerLauncher.request_termination`, SIGTERM; SIGKILL only after a
   timeout).
2. The worker notices at its next safe boundary. `raise_if_cancel_requested`
   reads the run's phase and raises `CancellationError` rather than starting
   more work.
3. The worker appends `run.cancelled` and exits. If it breaks while winding down
   it appends `run.failed` instead.

Cancellation is cooperative and phase-boundary-driven, which is why
`cancel_requested` is a phase of its own rather than a flag: the request is
durable, survives the CLI process exiting, and is visible to any later reader.

**Asking twice is free and changes nothing.** `request_cancel` is idempotent in
the store, not in the log: a run already in `cancel_requested` gets its current
state back and no second event, so `cancel_requested_at` is the moment the run
was first asked. That is what makes the operation safe to retry, which matters
because the process that asked may not survive long enough to learn whether it
succeeded. Asking a run that has already ended is a typed `RunError`
(`run_not_cancellable`) rather than a silent no-op, because the caller's belief
about the run is wrong and worth saying so.

The exit code for a cancelled run is 130, the shell convention for "terminated
by SIGINT" (`errors.EXIT_CANCELLED`).

## 9. Recovery semantics

- **Damaged or missing `state.json`.** Rebuilt from the log on the next read.
  It is a cache and holds nothing the log cannot recompute except the
  heartbeat, which is read back from its own file.
- **Crash between appending an event and rewriting the projection.** The
  projection is one event behind until the next append, heartbeat, or
  `rebuild_state`. Every writer derives the current phase from the log, never
  from the cache, so a stale cache can never cause a wrong transition to be
  accepted.
- **Torn final line in `events.jsonl`.** Rejected on read as a typed
  `ValidationError`. A lost trailing event is recoverable; a half-parsed one
  would not be.
- **A log that does not belong to the run.** The created event records
  `request_digest`, so a recovered run directory can be checked against the
  request it executes rather than assumed to match.
- **Worker died without a terminal event.** The run stays in its last phase
  with a stale heartbeat. Nothing invents a terminal event on the worker's
  behalf; the CLI reports the run as not alive and the operator decides.

### Error codes

Every failure the subsystem raises carries one of these machine-stable codes:

| Code | Raised when |
| --- | --- |
| `run_not_found` | The run directory has no `request.json`. |
| `run_already_exists` | `create` was called for a run that already has one. |
| `run_request_corrupt` | `request.json` will not validate. |
| `run_event_log_corrupt` | A line will not parse, a line is blank, or the log mixes run identifiers. |
| `run_event_sequence_invalid` | The sequence numbers gap, repeat, or arrive out of order. |
| `run_event_kind_invalid` | Unknown kind, kind and phase disagree, or a detail the kind carries is missing or malformed. |
| `run_transition_invalid` | The phase change is not an edge, or the event may not leave the run where it is. |
| `run_not_cancellable` | Cancellation was asked of a run that has already ended. |
| `run_lock_timeout` | The per-run lock was held for longer than `LOCK_TIMEOUT_SECONDS`. |

## 10. Fake execution semantics (WP3)

`executor_kind` is `"fake"` and nothing else through WP5. The fake executor
(spec §18.5, delivered with the worker) walks the normal path, and the run is
real in every respect except the subject: the state machine, the event log, the
lock, the receipts, and the report are all the production ones.

What is fake is unmistakably labelled. The subject is never executed — no
provider credential is read, no Docker image is pulled — the episode receipts
say so, and the report carries `proof_grade: development_only`,
`decision: development_only`, and `publication_eligible: false`. A
development-only report can never present itself as evidence; the model refuses
to construct one that tries.

## 11. WP5 taskset-validation insertion

`validating_taskset` is where real work first enters the otherwise fake run,
and it needs no new phase. In WP3 the phase resolves the taskset and compares
it with the Campaign's membership commitment. In WP5 the same phase also runs
the pinned Verifiers validator inside the managed engine, writes
`runs/<run-id>/taskset/lock.json` and `taskset/validation/`, and compares the
locally computed `TasksetValidationReceipt` digest with the publisher's
commitment (decisions 0003 A1: for the pure reference taskset these must be
equal).

Failure there is an ordinary failure: `validating_taskset → failed` with the
reason in `details.error`. The transition table does not change between WP3 and
WP5.

## 12. Campaign and DataPolicy references in `RunRequest`

`RunRequest` is written once at creation and is what the run executes. It
carries the scientific context by digest rather than by copy, so a run can
never drift from the objects it was started against (spec §11.12, decisions
0002):

| Field | What it pins |
| --- | --- |
| `campaign_spec_digest` | The `CampaignSpec` this run is an execution of. |
| `program_ref` | The optional future `ImprovementProgram` the run is attributed to. |
| `public_context` | The optional public Climb it was started under. Optional and separate on purpose — a run does not need a Climb to be valid (spec §6.8). |
| `data_policy_digest` | The `DataPolicy` that governs the resulting data. Rights follow the Campaign (spec §6.7). |
| `outcome_contract_digest` | The optional `OutcomeContract` the comparison is judged against. |
| `evaluation_backend` | Who orchestrated the evaluation and whose attestation the result carries. `local_techtree` / `participant` in WP0–WP5. |
| `taskset_lock_digest` | The resolved taskset membership, once WP5 locks it. |
| `baseline_manifest_digest`, `candidate_manifest_digest` | The two configurations being compared. They must differ; an identical pair measures nothing. |
| `draft_id`, `draft_digest` | The submission draft the run was started from. |
| `executor_kind` | `"fake"` through WP5. |

Every one of these propagates unchanged into the episode receipts and the
`UpliftReport`. Nothing in the run subsystem rewrites, defaults, or invents a
Campaign reference.

### Policy acknowledgement

`policy_acknowledgement` (decisions 0003 A5) records that the rights policy was
accepted, by which method, and when:

```python
class PolicyAcknowledgement(ProtocolModel):
    data_policy_digest: Digest
    method: Literal["interactive_cli", "explicit_cli_digest",
                    "host_agent_confirmation"]
    acknowledged_at: datetime
```

Acceptance and acknowledgement are different things. The draft states which
policy *must* be accepted (`policy_acceptance`); the run records that it *was*.
`RunRequest` refuses to exist unless
`policy_acknowledgement.data_policy_digest` equals its own
`data_policy_digest`, so a run cannot acknowledge one policy and execute under
another.

Possession of a valid confirmation token never implies acceptance. In machine
mode (`--no-input`) the caller must pass
`--accept-data-policy sha256:<exact-policy-digest>`, which yields method
`explicit_cli_digest`; automation cannot accept a policy it never read.
