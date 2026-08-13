# 0006 — Evaluation model selection and spend budget (provisional)

Status: chief-of-staff decision under delegated authority (Sean,
2026-08-13: PRIME_API_KEY exported, "$5 in the account for API / compute
spend if needed", "keep driving the work packages orchestration").
PROVISIONAL until founder ratification at the WP11h launch gate, where
the release coordinates (including the live Campaign's model spec) get
Sean's explicit sign-off. The live Campaign is regenerable until then, so
this choice freezes nothing permanently.

## Provider

Prime inference (per spec §10.3: base URL pinned by the release profile;
credential from the PRIME_API_KEY environment variable). Matches the
author's "first supported release profile".

## Model selection procedure (WP6b executes this)

The WP6b worker must select the subject model EMPIRICALLY, not from
memory:

1. Enumerate the models actually available to this key through the
   pinned Verifiers client / Prime inference API.
2. Choose the cheapest instruct-capable model that Hermes Agent 0.19.0
   supports as a subject, preferring a small model — BranchCode is
   deliberately easy; the demo measures skill-transfer, not frontier
   capability, and a small model gives more headroom between baseline
   and skill-enabled scores.
3. Record the exact provider string, model id, and (if exposed) revision
   in the live Campaign's ModelSpec, and note per-token pricing in the
   ticket.

## Spend guardrails

- Total authorized: USD 5.00 across all WP6–WP11 development and
  acceptance runs.
- The live Campaign's BudgetSpec sets `maximum_usd: 1.00` per run
  (36 tasks × 2 variants × short prompts should cost cents; 1.00 is a
  hard per-run ceiling, not a target).
- Workers estimate cost before the first real run and abort if an
  estimate exceeds the per-run cap; cumulative spend is noted on each
  ticket that makes model calls.
- The credential is read only from the environment at eval-child launch
  (spec §6.9); never stored, logged, echoed, or passed through chat or
  tool arguments.

## Amendment (2026-08-13, WP6c): selected model

The §"Model selection procedure" executed twice and converged on
**qwen/qwen3.7-flash** (Prime inference). Qwen3.5-0.8B was refuted
empirically: it cannot open a mounted Skill (probes: wrong-name search,
tool-call misfire; 0/4 with the Skill) and runs away on hard tasks.
qwen3.7-flash: 2/2 with the Skill, 0/3 clean baseline, then 0/36 vs 36/36
on the real concurrent run at USD 0.20 (estimate 0.19); reports no cached
tokens, so costs are exact. Spend to date (worst case): ~USD 1.30 of 5.00.
Still provisional until WP11h founder ratification.
