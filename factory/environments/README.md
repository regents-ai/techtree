# Environments

Turn your workflow into repeatable practice for agents. We generate realistic tasks
from your Skill, repository or workflow, and check that each task's tests accept good
work and reject bad work.

[techtree.sh/services/environments](https://techtree.sh/services/environments)

## You bring

- A Skill, a repository, or a description of your workflow and its tools.
- Or an existing Harbor, Prime or OpenEnv environment.

## We do

- We use NVIDIA's Skill2Env to generate Harbor tasks from a Skill.
- We use Hugging Face's Repo2RLEnv to generate them from a repository, its past fixes
  and recorded agent sessions.
- We use Prime Intellect's Verifiers to run the tasks and score them.
- An environment you already have, from Harbor, Prime or OpenEnv, starts with a
  compatibility review.
- We make sure the environment represents your actual job, and check that its tests
  accept good work and reject bad work.

## You receive

- A resettable environment.
- Realistic tasks, with their tools and fixtures.
- Reference solutions.
- Scoring.
- Entry points for evaluation and training.

## Libraries

| Library | Job here | License | Status |
| --- | --- | --- | --- |
| NVIDIA's [Skill2Env](https://github.com/NVlabs/Skill2Env) | Generates terminal tasks in Harbor's format from a Skill. `regents techtree forge` follows its task layout and adapts its planning and building steps, pinned to one revision; its own generator is used in delivery. | Apache-2.0 (its own source; Skills bundled with it keep their own terms) | Runs here today |
| Hugging Face's [Repo2RLEnv](https://github.com/huggingface/Repo2RLEnv) | Generates Harbor tasks from a repository's merged pull requests, commit history, security advisories and recorded agent sessions, and checks each with controls: the reference solution scores 1, doing nothing scores 0. | Apache-2.0 (its own code; the distribution is Apache-2.0 AND MIT) | Used in delivery |
| Prime Intellect's [Verifiers](https://github.com/PrimeIntellect-ai/verifiers) | Runs the tasks and scores them, the same way for evaluation and for training. | MIT | Runs here today |
| [Harbor](https://github.com/harbor-framework/harbor), from the makers of Terminal-Bench | The task format: instruction, container recipe, tests and solutions in one folder. The tasks `forge` builds follow it. | Apache-2.0 | Used in delivery |
| Prime Intellect's [Environments Hub](https://app.primeintellect.ai/dashboard/environments) | Hosts Verifiers environments at pinned versions. The HF Tasksmith Climb downloads its environment from it today. | A hosted service | Runs here today |
| [OpenEnv](https://github.com/openenv/OpenEnv), from its technical committee | An environment you already have in OpenEnv is reviewed for reuse before anything new is built. | BSD-3-Clause | Used in delivery |

## Run it

`regents techtree forge`, from the public
[regents-cli](https://github.com/regents-ai/regents-cli) command line, builds an
environment from a Skill on your own computer. It is experimental. It needs Docker
and a model provider; running an agent on the finished tasks also needs Hermes.
Planning and building send your Skill's files to the provider you choose; every step
that does so prints a review first and waits for your yes.

```sh
regents techtree forge inspect-skill path/to/your-skill
regents techtree forge plan SOURCE_ID --provider PROVIDER --model MODEL
# Review, correct, build and accept, one printed step at a time.
```

`inspect-skill` reads the Skill without running any of it. Each command prints the
next one: `plan-start`, `construct`, `construct-start`, `collect` and `accept`. Before
a built task can join a collection it must pass qualification, offline: its container
builds with the network off, doing nothing scores 0, the reference solution and a
second correct solution each score 1, and a deliberately wrong solution scores 0.

```sh
regents techtree forge verify COLLECTION_ID
regents techtree forge export COLLECTION_ID --to FOLDER
regents techtree forge correct-task CONSTRUCTION_ID TASK_NAME DIR
regents techtree forge status ID
```

`verify` checks that an accepted collection is unchanged since you accepted it.
`export` writes a private copy of it into a new folder for someone else to read.
`correct-task` records your hand-corrected copy of a built task, which goes through
the same qualification. `status` shows any forge record. Records land under
`~/.regents/techtree/forge/`. The automatic checks show that each task's tests agree
with its own sample solutions, not that they accept every correct answer, so read
each task before you accept a collection.

## Delivery

Project work runs in Techtree's private delivery system. What you receive is yours to
keep and rerun: the environment, its tasks with their tools and fixtures, the
reference solutions, the scoring, and the commands that run it for evaluation and for
training.

## Limits

- A higher score in a new environment does not mean the environment is better. An
  environment is better when it represents your job and its tests tell good work from
  bad.
- A generated task is a starting point, not a guarantee. Each one is checked against
  a reference solution and a wrong one, and read by a person before it is accepted.
- For ongoing work, failed attempts can propose new practice tasks, each one checked
  before it is admitted. The idea comes from
  [the AutoEnvScaling research](https://auto-env-scaling.github.io/).

## Start

[Book a call](https://calendly.com/techtree/agent-env-intro) or write to
[build@regents.sh](mailto:build@regents.sh).
