# Open tools

Techtree's open tools run a controlled Skill comparison on your own computer, sign
the result, and publish it to techtree.sh when you choose. This page lists what each
release offers and pins. The services Techtree sells are on the
[front page](../README.md#services).

## Capabilities

The served release is the one the
[bootstrap contract](https://techtree.sh/api/v1/bootstrap) names; the table under
[Release compatibility](#release-compatibility) lists every record. The current
Climbs are Hello World, Frontier-CS Open-Ended and HF Tasksmith.

Techtree's commands come from
[regents-cli](https://github.com/regents-ai/regents-cli) as `regents techtree …`.
From 0.3.0 its main feature is creating an environment from a Skill. Techtree looks
at a Skill without running it, plans tasks from it with your approval, builds and
checks them offline, and lets you accept them as a frozen collection you can run,
verify and export for someone else. Comparing Skills on that collection stays
optional. The commands are `regents techtree forge inspect-skill` through
`regents techtree forge export`; the
[0.3.0 plan](plan/v0.3.0-skill-environments.md) and its
[task set](plan/v0.3.0-task-set.md) describe them. The active bootstrap contract
remains the authority for installable CLI and plugin coordinates.

The served release also signs an agent's identity, pairs it with its person's
account and reads that account. Points earning and money tests remain off.

Before it, 0.2.1 brought the Hello World Climb and a first trial of building repair
tasks from a repository. That trial is no longer offered.

| Capability | Status | Where it lives |
| --- | --- | --- |
| Hello World Climb: a local Skill comparison with Hermes and Prime Intellect's Verifiers | Available now | [regents-cli](https://github.com/regents-ai/regents-cli) (`regents techtree climb`), [`plugin/`](../plugin/) (`/techtree demo`) |
| Signed result bundles and offline verification | Available now | [regents-cli](https://github.com/regents-ai/regents-cli) (`regents techtree proof verify`) |
| Publishing a verified run, and public Results pages | Available now | [regents-cli](https://github.com/regents-ai/regents-cli) (`regents techtree publish`, `regents techtree withdraw`), [`platform/`](../platform/) ([Results](https://techtree.sh/results)) |
| Pinned install guide and release coordinates | Available now | [`platform/`](../platform/) ([Run locally](https://techtree.sh/docs/run-locally), [bootstrap](https://techtree.sh/api/v1/bootstrap)), [`platform/priv/releases/`](../platform/priv/releases/) |
| Structured machine responses (`--json`) for agents and scripts | Available now | [regents-cli](https://github.com/regents-ai/regents-cli) |
| Create an environment from a Skill: inspect, plan, build, accept, run, verify, export | Experimental | [regents-cli](https://github.com/regents-ai/regents-cli) (`regents techtree forge inspect-skill` through `regents techtree forge export`) |
| Browser tools for agents (WebMCP), listed at [/capabilities.json](https://techtree.sh/capabilities.json): public reads of the install guide, the Climbs and the Results; signed identity and account reads; and `techtree_publication`, which publishes or withdraws a signed Result | Available now | [`platform/`](../platform/) |
| An MCP connector for other agents | Planned | Not built yet |
| Hosted environment building and hosted execution | Planned | Not built yet |

The active Run locally guide controls exact installation coordinates. Historical
release documents can still name the old plugin repository or the `techtree`
command; the plugin is developed in this monorepo's `plugin/` directory and the
command-line tool in regents-cli. Do not replace a pinned release coordinate with an
arbitrary branch.

## Release compatibility

Each release record under [`platform/priv/releases/`](../platform/priv/releases/)
pins one CLI build, one Hermes plugin commit and one catalog. The values below are
read from those records (`bootstrap.json`, `release-core.json`, `checksums.json`) and
from `platform/priv/catalog/sources/`. From `climb-v0.4.0` the plugin is installed
from this repository's `plugin/` folder; earlier records name commits of the archived
`regents-ai/techtree-hermes`.

| Release record | CLI on PyPI | CLI source revision | Hermes plugin commit | Catalog source revision | Catalog index | Host Hermes | Published to the stable channel |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [`climb-v0.1.0`](../platform/priv/releases/climb-v0.1.0/) | `techtree` 0.1.1 | `614daff` (former `regents-ai/techtree-python`) | `ca22ee7` | `614daff` | `sha256:10a7fcc5…` | 0.20.1 | 2026-08-20 |
| [`climb-v0.2.0`](../platform/priv/releases/climb-v0.2.0/) | `techtree` 0.2.0 | `70e75c7` (tag `v0.2.0`) | `4567937` | `70e75c7` | `sha256:4d216571…` | 0.20.1 | 2026-09-18 |
| [`climb-v0.2.1`](../platform/priv/releases/climb-v0.2.1/) | `techtree` 0.2.1 | `a1b9c05` (tag `v0.2.1`) | `d891b3b` | `a1b9c05` | `sha256:4d216571…` | 0.20.1 | 2026-09-21 |
| [`climb-v0.3.0`](../platform/priv/releases/climb-v0.3.0/) | `techtree` 0.3.0 | `74d87d3` (tag `v0.3.0`) | `e0765e6` | `74d87d3` | `sha256:4d216571…` | 0.21.3 | 2026-09-27 |
| [`climb-v0.3.1`](../platform/priv/releases/climb-v0.3.1/) | `regents-cli` 1.0.0 | `fdddd9f` (regents-cli tag `v1.0.0`) | `8f7831a` | `fdddd9f` | `sha256:9c20fb90…` | 0.21.3 | 2026-09-29 |
| [`climb-v0.4.0`](../platform/priv/releases/climb-v0.4.0/) | `regents-cli` 1.2.1 | `1b10a38` (regents-cli tag `v1.2.1`) | `149f4bf` (`plugin/`) | `1b10a38` | `sha256:0fd83a73…` | 0.21.3 | 2026-09-29 |
| [`climb-v0.5.0`](../platform/priv/releases/climb-v0.5.0/) | `regents-cli` 1.3.0 | `9bc532d` (regents-cli tag `v1.3.0`) | `c46a588` (`plugin/`) | `9bc532d` | `sha256:86f62d0f…` | 0.21.3 | 2026-09-30 |
| [`climb-v0.5.1`](../platform/priv/releases/climb-v0.5.1/) | `regents-cli` 1.3.1 | `4d9002a` (regents-cli tag `v1.3.1`) | `38957a4` (`plugin/`) | `4d9002a` | `sha256:86f62d0f…` | 0.21.3 | 2026-10-01 |
| [`climb-v0.5.2`](../platform/priv/releases/climb-v0.5.2/) | `regents-cli` 1.3.2 | `7a5ad0b` (regents-cli tag `v1.3.2`) | `4e93fc7` (`plugin/`) | `7a5ad0b` | `sha256:86f62d0f…` | 0.21.3 | 2026-10-01 |
| [`climb-v0.5.3`](../platform/priv/releases/climb-v0.5.3/) | `regents-cli` 1.3.3 | `7d5e82c` (regents-cli tag `v1.3.3`) | `9fc4622` (`plugin/`) | `7d5e82c` | `sha256:86f62d0f…` | 0.21.3 | 2026-10-01 |
| [`climb-v0.5.4`](../platform/priv/releases/climb-v0.5.4/) | `regents-cli` 1.3.4 | `158421c` (regents-cli tag `v1.3.4`) | `97475f1` (`plugin/`) | `158421c` | `sha256:86f62d0f…` | 0.21.3 | 2026-10-02 |
| [`climb-v0.6.0`](../platform/priv/releases/climb-v0.6.0/) | `regents-cli` 1.4.0 | `64b8b45` (regents-cli tag `v1.4.0`) | `826ae5a` (`plugin/`) | `64b8b45` | `sha256:836079f1…` | 0.21.3 | 2026-10-04 |
| [`climb-v0.6.1`](../platform/priv/releases/climb-v0.6.1/) | `regents-cli` 1.5.0 | `aa149a3` (regents-cli tag `v1.5.0`) | `e6ea3c5` (`plugin/`) | `aa149a3` | `sha256:836079f1…` | 0.21.3 | 2026-10-04 |
| [`climb-v0.7.0`](../platform/priv/releases/climb-v0.7.0/) | `regents-cli` 1.6.0 | `5b0926b` (regents-cli tag `v1.6.0`) | `58b86cb` (`plugin/`) | `5b0926b` | `sha256:2b81f26f…` | 0.21.3 | 2026-10-06 |
| [`climb-v0.7.1`](../platform/priv/releases/climb-v0.7.1/) | `regents-cli` 1.7.2 | `781ec97` (regents-cli tag `v1.7.2`) | `5d8e757` (`plugin/`) | `781ec97` | `sha256:2b81f26f…` | 0.21.3 | 2026-10-07 |
| [`climb-v0.7.2`](../platform/priv/releases/climb-v0.7.2/) | `regents-cli` 1.7.3 | `b1c9385` (regents-cli tag `v1.7.3`) | `6aee0dc` (`plugin/`) | `b1c9385` | `sha256:2b81f26f…` | 0.21.3 | 2026-10-08 |
| [`climb-v0.7.3`](../platform/priv/releases/climb-v0.7.3/) | `regents-cli` 1.10.2 | `1bc4817` (regents-cli tag `v1.10.2`) | `a469830` (`plugin/`) | `1bc4817` | `sha256:2b81f26f…` | 0.21.3 | 2026-10-13 |
| [`climb-v0.7.16`](../platform/priv/releases/climb-v0.7.16/) | `regents-cli` 1.10.15 | `3cc224d` (regents-cli tag `v1.10.15`) | `abb6804` (`plugin/`) | `3cc224d` | `sha256:2b81f26f…` | 0.21.3 | 2026-10-21 |
| [`climb-v0.7.17`](../platform/priv/releases/climb-v0.7.17/) | `regents-cli` 1.10.16 | `2c98218` (regents-cli tag `v1.10.16`) | `00ba176` (`plugin/`) | `2c98218` | `sha256:2b81f26f…` | 0.21.3 | 2026-10-23 |
| [`climb-v0.7.18`](../platform/priv/releases/climb-v0.7.18/) | `regents-cli` 1.10.17 | `773f8a6` (regents-cli tag `v1.10.17`) | `5ebe7d2` (`plugin/`) | `773f8a6` | `sha256:2b81f26f…` | 0.21.3 | 2026-10-23 |
| [`climb-v0.7.20`](../platform/priv/releases/climb-v0.7.20/) | `regents-cli` 1.10.19 | `02f8961` (regents-cli tag `v1.10.19`) | `c630e30` (`plugin/`) | `02f8961` | `sha256:b0ab3945…` | 0.21.3 | 2026-10-28 |
| [`climb-v0.7.21`](../platform/priv/releases/climb-v0.7.21/) | `regents-cli` 1.10.20 | `0e3768f` (regents-cli tag `v1.10.20`) | `91a4fd7` (`plugin/`) | `0e3768f` | `sha256:e0319bae…` | 0.21.3 | 2026-10-28 |
| [`climb-v0.7.23`](../platform/priv/releases/climb-v0.7.23/) | `regents-cli` 1.10.22 | `0b08d4a` (regents-cli tag `v1.10.22`) | `0bd9f4b` (`plugin/`) | `0b08d4a` | `sha256:e0319bae…` | 0.21.3 | 2026-11-02 |
| [`climb-v0.7.24`](../platform/priv/releases/climb-v0.7.24/) | `regents-cli` 1.10.23 | `8e8f2af` (regents-cli tag `v1.10.23`) | `56d1641` (`plugin/`) | `8e8f2af` | `sha256:e0319bae…` | 0.21.3 | 2026-11-04 |
| [`climb-v0.7.25`](../platform/priv/releases/climb-v0.7.25/) | `regents-cli` 1.10.24 | `fd32543` (regents-cli tag `v1.10.24`) | `31875a4` (`plugin/`) | `fd32543` | `sha256:78a9ec72…` | 0.21.3 | 2026-11-06 |
| [`climb-v0.7.26`](../platform/priv/releases/climb-v0.7.26/) | `regents-cli` 1.10.25 | `8b3240b` (regents-cli tag `v1.10.25`) | `72cdb0f` (`plugin/`) | `8b3240b` | `sha256:78a9ec72…` | 0.21.3 | 2026-11-12 |
| [`climb-v0.7.27`](../platform/priv/releases/climb-v0.7.27/) | `regents-cli` 1.10.26 | `2e4a571` (regents-cli tag `v1.10.26`) | `dcdcf07` (`plugin/`) | `2e4a571` | `sha256:78a9ec72…` | 0.21.3 | 2026-11-13 |
| [`climb-v0.7.28`](../platform/priv/releases/climb-v0.7.28/) | `regents-cli` 1.10.27 | `2f7eee7` (regents-cli tag `v1.10.27`) | `abe6548` (`plugin/`) | `2f7eee7` | `sha256:78a9ec72…` | 0.21.3 | 2026-11-13 |
| [`climb-v0.7.29`](../platform/priv/releases/climb-v0.7.29/) | `regents-cli` 1.10.28 | `1608c83` (regents-cli tag `v1.10.28`) | `7c3c728` (`plugin/`) | `1608c83` | `sha256:78a9ec72…` | 0.21.3 | 2026-11-13 |

The evaluated subject is Hermes 0.19.0 up to `climb-v0.3.0`, Hermes v2026.7.20 from
`climb-v0.3.1`, and Hermes v2026.9.24 with GPT-6 Luna at high reasoning from
`climb-v0.5.0`, and each record names the Hello World Climb (`hello-world-climb@1`)
as its introduction. From `climb-v0.4.0` a record also names the starter Skill of
every Climb it publishes. The full 40-character revisions and digests are in the
records themselves.

Host Hermes is the minimum Hermes version each published record accepts, and that
published value is the one that applies.

The site at techtree.sh serves one active release per channel; the live answer is
always [`/api/v1/bootstrap`](https://techtree.sh/api/v1/bootstrap). The commit the
site itself runs is `build.commit` at
[`/capabilities.json`](https://techtree.sh/capabilities.json).

The [changelog](../CHANGELOG.md) lists what each release changed, and what the 0.3.0
release does not yet show.

## Roadmap

| Stage | User outcome |
| --- | --- |
| **0.3.0: create an environment from a Skill** (released) | Inspect a supported Skill without running it; review and approve a plan; build and check tasks offline; accept a frozen collection; run one agent on it without any comparison; verify it and export a private copy for someone else. Comparing Skills on the collection stays optional. |
| **Later** (planned) | An MCP connector for other agents, hosted environment building and execution, and private hosting. |
| **Optional later** | NVIDIA's NeMo Fabric harnesses and NeMo Relay process evidence in the open tools. |

The [0.3.0 plan](plan/v0.3.0-skill-environments.md) and its
[task set](plan/v0.3.0-task-set.md) are the current product and delivery documents.
Earlier plans and handoffs (for example [`plan/v0.2.md`](plan/v0.2.md) and
[HANDOFF.md](../HANDOFF.md)) are kept as historical records and say so at the top.
