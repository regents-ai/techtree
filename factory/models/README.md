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
5. **Plan** (Tested): We write a training plan in prime-rl's format, with its cost.
   Training starts after you approve the plan and budget.
6. **Training** (Planned): Prime Intellect's
   [prime-rl](https://github.com/PrimeIntellect-ai/prime-rl) trains the model on your
   accepted examples first. When the project calls for it, training continues with
   reinforcement learning, using task scores as feedback.
7. **Final test** (Planned): We test the trained model against the original on the
   unseen set, including the cost per successful task.
8. **Handover** (Planned): You get the trained model, its training recipe, and a test
   package you can rerun, with help putting the model into service. When agents need
   to run under rules you set, we run them inside OpenShell with NVIDIA's
   [NemoClaw](https://github.com/NVIDIA/NemoClaw).

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
| Prime Intellect's [prime-rl](https://github.com/PrimeIntellect-ai/prime-rl) | Trains the model on your accepted examples, then with reinforcement learning on the same Verifiers environments the test uses, using task scores as feedback. | Apache-2.0 | Planned |
| NVIDIA's [NemoClaw](https://github.com/NVIDIA/NemoClaw) | Optional, when a project needs it: runs supported agents inside OpenShell, under the network rules you set. | Apache-2.0 | Planned |

## Run it

[`lab/`](../../lab/README.md) writes the settings file for a small training run from
the repository root, with [uv](https://docs.astral.sh/uv/).

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
- If the model misses the target, we explain where it fell short: the data, an
  unclear task, model size, running cost or new mistakes.
- The figure we report is the total running cost per accepted outcome, at a quality
  level we agree. The one-time training cost is shown separately.
- Training starts on your accepted examples. Reinforcement learning comes next, once
  we have checked the scoring.
- Results from our own runs are labelled a Techtree-run evaluation, not an
  independent audit.

## Start

[Book a call](https://calendly.com/techtree/agent-env-intro) or write to
[build@regents.sh](mailto:build@regents.sh).
