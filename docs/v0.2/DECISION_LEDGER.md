# Techtree v0.2 WP0 decision ledger

Status: binding input to WP0  
Recorded: 2026-08-31  
Authority: founder answers to the WP0 grilling pass

This ledger constrains WP0. It does not claim that any production Prime,
Fabric, Relay, or Codex integration is implemented.

## Roadmap adoption

- `docs/plan/v0.2.md` is the binding v0.2.0 execution-provenance plan.
  `docs/plan/techtree-market.md` is the binding plan for v0.2.x Techtree
  Market, v0.3 Techtree Foundry and the first Skill Climb, and deferred v0.3.x
  studies. Older roadmap text is context only.
- All products and protocols use Techtree names, including Techtree Market,
  Techtree Foundry, Techtree Climbs, Techtree Library, and
  `techtree.market.*`. Regents Labs is only the company and operator.
- Market runtime belongs in `platform/`. Local execution and proof verification
  in `cli/` and `plugin/` remain platform-independent.
- Payouts, Market, Foundry, optimization, and training are excluded from
  v0.2.0. The first Skill Climb is v0.3 work.

## v0.2 machine and publication contracts

- v0.2 replaces `techtree.cli.v1` directly with `techtree.cli.v2`; there is no
  v1 adapter or dual mode. Frozen v0.1 packages and proof bytes are unchanged.
- Stable operation identifiers map to existing CLI handlers rather than a
  second command hierarchy. Detailed append-only phases project into five
  stable public states.
- `run.wait` is bounded long-polling. v0.2 adds no daemon and no busy-polling.
- `GET /api/v1/publications/:bundle_digest` returns
  `techtree.published-result.v1`. Its `/bundle` child returns the exact stored
  submission bytes without re-encoding. No `/api/v1/results` route is added.
- Withdrawn entries retain metadata, tombstone, and receipt; their bundle
  download returns `410 Gone`.
- Prime Hosted is a hard release gate. If supported immutable selection and
  machine-readable operations remain inadmissible, v0.2.0 stays blocked.
- These machine-surface answers are written out in full in
  [`MACHINE_CONTRACT.md`](MACHINE_CONTRACT.md): the eleven-field envelope, the
  nine-field typed next action and its five retry classes, the eleven stable
  operation identifiers against the handlers they describe, the exact
  twelve-phase to five-state projection, and bounded `run.wait`. The document
  is bound to the code by
  [`cli/tests/contract/test_v02_machine_contract.py`](../../cli/tests/contract/test_v02_machine_contract.py),
  and it records six points the plan left open, each with the reading taken and
  why. WP0 froze the contract only; the producers move in WP1.
- The `plugin/hermes/` and `plugin/codex/` target layout is recorded in
  [`PLUGIN_LAYOUT.md`](PLUGIN_LAYOUT.md). Nothing moves in WP0, no shared
  plugin runtime SDK exists, and the move plus the Codex package land in WP6.

## Future protected decisions

- Signed Market records, authenticated mutations, payee control, payout
  reconciliation, challenge authority, executable-artifact isolation,
  private-data handling, and the x402 contract each require their stated
  security gate before a pilot.
- Proof Relay operators, cap, amount, chain/token, Safe, signers, challenge
  policy, acceptance policy, spending ceiling, rollback, reconciliation, and
  public-disclosure rules remain unresolved protected founder decisions. No
  payment occurs without founder approval of one immutable `BountySpec` and
  packet digest, expiry, and expected pre-action state.

## Product and ecosystem

- v0.2 may publish and consume one exact deterministic Prime conformance
  environment. It does not add arbitrary environment imports or Environment
  Forge.
- Prime Agent, NemoClaw, Grok Build, Pi, and future hosts are discovery or
  preview candidates only. Empty packages are forbidden.
- Stable subjects are Fabric-backed Hermes and Codex. Relay is optional,
  observe-only evidence.
- `plugin/` will become a workspace for thin host integrations. `cli/` remains
  the sole owner of scientific state, durable execution state, receipts,
  approvals, and publication behavior. No shared plugin runtime SDK is added.
- The existing Hermes plugin identity, commands, installation, update path,
  scanner expectations, and public documentation remain compatible.
- Human approval occurs through native Hermes, native Codex, or direct terminal
  confirmation. `platform/` does not become a browser run controller.

## Compatibility, withdrawal, and privacy

- Historical v0.1 compatibility means unchanged proof bytes and unchanged
  normalized verification semantics. A Climb name is never product-release
  provenance, and no replacement release selector is introduced by WP0.
- Withdrawal removes a Result from normal discovery while preserving immutable
  stored evidence, metadata, receipt, and append-only tombstone. Public bundle
  download returns `410 Gone`.
- A billing-principal label stays private by default. Public disclosure
  requires explicit participant opt-in in the publication intent.

## Upstream adoption

- Test the newest official stable upstream release first. A development build
  requires explicit approval. `verifiers==0.3.2.dev17` is approved only as a
  fallback spike candidate, not as the automatic v0.2 lock.
- Prime integration may use an official public SDK or official CLI machine
  surface. Production reliance on undocumented HTTP, dashboard scraping,
  decorative terminal output, or unstable local caches is forbidden.
- Fabric and adapters run in isolated CLI-owned managed environments. They do
  not modify the normal Hermes or Codex installations or copy reusable
  credentials.
- Stable Relay transport is bounded local ATOF with derived ATIF. There is no
  streaming service, platform trace sink, or public raw-trace hosting.
- Upstream issues and pull requests may be prepared locally but not sent, and
  release patches may not be silently vendored.

## Protected actions

Read-only discovery, local deterministic work, sanitized fixtures, internal
documents, focused checks, and approval-packet preparation may proceed.
Publishing an environment, starting a paid run, sending upstream
communications, adopting the final lock, publishing a package, activating a
release, or deploying requires a separate exact founder approval.

An ambiguous paid submission is reconciliation-only and must never be retried
automatically without a proven, locked provider idempotency guarantee.

## Prime owner status

The founder selected the Prime organization account `@techtree`, displayed
locally as Regents Labs. The proposed environment coordinate is therefore
`techtree/techtree-v02-conformance`. The organization slug and private local
display label may enter the approval packet; team IDs, user IDs, account email,
and other provider-internal identifiers may not enter project fixtures or
public evidence.

This resolves ownership but does not authorize publication. Publishing the
environment still requires its own exact protected-action approval packet.

## Ticket and completion discipline

- `techtree-31k` remains the v0.2 umbrella and `techtree-31k.1` is the WP0 epic
  with the eight children in `TICKETS.md`.
- No throwaway generic harness is added. The exact deterministic environment,
  sanitized upstream fixtures, and focused contract checks required for
  conformance remain mandatory.
- A ticket may say `complete` only when it links the full commit, exact
  artifacts and fixture digests, verification commands and outcomes, protected
  actions, unresolved contract fields, external effects, and reviewer.
- Plans, spikes, and fixtures are described as plans, spikes, and fixtures—not
  as implemented production features. Completion percentages are forbidden.
- Non-protected WP0 work may be integrated after review and gates. The final
  upstream lock remains proposed until its exact digest receives founder
  approval.
