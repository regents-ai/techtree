# Techtree Climb v0.1

## Work Packages 6–8 Implementation Specification

### Real Verifiers/Hermes execution, controlled uplift receipts and presentation, and the minimal read-only Ash web surface

**Status:** Binding implementation supplement for the current Techtree push  
**Audience:** Chief-of-staff agent, work-package owners, worker-thread implementers, reviewers, and release gatekeepers  
**Primary repositories:** `techtree-python/` for WP6–WP7; `techtree-ash/` for WP8  
**Not the same as:** PR slices 6–8. The repository already contains a separate binding document for PR6–PR8.  
**Work packages covered:**

```text
WP6 — Native Verifiers execution with a pinned Hermes subject in Docker
WP7 — Real EpisodeReceipts, controlled comparison, local UpliftReport, signing,
      presentation payloads, and the pairwise Skill-improvement seam
WP8 — Minimal read-only Ash/Phoenix onboarding and catalog surface at techtree.sh
```

**Pinned Prime Intellect Verifiers revision:**

```text
7e1c47d24d055aae587ee8259f77a3e8e193513a
```

**Pinned initial Hermes subject version:**

```text
0.19.0
```

**NeMo Relay:** deliberately excluded from WP6–WP8  
**Receipt upload/public proof publication:** deliberately excluded from this push  
**Primary local host:** macOS, including Apple Silicon  
**Primary subject runtime:** Verifiers Docker runtime  
**Primary evaluation truth:** Verifiers Episodes, Traces, named rewards, and metrics  
**Final local artifact:** a signed, locally verifiable `UpliftReport`; the terminal may call it an “Uplift receipt” in explanatory copy, but the canonical protocol object remains `UpliftReport`

---

# 0. Why this document exists

WP0–WP5 establish the reusable Campaign kernel: immutable Campaign and DataPolicy objects, deterministic candidate snapshots, manifests, an event-sourced detached worker, a separately locked scientific engine, deterministic task membership, and model-free taskset validation. The product-family direction remains that Climb is only the public projection of a reusable Campaign; Verify and Uplift will reuse the same execution and receipt kernel rather than becoming parallel evaluators.

The product model explicitly says that Climb is the public proof and competition mode, Verify executes baseline and assurance campaigns, Uplift searches for and proves an effective intervention, and Trace later packages rights-qualified evidence. The current implementation therefore must deepen the shared Campaign kernel without putting the broader ImprovementProgram into the Climb worker.

This document begins where the revised WP0–WP5 specification ends:

```text
validated Campaign
        ↓
resolved baseline and candidate ExperimentManifests
        ↓
run-owned immutable inputs
        ↓
real Hermes subjects in clean Docker runtimes
        ↓
Verifiers Episodes and Traces
        ↓
real EpisodeReceipts
        ↓
controlled comparison
        ↓
locally signed UpliftReport
        ↓
channel-aware human/agent presentation
```

WP8 adds only the public onboarding and read-only catalog surface needed for people and host agents to discover and install the local system. It does not receive local traces or receipts.

---

# 1. Whole-push product outcome

The end of WP8 is not yet the complete user journey because the Hermes operator plugin is WP9+. WP6–WP8 must nevertheless expose all stable interfaces required for the following whole-push acceptance scenario.

## 1.1 Required final user journey after WP9+

A user may be talking to Hermes through:

```text
a local terminal
Hermes Gateway on a phone
another Hermes-supported messaging surface
```

The user says, in substance:

```text
Install Techtree and show me whether this Skill helps.
```

The system must support this sequence:

```text
1. The user installs and explicitly enables the Techtree Hermes plugin.
2. The plugin checks for the `techtree` CLI.
3. With explicit installation approval, the plugin installs the pinned
   `techtree-python` release through `uv tool install`.
4. The plugin runs Techtree Doctor and reports any missing Docker or model
   prerequisite.
5. The plugin selects the simple Procedure Transfer Campaign.
6. The user explicitly accepts the Campaign's DataPolicy and execution budget.
7. Techtree launches one controlled comparison job containing:
      baseline: pinned Hermes subject, no tested Skill
      candidate: same pinned Hermes subject, tested Skill mounted
8. Baseline and candidate variants execute as close together in time as the
   declared schedule permits, with separate clean Docker runtimes and the same
   task membership, model, sampling, harness version, tools, and scorer.
9. The host agent can poll structured side-by-side progress.
10. Techtree builds signed local EpisodeReceipts and an UpliftReport.
11. In a terminal channel, the host agent loads the supplied
    `rich-terminal-output` operator Skill and presents the difference vividly.
12. In a phone/gateway channel, the host agent uses the compact Markdown
    projection instead of ANSI/Rich terminal control codes.
13. The user may ask Hermes to improve the tested Skill.
14. The host Hermes agent loads a separate preloaded improvement Skill supplied
    by the founder, receives a sanitized local improvement context, and spends
    one host-agent reasoning turn proposing Skill v2.
15. Techtree snapshots Skill v2 and runs a new controlled comparison:
      baseline: Skill v1
      candidate: Skill v2
16. Techtree shows the second side-by-side result and writes another locally
    verifiable UpliftReport.
17. No receipt, raw episode, trace, or Skill is uploaded to the Ash web app in
    this push.
```

## 1.2 What WP6–WP8 must provide for that journey

WP6 provides:

```text
real model-backed Verifiers execution
Docker subject isolation
pinned Hermes harness execution
variant scheduling
live structured progress
raw Verifiers output retention
normalized episode projections
```

WP7 provides:

```text
real receipts
local signatures
controlled declared and observed comparison
pairwise Skill insertion and Skill replacement
UpliftReport
presentation payloads
sanitized improvement context
local proof verification
```

WP8 provides:

```text
academic onboarding site
pinned install instructions
read-only bootstrap manifest
read-only Campaign/Climb catalog API
human-readable Campaign pages
no uploads and no execution
```

WP9+ provides:

```text
Hermes plugin installation and CLI bridge
operator workflow
channel detection
loading rich-terminal-output and founder-supplied improvement Skills
explicit user confirmation
one-turn Skill revision
```

---

# 2. Source-of-truth boundaries

## 2.1 Host Hermes is the operator, never the evaluated subject

The host Hermes process may contain mutable user state, memories, plugins, credentials, conversations, and local files. It chooses and supervises work only.

Every evaluated Hermes subject is created inside a Verifiers-managed Docker runtime from an immutable `ExperimentManifest`.

```text
Host Hermes
    operator and UX

Docker Hermes
    evaluated subject
```

The operator-side `rich-terminal-output` Skill and the founder-supplied Skill-improvement Skill must never be mounted into the evaluated subject.

## 2.2 Verifiers is evaluation and reward truth

Techtree does not recalculate task correctness from raw text when a valid Verifiers reward exists.

Techtree may:

```text
parse rewards
verify their names and weights
aggregate declared rewards
pair baseline/candidate task identities
verify invariants
compute report-level descriptive statistics
```

Techtree may not:

```text
replace the task's reward function
silently reinterpret a failed reward
invent a second answer key
change expected outputs
change task membership after resolution
```

At the pinned revision, Verifiers evaluation writes a resolved `config.toml`, appends one complete Episode JSON object per line to `traces.jsonl`, and writes `eval.log`. Episodes are appended in completion order, not task order. Techtree must always join and order results by normalized task identity, never by line position.

## 2.3 CampaignSpec is the scientific root

The worker requires the resolved `CampaignSpec` and run-owned inputs. It does not require public website availability or mutable Climb state.

The public `ClimbManifest` remains discovery and policy context. The local execution lineage carries:

```text
campaign_spec_digest
public_context, when the Campaign came from a Climb
program_ref, when present
outcome_contract_digest, when present
data_policy_digest
evaluation_backend
```

## 2.4 DataPolicy controls every artifact path

The reference local policy for this push remains:

```text
raw episodes:
    local retention allowed
    server upload prohibited
    public release prohibited
    training use prohibited

candidate Skill:
    participant-owned
    local use allowed
    public release may be required by a future public Climb
    no upload occurs in this push

aggregate result:
    local display allowed
    UpliftReport may be written locally
```

WP8 must not add an API route that accepts any of these local artifacts.

## 2.5 Evaluation backend and subject runtime stay separate

For this push:

```yaml
evaluation_backend:
  kind: local_techtree
  attestation: participant

agents:
  subject:
    runtime:
      type: docker
```

The evaluation backend says who orchestrated and attested to the run. The runtime says where the subject executed.

## 2.6 NeMo Relay is out of scope

No WP6–WP8 acceptance criterion depends on Relay, ATOF, ATIF, OpenTelemetry, or a Hermes observability plugin.

Evidence completeness in this push is based on:

```text
Verifiers config
Verifiers Episode and Trace records
reward and metric completeness
resolved subject/runtime information
raw output digests
Techtree receipt and report links
```

Relay can later strengthen operational evidence without changing score validity.

---

# 3. Required additive amendments before WP6 implementation

The committed WP0 models were intentionally narrow. The final local demo requires two additive capabilities that the initial no-Skill-versus-one-Skill Climb did not require.

These amendments must be made in one explicit, reviewed protocol ticket. Do not hide them inside the executor implementation.

## 3.1 Mutation kind: Skill replacement

Current v0.1 supports:

```text
skill_insertion:
    baseline Skills = []
    candidate Skills = [Skill v1]
```

The improvement loop requires:

```text
skill_replacement:
    baseline Skills = [Skill v1]
    candidate Skills = [Skill v2]
```

Amend:

```python
class MutationKind(str, Enum):
    SKILL_INSERTION = "skill_insertion"
    SKILL_REPLACEMENT = "skill_replacement"


class MutationContract(ProtocolModel):
    kind: MutationKind
    target_agent: Literal["subject"]
    allowed_differences: list[str]
    minimum_skills: int
    maximum_skills: int
```

Validation rules:

```text
skill_insertion:
    baseline must contain zero tested Skills
    candidate must contain exactly one tested Skill

skill_replacement:
    baseline must contain exactly one tested Skill
    candidate must contain exactly one tested Skill
    baseline and candidate Skill root digests must differ

both:
    every observed scientific difference must remain under
    /agents/subject/harness/skills
```

The public Procedure Transfer Climb continues to require `skill_insertion`. A local follow-up Uplift Campaign may use `skill_replacement` without a public Climb wrapper.

## 3.2 Execution schedule: concurrent variants

The current execution object permits only `baseline_then_candidate`. The target UX requires a single job whose two variants can progress side by side and minimize provider-time drift.

Amend:

```python
class VariantSchedule(str, Enum):
    SEQUENTIAL = "baseline_then_candidate"
    PARALLEL = "parallel_variants"


class ExecutionSpec(ProtocolModel):
    order: VariantSchedule
    max_concurrent: int
    timeout_seconds: int
    retry_limit: int
```

The reference live Campaign uses:

```yaml
execution:
  order: parallel_variants
  max_concurrent: 4
  timeout_seconds: 900
  retry_limit: 1
```

`max_concurrent` is the Campaign-wide upper bound. The executor divides it between variants so the total live episode count does not silently double beyond the declared limit.

## 3.3 Run phase and progress amendment

Add:

```python
RunPhase.RUNNING_VARIANTS = "running_variants"
```

Keep the existing sequential phases for fake tests and compatibility:

```text
running_baseline
running_candidate
```

Add known same-phase event kinds:

```python
VARIANT_STARTED = "variant.started"
VARIANT_PROGRESS = "variant.progress"
VARIANT_COMPLETED = "variant.completed"
```

They are valid only while phase is `running_variants`.

Add a projected structure:

```python
class VariantProgress(StateModel):
    variant: Literal["baseline", "candidate"]
    completed: int
    total: int
    running: int
    errored: int
    state: Literal["pending", "running", "completed", "failed", "cancelled"]


class RunState(StateModel):
    # existing fields remain
    variant_progress: dict[str, VariantProgress] = {}
```

No existing event kind becomes free-form. The run store must retain the strict known-kind and same-phase restrictions established by PR7.

## 3.4 Local proof semantics

Activate the existing Ed25519 primitives in WP7.

A real local report may use:

```text
proof_grade: P1
```

only when:

```text
all referenced artifact digests verify
all EpisodeReceipts are wrapped in signed ObjectEnvelopes
the UpliftReport is wrapped in a signed ObjectEnvelope
the local public key is included in the bundle
the comparison is controlled or controlled_with_warnings
score status is valid
```

The key is self-issued and local in this push. P1 therefore means:

```text
integrity-bound, participant-attested local execution
```

It does not mean independent or platform-witnessed execution.

## 3.5 No protocol amendment for presentation

Rich terminal output is a view, not scientific evidence.

Do not add terminal markup, color, emoji, prose, or channel-specific formatting to `EpisodeReceipt` or `UpliftReport`.

Create separate presentation models and builders under WP7.

---

# 4. Release inputs that remain founder-owned

Workers must not silently choose these release values:

```text
1. Repository license.
2. The exact model ID for the first released live Campaign.
3. The exact Git commit/tag used to publish the Hermes plugin.
4. The qualified name or path of the `rich-terminal-output` operator Skill.
5. The qualified name or path of the founder-supplied Skill-improvement Skill.
6. The initial subject Skill content used for the first demo, if it differs from
   the reference BranchCode procedure Skill.
```

Implementation and tests must accept these as release configuration.

For automated integration tests, use environment-provided values such as:

```text
TECHTREE_E2E_MODEL_ID
PRIME_API_KEY or active Prime CLI authentication
TECHTREE_RICH_OUTPUT_SKILL
TECHTREE_SKILL_IMPROVER_SKILL
```

Do not commit credentials.

---

# 5. Repository-level architecture after WP8

```text
techtree-python/
    protocol, CLI, engine, real execution, receipts, comparison,
    local signing, presentation payloads, and improvement context

techtree-ash/
    read-only onboarding, bootstrap manifest, and catalog projection

hermes-plugin/                         # WP9+
    operator-facing CLI bridge and workflow Skills
```

The local scientific loop must continue to work when:

```text
techtree.sh is offline
no Ash app is running
no Hermes plugin is installed
the user invokes the CLI directly
```

WP8 is discovery and onboarding, not a runtime dependency.


---

# 6. Work Package 6 — Native Verifiers execution

## 6.1 Objective

Replace the fake reward-producing executor with a real executor that:

```text
validates the already-locked Campaign inputs
compiles one resolved Verifiers configuration per variant
runs pinned Hermes Agent subjects in clean Docker runtimes
routes all subject model calls through Verifiers interception
runs baseline and candidate variants under the declared schedule
retains raw Verifiers outputs locally
normalizes output through engine-pinned tooling
publishes structured progress into the existing run event system
returns a typed RealExecutionResult to WP7
```

WP6 does not build final Techtree receipts or decide whether uplift is accepted. It produces verified execution inputs for WP7.

## 6.2 WP6 non-goals

Do not implement:

```text
NeMo Relay
website upload
public proof pages
leaderboards
Skill optimization
host Hermes plugin
founder-supplied improvement Skill invocation
release decisions
Prime Lab hosted execution
multiple models
multiple tasksets
multiple subject harnesses
```

The only live subject in WP6 is the pinned Hermes Agent harness.

## 6.3 Upstream facts that are part of the contract

Against the pinned Verifiers revision:

- The `eval` entrypoint accepts a taskset or `@ config.toml`.
- `--dry-run` resolves and validates configuration and writes resolved config.
- Evaluation output contains `config.toml`, `traces.jsonl`, and `eval.log`.
- Each non-empty line of `traces.jsonl` is one complete Episode object.
- Episode lines append as episodes complete, so file order is completion order.
- `push` defaults to true; Techtree must explicitly set it false.
- The native Hermes harness pins a Hermes version, supports Skills, creates a fresh per-Trace `HERMES_HOME`, disables bundled Skills when configured, routes model calls through the Verifiers interception endpoint, and cleans the home afterward.
- The native Hermes harness refuses `disabled_tools`; the reference Campaign must not compile that field.
- The default Verifiers evaluation client is OpenAI-compatible and can use Prime Inference through `PRIME_API_KEY` or active Prime CLI configuration.

These facts must also be covered by an engine compatibility test so a later Verifiers pin change cannot silently alter execution behavior.

---

## 6.4 Required file additions in `techtree-python`

```text
src/techtree/
├── verifiers/
│   ├── __init__.py
│   ├── models.py
│   ├── config.py
│   ├── compiler.py
│   ├── credentials.py
│   ├── child.py
│   ├── progress.py
│   ├── outputs.py
│   ├── normalize.py
│   ├── verify.py
│   └── errors.py
│
├── runs/
│   ├── real.py
│   ├── variants.py
│   └── child_registry.py
│
└── doctor/
    └── execution_checks.py

src/techtree/resources/engines/default/
├── tools/
│   ├── inspect_taskset.py                 # already present after WP4/WP5
│   ├── normalize_validation.py            # already present after amendments
│   └── normalize_eval_output.py            # new in WP6
└── packages/
    └── procedure-transfer-v1/
        └── procedure_transfer_v1/
            ├── __init__.py                 # amended export
            └── env.py                      # new named-subject Env

tests/
├── unit/
│   ├── test_verifiers_config.py
│   ├── test_verifiers_compiler.py
│   ├── test_verifiers_credentials.py
│   ├── test_verifiers_outputs.py
│   ├── test_verifiers_progress.py
│   ├── test_verifiers_verify.py
│   └── test_variant_schedule.py
│
├── integration/
│   ├── test_verifiers_dry_run.py
│   ├── test_verifiers_mock_eval.py
│   ├── test_real_executor_parallel.py
│   ├── test_real_executor_cancel.py
│   ├── test_eval_normalizer.py
│   └── test_named_subject_env.py
│
└── e2e/
    └── test_live_hermes_comparison.py
```

If the current repository already uses equivalent modules with different names, preserve the existing naming style. The responsibilities and boundaries below remain binding.

---

## 6.5 Named-subject Verifiers environment

### Problem

Verifiers’ default `SingleAgentEnv` uses an `agent` seat. Techtree’s scientific model names the evaluated role `subject` and future receipts group traces by declared role.

Do not rename a recorded `agent` role after execution merely for presentation. Make the role real in the Verifiers environment.

### File: engine package `procedure_transfer_v1/env.py`

Implement:

```python
from __future__ import annotations

import verifiers.v1 as vf


class ProcedureTransferEnvConfig(vf.EnvConfig):
    subject: vf.AgentConfig = vf.AgentConfig()


class ProcedureTransferEnv(vf.Env[ProcedureTransferEnvConfig]):
    async def run(self, task: vf.Task, agents: vf.Agents) -> None:
        await agents.subject.run(task)
```

### Export amendment

`procedure_transfer_v1/__init__.py` exports exactly one Taskset subclass and exactly one Env subclass:

```python
from procedure_transfer_v1.env import ProcedureTransferEnv
from procedure_transfer_v1.taskset import ProcedureTransferTaskset

__all__ = [
    "ProcedureTransferTaskset",
    "ProcedureTransferEnv",
]
```

This is valid because Verifiers filters exported classes by the requested base type. The Taskset loader still sees one Taskset, and the environment loader sees one Env.

### Tests

Prove:

```text
Taskset loads by package ID.
Environment resolves from the taskset package when env.id is empty.
The resolved EnvConfig contains a `subject` AgentConfig field.
A mock episode's Trace records agent.name == "subject".
No `agent` role appears in normalized output.
```

---

## 6.6 Models: `verifiers/models.py`

These are local integration models, not new Techtree protocol roots.

### `VariantName`

```python
class VariantName(str, Enum):
    BASELINE = "baseline"
    CANDIDATE = "candidate"
```

### `VariantExecutionPlan`

```python
class VariantExecutionPlan(ProtocolModel):
    variant: VariantName
    experiment_manifest_digest: Digest
    experiment_manifest_path: str
    verifiers_input_config_path: str
    verifiers_output_dir: str
    skill_paths: list[str]
    task_count: int
    max_concurrent: int
```

Paths are run-owned paths. This object is local and should not be published.

### `ChildProcessOutcome`

```python
class ChildProcessOutcome(ProtocolModel):
    variant: VariantName
    argv_digest: Digest
    exit_code: int
    started_at: datetime
    finished_at: datetime
    stdout_artifact: ArtifactRef
    stderr_artifact: ArtifactRef
    cancelled: bool
```

Do not store the raw argv if it could contain a secret. The compiled invocation must never put a secret in argv, so a sanitized argv may also be retained operationally.

### `NormalizedReward`

```python
class NormalizedReward(ProtocolModel):
    name: str
    score: float
    weight: float
    value: float
```

Require all values finite.

### `NormalizedUsage`

```python
class NormalizedUsage(ProtocolModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_input_tokens: int | None = None
```

### `NormalizedTool`

```python
class NormalizedTool(ProtocolModel):
    name: str
    description_digest: Digest
    parameters_digest: Digest
```

### `NormalizedRuntime`

```python
class NormalizedRuntime(ProtocolModel):
    kind: Literal["docker"]
    runtime_id: str | None
    image: str
    resolved_image_digest: Digest | None
    cpu: float | None
    memory_gb: float | None
```

The Docker engine may not always expose a resolved content digest in the wire record. When unavailable, the Campaign must already use a digest-pinned image reference and the normalizer records that declared digest with an explicit source indicator.

### `NormalizedTrace`

```python
class NormalizedTrace(ProtocolModel):
    trace_id: str
    agent_role: Literal["subject"]
    task_hash: Digest
    ok: bool
    model_id: str
    harness_id: str
    harness_version: str
    use_bundled_skill: bool
    skill_root_digests: list[Digest]
    runtime: NormalizedRuntime
    tools: list[NormalizedTool]
    rewards: list[NormalizedReward]
    metrics: dict[str, float | None]
    usage: NormalizedUsage | None
    num_turns: int
    last_reply: str | None
    errors: list[NormalizedExecutionError]
    raw_trace_digest: Digest
```

`last_reply` is local/private evidence and remains governed by the DataPolicy. It must not be included in future public projections by default.

### `NormalizedEpisode`

```python
class NormalizedEpisode(ProtocolModel):
    episode_id: str
    env_id: str
    task_hash: Digest
    task_position: int
    ok: bool
    traces: list[NormalizedTrace]
    errors: list[NormalizedExecutionError]
    raw_episode_digest: Digest
```

### `VariantExecutionResult`

```python
class VariantExecutionResult(ProtocolModel):
    variant: VariantName
    experiment_manifest_digest: Digest
    resolved_verifiers_config: ArtifactRef
    raw_traces: ArtifactRef
    eval_log: ArtifactRef
    normalized_episodes: ArtifactRef
    child_outcome: ChildProcessOutcome
    episodes: list[NormalizedEpisode]
```

### `RealExecutionResult`

```python
class RealExecutionResult(ProtocolModel):
    execution_backend: Literal["verifiers"]
    engine_digest: Digest
    verifiers_revision: str
    schedule: VariantSchedule
    baseline: VariantExecutionResult
    candidate: VariantExecutionResult
```

WP6 ends by returning this object to the worker. WP7 consumes it.

---

## 6.7 File: `verifiers/config.py`

### Responsibility

Define the typed local representation of the Verifiers TOML Techtree is allowed to emit.

Do not expose all upstream Verifiers knobs. The compiler is an allow-list boundary.

### Models

```python
class EvalClientToml(BaseModel):
    type: Literal["eval"] = "eval"
    api_key_var: str
    base_url: str | None = None
    headers: dict[str, str] = {}


class SamplingToml(BaseModel):
    temperature: float
    max_tokens: int


class HermesHarnessToml(BaseModel):
    id: Literal["hermes-agent"]
    version: str
    use_bundled_skill: Literal[False]
    skills: list[str]


class DockerRuntimeToml(BaseModel):
    type: Literal["docker"]
    image: str
    cpu: float | None
    memory: float | None


class SubjectAgentToml(BaseModel):
    harness: HermesHarnessToml
    runtime: DockerRuntimeToml
    max_turns: int | None
    max_input_tokens: int | None
    max_output_tokens: int | None
    max_total_tokens: int | None


class TasksetToml(BaseModel):
    id: str
    # Only taskset fields explicitly present on the pinned reference Taskset


class EnvToml(BaseModel):
    taskset: TasksetToml
    subject: SubjectAgentToml
    max_concurrent_agents: int = 1


class EvalToml(BaseModel):
    model: str
    client: EvalClientToml
    sampling: SamplingToml
    env: EnvToml
    num_tasks: int
    num_rollouts: Literal[1]
    shuffle: Literal[False]
    max_concurrent: int
    rich: Literal[False]
    push: Literal[False]
    output_dir: str
```

### Validation

Reject:

```text
push=true
rich=true
shuffle=true
num_rollouts != 1
use_bundled_skill=true
disabled_tools field
non-Docker runtime
non-Hermes harness
non-digest-pinned production image, once release mode is enabled
unknown client headers
credential values rather than env-var names
skill paths outside the run-owned input tree
```

---

## 6.8 File: `verifiers/compiler.py`

### `compile_variant_config`

```python
def compile_variant_config(
    *,
    campaign: CampaignSpec,
    experiment: ExperimentManifest,
    run_paths: RunPaths,
    variant: VariantName,
    variant_max_concurrent: int,
) -> EvalToml:
    """
    Translate one resolved Techtree experiment into the strict Verifiers config.

    Verify before compiling:
      experiment.campaign_spec_digest matches campaign digest
      data_policy_digest matches
      evaluation_backend matches
      membership and task count match
      subject role exists
      harness id/version match allowed reference values
      variant skill list matches the manifest
      every skill path is run-owned
    """
```

### `write_variant_config`

```python
def write_variant_config(
    config: EvalToml,
    destination: Path,
) -> ArtifactRef:
    """Write deterministic TOML atomically and return its artifact reference."""
```

### `compile_plans`

```python
def compile_plans(
    *,
    campaign: CampaignSpec,
    baseline: ExperimentManifest,
    candidate: ExperimentManifest,
    run_paths: RunPaths,
) -> tuple[VariantExecutionPlan, VariantExecutionPlan]:
    """Build both plans and divide Campaign concurrency without exceeding it."""
```

### Concurrency division

For `parallel_variants`:

```text
total maximum = campaign.execution.max_concurrent
baseline maximum = floor(total / 2), minimum 1
candidate maximum = total - baseline maximum, minimum 1
```

Require total at least 2 for parallel schedule.

For sequential schedule, each variant may use the full declared maximum.

### Model client mapping

Initial release supports a Prime profile:

```text
provider = prime
client.type = eval
client.api_key_var = PRIME_API_KEY
base_url omitted so pinned Verifiers resolves Prime configuration
```

Custom provider support is deferred unless an explicit protocol/client pin is added.

---

## 6.9 File: `verifiers/credentials.py`

### Responsibility

Check that the declared model endpoint can authenticate without ever returning, logging, or persisting a secret.

### Models

```python
class CredentialStatus(ProtocolModel):
    provider: str
    credential_env: str
    available: bool
    source: Literal["environment", "prime_config", "missing"]
    detail: str
```

### Functions

```python
def credential_status(model: ModelSpec) -> CredentialStatus:
    """Check env presence or active Prime config without returning the key."""


def require_credentials(model: ModelSpec) -> CredentialStatus:
    """Raise `model_credentials_missing` with safe next actions when absent."""


def scrubbed_child_environment(
    *,
    model: ModelSpec,
    engine: EngineInstallation,
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """
    Build the child environment from a narrow allow-list.

    Include only:
      PATH
      HOME
      TMPDIR
      declared credential variable when present in environment
      Prime configuration variables needed by the pinned client
      explicitly declared proxy variables when policy permits
    """
```

Do not copy the entire host environment.

---

## 6.10 File: `verifiers/child.py`

### `VerifiersChild`

```python
class VerifiersChild:
    def __init__(
        self,
        *,
        variant: VariantName,
        argv: Sequence[str],
        cwd: Path,
        env: Mapping[str, str],
        stdout_path: Path,
        stderr_path: Path,
    ) -> None: ...
```

### Methods

```python
def start(self) -> int:
    """Start in a new process group, record monotonic and wall-clock start."""


def poll(self) -> int | None:
    """Return exit code or None."""


def wait(self, timeout: float | None = None) -> int:
    """Wait and return exit code."""


def terminate(self, grace_seconds: float) -> None:
    """
    Send SIGTERM to the process group, allowing pinned Verifiers to run Docker
    teardown; after grace, send SIGKILL.
    """


def outcome(self) -> ChildProcessOutcome:
    """Return typed outcome after process exit and artifact hashing."""
```

### Invocation

Run the full path to the engine-owned `eval` command:

```text
<engine>/.venv/bin/eval @ <variant-input-config.toml>
```

Do not rely on `PATH` to select `eval`; PI0 found the generic command name must be invoked by full managed-engine path.

### Output handling

- Redirect stdout and stderr to separate run-owned files.
- Never stream raw trace JSON directly to the host agent.
- `eval.log` remains the primary upstream log.
- Raw stdout/stderr are retained for diagnostics and scrubbed before CLI display.

---

## 6.11 File: `verifiers/progress.py`

### Responsibility

Provide robust progress from append-only `traces.jsonl` while a variant is running.

### Functions

```python
def count_complete_jsonl_records(path: Path) -> int:
    """
    Count only complete newline-terminated, valid JSON object records.
    Ignore a temporarily incomplete final line while the child is writing.
    Do not rewrite or repair the source file.
    """


def inspect_progress(
    *,
    variant: VariantName,
    traces_path: Path,
    total: int,
    child_exit_code: int | None,
) -> VariantProgress:
    """Return completed/running/error state without interpreting rewards yet."""


def emit_progress_if_changed(
    *,
    run_store: RunStore,
    run_id: str,
    previous: VariantProgress | None,
    current: VariantProgress,
) -> None:
    """Append one `variant.progress` event only when projected values changed."""
```

### Important rule

Line position is never task position. Progress may count lines, but result pairing later uses task hashes.

---

## 6.12 Engine tool: `normalize_eval_output.py`

This tool runs inside the pinned managed engine and is part of the engine bundle digest.

### Why it belongs in the engine

It imports the exact pinned Verifiers wire models and output reader. It is part of the scientific interpretation boundary.

### Arguments

```text
--output-dir <Verifiers output directory>
--membership <TasksetLock JSON>
--experiment-manifest <ExperimentManifest JSON>
--output <normalized-episodes.jsonl>
```

### Functions

```python
def parse_args() -> argparse.Namespace


def load_membership(path: Path) -> list[str]:
    """Load ordered Techtree task digests and convert for matching as needed."""


def read_wire_episodes(output_dir: Path) -> list[Episode]:
    """Use pinned Verifiers `read_episodes` with wire Trace types."""


def normalize_reward(name: str, reward: object) -> dict[str, object]


def normalize_tool(tool: object) -> dict[str, object]


def normalize_runtime(trace: object, experiment: dict) -> dict[str, object]


def normalize_trace(trace: object, experiment: dict) -> dict[str, object]


def normalize_episode(episode: object, experiment: dict) -> dict[str, object]


def order_by_membership(
    episodes: list[dict[str, object]],
    ordered_task_hashes: list[str],
) -> list[dict[str, object]]:
    """
    Join by normalized task hash.
    Reject missing, duplicate, unexpected, or unhashable task records.
    """


def main() -> int:
    """Write canonical compact JSONL ordered by task membership."""
```

### Normalization exclusions

Do not place in normalized scientific records:

```text
host absolute paths
credential values
temporary directory names not required for provenance
non-deterministic log prefixes
raw Python traceback text unless the episode failed
```

### Raw evidence retention

The normalizer does not replace `traces.jsonl`. Techtree retains both:

```text
raw upstream evidence
normalized protocol projection
```

---

## 6.13 File: `verifiers/outputs.py`

### Functions

```python
def required_output_paths(output_dir: Path) -> dict[str, Path]:
    """Return config.toml, traces.jsonl, and eval.log paths."""


def require_output_files(output_dir: Path) -> dict[str, Path]:
    """Raise when any required file is missing or traces is empty."""


def artifact_for(path: Path, media_type: str) -> ArtifactRef:
    """Hash exact bytes and build an artifact reference."""


def read_normalized_episodes(path: Path) -> list[NormalizedEpisode]:
    """Parse every JSONL record and require one final newline."""


def build_variant_result(
    *,
    plan: VariantExecutionPlan,
    outcome: ChildProcessOutcome,
    engine_runner: EngineRunner,
    taskset_lock_path: Path,
) -> VariantExecutionResult:
    """
    Require outputs, run engine normalizer, parse normalized episodes,
    and build the complete variant result.
    """
```

---

## 6.14 File: `verifiers/verify.py`

### Responsibility

Determine whether a variant execution is complete and scientifically usable before WP7 builds receipts.

### Functions

```python
def verify_variant_execution(
    *,
    result: VariantExecutionResult,
    experiment: ExperimentManifest,
    taskset_lock: TasksetLock,
    primary_reward: str,
) -> list[ExecutionCheck]:
    """
    Return ordered checks and raise only on malformed inputs.
    """
```

Required checks:

```text
child completed without cancellation
required upstream files exist
resolved config parses
resolved config matches compiled experiment
exact episode count
exact ordered task membership after normalization
one subject Trace per episode
all episode and trace IDs unique
all subject role names equal subject
all task hashes normalized and expected
all episodes completed
all Traces completed
primary reward exists on every Trace
reward scores and weights are finite
model ID matches
Hermes harness ID and version match
use_bundled_skill is false
skill digests match the experiment variant
runtime is Docker
runtime image matches Campaign declaration
normalized tool inventory is internally valid
Verifiers version/commit match engine descriptor
```

### Exit-code rule

A zero child exit code is not sufficient for validity. Output checks determine validity.

A non-zero exit code normally fails the variant, but a graceful cancellation exit code maps to cancellation rather than scientific invalidity.

---

## 6.15 File: `runs/variants.py`

### `VariantPair`

```python
@dataclass(frozen=True)
class VariantPair:
    baseline: VariantExecutionPlan
    candidate: VariantExecutionPlan
```

### `VariantScheduler`

```python
class VariantScheduler:
    def __init__(
        self,
        *,
        run_store: RunStore,
        child_registry: ChildRegistry,
        poll_interval_seconds: float = 0.25,
    ) -> None: ...
```

### Methods

```python
def execute_parallel(
    self,
    *,
    run_id: str,
    baseline_child: VerifiersChild,
    candidate_child: VerifiersChild,
    total_tasks: int,
) -> tuple[ChildProcessOutcome, ChildProcessOutcome]:
    """
    Start both children before waiting on either.
    Poll both output files.
    Emit variant progress.
    Honor cancellation.
    If one fails early, terminate the sibling and fail the pair.
    """


def execute_sequential(...) -> tuple[ChildProcessOutcome, ChildProcessOutcome]:
    """Compatibility path for Campaigns that declare sequential execution."""
```

### Parallel start invariant

Both children must be constructed and all input files verified before either starts.

Start timestamps need not be equal, but the second child must be started immediately after the first without waiting for an episode result.

Record start skew in the operational execution record.

---

## 6.16 File: `runs/child_registry.py`

### Responsibility

Track active child processes so cancellation and crash handling can address both variants.

### Class

```python
class ChildRegistry:
    def register(self, run_id: str, child: VerifiersChild) -> None
    def children(self, run_id: str) -> tuple[VerifiersChild, ...]
    def terminate_all(self, run_id: str, grace_seconds: float) -> None
    def unregister(self, run_id: str, variant: VariantName) -> None
```

This is in-process operational state, not durable scientific truth.

Durable child PIDs may be written to:

```text
runs/<run-id>/children.json
```

for diagnostic cleanup after a worker crash.

---

## 6.17 File: `runs/real.py`

### Class: `RealVerifiersExecutor`

```python
class RealVerifiersExecutor:
    def __init__(
        self,
        *,
        engine_registry: EngineRegistry,
        run_store: RunStore,
        taskset_service: TasksetService,
        child_registry: ChildRegistry,
    ) -> None: ...
```

### `execute`

```python
def execute(
    self,
    context: ExecutionContext,
) -> RealExecutionResult:
    """
    Execute the real Campaign variants and return normalized results.
    WP7 owns receipt/report construction.
    """
```

### Required sequence

```text
1. Load staged run request and immutable run inputs.
2. Verify every staged digest.
3. Verify DataPolicy acknowledgement.
4. Resolve and verify the managed engine.
5. Require model credentials.
6. Reuse or perform local taskset validation through TasksetService.
7. Load TasksetLock and require Campaign commitment equality.
8. Load baseline and candidate ExperimentManifests.
9. Compile strict Verifiers configs.
10. Run `eval @ config.toml --dry-run` separately for both variants.
11. Verify resolved dry-run configs.
12. Transition to running_variants for parallel Campaigns.
13. Start both live eval children.
14. Poll progress and cancellation.
15. Require both children to end.
16. Normalize both output directories with engine-owned tooling.
17. Verify both VariantExecutionResults.
18. Return RealExecutionResult.
```

### Dry-run directories

Keep dry-run artifacts separate from live output:

```text
verifiers/<variant>/dry-run/
verifiers/<variant>/run/
```

This avoids ambiguous overwriting and lets reviewers inspect exactly what was validated before execution.

### Failure policy

Fail the run when:

```text
engine verification fails
credentials missing
Docker unavailable
config dry-run fails
child cannot start
one variant fails and sibling is terminated
output files missing
normalization fails
membership incomplete
primary reward missing
actual subject config differs
```

Do not produce an UpliftReport from one successful variant and one failed variant. WP7 may later support an explicit partial report, but not in this push.

---

## 6.18 Doctor execution checks

### File: `doctor/execution_checks.py`

Functions:

```python
def check_docker_platform() -> DoctorCheck:
    """Confirm Docker daemon and linux/arm64 or linux/amd64 subject support."""


def check_engine_eval(engine_registry: EngineRegistry) -> DoctorCheck:
    """Confirm full-path `eval` executable and exact Verifiers revision."""


def check_prime_auth(model: ModelSpec) -> DoctorCheck:
    """Confirm the declared Prime credential source is available without reading it."""


def check_subject_image(runtime: RuntimeSpec) -> DoctorCheck:
    """Inspect or pull the declared image as an explicit setup operation."""


def check_live_campaign(campaign: CampaignSpec) -> DoctorCheck:
    """Reject development placeholders before a real run."""
```

`techtree doctor --for-evaluation` makes these blocking.

Ordinary `techtree doctor` may report them as warnings when the user is only browsing.

---

## 6.19 Run filesystem additions

```text
runs/<run-id>/
├── inputs/
│   ├── campaign.json
│   ├── data-policy.json
│   ├── taskset-lock.json
│   ├── taskset-validation-receipt.json
│   ├── baseline-experiment.json
│   ├── candidate-experiment.json
│   └── skills/
│       ├── baseline/              # absent for insertion baseline
│       └── candidate/
│
├── verifiers/
│   ├── baseline/
│   │   ├── input.toml
│   │   ├── dry-run/
│   │   │   ├── config.toml
│   │   │   └── command.log
│   │   └── run/
│   │       ├── config.toml
│   │       ├── traces.jsonl
│   │       ├── eval.log
│   │       ├── stdout.log
│   │       ├── stderr.log
│   │       └── normalized-episodes.jsonl
│   └── candidate/
│       └── ... same structure ...
│
└── execution/
    ├── real-execution-result.json
    └── children.json
```

Raw Verifiers artifacts are mode `0600` and remain local.

---

## 6.20 WP6 CLI behavior

No new public command is required if existing `climb start` chooses executor from the RunRequest.

Add or extend:

```bash
techtree run status <run-id>
techtree run status <run-id> --watch
techtree run logs <run-id> --variant baseline
echtree run logs <run-id> --variant candidate
```

Correct the typo in implementation; the command is `techtree`, not `echtree`.

### Human progress

```text
Procedure Transfer v1
Run run_...

                    Baseline            Skill candidate
Episodes            7 / 20              8 / 20
State               running             running
Current score       provisional only    provisional only

The score remains provisional until every task completes and Techtree verifies
that the observed configurations match.
```

Do not display a final uplift delta while either variant is incomplete.

### Machine progress

`run status --json` exposes `variant_progress` and no ANSI text.

---

## 6.21 WP6 tests

### Unit tests

```text
strict config allow-list
Prime client mapping
push=false invariant
rich=false invariant
no disabled_tools
skill path containment
parallel concurrency division
credential detection without secret return
JSONL complete-line progress
task-hash normalization
output completeness
variant failure behavior
```

### Engine contract tests

Against the pinned engine:

```text
ProcedureTransferEnv resolves.
subject role exists.
Hermes harness config accepts version/use_bundled_skill/skills.
Dry-run produces expected resolved config.
Eval output parser reads Episode rows.
Normalizer orders by task membership.
```

### Mock model integration test

Run a local OpenAI-compatible deterministic mock endpoint that returns controlled responses.

It must exercise:

```text
Verifiers interception
Hermes ACP harness startup
Docker runtime
baseline and candidate skill staging
Episodes and Traces
reward scoring
parallel child orchestration
output normalization
```

The mock endpoint may use a deterministic script rather than an actual model, but the full Verifiers/Hermes/Docker path must be real.

### Live credential-gated E2E

```python
@pytest.mark.live_model
```

Environment requirements:

```text
TECHTREE_E2E_MODEL_ID
Prime authentication
Docker
```

The test runs a small task count, for example 3–5 tasks, to control cost.

It must not run in ordinary CI.

---

## 6.22 WP6 acceptance criteria

- [ ] Exact pinned engine is used.
- [ ] Full-path `eval` executable is invoked.
- [ ] `push=false` is resolved in both configs.
- [ ] `rich=false` is resolved in both configs.
- [ ] Baseline has no tested Skill for insertion Campaigns.
- [ ] Candidate has exactly the snapshotted tested Skill.
- [ ] Hermes bundled Skills are disabled in both variants.
- [ ] Subject role is recorded as `subject` by Verifiers.
- [ ] Both variants run in clean Docker runtimes.
- [ ] Both children start before either is awaited in parallel mode.
- [ ] Campaign-wide concurrency is not exceeded.
- [ ] Cancellation terminates both process groups and permits Docker cleanup.
- [ ] Raw `traces.jsonl` is retained for each variant.
- [ ] Normalized records are ordered by task membership, not completion order.
- [ ] Every expected task has exactly one episode and one subject Trace.
- [ ] Every subject Trace has the declared primary reward.
- [ ] Actual model, harness, Skill set, runtime, and tools are recorded.
- [ ] Missing or errored episodes fail the real execution.
- [ ] No Relay dependency exists.
- [ ] No website dependency exists.
- [ ] WP6 returns `RealExecutionResult`; it does not invent final uplift itself.


---

# 7. Work Package 7 — Real receipts, controlled comparison, local proof, and presentation

## 7.1 Objective

Consume `RealExecutionResult` from WP6 and produce the first real Techtree scientific result:

```text
signed EpisodeReceipts
receipt-set commitments
observed invariant comparison
paired reward aggregation
signed UpliftReport
local proof bundle
human and agent presentation payloads
sanitized Skill-improvement context
pairwise Skill-replacement Campaign seam
```

The output is local. It is not uploaded by WP7 or WP8.

## 7.2 Canonical naming decision

The canonical scientific artifact remains:

```text
UpliftReport
```

Human-facing copy may say:

```text
Uplift receipt
```

when explaining that the report is a content-addressed, locally signed receipt of the comparison. Do not introduce a second protocol object with overlapping truth.

## 7.3 WP7 non-goals

Do not implement:

```text
public proof publication
server-side verification
leaderboard submission
independent reproduction
Prime Lab attestation
ReleaseDecision
SkillOpt training loop
automatic multi-step optimization
NeMo Relay
```

The one-turn host-agent improvement workflow is enabled by an exported context and pairwise Campaign derivation; the actual reasoning turn belongs to WP9+.

---

## 7.4 Required file additions

```text
src/techtree/
├── identity/
│   ├── __init__.py
│   ├── models.py
│   ├── store.py
│   └── service.py
│
├── receipts/
│   ├── __init__.py
│   ├── episode.py
│   ├── set.py
│   ├── observed.py
│   ├── compare.py
│   ├── uplift.py
│   ├── bundle.py
│   └── verify.py
│
├── presentation/
│   ├── __init__.py
│   ├── models.py
│   ├── build.py
│   ├── rich.py
│   ├── compact.py
│   └── sanitize.py
│
├── uplift/
│   ├── __init__.py
│   ├── derive.py
│   ├── context.py
│   └── service.py
│
└── cli/commands/
    ├── proof.py
    └── uplift.py

tests/
├── unit/
│   ├── test_identity_store.py
│   ├── test_episode_receipt_builder.py
│   ├── test_receipt_set.py
│   ├── test_observed_comparison.py
│   ├── test_uplift_aggregation.py
│   ├── test_local_bundle_verify.py
│   ├── test_presentation_build.py
│   ├── test_presentation_sanitize.py
│   ├── test_improvement_context.py
│   └── test_skill_replacement_derivation.py
│
├── integration/
│   ├── test_real_result_to_report.py
│   ├── test_local_sign_and_verify.py
│   ├── test_run_result_rich.py
│   ├── test_run_result_compact.py
│   └── test_replacement_run_prepare.py
│
└── golden/
    ├── real-episode-receipt.json
    ├── real-uplift-report.json
    ├── presentation-payload.json
    └── improvement-context.json
```

Protocol goldens should use deterministic fixture data, not live timestamps or real provider output.

---

## 7.5 Local executor identity

### Purpose

Bind local receipts and reports to one participant-controlled key so later tampering is detectable and the artifact can truthfully be called participant-attested.

### Storage

```text
~/.techtree/identity/
├── executor-private-key.bin       mode 0600
└── executor-public.json           mode 0644 or 0600
```

The private key file contains raw or a clearly versioned encoded Ed25519 private key. It must never be included in a proof bundle.

### `identity/models.py`

```python
class ExecutorIdentity(ProtocolModel):
    kind: Literal["local_ed25519"]
    key_id: str
    algorithm: Literal["ed25519"]
    public_key: str
    created_at: datetime
```

`created_at` is operational identity metadata, not part of scientific comparison.

### `identity/store.py`

```python
class IdentityStore:
    def __init__(self, paths: TechtreePaths) -> None: ...

    def exists(self) -> bool:
        """Return whether both private and public identity files exist."""

    def create(self) -> ExecutorIdentity:
        """
        Generate Ed25519 material using the committed crypto primitives,
        create files exclusively, fsync, and return public identity.
        """

    def load_public(self) -> ExecutorIdentity:
        """Load and validate public identity."""

    def load_private(self) -> Ed25519PrivateKey:
        """Load private material without logging or returning serialized bytes."""

    def verify_pair(self) -> bool:
        """Sign and verify a fixed domain-separated challenge in memory."""
```

### `identity/service.py`

```python
class IdentityService:
    def ensure(self) -> ExecutorIdentity:
        """Return existing valid identity or create one after explicit setup."""

    def sign_object(self, value: ProtocolModel) -> ObjectEnvelope:
        """Canonicalize, digest, and sign the object digest."""

    def verify_envelope(self, envelope: ObjectEnvelope) -> VerificationResult:
        """Verify payload digest and signature against the embedded public identity."""
```

### Setup behavior

`techtree setup` may create the identity after printing:

```text
Techtree will create a local signing key used only to detect changes to your
local receipts. The key is not uploaded in this release.
```

Machine setup requires an explicit install/setup approval already owned by WP9; it must not silently create keys during plugin import.

---

## 7.6 EpisodeReceipt construction

### File: `receipts/episode.py`

### `build_episode_receipt`

```python
def build_episode_receipt(
    *,
    run_request: RunRequest,
    variant: VariantName,
    experiment: ExperimentManifest,
    episode: NormalizedEpisode,
    raw_artifacts: VariantExecutionResult,
    evaluation_backend: EvaluationBackend,
) -> EpisodeReceipt:
    """
    Construct one immutable Techtree receipt from one normalized Verifiers Episode.
    """
```

### Required lineage

Copy and verify:

```text
run_id
variant
campaign_spec_digest
program_ref, when present
public_context, when present
outcome_contract_digest, when present
data_policy_digest
experiment_manifest_digest
evaluation_backend
task hash and position
subject runtime
```

### Named traces

Each receipt contains:

```json
{
  "named_traces": {
    "subject": [
      {
        "trace_id": "...",
        "trace_digest": "sha256:...",
        "task_hash": "sha256:...",
        "rewards": {"exact_match": 1.0},
        "metrics": {},
        "ok": true
      }
    ]
  }
}
```

Require exactly one `subject` Trace in the reference Campaign.

### Score status

Set:

```text
valid
```

only when:

```text
episode and Trace are ok
primary reward exists
reward is finite
scoring ran
no relevant execution error exists
```

### Evidence status without Relay

Set:

```text
complete
```

when:

```text
raw Verifiers Episode exists
raw Trace digest exists
resolved config exists
raw traces artifact exists
normalized episode exists
subject/runtime/tool configuration is present
all artifact digests verify
Campaign evidence policy says Relay is not required
```

Relay absence must not cause `partial` when the Campaign explicitly says runtime evidence is not required.

### Raw artifact references

The receipt may reference the whole variant artifacts rather than duplicating them per episode. Paths stay local.

---

## 7.7 Receipt-set commitment

The frozen protocol may not yet include a receipt-set object. Use a deterministic local content-addressed manifest rather than embedding dozens of receipt digests directly in the report without structure.

### File: `receipts/set.py`

```python
class ReceiptSetManifest(ProtocolModel):
    schema_version: Literal["techtree.receipt-set.v1alpha1"]
    run_id: str
    variant: VariantName
    experiment_manifest_digest: Digest
    ordered_receipt_digests: list[Digest]
    task_membership_digest: Digest
    receipt_count: int
```

### Functions

```python
def build_receipt_set(
    *,
    run_id: str,
    variant: VariantName,
    experiment_manifest_digest: Digest,
    signed_receipts: Sequence[ObjectEnvelope[EpisodeReceipt]],
    ordered_task_hashes: Sequence[Digest],
) -> ReceiptSetManifest:
    """Order receipts by TasksetLock membership and build the commitment."""


def write_receipt_set(...) -> ArtifactRef:
    """Write canonical JSON and return digest reference."""


def verify_receipt_set(...) -> VerificationResult:
    """Verify order, count, signatures, and task membership."""
```

If adding this protocol model conflicts with the already frozen schema policy, keep it as a versioned local bundle manifest. The semantics and deterministic ordering are still required.

---

## 7.8 Observed scientific configuration

### File: `receipts/observed.py`

### Purpose

Build one normalized observed-configuration fingerprint from actual Trace and resolved-config data, independent of the declared manifest.

### `ObservedSubjectConfiguration`

```python
class ObservedSubjectConfiguration(ProtocolModel):
    model_id: str
    sampling_digest: Digest
    harness_id: str
    harness_version: str
    use_bundled_skill: bool
    skill_root_digests: list[Digest]
    runtime_kind: str
    runtime_image_digest: Digest
    tool_inventory_digest: Digest
    reward_contract_digest: Digest
    verifiers_revision: str
```

### Functions

```python
def observed_from_receipts(
    receipts: Sequence[EpisodeReceipt],
) -> ObservedSubjectConfiguration:
    """
    Require all receipts in one variant to agree on one subject configuration.
    Reject internal drift.
    """


def compare_declared_to_observed(
    experiment: ExperimentManifest,
    observed: ObservedSubjectConfiguration,
) -> list[ComparisonCheck]:
    """Check actual execution against the manifest."""
```

---

## 7.9 Controlled comparison verifier

### File: `receipts/compare.py`

### `compare_real_variants`

```python
def compare_real_variants(
    *,
    campaign: CampaignSpec,
    baseline_manifest: ExperimentManifest,
    candidate_manifest: ExperimentManifest,
    prepared_manifest_comparison: ManifestComparison,
    baseline_receipts: Sequence[EpisodeReceipt],
    candidate_receipts: Sequence[EpisodeReceipt],
    taskset_lock: TasksetLock,
) -> RealComparisonResult:
    """
    Verify declared and observed control and return paired receipt rows.
    """
```

### Declared checks

```text
same Campaign digest
same DataPolicy digest
same optional Program and OutcomeContract references
same taskset lock and membership
same environment
same model
same sampling
same harness ID/version/use_bundled_skill
same subject runtime and image
same execution/scoring/evidence contract
only allowed Skill path differs
```

### Mutation checks

For `skill_insertion`:

```text
baseline skill list empty
candidate skill list length one
```

For `skill_replacement`:

```text
baseline skill list length one
candidate skill list length one
root digests differ
```

### Observed checks

```text
same ordered task hashes
same episode count
same model ID
same effective sampling
same harness ID/version
same bundled-Skill setting
same runtime image
same tool inventory
same reward names and weights
same Verifiers revision
observed Skill digests match each manifest
```

### Schedule check

Record:

```text
parallel_variants
or
baseline_then_candidate
```

For parallel schedule, include start skew and completion window in operational comparison metadata.

### Comparison status

```text
controlled:
    every invariant holds and no declared warning exists

controlled_with_warnings:
    invariants hold, but a non-fatal condition exists, such as provider model
    revision not independently discoverable

invalid:
    any scientific invariant fails
```

Do not downgrade an actual model mismatch to a warning.

---

## 7.10 Reward aggregation

### File: `receipts/uplift.py`

### `pair_task_rewards`

```python
def pair_task_rewards(
    *,
    baseline_receipts: Sequence[EpisodeReceipt],
    candidate_receipts: Sequence[EpisodeReceipt],
    ordered_task_hashes: Sequence[Digest],
    reward_name: str,
) -> list[TaskDelta]:
    """Join by task hash and return rows in TasksetLock order."""
```

### `aggregate_primary_result`

```python
def aggregate_primary_result(
    deltas: Sequence[TaskDelta],
    reward_name: str,
) -> PrimaryUpliftResult:
    """Compute baseline mean, candidate mean, absolute/relative delta, wins/losses/ties."""
```

Rules:

```text
Use reward.score or the Campaign-declared weighted value consistently.
Do not mix definitions across tasks.
Reject non-finite values.
Relative delta is null when baseline mean is zero.
Treat equal values as ties using exact float equality only when rewards are
specified as exact discrete values; otherwise use a Campaign-declared tolerance.
```

### Optional descriptive interval

A deterministic paired bootstrap interval may be included in a presentation payload, using a fixed algorithm/version and seed derived from the report inputs. Do not add it to the frozen report without a schema amendment.

### `decide_uplift`

```python
def decide_uplift(
    *,
    campaign: CampaignSpec,
    comparison: RealComparisonResult,
    primary: PrimaryUpliftResult,
) -> UpliftDecision:
    """Apply only the Campaign's scientific acceptance rules."""
```

Decision semantics:

```text
accepted:
    comparison valid
    candidate above baseline if required
    minimum absolute delta met

rejected:
    comparison valid but acceptance threshold not met

inconclusive:
    comparison valid but predeclared sufficiency rule cannot decide

invalid:
    comparison invalid or score invalid
```

This is not a deployment ReleaseDecision.

### `build_uplift_report`

```python
def build_uplift_report(
    *,
    run_request: RunRequest,
    campaign: CampaignSpec,
    taskset_validation_receipt_digest: Digest,
    baseline_manifest: ExperimentManifest,
    candidate_manifest: ExperimentManifest,
    baseline_receipt_set: ReceiptSetManifest,
    candidate_receipt_set: ReceiptSetManifest,
    comparison: RealComparisonResult,
    task_deltas: Sequence[TaskDelta],
    primary: PrimaryUpliftResult,
) -> UpliftReport:
    """Construct the canonical real local report."""
```

Required statuses for a successful local result:

```text
execution: completed
score: valid
evidence: complete
comparison: controlled or controlled_with_warnings
publication: not_requested
decision: accepted/rejected/inconclusive
proof_grade: P1
publication_eligible: false in this push
```

`publication_eligible` is false because upload/publication is deliberately absent, not because the scientific result is fake.

---

## 7.11 Local proof bundle

### File: `receipts/bundle.py`

### Bundle layout

```text
runs/<run-id>/proof/
├── bundle.json
├── executor-public.json
├── campaign.json
├── data-policy.json
├── taskset-lock.json
├── taskset-validation-receipt.json
├── baseline-experiment.json
├── candidate-experiment.json
├── baseline-receipt-set.json
├── candidate-receipt-set.json
├── receipts/
│   ├── baseline/*.json
│   └── candidate/*.json
└── uplift-report.json
```

Raw `traces.jsonl` and private logs remain outside this portable proof bundle by default because the DataPolicy prohibits upload and public release. The bundle references their digests where required.

### `LocalProofBundleManifest`

```python
class LocalProofBundleManifest(ProtocolModel):
    schema_version: Literal["techtree.local-proof-bundle.v1alpha1"]
    run_id: str
    campaign_spec_digest: Digest
    data_policy_digest: Digest
    executor_identity: ExecutorIdentity
    artifacts: list[ArtifactRef]
    root_report_digest: Digest
```

### Functions

```python
def build_local_bundle(...) -> LocalProofBundleManifest

def write_local_bundle(...) -> Path

def verify_local_bundle(path: Path) -> VerificationResult
```

### Verification order

```text
1. Validate bundle manifest.
2. Verify every artifact digest.
3. Verify Campaign and policy linkage.
4. Verify TasksetLock and publisher/local validation receipt linkage.
5. Verify every EpisodeReceipt envelope signature.
6. Verify receipt sets.
7. Verify UpliftReport envelope signature.
8. Recompute paired aggregate from receipts.
9. Require recomputed result equals report.
10. Require report remains publication not_requested and publication_eligible false.
```

---

## 7.12 File: `receipts/verify.py`

### Public service

```python
class LocalProofVerifier:
    def verify_report(self, path: Path) -> VerificationResult: ...
    def verify_bundle(self, path: Path) -> VerificationResult: ...
    def explain(self, result: VerificationResult) -> list[VerificationMessage]: ...
```

### CLI

```bash
techtree proof verify ~/.techtree/runs/<run-id>/proof
```

Machine mode returns every failed check with stable codes.

Human mode must clearly distinguish:

```text
cryptographic/integrity verification
scientific comparison validity
participant attestation
lack of independent reproduction
lack of public publication
```

---

## 7.13 Presentation models

The exact contents of the founder’s `rich-terminal-output` Skill were not supplied with this request. WP7 therefore defines the structured input contract it can consume; it must not assume the Skill’s internal prompt or formatting implementation.

### File: `presentation/models.py`

```python
class ScoreBar(ProtocolModel):
    label: str
    value: float
    maximum: float
    display: str


class TaskResultRow(ProtocolModel):
    position: int
    task_label: str
    baseline_score: float
    candidate_score: float
    delta: float
    outcome: Literal["win", "loss", "tie"]


class SkillSummary(ProtocolModel):
    label: str
    root_digest: Digest | None
    file_count: int
    total_bytes: int


class PresentationCaveat(ProtocolModel):
    code: str
    severity: Literal["info", "warning", "error"]
    text: str


class UpliftPresentationPayload(ProtocolModel):
    schema_version: Literal["techtree.presentation.uplift.v1"]
    run_id: str
    campaign_title: str
    comparison_label: str
    baseline_skill: SkillSummary
    candidate_skill: SkillSummary
    baseline_score: float
    candidate_score: float
    absolute_delta: float
    relative_delta: float | None
    wins: int
    losses: int
    ties: int
    task_rows: list[TaskResultRow]
    baseline_tokens: int | None
    candidate_tokens: int | None
    baseline_seconds: float | None
    candidate_seconds: float | None
    decision: str
    proof_grade: str
    verification_status: str
    caveats: list[PresentationCaveat]
    next_actions: list[NextAction]
```

No hidden answer or secret may enter this payload.

---

## 7.14 Presentation builder

### File: `presentation/build.py`

```python
def build_uplift_presentation(
    *,
    report: UpliftReport,
    baseline_receipts: Sequence[EpisodeReceipt],
    candidate_receipts: Sequence[EpisodeReceipt],
    campaign_title: str,
    baseline_skill: SkillArtifact | None,
    candidate_skill: SkillArtifact,
    verification: VerificationResult,
) -> UpliftPresentationPayload:
    """Build a channel-neutral presentation payload."""
```

### Comparison labels

For insertion:

```text
No tested Skill → Skill v1
```

For replacement:

```text
Skill v1 → Skill v2
```

### Next actions

A successful first run should include:

```text
inspect failed tasks locally
ask the host agent to propose one Skill revision
prepare a Skill v1 → Skill v2 comparison
verify the local proof bundle
```

A rejected candidate should not be framed as failure of Techtree. It is useful evidence that the intervention did not meet the declared threshold.

---

## 7.15 Rich terminal renderer

### File: `presentation/rich.py`

This is the CLI fallback renderer. The WP9 Hermes operator may instead pass the neutral payload to the founder-supplied `rich-terminal-output` Skill.

### Functions

```python
def render_uplift_console(
    payload: UpliftPresentationPayload,
    console: Console,
) -> None:
    """Render an accessible, side-by-side Rich terminal result."""


def render_progress_console(
    status: RunStatus,
    console: Console,
) -> None:
    """Render live baseline/candidate progress without final claims."""
```

### Required visual hierarchy

```text
Header:
    Campaign title
    comparison label
    verified/local attestation badge

Primary result:
    side-by-side score bars
    large absolute delta
    accepted/rejected/inconclusive

Task outcomes:
    wins / losses / ties
    compact per-task table
    default show regressions and changed outcomes first

Efficiency:
    tokens
    time
    model calls when available

What changed:
    baseline Skill digest
    candidate Skill digest
    statement that all other declared fields remained fixed

Caveats:
    local participant attestation
    no independent reproduction
    no server upload
    no Relay requirement

Next:
    improve the Skill
    verify bundle
```

### Color and accessibility

- Do not use color as the only carrier of meaning.
- Use text labels `WIN`, `LOSS`, `TIE`.
- Respect `NO_COLOR` and `--no-color`.
- Avoid animated output when stdout is not a TTY.
- Never emit ANSI in JSON or gateway mode.

---

## 7.16 Compact/gateway renderer

### File: `presentation/compact.py`

```python
def render_uplift_markdown(
    payload: UpliftPresentationPayload,
    *,
    maximum_task_rows: int = 5,
) -> str:
    """Return compact Markdown suitable for a phone or gateway message."""
```

Example:

```text
**Skill improved the score: 25% → 85% (+60 points)**

- Wins: 13
- Losses: 1
- Ties: 6
- Comparison: controlled
- Proof: local P1, signature verified
- Raw episodes: retained locally; not uploaded

Largest regression: task branch-code-007, 1 → 0.

Next: I can inspect the local failures and propose one revision to the Skill.
```

Do not dump a 20-row table into a phone message.

---

## 7.17 Sanitization

### File: `presentation/sanitize.py`

```python
def sanitize_label(value: str, maximum: int = 120) -> str

def sanitize_error_summary(error: NormalizedExecutionError) -> str

def ensure_no_secret_patterns(value: str) -> None

def ensure_no_hidden_task_material(payload: UpliftPresentationPayload) -> None
```

The presentation may include:

```text
task public name or ordinal
public prompt summary when policy allows
agent's final answer when local policy allows
score and delta
```

It may not include:

```text
hidden expected answer
private grader source
provider key
authorization header
absolute private path
raw traceback containing environment values
```

---

## 7.18 Improvement context

### File: `uplift/context.py`

The host agent needs enough evidence to improve the Skill without receiving hidden verifier material.

### `ImprovementExample`

```python
class ImprovementExample(ProtocolModel):
    task_hash: Digest
    task_label: str
    public_prompt: str | None
    subject_reply: str | None
    reward: float
    outcome: Literal[
        "stable_success",
        "stable_failure",
        "improved",
        "regressed",
    ]
    public_metrics: dict[str, float | None]
    error_summary: str | None
```

### `SkillImprovementContext`

```python
class SkillImprovementContext(ProtocolModel):
    schema_version: Literal["techtree.skill-improvement-context.v1"]
    source_run_id: str
    campaign_spec_digest: Digest
    parent_skill_digest: Digest
    data_policy_digest: Digest
    objective: str
    current_result: PrimaryUpliftResult
    examples: list[ImprovementExample]
    constraints: list[str]
    prohibited_material: list[str]
```

### `build_improvement_context`

```python
def build_improvement_context(
    *,
    report: UpliftReport,
    candidate_receipts: Sequence[EpisodeReceipt],
    baseline_receipts: Sequence[EpisodeReceipt],
    campaign: CampaignSpec,
    parent_skill: SkillArtifact,
    task_public_projection: TaskPublicProjectionProvider,
) -> SkillImprovementContext:
    """
    Prefer failures, regressions, and boundary cases.
    Exclude expected answers and hidden grader material.
    """
```

### Selection order

```text
regressions first
candidate failures second
largest negative or smallest positive margins, when metrics support it
stable successes only as a small contrast sample
```

### CLI

```bash
techtree uplift context <run-id> --json
```

This command produces local machine-readable context. Human mode gives a short summary and path to the full JSON.

The context is not signed proof and is not uploaded.

---

## 7.19 Deriving a Skill-replacement Campaign

### File: `uplift/derive.py`

### `derive_skill_replacement_campaign`

```python
def derive_skill_replacement_campaign(
    *,
    source_campaign: CampaignSpec,
    source_run: UpliftReport,
    baseline_skill: SkillArtifact,
    candidate_skill: SkillArtifact,
) -> CampaignSpec:
    """
    Derive a new local Campaign that keeps every scientific field fixed except
    the declared Skill replacement.
    """
```

Rules:

```text
purpose remains component_uplift
public_context becomes null unless a separate Climb authorizes replacement
program_ref propagates when present
outcome_contract_digest propagates
taskset, membership, validation receipt, environment, model, sampling,
harness, runtime, scoring, evidence, budgets, and DataPolicy all propagate
mutation.kind becomes skill_replacement
allowed difference remains /agents/subject/harness/skills
baseline Skill is v1
candidate Skill is v2
```

The new Campaign receives a new digest because the mutation contract and Skill variant plan differ.

### `derive_replacement_manifests`

```python
def derive_replacement_manifests(
    *,
    campaign: CampaignSpec,
    baseline_skill: SkillArtifact,
    candidate_skill: SkillArtifact,
) -> tuple[ExperimentManifest, ExperimentManifest, ManifestComparison]:
    """Build v1 and v2 manifests and require a controlled replacement."""
```

---

## 7.20 Uplift service

### File: `uplift/service.py`

```python
class UpliftService:
    def __init__(
        self,
        *,
        catalog: CatalogService,
        skill_service: SkillPreparationService,
        draft_store: DraftStore,
        run_service: RunService,
    ) -> None: ...
```

### Methods

```python
def improvement_context(self, run_id: str) -> SkillImprovementContext:
    """Build sanitized local context from a completed real run."""


def prepare_replacement(
    self,
    *,
    source_run_id: str,
    candidate_skill_path: Path,
    candidate_label: str | None,
) -> PreparedDraft:
    """
    Use the source run's candidate Skill as the new baseline, snapshot the new
    candidate, derive a replacement Campaign, and issue confirmation/policy terms.
    """
```

### Safety

- The source run must be real, completed, and locally verified.
- The source candidate Skill must still verify against its run snapshot.
- The new candidate is snapshotted through the same scanner/archive policy.
- The new candidate root digest must differ.
- The DataPolicy must be shown and accepted again because a new run is being authorized.
- No hidden task material is copied into the Skill automatically.

### CLI reservation

```bash
techtree uplift prepare \
  --from-run <run-id> \
  --candidate-skill <path>

techtree uplift start <draft-id> \
  --confirmation-token <token> \
  --accept-data-policy sha256:...
```

WP9 may expose these through Hermes tools.

---

## 7.21 CLI result surface

### `techtree run result`

Options:

```text
--json
--format rich|compact|path
--show-tasks all|changed|regressions|none
--verify / --no-verify
```

Defaults:

```text
TTY human: rich, changed tasks, verify
non-TTY human: compact, changed tasks, verify
JSON: typed CliEnvelope containing report and presentation payload
```

### `techtree proof verify`

Accept:

```text
run ID
proof bundle directory
uplift-report envelope path
```

### `techtree uplift context`

Returns the sanitized improvement context.

### `techtree uplift prepare/start`

Creates the Skill v1 versus Skill v2 run.

No command uploads anything.

---

## 7.22 WP7 tests

### Receipt tests

```text
one receipt per expected task
named subject Trace
reward fidelity
DataPolicy propagation
Campaign lineage
runtime and tool inventory
raw artifact digest links
no Relay field required
```

### Signing tests

```text
identity creation is exclusive
mode 0600
public/private pair verifies
receipt mutation breaks verification
report mutation breaks verification
wrong key fails
private key never enters bundle
```

### Comparison tests

```text
insertion accepted
replacement accepted
model mismatch invalid
sampling mismatch invalid
harness version mismatch invalid
runtime image mismatch invalid
tool inventory mismatch invalid
reward weight mismatch invalid
missing task invalid
duplicate task invalid
skill digest mismatch invalid
parallel schedule recorded
```

### Aggregation tests

```text
zero baseline relative delta null
wins/losses/ties
finite validation
Campaign threshold
rejected candidate still produces valid report
```

### Presentation tests

```text
no ANSI in compact or JSON
NO_COLOR respected
Rich output contains textual WIN/LOSS/TIE
phone output bounded
no hidden answer
no secret
controlled comparison caveat
local P1 explanation
```

### Improvement tests

```text
context prioritizes regressions/failures
hidden answer omitted
source Skill digest pinned
replacement Campaign keeps all non-Skill fields
new Skill digest required
policy acknowledgement required again
```

---

## 7.23 WP7 acceptance criteria

- [ ] Every real Episode becomes a typed EpisodeReceipt.
- [ ] Every receipt retains Campaign, DataPolicy, evaluation backend, and subject runtime lineage.
- [ ] Receipts are ordered and committed through receipt-set manifests.
- [ ] Actual subject configuration is internally consistent within each variant.
- [ ] Declared-to-observed checks pass.
- [ ] Baseline/candidate task pairing uses normalized task hashes.
- [ ] Only the declared Skill path differs.
- [ ] Skill insertion works.
- [ ] Skill replacement works.
- [ ] Real rewards are aggregated without rescoring.
- [ ] Uplift decision applies Campaign rules only.
- [ ] Local executor identity is created safely.
- [ ] Receipts and report are signed and locally verifiable.
- [ ] P1 is described as local participant attestation, not independent proof.
- [ ] Publication remains not_requested and no upload occurs.
- [ ] Rich terminal renderer vividly shows the result.
- [ ] Compact Markdown renderer works for phone/gateway channels.
- [ ] Presentation payload is channel-neutral and free of hidden answers/secrets.
- [ ] Sanitized improvement context is available.
- [ ] A replacement draft can compare Skill v1 against Skill v2.
- [ ] No Relay dependency exists.


---

# 8. Work Package 8 — Read-only Ash/Phoenix web surface and release bootstrap registry

## 8.1 Objective

WP8 creates the first public `techtree.sh` surface without making the website part of scientific execution.

The website has four jobs:

```text
1. Explain what Techtree Climb does in a compact academic style.
2. Give humans and host agents an authoritative installation/bootstrap path.
3. Publish the immutable public Climb/Campaign catalog and its referenced objects.
4. Explain local proof status and how to verify a result on the participant's machine.
```

It does not:

```text
execute evaluations
accept candidate Skills
accept receipts or reports
store raw Episodes or Traces
authenticate users
run a leaderboard
sign participant receipts
upgrade a local proof grade
expose private programs
```

The first public web release is therefore a **read-only catalog and bootstrap registry**, not a receipt-ingestion control plane.

That boundary is intentional. The Campaign kernel is designed to be reused by Climb, Verify, Forge, Uplift, and reproduction, while the public Climb remains a projection over one Campaign. The site must preserve that object split rather than turn the public wrapper back into the scientific root.

---

## 8.2 Repository boundary

WP8 is implemented in the separate repository:

```text
techtree-ash/
```

It may consume a generated catalog artifact from `techtree-python`, but it must not import or reimplement the Python SDK.

Dependency direction:

```text
techtree-python release pipeline
        ↓ exact generated catalog bundle
techtree-ash catalog import
        ↓
techtree.sh read-only pages and API
```

The web application is never imported by the CLI or local worker.

The CLI may fetch public catalog or bootstrap data over HTTPS, but local execution remains functional from a cached or packaged catalog when the website is unavailable.

---

## 8.3 Required public routes

```text
GET /
GET /start
GET /climbs
GET /climbs/:slug
GET /proofs/local
GET /protocol
GET /healthz

GET /api/v1/bootstrap
GET /api/v1/catalog
GET /api/v1/climbs/:slug
GET /api/v1/objects/:digest
```

There are no public mutation routes in WP8.

The router test must prove that the following route families do not exist:

```text
POST /api/v1/submissions
POST /api/v1/artifacts
POST /api/v1/proofs
POST /api/v1/runs
POST /api/v1/login
```

Unknown mutation routes return `404`, not a placeholder success.

---

## 8.4 Public-page behavior

### `/`

The landing page contains:

```text
Techtree Climb
Controlled trials for agent Skills and harnesses.

What changed?
What stayed fixed?
Did the score move?
Can the result be verified locally?
```

Primary actions:

```text
Start locally
Browse Climbs
Read the protocol
```

The page should be academically restrained:

```text
high-contrast text
ample whitespace
small number of type scales
monospaced protocol excerpts
no animated hero
no artificial activity feed
no fabricated participant counts
no claims of independent verification for local P1 results
```

### `/start`

Shows two supported paths.

#### Host-Hermes path

```text
1. Install and enable the pinned Techtree Hermes plugin.
2. Open Hermes in a terminal or connected phone/gateway channel.
3. Ask: “Set up Techtree and run the introductory Climb.”
4. Review the package, data-policy, compute, and model-cost confirmations.
```

The exact install command is rendered from the current `BootstrapManifest`; it is not hard-coded in the LiveView.

#### Direct CLI path

```text
1. Install the pinned Techtree CLI.
2. Run techtree setup.
3. Run techtree climb list.
4. Run the introductory Climb.
```

The page explains that a model-provider credential and Docker are required for the real evaluation.

### `/climbs`

Displays public summaries from the Ash catalog projection:

```text
reference
title
status
purpose
task count
subject harness and version
mutation kind
DataPolicy summary
local compatibility hints
proof grade offered by the Climb
```

No leaderboard is shown in WP8.

### `/climbs/:slug`

Displays the resolved object graph:

```text
Climb metadata
Campaign digest
DataPolicy digest and plain-language summary
Taskset reference and validation receipt digest
model and harness
runtime
mutation contract
execution mode
scoring contract
publication policy
local verification caveat
exact CLI and Hermes next actions
```

The page must distinguish:

```text
ClimbManifest:
    public invitation and policy

CampaignSpec:
    scientific comparison contract
```

### `/proofs/local`

Explains:

```text
A local P1 result is signed by the participant's local executor key.
Techtree can verify local artifact integrity and controlled comparison.
The website did not witness the execution.
No independent reproduction is implied.
```

It includes:

```bash
techtree proof verify <local-proof-bundle>
```

It does not invite upload in WP8.

### `/protocol`

Provides a concise object map:

```text
DataPolicy
CampaignSpec
ClimbManifest
ExperimentManifest
TasksetValidationReceipt
EpisodeReceipt
UpliftReport
LocalProofBundle
```

The page links to JSON Schemas and exact catalog objects.

### `/healthz`

Returns plain or JSON health with:

```text
application status
catalog import status
catalog source revision
current bootstrap channel
```

It must not expose database credentials, environment variables, hostnames, or internal paths.

---

## 8.5 Bootstrap manifest

The website publishes one typed release object at:

```text
GET /api/v1/bootstrap
```

Model:

```elixir
defmodule Techtree.Catalog.BootstrapManifest do
  @moduledoc """
  Typed public release/bootstrap contract consumed by humans, the future
  Hermes plugin, and direct CLI installers.
  """

  use Ash.Resource,
    domain: Techtree.Catalog,
    data_layer: AshPostgres.DataLayer
end
```

Protocol-shaped response:

```json
{
  "schema_version": "techtree.bootstrap.v1alpha1",
  "channel": "development",
  "published_at": "2026-08-13T00:00:00Z",
  "minimums": {
    "hermes_version": "0.19.0",
    "python": "3.12",
    "uv": "0.11.1",
    "docker_required": true
  },
  "cli": {
    "distribution": "techtree",
    "version": "0.1.0",
    "source_revision": "<full-commit>",
    "install_argv": [
      "uv",
      "tool",
      "install",
      "techtree==0.1.0"
    ]
  },
  "hermes_plugin": {
    "plugin_id": "techtree",
    "repository": "regents-labs/techtree-hermes",
    "revision": "<full-40-character-commit>",
    "install_argv": [
      "hermes",
      "plugins",
      "install",
      "regents-labs/techtree-hermes",
      "--ref",
      "<full-40-character-commit>",
      "--enable"
    ],
    "doctor_argv": [
      "hermes",
      "plugins",
      "doctor",
      "techtree",
      "--ci"
    ]
  },
  "introductory_climb": {
    "reference": "procedure-transfer-v1@1",
    "host_prompt": "Set up Techtree and run the introductory Climb."
  }
}
```

### Bootstrap security rules

- All executable instructions are represented as argument arrays.
- The API may also include a human display string, but consumers never execute the display string.
- Plugin revisions are full immutable commits.
- CLI versions are exact versions, not ranges.
- A stable release may additionally include distribution hashes.
- The manifest is served only over HTTPS in production.
- The future plugin must still ask for explicit user approval before installing anything.
- Plugin import or registration must never install packages automatically.

---

## 8.6 Catalog serving contract

### `/api/v1/catalog`

Returns the exact generated `CatalogIndex` bytes from `techtree-python`.

The controller must not decode and re-encode the protocol object before serving it.

Reason:

```text
The exact bytes have a known digest and are already validated by the
Python protocol implementation. Elixir JSON serialization must not create
an alternate scientific representation.
```

### `/api/v1/objects/:digest`

Returns exact bytes for a content-addressed object.

Accepted digest syntax:

```text
sha256:<64 lowercase hexadecimal characters>
```

The controller:

```text
validates syntax
looks up the digest in the imported catalog index
resolves only the stored catalog-relative path
checks the file still hashes to the requested digest
sets content type from catalog metadata
returns exact bytes
```

It must never convert a digest directly into an arbitrary filesystem path.

### `/api/v1/climbs/:slug`

Returns a convenience API projection for selection UX:

```text
ClimbSummary
Compatibility-independent public metadata
DataPolicySummary
links to exact Climb and Campaign objects
```

This convenience projection is not itself a scientific protocol root.

---

## 8.7 Catalog artifact layout

```text
priv/catalog/
├── source.json
├── catalog.json
├── bootstrap.json
├── objects/
│   ├── campaigns/
│   │   └── <digest>.json
│   ├── climbs/
│   │   └── <digest>.json
│   ├── data-policies/
│   │   └── <digest>.json
│   ├── taskset-validations/
│   │   └── <digest>.json
│   └── validation-evidence/
│       └── <digest>.json
└── projections/
    └── climb-summaries.json
```

`source.json` records operational release provenance:

```json
{
  "techtree_python_revision": "<full-commit>",
  "catalog_digest": "sha256:...",
  "generated_at": "...",
  "generator_version": "..."
}
```

`source.json` is not referenced by the Campaign scientific digest graph.

---

## 8.8 Ash data model

Ash is used for searchable public projections and release state.

Exact protocol bytes remain in `priv/catalog` or immutable object storage.

### `CatalogEntry`

```elixir
defmodule Techtree.Catalog.CatalogEntry do
  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.Catalog,
    data_layer: AshPostgres.DataLayer

  postgres do
    table "catalog_entries"
    repo Techtree.Repo
  end
end
```

Attributes:

```text
id: UUID
protocol_digest: string, unique
kind: atom/string
reference: string, nullable
relative_path: string
media_type: string
byte_size: integer
source_revision: string
active: boolean
title: string, nullable
summary: string, nullable
status: string, nullable
projection: map, default empty
inserted_at
updated_at
```

Actions:

```text
read
get_by_digest
get_by_reference
list_active_climbs
upsert_from_import — private code interface only
retire_missing_from_import — private code interface only
```

Policies:

```text
public reads allowed
create/update/destroy denied through public interfaces
import actions allowed only from internal domain code
```

Identities:

```text
unique protocol_digest
unique non-null reference within kind
```

### `CatalogRelease`

Attributes:

```text
id
channel
catalog_digest
source_revision
bootstrap_digest
import_status
imported_at
active
error_summary, nullable
```

Actions:

```text
read
active_release
begin_import — internal
complete_import — internal
fail_import — internal
activate — internal transaction
```

The application exposes only one active release per channel.

### `BootstrapRelease`

Attributes:

```text
id
channel
schema_version
raw_payload
payload_digest
cli_version
plugin_revision
minimum_hermes_version
published_at
active
```

The API serves `raw_payload` exactly after verifying `payload_digest`.

---

## 8.9 Complete `techtree-ash` file skeleton

```text
techtree-ash/
├── .formatter.exs
├── .gitignore
├── LICENSE
├── README.md
├── mix.exs
├── mix.lock
│
├── config/
│   ├── config.exs
│   ├── dev.exs
│   ├── prod.exs
│   ├── runtime.exs
│   └── test.exs
│
├── lib/
│   ├── techtree.ex
│   ├── techtree/
│   │   ├── application.ex
│   │   ├── repo.ex
│   │   ├── release.ex
│   │   └── catalog/
│   │       ├── domain.ex
│   │       ├── catalog_entry.ex
│   │       ├── catalog_release.ex
│   │       ├── bootstrap_release.ex
│   │       ├── bundle.ex
│   │       ├── digest.ex
│   │       ├── importer.ex
│   │       ├── query.ex
│   │       └── verifier.ex
│   │
│   ├── techtree_web.ex
│   └── techtree_web/
│       ├── endpoint.ex
│       ├── router.ex
│       ├── telemetry.ex
│       ├── components/
│       │   ├── core_components.ex
│       │   └── layouts.ex
│       ├── controllers/
│       │   ├── bootstrap_controller.ex
│       │   ├── catalog_controller.ex
│       │   ├── climb_controller.ex
│       │   ├── object_controller.ex
│       │   ├── health_controller.ex
│       │   └── error_json.ex
│       └── live/
│           ├── home_live.ex
│           ├── start_live.ex
│           ├── protocol_live.ex
│           ├── local_proof_live.ex
│           └── climbs_live/
│               ├── index.ex
│               └── show.ex
│
├── priv/
│   ├── catalog/
│   │   └── ... generated catalog files ...
│   ├── repo/
│   │   ├── migrations/
│   │   │   ├── *_create_catalog_entries.exs
│   │   │   ├── *_create_catalog_releases.exs
│   │   │   └── *_create_bootstrap_releases.exs
│   │   └── seeds.exs
│   └── static/
│       ├── assets/
│       ├── favicon.ico
│       └── robots.txt
│
├── assets/
│   ├── css/app.css
│   ├── js/app.js
│   └── vendor/
│
├── lib/mix/tasks/
│   ├── techtree.catalog.import.ex
│   └── techtree.catalog.verify.ex
│
├── scripts/
│   └── sync_catalog.exs
│
└── test/
    ├── support/
    │   ├── conn_case.ex
    │   ├── data_case.ex
    │   └── catalog_fixture.ex
    ├── techtree/catalog/
    │   ├── bundle_test.exs
    │   ├── digest_test.exs
    │   ├── importer_test.exs
    │   ├── query_test.exs
    │   └── verifier_test.exs
    └── techtree_web/
        ├── controllers/
        │   ├── bootstrap_controller_test.exs
        │   ├── catalog_controller_test.exs
        │   ├── object_controller_test.exs
        │   └── health_controller_test.exs
        └── live/
            ├── home_live_test.exs
            ├── start_live_test.exs
            └── climbs_live_test.exs
```

---

## 8.10 File responsibilities and functions

### `mix.exs`

Defines:

```text
Phoenix
Phoenix LiveView
Ash
AshPostgres
Postgrex
Jason
Bandit or Cowboy
Swoosh only when generated app requires it; no mail behavior
```

Aliases:

```elixir
"setup": ["deps.get", "ash.setup", "assets.setup", "assets.build"]
"test": ["ash.setup --quiet", "test"]
"catalog.verify": ["techtree.catalog.verify"]
"catalog.import": ["techtree.catalog.import"]
"check": ["format --check-formatted", "compile --warnings-as-errors", "test"]
```

No authentication, payment, Oban, or object-upload dependency is required in WP8.

### `config/runtime.exs`

Reads:

```text
DATABASE_URL
SECRET_KEY_BASE
PHX_HOST
PORT
TECHTREE_CATALOG_ROOT, optional
TECHTREE_BOOTSTRAP_CHANNEL
```

It must fail clearly in production when required secrets are absent.

It must not read model-provider credentials.

### `lib/techtree/application.ex`

```elixir
def start(_type, _args)
```

Starts:

```text
Techtree.Repo
Phoenix PubSub
TechtreeWeb.Endpoint
```

The catalog importer does not run automatically on every boot.

A release command imports and activates catalog data explicitly.

### `lib/techtree/repo.ex`

Standard `AshPostgres.Repo` / `Ecto.Repo` configuration.

No custom business behavior.

### `lib/techtree/release.ex`

Functions:

```elixir
def migrate do
  # Run migrations in a release.
end

def import_catalog(path \\ nil) do
  # Call Catalog.Importer under a release boot.
end
```

### `catalog/domain.ex`

Declares Ash resources:

```text
CatalogEntry
CatalogRelease
BootstrapRelease
```

Exposes read actions and internal import code interfaces.

### `catalog/digest.ex`

Functions:

```elixir
def valid?("sha256:" <> hex)
def parse!(digest)
def hash_bytes(bytes)
def verify_bytes(bytes, digest)
```

Rules:

```text
lowercase hexadecimal only
exactly 64 characters after prefix
constant-time comparison where practical
```

This module hashes raw bytes only.

It does not implement RFC 8785 canonicalization.

### `catalog/bundle.ex`

Struct:

```elixir
%Bundle{
  root: Path.t(),
  source: map(),
  catalog_bytes: binary(),
  catalog: map(),
  bootstrap_bytes: binary(),
  bootstrap: map()
}
```

Functions:

```elixir
def load!(root)
def object_path(bundle, relative_path)
def read_object!(bundle, digest)
def list_entries(bundle)
def source_revision(bundle)
```

All resolved paths must remain under the bundle root.

### `catalog/verifier.ex`

Functions:

```elixir
def verify_bundle(bundle)
def verify_catalog_index(bundle)
def verify_object_locations(bundle)
def verify_bootstrap(bundle)
def verify_no_dangling_refs(bundle)
```

WP8 verifier responsibilities are intentionally narrow:

```text
raw byte digest
safe relative path
known media type
presence
catalog index shape
bootstrap shape
no dangling catalog location
```

The Python release pipeline remains authoritative for full protocol-semantic graph validation.

### `catalog/importer.ex`

Functions:

```elixir
def import!(root, opts \\ [])
def stage_entries(bundle, release)
def activate_release!(release)
def retire_previous_entries!(release)
def rollback_failed_import!(release, reason)
```

Import algorithm:

```text
1. Load bundle.
2. Verify raw bytes and all paths.
3. Begin a CatalogRelease with status importing.
4. Upsert metadata projection rows in one transaction.
5. Insert exact BootstrapRelease payload.
6. Mark prior active release inactive.
7. Activate new release.
8. Mark import complete.
```

A failed import leaves the prior active release untouched.

### `catalog/query.ex`

Functions:

```elixir
def list_climbs(opts \\ [])
def get_climb_by_slug(slug)
def get_entry_by_digest(digest)
def active_catalog_release()
def active_bootstrap_release()
def health_summary()
```

This is the only module LiveViews/controllers call for catalog reads.

### `controllers/bootstrap_controller.ex`

```elixir
def show(conn, _params)
```

Returns exact `raw_payload` of active BootstrapRelease.

Headers:

```text
content-type: application/json
etag: "<payload-digest>"
cache-control: public, max-age=300
```

Supports `If-None-Match`.

### `controllers/catalog_controller.ex`

```elixir
def index(conn, _params)
```

Returns exact active catalog bytes.

Headers:

```text
etag: catalog digest
cache-control: public, max-age=300
```

### `controllers/object_controller.ex`

```elixir
def show(conn, %{"digest" => digest})
```

- Validate digest.
- Resolve CatalogEntry.
- Read exact bytes from active release's catalog root.
- Reverify digest before sending.
- Return immutable caching headers:

```text
cache-control: public, max-age=31536000, immutable
etag: digest
```

### `controllers/climb_controller.ex`

```elixir
def show(conn, %{"slug" => slug})
```

Returns the `ClimbSummary` projection and exact-object links.

It must not synthesize a new Campaign or Climb protocol object.

### `controllers/health_controller.ex`

```elixir
def show(conn, _params)
```

Returns `200` when application and active catalog are healthy, otherwise `503`.

### LiveViews

Each LiveView implements:

```elixir
def mount(params, session, socket)
def render(assigns)
```

They call `Catalog.Query`, never read files directly.

`ClimbsLive.Show` also builds safe display commands from bootstrap argv arrays using a display-only shell quoting helper.

### `core_components.ex`

Provides a small component set:

```text
protocol_badge
status_badge
digest
command_block
definition_list
comparison_boundary
warning_callout
next_step
```

Components contain presentation only.

### `assets/css/app.css`

Defines:

```text
academic typographic scale
high-contrast light and dark modes
readable code blocks
responsive narrow viewport layout
reduced-motion compliance
print stylesheet for protocol pages
```

No remote font dependency is required.

### Mix tasks

#### `mix techtree.catalog.verify --path PATH`

Loads and verifies without mutating the database.

#### `mix techtree.catalog.import --path PATH`

Imports and activates a verified bundle.

Both return nonzero on any failure.

### `scripts/sync_catalog.exs`

This is a release-engineering helper, not runtime application behavior.

Arguments:

```text
--source PATH
--destination priv/catalog
```

It:

```text
requires an already-generated techtree-python export
copies to a temporary destination
verifies raw bytes
atomically replaces the destination
never invokes scientific generation itself
```

The Python repository owns catalog generation.

---

## 8.11 Website security requirements

- No arbitrary file serving.
- No path parameter besides validated digest and slug.
- Exact-object responses use immutable cache headers.
- Bootstrap/catalog mutable endpoints use short cache plus ETag.
- Set a restrictive Content Security Policy.
- Disallow framing unless explicitly needed.
- Set `X-Content-Type-Options: nosniff`.
- Do not embed credentials in bootstrap payloads.
- Do not expose internal object-store paths.
- Do not execute bootstrap argv on the server.
- Do not add analytics that violate the shipped DataPolicy.
- Do not claim the site witnessed local runs.
- Do not accept raw user Markdown in WP8.
- Render all catalog text as escaped text.

---

## 8.12 WP8 test plan

### Catalog tests

```text
valid bundle imports
byte mutation rejected
catalog index mutation rejected
path traversal rejected
dangling object rejected
digest case mismatch rejected
failed import leaves active release intact
reimport is idempotent
old release retired only after success
```

### API tests

```text
bootstrap exact bytes
catalog exact bytes
object exact bytes
ETag 304 behavior
immutable cache header
invalid digest 400 or 404 by fixed policy
unknown object 404
unknown climb 404
health 503 without active release
no mutation routes
```

### LiveView tests

```text
landing page uses no fabricated statistics
start page renders argv-derived commands
climb list renders DataPolicy summary
climb show links exact object digests
local proof page states participant-attested caveat
narrow phone viewport content remains usable
```

### Release tests

```text
migration release task
catalog import release task
production runtime config failure
source revision displayed
```

---

## 8.13 WP8 acceptance criteria

- [ ] `techtree-ash` is a separate, green repository.
- [ ] Ash resources represent public catalog projections and release state.
- [ ] Exact protocol objects are served byte-for-byte.
- [ ] No receipt, report, Episode, or Skill upload endpoint exists.
- [ ] No authentication system exists.
- [ ] No evaluator or worker exists in Elixir.
- [ ] `/start` renders the pinned plugin and CLI installation path.
- [ ] `/api/v1/bootstrap` returns typed argv arrays and immutable plugin revision.
- [ ] `/api/v1/catalog` serves the generated catalog.
- [ ] `/api/v1/objects/:digest` verifies bytes before serving.
- [ ] Catalog import is transactional and rollback-safe.
- [ ] Content-addressed objects use immutable caching.
- [ ] Public pages explain DataPolicy and P1 limitations honestly.
- [ ] Site works on phone-width screens.
- [ ] No Relay dependency exists.
- [ ] Uploading the UpliftReport remains out of scope.


---

# 9. Required handoff to Work Packages 9 and later

## 9.1 Why the WP9+ target is specified here

WP6–WP8 do not implement the Hermes operator experience, but they must produce the exact stable interfaces it will consume.

The release target after the remainder of the push is:

```text
Human in terminal or phone/gateway channel
        ↓
Host Hermes with pinned Techtree plugin
        ↓ explicit install approval
Techtree CLI and managed engine installed
        ↓
introductory public Climb selected
        ↓
baseline and Skill v1 evaluated concurrently
        ↓
real signed local UpliftReport / “Uplift receipt”
        ↓
Rich terminal or compact phone presentation
        ↓
one host-agent improvement turn using founder-supplied Skill
        ↓
Skill v2 shown as a reviewable diff
        ↓ explicit run approval
Skill v1 and Skill v2 evaluated concurrently
        ↓
second signed local UpliftReport
        ↓
local verification and artifact paths
```

No website upload occurs anywhere in this flow.

---

## 9.2 Recommended post-WP8 package sequence

The user-visible loop should take priority over optional runtime evidence.

Use:

```text
WP9  — Hermes operator plugin, explicit CLI bootstrap, and gateway-safe tools
WP10 — Guided Skill refinement plus rich/compact result experience
WP11 — Cross-repository release hardening and install-from-zero acceptance
WP12+ — Optional NeMo Relay runtime-evidence integration
```

This deliberately moves Relay behind the first complete local product loop.

Reason:

```text
Verifiers already supplies the Episode, named Trace, rewards, metrics,
resolved Agent config, runtime identity, tools, calls, timing, and errors.
Those are sufficient to establish the controlled local Skill comparison.
Relay can later strengthen operational evidence without blocking the first
useful product experience.
```

---

# 10. WP9 compatibility contract — Hermes operator plugin and CLI bootstrap

This section is a handoff contract, not the complete WP9 implementation specification.

## 10.1 Repository

```text
techtree-hermes/
```

The plugin is a standalone, pinned Hermes plugin.

It must remain a thin host-agent adapter over the CLI JSON interface.

It may orchestrate explicit installation and one-shot host-model UX, but it must not:

```text
compile Verifiers configs
launch Docker directly
parse raw Episodes
score tasks
construct receipts
compare manifests
sign scientific artifacts
implement DataPolicy rules separately
```

---

## 10.2 Installation direction

The website's bootstrap manifest pins both the plugin and CLI.

Initial user action:

```bash
hermes plugins install regents-labs/techtree-hermes \
  --ref <full-plugin-commit> \
  --enable
```

Plugin registration must not silently install anything.

After the user asks Hermes to set up Techtree, the plugin runs a bootstrap check.

If the CLI is absent, it returns an explicit installation plan:

```json
{
  "package": "techtree",
  "version": "0.1.0",
  "argv": [
    "uv",
    "tool",
    "install",
    "techtree==0.1.0"
  ],
  "requires_confirmation": true
}
```

Only after explicit user approval may the plugin invoke the exact pinned argv.

The model cannot choose:

```text
package name
package source
version
index URL
extra pip flags
executable path
```

After installation, the plugin verifies:

```bash
techtree --version --json --no-color --no-input
```

and then runs:

```bash
techtree doctor --json --no-color --no-input
```

### Missing `uv`

The plugin does not download and execute a remote installer automatically.

It returns an actionable prerequisite error and installation instructions from the bootstrap manifest.

---

## 10.3 Model-provider authentication

Hermes host authentication and the evaluated subject's Verifiers client authentication are separate concerns.

The first supported release profile is Prime inference:

```text
base URL:
    pinned by the public Campaign/release profile

credential source:
    PRIME_API_KEY environment variable
    or the authenticated Prime CLI configuration supported by the pinned
    Verifiers client
```

The plugin must not assume that because host Hermes can answer, Verifiers can access the same model provider.

Doctor output must distinguish:

```text
Host Hermes model access: ready / unknown
Techtree evaluation model access: ready / missing
```

The plugin never asks the model to paste an API key into chat or a tool argument.

---

## 10.4 Required plugin tools

```text
techtree_bootstrap_check
techtree_bootstrap_install
techtree_system_check
techtree_climbs_list
techtree_climb_inspect
techtree_demo_prepare
techtree_climb_start
techtree_run_status
techtree_run_cancel
techtree_run_result
techtree_proof_verify
techtree_uplift_context
techtree_uplift_prepare
techtree_uplift_start
```

All handlers:

```text
accept typed JSON
invoke Techtree through argv arrays
add --json --no-color --no-input
return the CLI envelope as JSON
never use shell=True
never accept arbitrary executable names
never accept secret values
```

Long work always returns a run ID.

No tool handler waits for the whole benchmark.

---

## 10.5 Introductory demo profile

The bootstrap manifest identifies:

```text
public Climb reference
starter subject Skill v1 digest
starter Skill object URL
expected Skill format
founder-supplied host improvement Skill ID
founder-supplied rich-result Skill ID
```

The starter subject Skill is a content-addressed public artifact.

The plugin or CLI:

```text
downloads exact bytes
verifies digest
materializes into a Techtree-owned cache
passes that path through ordinary Skill preparation
```

The downloaded Skill does not bypass the scanner, archive, draft, DataPolicy, or confirmation path.

---

## 10.6 Operator Skills versus evaluated Skills

There are three distinct concepts:

```text
Subject Skill v1
    Mounted into Docker for the first candidate variant.

Subject Skill v2
    Generated after the first report and mounted into Docker for the
    replacement candidate variant.

Host operator Skills
    Founder-supplied instructions used by the ordinary host Hermes agent to
    explain results and propose a revision.
```

Host operator Skills must never be mounted into the evaluated subject.

Recommended namespaced IDs:

```text
techtree:operator
techtree:rich-terminal-output
techtree:skill-improver
```

The exact contents of the latter two Skills are founder-supplied release inputs and are not invented by implementation workers.

---

# 11. WP10 compatibility contract — rich presentation and one-turn Skill refinement

## 11.1 Deterministic truth versus model-authored explanation

The CLI owns all numeric and scientific truth.

The host Skill may improve communication, but it may not calculate or alter:

```text
scores
deltas
wins/losses/ties
status fields
proof grade
DataPolicy
manifest differences
receipt digests
```

The handoff is:

```text
UpliftReport
        ↓ deterministic
ComparisonPresentation payload
        ├── CLI Rich renderer
        ├── compact Markdown renderer
        └── founder-supplied rich-terminal-output Skill
```

The Skill receives structured facts and a list of forbidden claims.

The CLI-produced output remains the authoritative fallback when the host model is unavailable or produces invalid content.

---

## 11.2 Rich-terminal-output Skill input contract

Because the founder-supplied Skill text is not part of this specification, workers implement only the contract.

Input object:

```json
{
  "schema_version": "techtree.presentation-input.v1alpha1",
  "channel": "terminal",
  "comparison": {
    "baseline_label": "No candidate Skill",
    "candidate_label": "BranchCode Skill v1",
    "baseline_score": 0.22,
    "candidate_score": 0.86,
    "absolute_delta": 0.64,
    "wins": 24,
    "losses": 1,
    "ties": 11,
    "decision": "accepted"
  },
  "integrity": {
    "score_status": "valid",
    "comparison_status": "controlled",
    "evidence_status": "complete",
    "proof_grade": "P1",
    "execution_attestation": "participant"
  },
  "cost": {},
  "timing": {},
  "notable_tasks": [],
  "artifact_paths": {},
  "forbidden_claims": [
    "Do not say this was independently reproduced.",
    "Do not imply that techtree.sh witnessed the execution.",
    "Do not reveal hidden expected answers."
  ]
}
```

Expected output is presentation text only.

It must not contain executable shell commands that were absent from `NextAction`.

The plugin should display the deterministic CLI panel before or alongside any model-authored summary.

---

## 11.3 Terminal experience

The terminal result should make the controlled difference visually obvious:

```text
┌──────────────────────────────────────────────────────────────┐
│ SKILL UPLIFT                                                 │
│ Procedure Transfer v1                                       │
├─────────────────────────────┬────────────────────────────────┤
│ BASELINE                    │ SKILL v1                       │
│ No candidate Skill          │ sha256:...                     │
│ 22%                         │ 86%                            │
├─────────────────────────────┴────────────────────────────────┤
│ +64 percentage points       24 wins · 1 loss · 11 ties      │
│ Decision: ACCEPTED                                          │
└──────────────────────────────────────────────────────────────┘

Controlled:
  model        same
  harness      same
  runtime      same
  taskset      same
  scorer       same
  changed      subject Skill only

Proof:
  score        valid
  comparison   controlled
  evidence     complete
  attestation  local participant P1
```

Colors are optional enhancements.

The same information remains understandable with:

```text
NO_COLOR=1
plain text log capture
screen reader
```

---

## 11.4 Phone/gateway experience

ANSI output is not sent to a phone or generic gateway channel.

Compact response:

```text
Skill v1 improved the score from 22% to 86% (+64 points).
24 tasks improved, 1 regressed, and 11 tied.

The model, Hermes version, runtime, taskset, and scorer were fixed; only the
candidate Skill changed. This is a locally participant-attested P1 result,
not an independent reproduction.

Next: review one proposed Skill revision, then run Skill v1 against Skill v2.
```

The plugin may send the artifact path or proof-bundle filename as a second message when the channel supports attachments or monospace text.

---

## 11.5 One-turn improvement flow

The improvement operation uses:

```text
source Skill v1
sanitized first-run comparison context
founder-supplied techtree:skill-improver instructions
one host-model reasoning/completion turn
```

The sanitized context includes:

```text
score summary
task hashes
pass/fail/regression category
public prompts when policy permits
subject replies
public metrics
runtime errors
cost and timing
source Skill text
```

It excludes:

```text
hidden expected answers
hidden grader material
sealed task content
provider secrets
raw private configuration
unredacted filesystem paths
```

Output schema:

```json
{
  "analysis_summary": "...",
  "change_rationale": ["..."],
  "revised_skill_markdown": "# ...",
  "expected_tradeoffs": ["..."],
  "confidence": "low|medium|high"
}
```

The plugin writes the proposed Skill into a Techtree-owned proposal directory:

```text
~/.techtree/proposals/<proposal-id>/SKILL.md
```

It then invokes the ordinary Skill scanner.

The proposal is not silently accepted.

Before a second evaluation, the user sees:

```text
source Skill digest
proposed Skill digest
line-level diff
scanner findings
estimated second-run episodes and model budget
exact DataPolicy digest
```

The user explicitly approves the second run.

---

## 11.6 Skill v1 versus Skill v2

The second Campaign uses:

```text
mutation kind: skill_replacement
baseline Skill: Skill v1
candidate Skill: Skill v2
```

Everything else remains fixed.

Both variants run concurrently through the same WP6 executor.

The second report communicates:

```text
Did the proposed change beat the already-Skill-enabled baseline?
Did any tasks regress?
Did cost or latency move?
Was the comparison still controlled?
```

The local artifact remains a signed `UpliftReport` envelope.

User-facing copy may call it:

```text
Uplift receipt
```

No separate competing protocol object is introduced merely for the label.

---

# 12. Whole-push end-to-end acceptance scenario

The release is not done merely because unit tests pass.

A clean-machine acceptance run must exercise the user journey.

## 12.1 Preconditions

```text
supported macOS host
Docker Desktop installed and running
Hermes >= pinned minimum
uv installed
Prime account/model access configured for Techtree evaluation
no existing Techtree home, or isolated TECHTREE_HOME
phone gateway optional but configured for gateway test
```

## 12.2 Terminal scenario

1. Install the pinned plugin.
2. Start Hermes.
3. Tell Hermes:

```text
Set up Techtree and run the introductory Climb.
```

4. Hermes shows the exact pinned CLI install operation.
5. User approves installation.
6. Plugin installs and verifies the CLI.
7. Plugin runs Doctor.
8. If evaluation provider auth is missing, it stops with an actionable message.
9. Plugin loads the introductory Climb and DataPolicy.
10. Plugin downloads and verifies the starter Skill v1.
11. Plugin prepares the baseline-versus-Skill draft.
12. User sees:

```text
what will run
what will change
what remains fixed
episode count
budget bound
DataPolicy
```

13. User accepts policy and run.
14. Host Hermes starts the detached run and immediately returns a run ID.
15. The user may keep talking to Hermes while the worker runs.
16. Status shows both variants active and independent progress.
17. Result displays the deterministic Rich comparison.
18. Host Hermes uses the founder-supplied rich-output Skill to explain the result without changing any value.
19. User asks:

```text
Try improving the Skill once.
```

20. Host Hermes obtains sanitized improvement context.
21. Host Hermes uses the founder-supplied improvement Skill for one completion turn.
22. Plugin writes Skill v2 and shows a diff.
23. User approves the second run.
24. Skill v1 and Skill v2 run concurrently.
25. The second Rich result displays.
26. Hermes returns local paths for:

```text
Skill v1
Skill v2
first UpliftReport
second UpliftReport
local proof bundles
```

27. Verification succeeds:

```bash
techtree proof verify <second-bundle>
```

28. Nothing is uploaded to the website.

---

## 12.3 Phone/gateway scenario

Repeat the same operation from a phone-connected Hermes channel.

Requirements:

- Installation and model-cost operations still require explicit confirmation.
- The channel receives no raw ANSI escape codes.
- Long-running work returns a run ID rather than holding the gateway request open.
- Status requests are bounded.
- The result uses compact Markdown.
- Skill diff is truncated safely with an option to inspect in terminal.
- The user can approve or reject the second run from the gateway.
- The final local proof path is returned.

The gateway is a host-operator interface only.

The evaluated Hermes subject still runs cleanly in Docker.

---

# 13. Cross-work-package invariants

The following rules bind WP6, WP7, WP8, and all later integration work.

## 13.1 Scientific truth

```text
Verifiers Task rewards are the sole score truth.
Techtree never re-scores the subject output.
Presentation Skills never alter result values.
```

## 13.2 Agent separation

```text
Host Hermes = operator
Docker Hermes = subject
```

No host conversation, memory, plugin, or operator Skill enters the subject unless explicitly declared in the ExperimentManifest.

## 13.3 Campaign lineage

Every real artifact retains:

```text
campaign_spec_digest
data_policy_digest
evaluation_backend
optional public_context
optional program_ref
optional outcome_contract_digest
```

## 13.4 Skill immutability

Every evaluated Skill comes from a Techtree-owned snapshot.

The subject never mounts a mutable user source directory.

## 13.5 Controlled comparison

First run:

```text
zero candidate Skills
versus
one Skill v1
```

Second run:

```text
Skill v1
versus
Skill v2
```

Only the declared Skill field may differ.

## 13.6 Rights

The exact DataPolicy digest is acknowledged for each draft.

No raw Episode upload occurs.

## 13.7 Installation safety

Plugin registration has no installation side effects.

Package installation requires explicit human approval.

## 13.8 Local proof honesty

A P1 local result means participant-attested local execution.

It does not mean:

```text
website-witnessed
independently reproduced
sealed
Prime-hosted
```

## 13.9 No Relay dependency

No acceptance gate in this push depends on Relay.

---

# 14. Work-package dependency graph

Recommended integration order from the current state:

```text
existing PR6–PR8 development substrate
        ↓
WP6a Verifiers config/compiler/output compatibility
        ↓
WP6b one real Hermes Docker variant
        ↓
WP6c concurrent baseline/candidate real executor
        ↓
WP7a Episode receipts and observed comparison
        ↓
WP7b signing, proof bundle, and verification
        ↓
WP7c Rich/compact presentation and replacement Campaign service
        ↓
WP8a Ash read-only catalog kernel
        ↓
WP8b bootstrap release and public pages
        ↓
WP9 Hermes plugin/bootstrap
        ↓
WP10 guided refinement + rich operator Skills
        ↓
WP11 clean-machine/phone release hardening
```

WP8 may be built in parallel with WP6/WP7 once its catalog input contract is frozen.

WP9 must wait for:

```text
stable CLI JSON commands
real run result
proof verification
bootstrap API
```

WP10 must wait for:

```text
ComparisonPresentation
SkillImprovementContext
skill_replacement flow
founder-supplied Skills
```

---

# 15. Error taxonomy required by WP6–WP8

Add or map typed errors for:

```text
evaluation_provider_not_ready
evaluation_config_invalid
evaluation_dry_run_failed
evaluation_process_failed
evaluation_timed_out
evaluation_cancelled
evaluation_output_missing
evaluation_output_corrupt
episode_count_mismatch
task_membership_mismatch
trace_role_mismatch
reward_missing
reward_non_finite
observed_configuration_mismatch
variant_start_failed
variant_sibling_cancelled
local_identity_invalid
signature_verification_failed
receipt_set_invalid
comparison_invalid
proof_bundle_invalid
presentation_redaction_failed
catalog_bundle_invalid
catalog_object_missing
catalog_object_digest_mismatch
bootstrap_release_missing
```

Every error model contains:

```text
stable code
safe human message
retryable boolean
sanitized details
NextAction when repair exists
```

No error includes:

```text
API key
Authorization header
raw provider request
hidden answer
private-key bytes
unredacted environment
```

---

# 16. Definition of done for WP6–WP8

## WP6

- [ ] The exact pinned Verifiers engine executes `eval` through full paths.
- [ ] A custom Env yields the named `subject` role.
- [ ] Hermes 0.19.0 is installed inside clean Docker runtime homes.
- [ ] Bundled subject Skills remain disabled.
- [ ] Baseline and candidate configs compile and dry-run.
- [ ] Prime evaluation auth is diagnosed separately from host Hermes auth.
- [ ] Verifiers platform push is disabled.
- [ ] Raw output is retained.
- [ ] Normalized output is deterministic in task-membership order.
- [ ] Baseline and candidate execute concurrently with recorded launch skew.
- [ ] Cancellation cleans up both child processes and Docker resources.
- [ ] The fake executor is no longer the default for a real Campaign.
- [ ] No Relay dependency exists.

## WP7

- [ ] Every expected Episode has a receipt.
- [ ] Actual rewards are preserved exactly.
- [ ] Declared and observed configurations agree.
- [ ] The manifest comparison and observed comparison both pass.
- [ ] Task pairing is complete and unique.
- [ ] UpliftReport supports insertion and replacement comparisons.
- [ ] Local Ed25519 identity signs receipt/report envelopes.
- [ ] Local proof verification is offline.
- [ ] P1 wording is honest.
- [ ] Rich terminal output is deterministic and accessible.
- [ ] Compact phone output is bounded and ANSI-free.
- [ ] Improvement context excludes hidden verifier material.
- [ ] Skill v1 versus Skill v2 can be prepared through the same Campaign kernel.
- [ ] No upload occurs.

## WP8

- [ ] `techtree.sh` has the academic onboarding and catalog pages.
- [ ] The public catalog preserves Climb/Campaign separation.
- [ ] Exact content-addressed objects are served byte-for-byte.
- [ ] Bootstrap release pins plugin and CLI.
- [ ] API returns executable instructions only as argv arrays.
- [ ] Catalog import is transactional.
- [ ] No mutation/upload/auth route exists.
- [ ] P1 limitations and DataPolicy are visible.
- [ ] Phone-width rendering works.
- [ ] The site is not in the local evaluator's critical path.

---

# 17. Instructions for the chief-of-staff agent

Treat this document as the binding implementation specification for **Work Packages 6, 7, and 8**, distinct from the already-committed PR6–PR8 slice supplement.

Required ticket split:

```text
WP6a — Verifiers eval compatibility and compiler
WP6b — real named-subject Hermes Docker execution
WP6c — concurrent variant scheduler and real executor

WP7a — Episode parsing, receipts, and receipt sets
WP7b — observed comparison, aggregation, and report
WP7c — local signing/proof verification and presentation
WP7d — skill_replacement and improvement-context service

WP8a — Ash catalog resources/importer
WP8b — exact-byte public API and bootstrap manifest
WP8c — academic LiveView pages and release hardening
```

Before dispatching workers:

1. Compare frozen committed models to the additive amendments in this document.
2. Do not mutate a frozen model casually. Record an explicit protocol amendment when a field/enum must expand.
3. Keep helper scripts that affect scientific interpretation inside the digested engine bundle.
4. Keep website files and Python files in separate worker scopes.
5. Keep generated protocol/catalog files single-owner.
6. Do not let any worker implement Relay, upload, authentication, or a leaderboard.
7. Do not let any worker invent the founder-supplied subject starter Skill, rich-output Skill, or improvement Skill.
8. Do not accept a real result until its local proof verifies from exact stored bytes.
9. Add the terminal and gateway acceptance scenarios as release-blocking tests or scripted manual gates.

The chief should record one deliberate roadmap amendment:

```text
Relay is deferred until after the complete install → first comparison →
one-turn Skill revision → second comparison flow is green.
```

---

# 18. Final product statement for this push

At the end of this push, Techtree should demonstrate one small but complete improvement program:

> A person asks their ordinary Hermes agent to test a Skill. Techtree installs through an explicitly approved, pinned path; runs a neutral and Skill-enabled Hermes subject concurrently in clean Docker environments; receives reward truth from Verifiers; proves that only the Skill changed; renders the difference clearly in a terminal or phone channel; lets the host agent propose one reviewed revision using a founder-supplied improvement Skill; reruns the old and new Skills under the same controlled Campaign; and creates a locally signed, offline-verifiable Uplift receipt without uploading the participant's trajectories or result.

That loop is the first usable expression of the wider Techtree product: Climb supplies public demand, Verify supplies controlled execution, Uplift supplies repeated improvement, and the shared Campaign kernel keeps the science and rights portable across the later product modes.

