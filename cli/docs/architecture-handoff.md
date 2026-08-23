# Techtree Climb v0.1 — Architecture Handoff

A detailed map of the product, the three codebases, their internal
structure, and how they interact. Written for an engineer picking up
the whole system cold. Everything here is checkable against the repos;
where a decision doc governs a choice it is cited (`docs/decisions/`).

---

## 1. The product in one page

Techtree Climb is "the open improvement and proof network for agent
systems." v0.1 — **Techtree Hello World** — is a deliberately small,
honest instance of the whole idea: a controlled A/B experiment on an
AI agent, packaged so anyone can run it on their own machine and prove
the result to anyone else without trusting a server.

The scientific claim it makes true is four statements (decision 0019):

1. **Same system.** The same pinned agent runs the same fixed tasks —
   same model, harness, runtime, task membership, tools, scorer,
   budget.
2. **One changed component.** Exactly one thing differs between the two
   sides: a Skill (a content-addressed bundle of instructions). First
   run: no Skill → Starter Skill v1. Later: Skill v1 → Skill v2.
3. **A measured difference.** Baseline score, candidate score, wins /
   losses / ties, cost, timing, regressions, validity.
4. **A verifiable receipt.** A signed proof bundle the participant can
   check offline (`techtree proof verify`), integrity-bound and
   participant-attested — not independently reproduced.

The v0.1 task family is **BranchCode v1**: 36 synthetic string-puzzle
tasks. The Starter Skill contains one deliberate defect (it counts
total characters where it should count distinct characters), so a
neutral agent scores ~0/36, the Starter lifts it to ~23/36 (the
"roughly two-thirds" band), and a corrected reference Skill would
reach 36/36. This makes the *mechanism* observable without any claim
of broad capability.

**The experience.** A Hermes-agent user pastes one prompt; their agent
reads a pinned install guide, installs a plugin (with a human approval
at each consequential step), the plugin drives a local CLI, the CLI
materializes a sandboxed evaluation engine, runs both sides in Docker,
scores them, signs a receipt. Optionally the user asks for one
**guided revision**: the host model proposes a new Skill once, the
diff is shown, and v1-vs-v2 is measured. Everything stays local;
nothing is uploaded; the only outbound calls are to the user's own
model provider.

**What it is NOT (v0.1 scope lock):** no leaderboard, no accounts, no
receipt upload, no remote evaluation, no third-party campaigns, no
multi-file guided revision, no reliability guarantee on the guided
revision (it ships **experimental** — decision 0028).

---

## 2. The three codebases at a glance

| Repo (GitHub) | Language / stack | Role | Ships to the user? |
|---|---|---|---|
| **techtree-python** (regents-ai/techtree-python) | Python 3.12–3.13, uv, Hatchling | The science: CLI, evaluation substrate, receipts, proofs, release tooling. Also the programme hub (decisions, specs, beads tracker, release artifacts). | Yes — as the `techtree` wheel on PyPI |
| **techtree-plugin** (regents-ai/techtree-hermes) | Python, standard library only | The Hermes operator plugin: agent-facing tools, slash command, the two founder Skills. A thin, dependency-free client over the CLI. | Yes — installed into Hermes at a pinned commit |
| **techtree-ash** (regents-ai/techtree-ash) | Elixir, Phoenix 1.8, Ash 3, AshPostgres, Bandit | The read-only website (techtree.sh): catalog, install guide, content-addressed object serving, the BootstrapRelease contract. | Yes — as a served site; never installed |

The **cardinal boundary**: the plugin never imports the Python
package. It shells out to the `techtree` CLI and speaks exactly one
protocol — a strict JSON envelope over stdout. This keeps the heavy
scientific dependency tree out of the user's Hermes process, lets the
two version independently, and makes the trust surface auditable. The
website never executes anything; it serves bytes and refuses anything
but GET/HEAD.

---

## 3. techtree-python — the science and the substrate

Python 3.12–3.13, built with Hatchling, managed with uv. Runtime
dependencies are deliberately few: `pydantic` (models), `cryptography`
(Ed25519 signing), `rfc8785` (canonical JSON for digests), `rich`
(terminal output), `typer` (CLI), `filelock`, `platformdirs`,
`tomli-w`. Two entry points: `techtree` (the CLI) and
`techtree-worker` (the detached run worker).

Gate: `make check` (ruff format + lint, mypy strict, unit tests,
generated-artifact drift check) and `make test-integration`.

### 3.1 The module map (`src/techtree/`)

Grouped by concern, in rough dependency order (lower layers first):

**Protocol core**
- `canonical.py` — RFC 8785 canonical JSON and `digest_object()`; the
  foundation of every content address in the system.
- `crypto.py` — Ed25519 sign/verify.
- `ids.py`, `constants.py`, `errors.py`, `fs.py`, `paths.py` —
  identifiers, stable error codes, atomic file writes, the
  `TechtreePaths` home layout.
- `models/` (15 files) — every protocol shape as a frozen pydantic
  model: `campaign.py` (**CampaignSpec** — the scientific contract:
  subject agent, sampling, budgets, execution, taskset membership,
  mutation contract), `climb.py` (**ClimbManifest** — the public
  wrapper + resolution), `data_policy.py`, `evaluation_backend.py`,
  `experiment.py` (manifests + `ManifestComparison`), `skill.py`
  (**SkillArtifact** — content-addressed file tree), `run.py`
  (RunRequest, RunState, ExecutorKind), `episode_receipt.py`,
  `uplift_report.py`, `validation.py`, `catalog.py`, `engine.py`,
  `base.py`, `cli.py`.

**Content & catalog**
- `catalog/` — the embedded, content-addressed catalog
  (`repository.py`, `service.py`) that ships inside the wheel under
  `resources/catalog/`. Holds the Campaign, Climb, DataPolicy,
  validation receipt, and membership for Hello World.
- `skills/` — `scanner.py` (secret detection over a candidate Skill —
  key blocks, provider token prefixes, aws patterns; the generic
  assignment heuristic was deleted, decision 0028), `archive.py`
  (deterministic tar), `policy.py`, `starter.py` (fetches/stages the
  starter Skill from its content address), `service.py`
  (`SkillPreparationService` — resolve → scan → snapshot → derive
  manifests → compare → persist a draft).
- `drafts/` — immutable prepared submissions (`source.py`,
  `store.py`).
- `manifests/` — build baseline/candidate manifests from a Campaign
  and assert the comparison is *controlled* (`builder.py`,
  `compare.py`).

**Run lifecycle**
- `runs/` (13 files) — the heart of execution. `service.py`
  orchestrates; `machine.py` is the state model
  (prepared/running/completed/failed/cancelled surface);
  `store.py` persists run-owned files (append-only);
  `events.py` the journal; `launcher.py` spawns the **detached
  worker** with a deliberately scrubbed environment; `real.py` the
  real executor (with `require_executable_budget` /
  `require_cost_bound` preconditions — decision 0029); `fake.py` the
  development executor; `executor.py` the shared interface;
  `variants.py` the baseline/candidate scheduling; `child_registry.py`
  tracks live eval children; `artifacts.py`, `validation.py`.
- `worker/` — `main.py` (the `techtree-worker` entry point), `execute.py`.

**Evaluation engine (the sandbox)**
- `engines/` — `installer.py` (provisions the pinned Prime Verifiers
  engine into a managed home), `registry.py`, `runner.py`,
  `bundle.py`. The engine is a separately-locked dependency set that
  the ordinary package does **not** import.
- `verifiers/` (12 files) — the bridge to the pinned Verifiers
  evaluation framework: `compiler.py` (Campaign → the framework's TOML
  config), `config.py` (the TOML models incl. `TimeoutToml` and the
  per-episode limits — decision 0029), `child.py` (launches one eval
  variant under a supervisor), `supervisor.py` (**the orphan-bound
  layer** — parent-liveness pipe + hard deadline + graceful group
  stop, decision 0029), `budget.py` (the executable-budget validator +
  cost-bound calculation), `credentials.py` (Prime credential
  resolution — the doctor-truth fix), `image.py` (Docker image
  resolution by digest), `outputs.py`, `progress.py`, `verify.py`.
- `tasksets/` — the BranchCode reference taskset, membership locking,
  validation (`membership.py`, `provider.py`, `resolver.py`,
  `service.py`, `verifiers_cli.py`).

**Evidence**
- `receipts/` (9 files) — `episode.py` (per-episode receipts from
  traces), `set.py` (receipt sets), `observed.py` (the observed
  comparison — proves only the Skill changed), `compare.py`,
  `execution.py` (signed ComparisonExecutionRecord), `uplift.py` (the
  signed UpliftReport), `bundle.py` (the proof bundle), `verify.py`
  (offline verification — the `proof verify` engine).
- `identity/` — the participant's local Ed25519 signing key
  (`store.py`, `service.py`, `models.py`); retained across uninstall
  by design.

**Guided revision**
- `uplift/` — `service.py` (orchestrates the one-turn revision),
  `context.py` (the sanitized improvement context sent to the host
  model), `source.py` (`VerifiedSourceSkill` — loads the just-run
  Skill bytes), `derive.py` (derives the replacement Campaign +
  manifests for v1-vs-v2), `public_tasks.py`.

**Presentation**
- `presentation/` — `build.py` (assembles the presentation payload
  from verified artifacts — proof grade derived, never hardcoded),
  `rich.py` (deterministic terminal output), `compact.py`
  (deterministic gateway/phone output, ANSI-free, bounded),
  `sanitize.py`, `models.py`. **No host model is ever called to word a
  result** (decision 0009).

**Release tooling**
- `release/` — `models.py` (**ReleaseCore** — the concrete release
  contract, self-referential fields deleted per decision 0026),
  `provenance.py` (reads the wheel's build-time commit stamp),
  `bootstrap.py` (BootstrapRelease shape + R10 placeholder rejection),
  `document.py`, `generate.py`, `checks.py`.

**CLI surface**
- `cli/` — `app.py` (the Typer app + `main`), `context.py`, `invoke.py`,
  `output.py` (the JSON envelope + next-action rendering),
  `commands/` — `setup.py`, `doctor.py`, `climb.py`, `run.py`,
  `uplift.py`, `skill.py`, `engine.py`, `proof.py`, `release.py`.
- `doctor/` — readiness checks (`checks.py`, `execution_checks.py`,
  `service.py`): CLI release, engine, Docker, catalog, host platform,
  provider credential (the credential check answers for the *run's*
  environment, not the terminal's — decision's wdc fix).

### 3.2 Non-code trees in techtree-python

- `docs/decisions/0001–0029` — the binding decision record.
- `docs/spec/` — the four vendored implementation specs +
  CHECKSUMS.json + INDEX.md.
- `docs/release/contracts/` — self-contained per-ticket execution
  contracts.
- `release/` — the release artifacts: ReleaseCore, the founder Skill
  approval packet + addendum, the certified-scientific-fingerprint,
  wheel-inspection, fresh-install-report, budget-contract-audit,
  claim-evidence-matrix, orphan-bound-analysis, the Hermes scanner
  dossier, the plugin-release-candidate record.
- `tests/` — unit + integration + contract, **plus `tests/plugin/`**
  (the plugin's relocated test corpus) and `tools/plugin/` (its
  relocated tooling) — moved here so the installable plugin tree
  carries no adversarial fixtures for Hermes's scanner (decision-era
  ticket llv).
- `.beads/` — the beads issue tracker DB (the programme's task record).

---

## 4. techtree-plugin — the Hermes operator plugin

**Standard library only. Zero third-party runtime dependencies.** It
owns no HTTP client and cannot open a socket — verified by a
conformance test. Everything it does with the outside world is run the
pinned `techtree` CLI, three call sites, all in `bridge.py`, all
`shell=False`, fixed argv, and (decision-era ticket llv, pass 2) a
**ten-variable environment allowlist** so no unrelated host secret
reaches the CLI.

Gate: `make check` (format, lint, mypy) in the plugin repo, **plus**
`make test-plugin` in techtree-python where the 791-test battery now
lives.

### 4.1 Files (repo root)

- `plugin.yaml` — the Hermes manifest: declares the tools, the slash
  command, the two Skills, and a plain-language capability declaration
  (what it does with the machine; `requires_env` is intentionally
  empty — it prompts for values, and the plugin reads none directly).
- `__init__.py` — registration entry (performs **no** side effects on
  load: no install, no network, no Docker, no model call — 5 sealed
  conformance tests + more).
- `bridge.py` — the CLI boundary: `call_cli`, `read_cli_version`,
  `invoke_cli_human`, `cli_environment()`. The ONLY place a subprocess
  is spawned.
- `schemas.py` — the model-visible tool JSON schemas (bounded value
  patterns; no API key / executable path / install command / unbounded
  id can ever be a tool argument).
- `tools/` — the tool handlers: `bootstrap.py`, `catalog.py`,
  `run.py`, `uplift.py`, `demo.py`, `proof.py`, `arguments.py`.
- `commands.py` — the `/techtree` slash command surface and its
  next-step rendering.
- `bootstrap.py` — install-plan production + the install approval flow.
- `approvals.py` — the native-approval boundary (no token machinery;
  the model cannot approve its own action — decision 0019).
- `llm.py` — the one-shot host-model seam (`OneShotHostLlm`): exactly
  one generation request per revision, zero retries, zero repairs;
  emits `host_proposal_generation_exhausted` on a truncated answer
  (decision 0028).
- `guards.py` — narrative/skill guards (the copied-case guard, the
  structure guard, the command-word list; the numeric-claims heuristic
  was deleted, decision 0028).
- `diff.py` — the deterministic Skill diff shown before the second
  approval.
- `narrative.py`, `channels.py` — bounded, ANSI-free relay of the
  CLI's deterministic output (control-character stripper lives here).
- `models.py`, `constants.py`, `errors.py` (recursive secret scrubber),
  `state.py`, `hooks.py`, `release.py` (carries the byte-identical
  ReleaseCore), `doctor.py`.
- `skills/operator/SKILL.md` — the operator Skill (product copy for
  the host agent).
- `skills/skill-improver/SKILL.md` — the **founder-frozen** improver
  Skill (digest `e6bc16c4…`, never edited).

---

## 5. techtree-ash — the read-only website

Elixir / Phoenix 1.8 / Ash 3 / AshPostgres, served by Bandit. Assets
via esbuild. Deployed on Fly.io (org `regent`, app `techtree-sh`,
Postgres-backed) — see `docs/release/deploy-flyio.md`.

Gate: `PGUSER=sean mix check` (format-check, warnings-as-errors
compile, 251 tests + doctests).

### 5.1 Domain (`lib/techtree/`)

An Ash domain modelling releases as immutable rows selected by a
per-channel active pointer:

- `domain.ex`, `application.ex`, `repo.ex` — Ash/Ecto wiring.
- `release/` and the `catalog/` resources: `bootstrap_release.ex`,
  `catalog_release.ex`, `catalog_entry.ex`, `publication.ex` (the
  active-release pointer — publish/rollback is a pointer move, never a
  mutation), `importer.ex` (imports a bootstrap bundle),
  `concrete_coordinates.ex` (R10 — a `placeholder_release:false`
  release must reject every placeholder-shaped value),
  `verifier.ex`, `digest.ex`, `bundle.ex`, `query.ex`,
  `starter_skill.ex`, `release.ex` (the `import_catalog` / publish
  functions run via `bin/techtree eval` on the host).

### 5.2 Web (`lib/techtree_web/`)

- `router.ex` — the whole surface. **LiveViews** (`/`, `/start`,
  `/climbs`, `/climbs/:slug`, `/proofs/local`, `/protocol`) and
  **GET/HEAD-only controllers** (`/healthz`, `/bootstrap`, `/catalog`,
  `/climbs/:slug` JSON, `/objects/:digest`).
- `object_controller.ex` — serves content-addressed bytes; **refuses
  to serve if the stored bytes no longer match the requested digest**;
  the starter Skill is served here at `/api/v1/objects/sha256:<file
  digest>`.
- `bootstrap_controller.ex` — serves the active BootstrapRelease
  document (the install contract the site publishes).
- `method_surface.ex` + `exact_response.ex` — enforce GET/HEAD-only
  (405 with `Allow: GET, HEAD`) and exact-byte serving with
  digest-derived ETags and immutable cache headers.
- `live/home_live.ex`, `start_live.ex` — the agent-first onboarding
  copy and the caution-confirm scan explanation.
- `install_components.ex`, `climb_copy.ex` — shared install/product
  copy (single source so pages can't drift), gated by copy-guard
  tests.

---

## 6. How the three interact — the data-flow spine

```
   ┌─────────────────────────── the user's machine ───────────────────────────┐
   │                                                                           │
   │  Hermes Agent (host model, e.g. GLM/GPT via the user's provider)          │
   │        │  loads                                                           │
   │        ▼                                                                  │
   │  techtree-plugin  ──── one pasted prompt drives it; native human          │
   │        │              approval before install / CLI install / paid run    │
   │        │  subprocess (shell=False, fixed argv, 10-var env allowlist)      │
   │        │  strict JSON envelope on stdout  ◄── the only cross-boundary API │
   │        ▼                                                                  │
   │  techtree  CLI (the wheel)                                                │
   │        │  prepares drafts, signs receipts, verifies proofs                │
   │        │  spawns ▼ detached                                               │
   │  techtree-worker ── scrubbed env ── verifiers/supervisor ── eval child    │
   │        │                                             │                    │
   │        │                                             ▼  Docker (pinned    │
   │        │                                    subject Hermes, by digest)    │
   │        │  model calls ────────────────────────────► the user's provider  │
   │        ▼                                                                  │
   │  ~/.techtree (TECHTREE_HOME): runs, receipts, proof bundles, signing key  │
   │        │  read-only fetch of the starter Skill by content address        │
   │        ▼                                                                  │
   └────────┼──────────────────────────────────────────────────────────────────┘
            │  HTTPS GET (bytes only, nothing uploaded)
            ▼
   techtree.sh (techtree-ash) — install guide, catalog, /objects/<digest>,
   the BootstrapRelease contract. GET/HEAD only. Never executes anything.
```

### 6.1 What binds the three together: shared digests

The repos are decoupled in code but **welded by content addresses**.
Three artifacts must agree byte-for-byte or the release is incoherent,
and a cross-repo verifier (`tools/verify_release_core.py`, 25 checks)
enforces it:

- **ReleaseCore** (currently `c037f457…`) — the release contract. Lives
  byte-identical in techtree-python (`release/` + packaged
  `resources/release/`), inside the built wheel, and in the plugin
  (`release.py`). The plugin refuses to act on a CLI whose ReleaseCore
  disagrees with its own.
- **The wheel** — carries a build-provenance stamp naming the exact
  source commit it was built from (decision 0026: identity is stamped
  at build time, never self-referenced in a committed file). Builds are
  byte-reproducible; the PyPI publish workflow rebuilds and refuses to
  publish on any mismatch.
- **The BootstrapRelease** (the website's release object) — the
  external witness that pins the wheel SHA-256, the plugin commit, and
  the source commit together, and names the starter Skill's file +
  tree digests and its `/objects/` URL.

### 6.2 The onboarding sequence, end to end

1. User pastes one prompt to Hermes → agent reads **techtree.sh/start**
   (served by ash) and the pinned plugin coordinate.
2. Agent runs `hermes plugins install … --ref <commit> --enable`.
   Hermes's install-time scanner reports **caution / 5 findings**; the
   agent shows them; the human confirms.
3. One Hermes restart loads the plugin's tools.
4. `/techtree setup` → the plugin (via `bootstrap.py`) produces the CLI
   install plan; human approves → the pinned `techtree` wheel installs
   (from PyPI at release; from a local `--find-links` dir pre-release).
5. Doctor (`techtree doctor --climb hello-world-climb@1`) checks
   Docker, engine, catalog, and the Prime credential (the honest
   check).
6. Prepare → the CLI resolves the Climb from the packaged catalog,
   fetches the starter Skill by content address from ash's
   `/objects/`, scans + snapshots it into an immutable draft.
7. Review surface shows the six disclosures (episodes, declared spend
   ceiling, same-agent/tasks, Skill-only change, provider disclosure,
   no-upload). Human approves the paid run.
8. The CLI launches the **detached worker**, which launches the
   **supervisor**, which launches the **Docker eval child** — one
   variant with the Skill, one without — the pinned subject Hermes
   making calls to the user's provider, scored by the Verifiers engine.
9. Receipts → signed UpliftReport → proof bundle in TECHTREE_HOME. The
   user can close the terminal and recover by run ID; `techtree proof
   verify` checks it offline.
10. Optional guided revision: the host model proposes one Skill v2
    (`uplift/` + the plugin's `llm.py`), the diff is shown, a second
    approval, then a v1-vs-v2 comparison and second proof.

### 6.3 The safety boundaries (where trust is enforced)

- **Plugin ↔ CLI**: strict JSON envelope, fixed argv, no shell,
  10-variable environment allowlist. The plugin can't smuggle a
  command or a secret.
- **Worker environment scrub**: the detached worker inherits only
  PATH/HOME/TMPDIR/TECHTREE_LOG_LEVEL (+ a TECHTREE_HOME it sets); a
  provider credential exported in the operator's shell cannot reach it
  — it must come from an active Prime CLI configuration.
- **Orphan containment** (decision 0029): every eval variant runs
  under a child-local supervisor with a parent-liveness pipe and a
  3600s hard deadline; a hard-killed worker's containers stop within
  ~1s; per-episode turn/token/time limits are enforced natively and a
  cost bound is checked before any spend.
- **Append-only evidence**: no completed run's files are ever
  modified; a run this build cannot read gets one honest error, never
  a rewrite.
- **Approval**: the model never approves its own action — a human
  approves at the CLI (y/N or explicit `--yes`) or Hermes's native
  surface; one `run.approved` audit event records it.
- **No upload**: no receipt/episode/trace/proof/proposal leaves the
  machine; the website is GET/HEAD-only; model calls go to the
  provider.

---

## 7. Development & release workflow

- **Task tracking**: beads (`bd`), DB in techtree-python.
- **Commits**: worker agents never run git; the orchestrating session
  commits per ticket after independently re-running the gates.
- **Change discipline** (decision 0022): after certification, no
  behavior change to runs/approvals/proposals/receipts/proof/host
  requests/Skill mounting/guards/Campaign without repeating the paid
  certification; copy/docs/test changes must leave every scientific
  digest byte-identical. The Gate-2 packet classifies every commit
  since the certified baseline.
- **Certification evidence** lives outside the repos at
  `techtree-climb/certification-evidence/` (local-only, never
  committed — run dirs contain answer keys).
- **Release gates**: `make check` + `make test-integration` +
  `make test-plugin` (python), `make check` (plugin), `mix check`
  (ash), and the 25-check cross-repo verifier.
- **Two founder gates**: Gate 1 (Skill approval) — DONE. Gate 2
  (release approval) — pending; nothing publishes, tags, deploys, or
  flips `placeholder_release` before the exact
  `APPROVE CLIMB V0.1 RELEASE` phrase.

For the current release coordinates, remaining tickets, and sharp
edges see `docs/agent-handoff.md` and `docs/v0.1-remaining-tickets.md`.
For binding rationale, `docs/decisions/`.
