# Execution contract — WP11c (ndq.3.3): plugin exact-commit release + bootstrap wrapper

Binding: decisions 0011, 0022, 0023; spec wp9-wp11 §9.3–9.4, §16.

## Purpose
Freeze the exact plugin commit Gate 2 will approve, prove it carries
the certified ReleaseCore and founder Skill, and produce the
release-candidate record — without pushing, tagging, or creating any
public repository.

## Inputs and immutable coordinates
- Plugin release source: techtree-plugin at 1ce5d4e12910d569a5d968eaac1742a0ed0cb40f
  (re-freeze v3), or a later commit containing only classified
  non-scientific changes.
- Exact ReleaseCore bytes (byte-identical to techtree-python's).
- Exact CLI version and local wheel SHA-256 from WP11b.
- Repository coordinate: github.com/regents-ai/techtree-hermes.
- skill-improver file digest per ReleaseCore.

## Dependencies
WP11b (wheel digest is an input to the candidate record).

## Owned files
Plugin repo (no push); release-candidate record JSON (committed in
techtree-python under release/).

## Forbidden actions
No push, no tag, no public repo creation before Gate-2 approval. No
BootstrapRelease digest embedded in the plugin — CYCLE RULE: the
BootstrapRelease contains the plugin commit, so the plugin cannot
contain the BootstrapRelease digest.

## Steps
1. Require the plugin worktree clean at the candidate commit.
2. Verify plugin release-core.json is byte-identical to
   techtree-python's (compare digests computed fresh from both files).
3. Verify skills/skill-improver/SKILL.md bytes hash to the ReleaseCore
   skill_improver_digest.
4. Verify no rich-terminal-output Skill is packaged or registered.
5. Verify registration performs no install, network request, Docker
   call, or model call (existing conformance tests; run them).
6. Run the plugin doctor in a throwaway HERMES_HOME.
7. Install the plugin from the LOCAL repository at the exact candidate
   commit; verify the full 40-character commit is what got installed.
8. Produce the release-candidate record:
   {"repository": "github.com/regents-ai/techtree-hermes",
    "commit": "<40-char>", "version": "0.1.0",
    "release_core_digest": "sha256:<from file>",
    "plugin_doctor": "passed"}
9. Bootstrap install argv (already pinned):
   `hermes plugins install <repo> --ref <40-char commit> --enable`.

## Outputs
Release-candidate record; doctor transcript; verification evidence.

## Acceptance
All verifications pass; the candidate commit is recorded in full; the
record's digests are read from artifacts, not typed.

## Stop conditions
Short commit anywhere · dirty plugin tree · ReleaseCore mismatch ·
install performs side effects · plugin doctor failure · the plugin
commit changes after the candidate record is produced (regenerate the
record or stop).

## Founder decisions required
None here (push/tag is Gate 2).
