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

## Public pages (signed out)

| What a visitor can do | Proved by |
| --- | --- |
| Read the home page, with the headline's ending turning and holding still under reduced motion | `pages.spec.ts`, `headline.spec.ts`, `home_live_test.exs` |
| Choose where to start, and copy the install steps when a release is published | `start_live_test.exs`, `release_copy_test.exs`; `pages.spec.ts` checks the page with no release. **Gap:** no browser check with a release published |
| Read the docs | `pages.spec.ts`, `docs_live_test.exs` |
| Browse and filter published Results | `runs_live_test.exs`; `pages.spec.ts` checks the page with no Results. **Gap:** no browser check with Results to filter |
| Open one Result | `result.spec.ts` (desktop and phone), `runs_live_test.exs` |
| Share a Result's link and see its own picture, while every other page shows the site's | `result.spec.ts` (the page names its picture, which answers as a 1200 by 630 PNG, at desktop and phone widths), `result_share_card_controller_test.exs` (a withdrawal moves the picture's address; an unpublished Result has none; drawing it counts against the request budget). **Gap:** the drawn words are checked by eye, and on the Mac the drawing library draws every word in the system typeface, not the site's |
| See Wallet Bench tests, or why there are none | `pages.spec.ts`, `wallet_bench_live_test.exs` |
| Read the Wallet Bench score grid for each test, and the list | `wallet_bench.spec.ts` (desktop and phone, contrast in light and dark), `wallet_bench_live_test.exs`, `wallet_bench_grid_test.exs`, `wallet_bench_md_test.exs` |
| Open a score's result window, download its full results, close it back to the score | `wallet_bench.spec.ts`, `wallet_bench_live_test.exs`, `wallet_bench_results_test.exs` (each file byte for byte; a changed file stops the download) |
| Read the Wallet Bench scores as data from another site (`/wallet-bench.json`) | `wallet_bench_scores_test.exs` |
| Open one Wallet Bench test and its evidence | `wallet_bench.spec.ts` (passed, failed and running tests at three widths) |
| Check a Result yourself (Verify) | `pages.spec.ts`, `proofs_live_test.exs` |
| Read a Climb | `climbs_live_test.exs`. **Gap:** no browser check with an imported Climb |
| Read the changelog, blog, About, Privacy, Terms, the tdd example, Repo2RLEnv, the Verify and Cyber Assist offers and their sample reports | `pages.spec.ts`, `public_markdown_test.exs`, `changelog_live_test.exs`, `pages_test.exs`, `tdd_showcase_live_test.exs` |
| Land on a page that doesn't exist and find the way home | `pages.spec.ts`, `error_html_test.exs` |
| Keep reading Home, Start, Docs, Results and Wallet Bench while the database is down | `outage_pages_test.exs`, `outage_property_test.exs`, `outage_test.exs` |

## Signed in

| What a person can do | Proved by |
| --- | --- |
| Open the side panel from their name: Sign out, Manage Account, Techtree account, their agents, Pair New Agent | `signed_in.spec.ts`, `side_panel_live_test.exs` |
| Use the side panel on a phone without sideways scrolling | `signed_in.spec.ts` |
| On a phone, see the open Menu over the page and the open side panel over the footer | `signed_in.spec.ts` |
| See public pages signed out, and stay signed in, while the database is down | `outage_pages_test.exs` |
| Open the Buy Credits window and reach Approve and Buy | `signed_in.spec.ts`: the window opens at desktop and phone width, both buttons show, everything in it fits a finger, and the wallet code loads on the account pages and on no other page |
| Sign in with Privy | **Gap:** needs a real Privy account; checked by hand |
| Rename a paired agent from its window on the Account page, at both widths; a name with hidden characters is refused | `signed_in.spec.ts` |
| See the three most recently active agents in the side panel | `panel_agents_test.exs` (property) |
| Pair an agent end to end | **Gap:** the code is issued in tests; the agent's side is not driven |
| Approve and Buy Credits on Base | **Gap:** needs a wallet and the chain; not run |
| Points, Wallets and Connections tabs with real data | **Gap:** read from the shared account service, which tests don't reach |

## Agents and machines

| What an agent can do | Proved by |
| --- | --- |
| Read `/agents.md`, `/llms.txt`, `/openapi.json` and the bootstrap | `agents_controller_test.exs`, `bootstrap_controller_test.exs`, `open_api_test.exs` |
| Read the catalog, Climbs, objects and publications | `catalog_controller_test.exs`, `climb_controller_test.exs`, `object_controller_test.exs`, `publication_*_test.exs` |
| Publish a Result and report a Climb | `publication_controller_test.exs`, `test/techtree/network/` |
| Sign in with its wallet and use the three agent addresses (publications, Model Climb reports, `/tools/account`) only while acting as its person: unsigned 401, unpaired `agent_not_paired`, person not here `person_not_here`, and an unpairing during the request sends none of the person's data | `agent_wallet_test.exs` |
| Be known by one record per wallet, with the first World ID person it accepted kept for good | `agent_test.exs` (property) |
| Keep and read Model Climb reports only for its own person | `report_policy_test.exs`. **Gap:** no check sends a real signed proof through `POST /api/model-climb/v1/reports` |
| Get a funded Wallet Bench test's money back to the funder even when a money test fails | `advance_test.exs` (the return turn is queued in the latest conversation; the attempt then stops with the money test's reason). **Gap:** the judge's 1, 2, 4 and 8 minute retries are not exercised |
| Use the `regents techtree` commands | `make check-cli` (the command descriptions); **Gap:** commands not run end to end here |

## Development checks

The shared runner is proved by `scripts/tests/test_check_change.py`: changed and new
files select checks, every ExUnit file runs once, failures stop the run, and owned
processes and databases are cleaned up. `make check-change` runs all configured
platform suites; shared/build/dependency changes select `make check`. The browser
gaps above still apply.
