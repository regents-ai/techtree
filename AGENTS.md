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
