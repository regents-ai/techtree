# 0003 — Round-two binding amendments to the WP0–WP5 spec

Status: binding. These amend `docs/spec/climb-v0.1-wp0-wp5.md`. Where this
document and the spec conflict, this document wins. Read together with
decisions 0001 and 0002.

## A1. Deterministic validation receipt vs. operational execution record

The scientific result and the operational execution record are SEPARATE
objects.

### Revised `TasksetValidationReceipt` (deterministic; replaces spec §11.9)

```python
class ValidationMethod(ProtocolModel):
    kind: Literal["verifiers_validate"]
    mode: Literal["all"]
    runtime: Literal["subprocess"]
    validator_revision: str

class TasksetValidationReceipt(ProtocolModel):
    schema_version: Literal["techtree.taskset-validation.v1alpha1"]
    taskset_lock_digest: Digest
    engine_digest: Digest
    method: ValidationMethod
    status: Literal["valid", "invalid", "errored"]
    upstream_summary: UpstreamValidationSummary
    checks: list[ValidationCheck]
    normalized_evidence: ArtifactRef | None
```

REMOVED from the receipt: `id`, `created_at`, raw artifact list, durations,
absolute paths, tracebacks, raw log references. The receipt's content digest
is its identity. A display id `validation_<first 24 hex of digest>` may be
derived but is never stored inside the receipt.

### New local operational object

```python
class ValidationExecutionRecord(StateModel):
    schema_version: Literal["techtree.validation-execution.v1alpha1"]
    id: str
    receipt_digest: Digest
    started_at: datetime
    finished_at: datetime
    command: list[str]
    command_digest: Digest
    host_platform: str
    worker_pid: int | None
    raw_artifacts: list[ArtifactRef]
```

Local operational provenance only: not part of the Campaign graph, never
referenced by the public Climb, never the publisher commitment, never in
byte-for-byte generated-fixture checks.

### Normalized validation evidence

The publisher builder transforms raw Verifiers outputs into a deterministic
`validation-evidence.json`:

```json
{
  "schema_version": "techtree.validation-evidence.v1alpha1",
  "taskset_lock_digest": "sha256:...",
  "method": {"kind": "verifiers_validate", "mode": "all",
             "runtime": "subprocess", "validator_revision": "7e1c47d..."},
  "tasks": [
    {"position": 0, "task_hash": "sha256:...",
     "gold": {"valid": true, "reason": "valid"},
     "setup": {"valid": true, "reason": "valid"}}
  ],
  "summary": {"total": 20, "valid": 20, "invalid": 0, "error": 0,
              "timeout": 0, "missing": 0}
}
```

Normalization removes: elapsed, wall-clock timestamps, temp paths, run
UUIDs, PIDs, hostnames, absolute output dirs, log prefixes, tracebacks on
successful validation. Tasks sorted by `position`.
`TasksetValidationReceipt.normalized_evidence` references this shipped
artifact.

### Consequences

- Expected equality for the pure reference Taskset:
  publisher receipt digest == local receipt digest (given matching engine
  digest, taskset lock, method, and normalized results). This REPLACES the
  spec sentence saying local/publisher digests may differ.
- The raw `ValidationExecutionRecord` differs per run; that is fine.
- `make generated-check` byte-compares: engine bundle, engine lock,
  TasksetLock, normalized validation evidence, TasksetValidationReceipt,
  DataPolicy, CampaignSpec, ClimbManifest, catalog index, goldens, schemas.
  It does NOT byte-compare: ValidationExecutionRecord, raw validate.log,
  raw results.jsonl, raw config.toml, worker logs — those are execution
  outputs, not generated source fixtures.

## A2. PR4 catalog bootstrap: no placeholder scientific graph

- PR4A (early): catalog models, repository, content-addressed loading,
  digest verification, graph resolution, cross-object validation,
  CatalogService, ClimbSummary, CompatibilityResult, CLI list/show — tested
  against a COMPLETE synthetic fixture graph at
  `tests/fixtures/catalog/complete/` (deterministic synthetic objects,
  contract-test only).
- The PACKAGED catalog ships valid and EMPTY until the real generation
  chain exists:
  `{"schema_version": "techtree.catalog.v1alpha1", "climbs": [], "objects": {}}`
  `techtree climb list` then correctly reports no embedded Climbs in this
  development build, with a suitable next action.
- PR4B (with PR12): the generator replaces the empty catalog with the real
  procedure-transfer-dev@1 graph (real engine digest, package digest,
  ordered hashes, membership digest, publisher TasksetLock, normalized
  evidence, publisher receipt, DataPolicy, CampaignSpec, ClimbManifest).
- NEVER ship hand-authored placeholder hashes or a pretend publisher
  receipt in package resources.

## A3. Engine helpers live inside the digested engine bundle

Remove `src/techtree/resources/engine_scripts/`. Revised bundle layout:

```text
resources/engines/default/
├── engine.json
├── pyproject.toml
├── uv.lock
├── tools/
│   ├── inspect_taskset.py
│   └── normalize_validation.py
└── packages/
    └── procedure-transfer-v1/
```

Both helpers are part of `engine_bundle_digest`, copied unchanged into the
installed engine, and invoked as
`<engine-python> <engine-root>/tools/<helper>.py ...` — never from the CLI
package. Host-side Techtree still launches the helper, parses typed output,
recomputes the membership digest, and compares with the Campaign. Add
`EngineRegistry.tool_path(digest, tool) -> Path` (or equivalent).

## A4. No dangling artifact references in the public catalog

Every referenced artifact is resolvable through the catalog object map, or
it is not referenced. v0.1 ships: TasksetValidationReceipt +
validation-evidence.json. NOT shipped/referenced publicly: validate.log,
raw results.jsonl, raw config.toml, temp paths, publisher worker log,
publisher ValidationExecutionRecord (those live in release-engineering/CI
storage or the build dir only).

## A5. Policy acceptance vs. acknowledgement

Split the concepts.

In `SubmissionDraft` (replaces PolicyAcknowledgement there):

```python
class PolicyAcceptanceRequirement(ProtocolModel):
    data_policy_digest: Digest
    required: bool          # true for every v0.1 public Climb
    summary: str            # stable human-readable rights summary
```

Field name: `policy_acceptance`.

In `RunRequest` (new):

```python
class PolicyAcknowledgement(ProtocolModel):
    data_policy_digest: Digest
    method: Literal["interactive_cli", "explicit_cli_digest",
                    "host_agent_confirmation"]
    acknowledged_at: datetime
```

Field name: `policy_acknowledgement`.

CLI behavior:
- Interactive: `climb start` shows the policy summary and asks
  `Accept DataPolicy sha256:...? [y/N]` → method `interactive_cli`.
- Machine (`--no-input`): possession of the confirmation token NEVER
  implies acceptance. Require
  `--accept-data-policy sha256:<exact-policy-digest>` matching
  `draft.data_policy_digest` exactly → method `explicit_cli_digest`.

## A6. Typed catalog/compat models (new file `models/catalog.py`)

```python
class CompatibilityIssue(ProtocolModel):
    code: str
    severity: Literal["warning", "error"]
    message: str
    blocking: bool          # CLI translates issues into NextActions

class EngineCompatibilityStatus(str, Enum):
    UNKNOWN = "unknown"
    NOT_INSTALLED = "not_installed"
    INSTALLED_UNVERIFIED = "installed_unverified"
    VERIFIED = "verified"

class CompatibilityResult(ProtocolModel):
    compatible: bool        # true only when no blocking issues
    host_platform: str
    host_supported: bool
    required_engine_digest: Digest
    engine_status: EngineCompatibilityStatus
    evaluation_backend_kind: EvaluationBackendKind
    evaluation_backend_supported: bool
    issues: list[CompatibilityIssue]

class DataPolicySummary(ProtocolModel):
    raw_episode_server_upload: Literal["allowed", "prohibited",
                                       "consent_required"]
    raw_episode_training_use: Literal["allowed", "prohibited",
                                      "consent_required"]
    candidate_skill_public_release: Literal["required_for_climb", "allowed",
                                            "prohibited", "consent_required"]
    uplift_report_visibility: Literal["public", "private", "prohibited"]

class ClimbSummary(ProtocolModel):
    reference: str
    climb_digest: Digest
    campaign_spec_digest: Digest
    title: str
    summary: str
    status: Literal["open", "closed", "development"]
    purpose: str
    taskset_id: str
    task_count: int
    subject_harness: str
    subject_harness_version: str
    mutation_kind: Literal["skill_insertion"]
    candidate_skill_visibility: Literal["public", "private"]
    evaluation_backend: EvaluationBackendKind
    proof_grade: Literal["development_only", "P1"]
    data_policy: DataPolicySummary
    compatibility: CompatibilityResult
```

Before WP4, an absent engine is a blocking issue for `prepare` while
`list`/`show` still display the Climb.

## A7. Catalog index is typed and schema'd

Also in `models/catalog.py`:

```python
class CatalogClimbEntry(ProtocolModel):
    reference: str
    digest: Digest
    path: str

class CatalogObjectLocation(ProtocolModel):
    kind: Literal["campaign", "data_policy", "taskset_validation",
                  "validation_evidence"]
    path: str
    media_type: str

class CatalogIndex(ProtocolModel):
    schema_version: Literal["techtree.catalog.v1alpha1"]
    climbs: list[CatalogClimbEntry]
    objects: dict[Digest, CatalogObjectLocation]
```

Validation: unique climb references and digests; relative paths only; no
traversal; no conflicting digest→path mappings; every listed path exists;
loaded file digest matches its index digest; object kind matches the
requested model. The generator owns catalog.json — never hand-edit.

Add schemas: `catalog.schema.json`, `climb-summary.schema.json`,
`compatibility-result.schema.json`.

## A8. `resolved_package_digest` semantics (embedded kind)

Deterministic digest of the SOURCE package tree in the engine bundle (not
wheel bytes, not site-packages). Include `pyproject.toml`,
`procedure_transfer_v1/**/*.py`, declared runtime package data. Exclude
caches/VCS/venv/build artifacts. Build a canonical manifest
(`techtree.package-content.v1`: sorted files with path/size/digest) and
digest it. Required triple equality:

```text
Campaign.taskset.ref.package.digest
  == EngineDescriptor.packages[procedure-transfer-v1].source_digest
  == TasksetLock.resolved_package_digest
```

Install the reference package as an editable path dependency inside the
managed engine (`[tool.uv.sources]` path + editable), and have engine
verification confirm the imported module's `__file__` resolves inside the
engine package root. Do not generalize wheel/hub semantics in WP0–WP5.

## A9. `supported_hosts` vocabulary

Go/OCI-style normalized strings only: `darwin/arm64`, `darwin/amd64`,
`linux/arm64`, `linux/amd64`. Provide
`normalize_host_platform(sys_platform, machine) -> str` (darwin/linux;
arm64|aarch64 → arm64; x86_64|amd64|AMD64 → amd64; unsupported combos raise
a typed compatibility error). Initial descriptor lists all four. Engine
host platform and Docker subject platform share the vocabulary but are
separate concepts; Doctor displays both when relevant.

## Revised blocking rules

```text
WP0–WP3: proceed with these model corrections
PR4A:    proceed with empty packaged catalog + complete injected fixture
PR4B:    waits for the PR9–PR12 generation chain (delivered with PR12)
WP4:     still requires PI0 (done)
WP5:     still requires PI0 + verified engine
Hermes plugin / Ash website / Relay: still deferred
```
