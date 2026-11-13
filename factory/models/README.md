# Models

A smaller model for the work you repeat. Techtree tests your current AI workflow,
builds a specialist, and measures the difference on cases it never saw. You keep the
model, the evaluation and the evidence behind the decision.

[techtree.sh/services/models](https://techtree.sh/services/models)

## You bring

- One repeated task, not a whole field: "classify a failed integration and pick the
  supported recovery step", not "technical support".
- Real inputs, and the outputs you accepted.
- What you run today, and what it costs.

## We do

- We use Prime Intellect's prime-rl for supervised fine-tuning, and for reinforcement
  learning when a project calls for it.
- We use Prime Intellect's Verifiers so that training and the final test share the
  same task definitions.
- When a project needs it, we use NVIDIA's NemoClaw to run supported agents inside
  OpenShell, under the rules you set.

## You receive

- A checkpoint or adapter.
- The training recipe.
- An evaluation package you can rerun.
- A deployment handover.
- A comparison with the original model, including the cost per successful task.

## Stages

| Stage | We do | You get |
| --- | --- | --- |
| Qualify | We define the task, the data permissions, the quality bar, the current cost and the limits on where the model can run. | A scoped experiment and an approved budget, or a clear reason not to train. |
| Baseline | We test what you run today and an inexpensive existing model, then freeze the test and the cases it holds back. | You learn whether training looks necessary at all. |
| Candidate | We curate examples and run one bounded training recipe. | A versioned adapter or checkpoint, with its training record. |
| Handover | We test on unseen cases, measure the model as it would be served, and run it beside your current service in a trial you approve. | The model files, the evaluation package, a cost report, its known limits, and how to switch to it or back. |

## Comparisons

Two questions, and we report them separately.

| Comparison | Question | Answered by |
| --- | --- | --- |
| Training | Did training improve the model? | The small base model against its trained version, on the same task and the same test. |
| Replacement | Should you replace what you run today? | Your current service against the proposed one, counting hosting, retries, response time and running cost. |

## Libraries

| Library | Job here | License | Status |
| --- | --- | --- | --- |
| Prime Intellect's [prime-rl](https://github.com/PrimeIntellect-ai/prime-rl) | Runs supervised fine-tuning and reinforcement learning, on the same Verifiers environments the test uses. | Apache-2.0 | Used in delivery |
| Prime Intellect's [Verifiers](https://github.com/PrimeIntellect-ai/verifiers) | Holds the same task definitions for training and for the test. | MIT | Runs here today |
| NVIDIA's [Nemotron](https://www.nvidia.com/en-us/ai-data-science/foundation-models/nemotron/) | Open models, with weights and training data published on Hugging Face, that a small specialist can start from. | See each model's card | Runs here today |
| NVIDIA's [NemoClaw](https://github.com/NVIDIA/NemoClaw) | Optional, when a project needs it: runs supported agents inside OpenShell, under the network rules you set. | Apache-2.0 | Used in delivery |

## Run it

[`lab/`](../../lab/README.md) runs both halves of a small example from the repository
root, with [uv](https://docs.astral.sh/uv/).

```sh
uv run --project lab techtree-lab compare
```

It runs NVIDIA Nemotron 3 Nano 4B in Ollama (pull `nemotron-3-nano:4b` into Ollama
first) on the 64 held-out payment-terms tasks twice, without and then with the Skill,
with the same settings: temperature 0, at most 512 tokens, no thinking. It prints
each side's mean score and solved count, the wins, ties and losses, and the 95%
interval of the difference. It writes the report and its traces to
`platform/priv/train/`, replacing the published pair; pass `--out FOLDER` to write
them somewhere else. This is the run behind the
[published example](../../README.md#results): a Skill comparison, not a training run.

```sh
uv run --project lab techtree-lab train-config
```

It writes `lab/configs/hosted/payment-terms-nemotron-3-nano-30b.toml`: LoRA reinforcement
learning on NVIDIA Nemotron 3 Nano 30B-A3B for 50 steps on the train split, in
prime-rl's shape, with the 64 held-out tasks measured before the first step and after
the last. It only writes the file. No training run starts from this repository.

## Delivery

Project work runs in Techtree's private delivery system. What you receive is yours to
keep and rerun: the model files, the training recipe, the evaluation package, the
cost report, and the command that reruns the final test.

## Limits

- Before training, we try a cheaper existing model and a better prompt or Skill. If
  that gets the saving, we say so.
- A candidate that falls short still gives you a paid, useful answer: whether the
  blocker is the data, an unclear task, model size, running cost or regressions.
- The figure we report is the total running cost per accepted outcome, at a quality
  level we agree. The one-time training cost is shown separately.
- We start with supervised fine-tuning on accepted examples, and add reinforcement
  learning when there is a reward we have validated.
- Results from our own runs are labelled a Techtree-run evaluation, not an
  independent audit.

## Start

[Book a call](https://calendly.com/techtree/agent-env-intro) or write to
[build@regents.sh](mailto:build@regents.sh).
