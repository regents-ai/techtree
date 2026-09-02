# 0040 — v0.2 introduces a second Campaign document

Date: 2026-09-02. Lane working default, recorded by the v0.2 chief on the
WP1.1 review. Subject to founder confirmation before the upstream lock is
adopted; nothing here is presented as a founder ruling.

## Ruling

v0.2 adds `techtree.campaign.v2` as a **second Campaign document** beside the
frozen `techtree.campaign.v1alpha1`, rather than adding a field to the one
that already exists. The two are siblings: they share the scientific contract
through a private, non-document base, and neither validates as the other.

## Why a field could not simply be added

Proof verification does not compare stored bytes against a stored digest and
stop there. It parses `campaign.json` and **re-derives** the digest from the
parsed object (`cli/src/techtree/receipts/verify.py`, `_check_linkage`, via
`digest_object`), then checks it against the digest the bundle manifest and
the signed uplift report commit to.

That makes the v0.1 Campaign's field list part of every signature already
issued. Any field added to it — including an optional one defaulting to
nothing, because canonicalization emits every declared field — changes the
digest of documents that were signed years of evidence ago. Measured rather
than assumed: adding one required field to `CampaignSpec` breaks the frozen
recorded comparison fixtures at import time, and the frozen v0.1 proof's
Campaign stops digesting to `sha256:ebf029ab…`, the value recorded in
`release/certified-scientific-fingerprint.json` and inside the platform's
signed proof bundle.

So the v0.1 Campaign is closed. It is read-only history.

## What the v0.2 Campaign drops, and why

The execution plan the v0.2 Campaign binds already states three facts the v0.1
Campaign also stated. A fact stated in two places is a fact that can disagree
with itself, and there is no principled way to say which copy ran. The v0.2
document therefore drops:

| Dropped from the Campaign | Now owned by |
| --- | --- |
| `evaluation_backend` | the plan's execution plane |
| `agents.subject.harness.id` and `.version` | the plan's subject plane |
| `evidence.verifiers_episode` | the plan's evidence plane |

The rule that a Campaign is evaluated by `local_techtree` only belongs to the
document that has the field, and does not apply to v0.2. The v0.1 document
keeps all three, untouched.

## Naming

- `techtree.campaign.v2` — the second version of a document v0.1 already had.
- `techtree.execution-plan.v1` — a *new* document, so it starts at v1 even
  though it arrives in the v2 protocol generation.
- `schemas/v1alpha1/` is the v0.1 tree and its bytes are frozen because
  published evidence is validated against it. `schemas/v2/` is the v0.2
  protocol generation and holds only the documents whose shape changed.

One exception to that freeze was unavoidable and is recorded here rather than
hidden: factoring the shared scientific fields into a base class moves them
ahead of the document-only fields in Pydantic's field order, so the `required`
array in `schemas/v1alpha1/campaign.schema.json` is reordered. The set is
identical, no property or constraint changed, JSON Schema attaches no meaning
to that order, and no Campaign document's bytes or digest moved.

## How it ends

`techtree-di5` cuts the live write path over completely: a v0.1 bundle
verifier owned by `techtree.historical`, a v0.2 verifier on the live path, and
every producer — proof bundles, drafts, catalog, the Verifiers compiler, the
receipt builders, Doctor — moved to the v2 document. No function handles both
shapes and nothing branches on which document is in hand. Until that lands,
the v2 document is protocol only and the live path still writes v0.1.

Historical v0.1 artifacts are then reachable only through
`techtree.historical`, read-only, with their source bytes and digests never
rewritten (`techtree-i4e`).
