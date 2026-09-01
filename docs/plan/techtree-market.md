# Techtree Market, Foundry, and Skill Climb roadmap

Status: binding plan for post-v0.2.0 work  
Audience: product, protocol, CLI, plugin, platform, security, and release implementers  
Scope: v0.2.x, v0.3, and deferred v0.3.x studies

## Authority and sequence

This document is the implementation authority for work after the focused
v0.2.0 execution-provenance release. The v0.2.0 contract remains
[`v0.2.md`](v0.2.md). The release order is:

1. v0.2.0 execution provenance and subject portability (`techtree-31k`).
2. v0.2.x Techtree Market proof pilots (`techtree-33x`), alongside v0.2.x
   hosted execution (`techtree-k7t`), which carries the Prime Hosted
   Evaluations work package moved out of v0.2.0 on 2026-09-01 and is specified
   in [`v0.2.md`](v0.2.md).
3. v0.3 Techtree Foundry and the first private Skill Climb (`techtree-8dj`).
4. Deferred v0.3.x studies (`techtree-5t7`).

These are dependency gates, not a claim that implementation must proceed in
one linear work-package sequence. The Beads dependency graph is authoritative
for work that may run in parallel.

All product and protocol names use Techtree: Techtree Market, Techtree
Foundry, Techtree Climbs, Techtree Library, and `techtree.market.*`. Regents
Labs is only the company and service operator.

## Ownership boundary

The monorepo is the only v0.2+ source of truth.

- `platform/` owns Techtree Market, authenticated mutation APIs, listings,
  payment reconciliation, access control, and public discovery.
- `cli/` owns local execution, scientific state, proof construction, offline
  verification, and explicit publication transport.
- `plugin/` owns thin host-specific operator integrations. Hermes and Codex
  are separate consumers of the same CLI contract; future hosts may add more
  plugin packages without moving scientific rules into a plugin.

The platform must never become a dependency for local execution or proof
verification. Component work follows the root `AGENTS.md` plus the existing
component instruction file where one exists; this plan does not create
duplicate component `AGENTS.md` files.

## Scientific and commercial separation

A signed result proves only what its evidence establishes. A Market record
may point to that result, but payment, listing, acceptance, reputation, or
access status never changes the proof's scientific meaning. Market records
are separately versioned, signed, authorized, and replay-protected.

No optimizer sees hidden proving answers. No model or submitter approves its
own paid proving run, submission acceptance, payout, challenge resolution, or
private-data release.

## v0.2.x — Techtree Market proof pilots

The Market epic is `techtree-33x` and is blocked by v0.2.0. Market code stays
inside `platform/`; the local CLI and plugins remain usable without it.

### Independent reproduction linkage (`techtree-33x.1`)

Link a source Result to a new independently executed proof. The link binds the
source and reproduction digests, executor identities, configuration
compatibility, declared drift, and verification outcomes. A provider rerun by
the same participant is not an independent reproduction.

### Signed market records (`techtree-33x.2`)

Define signed, canonical `techtree.market.*` envelopes for `BountySpec`,
`Submission`, and `AcceptanceDecision`. Every record binds its schema,
issuer, subject digests, nonce or sequence, creation and expiry rules, and the
previous record where applicable. Decisions are append-only and cannot mutate
the submitted proof.

### Payee and payout reconciliation (`techtree-33x.3`)

Bind a verified payee-control assertion before acceptance can authorize a
payout. `PayoutIntent` describes the approved obligation; Safe execution is
observed and reconciled into a `PayoutReceipt`. Techtree never treats an intent
as payment and never initiates value transfer without the protected founder
packet and the required human or Safe signatures.

### Techtree Library (`techtree-33x.4`)

A Library listing is backed by a verified proof and its declared source
rights. Search and display preserve evidence facets and never create a
performance leaderboard or upgrade a participant assertion to provider
verification. The v0.2.x pilot distributes only public, digest-bound artifacts
and never executes them on the platform. Private or server-executed artifact
lanes remain blocked by the Foundry admission gate in `techtree-8dj.8`.

### x402 access contract (`techtree-33x.5`)

Lock the exact x402 protocol, network, asset, price semantics, access grant,
expiry, replay behavior, and artifact digest before implementation. Access to
an artifact does not grant source, training, redistribution, or derivative
rights unless the signed record explicitly says so. The v0.2.x lane does not
execute purchased artifacts or admit private data.

### Authenticated agent API (`techtree-33x.6`)

This ticket owns the shared authentication, authorization, request-envelope,
replay, and abuse-control contract. Authenticated mutations require explicit
authorization, domain-separated
signatures, replay protection, idempotency, rate and size bounds, abuse
controls, and an audit trail. Public reads stay separate from mutation
authority. A wallet, account, or agent identity does not imply payee control.
Payout, Library, and x402 domain endpoints remain owned by their respective
tickets and cannot conform until those domain contracts are locked.

### Proof Relay protected decision

Proof Relay parameters are protected founder decisions. Before any payment or
public pilot, the approval packet must name:

- operators and participant cap;
- exact amount, chain, token, and Safe;
- required signers and spending ceiling;
- challenge window and challenge authority;
- acceptance policy and decision authority; and
- rollback, reconciliation, and public-disclosure rules.

The approval binds one immutable `BountySpec` and packet digest, its expiry,
and the expected pre-action state. Any material change requires a new packet.

The packet is the pilot gate. No sponsor or unpaid rehearsal is required, and
no current plan value should be mistaken for authorization.

## Mandatory Market security gates

Before a Market pilot, focused review must establish:

- canonical signed records and signature domain separation;
- authenticated mutations and object-level authorization;
- replay, duplicate, expiry, and abuse controls;
- verified payee control independent of participant identity;
- payout intent, Safe execution, and payout receipt reconciliation;
- explicit challenge and acceptance authorities;
- isolation of executable artifacts from platform and reviewer credentials;
- private-data classification, retention, access, and redaction rules; and
- a locked x402 protocol and payment/access contract.

Failure of any applicable gate blocks the pilot. It is not converted into a
weaker trust label.

## v0.3 — Techtree Foundry and the first Skill Climb

The Foundry epic is `techtree-8dj`. The first Skill Climb appears here, not in
v0.2.0 or v0.2.x.

### Source rights (`techtree-8dj.1`)

`SourceBundle` records bind origin, content digest, declared rights, permitted
uses, confidentiality, and lineage. Import is refused when required rights are
missing or contradictory.

### Environment compilation (`techtree-8dj.2`)

Techtree Foundry compiles a source bundle into a versioned
`EnvironmentBlueprint`. Compilation is deterministic where promised and emits
a receipt binding tools, dependencies, network policy, task material, and
unresolved requirements.

### Environment and verifier separation (`techtree-8dj.3`)

Task execution and scoring are separate capabilities. Subjects cannot read
hidden verifier code, answers, held-out data, or privileged credentials.
Failure to achieve the declared isolation strength blocks the proving use.

### Membership and isolation (`techtree-8dj.4`)

Development, validation, and proving memberships are explicit, disjoint where
required, digest-bound, and auditable. Receipts state the actual isolation
strength rather than a binary “secure” claim.

### Validation receipts (`techtree-8dj.5`)

Environment-build and task-set validation receipts bind compiler inputs,
outputs, checks, failures, task identity, verifier identity, and evidence
availability without exposing private task or answer material.

### Search lineage (`techtree-8dj.6`)

Candidate lineage and search receipts bind parent candidates, allowed
mutation, prompts or programs, budgets, observed development evidence, and
selection decisions. They never include proving answers or authorize paid
execution.

### Private Skill Climb (`techtree-8dj.7`)

The first Skill Climb uses private development and proving material, an
admitted environment/verifier boundary, lineage receipts, explicit approval,
and independently verifiable result evidence. It is blocked by the relevant
Market signing, payee, authorization, and reconciliation contracts.

### Private and executable artifact admission (`techtree-8dj.8`)

Private data and executable artifacts require declared owners, rights,
retention, egress, isolation, sandbox, capability, size, and cleanup policies.
An artifact that cannot meet the declared boundary is rejected before use.

### Customer Foundry pilot (`techtree-8dj.9`)

The pilot begins only after the private Skill Climb gate passes. Its packet
binds the customer-authorized data, rights, participants, spend, disclosure,
acceptance, and deletion policies.

## Deferred v0.3.x studies

Epic `techtree-5t7` is deferred until Foundry and Skill Climb evidence exists.
Its children study Prime Agent (`.1`), prime-rl (`.2`), model uplift (`.3`),
harness artifacts (`.4`), a Fabric Harness Climb (`.5`), Relay cross-harness
metrics (`.6`), environment quality (`.7`), and environment utility (`.8`).
Study output is evidence for later decisions, not an implicit product promise.

## Completion rules

- v0.2.x is complete only when each shipped Market record verifies, mutations
  are authenticated and replay-safe, proof download and withdrawal semantics
  remain correct, and any payout is reconciled from an approved intent to a
  verifiable receipt.
- v0.3 is complete only when source rights, environment compilation,
  environment/verifier separation, set membership, isolation strength,
  validation receipts, lineage, the private Skill Climb, and the customer
  pilot all satisfy their explicit gates.
- No paid action, production deployment, contract lock, package release, or
  public pilot occurs without the exact founder approval required for that
  protected action.
