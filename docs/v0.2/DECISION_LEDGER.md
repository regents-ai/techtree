# Techtree v0.2 WP0 decision ledger

Status: binding input to WP0  
Recorded: 2026-08-31  
Authority: founder answers to the WP0 grilling pass

Amended 2026-09-01 by the founder's Prime decisions and by the publication
envelope's real shipped state, both recorded in their own section below. Each
amended bullet above says so where it stands.

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
- `GET /api/v1/publications/:bundle_digest` is to return
  `techtree.published-result.v1`. Superseded on 2026-09-01 in its stated
  consequence only: WP0.7 shipped the `/bundle` child, which returns the exact
  stored submission bytes without re-encoding, but the metadata route still
  answers with the inherited `techtree.publication-entry.v1alpha1`. The target
  envelope is unchanged; WP5 replaces the metadata envelope in the same cutover
  as the facets it carries. No `/api/v1/results` route is added.
- Withdrawn entries retain metadata, tombstone, and receipt; their bundle
  download returns `410 Gone`.
- Prime Hosted is a hard admission gate. Superseded on 2026-09-01 in its
  release consequence only: WP4 moved to v0.2.x rather than blocking v0.2.0.
  The admission bar itself is unchanged — see the 2026-09-01 section below.
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

- v0.2 has one exact deterministic conformance environment. v0.2.0 publishes
  and runs it locally; consuming it as a hosted evaluation is v0.2.x. Neither
  release adds arbitrary environment imports or Environment Forge.
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
  download returns `410 Gone`. What “normal discovery” covers is contested
  against the shipped v0.1 log and is open as entry 5 of the 2026-09-01 section
  below.
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

That resolved ownership only. The publication itself was approved and executed
on 2026-09-01; see the next section.

## Decisions and amendments, 2026-09-01

Recorded 2026-09-01. Authority for 1–3: founder answers to WP0.3, carried on
`techtree-31k.1.3` and `techtree-31k.1.8`. Entry 4 is a chief decision on
sequencing; entry 5 records a founder decision that is still open.

### 1. A zero-cost read-only Prime session was authorized

A read-only session against the `@techtree` Prime organization was authorized
to capture sanitized response fixtures, and it was executed. No Prime resource
was mutated by it and no paid run occurred.

Consequence: seven captures were retained and are sanitized fixtures under the
owning component's tests — the owned environment listing before publication and
again after it, the environment status read, the environment action listing,
the environment action logs, the environment inspect as human text, and an
empty evaluation listing. No public environment listing and no team listing
were retained. Provider-internal identifiers are replaced by documented
placeholders and persisted nowhere; they still may not enter project fixtures
or public evidence.

### 2. The zero-cost environment publication was approved and executed

The prepared `$0` publication packet for `techtree/techtree-v02-conformance`,
intent digest
`sha256:b7702ee60314a5a1ab86073a13ebd030ac3c23639a1c6c20c9ab7643130dd368`, was
approved and executed on 2026-09-01. The environment is public at version
`0.1.0`. A fresh deterministic build with `SOURCE_DATE_EPOCH=1704067200`
produced `techtree_v02_conformance-0.1.0-py3-none-any.whl`, 4,413 bytes,
`sha256:ceca3bf0a8af32dde48230bce59a89ee77b6d330f4c09d050d05c055f538a6e0`,
equal to the approved packet and to the SHA256 the provider reported for the
uploaded wheel. No evaluation was created, no model was called, and no paid run
occurred.

Consequence: no document may still say this publication is blocked, pending, or
unauthorized. Prime's hub Integration Test passes install and import and fails
only `test_pyproject_has_metadata`, a non-standard `tags` list the hub wants
under `[project]`. Fixing it changes the wheel and tree digests and therefore
needs a new zero-cost packet and its own approval; that choice is open as
`techtree-2qy` and does not gate v0.2.0. Until it is taken, `0.1.0` is
published but not hub-validated, and must be described that way.

### 3. Prime Hosted Evaluations move to v0.2.x as inadmissible for v0.2.0

The captured Prime contract does not supply immutable environment selection,
structured create/logs/stop output, provider idempotency, bounded transport, or
a plan-bound estimate. These are upstream product gaps that no local work
closes. The founder recorded the hosted contract gap as inadmissible for v0.2.0
and moved WP4 to v0.2.x.

Consequences:

- v0.2.0 ships WP0, WP1, WP2, WP3, WP5, and WP6, with local execution as its
  only execution backend. A Result whose location facet is anything but `local`
  cannot be produced by it.
- WP4 keeps its number and its Bead `techtree-31k.5`, and keeps the “Paid
  remote execution” design in `docs/plan/v0.2.md`, which stays binding for it.
  It is re-parented under the v0.2.x hosted-execution epic `techtree-k7t` and
  depends on WP1 and WP5.
- The admission bar is not demoted or relaxed. WP4 starts when the upstream
  contract supplies those guarantees, and not before.
- WP5, now “V2-WP5 — Publish evidence facets and exact public bundles”, depends
  on WP3 only. Rerun proofs, the rerun filter, and the “Prime run reference
  captured” public label move to WP4, because v0.2.0 produces no provider
  record to label.
- The v0.2.0 release gate drops the hosted two-arm comparison, the reconciled
  ambiguous submission, and the provider-hosted rerun.
- WP0.8's approval packet no longer carries a Prime stop/go. It depends on
  every other WP0 child; today only WP0.5 remains open.
- WP0.3 is closed with its blockers recorded rather than resolved. The
  responses WP4 still needs — evaluation get, samples, hosted logs, hosted
  stop, and hosted create — are re-homed to WP4 and gate nothing in v0.2.0.

### 4. The publication metadata envelope is not renamed yet

WP0.7 shipped the `/bundle` child route and the `410 Gone` withdrawal, but not
the envelope rename: `GET /api/v1/publications/:bundle_digest` still answers
with the inherited `techtree.publication-entry.v1alpha1`.

Chief decision, 2026-09-01: WP5 replaces it with `techtree.published-result.v1`
in the same cutover as the evidence facets that envelope carries. Renaming
earlier than the facets — the narrower question at
[`PUBLICATION_WITHDRAWAL_AUDIT.md`](PUBLICATION_WITHDRAWAL_AUDIT.md) §7.2 —
defaults to no unless the founder says otherwise. No document may describe the
rename as shipped before that cutover.

### 5. Open founder decision for WP5: what withdrawal removes

[`PUBLICATION_WITHDRAWAL_AUDIT.md`](PUBLICATION_WITHDRAWAL_AUDIT.md) §7.1 is
unanswered. This ledger and `TICKETS.md` say withdrawal removes a Result from
normal discovery. The shipped v0.1 log keeps a withdrawn entry listed and
marked on purpose, and decision 0038 says the same, because a log that quietly
dropped its withdrawn entries would have unexplained holes in it.

Both cannot hold. Either “discovery” means the append-only log listing, and WP5
reverses a shipped v0.1 behaviour and 0038 needs an amendment; or it means only
the filtered browsable surfaces WP5 adds, and the log is untouched. WP5 does
not build those surfaces until the founder answers. Nothing here authorizes
changing the shipped log meanwhile.

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
- WP0.8 froze the proposed lock on 2026-09-01. Every field in
  `UPSTREAM_CONTRACT_LOCK.json` and `FABRIC_CAPABILITY_MATRIX.json` is now
  either evidence-backed or an explicit status naming a numbered decision in
  [`WP0_FOUNDER_PACKET.md`](WP0_FOUNDER_PACKET.md). That packet requests
  approval of one exact lock digest and carries the sixteen decisions this
  ledger and the WP0 contract documents left open. Adoption of the lock waits
  on the packet; the decisions themselves are stated there, not restated here.
