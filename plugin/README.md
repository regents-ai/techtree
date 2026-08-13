# Techtree for Hermes

Run a controlled Skill comparison on your own machine, from the conversation
you are already in.

Techtree measures whether a Skill actually improves an agent. It runs the same
pinned task set twice — once without the Skill, once with it — inside Docker,
records what happened, and produces a locally signed result you can check
offline. This plugin is the operator surface for that: it lets Hermes inspect
what a Climb measures, prepare a run, start it, follow it, and read the
result. Nothing is uploaded, and nothing is published.

The evaluated agent is never the Hermes you are talking to. It is a separate,
pinned agent in a container that receives only what the Climb declares.

## Install

The plugin is installed at an exact commit, and Hermes must be restarted
afterwards so it loads:

```bash
hermes plugins install regents-labs/techtree-hermes \
  --ref <full-40-character-plugin-commit> \
  --enable
```

Supported host: Hermes 0.20.0. The release the plugin is pinned to is
recorded in `release-core.json`.

Installing the plugin does not install Techtree itself. Ask in the
conversation — "is Techtree ready?" — and the plugin will tell you what is
missing and show you the exact command to install it. That command always
needs your approval, and only ever installs the one pinned version.

## What loading the plugin does

It reads two files that shipped inside the plugin, then tells Hermes which
tools exist. That is the whole of it.

Loading the plugin never installs software, never reaches the network, never
starts Docker, never runs Techtree, and never calls a model. This is enforced
by a test that seals off every way of starting a process, opening a socket, or
writing a file, and then requires the plugin to load anyway
(`tests/contract/test_no_registration_side_effects.py`).

## Commands

In any session, including a phone:

```text
/techtree setup      is Techtree installed, and is this machine ready?
/techtree climbs     what this build offers
/techtree demo       prepare the introduction, stopping before it spends
/techtree status     how a run is going
/techtree cancel     stop a run
/techtree result     the finished result
/techtree verify     check a local proof, offline
/techtree improve    what a finished run says about itself
```

In a terminal, where Techtree's own rendered output belongs:

```text
hermes techtree doctor | demo | status <run> | watch <run> | result <run> | verify <path>
```

`watch` follows a run live in your terminal. Nothing the model can call ever
holds an open watch — a conversation that is waiting is a conversation that
has stopped.

## Check the plugin

```bash
make doctor
```

Reports whether this build is sound — its manifest, its tool descriptions, its
release bytes, and whether its code stays within the standard library — and
whether the Techtree CLI and `uv` are present on this machine. A missing CLI is
a warning with a next step, not a failure: the plugin is meant to work on a
machine where Techtree was never installed.

## How it talks to Techtree

Every scientific thing this plugin can cause happens by running the `techtree`
command with a fixed list of arguments and reading back one JSON answer. There
is no second path: no shell, no imported Techtree code, no network of its own.
The plugin adds the machine-output flags itself, so an answer is never coloured
or half-interactive, and it accepts exactly one well-formed answer — anything
else is treated as the two sides disagreeing about the contract rather than
something to guess at.

The plugin and the installed Techtree also have to belong to the same release.
Both carry the identical `release-core.json`, published under the SHA-256 of
the file itself, so agreement can be checked with `shasum` in either
repository — or by asking the installed CLI what release it belongs to:

```bash
make release-core-cli
```

## Repository layout

```text
plugin.yaml          what the host reads: name, tools, hooks
release-core.json    the release this build is pinned to (generated)
__init__.py          registration
constants.py         fixed values; no mutable state
errors.py            plugin-local errors and secret scrubbing
models.py            local models and strict parsers
schemas.py           the model-visible tool schemas
release.py           the pinned release, its digest, and its cross-checks
bridge.py            the only path from the plugin into Techtree
doctor.py            the plugin's own doctor
commands.py          `/techtree` and `hermes techtree ...` registries
hooks.py             session lifecycle registry
channels.py          terminal or phone, and what changes
commands.py          /techtree and hermes techtree …
hooks.py             session start and end
state.py             the identifiers a conversation keeps
tools/               the tools the agent calls
services/            the container assembled during registration
skills/              bundled read-only operator Skills
scripts/             repository tooling
tests/               unit, contract, and integration tests
```

## Development

```bash
make install    # sync the tooling environment
make check      # format, lint, types, doctor, tests
```

The plugin runtime uses only the Python standard library, and never imports
Techtree's Python package: the CLI's JSON envelope is the only boundary
between the two. `make doctor` fails the build if that stops being true.

The contract tests can also be run against a real Techtree CLI:

```bash
make test-cli-contract TECHTREE_CLI_ARGV="uv run --project ../techtree-python techtree"
```

Only read-only commands are used there.

## What it remembers

Only identifiers: which draft, which run, which proof — never a key, never a
Skill's text, never anything from inside a run. They live for the length of
the conversation, and nothing is lost when it ends, because Techtree holds the
run itself: ask about a run by its identifier and the answer comes back from
Techtree, not from anything the plugin was keeping.

## On a phone

Everything except `watch` works from a messaging gateway. Answers are compact,
carry no terminal control codes, and are bounded — and when an answer is cut,
it says so and names the command that shows all of it. When nothing tells the
plugin which kind of session it is in, it assumes a phone, because output that
is safe on a phone is also fine in a terminal.

## Not here yet

This is an early build. The guided introduction stops short of preparing a
comparison until a published release names its starter Skill, and proposing a
revised Skill is not part of it. `make doctor` reports exactly what a build
implements. The operator walkthroughs, privacy notes, and removal instructions
arrive with the release documentation.
