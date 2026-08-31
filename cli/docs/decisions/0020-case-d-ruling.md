# 0020 — Case-D ruling: one fixed-cap rehearsal reattempt

Status: binding (author ruling relayed by the founder, 2026-08-14).

The GLM 5.2 canonical attempt is reclassified
`diagnostic_host_completion_truncated`: it discovered the correct
hypothesis, tested it rigorously, rejected it on one contradictory
observation (the aspen outlier), and hit the 16,000-token
host-completion ceiling while still reasoning. That ceiling is
candidate-production configuration, not the evaluated subject
Campaign; correcting it before release is a harness-limit correction,
not a user-level retry.

## Authorization

Exactly ONE new canonical guided-rehearsal attempt: same source run
(post1), same GLM 5.2 host, same founder skill-improver, same
sanitized context, same source Skill, same strict structured-output
schema — with a single predeclared higher completion ceiling (32,768
is reasonable when the provider supports it under strict schema and
the existing USD 0.30 hard ceiling holds; verify support before
launch; no fallback to a weaker schema mode; no adaptive ladder of
values). All values frozen before the response is seen: host model
ID, provider/profile, strict setting, new max completion tokens,
dollar ceiling, retries 0, repairs 0, improver/source/context/schema
digests, complete request digest. One generation request only.

## What must NOT change

Do not revise the founder skill-improver. Do not remove or relabel
the aspen outlier — telling the model would inject privileged
interpretation into candidate production. Do not change the
improvement context or the subject Campaign. The test is whether a
capable host proposes the simplest 12-of-13 general rule with stated
uncertainty despite one honest contradictory outcome — which the
founder Skill already invites.

## Outcome rules

- Valid Skill v2 → the existing immutable path: scan, snapshot,
  digest, deterministic diff, explicit approval, one v1-vs-v2
  comparison, second signed receipt. No outcome is retried.
- Finishes but no usable Skill → STOP; no further completion;
  finalize Gate 1 with the first controlled comparison canonical and
  guided revision marked experimental (shippable behind the label or
  omitted from the primary promise).
- Diagnoses correctly but cannot serialize the full file → the
  remaining problem is output-transport design (list-of-lines shape);
  a real schema change deferred to a later release with its own
  certification — never slipped into this one.

## Accounting and privacy

The packet distinguishes the diagnostic 16k attempt (correct
hypothesis, rejected on the outlier, truncated, no candidate, cost
recorded) from the canonical release-profile attempt (higher frozen
cap, one request, no retry, outcome preserved whatever it is;
candidates 0 or 1). The 51,635-character raw reasoning stays local
(bytes, digest, provider IDs, length, stop reason, private path);
the packet carries only a safe summary, response digest, length,
stop reason, and classification. Model reasoning never becomes
public release content.

## Sequencing note (chief)

Decision 0019's approval simplification replaces the token machinery
the current freeze certified, so the reattempt runs after 0019 lands
and the plugin re-freezes — the certified configuration must be the
released configuration.
