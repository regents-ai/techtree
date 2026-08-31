# Techtree v0.2 WP0 decision ledger

Status: binding input to WP0  
Recorded: 2026-08-31  
Authority: founder answers to the WP0 grilling pass

This ledger constrains WP0. It does not claim that any production Prime,
Fabric, Relay, or Codex integration is implemented.

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
- Withdrawal removes a Result from normal discovery while preserving its
  direct withdrawn page, immutable proof, immutable publication receipt, and
  append-only tombstone.
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

Read-only `prime teams list` discovery on 2026-08-31 returned no available
organization/team for the current operator. No personal account is selected as
a fallback. The proposed environment name remains
`<organization>/techtree-v02-conformance`; publication is blocked until an
organization exists or the founder explicitly approves temporary personal
ownership.

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
