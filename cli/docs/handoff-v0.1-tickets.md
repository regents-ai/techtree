# Climb v0.1 — Ticket Handoff

Written 2026-08-14 by the chief-of-staff session. Covers every ticket in
the beads tracker (DB lives in this repo; run `bd show <id>` for full
text). Two questions per ticket: what is it for, and is its written
description enough for a coding agent to complete it without this
session's context?

**Context a fresh agent MUST have:**

- All four binding spec files are VENDORED in `docs/spec/`
  (climb-v0.1-wp0-wp5.md, -pr6-pr8.md, -wp6-wp8.md, -wp9-wp11.md),
  verified byte-identical to their sources; `docs/spec/CHECKSUMS.json`
  records digests (tested by tests/unit/test_spec_index.py) and
  `docs/spec/INDEX.md` maps every ticket to its spec sections,
  decisions, and amendments. A ticket saying "Spec §9.5" means the
  WP9–WP11 file. No ticket requires a parent-directory file.
- Every remaining release ticket has a self-contained execution
  contract in `docs/release/contracts/` (decision 0023): purpose,
  immutable inputs, forbidden actions, steps, outputs, acceptance,
  stop conditions.
- `docs/decisions/0001–0023` in this repo are binding; 0022
  (post-rehearsal change discipline) constrains every remaining v0.1
  ticket: no behavior changes to runs, approvals, proposals, receipts,
  proof, host requests, Skill mounting, guards, or Campaign config
  without re-certification.
- Gate 1 is approved (`release/founder-approvals/gate1-founder-skills.md`).
  Gate 2 (publish/tag/deploy) is NOT — nothing publishes, pushes, tags,
  deploys, or flips `placeholder_release` without the founder's exact
  `APPROVE CLIMB V0.1 RELEASE` phrase.
- Frozen lineage: techtree-python 1ad6ecf (code; later commits are
  docs/copy only), techtree-plugin 1ce5d4e, ReleaseCore
  sha256:80807821…, starter tree 596d1368…, improver e6bc16c4….
- Workers do not run git; the orchestrating session commits.

## Open — remaining v0.1 release path

Ordered by dependency. All are children of epic `ndq.3` (WP11) unless
noted.

### techtree-python-ndq.3.2 — WP11b: CLI wheel release + fresh-install verification (P2)
Build the CLI wheel from the frozen source, compute its SHA-256,
install into a fresh home with the exact proposed argv, and require
`techtree release verify` to pass. Fills the `cli_source_commit` /
`cli_version` placeholders. Publishing to PyPI (distribution name
`techtree`, decision 0011) stays gated on Gate-2 approval.
**Spec status: adequate WITH the WP9–11 spec §9.5–9.6 + decision 0011.**
Two things the ticket does not say: (a) the wheel must be built from
the final post-copy-fix commit, and the 0022 acceptance battery must
prove the scientific surface byte-identical to the certified 1ad6ecf
code; (b) the fresh-install journey will hit the credential mechanism
documented in README ("The evaluation credential") — `prime login`,
not an exported variable.

### techtree-python-ndq.3.3 — WP11c: plugin exact-commit release + bootstrap wrapper (P2)
Bind the release to the exact 40-char plugin commit (1ce5d4e…) and
produce the bootstrap install wrapper. Notes already pin the repo
coordinate `github.com/regents-ai/techtree-hermes` and the install
argv. Repo creation/push happens ONLY at Gate-2 approval.
**Spec status: adequate** (spec §9.3–9.4 plus the ticket's own notes,
which carry the coordinate history).

### techtree-python-ndq.3.4 — WP11d: Ash BootstrapRelease deployment + rollback (P2)
Build the real BootstrapRelease in techtree-ash (wheel hash + plugin
commit + starter-Skill URL), import it into the read-only release
source, write deploy/rollback runbooks. Hosting decision and the
deploy itself are the founder's. The ticket's notes carry two real
scope items: enforce that `placeholder_release: false` forbids any
placeholder value (0007 R10, still unenforced in ash), and decide
whether the starter URL/digest need a queryable column.
**Spec status: partially underspecified.** The
`starter_skill_object_url` resolution is not written anywhere: the
chief's scouting found ash already serves content-addressed objects at
`GET /objects/:digest` with drift-refusal — the natural coordinate is
that endpoint on techtree.sh serving the starter SKILL.md bytes, but
which digest keys it (file `2aff2707…` vs tree `596d1368…`) must match
what the CLI's `_stage_document` fetch verifies. Pin this explicitly
and put the chosen URL in the Gate-2 packet.

### techtree-python-ndq.3.5 — WP11e: clean-machine terminal E2E + failure injection (P1, blocked by 3.2/3.3/wdc)
Install-from-zero terminal journey on a clean home, plus the §9.11
failure matrix (no Docker, no uv, no credential, dead network mid-run)
— every failure must land on a typed error with a working repair.
**Spec status: adequate WITH spec §9.8/9.10–9.11**, plus two session
findings the ticket predates: (a) the credential journey must use
`prime login` (an exported PRIME_API_KEY never reaches the detached
worker — that IS one of the failure-injection cases, and its error/
repair text was just rewritten); (b) `techtree doctor
--for-evaluation` can false-green on an exported variable (ticket
`wdc`) — the journey must not rely on that check alone. Paid: the
journey runs a real comparison; budget rules (estimate first, ceiling,
~1.03 remaining of 3.00) apply.

### techtree-python-ndq.3.6 — WP11f: agent-first Hermes community onboarding E2E (P1, blocked by 3.5)
Replaced by decision 0024 (iOS and phone clients are out of v0.1). One
pasted prompt to an existing Hermes agent drives the whole path —
pinned instructions → explicit approvals → plugin install → one
restart → CLI install/verify → doctor → Hello World — with twelve
acceptance points including the next-step rule and no unpinned
coordinates. **Fully specified** (contracts/wp11f.md).

### techtree-python-ndq.3.7 — WP11g: security, privacy, no-upload review (P1, in progress, blocked by 3.5)
Final pass of the review that already produced and closed the ten SEC
tickets: supply-chain review, a network capture proving no mutation
upload during the journeys, the §15.8 checklist, and the noted review
of the plugin's envelope-conflict scan coverage (deterministic,
affirmative-instruction-only — could miss paraphrase) before treating
the Skill freeze as final.
**Spec status: adequate.** Most of the substance is already done and
committed; what remains is the capture + checklist over the E2E runs.

### techtree-python-ndq.3.8 — WP11h: docs, runbooks, founder launch gate (P1, blocked by 3.6/3.7)
Assemble the Gate-2 release approval packet (decision 0013 s5 lists
its complete contents; the ticket notes this) and the published docs /
upgrade/disable/remove behavior summary; ends at the founder's
`APPROVE CLIMB V0.1 RELEASE` stop.
**Spec status: adequate WITH 0013 s5 — but add 0022:** the packet must
also carry the post-rehearsal change classification (every change
since certification marked scientific/non-scientific) required by
decision 0022 item 4 / Gate-1 packet §7g. That requirement postdates
the ticket text.

### techtree-python-wdc — Doctor credential truthfulness (P1, PROMOTED, blocks WP11e)
Promoted into v0.1 by decision 0023: `doctor --for-evaluation`
currently passes on an exported credential no detached run can use — a
readiness command that lies is a release bug. The fix makes doctor use
the same credential resolution the detached worker uses; the worker's
scrubbed environment is not loosened. Classified non-scientific
onboarding behavior for the Gate-2 packet, with the full battery.
**Spec status: fully specified** — six-row behavior table in
docs/release/contracts/wp11-doctor.md.

### techtree-python-iy0 — WP11-budget: Campaign budget-contract audit (P1, blocks WP11h)
Audit-only proof that every budget/limit field binds both variants
identically, resolved runtime matches the manifest, violations fail
closed, and public copy states the actual limits; records the
512→4096 lineage. **Fully specified** (contracts/wp11-budget.md).

### techtree-python-y8s — WP11-claims: claim-to-evidence matrix (P1, blocks WP11h)
One row per public product claim → implementation → test → live
evidence → limitation, with real paths/IDs/digests in every cell.
**Fully specified** (contracts/wp11-claims.md).

### techtree-python-rlf — WP11-postpublish: public-coordinate smoke + rollback (P2, post-Gate-2 only)
After release approval only: verify the public wheel/plugin/bootstrap/
starter bytes equal the approved digests, fresh public install, and a
rollback pointer rehearsal. Alters no approved bytes. **Fully
specified** (contracts/wp11-postpublish.md).

## Open — explicitly NOT v0.1

- **techtree-python-999 (P2)** — v0.2 run-state schema collapse
  (twelve→five), now ALSO owning the five-state public projection
  design (absorbed from closed ndq.3.41 per decision 0023; v0.1 ships
  the certified twelve-phase vocabulary). **Intentionally
  high-level**; needs its own design + certification plan at v0.2
  kickoff. Not executable as written — by design.
- **techtree-python-cwa (P2)** — v0.2 versioned historical run readers,
  strictly read-only (founder-approved exception to the
  no-compatibility-branch rule; decision 0022 item 3). **Adequate as a
  scope charter**; implementation design belongs to v0.2.
- **techtree-python-ndq.3.42 (P3)** — multi-file starter fetch +
  full-tree revision context. **Well specified** (names both code sites
  and the archive-format decision).
- **techtree-python-ndq.3.36 (P3)** — plugin makes duplicate CLI reads
  per proposal. **Well specified.**
- **techtree-python-ndq.3.24 (P3)** — engine inspection should report
  public task prompts generally (replaces the per-taskset lookup);
  belongs to the next engine-bundle opening. **Well specified.**
- **techtree-python-85a.2.6 (P3)** — carry token/time usage into
  EpisodeReceipt metrics (efficiency fields currently honest-null).
  **Well specified** (exact files/functions; warns receipt digests
  change → needs regenerated goldens, so it is post-v0.1 by nature).

Bookkeeping: epics `ndq` (WP9–11), `ndq.3` (WP11), `85a` (WP6–8), and
`85a.2` (WP7) remain open only because open children remain; close them
when their children close.

## Closed — complete record

One line each; `bd show <id>` has full close reasons.

### WP0–WP5, local substrate (epic 3jj — closed with all children)
- **3jj.1.1 / PR1** — repo, pyproject, Makefile gates, docs skeleton.
- **3jj.1.2 / PR2a** — protocol core: canonical JSON, digests, crypto.
- **3jj.1.3 / PR2b** — Campaign-kernel models, schemas, goldens.
- **3jj.2.1 / PR3** — CLI foundation, envelope, renderers, Doctor.
- **3jj.2.2 / PR4A** — content-addressed catalog kernel + packaged catalog.
- **3jj.2.3** — repair next-action for corrupt settings.
- **3jj.3.1 / PR5** — Skill scanner + deterministic archive.
- **3jj.3.2 / PR6** — manifests, drafts, policy acceptance, prepare.
- **3jj.4.1 / PR7** — run event system.
- **3jj.4.2 / PR8** — worker, launcher, fake executor, run commands.
- **3jj.4.3 / PR7-align** — canonical event kinds, same-phase restrictions.
- **3jj.5.1 / PI0** — pinned-Verifiers contract preflight.
- **3jj.5.2 / PR9** — managed engine at the exact pin.
- **3jj.5.3** — Doctor uses the real engine registry.
- **3jj.6.1 / PR10** — BranchCode v1 reference taskset.
- **3jj.6.2 / PR11** — taskset locking + real fixture regeneration.
- **3jj.6.3 / PR12** — Verifiers validation, receipts, worker integration.

### WP6–WP8, real evaluation + web (epic 85a — children closed except 85a.2.6 above)
- **85a.1.1 / WP6-proto** — additive protocol amendments.
- **85a.1.2 / WP6a** — Verifiers eval compatibility + compiler.
- **85a.1.3 / WP6b** — real named-subject Hermes Docker execution.
- **85a.1.4 / WP6c** — concurrent variant scheduler + real executor.
- **85a.2.1 / WP7a** — Episode parsing, receipts, receipt sets.
- **85a.2.2 / WP7b** — observed comparison, aggregation, report.
- **85a.2.3 / WP7c** — local signing, proof verification, presentation.
- **85a.2.4 / WP7d** — skill_replacement + improvement-context service.
- **85a.2.5** — scrubber over-redaction of token counts/IDs fixed.
- **85a.3.1 / WP8a** — Ash catalog resources + importer.
- **85a.3.2 / WP8b** — exact-byte public API + bootstrap manifest.
- **85a.3.3 / WP8c** — academic pages + web release hardening.

### WP9–WP10, plugin + guided revision (epics ndq.1, ndq.2 — closed)
- **ndq.1.1 / WP9a** — plugin repo, manifest, registration, Doctor.
- **ndq.1.2 / WP9b** — ReleaseCore, CLI bridge, strict envelope.
- **ndq.1.3 / WP9c** — explicit bootstrap/install approval + verification.
- **ndq.1.4 / WP9d** — catalog/demo/run/proof tool handlers + state.
- **ndq.1.5 / WP9e** — slash commands, CLI subcommands, gateway output.
- **ndq.1.6** — CLI starter-Skill materialization command.
- **ndq.2.1 / WP10a** — HostLlmPort + founder-Skill digest contracts.
- **ndq.2.2 / WP10b** — presentation service + narrative guards.
- **ndq.2.3 / WP10c** — sanitized improvement context, exactly-one-turn.
- **ndq.2.4 / WP10d** — proposal staging, scan, diff, second approval.
- **ndq.2.5 / WP10e** — v1-vs-v2 orchestration + both journeys.
- **ndq.2.6** — verified source-skill exposure + R2 context fields.

### WP11 closed subset (epic ndq.3)
- **ndq.3.1 / WP11a** — ReleaseCore generation + cross-repo equality.
- **ndq.3.9** — signed ComparisonExecutionRecord in the proof bundle.
- **ndq.3.10 / WP11-engine** — the single batched engine-bundle opening.
- **ndq.3.12** — climb show digest display (abbrev human / full JSON).
- **ndq.3.13** — engine installer `.installing` marker protocol.
- **ndq.3.14** — bootstrap manifest starter-Skill source URL field.
- **ndq.3.15/16/17 / WP11-p0** — Hello World naming migration + rich-output
  removal across python/plugin/ash.
- **ndq.3.18** — invalid 71-char candidate label fixed.
- **ndq.3.19 / WP11-improver-wire** — verified improver text steers the
  one host completion (nine-digest provenance).
- **ndq.3.20** — MIT license across the three repos.
- **ndq.3.21** — release-copy guard tests (privacy/account/attestation).
- **ndq.3.22** — executor_kind honesty fix (was hardcoded "fake").
- **ndq.3.23** — one-generation-request verification at the provider
  boundary.
- **ndq.3.25** — website install-first simplification, human/agent
  focus switcher.
- **ndq.3.26–3.35 / SEC batch** — recursive error-detail scrubbing;
  provider disclosure; copied-example guard fixed for short inputs;
  prose guard wired; private staging dirs; plugin disable/remove test;
  CLI uninstall/data-retention runbook; leaf-permission hardening;
  website endpoint surface (405s, multipart, MethodOverride); small
  findings batch.
- **ndq.3.37/38/40 / 0019** — comparison-symmetry gap analysis + fixes;
  token-free y/N + `--yes` approvals + run.approved event;
  four-statement presentation audit.
- **ndq.3.39 / 0019-3** — plugin on Hermes-native approval,
  DisclosureStore machinery removed.
- **ndq.3.43** — honest `run_request_unreadable` message replaces the
  lying "corrupt" error for pre-version runs.
- **ndq.3.11 / WP11-cal** — starter authoring + calibration +
  certification, closed against the Gate-1 founder approval.
- **ndq.3.41** — five-state projection verification: premise false
  (twelve phases are the certified public vocabulary); deferred to
  v0.2 by decision 0023, absorbed into ticket 999.

### Standalone
- **6gs** — golden/publisher membership digests unified on
  tasksets.membership_digest.
- **igy** — fake-executor progress/cancellation race fixed.
- **z2u** — zero transport retries on the product host-LLM path.
- **3ym** — credential onboarding: docs + failure-moment copy say
  `prime login`, not an exported variable.
