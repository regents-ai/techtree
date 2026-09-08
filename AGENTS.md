# Techtree contributor instructions

This monorepo is the source of truth for v0.2 development. Keep changes scoped
to the component that owns the behavior:

- `cli/` owns campaign execution, local results, publication transport, and
  the plugin's automated test suite.
- `contracts/` owns registry Solidity, scripts and tests; run Foundry checks there.
- `plugin/` owns the Hermes integration and Skills.
- `platform/` owns techtree.sh, publication ingestion, and public result views.

The root instructions apply everywhere. Before editing `cli/`, also read
`cli/CLAUDE.md`; before editing `platform/`, also read `platform/AGENTS.md`.
`plugin/` has no separate instruction file. Do not invent duplicate component
`AGENTS.md` files.

Use `make check` for the full model-free repository gate. Real-model checks,
publication, package release, pushing, and deployment require explicit founder
approval. Never read local secret files or commit credentials. Preserve the
frozen v0.1 release artifacts unless a release task explicitly replaces them.

Keep the three component READMEs useful from their own directories. When a
change crosses components, update the contract producer and consumer together
and verify the integration through `make -C cli check-plugin`.

Follow the workspace `regent-workflow`: Hermes/Astra coordinates Claude/Fable
assignments and verifies the integrated result. Current requests define work;
historical ticket maps and exports are reference material only. Product requirements
remain in `docs/plan/v0.2.md` and `docs/plan/techtree-market.md`.

For product orientation and related Regent products, see [README.md](README.md).
The public agent entry point is [platform/priv/static/llms.txt](platform/priv/static/llms.txt);
keep its advertised commands consistent with the owning CLI and HTTP contracts.
