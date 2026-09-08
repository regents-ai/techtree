# Techtree v0.2 CLI machine contract

Status: binding for v0.2 (WP0.6 decision)
Envelope version: `techtree.cli.v2`
Authority: [`docs/plan/v0.2.md`](../plan/v0.2.md), sections "Operator contract"
and "CLI v2 machine contract"; founder answers in
[`DECISION_LEDGER.md`](DECISION_LEDGER.md)

This document freezes `techtree.cli.v2` as the sole v0.2 machine envelope. It
is a contract, not a status report: naming an operation here does not claim
that every behavior it will eventually carry is implemented, and each row of
the operation inventory says which handler exists today.

`techtree.cli.v2` **directly replaces** `techtree.cli.v1`. There is no v1
adapter, no negotiation, no dual-write path, and no second command hierarchy.
The v1 contract, [`cli/docs/cli-json-contract.md`](../../cli/docs/cli-json-contract.md),
is the frozen historical description of the v0.1 packages and of the bytes they
already produced. It is historical rather than authoritative; its own command
list was reconciled separately, as recorded below. Those bytes are never
rewritten. v0.2 producers and consumers move to v2 together, in WP1 and WP6.

## What v2 does not change

The transport is unchanged, because the envelope is what moved and the process
boundary is not. Carried forward from v1, word for word:

- machine mode is on when `--json` is given, `output_mode = "json"` is set in
  `config.toml`, or `TECHTREE_OUTPUT_MODE=json` is set;
- machine mode implies `--no-input`; a prompt written to a host agent is a hang
  rather than a question;
- exactly one JSON object on stdout, followed by one newline, and nothing else;
- the JSON is canonical — keys sorted, no insignificant whitespace — so two
  runs that produce the same response produce the same bytes;
- every operational message, traceback, and parser error goes to stderr;
- the exit-code table is append-only and unchanged, and exit status never
  disagrees with `ok`;
- `cli` argument vectors are arrays, never shell strings;
- no field Techtree fills carries a secret, and no error message is filtered.

## The envelope

Every machine response is one object with exactly these eleven fields.

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | `"techtree.cli.v2"` | Always this literal. |
| `operation` | operation identifier | Which operation answered. One of the operations below. |
| `ok` | boolean | Whether the operation succeeded. |
| `state_digest` | digest or null | The durable state this envelope observed. |
| `facts` | object | What Techtree observed and can stand behind. |
| `unknowns` | list | What it could not determine, named. |
| `blockers` | list | What stops the operation or the next step. |
| `warnings` | list | What did not stop it but must be seen. |
| `content_refs` | list | Bytes the envelope refers to instead of inlining. |
| `next_actions` | list | At most three typed next steps. |
| `error` | object or null | Present exactly when `ok` is false. |

Invariants, enforced by the model rather than by convention:

- a successful envelope has no error, and a failed envelope has one;
- there are never more than three next actions;
- next-action operations plus their prepared arguments are unique within one
  envelope;
- a failed envelope may still carry `facts`, `unknowns`, and `blockers`,
  because for a diagnosis the findings are the useful part of the answer.

### `operation` replaces `command`

v1 keyed on `command`, the space-joined command path. v2 keys on `operation`,
a stable identifier from a closed inventory. The command path stops being part
of the machine contract, which is what lets a handler be renamed, split, or
given a new flag without breaking a host agent.

### `state_digest`

`state_digest` is the digest of the durable state the envelope was computed
from, so a caller can tell whether anything moved between two envelopes
without diffing their contents.

For every run-scoped operation it is the run's event-log digest —
`techtree.runs.events:event_digest` over the exact bytes of
`runs/<run-id>/events.jsonl` (see
[`run-state-machine.md`](../../cli/docs/run-state-machine.md) section 3). The
log is the truth and the projection is a cache, so the log's digest is the only
honest identity for "where this run had got to".

For a draft-scoped operation — preparing a comparison — it is the draft's own
digest, which is the identity of the durable state that preparation wrote and
what the start offered beside it is bound to.

For an operation with no durable subject — inspecting the machine, verifying a
proof file — `state_digest` is null. Null means "this answer is not about
durable state", never "the state is unknown"; something unknown is an
`unknowns` entry.

It has exactly one home. A payload never carries its own copy: two places to
read the same digest from is two places for them to disagree.

### `facts`

`facts` is the operation's payload: an object whose keys each operation
documents. It replaces v1's `data`.

**v2 has no free-text `messages` list.** In v1 a caller had to read prose to
learn something the payload did not carry. In v2 anything a caller must act on
is a typed fact, an unknown, a blocker, or a warning. Human presentation text
is built by the renderer from these, and is not part of the machine contract.

### `unknowns`

A fact that is absent and a fact that could not be determined are different
answers, and v1 could not tell them apart. Each entry:

| Field | Meaning |
| --- | --- |
| `id` | Stable identifier for the thing not determined. |
| `subject` | What it is about — a JSON Pointer into `facts`, or null. |
| `reason` | Why it could not be determined. |
| `resolvable_by` | The `operation` of a next action that could determine it, or null. |

An unknown is never rendered as a zero, an empty list, or a default. A cost
that could not be established is unknown; it is not free.

### `blockers`

A blocker stops this operation, or stops the step the caller wanted next. Each
entry:

| Field | Meaning |
| --- | --- |
| `id` | Stable identifier. |
| `text` | What is wrong, in plain words. |
| `blocks` | The operation identifiers this blocker forbids. |
| `resolvable_by` | The `operation` of a next action that would clear it, or null. |

Doctor's blocking checks are the case that matters: a failed environment check
becomes one blocker naming the operations it forbids, and the checks it ran
stay in `facts`.

### `warnings`

Same shape as a blocker without `blocks`: things that did not stop the
operation and must still be seen. A weaker evidence claim is a warning, never
silence and never a failure.

### `content_refs`

Bytes the envelope names rather than carries — a proof bundle, a worker log, a
report file, a provider record. Each entry:

| Field | Meaning |
| --- | --- |
| `id` | Stable identifier for the referenced content. |
| `kind` | What it is (`proof_bundle`, `run_log`, `report`, `export`, …). |
| `digest` | The content digest, or null where the bytes are not content-addressed. |
| `path` | A local filesystem path, or null. |
| `url` | A URL, or null. |
| `media_type` | The media type of the bytes. |
| `byte_count` | The size of the bytes, or null when not yet known. |

An entry offers at least one of `path` and `url`. Large or private bytes are
referenced, never inlined: an envelope is a message, not a container.

### `error`

| Field | Meaning |
| --- | --- |
| `code` | Stable machine identifier. Branch on this, never on `message`. |
| `message` | One line, unfiltered (decision 0036). |
| `details` | Identifiers, counts, and paths. |

v1's `retryable` boolean is **removed**, not kept alongside its replacement.
Whether and how to retry is stated by the `retry_class` of the repair action
the failed envelope carries, which can say five things where a boolean said
two. A failed envelope that has a sensible repair carries it as a next action;
one that has none says so by carrying none.

## Typed next actions

Each `next_actions` entry has exactly these nine fields.

| Field | Type | Meaning |
| --- | --- | --- |
| `operation` | operation identifier | Which operation to invoke. |
| `prepared_arguments` | object | The exact arguments to invoke it with. |
| `expected_state_digest` | digest or null | The `state_digest` this action assumes. |
| `side_effect` | side-effect class | What invoking it changes. |
| `approval_required` | boolean | Whether a person must approve it first. |
| `retry_class` | retry class | What to do when it does not clearly succeed. |
| `estimated_cost` | object or null | What it may cost, and the ceiling authorized. |
| `data_egress` | egress class | What leaves this machine if it runs. |
| `reason` | string | Why this is being offered. |

`prepared_arguments` is a named object rather than v1's argv array, because a
name cannot be mis-quoted into a second command. It has exactly three entries:

| Entry | Meaning |
| --- | --- |
| `command` | The command path, as literal segments. At least one. |
| `arguments` | The positional values, in order. |
| `options` | Each option by the name it is spelled with, valued by its value, or `true` where it takes none. |

An operation may describe more than one handler, so the invocation says which
one. A caller builds the call — or the command line it shows a person — by
joining `techtree`, the command path, the arguments, and the options; nothing
has to be parsed and nothing can be mis-quoted. The command path is *not* back
in the machine contract: a caller branches on `operation`, which is stable, and
takes the invocation as given rather than composing one of its own. Techtree
never executes a displayed command string.

`expected_state_digest` is how an action stays bound to the state it was
prepared against. When it does not equal the current `state_digest`, the
world moved, and the action must not be replayed on the new one; the retry
class says `reconcile_first`.

`approval_required` is not advisory. When it is true, a host agent obtains a
person's agreement on a native approval surface before invoking the action. It
is how an irreversible step stays irreversible-by-a-person even when a machine
is driving, and it is never a value a model may supply on a person's behalf.

### Retry classes

| Class | Meaning |
| --- | --- |
| `safe` | Invoking it again is harmless; the operation is idempotent in its effect. |
| `safe_after_delay` | Harmless to repeat, but not yet; something is still settling. |
| `reconcile_first` | Durable state may already have advanced. Read it before deciding anything. |
| `human_decision_required` | A person decides whether this runs again. A machine may not. |
| `forbidden` | Never invoke it again on this state. |

`forbidden` and `reconcile_first` carry the interruption matrix in
[`v0.2.md`](../plan/v0.2.md). An ambiguous paid submission — a request that may
have been accepted but lost its response — is `reconcile_first`, never `safe`:
Techtree does not automatically resubmit paid work, and no automatic duplicate
paid submission is permitted unless an upstream idempotency guarantee has been
proven and locked.

### Side-effect classes

| Class | Meaning |
| --- | --- |
| `none` | Reads only. Nothing on this machine or anywhere else changes. |
| `local_state` | Writes durable local state: a draft, an export, an installed engine, a materialized Skill, a cancellation request. |
| `local_execution` | Starts local execution, which consumes local resources and may spend model-provider budget. |
| `paid_remote_execution` | Sends work to a paid provider. Never invoked without an unexpired approval bound to the exact plan and ceiling. |
| `public_publication` | Sends bytes to the public publication service, or withdraws bytes already there. |

### Data-egress classes

| Class | Meaning |
| --- | --- |
| `none` | Nothing leaves this machine. |
| `package_index` | Package or engine downloads only. |
| `model_provider` | Prompts and subject output reach the model provider named by the Campaign. |
| `execution_provider` | The execution plan and its inputs reach the hosted execution provider. |
| `publication_service` | The proof bundle, or a signed withdrawal, reaches the publication service. |

`estimated_cost` is null when nothing is spent. Otherwise it is the non-secret
money statement of the `RemoteExecutionEstimate` in
[`v0.2.md`](../plan/v0.2.md) — currency, estimated cost, maximum authorized
cost, estimate source, uncertainty disclosure, and expiry — bound to the exact
`execution_plan_digest`. It never carries an account identifier; the
billing-principal label is a private non-secret label and stays private by
default.

## Operation inventory

These fourteen identifiers are the stable v2 surface. **They describe existing
CLI handlers; they do not create a second command hierarchy.** Every handler
below is cited as `module:function` and exists in `cli/src` today, which
`cli/tests/contract/test_v02_machine_contract.py` checks on every run.

An operation may describe more than one handler, and two operations may
describe the same handler where they are two answers that handler already
gives. That is the point of describing rather than duplicating.

| Operation | Handler | Also describes | What it answers |
| --- | --- | --- | --- |
| `plan.inspect` | `techtree.cli.commands.climb:show_climb_command` | `techtree.cli.commands.climb:list_climbs_command`, `techtree.cli.commands.doctor:doctor_command`, `techtree.cli.commands.engine:status_engine_command`, `techtree.cli.commands.engine:verify_engine_command`, `techtree.cli.commands.release:info_release_command`, `techtree.cli.commands.release:verify_release_command`, `techtree.cli.commands.uplift:skill_source_uplift_command` | What this machine supports, which release it is, which engine is active, which Climbs exist, and what one measures and costs. |
| `plan.prepare` | `techtree.cli.commands.climb:prepare_climb_command` | `techtree.cli.commands.uplift:prepare_uplift_command`, `techtree.cli.commands.uplift:context_uplift_command`, `techtree.cli.commands.skill:starter_skill_command` | Build a comparison plan and the local inputs it is built from, without starting anything. |
| `action.prepare` | `techtree.cli.commands.climb:start_climb_command` | `techtree.cli.commands.uplift:start_uplift_command`, `techtree.cli.commands.publish:publish_run_command`, `techtree.cli.commands.withdraw:withdraw_run_command` | What a side-effecting operation would do, what it costs, what leaves the machine, and what a person must approve — without doing it. |
| `action.execute` | `techtree.cli.commands.climb:start_climb_command` | `techtree.cli.commands.uplift:start_uplift_command`, `techtree.cli.commands.publish:publish_run_command`, `techtree.cli.commands.withdraw:withdraw_run_command`, `techtree.cli.commands.setup:setup_command`, `techtree.cli.commands.engine:install_engine_command` | Perform it, on an approval the caller already holds. |
| `run.status` | `techtree.cli.commands.run:status_run_command` | `techtree.cli.commands.run:logs_run_command` | One snapshot of where a run has got to, and its diagnostic output. |
| `run.wait` | `techtree.cli.commands.run:status_run_command` | — | The same snapshot, after waiting a bounded time for it to change. |
| `run.reconcile` | `techtree.cli.commands.run:status_run_command` | — | Recompute durable state from the append-only log and reconcile it with observed reality. |
| `run.cancel` | `techtree.cli.commands.run:cancel_run_command` | — | Ask a run to stop, durably and idempotently. |
| `result.inspect` | `techtree.cli.commands.run:result_run_command` | `techtree.cli.commands.run:logs_run_command` | The finished Result: its report, its numbers, its execution record, and its files. |
| `claim.inspect` | `techtree.cli.commands.run:result_run_command` | `techtree.cli.commands.proof:verify_proof_command` | What that Result is entitled to assert: proof grade, decision, publication eligibility, weaker-claim warnings, and the v0.2 evidence facets. |
| `proof.verify` | `techtree.cli.commands.proof:verify_proof_command` | — | Whether the stored bytes verify offline. |
| `profile.get` | `techtree.cli.commands.profile:get_profile_command` | — | Read the owner's shared personal profile using paired Privy proof, independent of publication keys. |
| `profile.sync` | `techtree.cli.commands.profile:sync_profile_command` | — | Explicitly synchronize personal X and wallet evidence; no publication, payout or signing authority. |
| `profile.update` | `techtree.cli.commands.profile:update_profile_command` | — | Edit the owner's shared name or selected linked wallet without changing payment destinations. |

How the four non-run, non-profile operations divide, stated once so a
fifteenth identifier is never invented to hold something these already cover:

- `plan.inspect` reads. *It* changes nothing; the steps it offers may change
  anything, and each says so. Doctor answers under `plan.inspect` and offers
  installing the evaluation engine, which writes local state and reaches a
  package index; `climb show` does the same for a machine that has no engine.
  A read that could only ever offer other reads would be a read with no way
  out of a blocked machine. Every class on an offered step is the truth about
  that step, never about the operation that offered it.
- `plan.prepare` builds the comparison plan and its inputs. It writes local
  state and starts nothing.
- `action.prepare` and `action.execute` are the same handlers in their two
  existing modes. In machine mode a start, a publication, or a withdrawal
  without `--yes` is refused and the refusal names the flag; that refusal is
  where `action.prepare` lives. The same handler with `--yes` and
  `--reviewed-on` is `action.execute`. This is why approval stays a person's
  act while a machine drives, and why no second hierarchy is needed.

  **The refusal carries the review.** The three refusals return what a person
  would have been shown — `techtree.cli.commands.climb:start_review` for a
  start, `techtree.cli.commands.publish:PublicationReviewPayload` for a
  publication, `techtree.cli.commands.withdraw:WithdrawalReviewPayload` for a
  withdrawal — as facts, alongside the identifiers they always carried and the
  exact lines the interactive path prints. Each offers the approved call as its
  one next action, marked `approval_required`, so a host agent shows the review
  on its own surface and calls again saying where the answer was given. Nothing
  in that flow lets a machine supply the answer itself.

  **`setup` and `engine install` have no preview mode.** Neither takes `--yes`
  and neither has a two-mode split, so `action.prepare` does not describe them
  and the inventory does not claim it does. They appear under `action.execute`
  alone. Whether they need a preview at all is still open; until one exists, a
  host agent that wants to know what they would do reads `plan.inspect`.
- `result.inspect` reports the Result; `claim.inspect` reports what may be
  claimed about it. The two consult publication eligibility by different
  routes, and the difference matters. `result_run_command` reads
  `report.publication_eligible`, a flag written onto the `UpliftReport` when
  the report was built by `techtree.receipts.uplift:build_uplift_report`;
  `verify_proof_command` calls
  `techtree.publication.service:PublicationService.publication_eligible`, which
  recomputes the answer from the stored report at the moment it is asked. Both
  routes end in the same rule,
  `techtree.receipts.uplift:publication_eligible_for`, but one is a recorded
  claim and the other is a live one. `claim.inspect` must say which it
  returned.

### Handlers this inventory does not describe

None. Every command registered in `techtree.cli.app:create_app` is described by
at least one of the fourteen operations above, and the inventory cites no handler
that is not registered there. The contract test checks both directions, so a
command added without an operation, or an operation left pointing at a deleted
handler, fails the build rather than drifting.

## The public state projection

Runs keep their detailed append-only internal phases. `RunPhase` in
`techtree.models.run` is unchanged, the event log is unchanged, and no phase is
retired. The five public states are a **projection over** those phases, not a
replacement for them.

The projection is total and exact:

| Internal phase | Public state |
| --- | --- |
| `created` | `prepared` |
| `validating_taskset` | `running` |
| `running_baseline` | `running` |
| `running_candidate` | `running` |
| `running_variants` | `running` |
| `building_receipts` | `running` |
| `verifying_comparison` | `running` |
| `building_report` | `running` |
| `cancel_requested` | `running` |
| `completed` | `completed` |
| `failed` | `failed` |
| `cancelled` | `cancelled` |

`cancel_requested` projects to `running`, not to `cancelled`. Cancellation is
cooperative and phase-boundary-driven: a run that has been asked to stop has
not stopped, may still be doing work, and may still end in `failed`. Reporting
it as `cancelled` would state an outcome that has not happened. The request
itself is visible as a fact — the moment it was first made — and not as a
state.

Everything else stays an event rather than becoming a public state: provider
provisioning, queue position, episode progress, variant progress, Relay flush,
collection, publication, and withdrawal. Adding a public state for any of them
would make the public vocabulary grow with every backend, which is exactly what
projecting to five states prevents.

Orthogonal to the five states, a run carries remote control facts —
`none`, `submitting`, `identified`, `reconciliation_required`, `terminal`, with
the provider reference, last observed provider status, last checked time, and
whether a submission was ambiguous. These are facts about a remote arm, not
public states: a run whose provider response was lost stays `running` and
requires reconciliation.

## Bounded `run.wait`

`run.wait` is a bounded long-poll over durable state. It is the only waiting
operation in the contract, and it adds no daemon and no busy-polling.

- **Explicit upper bound.** The caller passes `timeout_seconds`. The default is
  30 and the maximum is 90. A larger value is a usage error, not a silently
  clamped one.
- **90 is not arbitrary.** The Hermes bridge runs the CLI with a 120-second
  subprocess timeout (`plugin/cli/constants.py:DEFAULT_CLI_TIMEOUT_SECONDS`).
  A ceiling of 90 leaves the host's own timeout as the thing that never fires
  first, so an expiring wait is always Techtree's answer rather than the host's
  guess.
- **Expiry is a normal answer.** When the bound expires, `run.wait` returns the
  current envelope: `ok: true`, the run's current public state, and the current
  `state_digest`. Expiry is not an error, carries no error code, and is
  distinguished from a change only by the caller comparing `state_digest`.
- **It returns early on change.** A wait ends as soon as the run's durable
  state moves past the `state_digest` the caller passed in, or as soon as the
  run reaches a terminal public state.
- **No daemon.** Nothing is left running when the process exits. The run itself
  is already a detached worker that survives the CLI exiting, the terminal
  closing, and the host-agent session ending; `run.wait` observes it and adds
  no second long-lived process.
- **No busy-polling.** The wait blocks on the durable state changing. It does
  not re-read the log in a tight loop and does not sample faster than the
  worker's heartbeat interval (`DEFAULT_WORKER_HEARTBEAT_SECONDS`, 2 seconds),
  which is the fastest rate at which anything new can exist to observe.
- **A host agent's loop is bounded by construction.** Repeated `run.wait` calls
  are how a host follows a run, and each one is a separate short process with
  its own envelope.

Streaming stays human-only, and it is two separate options on two separate
commands rather than one facility: `--watch` on `techtree run status` reprints
a status line until the run ends, and `--follow` on `techtree run logs` tails
the worker log. Both remain rejected in machine mode. Neither is what
`run.wait` becomes.

## What v2 does not add

Rejected, and not to be reintroduced without a new founder decision:

- a `techtree.cli.v1` adapter, projector, negotiation mode, or dual-write path
  in v0.2 producers;
- a second command hierarchy, or a command that exists only to serve an
  operation identifier;
- a daemon, a background service, or any process that outlives the invocation;
- busy-polling in the CLI or in any host integration;
- a shared plugin runtime SDK — see [`PLUGIN_LAYOUT.md`](PLUGIN_LAYOUT.md);
- plugin-owned scheduler, receipt, approval, or publication behavior;
- free-text `messages` as a machine-readable channel;
- an error-level `retryable` boolean beside `retry_class`.

Frozen v0.1 packages and proof bytes keep their v1 envelope bytes. They are not
re-emitted, re-encoded, or re-signed, and no v0.2 code reads them through a
compatibility branch; historical artifacts are read by the read-only v0.1
projectors WP1 adds.

Two published schemas stop being generated because of that. `v1alpha1`'s
`cli-envelope.schema.json` describes an envelope this build no longer produces,
and its `run-state.schema.json` embeds that envelope's error, which lost
`retryable` in the cutover. Both keep the bytes v0.1 released and are verified
against a recorded digest by `cli/tools/export_schemas.py` rather than written
again. Regenerating either would rewrite history instead of checking it.

## Where this is implemented

WP1 replaced the envelope, the next-action model, and the state projection, and
added bounded `run.wait`. `techtree.constants:CLI_SCHEMA_VERSION` is
`techtree.cli.v2` in this build, every command answers under one of the fourteen
operations, and no v1 envelope or next-action shape remains in `cli/` or
`plugin/`. WP1.6 was the cutover, and it moved the Hermes consumer in the same
change; there was never a build in which the two spoke different versions.

- **WP4** implements the remote arm of `run.reconcile`.
- **WP6** migrates the Codex consumer.

### Which operation each command reports

The inventory above says which operations *describe* a handler. This says which
one a given invocation answers under, for the cases where a handler has more
than one answer to give. Everything not listed here reports the operation its
inventory row names.

| Invocation | Operation | Why |
| --- | --- | --- |
| `run status` with neither `--timeout-seconds` nor `--since-state-digest` | `run.status` | It answers about now. |
| `run status` with either of them | `run.wait` | It waits first, bounded, and the wait is the answer. |
| `run logs` | `run.status` | One handler, one answer: a run's diagnostic output. The inventory also lists it under `result.inspect`, and nothing distinguishes the two at the moment of running, so it reports the operation it is a snapshot of. |
| `run result` | `result.inspect` | The Result and the claim it is entitled to make come back together, and `result.inspect` is the one that describes the payload. |
| `proof verify` | `proof.verify` | Whether the stored bytes verify offline. |
| `climb start`, `uplift start`, `publish`, `withdraw` without `--yes`, where nobody can be asked | `action.prepare` | The refusal carries the review, which is the preparation. |
| The same four otherwise | `action.execute` | Either a person has already answered, or one is about to be asked. |
| A failure before any command starts | `plan.inspect` | Nothing got as far as being an operation; the envelope still names one, and this is the one that answers about this machine. |

Two of the fourteen identifiers are never reported by a handler in this build.
`claim.inspect` is answered inside `result.inspect`: `run result` returns the
recorded claim — `report.publication_eligible`, written when
`techtree.receipts.uplift:build_uplift_report` built the report — and says so by
carrying it as a fact of the Result rather than as a separate answer.
`run.reconcile` has only its local half, which happens on every `run status`.
Both remain valid targets for a next action.

### Where the handlers deviate from this contract

Places where the code and this document knowingly differ, with the reading
taken. They are deviations rather than gaps: the behavior is deliberate and
the contract has been amended to match, and each entry says what moved.

1. **`plan.inspect`'s next actions are not all `side_effect: none`.** This
   document said they were, of every read. Doctor's repairs and `climb show`'s
   offer to install the evaluation engine are `local_state` with
   `package_index` egress, because that is what invoking them does, and a read
   that could only offer reads would leave a blocked machine with nothing to
   do. The sentence above is amended; the operation reads, its steps are
   labelled truthfully, and a caller branches on the step's own classes.

### What the handlers do not do yet

Places where this contract describes behavior the cited handler does not have.
They are listed so an implementer sizes them rather than discovers them. An
item a work package has since delivered says so in place and keeps its number,
so a reference to "item 3" means the same item it always did.

1. **`run.wait` waits, as of WP1.4, and names itself, as of WP1.6.**
   `status_run_command` takes the bounded `timeout_seconds` option this
   contract requires, alongside the digest a caller last saw, and blocks until
   the run's durable state moves past it, the run reaches a terminal public
   state, or the bound expires. Asking to wait is what makes the answer
   `run.wait`, and `state_digest` is on the envelope where this contract puts
   it. `--watch` is unchanged: still human-only, still refused in machine mode,
   and refused beside a bounded wait rather than silently taking precedence
   over one. Waiting is asked for and never assumed, so a plain `run status`
   still answers about now.
2. **`run.reconcile` has only its local half.** Recomputing durable state from
   the append-only log is real and already happens on every `run status`. The
   remote arm — the `submitting` / `identified` / `reconciliation_required` /
   `terminal` control record — does not exist and is WP4 scope.
3. **`action.prepare` carries the machine-readable review, as of WP1.6.** A
   start, a publication, or a withdrawal that carries no `--yes` where nobody
   can be asked returns the review as facts: for a start, the episodes, the
   maximum the Campaign declares, the provider the model calls go to, the
   rights being accepted, and the exact lines a person reads; for a
   publication, the file and byte counts, the endpoint, the bundle digest and
   what the proof directory does not contain; for a withdrawal, the entry, the
   endpoint, and what withdrawing does and does not do. Each carries the
   approved call as its one next action, marked `approval_required`.
4. **`setup` and `engine install` have no preview mode.** Neither takes `--yes`
   and neither has a two-mode split. They appear under `action.execute` alone.
   Whether they need a preview at all is still open; until one exists, a host
   agent that wants to know what they would do reads `plan.inspect`.
5. **Every next action in the CLI has the v2 shape, as of WP1.6.** Every
   construction site across the climb, run, proof, publish, withdraw, engine,
   release, setup, skill and uplift handlers was rewritten, as was every
   `messages` producer: what a caller must act on is now a fact, an unknown, a
   blocker, or a warning, and the sentences a person reads are built by each
   command's own renderer out of the payload it produced.
6. **No envelope refers to bytes yet.** `content_refs` is defined, validated,
   and empty in every response this build produces. Nothing in v0.2.0 names
   bytes instead of carrying them; a proof bundle is verified in place and a
   report is inlined. The first producer is WP5's public evidence.
7. **`estimated_cost` states a declared maximum, never a quote.** The only
   money statement this build can make is the Campaign's own declared maximum,
   carried on the two start actions with `estimate_source:
   campaign_declared_maximum` and no `execution_plan_digest`, because no
   resolved plan is priced yet. A Campaign that declares no maximum produces no
   money statement and an `unknowns` entry saying so, never a zero. The quoted
   `RemoteExecutionEstimate` this field is otherwise drawn from arrives with
   the hosted backend in WP4.
8. **A next action names a Techtree operation and nothing else.** v1's actions
   could carry any argument vector, and Doctor used that to hand back
   `chmod`, `uv python install`, and `prime login`. v2 actions are typed
   operations, so those repairs are stated in the words of the blocker or
   warning that reports the check, and the action offered beside them is the
   Techtree operation that follows — the re-check, or the engine install.

### The v1 document's command list

`cli/docs/cli-json-contract.md` once listed nineteen stable command names where
the CLI registered twenty-four. That was reconciled by techtree-31k.15: the
document lists every registered command, and
`cli/tests/contract/test_cli_json_contract_doc.py` holds it to
`techtree.cli.app:create_app` so it cannot drift again.

It stays the frozen v1 description all the same — it describes the bytes v0.1
released, and this document is the v2 contract. The reasoning that a hand-kept
list goes stale is why the operation inventory above is checked against the
registered commands in both directions rather than maintained by hand.

## Open questions for the founder

Recorded rather than silently resolved. Each names the reading taken here and
what the plan actually says. WP1.6 built to every reading below as a working
default: they are reversible engineering choices with no protected effect, and
a different answer is applied to the envelope before lock adoption.

1. **`claim.inspect` is not defined in the plan.** Two readings exist. (a) The
   claim a Result is entitled to make — proof grade, decision, publication
   eligibility, weaker-claim warnings, evidence facets. (b) The release's own
   coordinate claims, which `release verify` checks. Reading (a) is taken,
   because "claim" everywhere else in this codebase and in the v0.2 plan's
   "claim semantics" means what evidence is entitled to assert, and because
   reading (b) would leave the evidence claim with no operation of its own.
   Under (a), `release info` and `release verify` are described by
   `plan.inspect`.
2. **`action.prepare` and `action.execute` share their handlers.** The plan
   lists them as two operations and requires that they map to existing
   handlers. The existing handlers already have exactly two modes, separated by
   `--yes`, so the two operations are those two modes rather than two commands.
   The alternative reading — that `action.prepare` is a new preparation command
   — is rejected as a second command hierarchy.
3. **The three-action ceiling is carried forward.** v1 caps `next_actions` at
   three (`techtree.models.cli:MAX_NEXT_ACTIONS`). The v0.2 plan does not
   mention a ceiling. It is kept, because the reason for it is unchanged: a
   host agent offered ten choices is being asked to plan rather than to act.
4. **`error.retryable` is removed rather than kept.** The plan puts retry
   classes on next actions and does not say what becomes of the v1 boolean.
   Keeping both would be dual-shape support, so it is deleted.
5. **The `side_effect` and `data_egress` value sets are derived, not quoted.**
   The plan names both fields but neither set. The five and five above are
   derived from what the existing commands actually do and from the plan's
   security and data boundary.
6. **`run.wait`'s numeric bound is chosen here.** The plan requires an explicit
   upper bound but does not give one. 30 default and 90 maximum are derived
   from the Hermes bridge's 120-second subprocess timeout.
