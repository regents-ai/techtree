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
[Star on GitHub](https://github.com/regents-ai/techtree)

[![The Techtree homepage](docs/assets/techtree-home.png)](https://techtree.sh/)

## What you can use today

**Released baseline: v0.1.1. In development: v0.2.0.** The public
[bootstrap contract](https://techtree.sh/api/v1/bootstrap) advertised v0.1.1
when checked on September 6, 2026. Development on `main` includes partial v0.2
protocol work; it is not the released installation.

| Capability | Status |
| --- | --- |
| Local Hermes/Verifiers Skill comparisons | Released Hello World workflow |
| Signed result bundles and offline verification | Released |
| Explicit publication and public result inspection | Released |
| Hermes-guided replacement Skill | Experimental released workflow |
| Fabric-backed Hermes and Codex, optional Relay evidence, CLI v2 | v0.2 implementation work; not a released end-to-end path |
| Public collaboration, forks, agent messages, and USDC bounties | Planned |
| Prime-hosted execution and proof-backed Library | Planned for v0.2.x |
| Foundry and separate private proving | Planned for v0.3 |

The active start guide controls exact installation coordinates. Historical
release documents can still name the old plugin repository; development now
lives in this monorepo’s `plugin/` directory. Do not replace a pinned release
coordinate with an arbitrary branch.

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
harnesses. v0.2 adds a Skill projection record distinguishing intended files,
observed exposure, and unknown loading behavior. Compare each harness with and
without the Skill before attributing a cross-harness difference to the Skill.
A mutable model alias is also weaker evidence than an immutable model build.

</details>

## How Prime and NVIDIA fit together

Techtree connects existing systems instead of building another evaluator,
harness runtime, trajectory format, or trainer.

| System | Role in the target integration |
| --- | --- |
| [Prime Verifiers](https://github.com/PrimeIntellect-ai/verifiers) | Task environments, evaluation execution, rewards, and native evidence. Already used by the released path. |
| [NVIDIA NeMo Fabric](https://github.com/NVIDIA/NeMo-Fabric) | Harness configuration, capability checks, execution lifecycle, and normalized outputs. Selected for v0.2 subject portability. |
| [NVIDIA NeMo Relay](https://github.com/NVIDIA/NeMo-Relay) | Instrumented lifecycle and process evidence. Optional, observe-only in the v0.2 comparison path. |
| Techtree | Frozen comparisons, evidence reconciliation, signed results, publication, and later collaboration and payment records. |

```text
Techtree Campaign
    → Verifiers task and scoring runtime
        → admitted Fabric adapter → Hermes or Codex subject
        → optional Relay process evidence
    → Techtree comparison and signed result
```

This is the **v0.2 target architecture**, not a claim that every bridge is
finished. Each combination needs exact-version compatibility evidence. Fabric
capabilities vary by harness; a successful invocation is not a correct task
answer. Relay records what is instrumented and cannot prove lossless capture
merely because an export completed.

Using Verifiers, calling a model through Prime, and using Prime-hosted
execution are three different choices. v0.2.0 targets local execution; hosted
execution remains a later workstream.

## Where we are going

| Stage | User outcome |
| --- | --- |
| **v0.2.0 — execution provenance** | Run a controlled comparison through admitted Hermes or Codex subjects; recover it through CLI v2; inspect evidence quality separately from score. Preserve historical proof verification. |
| **v0.2.x — public participation and Market pilots** | Reproduce published work, distribute proof-backed artifacts, and reconcile accepted contributions with USDC payments. Add the bounded collaboration surface described in the delivery plan. Hosted execution has its own admission gate. |
| **v0.3 — Foundry and private Skill Climb** | Turn authorized source material into ordinary Verifiers packages; separate development, selection, and proving tasks; evaluate a frozen candidate on untouched proving membership. |
| **Later research** | Managed candidate search, adaptive harnesses, learning streams, Prime Agent and `prime-rl` handoffs, and environment-quality studies. |

The [v0.2 contract](docs/plan/v0.2.md) and
[Market and Foundry plan](docs/plan/techtree-market.md) contain existing release
boundaries. The [delivery audit and implementation sequence](docs/plan/techtree-delivery-audit-2026-09-06.md)
reconciles current work and identifies the additional forum scope. The
[ticket ledger](docs/v0.2/TICKETS.md) maps the original work packages; live `bd`
records carry their status.

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

Foundry will accept authorized failures, traces, data, or repositories and
produce qualified Prime-compatible environments. Private sources and executable
artifacts need their own access and isolation boundary. GEPA is a possible
managed candidate producer, not a prerequisite for the first private Climb.

</details>

## Privacy

Publication is explicit. Local Episodes, Traces, logs, and proposals are not
automatically uploaded. Local-first execution can still send requests to a
model provider; guided revision may use a different provider and budget.
Inspect those destinations before approving a run.

Public result material must exclude credentials and private evidence. Downloading
or buying an artifact does not make it safe to execute. A shared Regent profile
does not grant authority over another participant’s publication key or wallet.

## Work on the monorepo

| Component | Responsibility | Development guide |
| --- | --- | --- |
| `cli/` | Python CLI, scientific kernel, local state, proof verification, publication transport, and plugin tests | [CLI](cli/README.md) |
| `plugin/` | Thin Hermes operator integration; Codex packaging is planned | [Plugin](plugin/README.md) |
| `platform/` | Ash/Phoenix site, catalog, publication ingestion, public results, and profiles | [Platform](platform/README.md) |
| `contracts/` | Graph registry Solidity, scripts, and local checks | [Contracts](contracts/README.md) |

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
