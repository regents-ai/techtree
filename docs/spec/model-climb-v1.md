# Model Climb v1 — contract

**Status:** draft for M0. Nothing here is implemented, released or approved to spend.
**Feature:** `model-climb-v1`, versioned apart from Techtree releases.
**Schema namespace:** `techtree.model-climb.v1alpha1`.
**Source:** the founder's engineering specification of 12 Oct 2026 ("Techtree Model Climb — Private fine-tuning, evaluation, and serving"). This document fixes the parts every repository must agree on: objects and digests, operations, errors, states, grants, the M0 compatibility profile and its test. Rationale and product scope stay in the specification.

## 1. Baseline

| Repository | Reference |
|---|---|
| `regents-ai/techtree` | `main` 60efb02dc1e3415b31bbfc1959f95eca9588d0e6 |
| `regents-ai/regents-cli` | `main` d7deae0679f003b43933c9a2d41a7af949cf40a8 (CLI 1.9.1) |

Each implementation pins its own baseline when it starts and rechecks this contract against it.

## 2. Ownership

| Part | Owner | Lives in |
|---|---|---|
| This contract and the native command descriptions | Techtree | `docs/spec/model-climb-v1.md`, `cli/COMMANDS.md` |
| Signed HTTP command descriptions | Techtree | `cli/commands.json` names no Model Climb path until the site's routes exist (M3) |
| Field-level schemas: one Pydantic model per `kind`, exported as JSON Schema | regents-cli, reviewed by Techtree | `src/regents_cli/techtree/model_climb/contracts.py` and its export, pinned in section 3.2 by sha256 |
| Engine: data releases, plans, grants admission, trainer/evaluator/serving adapters, attempts, reports, proof verification | regents-cli | `src/regents_cli/techtree/model_climb/`, `commands/model_climb.py` |
| Private workspace records, approvals, intents, runner leases, pages | Techtree | `platform/lib/techtree/model_climb/`, `platform/lib/techtree_web/live/model_climb_live/` |
| Browser agent tools | Techtree | `platform/priv/tool_manifest.json`, `platform/assets/js/model_climb_tools.ts` |
| Employee Skill | Techtree | `plugin/skills/fine-tune-and-serve-llm/` |
| ChatGPT/Codex package | Techtree | `integrations/openai/` |
| Delegated-client (OAuth) authentication, shared nested input validation for WebMCP | ash-template and the shared library first; Techtree consumes the pin | — |

The existing `regents techtree model` group (ChatGPT plan sign-in) is unchanged. Model Climb is the new group `regents techtree model-climb`.

## 3. Objects and digests

### 3.1 Encoding

- Canonical bytes are RFC 8785 JSON produced by regents-cli `techtree/canonical.py`. Digests are `sha256:<64 hex>` from the same module. No second canonicalizer.
- Every scientific object has exactly three top-level members besides `schema_version` and `kind`:
  - `spec`: everything that defines the science. The object's digest is the digest of `{schema_version, kind, spec}`.
  - `operational`: storage handles, timestamps, provider job ids, hostnames, ports. Never digested, never compared.
  - `digest`: the computed digest, checked on read.
- An object names another only by that object's digest. A read recomputes the digest and refuses an object whose stored `digest` does not match.
- `operational` is a closed set of fields declared per `kind` in the schema, never free-form. A field belongs to `spec` or `operational` by the schema, never by the producer's choice. Changing any `spec` field makes a new object with a new digest; objects are never edited in place.

### 3.2 Objects

| `kind` | `spec` must contain | Refers to |
|---|---|---|
| `ModelStudySpec` | workspace, task kind, hypothesis, allowed mutation (`model_weights` only in v1), baseline model, harness profile digests (prompt, output schema, decision policy), selection rule, metrics with constraints, budgets, data policy | `DatasetRelease`, `BenchmarkRelease` |
| `DatasetRelease` | snapshot digest, source lineage, rights class, row schema, transformation digest, feature cutoff rule, label policy, duplicate-cluster rule, split membership commitments (train, validation, proving, optional debug), exclusion counts by reason | source snapshot |
| `BenchmarkRelease` | verifier/environment refs, sealed proving membership commitment, output schema, sampling protocol, scorer test digest, qualification report digest | `DatasetRelease` |
| `TrainingRecipe` | trainer revision and lock digest, image digest, model revision, renderer, loss mask, LoRA config including the full target list, optimizer, seed, batch/context/step limits, checkpoint selection rule | — |
| `ResolvedModelPlan` | every input digest above, compute target (provider, mission, GPU model and count), approved egress list, compatibility profile digest, budget reservation, expiry | all of the above |
| `ModelArtifact` | base weights root, adapter root, adapter config, tokenizer and config refs, optional merged weights, derivation (plan + attempt), licence, privacy class | `ResolvedModelPlan`, `TrainingAttempt` |
| `TrainingAttempt` | run and attempt ids, observed resolved config digest, steps and tokens, checkpoint refs, exit reason, measured cost, predecessor attempt and whether optimizer/RNG state was restored | `ResolvedModelPlan`, the predecessor `TrainingAttempt` when there is one |
| `ModelUpliftReport` | native evaluator output refs, paired outcomes, uncertainty method and result, comparison validity, the six result fields (3.3), limitations | `ModelArtifact`, `BenchmarkRelease` |
| `ServiceComparisonReport` | the exact deployments compared, load and latency protocol, paired business metrics, disclosed infrastructure differences, cost model | `DeploymentRelease` |
| `DeploymentRelease` | model artifact, prompt, output schema, calibrator, policy version, runtime image, quantization, hardware profile, quota, fallback, predecessor release | `ModelArtifact`, the predecessor `DeploymentRelease` when there is one |

`operational` for `TrainingAttempt` holds the intent id, the upstream job id, the event cursor and timestamps.

When the provider builds the image from a build context sent with the job, as Autoresearch does, a recipe's image digest is the digest of that context: the Dockerfile, whose base images are named by digest, and every file beside it. The built image's own manifest digest comes from the provider's receipt for the finished job and is recorded with the attempt's measured results. A recipe that names a prebuilt image carries that image's manifest digest instead.

Field names and types are the exported JSON Schema (section 2), reviewed by Techtree on 12 Oct 2026: regents-cli 08bd5c3, `src/regents_cli/techtree/model_climb/contracts.schema.json`, sha256 `7b38f89af8d1294df4b294685b1c37d52ccf509eb2a8ca4e56757f7deff4a070`. A change to the schema changes this pin, and Techtree reviews it first.

Four digest fields may be `null`, which means nothing of that kind exists: a dataset release's `transformation_digest`, a benchmark release's `scorer_test_digest` and `qualification_report_digest`, and a harness profile's `decision_policy_digest`. Nothing is ever put there to stand for nothing. Only the plan `plan --profile` writes for `model_climb_profile_test` may refer to an object that holds one of these nulls; every other `spend` operation refuses such a plan at admission with `validation_error`, naming the field. (Decided 13 Oct 2026; the schema pin above moves when regents-cli exports the schema that allows it.)

### 3.3 Result fields

Six independent fields, never merged into one status:

```text
execution:   succeeded | failed | cancelled | indeterminate
integrity:   verified | invalid | incomplete
comparison:  valid | invalid | exploratory
outcome:     uplift | tie | regression | inconclusive
release_gate: pass | fail | insufficient_evidence | not_evaluated
attestation: participant | identified_executor | independently_reproduced
```

A training run that succeeded says nothing about `outcome`. Too few positives or negatives for the declared sample plan gives `release_gate: insufficient_evidence`.

### 3.4 Data and split commitments

- v1 reads JSONL only. Other formats come later inside the engine image, not the ordinary CLI package.
- Every row gets a stable private row id. A split's commitment is sha256 over the canonical, sorted list of HMAC-SHA256(salt, row id).
- The salt stays in the operator's local store. It is never written into any object, `operational` included, and never published.
- Proving membership is sealed: the trainer side receives the train and validation files and only the proving commitment.

### 3.5 Proof bundle

A Model Climb proof is a directory holding a `ModelUpliftReport`, every object it references by digest, and a manifest signed with the participant identity key. `regents techtree proof verify` chooses its check by the manifest's `schema_version`; existing bundles keep their current check unchanged.

On disk: `manifest.json` and `objects/<64 hex>.json`, one file per object, named by its digest. Sent to Techtree it is one JSON document with exactly three members:

```text
schema_version  "techtree.model-climb.proof.v1alpha1"
manifest        a signed envelope: exactly payload, payload_digest, signature
objects         every object the manifest lists, each exactly as in 3.1
```

The manifest's `payload` has exactly four members:

```text
schema_version  "techtree.model-climb.proof.v1alpha1"
report          the ModelUpliftReport's digest
objects         every object's digest, report included, sorted, each once
signer          {kind: "local_ed25519", algorithm: "ed25519", key_id, public_key}
```

`payload_digest` is the digest (3.1) of `payload`. `signature` is `{algorithm: "ed25519", key_id, signature}`: Ed25519 over the ASCII bytes of `payload_digest`, base64. `key_id` is `sha256:` over the raw 32-byte public key, and `public_key` is that key in base64. This is the same envelope and identity Techtree's published Skill results use; the key is the existing Techtree identity key.

Techtree accepts a proof (`model_climb_report_submit`) only when all of these hold, checked in this order, and otherwise answers `validation_error` naming the first that did not:

1. The document is at most 1,048,576 bytes and has exactly the three members, the right `schema_version` and at most 64 objects.
2. Every object has exactly `schema_version`, `kind`, `spec`, `operational` and `digest`; its `schema_version` is `techtree.model-climb.v1alpha1`, its `kind` one of 3.2, and its `digest` recomputes. No digest appears twice.
3. The manifest is exactly as above, and its `payload_digest` recomputes.
4. `key_id` is the digest of `public_key`, and the signature verifies under it.
5. The objects carried are exactly the digests the manifest lists.
6. `report` names the one `ModelUpliftReport` carried. Its `spec` has the fields 3.2 names, its paired outcomes add up (each case in one of four cells, each case positive or negative), its uncertainty interval is in order with a confidence between 0 and 1, and its result fields (3.3) take only their listed values.
7. The report's `artifact` and `benchmark_release` are carried, as a `ModelArtifact` and a `BenchmarkRelease`.
8. The report's `attestation` is `participant`. Techtree gives `identified_executor` and `independently_reproduced` itself, to runs it executed; an upload never claims them.

The full graph check (every reference, field-level schema) stays with `regents techtree proof verify`; the site records which checks it ran, these eight, and nothing more.

An accepted proof is private: it belongs to the person whose agent sent it (the agent's current pairing), and only that person's paired agents read it, through `model_climb_reports` and `model_climb_report`. Nothing in it is shown on a public page (Sean, TT-BYO-MC-PRIVATE a, 13 Oct 2026).

## 4. Operations

One operation id names the same action in every transport. A transport may expose fewer operations; it never gets more authority. An operation has one effect class in every form: a `spend` operation has no form that runs without its grant, and a drafting step is a `draft` operation of its own.

Effect classes: `read`, `draft` (writes a draft, no compute), `submit` (sends a signed record to the owner's private Techtree records; nothing becomes public), `request` (creates a review request, never a grant), `grant` (issues a signed execution grant), `spend` (rents compute or calls a model), `deploy` (changes a service), `publish`.

| Operation | Effect | CLI | HTTP | WebMCP | ChatGPT (initial) |
|---|---|---|---|---|---|
| `model_climb_capabilities` | read | yes | yes | yes | yes |
| `model_climb_profile_check` | draft | yes | no | no | no |
| `model_climb_profile_test` | spend | yes (operator only) | no | no | no |
| `model_climb_grant_issue` | grant | yes (local-only operator) | no | no | no |
| `model_climb_grant_revoke` | grant | yes (local-only operator) | no | no | no |
| `model_climb_list`, `model_climb_get` | read | yes | yes | yes | yes |
| `model_climb_prepare` | draft | yes | yes | yes | yes |
| `model_climb_data_register`, `model_climb_data_validate` | draft | yes (runner only) | no | no | no |
| `model_climb_data_status` | read | yes | yes | yes | yes, sanitized |
| `model_climb_plan` | draft | yes | yes | yes | yes |
| `model_climb_request_approval` | request | yes | yes | yes | yes |
| `model_climb_start` | spend | yes | yes | yes | no |
| `model_climb_status`, `model_climb_events` | read | yes | yes | yes | yes |
| `model_climb_cancel` | spend (stops spend) | yes | yes | yes | no; link to the owner's page |
| `model_climb_prove` | spend | yes | yes | yes | no |
| `model_climb_report`, `model_climb_reports` | read | yes | yes | yes | yes, approved projection |
| `model_climb_report_submit` | submit | yes | yes | no | no |
| `model_climb_deployment_prepare` | draft | yes | yes | yes | yes |
| `model_climb_deployment_apply`, `_promote`, `_rollback` | deploy | yes | yes | yes | no |
| `model_climb_runner_enroll`, `model_climb_runner_serve` | — | yes (runner only) | runner channel | no | no |

No operation runs a shell, Python, SQL, an arbitrary URL fetch, exports a credential, reads raw proving data, or uploads an arbitrary artifact. A signed proof (3.5) is not an arbitrary artifact: it holds only contract objects, and Techtree checks it before keeping it.

### 4.1 HTTP

- Private route family `/api/model-climb/v1/`: `capabilities`, `studies`, `plans`, `approval-requests`, `jobs`, `jobs/:id/cancel`, `reports`, `deployments`, `runners`, `events?cursor=`.
- Built first (M3, 13 Oct 2026): `POST reports` (`model_climb_report_submit`, body: the proof document of 3.5), `GET reports` (`model_climb_reports`) and `GET reports/:digest` (`model_climb_report`), the caller's owner's reports only; another person's digest answers `not_found`. A repeat of the same proof answers with the record already kept.
- Wallet-agent requests carry the shared SIWA request proof exactly as the template's one SIWA header implementation defines it. No new headers.
- Every mutation carries an `Idempotency-Key` and, where the resource changes, the expected resource version and plan digest. The server stores the request digest with the key; the same key with a different request is `idempotency_conflict`.
- Long work answers 202 with a stable `job_id`; nothing holds a request open for training.

### 4.2 Answers and errors

Success: `{"schema_version": "techtree.model-climb.operation.v1alpha1", "operation_id", ...operation fields, "next_actions": [...]}`.

Failure keeps the site's envelope `{"error": {"code", "message", "hint", "details"?}}`; `hint` says what to do next. New codes:

`approval_required`, `unsupported_capability`, `runner_unavailable`, `data_policy_denied`, `proving_access_denied`, `plan_changed`, `budget_exhausted`, `idempotency_conflict`, `job_indeterminate`, `evidence_incomplete`, `release_gate_failed`, `artifact_unavailable`.

Existing codes (`validation_error`, `not_found`, `conflict`, ...) keep their meaning.

## 5. States

```text
Study:      draft → data_ready → plan_frozen → awaiting_approval → training
            → candidate_frozen → proving → evaluated → release_review → closed
Attempt:    pending → admitted → provisioning → running → collecting
            → succeeded | failed | cancelled | budget_exhausted | indeterminate
Deployment: prepared → shadow → canary → production → retired; any of shadow, canary, production → rollback
```

- Upstream job id, intent id, lease generation and event cursor are written before the state advances.
- A submission whose outcome is unknown becomes `indeterminate`. The engine looks up the recorded provider job before it ever submits again; it never submits a duplicate automatically.
- Closing a browser, an HTTP request, an MCP session or a chat never cancels a job. Cancel is a request, then an observed termination.

## 6. Execution grants

A grant is a signed record bound to:

```text
issuer and approving human; workspace and authorized actor
operation; resolved plan digest
dataset, benchmark and model policy digests
provider, mission and GPU restriction
maximum USD and maximum wall time
maximum attempts and parallel jobs
permitted egress destinations
issued_at, expires_at, nonce, use count
```

- Changing any bound field invalidates the grant. A grant id alone authorizes nothing: the engine checks actor binding, expiry, revocation and policy on use.
- Separate grants for: training spend, the GPU compatibility test, final-test (proving) access, extra egress, a budget increase, production promotion, publication.
- The existing `--yes --reviewed-on` approval stays as it is for existing commands. It is not a grant and admits no Model Climb `spend` or `deploy` operation.
- In local-only mode on the operator's own machine, a grant is operator-attested and says so in `attestation`. It is issued by `regents techtree model-climb grant issue`, which shows the full bound record and needs a typed confirmation (the grant's maximum USD, typed as shown), and is signed with the existing Techtree identity key (Ed25519). Its `attestation` is `participant` with `operator_attested`. Its approving human is the operator's login name on that machine, recorded as given; `operator_attested` says nobody else checked it.
- Revocation and use counting are built with the first `spend` command (`model_climb_profile_test`); no command that spends exists without them.
- In local-only mode they live in a grant ledger: an append-only file beside the grants, one line per event, each line signed with the same identity key and naming the grant's digest and nonce. It is the engine's own local record, not a contract object, and section 3.2's schema pin does not cover it. Three rules hold:
  - `grant issue` writes the grant's `issued` line. A grant with no `issued` line in the ledger is refused. For a plan whose budget says `credit_ceiling_attested`, the `issued` line also records, by name, the operator's two answers of section 6.1 (automatic top-up is off; the balance is no more than the cap), and no such grant is issued unless both are yes.
  - A `used` line, carrying the attempt's intent id, is written before the job is submitted, never after. The engine refuses a grant whose `used` lines have reached `uses_allowed` or `max_attempts`, and any grant with a `revoked` line.
  - `regents techtree model-climb grant revoke <grant id>` (`model_climb_grant_revoke`) writes the `revoked` line. It only removes authority, so it asks for no typed confirmation, and revoking a revoked grant changes nothing. It does not stop a job already submitted.
  - A ledger that cannot be read, or that holds a line whose signature does not verify, admits nothing: every grant is refused with `approval_required` until a person has looked at the file.
  - The ledger is the operator's own file on the operator's own machine. Like the grant, it is `operator_attested`: it stops mistakes and repeats, and nobody else has checked it. The provider lookup by intent id (section 6.1) is what stops a second submission.
- Connected-mode grants come from the site, signed by a Techtree key whose public key this contract will publish. Until it does, the engine refuses every connected grant with `approval_required`.

### 6.1 Budget enforcement

Each plan names how its cap is enforced:

- `provider_hard_limit`: the provider stops spend at the cap.
- `bounded_operational_limit`: the runner stops the job at the cap less a shutdown allowance; the provider may bill a little past it.
- `estimate_only`: no enforcement; refused for any plan that requires a limit.

M0's compute is San Francisco Compute's Autoresearch (Sean, 12 Oct 2026), provider id `sfcompute_autoresearch`, paid from the operator's prepaid credit there, every job filed under the operator's mission. Autoresearch takes no region, so a compute target and a grant name the mission instead. A paid step is one batch job (`submit_job`) with `chip: "h100"`, `chip_count: 2`, `max_restarts: 0`, no resume and no checkpointing, and `max_duration_minutes` set to the largest whole number of minutes whose cost, at the rate read at resolve time, is no more than the grant's maximum USD. Its documentation says preflight refuses a job whose worst-case cost exceeds what remains under the workspace or organization cap, and that a cap or an empty balance stops a running job. Until the first paid run shows that, an Autoresearch plan is `bounded_operational_limit`, with the job's minutes as the runner's limit; its budget also says `credit_ceiling_attested`, which means the plan counts on the account's own spending limit and may be granted only on the operator's word for it. Prices checked 12 Oct 2026: $0.063 per GPU-minute for batch jobs, so the two-GPU test costs $0.126 a minute. The operator sets a monthly spend limit on the workspace and turns automatic top-up off; the plan is sealed before anyone reviews it, so the plan cannot hold the operator's word. The grant review asks the operator to attest both, each time, and the grant's `issued` ledger line is where the two answers are kept (section 6).

Autoresearch takes no dollar limit on a job. It answers one: `max_cost_usd`, worked out from the minutes, the GPUs and the rate, and the ceiling of one attempt. So the engine holds only two levers, minutes and restarts, and uses both:

- `max_restarts` is always 0. The provider's default is 1, and each restart bills a full attempt.
- The job never checkpoints. An attempt the provider itself ends bills nothing unless the job checkpointed, so the worst case stays one ceiling.
- The engine reads back the provider's `max_cost_usd` for the job and cancels the job, before it runs, if that is more than the grant allows. Cancelling a queued or building job costs nothing.
- Every job carries the provider's required checks block with one success check: the profile file exists in the output folder.

The image build is outside the grant's maximum USD. The provider's published API description says a job "bills only the running attempt (builds bill after a monthly free allowance; queued and preempted time is free)" and gives neither the allowance nor the build rate (read 13 Oct 2026). The plan says the build is outside the maximum, and the attempt records what the provider's usage shows for the build.

No plan for `model_climb_profile_test` may reserve more than 2000 cents (Sean, 13 Oct 2026: "$5-20 per run max"); the engine refuses a larger one at admission. The first plan reserves 1000.

Autoresearch does not restrict a batch job's outbound network: its manual gives a job the open internet, less a short blocked list. A plan's and a grant's egress list is therefore a declaration the provider does not enforce. The engine holds the job to it in the ways it can: the job's own commands fetch only the pinned model revision from the named host, and everything after that download runs with the model hub offline, `dashboard = false` and `--no-push` (section 7.3). The profile says the list was declared and not enforced by the provider. For M0 the list is `huggingface.co`, meaning that host and the download hosts it redirects a model file to.

Because the provider leaves the job's network open, four rules hold for every job, so that an open network puts at risk only the rented minutes, which the grant already bounds (Sentinel, 13 Oct 2026):

- The job holds nothing worth sending: no Techtree identity key, no provider service token and no write token of any kind, in its environment or its files. If the pinned model needs a hub token, that token is read-only and limited to that one model, it is set through the provider's environment setting and never in the command, and the plan records that one is present.
- Nothing is installed while the job runs; every package comes from the built image. The image build has an open network too, so the Dockerfile's installs are pinned by hash, or the plan says plainly that they are not yet.
- Results leave only through the provider's own output folder. The job's commands write nowhere else.
- The data is the four public synthetic fixtures of section 7.4. A job that holds private data could send it anywhere, so the first real data set on this provider is a decision for Sean, not a note.

The engine submits through Autoresearch's HTTP API or its `autor` CLI, signed in with a service token scoped to the workspace, which the operator creates; never through an operator's chat session. Every submission sets both `idempotency_key` and `label` to the attempt's intent id. After a submission whose outcome is unknown, the engine looks the job up by that label (`list_jobs`) and never submits again; if nothing is found it answers `job_indeterminate`, submits nothing, and a person decides what happens next.

## 7. M0 compatibility profile

### 7.1 Pinned tuple

| Part | Pin | Note |
|---|---|---|
| Model | `Qwen/Qwen3.5-9B` @ `c202236235762e1c871ad0ccb60c8ee5ba337b9a` | Apache-2.0, not gated, 9.65B params, 19.3 GB bf16, `Qwen3_5ForConditionalGeneration` with a vision encoder |
| Text/vision policy | text only; vision encoder frozen and not served | prime-rl LoRA forces `freeze_vision_encoder = true` |
| Trainer | prime-rl `main` 1e5318108da29d10960e91e54b80305f597de39d (pyproject 0.9.0) | Python 3.12, Linux, CUDA 13, torch ≥ 2.13, transformers 5.6.2 |
| Evaluator | `verifiers[harbor]` 0.3.2.dev208 | prime-rl main needs ≥ 0.3.2.dev158; stable 0.3.1 is too old |
| Server | vLLM 0.31.0 (`db9527a46873454610df6dbedf79a36d6bf1a7f6`) | `Qwen3_5ForConditionalGeneration`: LoRA supported |
| dtype | bf16 for weights, optimization and reduction | prime-rl defaults optimization to fp32; set `optimization_dtype = reduce_dtype = "bfloat16"` |
| Hardware | 2 × H100 80GB SXM in one Autoresearch batch job, one training, one inference | the adapter in vLLM's format is written only by SFT with online evals (section 7.3) |

The profile records the measured CUDA driver, kernel versions, peak memory per GPU and the matched module list. It certifies this tuple only.

### 7.2 LoRA targets and the coverage check

Qwen3.5-9B's text stack is 32 layers: 8 full-attention and 24 Gated DeltaNet. prime-rl's default targets reach attention only in the 8 full-attention layers and silently ignore names the model lacks.

The recipe lists every target explicitly:

```text
full attention (8 layers):  q_proj, k_proj, v_proj, o_proj
Gated DeltaNet (24 layers): in_proj_qkv, in_proj_z, in_proj_b, in_proj_a, out_proj
MLP (32 layers):            gate_proj, up_proj, down_proj
```

Expected matched modules in the text stack: 8×4 + 24×5 + 32×3 = **248**. Vision encoder and the multi-token-prediction layer: **0**.

The check: the trainer's matched module list must equal the expected set exactly, and every adapter tensor must be nonzero in `lora_B` after training. Anything else fails admission, whatever the trainer reported. The M0 dry run (12 Oct 2026) confirmed the module paths. The recipe's targets:

```text
^model\.language_model\.layers\.\d+\.self_attn\.(q_proj|k_proj|v_proj|o_proj)$
^model\.language_model\.layers\.\d+\.linear_attn\.(in_proj_qkv|in_proj_z|in_proj_b|in_proj_a|out_proj)$
^model\.language_model\.layers\.\d+\.mlp\.(gate_proj|up_proj|down_proj)$
```

They match 248 modules, none missing and none unexpected. Text-only SFT resolves without a `[model.vlm]` block. The recipe sets `[model.fusions] enabled = []`, so LoRA attaches to the separate projections the check counts, and admission fails unless the resolved configuration shows it.

### 7.3 Adapter export and serving

- prime-rl's DCP checkpoint exporter refuses LoRA checkpoints. The PEFT adapter (`adapter_model.safetensors`, `adapter_config.json`) is written by the filesystem weight broadcast, which SFT runs only with `[eval]` and `[inference]` configured.
- Serving: `vllm serve` on the base revision with `--enable-lora`, `--max-lora-rank` equal to the recipe's rank, `--lora-modules` naming the adapter differently from the base model, and structured output through `response_format` `json_schema` (`guided_json` no longer exists).
- vLLM packs `in_proj_qkv` with `in_proj_z`, and `in_proj_b` with `in_proj_a`. The test proves the trained adapter loads into those packed layers and changes the output.
- Verifiers runs with `--no-push`; its default uploads results to Prime Intellect.
- The trainer sends nothing anywhere: the recipe sets `dashboard = false`, and admission fails unless the resolved `heartbeat`, `monitors.prime` and `monitors.wandb` are all null. Metrics go only to a local `metrics.jsonl`.

### 7.4 The test

1. **Model-free (no spend).** In a pinned Linux container: resolve the SFT config with `--dry-run`, render the fixtures with the Qwen3.5 renderer, and check the loss mask covers only assistant targets. Fixtures are synthetic and public; no customer data.
2. **Paid, under its own grant.** In the granted batch job: load the exact revision; run a short SFT on the fixtures with online evals; record peak memory and matched modules; run the coverage check; start a fresh vLLM process with the adapter; run one Verifiers fixture against it with `--no-push`; confirm the adapter's answers differ from the base model's on the same fixture.
3. **Cleanup.** Confirm through the provider (`get_job`) that the job has ended and nothing of it is still running. Record the measured cost.

Steps 1 and 2 use the same four synthetic fixtures (`scripts/techtree/model-climb-image/fixtures.jsonl` in regents-cli), and the plan records their digest.

The output is the measured compatibility profile and its digest, with the built image's manifest digest from the provider's receipt. It does not claim uplift or general compatibility.

## 8. Open items

- Whether the weights load for text-only training without a `[model.vlm]` block (fixed by 7.4 step 2).
- How long Autoresearch honours an `idempotency_key`; its documentation does not say.
- Live Autoresearch prices; the plan reads them at resolve time and records them.
- Whether Autoresearch's cap stops a running job at `max_cost_usd` (fixed by 7.4 step 2); until then plans are `bounded_operational_limit`.
- The site's grant-signing public key (section 6), before connected mode.
- The delegated-client sign-in for ChatGPT and Codex (section 2), owned by ash-template.
- Whether stock vLLM loads the adapter without prime-rl's patches (fixed by 7.4 step 2).
