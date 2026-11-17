# Techtree

**Better agents for your business.**

Techtree is for a team that runs an agent workflow that matters and has no time to
learn six new open-source systems. NVIDIA, Prime Intellect, Microsoft, Hugging Face
and others now publish open tools for agent Skills, evals, environments and model
training. We put those tools to work on your workflow in a small, bounded project,
and every project ends on a final test on cases the work never saw.

Open-source tools. Paid custom projects.

[Book a call](https://calendly.com/techtree/agent-env-intro) ·
[build@regents.sh](mailto:build@regents.sh) · [techtree.sh](https://techtree.sh)

## Role

Techtree is an independent company. We help teams adopt what NVIDIA, Prime Intellect
and others publish in the open, and we take on the smaller engagements: one Skill,
one eval suite, one environment or one specialist model. When a team needs training
at scale, we hand it an environment and an eval we have already checked, built to
run on those makers' own tools. We have no agreement with any of these companies and
do not speak for them.

## Services

Each service is a paid project around one of your workflows, quoted on a call.

### Skills

Bring your Skill, the agent and model that use it, real examples of the work, and the
failures you already know about. You receive the original Skill and the revised one,
a before-and-after report on cost, new mistakes and how sure the result is, the exact
setup it ran on, and one command that reruns it.
[How it works](factory/skills/README.md) · [techtree.sh](https://techtree.sh/services/skills)

### Evals

Bring the job, with examples of good work and bad, or an eval you already have. You
receive reviewed test cases, scoring for every case, scores for what you run today,
an analysis of the failures, and one command that reruns the whole test.
[How it works](factory/evals/README.md) · [techtree.sh](https://techtree.sh/services/evals)

### Environments

Bring the workflow, a Skill or a repository, or an environment you already have. You
receive an environment that resets between runs, realistic tasks with their tools and
sample data, a worked solution for each task, scoring, and ready-made commands to
test agents on it and to train them.
[How it works](factory/environments/README.md) · [techtree.sh](https://techtree.sh/services/environments)

### Models

Bring the work you repeat, with real examples, and what you run today with its cost.
You receive the trained model files, the training recipe, a test package you can
rerun, help putting the model into service, and a comparison with the original model
that includes the cost per successful task.
[How it works](factory/models/README.md) · [techtree.sh](https://techtree.sh/services/models)

Each page lays out the service's steps in full. A step that runs a library, and the
library itself, is marked **Tested** (we have run it ourselves) or **Planned** (part
of the design, not yet run).

### Security

A one-off review of an application or agent integration, or a monthly watch on sites
you own. [techtree.sh](https://techtree.sh/services/security)

### Terms

The four services are sold on the same terms:

- Model and compute usage is billed separately, under a cap we agree first.
- If you already have an eval or an environment, we reuse it. Missing foundations
  are quoted separately.
- You pay for the scoped work and its evidence. If the result shows no improvement,
  you still receive it, with the reason.

## Libraries

These are the open-source projects behind the four services, grouped by maker. Each
one is its maker's work. For each: what it does, why we chose it (from its own
documentation), and what it gives you.

| Library | Service | What it does | Why we chose it | What you get | Status |
| --- | --- | --- | --- | --- | --- |
| Prime Intellect's [Verifiers](https://github.com/PrimeIntellect-ai/verifiers) | All four | Defines tasks, runs them and scores them. | One environment serves both evaluation and training, and it works with prime-rl and the Environments Hub. | The final test and any training share one task definition. | Tested |
| Prime Intellect's [prime-rl](https://github.com/PrimeIntellect-ai/prime-rl) | Evals, Models | Runs supervised fine-tuning, reinforcement learning and evaluation. | It covers post-training end to end, reads Verifiers environments natively, and scales to 1000+ GPUs. | A training recipe you can run again at a larger scale. | Planned |
| Prime Intellect's [Environments Hub](https://app.primeintellect.ai/dashboard/environments) | Environments | Hosts Verifiers environments for others to install. | Verifiers and prime-rl both load environments from it. | Your environment, ready to publish at a pinned version if you choose to. Publishing yours there is planned. | Tested |
| NVIDIA's [SkillEvaluator](https://github.com/NVIDIA/SkillEvaluator) | Skills | Checks a Skill and measures its effect on task results. | Its static check needs no API key, GPU or Docker, so problems show up before any paid run. | A Skill checked for safety and form, then measured with the agent. | Tested |
| NVIDIA's [Skill2Env](https://github.com/NVlabs/Skill2Env) | Environments | Turns an Agent Skill into terminal tasks. | Its tasks come out ready for reinforcement learning, in Harbor's task format. | Practice tasks drawn from your own Skill. | Planned |
| NVIDIA's [NemoClaw](https://github.com/NVIDIA/NemoClaw) | Models (optional) | Runs supported agents, Hermes among them, inside NVIDIA OpenShell sandboxes. | It adds network policy and egress control around the agent. | An agent that runs only under the rules you set. | Planned |
| NVIDIA's [NeMo Relay](https://github.com/NVIDIA/NeMo-Relay) | Any (optional) | Records an agent's model calls, tool calls and turns during a run. | It wraps the calls without rewriting the agent, and exports trajectories or OpenTelemetry traces. | A record of what the agent did, kept as supporting evidence beside the score. | Planned |
| NVIDIA's [NeMo Fabric](https://github.com/NVIDIA/NeMo-Fabric) | Any (optional) | Runs many agent harnesses through one interface. | It has adapters for 17 harnesses, Claude Code, Codex and Hermes Agent among them, with models, tools and Skills configured the same way. | Your own agent, tested under the same settings as the others. | Planned |
| NVIDIA's [Nemotron](https://www.nvidia.com/en-us/ai-data-science/foundation-models/nemotron/) | Models | A family of open models built for agents. | NVIDIA publishes the weights and the training data on Hugging Face. | A small open model you can host yourself. | Tested |
| Microsoft's [SkillOpt](https://github.com/microsoft/SkillOpt) | Skills | Rewrites a Skill's instructions from scored attempts while the model stays fixed. | It keeps an edit only when the edit raises the score on cases set aside for checking. | A compact revised Skill document. | Tested |
| Hugging Face's [Repo2RLEnv](https://github.com/huggingface/Repo2RLEnv) | Environments | Turns a repository into verifiable environments for coding agents. | It builds tasks from material that already exists: merged pull requests, commit history, security advisories and recorded agent sessions. | Practice tasks from your own code history. | Planned |
| Nous Research's [Hermes](https://github.com/NousResearch/hermes-agent) | Skills | An open agent that creates and improves Skills as it works. | Its Skills follow the agentskills.io open standard. | The agent every Climb evaluates, and the host the [plugin](plugin/) adds Techtree to. | Tested |
| [Harbor](https://github.com/harbor-framework/harbor), from the makers of Terminal-Bench | Evals, Environments | Evaluates agents in containers and generates rollouts for reinforcement learning. | One task format serves evaluation and training, for agents such as Claude Code, OpenHands and Codex CLI. | Tasks that need a working software environment, packaged so other tools can run them. | Tested |
| [OpenEnv](https://github.com/openenv/OpenEnv), from its technical committee | Environments | Builds isolated environments for agent reinforcement learning, with a Gymnasium-style interface. | Twelve organizations steer its interface together, NVIDIA, Prime Intellect and Hugging Face among them. | An OpenEnv environment you already have, reviewed for reuse instead of rebuilt. | Planned |

**Tested** means we have run it ourselves. **Planned** means it is part of the
design, not yet run.

This repository, with the public
[regents-cli](https://github.com/regents-ai/regents-cli) command line it installs,
runs some of them today:

- Prime Intellect's Verifiers runs every Climb and the [`lab/`](lab/) payment-terms tasks.
- The Environments Hub supplies the HF Tasksmith Climb's environment, pinned by
  digest.
- The experimental `regents techtree forge` builder follows Skill2Env's task layout
  and adapts its planning and building steps, pinned to one revision. Using
  Skill2Env's own generator on a project is planned.
- [`lab/`](lab/) runs NVIDIA Nemotron 3 Nano 4B on the payment-terms tasks, and
  writes a training settings file for Nemotron 3 Nano 30B-A3B in prime-rl's shape.
  No training run starts from this repository.
- The tasks `forge` builds follow Harbor's task format.

## Method

Every project runs in the same six steps:

1. **Intake**: You bring real examples of the work, and the failures you already know
   about.
2. **Success**: We agree what better means, how it is scored and the budget cap,
   before anything runs.
3. **Baseline**: We measure what you run today, several times over, and set the cases
   for the final test aside.
4. **Improve**: We make one change, to a Skill, an eval, an environment or a model,
   within the limits agreed up front.
5. **Final test**: One run on cases the work never saw, with everything else held
   fixed, so the difference is the change.
6. **Handover**: You keep the result, a report of what changed and what it costs to
   run, and one command that reruns the test.

Each service's page in [`factory/`](factory/README.md) lays out its own steps in full.
Along the way we turn your workflow into tasks, environments, evals and scoring, and
we build each piece so your team can run, inspect and extend it. Every choice goes in
the report: the model and its settings, the cases set aside, and every score.

Three rules hold on every project:

- We say whether a gain came from the change under test or from something else, such
  as the data, the agent around the model, its settings or the machines it ran on.
  Everything except the change is held fixed, so the comparison can tell them apart.
- A result with no improvement is still delivered, with the reason.
- Results from our own runs are a Techtree-run evaluation, not an independent audit.

## Expect

| Service | Outcome |
| --- | --- |
| Skills | A revised Skill, with a before and after on unseen cases that counts cost and new mistakes. Sometimes the finding is that the Skill was not the problem, and the report says what was. |
| Evals | A test that catches the failures you already know about and scores the same work the same way twice. A stricter test can lower your pass rate, because it stops counting answers that only looked right. |
| Environments | Practice tasks that reset between runs, whose tests pass good work and fail bad work, each checked against a worked solution and a deliberately wrong one. |
| Models | A smaller specialist measured against what you run today, counting hosting, retries, response time and running cost, or a clear reason not to train. |

The [published examples](#results) below show the shape of a result, one of them a
change that did not help. They are not a promise of the same gain on your work.

## Results

Three demonstrations Techtree ran itself on public Skills, not customer work. Each
used NVIDIA's Nemotron 3 Nano 4B (`nemotron-3-nano:4b`) on our own machine, scored
through Prime Intellect's Verifiers 0.4.1 with the same settings on both sides, after
NVIDIA's SkillEvaluator 0.9.0 checked the original Skill. Each made two revisions
from the working cases alone, a single plain rewrite by Anthropic's Claude Opus 5.5
and a revision by Microsoft's SkillOpt with Claude Opus 5.5 proposing its changes,
and kept the one that solved the most on the choosing cases. The line for chance was
agreed before anything ran: 5 in 100. A difference within it is reported as
inconclusive.

| Skill | Final test | Original | Improved | Verdict |
| --- | --- | --- | --- | --- |
| [Dependabot](https://techtree.sh/train/dependabot-nemotron-3-nano-4b) | 38 cases, 3 times each | 35%, 40 of 114 | 81%, 92 of 114 | Improved |
| [Gitmoji](https://techtree.sh/train/gitmoji-nemotron-3-nano-4b) | 39 cases, 3 times each | 68%, 79 of 117 | 85%, 99 of 117 | Improved |
| [React Best Practices](https://techtree.sh/train/react-best-practices-nemotron-3-nano-4b) | 37 cases, 3 times each | 54%, 60 of 111 | 51%, 57 of 111 | Inconclusive |

None of them shows a gain on other tasks or other models, or that anyone else has
repeated the run.

### Dependabot

On 14 Nov 2026 Techtree improved GitHub's public
[Dependabot Skill](https://github.com/github/awesome-copilot/tree/9fd4597c60d7ca3c290fe8d142797e96f1d306f8/skills/dependabot)
([skills.sh](https://skills.sh/github/awesome-copilot/dependabot)), from its
awesome-copilot collection (MIT license), used unchanged as the starting point. It
is a guide for setting up and managing Dependabot, GitHub's tool that keeps a
repository's dependencies up to date.

The task: given a repository's file list, reply with the Dependabot package
ecosystems it needs, as an alphabetical, comma-separated list and nothing else; an
answer counts only when it matches exactly.

We wrote 84 cases and split them once, before anything ran: 25 to work on the Skill,
21 to choose between versions and 38 kept apart for one final test. On the choosing
cases SkillOpt's revision solved 73% of the attempts (46 of 63), against 57% for the
plain rewrite (36 of 63) and 35% for the original (22 of 63), so it was chosen.

The improved Skill solved 52 more attempts on the final test: 25 cases did better, 12
the same and 1 worse (`rust-service-container`, from 3 of 3 to 2 of 3). If the two
versions were equally good, a difference this large would turn up by chance fewer
than 1 time in 1,000.

### Gitmoji

On 14 Nov 2026 Techtree improved GitHub's public
[Gitmoji Skill](https://github.com/github/awesome-copilot/tree/541d8f04995bdd454bbaea0c215c2a8ef7f21935/skills/gitmoji)
([skills.sh](https://skills.sh/github/awesome-copilot/gitmoji)), from its
awesome-copilot collection (MIT license), used unchanged as the starting point. It
writes commit messages in the gitmoji convention, choosing the emoji that matches the
intent of each change.

The task: given a plain description of one change, reply with the gitmoji shortcode
the commit should use, such as `:bug:`, and nothing else; an answer counts only when
it matches exactly.

We wrote 87 cases and split them once, before anything ran: 26 to work on the Skill,
22 to choose between versions and 39 kept apart for one final test. On the choosing
cases the plain rewrite solved 86% of the attempts (57 of 66), against 73% for
SkillOpt's revision (48 of 66) and 64% for the original (42 of 66), so it was chosen.

The improved Skill solved 20 more attempts on the final test: 17 cases did better, 17
the same and 5 worse. If the two versions were equally good, a difference this large
would turn up by chance about 0.1 times in 100.

### React Best Practices

On 15 Nov 2026 Techtree tried to improve Vercel's public
[React Best Practices Skill](https://github.com/vercel-labs/agent-skills/tree/dc8367e6f91c022d83361f03c3313fa05e848ee5/skills/react-best-practices)
([skills.sh](https://skills.sh/vercel-labs/agent-skills/vercel-react-best-practices)),
from its agent-skills collection (MIT license), used unchanged as the starting point.
It holds React and Next.js performance guidelines from Vercel Engineering: 70 rules
in 8 categories, ranked by impact.

The task: given a short piece of React, Next.js or TypeScript code and five of the
Skill's rule ids, reply with the id of the one rule the code breaks, and nothing else;
an answer counts only when it matches exactly.

We wrote 83 cases and split them once, before anything ran: 25 to work on the Skill,
21 to choose between versions and 37 kept apart for one final test. On the choosing
cases the plain rewrite solved 73% of the attempts (46 of 63), against 71% for the
original (45 of 63) and 59% for SkillOpt's revision (37 of 63), so it was chosen.

The change did not help. On the final test the rewrite solved 3 fewer attempts than
the original: 9 cases did better, 19 the same and 9 worse. If the two versions were
equally good, a difference this large would turn up by chance about 74.5 times in
100, so these cases cannot tell the two versions apart.

### Reports

- Each comparison's page has every case, the method, the tools and the report to
  download. All published Results are at
  [techtree.sh/results](https://techtree.sh/results).
- The reports are also in this repository under
  [`platform/priv/train/`](platform/priv/train/), and
  [Proof](https://techtree.sh/docs/verify) explains how to check them. The cases and
  the improved Skills are not published.

## Try it

The Hello World Climb runs the same agent on the same small tasks without a Skill and
with a starter Skill, then shows the difference. It needs Hermes, Docker and a model
provider. Give your Hermes agent this instruction:

```text
Read https://techtree.sh/docs/run-locally and use the exact release it publishes.
If no installable release is active, stop and tell me.

Explain the prerequisites and ask before installing software. Run Techtree
Doctor and prepare the Hello World Climb. Show the model provider and cost
limit. Obtain approval before paid inference and separately before publishing.
```

```text
Fixed tasks + configured subject + evaluation limits
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
       No tested Skill          Candidate Skill
             │                       │
             └───────────┬───────────┘
                         ▼
              Paired scores + signed bundle
                         │
              Verify locally → optionally publish
```

Your everyday Hermes is the operator; the agent under test is a separate, pinned
instance. Hello World's tasks are synthetic, so a result there says nothing about
your own Skill. A valid result can show improvement, a tie or a regression.

Local runs and offline checks need no Techtree account. Model calls go to the
provider you configure and may cost money there. Check a signed Result bundle without
rerunning a model:

```sh
regents techtree proof verify path/to/result-bundle
```

The [Run locally guide](https://techtree.sh/docs/run-locally) has the full steps,
including testing your own Skill. [Proof](docs/proof.md) says what a Result does and
does not prove.

## Agents

- Working in this repository: [AGENTS.md](AGENTS.md).
- Using Techtree: [techtree.sh/agents.md](https://techtree.sh/agents.md).
- A short index of the site: [techtree.sh/llms.txt](https://techtree.sh/llms.txt).

## Repository

| Folder | Holds |
| --- | --- |
| [`factory/`](factory/README.md) | One page per service: its steps, what you receive, the libraries with their status, what runs here, and the limits. |
| [`plugin/`](plugin/README.md) | The Hermes plugin that runs Techtree from a conversation. |
| [`cli/`](cli/COMMANDS.md) | The descriptions of every `regents techtree` command. The command line itself is [regents-cli](https://github.com/regents-ai/regents-cli). |
| [`lab/`](lab/README.md) | The payment-terms tasks, their runner and the training settings file. |
| [`platform/`](platform/README.md) | The site at techtree.sh: install guide, Results, service pages and the changelog. |

More: [`contracts/`](contracts/README.md) (the registry contract),
[`formal/`](formal/wallet_bench_funding/README.md) (the Wallet Bench funding model),
[`blog/`](blog/README.md), and [`docs/`](docs/), including
[Open tools](docs/open-tools.md) (what each release offers and pins),
[Proof](docs/proof.md) (what a Result proves, and privacy) and
[Development](docs/development.md) (setup and checks).
[SECURITY.md](SECURITY.md) covers vulnerability reports and where code runs;
[CHANGELOG.md](CHANGELOG.md) lists every change; [LICENSE](LICENSE) has the terms.

## Contribute

Outside contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md).

- To add an environment or an eval, follow
  [`lab/environments/payment_terms`](lab/environments/payment_terms/README.md): an
  environment for Prime Intellect's Verifiers with a train split, a held-out split
  and exact scoring, checked by `make -C lab check`.
- To add an integration, start from [`plugin/`](plugin/README.md), which runs one
  command with fixed arguments and reads one JSON answer back. A new command starts
  as a section in [`cli/COMMANDS.md`](cli/COMMANDS.md).
- Run `make check` before you open a pull request. It starts no paid model call.

## Start

Tell us the workflow and what better would mean. We will say on the call whether a
project makes sense.

[Book a call](https://calendly.com/techtree/agent-env-intro) ·
[build@regents.sh](mailto:build@regents.sh)
