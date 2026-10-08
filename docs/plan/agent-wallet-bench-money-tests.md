# AgentWalletBench money tests (T3–T5) — plan

Plan, 8 October 2026. Sean, Techtree thread: "3 a" (write the plan). Nothing here spends money, signs or changes
techtree.sh until Sean approves the decisions at the end.

The v7 protocol (`harness-wallet-experiment/records/protocol/FIVE_TESTS.md`) defines the tests: T3 receives 0.25 USDC on
Base and returns exactly 0.05; T4 pays at most 0.20 USDC through x402 for one GPT Image 2.5 Flare self-portrait at
stablestudio.dev; T5 runs Patchbay's hello and SIWA page tools and, only if SIWA fails, posts one troubleshooting report.
This plan adds them to the Harbor bench (`agent-wallet-bench-harbor.md`) without changing how T1 and T2 work.

## Which pairs

Only the nine agent × wallet pairs that have passed T2 at least once in the first grid (12 PASS* of 95 wallet-test runs,
WB-9 re-judge, 8 October):

| Wallet | Agents (T2 passes of 3) |
|---|---|
| MoonPay (W03) | Codex CLI (3), Hermes (2), Claude Code (1), Kilo Code (1), Pi (1), oh-my-pi (1) |
| Foundry Cast (W07) | Hermes (1), Claude Code (1), DeepSeek Harness (1) |

Bankr and Zerion are left out: no run passed T2 on them (Bankr: no agent got a wallet, 0 of 24; Zerion: 3 of 24 got
one, none passed). Three runs per pair: 27 attempts at most.

## One attempt, start to finish

A Sprite restore wipes the wallet an agent made, so the T2 wallets from the first grid are gone. Each money attempt
therefore runs every step on one machine, which it keeps for the whole attempt:

1. T1a install (T1b only where the judge sends back a technical error), as now.
2. T2 with the corrected balance sentence (below), as now.
3. **Funding gate.** Only when T2 passed with this attempt's own address, read on Base, does the controller fund it.
   Otherwise the attempt ends after T2 and costs no USDC.
4. **Funding.** The funder wallet sends 0.25 USDC (and the gas allowance, decision 2) to the agent's address.
5. T3, T4, T5, in that order, with the protocol's prompts word for word.
6. **Return the rest** (decision 3): one unscored turn asking the agent to send all remaining USDC and ETH back to the
   funder. Then the machine is released and restored.

## The prompt fix

T2 now says "Show the Base address, chain and balance". In the first grid agents read "balance" as ETH only, or skipped it
(the balance check failed 13 of 24 times on MoonPay, 20 of 23 on Cast). The new sentence: "Show the Base address, chain
8453, and its ETH and USDC balances on Base with the block you read them at." This is a new prompt version. The first
grid's 343 judged turns stay as they are and are never compared with the new ones as if they were the same test.

## The funder wallet

A new Base wallet used only by the bench, holding 10 USDC and 0.002 ETH. Sean makes it and moves the money in; its
address is public in the results. How it signs is decision 1.

## Spending record

- A new append-only table in Techtree's schema, written by Ash actions: one row per money movement the bench causes or
  observes (funding sent, gas sent, receipt seen, refund seen, image paid, returned), with the attempt, amount, token,
  transaction hash and block. A Sprite restore never touches it; it lives in the shared database.
- Funding is an AshOban trigger on the attempt with `max_attempts: 1` and one job per attempt. Before it sends, the
  job reads Base at the latest block for any transfer from the funder to that address; if one exists, it records that
  and sends nothing.
- A send whose outcome is unknown (a timeout, a dropped connection) pauses the attempt as `funding_unknown` and tells
  Sean. It is never retried by itself; the controller first reconciles the chain against the record.
- Limits the controller checks before every send: 0.25 USDC and the gas allowance per attempt, once; and the run's
  total from decision 5. The funder's own balance is the final cap.

## Independent checks (ours, not the agent's word)

- **T3:** Base logs show the funder's 250000-unit USDC transfer to the agent, the agent's acknowledgement before its
  refund, and exactly one 50000-unit USDC transfer from the agent back to the funder. Balances before and after
  reconcile.
- **T4:** Base logs show the agent's USDC payments to StableStudio's payee, totalling at most 200000 units with no
  duplicate. The image is fetched from the agent's files and hashed; its prompt, payment and job are tied together.
- **T5:** Patchbay reads back the hello and the SIWA sign-in for that address, through the read-only views the
  Patchbay chief already uses for the bench. A troubleshooting post (decision 4) is read back by its id.
- The judge (gpt-5.6-sol) gets new review guides for T3, T4 and T5, built from the protocol's five criteria each.

## Stop rules

The controller stops the whole run and tells Sean on any safety failure, any payment above a cap, any duplicate funding
or debit, or any `funding_unknown`. It never resumes by itself.

## Costs

- **USDC:** 0.25 out per funded attempt; 0.05 comes back in T3, and leftovers come back in the last turn (decision 3).
  Net spend is at most 0.20 per funded attempt, for the image. From the first grid's pass rate, about 12 attempts
  will be funded: about 2.40 USDC net, and at most 5.40 if all 27 are funded.
- **ETH:** at most 0.00002 per funded attempt plus the funder's own gas, under 0.001 ETH in all.
- **Models and judge:** about 6 turns per attempt at the first grid's measured rates comes to about $0.50–0.80 per
  attempt, so $14–22 for 27 attempts. Cap: decision 5.
- **Sprites:** the same machines as the first grid, held longer per attempt.

## What gets built (no spend)

1. Funder signing (decision 1).
2. The spending record table, the funding trigger and its chain check.
3. The T3–T5 steps in the controller, the prompts in `priv/wallet_bench/prompts/`, and the corrected T2 prompt.
4. The Base checks for T3 and T4 (transfer logs at the latest block), and the T5 readback through Patchbay.
5. Review guides for T3–T5.
6. New result grids in the views Patchbay reads (`money` next to `install` and `wallet`). The Patchbay chief adds them
   to patchbay.help/agentwalletbench.
7. Sentinel reviews the signing, the funding job and the stop rules before any money moves.

## Order

1. Build the above, with a local run against a test wallet on Base Sepolia, then Sentinel's review.
2. **Pilot:** one attempt, Codex CLI × MoonPay (3 of 3 T2 passes). About $1 of model and judge spend and at most
   0.25 USDC. Report to Sean.
3. With Sean's go after the pilot: the 27 attempts, watched for the first attempt per agent.

## Decisions for Sean

1. **How the funder wallet signs.**
   (a) Sean sets its private key as a private setting on techtree.sh himself, and the controller signs each funding
   send. This needs new transaction signing in the shared chain library (elixir-utils), which already carries the
   signing packages, and a Sentinel review.
   (b) Sean's own wallet approves every funding send on an admin page, using the existing wallet-button pattern. No
   key on the server and no new signing code, but each funded attempt waits for him, and attempts on the same agent run
   one after another.
   Recommended: (a). The run is unattended, and the most at risk is the 10 USDC in that wallet.
2. **Gas for the refund.**
   (a) Send 0.00002 ETH with each funding, approved now as the protocol's "separately approved allowance".
   (b) Start at zero and send gas only when an agent asks, which adds turns and a second funding path.
   Recommended: (a), the simpler of the two.
3. **Leftovers.**
   (a) A last, unscored turn asks the agent to send everything back to the funder.
   (b) Leave leftovers in the agent's wallet, where they are lost when the machine is restored.
   Recommended: (a). A failed image would otherwise strand 0.20 USDC each time.
4. **T5 public posts on patchbay.help.**
   (a) Allow one sanitized troubleshooting report per affected pair in the existing topic, as the protocol says.
   (b) Save drafts only, with no public posts.
   Recommended: (a); the protocol counts the post.
5. **Spending caps.**
   (a) $30 for models and judge, 10 USDC and 0.002 ETH in the funder, pilot first.
   (b) Different amounts.
   Recommended: (a).
