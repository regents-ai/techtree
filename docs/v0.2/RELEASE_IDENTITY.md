# Techtree v0.2 release identity

Techtree v0.2 is the execution-provenance and subject-portability release.

Its public summary is:

> v0.2 adds Prime-hosted comparisons, Fabric-backed Hermes and Codex subjects,
> bounded Relay evidence, and provider reruns. Future releases will add
> environment creation, optimization, and training.

This document fixes the target identity for planning and implementation. It is
not a claim that v0.2 has shipped. The binding plan, decision ledger, and ticket
state determine what is approved, implemented, and releasable.

## Stable release matrix

| Plane | Stable v0.2 support |
| --- | --- |
| Evaluation | One exact founder-approved Prime Verifiers build |
| Execution | Local Techtree and Prime Hosted Evaluations |
| Subjects | Direct Hermes, Fabric-Hermes, and Fabric-Codex |
| Operators | Hermes and Codex |
| Evidence | Native Verifiers evidence and optional observe-only NeMo Relay evidence |

Prime Agent, NemoClaw, Grok Build, Pi, and future hosts may have discovery
records or preview admission work. They are not stable v0.2 dependencies.

The upstream contract lock remains pending until its exact coordinates,
fixtures, conformance results, and founder approval are recorded. A date in a
draft lock is not release approval.

## Repository ownership

- `cli/` owns Campaigns, execution, durable state, receipts, proofs, provider
  boundaries, and the versioned machine contract.
- `plugin/` contains thin host integrations. It owns no scientific state,
  scheduler, provider client, approval rule, receipt, or publication protocol.
- `platform/` ingests and presents published evidence. It is not a local or
  browser-based run controller.

## Explicit exclusions

Environment Forge, arbitrary environment import or creation, automatic Skill
optimization, held-out proving workflows, training, a local control-plane
dashboard, and a broader stable harness matrix remain v0.3 or later.

## Historical evidence rule

Historical v0.1 compatibility means frozen proof bytes continue to verify with
the same normalized outcome and claim semantics. A Climb reference is not a
Techtree product-release identifier. Public filters and release claims may use
only provenance fields actually present in signed evidence; they may not infer
release identity from `hello-world-climb@1` or any other name.
