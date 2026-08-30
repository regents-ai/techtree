# Execution contract — WP11-budget: public Campaign budget-contract audit

Binding: decisions 0016, 0023. Audit only — no new subsystem, no new
knobs. Runs before WP11h.

## Purpose
The 512→4096 cap change (decision 0016) proved budget settings are
scientific configuration, not incidental flags. Audit every
budget/limit field of the release Campaign and prove the public story
matches the machine.

## Verify
per-call output cap (4096) · per-episode maximum model calls ·
per-episode maximum turns · per-episode timeout · per-episode
total-token ceiling if implemented · variant concurrency · comparison
cost ceiling · the SAME limits bind both variants (baseline and
candidate) · the resolved runtime configuration matches the manifest ·
budget violations fail closed (a breached ceiling ends the run without
a valid UpliftReport) · website and approval copy state the actual
limits.

## Record
The Campaign lineage across the cap change: the pre-change campaign,
decision 0016's rationale (hidden reasoning tokens vs the control arm;
symmetric raise; certification restart), and the post-change canonical
evidence. The audit shows the released Campaign's values are the
certified values.

## Output
release/budget-contract-audit.json — every field, its manifest value,
its resolved runtime value, the test or run evidence that binds them,
and the copy surfaces that state it.

## Stop conditions
Any asymmetry between variants · any limit whose resolved value
differs from the manifest · any public copy stating a different
number.
