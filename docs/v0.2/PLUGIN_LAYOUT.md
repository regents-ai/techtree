# Techtree v0.2 plugin layout

Status: binding target layout for v0.2 (WP0.6 decision)
Authority: [`docs/plan/v0.2.md`](../plan/v0.2.md), section "Operator contract";
founder answers in [`DECISION_LEDGER.md`](DECISION_LEDGER.md)

This document records where the Hermes and Codex host integrations will live
and what they may own. It moves nothing. `plugin/` is unchanged by WP0, no
`plugin/hermes/` or `plugin/codex/` directory is created here, and no shared
runtime package is added — a future module tree is not created before its first
executable caller exists.

## Today

`plugin/` is one Hermes plugin, at the repository root:

```text
plugin/
├── plugin.yaml           the Hermes manifest: name techtree, 17 tools, 2 hooks
├── release-core.json     the release bytes it must agree with the CLI about
├── pyproject.toml
├── uv.lock
├── Makefile
├── LICENSE
├── README.md
├── cli/                  the bridge: the one way into the Techtree CLI
├── host/                 the Hermes-facing surface: commands, channels, hooks
├── services/             presentation, approvals, proposals, session state
├── skills/               operator and skill-improver
├── tools/                the tool handlers the manifest names
└── docs/assets/
```

Its tests, typecheck, and doctor live in the CLI project — `cli/tests/plugin`
and `cli/tools/plugin`, reached by `make -C cli check-plugin` — because the
contract tests that talk to a real CLI use the CLI this plugin is pinned to.

## Target

Two sibling host packages under a `plugin/` workspace:

```text
plugin/
├── hermes/               exactly today's plugin/ contents, moved unchanged
│   ├── plugin.yaml       name techtree; identity, commands, and version line
│   ├── release-core.json
│   ├── cli/              its own bridge to the techtree CLI
│   ├── host/
│   ├── services/
│   ├── skills/
│   └── tools/
└── codex/                the Codex operator, new in WP6
    ├── <manifest>        shape decided by the Codex contract spike
    ├── release-core.json
    ├── cli/              its own bridge to the techtree CLI
    ├── host/
    ├── services/
    ├── skills/
    └── tools/
```

Each package is self-contained: its own manifest, its own bridge, its own
release-core bytes, its own host surface, and its own Skills. Neither imports
the other.

## The boundary

`cli/` remains the sole owner of scientific state, durable execution state,
receipts, approvals, and publication behavior. A host package owns none of it.

Specifically, a host package **must not**:

- keep or derive scientific state — no Campaign, draft, receipt, report, or
  proof is authored, cached, or reinterpreted in `plugin/`;
- schedule anything — no queue, no retry loop, no background worker, no timer,
  no busy-polling; a run is a detached worker the CLI launches;
- author or store approvals — it presents what the CLI says a person must
  approve and reports the answer back through `--yes` and `--reviewed-on`;
- author receipts or decide publication eligibility;
- reach the network itself, or start a container itself; and
- read, copy, or forward a reusable credential.

What a host package **does** own is the host's own surface: registering its
tools with its host, rendering the CLI's answers in that host's idiom, and
carrying its host's approval interaction. Everything scientific it can cause
happens by running the pinned `techtree` command with a fixed argument array,
no shell, and a named environment allowlist.

## No shared plugin runtime SDK

The two packages will hold near-identical bridge code. That duplication is
deliberate and is not to be factored out in v0.2.

A shared runtime package would become a third thing to version, and the one
thing every host integration must not do is acquire behavior of its own between
the host and the CLI. Two thin, separately readable bridges, each auditable by
reading one directory, are worth more than one clever shared one — and an
install-time scanner reading a host package should see only what that package
does.

The single source of truth both bridges follow is the CLI machine contract in
[`MACHINE_CONTRACT.md`](MACHINE_CONTRACT.md), not a shared library.

## Hermes compatibility

The existing Hermes plugin identity, commands, installation, update path,
scanner expectations, and public documentation remain compatible. The move to
`plugin/hermes/` is a repository path change, not a plugin change: the manifest
name stays `techtree`, its tool names are unchanged, and the release-core bytes
it shares with the CLI are unchanged.

Anything reading the plugin by path moves with it — `cli/tests/plugin`,
`cli/tools/plugin`, the `make -C cli check-plugin` targets, and the frozen
sibling-repository layout those targets already understand. That path update is
part of the move, in WP6, and is not a compatibility shim.

## Migration

WP0 records this map. Nothing else.

- **WP6** moves `plugin/` to `plugin/hermes/` and adds `plugin/codex/`, and
  migrates both consumers directly to `techtree.cli.v2`. There is no
  compatibility adapter and no dual-mode period: Hermes and Codex move in the
  same change as the producers.
- The Codex package's manifest shape, tool registration, and approval surface
  are determined by the Codex Fabric and operator contract spike in WP6. This
  document deliberately does not invent them.
- An empty package is forbidden. `plugin/codex/` is created when it has a
  working operator, not before.

## Open questions for the founder

1. **The Codex manifest format is unresolved.** WP6's spike decides it. The
   layout above assumes it needs the same five directories the Hermes package
   uses; if it does not, the directories it does not need are not created.
2. **Where the shared Skills live is unresolved.** `skills/operator` and
   `skills/skill-improver` are written against the CLI's behavior rather than
   against Hermes, so a Codex operator would want the same content. Copying
   them into both packages is assumed here, consistent with the no-shared-SDK
   decision; a single reviewed source with a build-time copy is the alternative
   and would need its own decision.
