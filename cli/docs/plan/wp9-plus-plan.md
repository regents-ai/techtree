# Plan: Work Packages 9+ (the operator-experience push)

Status: SUPERSEDED as implementation guidance by the author's exhaustive
`docs/spec/climb-v0.1-wp9-wp11.md` (2026-08-13), which is now the binding
specification; beads epics WP9/WP10/WP11 and their 18 tickets follow its
§14 split. This document remains useful only for the founder-inputs
checklist below. Original framing:

Grounded in `docs/spec/climb-v0.1-wp6-wp8.md` §9–§11 (the
author's WP9/WP10 compatibility contracts) and the target narrative:

> A person talks to their Hermes agent from a phone or terminal gateway,
> installs the hermes-plugin (which installs techtree-python), runs a
> baseline and a Skill-enabled run of a simple benchmark simultaneously,
> sees the difference driven home with rich terminal output, lets the
> agent think one turn about Skill improvements using a founder-supplied
> Skill, reruns new-vs-old Skill, and gets an Uplift receipt. Uploading
> the receipt to the web app is out of scope.

## Package sequence (author-ratified, decisions 0005)

```text
WP9  — Hermes operator plugin, explicit CLI bootstrap, gateway-safe tools
WP10 — Guided Skill refinement + rich/compact result experience
WP11 — Cross-repository release hardening, install-from-zero acceptance
WP12+ — Optional NeMo Relay runtime evidence (deferred until the full
        install → compare → revise → compare loop is green)
```

## WP9 — `techtree-hermes` plugin (repo comes alive)

A thin, pinned host-agent adapter over the CLI JSON contract. It never
compiles configs, launches Docker, parses episodes, scores, signs, or
re-implements DataPolicy — the CLI owns all of that.

Proposed tickets:

- **WP9a — plugin skeleton + bootstrap tools.** `techtree_bootstrap_check`
  / `techtree_bootstrap_install`: detect the CLI, return the exact pinned
  install plan (`uv tool install techtree==<version>`, argv array,
  requires_confirmation=true), invoke it only after explicit human
  approval, then `--version` + `doctor` verification. Registration
  installs nothing. Missing `uv` → actionable prerequisite error from the
  bootstrap manifest, never an auto-downloaded installer.
- **WP9b — run-control tools.** The remaining §10.4 tool set
  (system_check, climbs_list, climb_inspect, demo_prepare, climb_start,
  run_status, run_cancel, run_result, proof_verify, uplift_context,
  uplift_prepare, uplift_start). All typed JSON in, CLI envelope out,
  argv arrays only, `--json --no-color --no-input` always, no waiting for
  whole benchmarks (long work returns run IDs — matches the detached
  worker design).
- **WP9c — demo profile + starter-Skill materialization.** Download the
  content-addressed starter Skill v1 named by the bootstrap manifest,
  verify digest, cache, and feed it through the ordinary scanner/draft/
  policy path (no bypass).
- **WP9d — auth separation UX.** Doctor and plugin distinguish "host
  Hermes model access" from "Techtree evaluation model access"
  (PRIME_API_KEY / Prime CLI config per §10.3); the plugin never asks the
  model to paste a key into chat or a tool argument.

Dependencies: needs WP7 (real result + proof verify) and WP8b (bootstrap
API). WP9a/b can start against the committed CLI contract as soon as WP7c
lands; WP9c/d need WP8b's manifest shape frozen.

## WP10 — guided refinement + result experience

- **WP10a — presentation wiring.** *(Superseded by decisions 0009: the
  `rich-terminal-output` Skill was removed from the product release, and
  the released result path is the deterministic Rich and compact
  renderers only — no host-model narration turn exists in v0.1.)* The
  deterministic `ComparisonPresentation` payload (built in WP7c) renders
  through the deterministic CLI panel and the compact bounded ANSI-free
  phone/gateway renderer.
- **WP10b — one-turn improvement flow.** First report → sanitized
  `SkillImprovementContext` (no hidden answers, grader material, secrets,
  or unredacted paths) → host Hermes + founder-supplied
  `techtree:skill-improver` Skill → exactly one reasoning turn → proposed
  Skill v2 → scanner + digest + reviewable diff → explicit human approval
  → skill_replacement Campaign (v1 baseline vs v2 candidate) → second
  signed report. Operator Skills are never mounted into the Docker
  subject.

Dependencies: WP7d (improvement context + replacement flow) and the
founder Skill files. Until those files exist, workers implement and test
typed boundaries with fixture Skills only.

## WP11 — release hardening

- Clean-machine install-from-zero rehearsal (fresh macOS user account or
  container): the §12.2 terminal scenario end-to-end, scripted where
  possible, manual gate where not.
- Phone/gateway rehearsal per §12.3 (compact output, no ANSI, bounded
  messages, run IDs over waiting).
- Cross-repo version pinning audit: bootstrap manifest ↔ plugin commit ↔
  CLI version ↔ engine digest ↔ catalog release all agree.
- Failure-path drills: no Docker, no uv, no evaluation credential, dead
  network mid-run — every one lands on a typed error with a working
  repair action.

## Founder inputs needed along the way (sign-off gates)

1. Real subject model/provider + Prime evaluation credential (gates the
   first real WP6 run; already flagged).
2. Starter subject Skill v1 (content-addressed release artifact) —
   *supplied 2026-08-13 as `hello-world-starter-v1` (decisions 0009/0010).*
3. `techtree:rich-terminal-output` operator Skill — *removed from the
   release by decisions 0009; no longer a founder input.*
4. `techtree:skill-improver` operator Skill — *supplied 2026-08-13
   (decisions 0009/0010).*
5. LICENSE choice for techtree-python (placeholder committed) —
   *decided: MIT everywhere (decisions 0011).*
6. Release versions: first public `techtree` version string and the
   plugin repo/commit the bootstrap manifest pins.
7. techtree.sh hosting decision (WP8 deploy target — Fly.io per your
   usual stack?) — build is deploy-agnostic until then.

## Explicitly out of scope for the whole push

Uploading receipts/reports/episodes to techtree.sh, authentication,
leaderboards, remote evaluation, NeMo Relay (WP12+ at earliest),
ImprovementProgram/Blueprint/Trace modes.
