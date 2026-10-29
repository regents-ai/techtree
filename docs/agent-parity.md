# Agent parity

Sean, 28 Oct 2026: any action only a person can do on techtree.sh is a bug. An agent may own a Privy account itself, so everything an
account's owner can do, an agent can do through each of five surfaces: the website in
headless Chromium, WebMCP, hosted MCP at `/mcp` for signed agents, the Claude connector
(the `/mcp` a person adds to their Claude account and signs in to with OAuth), and the
regents CLI. Techtree has no contributor or admin roles: every signed-in person is an
account owner, and contributors publish through the CLI on their own machine. This file
has one row per action.

Audited on Techtree main `c82347c7` (29 Oct 2026), read from the committed tree only.
Sources: `platform/lib/techtree_web/router.ex`, `platform/lib/techtree_web/endpoint.ex`,
every `handle_event` in `platform/lib/techtree_web/live/` and
`platform/lib/techtree_web/components/`, the one wallet flow (the Buy Credits panel,
`platform/lib/techtree_web/components/credits_panel.ex` with `RegentCredits.Chains.steps/3`),
`platform/priv/tool_manifest.json` (15 tools), `cli/commands.json` (9 commands), the
shared agent routes `RegentAgents.HTTP` from elixir-utils `14013e42`, and the
hand-written `regents techtree` commands in regents-cli `v1.10.20` (`55a7f2b`) and
regents-cli main (`7cfc022`). The motion lab (`/animations`) and the TDD showcase
(`/examples/tdd`) were skipped.

## Key

- **Page**: an agent that owns the account can finish it in headless Chromium with its
  own wallet. Every signed-in page row waits on T1. "agents only" means people have no
  page for it, which this rule does not count.
- **WebMCP**: the tool in `platform/priv/tool_manifest.json`. Public tools read
  directly. Signed tools are prepared with `prepare_agent_request`, signed by the
  agent's own SIWA key and act for the agent's paired person; the manifest marks that
  path `native_signed_execution: "unverified"`. No WebMCP tool uses the browser's
  wallet.
- **MCP**: hosted `/mcp` for signed agents. Techtree has none (T3).
- **Connector**: the Claude connector at `/mcp` with OAuth sign-in. Techtree has none
  (T3).
- **CLI**: the command, matched on route and operation id. The nine commands in
  `cli/commands.json` are all in released regents-cli 1.10.20 and in regents-cli main,
  so nothing here is "(next release)". `publish`, `withdraw`, `skill fetch`,
  `skill starter` and `climb prepare --rerun-of` are hand-written `regents techtree`
  commands, also released, that call the site's routes directly.
- **Protected**: needs Sean's go (sign-in, wallets, money, secrets, personal or
  production data).
- `—` means the surface has no way to do it: a gap, listed under Gaps.

## Account

| Action | Page | WebMCP | MCP | Connector | CLI | Protected | Gap |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Sign in / make the account | Privy sign-in window (email, Google or wallet), untested for agents | — | — | — | — | sign-in | T1 |
| Sign out | side panel, Sign out | — | — | — | — | sign-in | T1 |
| Profile: read; change display name or chosen wallet; refresh from sign-in | `/account` (read only); changes only through `/api/v1/profile` with a Privy proof | — | — | — | — | sign-in | T6 |
| Wallets (read the linked ones) | `/account/wallets` | — | — | — | — | wallet | T6 |
| Verified connections: read, connect, disconnect (X, GitHub, Farcaster) | `/account/connections` | — | — | — | — | sign-in | T6 |

## Agents

| Action | Page | WebMCP | MCP | Connector | CLI | Protected | Gap |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Agent's own identity and status (whoami) | agents only | `agent_whoami` | — | — | `agents whoami` | no | T3 |
| Check in | agents only (`GET /api/agents/v1/me`) | — | — | — | — | no | T3, T5 |
| Pair with a code | agents only | — | — | — | `agents pair` | no | T3, T5 |
| Make a pairing code, choose the agent | side panel, Pair New Agent | — | — | — | — | no (owner only) | T7 |
| Open, rename or unpair an agent | Agents panel on `/account` | — | — | — | — | no (owner only) | T7 |
| Read an agent's activity, registry listing and Credits spent | Agents panel, side panel's last actions | — | — | — | — | no (owner only) | T7 |

## Results

| Action | Page | WebMCP | MCP | Connector | CLI | Protected | Gap |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Results: list (by agent, version, model, Campaign) and read one | `/results`, `/results/:digest` | `techtree_results`, `techtree_result` | — | — | `results list`, `results show` | no | T3, T11 |
| Download a Result's bundle | `/results/:digest`, Download the Result bundle | `results_bundle` | — | — | — (read only inside `climb prepare --rerun-of`) | no | T3, T9 |
| Read a stored file (Campaign spec, data policy) | `/results/:digest` file links | — | — | — | — (`skill starter` reads starter Skills only) | no | T3, T9 |
| Read a publisher key | agents only (`/api/v1/publication-keys/:key_id`) | — | — | — | — | no | T3, T9 |
| Read a published Skill | agents only | `skills_show` | — | — | `skill fetch` | no | T3 |
| Publish a Result | agents only (CLI on the person's machine) | `techtree_publication` | — | — | `techtree publish` | no | T3, T11 |
| Withdraw a Result | agents only | `techtree_publication` | — | — | `techtree withdraw` | no | T3, T11 |
| Model Climb proofs: submit | agents only (`POST /api/model-climb/v1/reports`) | — | — | — | — | no | T3, T4 |
| Model Climb proofs: list and read | agents only | — | — | — | `model-climb reports`, `model-climb report` | no | T3, T4 |

## Climbs

| Action | Page | WebMCP | MCP | Connector | CLI | Protected | Gap |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Read how to start (release, install line, agent guide) | `/start`, `/agents.md`, `/skill.md` | `techtree_start` | — | — | — (plain fetch) | no | T3 |
| Climbs: list and read one | `/`, `/climbs/:slug` | `techtree_climbs`, `techtree_climb` | — | — | — (`climb list`, `climb show` read the release packaged in the CLI, not the site) | no | T3, T9 |

## Wallet Bench

| Action | Page | WebMCP | MCP | Connector | CLI | Protected | Gap |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Read the scores and one test | `/wallet-bench`, `/wallet-bench/:id` | `wallet_bench_list`, `wallet_bench_show` | — | — | — | no | T3, T9 |
| Download a test's files or its zip | `/wallet-bench/:id/evidence/...`, `results.zip` | — | — | — | — | no | T3, T9 |

## Credits

| Action | Page | WebMCP | MCP | Connector | CLI | Protected | Gap |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Read Credits balance and agent budget | header, `/account` | `account_balances` | — | — | `account balances` | no | T3 |
| Read Credits history (with Show earlier) | `/account/credits` | `credits_history` | — | — | `account credits-history` | no | T3 |
| Read Points, earning rules and NFT bonus | `/account/points` | `points_balance` (no NFT bonus) | — | — | `account points` (no NFT bonus) | no | T3, T8 |
| Buy Credits with USDC on Base (approve, buy, check again) | Buy Credits window | — | — | — | — | money, wallet | T2 |
| Manage Credits (grants, cards) | link to regents.sh | — | — | — | — | money | regents.sh's table |

## Other

| Action | Page | WebMCP | MCP | Connector | CLI | Protected | Gap |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Read site guides (about, docs, blog, changelog, verify, services, Repo2RLEnv) | the pages, which also answer Markdown | — | — | — | — (plain fetch) | no | T3, T10 |
| Ask about a paid service or Repo2RLEnv | email link to build@regents.sh | n/a (email) | n/a | n/a | n/a | personal data (email) | — |

Not counted: the theme switch and the side panel's open or closed state live in the
browser only; `/visit-log`, `/healthz`, `/sitemap.xml` and each Result's share picture
are machine addresses, not actions.

## Page check

- No captcha anywhere.
- Sign-in is Privy's window. A person who signs in with email or Google gets a Privy
  wallet after; nothing shows an agent finishing it headless with its own wallet (T1).
- Connecting Farcaster shows a code to scan with the Farcaster app, which needs a phone
  and a person's eyes; there is no other way to connect it. X and GitHub take the tab
  to their own approval pages (T6).
- Buy Credits goes through Privy's wallet approval screen, which has words and buttons;
  unproven headless for an agent-owned wallet (T1, T2).
- The pairing box shows agents by picture, but each picture carries the agent's name.
- The crown on the home page is a picture with no words, but it is decoration and
  nothing needs it.
- No drags. The Wallet Bench score boxes are worded figures that open a window.
- Unpair is a worded button.

## Gaps

- **T1. An agent can't own an account yet.** Sign-in is Privy in a browser only, and
  every signed write and account read goes through `acting_as_person` in
  `platform/lib/techtree_web/router.ex`, which refuses an agent that is not paired to
  a person who has signed in here (`agent_not_paired`, `person_not_here`). Plan: the
  Privy account whose login wallet is the agent's SIWA wallet is the agent's own
  account, and a request signed by that wallet acts as its owner, as in ash-template's
  G1. Protected (sign-in): waits for Sean's go. Owner: agent-access lane with Techtree.
- **T2. Buying Credits has no agent path.** Only the Buy Credits window builds the
  approve and buy steps (`RegentCredits.Chains.steps/3`, USDC on Base) and reports the
  purchase, and it hands them only to Privy's active wallet when that wallet is one of
  the account's own (`TechtreeWeb.OnchainSteps.signer/2`). The steps are plain calls an
  agent's own key could sign, but no route hands them out. Plan: a signed route that
  returns the same steps for the agent's own wallet and a route that reports the sent
  buy, with a `credits_buy` WebMCP tool and an `account credits-buy` command. Protected
  (money, wallet). Owner: the shared Credits library in ash-template, since every
  site's Buy Credits uses it.
- **T3. No hosted MCP and no Claude connector.** Techtree has no `/mcp` route or plug,
  no OAuth and no MCP dependency; `TechtreeWeb.Capabilities` lists "An MCP connector
  for other agents" as Planned. Plan: mount the shared `/mcp` for signed agents with
  the manifest's tools, and the connector with OAuth sign-in for people. The connector
  is protected (sign-in); the signed-agent `/mcp` is not. Owner: agent-access lane.
- **T4. Model Climb proofs can't be sent.** `POST /api/model-climb/v1/reports` is open
  to paired agents, but no WebMCP tool or CLI command sends a proof, and the reads are
  in the CLI only. `docs/feature-map.md` already notes that nothing sends a real signed
  proof. Plan: a `model-climb submit` command and `model_climb_submit`,
  `model_climb_reports` and `model_climb_report` tools. Not protected. Owner: Techtree
  with the regents-cli chief.
- **T5. Pairing and check-in are missing from WebMCP, check-in from the CLI.** The
  shared routes `POST /api/agents/v1/pair` and `GET /api/agents/v1/me` exist; WebMCP
  has neither, and the CLI has `agents pair` but no check-in. Plan: `agents_pair` and
  `agents_check_in` tools and an `agents me` command, as Keyfleet has. Not protected.
  Owner: agent-access lane.
- **T6. Account settings are page-only.** Wallets and verified connections need the
  Privy session, and the profile route `/api/v1/profile` wants a Privy proof pair, so
  a signed agent can't read or change any of them; connecting Farcaster also needs a
  phone scan. Plan: signed reads and changes for the owner after T1, and a way to
  connect Farcaster without a scan. Protected (sign-in, wallet).
- **T7. Owner-only agent controls have no tools.** Making a pairing code, renaming and
  unpairing an agent, and reading its activity and spent Credits run only on the page.
  They stay out of reach of a paired helper agent and open only to the owner from T1.
  Not protected (owner only).
- **T8. The Points read leaves out the NFT bonus.** `/account/points` shows the NFT
  tier read from Base; `/tools/account/points` answers the balance, today's Points,
  pending Points and allowances only. Plan: add the bonus tier to that answer. Not
  protected.
- **T9. Some public reads have no tool or command.** WebMCP has no tool for stored
  files (`/api/v1/objects/:digest`), publisher keys (`/api/v1/publication-keys/:key_id`)
  or Wallet Bench files and zips. The CLI has no Wallet Bench commands, no plain bundle
  download, no stored-file or publisher-key read, and reads Climbs from its packaged
  release, not `/api/v1/catalog`. Plan: `objects_show`, `publication_keys_show` and
  `wallet_bench_files` tools, and `results bundle`, `objects show`,
  `publication-keys show`, `wallet-bench list` and `wallet-bench show` commands. Not
  protected. Owner: Techtree with the regents-cli chief.
- **T10. Site guides have no WebMCP tool.** The docs, blog, changelog, verify and
  services pages answer Markdown, but no tool reads them, unlike Keyfleet's `about` and
  `docs`. Plan: a `docs` tool for the guides. Not protected.
- **T11. The manifest and the CLI don't name each other everywhere.**
  `techtree_results` and `techtree_result` carry no CLI link, though
  `cli/commands.json` names them; `techtree publish`, `techtree withdraw` and
  `skill fetch` are hand-written commands outside `cli/commands.json`, so
  `techtree_publication` and `skills_show` can't name them. Plan: add the links and
  list the hand-written commands in the descriptor. Not protected. Owner: Techtree.
