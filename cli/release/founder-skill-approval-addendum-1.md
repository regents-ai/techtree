# Founder Skill Approval Packet — Addendum 1 (append-only)

This addendum extends the approved Gate-1 packet
(release/founder-skill-approval-draft.md, packet digest
sha256:b3ea3ba12af27af878fd4061f4a115b35f772b7c2ca61e2d4fb82d4b5701da35,
approved 2026-08-14 — record in
release/founder-approvals/gate1-founder-skills.md). The approved
packet's bytes are never edited; where this addendum and the packet
disagree, the addendum is the later record. The Gate-1 approval itself
stands: it approved the two founder Skill artifacts, whose digests are
unchanged (starter tree 596d1368…/file 2aff2707…, improver e6bc16c4…).

## A1.1 Supersessions of stale packet lines

- The packet header's "awaiting the founder's Gate-1 approval phrase"
  was satisfied on 2026-08-14; the approval record is the file above.
  Independently re-verified: the packet digest recomputed from the
  committed bytes matches the founder's approval phrase exactly.
- The packet's frozen lineage (ReleaseCore 80807821…, campaign
  5aef3fb7…, climb 61a7dd46…, catalog 468e8ab1…) describes the
  SUPERSEDED pre-regeneration lineage; see A1.3.

## A1.2 Sampling-cap lineage statements (0017 requirement, omitted from the packet)

- The pre-change Campaign carried sampling.max_tokens 512. Its exact
  bytes were not separately archived; decision 0016 records the cap as
  the only change (audit recomputation of the presumed pre-change
  digest: 449940f1…, stated as reconstruction, not evidence).
- 512 interacted with the subject model's hidden reasoning tokens
  (billed against completion tokens) to kill long call chains, and the
  per-episode risk fell 4.8:1 against the BASELINE arm (~10.9 calls
  per no-Skill episode vs ~2.3 with the Skill). Three of six paid
  pre-change comparisons died this way; USD 0.5037 bought no
  comparison.
- Statement one: the cap was raised to 4096 identically on both
  variants, as one symmetric change, before any post-change score was
  observed; task membership (56f697fb…) was not altered.
- Statement two: the change created a new artifact lineage; no
  pre-change run was relabeled or repaired, and pre-change runs never
  share a stability set with post-change runs — they are disclosed
  diagnostic evidence in the packet's §4.
- 4096 was chosen as eight times the observed ceiling of an
  uninterrupted call and half the harness's own 8000-token episode
  bound; ratified in decision 0017.

## A1.3 The regenerated release lineage (decisions 0025)

The budget-contract audit (release/budget-contract-audit.json) found
the then-released Campaign 5aef3fb7… carried a development-placeholder
subject and null budgets, while every canonical run executed the
fixture-derived campaign b9e3f00c…. Founder-authorized option A
resolved it:

- The release Campaign was regenerated from source to carry the
  certified science (subject prime / qwen/qwen3.7-flash, sampling cap
  4096, budgets 8000 output tokens / USD 1.00, parallel execution,
  concurrency 4, declared timeout 600, retries 0). The regenerated
  Campaign is DIGEST-IDENTICAL to b9e3f00c… — the exact campaign named
  in every certified run's signed proof. The fixture overlay was
  deleted; the shipped Campaign alone now produces the certified
  configuration.
- New coordinates: climb 93c03b3a…, catalog 62714b77…, ReleaseCore
  c0783963… (byte-identical across the three repositories, verified).
  Unchanged: engine 874cbae0…, membership 56f697fb…, policy 6c532a43…,
  receipt 080895d5…, evidence 9c4959d3…, both Skill digests.

## A1.4 Re-certification on the released lineage (canonical)

Three runs, each prepared through the PRODUCT path against the
packaged catalog (no fixture), pre-committed as canonical before any
score existed, executed 2026-08-14; all 0017 hard stops clear, zero
output-cap-killed episodes, every proof verified offline by the chief
independently, all controlled_with_warnings / evidence complete /
accepted / P1:

| Role | Run | Score | Report | Bundle | Cost |
|---|---|---|---|---|---|
| stability #1 | run_4bde126172c64cc3bc2b6dd7fd306bba | 0/36 → 23/36 | 5a49a010… | c043bb3d… | 0.1605 |
| stability #2 | run_f987eea81ba342d7b7de5515598fa5fa | 0/36 → 23/36 | a4414411… | cf0c2a04… | 0.1681 |
| engine reference | run_4305dc3de7de46779c5c749f01529618 | 0/36 → 36/36 | 45fa83a1… | 13fbf571… | 0.1955 |

The single warning in all three is the accepted model-revision
warning: the provider publishes no immutable revision for the subject
model, so both arms are known to have used the same model identifier,
not provably the same model build. The manifest comparison records
zero violations and exactly one allowed difference (the inserted
Skill). Candidate legs on the released lineage: 23, 23; beside
23/23/24 on the superseded post-change lineage — the 20–27 band and
the "roughly two-thirds" release claim hold.

## A1.5 Budget-audit finding dispositions

1. Placeholder subject / null budgets — RESOLVED (A1.3/A1.4).
2. Inert timeout — v0.1 disposition (0025): the declared value stays
   (faithful to certification, which carried the same declared-inert
   value); no public surface claims runs are time-bounded; enforcement
   is a v0.2 candidate with its own certification.
3. Cost language — the plugin/CLI copy states the Campaign's declared
   USD 1.00 maximum as a contract value only; no runtime estimation
   or automatic abort is claimed (ticket 5i8).
4. Certified-vs-released mismatch — RESOLVED by digest identity plus
   the A1.4 runs.

## A1.6 Durable evidence

All certification run directories (the packet's §4 runs, the guided
rehearsal, and the A1.4 runs) are preserved outside session temp
storage at techtree-climb/certification-evidence/ (local, never
uploaded), and proofs re-verify offline from those copies. Programme
spend at this addendum: USD 2.4957 of the founder's 10.00 cap
(decision 0025).
