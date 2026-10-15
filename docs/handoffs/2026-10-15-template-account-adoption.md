# Techtree shared-account adoption — 15 October 2026

Local candidate only. Sean assigned this implementation to the Techtree chief,
through chief chief. No push, deployment, production migration, wallet action or
paid run is authorized for this adoption. Points earning and money tests stay off.

## Scope and sources

Base: `dc744404ed1589731d44760cb14e7059e574042b`, already on main/live v142;
it includes the requested reviewed regression commit `e337952`.

Canonical account source: template `e77069396da623a3444668622bcb4777151f272d`.
Canonical local Credits correction: `8f71a80fe2c323c151dc467c7a3757507e31becf`.
Shared Elixir pin: `72c4448996d2d81774d07df54f2d11908578c532`.
Design-system pin: `ebfd3fa40126aa3c405e33266bf9bd68ff74ec8d`.
CLI 1.10.4: `69a9ca06b75ed826f8b727826166979e3efa66bd`.

Done means a reviewed local candidate with matching contracts, schema snapshots,
scoped build/static checks and representative account/session checks, plus explicit
remaining browser and release requirements. Local source readiness is not release acceptance.

Ash resources/policies own account authority; Ecto owns constraints and transactions;
Phoenix/Plug/LiveView own browser sessions and rendering; Signals react inline;
PubSub refreshes account views; existing Oban/AshOban owns durable work.

## Changes

- Canonical revocable sessions, verified account projection, linked identities,
  optional ENS lookup and owner pairing controls. Account, Points, Credits,
  wallets and connections share one LiveView frame. Public reading retains its
  strict headers, and publication retains its independent proof boundary.
- Canonical Privy bridge, cookie-rotation handling, account controls, agent dialog,
  Credits dialog and browser dependencies. Product catalog, benchmark and crown
  behavior remain in their existing modules.
- Credits balance/history and owner/Base/hash-scoped stored purchase reads.
  Copied the template correction: one report after a confirmed receipt, no page-owned
  reconciliation retry loops, no wallet replay or persisted pending transactions.
- Both Credits Signals listeners and the Points adapter are installed with
  `starts_at: nil` and `approved_rules: []`. No rule or money run is enabled.
- Typed paired-account and Credits-history contracts, invalid-cursor response,
  generated OpenAPI, current CLI guidance and the published CLI contract-check pin.
- One migration creates three site-owned tables: session authorities, linked
  identities and ENS projections, referencing existing shared human accounts.

## Verification

- Strict compilation, formatting, Credo, security scan, Ash codegen and generated
  usage checks passed. Browser type checking and asset build passed. CLI 1.10.4's
  actual command checker accepted the generated contract.
- Disposable server-disabled checks in a dedicated localhost database passed:
  refresh invalidates old cookies while current mounted leases remain valid;
  account switching and revocation withdraw authority; another owner cannot read
  the account; a revoked component event creates no pairing code; account tabs
  retain their frame and linked-wallet projection; both Signals handlers create no
  Points events or jobs while earning is off; DELETE routing preserves CSRF and
  method refusal behavior.
- The new migration's up path ran locally. It creates only the three new tables
  and constraints. No production migration or destructive cleanup ran.
- Independent security review found no actionable authority/state defect in the
  final account integration or canonical Credits correction. This is bounded
  review, not a claim of provider, wallet or production acceptance.
- The existing compile-dependency ceiling was 19. Account adoption adds four
  account resource/domain edges, one Points resource/domain edge, and the canonical
  session-key/header edges: 26 total. The ceiling now records that inspected graph;
  no runtime abstraction was added to evade the check.

No permanent behavioral tests were added. The broad historical suite was not run.
Evidence and disposable checks are under
`/Users/sean/Documents/regent/artifacts/techtree-template-alignment-2026-10-15/`.

## Remaining release requirements

1. Techtree's own approved `PRIVY_APP_ID` and ES256 public
   `PRIVY_VERIFICATION_KEY` must be available through its established local loader.
   The loader did not supply the complete pair; startup was refused. No settings
   file was read or another site's environment borrowed. Real sign-in, refresh,
   sign-out, cross-tab and browser/mobile dialog acceptance remain unverified.
2. Template/Contessa acceptance and release of the canonical Credits correction.
   Existing Regents queue, scheduler and Base indexer operation must be confirmed;
   source registration does not prove the production fallback works.
3. Confirm production prerequisites and permissions for the three site tables and
   canonical account writes, then obtain applicable authority for migration,
   push and deployment. Preserve rollback and verify public/account behavior after release.

All source work is local. The known live revision remains `dc744404` / v142.
