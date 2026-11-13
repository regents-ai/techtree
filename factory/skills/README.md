# Skills

Improve how an existing agent handles a particular workflow. We check your Skill,
revise its written instructions from scored attempts, and test the revision on cases
the work never saw.

[techtree.sh/services/skills](https://techtree.sh/services/skills)

## You bring

- An existing Skill.
- The agent and the model that use it.
- Examples of work it got right, and work it got wrong.

## We do

- We use NVIDIA's SkillEvaluator to check the Skill's quality and measure how the
  agent behaves with it.
- We use Microsoft's SkillOpt to propose changes to its instructions from scored
  attempts. The cases it learns from are kept apart from the final test.
- We use Prime Intellect's Verifiers to run the final comparison on cases the work
  never saw, keeping the model, tools and budgets fixed.

## You receive

- The revised Skill.
- Instructions to install it.
- A report on success, cost and regressions.

## Libraries

| Library | Job here | License | Status |
| --- | --- | --- | --- |
| NVIDIA's [SkillEvaluator](https://github.com/NVIDIA/SkillEvaluator) | Checks the Skill is safe and well formed (its static check needs no API key, GPU or Docker), looks for repeated or overlapping guidance, then measures whether the Skill helps the agent on live tasks. | Apache-2.0 | Used in delivery |
| Microsoft's [SkillOpt](https://github.com/microsoft/SkillOpt) | Proposes add, delete and replace edits to the Skill document from scored attempts, and keeps an edit only when it raises a held-out validation score. | MIT | Used in delivery |
| Prime Intellect's [Verifiers](https://github.com/PrimeIntellect-ai/verifiers) | Runs the final comparison and scores every task by its own rules. | MIT | Runs here today |
| Nous Research's [Hermes](https://github.com/NousResearch/hermes-agent) | The agent a Climb runs with and without the Skill. | MIT | Runs here today |

## Run it

Two Skill comparisons run from this repository today, through the public
[regents-cli](https://github.com/regents-ai/regents-cli) command line. Both need
Hermes, Docker and a model provider. Model calls go to the provider you choose and
may cost money there; every paid step waits for your yes.

### Hello World

The Hello World Climb runs the same agent on the same small, synthetic tasks without
a Skill and with a starter Skill. Give your Hermes agent this instruction:

```text
Read https://techtree.sh/docs/run-locally and use the exact release it publishes.
If no installable release is active, stop and tell me.

Explain the prerequisites and ask before installing software. Run Techtree
Doctor and prepare the Hello World Climb. Show the model provider and cost
limit. Obtain approval before paid inference and separately before publishing.
```

With the [Hermes plugin](../../plugin/README.md) installed, `/techtree demo` prepares
the same Climb and stops before it spends. The run and its signed result bundle land
in `~/.regents/techtree` on your computer. Check the bundle offline with:

```sh
regents techtree proof verify path/to/result-bundle
```

### Your Skill

Evaluate & Climb makes practice tasks from what your Skill teaches, then runs your
agent on them without the Skill and with it. It is experimental. Planning and
building send your Skill's files to the model provider you choose. Each command
prints the next one, and every step that sends anything to a model prints a review
first and waits for your yes.

```sh
regents techtree forge inspect-skill path/to/your-skill
regents techtree forge plan SOURCE_ID --provider PROVIDER --model MODEL
# Review, correct, build and accept, one printed step at a time.
regents techtree forge run --arm baseline --collection COLLECTION_ID --provider PROVIDER --model MODEL
regents techtree forge run --arm candidate --collection COLLECTION_ID --provider PROVIDER --model MODEL --skill path/to/your-skill
regents techtree forge compare BASELINE_RUN_ID CANDIDATE_RUN_ID
```

Records land under `~/.regents/techtree/forge/`. The comparison calls no model: it
pairs every task across the two runs, says whether the Skill improved, regressed, was
mixed or made no difference, overall and on the held-out tasks alone, and writes
`report.html` in the comparison's folder. To compare two versions of a Skill, give
the baseline run the earlier version with `--skill path/to/earlier-skill`. The
[Run locally guide](https://techtree.sh/docs/run-locally) has the full steps.

## Delivery

Project work runs in Techtree's private delivery system. What you receive is yours to
keep and rerun: the revised Skill, its install instructions, the report, and the
command that reruns the final comparison on the held-out cases.

## Limits

- SkillOpt improves the Skill's written instructions. Repairing the scripts that come
  with a Skill is separate engineering, which we scope on the call.
- The final test covers the cases we agreed. A better score there does not promise a
  better score on other work, other models or other agents.
- Sometimes the Skill is not the problem. When the model, the tools or the task
  definition is, the report says so.
- Results from our own runs are a Techtree-run evaluation, not an independent audit.

## Start

[Book a call](https://calendly.com/techtree/agent-env-intro) or write to
[build@regents.sh](mailto:build@regents.sh).
