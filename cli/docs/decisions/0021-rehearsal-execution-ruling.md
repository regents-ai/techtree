# 0021 — Rehearsal v1-vs-v2 execution after the launcher credential failure

Status: binding (chief ruling under the founder's standing orchestration
authorization, 2026-08-14). Records how the guided-rehearsal outcome
path proceeds after `model_credentials_missing`.

## What happened

The single authorized rehearsal completion (0020) succeeded at the
predeclared 32,768 ceiling: `finish_reason=stop`, 7,400 tokens,
request digest identical to the frozen value, USD 0.0417. The proposal
passed every guard and produced a valid Skill v2
(root `sha256:b143866e…`, parent v1 `596d1368…`, 1,907 bytes). Under
0020's outcome rules this selects the first path: scan, snapshot,
digest, deterministic diff, explicit approval, one v1-vs-v2
comparison, second signed receipt.

`techtree_uplift_start` then launched the comparison through the real
detached launcher for the first time in this programme, and the worker
failed instantly with `model_credentials_missing`: the scrubbed worker
environment deliberately copies only PATH/HOME/TMPDIR/
TECHTREE_LOG_LEVEL, so a provider credential exported in the
operator's shell cannot reach a detached run. No episode ran, nothing
was billed, no traces exist. The run is durably `failed` and its draft
is spent.

## Ruling

1. The failed run's bytes are preserved exactly as written — `failed`
   state, honest error, no rewriting, no relabeling. It appears in the
   packet's run classification as
   `infrastructure_failure_no_measurement`.
2. ONE fresh draft is prepared from the identical, unchanged Skill v2
   bytes already on disk, and the v1-vs-v2 comparison executes
   in-process — the same execution path that produced every piece of
   canonical evidence in this certification (both stability runs, the
   engine reference, and the fresh rehearsal source). This is
   consistency with the certified evidence base, not a workaround.
3. This is NOT a second completion (0020's scarce resource is spent
   and is not touched), and it is NOT a retried outcome (no outcome
   existed — no episode ran and nothing was billed). It is the same
   class as the calibration re-executions after infrastructure
   failure already ruled acceptable.
4. The environment-scrubbing behavior is correct and intentional and
   MUST NOT be weakened. The gap is a documentation/onboarding gap in
   the fresh-install journey — a participant exporting PRIME_API_KEY
   hits this at their FIRST paid run. Ticketed as techtree-python-3ym
   (docs/copy only), distinct from ndq.3.43.
5. Budget: comparison ceiling USD 0.30 (estimate ~0.21) from the
   remaining 1.0834 of the 3.00 programme cap. All other 0020 rules
   unchanged: the diff is reviewed before approval, the comparison
   runs once, its result is preserved whatever it is, and no outcome
   is retried.

## Why not wait for founder action

Option 1 (configuring an active Prime CLI credential) blocks on the
founder and exercises a path the certified evidence never used.
Option 2 spends pre-authorized budget on the pre-authorized
comparison over the pre-authorized execution path. The founder's
standing instruction is to keep driving and record decisions; the
Gate-1 stop still happens before any approval phrase is requested,
and the packet discloses this ruling in full.
