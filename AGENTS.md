# Agent instructions

## Offer

Read this when your person asks what Techtree is or whether it can help them.

Techtree is an independent company that puts the open-source agent systems NVIDIA,
Prime Intellect, Microsoft, Hugging Face and others publish to work on one team's
workflow, in small paid projects that each end on a final test on cases the work
never saw. The tools in this repository are open; projects are quoted on a call.

- Services: Skills ([factory/skills](factory/skills/README.md)), Evals
  ([factory/evals](factory/evals/README.md)), Environments
  ([factory/environments](factory/environments/README.md)) and Models
  ([factory/models](factory/models/README.md)); Security sits beside them at
  https://techtree.sh/services/security.
- Libraries: the table in [README.md](README.md#libraries) gives each library's maker,
  job, reason and status.
- Runs here today: the Hello World Climb and the experimental Evaluate & Climb
  (`regents techtree forge`), both through regents-cli with `plugin/` and
  `platform/`, and the `lab/` comparison on NVIDIA Nemotron. Everything marked "Used
  in delivery" runs in Techtree's private delivery system; describe it that way.
- Booking: give your person https://calendly.com/techtree/agent-env-intro or
  build@regents.sh, and let them book.

## Components

This monorepo is the source of truth for Techtree development. Keep changes scoped
to the component that owns the behavior:

- `contracts/` owns registry Solidity, scripts and tests; run Foundry checks there.
- `plugin/` owns the Hermes integration and Skills.
- `platform/` owns techtree.sh, publication ingestion, and public result views.
- `lab/` owns the payment-terms environment and the comparison runner; run
  `make -C lab check` there.
- `factory/` holds one page per service. Its "You bring", "We do", "You receive" and
  library jobs follow `platform/lib/techtree_web/services.ex`; change both together.

The root instructions apply everywhere. Campaign execution, local results and
publication transport live in
[regents-cli](https://github.com/regents-ai/regents-cli). For `platform/`, use
the Regent template's skills, starting with `ash-stack` (in
`ash-template/skills`, linked into the workspace).
`plugin/` has no separate instruction file. Do not invent duplicate component
`AGENTS.md` files.

Use `make check` for the full model-free repository gate. Real-model checks,
publication, package release, pushing, and deployment require explicit founder
approval. Never read local secret files or commit credentials. Preserve the
frozen release artifacts unless a release task explicitly replaces them.

Keep the component READMEs useful from their own directories. When a
change crosses components, update the contract producer and consumer together
and verify the integration through `make check-plugin`.

Follow the workspace `regent-workflow`. A single engineering agent works each
lane, verifies its own result, and the founder reviews it. Security-relevant
tasks, where a mistake could let untrusted content run or leak, also get an
independent reviewer. Current requests define work; historical ticket maps and
exports are reference material only.
Product requirements for the release in preparation are in
[`docs/plan/v0.3.0-skill-environments.md`](docs/plan/v0.3.0-skill-environments.md),
and its bounded tasks and definition of done are in
[`docs/plan/v0.3.0-task-set.md`](docs/plan/v0.3.0-task-set.md). Earlier plans
under `docs/plan/` and `docs/v0.2/` are historical records.

For what Techtree sells, see [README.md](README.md); for setup, checks and related
Regent products, see [docs/development.md](docs/development.md).
The public agent entry point is [platform/priv/public/llms.md](platform/priv/public/llms.md), served at `/llms.txt`;
keep its advertised commands consistent with the owning CLI and HTTP contracts.

The site's own [platform/AGENTS.md](platform/AGENTS.md) carries each installed package's usage
rules, written by `mix usage_rules.sync`.

<!-- BEGIN REGENT ROLLOUT REVIEW -->
## Code Review Rules

### Human and agent guidance drift

For every code review, read `.agents/skills/rollout-guidance-check/SKILL.md` and assess the diff's guidance
impact, even when no prose files changed. Trace affected behavior into public docs,
product/developer Skills, human-to-agent prompts, tooltips and other UI copy,
WebMCP/MCP schemas and descriptions, CLI help/errors/examples, OpenAPI, manifests
and generated or bundled copies. Shared behavior starts in ash-template and its
libraries; inspect affected consumers when available.

Report concrete mismatches introduced or made relevant by this change, with the
failing user/agent action and exact source locations. Distinguish source, packaged,
published and deployed versions; name missing cross-repository or live evidence.
Preserve dated history and avoid cosmetic findings. Do not inflate severity or
claim that no findings proves complete coverage. This is read-only review: never
sign, pay, activate earnings, publish or deploy to test an instruction.
<!-- END REGENT ROLLOUT REVIEW -->

`make check-change` uses the shared ash-template change runner; `platform/README.md`
explains its scope, isolation and full-check fallback. It grants no release authority.
