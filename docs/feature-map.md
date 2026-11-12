# Techtree feature map

Everything a person or an agent can do on Techtree, and the automated check that
proves it works. `make check` runs every check below; `make browser` runs the browser
ones alone. A line marked **Gap** has no automated proof yet.

Browser checks live in `platform/assets/test/browser/` and run headless Chromium
against a Techtree the tests start themselves, at 1280, 390 and 320 wide, with no
access to the outside world. In the browser, any outside request fails the test. On the server, test
config points every chain and sign-in service at a closed local port, and each test
fails if the server holds a connection to anywhere but this machine. Each page check fails on a page error,
a console error, sideways scrolling, or a press target too small: 44 px for a
finger on a touch screen, 24 px for a mouse control.

`make live-check` is the one check that reads the live site, after a release: the
same page checks at 1280 and 390 wide, signed out, plus the commit it runs, that
its migrations are all applied, its public documents and the browser tools its
home page offers, and the header's theme switch
(`platform/assets/test/live/live.spec.ts`); then, signed with this Mac's own
agent key through the regents command line, who the agent is and that it is
paired (`agents whoami`), and its person's Points (`account points`). It writes
nothing; the signed reads change only the time the site last saw the agent.

## Public pages (signed out)

| What a visitor can do | Proved by |
| --- | --- |
| Read the home page: one page heading, Evaluate & Climb as the core offer in its opening, its statement, the first Measure item and the first Products entry, and every section from the Stack to the footer, with nothing scrolling sideways | `pages.spec.ts`, `home.spec.ts`, `home_live_test.exs` |
| Watch the newest published Results turn in the opening, one in the middle and its neighbours dimmed beside it, by themselves, from the dots and by a swipe on a phone; Pause and keyboard focus hold them, and with less motion asked for they turn only from the dots | `home.spec.ts` (1280, 390 and 320 wide, with three Results published), `home_live_test.exs`, `marketing.test.ts` (which card sits where) |
| See the opening's moving picture and every other one on the home page drawn over its still; with less motion asked for, or with no WebGPU, each keeps its still | `home.spec.ts`, `home_live_test.exs` (every picture is hidden from screen readers and has its still) |
| See what Techtree is built on, each project under whose it is with a link to its own page (Prime Intellect's Verifiers, Environments Hub and Prime Agent; NVIDIA's Skill2Env, SkillEvaluator, marked Soon, and Nemotron; Nous Research's Hermes): on the home page under each maker's own logo, on the same light plate in both themes, the only logos on the site; as text in the Resources menu and the footer | `home_live_test.exs` (each logo over its maker's projects, no logo elsewhere on the page, and the menu column and the footer list the same projects), `home.spec.ts` (the band reads clearly in light and dark, and every logo loads on one plate), `pages_test.exs` (Verifiers is always named as Prime Intellect's) |
| See the Evaluate & Climb story in two steps, Evaluate (Validate and Deduplicate marked Soon, and the Live run) and Climb (Verdict and Offline check), each card a short loop that plays only while it is on the screen | `home_live_test.exs`, `home.spec.ts` (the cards move on the screen, rest off it, and stay as drawn with less motion asked for) |
| Open one item at a time in each product group (Measure, Prove and Build), by press or from the keyboard, the picture beside it drawing the open item's shape; with less motion asked for the still picture shows the same shape | `home.spec.ts` (keyboard, focus ring and contrast at 1280, 390 and 320), `home_live_test.exs` |
| Follow the On-ramp from your work through Techtree to Prime Intellect, and Book Call or email from it | `home_live_test.exs`, `home.spec.ts` (contrast in light and dark, the buttons' labels on their fills included) |
| See on the home page how many published Results still stand: a withdrawn one leaves the count | `home_live_test.exs` |
| Open each inner page (Start, Results, one Result, Offline check, Wallet Bench, Train, Formal, Repo2RLEnv, the three offers, Docs, Agents, Changelog, Blog and Account) on its dark band: its name as the one page title, its promise, its main action and, outside Account, Book Call; on a wide screen a dot picture of its own beside it | `pages.spec.ts` (one band and one title on each, its words and buttons readable in light and dark), the pages' own server tests |
| See the six products as cards on the home page, each a moving picture over its still that follows the mouse, and open each one's page | `value_cards.spec.ts`: at 1280 wide every panel draws and outlasts the pointer, three to a row, nothing past the screen's edge; with less motion asked for, and with no WebGPU, every card keeps its still. `pages.spec.ts` opens the home page at 1280, 390 and 320. **Gap:** the card test's own phone widths do not run, because Techtree's browser tests have a desktop project only; WebKit and a real phone are not run |
| Choose where to start, and copy the install steps when a release is published | `start_live_test.exs`, `release_copy_test.exs`; `pages.spec.ts` checks the page with no release. **Gap:** no browser check with a release published |
| Read the docs | `pages.spec.ts`, `docs_live_test.exs` |
| Turn the light and dark theme with the switch in the header, by press, Space or Enter, once a press, from a device set to light or to dark; the choice holds over a reload; the header keeps one row at 320 wide | `theme_switch.spec.ts`, `pages.spec.ts`, `home_live_test.exs`; `pages_test.exs` (the first page is drawn in a saved theme, and carries none until one is chosen). The script tests `platform/assets/test/theme.test.ts` and `theme_switch_*.test.ts` (run by `npm test` in `platform/assets`) hold the rules behind it: the cookie and the two themes, how far a press must move to be a drag and where the knob settles, the blocks' paths between moon and sun, and the lights' distance from each page colour. **Gap:** the drawn picture on a real screen is looked at by hand only (the test browser draws the flat switch) |
| Open the header's Products, Agents and Resources menus by press or by key: Tab walks into the open menu, Escape closes it and gives focus back, a press outside closes it, and the mouse moves from one open menu to the next; below a wide screen the same pages open in one Menu sheet; Resources ends with a Stack column of the projects Techtree is built on; the footer lists every page the menus do, the Stack included | `pages.spec.ts` (the menus at 1280, with what a screen reader is told; the sheet at 390 and 320), `home_live_test.exs` (every page carries the same three menus, sheet and footer, and marks the page you are on) |
| See Book Call in the header, the Menu sheet and the Watchdog offer only when a booking page is set; it opens that page in a new tab | `home_live_test.exs`, `service_live_test.exs` |
| Browse and filter published Results | `runs_live_test.exs`; `pages.spec.ts` checks the page with no Results. **Gap:** no browser check with Results to filter |
| Open one Result | `result.spec.ts` (desktop and phone), `runs_live_test.exs` |
| Share a Result's link and see its own picture, while every other page shows the site's | `result.spec.ts` (the page names its picture, which answers as a 1200 by 630 PNG, at desktop and phone widths), `result_share_card_controller_test.exs` (a withdrawal moves the picture's address; an unpublished Result has none; drawing it counts against the request budget). **Gap:** the drawn words are checked by eye, and on the Mac the drawing library draws every word in the system typeface, not the site's |
| See Wallet Bench tests, or why there are none | `pages.spec.ts`, `wallet_bench_live_test.exs` |
| Read the Wallet Bench score grid for each test, and the list | `wallet_bench.spec.ts` (desktop and phone, contrast in light and dark), `wallet_bench_live_test.exs`, `wallet_bench_grid_test.exs`, `wallet_bench_md_test.exs` |
| Open a score's result window, download its full results, close it back to the score | `wallet_bench.spec.ts`, `wallet_bench_live_test.exs`, `wallet_bench_results_test.exs` (each file byte for byte; a changed file stops the download) |
| Read the Wallet Bench scores as data from another site (`/wallet-bench.json`) | `wallet_bench_scores_test.exs` |
| Open one Wallet Bench test and its evidence | `wallet_bench.spec.ts` (passed, failed and running tests at three widths) |
| See the Train comparisons, or that there are none yet: the newest leads with each arm's score, the difference, a line saying what that difference shows (a Skill teaches the answer format) and a mark per task, and every comparison is listed | `pages.spec.ts`, `train_live_test.exs` |
| Open one Train comparison: both arms side by side, wins, ties and losses with the 95% interval, every task, the settings, environment and model, the digests with copy, and the report and traces to download | `pages.spec.ts`, `train_live_test.exs`, `train_controller_test.exs` (each download byte for byte under its own digest) |
| See only Train reports that check out: one whose digest or traces do not match is left out and its page is a 404 | `comparisons_test.exs`, `train_live_test.exs` |
| Ask about private training on their own tasks, by email | `train_live_test.exs` (the Email button's address) |
| Check a Result yourself (Offline check) | `pages.spec.ts`, `proofs_live_test.exs` |
| Read a Climb | `climbs_live_test.exs`. **Gap:** no browser check with an imported Climb |
| Read the changelog, blog, About, Privacy, Terms, the tdd example, Repo2RLEnv, the Verify, Cyber Assist and Watchdog offers, the Verify and Cyber Assist sample reports, and Techtree Formal | `pages.spec.ts`, `public_markdown_test.exs`, `changelog_live_test.exs`, `pages_test.exs`, `tdd_showcase_live_test.exs`, `formal_live_test.exs` |
| Land on a page that doesn't exist and find the way home | `pages.spec.ts`, `error_html_test.exs` |
| Keep reading Home, Start, Docs, Results and Wallet Bench while the database is down | `outage_pages_test.exs`, `outage_property_test.exs`, `outage_test.exs` |
| On the Watchdog offer, press Agent Message beside the email button: its window gives three texts to paste into an agent (CLI, MCP, WebMCP) that name the tool, the command and the address the site publishes; each fits the screen and copies exactly as shown, at 1280 and 390 wide; Escape, the X or a press beside it closes it; a visitor sees no form; the offer's Markdown gives the same three texts; no other offer has the button | `agent_message.spec.ts`, `messages_pages_test.exs` |

## Signed in

| What a person can do | Proved by |
| --- | --- |
| Open the account menu from their name on every page: their agents with Manage, Pair New Agent, Manage Account and Sign out; it hangs under the button inside the screen at 1280, 390 and 320 wide, the page still fits, a press outside or Escape closes it with focus back on the button, and with less motion it appears at once | `signed_in.spec.ts`, `account_menu_live_test.exs` |
| Turn the light and dark theme with the switch in the account menu, at 1280 and 320 wide, by press, Space or Enter; opening the menu moves nothing on the page, turning the switch never changes the menu's size, the choice holds over a reload and a live page change, and there is no second switch in the header | `theme_switch.spec.ts` |
| Pair New Agent in the account menu, and in the Agents list, opens the pairing window over the page they are on, every press, with the keyboard on the agent dropdown and the list of agents open; the menu closes first; Close, the backdrop or Escape close it, Escape closing an open list first; closed, focus goes back to what opened it; Manage Account opens the Account page and closes the menu; every signed-in page holds the one window | `signed_in.spec.ts`, `pairing.spec.ts`, `account_menu_live_test.exs` |
| Choose an agent in the pairing window and copy its message; the window keeps one height whatever is chosen; the agent's picture sits in a low band and choosing moves nothing under it; the list drops in and leaves with a short move, a press during it counts, and with less motion it opens and closes at once; each agent keeps its own code until a new one is asked for; a form sent back with nothing chosen leaves the box as it is | `pairing.spec.ts` |
| See their agents and Pair New Agent on the Agents tab (/account/agents), and their profile on the Account tab, at 1280, 390 and 320 wide, with nothing scrolling sideways | `signed_in.spec.ts`, `account_menu_live_test.exs` |
| See the Train pages signed in at 1280 and 390 wide, the newest comparison leading, its Settings link opening the comparison's settings and every task opening under Every task | `train.spec.ts` |
| On a phone, see the open Menu over the page, with the page and footer out of reach until it closes; on a short phone screen the account menu ends inside the screen and reaches Sign out | `signed_in.spec.ts` |
| See public pages signed out, and stay signed in, while the database is down | `outage_pages_test.exs` |
| On Watchdog, add a site you own, get its DNS record or file to publish, press Check to prove ownership, and add, turn off or remove the addresses on it; only your own list is seen or changed, and an address can't be active until its site is proven | `watchdog_test.exs`, `watchdog_ownership_test.exs`, `watchdog_live_test.exs`; `watchdog.spec.ts` adds a site and an address signed in at desktop and phone widths, sees a bad or repeated site and an address on another site refused under its own field, and removes the site through the site's own confirm window (Cancel keeps it, Remove removes it, the browser's box never opens). **Gap:** no browser check presses Check or turns an address on |
| On the Watchdog offer, open Agent Message and leave the team a message from its form: an empty message is refused under its field when the field is left, a sent one shows its receipt and clears the form, and the window stays open, at 1280 and 390 wide | `agent_message.spec.ts`, `messages_pages_test.exs` |
| As one of the site's admins (`REGENT_CREDITS_ADMINS`), read every message left for the team at /admin/messages, newest first, 50 a page; anyone else, signed in or not, gets the not-found page | `messages_pages_test.exs`; `agent_message.spec.ts` leaves a message and reads it there, connected, at 1280 and 390 wide |
| Sign in with Privy | **Gap:** needs a real Privy account; checked by hand |
| Rename a paired agent from its window on the Agents page, at both widths; a name with hidden characters is refused under the Name field itself; Unpair there asks in the site's own confirm window, opened over the agent's (Cancel keeps the agent, Unpair takes it off the list) | `signed_in.spec.ts` |
| See the three most recently active agents in the account menu | `menu_agents_test.exs` (property) |
| Every agent kind the library knows, Claude Duet included, draws its picture in the agents list and the account menu, so an agent paired on another site never breaks a person's list here | `agent_pictures_test.exs` |
| Pair an agent end to end | **Gap:** the code is issued in tests; the agent's side is not driven |
| See your Points total, today, the actions left with where to do them, and your own place on the leaderboard in the first render; a person with no name shows by their wallet, whose copy icon copies it in full; two people with one name keep a picture each; a signed-out visitor gets nothing from the shared board | `points_page_test.exs` |
| Wallets and Connections tabs with real data | **Gap:** read from the shared account service, which tests don't reach |

## Agents and machines

| What an agent can do | Proved by |
| --- | --- |
| Read `/agents.md`, `/llms.txt`, `/openapi.json` and the bootstrap | `agents_controller_test.exs`, `bootstrap_controller_test.exs`, `open_api_test.exs` |
| Read whether the site is serving at `/healthz` and `GET /api/v1/health`, which also says whether the running release's migrations are all applied (`migrations_applied`) and stays 200 while one waits | `health_controller_test.exs`; the live check reads it true after a release |
| Read the catalog, Climbs, objects and publications | `catalog_controller_test.exs`, `climb_controller_test.exs`, `object_controller_test.exs`, `publication_*_test.exs` |
| Publish a Result and report a Climb | `publication_controller_test.exs`, `test/techtree/network/` |
| Sign in with its wallet and use the three agent addresses (publications, Model Climb reports, `/api/v1/account`) only while acting as its person: unsigned 401, unpaired `agent_not_paired`, person not here `person_not_here`, and an unpairing during the request sends none of the person's data | `agent_wallet_test.exs` |
| A new account, each linked social account and a paired agent offer their one-time Points award once, inside the save that earns it; a sign-in that changes nothing offers nothing, and an agent's award names its wallet | `sign_in_milestones_test.exs` |
| An account, its linked social account and its paired agent from before the Points start earn their one-time Points at the start, once, through this site's own checks, and a later run offers nothing more | `start_awards_test.exs` |
| Read the Train comparisons as data (`/train.json`, or the browser tool `train_comparisons`), each page as Markdown at its own address, and download a comparison's report and traces with their digests as entity tags | `train_controller_test.exs`, `page_tools.spec.ts`, `agent_skills_test.exs`, `public_markdown_test.exs`, `sitemap_controller_test.exs` |
| Read its person's Points with the same figures the page shows, and nothing at all while the shared board is not read | `points_page_test.exs`; the live check reads them as this Mac's paired agent after a release |
| The board every signed-in reader shares: a refused reading keeps the one held, every reading offered reports its size against the limit, a failed first read is marked, an unchanged reading wakes no page, the kind holds one key, and measuring survives the table being away | `shared_reading_test.exs` |
| A signed POST under `/api` keeps its exact bytes, so the sign-in service checks the digest of what the agent signed | `agent_wallet_test.exs` |
| Use a page's signed browser tools through its own browser host (regents browser): each takes only its input, sends nothing with no signer or when the signer refuses, and sends exactly the bytes the signer signed, with the proof and no cookie | `page_tools.spec.ts` at 1280 |
| Be known by one record per wallet, with the first World ID person it accepted kept for good | `agent_test.exs` (property) |
| Keep and read Model Climb reports only for its own person | `report_policy_test.exs`. **Gap:** no check sends a real signed proof through `POST /api/model-climb/v1/reports` |
| Get a funded Wallet Bench test's money back to the funder even when a money test fails | `advance_test.exs` (the return turn is queued in the latest conversation; the attempt then stops with the money test's reason). **Gap:** the judge's 1, 2, 4 and 8 minute retries are not exercised |
| Fund Wallet Bench tests without the funder ever sending more than the run's total, and settle a send whose outcome was lost from Base, where a lagging node can never make a send that landed look replaced | `funding_test.exs`, `funding_cap_concurrency_test.exs` (five at once on real Postgres), `funding_settled_test.exs` (each outcome, and a property for the pinned search), `make check-formal` (the model in `formal/wallet_bench_funding`). **Gap:** `settled/1` is checked against a fake Base node, not Base itself |
| Sentinel's age of the oldest unconfirmed Wallet Bench payment: the oldest funding send still signed or unknown sets its age by flow, 0 when none waits, and a query that fails is logged and skipped; the test configuration names no query, so the site's poller never reads it there | `chain_numbers_test.exs`, `funding_test.exs` |
| A browser that sends Global Privacy Control starts no visit: no `_visit` cookie, no visit on the page or on any call it makes (even one it sends itself), no arrival or step line, and its Sign in press still reaches the site | `platform/test/techtree_web/visit_log_test.exs`, `platform/assets/test/browser/arrivals.spec.ts` |
| A crowd's second of visit lines, 1,500 written at once, reaches the site's output whole, each line once, on a handler of their own; an ordinary line is written once, by the default handler; and the release image writes one JSON visit line for one request | `platform/test/techtree_web/visit_lines_test.exs`, `scripts/release.sh` |
| Call the hosted MCP server at `/mcp` with its own signature: admitted as that agent with no Techtree tools yet; a query string, a page from another site, a batch, a body that is not JSON, two credentials, any other method or address and a 121st request in a minute are refused in the site's shape | `mcp_agent_test.exs` |
| With the Claude connector switched on, a person approves a connected app and pairs it from Pair New Agent; each app pairs on its own with its own code and wallet, a look-alike app or another account's token stays itself, only a check-in moves last contact, and off, the guide, pairing choice and agent-guide lines are gone | `claude_connector_test.exs`, `tool_errors_test.exs`. **Gap:** no real Claude connection or hosted signing service is exercised |
| Leave Techtree's team a private message under a topic, paired or not, and get its receipt, recorded as itself whatever the input says about the sender; the topic, text and reply_to are bounded and a refused message keeps nothing; each sender leaves 10 an hour and each address 30; only the site's admins read messages | `test/techtree/messages/leave_test.exs` |
| Its `operation_id` answers its first message again without using an allowance, also when another call kept it first, and refuses other text or another topic with `idempotency_conflict` | `test/techtree/messages/leave_test.exs`, `messages_api_test.exs` |
| `POST /api/v1/messages/{topic}` and the hosted tool `messages_leave` leave a message as the signed agent, answer a retry with the first receipt through either door, refuse bad input with `invalid_message` and its details, and count one address's 30 an hour together; an unsigned or forged request leaves nothing; the browser tool `messages_leave` has its host sign the message for its topic's address, with the topic out of the body, and asks for nothing without the UUID | `messages_api_test.exs`, `mcp_agent_test.exs`, `router_test.exs`, `page_tools.spec.ts` |
| Claude's connector offers `messages_leave` once its app is paired with the agent permission, and not before | `claude_connector_test.exs` |
| With the connector on, Claude may connect by its published identity (`https://claude.ai/oauth/mcp-oauth-client-metadata`) instead of registering: discovery says `client_id_metadata_document_supported`, consent on this site reads and records the document, the code trades for tokens that work at `/mcp` and refresh, and only consent reads the address; one address may open consent 30 times a minute | `claude_connector_test.exs` |
| Use the `regents techtree` commands | `make check-cli` (the command descriptions); **Gap:** commands not run end to end here |

## Development checks

The shared runner is proved by `scripts/tests/test_check_change.py`: changed and new
files select checks, every ExUnit file runs once, failures stop the run, and owned
processes and databases are cleaned up. `make check-change` runs all configured
platform suites; shared/build/dependency changes select `make check`. The browser
gaps above still apply.
