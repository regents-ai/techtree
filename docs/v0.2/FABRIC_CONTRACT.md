# NeMo Fabric adapter contract spike

Status: captured with release blockers. Candidates: `nemo-fabric==0.2.0` with
`nemo-fabric-runtime==0.2.0`, `nemo-fabric-adapters-hermes==0.2.0` and
`nemo-fabric-adapters-codex==0.2.0`; admission remains a separate founder
decision and is not granted here.

The evidence index in
[`cli/tests/fixtures/fabric/evidence_manifest.json`](../../cli/tests/fixtures/fabric/evidence_manifest.json)
binds the six exact NeMo Fabric wheels, the two adapter descriptors as shipped
wheel members, six source excerpts with their member and line ranges, and the
five observation files produced by real Fabric calls. The derived capability
record is
[`fabric_capabilities_0_2_0.json`](../../cli/tests/fixtures/fabric/fabric_capabilities_0_2_0.json)
and the release view is
[`FABRIC_CAPABILITY_MATRIX.json`](FABRIC_CAPABILITY_MATRIX.json). The index
records artifact digests, descriptor digests, excerpt digests and observation
digests; it contains no credential, no operator path, no harness configuration
and no model output.

Wheel provenance is bound by each wheel's PyPI digest and by the repository and
version its SBOM declares. Nothing inside any wheel names a commit, so the
`v0.2.0` commit recorded in the lock is asserted from the release tag, not from
wheel contents; every artifact record says so in its `source_commit_note`.

## What was run

Three disposable uv-managed environments on Python 3.12: one with the runtime
and both adapters and no harness, one with the runtime, the Hermes adapter and
`hermes-agent==0.19.0`, and one with the runtime and the Codex adapter's
`harness` extra, which pins `openai-codex==0.144.4`. Each managed process was
started with an explicit three-name environment — `HOME` pointed at a
disposable directory, a `PATH` that reached no host harness executable, and a
disposable `TMPDIR` — plus one placeholder model-key variable. No credential
variable was present, the operator's own home was never named in the process
environment, and the operator's Hermes and Codex installations, configuration
and stored logins were never used, modified or read.

Every adapter was exercised through a real Fabric plan and Doctor for each
normalized configuration control, and each adapter ran one full start, invoke
and stop lifecycle. Those lifecycles used a non-OpenAI provider coordinate
pointed at a closed loopback port with a placeholder key, so no model provider
was contacted, no model turn completed and nothing was billed. Each run
therefore terminated `failed` with a classified error at the invoke stage. That
is the intended outcome of a zero-spend probe and is not a successful subject
run: reward, Skill projection and comparison semantics through Fabric remain
unobserved.

## What the contract supports

Descriptors resolve from the installed adapter package, and the resolved plan
records that provenance. Adapter admission is exact: for both adapters, every
control the descriptor lists in `config.accepts` was admitted, and every
control it does not list was rejected by `Fabric.plan()` before any runtime
started. Rejection is not advisory — planning raises. For most refused controls
Doctor also reports the field as a failing check; for `tools.definitions` it
raises instead of returning a report, which is recorded as a finding below.
Either way the control is refused before spend, with no Techtree-side policing.

Hermes accepts model selection and base URL, temperature, system instructions,
maximum turns, enabled and blocked native tool selection, MCP servers with
OAuth2, and Skill paths. An empty enabled-tools list was applied natively: the
harness ran with no toolsets at all. Codex accepts model selection and base
URL, system instructions, MCP servers with OAuth2, and Skill paths, and
nothing else.

Both adapters run out of process, as a persistent local host started from the
managed environment's own interpreter, and both produced a normalized result
carrying terminal status, a classified error with its lifecycle stage, an
ordered event log from runtime start to runtime stop, and an artifact manifest.
The Hermes adapter redirects `HOME` and `HERMES_HOME` into a Fabric-owned
per-runtime directory before importing the harness; across a full lifecycle the
disposable directory supplied as `HOME` gained no entries, and all harness
state landed under the Fabric artifacts root.

## What the contract does not support

Neither adapter declares `tools.definitions`, `mcp.auth.service_account` or
`mcp.tool_filters`. Codex additionally declares no `tools.enabled`,
`tools.blocked`, `runtime.max_turns` or `models.temperature`, so a Campaign
that normalizes tool policy or turn limits cannot run on Codex at all.

For `tools.definitions` on both adapters, `Fabric.doctor()` raised a
`FabricConfigError` rather than returning a report with a failing check, so a
caller cannot collect that refusal alongside the other checks. Techtree must
handle both shapes of refusal.

Both descriptors resolve with all four runtime capabilities — service,
streaming, updates and cancellation — declared false. That is a descriptor
declaration, not an observed attempt: no cancellation, update or streaming call
was made, and the native surface does expose an `invoke_openai_stream` entry
point this spike did not exercise. Techtree must plan for a subject it cannot
cancel until that is tested. On the runs that terminated at invoke the
normalized result carried a null usage record, so no token or cost accounting
was seen; whether a completed turn reports usage is untested.

Neither descriptor declares any requirements. Fabric does enforce declared
requirements — a descriptor carrying an absent binary produced a failing
`requirement.binary` check — but because the shipped descriptors declare none,
Doctor returned `pass` for both adapters with no harness installed at all, and
the absence surfaced only as a lifecycle start failure. Harness presence is
therefore Techtree's gate, not Fabric's.

Two Codex-specific findings limit isolation and reproducibility. For an OpenAI
provider coordinate the adapter does not redirect `CODEX_HOME`; it passes the
caller's `HOME`, `CODEX_HOME`, `OPENAI_API_KEY` and `XDG_*` values straight
through to the harness child process, so a Techtree subject must supply owned
values rather than rely on the adapter. That path is proven from the adapter
source, which is retained with its digest; the OpenAI path itself was not run.
And starting Codex against a Fabric-owned home that Fabric created empty left a
git working tree with a `FETCH_HEAD` and a git config inside it, so plugin
content was fetched over the network during the run. The remote was not
inspected and none is asserted; the run is simply not hermetic as shipped.

Hermes Agent is the remaining supply question. The adapter never installs it.
NVIDIA states, in text retained from the `nemo-fabric` wheel metadata, that
releases from 0.20 onward are not installable from PyPI, and the index offered
nothing above `hermes-agent==0.19.0` when it was queried. Neither observation
proves what exists outside PyPI. `0.19.0` provides every module the adapter
imports, and is what the recorded lifecycle used.

## Protected actions

None were taken. No package was published, no upstream issue or pull request
was sent, no host installation or configuration was changed, and no paid or
real-model work ran. Release admission for either adapter is a separate founder
decision; `release_admitted` stays false in the capability matrix until that
decision is recorded.

## Consequence

WP2 and WP6 must add five Techtree-owned gates before any subject run: verify
harness presence and version before admission, supply an owned `HOME` and
`CODEX_HOME` for every Codex subject, treat a started subject as uncancellable
and bound it by timeout, derive usage from Techtree evidence, and handle both
shapes of Fabric refusal. Fabric remains in the v0.2 identity as the subject
backend, and its admission behaviour is strong enough to carry the plan's
"unsupported behaviour fails admission before spend" rule, but neither adapter
is a release-admissible subject until those gates exist, a real subject run is
observed, and the founder admits them.
