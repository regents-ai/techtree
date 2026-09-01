# Prime Hosted contract spike

Status: captured with release blockers, and the conformance environment is
published. Candidate: `prime==0.6.31`, with `prime-evals==0.2.3`; admission
remains blocked. Founder decision of 2026-09-01: Prime Hosted moves to
`v0.2.x`, and the hosted gap recorded here is inadmissible for `v0.2.0`.

The evidence index in
[`cli/tests/fixtures/prime/evidence_manifest.json`](../../cli/tests/fixtures/prime/evidence_manifest.json)
binds the exact official CLI wheel and source archive, the exact public SDK
wheel, plain CLI help, the exact 295,750-byte public v1 OpenAPI document, a
bounded projection of that document, and the sanitized read-only responses
observed on 2026-09-01. The shape record is
[`official_cli_0_6_31.json`](../../cli/tests/fixtures/prime/official_cli_0_6_31.json).
The index records artifact digests, source line ranges, excerpt digests, the
full OpenAPI digest, and each retained response with its exact command; it
contains no account data, credentials, or hosted run output.

## What the responses prove

Four machine reads are now observed and admitted as read shapes: the
environment listing, the environment status read, the environment action
listing, and the evaluation listing. Their envelopes and their limits are
recorded in `supported_machine_reads` in
[`PRIME_HOSTED_CONTRACT.json`](PRIME_HOSTED_CONTRACT.json). The limits matter
as much as the shapes. The evaluation listing was observed only as an empty
collection, so no evaluation record shape is admitted. The environment status
read returns provider-internal identifiers, which are replaced by documented
placeholders in the retained fixture and are persisted nowhere. Reading an
exact environment version was observed only as human text, so it is recorded as
a human-output observation and not as a machine read.

The observed list envelopes also disagree with each other: environments
paginate with `page` and `per_page`, evaluations with `skip` and `limit`, and
environment actions with `limit` and `offset`. Three shapes in one CLI widens
rather than closes the pagination question.

Everything else stays unobserved. Evaluation get, samples, hosted logs, hosted
stop, and hosted create produced no response in this capture, and the retained
evidence for them remains source and help shape only.

## What is still blocked

The recorded limits that prevent admission are unchanged by the capture, which
proves read shapes and not upstream guarantees. The hosted resolver forces
`@latest`; hosted create, logs, and stop have no structured CLI output; and no
supported provider idempotency, bounded transport, plan-bound estimate, safe
billing-principal record, or terminal cancellation confirmation is available.
The OpenAPI and SDK/CLI disagree on status and sample-pagination shapes, so
live completeness remains unproven. Every recorded `prime eval run` command
uses `--skip-upload`; no hosted evaluation was created, read, cancelled, or
paid for.

The publication added one further blocker, and the read-only diagnostics named
its cause. Prime's hub runs an Integration Test action on every push. For the
published `0.1.0` version it collected four checks: pyproject present, README
present, and install-and-import all passed, and the metadata check failed with
`pyproject.toml does not have tags`. The hub requires a `tags` list under
`[project]`, which is not a PEP 621 field. The published version is therefore
installable and importable but not hub-validated.

Satisfying that check means adding the non-standard `tags` key and publishing a
new semantic version, which changes the source tree and wheel digests. That is
a new protected publication and needs its own founder approval, so it is
recorded as a required action rather than taken. The committed environment
source tree still matches the tree that produced the published `0.1.0`, and no
`tags` key has been added to it.

## Protected actions

The zero-cost environment-publication packet was approved by the founder and
executed once on 2026-09-01 with `prime==0.6.31`, from the exact committed
source tree. A fresh deterministic build produced the same
4,413-byte `techtree_v02_conformance-0.1.0-py3-none-any.whl` as the approved
packet, and the CLI reported that same digest for the uploaded wheel; it also
uploaded a small source archive of the same tree. The result is
`techtree/techtree-v02-conformance` at semantic version `0.1.0`, public. No
evaluation, paid run, or model call occurred, and the cost was zero. The
execution record, including the provider identifiers deliberately left null, is
in [`PRIME_HOSTED_CONTRACT.json`](PRIME_HOSTED_CONTRACT.json) and
[`PRIME_CONFORMANCE_ENVIRONMENT.json`](PRIME_CONFORMANCE_ENVIRONMENT.json).

Republishing the environment with the hub's `tags` key is recorded there as a
required protected action. It has not been prepared or requested.

The paid hosted-run packet remains blocked until Prime supports immutable
environment selection and structured mutation and readback, and Techtree fixes
the estimate, topology, and reconciliation policy.

## Consequence

WP4 must not use private endpoints or parse terminal decoration. Prime Hosted
remains in the v0.2 identity, but is not a release-admissible runner until the
upstream contract supplies those guarantees.
