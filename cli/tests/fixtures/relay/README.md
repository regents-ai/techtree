# NeMo Relay, ATOF and ATIF evidence

This directory holds the bounded evidence used by the WP0.5 Relay contract
spike. It is derived from the exact `nemo-relay==0.8.2` release, the
`nvidia-nat-atif==1.8.0` schema package that defines ATOF and ATIF, the
`nemo-relay==0.7.3` generation the Fabric Codex gateway accepts, and the
Fabric 0.2.0 adapter wheels that carry the Relay plumbing.

`evidence_manifest.json` binds every wheel to its PyPI digest, every source
snapshot to its wheel member and line range, every observation file to its own
digest, and the three retained captures to theirs.
`relay_contract_0_8_2.json` is the derived contract record: what Relay
supports, what it does not, and what remains unobserved before release
admission.

`atof/complete.atof.jsonl` is the exact byte stream one Relay file sink wrote
for one deterministic subject. `atif/complete.native.atif.json` is the ATIF
document Relay's own plugin exported from that same run, and
`atif/complete.derived.atif.json` is the ATIF document the NeMo Agent Toolkit
converter produced from the retained ATOF file. The three together are the
evidence that ATIF is a lossy projection and that ATOF is the authoritative
artifact.

No subject run reached a model provider. Every run used a placeholder model
name and a loopback address on a closed port, so the model call is expected to
fail; that refusal is the intended outcome of a zero-spend probe and is not a
successful subject run. No Relay CLI was executed and no gateway was launched.
The operator's own Hermes, Codex and Relay installations and configuration were
never used, modified, or read into this evidence.
