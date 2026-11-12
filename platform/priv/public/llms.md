# Techtree

> Test a person's Skill: tasks made from it, their agent run without it (or with its earlier version) and with it, and a comparison that says whether to keep the change.

Techtree runs on the person's own computer, through regents-cli. Nothing you read or call on techtree.sh starts a run. Published Climb Results, the Wallet Bench and the Train comparisons are public to read.

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
- [Train](https://techtree.sh/train): an NVIDIA Nemotron model scored without and with one change on the same held-out tasks; the first is a Skill, which teaches the answer format. Each comparison has its report and traces; as JSON, [/train.json](https://techtree.sh/train.json).
- [Techtree Verify](https://techtree.sh/services/verify) and [Techtree Cyber Assist](https://techtree.sh/services/cyber-assist): paid checks of a team's own workflows, such as an agent wallet flow, or of its security. Each page has a sample report and says what to send to build@regents.sh.
- [Techtree Formal](https://techtree.sh/formal): what formal verification proves, recent advances with their sources, and how to send code to be proved, by email to build@regents.sh.
- [Techtree Watchdog](https://techtree.sh/services/watchdog): a monthly watch on the sites a team owns, for security weaknesses, inside agreed limits. The page says what to send to build@regents.sh.

Every page answers `Accept: text/markdown` with Markdown.
