# Techtree Climb v0.1

## Work Packages 0–5 Implementation Specification

### Revised around the shared Campaign kernel

**Status:** Greenfield implementation specification  
**Revision:** Campaign-kernel revision, 2026-08-13  
**Repository covered:** `techtree-python`  
**Work packages covered:** WP0 through WP5  
**Next excluded package:** WP6 — real baseline/candidate Hermes evaluation  
**Hermes plugin status:** Deliberately deferred until the CLI machine contract is stable  
**Ash website status:** Deliberately deferred; only public-object contracts are reserved here  
**NeMo Relay status:** Deliberately excluded  
**Primary development platform:** macOS, including Apple Silicon  
**Primary runtime language:** Python 3.12  
**Primary evaluation dependency:** Prime Intellect Verifiers v1  
**Pinned Verifiers commit:** `7e1c47d24d055aae587ee8259f77a3e8e193513a`  
**Primary local isolation dependency:** Docker, introduced for real subject evaluation in WP6  
**Primary goal:** Build a stable Campaign, CLI, worker, engine, and taskset-validation substrate that can power public Climb first and later be reused by private Verify, Forge, Uplift, reproduction, and Prime Lab execution without rewriting the scientific core.

---

# 0. How Climb v0.1 fits the Techtree product

Techtree is organized around a future `ImprovementProgram`: a durable record of a real workflow, its desired outcomes, the environments and evaluations used to measure it, the interventions attempted, the resulting evidence, and any training or deployment handoff.

Techtree exposes six product and workflow modes:

- **Blueprint** turns an ambiguous workflow into an approved improvement scope.
- **Forge** constructs and qualifies tasksets, environments, and verifiers.
- **Verify** establishes baselines and produces POC, release, and ongoing assurance.
- **Uplift** searches for the cheapest effective intervention and proves its effect.
- **Trace** packages selected episodes with provenance, rights, and training readiness.
- **Climb** publishes controlled campaigns as open competitions and public proof.

This document specifies only **Techtree Climb v0.1** and only its first six work packages.

Climb v0.1 is the first public use of a shared Techtree **Campaign kernel**:

```text
CampaignSpec
    scientific and execution contract

ExperimentManifest
    one resolved baseline, candidate, reproduction, or trained variant

TasksetValidationReceipt
    mechanical taskset validity

EpisodeReceipt
    one executed episode and its named traces

UpliftReport
    controlled comparison result
```

A public Climb wraps one `CampaignSpec` with:

```text
public catalog metadata
candidate-submission policy
publication policy
leaderboard policy
schedule and status
```

A private future Verify or Uplift workflow will be able to use the same `CampaignSpec` without becoming a public Climb.

A public Climb may exist independently of an `ImprovementProgram`.

A future private `ImprovementProgram` may contain many Campaigns without publishing any of them as Climbs.

The relationship is:

```text
ImprovementProgram, later ─────┐
                               ├── CampaignSpec
Public Climb ──────────────────┘
```

The six modes are not six identical database objects:

```text
Blueprint produces scope and contracts.
Forge produces qualified tasksets and environments.
Verify executes evaluation campaigns.
Uplift orchestrates interventions and candidate campaigns.
Trace packages selected evidence with rights and readiness metadata.
Climb publishes a Campaign as an open competitive network object.
```

Do not implement `ImprovementProgram`, Blueprint interviews, private customer workflows, release decisions, TraceSets, or Prime Lab handoffs in WP0–WP5.

The only forward-compatible additions required now are:

1. `CampaignSpec`, separate from `ClimbManifest`.
2. Generic `campaign_spec_digest` references in execution artifacts.
3. A required `DataPolicy`.
4. An explicit `EvaluationBackend`, separate from the subject runtime.
5. Optional `program_ref`.
6. Optional `outcome_contract_digest`.

These six changes are inexpensive before proof artifacts exist and expensive after proofs, APIs, and public links depend on the old shape.

---

# 1. Scope interpretation

“The first six work packages” means:

```text
WP0 — Freeze contracts
WP1 — CLI shell and NextAction UX
WP2 — Skill preparation
WP3 — Fake worker and run state machine
WP4 — Managed Verifiers engine
WP5 — Reference Taskset and validation
```

The following package is outside this document:

```text
WP6 — Native Verifiers baseline/candidate evaluation with Hermes in Docker
```

At the end of WP5, the system will be able to:

1. Represent all important Campaign and Climb protocol objects.
2. Serialize and hash those objects deterministically.
3. List and inspect an embedded development Climb.
4. Resolve that Climb to its immutable `CampaignSpec`, `DataPolicy`, and publisher taskset-validation artifact.
5. Validate and snapshot a candidate skill.
6. Build controlled baseline and candidate experiment manifests.
7. Start and supervise a detached local worker.
8. Exercise the full run UX using a fake baseline/candidate executor.
9. Install a pinned Verifiers engine.
10. Resolve a real Verifiers Taskset.
11. Compute and lock deterministic task membership.
12. Run Verifiers’ model-free task validation.
13. Issue a real local `TasksetValidationReceipt`.
14. Compare local validation with the Campaign’s publisher commitments.
15. Produce a development-only fake `UpliftReport`.
16. Expose a stable JSON CLI contract suitable for a future Hermes plugin.

It will not yet:

- Run the subject Hermes agent.
- Make baseline or candidate model calls.
- Run a Verifiers `eval`.
- Produce real Verifiers Episodes or Traces.
- Publish to `techtree.sh`.
- Load or execute the Hermes operator plugin.
- Use NeMo Relay.
- Make any public capability claim.
- Implement `ImprovementProgram`.
- Implement an `OutcomeContract` object; only its optional digest reference is reserved.
- Implement an `EnvironmentQualificationReport`.
- Implement a `ReleaseDecision`.
- Implement a `TraceSet`.
- Implement a Prime Lab handoff.

---

# 2. Binding decisions

These decisions are part of the specification and must be copied into:

```text
docs/decisions/0001-wp0-wp5-fixed-decisions.md
```

## 2.1 Verifiers pin

Use exactly:

```text
PrimeIntellect-ai/verifiers
7e1c47d24d055aae587ee8259f77a3e8e193513a
```

Do not use `main`, a branch, an unpinned PyPI range, or a moving tag.

A compatibility preflight ticket named:

```text
PI0 — Verify the pinned Verifiers contract
```

must run before WP4 or WP5 is allowed to merge.

The preflight must prove:

1. The pinned commit installs.
2. `TaskData`, `Task`, and `Taskset` import from `verifiers.v1`.
3. A tiny package exported through `__all__` loads as a Taskset.
4. Two loads produce identical task hashes.
5. Base `Task.validate()` behaves as expected.
6. `validate` accepts the pinned command form used by Techtree.
7. Validation creates:
   - `config.toml`
   - `results.jsonl`
   - `summary.json`
   - `validate.log`
8. The persisted summary fields match Techtree’s parser contract.

Any future Verifiers upgrade requires a dedicated dependency-bump change that reruns the preflight.

## 2.2 Shuffle

Climb v0.1 supports:

```yaml
shuffle: false
```

only.

Do not expose a shuffle seed in WP0–WP5.

Do not call Verifiers `Taskset.shuffle()`.

Membership is the first `num_tasks` tasks in the Taskset’s deterministic iteration order.

A later schema may add:

```yaml
shuffle: true
shuffle_seed: 42
```

but the seed must then become an immutable Campaign input.

## 2.3 Development public object names

Use:

```text
Campaign:
  procedure-transfer-dev-campaign@1

Climb:
  procedure-transfer-dev@1
```

Do not call the WP0–WP5 fixture `procedure-transfer-v1`.

That public name is reserved for the first real WP6 subject evaluation.

## 2.4 Development subject placeholders

The development Campaign freezes obvious non-executable placeholders:

```yaml
agents:
  subject:
    model:
      provider: development
      model_id: development-placeholder
      revision: null
      credential_env: TECHTREE_MODEL_API_KEY

    sampling:
      temperature: 0.0
      max_tokens: 512

    harness:
      id: hermes-agent
      version: 0.19.0
      use_bundled_skill: false
      skills: []

    runtime:
      type: docker
      image: techtree-development-placeholder:not-executed
      supported_platforms:
        - linux/arm64
        - linux/amd64
      cpu: 2.0
      memory_gb: 4.0
      network_policy: restricted

    trainable: false
```

The fake worker must not:

- Read `TECHTREE_MODEL_API_KEY`.
- Validate that the placeholder model exists.
- Pull the placeholder Docker image.
- Start the subject.
- Represent the result as scientific evidence.

WP6 creates a new real Campaign and Climb rather than mutating these development fixtures.

## 2.5 Bundled Hermes skills

For both future baseline and candidate:

```yaml
use_bundled_skill: false
```

The only allowed skill-only mutation is:

```text
/agents/subject/harness/skills
```

`use_bundled_skill` is invariant.

## 2.6 Signing

WP0 freezes and tests Ed25519 primitives.

No WP0–WP5 flow signs:

- Taskset locks.
- Validation receipts.
- Fake episode receipts.
- Fake uplift reports.
- Drafts.
- Runs.

Do not generate or persist device keys yet.

## 2.7 NeMo Relay

Relay is excluded.

No Relay package, field, exporter, receipt section, or status is implemented in WP0–WP5.

## 2.8 Task-hash normalization

Verifiers task hashes are raw 64-character lowercase SHA-256 hexadecimal strings.

Techtree protocol digests are:

```text
sha256:<64 lowercase hexadecimal characters>
```

Normalize at the Verifiers boundary:

```python
def normalize_verifiers_task_hash(raw: str) -> Digest:
    """Convert a Verifiers task hash to Techtree digest representation."""
```

Do not weaken Techtree’s `Digest` type.

## 2.9 Canonical result namespace

Use:

```bash
techtree run result <run-id>
```

not:

```bash
techtree climb result <run-id>
```

`climb` creates and describes a run.

`run` owns its status, logs, cancellation, and result.

---

# 3. Product boundary after WP5

The system after WP5 is:

```text
┌───────────────────────────────────────────────────────────────┐
│ techtree CLI                                                  │
│                                                               │
│  climb list                                                   │
│  climb show                                                   │
│  climb prepare                                                │
│  climb start                                                  │
│  run status                                                   │
│  run logs                                                     │
│  run cancel                                                   │
│  run result                                                   │
│  engine install                                               │
│  engine status                                                │
│  taskset validation                                           │
└───────────────────────────────┬───────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────┐
│ Techtree local state                                          │
│                                                               │
│  embedded public Climb catalog                                │
│  immutable CampaignSpecs                                      │
│  required DataPolicies                                        │
│  publisher taskset-validation commitments                     │
│  snapshotted candidate skills                                 │
│  immutable experiment manifests                               │
│  draft confirmation records                                   │
│  event-sourced runs                                           │
│  managed engine environments                                  │
│  local taskset locks                                          │
│  local taskset-validation receipts                            │
└───────────────────────────────┬───────────────────────────────┘
                                │
                    detached worker process
                                │
                                ▼
┌───────────────────────────────────────────────────────────────┐
│ WP3–WP5 worker                                                 │
│                                                               │
│  real taskset validation                                      │
│  fake baseline execution                                      │
│  fake candidate execution                                     │
│  fake development-only report                                 │
└───────────────────────────────┬───────────────────────────────┘
                                │
                       managed Python engine
                                │
                                ▼
┌───────────────────────────────────────────────────────────────┐
│ Prime Intellect Verifiers                                     │
│                                                               │
│  load Taskset                                                 │
│  compute actual task hashes                                   │
│  run model-free validate command                              │
│  write config.toml                                            │
│  write results.jsonl                                          │
│  write summary.json                                           │
│  write validate.log                                           │
└───────────────────────────────────────────────────────────────┘
```

The local scientific engine consumes the `CampaignSpec`.

The public `ClimbManifest` supplies:

- Discovery.
- Candidate constraints.
- Consent context.
- Public schedule and status.
- Publication policy.
- Leaderboard policy.

---

# 4. Core object hierarchy

## 4.1 `CampaignSpec`

`CampaignSpec` is the reusable scientific and execution contract.

It owns:

```text
taskset reference
task selection
membership commitment
publisher taskset-validation reference
environment
named agents
model
sampling
harness
subject runtime
mutation contract
evaluation backend
execution policy
scoring
evidence requirement
budgets
data-policy reference
optional program reference
optional outcome-contract reference
```

It does not own:

```text
public slug
opening or closing dates
candidate visibility
public leaderboard policy
public trace projection
proof-page metadata
```

## 4.2 `ClimbManifest`

`ClimbManifest` is a public invitation.

It owns:

```text
public identity
slug
version
title
status
schedule
CampaignSpec digest
candidate policy
publication policy
leaderboard policy
```

It does not duplicate model, harness, runtime, taskset, scoring, or mutation settings.

## 4.3 `ExperimentManifest`

An `ExperimentManifest` is one fully resolved variant derived from a Campaign:

```text
baseline
candidate
reproduction
trained variant, later
```

It references:

```text
campaign_spec_digest
optional public Climb context
optional program reference
data_policy_digest
optional outcome_contract_digest
```

## 4.4 `ImprovementProgram`

`ImprovementProgram` is deferred.

No model file, service, CLI command, persistence, or state machine is implemented in WP0–WP5.

Only this small reference shape is reserved:

```python
class ProgramRef(ProtocolModel):
    id: str
    version: int
```

## 4.5 `OutcomeContract`

`OutcomeContract` is deferred.

Only:

```text
outcome_contract_digest: Digest | None
```

is reserved in Campaign context and copied into execution artifacts.

## 4.6 `DataPolicy`

`DataPolicy` is required now because rights cannot safely be retrofitted after episodes are collected.

It governs:

```text
raw episode retention
server upload
public release
reproduction access
training use
derived aggregate publication
candidate skill ownership and release
future revocation
```

WP0–WP5 do not upload episodes, but all drafts, manifests, fake receipts, and fake reports must carry the policy digest.

## 4.7 `EvaluationBackend`

Evaluation backend and subject runtime are independent:

```text
Evaluation backend
    Who orchestrated and attested to the evaluation?

Subject runtime
    Where did the evaluated agent execute?
```

For v0.1:

```yaml
evaluation_backend:
  kind: local_techtree
  attestation: participant
```

and separately:

```yaml
agents:
  subject:
    runtime:
      type: docker
```

Future backends may include:

```text
prime_lab
independent_reproducer
```

---

# 5. Explicit non-goals

Do not include:

- SkillOpt optimization loops.
- GEPA optimization loops.
- Prime Agent self-refinement.
- Multiple candidate generations.
- Multiple named agents inside one environment.
- Codex, Claude Code, or OpenClaw subjects.
- Paid compute orchestration.
- Token rewards.
- Submission bounties.
- Onchain anchoring.
- Remote Techtree workers.
- A trajectory marketplace.
- Private enterprise tasksets.
- Long-term secret benchmark custody.
- A generic environment registry.
- A generic skill marketplace.
- A Techtree-native evaluator or reward language.
- A Techtree-native trace format replacing Verifiers.
- A graph database.
- `ImprovementProgram` behavior.
- Blueprint artifacts.
- OutcomeContract behavior.
- Environment qualification.
- Release decisions.
- Trace selection or exports.
- Prime Lab handoffs.
- NeMo Relay.

Reserve these CLI namespaces but do not implement them:

```text
techtree program ...
techtree blueprint ...
techtree forge ...
techtree verify ...
techtree uplift ...
techtree trace ...
techtree lab ...
```

The first implemented product namespace remains:

```text
techtree climb ...
```

---

# 6. Non-negotiable architectural rules

## 6.1 The CLI is the stable host-agent boundary

The future Hermes plugin calls the CLI as a subprocess.

It must not import Techtree into Hermes’s Python process.

The stable contract is:

```text
command arguments
JSON output envelope
error codes
exit codes
NextAction format
no-prompt machine mode
stdout/stderr separation
```

## 6.2 The worker is separate from the CLI process

A run must survive:

- Terminal closure.
- Hermes turn completion.
- Host-agent session disconnect.
- CLI exit.

`techtree climb start` launches:

```text
techtree-worker execute --run-id <id>
```

and returns promptly.

## 6.3 Source skills are never evaluated directly

The user’s skill directory is mutable.

The run uses a Techtree-owned immutable snapshot.

## 6.4 Campaign and experiment objects are immutable scientific inputs

The worker may read Campaign and Experiment objects.

The worker may not mutate them.

## 6.5 The fake executor is unmistakably fake

Every fake result states:

```text
execution_backend: fake
proof_grade: development_only
publication_eligible: false
```

## 6.6 Verifiers remains the future scoring authority

WP5 uses Verifiers for taskset loading and model-free validation.

WP6 uses Verifiers for Episodes, Traces, rewards, and real evaluation.

## 6.7 Data rights follow the Campaign

Every execution artifact copies:

```text
data_policy_digest
```

No run may silently change its rights policy.

## 6.8 Public context is optional and separate

The scientific engine requires only:

```text
campaign_spec_digest
```

A public Climb adds:

```json
{
  "public_context": {
    "kind": "climb",
    "climb_digest": "sha256:..."
  }
}
```

A future private campaign uses:

```json
{
  "public_context": null,
  "program_ref": {
    "id": "program_...",
    "version": 3
  }
}
```

---

# 7. Technology choices

## 7.1 Python

Use Python 3.12.

Ordinary package:

```toml
requires-python = ">=3.12,<3.14"
```

Managed engine:

```text
Python 3.12.x
```

## 7.2 Runtime dependencies

```toml
dependencies = [
  "cryptography>=45,<47",
  "filelock>=3.18,<4",
  "platformdirs>=4,<5",
  "pydantic>=2.12,<3",
  "rfc8785>=0.1,<1",
  "rich>=14,<15",
  "tomli-w>=1.2,<2",
  "typer>=0.16,<1",
]
```

The ordinary package does not depend directly on Verifiers.

## 7.3 Development dependencies

```toml
[dependency-groups]
dev = [
  "mypy>=1.17,<2",
  "pytest>=8,<9",
  "pytest-cov>=6,<8",
  "pytest-xdist>=3,<4",
  "ruff>=0.12,<1",
]
```

## 7.4 CLI framework

Use Typer for command structure and Rich for human rendering.

Machine mode disables Rich output.

## 7.5 Protocol models

Use Pydantic v2.

Signed or hashed objects use frozen, strict, extra-forbidden models.

Mutable local state uses strict, extra-forbidden, assignment-validating models.

---

# 8. Complete repository skeleton

```text
techtree-python/
├── .gitignore
├── .python-version
├── LICENSE
├── Makefile
├── README.md
├── pyproject.toml
├── uv.lock
│
├── docs/
│   ├── architecture.md
│   ├── cli-json-contract.md
│   ├── protocol-v1alpha1.md
│   ├── run-state-machine.md
│   ├── wp6-handoff.md
│   └── decisions/
│       ├── 0001-wp0-wp5-fixed-decisions.md
│       └── 0002-campaign-kernel.md
│
├── schemas/
│   └── v1alpha1/
│       ├── campaign.schema.json
│       ├── cli-envelope.schema.json
│       ├── climb.schema.json
│       ├── data-policy.schema.json
│       ├── engine.schema.json
│       ├── episode-receipt.schema.json
│       ├── evaluation-backend.schema.json
│       ├── experiment-manifest.schema.json
│       ├── run-state.schema.json
│       ├── skill-artifact.schema.json
│       ├── submission-draft.schema.json
│       ├── taskset-lock.schema.json
│       ├── taskset-validation-receipt.schema.json
│       └── uplift-report.schema.json
│
├── src/
│   └── techtree/
│       ├── __init__.py
│       ├── __main__.py
│       ├── canonical.py
│       ├── constants.py
│       ├── crypto.py
│       ├── errors.py
│       ├── fs.py
│       ├── ids.py
│       ├── paths.py
│       ├── settings.py
│       ├── version.py
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── campaign.py
│       │   ├── cli.py
│       │   ├── climb.py
│       │   ├── data_policy.py
│       │   ├── engine.py
│       │   ├── episode_receipt.py
│       │   ├── evaluation_backend.py
│       │   ├── experiment.py
│       │   ├── run.py
│       │   ├── skill.py
│       │   ├── uplift_report.py
│       │   └── validation.py
│       │
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── app.py
│       │   ├── context.py
│       │   ├── invoke.py
│       │   ├── output.py
│       │   └── commands/
│       │       ├── __init__.py
│       │       ├── climb.py
│       │       ├── doctor.py
│       │       ├── engine.py
│       │       ├── run.py
│       │       └── setup.py
│       │
│       ├── doctor/
│       │   ├── __init__.py
│       │   ├── checks.py
│       │   └── service.py
│       │
│       ├── catalog/
│       │   ├── __init__.py
│       │   ├── repository.py
│       │   └── service.py
│       │
│       ├── skills/
│       │   ├── __init__.py
│       │   ├── archive.py
│       │   ├── policy.py
│       │   ├── scanner.py
│       │   └── service.py
│       │
│       ├── manifests/
│       │   ├── __init__.py
│       │   ├── builder.py
│       │   └── compare.py
│       │
│       ├── drafts/
│       │   ├── __init__.py
│       │   ├── confirmation.py
│       │   └── store.py
│       │
│       ├── runs/
│       │   ├── __init__.py
│       │   ├── events.py
│       │   ├── executor.py
│       │   ├── fake.py
│       │   ├── launcher.py
│       │   ├── machine.py
│       │   ├── service.py
│       │   └── store.py
│       │
│       ├── worker/
│       │   ├── __init__.py
│       │   ├── execute.py
│       │   └── main.py
│       │
│       ├── engines/
│       │   ├── __init__.py
│       │   ├── bundle.py
│       │   ├── installer.py
│       │   ├── registry.py
│       │   └── runner.py
│       │
│       ├── tasksets/
│       │   ├── __init__.py
│       │   ├── membership.py
│       │   ├── resolver.py
│       │   ├── service.py
│       │   └── verifiers_cli.py
│       │
│       └── resources/
│           ├── catalog/
│           │   ├── catalog.json
│           │   ├── campaigns/
│           │   │   └── procedure-transfer-dev.json
│           │   ├── climbs/
│           │   │   └── procedure-transfer-dev.json
│           │   ├── data-policies/
│           │   │   └── procedure-transfer-dev.json
│           │   └── taskset-validations/
│           │       └── procedure-transfer-dev.json
│           │
│           ├── engines/
│           │   └── default/
│           │       ├── engine.json
│           │       ├── pyproject.toml
│           │       ├── uv.lock
│           │       └── packages/
│           │           └── procedure-transfer-v1/
│           │               ├── pyproject.toml
│           │               └── procedure_transfer_v1/
│           │                   ├── __init__.py
│           │                   ├── algorithm.py
│           │                   ├── dataset.py
│           │                   └── taskset.py
│           │
│           └── engine_scripts/
│               └── inspect_taskset.py
│
├── tools/
│   ├── build_engine_bundle.py
│   ├── build_fixture_catalog.py
│   ├── build_goldens.py
│   └── export_schemas.py
│
└── tests/
    ├── conftest.py
    │
    ├── unit/
    │   ├── test_campaign_models.py
    │   ├── test_canonical.py
    │   ├── test_confirmation.py
    │   ├── test_crypto.py
    │   ├── test_data_policy.py
    │   ├── test_evaluation_backend.py
    │   ├── test_ids.py
    │   ├── test_manifest_compare.py
    │   ├── test_run_machine.py
    │   ├── test_skill_archive.py
    │   ├── test_skill_scanner.py
    │   └── test_taskset_models.py
    │
    ├── contract/
    │   ├── test_catalog_object_graph.py
    │   ├── test_cli_envelope.py
    │   ├── test_cli_machine_mode.py
    │   ├── test_json_schemas.py
    │   └── test_protocol_golden_files.py
    │
    ├── integration/
    │   ├── test_engine_install.py
    │   ├── test_fake_run.py
    │   ├── test_run_cancel.py
    │   ├── test_skill_prepare.py
    │   ├── test_taskset_membership.py
    │   └── test_taskset_validation.py
    │
    ├── fixtures/
    │   ├── catalog/
    │   ├── climbs/
    │   ├── campaigns/
    │   ├── data-policies/
    │   ├── engines/
    │   ├── skills/
    │   │   ├── invalid-binary/
    │   │   ├── invalid-secret/
    │   │   ├── invalid-symlink/
    │   │   └── valid-procedure/
    │   └── protocol/
    │
    └── golden/
        ├── campaign.json
        ├── climb.json
        ├── cli-envelope.json
        ├── data-policy.json
        ├── experiment-baseline.json
        ├── experiment-candidate.json
        ├── fake-uplift-report.json
        ├── skill-artifact.json
        ├── taskset-lock.json
        └── taskset-validation-receipt.json
```

Do not create empty future service directories for Blueprint, programs, decisions, traces, or handoffs.

Only add the forward-compatible models required by this specification.

---

# 9. Root and documentation file specifications

## 9.1 `pyproject.toml`

### Responsibility

Defines:

- Package metadata.
- Runtime dependencies.
- Development dependencies.
- Console entry points.
- Package-data inclusion.
- Ruff, pytest, and mypy configuration.
- Python-version support.

### Required console scripts

```toml
[project.scripts]
techtree = "techtree.cli.app:main"
techtree-worker = "techtree.worker.main:main"
```

### Required package data

Include:

```text
resources/catalog/**/*
resources/engines/**/*
resources/engine_scripts/**/*
```

### Build system

Use Hatchling:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### Rules

- The ordinary package must not depend directly on Verifiers.
- The ordinary package must not depend on Hermes.
- The ordinary package must not depend on NeMo Relay.
- Engine dependencies belong in the independently locked managed engine.
- Do not add a web client in WP0–WP5; the catalog is embedded.

---

## 9.2 `uv.lock`

Locks only the ordinary CLI package.

It does not lock the managed Verifiers engine.

The managed engine has:

```text
src/techtree/resources/engines/default/uv.lock
```

---

## 9.3 `.python-version`

Contents:

```text
3.12
```

It controls local repository development.

The engine descriptor separately pins engine Python.

---

## 9.4 `.gitignore`

Ignore:

```text
.venv/
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
dist/
build/
*.egg-info/
.DS_Store
.idea/
.vscode/
tmp/
```

Do not ignore:

```text
uv.lock
schemas/
tests/golden/
resources/engines/default/uv.lock
resources/catalog/
```

Those are committed scientific and protocol artifacts.

---

## 9.5 `README.md`

Required sections:

1. Product statement.
2. Campaign-kernel explanation.
3. Current development status.
4. Installation.
5. Local development.
6. Command overview.
7. Explanation that WP0–WP5 runs are development-only.
8. Repository architecture.
9. Testing.
10. Security assumptions.
11. Generated-file policy.
12. Link to protocol documentation.

Required warning:

```text
The WP0–WP5 implementation validates real Prime Intellect Verifiers
tasksets but uses a fake baseline/candidate executor. It does not evaluate
a real agent. No result produced by the fake executor is a capability proof.
```

Required Campaign explanation:

```text
Climb is a public wrapper around a reusable CampaignSpec.
Execution artifacts reference the CampaignSpec, not the public Climb directly.
```

---

## 9.6 `Makefile`

Required targets:

```makefile
install
lint
format
format-check
typecheck
test
test-unit
test-contract
test-integration
schemas
engine-bundle
fixture-catalog
goldens
regenerate
generated-check
verifiers-preflight
check
clean
```

Definitions:

```text
schemas
    Run tools/export_schemas.py.

engine-bundle
    Run tools/build_engine_bundle.py.

fixture-catalog
    Run tools/build_fixture_catalog.py.

goldens
    Run tools/build_goldens.py.

regenerate
    engine-bundle → fixture-catalog → goldens → schemas.

generated-check
    Regenerate into a temporary tree and fail on drift.

verifiers-preflight
    Run the exact pinned-Verifiers compatibility tests.

check
    format-check → lint → typecheck → test → generated-check.
```

`generated-check` must not mutate the working tree.

---

## 9.7 `docs/architecture.md`

Contains:

- Host CLI architecture.
- Campaign versus Climb separation.
- Detached worker architecture.
- Local filesystem.
- Managed engine boundary.
- Taskset validation flow.
- DataPolicy propagation.
- Evaluation backend versus subject runtime.
- Explicit exclusion of Hermes execution before WP6.
- Explicit exclusion of Relay.
- Dependency-direction rules.
- Future reuse by Verify, Forge, Uplift, and reproduction.

No copied source implementation.

---

## 9.8 `docs/protocol-v1alpha1.md`

Normatively defines:

- Schema-version policy.
- ID formats.
- Digest format.
- Canonicalization.
- Signatures.
- CampaignSpec.
- ClimbManifest.
- PublicContext.
- ProgramRef.
- DataPolicy.
- EvaluationBackend.
- SkillArtifact.
- ExperimentManifest.
- TasksetLock.
- TasksetValidationReceipt.
- EpisodeReceipt.
- UpliftReport.
- Development-only fake result semantics.
- Generic campaign references.
- Data-policy immutability.
- Evaluation-backend immutability.

---

## 9.9 `docs/cli-json-contract.md`

Defines:

- One JSON object on stdout.
- Logs only on stderr.
- Exit-code rules.
- `CliEnvelope`.
- `NextAction`.
- Non-interactive mode.
- Stable command names.
- How future Hermes and other host-agent plugins call the CLI.
- Redaction requirements.
- Why command vectors are arrays rather than shell strings.

---

## 9.10 `docs/run-state-machine.md`

Defines:

- All run phases.
- Allowed transitions.
- Terminal states.
- Event format.
- State projection.
- Heartbeat semantics.
- PID semantics.
- Cancellation semantics.
- Recovery semantics.
- Fake execution semantics.
- WP5 taskset-validation insertion.
- Data-policy and Campaign references stored in `RunRequest`.

---

## 9.11 `docs/wp6-handoff.md`

Defines exactly what WP6 may assume:

```text
stable CampaignSpec
stable ClimbManifest wrapper
stable DataPolicy
stable EvaluationBackend
stable SkillArtifact
stable ExperimentManifest
stable CLI envelope
working detached worker
working managed engine
working Taskset resolver
working taskset validation
working fake end-to-end run
```

WP6 adds:

```text
Verifiers eval config compiler
Hermes harness selection
Docker subject runtime
real baseline run
real candidate run
Episode parser
EpisodeReceipt builder
real comparison verifier
```

WP6 must not collapse Campaign and Climb back together.

---

## 9.12 `docs/decisions/0001-wp0-wp5-fixed-decisions.md`

Records:

```text
Verifiers pin:
  7e1c47d24d055aae587ee8259f77a3e8e193513a

Shuffle:
  false only

Development Campaign:
  procedure-transfer-dev-campaign@1

Development Climb:
  procedure-transfer-dev@1

Bundled Hermes skills:
  false in baseline and candidate

Signing:
  primitives only; no live signing through WP5

Canonical result command:
  techtree run result

Relay:
  excluded

Task-hash boundary:
  normalize raw Verifiers hex to sha256:<hex>
```

This is the compact binding source for worker threads.

---

## 9.13 `docs/decisions/0002-campaign-kernel.md`

Records:

- Climb is a public wrapper.
- CampaignSpec owns scientific execution.
- DataPolicy is required.
- EvaluationBackend is separate from subject runtime.
- Execution artifacts reference `campaign_spec_digest`.
- `program_ref` and `outcome_contract_digest` are optional forward-compatible pointers.
- ImprovementProgram behavior is deferred.
- OutcomeContract behavior is deferred.
- No public product policy is duplicated inside CampaignSpec.

---

# 10. Core module file specifications

## 10.1 `src/techtree/__init__.py`

### Responsibility

Defines the supported public Python import surface.

### Exports

```python
from techtree.models.campaign import CampaignSpec
from techtree.models.climb import ClimbManifest
from techtree.models.data_policy import DataPolicy
from techtree.models.evaluation_backend import EvaluationBackendSpec
from techtree.models.skill import SkillArtifact
from techtree.models.experiment import ExperimentManifest
from techtree.models.validation import TasksetValidationReceipt
from techtree.models.episode_receipt import EpisodeReceipt
from techtree.models.uplift_report import UpliftReport
from techtree.version import __version__
```

### Rules

- No filesystem access.
- No settings loading.
- No CLI registration.
- No resource extraction.
- No side effects.
- Do not export deferred `ImprovementProgram` or `OutcomeContract` models.

---

## 10.2 `src/techtree/__main__.py`

### Function

```python
def main() -> None:
    """Invoke the Techtree CLI entry point."""
```

Implementation delegates to:

```python
techtree.cli.app.main
```

Supports:

```bash
python -m techtree
```

---

## 10.3 `src/techtree/version.py`

### Contents

```python
__version__: str
PROTOCOL_VERSION: str
CLI_SCHEMA_VERSION: str
```

### Functions

```python
def package_version() -> str:
    """Return installed package version through importlib.metadata."""

def version_info() -> dict[str, str]:
    """Return package and protocol versions for CLI and Doctor output."""
```

Handle editable-source execution gracefully.

---

## 10.4 `src/techtree/constants.py`

### Responsibility

Central protocol constants.

### Constants

```python
DIGEST_PREFIX = "sha256:"

CLI_SCHEMA_VERSION = "techtree.cli.v1"
CATALOG_SCHEMA_VERSION = "techtree.catalog.v1alpha1"
CAMPAIGN_SCHEMA_VERSION = "techtree.campaign.v1alpha1"
CLIMB_SCHEMA_VERSION = "techtree.climb.v1alpha1"
DATA_POLICY_SCHEMA_VERSION = "techtree.data-policy.v1alpha1"
EVALUATION_BACKEND_SCHEMA_VERSION = "techtree.evaluation-backend.v1alpha1"
SKILL_SCHEMA_VERSION = "techtree.skill.v1alpha1"
EXPERIMENT_SCHEMA_VERSION = "techtree.experiment.v1alpha1"
TASKSET_LOCK_SCHEMA_VERSION = "techtree.taskset-lock.v1alpha1"
TASKSET_VALIDATION_SCHEMA_VERSION = "techtree.taskset-validation.v1alpha1"
EPISODE_RECEIPT_SCHEMA_VERSION = "techtree.episode-receipt.v1alpha1"
UPLIFT_SCHEMA_VERSION = "techtree.uplift-report.v1alpha1"

DEFAULT_CONFIRMATION_TTL_SECONDS = 900
DEFAULT_WORKER_HEARTBEAT_SECONDS = 2
DEFAULT_STALE_HEARTBEAT_SECONDS = 15

MAX_SKILL_FILE_BYTES = 256 * 1024
MAX_SKILL_TOTAL_BYTES = 2 * 1024 * 1024
MAX_SKILL_FILES = 64

ALLOWED_SKILL_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
}

PINNED_VERIFIERS_REVISION = (
    "7e1c47d24d055aae587ee8259f77a3e8e193513a"
)
```

No behavior belongs here.

---

## 10.5 `src/techtree/errors.py`

### Hierarchy

```python
class TechtreeError(Exception)
class UsageError(TechtreeError)
class ValidationError(TechtreeError)
class PrerequisiteError(TechtreeError)
class NotFoundError(TechtreeError)
class ConflictError(TechtreeError)
class AuthenticationError(TechtreeError)
class EngineError(TechtreeError)
class RunError(TechtreeError)
class VerificationError(TechtreeError)
class CancellationError(TechtreeError)
class PolicyError(TechtreeError)
```

### `TechtreeError` fields

```python
code: str
exit_code: int
retryable: bool
message: str
details: dict[str, JsonValue]
next_actions: list[NextAction]
```

### Functions

```python
def error_to_cli_error(error: TechtreeError) -> CliError:
    """Convert an internal typed error to machine-safe CLI error data."""

def sanitize_exception_message(error: Exception) -> str:
    """Remove secret-looking values and unstable traceback detail."""

def exit_code_for(error: Exception) -> int:
    """Return documented CLI exit code."""
```

### Rules

- User messages are actionable.
- Debug tracebacks go to stderr only.
- Secret values never enter `details`.
- Data-policy contradictions raise `PolicyError`.

---

## 10.6 `src/techtree/ids.py`

### ID format

```text
<prefix>_<32 lowercase hexadecimal characters>
```

Prefixes include:

```text
campaign
climb
draft
run
receipt
uplift
policy
```

### Functions

```python
def new_id(prefix: str) -> str:
    """Create a new prefixed UUID4 hexadecimal identifier."""

def validate_id(value: str, expected_prefix: str | None = None) -> str:
    """Validate syntax and optionally require one prefix."""

def id_prefix(value: str) -> str:
    """Return the prefix from a valid ID."""
```

IDs are not integrity values.

Digests provide integrity.

---

## 10.7 `src/techtree/canonical.py`

### Responsibility

Sole canonical serialization and hashing implementation.

### Standard

Use RFC 8785 JSON Canonicalization Scheme.

### Functions

```python
def to_json_value(value: object) -> JsonValue:
    """
    Convert supported Pydantic models, enums, datetimes, paths,
    Decimals, mappings, and sequences to JSON-compatible values.
    """

def canonical_json_bytes(value: object) -> bytes:
    """Serialize a JSON value using RFC 8785 and return UTF-8 bytes."""

def canonical_json_text(value: object) -> str:
    """Return canonical JSON text."""

def sha256_digest_bytes(data: bytes) -> Digest:
    """Return sha256:<hex> for raw bytes."""

def digest_object(value: object) -> Digest:
    """Canonicalize a protocol object and return its digest."""

def verify_bytes_digest(data: bytes, expected: Digest) -> bool:
    """Use constant-time comparison for raw byte digest."""

def verify_object_digest(value: object, expected: Digest) -> bool:
    """Use constant-time comparison for canonical object digest."""

def normalize_verifiers_task_hash(raw: str) -> Digest:
    """
    Validate a raw 64-character lowercase Verifiers SHA-256 task hash
    and prefix it with sha256:.
    """
```

### Rules

- Aware datetimes convert to UTC with `Z`.
- Naive datetimes fail.
- NaN and infinity fail.
- Uppercase Verifiers hashes fail.
- Already-prefixed internal digests may be accepted only by a separate
  `validate_digest` helper, not silently by the raw-boundary function.

---

## 10.8 `src/techtree/crypto.py`

### Responsibility

Ed25519 primitives only.

### Functions

```python
def generate_private_key() -> Ed25519PrivateKey:
    """Create a new Ed25519 key."""

def public_key_bytes(private_key: Ed25519PrivateKey) -> bytes:
    """Return raw public-key bytes."""

def private_key_bytes(private_key: Ed25519PrivateKey) -> bytes:
    """Return raw private-key bytes."""

def load_private_key(raw: bytes) -> Ed25519PrivateKey:
    """Load and validate raw private key material."""

def load_public_key(raw: bytes) -> Ed25519PublicKey:
    """Load and validate raw public key material."""

def sign_digest(
    private_key: Ed25519PrivateKey,
    digest: Digest,
    *,
    key_id: str,
) -> SignatureEnvelope:
    """Sign the ASCII digest string."""

def verify_signature(
    public_key: Ed25519PublicKey,
    digest: Digest,
    signature: SignatureEnvelope,
) -> bool:
    """Verify the digest signature."""
```

No persistent key storage or live signing flow is implemented.

---

## 10.9 `src/techtree/fs.py`

### Responsibility

Safe filesystem primitives.

### Functions

```python
def atomic_write_bytes(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    """Write, fsync, chmod, and atomically replace."""

def atomic_write_text(path: Path, text: str, *, mode: int = 0o600) -> None:
    """UTF-8 wrapper."""

def atomic_write_json(path: Path, value: object, *, mode: int = 0o600) -> None:
    """Write readable JSON atomically."""

def read_json(path: Path) -> JsonValue:
    """Read UTF-8 JSON and raise typed malformed-data errors."""

def ensure_private_directory(path: Path) -> None:
    """Create a directory and apply 0700 where supported."""

def fsync_directory(path: Path) -> None:
    """Best-effort directory fsync."""

def remove_tree(path: Path) -> None:
    """Remove run-owned data without following links."""

def realpath_within(path: Path, root: Path) -> bool:
    """Return whether a resolved path is contained in root."""

def open_exclusive(path: Path, mode: int = 0o600) -> BinaryIO:
    """Create an immutable file with O_EXCL semantics."""
```

Immutable Campaign, Climb, DataPolicy, manifest, lock, and receipt artifacts use exclusive creation.

---

## 10.10 `src/techtree/paths.py`

### Class

```python
@dataclass(frozen=True)
class TechtreePaths:
    root: Path
    config_file: Path
    cache_dir: Path
    drafts_dir: Path
    runs_dir: Path
    engines_dir: Path
    identities_dir: Path
```

### Methods

```python
def draft_dir(self, draft_id: str) -> Path
def run_dir(self, run_id: str) -> Path
def engine_dir(self, digest: Digest) -> Path
```

### Functions

```python
def default_paths() -> TechtreePaths:
    """Resolve platform paths through platformdirs."""

def paths_from_root(root: Path) -> TechtreePaths:
    """Construct deterministic test paths."""

def ensure_path_layout(paths: TechtreePaths) -> None:
    """Create top-level private directories."""
```

No import-time directory creation.

---

## 10.11 `src/techtree/settings.py`

### Model

```python
class Settings(StateModel):
    api_url: str | None = None
    active_engine_digest: Digest | None = None
    log_level: str = "INFO"
    output_mode: Literal["human", "json"] = "human"
```

### Functions

```python
def load_settings(paths: TechtreePaths) -> Settings:
    """Load TOML or return defaults."""

def save_settings(paths: TechtreePaths, settings: Settings) -> None:
    """Atomically write TOML."""

def settings_from_environment(base: Settings) -> Settings:
    """Apply supported TECHTREE_* environment overrides."""

def resolved_settings(paths: TechtreePaths) -> Settings:
    """Load file settings and apply environment values."""
```

No provider secrets belong in this model.

---

# 11. Protocol model file specifications

## 11.1 `models/__init__.py`

Exports only stable model classes.

It must not import services, CLI code, resources, or settings.

It should group exports by:

```text
Campaign and public wrapper
execution artifacts
taskset validation
CLI and local state
```

---

## 11.2 `models/base.py`

### Types

```python
JsonScalar
JsonValue
Digest
UtcDateTime
NonEmptyString
```

### Base classes

```python
class ProtocolModel(BaseModel):
    """Frozen, strict, extra-forbidden hashed or signed object."""

class StateModel(BaseModel):
    """Strict mutable local-state projection."""
```

### Shared models

```python
class ArtifactRef(ProtocolModel):
    digest: Digest
    media_type: str
    size: int
    relative_path: str | None = None

class PublicKeyRef(ProtocolModel):
    algorithm: Literal["ed25519"]
    key_id: str
    public_key: str

class SignatureEnvelope(ProtocolModel):
    algorithm: Literal["ed25519"]
    key_id: str
    signature: str

class ObjectEnvelope(ProtocolModel, Generic[T]):
    payload: T
    payload_digest: Digest
    signature: SignatureEnvelope | None = None
```

### Validators

- Digest syntax.
- Positive artifact size.
- UTC-aware datetimes.
- Non-empty key IDs.
- Valid base64.
- `payload_digest` must be checked by services, not automatically recomputed in model construction.

---

## 11.3 `models/evaluation_backend.py`

### Purpose

Models who orchestrates and attests to evaluation independently of the agent runtime.

### Enums

```python
class EvaluationBackendKind(str, Enum):
    LOCAL_TECHTREE = "local_techtree"
    PRIME_LAB = "prime_lab"
    INDEPENDENT_REPRODUCER = "independent_reproducer"

class AttestationKind(str, Enum):
    PARTICIPANT = "participant"
    PLATFORM = "platform"
    INDEPENDENT = "independent"
```

### Model

```python
class EvaluationBackendSpec(ProtocolModel):
    schema_version: Literal["techtree.evaluation-backend.v1alpha1"]
    kind: EvaluationBackendKind
    attestation: AttestationKind
    workspace_ref: str | None = None
    provider_run_ref: str | None = None
    executor_identity: str | None = None
```

### Validation rules

```text
local_techtree:
    attestation must be participant
    workspace_ref must be null
    provider_run_ref must be null
    executor_identity may be null in WP0–WP5

prime_lab:
    attestation must be platform
    workspace_ref or provider_run_ref must be present

independent_reproducer:
    attestation must be independent
    executor_identity must be present
```

WP0–WP5 permit only `local_techtree`.

Future enum members may exist in the schema but services reject them until implemented.

---

## 11.4 `models/data_policy.py`

### Purpose

Defines rights and permitted future uses of Campaign artifacts.

### Models

```python
class DataOwner(ProtocolModel):
    kind: Literal["participant", "account", "shared"]
    account_ref: str | None = None

class RawEpisodePolicy(ProtocolModel):
    local_retention: Literal["allowed", "prohibited", "required"]
    server_upload: Literal["allowed", "prohibited", "consent_required"]
    public_release: Literal["allowed", "prohibited", "consent_required"]
    reproduction_access: Literal["allowed", "prohibited", "consent_required"]
    training_use: Literal["allowed", "prohibited", "consent_required"]

class DerivedArtifactPolicy(ProtocolModel):
    aggregate_scores: Literal["public", "private", "prohibited"]
    uplift_report: Literal["public", "private", "prohibited"]
    redacted_trace_projection: Literal["public", "private", "prohibited"]
    anonymized_product_analytics: Literal[
        "allowed",
        "prohibited",
        "consent_required",
    ]

class CandidateSkillPolicy(ProtocolModel):
    ownership: Literal["participant", "account", "shared"]
    public_release: Literal[
        "required_for_climb",
        "allowed",
        "prohibited",
        "consent_required",
    ]
    training_use: Literal["allowed", "prohibited", "consent_required"]

class RevocationPolicy(ProtocolModel):
    future_use_revocable: bool
    immutable_published_proofs_remain: bool

class DataPolicy(ProtocolModel):
    schema_version: Literal["techtree.data-policy.v1alpha1"]
    id: str
    version: int
    owner: DataOwner
    raw_episodes: RawEpisodePolicy
    derived_artifacts: DerivedArtifactPolicy
    candidate_skill: CandidateSkillPolicy
    revocation: RevocationPolicy
```

### Development policy

```yaml
owner:
  kind: participant

raw_episodes:
  local_retention: allowed
  server_upload: prohibited
  public_release: prohibited
  reproduction_access: consent_required
  training_use: prohibited

derived_artifacts:
  aggregate_scores: public
  uplift_report: public
  redacted_trace_projection: public
  anonymized_product_analytics: allowed

candidate_skill:
  ownership: participant
  public_release: required_for_climb
  training_use: prohibited

revocation:
  future_use_revocable: true
  immutable_published_proofs_remain: true
```

### Validation rules

- `account_ref` is required only when owner kind is `account`.
- Public Climb candidate policy may not contradict DataPolicy.
- WP0–WP5 do not upload any artifact, regardless of policy allowance.
- DataPolicy itself is immutable by digest.
- Any change creates a new DataPolicy version and CampaignSpec.

---

## 11.5 `models/campaign.py`

### Shared low-level models

```python
class ProgramRef(ProtocolModel):
    id: str
    version: int

class PublicContext(ProtocolModel):
    kind: Literal["climb"]
    climb_digest: Digest

class CampaignContext(ProtocolModel):
    program_ref: ProgramRef | None = None
    outcome_contract_digest: Digest | None = None
```

### Package and taskset models

```python
class PackageRef(ProtocolModel):
    kind: Literal["embedded", "git", "hub"]
    name: str
    revision: str
    digest: Digest

class TasksetRef(ProtocolModel):
    kind: Literal["verifiers"]
    id: str
    package: PackageRef
    config: dict[str, JsonValue]

class TaskSelection(ProtocolModel):
    num_tasks: int
    num_rollouts: int
    shuffle: Literal[False]

class TaskMembershipCommitment(ProtocolModel):
    mode: Literal["committed"]
    ordered_task_hashes: list[Digest]
    membership_digest: Digest

class CampaignTaskset(ProtocolModel):
    ref: TasksetRef
    selection: TaskSelection
    membership: TaskMembershipCommitment
    validation_receipt_digest: Digest
```

### Subject models

```python
class ModelSpec(ProtocolModel):
    provider: str
    model_id: str
    revision: str | None
    credential_env: str

class SamplingSpec(ProtocolModel):
    temperature: float
    max_tokens: int

class HarnessSpec(ProtocolModel):
    id: str
    version: str
    use_bundled_skill: bool
    skills: list[ArtifactRef]

class RuntimeSpec(ProtocolModel):
    type: Literal["docker"]
    image: str
    supported_platforms: list[str]
    cpu: float | None
    memory_gb: float | None
    network_policy: Literal["restricted", "open"]

class AgentSpec(ProtocolModel):
    model: ModelSpec
    sampling: SamplingSpec
    harness: HarnessSpec
    runtime: RuntimeSpec
    trainable: bool

class EnvironmentSpec(ProtocolModel):
    id: Literal["single-agent"]
```

### Scientific contract models

```python
class MutationContract(ProtocolModel):
    kind: Literal["skill_insertion"]
    target_agent: Literal["subject"]
    allowed_differences: list[str]
    minimum_skills: int
    maximum_skills: int

class ExecutionSpec(ProtocolModel):
    order: Literal["baseline_then_candidate"]
    max_concurrent: int
    timeout_seconds: int
    retry_limit: int

class ScoringSpec(ProtocolModel):
    primary_reward: str
    aggregation: Literal["mean"]
    require_candidate_above_baseline: bool
    minimum_absolute_delta: float

class EvidenceRequirements(ProtocolModel):
    verifiers_episode: Literal["required"]
    runtime_evidence: Literal["not_required", "optional", "required"]

class BudgetSpec(ProtocolModel):
    maximum_input_tokens: int | None = None
    maximum_output_tokens: int | None = None
    maximum_model_calls: int | None = None
    maximum_usd: float | None = None

class CampaignMetadata(ProtocolModel):
    id: str
    version: int
    purpose: Literal[
        "component_uplift",
        "baseline",
        "release_assurance",
        "environment_validation",
        "reproduction",
    ]

class CampaignSpec(ProtocolModel):
    schema_version: Literal["techtree.campaign.v1alpha1"]
    kind: Literal["Campaign"]
    metadata: CampaignMetadata
    context: CampaignContext
    taskset: CampaignTaskset
    environment: EnvironmentSpec
    agents: dict[str, AgentSpec]
    mutation_contract: MutationContract
    evaluation_backend: EvaluationBackendSpec
    execution: ExecutionSpec
    scoring: ScoringSpec
    evidence: EvidenceRequirements
    budgets: BudgetSpec
    data_policy_digest: Digest
```

### Campaign validation rules

- `agents` contains exactly `subject` in v0.1.
- Subject harness baseline skills are empty.
- `num_rollouts == 1`.
- `shuffle is False`.
- Allowed difference is exactly:

```text
/agents/subject/harness/skills
```

- Membership count equals `num_tasks`.
- Membership hashes are unique.
- Evaluation backend is `local_techtree` in WP0–WP5.
- Runtime type is Docker, though not executed before WP6.
- `use_bundled_skill` is false.
- Runtime evidence is `not_required` in WP0–WP5.
- `data_policy_digest` is required.
- Credential env matches a safe environment-variable pattern.
- No public publication policy appears here.

---

## 11.6 `models/climb.py`

### Purpose

Public wrapper around a Campaign.

### Models

```python
class CandidateConstraints(ProtocolModel):
    min_skills: int
    max_skills: int
    format: Literal["techtree-instruction-skill-v1"]

class CandidatePolicy(ProtocolModel):
    required_mutation: Literal["skill_insertion"]
    skill_visibility: Literal["public", "private"]
    constraints: CandidateConstraints

class PublicationPolicy(ProtocolModel):
    report_visibility: Literal["public", "private"]
    raw_episode_visibility: Literal["private", "prohibited"]
    public_trace_projection: Literal["redacted", "none"]
    proof_grade: Literal["development_only", "P1"]

class LeaderboardPolicy(ProtocolModel):
    enabled: bool
    evidence_required: Literal[
        "not_required",
        "complete",
        "complete_or_partial",
    ]

class ClimbMetadata(ProtocolModel):
    id: str
    slug: str
    version: int
    title: str
    summary: str
    status: Literal["open", "closed", "development"]
    opens_at: datetime | None = None
    closes_at: datetime | None = None

class ClimbManifest(ProtocolModel):
    schema_version: Literal["techtree.climb.v1alpha1"]
    kind: Literal["Climb"]
    metadata: ClimbMetadata
    campaign_spec_digest: Digest
    candidate_policy: CandidatePolicy
    publication: PublicationPolicy
    leaderboard: LeaderboardPolicy
```

### Resolved graph model

```python
class ResolvedClimb(ProtocolModel):
    climb: ClimbManifest
    climb_digest: Digest
    campaign: CampaignSpec
    campaign_digest: Digest
    data_policy: DataPolicy
    data_policy_digest: Digest
    publisher_validation: TasksetValidationReceipt
    publisher_validation_digest: Digest
```

### Validation rules

- Candidate required mutation matches Campaign mutation kind.
- Candidate constraints match Campaign mutation bounds.
- Skill visibility does not contradict DataPolicy.
- Publication policy does not contradict DataPolicy.
- Leaderboard must be disabled for `development_only` unless explicitly
  treated as a local UI demo.
- Climb does not contain scientific agent/taskset/scoring fields.

---

## 11.7 `models/skill.py`

### Models

```python
class SkillFile(ProtocolModel):
    path: str
    media_type: str
    size: int
    digest: Digest

class SecretFinding(ProtocolModel):
    path: str
    rule_id: str
    line: int | None
    severity: Literal["warning", "blocking"]

class SkillArtifact(ProtocolModel):
    schema_version: Literal["techtree.skill.v1alpha1"]
    name: str
    root_digest: Digest
    archive_digest: Digest
    files: list[SkillFile]
    source_kind: Literal["manual"]
    parent_skill_digest: Digest | None

class PolicyAcknowledgement(ProtocolModel):
    data_policy_digest: Digest
    required: bool

class ConfirmationRecord(StateModel):
    token_hash: Digest
    draft_digest: Digest
    expires_at: datetime
    consumed_at: datetime | None

class SubmissionDraft(ProtocolModel):
    schema_version: Literal["techtree.submission-draft.v1alpha1"]
    id: str
    campaign_spec_digest: Digest
    program_ref: ProgramRef | None
    public_context: PublicContext | None
    data_policy_digest: Digest
    outcome_contract_digest: Digest | None
    skill_artifact: SkillArtifact
    baseline_manifest_digest: Digest
    candidate_manifest_digest: Digest
    included_files: list[str]
    estimated_episodes: int
    policy_acknowledgement: PolicyAcknowledgement
    warnings: list[str]
    created_at: datetime
```

### Rules

- `SKILL.md` is present.
- Paths are POSIX relative.
- Files are sorted.
- No local path enters the artifact.
- Public Climb draft has non-null `public_context`.
- Draft campaign digest matches resolved Climb campaign digest.
- Draft DataPolicy digest matches Campaign.
- Confirmation binds to the complete draft digest, including rights policy.

---

## 11.8 `models/experiment.py`

### Models

```python
class ExperimentVariant(str, Enum):
    BASELINE = "baseline"
    CANDIDATE = "candidate"

class ExperimentConfiguration(ProtocolModel):
    taskset: CampaignTaskset
    environment: EnvironmentSpec
    agents: dict[str, AgentSpec]
    mutation_contract: MutationContract
    evaluation_backend: EvaluationBackendSpec
    execution: ExecutionSpec
    scoring: ScoringSpec
    evidence: EvidenceRequirements
    budgets: BudgetSpec
    data_policy_digest: Digest
    outcome_contract_digest: Digest | None

class ExperimentManifest(ProtocolModel):
    schema_version: Literal["techtree.experiment.v1alpha1"]
    id: str
    campaign_spec_digest: Digest
    program_ref: ProgramRef | None
    public_context: PublicContext | None
    variant: ExperimentVariant
    configuration: ExperimentConfiguration
    configuration_digest: Digest
    created_at: datetime

class JsonDifference(ProtocolModel):
    pointer: str
    baseline: JsonValue | None
    candidate: JsonValue | None

class ManifestComparison(ProtocolModel):
    baseline_configuration_digest: Digest
    candidate_configuration_digest: Digest
    differences: list[JsonDifference]
    allowed_differences: list[str]
    controlled: bool
    violations: list[str]
```

### Design rule

Compare only:

```text
ExperimentManifest.configuration
```

Do not compare:

```text
manifest ID
variant
creation time
public context
```

### Invariants

- Both manifests reference the same Campaign.
- Both carry the same DataPolicy.
- Both carry the same evaluation backend.
- Both carry the same optional OutcomeContract digest.
- Both carry the same ProgramRef and PublicContext.
- Baseline has zero candidate skills.
- Candidate has exactly one skill.
- Only allowed difference is skill list.

---

## 11.9 `models/validation.py`

### Models

```python
class TasksetLock(ProtocolModel):
    schema_version: Literal["techtree.taskset-lock.v1alpha1"]
    taskset_ref: TasksetRef
    engine_digest: Digest
    resolved_package_digest: Digest
    ordered_task_hashes: list[Digest]
    membership_digest: Digest
    task_count: int

class ValidationCheck(ProtocolModel):
    id: str
    status: Literal["passed", "failed", "warning", "not_run"]
    detail: str

class UpstreamValidationSummary(ProtocolModel):
    mode: Literal["all", "gold", "setup"]
    total: int
    recorded: int
    valid: int
    invalid: int
    error: int
    timeout: int
    missing: int
    valid_rate: float | None

class TasksetValidationReceipt(ProtocolModel):
    schema_version: Literal["techtree.taskset-validation.v1alpha1"]
    id: str
    taskset_lock_digest: Digest
    engine_digest: Digest
    status: Literal["valid", "invalid", "errored"]
    upstream_summary: UpstreamValidationSummary
    checks: list[ValidationCheck]
    artifacts: list[ArtifactRef]
    created_at: datetime
```

### Narrow responsibility

This receipt answers:

```text
Is the taskset mechanically valid and internally consistent?
```

It does not answer:

```text
Is the environment discriminative?
Is it robust to reward hacking?
Is it suitable for RL?
Is it economically valuable?
```

Those belong in a future `EnvironmentQualificationReport`.

### Required checks

```text
upstream_gold
upstream_setup
membership_repeatability
task_hash_uniqueness
committed_membership_match
expected_task_count
```

---

## 11.10 `models/episode_receipt.py`

Frozen now; fake-populated before WP6.

### Enums

```python
class ScoreStatus(str, Enum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    ERRORED = "errored"
    MISSING = "missing"
    DEVELOPMENT_ONLY = "development_only"

class EvidenceStatus(str, Enum):
    NOT_COLLECTED = "not_collected"
    COMPLETE = "complete"
    PARTIAL = "partial"
    INVALID = "invalid"
    DEVELOPMENT_ONLY = "development_only"
```

### Models

```python
class NamedTraceReceipt(ProtocolModel):
    role: str
    trace_id: str
    trace_digest: Digest
    task_hash: Digest
    rewards: dict[str, float]
    metrics: dict[str, float | None]
    ok: bool

class SubjectRuntimeReceipt(ProtocolModel):
    kind: Literal["not_executed", "docker"]
    resolved_image_digest: Digest | None = None
    platform: str | None = None

class EpisodeReceipt(ProtocolModel):
    schema_version: Literal["techtree.episode-receipt.v1alpha1"]
    id: str
    run_id: str
    campaign_spec_digest: Digest
    program_ref: ProgramRef | None
    public_context: PublicContext | None
    data_policy_digest: Digest
    outcome_contract_digest: Digest | None
    evaluation_backend: EvaluationBackendSpec
    subject_runtime: SubjectRuntimeReceipt
    variant: ExperimentVariant
    experiment_manifest_digest: Digest
    episode_id: str
    episode_digest: Digest
    task_hash: Digest
    named_traces: dict[str, list[NamedTraceReceipt]]
    score_status: ScoreStatus
    evidence_status: EvidenceStatus
    execution_backend: Literal["fake", "verifiers"]
    artifacts: list[ArtifactRef]
```

### Fake values

```text
evaluation_backend:
  local_techtree / participant

subject_runtime:
  kind = not_executed

execution_backend:
  fake

score_status:
  development_only

evidence_status:
  development_only
```

No Relay field exists.

---

## 11.11 `models/uplift_report.py`

### Enums

```python
class ExecutionStatus(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ComparisonStatus(str, Enum):
    PENDING = "pending"
    CONTROLLED = "controlled"
    CONTROLLED_WITH_WARNINGS = "controlled_with_warnings"
    INVALID = "invalid"
    DEVELOPMENT_ONLY = "development_only"

class PublicationStatus(str, Enum):
    NOT_REQUESTED = "not_requested"
    BLOCKED = "blocked"
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"

class UpliftDecision(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"
    INVALID = "invalid"
    DEVELOPMENT_ONLY = "development_only"
```

### Models

```python
class TaskDelta(ProtocolModel):
    task_hash: Digest
    baseline_reward: float
    candidate_reward: float
    delta: float

class PrimaryUpliftResult(ProtocolModel):
    reward_name: str
    baseline_mean: float
    candidate_mean: float
    absolute_delta: float
    relative_delta: float | None
    wins: int
    losses: int
    ties: int

class UpliftStatuses(ProtocolModel):
    execution: ExecutionStatus
    score: ScoreStatus
    evidence: EvidenceStatus
    comparison: ComparisonStatus
    publication: PublicationStatus

class UpliftReport(ProtocolModel):
    schema_version: Literal["techtree.uplift-report.v1alpha1"]
    id: str
    run_id: str
    campaign_spec_digest: Digest
    program_ref: ProgramRef | None
    public_context: PublicContext | None
    data_policy_digest: Digest
    outcome_contract_digest: Digest | None
    evaluation_backend: EvaluationBackendSpec
    taskset_validation_receipt_digest: Digest
    baseline_manifest_digest: Digest
    candidate_manifest_digest: Digest
    statuses: UpliftStatuses
    manifest_comparison: ManifestComparison
    primary_result: PrimaryUpliftResult
    task_deltas: list[TaskDelta]
    decision: UpliftDecision
    proof_grade: Literal["development_only", "P1"]
    publication_eligible: bool
    created_at: datetime
```

### Semantics

`decision` answers:

```text
Did the candidate satisfy the scientific comparison contract?
```

It does not answer:

```text
Should a customer deploy it?
```

A future `ReleaseDecision` is separate.

### Fake report

```text
execution = completed
score = development_only
evidence = development_only
comparison = development_only
publication = blocked
decision = development_only
proof_grade = development_only
publication_eligible = false
```

---

## 11.12 `models/run.py`

### Phases

```python
class RunPhase(str, Enum):
    CREATED = "created"
    VALIDATING_TASKSET = "validating_taskset"
    RUNNING_BASELINE = "running_baseline"
    RUNNING_CANDIDATE = "running_candidate"
    BUILDING_RECEIPTS = "building_receipts"
    VERIFYING_COMPARISON = "verifying_comparison"
    BUILDING_REPORT = "building_report"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
```

### Models

```python
class RunRequest(ProtocolModel):
    run_id: str
    draft_id: str
    draft_digest: Digest
    campaign_spec_digest: Digest
    program_ref: ProgramRef | None
    public_context: PublicContext | None
    data_policy_digest: Digest
    outcome_contract_digest: Digest | None
    evaluation_backend: EvaluationBackendSpec
    taskset_lock_digest: Digest | None
    baseline_manifest_digest: Digest
    candidate_manifest_digest: Digest
    executor_kind: Literal["fake"]
    created_at: datetime

class RunEvent(ProtocolModel):
    sequence: int
    timestamp: datetime
    run_id: str
    previous_phase: RunPhase | None
    phase: RunPhase
    kind: str
    details: dict[str, JsonValue]

class RunProgress(StateModel):
    current: int
    total: int
    label: str

class RunState(StateModel):
    run_id: str
    phase: RunPhase
    sequence: int
    updated_at: datetime
    worker_pid: int | None
    worker_started_at: datetime | None
    heartbeat_at: datetime | None
    cancel_requested_at: datetime | None
    error: CliError | None
    progress: RunProgress | None
    result_digest: Digest | None

class RunStatus(ProtocolModel):
    state: RunState
    worker_alive: bool
    heartbeat_stale: bool
    result_available: bool
```

---

## 11.13 `models/engine.py`

### Models

```python
class EnginePackage(ProtocolModel):
    name: str
    version: str
    source_digest: Digest

class EngineDescriptor(ProtocolModel):
    schema_version: Literal["techtree.engine.v1alpha1"]
    name: str
    python_version: str
    verifiers_version: str
    verifiers_revision: str
    supported_hosts: list[str]
    packages: list[EnginePackage]

class EngineInstallation(StateModel):
    digest: Digest
    installed_at: datetime
    python_executable: str
    descriptor_digest: Digest
    verified: bool

class EngineStatus(ProtocolModel):
    digest: Digest
    installed: bool
    active: bool
    verified: bool
    path: str
    python_executable: str | None
    detail: str
```

The engine digest covers the static bundle and is not self-referential inside `EngineDescriptor`.

---

## 11.14 `models/cli.py`

### Enums and models

```python
class MessageLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

class CliMessage(ProtocolModel):
    level: MessageLevel
    code: str | None
    text: str

class NextAction(ProtocolModel):
    id: str
    label: str
    reason: str | None
    cli: list[str] | None
    hermes_tool: str | None
    hermes_args: dict[str, JsonValue] | None
    requires_user_confirmation: bool

class CliError(ProtocolModel):
    code: str
    message: str
    retryable: bool
    details: dict[str, JsonValue]

class CliEnvelope(ProtocolModel, Generic[T]):
    schema_version: Literal["techtree.cli.v1"]
    ok: bool
    command: str
    data: T | None
    messages: list[CliMessage]
    warnings: list[CliMessage]
    next_actions: list[NextAction]
    error: CliError | None
```

### Invariants

- Success has no error.
- Failure has an error.
- Maximum three next actions.
- CLI actions are argv lists.
- No secrets.
- No raw provider credentials.
- Climb-show response includes Campaign and DataPolicy summaries.

### Doctor models

```python
class CheckStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"

class DoctorCheck(ProtocolModel):
    id: str
    label: str
    status: CheckStatus
    detail: str
    blocking: bool
    metadata: dict[str, JsonValue]
```

---

# 12. CLI module file specifications

## 12.1 `cli/context.py`

### Class

```python
@dataclass
class CliContext:
    paths: TechtreePaths
    settings: Settings
    json_output: bool
    no_color: bool
    no_input: bool
    debug: bool
```

### Function

```python
def build_cli_context(
    *,
    home: Path | None,
    json_output: bool,
    no_color: bool,
    no_input: bool,
    debug: bool,
) -> CliContext:
    """Resolve paths, create layout, load settings, and return context."""
```

No command-specific services are created here.

---

## 12.2 `cli/output.py`

### Functions

```python
def emit_envelope(context: CliContext, envelope: CliEnvelope) -> None:
    """Write one JSON object or render human output."""

def render_human(envelope: CliEnvelope, console: Console) -> None:
    """Render messages, typed data summaries, warnings, and next actions."""

def render_next_actions(actions: list[NextAction], console: Console) -> None:
    """Render ordered next steps with display-only shell quoting."""

def shell_display(argv: list[str]) -> str:
    """Use shlex.join for display only."""

def json_stdout(envelope: CliEnvelope) -> None:
    """Write one compact JSON object and one newline."""

def stderr_log(message: str) -> None:
    """Write operational logs to stderr."""
```

No displayed command string is executed.

---

## 12.3 `cli/invoke.py`

### Internal result type

```python
@dataclass
class CommandResult(Generic[T]):
    data: T
    messages: list[CliMessage]
    warnings: list[CliMessage]
    next_actions: list[NextAction]
```

### Functions

```python
def success_envelope(
    *,
    command: str,
    data: T,
    messages: list[CliMessage] | None = None,
    warnings: list[CliMessage] | None = None,
    next_actions: list[NextAction] | None = None,
) -> CliEnvelope[T]:
    """Construct a successful envelope."""

def failure_envelope(
    *,
    command: str,
    error: TechtreeError,
) -> CliEnvelope[None]:
    """Construct a failed envelope."""

def invoke_command(
    context: CliContext,
    command: str,
    action: Callable[[], CommandResult[T]],
) -> NoReturn:
    """Execute, emit exactly one envelope, and exit correctly."""
```

---

## 12.4 `cli/app.py`

### Responsibility

Builds the Typer application and registers command groups.

### Global options

```text
--home PATH
--json
--no-color
--no-input
--debug
--version
```

### Sub-apps

```text
climb
run
engine
```

### Reserved but unregistered names

```text
program
blueprint
forge
verify
uplift
trace
lab
```

Do not create empty Typer groups for them yet.

### Functions

```python
def create_app() -> typer.Typer:
    """Construct and return the application."""

def root_callback(...) -> None:
    """Build CliContext and attach it to Typer context."""

def main() -> None:
    """Run the application."""
```

No business logic belongs here.

---

## 12.5 `cli/commands/doctor.py`

### Command

```bash
techtree doctor
```

### Function

```python
def doctor_command(ctx: typer.Context) -> None:
    """Run DoctorService and emit checks plus repair actions."""
```

Before WP6:

```text
Python and writable Techtree home:
    blocking

uv:
    blocking once engine setup is requested

Docker and Hermes:
    warning in ordinary Doctor
```

---

## 12.6 `cli/commands/climb.py`

### Commands

```bash
techtree climb list
techtree climb show <reference>
techtree climb prepare <reference> --skill <path> [--label <label>]
techtree climb start <draft-id> --confirmation-token <token>
```

### Functions

```python
def list_climbs_command(...) -> None:
    """List public wrappers with resolved Campaign compatibility."""

def show_climb_command(...) -> None:
    """
    Show public policy, scientific Campaign summary, data rights,
    evaluation backend, and local compatibility.
    """

def prepare_climb_command(...) -> None:
    """Resolve Climb graph and prepare one candidate skill draft."""

def start_climb_command(...) -> None:
    """Consume confirmation and start detached run."""
```

### Service use

```text
CatalogService
SkillPreparationService
DraftStore
RunService
```

No direct object-store traversal or process launch inside command functions.

---

## 12.7 `cli/commands/run.py`

### Commands

```bash
techtree run status <run-id>
techtree run status <run-id> --watch
techtree run logs <run-id>
techtree run logs <run-id> --tail 200
techtree run logs <run-id> --follow
techtree run cancel <run-id>
techtree run result <run-id>
```

### Functions

```python
def status_command(...) -> None:
    """Return one status snapshot or human watch UI."""

def logs_command(...) -> None:
    """Return or stream sanitized worker logs."""

def cancel_command(...) -> None:
    """Request cancellation and signal worker."""

def result_command(...) -> None:
    """Return final UpliftReport."""
```

### Machine-mode rules

- `--watch` rejected with `--json`.
- `--follow` rejected with `--json`.
- Machine logs are bounded snapshots.
- One JSON envelope per invocation.

---

## 12.8 `cli/commands/engine.py`

### Commands

```bash
techtree engine install [digest]
techtree engine status [digest]
techtree engine verify [digest]
```

### Functions

```python
def install_engine_command(...) -> None:
    """Install selected or default embedded engine."""

def status_engine_command(...) -> None:
    """Return installation and activation status."""

def verify_engine_command(...) -> None:
    """Recompute bundle and live-environment checks."""
```

---

## 12.9 `cli/commands/setup.py`

### Command

```bash
techtree setup
```

### WP4 behavior

1. Ensure local path layout.
2. Run prerequisites.
3. Install default engine.
4. Set it active.
5. Verify it.
6. Print `climb list` as next action.

Do not install Hermes plugin.

Reserve but do not implement:

```bash
techtree setup --hermes
```

---

# 13. Doctor subsystem

## 13.1 `doctor/checks.py`

### Functions

```python
def check_python_version() -> DoctorCheck:
    """Require Python >=3.12,<3.14."""

def check_techtree_home(paths: TechtreePaths) -> DoctorCheck:
    """Check creation, writeability, and private permissions."""

def check_uv_cli() -> DoctorCheck:
    """Find uv and report version."""

def check_docker_cli() -> DoctorCheck:
    """Find docker executable."""

def check_docker_daemon() -> DoctorCheck:
    """Check Docker server reachability."""

def check_hermes_cli() -> DoctorCheck:
    """Find Hermes and report version; warning only."""

def check_active_engine(
    paths: TechtreePaths,
    settings: Settings,
) -> DoctorCheck:
    """Report whether active engine is installed and verified."""
```

All subprocesses use argument vectors and timeouts.

---

## 13.2 `doctor/service.py`

### Class

```python
class DoctorService:
    def __init__(
        self,
        paths: TechtreePaths,
        settings: Settings,
        engine_registry: EngineRegistry,
    ) -> None: ...

    def run(self) -> list[DoctorCheck]:
        """Run checks in deterministic order."""

    def blocking_failures(
        self,
        checks: list[DoctorCheck],
    ) -> list[DoctorCheck]:
        """Return blocking failures."""

    def warnings(
        self,
        checks: list[DoctorCheck],
    ) -> list[DoctorCheck]:
        """Return warnings."""

    def next_actions(
        self,
        checks: list[DoctorCheck],
    ) -> list[NextAction]:
        """Create no more than three repair actions."""
```

---

# 14. Catalog subsystem

## 14.1 Catalog resource model

`resources/catalog/catalog.json` maps public references and content-addressed objects:

```json
{
  "schema_version": "techtree.catalog.v1alpha1",
  "climbs": [
    {
      "reference": "procedure-transfer-dev@1",
      "path": "climbs/procedure-transfer-dev.json"
    }
  ],
  "objects": {
    "sha256:campaign...": "campaigns/procedure-transfer-dev.json",
    "sha256:policy...": "data-policies/procedure-transfer-dev.json",
    "sha256:validation...": "taskset-validations/procedure-transfer-dev.json"
  }
}
```

The object map is generated, not manually edited.

---

## 14.2 `catalog/repository.py`

### Class

```python
class EmbeddedCatalogRepository:
    def __init__(self, resource_root: Traversable) -> None: ...

    def list_climb_references(self) -> list[str]:
        """Return embedded public references."""

    def load_climb(self, reference: str) -> ClimbManifest:
        """Resolve slug, slug@version, or exact public ID."""

    def load_object(self, digest: Digest) -> JsonValue:
        """Load object path from content-addressed catalog map."""

    def load_campaign(self, digest: Digest) -> CampaignSpec:
        """Load and verify CampaignSpec digest."""

    def load_data_policy(self, digest: Digest) -> DataPolicy:
        """Load and verify DataPolicy digest."""

    def load_validation_receipt(
        self,
        digest: Digest,
    ) -> TasksetValidationReceipt:
        """Load and verify publisher validation receipt."""

    def catalog_metadata(self) -> dict[str, JsonValue]:
        """Return validated catalog metadata."""
```

### Rules

- Recompute each loaded object’s digest.
- Fail on missing object map entry.
- Fail on path traversal.
- Fail on type mismatch.
- Embedded objects are unsigned in WP0–WP5.
- Future remote catalog envelopes may add signatures without changing internal graph resolution.

---

## 14.3 `catalog/service.py`

### Supporting model

```python
@dataclass(frozen=True)
class HostInfo:
    operating_system: str
    architecture: str
    python_version: str
```

### Class

```python
class CatalogService:
    def __init__(
        self,
        repository: EmbeddedCatalogRepository,
        host_info: HostInfo,
        engine_registry: EngineRegistry,
    ) -> None: ...

    def list_climbs(
        self,
        *,
        status: str = "available",
    ) -> list[ClimbSummary]:
        """Return public summaries; available means open plus development fixtures."""

    def get_climb(self, reference: str) -> ResolvedClimb:
        """
        Load Climb → Campaign → DataPolicy → publisher validation receipt,
        verify every digest, and verify cross-object consistency.
        """

    def compatibility(
        self,
        resolved: ResolvedClimb,
    ) -> CompatibilityResult:
        """Check host, CLI, engine, and implemented backend compatibility."""

    def validate_public_policy(
        self,
        resolved: ResolvedClimb,
    ) -> None:
        """Reject contradictions among Climb, Campaign, and DataPolicy."""
```

### Cross-object checks

```text
Climb.campaign_spec_digest == digest(Campaign)
Campaign.data_policy_digest == digest(DataPolicy)
Campaign.taskset.validation_receipt_digest == digest(publisher validation)
Climb candidate policy matches Campaign mutation
Climb publication policy is permitted by DataPolicy
Development proof grade matches development status
Evaluation backend is implemented locally
```

---

# 15. Skill subsystem

## 15.1 `skills/policy.py`

### Model

```python
@dataclass(frozen=True)
class SkillPolicy:
    required_entrypoint: str = "SKILL.md"
    allowed_suffixes: frozenset[str]
    maximum_files: int
    maximum_file_bytes: int
    maximum_total_bytes: int
    allow_symlinks: bool = False
    allow_hidden_files: bool = False
```

### Function

```python
def default_instruction_skill_policy() -> SkillPolicy:
    """Return v0.1 Markdown instruction-skill policy."""
```

Reject hidden files.

---

## 15.2 `skills/scanner.py`

### Internal structures

```python
@dataclass
class ScannedFile:
    source_path: Path
    relative_path: PurePosixPath
    size: int
    media_type: str
    digest: Digest

@dataclass
class SkillScanResult:
    root: Path
    files: list[ScannedFile]
    secret_findings: list[SecretFinding]
    warnings: list[str]
```

### Functions

```python
def resolve_skill_root(path: Path) -> Path:
    """Accept SKILL.md or containing directory."""

def enumerate_files(root: Path) -> list[Path]:
    """Enumerate without following symlinks."""

def validate_file(
    path: Path,
    root: Path,
    policy: SkillPolicy,
) -> None:
    """Validate containment, type, suffix, size, and hidden status."""

def media_type_for(path: Path) -> str:
    """Map allowed suffix to stable media type."""

def scan_file_for_secrets(path: Path) -> list[SecretFinding]:
    """Find secret patterns without returning secret text."""

def scan_skill(
    path: Path,
    policy: SkillPolicy,
) -> SkillScanResult:
    """Perform complete validation and scanning."""
```

Blocking patterns include private keys, bearer headers, common API-key assignments, and `.env`-style secrets.

---

## 15.3 `skills/archive.py`

### Functions

```python
def normalized_tar_info(
    relative_path: PurePosixPath,
    size: int,
) -> tarfile.TarInfo:
    """Return uid/gid 0, empty names, mtime 0, mode 0644."""

def build_deterministic_tar(
    files: list[ScannedFile],
    output_path: Path,
) -> Digest:
    """Write lexicographically and return archive digest."""

def verify_archive(
    archive_path: Path,
    artifact: SkillArtifact,
) -> bool:
    """Verify archive and member manifest."""

def safe_extract_archive(
    archive_path: Path,
    destination: Path,
) -> None:
    """Reject links, devices, absolute paths, and traversal."""
```

Use uncompressed tar in WP2.

---

## 15.4 `skills/service.py`

### Internal return

```python
@dataclass(frozen=True)
class PreparedDraft:
    draft: SubmissionDraft
    confirmation_token: str
    confirmation_expires_at: datetime
    manifest_comparison: ManifestComparison
```

### Class

```python
class SkillPreparationService:
    def __init__(
        self,
        paths: TechtreePaths,
        catalog: CatalogService,
        draft_store: DraftStore,
        confirmation_service: ConfirmationService,
    ) -> None: ...

    def prepare(
        self,
        *,
        climb_reference: str,
        skill_path: Path,
        candidate_label: str | None,
    ) -> PreparedDraft:
        """Create complete immutable draft."""
```

### Internal methods

```python
def _snapshot_skill(
    self,
    draft_dir: Path,
    scan: SkillScanResult,
) -> SkillArtifact:
    """Copy validated files and create deterministic artifact."""

def _build_manifests(
    self,
    resolved: ResolvedClimb,
    skill: SkillArtifact,
) -> tuple[ExperimentManifest, ExperimentManifest, ManifestComparison]:
    """Build and compare variants from Campaign."""

def _estimate_episodes(
    self,
    campaign: CampaignSpec,
) -> int:
    """Calculate baseline plus candidate episodes."""

def _policy_acknowledgement(
    self,
    resolved: ResolvedClimb,
) -> PolicyAcknowledgement:
    """Bind draft to required DataPolicy."""

def _draft_warnings(
    self,
    resolved: ResolvedClimb,
    scan: SkillScanResult,
) -> list[str]:
    """Return scientific, development, and rights warnings."""
```

### Prepare output must show

```text
Climb identity
Campaign digest
DataPolicy digest
candidate files
candidate ownership
candidate public-release requirement
raw episode upload prohibition
training-use prohibition
scientific allowed difference
episode estimate
development-only status
```

---

# 16. Manifest subsystem

## 16.1 `manifests/builder.py`

### Functions

```python
def build_experiment_configuration(
    campaign: CampaignSpec,
) -> ExperimentConfiguration:
    """Copy the fixed scientific configuration."""

def build_baseline_manifest(
    campaign: CampaignSpec,
    *,
    public_context: PublicContext | None,
) -> ExperimentManifest:
    """Build baseline with no candidate skill."""

def build_candidate_manifest(
    campaign: CampaignSpec,
    skill: SkillArtifact,
    *,
    public_context: PublicContext | None,
) -> ExperimentManifest:
    """Build candidate with one skill reference."""

def finalize_manifest(
    *,
    campaign: CampaignSpec,
    campaign_digest: Digest,
    public_context: PublicContext | None,
    variant: ExperimentVariant,
    configuration: ExperimentConfiguration,
) -> ExperimentManifest:
    """Calculate configuration digest and create immutable manifest."""
```

### Rules

- Deep immutable copies.
- No mutation of Campaign.
- No local paths.
- No public policy duplicated inside configuration.
- DataPolicy, ProgramRef, OutcomeContract, and EvaluationBackend copy exactly from Campaign.

---

## 16.2 `manifests/compare.py`

### Functions

```python
def json_pointer_escape(segment: str) -> str:
    """Apply RFC 6901 escaping."""

def diff_values(
    baseline: JsonValue,
    candidate: JsonValue,
    pointer: str = "",
) -> list[JsonDifference]:
    """Return deterministic leaf differences."""

def pointer_is_within(
    pointer: str,
    allowed_root: str,
) -> bool:
    """Test path equality or descent."""

def compare_manifests(
    baseline: ExperimentManifest,
    candidate: ExperimentManifest,
    mutation: MutationContract,
) -> ManifestComparison:
    """Enforce controlled scientific mutation."""
```

### Required invariants

- Same Campaign digest.
- Same ProgramRef.
- Same PublicContext.
- Same DataPolicy.
- Same OutcomeContract.
- Same EvaluationBackend.
- Candidate has one skill.
- Baseline has zero skills.
- Every difference is under allowed skill pointer.
- At least one difference exists.

---

# 17. Draft subsystem

## 17.1 `drafts/confirmation.py`

### Class

```python
class ConfirmationService:
    def __init__(self, ttl_seconds: int) -> None: ...

    def issue(
        self,
        draft_digest: Digest,
    ) -> tuple[str, ConfirmationRecord]:
        """Return raw token once and stored hash record."""

    def verify(
        self,
        token: str,
        record: ConfirmationRecord,
        expected_draft_digest: Digest,
        *,
        now: datetime | None = None,
    ) -> None:
        """Reject mismatch, expiry, consumption, or wrong draft."""

    def consume(
        self,
        record: ConfirmationRecord,
        *,
        now: datetime | None = None,
    ) -> ConfirmationRecord:
        """Return consumed copy."""
```

Token is generated with `secrets.token_urlsafe(32)` and stored only as SHA-256.

Because the draft includes DataPolicy digest, confirmation is bound to the rights policy.

---

## 17.2 `drafts/store.py`

### Class

```python
class DraftStore:
    def __init__(self, paths: TechtreePaths) -> None: ...

    def create(
        self,
        *,
        draft: SubmissionDraft,
        confirmation: ConfirmationRecord,
        baseline: ExperimentManifest,
        candidate: ExperimentManifest,
        comparison: ManifestComparison,
        resolved_climb: ResolvedClimb,
    ) -> None:
        """Persist complete draft graph atomically."""

    def get(self, draft_id: str) -> SubmissionDraft:
        """Load draft."""

    def get_confirmation(self, draft_id: str) -> ConfirmationRecord:
        """Load confirmation record."""

    def get_manifests(
        self,
        draft_id: str,
    ) -> tuple[ExperimentManifest, ExperimentManifest]:
        """Load variants."""

    def get_comparison(self, draft_id: str) -> ManifestComparison:
        """Load prepared comparison."""

    def get_resolved_climb(self, draft_id: str) -> ResolvedClimb:
        """Load snapshotted public and Campaign graph."""

    def consume_confirmation(
        self,
        draft_id: str,
        token: str,
    ) -> None:
        """Verify and consume token."""

    def mark_started(self, draft_id: str, run_id: str) -> None:
        """One-time start marker."""

    def snapshot_dir(self, draft_id: str) -> Path:
        """Return immutable skill snapshot directory."""
```

### Draft layout

```text
drafts/<draft-id>/
├── draft.json
├── confirmation.json
├── comparison.json
├── started.json
├── public/
│   ├── climb.json
│   ├── campaign.json
│   ├── data-policy.json
│   └── publisher-validation.json
├── manifests/
│   ├── baseline.json
│   └── candidate.json
└── skill/
    ├── artifact.json
    ├── bundle.tar
    └── files/
        ├── SKILL.md
        └── ...
```

All public objects are snapshotted at prepare time.

---

# 18. Run subsystem

## 18.1 `runs/events.py`

### Functions

```python
def append_event(path: Path, event: RunEvent) -> None:
    """Append compact JSONL and fsync."""

def read_events(path: Path) -> list[RunEvent]:
    """Read events and reject sequence discontinuity."""

def next_sequence(events: list[RunEvent]) -> int:
    """Return next sequence number."""

def event_digest(path: Path) -> Digest:
    """Digest exact event-log bytes."""
```

---

## 18.2 `runs/machine.py`

### Constant

```python
ALLOWED_TRANSITIONS: dict[RunPhase, set[RunPhase]]
```

### Functions

```python
def validate_transition(current: RunPhase, target: RunPhase) -> None:
    """Raise on invalid transition."""

def reduce_events(events: list[RunEvent]) -> RunState:
    """Project complete state."""

def apply_event(state: RunState, event: RunEvent) -> RunState:
    """Apply one event."""

def is_terminal(phase: RunPhase) -> bool:
    """Return terminal state."""

def can_cancel(phase: RunPhase) -> bool:
    """Return cancellation eligibility."""
```

Normal path:

```text
created
→ validating_taskset
→ running_baseline
→ running_candidate
→ building_receipts
→ verifying_comparison
→ building_report
→ completed
```

---

## 18.3 `runs/store.py`

### Class

```python
class RunStore:
    def __init__(self, paths: TechtreePaths) -> None: ...

    def create(self, request: RunRequest) -> None:
        """Create run tree and initial event."""

    def get_request(self, run_id: str) -> RunRequest:
        """Load immutable request."""

    def append(
        self,
        run_id: str,
        *,
        phase: RunPhase,
        kind: str,
        details: dict[str, JsonValue] | None = None,
    ) -> RunState:
        """Validate transition, append, and project."""

    def state(self, run_id: str) -> RunState:
        """Load projection or rebuild."""

    def rebuild_state(self, run_id: str) -> RunState:
        """Recompute from events."""

    def write_pid(self, run_id: str, pid: int) -> None:
        """Persist worker PID."""

    def read_pid(self, run_id: str) -> int | None:
        """Read PID."""

    def write_heartbeat(self, run_id: str, phase: RunPhase) -> None:
        """Refresh heartbeat."""

    def result_path(self, run_id: str) -> Path:
        """Return UpliftReport path."""

    def write_result(self, run_id: str, report: UpliftReport) -> None:
        """Write immutable result."""

    def get_result(self, run_id: str) -> UpliftReport:
        """Load result."""

    def worker_log_path(self, run_id: str) -> Path:
        """Return log path."""
```

All mutation uses:

```text
runs/<run-id>/.lock
```

---

## 18.4 `runs/executor.py`

### Protocol

```python
class RunExecutor(Protocol):
    def execute(self, context: ExecutionContext) -> UpliftReport:
        """Execute complete run."""
```

### Context

```python
@dataclass(frozen=True)
class ExecutionContext:
    request: RunRequest
    run_store: RunStore
    draft_store: DraftStore
    taskset_service: TasksetService
```

### Function

```python
def raise_if_cancel_requested(
    store: RunStore,
    run_id: str,
) -> None:
    """Raise CancellationError when requested."""
```

---

## 18.5 `runs/fake.py`

### Class

```python
class FakeRunExecutor:
    def __init__(
        self,
        *,
        step_delay_seconds: float = 0.1,
        baseline_rewards: list[float] | None = None,
        candidate_rewards: list[float] | None = None,
    ) -> None: ...

    def execute(
        self,
        context: ExecutionContext,
    ) -> UpliftReport:
        """Run real taskset validation then fake comparison."""
```

### Sequence

1. Validate Campaign graph copied into draft.
2. Transition to `validating_taskset`.
3. Resolve and validate taskset.
4. Compare local TasksetLock with Campaign membership.
5. Check cancellation.
6. Transition to `running_baseline`.
7. Produce fake baseline receipts.
8. Transition to `running_candidate`.
9. Produce fake candidate receipts.
10. Transition to `building_receipts`.
11. Persist fake receipts with Campaign/DataPolicy/EvaluationBackend.
12. Transition to `verifying_comparison`.
13. Load prepared ManifestComparison.
14. Transition to `building_report`.
15. Build development-only UpliftReport.
16. Persist report.
17. Transition to `completed`.

### Default fake rewards

For 20 tasks:

```text
baseline:
  5 successes
  15 failures

candidate:
  17 successes
  3 failures
```

Still:

```text
decision = development_only
publication_eligible = false
```

---

## 18.6 `runs/launcher.py`

### Class

```python
class WorkerLauncher:
    def __init__(
        self,
        worker_executable: Path,
        run_store: RunStore,
    ) -> None: ...

    def launch(self, run_id: str) -> int:
        """Launch detached worker and return PID."""

    def is_alive(self, run_id: str) -> bool:
        """Check stored PID."""

    def request_termination(self, run_id: str) -> None:
        """Send SIGTERM to worker process group."""

    def force_kill(self, run_id: str) -> None:
        """Send SIGKILL after timeout where supported."""
```

Use:

```python
subprocess.Popen(
    [worker_binary, "execute", "--run-id", run_id],
    stdin=subprocess.DEVNULL,
    stdout=worker_log,
    stderr=subprocess.STDOUT,
    start_new_session=True,
    close_fds=True,
    env=scrubbed_environment,
)
```

No shell.

---

## 18.7 `runs/service.py`

### Class

```python
class RunService:
    def __init__(
        self,
        paths: TechtreePaths,
        draft_store: DraftStore,
        run_store: RunStore,
        launcher: WorkerLauncher,
        confirmation_service: ConfirmationService,
    ) -> None: ...

    def start(
        self,
        *,
        draft_id: str,
        confirmation_token: str,
    ) -> RunStatus:
        """Validate graph, consume confirmation, create run, launch."""

    def status(self, run_id: str) -> RunStatus:
        """Return state and worker health."""

    def cancel(self, run_id: str) -> RunStatus:
        """Append cancel request and signal worker."""

    def result(self, run_id: str) -> UpliftReport:
        """Return result or typed unavailable error."""

    def logs(
        self,
        run_id: str,
        tail: int | None = None,
    ) -> str:
        """Return sanitized log snapshot."""
```

### Start validations

- Draft not already started.
- Confirmation valid.
- Campaign digest matches snapshotted Campaign.
- Public context matches snapshotted Climb.
- DataPolicy matches Campaign.
- EvaluationBackend is locally implemented.
- Baseline/candidate manifests reference same Campaign.
- Prepared comparison is controlled.
- No policy digest changed.

---

# 19. Worker subsystem

## 19.1 `worker/main.py`

### Command

```bash
techtree-worker execute --run-id <id>
```

### Functions

```python
def build_parser() -> argparse.ArgumentParser:
    """Create internal worker parser."""

def main(argv: Sequence[str] | None = None) -> None:
    """Parse and call execute_run."""
```

No Rich output.

---

## 19.2 `worker/execute.py`

### Function

```python
def execute_run(
    run_id: str,
    *,
    paths: TechtreePaths | None = None,
) -> int:
    """
    Load request, start heartbeat, execute selected executor,
    handle cancellation and failure, and return process status.
    """
```

### Helpers

```python
def heartbeat_loop(
    stop_event: threading.Event,
    run_store: RunStore,
    run_id: str,
) -> None:
    """Refresh heartbeat."""

def executor_for(request: RunRequest) -> RunExecutor:
    """Resolve FakeRunExecutor in WP3–WP5."""

def handle_worker_error(
    run_store: RunStore,
    run_id: str,
    error: Exception,
) -> None:
    """Append sanitized failure."""

def handle_worker_cancelled(
    run_store: RunStore,
    run_id: str,
) -> None:
    """Append cancelled event."""
```

Signal handling records cancellation and exits at safe boundaries.

---

# 20. Managed engine subsystem

## 20.1 Static bundle contents

```text
resources/engines/default/
├── engine.json
├── pyproject.toml
├── uv.lock
└── packages/
    └── procedure-transfer-v1/
```

The engine bundle does not contain:

```text
ClimbManifest
CampaignSpec
DataPolicy
catalog.json
protocol goldens
JSON Schemas
```

Therefore Campaign generation does not create an engine-digest cycle.

---

## 20.2 `engines/bundle.py`

### Internal type

```python
@dataclass(frozen=True)
class BundleFile:
    relative_path: str
    size: int
    digest: Digest
```

### Functions

```python
def embedded_engine_root(name: str = "default") -> Traversable:
    """Locate packaged resources."""

def enumerate_bundle_files(root: Traversable) -> list[BundleFile]:
    """Enumerate deterministically."""

def engine_bundle_digest(root: Traversable) -> Digest:
    """Digest ordered bundle manifest."""

def read_engine_descriptor(root: Traversable) -> EngineDescriptor:
    """Load engine.json."""

def copy_engine_bundle(
    root: Traversable,
    destination: Path,
) -> None:
    """Copy without links or overwrite."""

def default_engine_digest() -> Digest:
    """Return packaged default digest."""
```

---

## 20.3 `engines/installer.py`

### Class

```python
class EngineInstaller:
    def __init__(
        self,
        paths: TechtreePaths,
        registry: EngineRegistry,
        uv_executable: Path,
    ) -> None: ...

    def install(self, digest: Digest | None = None) -> EngineStatus:
        """Materialize, frozen-sync, verify, and mark installed."""

    def verify(self, digest: Digest) -> EngineStatus:
        """Verify bundle and live environment."""

    def uninstall(self, digest: Digest) -> None:
        """Remove inactive engine."""
```

### Algorithm

1. Resolve embedded bundle.
2. Compute digest.
3. Match requested digest.
4. Acquire global install lock.
5. Copy to temporary directory.
6. Run `uv sync --frozen`.
7. Execute engine verification query.
8. Write `installed.json`.
9. Atomically rename to final digest directory.
10. Return verified status.

Do not run `uv lock` on user machines.

---

## 20.4 `engines/registry.py`

### Class

```python
class EngineRegistry:
    def __init__(
        self,
        paths: TechtreePaths,
        settings: Settings,
    ) -> None: ...

    def known(self) -> list[Digest]:
        """Return packaged and installed digests."""

    def installed(self) -> list[Digest]:
        """Return installed digest directories."""

    def path(self, digest: Digest) -> Path:
        """Return installation path."""

    def python(self, digest: Digest) -> Path:
        """Return managed Python."""

    def executable(self, digest: Digest, name: str) -> Path:
        """Return validate/eval script."""

    def status(self, digest: Digest) -> EngineStatus:
        """Return status."""

    def active_digest(self) -> Digest | None:
        """Return active digest."""

    def set_active(self, digest: Digest) -> Settings:
        """Verify and persist active engine."""
```

---

## 20.5 `engines/runner.py`

### Result

```python
@dataclass(frozen=True)
class EngineProcessResult:
    argv: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
```

### Class

```python
class EngineRunner:
    def __init__(
        self,
        registry: EngineRegistry,
        digest: Digest,
    ) -> None: ...

    def run(
        self,
        executable: str,
        args: Sequence[str],
        *,
        timeout: float,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
    ) -> EngineProcessResult:
        """Run one managed command."""

    def run_python_script(
        self,
        script: Path,
        args: Sequence[str],
        *,
        timeout: float,
        env: Mapping[str, str] | None = None,
    ) -> EngineProcessResult:
        """Run host-owned helper with managed Python."""
```

Validation needs no provider credentials.

---

# 21. Taskset subsystem

## 21.1 `resources/engine_scripts/inspect_taskset.py`

Executes inside managed engine.

### Arguments

```text
--taskset-id
--num-tasks
--output
```

No `--shuffle`.

### Functions

```python
def parse_args() -> argparse.Namespace:
    """Parse fixed helper arguments."""

def load_tasks(
    taskset_id: str,
    *,
    num_tasks: int,
) -> list[Task]:
    """Load Taskset and take first N tasks."""

def task_record(
    position: int,
    task: Task,
) -> dict[str, object]:
    """Return position, raw hash, name, and task type."""

def inspect_taskset(...) -> dict[str, object]:
    """Return taskset metadata and ordered records."""

def main() -> None:
    """Write one JSON object to output."""
```

Do not output expected answers, prompts, or hidden data.

---

## 21.2 `tasksets/membership.py`

### Functions

```python
def membership_digest(
    ordered_task_hashes: list[Digest],
) -> Digest:
    """Digest canonical ordered-hash object."""

def assert_unique_task_hashes(hashes: list[Digest]) -> None:
    """Reject duplicates."""

def compare_membership(
    actual: list[Digest],
    committed: list[Digest],
) -> ValidationCheck:
    """Return pass/fail and first mismatch."""

def load_inspection_output(path: Path) -> TasksetInspection:
    """Validate helper JSON and normalize hashes."""
```

### Internal models

```python
class TaskInspection(ProtocolModel):
    position: int
    hash: Digest
    name: str | None
    type: str

class TasksetInspection(ProtocolModel):
    taskset_id: str
    taskset_type: str
    infinite: bool
    task_count: int
    tasks: list[TaskInspection]
```

---

## 21.3 `tasksets/resolver.py`

### Class

```python
class TasksetResolver:
    def __init__(
        self,
        engine_runner: EngineRunner,
        inspect_script: Path,
    ) -> None: ...

    def resolve(
        self,
        *,
        taskset_ref: TasksetRef,
        selection: TaskSelection,
        engine_digest: Digest,
    ) -> TasksetLock:
        """Load twice, enforce determinism, and build lock."""
```

### Algorithm

1. Require Verifiers TasksetRef.
2. Require supported empty/custom config shape in WP5.
3. Run inspection.
4. Run inspection again in fresh process.
5. Normalize task hashes.
6. Compare ordered hashes.
7. Require count.
8. Require uniqueness.
9. Calculate membership digest.
10. Return lock.

The caller compares the lock with Campaign commitment.

---

## 21.4 `tasksets/verifiers_cli.py`

### Class

```python
class VerifiersValidationRunner:
    def __init__(self, engine_runner: EngineRunner) -> None: ...

    def run(
        self,
        *,
        taskset_id: str,
        num_tasks: int,
        output_dir: Path,
    ) -> EngineProcessResult:
        """Invoke pinned validate command."""

    def parse_summary(
        self,
        output_dir: Path,
    ) -> UpstreamValidationSummary:
        """Normalize summary.json."""

    def validation_artifacts(
        self,
        output_dir: Path,
    ) -> list[ArtifactRef]:
        """Digest expected validation outputs."""
```

Use the exact syntax proven by PI0.

---

## 21.5 `tasksets/service.py`

### Class

```python
class TasksetService:
    def __init__(
        self,
        paths: TechtreePaths,
        engine_registry: EngineRegistry,
        inspect_script: Path,
    ) -> None: ...

    def resolve_and_validate(
        self,
        *,
        campaign: CampaignSpec,
        run_dir: Path,
    ) -> tuple[TasksetLock, TasksetValidationReceipt]:
        """Resolve membership, validate, and issue local receipt."""
```

### Internal methods

```python
def _write_lock(
    self,
    run_dir: Path,
    lock: TasksetLock,
) -> ArtifactRef:
    """Persist lock."""

def _build_checks(
    self,
    lock: TasksetLock,
    campaign: CampaignSpec,
    summary: UpstreamValidationSummary,
) -> list[ValidationCheck]:
    """Build mechanical checks."""

def _receipt_status(
    self,
    checks: list[ValidationCheck],
    summary: UpstreamValidationSummary,
) -> Literal["valid", "invalid", "errored"]:
    """Determine status."""

def _write_receipt(
    self,
    run_dir: Path,
    receipt: TasksetValidationReceipt,
) -> ArtifactRef:
    """Persist receipt."""
```

### Success requirements

```text
inspection 1 succeeds
inspection 2 succeeds
hashes identical
hashes unique
count matches
membership matches Campaign
publisher validation references same TasksetLock commitment
Verifiers records every task
gold passes
setup passes
no errors
no timeouts
no missing rows
```

The local receipt need not have the same digest as the publisher receipt because IDs, times, and local artifact digests differ.

It must agree on:

```text
taskset lock
status
required check outcomes
```

---

# 22. Reference Taskset specification

## 22.1 Purpose

The reference Taskset proves:

- General procedure in `SKILL.md`.
- Unseen inputs.
- Deterministic expected answers.
- No answer table.
- Verifiers Taskset loading.
- Deterministic membership.
- Model-free validation.
- Future neutral baseline.
- Future skill candidate.

It is not a frontier benchmark.

## 22.2 BranchCode v1

1. Normalize input to lowercase ASCII.
2. Reject empty or unsupported text.
3. Map `a=1` through `z=26`.
4. Multiply each letter by one-indexed position.
5. Sum.
6. Count distinct characters.
7. Add seven times distinct count.
8. Reduce modulo 97.
9. Format `BRANCH-XX`.

---

## 22.3 `algorithm.py`

### Functions

```python
def normalize_input(value: str) -> str:
    """Strip, lowercase, and require ASCII a-z."""

def branch_code_number(value: str) -> int:
    """Return 0..96."""

def branch_code(value: str) -> str:
    """Return BRANCH-XX."""
```

Pure and deterministic.

---

## 22.4 `dataset.py`

### Constant

```python
PROVING_INPUTS: tuple[str, ...]
```

At least 32 fixed strings.

### Functions

```python
def proving_inputs() -> tuple[str, ...]:
    """Return immutable tuple."""

def validate_dataset() -> None:
    """Reject duplicates, invalid strings, and example overlap."""
```

No runtime generation.

---

## 22.5 `taskset.py`

### Models and classes

```python
class ProcedureTransferData(vf.TaskData):
    input_text: str
    answer: str

class ProcedureTransferTask(vf.Task[ProcedureTransferData]):
    def score_reply(self, reply: str) -> float:
        """Exact-match hidden answer."""

    @vf.reward
    async def exact_match(self, trace: vf.Trace) -> float:
        """Score trace.last_reply."""

    async def validate(self, runtime: vf.Runtime) -> bool:
        """
        Recompute oracle;
        require stored answer;
        require correct accepted;
        require known wrong rejected.
        """

class ProcedureTransferTaskset(
    vf.Taskset[ProcedureTransferTask, vf.TasksetConfig]
):
    def load(self) -> Iterable[ProcedureTransferTask]:
        """Yield deterministic tasks."""
```

### Prompt

```text
Apply BranchCode v1 to this input:

<input>

Return only the final BRANCH-XX token.
```

No procedure in prompt.

---

## 22.6 `__init__.py`

```python
from procedure_transfer_v1.taskset import ProcedureTransferTaskset

__all__ = ["ProcedureTransferTaskset"]
```

Export exactly one Taskset.

---

## 22.7 Reference package `pyproject.toml`

```toml
[project]
name = "procedure-transfer-v1"
version = "0.1.0"
description = "Deterministic BranchCode procedure-transfer taskset"
requires-python = ">=3.12"
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["procedure_transfer_v1"]
```

---

# 23. Embedded DataPolicy, Campaign, and Climb

## 23.1 DataPolicy

File:

```text
resources/catalog/data-policies/procedure-transfer-dev.json
```

Uses the development rights policy defined earlier.

Its digest is inserted into CampaignSpec.

## 23.2 Publisher validation receipt

File:

```text
resources/catalog/taskset-validations/procedure-transfer-dev.json
```

Generated by the pinned engine.

It references a publisher-generated TasksetLock commitment and records valid mechanical checks.

Its digest is inserted into CampaignSpec.

## 23.3 CampaignSpec

File:

```text
resources/catalog/campaigns/procedure-transfer-dev.json
```

Important values:

```yaml
metadata:
  id: campaign_...
  version: 1
  purpose: component_uplift

context:
  program_ref: null
  outcome_contract_digest: null

evaluation_backend:
  kind: local_techtree
  attestation: participant

evidence:
  verifiers_episode: required
  runtime_evidence: not_required

data_policy_digest: sha256:...
```

The scientific placeholders and task commitments follow the binding decisions.

## 23.4 ClimbManifest

File:

```text
resources/catalog/climbs/procedure-transfer-dev.json
```

Important values:

```yaml
metadata:
  slug: procedure-transfer-dev
  version: 1
  status: development
  title: Procedure Transfer Development Climb

campaign_spec_digest: sha256:...

candidate_policy:
  required_mutation: skill_insertion
  skill_visibility: public
  constraints:
    min_skills: 1
    max_skills: 1
    format: techtree-instruction-skill-v1

publication:
  report_visibility: public
  raw_episode_visibility: prohibited
  public_trace_projection: redacted
  proof_grade: development_only

leaderboard:
  enabled: false
  evidence_required: not_required
```

---

# 24. Tooling scripts

## 24.1 `tools/export_schemas.py`

### Functions

```python
def schema_models() -> dict[str, type[BaseModel]]:
    """Return filename/model mapping."""

def export_schema(
    model: type[BaseModel],
    destination: Path,
) -> None:
    """Generate stable JSON Schema."""

def main() -> None:
    """Rewrite schema tree."""
```

---

## 24.2 `tools/build_engine_bundle.py`

### Responsibilities

1. Copy authoritative reference package.
2. Write engine project.
3. Pin Verifiers exact commit.
4. Run `uv lock`.
5. Write engine descriptor.
6. Calculate and print bundle digest.

### Functions

```python
def copy_reference_package(
    source: Path,
    destination: Path,
) -> None:
    """Copy package source."""

def write_engine_project(
    destination: Path,
    pins: EnginePins,
) -> None:
    """Write pyproject with exact Verifiers source."""

def run_uv_lock(destination: Path) -> None:
    """Generate frozen lock."""

def write_engine_descriptor(
    destination: Path,
    descriptor: EngineDescriptor,
) -> None:
    """Write engine.json."""

def main() -> None:
    """Build static bundle."""
```

No catalog mutation.

---

## 24.3 `tools/build_fixture_catalog.py`

### Responsibilities

1. Locate built engine.
2. Install into temporary Techtree home.
3. Inspect Taskset twice.
4. Build publisher TasksetLock.
5. Run publisher model-free validation.
6. Build publisher TasksetValidationReceipt.
7. Build DataPolicy.
8. Build CampaignSpec.
9. Build ClimbManifest.
10. Write content-addressed object map.

### Functions

```python
def build_development_data_policy() -> DataPolicy:
    """Create fixed policy."""

def build_procedure_transfer_campaign(
    *,
    engine_digest: Digest,
    taskset_lock: TasksetLock,
    validation_receipt_digest: Digest,
    data_policy_digest: Digest,
) -> CampaignSpec:
    """Build scientific Campaign."""

def build_procedure_transfer_climb(
    *,
    campaign_digest: Digest,
) -> ClimbManifest:
    """Build public development wrapper."""

def write_catalog(
    *,
    climbs: list[ClimbManifest],
    objects: dict[Digest, Path],
    destination: Path,
) -> None:
    """Write catalog index and objects."""

def main() -> None:
    """Generate complete fixture catalog."""
```

---

## 24.4 `tools/build_goldens.py`

### Responsibility

Regenerate representative protocol fixtures from typed objects.

### Functions

```python
def golden_objects() -> dict[str, ProtocolModel]:
    """Return filename/model mapping."""

def write_golden(
    object_: ProtocolModel,
    destination: Path,
) -> None:
    """Write canonical or documented pretty JSON."""

def main() -> None:
    """Regenerate all goldens."""
```

---

# 25. Build and regeneration order

The binding order is:

```text
1. Edit engine pins and/or reference Taskset.
2. Build engine bundle.
3. Generate engine uv.lock.
4. Compute engine digest.
5. Install engine into temporary home.
6. Inspect Taskset twice.
7. Run publisher taskset validation.
8. Generate publisher TasksetLock.
9. Generate publisher TasksetValidationReceipt.
10. Generate DataPolicy.
11. Generate CampaignSpec.
12. Generate ClimbManifest.
13. Generate catalog object map.
14. Regenerate protocol goldens.
15. Regenerate JSON Schemas.
16. Run complete tests.
```

Commands:

```bash
python tools/build_engine_bundle.py
python tools/build_fixture_catalog.py
python tools/build_goldens.py
python tools/export_schemas.py
```

There is no true cycle because the engine does not contain catalog objects.

### Change classes

Engine pin or Taskset source:

```text
run full chain
```

Campaign placeholder metadata or DataPolicy:

```text
fixture-catalog → goldens
```

Protocol model:

```text
goldens → schemas
```

CI `generated-check` performs regeneration in a temporary tree and fails on drift.

---

# 26. Work package specifications

# WP0 — Freeze contracts

## Objective

Create durable protocol foundations before behavior.

## Added Campaign-kernel scope

WP0 now includes:

```text
CampaignSpec
ClimbManifest wrapper
DataPolicy
EvaluationBackend
ProgramRef
PublicContext
generic campaign references
```

It does not include:

```text
ImprovementProgram model
OutcomeContract model
ReleaseDecision model
TraceSet model
```

## Deliverables

```text
Pydantic models
schema constants
RFC 8785 canonicalization
SHA-256 digests
Verifiers task-hash normalizer
Ed25519 primitives
JSON Schema export
golden fixtures
protocol documentation
Campaign/Climb graph tests
DataPolicy contradiction tests
EvaluationBackend validation tests
```

## WP0 acceptance criteria

- [ ] Canonical output is byte-identical.
- [ ] One field mutation changes digest.
- [ ] Campaign has no public-policy fields.
- [ ] Climb has no scientific execution fields.
- [ ] DataPolicy is required by Campaign.
- [ ] EvaluationBackend is separate from runtime.
- [ ] All execution artifacts use `campaign_spec_digest`.
- [ ] Public Climb context is optional in scientific artifacts.
- [ ] ProgramRef and OutcomeContract digest are optional.
- [ ] Data-policy contradictions fail.
- [ ] Raw Verifiers hash normalizes correctly.
- [ ] No live signing.
- [ ] No Verifiers import.
- [ ] No Hermes import.
- [ ] No Relay import.

---

# WP1 — CLI shell and NextAction UX

## Objective

Create stable human and machine interface.

## Deliverables

```text
techtree executable
global options
human renderer
machine renderer
error boundary
exit codes
Doctor
embedded catalog
Climb list/show
resolved Campaign graph
DataPolicy display
NextAction behavior
CLI contract tests
```

## Commands

```bash
techtree --version
techtree doctor
techtree climb list
techtree climb show procedure-transfer-dev
```

## `climb show` must display

```text
public title and status
Campaign digest
purpose
task count
model placeholder
harness
subject runtime
evaluation backend
allowed mutation
primary reward
DataPolicy summary
candidate ownership
candidate public-release requirement
raw episode upload policy
training-use policy
development-only warning
```

## WP1 acceptance criteria

- [ ] Embedded Climb resolves Campaign.
- [ ] Campaign resolves DataPolicy.
- [ ] Campaign resolves publisher validation receipt.
- [ ] Every digest verifies.
- [ ] Contradictory public policy fails.
- [ ] Human and machine modes work.
- [ ] One JSON object on stdout.
- [ ] Every result has next action.
- [ ] No candidate path is read.
- [ ] No worker exists.
- [ ] No network.

---

# WP2 — Skill preparation

## Objective

Snapshot one candidate, build Campaign-derived experiment variants, enforce public candidate and data policies, and issue confirmation-bound draft.

## Sequence

1. Load resolved Climb graph.
2. Confirm development/open status.
3. Confirm Campaign and engine compatibility.
4. Resolve skill root.
5. Validate files.
6. Scan secrets.
7. Snapshot.
8. Build SkillArtifact.
9. Build baseline ExperimentManifest from Campaign.
10. Build candidate ExperimentManifest from Campaign.
11. Diff scientific configurations.
12. Require only skill mutation.
13. Bind DataPolicy.
14. Bind PublicContext.
15. Estimate episodes.
16. Build SubmissionDraft.
17. Issue confirmation token.
18. Persist entire graph.

## WP2 acceptance criteria

- [ ] No network.
- [ ] No model call.
- [ ] Snapshot immutable.
- [ ] Archive deterministic.
- [ ] Baseline zero skills.
- [ ] Candidate one skill.
- [ ] Campaign digest identical.
- [ ] DataPolicy digest identical.
- [ ] EvaluationBackend identical.
- [ ] PublicContext points to Climb digest.
- [ ] Policy acknowledgement included.
- [ ] Confirmation binds rights policy.
- [ ] Symlink and secret tests pass.

---

# WP3 — Fake worker and run state machine

## Objective

Complete asynchronous product loop without real evaluation.

## Deliverables

```text
RunRequest with generic Campaign references
event log
state machine
RunStore
WorkerLauncher
worker executable
FakeRunExecutor
status/logs/cancel/result commands
fake receipts carrying DataPolicy and EvaluationBackend
development-only report
```

## WP3 acceptance criteria

- [ ] Worker detached.
- [ ] Survives parent exit.
- [ ] State rebuilds from events.
- [ ] Heartbeat works.
- [ ] Logs work.
- [ ] Cancellation works.
- [ ] Duplicate draft start rejected.
- [ ] Fake EpisodeReceipts say subject not executed.
- [ ] Fake report blocked from publication.
- [ ] Campaign, DataPolicy, EvaluationBackend propagate unchanged.
- [ ] No provider credential read.
- [ ] No Docker pull.

---

# WP4 — Managed Verifiers engine

## Objective

Create separately pinned scientific environment.

## Deliverables

```text
PI0 preflight
engine bundle
exact Verifiers pin
separate uv.lock
bundle digest
EngineRegistry
EngineInstaller
EngineRunner
setup
engine commands
integration tests
```

## WP4 acceptance criteria

- [ ] PI0 green.
- [ ] Fresh home installs engine.
- [ ] Separate virtual environment.
- [ ] Exact Verifiers commit.
- [ ] `validate` exists.
- [ ] `eval` exists for WP6.
- [ ] Reference Taskset imports.
- [ ] Bundle digest stable.
- [ ] Global environment irrelevant.
- [ ] Reinstall idempotent.
- [ ] Catalog not embedded in engine.

---

# WP5 — Reference Taskset and model-free validation

## Objective

Load real Taskset, freeze membership, run real validation, create local receipt, and compare local validation with publisher Campaign commitment.

## Deliverables

```text
reference Taskset
taskset inspection helper
TasksetResolver
publisher taskset lock and validation fixture
local taskset lock
local validation runner
local validation receipt
Campaign commitment checks
fake worker integration
```

## Worker flow

```text
resolve snapshotted Campaign
        ↓
resolve local TasksetLock
        ↓
compare Campaign membership
        ↓
run local Verifiers validation
        ↓
compare with publisher validation contract
        ↓
fake baseline
        ↓
fake candidate
        ↓
development-only report
```

## WP5 acceptance criteria

- [ ] Taskset imports by ID.
- [ ] Exactly one Taskset exported.
- [ ] Ordered hashes repeat.
- [ ] Hashes normalize to Techtree digests.
- [ ] Hashes unique.
- [ ] Membership matches Campaign.
- [ ] Publisher validation references same committed membership.
- [ ] Local gold passes.
- [ ] Local setup passes.
- [ ] Negative control is tested by Task.validate.
- [ ] No errors/timeouts/missing.
- [ ] Local receipt verifies.
- [ ] Validation failure blocks fake phases.
- [ ] Final report remains development-only.

---

# 27. Test specifications

## 27.1 `tests/conftest.py`

Fixtures:

```python
temp_techtree_home
test_paths
test_settings
embedded_catalog_repository
catalog_service
resolved_development_climb
draft_store
run_store
engine_registry
valid_skill_path
prepared_draft
```

No test writes to real user home.

---

## 27.2 Unit tests

### `test_campaign_models.py`

- Campaign rejects public metadata.
- Climb rejects scientific fields.
- Campaign requires DataPolicy digest.
- Campaign validates single subject.
- Campaign rejects shuffle true.
- ProgramRef optional.
- OutcomeContract digest optional.

### `test_data_policy.py`

- Development policy valid.
- Public Climb contradiction rejected.
- Owner/account rules.
- Training-use values.
- Public candidate requirement.

### `test_evaluation_backend.py`

- Local/participant valid.
- Local/platform invalid.
- Prime Lab without refs invalid.
- Independent without executor invalid.
- WP0–WP5 service rejects unsupported kinds.

### Existing unit tests

```text
canonical
crypto
IDs
confirmation
manifest comparison
run machine
skill archive
skill scanner
taskset models
```

---

## 27.3 Contract tests

### `test_catalog_object_graph.py`

- Climb resolves Campaign.
- Campaign resolves DataPolicy.
- Campaign resolves validation receipt.
- Digests verify.
- Broken path fails.
- Wrong type fails.
- Public-policy contradiction fails.

### Existing contract tests

```text
CLI envelope
machine mode
JSON Schemas
golden files
```

---

## 27.4 Integration tests

### `test_skill_prepare.py`

Complete graph-aware prepare.

### `test_fake_run.py`

Prepare → start → poll → result.

### `test_run_cancel.py`

Cancel slow fake run.

### `test_engine_install.py`

Install pinned engine.

### `test_taskset_membership.py`

Inspect twice and compare Campaign.

### `test_taskset_validation.py`

Run real validation and compare publisher commitment.

---

# 28. Local filesystem after WP5

```text
~/.techtree/
├── config.toml
├── cache/
├── drafts/
│   └── draft_.../
│       ├── public/
│       │   ├── climb.json
│       │   ├── campaign.json
│       │   ├── data-policy.json
│       │   └── publisher-validation.json
│       ├── manifests/
│       └── skill/
├── engines/
│   └── sha256-.../
│       ├── engine.json
│       ├── pyproject.toml
│       ├── uv.lock
│       ├── packages/
│       ├── .venv/
│       └── installed.json
└── runs/
    └── run_.../
        ├── .lock
        ├── request.json
        ├── events.jsonl
        ├── state.json
        ├── heartbeat.json
        ├── pid
        ├── worker.log
        ├── taskset/
        │   ├── lock.json
        │   └── validation/
        │       ├── config.toml
        │       ├── results.jsonl
        │       ├── summary.json
        │       ├── validate.log
        │       └── receipt.json
        ├── receipts/
        │   ├── baseline/
        │   └── candidate/
        └── report/
            └── uplift.json
```

---

# 29. CLI flow after WP5

```bash
techtree setup
```

```bash
techtree climb list
```

```bash
techtree climb show procedure-transfer-dev
```

The output includes DataPolicy and Campaign digest.

```bash
techtree climb prepare procedure-transfer-dev \
  --skill ./skills/branch-code
```

```bash
techtree climb start draft_... \
  --confirmation-token ...
```

```bash
techtree run status run_... --watch
```

```bash
techtree run logs run_... --tail 200
```

```bash
techtree run result run_...
```

Required warning:

```text
This is a development-only report.

The taskset was validated through Prime Intellect Verifiers.
The baseline and candidate results were generated by the fake executor.
No agent was evaluated. The report is not publication eligible.

The candidate and generated artifacts remain governed by DataPolicy:
sha256:...
```

---

# 30. Hermes plugin boundary

Do not implement `hermes-plugin` during WP0–WP5.

Its future tools remain:

```text
techtree_system_check
techtree_climbs_list
techtree_climb_inspect
techtree_climb_prepare
techtree_climb_start
techtree_run_status
techtree_run_cancel
techtree_proof_get
```

The plugin later calls CLI JSON.

It does not implement Campaign resolution or DataPolicy enforcement itself.

---

# 31. Suggested pull-request sequence

## PR 1 — Repository and tooling

Root files, CI, docs skeleton.

## PR 2 — Protocol core

Now includes:

```text
CampaignSpec
Climb wrapper
DataPolicy
EvaluationBackend
generic campaign references
canonicalization
crypto primitives
schemas and goldens
```

## PR 3 — CLI foundation

CLI envelope, rendering, Doctor.

## PR 4 — Embedded catalog

Now includes content-addressed:

```text
Climb
Campaign
DataPolicy
publisher validation
```

## PR 5 — Skill scanner/archive

Unchanged in core behavior.

## PR 6 — Manifests/drafts

Now Campaign-derived and DataPolicy-bound.

## PR 7 — Run event system

RunRequest uses generic Campaign refs.

## PR 8 — Worker/fake executor

Fake receipts/report carry Campaign/DataPolicy/EvaluationBackend.

## PR 9 — Managed engine

Unchanged except exact pin.

## PR 10 — Reference Taskset

Unchanged scientific content.

## PR 11 — Taskset locking

Compares actual membership to Campaign.

## PR 12 — Taskset validation

Compares local mechanical validation to publisher commitment.

## PI0 — Pinned Verifiers preflight

May run in parallel with WP0–WP3 but blocks PR9–PR12.

---

# 32. Ticket dependency guidance

```text
Repository initialization
├── PI0 Verifiers preflight
└── PR1 Repository/tooling
      ↓
    PR2 Protocol core
      ↓
    PR3 CLI foundation
      ↓
    PR4 Catalog object graph
      ↓
    PR5 Skill scanner/archive
      ↓
    PR6 Campaign-derived manifests/drafts
      ↓
    PR7 Run event system
      ↓
    PR8 Worker/fake executor
```

Reference procedure pure code may begin early:

```text
algorithm.py
dataset.py
pure tests
```

Verifiers Taskset integration waits for PI0.

Then:

```text
PI0 + PR1 + reference Taskset
        ↓
PR9 Engine
        ↓
PR11 Taskset locking
        ↓
PR12 Taskset validation
```

---

# 33. Definition of done

## Campaign kernel

- [ ] Campaign and Climb are separate.
- [ ] Campaign owns scientific configuration.
- [ ] Climb owns public policy.
- [ ] DataPolicy is required.
- [ ] EvaluationBackend is explicit.
- [ ] ProgramRef optional.
- [ ] OutcomeContract digest optional.
- [ ] Execution artifacts use Campaign digest.
- [ ] Public context is optional.
- [ ] Cross-object digests verify.

## Protocol

- [ ] Schemas committed.
- [ ] Canonicalization deterministic.
- [ ] Digests stable.
- [ ] Crypto primitives tested.
- [ ] Goldens stable.
- [ ] No live signing.

## CLI

- [ ] Human and machine mode.
- [ ] Typed errors.
- [ ] Stable exit codes.
- [ ] Next actions.
- [ ] Data rights shown before preparation/start.
- [ ] No prompts in no-input mode.

## Candidate preparation

- [ ] Skill validation.
- [ ] Secret blocking.
- [ ] Immutable snapshot.
- [ ] Deterministic archive.
- [ ] Controlled manifests.
- [ ] DataPolicy binding.
- [ ] Confirmation binding.

## Run control

- [ ] Detached worker.
- [ ] Event sourcing.
- [ ] Heartbeat.
- [ ] Logs.
- [ ] Cancellation.
- [ ] Development-only fake result.
- [ ] Generic Campaign refs preserved.

## Engine

- [ ] Exact Verifiers pin.
- [ ] Separate lock.
- [ ] Stable digest.
- [ ] Verified install.
- [ ] Global environment irrelevant.

## Taskset validation

- [ ] Real Taskset loads.
- [ ] Membership stable.
- [ ] Publisher validation generated.
- [ ] Local validation passes.
- [ ] Local/publisher commitments agree.
- [ ] Receipt verifies.
- [ ] Failures block run.

## Explicit exclusions

- [ ] No Hermes subject.
- [ ] No real model call.
- [ ] No Verifiers eval.
- [ ] No Relay.
- [ ] No website.
- [ ] No publication.
- [ ] No ImprovementProgram behavior.
- [ ] No OutcomeContract behavior.
- [ ] No EnvironmentQualificationReport.
- [ ] No ReleaseDecision.
- [ ] No TraceSet.
- [ ] No Prime Lab handoff.
- [ ] No Hermes plugin implementation.

---

# 34. Handoff to WP6

WP6 reuses:

```text
CampaignSpec
ClimbManifest
DataPolicy
EvaluationBackend
SkillArtifact
ExperimentManifest
TasksetLock
TasksetValidationReceipt
RunRequest
RunEvent
RunState
RunStore
WorkerLauncher
EngineRegistry
EngineRunner
TasksetService
CliEnvelope
NextAction
```

WP6 adds:

```text
Verifiers eval TOML compiler
baseline eval
candidate eval
Docker checks
HermesAgentHarness
Episode parser
real EpisodeReceipt
real reward aggregation
observed comparison
real local P1 report
```

WP6 continues without Relay initially.

The first real loop is:

```text
Campaign taskset validated
        ↓
baseline Hermes subject in Docker
        ↓
candidate Hermes subject in Docker
        ↓
Verifiers Episodes and Traces
        ↓
Techtree controlled comparison
        ↓
local participant-attested P1 UpliftReport
```

After that loop is repeatable, Relay may be added as optional runtime evidence.

---

# 35. Final implementation principle

These first six work packages define the durable product substrate:

```text
WP0 defines the reusable Campaign and proof contracts.
WP1 defines how humans and host agents control them.
WP2 defines exactly what candidate and rights policy were accepted.
WP3 defines how work survives host-agent sessions.
WP4 defines which scientific software actually ran.
WP5 defines which tasks were valid and included.
```

The later product family wraps and reuses this kernel:

```text
Blueprint scopes a real workflow.
Forge qualifies the environment.
Verify executes Campaigns privately.
Uplift generates candidate Campaign variants.
Trace selects rights-qualified evidence.
Climb publishes a Campaign publicly.
Prime Lab executes or trains from qualified handoffs.
```

None of those later modes should require Techtree to rewrite the Campaign, execution, receipt, comparison, or rights foundations created here.


---

# Appendix A. Revision delta from the prior WP0–WP5 specification

The prior specification remains structurally valid. This revision changes the protocol boundary, not the product sequence.

## A.1 Added now

```text
CampaignSpec
DataPolicy
EvaluationBackend
ProgramRef
PublicContext
optional outcome_contract_digest
content-addressed embedded catalog graph
publisher TasksetValidationReceipt fixture
```

## A.2 Changed now

```text
ClimbManifest
    becomes a public wrapper instead of the scientific contract

SubmissionDraft
    climb_digest → campaign_spec_digest + optional PublicContext
    adds data_policy_digest
    adds optional program_ref and outcome_contract_digest

ExperimentManifest
    climb_digest → campaign_spec_digest
    adds DataPolicy and EvaluationBackend propagation

RunRequest
    climb_digest → campaign_spec_digest
    adds public/program context and rights policy

EpisodeReceipt
    generic Campaign references
    explicit EvaluationBackend
    explicit subject runtime
    no Relay

UpliftReport
    generic Campaign references
    DataPolicy and EvaluationBackend
    typed ExecutionStatus and PublicationStatus

Catalog
    resolves Climb → Campaign → DataPolicy → publisher validation
```

## A.3 Unchanged

```text
contracts before behavior
CLI as host-agent boundary
detached worker
fake executor
managed engine
pinned Verifiers preflight
reference Taskset
model-free validation
no Relay
no signing flow
no Hermes plugin during WP0–WP5
no Ash website during WP0–WP5
```

## A.4 Deferred

```text
ImprovementProgram
Blueprint
OutcomeContract implementation
EnvironmentQualificationReport
ReleaseDecision
TraceSet
TrainingExportReceipt
PrimeLabHandoff
private Verify control plane
SkillOpt
```

## A.5 Worker-thread rule

No worker should continue from an older ticket slice that places scientific configuration directly inside `ClimbManifest`.

All tickets must be refreshed from this revision before implementation begins.
