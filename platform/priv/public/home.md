# Techtree

Improve a Skill. Prove it worked.

Run the same tasks with and without your Skill. See what improved, what regressed, and keep a report anyone can check.

Techtree's Climb evaluator uses [Prime Intellect's Verifiers](https://github.com/PrimeIntellect-ai/verifiers) and supports signed, independently checkable result bundles.

## Test your Skill (experimental)

Techtree makes practice tasks from what your Skill teaches. Your agent then works the same tasks twice: once without the Skill, or with its earlier version, and once with it. The model, the tools and the limits stay the same, so any difference comes from the Skill.

1. Tasks made from your Skill. You review the plan and keep the tasks that work.
2. Run twice: without the Skill or its earlier version, then with it.
3. Decide. Techtree says whether the Skill improved, regressed, was mixed or made no difference. Some tasks are held out from anyone improving the Skill; their result is the one to trust, because no revision could have studied them.

[See a real comparison](/examples/tdd).

## A quick look

The Hello World Climb ships with every release: a small, fixed set of tasks run once without a starter Skill and once with it. It shows how a run is approved, what it records and what a Result looks like. Its toy tasks say nothing about your own Skill.

## Published Climbs

- [Techtree Hello World](/climbs/hello-world-climb): a toy introductory demonstration of the mechanism, not a measure of broad capability.
- [Frontier-CS Open-Ended](/climbs/frontier-cs-open-ended-climb): ten open-ended optimisation problems with no known best answer, from Frontier-CS (MIT licence) as chosen by the FrontierSmith authors. With thanks to both.
- [HF Tasksmith](/climbs/tasksmith-climb): six real changes from Hugging Face's trl, transformers, diffusers, peft and accelerate repositories, from the HF ML Tasksmith collection. With thanks to its authors.

Techtree is a working technical preview built from three independent parts: Prime Intellect's Verifiers scores each Climb's tasks, Nous Research's Hermes runs the agent, and Techtree runs the comparison and keeps the evidence. Every finished Climb ends in a signed Result that anyone can check offline.

## When to use it

- To decide whether a change to a Skill is worth keeping.
- To compare your agent with and without a Skill on tasks made from it.
- To check someone else's published Result offline, without trusting this site.

It is not a general benchmark of a model's broad capability, and it does not run your agent for you in the cloud.

## How to start

- [Start](/start): test your Skill, or take a quick look with the example Climb.
- [Agent guide](/agents.md): the exact release to install and every step for your agent to follow, from making the tasks to comparing the runs. Each review waits for the person's own answer.
- [Docs](/docs): install, test a Skill, verify, publish and integrate.

## Your work stays local

Techtree doesn't watch your runs. Your work stays local unless you choose to publish a finished Climb Result. Model calls go to the model provider you run with, under that provider's policies.

## Pages

- [Results](/results): published Results, newest first. Only Climb runs can be published today.
- [Check a Result](/verify): how to check a Result offline, and what the check shows.
- [Techtree Verify](/services/verify) and [Techtree Cyber Assist](/services/cyber-assist): paid checks of your team's own workflows, such as an agent wallet flow, or of its security.
- [Changelog](/changelog): what changed in each release.
- [Repo2RLEnv](/repo2rlenv): the planned hosted service for building tasks from a repository.
- [About](/about), [Contact](/contact), [Privacy](/privacy) and [Terms](/terms)

## For agents and programs

- [/skill.md](/skill.md): the Techtree skill, for an agent to install: what to watch and how to check back.
- [/agents.md](/agents.md): the agent guide: the release to install and every step.
- [/llms.txt](/llms.txt): the short start for agents: what Techtree is, the install line and where everything is.
- [/openapi.json](/openapi.json): every public API address, typed.
- [/sitemap.xml](/sitemap.xml): every public page.
