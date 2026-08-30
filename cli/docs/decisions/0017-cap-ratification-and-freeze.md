# 0017 — 0016 ratified; post-change gates, freeze discipline, and reconciliation

Status: binding (author ratification relayed by the founder,
2026-08-14). Written against events the ratification crossed in
flight: the post-change certification had already completed when it
arrived. Reconciliation is explicit below.

## Ratified

Decision 0016 (symmetric cap raise, new Campaign digest, full
regeneration, no pre/post mixing, all old runs retained as
diagnostic, restart from clean state, hard stop on recurrence) is
ratified. The scientific invariant of record: a changed scientific
configuration creates a new artifact lineage; it never retroactively
repairs the old one.

## Post-change gates vs the completed runs

Both fresh calibrations and the reference completed: 72/72 episodes
each, no episode failed on an output-cap stop, no missing reward,
baseline 0/36 (band 0–2), starter 23/36 twice (band 20–27), reference
36/36, all proofs and signed execution records verify, costs
0.1709–0.1827 under ceilings. Exact-24 is not required and not
claimed; the public claim stays "calibrated to solve roughly
two-thirds of the toy tasks."

**Disclosed amber item for the author:** two individual baseline
CALLS in the first post-change calibration reached the 4096 ceiling
(longest 4098) and the harness recovered; both episodes completed and
scored. No episode was killed by the cap anywhere post-change. The
chief's reading: the hard-stop rule targets episode-killing cap
stops, and call-level truncation with recovery is the harness's
designed behavior — but the ratification's stricter phrasing ("any
post-change episode hits the cap") makes this the author's call. The
packet carries the two calls' data. The cap is NOT raised again.

## Episode-budget confirmation

The Campaign declares, identically for both arms: max_tokens 4096 per
call, timeout_seconds 600 per episode, retry_limit 0, max_concurrent
1, num_rollouts 1. No separate max_turns or max_total_tokens knob
exists. The episode budget is nonetheless finite: generation rate
bounds a 600-second episode to roughly twenty maximum-length calls
(~82k output tokens, cents at pinned prices), and the observed
baseline episode is ~11 calls. Chief ruling: do NOT add a new
Campaign knob now — it would restart certification (~USD 0.75) to add
a guard the timeout already provides in this toy Campaign. Queued for
the author with these numbers; reversible before freeze at the cost
of a recertification.

## Membership is frozen against outcomes

No membership change may follow observed post-change scores. If
calibration ever leaves the band: either publish a newly supported
band, or revise the starter as a new artifact with new static
calibration, new digest, and restarted certification. Never both,
never silently.

## Freeze discipline (in force now)

The Python scientific tree is frozen at the cap-change lineage
(campaign 5aef3fb7, engine 874cbae0, membership 56f697fb, starter
596d1368, improver e6bc16c4) for the remainder of certification.
Permitted: run-owned evidence, certification records, packet
assembly, cross-repo synchronization of committed artifacts,
release-packaging fields that touch no scientific digest (the
in-flight bootstrap starter-URL field), copy and copy-guard changes.
Not permitted without a full digest cascade and certification
restart: Campaign, sampling, membership, starter bytes, normalizer,
runtime image, model/profile, scorer, harness, or tool-surface
changes.

## Hard stops (full list, in force)

Any post-change episode killed by the cap; either arm resolving a
different cap or runtime image; baseline materially above band;
starter materially outside band; a proof requiring an old artifact to
change; more than one host generation request in the rehearsal; a
proposal containing an observed evaluation case; a second run without
explicit approval; any local artifact uploaded; spend crossing the
ceiling. A recurred cap kill is investigated, never auto-raised.

## Economics presentation

Four separate values everywhere costs appear (Campaign budget,
website copy, plugin approval copy, packet, execution records):
typical observed cost, pre-run estimate, hard authorized ceiling,
actual provider-reported cost. The ceiling is never presented as the
expected price. Hidden reasoning is recorded as counts and stop
reasons only — never content.

## Gate-1 packet additions

A sampling-cap correction lineage section (old digest + 512, failure
IDs/arms/costs, 0016, new digest + 4096, regeneration report,
post-change canonical IDs) with the explicit statements: no
pre-change run is canonical certification evidence, and no historical
run artifact was rewritten. The final run table classifies every run
by campaign digest, purpose, completeness, score, and canonical
status; post-change cost and call-count distributions, maximum call
and episode totals, and all stop reasons attach.

## Still open

The guided rehearsal remains blocked on the author's host-model
ruling (the attempt-4 evidence: the pinned-subject model, used as a
stand-in host, cannot find the planted defect even with inputs
visible and twice failed to emit a multi-line file into JSON — the
improver-revision lever is contraindicated; a stronger rehearsal host
is the chief's recommendation since the product's host is the
participant's own model).
