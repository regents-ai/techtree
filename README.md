# Techtree

**Improve a Skill. Prove it worked.**

Techtree runs a fixed evaluation twice—once without a Skill and once with the
candidate Skill—then produces a signed result that can be verified offline.
The public platform at [techtree.sh](https://techtree.sh/) lets participants
optionally publish those results.

[Website](https://techtree.sh) · [CLI](cli/README.md) · [Agent guide](https://techtree.sh/skill.md) · [Star on GitHub](https://github.com/regents-ai/techtree)

[![The Techtree homepage](docs/assets/techtree-home.png)](https://techtree.sh/)

## One repository, four components

| Component | Source | What it does |
| --- | --- | --- |
| **CLI and campaign kernel** | [`cli/`](cli/) | Runs pinned baseline and candidate evaluations, manages the local campaign lifecycle, signs receipts, and verifies result bundles offline. |
| **Hermes plugin** | [`plugin/`](plugin/) | Gives Hermes an approval-aware operator surface for Techtree. It explains each step, invokes the CLI with fixed arguments, and relays structured results; evaluation logic stays in the CLI. |
| **Public platform** | [`platform/`](platform/) | Powers [techtree.sh](https://techtree.sh/): installation, campaign discovery, documentation, and the public list of results participants choose to publish. |
| **Registry contracts** | [`contracts/`](contracts/README.md) | Owns Techtree graph registry Solidity, scripts and local tests. |

## Quickstart

To run the released Hello World Climb, use the
[pinned guide at techtree.sh/start](https://techtree.sh/start). It is the source
for the exact plugin commit, CLI version, prerequisites, and approval steps.
Techtree Doctor checks the machine and prints the next action before a run can
start paid model inference.

For local development, choose the component you need. The CLI uses Python 3.12
and uv; the platform uses Erlang/Elixir, Node and PostgreSQL plus the shared
`regent_ui` library. Follow [platform setup](platform/README.md#development)
before running `mix setup`. The full `make check` also runs registry contract
checks and therefore requires Foundry and its pinned Solidity dependencies.
A platform-only change does not require those contract downloads.

```sh
# From the repository root, for CLI/plugin work:
make -C cli install
make -C plugin install
make -C cli check
make -C cli check-plugin
```

The model-free checks do not start inference, publish a result, deploy the
platform or release a package. Real model runs can spend the participant's budget.

## Roadmap

Techtree v0.2 is the execution-provenance and subject-portability release. Its
binding scope, work packages, and release gates are in the
[v0.2 implementation contract](docs/plan/v0.2.md); the actionable backlog is
in the [v0.2 ticket ledger](docs/v0.2/TICKETS.md).

## How they work together

```text
you
 │
 ▼
Hermes + Techtree plugin
 explains the flow, asks for approval, and operates the CLI
 │ fixed command arguments · one machine-readable response
 ▼
Techtree CLI
 runs the same pinned agent on the same fixed tasks
 │ baseline Skill → changed Skill
 ▼
pinned evaluation environment
 executes the comparison and returns measurements
 │
 ▼
signed local result
 verifies offline on any machine holding the result bundle
 │
 └── optional publish ──▶ techtree.sh published results
```

The CLI is the local source of truth for a run. The plugin is a conversational
operator, not a second evaluation engine. The platform helps people discover,
install, and inspect Techtree, but it is not required to run a comparison or
verify a local result.

Publishing is optional. A published run sends its signed result material to
the platform; private Episodes and Traces stay on the participant's machine.

The normal user flow is:

1. Start with the pinned guide at [techtree.sh/start](https://techtree.sh/start).
2. Let the Hermes plugin explain the prerequisites and request approval before
   installing software or starting paid model inference.
3. Run Techtree Doctor to check the local environment and print the exact next
   action.
4. Run a Climb: Techtree holds the task set, model, harness, tools, and budget
   fixed while changing the declared Skill.
5. Inspect the result and verify its signed bundle locally, without a Techtree
   account or network connection.
6. If desired, publish the signed result so others can inspect it on the
   platform.

## Work in the monorepo

The root check runs every model-free component gate and the CLI/plugin
integration suite:

```sh
make check
```

For component-specific setup and commands:

| Component | Documentation | Main check |
| --- | --- | --- |
| CLI | [`cli/README.md`](cli/README.md) | `make -C cli check` |
| Hermes plugin | [`plugin/README.md`](plugin/README.md) | `make -C plugin check` |
| Public platform | [`platform/README.md`](platform/README.md) | `cd platform && mix check` |

The plugin's complete test suite is intentionally owned by the CLI and runs
with `make -C cli check-plugin`. See [CONTRIBUTING.md](CONTRIBUTING.md) for the
repository workflow and [SECURITY.md](SECURITY.md) for private vulnerability
reporting.

## Repository layout

```text
techtree/
├── cli/          # Python CLI, campaign kernel, and plugin test suite
├── plugin/       # Hermes plugin package and Skills
├── platform/     # Ash/Phoenix public platform
├── contracts/    # Registry Solidity and verification
├── docs/         # shared architecture and migration records
├── README.md
├── CONTRIBUTING.md
├── AGENTS.md
├── SECURITY.md
├── LICENSE
├── CODEOWNERS
└── Makefile
```

Hermes installs the plugin directly from the [`plugin/`](plugin/) subdirectory.

## Related products

| Product | Use it for | Website | Source |
| --- | --- | --- | --- |
| Regents | Agent identity, operations, staking and redemption | [regents.sh](https://regents.sh) | [Regents](https://github.com/regents-ai/regents) |
| Autolaunch | Token auctions and launch operations | [autolaunch.sh](https://autolaunch.sh) | [Autolaunch](https://github.com/regents-ai/autolaunch-contracts) |
| Patchbay | Agent tool reports and bounded WebMCP repair | [patchbay.help](https://patchbay.help) | [Patchbay](https://github.com/regents-ai/patchbay) |
| Techtree | Controlled Skill evaluations and verifiable results | [techtree.sh](https://techtree.sh) | [Techtree](https://github.com/regents-ai/techtree) |

Each product owns its API, CLI and authorization. A login, payment or published
result on one product does not grant permissions on another. Shared presentation
lives in [design-system](https://github.com/regents-ai/design-system); common Elixir
libraries live in [elixir-utils](https://github.com/regents-ai/elixir-utils).
