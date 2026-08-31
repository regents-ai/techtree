# 0023 — Release execution contracts and audit tickets

Status: binding (author advice relayed and adopted whole by the
founder, 2026-08-14: "incorporate all of this advice"). Governs every
remaining v0.1 ticket. Detailed per-ticket contracts live in
docs/release/contracts/ and are part of this decision.

## 1. Self-contained repository

The four binding spec files are vendored in docs/spec/ (verified
byte-identical to their sources), with CHECKSUMS.json, INDEX.md
(ticket → spec section → decisions → amendments), and a digest test
(tests/unit/test_spec_index.py). No ticket may require a
parent-directory file. Every remaining release ticket carries a
self-contained execution contract: purpose, inputs/immutable
coordinates, dependencies, owned files, forbidden actions, steps,
outputs, acceptance, evidence, stop conditions, founder decisions
required.

## 2. Ticket rulings

- **WP11b (ndq.3.2)** gains a certified-scientific-fingerprint check:
  a new release/certified-scientific-fingerprint.json records the
  exact certified digests (engine, catalog, climb, campaign, taskset
  lock, validation receipt, data policy, both Skills, subject
  model/hermes/verifiers, runtime image digests) and every build
  compares against it; clean-tree wheel build, wheel-content
  inspection, isolated fresh-install (fresh HOME/TECHTREE_HOME/
  UV_TOOL_DIR/UV_TOOL_BIN_DIR), exact output artifacts, and stop
  conditions. Full contract: docs/release/contracts/wp11b.md.
- **WP11c (ndq.3.3)**: exact ReleaseCore byte-equality, local
  exact-commit plugin install, plugin doctor in a throwaway home,
  release-candidate record, no-push stop conditions. CYCLE RULE: the
  plugin embeds ReleaseCore and must NOT embed the BootstrapRelease
  digest (that object contains the plugin commit). Contract: wp11c.md.
- **WP11d (ndq.3.4)**: BINDING — starter_skill_object_url is keyed by
  the SKILL.md FILE digest (the URL serves exact file bytes); the
  bootstrap starter_skill object carries BOTH file_digest and
  tree_digest (file identifies the served bytes, tree identifies the
  mounted bundle); the CLI fetch verifies file digest then the built
  one-file tree digest. The final placeholder_release:false candidate
  bytes are BUILT BEFORE founder approval but NOT activated — the
  founder approves the exact bytes that will later be served
  unchanged; no flip-after-approval. Rollback is an immutable-release
  active-pointer switch, never mutation or deletion. No queryable
  URL/digest column in v0.1. Contract: wp11d.md.
- **wdc (doctor credential false-green) is PROMOTED into v0.1 and
  blocks WP11e.** A readiness command that can say "ready" when the
  detached worker cannot authenticate is a release bug. Doctor's
  credential check must use the same resolution the detached worker
  uses; an exported-variable-only state reports not ready; no
  credential value in output; repair action is `prime login`. The
  worker's scrubbed environment is NOT loosened. Classification for
  the Gate-2 packet: non-scientific onboarding behavior — outside the
  certified scientific surface (which is: runs, approvals, proposals,
  receipts, proof, host requests, Skill mounting, guards, Campaign
  config) — landed with the full acceptance battery. Contract:
  wp11-doctor.md.
- **WP11e (ndq.3.5)**: isolated-path clean-machine definition stated
  honestly (fresh homes, not a fresh OS; record image-cache state);
  prime-login credential journey; the full two-comparison terminal
  journey including session-close/re-poll; typed failure-injection
  matrix split into no-paid and paid cases; pre-Gate-2 local-artifact
  installs never claimed as public-path certification. Contract:
  wp11e.md.
- **WP11f (ndq.3.6)**: no certification claim without the named,
  pinned reference gateway (spec §4.4 leaves REFERENCE_GATEWAY as a
  release-test choice — a FOUNDER decision, ticket
  wp11-gateway-profile). The ticket states whether it performs a live
  full journey or contract replay against canonical runs, and release
  copy matches that truthfully. Contract: wp11f.md.
- **WP11g (ndq.3.7)**: the no-upload proof uses three complementary
  methods — static route/client audit, instrumented application-level
  HTTP method logging, and E2E destination capture; plus supply-chain
  checks, on-disk permission modes, recursive scrubber adversarial
  cases, verifiers push disabled at both config layers, and the
  Skill-conflict-scan limitation recorded (no new LLM scanner in
  v0.1). Contract: wp11g.md.
- **WP11h (ndq.3.8)**: Gate-2 packet adds (a) the decision 0022
  post-rehearsal change classification — every commit after 1ad6ecf
  classified scientific / non_scientific_copy / release_packaging /
  documentation / test_only, with fingerprint proof for every
  non-scientific class — and (b) the claim-to-evidence matrix.
  Contract: wp11h.md.
- **ndq.3.41 is CLOSED, deferred to v0.2.** v0.1 ships the certified
  twelve-phase vocabulary; no projection before release; no claim
  that a five-state public schema exists. The five-state projection
  design becomes part of ticket 999 (v0.2 collapse).

## 3. New release-audit tickets

1. **WP11-budget** — public Campaign budget-contract audit: verify
   every budget/limit field (output cap, per-episode call/turn/
   timeout limits, concurrency, cost ceiling) is identical across
   variants, resolved runtime matches manifest, violations fail
   closed, and public/approval copy matches actual limits; record the
   512→4096 lineage (decision 0016). Audit only — no new subsystem.
2. **WP11-claims** — product-claim-to-evidence matrix: one row per
   public product claim mapping implementation → automated test →
   live evidence → limitation. Contract: wp11-claims.md.
3. **WP11-gateway-profile** — one-page FOUNDER decision naming the
   reference gateway (name, version, Host Hermes version, approval
   mechanism, limits, reconnect behavior, phone client).
4. **WP11-postpublish** — post-Gate-2 public-coordinate smoke and
   rollback check; activates only after the release approval; alters
   no approved bytes.

## 4. Scope statement (release copy)

Explicit Skill-bundle v1-vs-v2 comparisons are supported when both
bundles are supplied. The guided Hello World revision is
single-SKILL.md in v0.1 (ndq.3.42 stays deferred). Release
documentation carries this limitation; no copy claims the guided
improver revises multi-file bundles.

## 5. What is NOT added

No new scientific subsystems, no LLM-based semantic Skill scanner, no
five-state projection, no schema collapse, no versioned readers. The
remaining work is release integrity, onboarding truthfulness, exact
distribution coordinates, and final acceptance: the published bytes
must demonstrably be the certified product.
