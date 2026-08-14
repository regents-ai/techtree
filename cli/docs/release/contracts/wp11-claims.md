# Execution contract — WP11-claims: product-claim-to-evidence matrix

Binding: decision 0023. Runs before WP11h; its output is a Gate-2
packet attachment.

## Purpose
Prove the public product description without adding runtime machinery:
one row per claim, each mapped to implementation, automated test, live
evidence, and honest limitation.

## Output
release/product-claim-evidence-matrix.md and .json.

## Required rows (extend if public copy claims more)

| Claim | Implementation | Automated test | Live evidence | Limitation |
|---|---|---|---|---|
| Campaign immutable | digest model | mutation test | Campaign digest | internal concept |
| Same tasks | TasksetLock | membership tests | proof bundle | fixed membership |
| Taskset valid | validation receipt | gold/negative tests | receipt digest | mechanical only |
| Neutral baseline | manifests | insertion test | run ID | toy task |
| Clean subjects | Docker runtime | isolation test | traces | local executor |
| Skill only changed | comparison verifier | mismatch matrix | UpliftReport | known derived description delta |
| Per-task receipts | receipt set | tamper tests | bundle | internal evidence |
| Signed report | Ed25519 envelope | signature tests | report digest | participant-attested |
| Cost/timing | execution record | provenance tests | record digest | provider revision unavailable |
| Data policy | DataPolicy | policy tests | digest | fixed v0.1 policy |
| Offline verify | proof verifier | tamper suite | command transcript | no honest-compute proof |
| Explicit approval | CLI/Hermes surface | anti-self-approval tests | audit event | surface attestation |
| Incomplete fails closed | executor | missing-episode test | failed run record | no Uplift receipt |

Each cell must name the actual module/test/artifact (file paths, test
names, run IDs, digests) — not a category. Live evidence cites the
canonical certification runs (Gate-1 packet §4) wherever applicable.

## Scope rows to add per 0023 §4
- Skill-bundle v1-vs-v2 comparison: supported when both bundles are
  supplied explicitly (multi-file mounting test, replacement run
  evidence).
- Guided revision: single-SKILL.md in v0.1; flow certified, no
  measured-uplift claim (Gate-1 §7c).

## Stop conditions
Any public claim with no implementation row · any row whose limitation
contradicts public copy.
