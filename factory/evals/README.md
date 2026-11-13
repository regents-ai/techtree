# Evals

Build a reliable test for whether agents can do this job. We turn your workflow and
its known failures into reviewed test cases with graders, then measure where you
stand today.

[techtree.sh/services/evals](https://techtree.sh/services/evals)

## You bring

- A workflow and representative examples.
- The failures you already know about.
- Your definition of success.
- Or an existing eval to improve.

## We do

- We use Prime Intellect's Verifiers to define the tasks and score them.
- We use Prime Intellect's prime-rl to run the full evaluation.
- Where a task needs a working software environment, we package it with Harbor.

## You receive

- Reviewed test cases.
- Graders.
- Baseline results.
- An analysis of the failures.
- One command that reruns the suite.

## Libraries

| Library | Job here | License | Status |
| --- | --- | --- | --- |
| Prime Intellect's [Verifiers](https://github.com/PrimeIntellect-ai/verifiers) | Defines the tasks and scores them, so the same definitions can later serve training. | MIT | Runs here today |
| Prime Intellect's [prime-rl](https://github.com/PrimeIntellect-ai/prime-rl) | Runs the full evaluation on Verifiers environments. | Apache-2.0 | Used in delivery |
| [Harbor](https://github.com/harbor-framework/harbor), from the makers of Terminal-Bench | Packages the tasks that need a working software environment, run in containers. | Apache-2.0 | Used in delivery |
| NVIDIA's [NeMo Fabric](https://github.com/NVIDIA/NeMo-Fabric) | Optional: runs several agent harnesses under one configuration, when a suite should compare agents. | Apache-2.0 | Used in delivery |
| NVIDIA's [NeMo Relay](https://github.com/NVIDIA/NeMo-Relay) | Optional: records each run's model calls, tool calls and turns, kept as supporting evidence beside the score. | Apache-2.0 | Used in delivery |

## Run it

[`lab/`](../../lab/README.md) holds one small eval you can run today:
`regents/payment-terms`, an environment for Prime Intellect's Verifiers 0.4.1. Each
task describes a paid offer in plain words and asks for its payment requirements as
one JSON object. Twelve fields are scored exactly. The 1,024 train tasks and 64
held-out tasks never overlap.

From the repository root, with [uv](https://docs.astral.sh/uv/) and a model behind an
OpenAI-compatible endpoint (Ollama's by default):

```sh
uv run --project lab techtree-lab eval
```

It runs the 64 held-out tasks and prints the mean score and the number solved. It
writes no file. `--skill lab/skills/payment-terms/SKILL.md` adds the Skill;
`--split train`, `--model`, `--base-url` and `--concurrency` (up to 4) change the
rest, and `--json` prints the answer as JSON. The environment and its scoring are in
[`lab/environments/payment_terms`](../../lab/environments/payment_terms/README.md).

## Delivery

Project work runs in Techtree's private delivery system. What you receive is yours to
keep and rerun: the test cases, the graders, the baseline results, the failure
analysis, and the one command that reruns the suite.

## Limits

- A better eval catches the failures that matter and scores the same work the same
  way every time. It need not produce a higher pass rate, and a stricter one often
  lowers it.
- An eval measures the cases it holds. A pass on them is evidence about that work,
  not about every task the agent might meet.
- Results from our own runs are a Techtree-run evaluation, not an independent audit.

## Start

[Book a call](https://calendly.com/techtree/agent-env-intro) or write to
[build@regents.sh](mailto:build@regents.sh).
