# Techtree v0.2 ticket ledger

This is the monorepo backlog for the binding
[`v0.2 implementation contract`](../plan/v0.2.md). Each implementation ticket
owns one work package. A ticket may be split into component-sized delivery
tasks, but a child must inherit the same work-package boundary and may not
invent a second architecture.

The seven tickets below are ordered dependencies. WP0 blocks WP1; WP1 blocks
WP2, WP3, and WP4; WP2 blocks WP3 and WP6; WP3 and WP4 block WP5. The full
release gate runs only after WP5 and WP6.

| Work | Bead |
| --- | --- |
| v0.2 epic | `techtree-31k` |
| WP0 | `techtree-31k.1` |
| WP1 | `techtree-31k.2` |
| WP2 | `techtree-31k.3` |
| WP3 | `techtree-31k.4` |
| WP4 | `techtree-31k.5` |
| WP5 | `techtree-31k.6` |
| WP6 | `techtree-31k.7` |

The inherited maintenance tickets are `techtree-31k.8` through
`techtree-31k.12`, in the same order as the maintenance list below.

## V2-WP0 — Lock authority and upstream contracts

Priority: P0  
Type: decision and conformance  
Owner: cross-component

Deliverables:

- Audit the website, README, roadmap, and release-note sources for the binding
  v0.2 release identity.
- Lock one execution-plan digest per Campaign and the generic compatibility
  rules.
- Confirm that the v0.1 publication and withdrawal schemas are the inherited
  write contract.
- Complete sanitized contract spikes for Verifiers, Prime Hosted Evaluations,
  Fabric, and Relay.
- Replace every pending field in `UPSTREAM_CONTRACT_LOCK.json`, freeze it, and
  record the founder approval that authorized each adopted coordinate.
- Populate `FABRIC_CAPABILITY_MATRIX.json` from descriptor claims, Techtree
  conformance evidence, and explicit release admission.

Acceptance:

- No production integration has an unresolved version or API shape.
- Fixture responses contain no secret or private trace material.
- Discovery of a newer upstream version does not alter the lock.
- Every remaining v0.2 ticket links to exactly one work package.

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
- Collapse current writes to the five durable states and add read-only v0.1
  projectors.
- Generate canonical schemas, goldens, tamper cases, and consumer fixtures.

Acceptance:

- Every frozen v0.1 proof remains byte-identical and verifies with the same
  normalized outcome and claim semantics.
- No historical reader rewrites old evidence or revives an old write shape.
- An undeclared Campaign difference is incompatible.
- Invalid or indeterminate comparisons cannot headline uplift.
- Any changed plan, budget, account, or expired estimate invalidates approval.

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

## V2-WP4 — Add Prime Hosted Evaluations

Priority: P0  
Type: paid remote execution  
Owner: `cli/`

Deliverables:

- Publish and pin one tiny deterministic Prime conformance environment.
- Implement estimate, approval, submit, reconcile, collect, cancel, and
  interrupted two-arm recovery against the provider's real topology.
- Bound, hash, sanitize, canonicalize, and persist provider responses in the
  specified order.
- Keep provider transport commitments separate from persisted sanitized
  records.

Acceptance:

- A hosted comparison reconstructs from durable provider identities and
  provider-fetched results without manual substitution.
- Both arms use the same exact environment version and pair every task.
- No create request occurs without unexpired plan-bound spend approval.
- Ambiguous submission never automatically creates a duplicate paid job.
- Tests cover estimate expiry, post-approval plan change, baseline-only create,
  ambiguous second arm, lost provider ID, partial collection, and cancellation.
- No reusable credential enters arguments, intent records, logs, receipts, or
  proof material.

## V2-WP5 — Publish reruns and evidence facets

Priority: P1  
Type: proof and public platform  
Owner: `cli/` and `platform/`

The `ash-regents` skill is required for every `platform/` implementation task.

Deliverables:

- Add a new proof and compatibility comparison for every provider-hosted rerun;
  never mutate the original.
- Extend the existing publication submission, receipt, withdrawal, and public
  Result projection rather than creating a parallel protocol.
- Show integrity, controlled-comparison validity, location, cumulative
  observation, trace coverage, model pin strength, Skill projection, and every
  rerun separately.
- Add filters by Climb, Skill, harness, model, location, trace coverage, and
  rerun kind without adding a “top” sort.

Acceptance:

- Repeating a publication returns the same accepted entry and a verifiable
  server-signed receipt.
- Withdrawal is replay-safe, appends a tombstone, and removes discovery without
  mutating the proof.
- Public copy says “Prime run reference captured” for participant-captured
  records and never upgrades that to provider verification.
- Private evidence commitments are not described as independently rechecked.
- Invalid or indeterminate comparisons do not display uplift as their headline.

Inherited ticket reconciled here:

- `techtree-python-8j2.9` — public evidence projection, reruns, bundle access,
  and withdrawal. Its old claim that v0.1 lacked publication is superseded by
  the shipped v0.1 publication protocol.

## V2-WP6 — Add Codex as a stable subject and operator

Priority: P1  
Type: subject and operator integration  
Owner: `cli/` plus Codex integration packaging

Deliverables:

- Admit the Codex Fabric adapter through the same generated capability matrix
  and conformance suite.
- Add Codex operator packaging over Techtree's existing machine contract.
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

## Moved out of v0.2

These old tickets are retained as context but belong to v0.3 or discovery:

- `techtree-python-cjj` and `techtree-python-8ti` — automatic Skill search,
  optimizer selection, development/proving split, and training direction.
- `techtree-python-8j2.12` — `techtree up`, local daemon, dashboard, and control
  plane.
- `techtree-python-8j2.10` — generated versioned CLI documentation.

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
