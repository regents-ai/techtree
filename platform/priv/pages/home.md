# Techtree

Improve a Skill. Prove it worked.

Same agent. Same tasks. One Skill upgraded. Built on [Prime Intellect's Verifiers](https://github.com/PrimeIntellect-ai/verifiers) and [Nous Research's Hermes](https://github.com/NousResearch/hermes-agent).

## What Techtree is

Your agent works the same fixed tasks twice: once without the Skill and once with it. The model, the tools and the limits stay the same, so any difference in the results comes from the Skill. Techtree calls this a Climb.

Techtree is a working technical preview built from three independent parts: Prime Intellect's Verifiers scores the tasks, Nous Research's Hermes runs the agent, and Techtree runs the comparison and keeps the evidence. Every finished comparison ends in a signed Result that anyone can check offline.

## When to use it

- To decide whether a change to a Skill is worth keeping.
- To compare your agent with and without a Skill on the same fixed tasks.
- To make test tasks from a Skill (experimental).
- To build repair tasks from a repository's own history (experimental).
- To check someone else's published Result offline, without trusting this site.

It is not a general benchmark of a model's broad capability, and it does not run your agent for you in the cloud.

## How to start

- [Start](/start): try the example Climb, evaluate your own Skill, or build tasks from your repository.
- [Agent installation guide](/skill.md): the exact release to install and the steps for your agent to follow. Each review waits for the person's own answer.
- [Docs](/docs): install, run, verify, publish and integrate.

## Your work stays local

Techtree doesn't watch your runs. Your work stays local unless you choose to publish the finished Result bundle. Model calls go to the model provider you run with, under that provider's policies.

## Pages

- [Results](/results): published Results, newest first.
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
