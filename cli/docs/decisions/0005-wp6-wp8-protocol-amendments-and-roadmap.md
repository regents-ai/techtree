# 0005 — WP6–WP8 protocol amendments and roadmap

Status: binding. Companion to `docs/spec/climb-v0.1-wp6-wp8.md` (§3, §17).

## Roadmap amendment (author-directed)

```text
Relay is deferred until after the complete install → first comparison →
one-turn Skill revision → second comparison flow is green.
```

Post-WP8 sequence: WP9 Hermes operator plugin + CLI bootstrap; WP10 guided
Skill refinement + rich/compact result experience; WP11 clean-machine,
phone/gateway, release hardening; WP12+ optional NeMo Relay evidence.

## Naming decision

The canonical protocol object remains `UpliftReport`. "Uplift receipt" is
user-facing language for its signed envelope (terminal, Hermes, website).
No new protocol type is created for UX copy.

## Protocol amendments (chief audit of frozen models vs spec §3)

These four expansions are ADDITIVE, land in ONE explicit protocol ticket
(WP6-proto) before any WP6 executor work, and regenerate schemas/goldens:

1. `MutationContract.kind` widens from `Literal["skill_insertion"]` to a
   `MutationKind` enum adding `skill_replacement`, with the §3.1 validation
   rules (insertion: 0→1 skills; replacement: 1→1 with differing root
   digests; both: all differences under /agents/subject/harness/skills).
   The public Procedure Transfer Climb continues to require
   skill_insertion.
2. `ExecutionSpec.order` widens from
   `Literal["baseline_then_candidate"]` to a `VariantSchedule` enum adding
   `parallel_variants`. `max_concurrent` is the Campaign-wide bound,
   divided between variants by the executor.
3. Run model: add `RunPhase.RUNNING_VARIANTS`, same-phase event kinds
   `variant.started` / `variant.progress` / `variant.completed` (valid
   only in running_variants; the PR7 known-kind and same-phase
   restrictions stay strict), `VariantProgress` state model, and
   `RunState.variant_progress: dict[str, VariantProgress]`. Existing
   sequential phases remain for the fake executor and compatibility.
4. Proof semantics: WP7 activates the existing Ed25519 primitives.
   `proof_grade: P1` (literal already present) is permitted only under the
   §3.4 conditions and means "integrity-bound, participant-attested local
   execution" — never independent or platform-witnessed. No presentation
   fields enter protocol objects (§3.5).

Everything else in the frozen WP0 model surface stands unchanged.

## Founder-owned release inputs (workers implement typed boundaries only)

- Real model/provider + evaluation credentials for the live Campaign
  (Prime inference auth; separate from host Hermes auth) — Sean sign-off.
- Starter subject Skill, `techtree:rich-terminal-output` Skill,
  `techtree:skill-improver` Skill — supplied later; do not invent.

## Standing prohibitions for WP6–WP8 workers

No Relay, no upload routes, no authentication, no leaderboard, no remote
execution, no recomputed benchmark answers (Verifiers is reward truth),
no scientific interpretation helpers outside the digested engine bundle,
Python (`techtree-python`) and Elixir (`techtree-ash`) scopes disjoint,
generated protocol/catalog artifacts single-owner, and no real result
accepted until its local proof verifies from exact stored bytes. The §12
terminal and phone/gateway scenarios are release-blocking gates.
