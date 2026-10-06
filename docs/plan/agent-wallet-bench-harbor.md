# AgentWalletBench on Harbor — plan

Plan, 6 October 2026. Sean's direction: rebuild the bench on Harbor with 9 agents × 12 wallet tools, each wallet
installed from its own official quickstart, following the reviewed structure for the evals (Sprites baselines,
Harbor task and agent interfaces, optional model-call capture, our own independent verifiers and controls above), and
leaving out the training (RL) part.

**Sean's decisions, 6 October ("1 a 2 b 3 a 4 b 5 a 6 a"):**

1. The Techtree chief engineer builds and runs it; the harness-wallet lane hands over.
2. MetaMask, Turnkey, Splits, Privy, Phantom and Circle are listed as WAITING_HUMAN and not run.
3. Bankr's `bankr login siwe --private-key` sign-in, with a key the agent makes itself, counts as needing no person.
4. Coinbase Agentic Wallet ("cannot run on a server") and Safe ("makes no keys") are listed and not run.
5. Cline takes the install tests only; its wallet test is NOT_RUN (it cannot continue a conversation from a script).
6. Up to $10 for the qualification turns (one per agent) and the pilot, then a report to Sean before the full grid.

Results are kept in the bench's own tables in the shared database; Patchbay reads them through read-only views
(Sean, Patchbay thread, 6 October: "it will be saving it in your shared DB, so read from there").

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
| Bankr (W01) | `npm i -g @bankr/cli` | Only for email sign-in; `bankr login siwe --private-key` signs in with the agent's own key and accepts Terms by itself | Runs end to end (decision 3) |
| MetaMask (W02) | `npm i -g @metamask/agent-wallet` | Yes (browser sign-in); a pre-made `MM_CLI_TOKEN` avoids it | Needs a person, or a Regent token |
| Turnkey (W17) | Linux release binary of `tkcli` | Yes (organisation + passkey); a pre-registered key pair avoids it | Needs a person, or a Regent organisation |
| Splits (W14) | `npm i -g @splits/splits-cli` | For the API key only (browser, passkey); no signing command | Makes a key; signing is the agent's own |
| Privy (W15) | `npm i -g @privy-io/agent-wallet-cli` | Yes (browser approval each time) | Needs a person |
| Phantom (W06) | `npm i -g @phantom/cli` (now 3.0.0) | Yes (browser sign-in) | Needs a person |
| Circle (W09) | `npm i -g @circle-fin/cli` | Yes (emailed code); cannot sign before a funded first transaction | Needs a person |
| Coinbase Agentic Wallet (W05) | `npx awal` | Yes (emailed code); its wallet server is a desktop app | Does not install on a server (0 of 13 in the survey) |
| Safe CLI (W10) | `uv tool install safe-cli` | No, but it makes no keys and a Safe costs gas to deploy | Cannot do the test as written |

Pairs that need a person are still listed in the results with that outcome (WAITING_HUMAN keeps its own name and is
never drawn as a failure), so the grid always has 108 cells. After decisions 2–5 the bench runs Foundry Cast, MoonPay,
Zerion and Bankr with every agent (Cline: install only); the other eight wallets carry their fixed result in the
catalog.

## The structure (the reviewed shape)

```
Techtree controller (existing Ash service on techtree.sh)
  rounds and their order, attempts, append-only results, spending, publishing
          │  one Oban job per step (start a turn, collect it, judge it)
          ▼
The attempt's Sprite (fresh copy of the agent's clean baseline, kept for the whole attempt)
  turn.sh → the bench runner (Harbor 0.24.0, as root) → the agent's Harbor adapter → the agent (as `bench`)
  translator (LiteLLM, $5 cap, records every model call)  →  gpt-6-luna

Independent checks (run by the controller, not trusted from the machine)
  Base RPC address read, signature recovery (siwa), judge model with the review guides
```

1. **Controller keeps the rounds.** T1a (install) for every pair, then T1b (install retry) only where the judge sends
   back a technical error, then T2 (make a wallet, say how keys are kept, sign) where an install worked, then the
   signature request where the agent signed but never printed it. Harbor runs one turn at a time; the controller
   decides the next. A person-needed pause is recorded as WAITING_HUMAN, never timed out and retried. Each attempt has
   its own id; results are never overwritten, and a new agent or wallet version is a new comparison.
2. **Agent adapters (Harbor's interface).** Harbor's own adapters for Claude Code, Codex, OpenCode and Pi; Harbor's
   Hermes and Cline adapters with the survey's pinned install (Cline is signed in to the translator at baseline,
   since Harbor's Cline adapter has no address setting); and three written by us from the survey's working recipes:
   Kilo Code (on Harbor's OpenCode adapter, whose output it shares), oh-my-pi (on Harbor's Pi adapter, whose session
   format it keeps) and DeepSeek Harness (its own converter to Harbor's trajectory format). Every adapter pins the
   survey's version and points at the translator. A later turn continues the attempt's conversation: by the session id
   the controller passes from the previous turn for agents that resume by id (Hermes, Kilo, oh-my-pi, DeepSeek), by
   "continue the last conversation" for the others, since each machine holds one conversation. Each adapter is checked
   once on a Sprite before it joins the grid (a "qualification" turn).
3. **The runner lives on the machine.** `priv/wallet_bench/runner/` (Python, locked with uv, Harbor 0.24.0) is part of
   the recipe pack. Baseline builds it into `/opt/awb-runner` and installs the agent through the adapter (Harbor's
   `setup`); each turn, `turn.sh` runs `runner turn`, which hands the prompt to the adapter and copies the agent's own
   output (`stream.jsonl`) and Harbor's trajectory (`trajectory.json`) into the turn folder. The machine itself is
   the Harbor environment: the agent's commands run as `bench` in a login shell, and the turn's wall cap holds across
   all of them (each later clean-up command, such as copying the session out, gets 60 seconds). Harbor's trial and
   job runners and its task format are not used: the controller owns every step, and the prompts stay the survey's,
   word for word, in `priv/wallet_bench/prompts/`. No wallet commands are handed to the agent.
4. **No Harbor code on techtree.sh.** The controller reaches the machine through the same Sprites calls as before;
   techtree.sh's image does not change.
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
pages, the turn folder the collector and judge read (`turn-summary.json`, `transcript.md`, `stream.jsonl`, the
checks' files). Replaced by Harbor, as a hard cutover: Claude Code's install and turn scripts, its output parser and
the machine's transcript writer (`runner transcript` now writes `transcript.md`, `turn-summary.json` and
`tool-calls.json` from the trajectory). The catalog lists all 9 agents and 12 wallets, with the fixed results above;
an attempt can only be requested for a wallet without one, and Cline's attempts end after the install tests.

## Order of work

1. The runner, the adapters and the catalog (built 6 October). Then each agent's baseline on a Sprite. No model
   spend.
2. The nine adapters, each qualified with one turn. About $1 (decision 6).
3. Pilot: OpenCode and Pi × Foundry Cast and Bankr, 3 runs each, including one deliberately failing check to prove a
   failure is caught. About 12 attempts, $3–6 (decision 6). Then a report to Sean.
4. With Sean's go: the full grid, 3 runs per pair, watched for the first attempt per agent; the Sprites cost reported
   after the first 10 pairs (HQ 131's condition).

## Cost

Measured on 6 October: $0.11–0.25 per attempt, mostly the judge. 108 pairs × 3 runs = 324 attempts, of which roughly
7 × 9 × 3 = 189 stop early at a person or an install that cannot work: about $40–75 in model and judge spend; cap asked
$110 (as HQ 131).
