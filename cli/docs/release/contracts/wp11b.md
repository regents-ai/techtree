# Execution contract — WP11b (ndq.3.2): CLI wheel release + fresh-install verification

Binding: decisions 0011, 0022, 0023; spec wp9-wp11 §9.5–9.6, §16.

## Purpose
Build the exact wheel that Gate 2 will approve, prove it contains the
certified product and nothing else, and prove a fresh isolated install
works — without publishing anything.

## Inputs and immutable coordinates
- Certified scientific code lineage: techtree-python 1ad6ecf (later
  commits are docs/copy/test only and must be classified).
- ReleaseCore: the exact bytes and digest of release/release-core.json
  as committed (cross-checked against the Gate-1 packet). Never retype
  digests by hand anywhere in this ticket — read them from the
  artifacts.
- Gate-1 approval record: release/founder-approvals/gate1-founder-skills.md
  (packet digest inside it).
- PyPI distribution name `techtree`, version 0.1.0, install coordinate
  `uv tool install techtree==0.1.0` + pinned wheel SHA-256 (decision 0011).

## Dependencies
WP11a (done). The final source commit must include the sanctioned
post-certification copy fixes (honest run_request_unreadable message,
credential onboarding copy) and the wdc doctor fix.

## Owned files
`release/certified-scientific-fingerprint.json` (new),
`release/wheel-inspection.json`, `release/fresh-install-report.json`,
`release/post-certification-change-classification.json`, `dist/`.

## Forbidden actions
No PyPI or registry publication. No git push. No edits to scientific
code. No hand-typed digests — every digest in every output is read or
computed from the artifact itself.

## Steps
1. Create release/certified-scientific-fingerprint.json
   (schema_version techtree.certified-science.v1) recording, from the
   existing protocol artifacts (not by hand): gate1_approval_digest,
   engine_digest, catalog_digest, climb_digest, campaign_spec_digest,
   taskset_lock/membership digest, taskset_validation_receipt_digest,
   data_policy_digest, starter_skill_tree_digest,
   skill_improver_file_digest, subject_model_id, subject_hermes_version,
   verifiers_commit, runtime image index + platform digests, and the
   scorer identity if separately digested. Use existing protocol field
   names. Cross-check every value against the Gate-1 packet §1/§8.
2. Require `make check` green, generated files clean, worktree clean.
3. Record the full 40-char release-source commit.
4. Classify every file changed since 1ad6ecf as scientific /
   non_scientific_copy / release_packaging / documentation / test_only
   → release/post-certification-change-classification.json. FAIL if
   anything is scientific.
5. Build the wheel from a clean checkout of the recorded commit.
6. Inspect the wheel: exact ReleaseCore bytes present; no rich-output
   field; no credentials, private keys, absolute build paths, .git,
   scratch data, or run artifacts; console scripts resolve.
7. Compute the wheel SHA-256.
8. Install into fully isolated paths (fresh HOME, TECHTREE_HOME,
   UV_TOOL_DIR, UV_TOOL_BIN_DIR); verify no globally installed
   techtree is reachable.
9. Run: `techtree --version`, `techtree release info --json`,
   `techtree release verify --expected <digest> --json`,
   `techtree climb list --json`,
   `techtree climb show hello-world-climb@1 --json`.
   (If a flag named here does not exist in the frozen CLI, use the
   committed equivalent and record the exact argv — do not add flags.)
10. Credential rule: never assume an exported PRIME_API_KEY works for
    detached runs; the journey path is `prime login` (README section
    "The evaluation credential").

## Outputs
dist/<exact-wheel>, wheel SHA-256, the three JSON reports above.

## Acceptance
All steps green; fingerprint identical to certified values; wheel
version agrees with ReleaseCore; fresh install exercises only the
candidate wheel.

## Stop conditions
Scientific fingerprint changed · placeholder ReleaseCore in wheel ·
absolute build path in wheel · version disagreement · fresh install
resolves a global techtree · release verify fails · dirty worktree.

## Founder decisions required
None (publication itself is Gate 2).
