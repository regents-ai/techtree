# Changelog

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
