# Evals

Build a reliable test for whether agents can do this job. We turn your workflow and
its known failures into reviewed test cases, each with its scoring, then measure
where you stand today.

[techtree.sh/services/evals](https://techtree.sh/services/evals)

## Process

Tested: we have run it ourselves. Planned: part of the design, not yet run.

1. **Intake**: You bring the job, with examples of good work and bad, or an eval you
   already have.
2. **Success**: We agree what the test must tell you.
3. **Review**: You approve the test cases before any of them count.
4. **Build** (Tested): We package the cases and their scoring with Prime Intellect's
   [Verifiers](https://github.com/PrimeIntellect-ai/verifiers), and with
   Terminal-Bench's [Harbor](https://github.com/harbor-framework/harbor) when a case
   needs working software around it.
5. **Scoring check** (Planned): We show that the scoring accepts known-good work and
   rejects plausible mistakes.
6. **Baseline** (Tested): We measure your current agent or model, several times
   over, and explain where it fails.
7. **Full run** (Planned): For a large test, Prime Intellect's
   [prime-rl](https://github.com/PrimeIntellect-ai/prime-rl) runs the whole
   evaluation at scale.
8. **Handover**: You receive everything below.

## You receive

- Reviewed test cases.
- Scoring for every case.
- Scores for what you run today.
- An analysis of the failures.
- One command that reruns the whole test.

All of it is yours to keep and rerun.

## Libraries

Tested: we have run it ourselves. Planned: part of the design, not yet run.

| Library | Job here | License | Status |
| --- | --- | --- | --- |
| Prime Intellect's [Verifiers](https://github.com/PrimeIntellect-ai/verifiers) | Defines the tasks and scores them, so the same definitions can later serve training. | MIT | Tested |
| [Harbor](https://github.com/harbor-framework/harbor), from the makers of Terminal-Bench | Packages the tasks that need working software around them, run in containers. | Apache-2.0 | Tested |
| Prime Intellect's [prime-rl](https://github.com/PrimeIntellect-ai/prime-rl) | Runs the whole evaluation at scale on Verifiers environments. | Apache-2.0 | Planned |
| NVIDIA's [NeMo Fabric](https://github.com/NVIDIA/NeMo-Fabric) | Optional: runs several agents under one setup, when a test should compare agents. | Apache-2.0 | Planned |
| NVIDIA's [NeMo Relay](https://github.com/NVIDIA/NeMo-Relay) | Optional: records each run's model calls, tool calls and turns, kept as supporting evidence beside the score. | Apache-2.0 | Planned |

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
