# Changelog

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

- CLI integrations receive structured facts, unknowns, blockers, and suggested
  next actions. The response format replaces the previous format; integrations
  must update with the CLI rather than assume old responses still apply.
- New comparisons record evaluation rules separately from execution settings.
  Existing signed proof bundles remain readable without rewriting their files.
- CLI, Hermes plugin, and website development now share one repository. Existing
  pinned installation instructions in the active Start guide remain authoritative.

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
