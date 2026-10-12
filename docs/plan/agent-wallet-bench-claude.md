# Wallet Bench on Claude Opus 5.5

Sean, 12 October 2026 03:57Z (relayed verbatim): "30. b - switch to either codex
running it or claude, but it must use the claude api key for opus 5.5. it is fine
to redo results".

Every model call the Bench makes, the tested agent's and the judge's, goes to
`claude-opus-5-5` on Anthropic's API with the Bench's Claude key. Nothing in the
Bench calls OpenAI afterwards. Branch `tt/bench-claude-1012`, from the live
release `44b20a1`.

## What it costs

From the live database (12 October), the 176 attempts that made model calls on
gpt-6-luna:

| | Per attempt |
| --- | --- |
| Agent's model calls, average | $0.014 |
| Agent's model calls, largest | $0.066 |
| Judge (gpt-5.6-sol, the same price as Opus 5.5) | $0.18 average |

Opus 5.5 is $4 input, $0.20 cache read, $5 cache write (five minutes) and $20
output per million tokens: 20 to 40 times gpt-6-luna. The same work on Opus
would be about $0.30 to $0.60 for the agent's calls on average and $2.60 at the
most, more if Opus thinks longer than luna did. The judge costs what it did.

- First batch of four attempts: about $3 to $8 in all, under the $25 ceiling.
- Redoing all 176 earlier attempts: about $90 to $250, a separate approval.

## The model relay (machine side)

`priv/wallet_bench/machine/proxy-install.sh`
- Route every model name to `anthropic/claude-opus-5-5` with the Claude key.
- Opus prices in place of luna's; Opus has no long-prompt tier.
- LiteLLM 1.103.1 does not list Opus 5.5 (it stops at `claude-opus-5`).
  LiteLLM 1.104.3 lists it, with adaptive thinking and `output_config`. It is
  installed with every package it needs from `litellm-requirements.txt`, each
  matched to its hashes (the B4 follow-up, done here).

`priv/wallet_bench/machine/bench_hooks.py`
- Effort: every call runs with adaptive thinking and `output_config.effort`
  `high`. Native Messages calls get both set directly; chat calls get
  `reasoning_effort` `high` and Responses calls `reasoning.effort` `high`, which
  LiteLLM turns into the same Anthropic fields.
- No thinking-binding header or `drop_block`: Claude Code (H05) keeps its own
  history as Anthropic expects, and translated harnesses carry no thinking
  blocks between turns.
- Removed before sending, because each costs more than the hold or calls other
  models: Anthropic's server tools (web search, web fetch, code execution, tool
  search, MCP servers, containers and skills, advisor), `fallbacks`, `speed`
  (fast mode costs twice), `service_tier`, `inference_geo`,
  `context_management`, and a one-hour cache time (forced to five minutes).
- Hold: each call's output is capped at 32,000 tokens. Each call holds its
  own most-possible price: its input tokens, all priced as five-minute cache
  writes, plus 32,000 output tokens ($0.64). Native Messages calls are counted by
  Anthropic's free token counter, plus a tenth because the counter is an
  estimate. Translated calls are bounded by their length in bytes, since no
  Claude token is shorter than a byte, plus 10,000 tokens for the tool
  instructions Anthropic adds and 10,000 for each image. Translated calls
  carrying a file or document are refused, because a short link or small file
  can stand for many pages. No hold counts more input than the 1M context. This
  replaces the fixed $0.33.
- Each call is charged once, by whichever of answered, interrupted or failed
  comes first. LiteLLM's resend on a fresh connection after a broken one is
  switched off, so a reset after Anthropic received a request fails the call
  and charges its hold instead of sending it twice. An error inside a stream
  that had started is charged its hold, since tokens may already be billed.
- The tool filter keeps the harness's own tools only: Anthropic custom tools,
  and for translated calls the function and custom tools LiteLLM turns into them.
- Logging reads effort from the Anthropic request shape.

`credentials.sh`, `baseline.sh`, `calls.py`
- The key file is `anthropic.key`; the manifest says `claude-opus-5-5`, `high`.

## The tested agents (runner side)

`priv/wallet_bench/runner/awb_runner/roster.py`, `agents.py`, `prime.py`
- Every harness asks for `claude-opus-5-5`. Each keeps the route it uses on the
  live release; only the model name changes. Moving a harness to Anthropic's
  format would mean a new, untested setup for each one, for no gain in the
  first batch.

| Harness | Route |
| --- | --- |
| H05 Claude Code | Anthropic's format, as now; the cleanest path |
| H10 Codex | OpenAI Responses, translated. Risk: its shell tools have no Anthropic form and LiteLLM drops them |
| H04, H06–H09, H12, H13, H16 | OpenAI format, translated, as now |

The relay's spending cap is checked against a stand-in Claude server before the
release (kit in `artifacts/techtree-bench-claude-2026-10-12/relay-cap`). The
first batch runs the harness Sean picks (decision 33; recommended Claude Code,
the cleanest path). Other harnesses are checked on Opus in later batches; any
that cannot run is named with the reason and stays out of batches.

## The judge and the site (server side)

- New shared package `regent_anthropic` in `repos/elixir-utils/anthropic`, a
  sibling of `regent_openai`. It sends one Messages request through
  `regent_http`, uses a dated price table, structured answers through
  `output_config.format`, returns the cost on every answer, and keeps the
  billed cost on a failed call. The elixir-utils owner reviews and lands it,
  and the Bench pins it.
- `lib/techtree/wallet_bench/judge.ex`: calls `RegentAnthropic`. Adaptive
  thinking, `high` effort, 32,000 output tokens.
- A judge call that fails after it was billed (refused, cut short, or not in
  the asked shape) is not added to the turn's judge cost, and the job tries
  again. The live release does the same at the same price (gpt-5.6-sol and
  Opus 5.5 are both $4 in and $20 out per million tokens), so this is a
  follow-up, not part of the move.
- `lib/techtree/wallet_bench/batch.ex`: plans and validates
  `claude-opus-5-5`, `high`.
- `config/config.exs`: `judge_model: "claude-opus-5-5"`.
- `config/runtime.exs`: `WALLETBENCH_ANTHROPIC_API_KEY` for both the machines
  and the judge.
- `mix.exs`: `regent_anthropic` replaces `regent_openai`. Nothing else in
  Techtree uses `regent_openai`.
- `lib/techtree/wallet_bench/attempt/changes/attach_credentials.ex`, `blank.ex`:
  wording; `sk-ant-` keys already match the blanking pattern.
- A new migration replaces the published setup note, which names gpt-6-luna and
  gpt-5.6-sol. Earlier runs keep their own model on their pages.
- `platform/.dockerignore`: adds `priv/wallet_bench/runner/.venv/` and
  `**/__pycache__/` (Sentinel LOW).
- `docs/plan/agent-wallet-bench-manual-upgrades.md`: cost basis rewritten for Opus.

## Order

1. `regent_anthropic` in elixir-utils on its own branch; the owner reviews.
2. Relay, hooks and runner; the spending cap against the stand-in server.
3. Judge, batch, setup note, ignore list, runbook.
4. Local checks; Codex read-only review; Sentinel.
5. Release under Sean's go, then the first batch inside its ceiling, then a report.

No real model call before the release. The first batch is the acceptance.

## Estimate

About two working days to a reviewed candidate. The relay's spending cap took
nine review rounds last time, so the hold change may need more than one.
