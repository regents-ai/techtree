# Prime Hosted evidence

This directory contains the bounded evidence used by the WP0.3 Prime Hosted
contract spike. The evidence is derived from the exact `prime==0.6.31` and
`prime-evals==0.2.3` wheels, the pinned Prime source archive, plain CLI help,
a selected projection of the public OpenAPI document, and the sanitized
read-only responses observed on 2026-09-01.

`evidence_manifest.json` binds every source snapshot to its wheel member, line
range, excerpt-byte digest, and parent-member digest. Help snapshots carry
their own exact byte digests. The OpenAPI projection records its JSON pointers
and is checked against the retained 295,750-byte public document, whose source
digest and path are recorded in the manifest.

`responses/` holds the retained provider responses under `response_snapshots`,
each with the exact command that produced it. Where a response returned
provider-internal identifiers, those fields are replaced by documented
placeholders and are persisted nowhere. The retained hub action log is the
provider's own runner output; the `/workspace` paths in it are the hub's, not a
local machine.

No hosted evaluation was created, read, cancelled, or paid for, and no model
work was started. The one provider mutation is the separately approved
zero-cost publication of the conformance environment, recorded in the manifest
under `provider_actions_observed`. These are contract observations, not
hosted-run results.
