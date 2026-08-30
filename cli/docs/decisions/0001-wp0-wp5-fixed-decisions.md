# 0001 — WP0–WP5 fixed decisions

Status: binding for all WP0–WP5 work. Worker threads follow this document
over any conflicting older ticket or spec slice.

```text
Verifiers pin:
  PrimeIntellect-ai/verifiers
  7e1c47d24d055aae587ee8259f77a3e8e193513a
  (never main, a branch, a tag, or an unpinned PyPI range;
   any upgrade requires a dedicated dependency-bump ticket that
   reruns the PI0 preflight)

Shuffle:
  false only; no shuffle seed exists in WP0–WP5;
  membership = first num_tasks tasks in Taskset iteration order;
  never call Verifiers Taskset.shuffle()

Development Campaign:
  procedure-transfer-dev-campaign@1

Development Climb:
  procedure-transfer-dev@1
  (the name procedure-transfer-v1 is reserved for the first real
   WP6 subject evaluation; never mutate the dev fixtures into it)

Bundled Hermes skills:
  use_bundled_skill = false in baseline and candidate; invariant;
  the only allowed difference is /agents/subject/harness/skills

Signing:
  Ed25519 primitives only; no live signing, no device keys,
  no identity storage through WP5

Canonical result command:
  techtree run result <run-id>   (not: techtree climb result)

Relay:
  NeMo Relay is excluded; no package, field, exporter, or status

Task-hash boundary:
  Verifiers task hashes are raw 64-char lowercase hex; normalize to
  sha256:<hex> at the Verifiers boundary (normalize_verifiers_task_hash);
  never weaken the Techtree Digest type
```

Development subject placeholders (frozen; the fake worker must never read
`TECHTREE_MODEL_API_KEY`, validate the model, or pull the Docker image):

```yaml
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
  supported_platforms: [linux/arm64, linux/amd64]
  cpu: 2.0
  memory_gb: 4.0
  network_policy: restricted
trainable: false
```
