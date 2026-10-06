# AgentWalletBench: the full head-to-head grid

Proposal, 6 October 2026. Sean's direction (HQ 126, relayed by HQ, control 4a7ee6a): "we need to get the data for the
full head to head chart from the agents x wallet-CLIs which can be tested on a Sprite". Nothing here runs without
Sean's yes.

## What gets tested

Every agent that ran on a Sprite in the 1 October survey, against every wallet whose wallet test needs no person.

**Agents (13):** Muse Code (H01), Grok Build (H02), Hermes Agent (H04), Claude Code (H05), Cline (H06), Kilo Code
(H07), Pi Agent (H08), oh-my-pi (H09), Codex CLI (H10), DeepSeek Harness (H12), OpenCode (H13), IronClaw (H15), Prime
Agent (H16). Every one installed wallets at the first turn in the survey (IronClaw 10 of 18). All talk to the same
model, gpt-6-luna, through the machine's translator, so the comparison is between agents, not models.

- Cline cannot continue a conversation, so the signature request that follows its wallet test cannot reach the same
  conversation. How the bench handles that is settled on its test machine before Cline's pairs run; until then Cline's
  row shows its installs only.
- IronClaw's own filter and service errors cost it 8 of 18 installs in the survey; those show as IronClaw's results,
  not as gaps.

**Wallets (9):** MoonPay (W03), Foundry Cast (W07), Ape (W08), Safe CLI (W10), Web3Signer (W12), Zerion (W13), Splits
(W14), Tether WDK CLI (W16), 0xSequence Ethkit CLI (W18). In the survey each reached a make-a-wallet result with no
person involved.

**Left out, and why (shown on the chart as "needs a person" or "does not install"):** Bankr, MetaMask Agent Wallet,
Coinbase CDP, Phantom, Circle CLI, Privy Agent CLI, Turnkey and Fireblocks need a person to sign in or accept Terms
before a wallet exists (survey: WAITING_HUMAN on nearly every pair). Coinbase Agentic Wallet did not install on Linux
for any agent.

That is 13 × 9 = **117 pairs**. Each attempt is the survey's two tests: install, then make a wallet and sign a message
(plus the install retry only when the first install fails).

## Runs, time and cost

Measured on techtree.sh on 6 October: an attempt takes 4–13 minutes and costs $0.11–0.25 (Claude Code × Foundry
Cast $0.11–0.15; Claude Code × MoonPay $0.20–0.24, where the signature request adds a judged turn). The tested agent's
model is $0.01–0.02 of that; the judge model (gpt-5.6-sol) is the rest. Other agents may use more model calls; the
machine refuses any attempt past $5.

| Option | Attempts | Expected model + judge spend | Cap asked for |
|---|---|---|---|
| One run per pair | 117 | about $15–30 | $40 |
| Three runs per pair | 351 | about $40–90 | $110 |

Time: one machine per agent, attempts on a machine one after another, 13 machines side by side. Three runs per pair is
27 attempts per machine, about 2–6 hours.

Not yet in these numbers: the Sprites machines' own running cost. The 1–2 October totals Sean is fetching (31a) give
the rate; 13 machines kept for one day should be small next to the model spend, and they are reset after each attempt.

## Results so far on techtree.sh (6 October)

| Pair | Runs | Install: all five checks | Make a wallet: all five checks (plain-file caveat) | Real wallet made and signature verified |
|---|---|---|---|---|
| Claude Code × Foundry Cast | 3 | 3 of 3 | 0 of 3 (stopped short each time) | 0 of 3 |
| Claude Code × MoonPay | 3 | 3 of 3 | 2 of 3 | 3 of 3 |

The MoonPay run marked failed (30420867) made a wallet and a verified signature; the judge faulted its chain answer
because the bench's MoonPay notes wrongly said the wallet covers every EVM chain. Claude Code had quoted MoonPay's own
list, which is right. The notes are corrected (8689cfd), not yet released.

## Work before any run

1. Techtree: add the 12 other agents' recipes (the survey's install, turn and parse scripts, copied unchanged and
   checked once each on a test machine), the 7 other wallets' notes and install prompts (word for word from the
   survey), and a results download for Patchbay's chart (shape below, as the Patchbay UI lane asked on 6 October).
   One Techtree release.
2. Build the 13 agents' machines once each (about 3 minutes each, no model spend).
   On 6 October a machine restarted on its own after a reset, and the bench rightly refused to use it again; replacing
   it was a hand step (retire, request a new one, about 3 minutes). Across 351 attempts that will happen more than
   once, so a refused machine should be retired and replaced by the bench itself (one more AshOban step on the machine
   resource) rather than waiting for an operator.
3. Run, watch the first attempt per agent, then let the rest go. Report the Sprites machine cost after the first 10
   pairs before the rest run (HQ's condition on 131).

## The results download

Versioned, so older releases keep working: `agent-wallet-bench-v8.csv`, `agent-wallet-bench-v8.json` and
`agent-wallet-bench-v8-criteria.csv`.

- **Rows** (`-v8.csv`): the survey's columns in the survey's order (harness_id, harness, wallet_id, wallet, test,
  attempt, outcome, outcome_detail, criteria_true, criteria_false, criteria_open), then `run` (1, 2, 3 for repeated
  runs of a pair) and `attempt_id` (the bench's id, linking to its page on techtree.sh). One row per pair, test and
  run. `attempt` keeps the survey's meaning: `official`, or `follow-up` for a go-ahead prompt. The signature request
  belongs to the wallet test, as in the survey: the T2 row carries the wallet test's final result.
- **Release details** (`-v8.json`): release id, date and rubric version; every harness and wallet in the grid (id and
  name), so an untested pair shows as an empty cell; each test with one plain sentence; every outcome with a one-line
  meaning and whether it counts as tested (NOT_RUN, NOT_REQUIRED, the blocked results and WAITING_HUMAN each keep
  their own name and are never drawn as failures); the setup every row shares (model gpt-6-luna for every agent, stock
  agents, one Sprites machine per agent). It also states how runs combine: a pair's result for a test is a count,
  how many of its runs met all five checks out of the runs that took place (shown as "2 of 3", PASS and PASS* counted
  separately), never turned into a single pass or fail. The rows hold exactly the runs that took place; a run that is
  missing was not run.
- **Checks** (`-v8-criteria.csv`): one row per check: harness_id, wallet_id, test, attempt, run, criterion_id,
  criterion text, result (true, false or open). The judge already records each check, so this costs nothing extra.

## What Sean gets

- The head-to-head grid on patchbay.help, built by the Patchbay UI lane from Techtree's download: pick two agents (or
  two wallets) and compare them pair by pair.
- A plain success count per pair: how many of the runs met all five checks on install, and on make-a-wallet.
- Note on "full success": in the survey no make-a-wallet result met all five checks without a caveat. The best result
  on every wallet that needs no person was "all five checks met, but the wallet's password or key sits in a plain file"
  (PASS*). The chart shows PASS and PASS* side by side so that caveat is visible.
