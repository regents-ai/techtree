# Techtree

Techtree is the open improvement and proof network for agent systems. Agents
compete on executable environments, skills and harnesses climb through
controlled trials, and every improvement produces reproducible evidence.

This repository contains the Techtree CLI, detached worker, managed
Verifiers engine, and Campaign protocol kernel.

## Campaign kernel

Climb is a public wrapper around a reusable CampaignSpec.
Execution artifacts reference the CampaignSpec, not the public Climb directly.

A Climb owns public identity: slug, version, title, status, schedule, and the
candidate, publication, and leaderboard policies. A CampaignSpec owns the
science: taskset reference, selection and membership commitment, environment,
named agents, evaluation backend, scoring, evidence requirements, and budgets.
Every campaign points at a DataPolicy, and every artifact a run produces
carries that policy's digest, so the rights attached to a submission cannot
change quietly between preparation and publication.

## Development status

> The WP0–WP5 implementation validates real Prime Intellect Verifiers
> tasksets but uses a fake baseline/candidate executor. It does not evaluate
> a real agent. No result produced by the fake executor is a capability proof.

Implementation is in progress. See `docs/decisions/` for binding decisions
and `docs/spec/climb-v0.1-wp0-wp5.md` for the full implementation
specification.

## Installation

Techtree targets Python 3.12 and uses [uv](https://docs.astral.sh/uv/) for
every workflow.

```bash
uv sync
```

That creates the project environment and installs the `techtree` and
`techtree-worker` executables into it.

```bash
uv run techtree --version
```

## Local development

```bash
make install          # uv sync
make format           # rewrite formatting and apply safe lint fixes
make check            # format-check, lint, typecheck, test, generated-check
```

`make check` is the gate. Individual steps are available as `make format-check`,
`make lint`, `make typecheck`, and `make test`.

The scientific environment is separate. The managed engine under
`src/techtree/resources/engines/default/` has its own pinned dependencies and
its own lock file, and the ordinary package never depends on Verifiers,
Hermes, or NeMo Relay.

## Command overview

```bash
techtree setup                                   # install the managed engine
techtree climb list
techtree climb show <climb-slug>                 # includes campaign and policy digests
techtree climb prepare <climb-slug> --skill <path>
techtree climb start <draft-id> --confirmation-token <token>
techtree run status <run-id> --watch
techtree run logs <run-id> --tail 200
techtree run result <run-id>                     # the comparison, with its caveats
techtree proof verify <run-id>                   # check the run's local proof, offline
techtree uplift context <run-id>                 # what a host agent may read about a run
techtree uplift prepare --from-run <run-id> --candidate-skill <path>
techtree uplift start <draft-id> --confirmation-token <token>
```

The detached worker is started by the CLI and is not a user-facing command.

Every command speaks two languages: rendered output for a person and, with
`--json`, exactly one JSON object on standard output so another program can
drive the CLI. Logs always go to standard error.

## Local proof

A finished real run signs its receipts and its report with a key this machine
made and keeps. The signed documents travel together in a proof bundle inside
the run directory, and `techtree proof verify` checks that bundle from its own
stored bytes — no network, no Techtree account, and no Techtree state of its
own, so a bundle copied to another machine still checks out.

What a verified proof says is bounded, and the product says so wherever it
shows one: the participant's own key vouches for bytes that verify against each
other. Nobody has independently reproduced the comparison, no platform
witnessed it, and nothing was uploaded. Running the comparison is a different
matter from checking its proof: model inference is sent to the model provider
whose credentials the run uses, under that provider's policies.

## Improving a skill

A finished run can be continued. `techtree uplift context` writes a sanitized
account of what that run showed — the objective, the headline numbers, and the
tasks worth looking at — for a host agent to read before proposing a revision.
It carries no hidden expected answer, no grader material, no credential, no
local path, and no transcript of what the evaluated agent replied; the context
lists what it withholds, on the artifact itself.

`techtree uplift prepare` then sets up the second comparison: the skill the
first run measured against the revision, everything else held fixed. The
baseline is pinned to the skill as it was evaluated rather than to whatever is
in a directory now, the revision goes through the same scanner and the same
controlled-comparison check as any first submission, and the data policy is
shown and accepted again before the second run starts. Nothing about that
second run is smaller than the first: it produces its own signed report and its
own local proof.

Techtree does not write the revision. Proposing one is a host agent's job, and
no command here calls a model.

## Development-only runs

Runs produced before WP6 validate a real taskset through Prime Intellect
Verifiers, but the baseline and candidate results come from a fake executor.
No agent is executed, no model credential is read, and no container image is
pulled. Reports from these runs are marked development-only and are blocked
from publication.

## Repository architecture

```text
src/techtree/          the CLI package
  models/              protocol objects: campaign, climb, data policy, artifacts
  cli/                 Typer application, rendering, command groups
  catalog/             the embedded campaign and climb catalog
  skills/              skill scanning and archiving
  manifests/ drafts/   experiment manifests and prepared submissions
  runs/ worker/        run state, events, and the detached worker
  engines/             managed engine registry, installer, and runner
  tasksets/            taskset resolution, membership, and validation
  resources/           embedded catalog and the managed engine bundle
docs/                  architecture, protocol, and binding decisions
schemas/v1alpha1/      exported JSON Schemas for protocol objects
tools/                 generators for the engine bundle, catalog, goldens, schemas
tests/                 unit, contract, and integration suites plus fixtures
```

Dependencies point inward: commands depend on services, services depend on
protocol models, and protocol models depend on nothing in the package.

## Testing

```bash
make test               # unit and contract suites
make test-unit
make test-contract
make test-integration   # real filesystem and subprocess flows
make verifiers-preflight
```

Integration and preflight tests are excluded from the default run because they
are slow and, for preflight, require the pinned Verifiers build. No test reads
or writes a real user home; suites work inside a temporary Techtree home.

## Security assumptions

- Skills are treated as untrusted input. They are scanned and archived, never
  executed by the CLI.
- Signing uses Ed25519 primitives only. There is no live signing, no device
  key, and no identity storage before WP6.
- Provider credentials are never stored in Techtree settings, never logged,
  and never read by the fake executor.
- The CLI prints command suggestions for a person to run; it never executes a
  displayed command string.
- All local state lives under a private Techtree home directory.

## Generated files

Some committed files are generated and must never be hand-edited: the JSON
Schemas under `schemas/`, the protocol goldens under `tests/golden/`, the
embedded catalog under `src/techtree/resources/catalog/`, and the managed
engine bundle under `src/techtree/resources/engines/`.

```bash
make regenerate         # engine bundle, catalog, goldens, schemas, in that order
make generated-check    # regenerate in a temporary tree and fail on drift
```

`make generated-check` never writes to the working tree.

## Protocol documentation

- `docs/protocol-v1alpha1.md` — normative protocol definition
- `docs/architecture.md` — system architecture
- `docs/cli-json-contract.md` — machine-mode CLI contract
- `docs/run-state-machine.md` — run phases and events
- `docs/wp6-handoff.md` — what WP6 may assume
- `docs/decisions/` — binding decisions
