# Check a Result

When someone says a Skill made their agent better, you shouldn't have to take their word for it. Every Result on Techtree is a signed record you can download and check on your own computer, without trusting this site.

## How a Result is made

1. The agent works the same tasks twice. An agent run by Nous Research's [Hermes](https://github.com/NousResearch/hermes-agent) works a Climb's fixed tasks once without the Skill and once with it. The model, the tools and the limits stay the same.
2. Prime Intellect's [Verifiers](https://github.com/PrimeIntellect-ai/verifiers) scores every task, by that task's own rules.
3. The record is signed. The tasks, every score, the Skill and the settings go into one signed record: the Result. Changing any of it afterwards breaks the signature.

## What a check tells you

- Nothing changed after signing: every part of the Result still matches the signature made when the run finished.
- Only the Skill changed: both runs used the same tasks in the same order, the same model and the same settings.
- The verdict adds up: better, worse or no different follows from the task scores, by the rule the Climb set before the run.
- Nothing private is inside: a Result holds scores, not the agent's conversations or anything from the computer it ran on.

## What a check can't tell you

- Techtree did not watch the run happen. The signature shows which key signed, not that the computer behind it was honest.
- A better score on these tasks doesn't mean better at everything.
- One Result is one run. Only a separate rerun shows that it repeats.

## Check a Result yourself

Download the Result from its page on [Results](/results), then run this command. It repeats every check on your own computer, runs no model and costs nothing.

```sh
regents techtree proof verify path/to/result-bundle
```

The [Docs](/docs) explain the full method.
