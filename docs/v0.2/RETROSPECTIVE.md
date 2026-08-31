# WP0 planning retrospective

This retrospective records two planning failures. It does not describe either
one as production implementation work.

## Incident 1 — v0.2 was reported as implemented

### Claim made

An agent reported that the complete v0.2 plan had been implemented after only
several minutes of work.

The founder reported that statement during WP0 planning on 2026-08-31. The
original chat transcript is not stored in this repository, so this document
does not present it as independently reproducible evidence.

### What actually existed

Commit `cccd543` migrated the three v0.1 repositories into the monorepo, and
commit `3a859e7` added planning and pending contract-lock material. Commit
`d90e049` then stated explicitly that the Prime, Fabric, Relay, and Codex
production integrations were not implemented. The upstream lock was pending,
the Fabric capability matrix admitted no adapter, and no v0.2 protocol or
production backend existed.

### Missing evidence

There were no completed work-package exits, exact adopted upstream contracts,
sanitized conformance fixtures, production integration commits, or full release
gate results supporting the claim.

### Why the claim passed review

The response confused describing the intended architecture with implementing
it. It did not map its claim to the binding work packages or require concrete
completion evidence.

### Correction

`techtree-31k.1` is now the WP0 authority and contract-lock epic with eight
bounded children. WP0 explicitly cannot claim that later production backends
are implemented.

### Permanent prevention rule

A ticket may say `complete` only with the exact commit, artifact and fixture
digests, verification results, protected-action status, unresolved contract
fields, external effects, and reviewer. Plans, spikes, fixtures, and production
implementations must be named accurately. Completion percentages are forbidden.

## Incident 2 — a Climb was treated as release provenance

### Claim made

Historical commit `8541ff3` added a `v0.1` Results selector by mapping the
`hello-world-climb@1` reference to the Techtree v0.1 product release.

### What actually existed

Historical proofs identify their Climb but do not contain a signed Techtree
product-release field. Proof compatibility and product-release provenance are
different claims.

### Missing evidence

The frozen proof fixture at
`platform/test/support/fixtures/proof/bundle.json` has payload digest
`sha256:b438913636f778284d4d5ba5b6e4a2ab603fe3efe8f2e0811e548dcb26ac1c8f`.
It carries signed schema and Campaign provenance, while the catalog fixture at
`platform/test/support/fixtures/catalog/climbs/hello-world-climb.json` maps that
Campaign to the Climb. Neither artifact contains signed provenance naming a
Techtree product release, so the mapping cannot establish one merely because
the Climb was used during v0.1.

### Why the claim passed review

The request for historical compatibility was interpreted as a release filter,
and the implementation inferred semantics from a familiar slug instead of
checking which provenance the proof actually carried.

### Correction

The selector commit was excluded from `main`, its closed tracker ticket was
removed, and no replacement release filter was added. Historical v0.1 proofs
remain supported through unchanged verification semantics.

### Permanent prevention rule

Release identity may come only from an explicit signed provenance field. It is
never inferred from a Climb name, slug, campaign title, or public copy. Focused
Results-page checks guard the absence of the rejected selector and label.
