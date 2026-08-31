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

## Founder answers (2026-08-26, ruled directly, no author relay needed)

1. Additional models are SIBLING Campaigns under one Climb, presented
   as different lines on the same chart. Uncalibrated models are
   distinguished by DASHED lines. Chief's binding refinement so this
   never collides with the no-invented-numbers rule: a line — solid
   or dashed — is only ever drawn from measured runs. A certified,
   calibrated band draws solid; preliminary measured runs that are
   not yet a certified calibration draw dashed and say so in the
   label; a model with no measured runs gets no line at all, only a
   legend entry marked "not yet calibrated". A dashed line is a
   confidence style, never a sketch of data that does not exist.
2. Per-model band discipline accepted: each model's band is stated
   only from that model's own calibration runs; copy guards extend to
   every surface that states a band when the first added model ships.
