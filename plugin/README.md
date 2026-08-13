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

## Check the plugin

```bash
make doctor
```

Reports whether this build is sound — its manifest, its tool descriptions, its
release bytes, and whether its code stays within the standard library — and
whether the Techtree CLI and `uv` are present on this machine. A missing CLI is
a warning with a next step, not a failure: the plugin is meant to work on a
machine where Techtree was never installed.

## Repository layout

```text
plugin.yaml          what the host reads: name, tools, hooks
release-core.json    the release this build is pinned to (generated)
__init__.py          registration
constants.py         fixed values; no mutable state
errors.py            plugin-local errors and secret scrubbing
models.py            local models and strict parsers
schemas.py           the model-visible tool schemas
release.py           embedded release loading and digests
doctor.py            the plugin's own doctor
commands.py          `/techtree` and `hermes techtree ...` registries
hooks.py             session lifecycle registry
tools/               tool handlers
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

## Not here yet

This is an early build. The tool handlers, command surfaces, session hooks,
and bundled Skills land in the following work packages; `make doctor` reports
exactly which declared tools and hooks a build implements. The operator
walkthroughs, privacy notes, and removal instructions arrive with the release
documentation.
