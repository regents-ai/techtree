# Techtree delivery audit and implementation sequence

Date: September 6, 2026. Baseline: `68d5fd3390c8e1c4dd2dee7916f2efc67369bd29`.
Graph: Techtree’s own `.beads`, not Control’s graph.
Documentation ticket: `techtree-a2v`.

This is an evidence-backed delivery plan for the founder’s Techtree assignment.
It explains the existing contracts and proposes the missing collaboration work;
it does not silently replace upstream locks, release gates, or payment authority.
This pass edits documentation. It does not upgrade dependencies, integrate the
unfinished protocol branch, change production data, or activate a release.

## 1. Engineering recommendation

Finish one useful path: a local agent discovers a real Skill comparison, runs
it through a qualified Prime/NeMo integration, publishes inspectable evidence,
and another agent can reproduce or fork it. Then attach a bounded USDC
reproduction bounty. Use that path to decide which additional infrastructure
is worth building.

The architecture already has a sensible division of responsibility. Keep the
scientific kernel in Python, the public product and market in Ash/Phoenix, and
upstream runtimes behind narrow adapters. The biggest immediate problem is
unfinished integration and contradictory status records, not a demonstrated
need to rewrite the system. No deletion quota or broad test purge is justified
by this inspection.

Success for the next release is a reproducible comparison and honest evidence,
not the number of schemas, ticket closures, or mock assertions produced.

## 2. What was inspected

- Both supplied README drafts, root/component documentation, root instructions,
  platform instructions, Makefiles, v0.2 contracts and Market roadmap.
- All 76 pre-existing live Beads tickets, their dependency edges, active ticket
  details, local worktree heads/status, and main versus in-flight commit ranges.
- Recent platform, CLI, shared-profile, schema, and release-credential commits.
- CLI schema constant, Campaign models and bundle writer, proof-verification
  command, run lifecycle modules, publication routes, agent discovery text,
  upstream lock and founder packet, selected regression and copy-test sources.
- Public `/start` and `/api/v1/bootstrap`: both returned HTTP 200. Bootstrap
  advertised CLI `0.1.1`, its pinned wheel, and the legacy pinned Hermes plugin.
  This checks the published contract, not successful installation or paid execution.
- Official Prime Verifiers and NVIDIA Fabric/Relay documentation, linked below.

This is a targeted architecture and delivery audit, not a complete security
review. Existing application tests, actual model evaluation, wallet signatures,
provider verification, package installation and production cutover were not
rerun in this documentation task. Local commit presence is not deployment proof.

## 3. README decisions

The supplied improved draft provides the right research direction, separates
operator from subject, and correctly limits participant-attested proof. Its
long research exposition would obscure the first useful action for a casual
GitHub visitor. The edited README keeps the entry point and capability table
near the top and puts deeper comparison/economic detail behind disclosures.

Corrections made against this checkout:

- Keep all four component owners, including the newly imported `contracts/`.
- Identify v0.1.1 from the actual public bootstrap and local release record.
  Distinguish partial v0.2 code on main from an end-to-end released v0.2 path.
- Preserve the pinned start guide, historical-plugin caveat, setup prerequisites,
  shared-library requirement, Foundry gate, and existing product/GitHub links.
- Explain collaboration, forks, messages, and USDC as the requested direction,
  not existing endpoints or approved payment terms.
- Retain proof limitations, same-membership Hello World caveat, local-first
  privacy, and the separation of evaluation, hosting, harness and evidence.
- Link existing plans for Foundry, managed search and training rather than
  turning every research paragraph into an implementation commitment.

The two user-supplied files remain untouched. Their editorial instructions
were treated as suggestions and checked against the repository.

## 4. Current delivery state

### Recent main changes

| Commit(s) | What landed locally | Implication |
| --- | --- | --- |
| `68d5fd3`, `ef5bbed` | Explicit migration credentials and the selected Techtree schema, including publication sequence | Preserve these during integration. Production migration success cannot be inferred from these commits. |
| `18100f8`, `4d27684` | Shared profiles, private adapters, and local boundary/browser fixes | A v2 CLI merge must include the newer profile operations, and profile identity must not replace publication-key authority. |
| `ed0503a` | Human onboarding and agent discovery | Preserve related-product links; update capability claims only with matching implementation evidence. |
| `d9394ea`, `6b1dccb` | Registry checks and contracts imported into monorepo | Old three-component docs and setup instructions are stale. |
| `9a9b7d0`, `a52e651`, `573634a` | Shared visual foundations and removal of incidental test-count coupling | Reuse shared primitives; do not reintroduce page-specific design or test-count rules. |
| `b27cd4f`, `45e3520`, `1e7e6b8`, `1a57ae5`, `43228f2`, `9515aa5` | v2 run documents, evidence models, execution plan, state projection/waiting, historical readers and compatibility policy | These are building blocks. The live CLI constant remains `techtree.cli.v1`; the bundle writer still consumes `CampaignSpec`. |

### In-flight work

There were 13 registered worktrees including main at inspection. The four
in-progress tickets are below. Their worktrees were clean at inspection;
clean means no uncommitted edits, not complete or abandoned. No writer was
interrupted and no worktree was removed.

| Ticket | Observed work | Disposition |
| --- | --- | --- |
| `techtree-5qe` | Three commits absent from main, ending `5b47bf7`; 124 files, 5,536 additions / 2,070 deletions relative to merge base. Last commit September 2. | Recover this branch rather than reimplementing CLI v2. A non-checkout `git merge-tree` simulation found no textual conflicts, but that is not semantic compatibility. It predates shared-profile operations. The final ticket comment records two completed review obligations and one unfinished refusal-test obligation; rerun the merged CLI/plugin contract before integration. |
| `techtree-di5` | Worktree at `239d7ab`, already reachable from main; no unique commits. Ticket promises the live Campaign v2 cutover, while main’s bundle writer still uses `CampaignSpec`. | Real unfinished work, not a closure candidate. September 2 comments record approval to prepare release identity `climb-v0.2.0` / CLI `0.2.0`; exact regenerated publication digests still need their release packet. Resume the producer/reader cutover, keeping historical bytes intact. It blocks `5qe`. |
| `techtree-5a8` | Onboarding commit `ed0503a` is on main; ticket notes say reviewed and integrated, with no active writer. | Closure candidate after reconciling recorded review evidence with the current lifecycle validator; do not repeat the implementation. |
| `techtree-781` | Old profile candidate `a91eac3` remains on its branch. Ticket notes explicitly supersede it with integrated `techtree-zko` / `18100f8`. | Mark the local candidate superseded after validating the successor record. Preserve real four-origin/provider and production acceptance on **Control graph `regent-qht.28`**. Do not merge the old profile branch again or claim live identity verification. |

Ticket comments provide a more useful handoff than the status field alone:

- `5qe` was explicitly stopped cleanly on September 2. At `139348f`, the
  historical independent re-review reported no P0/P1 findings but obligations.
  `4682b62` adds withdrawal review binding; `5b47bf7` replaces personal-path
  Doctor fixtures. The four-refusal test still needs review-binding and effect
  classification assertions; lower-priority parser/guard cleanups and final
  gates were not completed. Historical test totals are evidence for those old
  inputs only, not approval of a merge with today’s main.
- `di5` comments record approval to prepare the v0.2 identity, then confirmation
  of release ID/version and retained host bounds. Do not ask those choices
  again or leave preparation blocked on them. Prepare exact regenerated bytes
  separately from publication. The comments also carry concrete follow-ups:
  v2 manifest comparison, engine-digest agreement and signed receipt/report goldens.
- `5qe` comments explicitly correct an earlier claim that packet answers 1–6
  had been approved. They are reversible working defaults, not recorded exact
  lock adoption. Preserve this distinction when cleaning up stale blockers.

The Codex task inventory showed the active parent “September Chief” and this
Techtree fork, but no separate active Techtree implementation task in the returned
inventory. That limited inventory does not prove an older task or external writer
is inactive; reconcile custody before resuming either protocol worktree.

### Ticket health

Before this audit ticket, the graph contained **76 tickets: 28 closed, 33 open,
4 in progress, 2 blocked, and 9 deferred**. The appendix records each ticket.

The intended dependency chain is mostly represented: WP1 → Fabric parity →
Relay → public evidence, with Codex following Fabric. Hosted work stays in its
own v0.2.x epic. Three repairs are needed before dispatch:

1. The prose ledger still says only WP0.5 remains open ahead of WP0.8. Both are
   closed in live Beads. Use live status, and remove this dated sentence during
   the lock/status reconciliation ticket.
2. `techtree-31k.14` is blocked for lock adoption, but has **no blocking dependents**
   in the graph. The lock itself remains proposed and answer slots remain empty.
   Record actual accepted decisions; add explicit prerequisite edges only to
   work that requires the adopted integrations. Do not invent founder answers
   or make documentation/protocol preparation wait on unrelated spending gates.
3. `techtree-q6g` says the founder will name a real Skill and requests held-out
   tasks, while v0.2 otherwise defers private proving to v0.3. Distinguish a
   useful engineering demonstration from a held-out improvement claim. Recover
   any later choice; otherwise propose one concrete public environment and Skill
   under this mandate. Do not call repeatedly used parity cases untouched proof.

Do not close old tickets based on title similarity or delete historical tracking.
`techtree-a2v` is the only new implementation ticket created in this pass. The
new forum tickets below are proposed subdivisions, not silently activated work.

## 5. Architecture and instruction findings

### Preserve the useful boundaries

- Verifiers owns tasks and reward; Fabric owns harness lifecycle; Relay supplies
  observed evidence. Techtree binds the experiment and checks its claims.
- Ash owns product resources, actions and authorization. Public profiles,
  publication signing identities and payout authorities remain distinct.
- CLI owns durable local execution. A website outage must not prevent local
  proof verification. Plugins stay thin; no new daemon or parallel evaluator.
- Continue using the shared identity and UI libraries. Techtree product data
  stays in its owned schema. No database redesign is needed for this plan.

### Demonstrated friction and recommended fixes

| Evidence | Problem | Smallest useful change |
| --- | --- | --- |
| `Makefile` runs `mix deps.get`, asset setup and build inside `check-platform` | The full check includes setup/network work, so it is not a purely check-only command | Separate prepare from verification in the existing targets; document fresh-checkout setup. Record pinned dependencies and show that verification leaves tracked files unchanged. |
| `platform/AGENTS.md` has 365 lines; root still says “three component READMEs”; WP5 requires old `ash-regents` | Stale inventory and competing general guidance | Shorten platform guidance to local boundaries/commands; point relevant work to canonical Ash router/specialists. Preserve necessary Phoenix constraints in contextual references, not blanket pre-reading. |
| `cli/tests/contract/test_release_copy.py` is 1,503 lines; plugin removal tests pin headings and wording | Some safety/release checks coexist with incidental copy coupling | Retain checks that prevent misleading release claims, unsafe deletion commands and private-data exposure. Replace purely editorial assertions when touching those passages; do not erase the suite by line count. |
| `cli/src/techtree/cli/commands/run.py` is 1,191 lines; `runs/service.py` is 719 | Large change surface for the pending protocol merge | Complete the cutover first; then simplify repeated presentation/query conversions only where two consumers need the same behavior. File length alone is not a defect or reason for new abstractions. |
| `platform/README.md` says the application does not authenticate anyone, despite the shared-profile routes | Product documentation contradicts current main | Correct the profile exception during the focused docs reconciliation; retain publication-key separation. |
| Router comments claim one body-accepting address, while profile PATCH/POST routes now exist | Security commentary no longer describes the actual surface | Correct comments with the next router change; check each mutation’s real authentication/authorization rather than relying on the old comment. |
| `techtree-bb4` tracks personal home paths; old plugin/release coordinates remain | Public source portability and historical compatibility are different concerns | Remove accidental local paths from active docs/tooling with neutral fixtures. Preserve signed historical bytes and mark their legacy coordinates; do not bulk replace inside release artifacts. |
| Discovery text explicitly disclaims native WebMCP readiness; no native registration found in inspected app entrypoint | CLI and public API availability could be mistaken for browser-tool parity | Publish an explicit supported operation set and verify it in an actual WebMCP host before advertising readiness. |

This inspection did not establish that a redundant wrapper is safe to delete,
that a dependency is unused, or that the system is faster after a change. Those
claims need a specific consumer trace or before/after measurement.

## 6. Upstream adoption strategy

Use upstream capabilities to reduce Techtree code, while preserving exact
version admission. Current documentation is a discovery source, not permission
to alter the existing lock.

- **Prime Verifiers:** keep environments ordinary installable Verifiers packages
  so contributors can use the Prime ecosystem without Techtree. Reuse its task,
  evaluation and reward machinery. Qualify one useful public environment before
  adding a catalog of integrations. [Official overview](https://docs.primeintellect.ai/verifiers/overview),
  [source](https://github.com/PrimeIntellect-ai/verifiers).
- **NeMo Fabric:** reuse configuration, planning, Doctor and lifecycle APIs;
  qualify Hermes first, then Codex. Official guidance warns that optional
  capabilities vary by harness and that recent Hermes installation differs from
  older PyPI packaging. Compare that with the lock’s Hermes 0.19.0 rather than
  substituting a current install command into a frozen release.
  [Official README](https://github.com/NVIDIA/NeMo-Fabric),
  [compatibility guides](https://github.com/NVIDIA/NeMo-Fabric/tree/main/adapters).
- **NeMo Relay:** keep capture optional and observe-only for this comparison.
  Admit one coverage profile with missing-event and failed-export behavior.
  Retain native evidence; a normalized trace must not erase unknowns.
  [Official README](https://github.com/NVIDIA/NeMo-Relay).
- Keep hosted execution’s immutable selection, cost and reconciliation gaps
  explicit in WP4. Do not block local Verifiers adoption on hosted readiness.
  Prime Agent, GEPA and `prime-rl` stay later experiments; none is needed to
  deliver the first useful public comparison.

## 7. Implementation order and observable acceptance

Each row is a bounded delivery step. Reuse the listed tickets; put exact
acceptance and verification in the dispatched ticket. No estimates here are
promises of release dates or upstream readiness.

### A. Recover current work and remove contradictory blockers

**Tickets:** `31k.14`, `di5`, `5qe`, `5a8`, `781` (all prefixed `techtree-`).

1. Reconcile current writer custody and prior decisions. Close/supersede only
   the two integrated local tickets with their existing evidence. Record the
   source of remaining provider acceptance on the central graph.
2. Reconcile the exact upstream packet and real-task requirement. The v0.2 release identity already has a recorded preparation decision; retain it. Keep spent
   budget, publication, and payout authority separate from code preparation.
3. Finish `di5` in isolation: one live Campaign v2 producer path, separate
   historical readers, preserved frozen v0.1 bundles and normalized outcomes.
4. Bring `5qe` forward onto that candidate and current main. Include profile
   operations added since its branch point, error handling, typed next actions,
   cancellation, publication/withdrawal and plugin consumers in the same cutover.

**Done:** a model-free representative campaign completes, survives process
restart, reports a bounded wait result, and verifies offline; malformed or stale
intent fails before external effects. Every current command has the correct v2
machine response. Historical proof bytes remain unchanged. Run the affected
CLI and plugin suites, generated-artifact comparison and relevant type checks.
Review the public/protected boundary changes independently before integration.

### B. Deliver a useful Prime/Fabric comparison

**Tickets:** `31k.3`, `q6g`, relevant maintenance `31k.8`–`.12`.

Choose a concrete Skill/task family using an existing Prime environment where
rights and task membership are inspectable. Prefer an artifact-producing task
with an objective checker and a plausible Skill benefit over another synthetic
success demo. Run deterministic admission/parity first; paid evaluation follows
only with exact provider, budget and evidence destinations settled.

**Done:** direct and Fabric Hermes agree under the declared parity policy;
baseline/candidate task and tool state are isolated; missing capabilities fail
before spend; both successes and regressions produce accurate evidence. Show
what the Skill changed and what remained fixed. A small sample is labeled as
such, with no claim of statistical generalization. Avoid requiring measurable
positive uplift to consider the execution implementation correct.

### C. Add Codex and public evidence without duplicating the kernel

**Tickets:** `31k.7` alongside `31k.4`, then `31k.6`.

Build the Codex operator over the same CLI contract. Qualify the Codex subject
separately. Add optional Relay capture and show its status independently of task
score. Extend existing publication routes and stored bundle access; do not add
a second results protocol. Settle withdrawal discovery behavior before filters.

**Done:** an agent can discover, prepare, run, resume, inspect and explicitly
publish a result from the supported host. Another machine verifies the public
bytes. Incomplete trace capture remains visible; withdrawn bytes return 410;
private commitments are never shown as independently recomputed evidence.
No global “top” score mixes incompatible Campaigns.

### D. Build the first public collaboration loop

**Existing anchors:** `33x.1`, `33x.4`, `33x.6`. Add three bounded child tickets
under the Market epic when dispatched; current records do not cover these
features adequately. This is the founder’s new forum requirement, distinct
from deferred multi-agent research in `5t7`.

1. **Artifact forks and result discussions.** Reuse catalog/publication IDs.
   Represent an immutable artifact version with digest, declared license,
   author and parent digest. A fork makes a new artifact; discussion attaches
   to a stable artifact/result identity. Do not copy private traces or treat
   a fork as a verified improvement.
2. **Agent messages and collaboration controls.** Begin with paginated public
   threads/replies and addressed agent mentions. Defer private inboxes until
   their access/retention contract exists. Add edit/tombstone policy, size/rate
   limits, reporting and moderation. Treat Markdown, LaTeX and links as
   untrusted rendered content; no auto-execution of instructions or artifacts.
3. **Same actions through browser, API and CLI.** Ash named actions own reads
   and mutations; typed HTTP contracts expose them. CLI and browser tools use
   those contracts with their own verified caller context. Define pagination,
   stable IDs, errors and retry semantics once. Share operation semantics,
   not necessarily byte-identical transport envelopes. The browser cannot
   execute arbitrary local CLI commands; plugins cannot self-authorize spend.

**Done:** agent A publishes a public artifact, B forks with attribution, both
exchange a message, and B attaches a separately verified result. An unrelated
identity cannot edit either artifact or impersonate either author. Repeated
requests do not duplicate a submitted message; retrieval is bounded and complete.
An equivalent flow works through CLI and HTTP, then through a supported native
WebMCP host. A JavaScript fallback alone does not satisfy the last criterion.

**UI:** default pages show title, author, artifact type, evidence status and one
primary action. Put methodology, environment details and long discussion behind
keyboard-accessible chevrons. Semantic structured data remains available through
agent APIs; do not rely on hidden visual text as a protocol. Desktop, mobile,
empty/error states and focus should use shared Regent components.

### E. Pay for one independently reproduced result in USDC

**Tickets:** `33x.1` → `33x.2` → `33x.6` → `33x.3`.

Keep the first job narrow: reproduce a declared result with independently
attributable evidence. Record bounty terms, submission and acceptance separately.
Bind the payee’s control assertion and exact chain/token before the payout intent.
Use the planned operator/Safe-signed path; no agent wallet custody service or
new escrow contract is required for this initial path.

**Done before live payment:** isolated fixture-chain or mocked-receipt flows
cover acceptance, rejection, duplicate submission, wrong payee/chain/token,
expiry, ambiguous execution, failed/reverted transaction and reconciliation.
A payout intent is never presented as paid. Reconciliation links the actual
transaction, amount and beneficiary and cannot count the same payment twice.
Actual transfer requires the exact approved pilot packet and authorized signers.

For human wallet controls, preserve the Regent rule that every distinct press
reaches the wallet; handling duplicate domain obligations is separate from
suppressing a user’s wallet interaction. Preserve each rejection and receipt.

**Competition:** begin with transparent acceptance rules and independently
reproduced results. A Campaign-scoped contest with comparable frozen membership
can follow. The current Library plan forbids a performance leaderboard; amend
that scope explicitly before implementing any ranking. Do not introduce a
universal agent reputation score as a shortcut.

### F. Library access, Foundry and larger studies

**Tickets:** `33x.4`/`.5`, `k7t`/`31k.5`, then `8dj.*`; keep `5t7.*` deferred.

Public digest-bound Library distribution can proceed without executing purchased
artifacts. x402 access needs its exact protocol/network/asset/access contract;
it is separate from bounty adjudication and payout. Reuse a maintained protocol
implementation after admission instead of writing a payment verifier from scratch.

Foundry starts with rights/provenance, then environment compilation, verifier
isolation and separate memberships. Deliver one source-to-Verifiers environment
and one private Skill Climb before managed search or training orchestration.
Hosted execution is independent of the local product’s availability.

**Done:** artifact rights and digest survive publication/fork/access; private
material never leaks through public projections; candidate search cannot inspect
proving answers; the final frozen comparison can report a tie or regression.
Only then evaluate training or distributed-search integrations on measured need.

## 8. Verification and operating changes

Use one integrating owner. Recover existing branches rather than dispatching
new writers over their paths. Independent work can run in separate worktrees;
serialize protocol producer/consumer integration. Keep Techtree graph references
separate from cross-product Control tickets.

Run checks that protect the changed behavior. The README edit needs rendering,
links and factual reconciliation, not a full paid model run or new source-string
tests. The protocol cutover needs its existing broad CLI/plugin gates. Payments,
identity, private artifacts and proof-authority changes need the corresponding
independent review and failure-path evidence.

For the first product implementation, record setup time, focused check time,
full required gate time and any manual intervention. Split setup/check commands
using those observations. Do not claim faster verification until measured.

Completion reports must state exactly which UI, CLI, persistence, worker and
external-provider paths were exercised. A clean merge, a fixture pass, a
published environment and an accepted upstream lock each establish different
facts. None alone establishes an end-to-end working release.

## 9. Remaining decisions and limits

- The exact upstream adoption and 16 packet answers are not present as accepted
  records in the inspected lock. Broad implementation ownership does not justify
  fabricating historical answers; reconcile existing conversation evidence and
  make the smallest remaining design choices explicit before dependent work.
- Resolve the real-task requirement without conflating parity with held-out proof.
- Define public thread moderation and artifact rights before enabling mutations.
- Exact USDC pilot terms and signer authority remain attached to the payout packet.
- Confirm the deployed release/install path before retiring legacy plugin hosting.
- Full provider, model, native WebMCP, payment and production verification remains
  outstanding. No claim in this audit certifies those paths.

## Appendix: pre-existing live ticket snapshot

Statuses below are a September 6 snapshot, not a second live tracker. IDs are
in the Techtree graph. Parent labels alone are not dependency edges. The audit
ticket itself was created after this snapshot.

| Ticket | Status | Work |
| --- | --- | --- |
| `techtree-2qy` | open | Decide whether to republish the Prime conformance environment with hub tags metadata |
| `techtree-31k` | open | Techtree v0.2.0 — execution provenance and subject portability |
| `techtree-31k.1` | closed | V2-WP0 — Authority, discovery, conformance, and upstream contract lock |
| `techtree-31k.1.1` | closed | WP0.1 — Recover the planning baseline and lock release identity |
| `techtree-31k.1.2` | closed | WP0.2 — Lock the Verifiers candidate and deterministic environment contract |
| `techtree-31k.1.3` | closed | WP0.3 — Capture the Prime Hosted Evaluations contract |
| `techtree-31k.1.4` | closed | WP0.4 — Lock Fabric Hermes and Codex adapter capabilities |
| `techtree-31k.1.5` | closed | WP0.5 — Lock Relay, ATOF, ATIF, and coverage profiles |
| `techtree-31k.1.6` | closed | WP0.6 — Lock the CLI v2 machine contract and plugin map |
| `techtree-31k.1.7` | closed | WP0.7 — Lock publication projection, bundle access, withdrawal, and privacy |
| `techtree-31k.1.8` | closed | WP0.8 — Resolve Prime gates, freeze the proposed lock, and prepare approval |
| `techtree-31k.10` | open | V2 maintenance — report public task prompts generically |
| `techtree-31k.11` | open | V2 maintenance — receipt token and elapsed-time usage |
| `techtree-31k.12` | open | V2 maintenance — distinguish credential shape from authentication |
| `techtree-31k.14` | blocked | Adopt the founder-approved upstream lock and record the sixteen packet answers |
| `techtree-31k.15` | closed | V2 maintenance — align the v1 CLI surface documentation with the registered commands |
| `techtree-31k.2` | open | V2-WP1 — Replace the machine protocol and preserve v0.1 evidence |
| `techtree-31k.3` | open | V2-WP2 — Establish Fabric-Hermes backend parity |
| `techtree-31k.4` | open | V2-WP3 — Add bounded Relay evidence |
| `techtree-31k.5` | open | V2-WP4 — Add Prime Hosted Evaluations |
| `techtree-31k.6` | open | V2-WP5 — Publish evidence facets and exact public bundles |
| `techtree-31k.7` | open | V2-WP6 — Add Codex as a v2 subject and operator |
| `techtree-31k.8` | open | V2 maintenance — multi-file starter fetch and revision context |
| `techtree-31k.9` | open | V2 maintenance — remove duplicate plugin CLI reads |
| `techtree-33x` | open | Techtree v0.2.x — Market proof pilots |
| `techtree-33x.1` | open | Market 0.2.1 — Bind independent reproduction linkage |
| `techtree-33x.2` | open | Market 0.2.2 — Freeze signed bounty, submission, and acceptance records |
| `techtree-33x.3` | open | Market 0.2.3 — Bind payees and reconcile protected payouts |
| `techtree-33x.4` | open | Market 0.2.4 — Publish proof-backed Library listings |
| `techtree-33x.5` | open | Market 0.2.5 — Lock x402 artifact access |
| `techtree-33x.6` | open | Market 0.2.6 — Add authenticated agent API core and abuse controls |
| `techtree-5a8` | in_progress | techtree: public onboarding and product discovery |
| `techtree-5qe` | in_progress | WP1.6 — techtree.cli.v2 envelope cutover with typed next actions and Hermes consumer migration |
| `techtree-5s2` | closed | Align the CLI README truth test with the monorepo wording |
| `techtree-5t7` | deferred | Techtree v0.3.x — Training and harness studies |
| `techtree-5t7.1` | deferred | Study 0.3.x.1 — Admit Prime Agent as a native subject |
| `techtree-5t7.2` | deferred | Study 0.3.x.2 — Define the prime-rl training handoff |
| `techtree-5t7.3` | deferred | Study 0.3.x.3 — Define ModelUpliftReport |
| `techtree-5t7.4` | deferred | Study 0.3.x.4 — Define HarnessArtifact and state policy |
| `techtree-5t7.5` | deferred | Study 0.3.x.5 — Run a Fabric Harness Climb |
| `techtree-5t7.6` | deferred | Study 0.3.x.6 — Compare Relay cross-harness process metrics |
| `techtree-5t7.7` | deferred | Study 0.3.x.7 — Run an Environment Quality Climb |
| `techtree-5t7.8` | deferred | Study 0.3.x.8 — Run an Environment Utility Climb |
| `techtree-5xy` | closed | WP1.3 — Comparison validity, cumulative observation, evidence availability, reproduction lists, estimates and approvals |
| `techtree-781` | in_progress | Add the shared Regent profile with Privy and personal X verification |
| `techtree-8dj` | open | Techtree v0.3 — Foundry and Skill Climb |
| `techtree-8dj.1` | open | Foundry 0.3.1 — Bind SourceBundle rights and provenance |
| `techtree-8dj.2` | open | Foundry 0.3.2 — Compile EnvironmentBlueprint into Verifiers packages |
| `techtree-8dj.3` | open | Foundry 0.3.3 — Separate environments from verifiers |
| `techtree-8dj.4` | open | Foundry 0.3.4 — Bind development, validation, and proving membership |
| `techtree-8dj.5` | open | Foundry 0.3.5 — Issue environment build and taskset validation receipts |
| `techtree-8dj.6` | open | Foundry 0.3.6 — Record candidate lineage and search receipts |
| `techtree-8dj.7` | open | Foundry 0.3.7 — Run the first private Skill Climb |
| `techtree-8dj.8` | open | Foundry 0.3.8 — Enforce private-data and executable-artifact admission |
| `techtree-8dj.9` | open | Foundry 0.3.9 — Deliver the Techtree Foundry customer pilot |
| `techtree-99r` | closed | Verify frozen v1alpha1 schemas instead of regenerating them |
| `techtree-bb4` | open | Remove personal home paths from tracked files in the public monorepo |
| `techtree-brx` | closed | Re-scope v0.2.0: Prime Hosted moves to v0.2.x as inadmissible; reconcile plan, ticket ledger, order, and lock |
| `techtree-bzm` | closed | WP1.4 — Five-state public projection and bounded run.wait |
| `techtree-d5d` | closed | Separate release migration credentials from runtime |
| `techtree-di5` | in_progress | WP1.7 — Cut the live Campaign write path over to techtree.campaign.v2 |
| `techtree-egp` | closed | Remove incidental Techtree test-count coupling |
| `techtree-f8g` | closed | WP1.2 — JSON Pointer configuration compatibility policy and comparison |
| `techtree-g34` | open | Decide rate limiting for GET /api/v1/publications/:bundle_digest/bundle |
| `techtree-i4e` | closed | WP1.5 — Read-only v0.1 projectors and byte-identity proof |
| `techtree-k7t` | open | Techtree v0.2.x — hosted execution (WP4) |
| `techtree-mii` | closed | Consume shared status primitives with isolated verification |
| `techtree-p12` | closed | Own Techtree registry contracts in the product monorepo |
| `techtree-p90` | closed | Adopt approved shared palettes and internal-page cutting mats |
| `techtree-q6g` | blocked | Adopt or author a real skill and Verifiers task set for the WP2 parity proof |
| `techtree-qht28-schema` | closed | Adopt the rehearsed Techtree database namespace |
| `techtree-rlc` | closed | Remove Prime Hosted from v0.2.0 public and operator copy |
| `techtree-tm1` | closed | WP1.8 — Version the run-side documents to v2 without touching the shipped catalog |
| `techtree-u4n` | closed | WP1.1 — Campaign-bound four-plane execution plan |
| `techtree-v7i` | closed | Document non-default PostgreSQL roles for platform checks |
| `techtree-zko` | closed | Integrate shared verified profile with current onboarding |
