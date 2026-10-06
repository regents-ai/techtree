# AgentWalletBench on Harbor — plan

Proposal, 6 October 2026. Sean's direction: rebuild the bench on Harbor with 9 agents × 12 wallet tools, each wallet
installed from its own official quickstart, following the reviewed structure for the evals (Sprites baselines,
Harbor task and agent interfaces, optional model-call capture, our own independent verifiers and controls above), and
leaving out the training (RL) part. Nothing here runs or spends without Sean's yes.

Sources: Harbor 0.24.0 (github.com/harbor-framework/harbor, docs.harborframework.com, read 6 October); the 1 October
survey (`harness-wallet-experiment/runs/sprite-run-20261001/`: harness recipes, wallet profiles, DECISIONS.md); the v1
plan (`docs/plan/agent-wallet-bench-v1.md`), whose rulings still apply unless changed below.

## The grid: 9 × 12 = 108 pairs

**Agents (9):** Hermes Agent (H04), Claude Code (H05), Cline (H06), Kilo Code (H07), Pi (H08), oh-my-pi (H09), Codex CLI
(H10), DeepSeek Harness (H12), OpenCode (H13). Every one uses the same model, gpt-6-luna, through the machine's
translator (LiteLLM) with the $5 cap per attempt, approval prompts off and labelled so.

**Wallets (12), with what each needs, from today's quickstarts and the survey:**

| Wallet | Install (official) | Person needed? | Expected result without one |
|---|---|---|---|
| Foundry Cast (W07) | `curl -L https://getfoundry.sh/install \| bash; foundryup` | No | Runs end to end |
| MoonPay (W03) | `npm i -g @moonpay/cli` | No (records its own Terms consent, ruling 2) | Runs end to end |
| Zerion (W13) | `npm i -g zerion-cli` | No (needs a passphrase file or a terminal) | Runs end to end |
| Bankr (W01) | `npm i -g @bankr/cli` | Only for email sign-in; `bankr login siwe --private-key` signs in with the agent's own key and accepts Terms by itself | Runs end to end if that counts like ruling 2 |
| MetaMask (W02) | `npm i -g @metamask/agent-wallet` | Yes (browser sign-in); a pre-made `MM_CLI_TOKEN` avoids it | Needs a person, or a Regent token |
| Turnkey (W17) | Linux release binary of `tkcli` | Yes (organisation + passkey); a pre-registered key pair avoids it | Needs a person, or a Regent organisation |
| Splits (W14) | `npm i -g @splits/splits-cli` | For the API key only (browser, passkey); no signing command | Makes a key; signing is the agent's own |
| Privy (W15) | `npm i -g @privy-io/agent-wallet-cli` | Yes (browser approval each time) | Needs a person |
| Phantom (W06) | `npm i -g @phantom/cli` (now 3.0.0) | Yes (browser sign-in) | Needs a person |
| Circle (W09) | `npm i -g @circle-fin/cli` | Yes (emailed code); cannot sign before a funded first transaction | Needs a person |
| Coinbase Agentic Wallet (W05) | `npx awal` | Yes (emailed code); its wallet server is a desktop app | Does not install on a server (0 of 13 in the survey) |
| Safe CLI (W10) | `uv tool install safe-cli` | No, but it makes no keys and a Safe costs gas to deploy | Cannot do the test as written |

Pairs that need a person are still listed in the results with that outcome (WAITING_HUMAN keeps its own name and is
never drawn as a failure), so the grid always has 108 cells.

## The structure (the reviewed shape)

```
Techtree controller (existing Ash service on techtree.sh)
  rounds and their order, attempts, append-only results, spending, publishing
          │  one Oban job per turn
          ▼
Harbor runner (Harbor 0.24.x, run by that job on techtree.sh)
  agent adapter  +  wallet task (one turn)  +  Sprites environment
          │
          ▼
The attempt's Sprite (fresh copy of the agent's clean baseline, kept for the whole attempt)
  translator (LiteLLM, $5 cap, records every model call)  →  gpt-6-luna

Independent checks (run by the controller, not trusted from the machine)
  Base RPC address read, signature recovery (siwa), judge model with the review guides
```

1. **Controller keeps the rounds.** T1a (install) for every pair, then T1b (install retry) only where the judge sends
   back a technical error, then T2 (make a wallet, say how keys are kept, sign) where an install worked, then the
   signature request where the agent signed but never printed it. Harbor runs one turn at a time; the controller
   decides the next. A person-needed pause is recorded as WAITING_HUMAN, never timed out and retried. Each attempt has
   its own id; results are never overwritten, and a new agent or wallet version is a new comparison.
2. **Agent adapters (Harbor's interface).** Built in and used with our settings: Claude Code, Codex, OpenCode, Pi,
   Hermes, Cline. Written by us as small Harbor agent classes, copied from the survey's working recipes: oh-my-pi
   (from Harbor's Pi adapter), DeepSeek Harness, Kilo Code (from Harbor's OpenCode adapter, since Kilo is built on
   it). Every adapter pins the survey's version (or a newer one recorded per attempt), points at the translator, and
   continues the same conversation for later turns with the agent's own resume flag. Each adapter is checked once on
   a Sprite before it joins the grid (a "qualification" turn).
3. **Wallet tasks (Harbor's task format).** One folder per wallet with the survey's prompts word for word and the
   official quickstart link; no wallet commands are handed to the agent. The task's tests only collect evidence (the
   transcript, the agent's own trajectory, files the checks need); scoring happens outside the machine.
4. **Sprites environment.** Harbor has no Fly.io or Sprites support; we add one environment class (start = restore the
   attempt's Sprite or make it from the baseline, run a command, copy files in and out, stop). It uses the same
   Sprites calls the bench already makes.
5. **Checks stay ours and independent.** The address is read on Base, the signature recovered with siwa, and the judge
   (gpt-5.6-sol, review guides T1 and T2) rules with those facts in front of it. Anything the agent writes is a claim
   to check. Harbor's own reward is not the public score.
6. **Three evidence streams per turn:** the agent's own trajectory (Harbor's ATIF format), the translator's record of
   every model call, and the independent checks. Timings are labelled "through the translator".
7. **Results.** Each result carries every version: agent, wallet, adapter, task, judge guide, Harbor, baseline image.
   A pair's result is a count ("2 of 3 runs met all five checks"), PASS and PASS* counted apart; cost and time are
   compared only across pairs where both sides succeeded. The download for Patchbay keeps the v8 shape.
8. **Before any money test (T3–T5, not in this plan):** a rule that the controller reconciles the earlier
   transaction and the spending record before any retry, and that resetting a Sprite never resets the spending
   record.

## What changes in the existing service

Kept: the Ash resources, AshOban attempt steps, events table, judge, siwa and Base checks, evidence bucket, blanking,
pages. Replaced by Harbor: the per-agent install and turn scripts and their output parsers (Harbor adapters and
trajectories take over), the turn transport to the Sprite (the Sprites environment class). techtree.sh's image gains
Python and Harbor. Hard cutover: the old recipe scripts and parsers are deleted when the Harbor path works.

## Order of work

1. Harbor on techtree.sh, the Sprites environment, and the translator reachable from the Sprite. No model spend.
2. Pilot: OpenCode and Pi × Foundry Cast and one other wallet (see decisions), 3 runs each, including one deliberately
   failing check to prove a failure is caught. About 12 attempts, $3–6.
3. The six built-in adapters and the three new ones, each qualified with one turn. About $1.
4. The full grid, 3 runs per pair, watched for the first attempt per agent; the Sprites cost reported after the first
   10 pairs (HQ 131's condition).

## Cost

Measured on 6 October: $0.11–0.25 per attempt, mostly the judge. 108 pairs × 3 runs = 324 attempts, of which roughly
7 × 9 × 3 = 189 stop early at a person or an install that cannot work: about $40–75 in model and judge spend; cap asked
$110 (as HQ 131).
