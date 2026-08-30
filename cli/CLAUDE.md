# Project Instructions for AI Agents

This file provides instructions and context for AI coding agents working on this project.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:6cd5cc61 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->


## Build & Test

```bash
make check            # format, lint, typecheck, unit + contract tests, generated-check
make test-integration # the integration battery
make check-plugin     # the sibling plugin: its tests, its typecheck, its doctor
make regenerate       # rebuild every generated artifact, then re-run generated-check
```

Python is managed with `uv`; the supported interpreter range is declared in
`pyproject.toml` and nowhere else.

## Architecture Overview

Techtree Climb is the open improvement and proof network for agent systems.
v0.1 is a proof of concept for the PI-Verifiers / Hermes / Techtree stack
(decisions document 0035): the same pinned agent runs the same synthetic tasks
twice, one declared Skill changes, and a signed receipt records the difference
so it can be verified offline.

This repository is the CLI and evaluation substrate, and the hub: the campaign
kernel (a CampaignSpec is the scientific contract, a ClimbManifest its public
wrapper), the content-addressed catalog, the run lifecycle, receipts, signed
uplift reports, offline proof verification, and the terminal and compact
renderers. It also holds the decision records, the specs, the release
artifacts, and the sibling plugin's tests and tooling.

`docs/product-architecture.md` is the long form.

## Conventions & Patterns

- `docs/decisions/` is binding. When a document here and a decision disagree,
  the decision wins.
- Evidence is append-only: a completed run's files are never modified, and
  stored bytes are never rewritten to be more convenient.
- Hard cutover: no fallbacks, no compatibility branches, no shims, no aliases,
  no dual-shape support. Delete old handling rather than police it.
- Customer-facing text is plain language, and every claim surface is guarded by
  a test. The guards encode rulings, not style.

## Agent skills

### Issue tracker

Issues live in beads (`bd`) — a local Dolt database at `.beads/`, IDs prefixed `techtree-python-`. GitHub Issues are not used. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical roles, each label string equal to its name: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context. Binding decision records live in `docs/decisions/` (not `docs/adr/`), with work-package specs in `docs/spec/`. See `docs/agents/domain.md`.
