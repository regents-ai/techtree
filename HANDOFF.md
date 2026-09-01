# Handoff — Techtree v0.2 roadmap adopted, WP0 in progress

Updated 2026-08-31 after WP0.3 integration and the v0.2–v0.3 roadmap and
tracker reconciliation.

This is a starting brief, not authority to implement blindly. Read the root
instructions, binding plans, current Beads graph, recent commits, and live
working tree before changing anything.

## Repository authority

`regents-ai/techtree` is the only source of truth for v0.2+ development.

| Component | Ownership |
| --- | --- |
| `cli/` | Local and hosted execution, scientific and durable run state, proof construction, publication transport, and offline verification |
| `plugin/` | Thin host-specific operator integrations, beginning with Hermes and Codex |
| `platform/` | techtree.sh, publication ingestion and public Results, Techtree Market, Techtree Library, authentication, access, and payout reconciliation |

The platform is never required for local execution or proof verification. The
frozen v0.1 repositories and packages remain historical release provenance;
v0.2 work does not rewrite their proof bytes.

## Binding plans and tracker

- `docs/plan/v0.2.md` governs the focused v0.2.0 execution-provenance release.
- `docs/plan/techtree-market.md` governs v0.2.x Techtree Market, v0.3
  Techtree Foundry and the first Skill Climb, and deferred v0.3.x studies.
- `docs/v0.2/DECISION_LEDGER.md` records founder decisions and protected gates.
- `docs/v0.2/TICKETS.md` maps plans to the Beads graph.

The active epics are `techtree-31k` for v0.2.0, `techtree-33x` for v0.2.x
Market, and `techtree-8dj` for v0.3 Foundry and Skill Climb. `techtree-5t7` is
the deferred v0.3.x study line.

## Integrated work

WP0.1 and WP0.2 are closed. The reviewed WP0.3 commit
`d80f641d2f2c4a1bfad49d7a25c189759164e9b0` is integrated into `main` as its
own commit. It retains exact Prime/OpenAPI/source evidence, enforces
`--skip-upload`, and accurately marks unobserved machine reads as unproven.

WP0.3 remains in progress. Supported immutable Prime environment selection and
bounded machine-readable runtime responses are unresolved. Prime Hosted is a
hard v0.2.0 release gate: if the supported contract remains inadmissible, the
release stays blocked.

The v0.2 machine contract is a direct move to `techtree.cli.v2`, with typed
next actions, stable operation identifiers mapped to current handlers,
detailed internal phases projected to five public states, and bounded
`run.wait`. There is no v1 adapter, dual mode, daemon, or busy polling.
This is a binding decision, not completed code. WP0.6 must still publish the
exact operation-to-handler map, total phase-to-state projection, and
`run.wait` wake, timeout, terminal, and reconciliation semantics before the
contract can be called locked.

The publication contract keeps
`GET /api/v1/publications/:bundle_digest`, adds
`techtree.published-result.v1`, and adds exact stored bundle retrieval at the
`/bundle` child route. Withdrawn metadata, tombstone, and receipt remain while
bundle retrieval returns `410 Gone`. No `/api/v1/results` route is planned.

## Remaining v0.2.0 order

Use the Beads dependency graph rather than a false linear WP0 sequence.
WP0.4–WP0.7 may proceed only as their dependencies allow. WP0.8 combines the
Prime stop/go decision, final upstream lock, and exact founder approval packet.
WP1 production protocol work waits for required WP0 contracts to freeze.

Do not pull Market, payouts, Foundry, optimization, the first Skill Climb, or
training into v0.2.0.

## Protected boundaries

Do not publish a Prime environment, start paid inference, mutate provider
resources, adopt a final upstream lock, release a package, deploy the platform,
or move money without the specific founder authority required for that action.

Proof Relay payment parameters remain unresolved protected decisions. Before
payment, one packet must bind operators, participant cap, amount, chain/token,
Safe, signers, challenge policy, acceptance policy, spending ceiling,
rollback, reconciliation, and public-disclosure rules. Founder approval binds
one immutable `BountySpec` and packet digest, expiry, and expected pre-action
state.

Never persist credentials, private provider identifiers, private traces, or
raw provider responses containing forbidden material. Unsupported upstream
behavior is a blocker, not permission to invent an adapter contract.

## Local checkout state

The reviewed WP0.1, WP0.2, WP0.3, and `regent-0h5` ticket worktrees are
integrated and should be absent after cleanup. The `docs/readme-flow` branch is
superseded by the corrected release-identity decision and must not be merged.
The remote `regent-zs6.9-techtree-fast-wins` branch is preserved, but its
conflicting local worktree is retired without a wholesale merge. Historical
standalone repositories are untouched.

## Resume procedure

1. Read the root instructions, both binding plans, the decision ledger, and
   the ticket ledger.
2. Check current Git state and `bd ready`, `bd blocked`, and dependency cycles.
3. Claim one unblocked Bead and keep edits within its stated component and
   work-package boundary.
4. For `platform/` implementation, use `ash-regents`.
5. Run focused checks while working and the established monorepo gate before
   completion. Do not add a smoke-test framework or new harness.
6. Report exact evidence, remaining blockers, and any protected action still
   awaiting founder approval.
