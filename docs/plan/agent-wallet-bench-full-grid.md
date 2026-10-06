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

Measured on techtree.sh (Claude Code × Foundry Cast, 6 October): an attempt takes 4–13 minutes and costs about
$0.11–0.15, of which about $0.012 is the tested agent's model and the rest the judge model (gpt-5.6-sol). Other agents
may use more model calls; the machine refuses any attempt past $5.

| Option | Attempts | Expected model + judge spend | Cap asked for |
|---|---|---|---|
| One run per pair | 117 | about $15–20 | $30 |
| Three runs per pair | 351 | about $45–55 | $75 |

Time: one machine per agent, attempts on a machine one after another, 13 machines side by side. Three runs per pair is
27 attempts per machine, about 2–6 hours.

Not yet in these numbers: the Sprites machines' own running cost. The 1–2 October totals Sean is fetching (31a) give
the rate; 13 machines kept for one day should be small next to the model spend, and they are reset after each attempt.

## Work before any run

1. Techtree: add the 12 other agents' recipes (the survey's install, turn and parse scripts, copied unchanged and
   checked once each on a test machine), the 7 other wallets' notes and install prompts (word for word from the
   survey), and a results download (one row per attempt and test, the same columns as the survey's CSV) for Patchbay's
   chart. One Techtree release.
2. Build the 13 agents' machines once each (about 3 minutes each, no model spend).
3. Run, watch the first attempt per agent, then let the rest go.

## What Sean gets

- The head-to-head grid on patchbay.help, built by the Patchbay UI lane from Techtree's download: pick two agents (or
  two wallets) and compare them pair by pair.
- A plain success count per pair: how many of the runs met all five checks on install, and on make-a-wallet.
- Note on "full success": in the survey no make-a-wallet result met all five checks without a caveat. The best result
  on every wallet that needs no person was "all five checks met, but the wallet's password or key sits in a plain file"
  (PASS*). The chart shows PASS and PASS* side by side so that caveat is visible.
