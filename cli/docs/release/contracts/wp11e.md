# Execution contract — WP11e (ndq.3.5): clean-machine terminal E2E + failure injection

Binding: decisions 0022, 0023, 0025, 0027; spec wp9-wp11 §9.8,
§9.10–9.11.
Blocked by: WP11b, WP11c, wdc (doctor credential truthfulness), and the
final pre-acceptance artifact freeze.

## Purpose
Prove a clean user's complete terminal journey — install through two
verified comparisons — on the exact candidate artifacts, and prove
every likely failure lands on a typed error with a working repair.

## "Clean machine", defined honestly
Fresh HOME, TECHTREE_HOME, HERMES_HOME, UV_TOOL_DIR, UV_TOOL_BIN_DIR;
no globally importable techtree; clean plugin install; separate
managed-engine installation. Use a pinned Python 3.12 interpreter as
the primary supported path. Record whether Docker images were already
cached. This is fresh homes on the founder's existing Mac, not a fresh
OS — say so in the report.

## Pre-Gate-2 vs post-Gate-2
This ticket installs the exact LOCAL candidate wheel and the exact
LOCAL plugin commit. It certifies the artifacts, not the public
distribution path — never claim otherwise. The public-coordinate smoke
is WP11-postpublish, after Gate 2.

## The journey (live, paid)
1. Hermes/plugin readiness. 2. CLI absent/isolated. 3. Explicit CLI
install approval. 4. `prime login`. 5. Docker/engine doctor
(now truthful about credentials, per wdc). 6. Hello World prepare.
7. Review shows: episodes, the Campaign's declared spend limit, same
agent/tasks, Skill-only change, provider disclosure, and
no-Techtree-upload. 8. Explicit approval. 9. Start → run ID. 10. CLOSE
the initiating terminal/session. 11. Poll from a new process.
12. Deterministic result. 13. Verify local proof. 14. Request one
guided revision. 15. Confirm exactly one model request. 16. Review the
exact Skill diff and second declared budget. 17. Explicit approval.
18. v1-vs-v2 run. 19. Verify second proof. 20. Confirm no artifact
upload.

## Paid authorization and ledger
Decision 0025 authorizes a USD 10.00 programme cap; USD 2.4957 was
spent before this closeout plan was approved. Before every paid leg,
estimate it and confirm the durable ledger has enough remaining.
Apply the standing hard stops: USD 0.30 per comparison, USD 0.30 per
host-model call, and no retry of any paid outcome. STOP on a shortfall
or hard-stop violation and request a new explicit founder ruling.
Never silently substitute fixtures for the live journey.

## Failure-injection matrix — no paid inference
uv absent · docker executable absent · docker daemon stopped · engine
absent · stale engine .installing marker · Prime auth absent · starter
URL unavailable · starter digest mismatch · ReleaseCore mismatch ·
plugin/CLI version mismatch · unwritable techtree home · tampered
proof bundle.

## Failure-injection matrix — paid/provider-path
network fails after run start · provider auth fails · worker process
killed · terminal disconnects · one required episode incomplete ·
declared spend limit reached.

For every case: stable typed error code · honest message · working
repair action · no partial valid UpliftReport · no secret leakage.

The `python:3.11-slim` tag moved off the pinned image index. Assert the
digest-pull path explicitly. Also record the observed behavior of an
unsupported Python interpreter without treating it as the certified
journey.

## Outputs
release/acceptance/terminal-e2e.json · terminal-e2e.md · scrubbed
transcript · run IDs · proof digests · actual cost · failure-matrix
results.

Live run directories, hidden task answers, raw Episodes, Traces,
provider responses, credentials, and the durable certification store
remain outside every repository.

## Stop conditions
Estimate exceeds the authorized ledger · any USD 0.30 hard stop would
be crossed · any paid outcome would be retried · any failure case
without a typed error and working repair · any upload observed · any
claim that this certifies the public install path.
