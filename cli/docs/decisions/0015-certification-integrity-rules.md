# 0015 — Certification integrity rules (author assessment, reconciled)

Status: binding (author rulings relayed by the founder, 2026-08-13).
The assessment was written at the log point "B failed once, rehearsal
pending"; events that postdate it are reconciled at the end.

## 1. Certification-run classification (supersedes the chief's
## option-1 stability ruling)

Only post-fix, complete, final-artifact runs are canonical evidence.

| Run | Post-fix? | Complete? | Certification use |
|---|---|---|---|
| Discovery probe | pre-fix | yes | diagnostic |
| Calibration 1 (0/36→24/36) | pre-fix | yes | disclosed only, NOT canonical |
| Engine recertification (0/36→36/36) | post-fix | yes | engine evidence |
| Calibration A (0/36→24/36) | post-fix | yes | canonical |
| Calibration B + re-run | post-fix | no | disclosed failures |
| Guided rehearsal attempts | post-fix | — | disclosed; canonical when a complete v1→v2 pair lands |

Consequence: the stability pair requires ONE MORE complete post-fix
baseline-vs-starter comparison beside Calibration A.

## 2. Artifact immutability (required written answer before Gate 1)

Question of record: were any run-owned or proof-owned files from an
already completed paid run modified after execution when the
executor_kind bug was fixed? If only committed test/contract fixtures
were regenerated, document exactly which. If live scientific
artifacts were changed: preserve or restore original bytes, classify
those runs pre-fix/non-certifying, exclude from canonical evidence,
add a correction/supersession record. The append-only evidence model
admits no retroactive truth-fixing.

## 3. Output-token-cap failure policy

An incomplete run is "no result", never a poor score; execution
errors are never mapped to reward zero inside Techtree — only the
Verifiers task contract defines what earns zero. A score-blind
full-pair rerun of a failed comparison is permitted when the original
produced no comparison, nothing favorable was discarded, the failure
and its cost stay disclosed, and authorization precedes the outcome.
If the SAME output-cap failure repeats: stop, investigate (cap size,
truncation point, hidden reasoning tokens, symmetry of risk), and any
cap change applies to BOTH variants, creates a new Campaign digest,
restarts post-change certification, and never mixes pre/post-change
runs in one stability set.

## 4. One completion means one model generation request

The one-turn promise binds at the provider boundary, not just the
plugin method: automatic semantic retries, invalid-output retries, and
structured-repair completions are all zero for the guided flow;
transport-level client retry (e.g. an HTTP client's default retry on
429/timeout) must be disabled or shown absent. Record per attempt:
invocation count, outbound generation-request count where observable,
request/response IDs where available, request and response digests. A
failed or invalid single request consumes the attempt, proposes no
candidate, and returns an honest typed failure.

## 5. Live evidence vs committed fixtures

Committed fixtures are sanitized conformance assets, never the
canonical live run record. Before commit: no absolute paths, no
unnormalized timestamps, no hostname/username, no credential
material, no provider request bodies, no hidden answers, no excluded
subject replies, no ephemeral cost/timing in byte-stable artifacts.
Release evidence (signed artifacts, real cost/timing, run IDs) is
retained outside the engine bundle; no engine digest may depend on
ephemeral provider values.

## 6. Reliability release gate and band language

Final canonical evidence requires: two complete post-fix baseline-v1
comparisons, one complete guided v1→v2 rehearsal, one complete
clean-machine introductory journey — with no output-cap incompletion
in those canonical runs. Release copy: "calibrated to the 20–27/36
band" (public page: "calibrated to solve roughly two-thirds of the
toy tasks; individual runs may vary") — never an exact-score claim.
The stability sample (24, 24, 23 with the easy-task slip explained)
stays in the record.

## 7. Gate-1 packet additions

Sections required: (A) artifact-immutability statement; (B) the
classification table above for every paid run; (C) retry accounting
(why each rerun, score-blind authorization, host-proposal request
count, evaluation rerun count); (D) incomplete-run costs inside total
certification spend; (E) final proof roots per canonical run (request
digest, campaign digest, all skill digests, candidate v2 digest,
execution-record digest, report digest, bundle digest, executor key
fingerprint, verification result).

## Reconciliation with events that postdate the assessment

- Calibration B's re-run failed with DIFFERENT causes (closed stream;
  upstream 429), not the output-cap. The same-cause stop rule
  therefore does not bind; one further score-blind full-pair attempt
  is authorized under rule 3 to complete the stability pair, with a
  hard stop if any output-cap incompletion recurs.
- Rehearsal attempts 1 and 2 failed and were diagnosed (decisions
  0014): context starvation (public_prompt hardcoded None despite
  R1's MAY) and a guard refusal with an untruthful reason. The 0014
  fixes stand — they are consistent with this assessment's honesty
  posture — flagged for author veto until the freeze. The improver-
  revision lever (0013) remains unused.
- Attempt 3 runs post-fix with the transport-retry verification of
  rule 4 applied to the harness (client retries hard-disabled) and to
  the product path by test.
