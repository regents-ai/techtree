# 0027 — Stable release channel and approved implementation plan

Status: binding founder ruling, 2026-08-18.

This decision records the founder's exact authorization for the final
Climb v0.1 implementation sequence. It supplements decisions 0022–0026
and resolves the release-channel sub-decision in WP11h.

## 1. Release channel

The Climb v0.1 release channel is `stable`.

`development` remains a development channel and is not silently
renamed. The final inactive BootstrapRelease candidate is regenerated
for `stable` after the Python and Hermes release-truth changes have
landed and their final commits exist.

## 2. Rollback floor

The `stable` channel uses a deliberately non-installable placeholder
release as its rollback floor. Rollback is a pointer move to those
exact staged bytes, not a pointer-to-nothing state and not a rebuild.

The placeholder must identify itself as a placeholder, pass the
placeholder-specific verifier rules, expose no usable release
coordinates, remain staged when the real release is activated, and be
named by exact digest in the Gate-2 runbook and packet.

## 3. Sequence and artifact freeze

The sequence is binding:

1. Land the non-scientific Python documentation/contract/test pass.
2. Land the non-scientific Hermes documentation/test pass.
3. Rebuild the wheel from a clean Git checkout at the final Python
   commit; do not build from an export and do not weaken the decision
   0026 provenance hook.
4. Regenerate the inactive `stable` BootstrapRelease and stable
   placeholder floor with the final wheel hash, Python source commit,
   and Hermes plugin commit.
5. Run the canonical pinning checklist and require
   `tools/verify_release_core.py --bootstrap ... --wheel ...` to pass
   all 25 checks.
6. Freeze those candidate bytes before WP11e, WP11f, or the dynamic
   WP11g evidence is collected.

Any merge to a release repository after the freeze makes every
affected pinned coordinate stale and requires the pinning cycle and
downstream acceptance evidence to be repeated.

## 4. Paid authorization and division of labor

Decision 0025's USD 10.00 programme cap remains standing. The ledger
was approximately USD 2.50 spent at authorization. Every paid leg
requires an estimate first, a USD 0.30 ceiling per comparison, a USD
0.30 ceiling per host-model call, and no retry of a paid outcome.

The chief session on the founder's Mac executes WP11e, WP11f, and the
dynamic part of WP11g because that machine holds Prime login, Docker,
Hermes 0.20.1, the durable budget ledger, and the local-only evidence
store. Repository PRs may commit only scrubbed summaries and digests.
They never commit live run directories, hidden task answers, raw
Episodes or Traces, credentials, provider responses, or the durable
certification-evidence store.

## 5. Repository and publication controls

Implementation is limited to:

- `regents-ai/techtree-python`
- `regents-ai/techtree-hermes`
- `regents-ai/techtree-ash`

All implementation pull requests are drafts. Nothing is merged,
published, deployed, tagged, or activated without a separate founder
instruction. Gate 2 still requires the exact final release approval
phrase and packet digests; this implementation-plan approval is not
release approval.

The founder also directed that `main` be branch-protected in all three
repositories. That repository-administration action is independent of
release artifact bytes and must be verified from GitHub settings.

## 6. Founder authorization

The founder authorized, verbatim:

> APPROVE IMPLEMENTATION PLAN — channel stable; use a stable-channel
> placeholder release as the rollback floor; use the standing
> decision-0025 paid-run authorization with estimate-first, USD 0.30
> per comparison, USD 0.30 per host call, and no paid retries; the
> chief will execute WP11e, WP11f, and WP11g-dynamic on the founder’s
> Mac; enable a writable workspace limited to
> regents-ai/techtree-python, regents-ai/techtree-hermes, and
> regents-ai/techtree-ash; open draft PRs only, with no merge,
> publication, deployment, tagging, or activation without separate
> founder instruction.
