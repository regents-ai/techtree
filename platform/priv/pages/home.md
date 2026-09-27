# Techtree

Improve a Skill. Prove it worked.

Same agent. Same tasks. One Skill upgraded. Built on [Prime Intellect's Verifiers](https://github.com/PrimeIntellect-ai/verifiers) and [Nous Research's Hermes](https://github.com/NousResearch/hermes-agent).

## Test your Skill (experimental)

Techtree makes practice tasks from what your Skill teaches. Your agent then works the same tasks twice: once without the Skill, or with its earlier version, and once with it. The model, the tools and the limits stay the same, so any difference comes from the Skill.

1. Tasks made from your Skill. You review the plan and keep the tasks that work.
2. Run twice: without the Skill or its earlier version, then with it.
3. Decide. Techtree says whether the Skill improved, regressed, was mixed or made no difference. Some tasks are held out from anyone improving the Skill; their result is the one to trust, because no revision could have studied them.

[See a real comparison](/examples/tdd).

## A quick look

The Hello World Climb ships with every release: a small, fixed set of tasks run once without a starter Skill and once with it. It shows how a run is approved, what it records and what a Result looks like. Its toy tasks say nothing about your own Skill.

Techtree is a working technical preview built from three independent parts: Prime Intellect's Verifiers scores the tasks, Nous Research's Hermes runs the agent, and Techtree runs the comparison and keeps the evidence. Every finished Climb ends in a signed Result that anyone can check offline.

## When to use it

- To decide whether a change to a Skill is worth keeping.
- To compare your agent with and without a Skill on tasks made from it.
- To build repair tasks from a repository's own history (experimental).
- To check someone else's published Result offline, without trusting this site.

It is not a general benchmark of a model's broad capability, and it does not run your agent for you in the cloud.

## How to start

- [Start](/start): test your Skill, take a quick look with the example Climb, or build tasks from your repository.
- [Agent installation guide](/skill.md): the exact release to install and every step for your agent to follow, from making the tasks to comparing the runs. Each review waits for the person's own answer.
- [Docs](/docs): install, test a Skill, verify, publish and integrate.

## Your work stays local

Techtree doesn't watch your runs. Your work stays local unless you choose to publish a finished Climb Result. Model calls go to the model provider you run with, under that provider's policies.

## Pages

- [Results](/results): published Results, newest first. Only Climb runs can be published today.
- [Verify](/verify): what verification establishes, and how to check a Result offline.
- [Changelog](/changelog): what changed in each release.
- [Repo2RLEnv](/repo2rlenv): the planned hosted service for building tasks from a repository.
- [Blog](/blog)
- [About](/about), [Contact](/contact) and [Privacy](/privacy)

## For agents and programs

- [/skill.md](/skill.md): the installation guide for an agent.
- [/llms.txt](/llms.txt): when to use Techtree and where everything is.
- [/openapi.json](/openapi.json): every public API address, typed.
- [/sitemap.xml](/sitemap.xml): every public page.
