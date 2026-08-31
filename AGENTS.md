# Techtree contributor instructions

This monorepo is the source of truth for v0.2 development. Keep changes scoped
to the component that owns the behavior:

- `cli/` owns campaign execution, local results, publication transport, and
  the plugin's automated test suite.
- `plugin/` owns the Hermes integration and Skills.
- `platform/` owns techtree.sh, publication ingestion, and public result views.

Read and follow a component's nested `AGENTS.md` before editing beneath it.
The root instructions apply everywhere; nested instructions add component
rules.

Use `make check` for the full model-free repository gate. Real-model checks,
publication, package release, pushing, and deployment require explicit founder
approval. Never read local secret files or commit credentials. Preserve the
frozen v0.1 release artifacts unless a release task explicitly replaces them.

Keep the three component READMEs useful from their own directories. When a
change crosses components, update the contract producer and consumer together
and verify the integration through `make -C cli check-plugin`.

Track work in the monorepo's Beads database with `bd`. Use `bd ready` for
unblocked work and `bd show <id>` before implementation. Claim the ticket with
`bd update <id> --claim` before changing code. The v0.2 epic is
`techtree-31k`; its binding plan and ticket mapping are in
`docs/plan/v0.2.md` and `docs/v0.2/TICKETS.md`. Export the tracker to
`.beads/issues.jsonl` after changing tickets so collaborators can reconstruct
the current issue set.
