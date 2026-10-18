# Techtree feature map

Everything a person or an agent can do on Techtree, and the automated check that
proves it works. `make check` runs every check below; `make browser` runs the browser
ones alone. A line marked **Gap** has no automated proof yet.

Browser checks live in `platform/assets/test/browser/` and run headless Chromium
against a Techtree the tests start themselves, at 1280, 390 and 320 wide. Each page
check fails on a page error, a console error, sideways scrolling, or a press target
too small for a finger (44 px on a touch screen, 24 px with a mouse).

## Public pages (signed out)

| What a visitor can do | Proved by |
| --- | --- |
| Read the home page, with the headline's ending turning and holding still under reduced motion | `pages.spec.ts`, `headline.spec.ts`, `home_live_test.exs` |
| Choose where to start, and copy the install steps when a release is published | `pages.spec.ts`, `start_live_test.exs`, `release_copy_test.exs` |
| Read the docs | `pages.spec.ts`, `docs_live_test.exs` |
| Browse and filter published Results | `pages.spec.ts`, `runs_live_test.exs` |
| Open one Result | `runs_live_test.exs`. **Gap:** no browser check with a published Result |
| See Wallet Bench tests, or why there are none | `pages.spec.ts`, `wallet_bench_live_test.exs` |
| Open one Wallet Bench test and its evidence | **Gap:** no check with a recorded test |
| Check a Result yourself (Verify) | `pages.spec.ts`, `proofs_live_test.exs` |
| Read a Climb | `climbs_live_test.exs`. **Gap:** no browser check with an imported Climb |
| Read the changelog, blog, About, Privacy, Terms, the tdd example and Repo2RLEnv | `pages.spec.ts`, `changelog_live_test.exs`, `pages_test.exs`, `tdd_showcase_live_test.exs` |
| Land on a page that doesn't exist and find the way home | `pages.spec.ts`, `error_html_test.exs` |
| Keep reading Home, Start, Docs, Results and Wallet Bench while the database is down | `outage_pages_test.exs`, `outage_property_test.exs`, `outage_test.exs` |

## Signed in

| What a person can do | Proved by |
| --- | --- |
| Open the side panel from their name: Sign out, Manage Account, Techtree account, their agents, Pair New Agent | `signed_in.spec.ts`, `side_panel_live_test.exs` |
| Use the side panel on a phone without sideways scrolling | `signed_in.spec.ts` |
| See public pages signed out, and stay signed in, while the database is down | `outage_pages_test.exs` |
| Open the Buy Credits window with Approve and Buy wired to the wallet | `signed_in.spec.ts` (the wallet code loads on account pages only) |
| Sign in with Privy | **Gap:** needs a real Privy account; checked by hand |
| Pair an agent end to end | **Gap:** the code is issued in tests; the agent's side is not driven |
| Approve and Buy Credits on Base | **Gap:** needs a wallet and the chain; not run |
| Points, Wallets and Connections tabs with real data | **Gap:** read from the shared account service, which tests don't reach |

## Agents and machines

| What an agent can do | Proved by |
| --- | --- |
| Read `/agents.md`, `/llms.txt`, `/openapi.json` and the bootstrap | `agents_controller_test.exs`, `bootstrap_controller_test.exs`, `open_api_test.exs` |
| Read the catalog, Climbs, objects and publications | `catalog_controller_test.exs`, `climb_controller_test.exs`, `object_controller_test.exs`, `publication_*_test.exs` |
| Publish a Result and report a Climb | `publication_controller_test.exs`, `test/techtree/network/` |
| Use the `regents techtree` commands | `make check-cli` (the command descriptions); **Gap:** commands not run end to end here |
