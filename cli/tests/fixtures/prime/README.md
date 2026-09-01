# Prime Hosted evidence

This directory contains the bounded evidence used by the WP0.3 Prime Hosted
contract spike. The evidence is derived from the exact `prime==0.6.31` and
`prime-evals==0.2.3` wheels, the pinned Prime source archive, plain CLI help,
and a selected projection of the public OpenAPI document.

`evidence_manifest.json` binds every source snapshot to its wheel member, line
range, excerpt-byte digest, and parent-member digest. Help snapshots carry
their own exact byte digests. The OpenAPI projection records its JSON pointers
and is checked against the retained 295,750-byte public document, whose source
digest and path are recorded in the manifest.

No hosted environment was published, no hosted evaluation was created or
cancelled, and no paid model work was started. These are contract observations,
not hosted-run results.
