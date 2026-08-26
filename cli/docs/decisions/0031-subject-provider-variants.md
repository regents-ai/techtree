# 0031 — Subject-provider variants; v0.1 ships Prime + Nous Portal

Date: 2026-08-26. Founder ruling.

## Ruling

The end user chooses which provider the evaluated subject runs on.
Four providers are supported: OpenAI, Anthropic (Claude), Nous
Portal, and Prime. Sequencing, chosen by the founder from three
costed options: v0.1 ships TWO certified variants — the existing
Prime variant and a new Nous Portal variant — and the OpenAI and
Anthropic variants follow after release.

## What a variant is

A pinned model cannot move across providers: OpenAI does not serve
qwen, Anthropic serves only Claude models, Nous Portal's own models
are the Hermes family. "Supporting a provider" therefore means a
per-provider CAMPAIGN VARIANT: its own content-addressed Campaign
pinning a (provider, model, credential path) triple that provider
actually serves, its own paid certification, and its own calibrated
score band. The four statements hold within a variant. Results are
never compared across variants, and no copy may imply they can be.

The contract already carries this shape: ModelSpec's `provider` and
`credential_env` are Campaign fields (models/campaign.py), the
compiler has no provider table and never writes a provider URL into
run inputs, and the Hello World document simply declares
provider=prime. Nothing in the kernel is Prime-specific.

## The Nous Portal wrinkle (verified against Portal docs 2026-08-26)

Portal inference is OpenAI-compatible at
inference-api.nousresearch.com/v1 with Hermes-4.3-36B / Hermes-4-70B /
Hermes-4-405B — but Portal authentication is OAuth: a refresh token
at ~/.hermes/auth.json minting short-lived JWTs per request, not a
static API key in an environment variable. The Campaign contract
authenticates the sealed subject through `credential_env`, and the
eval client reads that variable inside the container. Bridging this —
static Portal keys if they exist, a launch-time JWT injected as the
declared variable with a refresh story for long runs, or something
else — is the first design question, and it goes to the author before
any implementation. Portal also proxies OpenAI and Anthropic models,
which may be a shortcut worth weighing for the post-release variants.

## What this does to the release plan

The source freeze and the one-time re-pin (ticket as0) now wait on
the Nous variant landing; Gate 2 covers both variants. Certifying
the Nous variant is new paid work — model pin, band calibration and
budget need explicit founder authorization once the author's answers
are in. Nothing about the certified Prime lineage changes.

Tickets: techtree-python-yqj (directive), children for the author
packet, the credential design, the variant Campaign, certification,
and the post-release OpenAI/Anthropic variants.
