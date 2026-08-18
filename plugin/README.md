# Techtree for Hermes

## Give this repository to your Hermes agent

Paste this into Hermes:

> Read this repository's pinned Hello World installation instructions.
> Explain the exact commands, the prerequisites, what spends money,
> and the privacy terms. Ask before installing the plugin, installing
> the Techtree CLI, or starting a paid run. After the plugin is
> enabled, tell me when to restart Hermes, then continue with Techtree
> Doctor and the Hello World Climb.

Techtree runs a neutral agent and a Skill-enabled agent against the
same toy tasks, shows the measured difference, and creates a signed
local receipt you can verify offline.

This plugin is the operator surface for that: it lets Hermes inspect what a
Climb measures, prepare a run, start it, follow it, and read the result.

Techtree uploads none of your Episodes, Traces, receipts, proof bundles, or
Skill proposals, and publishes nothing. Model inference is still sent to the
model provider you configured, under that provider's policies — a comparison
that runs locally is not a comparison that runs without the network.

The evaluated agent is never the Hermes you are talking to. It is a separate,
pinned agent in a container that receives only what the Climb declares.

The guided introduction is **Techtree Hello World** (`hello-world-climb@1`), a
toy Skill-uplift Climb: it runs the synthetic BranchCode v1 task family with
and without the `hello-world-starter-v1` Skill, then offers one guided
revision. It shows how the mechanism works. It is not a measure of broad
capability.

## Install

Install only from the exact pinned guide at
[techtree.sh/start](https://techtree.sh/start). The guide reads the install
vector from the active BootstrapRelease, links the exact 40-character plugin
commit, and shows the command argument for argument. Do not copy a branch name,
a floating package version, or an example placeholder into an install command.

Supported host: Hermes 0.20.1. The evaluated subject remains the separately
pinned Hermes 0.19.0 named by the Campaign. The release this plugin belongs to
is recorded in `release-core.json`.

Installing the plugin does not install Techtree itself. Ask in the
conversation — "is Techtree ready?" — and the plugin will tell you what is
missing and show you the exact command to install it. That command always
needs your approval and installs only the version pinned by the same release.

After the plugin is installed and enabled, restart Hermes once so the tools
load. The plugin then asks again before installing the Techtree CLI. A paid
comparison has its own separate approval after Doctor and the run review.

## What loading the plugin does

It reads two files that shipped inside the plugin, then tells Hermes which
tools exist. That is the whole of it.

Loading the plugin never installs software, never reaches the network, never
starts Docker, never runs Techtree, and never calls a model. This is enforced
by a test that seals off every way of starting a process, opening a socket, or
writing a file, and then requires the plugin to load anyway
(`tests/contract/test_no_registration_side_effects.py`).

## Commands

In any session:

```text
/techtree setup      is Techtree installed, and is this machine ready?
/techtree climbs     what this build offers
/techtree demo       prepare Techtree Hello World, stopping before it spends
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
channels.py          how compact an answer has to be
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

## Bounded answers

Everything except `watch` answers in the conversation itself. Those answers are
compact, carry no terminal control codes, and are bounded — and when an answer
is cut, it says so and names the command that shows all of it. When nothing
tells the plugin how much room it has, it assumes the smaller budget, because
an answer that fits a narrow window is also fine in a wide one.

## What it writes, and turning it off

The plugin writes to exactly one place, for one reason, and only during a
guided revision. Everything else it remembers lives in the conversation and
is gone when the conversation is.

```text
${XDG_STATE_HOME:-~/.local/state}/techtree-hermes/proposals/
```

When you ask for a revision, the proposed Skill is written there so Techtree
can be handed a path to scan. Techtree takes its own snapshot immediately, and
the plugin deletes its copy in the same call. The directory is created
`0700` and the file `0600`, so nothing there is readable by other users of the
machine. If a deletion ever fails, the answer says so and names the directory
that still exists — the plugin does not fail that quietly, because what is
left behind is your own Skill text.

Nothing else persists. The plugin keeps draft identifiers, run identifiers and
proof paths in memory for the length of a session; it writes no configuration
file, no cache, no log, and no credential anywhere.

### Disabling

```bash
hermes plugins disable techtree
```

The tools, the `/techtree` command and the session hooks stop being offered.
Nothing on disk changes.

### Removing

```bash
hermes plugins remove techtree
rm -rf "${XDG_STATE_HOME:-$HOME/.local/state}/techtree-hermes"
```

The first command removes the plugin. The second removes the staging directory
described above, which is the only thing the plugin can leave behind — you can
look inside it first; on a healthy machine it is empty.

Two things are deliberately **not** removed by either command, because they are
not the plugin's to delete:

- **Techtree's own home** — your runs, drafts, proof bundles and the evaluation
  engine. It belongs to the Techtree CLI, not to this plugin. Remove the CLI
  with `uv tool uninstall techtree` and delete its home if you want it gone.
- **Anything held by your model provider.** A guided revision sends the Skill
  text and the sanitized improvement context to the provider behind the agent
  you are talking to, and an evaluated run sends its tasks to the provider the
  run is configured with. What those providers retain is governed by their
  policies, and no command here reaches it.

## Release status

This build carries the concrete Climb v0.1 release contract. It names the
starter Skill and the founder-frozen `skill-improver`, so the installed plugin
can prepare Techtree Hello World and offer one guided revision after a finished
comparison. The stable release remains an inactive candidate until the Gate-2
packet is approved. Repository presence alone is not a public release signal;
use the exact pinned installation guide.
