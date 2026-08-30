# 0029 — The orphan bound: three containment layers (author-countersigned)

Status: binding (author ruling relayed by the founder 2026-08-20:
"implement or ask questions"; no blocking questions). Supersedes the
chief's single-watchdog proposal. Full technical specification:
docs/release/contracts/orphan-bound-fix.md (the author's spec,
preserved). One sentence this fix must make true:

> Every paid comparison has finite token, turn, and time limits that
> survive the death of the Techtree worker.

## The three layers

A. **Make the declared budgets real** — wire
   execution.timeout_seconds into the native Verifiers rollout
   timeout; compile finite max_turns / max_input_tokens /
   max_output_tokens / max_total_tokens; add the executable-budget
   validator (campaign_budget_not_enforced) so no declared field can
   ever again be decorative; enforce maximum_usd as a PRE-RUN
   precondition computed from the enforced token limits
   (campaign_cost_bound_exceeded).
B. **Survive worker death** — a tiny child-local supervisor process
   (own session) around each managed eval: parent-liveness pipe (EOF
   on worker death → immediate SIGTERM to the eval group), hard
   monotonic 1800-second variant deadline, SIGTERM-then-grace (inner
   20s < outer 30s, invariant-tested), private 0600 supervision
   record (techtree.eval-supervision.v1; no argv, no credentials).
   Eval keeps its own process group. NOT a daemon/service/registry.
C. **Prove it and bound it honestly** — no broad Docker kills ever
   (signal the exact supervised tree; Verifiers cleans up its own
   containers; if a container survives the graceful stop, STOP the
   release rather than adding a sweep); a REAL worker-SIGKILL
   injection capturing exact container IDs disappearing, supervision
   records saying parent_lost, elapsed orphan time, residual cost;
   the dollar bound derived from ENFORCED limits (episode input ≤
   I + context-window C, output ≤ O + per-call S, one-turn soft
   overshoot included), published as
   release/orphan-bound-analysis.json with the price profile and
   timestamp — "token exposure is protocol-bounded; the dollar figure
   uses provider pricing recorded at release time."

## Limit selection (no intuition)

A calibration table from every successful canonical episode (turns,
input/output/total tokens, elapsed seconds; split by
baseline/starter/reference/v1/v2; median/p95/p99/max + the task hash
at max). Predeclared formulas: turns = ceil(1.25 × observed max);
input = 1.5 × observed max rounded up; output = keep 8000 if runs sat
comfortably below; rollout timeout = 600 (now enforced); variant hard
deadline = 1800. Identical for both variants, in both compiled and
resolved configs, checked by the observed comparison, mutation-tested
(deleting any compiler assignment must fail a test).

## The maximum_model_calls mapping

Before compiling it to Verifiers max_turns: a conformance check that
intercepted subject-model generations == Trace.num_turns for the
pinned profile (recorded fixtures + one live probe). If it fails, add
maximum_turns and leave maximum_model_calls unsupported until v0.2 —
never a silent false mapping.

## Chief resolutions of two internal inconsistencies (recorded)

1. Budgets expose THREE publisher decisions (turns, input, output);
   maximum_total_tokens is DERIVED (input + output) in the compiler
   per the spec's §2, not a fourth declared field; the validator
   checks the three declared fields plus timeout_seconds > 0.
2. The 1800-second variant deadline is a named release constant in
   the child-launch path (with the grace invariants), not a Campaign
   field, per the spec's layer split (rollout timeout is the
   Campaign's; the variant deadline is the supervisor's).

## Recertification (scientific execution + budget change)

New Campaign digest → compiled configs → fixtures → catalog cascade →
ReleaseCore → wheel/plugin/website copies. Paid: two baseline-vs-v1
stability comparisons, one baseline-vs-reference, one v1-vs-frozen-v2
(re-execute, never re-propose — the absolute-last-proposal ruling
holds), plus the live turn-conformance probe and the kill injection.
Then the founder's packaged onboarding journey. Offline verification
of every new proof; budget audit refresh; no-upload capture.

## Stop conditions

Worker death not triggering prompt child shutdown (pipe EOF + grace,
not the 30-minute deadline) · containers surviving the supervisor ·
any declared cap still inert · any post-fix canonical run REACHING a
new limit (stop; never auto-raise; any cap change is another Campaign
version) · finite token/turn exposure not derivable from enforced
limits (mutable provider pricing is NOT itself a blocker; missing
finite exposure is).
