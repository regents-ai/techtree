# Changelog

## v0.2.2 (unreleased)

### Changed

- `techtree doctor` now says whether the `techtree` Hermes profile is signed
  in, and to which providers, checked the same way `techtree forge run` checks
  before it starts. A missing or signed-out profile is reported with the exact
  command that resolves it.
- The host Hermes this release is tested on is 0.21.3, and 0.21.3 is now the
  minimum: experiments run in a Hermes profile of their own, and that is the
  Hermes it was verified on.
- The published package is built the same way every time, from a clean copy of
  the release commit, so what is on PyPI is exactly what was approved.

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
