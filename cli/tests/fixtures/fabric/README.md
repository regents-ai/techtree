# NeMo Fabric adapter evidence

This directory holds the bounded evidence used by the WP0.4 Fabric capability
spike. It is derived from the exact `nemo-fabric==0.2.0` release family, the
descriptors those wheels ship, and three disposable uv-managed environments
that ran real Fabric plan, Doctor and lifecycle calls.

`evidence_manifest.json` binds every wheel to its PyPI digest, every source
snapshot to its wheel member and line range, and every observation file to its
own digest. `fabric_capabilities_0_2_0.json` is the derived capability record:
what each descriptor claims, what Techtree observed, and what remains
unresolved before release admission.

No subject run reached a model provider. Every lifecycle used a non-OpenAI
provider coordinate pointed at a closed loopback port with a placeholder key,
so no model turn completed and nothing was billed; each run terminated in a
classified error at the invoke stage, which is the intended outcome and not a
success. The Codex harness did fetch plugin content over the network on first
start, which is recorded as its own finding. The operator's own Hermes and
Codex installations and configuration were never used, modified, or read into
this evidence.
