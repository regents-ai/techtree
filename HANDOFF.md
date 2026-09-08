# Handoff — Techtree v0.2.0, WP0 closed, WP1 protocol cutover in progress

## Delivery — 2026-09-08

The accumulated Techtree work is published to GitHub. Required Regent UI, Privy
and identity sources are published on scoped `release/techtree-libraries-20260908`
branches; CI pins their exact commits. Unrelated sibling history and dirty source
work were not pushed. All repository-owned ignore files in scope now exclude
`local-only-*`; no matching tracked private files were found.

The site has been deployed to Fly and its public pages checked. The existing
catalog, bootstrap and all five public object digests are unchanged. Check
`/healthz` for the exact deployed application revision and GitHub Checks for the
latest CI outcome. The authenticated-CI migration fixture now uses configured
test credentials rather than a password that only worked with local trust auth.

Execution-foundation work remains next, in the order approved in
`docs/plan/repo2rlenv-v02x.md`; no paid parity run or new catalog activation is
implied by this delivery.

## Predeployment verification — 2026-09-08

The founder approved committing/pushing Techtree, deploying the public site and
the narrow roadmap amendment in `docs/plan/repo2rlenv-v02x.md`. Repo2RLEnv remains
Planned. Profile navigation and the document route are withdrawn; shared identity
APIs remain. Results now select harness/exact runtime, model and exact Campaign
before keyset pagination, with literal filter coordinates preserved by Ash.

Current local gates passed: CLI 4,086 tests plus six model-free preflight checks,
plugin 954 tests, platform 449 tests plus six doctests, and 56 registry tests.
Generated CLI artifacts match regeneration. Assets build and whitespace checks
passed. These are model-free checks, not Fabric/Hermes parity or Relay coverage.

Production preflight found the old image and stable v1 catalog still active.
`DATABASE_DIRECT_URL` has now been installed in Fly. Do not replace the active
catalog's file bytes with the generated v2 bundle or move the bootstrap pointer
merely to deploy the website. Preserve the public catalog and object digests.

The founder subsequently approved scoped shared-library publication. The verified
GitHub branch `release/techtree-libraries-20260908` now supplies design-system
`0ce0c3bfea98d86b3e395d2650bbfb493fd243b8`, elixir-utils
`17e9e356040c6322bdd8e84830eeef19c4ed3c42`, and Regents identity
`747c54169b338b4b832250173e37e05b26f74be7`. Techtree's platform gate also passed
against these clean package sources. CI checks them out explicitly and uses the
locally verified Elixir 1.19.5 / OTP 28.3.1 toolchain, compatible with the shared
packages' declared Elixir range. Unrelated sibling history and dirty edits were
not published. `local-only-*` is ignored at every depth. This note does not claim
a site deploy.

## Earlier integration brief

Updated 2026-09-07 at main `a6a51f5`. This replaces the 2026-08-31 brief, which
is preserved in Git history (`git show a6a51f5:HANDOFF.md`); the decisions it
recorded live in `docs/v0.2/DECISION_LEDGER.md`.

This is a starting brief, not authority to implement. The founder's current
request defines scope and ownership. Coordination follows the workspace
`regent-workflow`: Hermes/Astra coordinates bounded Claude/Fable assignments and
verifies the integrated result. Ticket IDs in this file and in linked documents
(`techtree-…`) are historical reference labels, not a live tracker and not an
assignment. Read the root instructions, the binding plans, recent commits and
the live working tree before changing anything.

## Local follow-up — agent-version browsing

Implemented per-family, exact-runtime-version Results browsing using the canonical
`ash-stack` guidance. See `docs/plan/agent-version-browsing.md` for the current
contract, fallback ordering and execution boundary. The initial live selection
is recorded in the URL; historical navigation and keyset pagination keep scores
scoped to that version. Families appear only when accepted records exist.

Comparison verification now enforces the paired adapter/tool contract instead
of requiring the single-version historical conformance snapshot. Runtime/image
and execution-plan bindings remain intact; historical recordings were not changed.
Prime Agent/Codex execution adapters and new upstream runtime certification remain
outside this implementation.

The dependency-refresh release mismatch is also resolved locally: the plugin's
v0.2 ReleaseCore now matches the generated CLI bytes, and the two read-only release
response fixtures were recaptured from successful CLI commands, not hand-edited.

Verification: `check-cli` passed (4,086 tests, one skip, plus six preflight tests);
`check-platform` passed (449 tests and six doctests); `check-plugin` passed
(954 tests, type checks and doctor). Browser checks used explicitly synthetic,
disposable local rows and covered version/family switching, 28 historical rows
across keyset pages, keyboard interaction, mobile overflow, browser back, exact
initial URL selection and malformed coordinates. PostgreSQL emitted shared-host
connection-budget warnings during the passing platform gate. No production pool
or unrelated server was changed to silence them.

Evidence and screenshots: workspace `artifacts/techtree-agent-versions/`.
Changes remain uncommitted and undeployed; founder UI review remains outstanding.

## Read first

- `AGENTS.md` at the root; `cli/CLAUDE.md` before editing `cli/`;
  `platform/AGENTS.md` before editing `platform/`.
- `docs/plan/v0.2.md` governs v0.2.0. `docs/plan/techtree-market.md` governs
  v0.2.x Market, v0.3 Foundry and the first Skill Climb, and deferred studies.
- `docs/v0.2/DECISION_LEDGER.md` records founder decisions and protected gates.
- `docs/v0.2/TICKETS.md` records the historical plan-to-ticket mapping.
- `docs/plan/techtree-delivery-audit-2026-09-06.md` is the dated delivery
  audit and implementation sequence (steps A–F).
- `cli/docs/v0.2/DI5_REPUBLISH_PACKET.md` is the WP1.7 candidate packet: what
  changed, preserved bytes, open points and the checks recorded for it.
- Ash/Phoenix work in `platform/` uses the workspace `ash-stack` skill and the
  specialist it routes to.

## Repository authority

`regents-ai/techtree` is the only source of truth for v0.2+ development.

| Component | Ownership |
| --- | --- |
| `cli/` | Local and hosted execution, scientific and durable run state, proof construction, publication transport, and offline verification |
| `plugin/` | Thin host-specific operator integrations, beginning with Hermes and Codex |
| `platform/` | techtree.sh, publication ingestion and public Results, Techtree Market, Techtree Library, authentication, access, and payout reconciliation |
| `contracts/` | Graph registry Solidity, deployment scripts and local Foundry checks |

The platform is never required for local execution or proof verification. The
frozen v0.1 repositories and packages remain historical release provenance;
v0.2 work does not rewrite their proof bytes.

## Where v0.2.0 stands

### WP0 — closed, lock frozen but not adopted

All eight WP0 children are closed (audit snapshot, 2026-09-06). The proposed
upstream lock in `docs/v0.2/UPSTREAM_CONTRACT_LOCK.json` and
`FABRIC_CAPABILITY_MATRIX.json` is frozen; adoption waits on founder approval
of the exact lock digest and the sixteen answers requested in
`docs/v0.2/WP0_FOUNDER_PACKET.md`. Those answers are not yet recorded as
accepted; do not fabricate them.

Prime Hosted Evaluations (WP4) are v0.2.x by founder decision of 2026-09-01,
so v0.2.0 executes locally only. The same decision approved and executed the
zero-cost publication of `techtree/techtree-v02-conformance@0.1.0` as public:
installable and importable, not hub-validated. Details and the WP0.3 blockers
are in `docs/v0.2/DECISION_LEDGER.md`.

### WP1 — protocol, durable state, historical readers: mostly on main

Landed on `main` (2026-09-01, commits `1e7e6b8`, `9515aa5`, `45e3520`,
`1a57ae5`, `43228f2`, `b27cd4f`): the Campaign-bound four-plane execution plan
(WP1.1), JSON Pointer compatibility policy (WP1.2), the evidence contract with
estimates and approvals (WP1.3), the five-state projection and bounded
`run.wait` (WP1.4), the read-only v0.1 projector with its byte-identity proof
(WP1.5), and the v2 run-side documents (WP1.8).

Landed on `main` on 2026-09-06 and 2026-09-07 (`56efc27`, `a6a51f5`): the live
Campaign write path (WP1.7). One live shape, `techtree.campaign.v2`, binds its
resolved execution plan by digest; v0.1 reading lives in `techtree.historical`;
the frozen v0.1 proof fixture, `schemas/v1alpha1` and the v1 goldens are
byte-identical. The release identity is prepared as a candidate,
`climb-v0.2.0` with CLI `0.2.0`, and the v0.1 release files are snapshotted
under `cli/release/history/climb-v0.1.0/`. Nothing is published. The packet
`cli/docs/v0.2/DI5_REPUBLISH_PACKET.md` still opens with "branch candidate";
that line predates its integration onto `main`. Its digests are what the tree
generates and are not approved release identity. Its section 10 carries the
open points: `protocol_version` in the ReleaseCore still says `v1alpha1`;
internal `execution_backend` trace fields are not yet renamed. Its platform
catalog v2 / `execution_plan` blocker is resolved locally by the follow-up below. The stale
plugin envelope fixtures mentioned in that packet were migrated in the local
CLI v2 recovery below.

Integrated into this checkout as **uncommitted changes** on 2026-09-07: the
CLI v2 machine envelope (WP1.6), typed next actions and the Hermes consumer
migration. `CLI_SCHEMA_VERSION` now says `techtree.cli.v2`. Astra recovered
`76ad055` in worktree branch `astra/finish-cli-v2`; Fable completed the profile
operation inventory and four-refusal review-binding/effect assertions, rejected
false consent flags in the CLI/schema/plugin, and preserved reviewed publication
metadata in the offered action. Independent review approved the product fixes;
its test-validation correction is applied. The integrated gates passed below.

The source branches `regent/techtree-5qe-cli-v2-envelope` and
`regent/techtree-5qe-recovery-5b47bf7` remain untouched. No commit or release was
created. The local recovery also refuses requested trace coverage until the
runtime can produce it, both at execution admission and catalog compatibility.

WP2 (Fabric-Hermes parity), WP3 (Relay evidence), WP5 (evidence facets and
exact public bundles) and WP6 (Codex) have not started on `main`. The real
Skill and task set for the WP2 parity proof is an open founder decision.

The v0.2 machine contract itself is frozen in `docs/v0.2/MACHINE_CONTRACT.md`:
a direct move to `techtree.cli.v2` with no v1 adapter, dual mode, daemon or
busy polling.

The publication contract keeps
`GET /api/v1/publications/:bundle_digest` and adds exact stored bundle
retrieval at the `/bundle` child route, which WP0.7 shipped. Withdrawn
metadata, tombstone, and receipt remain while bundle retrieval returns
`410 Gone`. The metadata route still answers with the inherited
`techtree.publication-entry.v1alpha1`; WP5 replaces it with
`techtree.published-result.v1` in the same cutover as the evidence facets. No
`/api/v1/results` route is planned.

## Remaining v0.2.0 order

Use the product requirements, actual component dependencies and the current
assignment to identify what may run in parallel. The delivery audit's step A is
the completed local step: WP1.6 envelope cutover on top of the WP1.7 candidate.
Platform catalog v2 ingestion is now integrated locally. Next is WP2 parity
(step B), WP3 and WP6 alongside WP5 (step C). WP3 requires WP2; WP5 requires
WP3; WP6 requires WP2. WP4 is out of the v0.2.0 order.

Do not pull Market, payouts, Foundry, optimization, the first Skill Climb, or
training into v0.2.0.

## Verification of the local recovery — 2026-09-07

Astra ran `env -u FORCE_COLOR -u CLICOLOR_FORCE -u NO_COLOR make check-cli
check-plugin check-plugin-integration` on this integrated checkout: **exit 0**,
**4,080 CLI tests**, **954 plugin tests**, **6 conformance preflight tests**,
format/lint/typechecks, generated-artifact comparison and plugin doctor passed.
One CLI case is skipped because this filesystem folds case. Another **33**
focused integration cases passed here (repeat/concurrent starts and starter next
actions); Fable's full model-free integration battery passed **302** cases in
the recovery worktree, whose final diff matches the integrated snapshot.

The platform gate used local PostgreSQL with isolated partition
`_astra_review_20260907` and port `4187`: **6 doctests, 437 tests, 0 failures**.
Local Foundry checks passed **56** tests. At that checkpoint, platform code and
dependency versions were unchanged; the security follow-up below supersedes
that state. No paid evaluations or live publication ran.

Frozen `cli/release`, `cli/schemas/v1alpha1`, packaged resources and the historical
conformance proof remain unchanged from `a6a51f5`. Nothing is staged or committed.
The review, recovery patch and raw verification logs are in the workspace at
`artifacts/techtree-review-2026-09-07/`. Read `REVIEW.md` there for findings and
remaining release blockers. Do not reapply the WIP branch over this dirty tree.

### Platform security and catalog v2 follow-up — 2026-09-07

The dependency and catalog changes are integrated here, still uncommitted.
Astra stopped the Fable sessions when asked, completed the remaining work
directly, and ran the integrated checks. Ash 3.33.0, AshPhoenix 2.3.25, Bandit
1.12.5 and Privy React Auth 3.40.0 replace the advisory-bearing versions;
documented npm overrides remove vulnerable transitive branches. Fresh npm
audits (full and production-only) report zero vulnerabilities; the OSV batch
query covers all **63** locked Hex packages and reports none affected.

The platform accepts catalog/Campaign v2, imports and serves the bound
execution plan, and reads execution metadata from that plan. Import failure
and byte-integrity rules remain enforced. Publication also rejects signed
reports with the wrong schema, Campaign, or execution-plan binding; the new
regression reproduced acceptance before that check was implemented.

`make check-platform` passes **446 tests and 6 doctests**, formatting,
warnings-as-errors compilation, clean npm install and asset builds. A fresh
VM sync and `mix catalog.verify` accept the CLI export. The new synthetic v2
proof passes the CLI's **351** verification checks and supplies the actual
CLI-produced submission used by platform ingestion/controller tests.
Its generator intentionally creates fresh test signatures; the archived v0.1
proof and frozen CLI release bytes are untouched.

This closes the two local follow-ups, not release approval: no paid v2
certification, live Privy/wallet smoke test, deployment or publication was run.
Artifacts and raw audits are in `artifacts/techtree-platform-followups/` in the
Regent workspace. The previous CLI recovery and all unrelated dirty work remain.

### Earlier WP1.7 packet evidence

The WP1.7 packet, section 12, records these results in the `techtree-di5`
worktree on 2026-09-07: `make check` exit 0 with 4048 tests passed and
generated artifacts matching the tree; the integration battery 300 passed;
`make check-plugin` 929 passed with the plugin doctor passing. Docker was not
exercised (the daemon was unreachable; four Doctor tests use a stand-in
`docker` at the command boundary). `real_model` tests were not run. No wheel
was built, nothing was pushed, published or signed with a real key. Treat those
earlier figures as that packet's evidence for its tree; the recovery checks
above are the current local verification.

## Protected boundaries

Do not publish a Prime environment, start paid inference, mutate provider
resources, adopt a final upstream lock, release a package, deploy the platform,
or move money without the specific founder authority required for that action.
The one approval granted so far covers exactly one act: the executed zero-cost
publication of `techtree/techtree-v02-conformance@0.1.0`. Republishing it —
including for the hub `tags` metadata question open as `techtree-2qy` — needs
its own packet.

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

`git worktree list` on 2026-09-07 shows this checkout on `main` at `a6a51f5`
plus `astra-finish-cli-v2` at `76ad055` under
`/Users/sean/Documents/regent/worktrees/techtree/`. Thirteen further registered
worktrees report `prunable` because their directories are gone; their branches
(`regent/techtree-*`) remain. `git branch --no-merged main` on 2026-09-07 lists
only the two `5qe` branches, `astra/finish-cli-v2`, `docs/readme-flow` and
`regent/techtree-781-shared-profile`; every other branch is reachable from
`main`. The `781` profile candidate (`a91eac3`) is superseded by the integrated
shared profile (`18100f8`) and must not be merged again. Do not prune, reset or
clean worktrees without confirming the owner. The `docs/readme-flow` branch is superseded by the
corrected release-identity decision and must not be merged. The remote
`regent/regent-zs6.9-techtree-fast-wins` branch is preserved without a
wholesale merge. Historical standalone repositories are untouched.

The `.beads/` directory and its exports are historical tracker evidence. Do
not run tracker commands or maintain a ticket graph for new work.

## Resume procedure

1. Read the root instructions, both binding plans and the decision ledger.
   Treat the ticket ledger and the delivery audit as reference.
2. Check current Git state and the current assignment's acceptance criteria and
   dependencies.
3. Work only within the component and work package the founder's request
   names. A single writer works in the assigned checkout; concurrent writers use
   separate worktrees and branches, with one integrator per repository.
4. For `platform/` implementation, use the workspace `ash-stack` skill.
5. Run focused checks while working and the established monorepo gate before
   completion. Do not add a smoke-test framework or new harness.
6. Report exact evidence, remaining blockers, and any protected action still
   awaiting founder approval.
