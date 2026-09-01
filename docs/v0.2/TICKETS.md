# Techtree v0.2 ticket ledger

This is the monorepo backlog for the binding
[`v0.2 implementation contract`](../plan/v0.2.md) and
[`Market and Foundry roadmap`](../plan/techtree-market.md). Each implementation ticket
owns one work package. A ticket may be split into component-sized delivery
tasks, but a child must inherit the same work-package boundary and may not
invent a second architecture. The founder choices constraining WP0 are recorded
in [`DECISION_LEDGER.md`](DECISION_LEDGER.md).

v0.2.0 ships WP0, WP1, WP2, WP3, WP5, and WP6. WP0 blocks WP1; WP1 blocks WP2
and WP3; WP2 blocks WP3 and WP6; WP3 blocks WP5. The v0.2.0 release gate runs
only after WP5 and WP6.

WP4 — Prime Hosted Evaluations — is v0.2.x by founder decision of 2026-09-01,
recorded in [`DECISION_LEDGER.md`](DECISION_LEDGER.md). It depends on WP1 and
WP5 and is not part of the v0.2.0 gate. Its Bead `techtree-31k.5` and its
number do not change; it is re-parented under the v0.2.x hosted-execution epic
`techtree-k7t`. So `techtree-31k` closes for v0.2.0 when its v0.2.0 children
close, and Techtree Market (`techtree-33x`) keeps waiting on `techtree-31k`.

| Work | Bead | Release |
| --- | --- | --- |
| v0.2.0 epic | `techtree-31k` | v0.2.0 |
| v0.2.x hosted-execution epic | `techtree-k7t` | v0.2.x |
| WP0 | `techtree-31k.1` | v0.2.0 |
| WP1 | `techtree-31k.2` | v0.2.0 |
| WP2 | `techtree-31k.3` | v0.2.0 |
| WP3 | `techtree-31k.4` | v0.2.0 |
| WP4 | `techtree-31k.5` | v0.2.x |
| WP5 | `techtree-31k.6` | v0.2.0 |
| WP6 | `techtree-31k.7` | v0.2.0 |

The inherited maintenance tickets are `techtree-31k.8` through
`techtree-31k.12`, in the same order as the maintenance list below.

WP0 is itself an epic with eight children:

| Work | Bead | Primary ownership |
| --- | --- | --- |
| Recovery, retrospective, and release identity | `techtree-31k.1.1` | root docs and `platform/` |
| Verifiers and deterministic environment contract | `techtree-31k.1.2` | `cli/` |
| Prime Hosted contract spike | `techtree-31k.1.3` | `cli/` |
| Fabric Hermes/Codex capability admission | `techtree-31k.1.4` | `cli/` and `plugin/` |
| Relay, ATOF, ATIF, and coverage profiles | `techtree-31k.1.5` | `cli/` |
| CLI v2 machine contract and multi-plugin map | `techtree-31k.1.6` | `cli/` and `plugin/` |
| Publication inheritance, result envelope, bundle access, privacy, and withdrawal | `techtree-31k.1.7` | `cli/` and `platform/` |
| Proposed lock and founder approval packet | `techtree-31k.1.8` | cross-component |

`.1.1` establishes the corrected baseline. After it completes, `.1.2`, `.1.4`,
`.1.6`, and `.1.7` may proceed in parallel. `.1.3` depends on `.1.2`; `.1.5`
depends on `.1.4`; and `.1.8` depends on every other WP0 child. It no longer
carries a Prime stop/go, and today only `.1.5` remains open ahead of it.

`.1.3` is closed with its blockers recorded rather than resolved. It holds the
exact `prime==0.6.31` / `prime-evals==0.2.3` artifacts, the public OpenAPI
bytes, bounded CLI and source captures, and seven sanitized read-only responses
observed on 2026-09-01. Four machine reads are observed and admitted as read
shapes — the environment listing, the environment status read, the environment
action listing, and the evaluation listing — each with its limits recorded
beside it. The conformance environment is published. Six upstream blockers
stand unchanged, and the hub `tags` gap is a seventh; the capture proves read
shapes, not upstream guarantees, so it closes WP0.3 without admitting a hosted
runner.

The responses WP4 still needs — evaluation get, samples, hosted logs, hosted
stop, and hosted create — produced nothing in that capture and are re-homed to
WP4 in v0.2.x. They gate nothing in v0.2.0.

## V2-WP0 — Authority, discovery, conformance, and upstream contract lock

Priority: P0  
Type: decision and conformance  
Owner: cross-component

Deliverables:

- Document the two false-completion incidents and make evidence-backed
  completion language a permanent ticket rule.
- Audit the website, README, roadmap, and release-note sources for the binding
  v0.2 release identity. Never infer a Techtree release from a Climb name.
- Lock one execution-plan digest per Campaign and the generic compatibility
  rules.
- Lock `techtree.cli.v2`, typed next actions, stable operation identifiers,
  the public five-state projection, and bounded `run.wait`. Do not create a v1
  adapter, dual mode, second command hierarchy, daemon, or busy-poll loop.
- Confirm that the v0.1 publication and withdrawal schemas are inherited. Ship
  exact stored submission bytes at the metadata route's `/bundle` child and
  `410 Gone` for withdrawn bundle downloads. Lock
  `techtree.published-result.v1` as the metadata route's target envelope, for
  WP5 to cut over to with the facets it carries. Do not add
  `/api/v1/results`.
- Complete sanitized contract spikes for Verifiers, Fabric, and Relay, and
  capture the Prime Hosted Evaluations contract as far as the upstream surface
  supports, recording every unsupported behaviour by name.
- Test the newest stable upstream release first. The already identified
  `verifiers==0.3.2.dev17` is an allowed fallback spike candidate, not an
  automatic release lock.
- Record the `plugin/hermes/` and `plugin/codex/` target layout without moving
  the current Hermes plugin or creating a shared runtime SDK in WP0.
- Replace every pending field in `UPSTREAM_CONTRACT_LOCK.json`, prepare the
  exact founder approval packet, and keep the lock proposed until that digest
  is approved.
- Populate `FABRIC_CAPABILITY_MATRIX.json` from descriptor claims, Techtree
  conformance evidence, and explicit release admission.

Acceptance:

- No production integration has an unresolved version or API shape.
- Fixture responses contain no secret or private trace material.
- Discovery of a newer upstream version does not alter the lock.
- Every remaining v0.2 ticket links to exactly one work package.
- The Prime environment owner is the `@techtree` organization account,
  displayed locally as Regents Labs. Its zero-cost publication packet was
  approved and executed on 2026-09-01:
  `techtree/techtree-v02-conformance@0.1.0` is public, built from
  `cli/tests/conformance/prime_environment` with
  `SOURCE_DATE_EPOCH=1704067200`, wheel
  `sha256:ceca3bf0a8af32dde48230bce59a89ee77b6d330f4c09d050d05c055f538a6e0`.
  No evaluation was created and no paid run occurred. Prime's hub Integration
  Test passes install and import and fails only on a non-standard `tags`
  metadata requirement; whether to republish for it is open as
  `techtree-2qy`, and it does not gate v0.2.0.
- Prime's immutable-selection and machine-read contracts are inadmissible. The
  gate is not demoted or relaxed: WP4 moved to v0.2.x instead, and v0.2.0 ships
  with local execution only.

## V2-WP1 — Version the protocol and preserve v0.1 evidence

Priority: P0  
Type: protocol and migration  
Owner: `cli/`, with consumers updated in `plugin/` and `platform/`

Deliverables:

- Add the Campaign-bound four-plane execution plan.
- Add JSON-Pointer compatibility policies for backend parity and reruns.
- Add comparison validity, cumulative execution observation, reproduction
  lists, evidence artifact availability, exact estimates and approvals, hosted
  two-arm topology, and remote reconciliation state.
- Retain detailed append-only run phases and project them to the five public
  states.
- Replace `techtree.cli.v1` directly with `techtree.cli.v2`, including typed
  next actions and bounded `run.wait`, and add read-only v0.1 projectors.
- Generate canonical schemas, goldens, tamper cases, and consumer fixtures.

Acceptance:

- Every frozen v0.1 proof remains byte-identical and verifies with the same
  normalized outcome and claim semantics.
- No historical reader rewrites old evidence or revives an old write shape.
- An undeclared Campaign difference is incompatible.
- Invalid or indeterminate comparisons cannot headline uplift.
- Any changed plan, budget, account, or expired estimate invalidates approval.
- Hermes and Codex consumers migrate directly to v2; there is no compatibility
  adapter or dual-mode period.

Inherited tickets reconciled here:

- `techtree-python-999` — five-state durable lifecycle and public projection.
- `techtree-python-cwa` — read-only historical readers.
- Provider-coordinate portions of `techtree-python-yqj`.

## V2-WP2 — Establish Fabric-Hermes parity

Priority: P0  
Type: subject backend  
Owner: `cli/` and `plugin/`

Deliverables:

- Implement Fabric discovery, plan, Doctor, admission, execution, collection,
  and cleanup for Hermes.
- Produce Fabric plan, subject execution, and Skill projection receipts.
- Represent the empty baseline without a fabricated Skill digest.
- Run direct and Fabric Hermes as separate Campaigns linked by the parity
  compatibility policy.
- Support admitted Hermes-selected local providers, including Hermes-supported
  OpenAI and Anthropic subscription authentication, without copying reusable
  credentials into Techtree.

Acceptance:

- Deterministic direct/Fabric runs match on task membership, model requests,
  tool calls and results, rewards, aggregation, terminal class, and proof
  semantics; only declared backend evidence differs.
- Baseline and candidate use fresh runtimes and identical projection policy.
- Unsupported provider, model, tool, or projection requirements fail before
  spend with a repair action.
- Doctor and approval identify the non-secret provider, model, auth mode, and
  account that bears usage.
- Prime, OpenAI subscription, and Anthropic subscription paths have credential
  canaries and within-provider symmetry tests.

Inherited tickets reconciled here:

- `techtree-python-fqi` — Hermes-selected provider execution.
- Runtime portions of `techtree-python-yqj`.

## V2-WP3 — Add bounded Relay evidence

Priority: P1  
Type: evidence backend  
Owner: `cli/`

Deliverables:

- Add versioned adapter-specific Relay coverage profiles.
- Derive expected event IDs from declared sources and calculate coverage.
- Capture ATOF first, derive or collect ATIF, correlate events, and bind
  evidence availability.
- Implement the required teardown order and delivery diagnostics.

Acceptance:

- `not_requested`, `unavailable`, `incomplete`, and
  `complete_for_profile` are distinguishable and fixture-covered.
- Complete coverage cannot be manually asserted or achieved by shrinking the
  denominator.
- Relay-off and Relay-on deterministic runs are identical in all scientific and
  subject interactions; only evidence artifacts differ.
- Late registration, missing root scope, failed flush, dropped events,
  serialization failure, sink failure, and hard process death are covered.

## V2-WP5 — Publish evidence facets and exact public bundles

Priority: P1  
Type: proof and public platform  
Owner: `cli/` and `platform/`

Depends on WP3 only.

The `ash-regents` skill is required for every `platform/` implementation task.

Deliverables:

- Extend the existing publication submission, receipt, withdrawal, and public
  Result projection rather than creating a parallel protocol.
- Persist the evidence facets and, in the same cutover, replace the inherited
  `techtree.publication-entry.v1alpha1` envelope at
  `GET /api/v1/publications/:bundle_digest` with
  `techtree.published-result.v1`. Renaming earlier than the facets is the
  narrower question at
  [`PUBLICATION_WITHDRAWAL_AUDIT.md`](PUBLICATION_WITHDRAWAL_AUDIT.md) §7.2 and
  defaults to no. WP0.7 already ships the exact stored submission bytes at
  `GET /api/v1/publications/:bundle_digest/bundle` without re-encoding, and no
  `/api/v1/results` route is added.
- Settle §7.1 of that audit — what withdrawal removing a Result from discovery
  means against v0.1's shipped decision to keep a withdrawn entry visible and
  marked — before building the filtered surfaces that depend on the answer.
- Show integrity, controlled-comparison validity, location, cumulative
  observation, trace coverage, model pin strength, and Skill projection
  separately.
- Add filters by Climb, Skill, harness, model, location, and trace coverage
  without adding a “top” sort.

Acceptance:

- Repeating a publication returns the same accepted entry and a verifiable
  server-signed receipt.
- Withdrawal is replay-safe, appends a tombstone, and removes discovery without
  mutating the proof; metadata and receipt remain, while bundle download
  returns `410 Gone`. Active downloads use `Cache-Control: no-store`; copies
  downloaded before withdrawal remain independently verifiable.
- Private evidence commitments are not described as independently rechecked.
- Invalid or indeterminate comparisons do not display uplift as their headline.

The rerun proof, the rerun filter, and the “Prime run reference captured”
public label belong to WP4 in v0.2.x, because v0.2.0 produces no provider
record to label.

Inherited ticket reconciled here:

- `techtree-python-8j2.9` — public evidence projection, bundle access, and
  withdrawal. Its old claim that v0.1 lacked publication is superseded by the
  shipped v0.1 publication protocol. Its rerun projection moves to WP4.

## V2-WP6 — Add Codex as a stable subject and operator

Priority: P1  
Type: subject and operator integration  
Owner: `cli/` plus Codex integration packaging

Deliverables:

- Admit the Codex Fabric adapter through the same generated capability matrix
  and conformance suite.
- Add Codex operator packaging over `techtree.cli.v2` and migrate Hermes to the
  same v2 contract without a v1 adapter.
- Record Codex Skill, MCP, model, tool, context, and runtime projection.

Acceptance:

- Unsupported normalized tool controls fail admission before spend.
- A fresh Codex session passes Doctor and completes one valid within-harness
  comparison.
- Hermes and Codex results disclose projection differences and are never called
  equivalent-harness comparisons.
- NemoClaw, Grok Build, and Pi remain preview-only and cannot block release.

Inherited ticket reconciled here:

- `techtree-python-8j2.11` — Fabric capability matrix and Codex path.

## Separate maintenance tickets

These remain useful v0.2 work but do not alter the seven-package architecture.
They should be implemented independently after the owning contract is stable:

- `techtree-python-ndq.3.42` — multi-file starter fetch and full-tree revision
  context. This does not authorize general whole-repository mutation.
- `techtree-python-ndq.3.36` — remove duplicate plugin CLI reads.
- `techtree-python-ndq.3.24` — report public task prompts generically when the
  next engine bundle is opened.
- `techtree-python-85a.2.6` — carry token and elapsed-time usage into Episode
  receipt metrics and regenerate affected goldens.
- `techtree-python-aww` — distinguish credential shape checks from a provider
  authentication probe without leaking credentials or spending unexpectedly.

Their monorepo ticket IDs are:

- `techtree-31k.8` — multi-file starter fetch and revision context (WP2).
- `techtree-31k.9` — duplicate plugin CLI reads (WP2).
- `techtree-31k.10` — generic public task prompts (WP0).
- `techtree-31k.11` — receipt token and elapsed-time usage (WP1).
- `techtree-31k.12` — credential shape versus authentication (WP2).

## Moved out of v0.2.0

`techtree-31k.5` (WP4, Prime Hosted Evaluations) moved to v0.2.x on 2026-09-01,
under the hosted-execution epic `techtree-k7t`, and has its own section below.
Its child `techtree-2qy` — whether to republish the conformance environment
with hub `tags` metadata — moved with it.

These old tickets are retained as context but belong to v0.3 or discovery:

- `techtree-python-cjj` and `techtree-python-8ti` — automatic Skill search,
  optimizer selection, development/proving split, and training direction.
- `techtree-python-8j2.12` — `techtree up`, local daemon, dashboard, and control
  plane.
- `techtree-python-8j2.10` — generated versioned CLI documentation.

## v0.2.x — Prime Hosted Evaluations (`techtree-31k.5`)

WP4 keeps its Bead, its number, and the design in
[`v0.2.md`](../plan/v0.2.md) §“Paid remote execution”. What changed is the
release it ships in, and its parent: it now sits under the v0.2.x
hosted-execution epic `techtree-k7t`.

- Priority: P0 for v0.2.x
- Type: paid remote execution
- Owner: `cli/`
- Depends on: WP1 and WP5

Deliverables:

- Pin the published `techtree/techtree-v02-conformance` environment and extend
  it to the hosted run and the provider-hosted rerun.
- Implement estimate, approval, submit, reconcile, collect, cancel, and
  interrupted two-arm recovery against the provider's real topology.
- Bound, hash, sanitize, canonicalize, and persist provider responses in the
  specified order.
- Keep provider transport commitments separate from persisted sanitized
  records.
- Add a new proof and compatibility comparison for every provider-hosted rerun;
  never mutate the original.
- Render every rerun separately, add the rerun-kind filter, and say “Prime run
  reference captured” for a participant-captured record without upgrading it to
  provider verification.

Admission gate, unchanged:

- Supported immutable environment selection and machine-readable Prime
  operations must exist upstream. Until they do, WP4 does not start, and no
  release demotes or relaxes this.
- A hosted comparison reconstructs from durable provider identities and
  provider-fetched results without manual substitution.
- Both arms use the same exact environment version and pair every task.
- No create request occurs without unexpired plan-bound spend approval.
- Ambiguous submission never automatically creates a duplicate paid job.
- Tests cover estimate expiry, post-approval plan change, baseline-only create,
  ambiguous second arm, lost provider ID, partial collection, and cancellation.
- No reusable credential enters arguments, intent records, logs, receipts, or
  proof material.

## v0.2.x — Techtree Market (`techtree-33x`)

This epic is blocked by `techtree-31k`. Market implementation belongs in
`platform/`; local execution and proof verification remain independent. The
`ash-regents` skill is required for every `platform/` implementation ticket.

| Work | Bead | Gate |
| --- | --- | --- |
| Independent reproduction linkage | `techtree-33x.1` | verified source and reproduction proofs |
| Signed `BountySpec`, `Submission`, and `AcceptanceDecision` | `techtree-33x.2` | canonical signed records and challenge authority |
| Payee binding, `PayoutIntent`, Safe reconciliation, and `PayoutReceipt` | `techtree-33x.3` | payee control and exact founder payment packet |
| Proof-backed Techtree Library listings | `techtree-33x.4` | rights and proof verification; public non-executing artifacts only in v0.2.x |
| x402 contract lock and artifact access | `techtree-33x.5` | exact network, asset, pricing, replay, and access contract; no private/server execution lane |
| Authenticated agent API core | `techtree-33x.6` | shared authorization, replay protection, idempotency, and abuse controls; domain endpoints stay in `.3`–`.5` |

Signed market records, authenticated mutations, payee control, payout
reconciliation, challenge authority, executable-artifact isolation,
private-data handling, and x402 locking are mandatory security gates. Proof
Relay parameters are protected founder decisions: operators, cap, amount,
chain/token, Safe, signers, challenge policy, acceptance policy, and spending
ceiling, plus rollback, reconciliation, and public-disclosure rules, must be
bound in one immutable `BountySpec` and packet digest with an expiry and
expected pre-action state before payment.

## v0.3 — Techtree Foundry and Skill Climb (`techtree-8dj`)

The first Skill Climb is v0.3 work. It is not part of v0.2.0 or the initial
Market proof pilot.

| Work | Bead |
| --- | --- |
| Source rights and `SourceBundle` provenance | `techtree-8dj.1` |
| `EnvironmentBlueprint` compilation | `techtree-8dj.2` |
| Environment and verifier separation | `techtree-8dj.3` |
| Development, validation, and proving membership plus isolation strength | `techtree-8dj.4` |
| Environment-build and task-set validation receipts | `techtree-8dj.5` |
| Candidate lineage and search receipts | `techtree-8dj.6` |
| First private Skill Climb | `techtree-8dj.7` |
| Private-data and executable-artifact admission | `techtree-8dj.8` |
| Customer Techtree Foundry pilot | `techtree-8dj.9` |

## Deferred v0.3.x studies (`techtree-5t7`)

These tickets stay deferred until Foundry and Skill Climb evidence exists.

| Study | Bead |
| --- | --- |
| Prime Agent | `techtree-5t7.1` |
| prime-rl | `techtree-5t7.2` |
| Model uplift | `techtree-5t7.3` |
| Harness artifacts | `techtree-5t7.4` |
| Fabric Harness Climb | `techtree-5t7.5` |
| Relay cross-harness metrics | `techtree-5t7.6` |
| Environment quality | `techtree-5t7.7` |
| Environment utility | `techtree-5t7.8` |

Environment Forge, held-out optimization, model training, broader stable
harnesses, independent reproduction networks, and incentives must not appear
as promised v0.2 work.

## Dispatch rule

Before implementation, create one delivery ticket per independently reviewable
component slice beneath the owning work package. A remote slice must specify
the durable state, next safe operation, whether spend may continue, forbidden
automatic retries, evidence that may still be issued, and public label for each
relevant interruption boundary in the implementation contract.

No ticket is complete until its focused tests and the model-free monorepo gate
pass. Paid conformance and staged publication run only with explicit founder
approval.
