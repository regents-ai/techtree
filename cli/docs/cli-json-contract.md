# CLI JSON contract

The Techtree command-line interface is the stable boundary that host agents
program against. A host agent — the future Hermes plugin, a CI job, another
tool — runs `techtree` as a subprocess and reads its output. It never imports
Techtree into its own Python process.

This document is that contract. Everything described here is stable within the
`techtree.cli.v1` envelope version. It describes the boundary as specified, not
as far as any one build has got: a command listed here that a build has not
implemented answers with the error code `not_implemented` rather than being
absent. Every command listed in this document is implemented today; the
`not_implemented` mechanism remains for reserved future commands.

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
form. Accepting a DataPolicy, for example, requires
`--accept-data-policy sha256:<exact-policy-digest>`: possession of a
confirmation token never implies acceptance.

## The envelope

```json
{
  "schema_version": "techtree.cli.v1",
  "ok": true,
  "command": "doctor",
  "data": {},
  "messages": [{"level": "info", "code": "doctor_summary", "text": "..."}],
  "warnings": [{"level": "warning", "code": "active_engine", "text": "..."}],
  "next_actions": [],
  "error": null
}
```

| Field            | Meaning                                                    |
| ---------------- | ---------------------------------------------------------- |
| `schema_version` | Always `techtree.cli.v1` for this contract.                 |
| `ok`             | Whether the command succeeded.                              |
| `command`        | The stable command identifier (see below).                  |
| `data`           | The command's payload. Each command documents its own.      |
| `messages`       | Informational text, in the order it should be read.         |
| `warnings`       | Things that did not stop the command but ought to be seen.  |
| `next_actions`   | At most three concrete next steps.                          |
| `error`          | Present exactly when `ok` is false.                         |

Invariants, enforced by the model rather than by convention:

- A successful envelope has no error.
- A failed envelope has an error.
- There are never more than three next actions.
- Next-action identifiers are unique within one envelope.

A failed envelope may still carry `data`. Doctor is the case that matters: when
it finds a blocking problem it reports failure *and* returns every check it
ran, because the diagnosis is the useful part of the answer.

### `error`

```json
{
  "code": "run_result_not_ready",
  "message": "run run_... has not completed; its result is not available yet",
  "retryable": true,
  "details": {"run_id": "run_...", "phase": "running_baseline"}
}
```

`code` is a stable machine identifier; branch on it rather than on `message`.
`retryable` says whether running the same command again could plausibly
succeed. `details` carries identifiers, counts, and paths.

### `next_actions`

```json
{
  "id": "install_engine",
  "label": "Install the managed evaluation engine",
  "reason": "Preparing or starting a Climb needs an installed, active engine.",
  "cli": ["techtree", "engine", "install"],
  "hermes_tool": null,
  "hermes_args": null,
  "requires_user_confirmation": false
}
```

`id` is stable and is what a host agent keys off. `cli` is an argument vector.
`hermes_tool` names a host-agent tool instead, with `hermes_args` as its
arguments. An action always offers at least one of the two.

`requires_user_confirmation` is not advisory. When it is true, a host agent
must obtain a person's agreement before running the action. It is how an
irreversible step stays irreversible-by-a-person even when a machine is
driving.

Every successful command offers a sensible next action, and every error carries
a repair action where one exists.

### Why command vectors are arrays

`cli` is an array of arguments, never a shell string, because:

- Nothing has to quote it, and therefore nothing can quote it wrong. A path
  containing a space, a quote, or a semicolon is one array element and cannot
  become two commands.
- No shell is involved, so no argument can be interpreted as a redirection, a
  pipeline, or a substitution.
- A host agent can inspect the vector — check the program name, check the
  arguments — before deciding to run it.

Human output does render a quoted command line, using `shlex.join`. That string
is for reading. Techtree never executes a displayed command string.

## Stable command names

`command` is the space-joined command path without the program name.

```text
doctor
climb list
climb show
climb prepare
climb start
run status
run logs
run cancel
run result
proof verify
release info
release verify
uplift context
uplift prepare
uplift start
engine install
engine status
engine verify
```

Commands that are registered but not implemented in a given build answer with
`ok: false` and error code `not_implemented`. A name that exists and says so is
scriptable; a name that does not exist yet is indistinguishable from a typo.

The namespaces `program`, `blueprint`, `forge`, `verify`, `trace`, and `lab`
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

No envelope carries a secret. Specifically:

- No provider credential, API key, token, or password, in any field.
- A subject's credential is named by an environment variable in the Campaign;
  the value is read at execution time and never copied into settings, a run
  directory, an envelope, or any protocol document.
- Error messages pass through a scrubber on their way out. Anything shaped like
  a secret assignment, a bearer value, a prefixed key, or a long opaque run is
  replaced with `[redacted]`.
- Digests and Verifiers task hashes survive redaction. They are identifiers an
  operator needs to see, and they are not secrets.
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
    if action["requires_user_confirmation"]:
        ask_the_user_first(action["label"])
```

Rules for the caller:

- Always pass `--json`. Never parse human output.
- Always close stdin. Nothing should ever be waiting for it, and closing it
  makes that a guarantee rather than a hope.
- Branch on `returncode` and `error.code`, never on message text.
- Run `cli` vectors as argument vectors. Never join them into a shell string.
- Honour `requires_user_confirmation`.
- Treat unknown fields as additive. New optional fields may appear within
  `techtree.cli.v1`; existing fields do not change meaning.

Long-running work is not held open by the CLI. `techtree climb start` launches
a detached worker and returns; the run survives the CLI exiting, the terminal
closing, and the host-agent session ending. Progress is read with
`techtree run status`, which returns one snapshot per invocation in machine
mode. The streaming options `--watch` and `--follow` are human-only and are
rejected with `--json`.
