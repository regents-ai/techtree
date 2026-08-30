# Techtree Climb v0.1

## Remaining Work Packages 9–11 Implementation Specification

### Hermes operator bootstrap, guided two-stage Skill uplift, and cross-repository release hardening

**Status:** Binding implementation specification for the remaining Climb v0.1 work after WP8  
**Audience:** Chief-of-staff agent, ticket authors, worker-thread implementers, reviewers, release engineer, and founder  
**Repositories covered:** `techtree-python/`, `techtree-hermes/`, and `techtree-ash/`  
**Work packages covered:** WP9, WP10, and WP11  
**Not covered:** NeMo Relay integration, proof/report upload, public leaderboard submission, remote evaluation, private ImprovementProgram behavior, SkillOpt loops, or Prime Lab training  
**Primary host operator:** An ordinary user-controlled Hermes Agent session, reached through the terminal/TUI or a Hermes gateway channel  
**Evaluated subject:** A clean, pinned Hermes subject launched through Verifiers in Docker  
**Evaluation truth:** Prime Intellect Verifiers  
**Canonical scientific artifact:** `UpliftReport`; user-facing copy may call its locally signed proof envelope an **Uplift receipt**  
**Primary privacy rule:** Results, receipts, Skills, Episodes, and proof bundles remain local; the website is read-only and receives no upload  
**Relay status:** Deliberately deferred until the complete local product loop is green  

---

# 0. Executive answer: what remains after WP8

There are **three remaining Work Packages required for Climb v0.1**:

```text
WP9  — Hermes operator plugin, explicit Techtree CLI bootstrap,
       channel-safe tools, and first-run orchestration

WP10 — Rich/compact result explanation, one-turn Skill revision,
       Skill v1 → Skill v2 approval, and second controlled comparison

WP11 — Cross-repository release assembly, clean-machine terminal and
       phone/gateway acceptance, security/recovery hardening, and launch docs
```

The first optional package after v0.1 is:

```text
WP12+ — NeMo Relay runtime-evidence integration
```

WP12 is **not a Climb v0.1 release requirement**.

The complete v0.1 user journey is:

```text
One explicit host-side Hermes plugin install
        ↓
User talks to Host Hermes from terminal or phone gateway
        ↓
Plugin checks for the Techtree CLI
        ↓
Plugin presents an exact, pinned CLI installation plan
        ↓ explicit approval through Hermes' normal approval path
Plugin installs and verifies techtree-python
        ↓
Techtree Doctor verifies engine, Docker, catalog, DataPolicy,
and evaluation-provider authentication
        ↓
Plugin materializes the founder-supplied public starter Skill v1
        ↓
Plugin prepares the introductory public Climb
        ↓ explicit DataPolicy + model-budget approval
Techtree runs concurrently:
  neutral no-candidate-Skill subject
  starter Skill v1 subject
        ↓
Verifiers records Episodes, Traces, rewards, metrics, usage, and errors
        ↓
Techtree builds receipts, verifies the controlled comparison,
signs the local UpliftReport, and creates a local proof bundle
        ↓
CLI shows the deterministic Rich result
Host Hermes uses the founder-supplied rich-terminal-output Skill
for a truthful explanatory turn
        ↓
User asks for one improvement attempt
        ↓
Host Hermes uses the founder-supplied skill-improver Skill for exactly
one structured host-model completion
        ↓
Techtree stages Skill v2, scans it, computes its digest, and shows a diff
        ↓ explicit second approval
Techtree runs concurrently:
  Skill v1 subject
  Skill v2 subject
        ↓
Techtree creates and verifies the second local Uplift receipt
        ↓
Terminal or phone receives the result and local artifact paths
        ↓
Nothing is uploaded to techtree.sh
```

---

# 1. Scope correction: a plugin cannot install itself

The requested user experience must acknowledge one unavoidable bootstrap boundary:

> A Hermes plugin cannot participate in installing itself before it exists.

The guaranteed v0.1 path is therefore:

```text
1. Install and enable the pinned Techtree Hermes plugin on the Hermes host.
2. Restart or start a Hermes session so the plugin is loaded.
3. From that point onward, use the terminal or phone/gateway conversation
   to install and operate Techtree.
```

The canonical plugin installation is an explicit host command:

```bash
hermes plugins install regents-labs/techtree-hermes \
  --ref <full-40-character-plugin-commit> \
  --enable
```

A phone-only user may ask an already-capable Hermes host to run that command through Hermes' ordinary terminal tool and approval system. That is a Hermes host-management path, not a capability supplied by a plugin that is not yet installed. Climb v0.1 must not claim universal phone-only self-installation from a completely untouched Hermes host.

After the plugin is installed and loaded, **the rest of the journey must be operable from a phone gateway without SSH or terminal access**, provided:

- Docker and Hermes are already running on the host.
- The selected gateway exposes the ordinary Hermes conversation and tool-approval flow.
- The user can answer explicit installation and model-budget approval prompts.
- Evaluation-provider authentication is already available on the host.

---

# 2. Product definition of Climb v0.1

Climb v0.1 is complete when a user can prove two controlled Skill comparisons locally:

## 2.1 First comparison

```text
No candidate Skill
        versus
Founder-supplied starter subject Skill v1
```

This comparison answers:

> Does this declared Skill improve the pinned subject agent on the declared Campaign?

## 2.2 Second comparison

```text
Starter subject Skill v1
        versus
One host-agent-proposed Skill v2
```

This comparison answers:

> Did the one-turn revision improve the already Skill-enabled subject under the same controlled Campaign?

## 2.3 Required output

Each comparison creates:

```text
baseline ExperimentManifest
candidate ExperimentManifest
Verifiers output directories
EpisodeReceipts
receipt-set commitments
ManifestComparison
observed comparison result
UpliftReport
local Ed25519 signatures
local proof bundle
ComparisonPresentation payload
```

The user-facing label may be:

```text
Uplift receipt
```

The protocol object remains:

```text
UpliftReport
```

## 2.4 Explicit non-goals

Climb v0.1 does not:

- Upload an UpliftReport to the web application.
- Upload raw Episodes, Traces, logs, or Skills.
- Publish a leaderboard submission.
- Claim independent reproduction.
- Use a remote Techtree evaluator.
- Perform more than one guided Skill-revision attempt in the introductory demo.
- Run SkillOpt or GEPA as part of the demo.
- Add NeMo Relay as a release dependency.
- Add a private ImprovementProgram or release-decision workflow.
- Let the host Hermes conversation enter the evaluated Docker subject.
- Let model-authored explanation change any scientific field.

---

# 3. Source-of-truth boundaries

## 3.1 Host versus subject

```text
Host Hermes
    User-facing operator.
    May use Techtree operator Skills.
    May explain results.
    May propose one Skill revision.
    Is never the evaluated subject.

Docker Hermes
    Pinned evaluated subject.
    Receives only the declared subject Skill, tools, runtime, task,
    model endpoint, and system configuration.
```

Host state that must never leak into the subject unless declared in the immutable manifest:

- Conversation history.
- Host memories.
- Host-installed plugins.
- Host operator Skills.
- Host workspace files.
- Host credentials other than the provider credential deliberately exposed through the Verifiers client boundary.
- Gateway metadata.

## 3.2 Scientific truth

```text
Verifiers Task reward records
    sole score truth

Techtree
    resolves, freezes, executes, binds, compares, signs, verifies,
    presents, and stores local artifacts

Host model / operator Skills
    explanation and proposal only
```

The plugin and host model must never:

- Recalculate rewards.
- Replace a missing reward.
- Infer hidden expected answers.
- Change wins, losses, ties, or deltas.
- Change status fields.
- Upgrade proof grade.
- Say the website witnessed local execution.

## 3.3 Campaign versus Climb

`CampaignSpec` remains the reusable scientific contract.

`ClimbManifest` remains the public invitation and policy wrapper.

The plugin may use the public Climb to help the user select and consent, but every scientific operation is rooted in:

```text
campaign_spec_digest
```

Every local artifact continues to carry:

```text
campaign_spec_digest
data_policy_digest
evaluation_backend
optional public_context
optional program_ref
optional outcome_contract_digest
```

## 3.4 Data rights

The DataPolicy for the introductory Climb must continue to mean:

```text
candidate Skill ownership:
    participant

candidate Skill public release:
    required for the public Climb profile

raw Episodes:
    local retention allowed
    server upload prohibited
    public release prohibited
    training use prohibited

UpliftReport and aggregate score:
    may be displayed locally
    public-use permission may exist in policy
    no upload occurs in v0.1
```

The exact DataPolicy digest must be acknowledged for both drafts:

- No-Skill versus Skill v1.
- Skill v1 versus Skill v2.

An earlier acknowledgement is not silently reused for a new draft.

## 3.5 Website boundary

The WP8 website supplies only read-only public material:

- Installation documentation.
- Bootstrap release metadata.
- Public Climb and Campaign objects.
- Public starter Skill object.
- Protocol documentation.
- Health status.

WP9–WP11 add no mutation endpoint.

The plugin and CLI must contain no code path for:

```text
POST receipt
POST report
POST proof bundle
POST Skill
POST raw Episode
POST Trace
```

---

# 4. Founder-owned release inputs

Implementation workers must not invent the contents of the following artifacts.

## 4.1 Starter subject Skill v1

Required artifact:

```text
starter-subject-skill/
└── SKILL.md
```

Release requirements:

- Valid `techtree-instruction-skill-v1` format.
- Publicly distributable.
- Content-addressed.
- No proving-input answer table.
- No hidden verifier material.
- Designed to produce a clear uplift over the no-Skill baseline.
- Expected to leave at least some room for a meaningful revision, but no runtime result is fabricated to ensure that.
- Included in the WP8 public release bundle or another exact read-only object URL pinned by the bootstrap release.

Required release metadata:

```text
starter_skill_digest
starter_skill_object_url
starter_skill_media_type
starter_skill_size
starter_skill_label
```

## 4.2 `techtree:rich-terminal-output`

Required artifact:

```text
skills/rich-terminal-output/SKILL.md
```

Founder supplies its actual instructions.

Implementation workers define and enforce only:

- Input schema.
- Output schema.
- Maximum output size.
- Forbidden-claim rules.
- No-numeric-invention rule.
- Terminal and gateway channel modes.
- Deterministic fallback.

## 4.3 `techtree:skill-improver`

Required artifact:

```text
skills/skill-improver/SKILL.md
```

Founder supplies its actual instructions.

Implementation workers define and enforce only:

- Sanitized improvement-context schema.
- Exactly one host-model completion per explicit proposal attempt.
- Structured output schema.
- Skill-scanner and secret-scanner gate.
- Reviewable diff.
- One-proposal limit in the introductory demo.
- No hidden answers or grader material.

## 4.4 Reference phone gateway

The implementation is channel-generic, but WP11 must certify one concrete mobile gateway end to end.

Founder/release owner supplies:

```text
REFERENCE_GATEWAY=<one supported Hermes gateway>
```

The selected gateway is a release-test target, not a Techtree protocol field.

Other Hermes gateways should work when they expose the same ordinary tool and approval behavior, but they are not called certified until tested.

## 4.5 Release coordinates

Founder/release owner confirms:

```text
CLI distribution name
CLI version
CLI source commit
plugin repository
plugin full commit
website origin
introductory Climb reference
Prime model profile
host Hermes minimum version
host Hermes maximum-tested version
subject Hermes version
```

The release process freezes those values; no model chooses them at runtime.

---

# 5. Architecture after WP11

```text
┌────────────────────────────────────────────────────────────────────┐
│ Human surface                                                       │
│                                                                    │
│ Terminal/TUI                         Phone/gateway                  │
└──────────────┬─────────────────────────────┬────────────────────────┘
               │                             │
               └──────────────┬──────────────┘
                              ▼
                    Host Hermes Agent
                              │
                Techtree standalone plugin
              ┌───────────────┼────────────────┐
              │               │                │
       CLI JSON bridge  host LLM one-shot  plugin session state
              │         presentation/revision   │
              └───────────────┼────────────────┘
                              ▼
                       techtree CLI
              ┌───────────────┼────────────────┐
              │               │                │
       Campaign/drafts   detached worker   local proof verify
              │               │                │
              └───────────────┼────────────────┘
                              ▼
                     managed engine
                              │
                       Verifiers eval
                  ┌───────────┴───────────┐
                  ▼                       ▼
       Docker Hermes baseline   Docker Hermes candidate
                  │                       │
                  └───────────┬───────────┘
                              ▼
               Episodes, Traces, rewards, metrics
                              │
                              ▼
             local receipts and UpliftReport
                              │
                 no upload / no web mutation
```

The WP8 Ash site remains outside the local scientific critical path:

```text
techtree.sh
    bootstrap and release metadata
    public catalog
    starter Skill bytes
    onboarding and documentation
```

---

# 6. Cross-package local UX models

These are plugin/local UX objects, not new signed scientific protocol objects.

They may live in the plugin repository or, where reusable by other host-agent integrations, in `techtree-python` under a non-protocol namespace.

## 6.1 `ChannelKind`

```python
class ChannelKind(str, Enum):
    TERMINAL = "terminal"
    GATEWAY = "gateway"
    UNKNOWN = "unknown"
```

Rules:

- `UNKNOWN` receives compact, ANSI-free output.
- The plugin must not infer terminal merely because it runs on macOS/Linux.
- An explicit tool argument or documented Hermes callback field may select the channel.
- Raw ANSI is never emitted through a model-visible JSON tool result.

## 6.2 `DemoStage`

```python
class DemoStage(str, Enum):
    PLUGIN_READY = "plugin_ready"
    CLI_INSTALL_REQUIRED = "cli_install_required"
    CLI_READY = "cli_ready"
    FIRST_DRAFT_PREPARED = "first_draft_prepared"
    FIRST_RUN_ACTIVE = "first_run_active"
    FIRST_RESULT_READY = "first_result_ready"
    REVISION_PROPOSAL_READY = "revision_proposal_ready"
    SECOND_DRAFT_PREPARED = "second_draft_prepared"
    SECOND_RUN_ACTIVE = "second_run_active"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

This is convenience state only.

Scientific truth remains in Techtree run and proof artifacts.

## 6.3 `DemoSessionState`

```python
@dataclass(frozen=True)
class DemoSessionState:
    demo_id: str
    release_core_digest: str
    climb_reference: str
    stage: DemoStage
    first_draft_id: str | None
    first_run_id: str | None
    first_proof_path: str | None
    source_skill_v1_digest: str | None
    proposal_id: str | None
    second_draft_id: str | None
    second_run_id: str | None
    second_proof_path: str | None
    revision_attempts: int
    updated_at: str
```

Rules:

- No API keys.
- No confirmation tokens after use.
- No private key bytes.
- No raw Episode data.
- No full Skill text.
- No hidden task content.
- State is reconstructable from stored Techtree IDs where possible.

## 6.4 `PresentationNarrative`

The model-authored presentation output must not carry scientific numbers.

```python
@dataclass(frozen=True)
class PresentationNarrative:
    headline: str
    verdict: str
    observations: tuple[str, ...]
    caveats: tuple[str, ...]
    next_step: str | None
    selected_task_refs: tuple[str, ...]
```

Canonical scores and statuses are rendered separately from the deterministic `UpliftPresentationPayload`.

## 6.5 `SkillRevisionOutput`

```python
@dataclass(frozen=True)
class SkillRevisionOutput:
    analysis_summary: str
    change_rationale: tuple[str, ...]
    revised_skill_markdown: str
    expected_tradeoffs: tuple[str, ...]
    confidence: Literal["low", "medium", "high"]
```

This is a proposal, not an evaluated artifact.

## 6.6 `ReleaseCore`

`ReleaseCore` avoids a cross-repository self-reference cycle.

```python
@dataclass(frozen=True)
class ReleaseCore:
    schema_version: Literal["techtree.release-core.v1"]
    release_id: str
    cli_version: str
    cli_source_commit: str
    protocol_version: str
    engine_digest: str
    catalog_digest: str
    intro_climb_reference: str
    starter_skill_digest: str
    rich_output_skill_digest: str
    skill_improver_digest: str
    minimum_host_hermes_version: str
    maximum_tested_host_hermes_version: str
    subject_hermes_version: str
```

`ReleaseCore` does not include:

- Plugin commit, because the plugin embeds the ReleaseCore.
- CLI wheel hash, because the wheel embeds the ReleaseCore.
- Website deployment ID.

Those belong to the later `BootstrapRelease` wrapper.

---

# 7. Work Package 9 — Hermes operator plugin and explicit CLI bootstrap

## 7.1 Objective

Build the standalone Hermes plugin that:

1. Loads safely with no installation or network side effects.
2. Exposes typed Techtree tools to Host Hermes.
3. Uses the existing Techtree CLI JSON contract as its only scientific control interface.
4. Offers an explicit, pinned plan to install `techtree-python` when absent.
5. Uses Hermes' normal human approval surface for the installation command.
6. Verifies the installed CLI release and runs Doctor.
7. Lets terminal and gateway users inspect, prepare, start, monitor, cancel, and read the introductory Climb.
8. Keeps long work asynchronous by returning run IDs.
9. Registers the operator and founder-supplied Skills without mounting them into the evaluated subject.

## 7.2 WP9 non-goals

WP9 does not:

- Implement real Verifiers execution; WP6 owns that.
- Construct receipts or reports; WP7 owns that.
- Implement rich model-authored explanation; WP10 owns that.
- Propose Skill v2; WP10 owns that.
- Upload anything.
- Modify the website.
- Install the plugin itself.
- Automatically install `uv`.
- Ask the user to paste an API key into chat.
- Use arbitrary model-generated shell commands.
- Add Relay.

## 7.3 Repository skeleton

```text
techtree-hermes/
├── README.md
├── LICENSE
├── pyproject.toml
├── plugin.yaml
├── release-core.json
├── __init__.py
├── constants.py
├── errors.py
├── models.py
├── schemas.py
├── bridge.py
├── release.py
├── bootstrap.py
├── approvals.py
├── channels.py
├── state.py
├── commands.py
├── hooks.py
│
├── tools/
│   ├── __init__.py
│   ├── bootstrap.py
│   ├── catalog.py
│   ├── demo.py
│   ├── run.py
│   ├── proof.py
│   └── uplift.py
│
├── services/
│   ├── __init__.py
│   ├── container.py
│   ├── assets.py
│   └── session.py
│
├── skills/
│   ├── operator/
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── approvals.md
│   │       ├── proof-grades.md
│   │       └── troubleshooting.md
│   ├── rich-terminal-output/
│   │   └── SKILL.md
│   └── skill-improver/
│       └── SKILL.md
│
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── cli/
│   │   ├── release/
│   │   └── skills/
│   ├── unit/
│   │   ├── test_bridge.py
│   │   ├── test_release.py
│   │   ├── test_bootstrap.py
│   │   ├── test_approvals.py
│   │   ├── test_channels.py
│   │   ├── test_state.py
│   │   ├── test_schemas.py
│   │   └── test_registration.py
│   ├── contract/
│   │   ├── test_cli_envelopes.py
│   │   ├── test_plugin_doctor.py
│   │   └── test_no_registration_side_effects.py
│   └── integration/
│       ├── test_bootstrap_flow.py
│       ├── test_demo_first_run.py
│       └── test_terminal_commands.py
│
└── tools/
    ├── export_tool_schemas.py
    ├── verify_release_core.py
    └── check_founder_skills.py
```

The runtime plugin code should use only the Python standard library and Hermes' documented plugin context. Development tooling may use pytest and linting dependencies.

---

## 7.4 Root file responsibilities

### `plugin.yaml`

Declares:

```yaml
name: techtree
version: 0.1.0
description: Controlled local agent Skill evaluation and uplift through Techtree
provides_tools:
  - techtree_bootstrap_check
  - techtree_bootstrap_install
  - techtree_system_check
  - techtree_climbs_list
  - techtree_climb_inspect
  - techtree_climb_prepare
  - techtree_demo_prepare
  - techtree_climb_start
  - techtree_run_status
  - techtree_run_cancel
  - techtree_run_result
  - techtree_proof_verify
  - techtree_uplift_context
  - techtree_uplift_prepare
  - techtree_uplift_start
provides_hooks:
  - on_session_start
  - on_session_end
```

Do not use `requires_env` for provider credentials. Provider authentication belongs to the Techtree/Verifiers Doctor boundary, not to plugin loading.

### `release-core.json`

Generated file containing exact `ReleaseCore` bytes.

Rules:

- Never hand-edit.
- Included in the plugin commit.
- Digest verified at plugin registration.
- Must equal the CLI's reported ReleaseCore digest after installation.

### `__init__.py`

Contains only plugin registration and service assembly.

Required functions:

```python
def register(ctx) -> None:
    """
    Validate local static release assets, build dependency container,
    register tools, commands, hooks, and bundled Skills.

    Must not:
      access the network
      install a package
      run Docker
      run the Techtree CLI
      call an LLM
      mutate user files beyond Hermes-owned plugin state initialization
    """
```

```python
def _register_tools(ctx, services) -> None:
    """Register every declared model-visible tool."""
```

```python
def _register_commands(ctx, services) -> None:
    """Register `/techtree` and `hermes techtree ...` command surfaces."""
```

```python
def _register_skills(ctx) -> None:
    """Register namespaced read-only operator Skills."""
```

```python
def _register_hooks(ctx, services) -> None:
    """Register additive-signature session hooks with **kwargs."""
```

### `constants.py`

Defines:

```text
PLUGIN_ID
PLUGIN_VERSION
TOOLSET_NAME
CLI_COMMAND
CLI_JSON_FLAGS
DEFAULT_CLI_TIMEOUT_SECONDS
DEFAULT_NETWORK_TIMEOUT_SECONDS
MAX_CLI_STDOUT_BYTES
MAX_CLI_STDERR_BYTES
MAX_TOOL_RESULT_BYTES
MAX_BOOTSTRAP_MANIFEST_BYTES
MAX_STARTER_SKILL_BYTES
INSTALL_PLAN_TTL_SECONDS
DEMO_SESSION_TTL_SECONDS
SUPPORTED_RELEASE_CORE_SCHEMA
```

No mutable state.

### `errors.py`

Defines plugin-local errors:

```python
class PluginError(Exception): ...
class CliNotInstalledError(PluginError): ...
class CliInvocationError(PluginError): ...
class CliEnvelopeError(PluginError): ...
class ReleaseMismatchError(PluginError): ...
class BootstrapPlanError(PluginError): ...
class ApprovalRequiredError(PluginError): ...
class ChannelError(PluginError): ...
class PluginStateError(PluginError): ...
```

Functions:

```python
def safe_error_payload(error: Exception) -> dict:
    """Return stable code, safe message, retryability, and repair action."""
```

```python
def scrub_text(value: str) -> str:
    """Remove Bearer tokens, quoted secret keys, provider tokens, and private keys."""
```

The plugin must not duplicate every Techtree error code. It preserves CLI envelopes when the CLI produced the error and uses plugin-local codes only for the bridge/bootstrap layer.

### `models.py`

Contains stdlib dataclasses/enums for:

```text
ChannelKind
DemoStage
DemoSessionState
ReleaseCore
BootstrapInstallPlan
CliInvocation
CliResponse
PluginAction
```

Functions:

```python
def parse_release_core(raw: bytes) -> ReleaseCore
```

```python
def parse_cli_envelope(raw: str) -> dict
```

```python
def parse_bootstrap_install_plan(value: dict) -> BootstrapInstallPlan
```

Validation is strict:

- Reject unknown schema versions.
- Reject extra executable fields.
- Reject shell-string installation instructions.
- Require argv arrays.
- Require exact package/version from `ReleaseCore` or `BootstrapRelease`.

### `schemas.py`

Exports one JSON-schema dictionary per tool.

Rules:

- Descriptions state when the model should use the tool.
- Descriptions explicitly name cost/approval effects.
- No schema accepts an API key.
- No schema accepts an executable path.
- No schema accepts an arbitrary install command.
- IDs and digests have bounded string patterns.
- Channel is `terminal`, `gateway`, or `unknown`.
- Path-taking tools state that the path must be explicitly identified by the user.

Function:

```python
def all_tool_schemas() -> dict[str, dict]:
    """Return immutable name-to-schema mapping for registration and tests."""
```

---

## 7.5 CLI bridge

### `bridge.py`

The bridge is the only normal path from plugin tools into Techtree behavior.

Functions:

```python
def resolve_techtree_binary() -> str | None:
    """Return the installed Techtree executable path using shutil.which."""
```

```python
def build_cli_argv(arguments: Sequence[str]) -> list[str]:
    """
    Prepend resolved executable and append:
      --json
      --no-color
      --no-input
    Reject arguments containing NUL.
    """
```

```python
def invoke_cli(
    arguments: Sequence[str],
    *,
    timeout_seconds: float,
    maximum_stdout_bytes: int = MAX_CLI_STDOUT_BYTES,
    maximum_stderr_bytes: int = MAX_CLI_STDERR_BYTES,
) -> dict:
    """
    Invoke with subprocess.run(shell=False), capture output, parse exactly one
    CliEnvelope, sanitize stderr, and return the envelope unchanged.
    """
```

```python
def invoke_cli_human(
    arguments: Sequence[str],
) -> int:
    """
    Terminal-only direct subprocess used by Hermes CLI subcommands such as
    `hermes techtree watch`; inherits stdout/stderr and never returns through
    a gateway tool.
    """
```

```python
def verify_cli_release(expected: ReleaseCore) -> dict:
    """
    Run `techtree release info` or the equivalent frozen command and require
    exact release-core digest and compatible CLI version.
    """
```

Environment behavior:

- Inherit the host environment so the CLI/worker can access existing Prime authentication.
- Never enumerate or log environment values.
- Never copy secrets into arguments.
- Remove plugin-only temporary variables when unnecessary.
- Preserve `TECHTREE_HOME` when explicitly configured.

Output behavior:

- Tool handler returns the original safe CLI envelope.
- Stderr is attached only as bounded sanitized diagnostics.
- More than one JSON object on stdout is a contract failure.
- ANSI on stdout in machine mode is a contract failure.

---

## 7.6 Release and bootstrap

### `release.py`

Functions:

```python
def load_embedded_release_core() -> ReleaseCore:
    """Read and verify exact release-core.json bytes."""
```

```python
def release_core_digest(core: ReleaseCore) -> str:
    """Calculate the canonical digest using the release-core contract."""
```

```python
def compare_cli_release(
    embedded: ReleaseCore,
    installed: dict,
) -> list[str]:
    """Return mismatch codes; empty means compatible."""
```

```python
def compare_bootstrap_release(
    core: ReleaseCore,
    bootstrap: dict,
    installed_plugin_commit: str | None,
) -> list[str]:
    """Verify website release points at this core and plugin revision."""
```

### `bootstrap.py`

Responsibilities:

- Detect `uv`.
- Detect Techtree CLI.
- Produce an exact install plan.
- Save an expiring plan in plugin state.
- Request human approval through Hermes' normal approval-bearing terminal tool.
- Verify CLI after install.
- Run Techtree Doctor.

Functions:

```python
def bootstrap_check(services, *, include_doctor: bool = True) -> dict:
    """
    Return plugin version, release-core digest, uv status, CLI status,
    release compatibility, Doctor summary, and next action.
    """
```

```python
def create_install_plan(
    release: ReleaseCore,
    *,
    uv_path: str,
) -> BootstrapInstallPlan:
    """
    Construct one fixed argv from release data. No user/model-controlled package,
    version, index, URL, or extra flag is accepted.
    """
```

```python
def install_cli_with_approval(
    ctx,
    services,
    *,
    plan_id: str,
) -> dict:
    """
    Validate the stored unexpired plan and dispatch its fixed command through
    Hermes' ordinary terminal approval path. After success, verify release and
    run Doctor.
    """
```

```python
def manual_install_response(plan: BootstrapInstallPlan) -> dict:
    """Return exact argv for environments without an approved terminal tool."""
```

### Installation command policy

The install command is generated, not model-authored.

Conceptual release plan:

```json
{
  "package": "techtree",
  "version": "0.1.0",
  "argv": ["uv", "tool", "install", "techtree==0.1.0"],
  "release_core_digest": "sha256:...",
  "requires_confirmation": true
}
```

The exact release may add fixed, reviewed `uv` arguments. The model cannot add any.

`install_cli_with_approval` should prefer:

```python
ctx.dispatch_tool("terminal", {"command": fixed_display_command})
```

because dispatched terminal work passes through Hermes' ordinary approval, redaction, and budget pipeline.

This is the one reviewed exception to the general rule that plugin-to-Techtree calls use direct argv arrays: the CLI does not exist yet, and human approval for installation is required.

The command string is derived solely from a validated fixed argv and shell-quoted for display. It contains no user/model input.

When the terminal tool or gateway approval path is unavailable, the plugin must not fall back to an unapproved direct subprocess install. It returns manual instructions.

### Missing `uv`

The plugin:

- Does not run `curl | sh`.
- Does not run a remote installer.
- Does not choose a package manager.
- Returns the release documentation URL and platform-specific instructions from the read-only bootstrap metadata.

---

## 7.7 Approval handling

### `approvals.py`

Functions:

```python
def issue_local_plan_id(kind: str, digest: str) -> str:
    """Create a random opaque plan ID; never encode a secret."""
```

```python
def require_install_plan(state, plan_id: str) -> BootstrapInstallPlan:
    """Require exact ID, unexpired plan, and current release core."""
```

```python
def require_user_confirmed_tool_context(kwargs: dict) -> None:
    """
    Apply only when Hermes exposes a documented confirmation indicator.
    Do not invent undocumented callback semantics.
    """
```

```python
def policy_acceptance_args(
    *,
    draft_id: str,
    confirmation_token: str,
    data_policy_digest: str,
) -> list[str]:
    """Build exact start arguments for machine-mode explicit acceptance."""
```

Techtree run approval remains enforced by the CLI:

```text
confirmation token
+
--accept-data-policy <exact digest>
```

The plugin does not replace or weaken that mechanism.

---

## 7.8 Channel handling

### `channels.py`

Functions:

```python
def resolve_channel(
    explicit: str | None,
    callback_context: dict,
) -> ChannelKind:
    """
    Use explicit valid hint first, documented Hermes context second,
    UNKNOWN otherwise.
    """
```

```python
def ensure_gateway_safe(value: str) -> str:
    """Reject/strip ANSI, NUL, overlong text, and unsafe control characters."""
```

```python
def bounded_gateway_text(value: str, maximum_chars: int) -> str:
    """Truncate at a Unicode-safe boundary and include an explicit truncation note."""
```

Rules:

- Gateway tools always return compact Markdown or structured JSON.
- Terminal Rich output is shown through Techtree/Hermes CLI commands, not embedded raw in model tool JSON.
- Unknown channel defaults to gateway-safe behavior.

---

## 7.9 Plugin state

### `state.py`

Wraps `ctx.state`.

Functions:

```python
def load_sessions(ctx) -> dict[str, DemoSessionState]:
```

```python
def save_session(ctx, session: DemoSessionState) -> None:
```

```python
def latest_session(ctx) -> DemoSessionState | None:
```

```python
def active_run_ids(ctx) -> list[str]:
```

```python
def prune_expired_plans(ctx, now: datetime) -> int:
```

```python
def reconcile_session_with_cli(
    ctx,
    session: DemoSessionState,
) -> DemoSessionState:
    """Read bounded Techtree status and advance convenience state."""
```

Rules:

- Use profile-scoped Hermes plugin state.
- Keep state below the Hermes plugin-state size limit.
- Store only IDs, digests, labels, and local proof paths.
- Malformed state is reported and preserved for debugging; do not silently discard.
- Scientific artifacts never live in plugin state.

---

## 7.10 Service container

### `services/container.py`

```python
@dataclass(frozen=True)
class PluginServices:
    ctx: object
    release_core: ReleaseCore
    bridge: CliBridge
    bootstrap: BootstrapService
    assets: AssetService
    sessions: SessionService
```

Functions:

```python
def build_services(ctx) -> PluginServices:
    """Construct one immutable service container during registration."""
```

No service constructor performs network, CLI, Docker, or LLM work.

### `services/assets.py`

Responsibilities:

- Ask the Techtree CLI to materialize the starter Skill from the pinned public release.
- Never download arbitrary URLs supplied by the model.
- Verify returned Skill digest against `ReleaseCore`.

Functions:

```python
def materialize_starter_skill(services) -> dict:
    """Invoke the fixed Techtree bootstrap/materialization command."""
```

```python
def verify_starter_skill_result(result: dict, release: ReleaseCore) -> None:
```

### `services/session.py`

Functions:

```python
def create_demo_session(
    *,
    release: ReleaseCore,
    climb_reference: str,
) -> DemoSessionState:
```

```python
def update_after_first_prepare(session, envelope) -> DemoSessionState:
```

```python
def update_after_first_start(session, envelope) -> DemoSessionState:
```

```python
def update_after_first_result(session, envelope) -> DemoSessionState:
```

WP10 extends this service for proposal and second-run stages.

---

## 7.11 Tool handlers

Every tool handler:

- Accepts `args: dict, **kwargs`.
- Returns one JSON string.
- Catches exceptions and returns safe error JSON.
- Does not raise into the Hermes agent loop.
- Does not execute long-running evaluation synchronously.
- Does not expose secrets.

### `tools/bootstrap.py`

#### `techtree_bootstrap_check`

Input:

```json
{
  "include_doctor": true
}
```

Behavior:

- No installation.
- No model call.
- No Docker run.
- Detect `uv` and CLI.
- Verify release compatibility when CLI exists.
- Run Doctor only when CLI exists and requested.
- Return exact next action.

#### `techtree_bootstrap_install`

Input:

```json
{
  "plan_id": "install_..."
}
```

Behavior:

- May change host package state.
- Only valid after `bootstrap_check` created the plan.
- Requires normal Hermes terminal-tool approval.
- No arbitrary package/version/flags.
- Verifies CLI and Doctor afterward.

### `tools/catalog.py`

#### `techtree_system_check`

Calls:

```text
techtree doctor
```

Returns distinct checks for:

```text
CLI release
managed engine
Docker
public catalog
host platform
evaluation-provider authentication
```

#### `techtree_climbs_list`

Calls:

```text
techtree climb list
```

Does not install or evaluate.

#### `techtree_climb_inspect`

Calls:

```text
techtree climb show <reference>
```

Returns:

- Scientific Campaign summary.
- DataPolicy summary.
- Required model/provider.
- Task count.
- Cost/budget bound.
- Proof grade.
- Compatibility issues.

### `tools/demo.py`

#### `techtree_demo_prepare`

Input:

```json
{
  "channel": "terminal|gateway|unknown"
}
```

Required sequence:

1. Require compatible installed CLI.
2. Run Doctor and block on required failures.
3. Materialize and verify starter Skill v1.
4. Inspect pinned introductory Climb.
5. Invoke ordinary `techtree climb prepare` with the Techtree-owned starter Skill path.
6. Create/update `DemoSessionState`.
7. Return:
   - Demo ID.
   - Draft ID.
   - Skill digest.
   - Exact changed field.
   - DataPolicy summary/digest.
   - Episode and budget estimate.
   - Confirmation token.
   - Explicit next approval action.

No model calls occur.

#### `techtree_climb_prepare`

General low-level candidate preparation.

Input path must be explicitly identified by the user.

It invokes ordinary CLI preparation and never bypasses scanning.

#### `techtree_climb_start`

Input:

```json
{
  "draft_id": "draft_...",
  "confirmation_token": "...",
  "data_policy_digest": "sha256:...",
  "channel": "terminal|gateway|unknown"
}
```

Behavior:

- Starts detached run.
- Returns run ID promptly.
- Stores active run ID in demo session when applicable.
- Does not poll to completion.

### `tools/run.py`

#### `techtree_run_status`

Input:

```json
{
  "run_id": "run_..."
}
```

Returns bounded current status and variant progress.

No long wait.

#### `techtree_run_cancel`

Requires explicit user request.

Calls CLI cancellation and returns current state.

#### `techtree_run_result`

WP9 behavior:

- Requires completed run.
- Returns deterministic report/presentation payload and proof path.
- Does not yet call rich-output host Skill; WP10 adds that optional layer.

### `tools/proof.py`

#### `techtree_proof_verify`

Accepts only:

- Run ID resolved by CLI, or
- User-explicit local proof path.

Returns integrity/scientific/attestation checks separately.

No remote URL upload or retrieval.

### `tools/uplift.py`

WP9 exposes read/control wrappers already implemented by CLI:

```text
techtree_uplift_context
techtree_uplift_prepare
techtree_uplift_start
```

WP10 adds host-model proposal behavior.

---

## 7.12 Slash commands and Hermes CLI commands

### `commands.py`

Register one slash command:

```text
/techtree
```

Supported subcommands:

```text
/techtree setup
/techtree climbs
/techtree demo
/techtree status [run-id]
/techtree cancel <run-id>
/techtree result [run-id]
/techtree verify [run-id-or-proof-path]
/techtree improve [run-id]          # enabled fully in WP10
```

Functions:

```python
def handle_slash_command(raw_args: str, services) -> str:
    """Parse a fixed grammar; reject arbitrary passthrough."""
```

```python
def parse_slash_args(raw_args: str) -> tuple[str, list[str]]:
```

```python
def register_cli_subcommands(ctx, services) -> None:
    """Register `hermes techtree ...` terminal-only commands."""
```

Hermes CLI subcommands:

```text
hermes techtree doctor
hermes techtree demo
hermes techtree status <run-id>
hermes techtree watch <run-id>
hermes techtree result <run-id>
hermes techtree verify <path>
```

`watch` invokes Techtree's human watch command directly and is terminal-only.

No gateway/model tool holds an open watch process.

---

## 7.13 Hooks

### `hooks.py`

```python
def on_session_start(**kwargs) -> None:
    """
    Prune expired install plans and perform bounded local state reconciliation.
    No network, installation, Docker, or model call.
    """
```

```python
def on_session_end(**kwargs) -> None:
    """
    Flush plugin state and delete plugin-owned temporary proposal files only.
    Never delete Techtree runs, Skills, reports, or proof bundles.
    """
```

Both functions accept `**kwargs` for Hermes additive compatibility.

---

## 7.14 Bundled operator Skill

### `skills/operator/SKILL.md`

Implementation workers may author this Skill from the specification.

It must teach Host Hermes:

```text
Host Hermes is operator, not subject.
Inspect before preparing.
Show all approval-relevant facts.
Never infer DataPolicy acceptance.
Never start model-cost work without explicit approval.
Return run IDs for long work.
Poll status only through bounded tool calls.
Use deterministic result facts.
Never claim independent reproduction.
Never upload local artifacts.
Use rich-terminal-output only after deterministic result exists.
Use skill-improver for one proposal only after a valid completed first run.
Show Skill diff before second approval.
```

It must distinguish:

- Starter subject Skill.
- Revised subject Skill.
- Host operator Skills.

---

## 7.15 WP9 tests

### Registration tests

- Plugin doctor passes.
- Declared tools equal registered tools.
- Declared hooks equal registered hooks.
- Skills register under namespaced IDs.
- Registration performs no subprocess, network, Docker, filesystem install, or LLM call.
- Registration succeeds without Techtree CLI installed.

### Bridge tests

- Uses `shell=False` for CLI calls.
- Adds machine flags exactly once.
- One JSON envelope accepted.
- Multiple JSON records rejected.
- ANSI rejected in machine output.
- Oversized output rejected safely.
- Stderr scrubber catches Bearer and quoted-key secrets.
- Provider environment values never enter logs.

### Bootstrap tests

- Missing `uv` returns instructions, not auto-install.
- Missing CLI creates exact plan.
- Plan expires.
- Wrong plan ID rejected.
- Model cannot override package/version/index/flags.
- Installation uses approved terminal dispatch.
- Missing approval-capable terminal returns manual plan.
- Installed release mismatch rejected.
- Doctor blocking failure prevents demo preparation.

### State tests

- State contains no secret or Skill text.
- Malformed state fails safely.
- Expired plans pruned.
- Latest demo session selected deterministically.
- CLI state reconciliation cannot invent a completed run.

### Tool tests

- Every handler returns JSON string on success and error.
- Long operations return run ID.
- Start requires draft token and DataPolicy digest.
- Cancel requires explicit call.
- Path-taking tool rejects implicit/default path.
- Gateway result contains no ANSI.

### Integration tests

- Fake Techtree CLI fixture covers complete first-run tool sequence.
- Real CLI contract test runs Doctor/list/show/prepare against temporary Techtree home.
- Plugin state survives a new Hermes session fixture.
- Terminal CLI subcommands invoke human Techtree output.

---

## 7.16 WP9 acceptance criteria

- [ ] Plugin installs from an exact full commit.
- [ ] Plugin loads without Techtree CLI installed.
- [ ] Registration has no installation side effect.
- [ ] `bootstrap_check` identifies missing CLI.
- [ ] Installation plan is pinned and immutable.
- [ ] Install executes only through explicit Hermes approval or manual user command.
- [ ] Missing `uv` never triggers a remote installer.
- [ ] CLI release is verified after install.
- [ ] Doctor separates host Hermes access from Techtree evaluation access.
- [ ] Starter Skill materializes by exact digest and still passes ordinary Techtree scanning.
- [ ] Demo preparation shows policy and budget.
- [ ] First run starts detached and returns a run ID.
- [ ] Status works from terminal and gateway.
- [ ] Result returns deterministic local proof information.
- [ ] No handler uploads data.
- [ ] No host operator Skill enters Docker subject configuration.
- [ ] No Relay dependency exists.

---

# 8. Work Package 10 — Rich result experience and one-turn Skill revision

## 8.1 Objective

Complete the conversational product loop after WP9 by:

1. Showing the first controlled comparison clearly.
2. Using the founder-supplied `rich-terminal-output` Skill for one truthful explanatory host-model completion.
3. Producing gateway-safe compact output when the user is on a phone.
4. Building sanitized improvement context from the completed first run.
5. Using the founder-supplied `skill-improver` Skill for exactly one structured host-model completion.
6. Staging proposed Skill v2 through the ordinary Techtree scanner and archive path.
7. Showing a reviewable diff and second-run budget.
8. Requiring explicit approval.
9. Starting the Skill v1 versus Skill v2 controlled comparison.
10. Showing and verifying the second local Uplift receipt.

## 8.2 WP10 non-goals

WP10 does not:

- Optimize repeatedly.
- Search over many candidate Skills.
- Run SkillOpt.
- Automatically accept Skill v2.
- Automatically start the second run.
- Guarantee Skill v2 improves.
- Hide a negative or inconclusive result.
- Give hidden answers to the host model.
- Make presentation text part of signed proof.
- Upload presentation, proposal, Skill, or report.
- Add Relay.

## 8.3 Additional/modified plugin files

```text
techtree-hermes/
├── narrative.py
├── llm.py
├── guards.py
│
├── services/
│   ├── presentation.py
│   ├── improvement.py
│   └── proposal.py
│
├── tools/
│   └── uplift.py                # expanded
│
├── tests/
│   ├── unit/
│   │   ├── test_narrative.py
│   │   ├── test_llm.py
│   │   ├── test_guards.py
│   │   ├── test_presentation_service.py
│   │   ├── test_improvement_service.py
│   │   └── test_proposal_service.py
│   ├── contract/
│   │   ├── test_rich_skill_contract.py
│   │   └── test_improver_skill_contract.py
│   └── integration/
│       ├── test_first_result_explanation.py
│       ├── test_one_turn_revision.py
│       └── test_second_run_flow.py
```

Potential small CLI contract additions in `techtree-python` are allowed only when WP7 did not already expose the needed stable machine data:

```text
techtree run result <run-id> --json
techtree uplift context <run-id> --json
techtree uplift prepare <run-id> --skill <path> --json
techtree uplift start <draft-id> ... --json
techtree proof verify <path> --json
```

Do not create a parallel scientific implementation in the plugin.

---

## 8.4 Host LLM port

### `llm.py`

The plugin may use Hermes' documented host-owned one-shot LLM interface.

Define a narrow adapter:

```python
class HostLlmPort(Protocol):
    def complete_structured(
        self,
        *,
        system: str,
        user: str,
        schema: dict,
        purpose: str,
    ) -> dict:
        ...
```

Hermes implementation:

```python
class HermesHostLlm:
    def __init__(self, ctx) -> None: ...

    def complete_structured(...) -> dict:
        """Call ctx.llm.complete_structured exactly once."""
```

Rules:

- No automatic retry that makes a hidden second completion.
- Provider failure returns a typed error.
- Invalid structured output returns a typed error.
- User may explicitly request another attempt; that is a new action and, for the introductory demo, the revision limit still applies.
- Host model identity may be recorded in local operational metadata, never treated as subject identity.
- Host auth never becomes evaluation auth.

---

## 8.5 Founder Skill loading and digest verification

### `services/assets.py` extension

Functions:

```python
def load_bundled_skill_text(
    skill_name: Literal["rich-terminal-output", "skill-improver"],
) -> str:
```

```python
def bundled_skill_digest(skill_name: str) -> str:
```

```python
def verify_founder_skill_digests(release: ReleaseCore) -> None:
```

Release blocks when:

- File absent.
- Digest mismatch.
- Skill file empty.
- Skill exceeds reviewed size.
- Skill contains secret-like content.

These Skills are read-only and namespaced.

---

## 8.6 Rich presentation truth contract

### `narrative.py`

Functions:

```python
def build_presentation_input(
    *,
    deterministic_payload: dict,
    channel: ChannelKind,
) -> dict:
    """
    Construct the exact founder-Skill input. Exclude hidden material and
    include forbidden claims.
    """
```

```python
def presentation_output_schema() -> dict:
    """Return schema for PresentationNarrative without numeric truth fields."""
```

```python
def parse_presentation_narrative(value: dict) -> PresentationNarrative:
```

The output schema must not contain:

```text
baseline_score
candidate_score
absolute_delta
wins
losses
ties
proof_grade
status
receipt_digest
```

Those values always come from deterministic Techtree payload.

The host model may choose:

- A concise headline.
- Which verified observations deserve emphasis.
- Which verified caveat to foreground.
- A next-step explanation.
- References to allowed task labels.

It may not introduce scientific values.

---

## 8.7 Narrative guards

### `guards.py`

Functions:

```python
def validate_narrative(
    narrative: PresentationNarrative,
    *,
    allowed_task_refs: set[str],
    channel: ChannelKind,
) -> None:
```

```python
def forbid_unapproved_claims(text: str) -> None:
```

```python
def forbid_new_commands(text: str, allowed_commands: set[str]) -> None:
```

```python
def forbid_ansi(text: str) -> None:
```

```python
def forbid_secret_patterns(text: str) -> None:
```

```python
def bounded_narrative(narrative: PresentationNarrative) -> PresentationNarrative:
```

Forbidden claims include semantic equivalents of:

```text
independently reproduced
website verified the execution
sealed evaluation
Prime-hosted execution
training-ready data
guaranteed improvement
the agent universally learned the capability
```

If validation fails:

- Discard model-authored narrative.
- Return deterministic CLI/compact presentation.
- Record safe local diagnostic.
- Do not call the model again automatically.

---

## 8.8 Presentation service

### `services/presentation.py`

```python
class PresentationService:
    def __init__(
        self,
        *,
        llm: HostLlmPort,
        release: ReleaseCore,
    ) -> None: ...
```

Methods:

```python
def explain_result(
    *,
    result_envelope: dict,
    channel: ChannelKind,
) -> dict:
    """
    Return deterministic presentation plus optional validated narrative.
    Make exactly one host completion when enabled.
    """
```

```python
def deterministic_only(
    *,
    result_envelope: dict,
    channel: ChannelKind,
) -> dict:
```

```python
def merge_presentation(
    deterministic: dict,
    narrative: PresentationNarrative | None,
    channel: ChannelKind,
) -> dict:
```

### Terminal result ordering

The output order is mandatory:

```text
1. Deterministic Techtree score panel.
2. Controlled-change statement.
3. Proof and attestation status.
4. Model-authored narrative from rich-terminal-output, when valid.
5. Next actions.
```

The model-authored narrative never precedes the canonical numbers.

### Gateway result ordering

```text
1. Compact canonical score sentence.
2. Wins/losses/ties and controlled status.
3. P1 caveat.
4. Short validated narrative.
5. One next action.
6. Local proof path in a bounded monospace block when appropriate.
```

No ANSI.

---

## 8.9 Tool result integration

### `techtree_run_result` extension

Input adds:

```json
{
  "run_id": "run_...",
  "channel": "terminal|gateway|unknown",
  "include_host_explanation": true
}
```

Behavior:

1. Invoke deterministic CLI result.
2. Verify report/proof status.
3. Build channel-neutral presentation input.
4. When requested and host LLM available, call rich-output Skill once.
5. Guard output.
6. Return merged presentation.
7. Update `DemoSessionState`.

A result with invalid proof may still be inspected, but no rich positive framing is allowed. The response leads with verification failure.

---

## 8.10 Improvement context retrieval

### `services/improvement.py`

```python
class ImprovementService:
    def __init__(
        self,
        *,
        llm: HostLlmPort,
        release: ReleaseCore,
        temp_root: Path,
    ) -> None: ...
```

Methods:

```python
def get_context(source_run_id: str) -> dict:
    """Invoke `techtree uplift context` and validate its schema."""
```

```python
def load_source_skill(context: dict) -> str:
    """
    Read the Techtree-owned Skill v1 snapshot identified by the completed run.
    Do not expose its absolute path to the host model.
    """
```

```python
def build_improver_input(
    *,
    context: dict,
    source_skill_markdown: str,
) -> dict:
```

```python
def propose_once(
    *,
    source_run_id: str,
    demo_session: DemoSessionState,
) -> SkillRevisionOutput:
    """Make exactly one structured host-model completion."""
```

The context includes only policy-allowed material:

```text
first comparison summary
public task labels/hashes
outcome categories
public prompts when allowed
subject replies when allowed
reward values
public metrics
safe error summaries
cost/timing
source Skill text
mutation constraints
```

It excludes:

```text
expected answers
hidden task fields
hidden grader source
provider requests
API keys
Authorization headers
private keys
unredacted environment values
raw private paths
```

---

## 8.11 Exactly-one-turn rule

For the introductory demo:

```text
revision_attempts maximum = 1
```

`propose_once` must:

1. Check completed valid first run.
2. Check `revision_attempts == 0`.
3. Build one structured request.
4. Call host LLM exactly once.
5. Validate output.
6. Increment attempt count regardless of whether output later passes the Skill scanner.
7. Return failure without automatic retry when invalid.

Why count invalid output as the attempt:

- It preserves the promise of one agent reasoning turn.
- It avoids hidden multiple optimization attempts.
- It keeps demo costs predictable.
- A user may leave the guided demo and use lower-level manual tooling afterward.

No background self-improvement loop is created.

---

## 8.12 Skill revision output schema

The host model receives the founder Skill instructions and must return:

```json
{
  "analysis_summary": "...",
  "change_rationale": ["..."],
  "revised_skill_markdown": "# ...",
  "expected_tradeoffs": ["..."],
  "confidence": "low|medium|high"
}
```

Validation:

- Full revised `SKILL.md`, not a patch instruction.
- Non-empty.
- Below plugin temporary maximum.
- No NUL.
- No private key or token patterns.
- No obvious expected-answer table.
- No command or executable attachment.
- Confidence enum exact.
- Rationale bounded.

This validation is preliminary.

The authoritative Skill scanner remains the Techtree CLI.

---

## 8.13 Proposal staging

### `services/proposal.py`

```python
class ProposalService:
    def __init__(
        self,
        *,
        plugin_data_root: Path,
    ) -> None: ...
```

Methods:

```python
def write_temporary_skill(
    *,
    demo_id: str,
    output: SkillRevisionOutput,
) -> Path:
    """Write 0600 temporary SKILL.md under plugin-owned data."""
```

```python
def prepare_replacement_draft(
    *,
    source_run_id: str,
    skill_path: Path,
) -> dict:
    """
    Invoke ordinary `techtree uplift prepare`; Techtree snapshots, scans,
    hashes, compares, and creates the second draft.
    """
```

```python
def remove_temporary_skill(path: Path) -> None:
    """Remove plugin temp after Techtree snapshot succeeds or on session cleanup."""
```

```python
def validate_replacement_response(response: dict, source_run_id: str) -> None:
```

The prepared response must expose:

```text
proposal/draft ID
Skill v1 root digest
Skill v2 root digest
included files
unified line diff or bounded diff summary
scanner findings
controlled difference path
second-run episode count
maximum model/token budget
DataPolicy digest
confirmation token
```

The plugin stores no confirmation token after it is used.

---

## 8.14 Diff presentation

The user must see what changed before the second run.

Terminal:

- Unified diff with syntax highlighting when available.
- Added/removed line counts.
- Digests.
- Scanner result.
- Rationale and expected tradeoffs.
- Cost/policy summary.

Gateway:

- Total line changes.
- First bounded changed hunks.
- Explicit truncation notice.
- Skill v1 and v2 digests.
- Command/path to inspect full local diff in terminal.

The host model may summarize the diff but cannot hide or replace the deterministic diff summary.

---

## 8.15 Uplift proposal tool

### `techtree_uplift_propose`

New high-level plugin tool.

Input:

```json
{
  "source_run_id": "run_...",
  "channel": "terminal|gateway|unknown"
}
```

Behavior:

1. Require first result completed and locally verified.
2. Require source candidate Skill v1.
3. Require no prior guided revision attempt.
4. Build sanitized context.
5. Load and verify founder skill-improver file.
6. Make one structured host completion.
7. Validate proposal.
8. Write temporary Skill.
9. Invoke Techtree `uplift prepare`.
10. Delete temporary file after Techtree-owned snapshot is secure.
11. Update demo state.
12. Return deterministic diff, rationale, policy, budget, and explicit approval action.

No second run starts.

---

## 8.16 Second-run start

### `techtree_uplift_start`

Input:

```json
{
  "draft_id": "draft_...",
  "confirmation_token": "...",
  "data_policy_digest": "sha256:...",
  "channel": "terminal|gateway|unknown"
}
```

Behavior:

- Uses exact second draft.
- Requires policy acceptance again.
- Starts Skill v1 and Skill v2 concurrently through the same Techtree run service.
- Returns run ID.
- Updates demo session.
- Does not wait.

Presentation labels:

```text
baseline = Skill v1
candidate = Skill v2
```

The underlying scientific field difference remains the declared subject Skill.

---

## 8.17 Second result

`techtree_run_result` handles the second run using the same truth/presentation pipeline.

The result must clearly answer:

- Did Skill v2 beat Skill v1?
- How many tasks improved, regressed, or tied?
- Was the comparison controlled?
- Did token/time usage change?
- Is the local proof valid?
- Where are Skill v1, Skill v2, and both proof bundles stored?

It must not say Skill v2 improved when the report is rejected, inconclusive, or invalid.

A negative second result is a valid product outcome.

---

## 8.18 Demo-session progression

Allowed progression:

```text
PLUGIN_READY
  → CLI_INSTALL_REQUIRED | CLI_READY

CLI_READY
  → FIRST_DRAFT_PREPARED

FIRST_DRAFT_PREPARED
  → FIRST_RUN_ACTIVE

FIRST_RUN_ACTIVE
  → FIRST_RESULT_READY | FAILED | CANCELLED

FIRST_RESULT_READY
  → REVISION_PROPOSAL_READY

REVISION_PROPOSAL_READY
  → SECOND_DRAFT_PREPARED

SECOND_DRAFT_PREPARED
  → SECOND_RUN_ACTIVE

SECOND_RUN_ACTIVE
  → COMPLETE | FAILED | CANCELLED
```

State transitions are plugin UX conveniences and must be reconciled with CLI truth.

The plugin may not mark a result ready solely because its state says so.

---

## 8.19 WP10 terminal journey

From an interactive Hermes terminal/TUI:

```text
User:
  Set up Techtree and run the intro Skill Climb.

Hermes:
  Shows CLI installation plan if needed.

User:
  Approves install.

Hermes:
  Verifies CLI and Doctor.
  Prepares intro draft.
  Shows DataPolicy and budget.

User:
  Approves run.

Hermes:
  Returns run ID and tells the user how to watch.

User or `/techtree status`:
  Sees concurrent baseline/candidate progress.

Hermes:
  Shows deterministic Rich result.
  Uses rich-terminal-output Skill for one explanatory completion.

User:
  Try improving the Skill once.

Hermes:
  Uses skill-improver exactly once.
  Shows v1/v2 digests and diff.
  Shows second budget and policy.

User:
  Approves.

Hermes:
  Returns second run ID.
  Shows second result and proof path when requested.
```

---

## 8.20 WP10 phone/gateway journey

After the plugin is already installed and loaded:

```text
User:
  Set up Techtree and run the intro Climb.

Hermes:
  Shows pinned CLI install plan.

User:
  Approves through gateway-supported approval flow.

Hermes:
  Returns setup result and draft summary.

User:
  Approves DataPolicy and run.

Hermes:
  Returns run ID immediately.

User:
  Status?

Hermes:
  Returns compact progress.

User:
  Result?

Hermes:
  Returns compact canonical result plus validated short narrative.

User:
  Try improving it once.

Hermes:
  Returns bounded diff and second-run approval summary.

User:
  Approves.

Hermes:
  Returns second run ID.

User:
  Result?

Hermes:
  Returns compact second Uplift receipt and local proof path.
```

Phone requirements:

- No ANSI.
- No unbounded logs.
- No 20-row tables.
- No blocking gateway request for the full benchmark.
- No API key request in chat.
- Explicit approval remains required.
- Full diff and artifacts remain available locally.

---

## 8.21 WP10 tests

### Rich-output contract tests

- Founder Skill file digest matches release.
- Input contains only deterministic allowed facts.
- Output schema contains no numeric truth fields.
- One host completion only.
- Invalid output triggers deterministic fallback.
- Forbidden claims rejected.
- New commands rejected.
- ANSI rejected in gateway output.
- Unknown task refs rejected.

### Improvement-context tests

- Hidden expected answers absent.
- Hidden grader material absent.
- Secrets absent.
- Absolute paths absent.
- Regressions/failures prioritized.
- Source Skill text present only when policy permits.
- Context stays bounded.

### One-turn tests

- Exactly one host completion call.
- No automatic retry.
- Invalid structured output consumes guided attempt.
- Second proposal blocked in demo session.
- Low-level manual CLI remains unaffected.

### Proposal tests

- Temporary file mode is private.
- Techtree scanner is authoritative.
- Secret proposal blocked.
- Oversized proposal blocked.
- Post-scan mutation detected by Techtree snapshot path.
- Temporary file deleted after successful snapshot.
- Diff matches exact v1/v2 bytes.

### Second-run tests

- Baseline is Skill v1.
- Candidate is Skill v2.
- Only Skill field differs.
- Policy digest unchanged.
- Other Campaign fields unchanged.
- Concurrent schedule used.
- Result handles accepted/rejected/inconclusive.
- Second proof verifies locally.

### Gateway tests

- Compact response under configured character limit.
- No ANSI/control characters.
- Diff truncation explicit.
- Run ID always returned.
- Status is pull-based and bounded.

---

## 8.22 WP10 acceptance criteria

- [ ] Deterministic result is always shown before model-authored explanation.
- [ ] rich-terminal-output Skill is founder-supplied and digest-pinned.
- [ ] Model-authored narrative cannot alter scores or statuses.
- [ ] Invalid narrative falls back without retry.
- [ ] Gateway output is compact and ANSI-free.
- [ ] Improvement context contains no hidden verifier material.
- [ ] skill-improver Skill is founder-supplied and digest-pinned.
- [ ] Exactly one guided improvement completion is made.
- [ ] Skill v2 passes ordinary Techtree scanning/snapshotting.
- [ ] User sees a deterministic diff before second run.
- [ ] Second run requires explicit policy and budget approval.
- [ ] Skill v1 and Skill v2 run through the same controlled Campaign.
- [ ] Second local proof bundle verifies.
- [ ] Negative second result is represented honestly.
- [ ] No artifact is uploaded.
- [ ] No Relay dependency exists.

---

# 9. Work Package 11 — Cross-repository release hardening and install-from-zero acceptance

## 9.1 Objective

Turn the working code paths into one coherent, reproducible, supportable Climb v0.1 release across:

```text
techtree-python
techtree-hermes
techtree-ash
```

WP11 owns:

- Release artifact assembly.
- Cross-repository version binding.
- Package publication checks.
- Exact plugin install coordinates.
- Bootstrap release generation.
- Clean-machine terminal acceptance.
- Certified phone/gateway acceptance.
- Upgrade, disable, remove, and data-retention documentation.
- Failure injection and recovery.
- Privacy/no-upload verification.
- Final launch checklist.

## 9.2 WP11 non-goals

WP11 does not:

- Add new scientific features.
- Add a leaderboard.
- Add upload.
- Add remote evaluation.
- Add Relay.
- Add more than one guided revision attempt.
- Add more subject harnesses.
- Add private programs.
- Add training export.

No feature creep is accepted under “release hardening.”

---

## 9.3 Cross-repository release artifacts

### 9.3.1 `ReleaseCore`

Generated from frozen source inputs before CLI/plugin publication.

Contains:

```text
release ID
CLI version and source commit
protocol version
engine digest
catalog digest
intro Climb reference
starter subject Skill digest
rich-output Skill digest
skill-improver Skill digest
host Hermes compatibility range
subject Hermes version
```

Identical bytes are embedded in:

- `techtree-python` package.
- `techtree-hermes` plugin repository.
- WP8 catalog/release source where appropriate.

### 9.3.2 `BootstrapRelease`

Website-published wrapper generated after plugin commit and CLI wheel exist.

Contains:

```text
schema version
release ID
ReleaseCore digest
CLI distribution name
CLI version
CLI wheel filename and SHA-256
CLI package index/origin metadata
plugin repository
plugin full commit
minimum Hermes version
exact plugin install argv
exact CLI install argv
plugin doctor argv
website origin
intro Climb reference
starter Skill object URL/digest
starter prompt
reference DataPolicy digest
release documentation URLs
```

`BootstrapRelease` is read-only.

It does not contain a receipt-upload endpoint.

### 9.3.3 Cycle avoidance

Release generation order must avoid self-reference:

```text
1. Freeze source and founder Skills.
2. Generate ReleaseCore.
3. Embed ReleaseCore into techtree-python and techtree-hermes source.
4. Build and publish techtree-python wheel.
5. Commit/tag techtree-hermes; obtain full plugin commit.
6. Generate BootstrapRelease using ReleaseCore digest, wheel hash,
   and plugin commit.
7. Import/deploy BootstrapRelease and catalog into techtree-ash.
8. Run cross-repository verification.
9. Tag/deploy the web release.
```

The plugin does not embed `BootstrapRelease` digest.

It embeds `ReleaseCore` and verifies the website wrapper points to that core and its installed plugin commit.

---

## 9.4 Release file skeletons

### `techtree-python`

```text
release/
├── release-core.json
├── release-core.schema.json
├── build-info.json
└── README.md

tools/
├── build_release_core.py
├── verify_release_core.py
├── build_distribution.py
├── inspect_wheel.py
└── smoke_installed_cli.py

docs/release/
├── install.md
├── direct-cli.md
├── local-proof.md
├── privacy.md
├── troubleshooting.md
└── uninstall.md
```

### `techtree-hermes`

```text
release-core.json

tools/
├── verify_release_core.py
├── check_founder_skills.py
├── smoke_plugin_install.py
└── smoke_plugin_remove.py

docs/
├── install.md
├── terminal-demo.md
├── gateway-demo.md
├── approvals.md
├── privacy.md
├── troubleshooting.md
└── removal.md
```

### `techtree-ash`

```text
priv/releases/<release-id>/
├── bootstrap.json
├── bootstrap.schema.json
├── release-core.json
└── checksums.json

scripts/
├── build_bootstrap_release.exs
├── verify_bootstrap_release.exs
└── smoke_public_release.sh

docs/release/
├── runbook.md
└── rollback.md
```

No fourth repository is created.

---

## 9.5 `techtree-python` release commands

Add or freeze:

```bash
techtree release info --json --no-color --no-input
techtree release verify --expected <release-core-digest> --json --no-color --no-input
```

`release info` returns:

```text
CLI version
source commit
protocol version
ReleaseCore digest
engine digest
catalog digest
intro Climb reference
```

`release verify` checks:

- Embedded ReleaseCore bytes/digest.
- Installed package version.
- Managed engine digest.
- Catalog digest.
- Generated schemas/goldens where relevant.
- Reference Skill metadata.

It makes no model call.

---

## 9.6 Package publication requirements

### CLI wheel

- Built from clean tagged source.
- `uv lock` and generated files clean.
- Tests and type/lint gates green.
- Contains exact ReleaseCore.
- Contains no private keys or credentials.
- Contains no local absolute build paths in release metadata.
- Console scripts resolve.
- Fresh `uv tool install` works.
- `techtree release verify` passes after installation.
- Wheel SHA-256 recorded in BootstrapRelease.

### Plugin repository

- Exact full commit used in website command.
- `hermes plugins doctor . --ci` passes.
- Founder Skill digests match ReleaseCore.
- Runtime code has no third-party dependency beyond documented Hermes environment assumptions.
- Registration side-effect test passes.
- Plugin commit has no uncommitted/generated drift.

### Website release

- Serves exact BootstrapRelease bytes.
- Serves exact catalog/object bytes.
- Starter Skill digest matches ReleaseCore.
- No POST/mutation route introduced.
- Rollback can restore prior release atomically.

---

## 9.7 Compatibility matrix

Required v0.1 release matrix:

```text
Host operating systems:
  darwin/arm64
  darwin/amd64
  linux/amd64
  linux/arm64 where CI/host capacity permits

Python:
  version range supported by the CLI package
  managed engine pinned Python 3.12

Docker:
  Docker Desktop on macOS
  Docker Engine on Linux

Host Hermes:
  minimum version pinned by ReleaseCore
  current release-candidate version

Subject Hermes:
  exact version pinned by Campaign/engine

Channels:
  Hermes terminal/TUI
  one founder-selected REFERENCE_GATEWAY

Evaluation provider:
  Prime inference release profile
```

Each matrix row has:

```text
unit/contract status
installation status
Doctor status
first run status
second run status
proof verification status
known limitations
```

Unsupported combinations fail with actionable compatibility errors, not best-effort execution.

---

## 9.8 Clean-machine terminal acceptance

Use a clean user account or disposable machine with:

```text
Hermes installed
Techtree plugin absent
Techtree CLI absent
TECHTREE_HOME absent
Docker available
Prime authentication available
```

Required sequence:

1. Open the WP8 `/start` page.
2. Copy exact pinned plugin install command.
3. Install and enable plugin.
4. Restart/start Hermes.
5. Ask:

```text
Set up Techtree and run the introductory Skill Climb.
```

6. Confirm plugin does not silently install CLI.
7. Review CLI install plan.
8. Approve through normal Hermes approval.
9. Verify CLI release and Doctor.
10. Review Climb, DataPolicy, and budget.
11. Approve first run.
12. Observe baseline and Skill v1 active concurrently.
13. Close/reopen terminal while worker continues.
14. Reconnect and get status.
15. Read first deterministic Rich result.
16. Confirm rich-output Skill adds only guarded narrative.
17. Ask:

```text
Try improving the Skill once.
```

18. Confirm exactly one host model completion.
19. Review full/summary diff and v1/v2 digests.
20. Approve second run.
21. Observe Skill v1 and Skill v2 concurrently.
22. Read second result.
23. Verify second proof locally.
24. List local artifact paths.
25. Confirm no outbound upload request occurred.

Release evidence records command outputs and safe screenshots/logs without secrets or hidden answers.

---

## 9.9 Phone/gateway acceptance

Precondition:

- Plugin is installed and loaded on the Hermes host.
- Reference gateway is connected.
- User has no active SSH/terminal session during the conversational flow.

Required sequence:

1. Send setup/run request from phone.
2. When CLI missing, receive fixed installation summary.
3. Approve through the gateway-supported Hermes approval path.
4. Receive setup/Doctor outcome.
5. Receive first draft policy/budget summary.
6. Approve first run.
7. Receive run ID promptly.
8. Ask for status at least twice.
9. Receive bounded progress with no ANSI.
10. Receive compact first result.
11. Confirm local P1 caveat appears.
12. Ask for one improvement.
13. Receive bounded diff summary and exact digests.
14. Approve second run.
15. Receive second run ID.
16. Ask for status/result.
17. Receive compact second result and proof path.
18. Confirm no raw logs, hidden answers, or unbounded tables entered channel.
19. Confirm no website upload.

When the selected gateway cannot carry terminal approval prompts, the plugin must return manual installation instructions rather than install directly. The rest of the demo can still be gateway-driven after manual CLI installation.

---

## 9.10 Direct CLI fallback acceptance

The product remains usable without the Hermes plugin.

A release engineer must run:

```text
techtree setup / Doctor
climb list/show
starter Skill materialization
first prepare/start/status/result
proof verify
uplift context
manual Skill v2 file
second prepare/start/status/result
proof verify
```

This proves the plugin remains a thin convenience adapter.

---

## 9.11 Failure-injection matrix

Release tests must inject:

### Installation

- `uv` missing.
- CLI missing.
- Wrong CLI version already installed.
- CLI executable shadowed earlier on PATH.
- BootstrapRelease points to wrong ReleaseCore.
- Plugin commit mismatch.
- Wheel install interrupted.
- Plugin disabled after install.

### Prerequisites

- Docker CLI missing.
- Docker daemon stopped.
- Insufficient disk.
- Unsupported host architecture.
- Managed engine corrupt.
- Catalog object digest mismatch.
- Starter Skill digest mismatch.
- Prime authentication missing.

### First run

- One variant fails dry-run.
- One variant fails to launch.
- One variant provider call fails.
- User cancels.
- Terminal disconnects.
- Worker process killed.
- Partial `traces.jsonl`.
- Missing reward.
- Membership mismatch.
- Proof signing fails.

### Presentation

- Host LLM unavailable.
- Host LLM returns invalid JSON.
- Host LLM invents forbidden claim.
- Host LLM emits ANSI for gateway.
- Host LLM output too long.

### Improvement

- First result invalid.
- No failed examples.
- Improver output invalid.
- Proposed Skill contains secret.
- Proposed Skill exceeds limit.
- Proposed Skill unchanged from v1.
- User rejects diff.
- User attempts second guided revision.

### Second run

- Skill v2 loses.
- Skill v2 ties.
- One variant fails.
- Proof verification fails.

Every injected failure must produce:

```text
stable safe code
truthful state
retryability
repair action
no secret
no false proof
```

---

## 9.12 Security review

Review at minimum:

### Plugin supply chain

- Exact commit install.
- ReleaseCore digest.
- No auto-update.
- No arbitrary repo/ref from model.
- No plugin registration side effects.

### CLI installation

- Exact package/version.
- Fixed argv.
- Normal Hermes approval.
- Post-install release verification.
- No remote installer fallback.

### Command injection

- CLI calls use argv arrays.
- Bootstrap terminal dispatch contains only fixed release values.
- Slash-command grammar fixed.
- No arbitrary passthrough.
- No `shell=True` in plugin subprocess code.

### Secrets

- No API key in tool schema.
- No API key in chat requirement.
- Environment not logged.
- CLI stderr scrubbed.
- Host LLM input excludes secrets.
- Proposal scanner blocks secrets.

### Agent separation

- Host Skills never mounted into subject.
- Host model output cannot change manifests.
- Subject Skills always Techtree snapshots.

### Data rights

- Policy acknowledgement required twice.
- No upload client/path.
- Network tests assert no mutation request.
- Raw Episodes remain local.

### Proof honesty

- P1 means participant-attested local.
- Model narrative guard.
- Invalid proof blocks positive framing.
- No independent/website/Prime-hosted implication.

---

## 9.13 Privacy/no-upload verification

Use network instrumentation in E2E tests.

Allowed outbound destinations:

```text
public techtree.sh GET endpoints
package index during explicit CLI installation
Prime inference endpoint during declared evaluation
Hermes host model endpoint for ordinary operator completions
```

Forbidden:

```text
POST/PUT/PATCH receipt/report/proof/Skill/Episode/Trace to techtree.sh
undeclared analytics containing run data
third-party paste/log service
```

Test after both runs:

- Web application has no new submission/proof record.
- Network log contains no upload mutation.
- DataPolicy remains satisfied.
- Local artifacts exist.

---

## 9.14 Upgrade, disable, remove, and local-data behavior

Documentation must distinguish:

### Disable plugin

```bash
hermes plugins disable techtree
```

Does not delete:

- Techtree CLI.
- `~/.techtree` data.
- Runs/proofs/Skills.

### Remove plugin

```bash
hermes plugins remove techtree
```

Does not delete Techtree local data.

### Remove CLI

```bash
uv tool uninstall techtree
```

Does not delete `~/.techtree` unless user explicitly chooses to remove it.

### Upgrade

Pinned plugin releases do not silently move.

A new release provides:

- New exact plugin commit.
- New CLI version.
- New ReleaseCore.
- Migration compatibility statement.
- Explicit upgrade plan.

The plugin may offer an upgrade plan but may not auto-run it.

### Local data deletion

Provide a separate documented command or manual path.

Never delete local receipts/proofs merely because plugin or CLI is removed.

---

## 9.15 Documentation requirements

### Website `/start`

Must explain:

- One-time plugin install.
- Plugin then installs CLI only after approval.
- Docker prerequisite.
- Prime evaluation authentication.
- Estimated first-run cost/budget.
- Local P1 proof meaning.
- No upload.
- Phone path begins after plugin is installed/loaded.

### Plugin README

Includes:

- Exact install command template.
- Restart requirement.
- Supported Hermes versions.
- Setup prompt.
- Tool/approval behavior.
- Terminal and gateway walkthroughs.
- Privacy.
- Disable/remove instructions.

### CLI docs

Includes:

- Direct fallback.
- Local artifact layout.
- Proof verification.
- DataPolicy.
- Troubleshooting.

### Support runbook

Decision tree for:

```text
plugin absent/disabled
CLI absent/mismatch
uv absent
Docker unavailable
auth missing
run active/stale/failed
proof invalid
proposal invalid
gateway output truncated
```

---

## 9.16 Release observability

No user-run telemetry upload is required.

Local diagnostics may include:

```text
plugin log with safe codes
CLI worker log
run events
Doctor output
release compatibility report
```

Rules:

- Local only.
- Secret-scrubbed.
- No hidden answers in general support bundle.
- User explicitly chooses any future support export; not implemented in v0.1.

---

## 9.17 Calibration gate for introductory Climb

Before release, run the full first comparison repeatedly against the pinned release model/profile.

Required hard gates:

- Run completes reliably.
- Baseline and Skill v1 comparison remains controlled.
- Starter Skill v1 produces accepted uplift in the release certification runs.
- Proof verifies every time.
- Cost stays under published budget.

For the one-turn Skill v2:

Hard gates:

- Structured proposal is produced and scanned reliably.
- Second comparison completes.
- Proof verifies.
- Negative/tied results are rendered correctly.

Do **not** require Skill v2 to improve every time. The product must report the result honestly.

Track as a release-quality signal:

```text
fraction of certified runs where v2 beats v1
```

but do not alter or retry the user's one-turn proposal to force a positive result.

---

## 9.18 WP11 test and review gates

### Automated

```text
all three repository quality gates
generated-file drift checks
release-core equality checks
plugin doctor
fresh wheel install
fresh plugin clone/install fixture
website bootstrap verification
CLI/plugin contract suite
no-upload network assertions
failure-injection suite
```

### Live manual/scripted

```text
macOS Apple Silicon terminal flow
Linux host flow
reference phone gateway flow
terminal disconnect recovery
plugin disable/remove
CLI uninstall with data retained
```

### Founder acceptance

Founder confirms:

- Starter Skill v1 content.
- rich-terminal-output Skill content.
- skill-improver Skill content.
- Reference gateway.
- Release model/profile and budget.
- Website copy.
- License choices for each repository.

---

## 9.19 WP11 acceptance criteria

- [ ] ReleaseCore bytes are identical across CLI and plugin.
- [ ] BootstrapRelease points to exact ReleaseCore, wheel, and plugin commit.
- [ ] Fresh `uv tool install` produces a verified CLI.
- [ ] Exact plugin install and Doctor pass.
- [ ] Intro starter Skill digest matches release.
- [ ] Founder Skills digests match release.
- [ ] Clean-machine terminal flow completes both comparisons.
- [ ] Reference phone gateway completes the conversational flow after plugin bootstrap.
- [ ] Terminal loss does not kill run worker.
- [ ] All approval boundaries remain explicit.
- [ ] First proof verifies locally.
- [ ] Second proof verifies locally.
- [ ] Accepted, rejected, and inconclusive presentations are tested.
- [ ] No upload request occurs.
- [ ] Disable/remove/uninstall behavior is documented and tested.
- [ ] Privacy/security review is complete.
- [ ] No Relay dependency exists.

---

# 10. Whole v0.1 conversational state machine

The host-agent experience is not the scientific state machine. It is an orchestration projection over CLI truth.

## 10.1 Bootstrap

```text
plugin loaded
    ├── CLI compatible → ready
    ├── CLI absent → install plan
    ├── uv absent → manual prerequisite
    └── CLI mismatch → explicit upgrade/repair plan
```

## 10.2 First run

```text
ready
  → starter Skill materialized
  → first draft prepared
  → user reviews policy/budget
  → first run started
  → run active
  → first report verified
  → deterministic result shown
  → optional guarded host explanation
```

## 10.3 Revision

```text
first report verified
  → sanitized context
  → one host completion
  → proposed Skill v2
  → Techtree scan/snapshot
  → diff shown
  → user reviews policy/budget
  → second run started
  → second report verified
  → deterministic result shown
  → optional guarded host explanation
  → demo complete
```

## 10.4 Disallowed automatic transitions

Never automatically transition:

```text
install plan → installed
prepared draft → run started
first result → Skill proposal
Skill proposal → second run started
invalid proof → positive result explanation
second result → another proposal
```

---

# 11. Exact tool-call sequence for the introductory demo

A conforming Host Hermes interaction should approximate:

```text
User asks for setup/demo

1. techtree_bootstrap_check
2. [when needed] techtree_bootstrap_install after approval
3. techtree_system_check
4. techtree_demo_prepare

User approves DataPolicy/budget

5. techtree_climb_start
6. techtree_run_status ... as requested
7. techtree_run_result
8. techtree_proof_verify

User asks for one improvement

9. techtree_uplift_propose

User approves diff/policy/budget

10. techtree_uplift_start
11. techtree_run_status ... as requested
12. techtree_run_result
13. techtree_proof_verify
```

The agent may call `climbs_list` or `climb_inspect` for explanation, but it should not need terminal/docker commands.

---

# 12. Required error taxonomy for WP9–WP11

Add stable plugin/release errors:

```text
plugin_release_core_invalid
plugin_release_core_mismatch
plugin_state_corrupt
uv_not_found
techtree_cli_not_found
techtree_cli_release_mismatch
bootstrap_install_plan_missing
bootstrap_install_plan_expired
bootstrap_install_not_approved
bootstrap_terminal_tool_unavailable
bootstrap_install_failed
bootstrap_post_install_verify_failed
bootstrap_release_mismatch
starter_skill_missing
starter_skill_digest_mismatch
founder_skill_missing
founder_skill_digest_mismatch
channel_invalid
channel_ansi_forbidden
cli_output_invalid
cli_output_too_large
cli_timeout
cli_stderr_unsafe
host_llm_unavailable
host_llm_output_invalid
presentation_claim_forbidden
presentation_output_too_large
improvement_context_invalid
improvement_context_forbidden_material
improvement_attempt_already_used
skill_revision_output_invalid
skill_revision_secret_detected
skill_revision_unchanged
skill_revision_prepare_failed
demo_session_not_found
demo_stage_invalid
reference_gateway_unsupported
release_core_drift
bootstrap_release_drift
no_upload_invariant_failed
```

Each error contains:

```text
code
safe message
retryable
safe details
one or more NextAction entries when repair exists
```

Never include:

- Secret values.
- Raw Authorization headers.
- Private key bytes.
- Hidden expected answers.
- Raw provider request bodies.
- Full environment dumps.

---

# 13. Cross-work-package test matrix

| Capability | Unit | Contract | Integration | Live release |
|---|---:|---:|---:|---:|
| Plugin registration | ✓ | Hermes Doctor | ✓ | ✓ |
| CLI bootstrap plan | ✓ | fixed argv | fake terminal | clean host |
| CLI release verification | ✓ | ReleaseCore | fresh install | clean host |
| Doctor | existing | CLI JSON | plugin bridge | clean host |
| Starter Skill | digest | catalog object | materialize/scan | live |
| First prepare/start | existing | plugin schemas | real CLI | live model |
| Concurrent first run | WP6 | result schema | live/mock | live model |
| First proof | WP7 | proof schema | offline verify | live |
| Rich narrative | ✓ | founder Skill contract | fake host LLM | live host LLM |
| Gateway compact output | ✓ | no ANSI | gateway fixture | reference gateway |
| Improvement context | WP7 | no hidden material | plugin bridge | live |
| One-turn revision | ✓ | one-call assertion | fake host LLM | live host LLM |
| Skill v2 scan/diff | ✓ | CLI envelope | real CLI | live |
| Concurrent second run | WP6/WP7 | replacement schema | mock/live | live model |
| Second proof | WP7 | proof schema | offline verify | live |
| No upload | ✓ | route absence | network capture | live |
| Remove/uninstall | ✓ | docs/argv | disposable home | release host |

---

# 14. Dependency graph and ticket split

## 14.1 Package dependencies

```text
WP8 bootstrap/catalog stable
WP7 result/context/replacement/proof stable
        ↓
WP9 Hermes plugin/bootstrap
        ↓
WP10 rich explanation and one-turn revision
        ↓
WP11 cross-repository release hardening
```

WP11 release tooling can begin in parallel after release schemas are frozen, but final integration waits for WP9 and WP10.

## 14.2 Recommended WP9 tickets

```text
WP9a — Plugin repository/tooling, manifest, registration, and Doctor
WP9b — ReleaseCore, CLI bridge, and strict envelope contract
WP9c — Explicit bootstrap/install approval and post-install verification
WP9d — Catalog/demo/run/proof tool handlers and plugin state
WP9e — Slash commands, Hermes CLI commands, operator Skill, and gateway-safe output
```

## 14.3 Recommended WP10 tickets

```text
WP10a — HostLlmPort and founder-Skill digest contracts
WP10b — Rich-output presentation service and narrative guards
WP10c — Sanitized improvement context and exactly-one-turn proposal
WP10d — Proposal staging, scan, deterministic diff, and second-run approval
WP10e — Skill v1 → Skill v2 orchestration and terminal/gateway presentation
```

## 14.4 Recommended WP11 tickets

```text
WP11a — ReleaseCore generation and cross-repo equality
WP11b — CLI wheel/package release and fresh-install verification
WP11c — Plugin exact-commit release and bootstrap wrapper
WP11d — Ash BootstrapRelease deployment and rollback
WP11e — Clean-machine terminal E2E and failure injection
WP11f — Reference gateway E2E and channel hardening
WP11g — Security/privacy/no-upload review
WP11h — Documentation, uninstall/upgrade runbooks, and founder launch gate
```

## 14.5 File ownership

Single-owner generated files:

```text
ReleaseCore
BootstrapRelease
CLI wheel checksums
plugin skill digests
catalog release
JSON schemas
release docs command snippets
```

No concurrent worker edits them without chief coordination.

---

# 15. Definition of done for Climb v0.1

Climb v0.1 is done only when every statement below is true.

## 15.1 Installation

- [ ] Website gives an exact full-commit plugin command.
- [ ] Plugin installs/enables through official Hermes plugin management.
- [ ] Plugin registration performs no CLI installation.
- [ ] Host Hermes can present a pinned CLI installation plan.
- [ ] Human approval is required.
- [ ] CLI installation is verified against ReleaseCore.
- [ ] Missing `uv` does not trigger an automatic remote installer.

## 15.2 Prerequisites

- [ ] Doctor verifies CLI, engine, Docker, catalog, host platform, and evaluation auth.
- [ ] Host Hermes auth and evaluation auth are distinguished.
- [ ] No API key is requested through model-visible tool arguments.

## 15.3 First comparison

- [ ] Starter Skill v1 is exact and content-addressed.
- [ ] Starter Skill passes ordinary scanning/snapshotting.
- [ ] User sees DataPolicy and maximum budget.
- [ ] User explicitly approves.
- [ ] No-Skill and Skill v1 execute concurrently.
- [ ] Both subjects are clean Docker Hermes instances.
- [ ] Verifiers is sole score truth.
- [ ] Only subject Skill differs.
- [ ] Local receipts/report/proof are built and signed.
- [ ] Proof verifies offline.

## 15.4 First result UX

- [ ] Terminal displays deterministic Rich result.
- [ ] Phone displays bounded ANSI-free result.
- [ ] rich-terminal-output Skill is used through its guarded contract.
- [ ] Model-authored explanation cannot change scientific values.
- [ ] P1 limitations are explicit.

## 15.5 One-turn revision

- [ ] User explicitly requests improvement.
- [ ] Context contains no hidden verifier material.
- [ ] Founder skill-improver is loaded by exact digest.
- [ ] Exactly one host-model completion occurs.
- [ ] Skill v2 is a full reviewable SKILL.md proposal.
- [ ] Techtree scans/snapshots Skill v2.
- [ ] User sees exact digests and diff.
- [ ] No automatic second run.

## 15.6 Second comparison

- [ ] User sees second DataPolicy and budget approval.
- [ ] Skill v1 and Skill v2 execute concurrently.
- [ ] Only subject Skill differs.
- [ ] Report truthfully handles win, tie, loss, invalid, or inconclusive.
- [ ] Second local proof verifies.
- [ ] Local paths for both Skills and both proof bundles are available.

## 15.7 Phone and terminal

- [ ] Terminal/TUI journey passes from clean host.
- [ ] Reference phone gateway journey passes after plugin bootstrap.
- [ ] Long runs return IDs and survive terminal/session loss.
- [ ] Phone status is bounded and pull-based.
- [ ] No ANSI reaches gateway.

## 15.8 Privacy and scope

- [ ] No receipt/report/proof/Skill/Episode/Trace is uploaded.
- [ ] Website has no upload route.
- [ ] Network capture confirms no mutation upload.
- [ ] No Relay dependency exists.
- [ ] No SkillOpt loop exists.
- [ ] No public leaderboard submission exists.

## 15.9 Release

- [ ] ReleaseCore matches CLI and plugin.
- [ ] BootstrapRelease matches wheel and plugin commit.
- [ ] Clean generated state.
- [ ] Full quality gates green.
- [ ] Security/privacy review complete.
- [ ] Founder-owned Skills and release coordinates approved.
- [ ] Install, troubleshooting, removal, and local-data docs published.

---

# 16. Instructions for the chief-of-staff agent

Treat this document as the binding implementation specification for the remaining Climb v0.1 packages after WP8.

Create three Work Package epics:

```text
WP9  Hermes operator plugin and explicit CLI bootstrap
WP10 Guided result explanation and one-turn Skill revision
WP11 Cross-repository release hardening
```

Create the ticket slices in §14.

Before dispatching workers:

1. Read all existing decision documents and the committed WP6–WP8 specification.
2. Verify the committed CLI result/context/start contracts before writing plugin assumptions into tickets.
3. Record any additive CLI-envelope field as a compatibility decision; do not silently fork the contract.
4. Obtain founder-supplied Skill files before marking WP10 release-ready.
5. Keep plugin runtime code independent of Techtree Python imports.
6. Keep scientific behavior in Techtree, not the plugin.
7. Keep host LLM calls to exactly the defined one-shot purposes.
8. Keep every install command fixed and approval-bearing.
9. Keep website mutation/upload out of scope.
10. Keep Relay deferred.

Required chief gatekeeping rules:

```text
No worker may let the plugin install during register().
No worker may pass arbitrary shell/model input into installation.
No worker may put scores in model-authored output schemas.
No worker may auto-retry the guided improvement turn.
No worker may start the second run without displaying the diff and policy.
No worker may call a local P1 result independently reproduced.
No worker may add an upload endpoint “for later.”
```

Recommended parallelism:

```text
After WP8/WP7 contracts are stable:
  Thread A — WP9 plugin foundation/bridge
  Thread B — WP11 ReleaseCore tooling skeleton
  Thread C — founder-Skill contract fixtures/tests

Then:
  WP9 bootstrap and tool surface
  WP10 presentation and improvement in parallel where file scopes permit
  WP11 integration after both land
```

---

# 17. Post-v0.1 deferred packages

The following are explicitly deferred and must not be smuggled into WP9–WP11:

## WP12 — Optional NeMo Relay runtime evidence

Potential later scope:

```text
subject Relay enablement
ATOF/ATIF collection
Trace-to-Relay binding
runtime-evidence completeness
proof-grade strengthening
```

## Later Climb versions

```text
other subject harnesses
other mutation lanes
independent reproduction
Prime-hosted execution
sealed tasks
public proof upload
leaderboards
network incentives
```

## Other Techtree modes

```text
ImprovementProgram
Blueprint
private Verify/release gates
Forge qualification
SkillOpt/optimizer loops
TraceSet/training readiness
Prime Lab handoff
```

Those later modes wrap and reuse the Campaign/execution/receipt kernel; they do not redefine Climb v0.1.

---

# 18. Final product statement

At the end of WP11, Climb v0.1 is one small, complete, honest improvement loop:

> A person installs one pinned Hermes plugin, then talks to their ordinary Hermes agent from a terminal or phone. With explicit approval, the plugin installs and verifies Techtree, prepares a public introductory Climb, and launches a clean no-Skill subject and a clean Skill-enabled subject concurrently. Verifiers supplies the reward truth; Techtree proves that only the Skill changed and creates a signed local Uplift receipt. The result is shown clearly through deterministic Rich or compact output and a guarded founder-supplied explanation Skill. The user may then request exactly one revision; a founder-supplied improvement Skill drives one host-model completion, Techtree shows and scans the proposed Skill v2, and—only after another explicit approval—runs Skill v1 against Skill v2. The second local proof is verified and retained on the user's machine. Nothing is uploaded to the website.

That is the Climb v0.1 release boundary.
