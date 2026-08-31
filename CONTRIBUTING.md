# Contributing to Techtree

Techtree is one repository with three independently buildable components. Read
the component README and any nested `AGENTS.md` before changing that component.

## Development checks

Install the toolchains required by the component you are changing, then run its
gate from the repository root:

```sh
make check-cli
make check-plugin
make check-plugin-integration
make check-platform
```

Run `make check` before opening a pull request. The full gate is model-free: it
must not start paid inference, publish a result, deploy the platform, or release
a package.

## Change boundaries

- Keep CLI and protocol behavior in `cli/`.
- Keep Hermes presentation and operator behavior in `plugin/`.
- Keep public web and publication-ingestion behavior in `platform/`.
- When a shared contract changes, update every affected component in the same
  pull request and add an integration check.
- Do not rewrite frozen v0.1 release records as part of ordinary v0.2 work.

Use focused commits and explain user-visible behavior in the pull request.
Deployment and release instructions live with the component they affect and
are run only with explicit founder approval.

## Issue tracking

This monorepo uses Beads rather than GitHub Issues. Run `bd ready` to find
unblocked work and `bd show <id>` to read its contract. Claim a ticket with
`bd update <id> --claim` before implementation. The v0.2 roadmap begins at
`techtree-31k` and is documented in
[`docs/v0.2/TICKETS.md`](docs/v0.2/TICKETS.md).
