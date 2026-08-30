# 0025 — Campaign regeneration: option A, new USD 10.00 cap

Status: binding (founder authorization, 2026-08-14, verbatim: "I
authorize 'campaign regeneration: option A' use a new $10 cap").
Resolves ticket techtree-python-327 (P0 release blocker) and
supersedes the USD 3.00 programme cap of decision 0016 s4.

## Budget

The programme cap is raised to USD 10.00 within the founder's pool.
Accounting continues unbroken: 1.9717 spent to date, 8.0283 remaining
at authorization. All existing per-run rules stay: estimate before
run, USD 0.30 ceiling per comparison, USD 0.30 per host call, no
retry of paid outcomes.

## What option A is

1. REGENERATE the release Campaign to carry the certified science.
   The current catalog Campaign (5aef3fb7…) ships a development
   placeholder subject and null budgets; every certified run executed
   the fixture-derived campaign b9e3f00c… instead (audit:
   release/budget-contract-audit.json). The regenerated Campaign
   carries exactly the certified values:
   - subject: prime / qwen/qwen3.7-flash, credential_env
     PRIME_API_KEY, the honest model_revision_unavailable warning;
   - sampling.max_tokens 4096;
   - budgets.maximum_output_tokens 8000;
   - budgets.maximum_usd 1.00;
   - execution: parallel variants, max_concurrent 4,
     timeout_seconds 600, retry_limit 0
   (the values of the reproduced certified derivation, constants in
   tests/fixtures/verifiers/support.py — the regeneration makes the
   PRODUCT carry what the FIXTURE carried).
2. Regenerate everything downstream in the approved order: campaign →
   climb → catalog → schemas/goldens → release-inputs/release-core →
   cross-repo release copies. New campaign/climb/catalog digests; a
   new ReleaseCore digest; byte-identical ReleaseCore across repos
   re-verified.
3. RE-RUN the minimal canonical set under the regenerated lineage:
   one baseline-vs-starter stability pair plus one engine reference,
   with 0017's hard stops (band 20–27/36, zero cap kills, complete
   evidence, proofs verify offline). Estimated ~USD 0.54; each run
   pre-committed before its score exists; no selection, no retry of
   outcomes. These become the canonical certification runs of record
   for the released lineage; the prior runs remain preserved and
   disclosed as certification of the superseded lineage.
4. The Gate-1 approval STANDS: it approved the two Skill files (whose
   digests do not change) and accepted the certification record as of
   its date. The new lineage and runs are carried by the Gate-1
   addendum (ticket 28y) and the Gate-2 packet — the approved packet
   bytes are never edited.

## Timeout disposition (rides along, chief-recommended, copy-only)

The declared timeout_seconds 600 is enforced by nothing (audit
finding 1). The certified derivation carried the same declared-inert
value, so declaring it is faithful to certification; CLAIMING
enforcement is not. v0.1: no public surface may state that runs are
time-bounded; enforcement is a v0.2 candidate with its own
certification. The new /start page already quotes no figures; the
copy guards' no-price rule extends naturally here.

## Consequent unblocks

After regeneration + green re-runs: WP11b (wheel) unblocks; ticket
5i8 (plugin cost wording) becomes executable — the disclosure states
the Campaign's DECLARED USD 1.00 ceiling as a contract value, with no
claim of runtime estimation or abort.
