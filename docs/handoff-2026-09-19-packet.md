# Techtree 0.2.1 packet handoff, 2026-09-19 19:54Z

For the Claude account taking over the Techtree lane from the Fable 5.1
thread that ran it since 2026-09-18. This document is the current state; the
earlier `docs/handoff-2026-09-19.md` is the long-form reference for the
stack, what is live, and the 0.2.x/0.3.0 scope. Read that one second.

Nothing in this document is pushed. Everything from `324a943` onward on
`release/v0.2.0` after `19f3c7c` is local only, on the founder's "hold":
the packet ships together, on his word.

## 1. Standing rules (unchanged, binding)

- Sole agent on this lane. Hermes/Astra pairing, ocs and votes are retired.
- Pushes, merges to main, deploys, production data changes, Fly
  secrets/config, contract or money actions: the founder's explicit word for
  that exact action, then do it once and report.
- Hard cutover only: no fallbacks, compatibility branches, shims, aliases or
  dual shapes. Do not touch unrelated code.
- Tests only when directed. The founder directed tests for items 1–3 of this
  packet ("1b"); items 3 and 4 were written under that precedent and flagged.
  Flag again if you add more.
- Never read `.env`, `.env.local`, `.envrc`, Hermes `config.yaml`,
  `auth.json` or profile contents; never print secrets or connection strings.
  Copy only `state.db` out of a throwaway Hermes profile. Never `--safe-mode`.
- Never drop or recreate any database without an explicit grant; never
  `rm -rf` (ask the founder to delete); never bare `git stash`; never run
  bd/beads.
- Customer-facing copy never carries implementation words. The copy guard is
  `cli/tests/contract/test_release_copy.py` (it also forbids "cost estimate").
- Report in plain English; every open founder decision is numbered with
  options and a recommendation. Briefs short.
- Dev spend: the founder granted USD 10 for qualification runs on his own
  Codex subscription (decision 3a). Every run so far cost USD 0
  (`cost_status: included`). Announce the first real run of any new kind.

## 2. Where everything is

- Worktree: `worktrees/techtree-release-v020`, branch `release/v0.2.0`.
  `origin/main` = `origin/release/v0.2.0` = `19f3c7c`. Local HEAD `5f83b47`.
  Never touch `repos/techtree` (unrelated dirty files).
- Lane notes (append-only, stamped from `date -u`):
  `artifacts/techtree-pairing/notes-fable-2026-09-18.md`. Resume from the
  bottom.
- Evidence: `artifacts/techtree-pairing/release-v020/` (envelopes
  `R2A…R2D-forge-run-*.json`, `R3A-forge-compare.json`,
  `R4A-forge-run-candidate.json`).
- Qualified experiment home used for every real run:
  `artifacts/techtree-pairing/release-v020/I1c-qualified-r3/home`, build
  `build_255c23a0d8694841b9a6a47b1bf38a5b`, one qualified task
  `local__click-f58ca3e81424`.
- Candidate Skill used so far (sentinel-copy, 247 bytes): it lived in the old
  session's scratchpad. The run `forgerun_1d61ac5f…` did not snapshot it
  (predates item 4). Recreate it as `skills/sentinel-copy/SKILL.md`:

  ```markdown
  ---
  name: sentinel-copy
  description: Repair copy and pickle behaviour of sentinel enums.
  ---
  # Sentinel copy

  When an enum member must survive copy, deepcopy and pickle, implement __copy__, __deepcopy__ and __reduce__ to return the member itself.
  ```

- Hermes: `/Users/sean/.local/bin/hermes`, reports 0.21.3, install
  `~/.hermes/hermes-agent` at upstream `6d712cf8d1` since 18:22Z today.
- Memory file for this lane (Claude auto-memory, previous account):
  `~/.claude/projects/-Users-sean-Documents-regent/memory/techtree-v020-release-solo-lane-2026-09-18.md`.
  A new account will not have it; this document replaces it.

## 3. The packet and its state

Founder priority for v0.2.1: a complete, useful repository experiment on the
existing stack. Excluded: autonomous epoch search, private proving, new
harnesses, training, hosted execution, payments, another orchestration
framework. Founder decisions taken: (1a) direct Harbor-compatible grading
labelled "local experiment"; (2a) fresh empty Hermes state per arm, memory
off; (3a) USD 10 dev cap.

| Item | State | Commits (local, `release/v0.2.0`) |
| --- | --- | --- |
| 0. Leak refusal (`candidate_policy_violation`) + tests | done, pushed/local | `324a943` (pushed), `336a868` (local) |
| 1. Forge run specification + comparability gate | done | `f896ca0` |
| 2. `forge run` with the person's own Hermes | done, real runs R2C/R2D graded 1.0 | `d009331`, `c76fa10` |
| 3. `forge compare` + self-contained HTML report | done, real comparison `forgecmp_618ffcb2…` (tie) | `e0d4bea` |
| 4. One revision cycle through `uplift` | code + 17 tests done; **real cycle blocked** (§4) | `5f83b47` |
| 5. Docker + fresh Linux qualification, then release 0.2.1 | not started | — |

Gates at `5f83b47`: `make check` (4165 unit/contract, 6 preflight),
`make test-integration` (306). Run them from `cli/`.

What item 4 delivers (all in `cli/src/techtree/`):

- `forge/skill.py`: a candidate run takes its own copy of the Skill under
  `forge/runs/<id>/skill/` and fills each attempt's profile from it;
  `read_owned_skill` reads it back only after re-hashing every file.
- `forge/improvement.py`: `uplift context FORGECMP_ID` writes
  `forge/comparisons/<id>/improvement/context.json` (instructions, both
  arms' results, objective; never the reference fix, tests, patches or
  local paths).
- `forge/revision.py`: `uplift prepare --from-run FORGECMP_ID
  --candidate-skill PATH [--label NAME]` freezes one revision under
  `forge/revisions/<forgerev_id>/{skill/,spec.json,revision.json}`;
  refuses an unchanged Skill (`forge_revision_unchanged`), a Hermes whose
  reported version changed (`forge_agent_changed`), any other spec
  difference (`forge_comparison_invalid`); screens the Skill against every
  task's reference patch and tests (lines of 24+ chars, scored test names)
  and records findings with warning `forge_revision_shares_hidden_material`.
  `uplift start FORGEREV_ID` shows the review and asks; `--yes` runs it as a
  candidate arm, compares against the same baseline, records a verdict;
  kept either way, never measured twice (`forge_revision_measured`).
  `forge status` reads `forgerev_` ids.
- Tests: `cli/tests/unit/test_forge_revision.py`; fakes in
  `cli/tests/fixtures/forge/support.py`.
- Docs updated: `cli/docs/product-architecture.md` (forge paragraphs),
  `platform/priv/changelog.md` (root `CHANGELOG.md` is a **symlink** to it;
  edit once), `docs/plan/repo2rlenv-local-lane.md` slice 3.

## 4. The blocker, exactly

Run R4A (`forgerun_fe81009e9ccb43b28e096b342c9f8a23`, candidate arm, needed
so the run owns its Skill) recorded `agent_failed` after 0.7 s: Hermes said
"No Codex credentials stored" for the throwaway profile. The runner's
design (item 2) creates a throwaway profile `~/.hermes/profiles/techtree-<run12>-<n>`
so the root's sign-ins are borrowed and refreshes written back, nothing
copied. That assumption is now false:

- Hermes commit `93889b770d` (2026-09-16, issue #111724): "named profiles no
  longer inherit the root profile's auth.json". Maintainer ruling: profiles
  are independent islands; a profile with no provider is asked to sign in
  (`hermes -p NAME auth add openai-codex --type oauth`).
- The local install pulled it at 18:22Z today (reflog `d84ece48b8` →
  `6d712cf8d1`), after R2D (17:37Z) and before R4A (19:11Z). The version
  string stayed 0.21.3, so the spec's `agent.version` could not tell.
- Copying a token is out: Codex OAuth refresh tokens are single-use
  families; a copy logs the other owner out (Hermes docs,
  `website/docs/user-guide/profiles.md` "Every profile owns its credentials").
- Linking the root store into the profile is out: Hermes rewrites
  `auth.json` by temp-file + rename (`hermes_cli/auth.py::_save_private_json`),
  which would replace the link and strand the rotated token in the
  throwaway profile.
- Hermes' automatic adoption of `~/.codex/auth.json` did not fire and must
  not be relied on (same token-family problem, and it persists a copy).

R2C, R2D and `forgecmp_618ffcb2…` remain valid evidence at the pre-#111724
Hermes. R4A stays as the honest failure record. No profile or container was
left behind (checked).

## 5. Founder decisions open (ask, do not assume)

1. **Runner profile model.**
   (a) Recommended: one persistent Hermes profile `techtree` that the
   person signs in once (`hermes profile create techtree`, then
   `hermes -p techtree auth add openai-codex --type oauth`; only the person
   can do the sign-in). Techtree owns that profile's `config.yaml`, writes
   it per attempt, fills `skills/<name>` from the run's Skill copy and
   removes it after, keeps `state.db` beside the evidence and removes it, so
   state is fresh per attempt except the sign-in. Add a lock so two runs
   never share the profile, a `doctor` check that the profile has a
   provider, and update `product-architecture.md` "Forge run", the run
   docstring in `forge/run.py`, `run_warnings`/review text ("copies no
   credential" stays true) and tests.
   (b) Root Hermes home with a config override (`HERMES_CONFIG` env exists):
   no sign-in step, but the person's memory, plugins, MCP servers, skills
   and session store leak into the experiment — against decision 2a.
   (c) Hold the real cycle and continue with item 5.
2. **Record the full `hermes --version` banner** (version, build date,
   upstream commit) as `agent.version` in `forge/experiment.py::hermes_version`
   (regex `_VERSION_BANNER`), so `prepare` refuses a revision after an
   update like today's. Recommended yes. Consequence: new runs cannot be
   compared with R2C/R2D (correct), so the real cycle re-runs both arms.
3. Item 4 tests (17) written under the 1b precedent: keep or drop.

## 6. How to finish item 4 once decision 1 is taken

Home `H=artifacts/techtree-pairing/release-v020/I1c-qualified-r3/home`,
all commands `uv run techtree --home $H --json …` from `cli/`. Save every
envelope as `release-v020/R4x-*.json`. Expected cost USD 0, under the cap.

1. `forge run --yes --arm baseline --build build_255c23a0d8694841b9a6a47b1bf38a5b --provider openai-codex --model gpt-5.6-sol`
   (only if decision 2 is yes; otherwise reuse `forgerun_8064b383…`).
2. `forge run --yes --arm candidate … --skill PATH/skills/sentinel-copy`.
3. `forge compare BASELINE_RUN_ID CANDIDATE_RUN_ID`.
4. `uplift context FORGECMP_ID`; `uplift skill-source CANDIDATE_RUN_ID`.
5. Write one revised `SKILL.md` yourself as the host agent (say so in the
   report; no search, one explicit proposal), in a new directory.
6. `uplift prepare --from-run FORGECMP_ID --candidate-skill DIR --label sentinel-copy-v2`.
7. `uplift start FORGEREV_ID --yes --reviewed-on host-agent`; then
   `forge status FORGEREV_ID`.
8. Notes, then report: verdict, screening findings, costs.

`gpt-5.3-codex` is refused by the ChatGPT-account backend; use
`gpt-5.6-sol`. The task's agent timeout is 1800 s; a real attempt took
170–230 s.

## 7. Item 5, as scoped

Docker qualification on a fresh Linux machine (not this Mac): install
`techtree` from a wheel built at the packet's HEAD, run `forge build` on a
small public repository, `forge run` both arms with the person's own Hermes,
`forge compare`, one `uplift` cycle. Acceptance from the founder's packet:
real baseline/candidate attempts; correct refusal of incompatible
comparisons; useful task-level evidence; no credential copying and no
automatic publication; successful use outside the original development
environment. Then version bump to 0.2.1, changelog date, tag and PyPI via
`.github/workflows/publish-cli.yml` (tag + expected wheel hash), plugin if
changed, catalog activation last — each step on the founder's word, as in
the v0.2.0 sequence recorded in the notes.

## 8. Gotchas learned on this lane

- Hermes `-z` ignores `agent.max_turns`; use `agent.run_budget_seconds`.
  Hermes exits 0 on failure; read the usage file's `completed`/`failed`.
- Hermes' Docker backend binds the host cwd at `/workspace` only for a
  shared container; the runner sets `terminal.docker_volumes` and
  `terminal.cwd` explicitly. Hermes stops but never removes its sandbox
  container; the runner removes containers labelled
  `hermes-profile=<profile>` after every attempt.
- The improvement context flattens the instruction's line breaks before the
  control/local-path check; the verdict has its own 400-char limit.
- To preview a static HTML file in the app's browser pane, register a
  temporary `python3 -m http.server` launch entry; `file://` does not open.
- `make check` regenerates schemas and the release core; a clean
  `generated-check` is part of the gate.
