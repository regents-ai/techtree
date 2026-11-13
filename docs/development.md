# Development

regents-cli executes, the plugin adapts, the platform publishes, and the contracts
own the registry.

| Part | Role | What it owns | Guide |
| --- | --- | --- | --- |
| [regents-cli](https://github.com/regents-ai/regents-cli) | **Executes** | Everything that runs, builds or verifies, on your own machine, under `regents techtree`: Climbs and runs, Skill environments (`regents techtree forge`), signing and offline proof checks, and publication. | [regents-cli](https://github.com/regents-ai/regents-cli#techtree) |
| [`plugin/`](../plugin/) | **Adapts** | A thin Hermes adapter over regents-cli: it runs `regents techtree` with fixed arguments, reads one JSON answer back, and asks the person before anything that spends or publishes. No evaluation logic, and no network of its own. | [Plugin](../plugin/README.md) |
| [`platform/`](../platform/) | **Publishes** | techtree.sh: the install guide and bootstrap, the catalog, publication intake, Results and verification pages, the service pages and the changelog. | [Platform](../platform/README.md) |
| [`contracts/`](../contracts/) | **Registry** | The `TechtreeGraphRegistryV1` Solidity contract, its deployment scripts and Foundry tests. | [Contracts](../contracts/README.md) |
| [`lab/`](../lab/) | **Measures** | The payment-terms environment, the Nemotron comparison and the training settings file. | [Lab](../lab/README.md) |

## Setup

For plugin development, install Python 3.12 and [uv](https://docs.astral.sh/uv/),
then:

```sh
git clone https://github.com/regents-ai/techtree.git
cd techtree
make -C plugin install
make -C plugin check
```

The command-line tool is developed in
[regents-cli](https://github.com/regents-ai/regents-cli).

Platform development additionally needs Erlang/Elixir, Node, PostgreSQL, and the
shared library setup described in the
[platform guide](../platform/README.md#development). Follow that guide before
`mix setup`.

## Checks

`make check` runs the full model-free repository gate, including platform asset
setup and registry checks. It requires the platform prerequisites, Foundry, pinned
Solidity dependencies, and Node for the pinned Quint that checks the
[Wallet Bench funding model](../formal/wallet_bench_funding/README.md). It does not
start paid inference, publish results, release packages, deploy, or transfer money.
Setup can download dependencies.

See [CONTRIBUTING.md](../CONTRIBUTING.md) and [AGENTS.md](../AGENTS.md) for the
contributor workflow, [SECURITY.md](../SECURITY.md) for vulnerability reporting, and
[LICENSE](../LICENSE) for terms.

## Related

| Product | Purpose | Source |
| --- | --- | --- |
| [Regents](https://regents.sh) | Agent identity and operations | [regents](https://github.com/regents-ai/regents) |
| [Autolaunch](https://autolaunch.sh) | Token auctions and launch operations | [autolaunch](https://github.com/regents-ai/autolaunch) |
| [Patchbay](https://patchbay.help) | Agent tool reports and bounded browser-tool repairs | [patchbay](https://github.com/regents-ai/patchbay) |

Shared presentation lives in
[design-system](https://github.com/regents-ai/design-system); common Elixir libraries
live in [elixir-utils](https://github.com/regents-ai/elixir-utils). Products share
useful foundations while keeping their own authorization boundaries.
