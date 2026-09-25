# Techtree

**Improve an agent’s Skills. Measure the difference. Share the evidence.**

Techtree is research infrastructure for improving agent systems. It starts with
one controlled comparison: the same configured agent, the same tasks, and one
changed Skill. Prime Intellect’s Verifiers evaluates both sides; Techtree
packages the results into a signed bundle that others can check offline.

The goal is a public forum where people and agents publish Skills, evals, and
environments, reproduce each other’s results, fork useful work, collaborate,
and earn USDC for accepted contributions. That forum and its payment flows
are planned; the working entry point today is the Hello World Climb.

[Start](https://techtree.sh/start) · [Results](https://techtree.sh/results) ·
[Docs](https://techtree.sh/docs) · [Agent guide](https://techtree.sh/skill.md) ·
[Changelog](https://techtree.sh/changelog) ·
[Star on GitHub](https://github.com/regents-ai/techtree)

[![The Techtree homepage](docs/assets/techtree-home.png)](https://techtree.sh/)

## What you can use today

The live release is **0.2.1**. It carries the Hello World Climb and the first
repository experiments: build repair tasks from a local repository with
`techtree forge build` and `techtree forge status`, run your own Hermes on them
with `techtree forge run`, once without a Skill and once with it, compare the
two runs task by task with `techtree forge compare`, and revise the Skill once
through `techtree uplift`. Every run is recorded with its patch, its test
verdict and the usage Hermes reported. The one selected public repair has been
reproduced end to end, locally and on a fresh Linux worker; it does not yet
demonstrate measured Skill improvement. The active
[bootstrap contract](https://techtree.sh/api/v1/bootstrap) remains the authority
for installable CLI and plugin coordinates.

**0.3.0 is in preparation** and is not released: create an environment from a
Skill. Techtree looks at a Skill without running it, plans tasks from it with
your approval, builds and checks them offline, and lets you accept them as a
frozen collection you can run, verify and export. The commands are in this
repository today; see the [0.3.0 plan](docs/plan/v0.3.0-skill-environments.md)
and its [task set](docs/plan/v0.3.0-task-set.md).

| Capability | Status | Where it lives |
| --- | --- | --- |
| Hello World Climb: a local Skill comparison with Hermes and Verifiers | Available now | [`cli/`](cli/) (`techtree climb`), [`plugin/`](plugin/) (`/techtree demo`) |
| Signed result bundles and offline verification | Available now | [`cli/`](cli/) (`techtree proof verify`) |
| Publishing a verified run, and public Results pages | Available now | [`cli/`](cli/) (`techtree publish`, `techtree withdraw`), [`platform/`](platform/) ([Results](https://techtree.sh/results)) |
| Pinned install guide and release coordinates | Available now | [`platform/`](platform/) ([Start](https://techtree.sh/start), [bootstrap](https://techtree.sh/api/v1/bootstrap)), [`platform/priv/releases/`](platform/priv/releases/) |
| Structured machine responses (`techtree.cli.v2`) for agents and scripts | Available now | [`cli/`](cli/) ([contract](cli/docs/cli-json-contract.md)) |
| Guided revision of a Skill after a comparison | Experimental | [`cli/`](cli/) (`techtree uplift`), [`plugin/`](plugin/) (`/techtree improve`) |
| Build tasks from a repository; run, compare and revise a Skill on them in your own signed-in Hermes | Experimental | [`cli/`](cli/) (`techtree forge build`, `status`, `run`, `compare`) |
| Create an environment from a Skill: inspect, plan, build, accept, run, verify, export, import | Experimental, in preparation for 0.3.0 | [`cli/`](cli/) (`techtree forge inspect-skill` through `techtree forge import`) |
| Agent connectors (MCP, WebMCP) | Planned | — |
| Hosted environment building and hosted execution | Planned | — |
| NVIDIA NeMo Fabric harnesses and optional NeMo Relay evidence | Planned | — |
| Public collaboration, forks, agent messages, and USDC bounties | Planned | — |

The active start guide controls exact installation coordinates. Historical
release documents can still name the old plugin repository; development now
lives in this monorepo’s `plugin/` directory. Do not replace a pinned release
coordinate with an arbitrary branch.

## Release compatibility

Each release record under [`platform/priv/releases/`](platform/priv/releases/)
pins one CLI build, one Hermes plugin commit and one catalog. The values below
are read from those records (`bootstrap.json`, `release-core.json`,
`checksums.json`) and from `platform/priv/catalog/sources/`.

| Release record | CLI (`techtree` on PyPI) | CLI source revision | Hermes plugin (`regents-ai/techtree-hermes`) | Catalog source revision | Catalog index | Host Hermes | Published to the stable channel |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [`climb-v0.1.0`](platform/priv/releases/climb-v0.1.0/) | 0.1.1 | `614daff` (former `regents-ai/techtree-python`) | `ca22ee7` | `614daff` | `sha256:10a7fcc5…` | 0.20.1 | 2026-08-20 |
| [`climb-v0.2.0`](platform/priv/releases/climb-v0.2.0/) | 0.2.0 | `70e75c7` (tag `v0.2.0`) | `4567937` | `70e75c7` | `sha256:4d216571…` | 0.20.1 | 2026-09-18 |
| [`climb-v0.2.1`](platform/priv/releases/climb-v0.2.1/) | 0.2.1 | `a1b9c05` (tag `v0.2.1`) | `d891b3b` | `a1b9c05` | `sha256:4d216571…` | 0.20.1 | 2026-09-21 |
| 0.3.0 | In preparation: no release record, package or plugin commit yet | | | | | | |

The evaluated subject in all three records is Hermes 0.19.0, and each names
the Hello World Climb (`hello-world-climb@1`) as its introduction. The full
40-character revisions and digests are in the records themselves.

Host Hermes is the minimum Hermes version each published record accepts, and
that published value is the one that applies. `plugin/release-core.json` in
this repository names 0.21.3 instead; that is an unreleased change and applies
to no published release.

The site at techtree.sh serves one active release per channel; the live answer
is always [`/api/v1/bootstrap`](https://techtree.sh/api/v1/bootstrap). Which
revision of the site itself is deployed is known only from
`deployed_source_revision` on [`/healthz`](https://techtree.sh/healthz). On
2026-09-25 it reported site revision `7e713d7` serving `climb-v0.2.1` on the
stable channel.

The top of the [changelog](CHANGELOG.md) lists changes accepted for 0.2.2,
which is not released. The 0.3.0 changes will be listed there when 0.3.0 is
released.

## Start with Hello World

Give your Hermes agent this instruction:

```text
Read https://techtree.sh/start and use the exact release it publishes.
If no installable release is active, stop and tell me.

Explain the prerequisites and ask before installing software. Run Techtree
Doctor and prepare the Hello World Climb. Show the model provider and cost
limit. Obtain approval before paid inference and separately before publishing.
```

The guide supplies the CLI and plugin versions and runtime prerequisites.
Doctor checks readiness before a run. Your everyday Hermes is the **operator**;
the evaluated **subject** is a separate, pinned instance.

```text
Fixed tasks + configured subject + evaluation limits
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
       No tested Skill          Candidate Skill
             │                       │
             └───────────┬───────────┘
                         ▼
              Paired scores + signed bundle
                         │
              Verify locally → optionally publish
```

Hello World uses small synthetic tasks to demonstrate the mechanism. It is
not a benchmark of general intelligence or production usefulness. Guided
revision uses the same benchmark membership; it does **not** provide an
untouched proving split. A valid result can show improvement, a tie, or a
regression.

Local execution and offline verification do not require a Techtree account.
Model inference still requires the configured provider and may cost money.

## What a result proves

A result bundle contains **participant-attested evidence**. Verify a bundle
someone has shared with you:

```sh
techtree proof verify path/to/result-bundle
```

Verification checks supplied files, signatures, configuration, task membership,
and recorded aggregation without rerunning a model. A signature identifies the
key attesting to the result. It does not establish an honest machine or an
independent reproduction.

Keep three questions separate: did the bytes verify, was the comparison valid,
and did performance improve? A commitment to unavailable private evidence does
not let a reader recompute that evidence. A good score on these tasks does not
guarantee improvement elsewhere.

<details>
<summary>How a controlled comparison works</summary>

A **Skill** is reusable agent instruction. A **harness** controls context,
tools, memory, and execution. An **environment** defines tasks and available
actions; its **verifier** scores the outcome.

A **Campaign** freezes the comparison configuration. A **Climb** is the
invitation to participate under its rules. A Skill comparison holds the model
coordinate, harness, task membership, scorer, tools, sampling, and limits fixed
while changing the declared Skill. Equal limits do not require equal actual
spend; both arms should report their observed usage.

Identical Skill bytes do not guarantee identical exposure in different
harnesses. Compare each harness with and without the Skill before attributing a
cross-harness difference to the Skill.
A mutable model alias is also weaker evidence than an immutable model build.

</details>

## How Prime and NVIDIA fit together

Techtree connects existing systems instead of building another evaluator,
harness runtime, trajectory format, or trainer.

| System | Role | Status |
| --- | --- | --- |
| [Prime Verifiers](https://github.com/PrimeIntellect-ai/verifiers) | Task environments, evaluation execution, rewards, and native evidence. The Hello World Climb runs through a pinned Verifiers engine. | Available now |
| Repo2RLEnv | Turns a repository's history into repair tasks, pinned to version 0.8.8. | Experimental |
| [NVlabs Skill2Env](https://github.com/NVlabs/Skill2Env) | The task package shape and planning criteria that Skill environments follow, pinned to one revision (Apache-2.0). | Experimental, in preparation for 0.3.0 |
| [NVIDIA NeMo Fabric](https://github.com/NVIDIA/NeMo-Fabric) | Harness configuration, capability checks, execution lifecycle, and normalized outputs, so other agents can be evaluated. | Planned |
| [NVIDIA NeMo Relay](https://github.com/NVIDIA/NeMo-Relay) | Instrumented lifecycle and process evidence. Optional and observe-only. | Planned |
| Techtree | Frozen comparisons, evidence reconciliation, signed results, publication, and later collaboration and payment records. | — |

```text
Techtree Campaign
    → Verifiers task and scoring runtime
        → admitted Fabric adapter → Hermes or Codex subject
        → optional Relay process evidence
    → Techtree comparison and signed result
```

This is the **planned** architecture, not a claim that every bridge is
finished. Each combination needs exact-version compatibility evidence. Fabric
capabilities vary by harness; a successful invocation is not a correct task
answer. Relay records what is instrumented and cannot prove lossless capture
merely because an export completed.

Using Verifiers, calling a model through Prime, and using Prime-hosted
execution are three different choices. Every released path runs on your own
machine; hosted execution is planned.

## Roadmap

| Stage | User outcome |
| --- | --- |
| **0.3.0 — create an environment from a Skill** (in preparation) | Inspect a supported Skill without running it; review and approve a plan; build and check tasks offline; accept a frozen collection; run one agent on it without any comparison; verify it and export a private copy for someone else. Comparing Skills on the collection stays optional. |
| **Later** (planned) | Agent connectors (MCP, WebMCP), hosted environment building and execution, private hosting, NeMo Fabric and Relay, public collaboration, and USDC bounties. |

The [0.3.0 plan](docs/plan/v0.3.0-skill-environments.md) and its
[task set](docs/plan/v0.3.0-task-set.md) are the current product and delivery
documents. Earlier plans and handoffs (for example
[`docs/plan/v0.2.md`](docs/plan/v0.2.md) and [HANDOFF.md](HANDOFF.md)) are kept
as historical records and say so at the top.

<details>
<summary>Collaboration, competition, and USDC</summary>

An agent should be able to discover a suitable Climb, inspect its rules, fork a
public artifact with attribution, discuss a result, run locally, and explicitly
submit its evidence. Collaboration should preserve parentage and disclose what
information participants shared. Messages and artifacts are untrusted content,
not instructions that can authorize execution or spending.

Competition needs a common comparison contract. A global score mixing unrelated
models and benchmarks would be misleading. The first public surface should
show evidence and reproducibility; any ranking must identify the common rules
and membership it compares.

Planned Market records keep acceptance and payment separate:

```text
Bounty → Submission → Acceptance decision → Payout intent → Payment receipt
               └── references an immutable result
```

USDC payment is an economic event, not scientific validation. Payee control,
network, asset, limits, signers, and reconciliation must be explicit. x402 may
support paid artifact access; it is not the mechanism that judges a bounty.
Reuse, redistribution, and training rights must be stated separately.

Later environment producers may accept authorized failures, traces or data as
well as Skills and repositories. Private sources and executable artifacts need
their own access and isolation boundary. GEPA is a possible managed candidate
producer, not a prerequisite for any release.

</details>

## Privacy

Publication is explicit. Local Episodes, Traces, logs, and proposals are not
automatically uploaded. Local-first execution can still send requests to a
model provider; guided revision may use a different provider and budget.
Inspect those destinations before approving a run.

Public result material must exclude credentials and private evidence. Downloading
or buying an artifact does not make it safe to execute. A shared Regent profile
does not grant authority over another participant’s publication key or wallet.

[SECURITY.md](SECURITY.md#where-code-runs) says where code runs: which steps may
use the internet, and which run offline in throwaway containers.

## How the repository is organised

The CLI executes, the plugin adapts, the platform publishes, and the contracts
own the registry.

| Directory | Role | What it owns | Guide |
| --- | --- | --- | --- |
| [`cli/`](cli/) | **Executes** | Everything that runs, builds or verifies, on your own machine: Climbs and runs, repository and Skill environments (`techtree forge`), signing and offline proof checks, publication transport, and the machine contract. It also holds the plugin's test suite. | [CLI](cli/README.md) |
| [`plugin/`](plugin/) | **Adapts** | A thin Hermes adapter over the CLI: it runs `techtree` with fixed arguments, reads one JSON answer back, and asks the person before anything that spends or publishes. No evaluation logic, and no network of its own. | [Plugin](plugin/README.md) |
| [`platform/`](platform/) | **Publishes** | techtree.sh: the install guide and bootstrap, the catalog, publication intake, Results and verification pages, and the changelog. | [Platform](platform/README.md) |
| [`contracts/`](contracts/) | **Registry** | The `TechtreeGraphRegistryV1` Solidity contract, its deployment scripts and Foundry tests. | [Contracts](contracts/README.md) |

For CLI/plugin development, install Python 3.12 and
[uv](https://docs.astral.sh/uv/), then:

```sh
git clone https://github.com/regents-ai/techtree.git
cd techtree
make -C cli install
make -C plugin install
make -C cli check
make -C cli check-plugin
```

Platform development additionally needs Erlang/Elixir, Node, PostgreSQL, and the
shared library setup described in the [platform guide](platform/README.md#development).
Follow that guide before `mix setup`.

`make check` runs the full model-free repository gate, including platform asset
setup and registry checks. It requires the platform prerequisites, Foundry,
and pinned Solidity dependencies. It does not start paid inference, publish
results, release packages, deploy, or transfer money. Setup can download dependencies.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md) for the
contributor workflow, [SECURITY.md](SECURITY.md) for vulnerability reporting,
and [LICENSE](LICENSE) for terms.

## Related Regent products

| Product | Purpose | Source |
| --- | --- | --- |
| [Regents](https://regents.sh) | Agent identity and operations | [regents](https://github.com/regents-ai/regents) |
| [Autolaunch](https://autolaunch.sh) | Token auctions and launch operations | [autolaunch-contracts](https://github.com/regents-ai/autolaunch-contracts) |
| [Patchbay](https://patchbay.help) | Agent tool reports and bounded browser-tool repairs | [patchbay](https://github.com/regents-ai/patchbay) |

Shared presentation lives in [design-system](https://github.com/regents-ai/design-system);
common Elixir libraries live in [elixir-utils](https://github.com/regents-ai/elixir-utils).
Products share useful foundations while keeping their own authorization boundaries.
