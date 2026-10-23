# Changelog

## Website (2026-10-23)

### Changed

- When you sign in with a wallet of your own, that wallet is your main wallet,
  with its ENS name. The Regents wallet made for you at sign-in no longer takes
  its place.
- Pair New Agent in the side panel offers IronClaw where NemoClaw was, with its
  own setup page at /agents/ironclaw. NemoClaw agents still pair as any agent.
- The Hermes pairing message tells your agent to keep the key it pairs with,
  made with the SIWA client or its own wallet.
- USDC sent to Credits some other way than Buy Credits now shows on your
  balance within five minutes of landing on Base, instead of within one. Buy
  Credits is still credited within a minute.
- An agent's window on your Account page lets you rename it. The new name
  shows on every Regent site; names with hidden characters are refused.
- Each agent on your Account page shows its own wallet beside its name, with
  a copy icon, and says when it last checked in.
- Your agents in the side panel lists the three most recently active, then
  those with no activity yet. Manage beside the heading opens your agents on
  the Account page.

### Fixed

- On a shared computer, connecting a wallet after signing out can no longer
  sign the previous person back in. If the earlier sign-out didn't fully
  finish, it is finished first; if that fails, the wallet window doesn't open
  and you stay signed out.
- Opening or downloading a Wallet Bench test's recorded files while their
  storage is slow now shows a page asking you to try again in a minute,
  instead of an error.
- The Pair New Agent box no longer breaks the side panel when the page
  reconnects before you pick an agent. Each agent now keeps its own pairing
  code, so choosing another agent and coming back shows the same code until it
  expires.

## Website (2026-10-22)

### Fixed

- Every connection the site makes to another service now trusts Mozilla's
  current list of certificate authorities. Certificates from the eMudhra
  authorities whose keys were compromised on 20 October are refused.
- Updated a library the home page crown is drawn with to include its three
  security fixes.
- Updated the library that signs the site's sign-in cookies so the site's
  secret key can never appear in an error report.

## Website (2026-10-21)

### Changed

- The home page now makes one promise: improve a Skill and prove it worked. It
  shows the newest Result under the headline, with its verdict, and one Start
  button. Wallet Bench sits further down the page.
- Every Result now says Improved, Regressed or Too close to call, how many of
  its tasks got better, stayed the same and got worse, and how many runs back
  it. A higher score where most tasks got worse is never called Improved. The
  API gives the same verdict and run count.
- The Results page lists every Result by default and says how many it is
  showing out of the total. Each filter starts at All, and choosing a harness,
  version, model, challenge or route narrows the list from there.
- A Result made on an earlier version of its Climb says so, as its Climb's page
  does.
- Every public page also answers in Markdown for agents that ask for it, and
  says so in its page head.
- The short start at /llms.txt is now a short page: what Techtree is, the exact
  install line, how to check it worked, and what you pay. The agent guide at
  /agents.md holds the rest and no longer repeats the Skill file.
- The install line and version in the agent documents always match the
  release Techtree is serving.
- The home page lists all three Climbs.
- The motion lab and the empty blog are no longer part of the public site.
- The Privacy page names every service your browser connects to when you sign in.
- On a wide screen, the Results filter names sit beside their choices instead of
  under them.
- The home page says exactly what Prime Intellect's Verifiers does: it scores
  each Climb's tasks, and every Result is a signed record anyone can check.
- Docs is now one page per guide, with a list of every guide, a side menu and
  Previous and Next links. Each guide also answers in Markdown.
- Wallet Bench shows only the wallet tools that have results, and lists the
  others below the table. Every score under 10 says what cost it points, and
  each test's page opens with its verdict. A test names the agent with its
  version and the wallet tool's version.
- On a phone, the Results and Wallet Bench tables become cards, and the header
  fits on one row with a Menu button.
- Plainer words across Results: Agent instead of harness, Change instead of a
  symbol, and "Signed by the publisher · Files checked · Not rerun by anyone
  else" for what a Result's record shows.
- On Results, rows slide into place when you change a filter.
- The home page crown appears as a still picture first and comes alive once
  your browser has drawn it.
- Agents can find the Techtree skill at /.well-known/agent-skills/index.json,
  and each agent the side panel offers has its own skill at
  /agents/<agent>/skill.md.
- A browser's agent can now download a Result's bundle, read the Skill it
  measured, and read the Wallet Bench scores and each test behind them.

## Website (2026-10-20)

### Changed

- Wallet Bench's recorded files hide any picture shown inside a tested agent's
  own output, as they already hide keys and recovery phrases.
- Wallet Bench's recorded files hide PGP private keys too.
- Wallet Bench's recorded files also hide a recovery phrase typed in capitals,
  numbered, or with its words joined by hyphens, slashes, dots or other marks.
- Wallet Bench refuses a tested agent's files when they would unpack to more
  than the bench keeps.
- Wallet Bench's scores and downloads count toward the same per-minute request
  allowance as the API.
- Publishing a Result is no longer, on rare occasions, refused for naming a
  place on your own machine when it named none.
- Browsers asking for /favicon.ico get Techtree's icon.
- Wallet Bench's recorded files also hide BMP, TIFF, AVIF, HEIC and SVG
  pictures and PDFs shown inside a tested agent's output, in either base64
  alphabet and with indented lines.
- A hidden email address or key at the start of a line no longer breaks the
  recorded file it sits in, and long outputs are checked for secrets quickly.
- A shared Techtree link shows a new picture in the Canopy colours, with the
  Regents cut corners and their Tangerine and Powder Blue marks. Its words and
  techtree.sh now sit in the left part of the picture, which is all X shows on
  a phone, and clear of the bottom-left corner, where X writes the site's
  name. Before, the headline ran past that part and techtree.sh sat at the
  top right, out of view on a phone.

## Website (2026-10-19)

### Changed

- On Wallet Bench, a pass that leaves a plain password or key file on the
  test machine now scores at most 9.0 instead of 10.0, so only a clean pass
  reaches 10. The /wallet-bench.json feed carries the same scores.
- When many people open Wallet Bench's recorded files at the same moment, a
  few are asked to try again in a minute, so the site stays up for everyone.
- Wallet Bench no longer records pictures a tested agent saves on its test
  machine, and a recorded file opens as text.
- A page you opened just before the site updates keeps working while the update
  rolls out, instead of losing its scripts and styles.
- In the seconds after the site's database restarts, a page shows its "can't
  be shown right now" note for one visit instead of an error page.
- On touch screens, links that stand on their own, the side panel's Sign out
  and account buttons, and in Buy Credits the Purchase History link, the amount
  field, the links at its foot and the account page's "Manage Credits on
  regents.sh" link are easier to tap.
- The GitHub star count in the header arrives with the page, so it no longer
  goes missing when GitHub limits a shared network's visits.
- On Wallet Bench, each agent and wallet pair in the list is easier to tap on a
  phone.
- Techtree wears its new green Canopy colours in light and dark: a pale green
  page in light and a deep forest green in dark, with lime buttons and green
  corner marks. The home page's Skill, Harness and Env cards, the boxes to
  paste into your agent's chat, the section bars and the theme switch all use
  the new colours, and no orange or pale blue is left on any page.
- The crown on the home page sits in a deep green field with pale green beams
  in light and lime beams in dark, and the still picture shown where the crown
  can't be drawn shows the same.
- The picture shown when a Techtree link is shared uses the new colours, and
  the browser tab icon and app icons show the Techtree mark in Canopy green.
- When a Techtree link is shared on X, its picture now carries a written
  description for people who can't see it.
- In the side panel's Pair New Agent box, each agent picture sits in one
  frame on white in both themes, and before you choose, the box reads "Choose
  type of agent below to get pairing message."
- Buttons are slimmer, about 40 pixels tall, with their words on one line. On
  touch screens they stay at least 44 pixels each way.
- The lime Sign in and Copy page buttons have darker green corner marks and
  edges, so they stand out clearly on the pale page and on the lime itself.
- Wallet Bench is a score grid: a row for each agent and a column for each
  wallet tool, with Wallet and Install tests to switch between and a list of
  every test beside it. Each box scores the pair's newest result out of 10
  from the judge's nine checks; a red box is a safety failure.
- A score opens its result in a window with every check and its reason, and
  "Download full results" gives one file with the results and every recorded
  log.
- The same scores are at /wallet-bench.json for other sites and agents, each
  linked to its result.

## Website (2026-10-18)

### Changed

- When your device asks for less motion, the home page headline keeps its
  first ending instead of changing every few seconds.
- On phones narrower than 375 pixels, the header shows the Techtree mark
  without the word, so the light and dark switch no longer covers it.
- The Start page's note for when there's nothing to install yet, and the
  Wallet Bench page before any test has run, now say what will appear and
  where to go next.
- The X and GitHub icons at the foot of every page, and the Techtree link on
  the page-not-found screen, are easier to tap on a phone.
- If the site's database stops answering, Home, Start, Docs, Results and Wallet
  Bench stay up for visitors who aren't signed in and say what can't be shown
  right now, instead of the whole page failing or wrongly saying there's
  nothing there.
- During a database outage those pages now answer in about half the time.
- During a database outage, signed-in visitors also see those pages, shown
  signed out. They're still signed in once the database is back.
- Pages other than your Account pages load less, because the wallet code now
  loads only on the Account pages.

## Website (2026-10-17)

### Changed

- The home page headline reads "Improve any agent's Harness / Environment /
  Skills to", and its last words turn through "use less tokens", "perform evals
  stronger" and "create better traces".
- While the Regent sign-in service can't say what your agents have been doing,
  the side panel asks again at most once a minute per agent, and activity from
  the Regents mobile app is shown with the other sites.
- The home page headline reads "Least-token uplift of Harness / Environment /
  Skill".

## Website (2026-10-16)

### Changed

- Every page has Sign in at the top right. Signed in, your name opens a side
  panel with Sign out, Manage Account, your paired agents with where each was
  last active, and Pair New Agent with ten agents to choose from. On a wide
  screen it stays open as you move between pages; on a phone it opens over the
  page.
- The Account page's Pair New Agent opens the side panel, and an agent that
  isn't paired yet is told to ask its person to open Pair New Agent there.
- The home page says what Techtree is for: "The fastest way for a business to
  uplift their agent Harness / Environment / Skill", built on Prime Intellect &
  NVIDIA Nemotron. Each wallet test starts from the same identical cloud server
  on Fly.io Sprites.
- Every Techtree command described here is now checked against the regents-cli
  1.10.12 that people install, so the descriptions match what the commands do.
- An agent whose person hasn't signed in on Techtree yet is told exactly that,
  and to ask its person to sign in here once, instead of being told the account
  doesn't exist. Every Regent account already exists on every Regent site.
- The agent guide says what an agent's check-in carries: its person's Techtree
  account, with display name, ENS name and wallets.
- Main buttons take the shared Regent look: two cut corners, the hover arrow
  and the press motion. Each button shows one arrow, and Copy page has none.

## v0.7.3 (2026-10-13)

### Changed

- Techtree now names regents-cli 1.10.2, with the same Climbs, catalog,
  engines and starter Skills as v0.7.2. Every answer from regents-cli 1.10
  ends with what to do next: the exact command to run, or what your person
  has to do first. A payment that may have gone through is never offered as
  a plain rerun. Install it with
  `uv tool install --python 3.12 regents-cli==1.10.2`, or upgrade with
  `uv tool upgrade regents-cli`. The Hermes plugin is 0.7.3.

## v0.7.2 (2026-10-08)

### Changed

- Techtree now names regents-cli 1.7.3, with the same Climbs, catalog,
  engines and starter Skills as v0.7.1. regents-cli 1.7.3 works with an
  agent key set up by the SIWA agent client's `use-wallet`, and on a Mac it
  keeps the agent key locked with a passkey. Install it with
  `uv tool install --python 3.12 regents-cli==1.7.3`, or upgrade with
  `uv tool upgrade regents-cli`. The Hermes plugin is 0.7.2.

## v0.7.1 (2026-10-07)

### Changed

- Techtree now names regents-cli 1.7.2, with the same Climbs, catalog,
  engines and starter Skills as v0.7.0. regents-cli 1.7 adds
  `regents auth accept-world-id`, which accepts the person who vouched for
  your agent with World ID; every site then shows that person behind the
  agent. Install it with `uv tool install --python 3.12 regents-cli==1.7.2`,
  or upgrade with `uv tool upgrade regents-cli`. The Hermes plugin is 0.7.1.

## v0.7.0 (2026-10-06)

### Added

- A Climb can run on your ChatGPT plan as well as on your own Prime key. Sign
  in with `regents techtree model login`; each Climb page lists the routes it
  runs on, and a run uses one route for both sides. A run on your plan shows
  no dollar cost. Techtree sells no model calls and charges nothing.
- A Climb now scores each task on its environment's own weighted total of
  rewards. Today's three Climbs each still have one reward, so their scores
  mean what they meant before. The Tasksmith Climb page names the Prime
  Environments Hub taskset it runs, `techtree/hf-tasksmith-v1`.
- Published Results carry their Skill, so anyone can fetch it with
  `regents techtree skill fetch` or rerun a Result with
  `regents techtree climb prepare --rerun-of`. Run pages show the Skill and
  say when a Result reruns another.

### Changed

- Techtree now names regents-cli 1.6.0. The Climbs move to
  `hello-world-climb@3`, `frontier-cs-open-ended-climb@3` and
  `tasksmith-climb@2`, with the same tasks, limits and starter Skills. Install
  it with `uv tool install --python 3.12 regents-cli==1.6.0`. The Hermes
  plugin is 0.7.0.

## v0.6.1 (2026-10-04)

### Changed

- Techtree now names regents-cli 1.5.0, which lets an agent add itself to
  the public agent registry on Base with `regents auth register`. Listing is
  optional. Climbs, Campaigns and starter Skills are unchanged. Install it
  with `uv tool install --python 3.12 regents-cli==1.5.0`. The Hermes plugin
  is 0.6.1.

## v0.6.0 (2026-10-04)

### Added

- A new Climb, HF Tasksmith, asks whether a Skill helps an agent make 6 real
  changes to Hugging Face code. Each task brings its own working and grading
  images, and grading happens in a fresh box that sees only the files the task
  names. Six more tasks are kept apart: they are run once, on the winning
  Skill, reported beside its result, and never decide the winner. Run pages
  and the Climb page say when a result comes from those held-out tasks.

### Changed

- Hello World and Frontier-CS move to `@2`. Only the file format changed:
  same tasks, model, limits and starter Skills. Results published for `@1`
  keep their pages.
- Techtree now names regents-cli 1.4.0. Install it with
  `uv tool install --python 3.12 regents-cli==1.4.0`. The Hermes plugin is
  0.6.0.

## v0.5.4 (2026-10-02)

### Changed

- Techtree now names regents-cli 1.3.4, which adds Patchbay's commands for
  known fixes and free fixes. Climbs, Campaigns and starter Skills are
  unchanged. Install it with
  `uv tool install --python 3.12 regents-cli==1.3.4`. The Hermes plugin is
  0.5.4.

## v0.5.3 (2026-10-01)

### Changed

- A result now shows what the model provider reported the run cost, added
  up over every model call on both sides, in place of a figure worked out
  from a price list. If the provider did not report a cost for every call,
  no total is shown and the result says why. Install regents-cli 1.3.3 with
  `uv tool install --python 3.12 regents-cli==1.3.3`. The Hermes plugin is
  0.5.3.

## v0.5.2 (2026-10-01)

### Changed

- A run now stops once its spend reaches the most its Campaign allows. While
  it runs, Techtree adds up the cost the model provider reports for each
  finished task, and when the total reaches the Campaign's maximum it stops
  both sides. A stopped run has no score. Tasks still under way when it stops
  can add a little to the total. If the provider does not report a cost, the
  run stops too. Runs are no longer turned away before they start. Install
  regents-cli 1.3.2 with
  `uv tool install --python 3.12 regents-cli==1.3.2`. The Hermes plugin is
  0.5.2.

## v0.5.1 (2026-10-01)

### Changed

- A new Frontier-CS starter Skill, `frontier-cs-starter-v4`. It asks the
  agent to plan a few methods before coding, build its own test inputs and
  scorer, and keep improving its answer until most of the time is used. In
  two test runs with GPT-6 Luna it scored 0.542 on average against 0.508
  without a Skill, higher on 7 of the 9 problems that could be scored. It
  replaces `frontier-cs-starter-v3`. Install regents-cli 1.3.1 with
  `uv tool install --python 3.12 regents-cli==1.3.1`. The Hermes plugin is
  0.5.1.

## v0.5.0 (2026-09-30)

### Changed

- Both Climbs now run GPT-6 Luna (`openai/gpt-6-luna`) at high reasoning,
  on Hermes v2026.9.24. Install regents-cli 1.3.0 with
  `uv tool install --python 3.12 regents-cli==1.3.0`. The Hermes plugin is
  0.5.0.
- The Frontier-CS starter Skill is now `frontier-cs-starter-v3`: it sets out
  GPT-6 Luna's reply and attempt limits and when to think hard. It
  replaces `frontier-cs-starter-v2`.

## v0.4.5 (2026-09-30)

### Changed

- On [Results](https://techtree.sh/results), each filter row has a link that
  opens in a new tab: the harness's project page, the model's page on
  OpenRouter, and the Climb's own page.

## v0.4.4 (2026-09-30)

### Changed

- The [Verify](https://techtree.sh/verify) page now explains, in plain words,
  how a Result is made: Nous Research's Hermes runs the tasks,
  [Prime Intellect's Verifiers](https://github.com/PrimeIntellect-ai/verifiers)
  scores every task, and the record is signed. It then says what checking a
  Result tells you, what it can't, and why it matters.
- The theme button in the header has slightly rounded corners.
- The agent guide at [/llms.txt](https://techtree.sh/llms.txt) links
  Autolaunch's source at [regents-ai/autolaunch](https://github.com/regents-ai/autolaunch).

## v0.4.3 (2026-09-30)

### Changed

- The Hermes plugin now installs from the `plugin` folder of
  [regents-ai/techtree](https://github.com/regents-ai/techtree/tree/main/plugin):
  `hermes plugins install regents-ai/techtree/plugin --ref <commit> --enable`,
  with the exact commit on the Start page. The plugin itself is unchanged
  (0.4.1). The separate `techtree-hermes` repository is archived.

## v0.4.2 (2026-09-30)

### Changed

- The About page now says what Techtree does, what makes it different, who
  uses it, who builds it, and its key facts. The agent guide at
  [/llms.txt](https://techtree.sh/llms.txt) carries the same key facts.
- The theme button in the header is smaller, sits apart from the GitHub
  button, and shows the other theme's colours when you point at it.
- Tables on the About, Contact, Privacy and Terms pages wrap long values to
  fit a phone.

## v0.4.1 (2026-09-29)

### Added

- An agent can pair with its person's Regent account here, signing with its
  own key: `POST /api/agents/v1/pair`, then check in with
  `GET /api/agents/v1/me`. One pairing works on every Regent site; the
  [agent sign-in guide](https://siwa.regents.sh/skill.md) shows how.

### Changed

- Install regents-cli 1.2.1 with
  `uv tool install --python 3.12 regents-cli==1.2.1`. A Result's summary now
  names the Skill that changed, for example "No tested Skill → frontier-cs-v2".
  The Hermes plugin is 0.4.1.
- The Frontier-CS Open-Ended Climb page gives both runs of its starter Skill
  and links the second run's Result.

## v0.4.0 (2026-09-29)

### Added

- A second Climb, the Frontier-CS Open-Ended Climb
  (`frontier-cs-open-ended-climb@1`, experimental): ten open-ended programming
  problems from [Frontier-CS](https://github.com/FrontierCS/Frontier-CS),
  created with [FrontierSmith](https://github.com/FrontierCS/FrontierSmith),
  where no perfect answer is known. For each problem the agent writes a C++17
  program, and the problem's own checker scores it from 0 to 1.
- Each Climb now has its own starter Skill:
  `regents techtree skill starter --climb <climb>`.
- The home page lists every published Climb.

### Changed

- Install regents-cli 1.2.0 with
  `uv tool install --python 3.12 regents-cli==1.2.0`. The Hermes plugin (0.4.0)
  prepares the starter Skill of the Climb it is running.

### Removed

- The source of the old `techtree` command is gone from this repository. It is
  developed in [regents-cli](https://github.com/regents-ai/regents-cli).

## v0.3.1 (2026-09-29)

### Changed

- Techtree's command-line tool is now part of
  [regents-cli](https://github.com/regents-ai/regents-cli). Install it with
  `uv tool install --python 3.12 regents-cli==1.0.0`; every command that was
  `techtree …` is now `regents techtree …`.
- The Hermes plugin (0.3.1) runs `regents techtree` for every step. It stops
  after the first comparison: it no longer proposes a revised Skill or runs a
  second comparison. Its 13 tools keep their names and answers.
- The Hello World Climb now tests Hermes v2026.7.20 (it was 0.19.0), and was
  checked again on it: with the starter Skill the agent solved 23, 22 and 24
  of 36 tasks across three runs, and none without it.

### Removed

- Building tasks from a repository on your own computer, and running an
  exported Skill environment again from its folder.

## v0.3.0 (2026-09-27)

This release folds in everything that was listed for 0.2.2, which was never
released on its own.

### Added

- Create an environment from a Skill: a set of checked tasks written from one
  Skill of yours, that you review, accept and can hand to someone else. Each
  step shows what it will do and waits for your yes before any model is
  called, and every step keeps its record whether it succeeded or not. No
  comparison is needed to finish; comparing Skills on the tasks is a separate,
  optional step.
- `techtree forge inspect-skill PATH` looks at a Skill without running any of
  it. It lists every file, says which ones it can carry and which it cannot
  and why, and follows what `SKILL.md` names. When a file the Skill needs
  cannot be carried, or a link points to a missing file or outside the
  Skill's folder, it refuses by name before any model sees the Skill. A
  reduced copy you make is recorded as a new Skill that names the one it came
  from. Tools a Skill asks for are recorded as its request, never granted.
- `techtree forge plan` prepares the planning of tasks and calls nothing;
  `techtree forge plan-start` shows exactly what leaves your computer (the
  Skill's files, word for word, inside Techtree's planning instructions), the
  provider and model, and the limits, then makes one call on your yes. The
  planner has no tools. It first states what the Skill claims to improve and
  what would show it, then proposes tasks that each test one claim as a
  positive case, a boundary case or a counterexample. A plan is tried once;
  trying again is a new plan with its own approval.
- `techtree forge correct-proposal` records your corrections to the claims and
  tasks as a new proposal; the original is kept.
- `techtree forge construct` prepares the building of the tasks and calls
  nothing; `techtree forge construct-start` makes one call per task on your
  yes. Every package is then checked on your computer with Docker and the
  network off: its tests must fail when nothing is done, succeed for its
  solution and for another correct solution, and fail for a deliberately
  wrong one. A failed, refused or timed-out call is kept and the other tasks
  go on; nothing is retried on your account.
- `techtree forge correct-task` checks a copy of a built task that you edited
  by hand, the same way a written task is checked, and records it as your
  correction beside the original, with every file you changed.
- `techtree forge collect` and `techtree forge accept` show every proposed
  task with how it went, then freeze the tasks you accept as one collection.
  Accepting splits the tasks into a part an improving agent may study and a
  held-out part it never sees; which task goes where follows from the tasks
  themselves, not from anyone's choice. Any later change is a new version,
  accepted again. `techtree forge verify` checks that a collection is exactly
  what was accepted.
- `techtree forge run --collection ID` runs an agent on an accepted
  collection, with or without a Skill, and gives you each task's outcome with
  no comparison needed. The agent gets a shell, files, code and Skills, and
  no network. What the agent left in its working folder is recorded before
  any test runs; a link that leads out of that folder, or output past the
  kept limit, is a failure of its own and is not graded.
- `techtree forge compare` works on a collection. It names the Skill the tasks
  were written from and the Skill on each side, even when two of them are the
  same file, says "Evaluation on Skill-derived tasks", and gives a verdict for
  the whole collection and for the held-out tasks alone. A Skill's earlier
  version can stand on the baseline side, so you can compare old against new.
- `techtree uplift` works on a collection: the agent that revises the Skill
  sees only the studied tasks, and the revision's verdict is worked out on the
  held-out tasks alone.
- `techtree forge export COLLECTION --to FOLDER` writes a private copy of an
  accepted collection for someone else, and `techtree forge verify-export`
  checks it from its folder alone. The copy leaves out the Skill's text, the
  logs from writing the tasks, and everything else on your computer. It
  includes the tests and reference solutions, so give it only to people who
  check or run the tasks. The check prints the collection's fingerprint: the
  copy is the same collection only if that matches the one the sender gave
  you.
- `techtree forge import FOLDER` brings an exported collection into another
  Techtree and checks every task again there, so `forge run` and
  `forge compare` work on it unchanged. The export's own README lists what
  you need and the exact commands.
- The Results page answers "Keep this Skill change?". It leads with improved,
  regressed or not enough evidence, and on which tasks, then shows one task of
  each kind and the Skill change itself. Three badges say what is known: the
  files are verified, who reported the numbers, and that it has not yet been
  reproduced by anyone else. A panel shows how to run it again: what you
  need, the exact commands, and the limits per try and per run in model calls
  and tokens. Results published before this release are assessed the same
  way; the two already published were checked and both hold.
- Every published Result's page offers its bundle for download, and
  `techtree proof verify` checks the downloaded file directly, including that
  it is the bundle the Result names.
- [The tdd example](https://techtree.sh/examples/tdd) shows one real
  comparison made with this release: Matt Pocock's `tdd` Skill (MIT licence)
  against no Skill, on six tasks written from it. With the Skill the agent
  scored full marks on 6 of 6 tasks, without it on 3 of 6; on the three
  held-out tasks alone the Skill won 1 and tied 2. The page shows the claims,
  the tasks, the Skill, what limited the runs and what they cannot show, and
  links to the exported tasks so anyone can run them again. The home page
  links to it.
- Every page offers five read-only tools to an agent working in a browser
  that supports WebMCP: the Start guide, the list of Climbs, one Climb, the
  list of Results and one Result. Each reads a page a person can already see.
  This is already live on techtree.sh.
- The home page, About, Contact and Privacy pages and `/skill.md` answer in
  Markdown when an agent asks for it. The site now has `/openapi.json`, a
  sitemap, and About, Contact and Privacy pages linked from the footer. This
  is already live on techtree.sh.

### Changed

- The home page, Start, Docs and the agent guide now lead with testing your
  own Skill: make tasks from it, run them without it (or with its earlier
  version) and with it, and compare. The home page's main action is one line
  to paste into your agent's chat; the install command is one click further.
  Start offers three paths, each with what it needs, how long it takes and
  where your data goes: test your Skill, take a quick look with the Hello
  World Climb, or build tasks from your repository. The Climb is introduced
  only after a controlled comparison is explained.
- Every capability on the site is marked Available now, Experimental or
  Planned from one list, and the only version labels come from the active
  release. Pages that described the v0.1 and v0.2 plans, or said the site is
  built on NVIDIA NeMo, no longer do.
- Hermes users get the same instruction as coding agents; the plugin's own
  commands are described in the Hermes section of Docs.
- The Repo2RLEnv service leaves the top menu and gains a "Tell me when it
  opens" email link.
- `techtree doctor` now says whether the `techtree` Hermes profile is signed
  in, and to which providers, checked the same way `techtree forge run` checks
  before it starts. A missing or signed-out profile is reported with the exact
  command that resolves it.
- The host Hermes this release is tested on is 0.21.3, and 0.21.3 is now the
  minimum: experiments run in a Hermes profile of their own, and that is the
  Hermes it was verified on.
- The published package is built the same way every time, from a clean copy of
  the release commit, so what is on PyPI is exactly what was approved.
- `techtree forge build` and `techtree forge status` now say in plain words
  what happened to every task and every candidate commit: each generated task
  reads "qualified" or "rejected" with the reason a person can act on, and one
  summary line says how many tasks qualified and why the other commits were
  skipped over. A build that leaves fewer than three usable tasks carries a
  `forge_few_tasks` warning, since a comparison on so few can say how one
  attempt went, not whether a Skill helps; the build stays usable.
- Qualified for real on three public repositories with Docker and no model:
  `pallets/click` (Python, 1 task from 10 recent commits), `pallets/jinja`
  (Python, 4 tasks from 150 recent commits; the 30 most recent yielded none,
  being merges and short messages) and `spf13/cobra` (Go, 1 task from 30
  recent commits, with a Go image supplied through `--dockerfile`). Go test
  output that is not valid text stops the task generator (seen on
  `pelletier/go-toml`); that limit sits in the pinned generator and is
  recorded, not worked around. The click task qualified again, with the same
  checks, under this release's records.
- A comparison now gives a verdict a person can act on: inconclusive, mixed,
  improved, regressed or no difference, by fixed rules applied in that order,
  with fewer than three graded pairs always inconclusive. The report names
  every task the Skill lost, even when the average went up, and says for each
  task whether it went both ways across attempts; with one attempt per task it
  says plainly that consistency was not measured. The terminal output and the
  machine-readable record carry the same three facts.
- Every task image, for repository tasks and Skill tasks alike, is now built
  with the network off. Skill tasks may only start from base images the
  release lists, pinned to an exact version.
- Every container Techtree starts for a task now has a cap on its number of
  processes, keeps only one of the special permissions a container normally
  has, and cannot gain new ones.
- `techtree publish` lists every file that will leave your computer before it
  asks, and sends exactly those bytes. Techtree does not search what it sends
  for passwords or keys; it shows you every file instead.
- Forge builds, runs, comparisons and revisions made with 0.2.1 or earlier stay
  on disk untouched but are no longer read: Techtree names the file and says
  its format is not supported. Build the tasks again with this release.
- Security reports go by email or GitHub private reporting, and `SECURITY.md`
  names both. The Privacy page says that deleting your sign-in account does not
  remove Techtree's copy of your profile, and how to ask for that by email.
- Buttons, the Copy page menu and the task list on a Result page move a little
  when pressed or changed; a keyboard press or a reader who asked for less
  motion gets the change at once.
- The README describes the parts of this repository and which CLI, plugin,
  catalog and site versions go together.

### Fixed

- A Result's page used to show the verdict its report stated. The site now
  works the averages, the change and the decision out again from the task
  scores, by the same exact rule the CLI uses, and refuses a published report
  whose numbers disagree with its own task scores.
- Why a task run left no score is now set by Techtree, not by a file the
  task's tests could write. This also corrects the "verifier timed out" label
  on repository runs.
- A stray byte that is not valid text in a command's output no longer stops a
  task check.
- A declined or unanswered prompt now says how to go ahead, and the next steps
  name `--home` when you use one.
- Updated the website's Ash dependency to include a security fix.

### What this release does not yet show

- **The guided repository walk-through planned for 0.2.2 is not in this
  release.** One command that would build tasks from your repository, run
  both sides and compare, with a single approval, was deferred when Skill
  environments became the priority. It was not shipped, and its acceptance
  runs (a real model run on `pallets/click`, then a second walk-through on a
  fresh Linux computer) never took place. The Hermes plugin tools that would
  have read its results back are not included either. On a repository, use
  `techtree forge build`, `forge run` for each side, and `forge compare`, one
  step at a time.
- **Qualification yield and rejected tasks, from the real runs.**
  - The first Skill environment, from a corrected copy of Techtree's own
    Hello World starter Skill: the planner proposed 1 task of the 3 allowed.
    Its first build qualified but was not collected, because its instruction
    restated every step of the Skill, so an agent without the Skill had all
    it needed. The building instructions now forbid that; no check catches it
    automatically. The rebuilt task qualified and was accepted as a one-task
    collection.
  - The `tdd` example, first attempt: 7 claims and 7 tasks proposed. Of 7
    built tasks, 2 qualified. Three were rejected because their tests kept
    copies of the starting files, which cannot be told apart from leaked
    answers; one because its other correct solution did not score 1; one
    because its reference solution did not make its tests succeed. Building
    the 5 again gave 4 more; one was rejected again for its other correct
    solution. A review then found all 6 collected tasks unfair, because some
    gave the tested choice away and some graders refused correct answers. None
    was accepted, and the planning and building instructions were changed.
  - The `tdd` example, second attempt: 5 claims and 5 tasks proposed. A person
    removed 2 tasks and added 4, making 7. All 7 built tasks qualified. A
    person's review then corrected 5 of them by hand (6 corrections in all)
    and left out 1, `percentage-only`, which had qualified; the reason it was
    left out was not written down. The accepted collection has 6 tasks, 3 of
    them held out, testing 4 of the 5 claims.
- **Authoring attempts and interruptions.** Every real planner and creator
  call was announced and approved before it ran, on `gpt-5.6-sol` from
  `openai-codex` through the `techtree` Hermes profile. In all: 3 calls for
  the first environment (one planner, two creator), 13 for the `tdd` first
  attempt (one planner, seven creator, five creator again) and 8 for the
  second (one planner, seven creator). No real call was interrupted, failed
  or ended with an unknown outcome, so recovery from an interrupted call has
  been shown only with stand-ins and with a stopped walk-through that called
  no model. The second `tdd` attempt took from 20:44 UTC on 26 September
  (planning) to 01:17 UTC on 27 September (acceptance), including the
  reviews and hand corrections above; that is the project's own time, not an
  outside creator's.
- **No one outside the project has yet created or evaluated an environment
  with 0.3.0.** The release was meant to wait for one outside creator to make
  an environment from their own Skill and a different outside evaluator to
  verify and run the export on a fresh computer. Neither has happened, so
  there is no outside outcome, completion time or count of the help they
  needed to report. Every environment so far was made by the project from a
  Skill it chose.
- **Skill material Techtree cannot carry.** Only `.md`, `.txt`, `.json`,
  `.yaml` and `.yml` files that are UTF-8 text are carried, up to 256 KiB each,
  64 files and 2 MiB in all. Scripts, images, other binary files and files
  with no extension (a plain `LICENSE`, for example) are not; neither are
  hidden files, links or special files. A Skill that needs such a file, links
  to a missing file or outside its own folder, or whose `SKILL.md` header uses
  more than plain `key: value` lines and one level of `metadata`, is refused
  before any model call. Of the eight Skills the project keeps for its own
  work, only one could be used as it was; the other seven link outside their
  own folder. Tasks can only start from Python 3.12 (`python:3.12-slim`) and
  never reach the network, so a Skill whose tasks need another language,
  service or live download cannot become an environment yet.
- **Provider usage that has no price.** Every real call was on a provider
  subscription that Hermes reports as "included", so Techtree records no
  price for it, and it never counts such a call as free. Nothing is quoted in
  advance, and the site gives limits in model calls and tokens only. What the
  calls used: the first environment, 14,936 tokens; the `tdd` first attempt,
  165,583 tokens; its second attempt, 108,375 tokens to plan and build; the
  `tdd` comparison, 41 model calls and 338,454 tokens without the Skill and
  95 model calls and 1,026,256 tokens with it.
- **Checks not yet made.**
  - No outside creator or evaluator, as above, and no run of 0.3.0 on a
    fresh computer.
  - Skill tasks have been built and checked only on Docker running
    linux/arm64 (a Mac). `techtree forge import` refuses tasks built for
    another platform, so the `tdd` example's tasks can only be imported where
    Docker runs linux/arm64.
  - The `tdd` example's export was checked from its folder but was not
    imported into a second Techtree. Importing an export and running and
    comparing it there has been shown only with stand-ins in the automated
    checks.
  - Revising a Skill on a collection, with its held-out verdict, has not been
    run with a real model.
  - The `tdd` example ran each task once on each side, so consistency across
    attempts was not measured, and the same model wrote the tasks and was the
    agent tested on them.
  - The real Skill environment runs used Hermes 0.21.4, which is newer than
    the 0.21.3 this release records as tested.
  - The automatic checks show that each task's tests agree with its own
    sample solutions, not that they accept every correct answer; read each
    task, and correct any with `techtree forge correct-task`, before
    accepting.
  - Each task carries a written rubric, but nothing scores it; only the
    task's tests decide.
  - An acceptance is a record on your own computer, not a signature; someone
    who rewrites a collection and its acceptance together is not caught.
  - The Hermes plugin has no tools for creating an environment; in Hermes,
    the agent follows the steps on techtree.sh/skill.md in the terminal.
  - Only Climb runs can be published. Results from a Skill environment stay
    on your computer.
  - The browser tools need a browser with WebMCP switched on; ordinary
    Chrome does not offer it without changing a setting.
- **Known limits.**
  - A try in `techtree forge run` is bounded by time only: the agent gets its
    task's own limit (30 minutes for every task so far) and Techtree stops it
    2 minutes later. Nothing limits its model calls or tokens.
  - A task's part is inherited forward only: a task held out in an accepted
    collection stays held out, even if a later collection for another Skill
    studies a task with the same files. Tasks whose files differ only
    slightly are not recognised as the same task.
  - While a task runs, Techtree does not yet cap how much it prints or writes,
    so a task written to do harm could fill memory or disk before its time
    runs out. Run tasks from people you trust, and read them first.
  - Checking an export shows that it agrees with its own records, not where
    it came from. Importing one downloads its base images from the network;
    after that every task is built and run with the network off.
  - An export cannot include the Skill's text yet, even when you have the
    right to share it.

### Not in this release

- An MCP connector for other agents, hosted building and running of
  environments, private hosting, managed creation, payments and bounties,
  NVIDIA NeMo Fabric and Relay support, automatic Skill improvement, and
  training remain planned.
- Publishing a Skill environment, or a comparison made on one, to
  techtree.sh.

## v0.2.1 (2026-09-19)

### Added

- `techtree forge run` runs one arm of an experiment on the tasks a forge build
  qualified, with your own Hermes and your own provider sign-in: the baseline
  arm without the Skill, the candidate arm with it. Before anything runs it
  shows what will run and asks. Every attempt is recorded with its patch, its
  test verdict, the usage Hermes reported, and — when there is no verdict —
  why: the agent ran out of time or did not finish, the tests ran out of time,
  or left nothing readable. Nothing is scored as zero for want of evidence, and
  no attempt is retried on your account. `techtree forge status` reads a run
  back.
- Experiments run in a Hermes profile of their own named `techtree`. Create it
  with `hermes profile create techtree --no-alias` and sign it in once with
  `hermes -p techtree auth add PROVIDER`. Techtree copies no sign-in and reads
  none; around every attempt it empties that profile of everything else, so each
  attempt starts fresh. If the profile is missing or signed out, `forge run`
  says so and names the command before anything starts, and `techtree doctor`
  reports whether the profile exists. Two experiments never share it at once.
- An experiment records the whole version line your Hermes reports, including
  its build date and source commit, so a Hermes that was updated between two
  runs is never compared as if it were the same.
- `techtree forge compare` pairs a baseline run with a candidate run, task by
  task, and writes a self-contained HTML report you can open from disk beside
  the machine-readable record. It says whether the Skill won, lost or tied on
  each task, what each arm used in time, model calls, tokens and reported
  cost, what the two arms were allowed to differ in, and how far the evidence
  carries. A pair without a verdict on both sides is shown as unresolved,
  never counted as zero, and the summary says "Partial" until every planned
  pair has one. Comparing calls no model.
- A forge comparison can be revised once through `techtree uplift`, the same
  way a Climb run can. `uplift context` on a comparison writes what a reviser
  may read: the task instructions, both arms' results, and what the Skill is
  meant to improve — never the reference fix, the tests, or either arm's
  patch. `uplift skill-source` reads the Skill a candidate run measured back
  from the run's own verified copy. `uplift prepare` takes one revised Skill,
  keeps everything else about the experiment the same, refuses an unchanged
  Skill or a changed Hermes, and screens the revision against every task's
  reference fix and tests, recording each shared line rather than refusing.
  `uplift start` shows what will run, asks, measures the revision against the
  same baseline, and records whether it improved, regressed or matched. The
  revision is kept either way, and is never measured twice. `techtree forge
  status` reads a revision back.
- A candidate run keeps its own copy of the Skill it measured, and every
  attempt runs from that copy.
- A forge experiment is declared before it runs, and two arms are compared only
  when nothing but the Skill differs between them.
- A candidate Skill that names the cases a Climb scores it on is refused when
  it is prepared, whether for a first submission or as a revision of a measured
  Skill. A Skill describes the rule; it may not carry the scored inputs.

## v0.2.0 (2026-09-18)

### Added

- Read release notes at [Changelog](https://techtree.sh/changelog), available from
  the site header.
- Build repair tasks from a local Git repository with `techtree forge build`.
  Each accepted task checks that the unrepaired code fails the relevant tests
  and that the reference repair passes them. Building tasks does not call a model.
- Inspect retained build results with `techtree forge status`, including failed
  or cancelled builds, without requiring Docker or the task generator to be
  available. Incomplete results are shown as incomplete, not as usable tasks.
- Keep the generated task files, their content fingerprints, validation logs,
  and control/reference results together so a build can be inspected later.
- Browse published Results by harness, model, and exact challenge. An unknown
  selection does not silently show unrelated results. This is already live on
  techtree.sh.

### Changed

- Results and objects published before this release stay available at their
  existing addresses. New runs must be recorded with the current CLI against
  the current catalog; uploads made with CLI 0.1.1 against the earlier campaign
  are no longer accepted. Upgrade by following the [Start guide](https://techtree.sh/start).
- CLI integrations receive structured facts, unknowns, blockers, and suggested
  next actions. The response format replaces the previous format; integrations
  must update with the CLI rather than assume old responses still apply.
- New comparisons record evaluation rules separately from execution settings.
  Existing signed proof bundles remain readable without rewriting their files.
- CLI, Hermes plugin, and website development now share one repository. Existing
  pinned installation instructions in the active Start guide remain authoritative.
- The site header shows the GitHub star button and its star count as one button.

### Fixed

- Updated the website's Ash dependency to include its field-policy security fix.
- The supplied Python build image keeps the project's installed test tools
  available when a login shell starts.
- Task generation retains raw validation output and distinguishes missing test
  results from a repair that produces no failing-to-passing tests.
- Interrupted builds retain progress and failure details. Docker commands have
  time limits, and interrupted operations attempt to remove their owned containers.

### Not in this release

- Running a coding agent on the generated repair tasks with `forge run`,
  comparing baseline and candidate Skills with `forge compare`, and reporting
  their measured time and usage are not included.
- Evaluating the default Hermes profile or a named profile with isolated state,
  Hermes-owned authentication, and a verified grading handoff is not included.
- A Prime reference-agent handoff, an independently authorized external-use case
  study, Fabric-backed Hermes/Codex comparisons, and optional Relay evidence
  are not included as qualified end-to-end workflows.
- Qualification has been reproduced for one selected public repair, locally and
  on a fresh Linux worker. This is task-pipeline evidence, not an agent repair,
  a demonstration of Skill benefit, or a held-out evaluation.
- The full generation and per-task deadlines were not run to expiry. Among the
  generator's rejection reasons, only the missing or unreadable test-output
  case was deliberately exercised in a real build; this is not exhaustive
  failure-path coverage.
- Hosted comparisons, public collaboration and payments, automatic Skill
  optimization, private proving, and training remain outside this milestone.
