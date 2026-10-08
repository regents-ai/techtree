# AgentWalletBench money tests (T3–T5) — plan

Plan, 8 October 2026. Sean, Techtree thread: "3 a" (write the plan), then "1a 2a - ok it should send 0.00003 eth on
base 3a 4a 5a" (the decisions at the end, answered). Nothing moves on Base mainnet before Sean's go on the pilot.

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
3. **Funding gate.** Only when T2 passed with this attempt's own address, read on Base, and the bench itself confirmed
   the T2 signature came from that address, does the controller fund it. The bench recovers the key's signature
   (EIP-191); for a smart wallet the key did not sign for, it asks the wallet itself (ERC-1271).
   Otherwise the attempt ends after T2, costs no USDC and records why it was not funded ("The wallet test did not
   pass (FAILED_TECHNICAL)."); its refund, image and Patchbay results read "Not run" with that reason. When the bench
   itself cannot fund (funding paused, a total reached, the funder short, an address that is not new on Base), the
   attempt fails as a bench failure instead and leaves the results, so a bench problem never uses up one of a pair's
   three runs.
4. **Funding.** The funder wallet sends 0.25 USDC and 0.00003 ETH for gas (decision 2) to the agent's address.
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

## Spending record (as built)

- `wallet_bench_payments`, in Techtree's schema: one row per send the bench makes, with the attempt, token, amount,
  funder, agent address, nonce, the signed bytes, the transaction hash, the block and a state (`signed`, `confirmed`,
  `reverted`, `unknown`, `replaced`). The bytes and hash are stored before anything is broadcast, so sending again is
  the same transaction, never a second one. A Sprite restore never touches it.
- Funding is two AshOban steps on the attempt. **Sign:** reads Base at the latest block, decides, signs both sends
  and stores them in the same transaction as the attempt's move to `sending`; nothing is broadcast. **Send:**
  broadcasts the stored bytes and reads the receipts, waiting (an Oban snooze, not a retry) while one is pending.
  Both confirmed: T3 is queued in the same transaction. One reverted: the attempt stops. No receipt ten minutes after
  signing: the send becomes `unknown`, which pauses all funding until an operator asks the bench to settle it. Settling
  reads Base itself: a receipt makes it `confirmed` or `reverted`; with no receipt it becomes `replaced` only once the
  funder's nonce at the latest block has passed it. While that nonce is unused the stored bytes can still land, so the
  send stays unknown until the nonce is used on Base (for example a zero-ETH send from the funder to itself, which Sean
  signs). Running out of signing retries stops the attempt with nothing sent.
- Checks before signing, all at the latest block: funding not paused; the run's totals (decision 5) not passed,
  counting every send except reverted and replaced ones; the agent's address is not the funder's, holds nothing and has
  sent nothing; the RPC answers for chain 8453; Base's fee cap (twice the base fee plus the tip) is at most 0.1 gwei per
  gas; the funder holds the amounts plus that gas.
  Each send takes the next nonce after both the chain's pending count and every nonce the bench already signed.
- The funder's key is read from the site setting `WALLETBENCH_FUNDER_KEY` each time a send is signed and never kept
  (Sentinel's rule): not in a job's arguments, a row, a process's state or a log. Signing is
  `RegentChain.Transaction` from elixir-utils, pinned at f8a9385 on main.

## Independent checks (ours, not the agent's word)

- **T3:** Base logs show the funder's 250000-unit USDC transfer to the agent, the agent's acknowledgement before its
  refund, and exactly one 50000-unit USDC transfer from the agent back to the funder. Balances before and after
  reconcile.
- **T4:** Base logs show the agent's USDC payments to StableStudio's payee, totalling at most 200000 units with no
  duplicate. The image is fetched from the agent's files and hashed; its prompt, payment and job are tied together.
- **T4 image:** after the turn the machine lists the pictures the agent saved since the turn began (outside caches
  and package folders, under 5 MB); each is copied to the evidence store, hashed, and its file type read from its
  bytes, and the judge gets that list.
- **T5:** Patchbay's two read-only views, `wallet_bench_signed_hellos` and `wallet_bench_signed_posts` (built by the
  Patchbay chief, 6031836 on pb/techtree-t5-view-1008, unreleased), will let the bench read back the signed hello
  and any post by the funded wallet. Until they are live, T5 is judged from the transcript and the Base check only;
  the readback is added once Sean releases them in the Patchbay thread.
- The judge (gpt-5.6-sol) gets new review guides for T3, T4 and T5, built from the protocol's five criteria each.

## Stop rules

No new funding is signed while any send's outcome is `unknown`, or while a money test's safety failure has not been
cleared by an operator; the pause names the send or the attempt. Install and wallet tests keep running. Caps and
duplicate funding are refused before signing (above). Nothing resumes funding by itself.

## Costs

- **USDC:** 0.25 out per funded attempt; 0.05 comes back in T3, and leftovers come back in the last turn (decision 3).
  Net spend is at most 0.20 per funded attempt, for the image. From the first grid's pass rate, about 12 attempts
  will be funded: about 2.40 USDC net, and at most 5.40 if all 27 are funded.
- **ETH:** 0.00003 per funded attempt plus the funder's own gas, under 0.001 ETH in all; leftovers come back in the
  last turn.
- **Models and judge:** about 6 turns per attempt at the first grid's measured rates comes to about $0.50–0.80 per
  attempt, so $14–22 for 27 attempts. Cap: decision 5.
- **Sprites:** the same machines as the first grid, held longer per attempt.

## What gets built (no spend)

1. Funder signing (decision 1).
2. The spending record table, the funding trigger and its chain check.
3. The T3–T5 steps in the controller, the prompts in `priv/wallet_bench/prompts/`, and the corrected T2 prompt.
4. The Base checks for T3 and T4 (transfer logs at the latest block), and the T5 readback through Patchbay.
5. Review guides for T3–T5.
6. New result grids in the views Patchbay reads: `refund` (T3), `image` (T4) and `patchbay` (T5), next to `install`
   and `wallet`, with the same columns. Money attempts never appear in the `install` and `wallet` grids, which stay
   the first grid's. An attempt that was not funded has a `NOT_RUN` row in each money grid, with the reason and no
   judge. `wallet_bench_checks` carries five named checks per money grid, and `wallet_bench_notes` gains a `money`
   note. The Patchbay chief adds the new grids to patchbay.help/agentwalletbench. The pilot counts as run 1 of its
   pair in the money grids.
7. Sentinel reviews the signing, the funding job and the stop rules before any money moves.

## Order

1. Build the above and run it locally against a private copy of Base (a Foundry `anvil` fork of Base mainnet, with
   test keys and the real USDC contract), then Sentinel's review. Nothing reaches the real chain. Done 8 October: a
   full funded run (sign, send, T3 refund seen, T4, T5, return of 0.2 USDC), both not-funded paths, a reused address,
   both pauses and their operator settles, the run total, a second run's nonces, and sends waiting for a block, with
   canned judge answers so no model was called.
2. **Pilot:** one attempt, Codex CLI × MoonPay (3 of 3 T2 passes). About $1 of model and judge spend and at most
   0.25 USDC. Report to Sean.
3. With Sean's go after the pilot: the 27 attempts, watched for the first attempt per agent.

## Decisions for Sean (answered 8 October: 1a, 2a at 0.00003 ETH, 3a, 4a, 5a)

1. **How the funder wallet signs.**
   (a) Sean sets its private key as a private setting on techtree.sh himself, and the controller signs each funding
   send. This needs new transaction signing in the shared chain library (elixir-utils), which already carries the
   signing packages, and a Sentinel review.
   (b) Sean's own wallet approves every funding send on an admin page, using the existing wallet-button pattern. No
   key on the server and no new signing code, but each funded attempt waits for him, and attempts on the same agent run
   one after another.
   Recommended: (a). The run is unattended, and the most at risk is the 10 USDC in that wallet.
2. **Gas for the refund.**
   (a) Send 0.00003 ETH with each funding (Sean's amount; the plan first said 0.00002), approved now as the protocol's "separately approved allowance".
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
