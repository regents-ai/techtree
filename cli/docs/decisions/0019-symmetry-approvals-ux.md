# 0019 — Comparison symmetry, native approvals, and the four-statement UX

Status: binding (founder directives, 2026-08-14). Three changes land
before the canonical rehearsal re-freeze.

## 1. Baseline is a role, not "no Skill"

A baseline is the current system a candidate is compared against. The
comparison model supports both forms with no special-casing anywhere
in evaluation or proof machinery:
- skill_insertion: baseline = no tested Skill, candidate = Skill v1
- skill_replacement: baseline = Skill v1, candidate = Skill v2

A Skill version is a content-addressed TREE (root_digest + per-file
digests) — SKILL.md plus references/, templates/, and other declared
non-executable supporting files — never just one Markdown file. The
mutation contract stays: allowed_differences is exactly the subject
harness's skills; everything else must match. A causal
component-uplift claim exists only when exactly the declared
component changed; additional changes make it a full-system
comparison; unexplained runtime drift invalidates it.

User-facing labels: "No tested Skill → Starter Skill v1" for the
first run; "Skill v1 → Skill v2" for later runs.

Implementation note: much of this already holds (SkillArtifact is a
content-addressed tree; MutationKind carries skill_replacement; the
replacement flow pins v1-as-evaluated as baseline). The work item is
a verified gap analysis plus fixes for any place that special-cases
the no-Skill baseline or assumes a single-file Skill.

## 2. Approval boundaries stay; token machinery goes

Removed: confirmation tokens, single-use acceptance records,
policy-digest command arguments, intermediate persisted approval
states. The four necessary approvals remain — install software, first
paid run, send revision context to the Host Hermes provider, second
paid run after reviewing the diff — expressed simply:

- CLI: prepare → review exact change, cost, and policy → explicit
  y/N → run → result. The prompt states: episode count, maximum
  authorized cost, "The Skill is the only scientific change", where
  model calls go, and that Techtree uploads no local evaluation
  artifacts. A non-interactive operator may pass an explicit --yes;
  it is not a model-controlled shortcut.
- Plugin: Hermes's NATIVE user-approval boundary. The plugin prepares
  the immutable draft, shows the exact change, policy summary, and
  budget; the human approves in the conversation or approval UI; the
  plugin starts that exact draft. The model can never approve its own
  action.
- Audit: one ordinary run event — kind run.approved, draft_digest,
  actor (e.g. human_via_hermes), approved_at. An audit fact, not a
  cryptographic acceptance artifact.
- Durable run states: prepared, running, completed, failed,
  cancelled. Operational progress is events, not protocol states.

The safety principle stays. The token machinery goes — including the
plugin's just-built DisclosureStore two-step (the disclosure CONTENT
and the boundary survive; the token mechanism is replaced by the
native approval surface).

## 3. The public UX is four statements

1. Same agent and same tasks (same model, harness, runtime,
   membership, tools, scorer, budget).
2. The Skill was the only change (first run: No tested Skill →
   Skill v1; later: Skill v1 → Skill v2; the complete bundle is
   content-addressed).
3. Here is the measured difference (baseline score, candidate score,
   absolute uplift, wins/losses/ties, cost, timing, regressions,
   validity).
4. Here is the local receipt and how to verify it
   (techtree proof verify; integrity-bound, participant-attested,
   offline-verifiable, not independently reproduced).

An ordinary user never needs CampaignSpec, TasksetLock internals,
receipt-set manifests, canonical JSON, signature envelopes, DataPolicy
graphs, launch-skew, backend taxonomy, or journal event kinds — those
exist to make the four statements true. Keep the smallest internal
mechanism set required to make the simple UX true; rigor stays
internal, the experience stays almost trivial: same system, one
changed Skill, measured uplift, verifiable receipt.
