# Public Wallet Bench export — 17 October 2026

Cloud handoff branch: `codex/wallet-bench-export-20261017`.
Reviewed base and observed deployed code: `119a0a4ac8f585c87c0d06809cf10f844467c1f5`.

Sean's requested zoomable 3×3-dot matrix and full-screen Patchbay report require the
public evidence currently rendered by Techtree's run page. `GET /api/wallet-bench/:id`
provides schema 1 using the same published attempt reads, an explicit public field
projection and the existing sanitized evidence manifests. It runs no benchmark and
adds no write, signing or money action. This producer must deploy before the Patchbay
consumer, after the Mac session's model-free application gates and Sentinel read.

Full design decisions, source-review result, test counts, unverified boundaries and
ordered acceptance checks are in the companion Patchbay handoff:
https://github.com/regents-ai/patchbay/blob/codex/wallet-bench-matrix-20261017/docs/handoffs/2026-10-17-wallet-bench-matrix.md

The actual serializer boundary test passes in isolation, including private sentinel
exclusion, exact amounts, event completion time and evidence paths. A synthetic JSON
round-trip passes Patchbay's consumer and rejects wrong identity/count/artifact types.
This is not a full application/DB/HTTP test. Run the existing OpenAPI route-parity test
and new `wallet_bench_json_test.exs` in the configured Mac checkout, then verify the
actual new route and malformed-ID 404. The existing OpenAPI test includes this new
API prefix; the generated public description and `/llms.txt` document the route.

The public and repository changelogs carry the same unreleased entry. Update them to
the actual release state at shipment. No frozen result, benchmark configuration,
private provider record, historical evidence file or production database was changed.
