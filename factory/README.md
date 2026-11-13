# Factory

The factory is how Techtree improves an agent on one workflow. Each of the four
services takes something you already have, changes one thing, and measures the change
on cases the work never saw. The libraries come from NVIDIA, Prime Intellect,
Microsoft, Hugging Face and others; Techtree picks them, wires them to your workflow
and reports what happened.

[Book a call](https://calendly.com/techtree/agent-env-intro) ·
[build@regents.sh](mailto:build@regents.sh)

## Chain

Every project runs the same six steps:

1. You show us examples of the work: real inputs, accepted outputs and the failures
   you know about.
2. We agree in writing what success means before anything changes.
3. We measure a baseline: what you run today, and a cheaper option where one exists.
4. We make one bounded improvement.
5. We run a final test on cases the work never saw, with everything else held fixed.
6. You receive the deliverable, a report, and the command that reruns the test.

The report says whether a gain came from the change under test or from something
else, such as the data, the harness, inference settings or infrastructure. A result
with no improvement is still delivered, with the reason. Results from our own runs
are a Techtree-run evaluation, not an independent audit.

## Services

| Service | You bring | The improvement | Page |
| --- | --- | --- | --- |
| Skills | A Skill, the agent and model that use it, and examples | A revised Skill | [skills/](skills/README.md) |
| Evals | A workflow, examples, known failures and your definition of success | A test suite with graders | [evals/](evals/README.md) |
| Environments | A Skill, a repository or a description of your workflow | A resettable practice environment | [environments/](environments/README.md) |
| Models | One repeated task, real inputs and accepted outputs, and today's cost | A smaller specialist model | [models/](models/README.md) |

Security sits beside the four: a one-off review or a monthly watch, described on
[techtree.sh](https://techtree.sh/services/security).

## Libraries

The [library table](../README.md#libraries) on the front page lists every library
with its maker, what it does, why we chose it and what it gives you. Each service
page names the ones it uses and the job each one does there.

Each library has one of two statuses:

- **Runs here today**: this repository, with the public
  [regents-cli](https://github.com/regents-ai/regents-cli) command line it installs,
  uses it now. The service pages show the commands.
- **Used in delivery**: part of how a paid project is done. It does not run from this
  repository.

## Delivery

Project work runs in Techtree's private delivery system. What you receive is yours to
keep and rerun: the Skill, the eval suite, the environment or the model files, the
report, and the command that reruns the final test. This repository explains the
work and holds the public examples that run today.
