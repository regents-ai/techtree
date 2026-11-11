# techtree-lab

The lab behind Techtree's Train page. It measures a model on one task set, without and
with a change, and writes the comparison report the page shows.

- **The task set**: `regents/payment-terms`, in `environments/payment_terms`. Each task
  describes a paid offer in plain words and asks for its x402 v2 payment requirements
  (USDC on Base) as one JSON object. Every field is scored exactly. It is a
  [verifiers](https://github.com/PrimeIntellect-ai/verifiers) 0.4.1 environment, ready to
  publish to Prime's Environments Hub as `regents/payment-terms`.
- **The Skill**: `skills/payment-terms/SKILL.md`, short guidance for writing those
  requirements exactly. It holds none of the held-out tasks.
- **The report**: `platform/priv/train/payment-terms-nemotron-3-nano-4b-skill.json`, with
  every exchange with the model beside it in `.traces.jsonl`.

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
uv run --project lab techtree-lab compare
```

Runs NVIDIA Nemotron 3 Nano 4B in Ollama (`nemotron-3-nano:4b`, pulled first) on the 64
held-out tasks twice, without and then with the Skill, with the same settings:
temperature 0, at most 512 tokens, no thinking. It writes the report and its traces to
`platform/priv/train/` and prints each arm's mean reward and solved count, the wins,
ties and losses, and the 95% interval of the difference.

```sh
uv run --project lab techtree-lab train-config
```

Writes `configs/hosted/payment-terms-nemotron-3.5-lightning.toml`: LoRA RL on
NVIDIA Nemotron 3.5 Lightning for 50 steps with the train split, in the shape
`prime train` accepts. It only writes the file; starting a run is a separate decision.

Each command takes `--json` for machine-readable output.

## Checks

```sh
make -C lab check
```

Formatting, lint, types and tests, including a full `compare` against a stand-in
endpoint. The root `make check` runs it too.
