# Execution contract — WP11e (ndq.3.5): clean-machine terminal E2E + failure injection

Binding: decisions 0022, 0023; spec wp9-wp11 §9.8, §9.10–9.11.
Blocked by: WP11b, WP11c, wdc (doctor credential truthfulness).

## Purpose
Prove a clean user's complete terminal journey — install through two
verified comparisons — on the exact candidate artifacts, and prove
every likely failure lands on a typed error with a working repair.

## "Clean machine", defined honestly
Fresh HOME, TECHTREE_HOME, HERMES_HOME, UV_TOOL_DIR, UV_TOOL_BIN_DIR;
no globally importable techtree; clean plugin install; separate
managed-engine installation. Record whether Docker images were already
cached. This is fresh homes on the existing machine, not a fresh OS —
say so in the report.

## Pre-Gate-2 vs post-Gate-2
This ticket installs the exact LOCAL candidate wheel and the exact
LOCAL plugin commit. It certifies the artifacts, not the public
distribution path — never claim otherwise. The public-coordinate smoke
is WP11-postpublish, after Gate 2.

## The journey (live, paid)
1. Hermes/plugin readiness. 2. CLI absent/isolated. 3. Explicit CLI
install approval. 4. `prime login`. 5. Docker/engine doctor
(now truthful about credentials, per wdc). 6. Hello World prepare.
7. Review shows: episodes, cost ceiling, same agent/tasks, Skill-only
change, provider disclosure, no-Techtree-upload. 8. Explicit approval.
9. Start → run ID. 10. CLOSE the initiating terminal/session.
11. Poll from a new process. 12. Deterministic result. 13. Verify
local proof. 14. Request one guided revision. 15. Confirm exactly one
model request. 16. Review exact Skill diff and second budget.
17. Explicit approval. 18. v1-vs-v2 run. 19. Verify second proof.
20. Confirm no artifact upload.

Budget: estimate before running; the founder pool remainder (~1.03 of
the 3.00 programme cap at contract time) must cover the estimate, or
STOP and request a new explicit budget authorization. Never silently
substitute fixtures for the live journey.

## Failure-injection matrix — no paid inference
uv absent · docker executable absent · docker daemon stopped · engine
absent · stale engine .installing marker · Prime auth absent · starter
URL unavailable · starter digest mismatch · ReleaseCore mismatch ·
plugin/CLI version mismatch · unwritable techtree home · tampered
proof bundle.

## Failure-injection matrix — paid/provider-path
network fails after run start · provider auth fails · worker process
killed · terminal disconnects · one required episode incomplete · cost
ceiling reached.

For every case: stable typed error code · honest message · working
repair action · no partial valid UpliftReport · no secret leakage.

Note from prior session: python:3.11-slim's tag has moved off the
pinned digest — assert the digest-pull path explicitly.

## Outputs
release/acceptance/terminal-e2e.json · terminal-e2e.md · scrubbed
transcript · run IDs · proof digests · actual cost · failure-matrix
results.

## Stop conditions
Estimate exceeds remaining authorized budget · any failure case
without a typed error + working repair · any upload observed · any
claim that this certifies the public install path.
