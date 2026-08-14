# Execution contract — wdc: Doctor credential truthfulness (PROMOTED to v0.1)

Binding: decisions 0022, 0023. Blocks WP11e.

## Purpose
`techtree doctor --for-evaluation` must never report credential
readiness that a detached run cannot use. Today an exported
PRIME_API_KEY makes the check PASS while every real run fails
(doctor/execution_checks.py runs credential_status in the doctor's own
shell). A readiness command that lies is a release bug.

## Required behavior
Credential readiness uses the SAME resolution the detached evaluation
worker uses (an active Prime CLI configuration readable via inherited
HOME — see verifiers/credentials.py and runs/launcher.py).

| State | Doctor result |
|---|---|
| prime login valid | ready |
| only an exported PRIME_API_KEY (worker cannot inherit it) | not ready |
| both present | ready (through the Prime login) |
| neither present | not ready |
| expired/invalid Prime login | not ready |
| malformed credential store | typed failure |

- No credential value ever appears in output.
- Repair action: run `prime login`, then rerun doctor.
- Do NOT make the worker inherit host environment variables to
  preserve old doctor behavior — the scrubbed environment is correct.
- When an exported variable is present but unusable, the doctor output
  may say so plainly (it is the most likely user confusion).

## Classification (Gate-2 packet)
Non-scientific onboarding behavior change, landed after certification:
outside the certified scientific surface (runs, approvals, proposals,
receipts, proof, host requests, Skill mounting, guards, Campaign
config). Requires the full 0022 acceptance battery and appears in the
post-certification change classification.

## Owned files
src/techtree/doctor/execution_checks.py (and the credential-status
plumbing it calls), tests for every table row above. README's
"evaluation credential" section already warns about the old behavior —
update it to match the fixed behavior (drop the distrust warning once
the check is truthful).

## Acceptance
All six table rows covered by tests · full `make check` +
integration green · scientific fingerprint unchanged · no secret in
any output.

## Stop conditions
Any design that loosens the worker environment scrubbing · any check
that "passes" via a code path a real run cannot take.
