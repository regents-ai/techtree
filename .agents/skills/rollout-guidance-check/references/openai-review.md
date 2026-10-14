# OpenAI code review integration

The root `AGENTS.md` Code Review Rules section instructs Codex to read this Skill
for each code review and assess the changed behavior's guidance impact. Review code
changes even when no documentation file changed. Read-only review never authorizes
executing a copied command that signs, pays, publishes, deploys or changes production.

## Portable source

The authored Skill lives in `regents-ai/ash-template`, under
`skills/rollout-guidance-check/`. Other repositories carry generated, byte-identical
review packages under `.agents/skills/rollout-guidance-check/` (VideoControl uses
`review/rollout-guidance-check/` because its `.agents/` is private local configuration).
Their `SOURCE.json` records the source identity and each packaged file's hash. Edit
the canonical source and sync packages; do not independently edit generated copies.
Ash-template reads its canonical Skill directly and needs no duplicate package.

From the canonical Skill directory, maintain a consumer with:

```sh
python3 scripts/sync_review.py --repo /absolute/consumer
python3 scripts/sync_review.py --repo /absolute/consumer --check
```

Repeat `--repo` for multiple consumers. This changes only the named review package and
the marked review-rules block in the root AGENTS.md. It preserves other instructions,
refuses symlinks and independently edited packages, and never commits or pushes.
Review and publish these files through each repository's normal authorized process.

## Scope and findings

Use the base/target revisions supplied by the PR. Follow affected callers, renderers,
descriptors, generators and dependency consumers; use the surface map as a guide,
not a guarantee that sibling repositories are available. A source-only reviewer can
identify a release dependency but cannot prove production adoption.
In a standalone checkout, map this repository's `repos/<name>/` (or
`services/<name>/`) prefixes in the surface map to the checkout root. Other prefixes
name cross-repository dependencies; their absence is a coverage limit, not a broken
local file reference.

Report incorrect instructions that cause a concrete failure: an unusable command,
wrong required input, false availability/authority claim, unsafe payment recovery,
misleading price or Points allowance, or a missing matching generated contract.
Explain the changed behavior and the affected consumer, with precise source locations.
Do not demand edits for unrelated surfaces, cosmetic preferences or dated history.
Never inflate severity to get past a hosting threshold. If the host only exposes
high-priority findings, silence does not certify that lower-priority drift is absent.

When the review format permits, include coverage and unavailable evidence. If the
host restricts output to findings, do not fabricate a finding just to force a coverage
message; record that limitation in the rollout acceptance record.

## Hosted activation and proof

OpenAI documents repository rules in AGENTS.md and separate automatic-review controls:
[GitHub integration](https://learn.chatgpt.com/docs/third-party/github).

- Instructions and the package must reach GitHub before cloud review can read them.
- In Code Review settings, enable the repository, choose All PRs and On every push.
  This covers new pushes to pull requests, not direct commits without a PR or unsaved
  local edits. Keep unrelated personal preferences, security-review settings and
  paid-credit settings unchanged.
- A local-only repository without a remote cannot receive GitHub PR reviews.
- Verify with an authorized representative PR and retain its exact head and review
  result. A saved switch, valid package or local evaluation is setup evidence, not
  proof the hosted reviewer applied these rules.

Automatic review is an additional reviewer, not a deterministic merge gate or proof
that every live instruction has been exercised. No API-key workflow, hourly scheduler,
or second operation registry is needed for this integration.
