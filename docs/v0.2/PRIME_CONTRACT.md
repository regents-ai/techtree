# Prime Hosted contract spike

Status: captured with release blockers. Candidate: `prime==0.6.31`, with
`prime-evals==0.2.3`; admission remains blocked.

The evidence index in
[`cli/tests/fixtures/prime/evidence_manifest.json`](../../cli/tests/fixtures/prime/evidence_manifest.json)
binds the exact official CLI wheel and source archive, the exact public SDK
wheel, plain CLI help, the exact 295,750-byte public v1 OpenAPI document, and
a bounded projection of that document. The shape record is
[`official_cli_0_6_31.json`](../../cli/tests/fixtures/prime/official_cli_0_6_31.json).
The index records artifact digests, source line ranges, excerpt digests, and
the full OpenAPI digest; it contains no account data, credentials, or hosted
run output.

The retained evidence shows machine-readable CLI and SDK shapes for team
discovery, environment inspection, evaluation get/list, and sample reads, but
no sanitized runtime response envelope has been observed, so none is admitted
as a supported read yet. The evidence also records the limits that prevent
admission: the hosted resolver forces
`@latest`; hosted create, logs, and stop have no structured CLI output; and no
supported provider idempotency, bounded transport, plan-bound estimate, safe
billing-principal record, or terminal cancellation confirmation is available.
The OpenAPI and SDK/CLI disagree on status and sample-pagination shapes, so
live completeness remains unproven. Every recorded `prime eval run` command
uses `--skip-upload`; no hosted mutation or paid work was performed.

## Protected actions

The zero-cost environment-publication intent and its digest are recorded in
[`PRIME_HOSTED_CONTRACT.json`](PRIME_HOSTED_CONTRACT.json). It has not been
approved or executed. The paid hosted-run packet is blocked until Prime
supports immutable environment selection and structured mutation/readback,
and Techtree fixes the estimate, topology, and reconciliation policy.

## Consequence

WP4 must not use private endpoints or parse terminal decoration. Prime Hosted
remains in the v0.2 identity, but is not a release-admissible runner until the
upstream contract supplies those guarantees.
