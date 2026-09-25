# CLI JSON contract

The Techtree command-line interface is the stable boundary that host agents
program against. A host agent — the Hermes plugin in `plugin/`, a CI job,
another tool — runs `techtree` as a subprocess and reads its output. It never
imports Techtree into its own Python process.

This document describes that boundary as the CLI emits it today: envelope
version `techtree.cli.v2` (`techtree.constants:CLI_SCHEMA_VERSION`), whose
published JSON Schema is
[`schemas/v2/cli-envelope.schema.json`](../schemas/v2/cli-envelope.schema.json).
`techtree.cli.v2` replaced `techtree.cli.v1` in a hard cutover, and the CLI
emits only v2. The decision record that froze v2, with the full
operation inventory checked against the code, is
[`docs/v0.2/MACHINE_CONTRACT.md`](../../docs/v0.2/MACHINE_CONTRACT.md).

## One JSON object on stdout

In machine mode a command writes exactly one JSON object to stdout, followed by
one newline, and nothing else. There is no banner, no progress output, no
partial object, and no second object.

Machine mode is on when any of the following is true:

- `--json` appears anywhere on the command line.
- `output_mode = "json"` is set in `config.toml`.
- `TECHTREE_OUTPUT_MODE=json` is set in the environment.

The JSON is canonical: keys sorted, no insignificant whitespace. That is a
stability guarantee, not a formatting preference — two runs that produce the
same response produce the same bytes.

## Logs only on stderr

Every operational message goes to stderr: debug logging under `--debug`,
tracebacks, and the argument parser's own error output. stdout carries the
envelope and nothing else, so `techtree ... --json | jq` never needs filtering.

Human output also goes to stdout, and it contains no ANSI escape sequences when
stdout is not a terminal or when `--no-color` is given.

## Global options

These are accepted anywhere on the command line. `techtree --json doctor` and
`techtree doctor --json` are the same invocation.

| Option        | Meaning                                                |
| ------------- | ------------------------------------------------------ |
| `--home PATH` | Directory Techtree keeps its local state in.            |
| `--json`      | Emit one JSON envelope instead of human output.         |
| `--no-color`  | Never colour human output.                              |
| `--no-input`  | Never prompt; fail with a typed error instead of asking.|
| `--debug`     | Write operational detail to stderr.                     |
| `--version`   | Print the package version and exit 0.                   |

## Non-interactive mode

`--no-input` means no command ever waits for a human. A command that would have
asked something fails instead, with an error naming what it needed.

Machine mode implies `--no-input`. A prompt written to a host agent is a hang,
not a question, so `--json` and interactivity cannot be requested together.

Anything a person would confirm interactively has an explicit non-interactive
form. A command that starts, publishes, withdraws or approves something prints
the review of what it would do and asks; in machine mode that same call is
refused, the refusal carries the review as facts, and its one next action is
the approved call with `--yes` and `--reviewed-on host-agent`, marked
`approval_required`. `--yes` and `--reviewed-on` state what a person already
did on a surface they can see. They are never a shortcut a model may take on a
person's behalf.

## The envelope

Every machine response is one object with exactly these eleven fields. This is
`techtree climb show hello-world-climb@1 --json` on a machine with no
evaluation engine yet, with `facts` left out:

```json
{
  "schema_version": "techtree.cli.v2",
  "operation": "plan.inspect",
  "ok": true,
  "state_digest": null,
  "facts": {},
  "unknowns": [],
  "blockers": [
    {
      "id": "engine_not_installed",
      "text": "The evaluation engine this Climb needs is not installed yet. Run `techtree engine install` before preparing a submission.",
      "blocks": ["plan.prepare", "action.execute"],
      "resolvable_by": "action.execute"
    }
  ],
  "warnings": [
    {
      "id": "development_climb",
      "text": "hello-world-climb@1 is a development Climb. Its results are for trying the flow out and are not comparable evidence.",
      "resolvable_by": null
    }
  ],
  "content_refs": [],
  "next_actions": [
    {
      "operation": "action.execute",
      "prepared_arguments": {"command": ["engine", "install"], "arguments": [], "options": {}},
      "expected_state_digest": null,
      "side_effect": "local_state",
      "approval_required": false,
      "retry_class": "safe",
      "estimated_cost": null,
      "data_egress": "package_index",
      "reason": "Preparing a submission for this Climb needs the evaluation engine."
    }
  ],
  "error": null
}
```

| Field            | Meaning                                                              |
| ---------------- | -------------------------------------------------------------------- |
| `schema_version` | Always `techtree.cli.v2`.                                             |
| `operation`      | Which of the stable operations answered (see below).                  |
| `ok`             | Whether the operation succeeded.                                      |
| `state_digest`   | Digest of the durable state this answer observed, or null when the answer is not about durable state. |
| `facts`          | The operation's payload, always an object. Each command documents its own keys. |
| `unknowns`       | What could not be determined, each named (`id`, `subject`, `reason`, `resolvable_by`). |
| `blockers`       | What stops this operation or the next step (`id`, `text`, `blocks`, `resolvable_by`). |
| `warnings`       | What did not stop it but must be seen (`id`, `text`, `resolvable_by`). |
| `content_refs`   | Bytes the envelope names rather than carries (`id`, `kind`, `digest`, `path`, `url`, `media_type`, `byte_count`). |
| `next_actions`   | At most three typed next steps.                                       |
| `error`          | Present exactly when `ok` is false.                                   |

There is no free-text `messages` list and no `command` field. Anything a caller
must act on is a fact, an unknown, a blocker or a warning, and a caller
branches on `operation`, not on the command path.

Invariants, enforced by the model rather than by convention:

- A successful envelope has no error, and a failed envelope has one.
- `facts` is always an object.
- There are never more than three next actions.
- No two next actions share the same operation and prepared arguments.
- A blocker names at least one operation it forbids.
- A content reference offers a `path`, a `url`, or both.

A failed envelope may still carry `facts`, `unknowns` and `blockers`. Doctor is
the case that matters: when it finds a blocking problem it reports failure
*and* returns every check it ran, because the diagnosis is the useful part of
the answer.

An unknown is never shown as a zero, an empty list, or a default. A cost that
could not be established is unknown; it is not free.

### `operation`

`operation` is one of fourteen stable identifiers. They describe the existing
commands rather than forming a second command hierarchy, so one operation can
answer for several commands.

| Operation | What it answers |
| --- | --- |
| `plan.inspect` | Reads: what this machine supports, which release and engine it has, what a Climb measures, where a forge record stands. |
| `plan.prepare` | Prepares local inputs without starting anything: a draft, a Skill inspection, a plan, a proposal, a construction, a collection. |
| `action.prepare` | A side-effecting step refused in machine mode because nobody has approved it yet; the refusal carries the review. |
| `action.execute` | The same step, performed on an approval the caller already holds. |
| `run.status` | One snapshot of where a run has got to. |
| `run.wait` | The same snapshot after a bounded wait for it to change. |
| `run.reconcile` | Durable run state recomputed from its append-only log. |
| `run.cancel` | A durable, repeatable request for a run to stop. |
| `result.inspect` | A finished Result or comparison report. |
| `claim.inspect` | What a Result is entitled to claim. |
| `proof.verify` | Whether stored bytes verify offline. |
| `profile.get`, `profile.sync`, `profile.update` | The private shared profile (see the last section). |

A failure before any command starts answers under `plan.inspect`.

### `error`

```json
{
  "code": "run_not_found",
  "message": "no such run: run_0123456789abcdef0123456789abcdef",
  "details": {"run_id": "run_0123456789abcdef0123456789abcdef"}
}
```

`code` is a stable machine identifier; branch on it rather than on `message`.
`message` is one line. `details` carries identifiers, counts and paths.

There is no `retryable` flag on the error. Whether and how to try again is the
`retry_class` of the repair action the failed envelope carries. A failure with
no sensible repair carries no next action.

### `next_actions`

Each entry has exactly these nine fields:

| Field | Meaning |
| --- | --- |
| `operation` | Which operation invoking it answers under. |
| `prepared_arguments` | The exact invocation: `command` (the command path as literal segments), `arguments` (positional values in order), and `options` (each option by its own name, valued by its value or `true` where it takes none). |
| `expected_state_digest` | The `state_digest` this action was prepared against, or null. When it no longer matches the current state, do not replay the action. |
| `side_effect` | `none`, `local_state`, `local_execution`, `paid_remote_execution` or `public_publication`. |
| `approval_required` | Whether a person must approve it first. |
| `retry_class` | `safe`, `safe_after_delay`, `reconcile_first`, `human_decision_required` or `forbidden`. |
| `estimated_cost` | Null when nothing quoted a cost; otherwise the currency (`USD`), estimated cost, maximum authorized cost, where the figure came from, what is uncertain about it, when it expires, and the execution plan it is bound to. It never carries an account identifier. |
| `data_egress` | What leaves this machine if it runs: `none`, `package_index`, `model_provider`, `execution_provider` or `publication_service`. |
| `reason` | Why this is being offered. |

`approval_required` is not advisory. When it is true, a host agent must obtain a
person's agreement on a surface that person can see before invoking the action.
It is how an irreversible step stays irreversible-by-a-person even when a
machine is driving, and it is never a value a model may supply on a person's
behalf.

Retry classes, in one line each:

| Class | Meaning |
| --- | --- |
| `safe` | Invoking it again is harmless. |
| `safe_after_delay` | Harmless to repeat, but not yet; something is still settling. |
| `reconcile_first` | Durable state may already have moved. Read it before deciding anything. |
| `human_decision_required` | A person decides whether this runs again. A machine may not. |
| `forbidden` | Never invoke it again on this state. |

### Why invocations are named parts, not strings

`prepared_arguments` is a named object, never a shell string, because:

- Nothing has to quote it, and therefore nothing can quote it wrong. A path
  containing a space, a quote, or a semicolon is one element and cannot become
  two commands.
- No shell is involved, so no argument can be interpreted as a redirection, a
  pipeline, or a substitution.
- A host agent can inspect the invocation — the command path, the arguments,
  the options — before deciding to run it.

A caller builds the argument vector by joining `techtree`, the command path,
the arguments and the options. Human output does render a quoted command line
for reading. Techtree never executes a displayed command string.

## Stable command names

These are the registered command paths, without the program name. They are
what `prepared_arguments.command` spells and what a person types; the envelope
itself names the `operation` that answered.

```text
profile get
profile sync
profile update
doctor
setup
publish
withdraw
climb list
climb show
climb prepare
climb start
skill starter
run status
run logs
run cancel
run result
proof verify
release info
release verify
uplift context
uplift skill-source
uplift prepare
uplift start
engine install
engine status
engine verify
forge build
forge run
forge compare
forge inspect-skill
forge plan
forge plan-start
forge correct-proposal
forge construct
forge construct-start
forge collect
forge accept
forge verify
forge export
forge verify-export
forge import
forge status
```

Commands that are registered but not implemented in a given build answer with
`ok: false` and error code `not_implemented`. A name that exists and says so is
scriptable; a name that does not exist yet is indistinguishable from a typo.

The namespaces `program`, `blueprint`, `verify`, `trace`, and `lab`
are reserved and are not registered.

## Exit codes

Exit status and `ok` never disagree: `0` means `ok` is true, anything else
means `ok` is false and an error is present. A caller can branch on the exit
code alone and parse output only when it wants the detail.

| Code | Meaning                                             |
| ---- | --------------------------------------------------- |
| 0    | Success.                                             |
| 1    | Unclassified failure, including internal defects.    |
| 2    | Usage error.                                         |
| 3    | Validation failure.                                  |
| 4    | A prerequisite is missing.                           |
| 5    | The named object does not exist.                     |
| 6    | Conflict with existing immutable state.              |
| 7    | Authentication failure.                              |
| 8    | A data-rights or publication policy forbids it.      |
| 9    | The managed engine failed.                           |
| 10   | A run failed, or is illegal in its current phase.    |
| 11   | A digest, signature, or commitment did not verify.   |
| 130  | Cancelled.                                           |

Values are append-only. A retired number is never reused.

Argument parsing happens before any command runs. A command line the parser
cannot understand — an unknown command, a missing argument — is reported by the
parser on stderr with exit code 2 and produces no stdout output. Running
`techtree` with no arguments at all prints help on stdout and exits 2. Every
invocation that reaches a command emits exactly one envelope.

Running `techtree --json` with no command is a command line the parser *does*
understand, so it produces a proper envelope: `ok: false`, error code
`no_command`, exit code 2.

## Redaction

No field Techtree fills carries a secret. Specifically:

- No provider credential, API key, token, or password, in any field Techtree
  authors.
- A subject's credential is named by an environment variable in the Campaign;
  the value is read at execution time and never copied into settings, a run
  directory, an envelope, or any protocol document.
- An error message is not filtered. Decision 0036: nothing inspects a string
  for credential shapes, so a message carries whatever the underlying tool
  printed, word for word — including a credential, if the tool printed one.
  What is still done to a message is flattening it onto one line and
  normalising memory addresses so the same failure reads the same way twice.
- Tracebacks are never part of the contract. Under `--debug` they go to stderr.

## How a host agent calls the CLI

```python
completed = subprocess.run(
    ["techtree", "--json", "--no-input", "doctor"],
    capture_output=True,
    text=True,
    timeout=120,
    stdin=subprocess.DEVNULL,
)
envelope = json.loads(completed.stdout)

if not envelope["ok"]:
    handle(envelope["error"]["code"], completed.returncode)

for action in envelope["next_actions"]:
    if action["approval_required"]:
        ask_the_user_first(action["reason"], action["prepared_arguments"])
```

Rules for the caller:

- Always pass `--json`. Never parse human output.
- Always close stdin. Nothing should ever be waiting for it, and closing it
  makes that a guarantee rather than a hope.
- Branch on `returncode`, `operation` and `error.code`, never on text.
- Build argument vectors from `prepared_arguments`. Never join them into a
  shell string.
- Honour `approval_required` and `retry_class`.
- Check `schema_version`. A different version is a different contract, not
  something to adapt.

Long-running work is not held open by the CLI. `techtree climb start` launches
a detached worker and returns; the run survives the CLI exiting, the terminal
closing, and the host-agent session ending. Progress is read with
`techtree run status`, which returns one snapshot per invocation in machine
mode, or waits a bounded time for a change when given `--timeout-seconds` or
`--since-state-digest`. The streaming options `--watch` and `--follow` are
human-only and are rejected with `--json`.

## Private shared profile

`profile get`, `profile sync`, and `profile update` use the Regent profile API
in `profile.openapi.json`. Pipe paired Privy proof JSON (`access`, `identity`)
from an approved credential provider; never pass proof as flags or substitute
publication keys. This adapter does not obtain a Privy session. The default origin
is `https://techtree.sh`; only explicit `--base-url` changes it. No cookies,
redirects, automatic retries, signing, payment authority or publication permissions.

`data` contains the same `{ok, status, body}` result as WebMCP; transport failures
contain `error.code` and `error.outcome_unknown`. A dispatched write with unknown
outcome must be read back before deciding to retry. Use `--display-name`,
`--wallet-address`, or `--clear-wallet` for updates. X verification reports the last
synchronized signed proof, not a live X check or company role.
