# 0033 — Prime-only serving; the user chooses the model

Date: 2026-08-26. Founder ruling, superseding the DESIGN sections of
0031 and 0032 (their four-provider ambition is retained as post-v0.1
direction; their contract changes are NOT implemented).

## Ruling

If provider flexibility is complicated — and it is (OAuth credential
bridge for Portal, a proxy serving chain, a CampaignSpec schema change
forcing lineage regeneration) — v0.1 keeps Prime as the only serving
provider, and end-user choice is expressed as CHOICE OF MODEL among
Prime-served models.

## Why this is the simple path (verified against the code)

Model choice requires no kernel, schema, or credential work at all: a
choosable model is simply another published, content-addressed
Campaign pinning that model with provider=prime and PRIME_API_KEY,
exactly the shape the catalog already holds. The CLI already lists
and prepares whatever Campaigns the release publishes. What each
additional model costs is scientific, not engineering: its own paid
certification and its own calibrated score band, since the "roughly
two-thirds" band is qwen-calibrated and does not transfer.

## v0.1 consequences

- v0.1 ships exactly the certified lineage: qwen/qwen3.7-flash via
  Prime. No re-certification, no schema change, no new credential
  path, no change to the frozen science. The Gate-2 plan and the
  parked re-pin (as0) return to their pre-0031 state: freeze when the
  open byte-changing tickets land.
- Additional Prime-served models arrive post-release as new certified
  Campaigns, each with founder-authorized certification spend and its
  own band copy. The choice UX is the existing Climb list.
- Multi-provider serving (Portal, then OpenAI/Anthropic with their
  own models) stays on the roadmap per 0031/0032 but nothing of it is
  built or carried in v0.1 — no dormant serving-layer code, per the
  hard-cutover rule.

## To the author (small packet)

1. Presentation: additional models as sibling Campaigns under one
   Climb, or as separate Climbs? What the public page may say about a
   model choice before that model's band is calibrated.
2. Band discipline per model: binding wording pattern so each model's
   band is stated only from its own calibration runs.
