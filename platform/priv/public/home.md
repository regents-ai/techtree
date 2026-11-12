# Techtree

Improve a Skill. Prove it worked.

Evaluate & Climb runs your agent on the same tasks with and without your Skill, shows what improved and what regressed, and keeps a signed Result anyone can check.

Every Climb is scored by [Prime Intellect's Verifiers](https://github.com/PrimeIntellect-ai/verifiers). Skill checks from [NVIDIA's SkillEvaluator](https://github.com/NVIDIA/SkillEvaluator) are coming soon.

## Built on the open-source frontier tech of

Prime Intellect, NVIDIA and Nous Research.

- [Prime Intellect's Verifiers](https://github.com/PrimeIntellect-ai/verifiers): scores every task in a Climb.
- [Prime Intellect's Environments Hub](https://app.primeintellect.ai/dashboard/environments): where the Tasksmith Climb gets its tasks.
- [Prime Intellect's Prime Agent](https://github.com/PrimeIntellect-ai/prime-agent): one of the agents Wallet Bench tests.
- [NVIDIA's Skill2Env](https://github.com/NVlabs/Skill2Env): the recipe Techtree's Skill tasks follow.
- [NVIDIA's SkillEvaluator](https://github.com/NVIDIA/SkillEvaluator) (coming soon): checks a Skill's quality and overlap.
- [NVIDIA's Nemotron](https://www.nvidia.com/en-us/ai-data-science/foundation-models/nemotron/): the models the Train page scores.
- [Nous Research's Hermes](https://github.com/NousResearch/hermes-agent): runs the agent in a Climb.

## Products

- [Evaluate & Climb](/start): check your Skill, then compare your agent with and without it.
- [Wallet Bench](/wallet-bench): which coding agents can set up which wallet tools safely.
- [Train](/train): NVIDIA Nemotron models scored before and after one change.
- [Offline check](/verify): download a signed Result and check it on your own computer.
- [Repo2RLEnv](/repo2rlenv): coming soon, past fixes in your repository become practice tasks for agents.
- [Watchdog](/services/watchdog): we test sites you prove you own for security weaknesses, then retest after you fix.

## Evaluate & Climb (experimental)

Evaluate a Skill, then climb: improve it, and prove the gain with a Result anyone can check. The approach follows [NVIDIA's open-source SkillEvaluator](https://github.com/NVIDIA/SkillEvaluator): check a Skill first, then compare live runs with and without it. Its quality and overlap checks are coming to Techtree soon.

- Evaluate: check the Skill, then compare runs with and without it. Validate (coming soon) asks whether the Skill is safe and well written; Deduplicate (coming soon) asks whether its guidance repeats itself; the live run asks whether the Skill helps the agent.
- Climb: improve the Skill, and prove the gain with a Result anyone can check.

Techtree makes practice tasks from what your Skill teaches, following [NVIDIA's Skill2Env](https://github.com/NVlabs/Skill2Env). Your agent then works the same tasks twice: once without the Skill, or with its earlier version, and once with it. The model, the tools and the limits stay the same, so any difference comes from the Skill. In a Climb, Prime Intellect's Verifiers scores every task by its own rules, the same way on both sides.

1. Tasks made from your Skill. You review the plan and keep the tasks that work.
2. Run twice: without the Skill or its earlier version, then with it.
3. Decide. Techtree says whether the Skill improved, regressed, was mixed or made no difference. Some tasks are held out from anyone improving the Skill; their result is the one to trust, because no revision could have studied them.

[See a real comparison](/examples/tdd).

## Example

The Hello World Climb ships with every release: a small, fixed set of tasks run once without a starter Skill and once with it. It shows how a run is approved, what it records and what a Result looks like. Its toy tasks say nothing about your own Skill.

## Published Climbs

- [Techtree Hello World](/climbs/hello-world-climb): a toy introductory demonstration of the mechanism, not a measure of broad capability.
- [Frontier-CS Open-Ended](/climbs/frontier-cs-open-ended-climb): ten open-ended optimisation problems with no known best answer, from Frontier-CS (MIT licence) as chosen by the FrontierSmith authors. With thanks to both.
- [HF Tasksmith](/climbs/tasksmith-climb): six real changes from Hugging Face's trl, transformers, diffusers, peft and accelerate repositories, from the HF ML Tasksmith collection. With thanks to its authors. Each run installs them from Prime Intellect's Environments Hub.

Techtree is a working technical preview built from three independent parts: Prime Intellect's Verifiers scores each Climb's tasks, Nous Research's Hermes runs the agent, and Techtree runs the comparison and keeps the evidence. Every finished Climb ends in a signed Result that anyone can check offline.

## On-ramp

Techtree is where a team starts. We do the first steps with you: check the Skill, build the practice tasks and a fair test, and prove the result.

Climbs run on Prime Intellect's Verifiers, which Prime Intellect's own training uses too, so what you leave with is ready to take to Prime Intellect for training and environments at scale. We work with smaller teams on these first steps.

1. Your work: a Skill, or a repository and its history of fixes.
2. Techtree: evaluate the Skill, build the tasks and the fair test, prove the gain.
3. [Prime Intellect](https://www.primeintellect.ai/): training and environments at scale.

[Email us](mailto:build@regents.sh).

## Use cases

- To decide whether a change to a Skill is worth keeping.
- To compare your agent with and without a Skill on tasks made from it.
- To check someone else's published Result offline, without trusting this site.

It is not a general benchmark of a model's broad capability, and it does not run your agent for you in the cloud.

## Start

- [Start](/start): test your Skill, or take a quick look with the example Climb.
- [Agent guide](/agents.md): the exact release to install and every step for your agent to follow, from making the tasks to comparing the runs. Each review waits for the person's own answer.
- [Docs](/docs): install, test a Skill, verify, publish and integrate.

## Privacy

Techtree doesn't watch your runs. Your work stays local unless you choose to publish a finished Climb Result. Model calls go to the model provider you run with, under that provider's policies.

## Pages

- [Results](/results): published Results, newest first. Only Climb runs can be published today.
- [Offline check](/verify): how to check a Result offline, and what the check shows.
- [Techtree Verify](/services/verify) and [Techtree Cyber Assist](/services/cyber-assist): checks of your team's own workflows, such as an agent wallet flow, or of its security.
- [Techtree Formal](/formal): what formal verification proves, recent advances with their sources, and how to send code to be proved.
- [Techtree Watchdog](/services/watchdog): a monthly watch on the sites you own, for security weaknesses, inside limits you agree.
- [Changelog](/changelog): what changed in each release.
- [Repo2RLEnv](/repo2rlenv): the planned hosted service for building tasks from a repository.
- [About](/about), [Privacy](/privacy) and [Terms](/terms)

## Agents

- [/skill.md](/skill.md): the Techtree skill, for an agent to install: what to watch and how to check back.
- [/agents.md](/agents.md): the agent guide: the release to install and every step.
- [/llms.txt](/llms.txt): the short start for agents: what Techtree is, the install line and where everything is.
- [/openapi.json](/openapi.json): every public API address, typed.
- [/sitemap.xml](/sitemap.xml): every public page.
