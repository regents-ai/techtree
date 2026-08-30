# 0007 — Binding v0.1 release decisions (author ratifications)

Status: binding. Author's answers to the ten implementation questions plus
release ratifications, relayed by Sean 2026-08-13. Where this conflicts
with earlier specs, this wins. Founder inputs now sharply bounded: the
three final Skill files (drafts may be prepared per the contracts below;
Sean approves), the repository license, and final concrete release
coordinates.

## R1. Improvement context — replies stay excluded (ratified)

For BranchCode, `subject_reply` is null for correct AND incorrect
episodes. MAY include: public task input/label, task hash,
success/failure, reward, public metrics, safe error category,
improved/regressed/unchanged, source Skill fingerprint, aggregate usage
and timing. MUST exclude: subject final reply, expected answer, grader
source, hidden task fields, raw model messages, raw tool arguments,
private paths, provider payloads. Future environments need an explicit
taskset-specific disclosure policy — never inferred from "not exact
match". Field stays optional-but-empty in v0.1.

## R2. Skill text — fingerprints in the context, text loaded verified

Context stores: source Skill root digest, entrypoint file digest, source
run ID, source report digest. The plugin resolves the run-owned verified
snapshot, re-verifies digests, reads SKILL.md, supplies the text as a
separate ephemeral host-model input, and digest-binds the complete host
request. Skill v2 provenance records: parent v1 root digest, entrypoint
digest, improvement-context digest, host request digest, host
structured-response digest, skill-improver Skill digest, host model ID,
revision attempt = 1.

## R3. climb show — summary AND digests

Human: plain-language policy summary + abbreviated Campaign/DataPolicy
digests. JSON: complete campaign_spec_digest + data_policy_digest.
Prepare/start continue to show and accept the complete policy digest.

## R4. Starter Skill v1 calibration (content now author-specified)

Intentionally incomplete BranchCode Skill whose ONE defect is step 5:
"Add 7 times the TOTAL number of characters" (correct rule: DISTINCT).
Targets: baseline ≤2/36; v1 in 20–27/36 (prefer 24); v2 ≥32/36 improving
by ≥6 with ≤1 regression. Calibration procedure: count all-unique-char
inputs among the 36; run the defective skill; require the band; require
all failures on repeated-character inputs; require corrected skill 36/36;
require no wrong-rule/correct-rule output collision; test every frozen
task explicitly. If the membership does not yield the band, recalibrate
membership or choose a similarly singular public-feature defect — never
alter hidden answers or scoring. Two full rehearsals with release model +
frozen artifacts required. Calibration makes the narrative likely; the UI
never fakes a positive; ties/regressions are reported honestly. The
starter Skill self-identifies as "intentionally incomplete introductory
Skill".

## R5. Controlled vs controlled_with_warnings

Docker image pinning by digest is RELEASE-BLOCKING: release Campaign
records the OCI image-index digest, resolved platform-specific digest,
and subject platform; both variants must resolve to the same
platform-specific digest; then the Docker warning is removed. The missing
provider model revision is an ACCEPTED v0.1 warning
(model_revision_unavailable): release results are normally
controlled_with_warnings with the copy "All Techtree-controlled fields
matched. The provider does not expose an immutable revision for the
selected model alias." Never suppress the warning to obtain the word
"controlled". Any actual mismatch is invalid, not a warning.

## R6+R8. ComparisonExecutionRecord — new signed operational artifact

Do NOT reopen the 72 EpisodeReceipts. One signed, content-addressed
`techtree.comparison-execution.v1alpha1` record per comparison: per-variant
started/finished/elapsed, model_calls, input/cached/output/total tokens,
cost_usd with EXPLICIT provenance (provider_reported |
computed_from_pinned_price | estimated | unavailable — never show an
estimate as provider-reported), source artifact digests; pair-level
schedule, launch skew, overlap, concurrency allocation,
cancellation/failure state. Signed with the local executor key, included
in the proof bundle, used by rich and compact presentation, orthogonal to
Verifiers reward truth. Missing economics never invalidates a valid
score — it makes cost/timing unavailable/unverified with an
operational-evidence warning. A later UpliftReport revision may add an
optional comparison_execution_record_digest.

## R7. Decision 0004 ratified, with the refined protocol

Build the venv at its final digest path under the exclusive install lock;
`.installing` marker written first and removed last; stale markers
detected at next setup; failed installs removed or quarantined before
retry; installed.json (atomic, fsync) is the only publication signal;
verified engines never mutated in place; reinstall idempotent.

## R9. One engine-bundle opening in WP11 (batched)

Single opening includes: (1) effective sampling in the eval normalizer +
observed comparison; (2) release Docker image pinned by digest; (3)
resolved platform digest captured/verified; (4) skill-related
tool-description delta as a pinned harness conformance fixture; (5)
push=false verified in resolved config; (6) platform-upload code path
verified not invoked; (7) usage normalization for the
ComparisonExecutionRecord; (8) all existing parsing/reward behavior
preserved. Then the full regeneration order (engine → digests → installed
engine → package digests → inspection → locks → validation evidence →
receipts → Campaigns → Climb → catalog → goldens/schemas as changed →
ReleaseCore → website bootstrap → plugin release copy) and the full rerun
list (PI0, engine verify, taskset validation, real baseline/full-skill
run, starter v1 calibration, one-turn v2 rehearsal, offline proof
verification, clean-home setup, plugin release-equality).

## R10. placeholder_release is a permanent schema rule

Mandatory boolean, NO default; omission is a schema error. true: label as
development placeholders, refuse the public bootstrap install flow,
developer-only override never exposed as a model-visible gateway
argument. false: every coordinate concrete and immutable (version,
source/index policy, plugin repo + full commit, engine/Campaign/Climb/
three Skill digests, minimum Hermes version, bootstrap schema version);
WP11 fails on any empty/mutable/latest/main/TBD value. Inherited by
ReleaseCore, the Ash bootstrap projection, and the plugin release
verifier.

## Release ratifications

- qwen/qwen3.7-flash is the v0.1 release-candidate subject model (0006
  now ratified, subject to the WP11 gates: skill discovery succeeds,
  baseline near zero, full reference Skill 36/36, starter in band,
  provider-reported costs available, no unexpected errors, same model ID
  observed both variants, revision warning shown). Qwen3.5-0.8B is NOT a
  supported subject.
- Platform upload: compiled request must disable push AND resolved config
  must confirm it; a conformance test fails if a future pin changes the
  default or ignores the setting. No v0.1 run sends transcripts to a
  hosted platform.
- Tool-description delta: exact derived-difference rule (count/names/
  schemas/capabilities unchanged; only the known skill-aware description
  field changes; matches the pinned Hermes conformance fixture);
  classified "expected derived difference caused by the declared Skill
  mutation"; any other tool difference invalidates.
- Second result language: "guided Skill-replacement Uplift receipt",
  "same-benchmark development iteration", with the disclosure sentence
  about feedback coming from the same membership. NEVER "sealed uplift",
  "held-out uplift", "generalization proof", "independent validation".
  Candidate provenance includes the source feedback report digest.
- The 0/36→36/36 run stays as the reference full-skill proof; it is NOT
  the starter Skill (no headroom).

## Founder-Skill behavioral contracts (drafts may be prepared; Sean approves)

- skill-improver: find ONE general rule explaining the failure pattern;
  smallest general correction; no task-specific exceptions; never copy
  input/output pairs; never an answer table; return one complete revised
  SKILL.md; preserve correct rules; state tradeoffs; exactly one proposal.
  Receives verified source text separately from the digest-pinned context.
- rich-terminal-output: produces ONLY narrative choices (headline,
  observations to emphasize, one caveat to foreground, next-step
  explanation); never outputs or alters scores, deltas, W/L/T, cost,
  timing, proof grade, status, digests, or commands.
- Release pins and verifies all three Skill digests.
