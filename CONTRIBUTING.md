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
- Do not rewrite frozen release records as part of ordinary development.

Use focused commits and explain user-visible behavior in the pull request.
Deployment and release instructions live with the component they affect and
are run only with explicit founder approval.

## Work coordination

Use the founder's current task and the workspace `regent-workflow`. A single
engineering agent works each lane and verifies its own result; the founder
reviews it. Security-relevant tasks, where a mistake could let untrusted
content run or leak, also get an independent reviewer. The current plan is
[`docs/plan/v0.3.0-skill-environments.md`](docs/plan/v0.3.0-skill-environments.md)
with its [task set](docs/plan/v0.3.0-task-set.md). Historical ticket maps remain
available as context; no tracker command is required.
