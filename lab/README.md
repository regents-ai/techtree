# techtree-lab

Techtree's lab: one task set to measure a model on, its runner, and a hosted training
settings file.

- **The task set**: `regents/payment-terms`, in `environments/payment_terms`. Each task
  describes a paid offer in plain words and asks for its x402 v2 payment requirements
  (USDC on Base) as one JSON object. Every field is scored exactly. It is a
  [verifiers](https://github.com/PrimeIntellect-ai/verifiers) 0.4.1 environment, ready to
  publish to Prime's Environments Hub as `regents/payment-terms`.
- **The Skill**: `skills/payment-terms/SKILL.md`, short guidance for writing those
  requirements exactly. It holds none of the held-out tasks.

## Commands

Run from the repository root. Everything runs on this computer; nothing is sent to Prime.

```sh
uv run --project lab techtree-lab eval
```

Runs one set of tasks (the held-out 64 by default) against a model through an
OpenAI-compatible endpoint, Ollama's by default, and prints the mean reward and the
number solved. `--skill lab/skills/payment-terms/SKILL.md` adds the Skill;
`--split train`, `--model`, `--base-url` and `--concurrency` (up to 4) change the rest.

```sh
uv run --project lab techtree-lab train-config
```

Writes `configs/hosted/payment-terms-nemotron-3-nano-30b.toml`: LoRA RL on
NVIDIA Nemotron 3 Nano 30B-A3B for 50 steps with the train split, on one 96 GB card
training and one serving, with the 64 held-out tasks measured before the first step
and after the last. `prime train validate` accepts it. It only writes the file;
starting a run is a separate decision.

Each command takes `--json` for machine-readable output.

## Checks

```sh
make -C lab check
```

Formatting, lint and types. The root `make check` runs it too.
