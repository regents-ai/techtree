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

Bring an existing Skill, the agent and model that use it, and examples of work it got
right and wrong. You receive the revised Skill, instructions to install it, and a
report on success, cost and regressions.
[How it works](factory/skills/README.md) · [techtree.sh](https://techtree.sh/services/skills)

### Evals

Bring a workflow, representative examples, the failures you already know about and
your definition of success, or an eval you already have. You receive reviewed test
cases, graders, baseline results, an analysis of the failures, and one command that
reruns the suite.
[How it works](factory/evals/README.md) · [techtree.sh](https://techtree.sh/services/evals)

### Environments

Bring a Skill, a repository or a description of your workflow and its tools, or an
environment you already have. You receive a resettable environment with realistic
tasks, their tools and fixtures, reference solutions, scoring, and entry points for
evaluation and training.
[How it works](factory/environments/README.md) · [techtree.sh](https://techtree.sh/services/environments)

### Models

Bring the one task you repeat, real inputs with the outputs you accepted, and what
you run today with its cost. You receive a smaller model as a checkpoint or adapter,
its training recipe, an evaluation package you can rerun, a deployment handover, and
a comparison with your current model that includes the cost per successful task.
[How it works](factory/models/README.md) · [techtree.sh](https://techtree.sh/services/models)

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
| Prime Intellect's [Verifiers](https://github.com/PrimeIntellect-ai/verifiers) | All four | Defines tasks, runs them and scores them. | One environment serves both evaluation and training, and it works with prime-rl and the Environments Hub. | The final test and any training share one task definition. | Runs here today |
| Prime Intellect's [prime-rl](https://github.com/PrimeIntellect-ai/prime-rl) | Evals, Models | Runs supervised fine-tuning, reinforcement learning and evaluation. | It covers post-training end to end, reads Verifiers environments natively, and scales to 1000+ GPUs. | A training recipe you can run again at a larger scale. | Used in delivery |
| Prime Intellect's [Environments Hub](https://app.primeintellect.ai/dashboard/environments) | Environments | Hosts Verifiers environments for others to install. | Verifiers and prime-rl both load environments from it. | Your environment, ready to publish at a pinned version if you choose to. | Runs here today |
| NVIDIA's [SkillEvaluator](https://github.com/NVIDIA/SkillEvaluator) | Skills | Checks a Skill and measures its effect on task results. | Its static check needs no API key, GPU or Docker, so problems show up before any paid run. | A Skill checked for safety and form, then measured with the agent. | Used in delivery |
| NVIDIA's [Skill2Env](https://github.com/NVlabs/Skill2Env) | Environments | Turns an Agent Skill into terminal tasks. | Its tasks come out ready for reinforcement learning, in Harbor's task format. | Practice tasks drawn from your own Skill. | Runs here today |
| NVIDIA's [NemoClaw](https://github.com/NVIDIA/NemoClaw) | Models (optional) | Runs supported agents, Hermes among them, inside NVIDIA OpenShell sandboxes. | It adds network policy and egress control around the agent. | An agent that runs only under the rules you set. | Used in delivery |
| NVIDIA's [NeMo Relay](https://github.com/NVIDIA/NeMo-Relay) | Any (optional) | Records an agent's model calls, tool calls and turns during a run. | It wraps the calls without rewriting the agent, and exports trajectories or OpenTelemetry traces. | A record of what the agent did, kept as supporting evidence beside the score. | Used in delivery |
| NVIDIA's [NeMo Fabric](https://github.com/NVIDIA/NeMo-Fabric) | Any (optional) | Runs many agent harnesses through one interface. | It has adapters for 17 harnesses, Claude Code, Codex and Hermes Agent among them, with models, tools and Skills configured the same way. | Your own agent, tested under the same settings as the others. | Used in delivery |
| NVIDIA's [Nemotron](https://www.nvidia.com/en-us/ai-data-science/foundation-models/nemotron/) | Models | A family of open models built for agents. | NVIDIA publishes the weights and the training data on Hugging Face. | A small open model you can host yourself. | Runs here today |
| Microsoft's [SkillOpt](https://github.com/microsoft/SkillOpt) | Skills | Rewrites a Skill's instructions from scored attempts while the model stays fixed. | It keeps an edit only when the edit raises a held-out validation score. | A compact revised Skill document. | Used in delivery |
| Hugging Face's [Repo2RLEnv](https://github.com/huggingface/Repo2RLEnv) | Environments | Turns a repository into verifiable environments for coding agents. | It builds tasks from material that already exists: merged pull requests, commit history, security advisories and recorded agent sessions. | Practice tasks from your own code history. | Used in delivery |
| Nous Research's [Hermes](https://github.com/NousResearch/hermes-agent) | Skills | An open agent that creates and improves Skills as it works. | Its Skills follow the agentskills.io open standard. | The agent every Climb evaluates, and the host the [plugin](plugin/) adds Techtree to. | Runs here today |
| [Harbor](https://github.com/harbor-framework/harbor), from the makers of Terminal-Bench | Evals, Environments | Evaluates agents in containers and generates rollouts for reinforcement learning. | One task format serves evaluation and training, for agents such as Claude Code, OpenHands and Codex CLI. | Tasks that need a working software environment, packaged so other tools can run them. | Used in delivery |
| [OpenEnv](https://github.com/openenv/OpenEnv), from its technical committee | Environments | Builds isolated environments for agent reinforcement learning, with a Gymnasium-style interface. | Twelve organizations steer its interface together, NVIDIA, Prime Intellect and Hugging Face among them. | An OpenEnv environment you already have, reviewed for reuse instead of rebuilt. | Used in delivery |

**Runs here today** means this repository, with the public
[regents-cli](https://github.com/regents-ai/regents-cli) command line it installs,
uses it now. **Used in delivery** means it is part of how a paid project is done and
does not run from this repository.

- Prime Intellect's Verifiers runs every Climb and the [`lab/`](lab/) comparison.
- The Environments Hub supplies the HF Tasksmith Climb's environment, pinned by
  digest.
- The experimental `regents techtree forge` builder follows Skill2Env's task layout
  and adapts its planning and building steps, pinned to one revision. Skill2Env's own
  generator is used in delivery.
- [`lab/`](lab/) compares NVIDIA Nemotron 3 Nano 4B without and with a Skill, and
  writes a training settings file for Nemotron 3 Nano 30B-A3B in prime-rl's shape.
  No training run starts from this repository.
- The tasks `forge` builds follow Harbor's task format.

## Method

Every project follows one chain:

1. You show us examples of the work: real inputs, accepted outputs and the failures
   you know about.
2. We agree in writing what success means before anything changes.
3. We measure a baseline: what you run today, and a cheaper option where one exists.
4. We make one bounded improvement: a Skill, an eval, an environment or a model.
5. We run a final test on cases the work never saw, with everything else held fixed.
6. You receive the deliverable, a report, and the command that reruns the test.

Along the way we turn your workflow into tasks, environments, evals and reward
signals, and we build each piece so your team can run, inspect and extend it. Every
experimental choice goes in the report: the model and its settings, the cases held
back, and every score.

Three rules hold on every project:

- We say whether a gain came from the change under test or from something else, such
  as the data, the harness, inference settings or infrastructure. Everything except
  the change is held fixed, so the comparison can tell them apart.
- A result with no improvement is still delivered, with the reason.
- Results from our own runs are a Techtree-run evaluation, not an independent audit.

## Expect

| Service | Outcome |
| --- | --- |
| Skills | A revised Skill, with a before and after on unseen cases that counts cost and regressions. Sometimes the finding is that the Skill was not the problem, and the report says what was. |
| Evals | A suite that catches the failures you already know about and scores the same work the same way twice. A stricter suite can lower your pass rate, because it stops counting answers that only looked right. |
| Environments | Resettable practice tasks whose tests accept good work and reject bad work, each checked against a reference solution and a deliberately wrong one. |
| Models | A smaller specialist measured against what you run today, counting hosting, retries, response time and running cost, or a clear reason not to train. |

The [published example](#results) below shows the shape of a result. One example is
not a promise of the same gain on your work.

## Results

On 12 Nov 2026 Techtree ran NVIDIA Nemotron 3 Nano 4B on 64 held-out payment-terms
tasks, once without a Skill and once with one, with the same settings: temperature 0,
at most 512 tokens, no thinking. Each task asks for one JSON object, and every field
is scored exactly. The run used Prime Intellect's Verifiers 0.4.1.

| | Without the Skill | With the Skill |
| --- | --- | --- |
| Average score (fields right) | 0% | 96% |
| Tasks fully right | 0 of 64 | 34 of 64 |

The Skill scored higher on all 64 tasks, with a 95% interval of +95 to +97 points.

The Skill teaches the answer format these tasks are scored on, and it is the only
thing that differs between the two sides. The result shows how well a small model
follows a written Skill. It does not show a smarter model, a gain on other tasks or
other models, or that anyone else has repeated the run.

- [The comparison's page](https://techtree.sh/train/payment-terms-nemotron-3-nano-4b-skill),
  with every task, the settings, and the report and traces to download. All
  published Results are at [techtree.sh/results](https://techtree.sh/results).
- Check it offline: `shasum -a 256 payment-terms-nemotron-3-nano-4b-skill.traces.jsonl`
  prints the traces digest the page shows. The report and traces are also in this
  repository under [`platform/priv/train/`](platform/priv/train/), and
  [Proof](https://techtree.sh/docs/verify) explains every digest.
- Run it again on your own computer with [`lab/`](lab/README.md).

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
| [`factory/`](factory/README.md) | One page per service: what you bring and receive, the libraries, what runs here, and the limits. |
| [`plugin/`](plugin/README.md) | The Hermes plugin that runs Techtree from a conversation. |
| [`cli/`](cli/COMMANDS.md) | The descriptions of every `regents techtree` command. The command line itself is [regents-cli](https://github.com/regents-ai/regents-cli). |
| [`lab/`](lab/README.md) | The Nemotron comparison and the training settings file. |
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
