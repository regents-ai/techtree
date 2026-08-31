# Domain Docs

How the engineering skills should consume this repo's domain documentation
when exploring the codebase. This is a **single-context** repo.

## Before exploring, read these

In this order — later sources yield to earlier ones:

1. **`docs/decisions/`** — this repo's architecture decision records, one
   numbered markdown file per ruling (`0001-…` through `0029-…` today).
   These are binding. Read the ones that touch the area you're about to work
   in, and note that later records can supersede earlier ones (`0003`
   supersedes parts of the WP0–WP5 spec; each record states its own status).
2. **`docs/spec/`** — the work-package specifications
   (`climb-v0.1-wp0-wp5.md` and its siblings, with `INDEX.md` as the map).
   Authoritative where no decision record overrides them.
3. **`CONTEXT.md`** at the repo root, if it exists — the domain glossary.

If any of these don't exist, **proceed silently**. Don't flag their absence;
don't suggest creating them upfront. The `/domain-modeling` skill (reached
via `/grill-with-docs` and `/improve-codebase-architecture`) creates them
lazily when terms or decisions actually get resolved.

## Where decisions get written

New decision records go in **`docs/decisions/`**, not `docs/adr/` — match
the existing convention: `NNNN-kebab-title.md`, next number in sequence, a
`# NNNN — Title` heading, and a `Status:` line stating whether the record is
binding and what it supersedes.

## File structure

```
/
├── CONTEXT.md              ← glossary (created lazily, not present yet)
├── docs/
│   ├── decisions/          ← ADRs: 0001-…, 0002-…, binding rulings
│   └── spec/               ← work-package specs + INDEX.md
└── src/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor
proposal, a hypothesis, a test name), use the term as defined in
`CONTEXT.md`, and failing that the term used in `docs/decisions/` and
`docs/spec/`. Don't drift to synonyms the project explicitly avoids.

If the concept you need isn't recorded yet, that's a signal — either you're
inventing language the project doesn't use (reconsider) or there's a real
gap (note it for `/domain-modeling`).

## Flag decision conflicts

If your output contradicts an existing decision record, surface it
explicitly rather than silently overriding:

> _Contradicts 0016 (sampling cap change) — but worth reopening because…_
