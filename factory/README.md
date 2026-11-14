# Factory

The factory is how Techtree improves an agent on one workflow. Each of the four
services takes something you already have, changes one thing, and measures the change
on cases the work never saw. The libraries come from NVIDIA, Prime Intellect,
Microsoft, Hugging Face and others; Techtree picks them, wires them to your workflow
and reports what happened.

[Book a call](https://calendly.com/techtree/agent-env-intro) ·
[build@regents.sh](mailto:build@regents.sh)

## Process

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

Each service's page lays out its own steps in full. The report says whether a gain
came from the change under test or from something else, such as the data, the agent
around the model, its settings or the machines it ran on. A result with no
improvement is still delivered, with the reason. Results from our own runs are a
Techtree-run evaluation, not an independent audit.

## Services

| Service | You bring | You receive | Page |
| --- | --- | --- | --- |
| Skills | Your Skill, the agent and model that use it, and real examples | The revised Skill and a before-and-after report | [skills/](skills/README.md) |
| Evals | The job, with examples of good work and bad, or an eval you already have | Reviewed test cases, with scoring for every case | [evals/](evals/README.md) |
| Environments | The workflow, a Skill or a repository | An environment that resets between runs, with realistic tasks | [environments/](environments/README.md) |
| Models | The work you repeat, with real examples | A smaller trained model and a comparison with the original | [models/](models/README.md) |

Security sits beside the four: a one-off review or a monthly watch, described on
[techtree.sh](https://techtree.sh/services/security).

## Libraries

The [library table](../README.md#libraries) on the front page lists every library
with its maker, what it does, why we chose it and what it gives you. Each service
page names the ones it uses and the job each one does there.

Each library, and each step that runs one, has one of two statuses:

- **Tested**: we have run it ourselves.
- **Planned**: part of the design, not yet run.

What runs from this repository today, with the public
[regents-cli](https://github.com/regents-ai/regents-cli) command line it installs, is
under Run it on each service page, with the commands.

## Delivery

What you receive is yours to keep and rerun: the Skill, the eval, the environment or
the model files, the report, and the command that reruns the final test. This
repository explains the work and holds the public examples that run today.
