# Environments

Turn your workflow into repeatable practice for agents. We generate realistic tasks
from your Skill, repository or workflow, and prove that each one passes good work and
fails bad work.

[techtree.sh/services/environments](https://techtree.sh/services/environments)

## Process

Tested: we have run it ourselves. Planned: part of the design, not yet run.

1. **Intake**: You bring the workflow, a Skill or a repository. An environment you
   already have, from Harbor, Prime or OpenEnv, starts with a review of what can be
   reused.
2. **Success**: We agree what an agent should be able to practise.
3. **Tasks** (Planned): Tasks come from you, or we generate them: from a Skill with
   NVIDIA's [Skill2Env](https://github.com/NVlabs/Skill2Env), or from a repository,
   its past fixes and recorded agent sessions with Hugging Face's
   [Repo2RLEnv](https://github.com/huggingface/Repo2RLEnv).
4. **Soundness** (Tested): Every task is proven fair with Terminal-Bench's
   [Harbor](https://github.com/harbor-framework/harbor) in a sealed setup with no
   network: doing nothing scores zero, the worked solution passes and bad work fails.
5. **Baseline** (Planned): We measure an agent on the tasks with Prime Intellect's
   [Verifiers](https://github.com/PrimeIntellect-ai/verifiers).
6. **Handover**: You receive everything below.

## You receive

- An environment that resets between runs.
- Realistic tasks, with their tools and sample data.
- A worked solution for each task.
- Scoring.
- Ready-made commands to test agents on it and to train them.

All of it is yours to keep and rerun.

## Libraries

Tested: we have run it ourselves. Planned: part of the design, not yet run.

| Library | Job here | License | Status |
| --- | --- | --- | --- |
| [Harbor](https://github.com/harbor-framework/harbor), from the makers of Terminal-Bench | The task format: instruction, container recipe, tests and solutions in one folder. The tasks `forge` builds follow it, and each one is proven fair in a sealed setup with no network. | Apache-2.0 | Tested |
| Prime Intellect's [Verifiers](https://github.com/PrimeIntellect-ai/verifiers) | Runs the tasks and scores them, the same way for evaluation and for training. | MIT | Tested |
| Prime Intellect's [Environments Hub](https://app.primeintellect.ai/dashboard/environments) | Hosts Verifiers environments at pinned versions. The HF Tasksmith Climb downloads its environment from it today. | A hosted service | Tested |
| NVIDIA's [Skill2Env](https://github.com/NVlabs/Skill2Env) | Generates terminal tasks in Harbor's format from a Skill. `regents techtree forge` already follows its task layout and adapts its planning and building steps, pinned to one revision; using its own generator on a project is planned. | Apache-2.0 (its own source; Skills bundled with it keep their own terms) | Planned |
| Hugging Face's [Repo2RLEnv](https://github.com/huggingface/Repo2RLEnv) | Generates Harbor tasks from a repository's merged pull requests, commit history, security advisories and recorded agent sessions, and checks each with controls: the worked solution scores 1, doing nothing scores 0. | Apache-2.0 (its own code; the distribution is Apache-2.0 AND MIT) | Planned |
| [OpenEnv](https://github.com/openenv/OpenEnv), from its technical committee | An environment you already have in OpenEnv is reviewed for reuse before anything new is built. | BSD-3-Clause | Planned |

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

## Limits

- A higher score in a new environment does not mean the environment is better. An
  environment is better when it represents your job and its tests tell good work from
  bad.
- A generated task is a starting point, not a guarantee. Each one is checked against
  a worked solution and a wrong one, and read by a person before it is accepted.
- For ongoing work, failed attempts can propose new practice tasks, each one checked
  before it is added. The idea comes from
  [the AutoEnvScaling research](https://auto-env-scaling.github.io/).

## Start

[Book a call](https://calendly.com/techtree/agent-env-intro) or write to
[build@regents.sh](mailto:build@regents.sh).
