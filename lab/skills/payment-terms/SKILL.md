---
name: payment-terms
description: Turn a paid offer written in words into the exact x402 v2 payment requirements for USDC on Base.
---

# Payment terms

Reply with one JSON object and nothing else: the body a server sends with its
402 Payment Required response.

```json
{
  "x402Version": 2,
  "resource": {
    "url": "<resource URL>",
    "description": "<what the payer gets>",
    "mimeType": "application/json"
  },
  "accepts": [
    {
      "scheme": "exact",
      "network": "eip155:8453",
      "amount": "<price in USDC base units>",
      "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
      "payTo": "<seller address>",
      "maxTimeoutSeconds": <seconds the offer holds>,
      "extra": { "name": "USD Coin", "version": "2" }
    }
  ]
}
```

## Fields

- `x402Version`: the number 2.
- `resource.url`: the resource URL, copied exactly, query string included.
- `resource.description`: the quoted description, copied exactly, without the quotes.
- `resource.mimeType`: `"application/json"`.
- `accepts`: a list with exactly one requirement.
- `scheme`: `"exact"`.
- `network`: Base mainnet is `"eip155:8453"`, however the offer names Base.
- `amount`: USDC has 6 decimals, so the price in dollars times 1,000,000, written
  as a string of digits with no decimal point, sign or commas.
- `asset`: USDC on Base, `"0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"`, in this
  exact letter case.
- `payTo`: the seller's address, copied exactly.
- `maxTimeoutSeconds`: how long the offer holds, in seconds, as a number.
- `extra`: the USDC signing domain, `{"name": "USD Coin", "version": "2"}`.

## Amounts

| Price | `amount` |
| --- | --- |
| $2 | `"2000000"` |
| $0.40 | `"400000"` |
| 3 cents | `"30000"` |
| two dollars and five cents | `"2050000"` |
| $0.0002 | `"200"` |

## Times

| Offer holds for | `maxTimeoutSeconds` |
| --- | --- |
| 45 seconds | `45` |
| two minutes | `120` |
| a quarter of an hour | `900` |
| two hours | `7200` |

`amount` is a string; `x402Version` and `maxTimeoutSeconds` are numbers.
