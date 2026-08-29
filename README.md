# Techtree

**Improve a Skill. Prove it worked.**

Opinionated Stack for Agent Skill Uplift.
Built on Prime Intellect and NVIDIA NeMo.

[![The Techtree homepage](docs/assets/techtree-home.png)](https://techtree.sh/)

> [!IMPORTANT]
> **This repository is a placeholder for the future Techtree monorepo.** The
> v0.1 source still lives in the three repositories below. Use their READMEs
> for installation, development, and release instructions.

## Three repositories, one system

| Component | Current source | What it does |
| --- | --- | --- |
| **CLI and campaign kernel** | [`regents-ai/techtree-python`](https://github.com/regents-ai/techtree-python) | Runs pinned baseline and candidate evaluations, manages the local campaign lifecycle, signs receipts, and verifies proof bundles offline. |
| **Hermes plugin** | [`regents-ai/techtree-hermes`](https://github.com/regents-ai/techtree-hermes) | Gives Nous Research's Hermes an approval-aware operator surface for Techtree. It explains each step, invokes the CLI with fixed arguments, and relays structured results; evaluation logic stays in the CLI. |
| **Public platform** | [`regents-ai/techtree-ash`](https://github.com/regents-ai/techtree-ash) | Powers [techtree.sh](https://techtree.sh/): the pinned installation guide, campaign catalog, documentation, local-proof explanation, and public list of runs participants choose to publish. |

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
signed local receipt
 verifies offline on any machine holding the proof bundle
 │
 └── optional publish ──▶ techtree.sh published runs
```

The CLI is the local source of truth for a run. The plugin is a conversational
operator, not a second evaluation engine. The platform helps people discover,
install, and inspect Techtree, but it is not required to run a comparison or
verify a local proof.

Publishing is optional. A published run sends its signed proof material to the
platform; private Episodes and Traces stay on the participant's machine.

## Normal user flow

1. Start with the pinned guide at [techtree.sh/start](https://techtree.sh/start).
2. Let the Hermes plugin explain the prerequisites and request approval before
   installing software or starting paid model inference.
3. Run Techtree Doctor to check the local environment and print the exact next
   action.
4. Run a Climb: Techtree holds the task set, model, harness, tools, and budget
   fixed while changing the declared Skill.
5. Inspect the result and verify its signed proof locally, without a Techtree
   account or network connection.
6. If desired, publish the signed run so others can inspect it on the platform.

## Work in the current repositories

Each component remains independently buildable and keeps its own detailed
documentation:

| Component | Documentation | Main check |
| --- | --- | --- |
| CLI | [`techtree-python` README](https://github.com/regents-ai/techtree-python#readme) | `make check` |
| Hermes plugin | [`techtree-hermes` README](https://github.com/regents-ai/techtree-hermes#readme) | `make check` |
| Public platform | [`techtree-ash` README](https://github.com/regents-ai/techtree-ash#readme) | `mix check` |

The plugin's full integration suite is run from a sibling CLI checkout with
`make test-plugin`. Release work continues in the component repositories until
the monorepo migration is complete.

## Planned monorepo

After the frozen v0.1 release, the three repositories will move here with their
full Git histories preserved:

```text
techtree/
├── cli/          # current techtree-python
├── plugin/       # current techtree-hermes
├── platform/     # current techtree-ash
├── README.md
├── CONTRIBUTING.md
├── AGENTS.md
├── SECURITY.md
├── LICENSE
├── CODEOWNERS
├── Makefile
└── .github/
```

The component READMEs will remain at `cli/README.md`, `plugin/README.md`, and
`platform/README.md`. Until those directories appear, follow the links above;
this repository is an overview, not an installable build.
