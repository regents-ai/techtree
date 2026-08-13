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

Two escapes leave it:

- **Failure.** Any phase that is still working may move to `failed`.
- **Cancellation.** Any phase that is still working may move to
  `cancel_requested`, and from there to `cancelled` (wound down cleanly) or
  `failed` (broke while winding down).

`cancel_requested` never rejoins the normal path. A run that was asked to stop
does not quietly complete instead.

The complete table is `ALLOWED_TRANSITIONS` in `runs/machine.py`, derived from
`NORMAL_PATH` and those two escapes and checked edge by edge — every ordered
pair of phases — in `tests/unit/test_run_machine.py`.

### Events that do not change the phase

Every non-terminal phase also accepts an event whose `phase` equals the phase
the run is already in. That is not a loop in the state machine; it is how a run
records something true of it while it stays where it is — the worker's process
id, progress through a long phase, the digest of the report just written.

Recording those as events is what keeps the projection derivable from the log.
A fact written only into `state.json` would be a fact the log could not rebuild.

### Terminal states

`completed`, `failed`, and `cancelled` have no outgoing edges at all. A
terminal run's log is closed: `validate_transition` refuses every further
event, including same-phase ones. `is_terminal` reads this straight off the
table.

`can_cancel` is narrower than "has an edge to `cancel_requested`": a run that
has already been asked to stop returns `false`, because a second request would
change nothing and the caller is better told so.

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
| `kind` | A short name for what happened, chosen by the writer. |
| `details` | Free-form JSON. |

Both `previous_phase` and `phase` are recorded so that a reader reconstructing
a run never has to infer where it came from — which matters most for
`cancel_requested`, where the phase the run was interrupted in is otherwise
lost.

`details` is free-form except for four keys the projection interprets
(`runs/machine.py`):

| Key | Value | Effect |
| --- | --- | --- |
| `error` | A `CliError` object | Sets `RunState.error`. **Required** on every event entering `failed`. |
| `progress` | A `RunProgress` object | Sets `RunState.progress`. |
| `result_digest` | A Techtree digest | Sets `RunState.result_digest`. |
| `worker_pid` | A positive integer | Sets `RunState.worker_pid`, and `worker_started_at` to the event's timestamp. |

A malformed value under any of those keys is a typed `ValidationError`, not a
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

| `RunState` field | Where it comes from |
| --- | --- |
| `run_id`, `phase`, `sequence`, `updated_at` | The most recent event. |
| `worker_pid`, `worker_started_at` | The event carrying `worker_pid`; carried forward after that. |
| `cancel_requested_at` | The timestamp of the **first** event entering `cancel_requested`. |
| `error` | The `error` detail of the event entering `failed`. |
| `progress` | The most recent `progress` detail **within the current phase**. Entering a new phase clears it. |
| `result_digest` | The `result_digest` detail; carried forward. |
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
`worker_started` event carrying `worker_pid`, which is what makes the worker's
start part of the rebuildable history. `worker_started_at` is that event's
timestamp.

A recorded pid is not proof of life. `WorkerLauncher.is_alive` checks the
process, and pid reuse means the check is a strong hint rather than a
guarantee; the heartbeat is the corroborating signal.

## 8. Cancellation semantics

1. `techtree run cancel <run-id>` appends an event entering `cancel_requested`
   and signals the worker's process group (`WorkerLauncher.request_termination`,
   SIGTERM; SIGKILL only after a timeout).
2. The worker notices at its next safe boundary. `raise_if_cancel_requested`
   reads the run's phase and raises `CancellationError` rather than starting
   more work.
3. The worker appends `cancelled` and exits. If it breaks while winding down it
   appends `failed` instead.

Cancellation is cooperative and phase-boundary-driven, which is why
`cancel_requested` is a phase of its own rather than a flag: the request is
durable, survives the CLI process exiting, and is visible to any later reader.
`cancel_requested_at` records the first request only.

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
