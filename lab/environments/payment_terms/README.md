# regents/payment-terms

A single-turn environment for [verifiers](https://github.com/PrimeIntellect-ai/verifiers)
0.4.1. Each task describes a paid offer in plain words (the price in USDC, the network,
who gets paid, the resource and how long the offer holds) and asks for the x402 v2
payment requirements as one JSON object: the body a server sends with its
402 Payment Required response.

Prices come in many forms ("$1.50", "one dollar and fifty cents", "150 cents",
"0.0036 USDC"). The network is Base mainnet (`eip155:8453`) and the asset is USDC
(`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`), so amounts are whole numbers of
6-decimal base units.

## Tasks

Tasks are generated from a seed. Each answer belongs to exactly one split, chosen by
the SHA-256 of the answer, so the splits never share a task:

| Split | Tasks |
| --- | --- |
| `train` | 1024 |
| `held_out` | 64 |

```toml
[env.taskset]
id = "regents/payment-terms"
split = "held_out"
seed = 0
```

## Reward

The reply's one JSON object is found wherever it sits (a code fence or a sentence
around it is fine). Twelve fields are then compared exactly, value and JSON type:
`x402Version`, the resource's `url`, `description` and `mimeType`, and the single
requirement's `scheme`, `network`, `amount`, `asset`, `payTo`, `maxTimeoutSeconds`
and `extra.name` and `extra.version`.

- `fields` (reward): the share of the twelve fields that are right, from 0 to 1.
- `solved` (metric): 1 when all twelve are right, else 0.

A reply with no JSON object, or more than one, scores 0.
