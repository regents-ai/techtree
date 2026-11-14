# Models

A smaller model for the work you repeat. Techtree tests your current AI workflow,
builds a specialist, and measures the difference on cases it never saw. You keep the
model, the evaluation and the evidence behind the decision.

[techtree.sh/services/models](https://techtree.sh/services/models)

## Process

Tested: we have run it ourselves. Planned: part of the design, not yet run.

1. **Intake**: You bring the work you repeat, with real examples: one task, such as
   "classify a failed integration and pick the supported recovery step", not a whole
   field.
2. **Qualify** (Tested): We check whether a smaller model is right for this, and try
   a cheaper existing model first.
3. **Success**: We agree the target, and split your examples once: some for
   training, and a set the model never sees.
4. **Baseline** (Tested): We measure the small model and your current model with
   Prime Intellect's [Verifiers](https://github.com/PrimeIntellect-ai/verifiers)
   before any training.
5. **Plan** (Tested): We write a training plan in prime-rl's format, with its cost,
   for your approval. Nothing trains without it.
6. **Training** (Planned): Prime Intellect's
   [prime-rl](https://github.com/PrimeIntellect-ai/prime-rl) trains the model on your
   accepted examples, then on scored practice when the project calls for it.
7. **Final test** (Planned): We test the trained model against the original on the
   unseen set, including the cost per successful task.
8. **Handover** (Planned): You receive everything below, with help putting the model
   into service. When agents need to run under rules you set, we run them inside
   OpenShell with NVIDIA's [NemoClaw](https://github.com/NVIDIA/NemoClaw).

## You receive

- The trained model files.
- The training recipe.
- A test package you can rerun.
- Help putting the model into service.
- A comparison with the original model, including the cost per successful task.

All of it is yours to keep and rerun.

## Comparisons

Two questions, and we report them separately.

| Comparison | Question | Answered by |
| --- | --- | --- |
| Training | Did training improve the model? | The small model before and after training, on the same task and the same test. |
| Replacement | Should you replace what you run today? | Your current service against the proposed one, counting hosting, retries, response time and running cost. |

## Libraries

Tested: we have run it ourselves. Planned: part of the design, not yet run.

| Library | Job here | License | Status |
| --- | --- | --- | --- |
| Prime Intellect's [Verifiers](https://github.com/PrimeIntellect-ai/verifiers) | Holds the tasks that training and the final test share. | MIT | Tested |
| NVIDIA's [Nemotron](https://www.nvidia.com/en-us/ai-data-science/foundation-models/nemotron/) | Open models, with weights and training data published on Hugging Face, that a small specialist can start from. | See each model's card | Tested |
| Prime Intellect's [prime-rl](https://github.com/PrimeIntellect-ai/prime-rl) | Trains the model on your accepted examples, then on scored practice, on the same Verifiers environments the test uses. | Apache-2.0 | Planned |
| NVIDIA's [NemoClaw](https://github.com/NVIDIA/NemoClaw) | Optional, when a project needs it: runs supported agents inside OpenShell, under the network rules you set. | Apache-2.0 | Planned |

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

## Limits

- Before training, we try a cheaper existing model and a better prompt or Skill. If
  that gets the saving, we say so.
- A candidate that falls short still gives you a paid, useful answer: whether the
  blocker is the data, an unclear task, model size, running cost or new mistakes.
- The figure we report is the total running cost per accepted outcome, at a quality
  level we agree. The one-time training cost is shown separately.
- Training starts on your accepted examples. Scored practice comes next, once we have
  checked the scoring.
- Results from our own runs are labelled a Techtree-run evaluation, not an
  independent audit.

## Start

[Book a call](https://calendly.com/techtree/agent-env-intro) or write to
[build@regents.sh](mailto:build@regents.sh).
