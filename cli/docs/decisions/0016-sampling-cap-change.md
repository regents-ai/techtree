# 0016 — The sampling cap rises symmetrically; post-change certification restarts

Status: binding (chief decision exercising the 0015 s3 pre-structured
rule, 2026-08-13/14). Founder/author may veto before the freeze.

## Finding

The Campaign's sampling `max_tokens: 512` interacts with
qwen/qwen3.7-flash's reasoning tokens (which bill against
`completion_tokens` — a mean of ~105 baseline / ~180 candidate spent
before any visible output) to kill episodes whose call chains run
long. Per call the at-cap risk is symmetric (2.41% vs 2.42%); per
episode it is 4.8:1 against the BASELINE, because an episode without
the Skill takes ~10.9 calls against ~2.3 with it. Measured baseline
episode kill rate 1.85% → a ~49% chance per comparison of losing at
least one of 36 baseline episodes. Observed: 3 of 6 paid comparisons
died exactly this way (branch-code-030; -024; -003 and -004 in one
run). USD 0.5037 of certification spend bought no comparison. This is
a Campaign parameter defect threatening the control arm — not
provider flakiness, not bad luck.

## Decision

1. Raise the Campaign sampling `max_tokens`, applied identically to
   both variants — one symmetric change, no other sampling or
   configuration difference. The worker chooses the value from the
   observed call-length distribution (clear the observed tail plus
   the reasoning burden with comfortable margin; justify the number;
   `env.subject.max_output_tokens: 8000` remains the outer bound).
2. Per 0015 s3: new Campaign digest and full downstream cascade
   (membership commitment unchanged, but campaign/policy → catalog →
   ReleaseCore → cross-repo copies regenerate), and post-change
   certification restarts. Pre-change and post-change runs never
   share a stability set.
3. Evidence classification: every pre-change run (cal1, calA, the
   three failed B attempts, the probe, rehearsal attempts) becomes
   pre-change diagnostic evidence, disclosed in full with costs. The
   canonical set is rebuilt post-change: two complete baseline-vs-
   starter comparisons, one engine reference comparison under the
   release Campaign, one complete guided v1→v2 rehearsal.
4. The certification programme cap rises from USD 2.00 to USD 3.00,
   still inside the founder's USD 5.00 pool (decision 0006; ~2.64
   remained in the pool at this ruling). Estimate-before-run and the
   1.00/run ceiling are unchanged.
5. The calibration expectation is unchanged by the cap: the baseline
   scores 0/36 for capability reasons, and candidate at-cap exposure
   was 1.9% of episodes. The 24-agreement membership and the
   20–27/36 band stand. If the post-change runs contradict this, stop
   and re-examine.
