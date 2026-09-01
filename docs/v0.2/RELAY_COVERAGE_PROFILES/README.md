# Relay coverage profiles

This directory contains the adapter-specific `RelayCoverageProfile` drafts
produced by the WP0.5 contract spike. Neither profile is released: both are
drafts against the coordinates in
[`UPSTREAM_CONTRACT_LOCK.json`](../UPSTREAM_CONTRACT_LOCK.json), and both stay
`release_admitted: false` until the founder admits them.

| Profile | Adapter | Status |
| --- | --- | --- |
| [`hermes.relay-coverage-profile.json`](hermes.relay-coverage-profile.json) | `nvidia.fabric.hermes` | draft pending WP3 implementation |
| [`codex.relay-coverage-profile.json`](codex.relay-coverage-profile.json) | `nvidia.fabric.codex` | draft blocked by an upstream version conflict |

A profile defines the exact events Techtree expects from one adapter, the
sources those expectations are derived from — the Verifiers trace, the Fabric
execution receipt, and native harness events — and the blind spots that remain.
Complete coverage is calculated; it is never manually asserted. The only
complete status is `complete_for_profile`. Profiles distinguish Relay not being
requested from Relay being requested but unavailable.

Each profile pins both its schema version and the `relay-coverage-v1`
calculation version, and each records that Relay is observe-only: no value a
profile computes may enter a score, a spend decision, or an execution decision.

The findings behind these drafts are in
[`RELAY_CONTRACT.md`](../RELAY_CONTRACT.md), and the evidence they cite is in
`cli/tests/fixtures/relay/`.

Do not add private traces, credentials, environment dumps, or unsanitized
provider responses here.
