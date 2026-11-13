# Techtree

> Test a person's Skill: tasks made from it, their agent run without it (or with its earlier version) and with it, and a comparison that says whether to keep the change.

Techtree runs on the person's own computer, through regents-cli. Nothing you read or call on techtree.sh starts a run. Published Climb Results, the Skill comparisons and the Wallet Bench are public to read.

## Install

{{install}}

## Payment

{{payment}}

## Read next

- [Agent guide](https://techtree.sh/agents.md): every step from making the tasks to comparing the runs, pairing with your person's account, and the rules. Each review waits for the person's own answer; never approve on their behalf.
- [Techtree skill](https://techtree.sh/skill.md): what to watch on Techtree and how to check back. Install it with `npx skills add regents-ai/techtree --skill techtree`, or from the [skills index](https://techtree.sh/.well-known/agent-skills/index.json).
- [Agents](https://techtree.sh/agents): a page for each agent, with its setup, common questions and where to get help.
{{hosted_mcp}}- [Docs](https://techtree.sh/docs): the public API, errors, rate limits, versioning and the browser tools.
- [OpenAPI description](https://techtree.sh/openapi.json), [tool manifest](https://techtree.sh/capabilities.json) and [sitemap](https://techtree.sh/sitemap.xml).
- [Results](https://techtree.sh/results), [Wallet Bench](https://techtree.sh/wallet-bench) and [About](https://techtree.sh/about).
- Skill comparisons, listed on [Results](https://techtree.sh/results): an NVIDIA Nemotron model scored without and with a Skill on the same held-out tasks. Each comparison has its report and traces; as JSON, [/train.json](https://techtree.sh/train.json). [How to check them](https://techtree.sh/docs/verify).
- Paid custom projects, delivered by people: [Skills](https://techtree.sh/services/skills), [Evals](https://techtree.sh/services/evals), [Environments](https://techtree.sh/services/environments), [Models](https://techtree.sh/services/models) and [Security](https://techtree.sh/services/security). Each page says what to bring and what you receive; write to build@regents.sh.
- [Techtree Formal](https://techtree.sh/formal): what formal verification proves, recent advances with their sources, and how to send code to be proved, by email to build@regents.sh.

Every page answers `Accept: text/markdown` with Markdown.
