# 0032 — The model is the subject; the provider is a serving choice

Date: 2026-08-26. Founder ruling, refining decision 0031.

## Ruling

The variant axis is the MODEL, not the provider. The CLI shows which
model is being tested; the participant chooses which supported
provider serves it. The same model served by two providers is treated
as near-identical, with serving variance acknowledged in presentation
(error bands or equivalent) rather than walling results off per
provider. End results never compare providers, and never claim
provider equivalence either — the provider is disclosed as an
execution coordinate of the run, like the machine it ran on.

This supersedes 0031's per-provider Campaign-variant frame. What
survives from 0031: the four-provider commitment (OpenAI, Anthropic,
Nous Portal, Prime), the v0.1 scope of Prime + Nous Portal, and the
Portal credential wrinkle.

## The design this implies

1. The Campaign pins the model and sampling — the scientific subject.
   The provider and its credential path move OUT of the frozen
   scientific contract into a serving coordinate: chosen at run
   time from a supported registry, recorded in the run request,
   receipts and proof, disclosed wherever the result is shown.
2. Within one comparison, baseline and candidate MUST be served by
   the same provider — otherwise the Skill is not the only change.
   Enforced before launch, evidenced after.
3. Comparability groups by model. Two participants who ran the same
   model are comparable, with the serving path disclosed; nothing is
   ever presented as a provider-versus-provider result.
4. Serving variance is acknowledged honestly: v0.1 at minimum
   discloses the provider and a variance caveat; statistical error
   bands are a presentation design the author is asked to rule on.

## v0.1 consequences

- The pinned subject model stays qwen/qwen3.7-flash. The calibrated
  band is model-calibrated and carries over to any serving path,
  with the variance caveat.
- Verified 2026-08-26: Nous Portal's gateway exposes Qwen models via
  a proxy chain (Portal -> OpenRouter -> an upstream host); Nous's
  own backend natively serves only the Hermes family. Whether the
  exact pinned coordinate is available through Portal, and whether
  sampling controls pass through faithfully, must be verified at
  implementation; the proxy-chain disclosure question goes to the
  author.
- Moving provider out of CampaignSpec changes the schema and the
  campaign document, so the fingerprint moves and the lineage must be
  regenerated and re-certified the way decision 0025 did it — a
  bounded, known procedure, and far cheaper than certifying a new
  model: no new band calibration.
- OpenAI and Anthropic arrive post-release WITH their models: those
  providers only serve their own model families, so they enter as new
  subject models, each with its own calibration.

Blocked on: the author's answers to the revised packet, and founder
budget authorization for the lineage regeneration + a Portal-served
certification leg.
