# Project Instructions for AI Agents

## Build & Test

```bash
make check            # format, lint, typecheck, tests, generated-check, v0.2 preflight
make test-integration # the integration battery
make check-plugin     # the plugin: its tests, its typecheck, its doctor
make regenerate       # rebuild every generated artifact, then re-run generated-check
```

Python is managed with `uv`; the supported interpreter range is declared in
`pyproject.toml` and nowhere else.

## Architecture Overview

Techtree Climb is the open improvement and proof network for agent systems.
v0.1 is a working technical preview of the PI-Verifiers / Hermes / Techtree stack
(decisions document 0035): the same pinned agent runs the same synthetic tasks
twice, one declared Skill changes, and a signed receipt records the difference
so it can be verified offline.

This repository is the CLI and evaluation substrate, and the hub: the campaign
kernel (a CampaignSpec is the scientific contract, a ClimbManifest its public
wrapper), the content-addressed catalog, the run lifecycle, receipts, signed
uplift reports, offline proof verification, and the terminal and compact
renderers. It also holds the decision records, the specs, the release
artifacts, and the plugin's tests and tooling.

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

## Agent guidance

### Triage labels

The five canonical roles, each label string equal to its name: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context. Binding decision records live in `docs/decisions/`, with work-package specs in `docs/spec/`. See `docs/agents/domain.md`.
