# 0037 — The verified-run page shows the real certified example

Date: 2026-08-26. Founder ruling.

## Ruling

The public verified-run page leads with a real, published example:
"Example Baseline vs. Instructional Skill", drawn from the signed
uplift report of the quiet-window re-certification run
run_06b2377d55f6455a9dc5a73e6f14e384 (2026-08-20, campaign
ad393bc0…). Exact counts are shown — 0 of 36 without the Skill, 24 of
36 with it, 24 wins, 12 ties, 0 losses, decision accepted — as an
explicit, single-example exception to the band-only rule. The band
rule stands everywhere else.

## Provenance and safeguards

- The report file entered techtree-ash byte-exact from the proof
  bundle (priv/examples/uplift-report.json, sha256:0acf6117…), after
  the chief verified the proof offline (339 checks) and scanned the
  file: it carries only reward numbers, fingerprints and task hashes.
- Every number on the page is computed from that served file at
  render time; nothing is typed into a template. A test recomputes
  the numbers from the same file and fails on any drift; a second
  guard refuses any win/tie/loss figure on the page that the report
  does not carry.
- The example renders ONLY while its campaign fingerprint equals the
  campaign the channel serves; otherwise the page falls back to the
  honest no-result state. Consequence: the in-flight Verifiers-pin
  switch will change the campaign fingerprint, and the example MUST
  be refreshed from a new certified run of the re-pinned campaign —
  otherwise the page quietly (and honestly) loses its example.
- Reader-facing truth is unchanged: nothing is received or uploadable;
  the page still says publishing your own result arrives in a later
  release.

## Copy

The founder's wording is used with one grammatical repair, flagged:
"proving that a Hermes agent can run long-horizon tasks using the
Techtree Plugin, and create verifiers proofs of Skill uplift" (the
draft's "can have long-horizon tasks" read as a typo). The word
verifiers carries the hover definition card (Prime Intellect credit,
GitHub link) ruled earlier the same day.
