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
- LiteLLM 1.103.1 does not list Opus 5.5 (it stops at `claude-opus-5`). Move to
  a release that lists it, installed with hashes (a B4 follow-up), or declare the
  model's abilities in the relay's settings. Decided in the build.

`priv/wallet_bench/machine/bench_hooks.py`
- Effort: every call runs with adaptive thinking and `output_config.effort`
  `high`. The OpenAI `reasoning_effort` and `reasoning` rewrites go.
- Thinking stays valid across turns: the relay sets the
  `thinking-binding-controls-2026-08-01` header and `drop_block`, so a harness
  that edits its history loses that reasoning instead of failing the call.
- Removed before sending, because each costs more than the hold or calls other
  models: Anthropic's server tools (web search, web fetch, code execution, tool
  search, MCP servers, containers and skills, advisor), `fallbacks`, `speed`
  (fast mode costs twice), `service_tier`, `inference_geo`,
  `context_management`, and a one-hour cache time (forced to five minutes).
- Hold: each call's output is capped at 32,000 tokens. Each call holds its
  own most-possible price: its input tokens, counted exactly by Anthropic's free
  token-count endpoint for native calls and bounded by the request's length for
  translated ones, all priced as cache writes, plus 32,000 output tokens. This
  replaces the fixed $0.33.
- The tool filter keeps the harness's own tools only: Anthropic custom tools,
  and for translated calls the function tools LiteLLM turns into them.
- Logging reads effort from the Anthropic request shape.

`credentials.sh`, `baseline.sh`, `calls.py`
- The key file is `anthropic.key`; the manifest says `claude-opus-5-5`, `high`.

## The tested agents (runner side)

`priv/wallet_bench/runner/awb_runner/roster.py`, `agents.py`, `prime.py`
- Every harness asks for `claude-opus-5-5`. Where a harness can speak
  Anthropic's own format to a set address, it does, so its thinking carries
  across turns; otherwise LiteLLM translates.

| Harness | Route |
| --- | --- |
| H05 Claude Code | Anthropic's format, as now; the cleanest path |
| H10 Codex | OpenAI Responses, translated. Risk: Codex's free-form patch tool has no Anthropic match |
| H08 Pi, H09 oh-my-pi, H16 Prime | switch to their Anthropic setting |
| H06 Cline, H07 Kilo, H13 OpenCode | Anthropic provider with a set address, if their pinned versions allow it; else translated |
| H04 Hermes, H12 DeepSeek Harness | translated Chat Completions |

Each harness is checked against a stand-in model server before the release. Any
that cannot run on Opus is named with the reason, and it stays out of batches.

## The judge and the site (server side)

- New shared package `regent_anthropic` in `repos/elixir-utils/anthropic`, a
  sibling of `regent_openai`. It sends one Messages request through
  `regent_http`, uses a dated price table, structured answers through
  `output_config.format`, returns the cost on every answer, and keeps the
  billed cost on a failed call. The elixir-utils owner reviews and lands it,
  and the Bench pins it.
- `lib/techtree/wallet_bench/judge.ex`: calls `RegentAnthropic`. Adaptive
  thinking, `high` effort, 32,000 output tokens.
- `lib/techtree/wallet_bench/turn/changes/judge_turn.ex`: records the billed
  cost of a failed judge call.
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
2. Relay, hooks and runner; each harness against the stand-in server.
3. Judge, batch, setup note, ignore list, runbook.
4. Local checks; Codex read-only review; Sentinel.
5. Release under Sean's go, then the first batch inside its ceiling, then a report.

No real model call before the release. The first batch is the acceptance.

## Estimate

About two working days to a reviewed candidate. The relay's spending cap took
nine review rounds last time, so the hold change may need more than one.
