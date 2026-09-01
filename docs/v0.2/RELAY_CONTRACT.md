# NeMo Relay, ATOF and ATIF contract spike

Status: captured with release blockers. Candidates: `nemo-relay==0.8.2` for the
Relay runtime and `nvidia-nat-atif==1.8.0` for the ATOF and ATIF schemas;
admission remains a separate founder decision and is not granted here. Relay
stays observe-only: nothing recorded here gives it authority over a score, a
spend decision, or an execution decision.

The evidence index in
[`cli/tests/fixtures/relay/evidence_manifest.json`](../../cli/tests/fixtures/relay/evidence_manifest.json)
binds seven exact wheels, seven source excerpts with their member and line
ranges, five observation files, and three retained captures from a real Relay
run. The derived contract record is
[`relay_contract_0_8_2.json`](../../cli/tests/fixtures/relay/relay_contract_0_8_2.json),
and the two adapter profiles are in
[`RELAY_COVERAGE_PROFILES/`](RELAY_COVERAGE_PROFILES/). The index records
artifact digests, excerpt digests, observation digests and capture digests; it
contains no credential, no operator path, no harness configuration and no model
output.

Wheel provenance is bound by each wheel's PyPI digest and by the release tag
its version carries. The CycloneDX document inside the `nemo-relay` 0.8.2 wheel
declares its internal Rust crate at version 0.8.0, not 0.8.2, and embeds
build-machine paths, so it binds neither the distribution version nor a commit.
The commit recorded in the lock is asserted from the release tag; the manifest
says so.

## Coordinates

ATOF is the Agent Trace Observation Format: the raw, append-only JSON Lines
stream Relay emits, one object per lifecycle event, each carrying its own
`atof_version`. ATIF is the Agent Trajectory Interchange Format: a derived
document that summarises a run as ordered steps.

| Thing | Coordinate |
| --- | --- |
| Relay runtime and Python bindings | `nemo-relay==0.8.2` |
| ATOF wire version | `0.1` |
| ATIF schema version | `ATIF-v1.7` |
| ATOF and ATIF schema package | `nvidia-nat-atif==1.8.0` |
| Observability config version | `3` |
| Coverage calculation version | `relay-coverage-v1` |
| Relay CLI the Codex gateway accepts | `nemo-relay-cli-bin` in `>=0.7.2,<0.8.0` |

ATOF and ATIF have no standalone distribution. Both models and the ATOF to ATIF
converter live inside `nvidia-nat-atif`, a NeMo Agent Toolkit subpackage, and
the converter needs that package's `full` extra for `jsonschema`.

## What was run

Three disposable uv-managed environments on Python 3.12: one with
`nemo-relay==0.8.2`, `nemo-relay-plugin==0.8.2` and `nvidia-nat-atif==1.8.0`;
one with `nemo-relay==0.7.3` alone, to compare the generation the Codex gateway
requires; and one with the Fabric 0.2.0 adapter wheels, read for their Relay
plumbing and never executed. Each managed process was started with an explicit
environment — a disposable `HOME`, a disposable `TMPDIR`, a `PATH` reaching no
host harness executable, and one placeholder model-key variable. No credential
variable was present and the operator's Hermes, Codex and Relay installations,
configuration and stored logins were never used, modified or read.

One deterministic subject was run under each condition recorded in
[`observed/lifecycle.json`](../../cli/tests/fixtures/relay/observed/lifecycle.json)
and
[`observed/delivery_diagnostics.json`](../../cli/tests/fixtures/relay/observed/delivery_diagnostics.json):
an agent scope containing one mark, one tool call that succeeds, and one model
call pointed at a closed loopback port with a placeholder model name. The model call
always fails at connect, so no model provider was contacted, no model turn
completed and nothing was billed. That refusal is the intended outcome of a
zero-spend probe and is not a successful subject run.

## What the contract supports

A configured ATOF file sink wrote every emitted event as one JSON object per
line with a stable thirteen-key envelope and an explicit `atof_version` on each
event. A scope start and its end share one UUID and every child names its
parent, so a run's hierarchy is reconstructable from the stream alone. The
plugin's ATIF export names the root agent scope UUID as both `session_id` and
`trajectory_id`, which is the correlation anchor between the raw stream and any
projection of it.

Registration order is decisive and observable. An exporter registered before the
root scope opened captured seven events including the root scope start; the same
exporter registered one statement later captured six and silently lost the root
start. That is the evidence behind the profiles' rule that registration must
precede subject start.

Misconfiguration fails early rather than at flush time. A file sink whose output
path traverses a regular file raises at exporter construction, before the
subject starts. An unsupported observability config version is refused with a
typed diagnostic at validate time and raises at initialize time; it is never
silently downgraded.

## The version that all three producers accept

Relay 0.8.2 accepts observability config versions 3 and 4 and defaults to 4.
Relay 0.7.3 accepts only 3. The Fabric 0.2.0 adapters accept only 3, or a config
that omits the key. Version 3 is therefore the only value the whole locked stack
accepts, and it is what Techtree pins. Under version 3 Relay refuses the
OpenTelemetry logs and metrics sections as trace-only, which costs Techtree
nothing: ATOF and ATIF are unaffected.

## What the contract does not support

**There is no dropped-event diagnostic for ATOF.** Relay 0.8.2 exposes no
dropped-event counter, no queue-depth reading and no delivery receipt on the
ATOF exporter or in the plugin report. An ATOF stream sink pointed at a closed
loopback port delivered nothing and reported nothing — not in the initialize
report, not in the runtime report, and not as a teardown failure. The same sink
pointed at a live loopback listener made one connection per event, so that
silence is a swallowed failure and not an unattempted one. The OpenTelemetry
path is different: a failed export is countable through
`runtime_diagnostics()`, and clearing the plugin configuration raises a
classified delivery failure. Techtree therefore cannot ask Relay whether an ATOF
event was dropped, may never claim lossless delivery, and finds missing events
only by comparing observed identities against a profile's declared expectations.

The typed `ConfigReport` declares a `runtime_diagnostics` list as required, but
every validate, initialize and report call in this spike returned a mapping
carrying only `diagnostics`. The key must be read defensively and its absence
proves nothing about delivery.

**Flush proves nothing about durability.** A seven-event run had already reached
the file before any flush was requested, and the same seven events survived an
immediate `os._exit`. Neither observation proves durability or losslessness at
any larger size. Worse, the raw file that survives a hard death says nothing
about having been abandoned: a truncated stream and a complete stream are
indistinguishable from the bytes alone.

**The ordered flush refuses inside the subject's event loop.** The synchronous
subscriber flush raises when a loop is running and names the async alternative.
The exporter's own flush does not refuse, so a caller that flushes only the
exporter gets no warning that queued subscriber delivery was never awaited.
Teardown must run outside the subject's loop, or await the async flush.

**ATIF is lossy, and the two producers disagree.** Relay's own plugin export and
the NeMo Agent Toolkit converter both emit ATIF-v1.7 from the same seven-event
stream and disagree on how many steps that stream contains — two against four.
Both erase the refused model call that ATOF records with
`otel.status_code: ERROR` and an exception type; the converter's projection
reports that same call as `completed`. The converter also loses the agent name
and the session identity, because it never sees the plugin configuration. No
terminal status, failure class, reward or coverage denominator may be read from
ATIF. ATOF is authoritative and coverage is calculated over ATOF event
identities.

The native ATIF file is not a redacted summary either: it embeds the complete
raw ATOF stream under `extra.observed_events`. It is treated as private local
evidence exactly like the ATOF file.

**The Codex Relay path cannot use the newest stable Relay.** The Fabric 0.2.0
Codex adapter resolves the `nemo-relay` CLI, runs `--version`, and raises unless
the result falls in `>=0.7.2,<0.8.0`; every pre-release is rejected outright.
The newest official stable Relay is 0.8.2. The Codex harness extra already pins
`nemo-relay-cli-bin==0.7.3`, which is inside that band, so the path is reachable
— but only on a Relay generation Techtree does not otherwise adopt, so Techtree
may not assume one Relay client API across the two generations. The two Python
surfaces were not compared and no such comparison is retained here. Hermes has
no such
constraint: `hermes-agent==0.19.0` declares `nemo-relay<1.0,>=0.5` under an
optional extra and installs no Relay at all, so Techtree must pin the Hermes-side
Relay itself.

**No subject ran under Relay through either adapter.** No Hermes trajectory and
no Codex gateway run was observed. The Hermes environment names, the forced
append mode on its ATOF file sink, its rejection of ambient Relay configuration,
its documented direct ATIF/ATOF fallback when TOML initialization fails, and the
whole Codex gateway lifecycle are read from adapter source, not from an executed
run. Both profiles record that as an unobserved blind spot rather than assuming
it works.

## Coverage semantics

`relay-coverage-v1` calculates one status per invocation from ATOF alone.

`not_requested` means the Campaign selected native-only evidence: no Relay
configuration was written, no plugin registered, no artifact exists. It is not a
failure and carries no reason codes.

`unavailable` means Relay was requested and produced no usable evidence: the
plugin never registered before the subject started, no ATOF artifact was
produced, the harness fell back to its own direct path so Techtree's
configuration was not in force, the Codex gateway never became ready, or the
ordered teardown never ran, a hard process death included.

`incomplete` means Relay produced evidence that does not satisfy the profile: a
required expected identity is missing, a scope start has no matching end, the
root agent scope did not both open and close, a delivery or teardown diagnostic
was recorded, or a size bound was hit and the stream was truncated.

`complete_for_profile` is calculated, never asserted. It requires registration
before subject start, an opened and closed root scope, every required identity
from every declared source correlated to an observed event, no missing required
identity, no delivery or teardown diagnostic, a completed ordered teardown
including flush and shutdown, and both the profile digest and
`relay-coverage-v1` pinned in the evidence statement. The denominator is fixed
from the declared sources before the stream is read, so coverage can never be
completed by shrinking it, and an empty denominator is never complete.

Expected identities come from three declared sources. The Fabric execution
receipt supplies the invocation boundary and therefore the required root agent
scope pair. The Verifiers trace supplies the ordered model requests and tool
calls and therefore the required LLM and tool scope pairs. Native harness events
supply the harness's own lifecycle marks, which are recorded when present and
never required, because no profile can enumerate them in advance.

## Teardown

The ordered teardown is: await the subject result, confirm quiescence when
available, close the root scope, force-flush ATOF subscribers, clear and shut
down Relay, stop the Codex gateway where one exists, inspect plugin and delivery
diagnostics, hash ATOF, derive or collect ATIF, validate correlations, then write
the evidence statement. Clearing the plugin configuration can raise a classified
delivery failure; that raise is a diagnostic to record, not a run to discard.

## Size bounds

Relay enforces none. The retained seven-event stream is 2813 bytes on disk, and
its largest single event is 565 bytes — that figure is the longest JSON line in
the same file, counted in bytes and excluding its trailing newline, while the
2813 is the whole file. Its native ATIF file is 5946 bytes because it embeds the
whole stream again. A stream sink issues one request per
event, so volume is linear in events with no batching. Every bound in the
profiles — bytes per invocation, events per invocation, bytes per event, gateway
log bytes — is a Techtree limit, and hitting one makes a run incomplete. A bound
may never be raised to make a run look complete.

## Protected actions

None were taken. No package was published, no upstream issue or pull request was
sent, no host installation or configuration was changed, no Relay CLI was
executed, no gateway was launched, and no paid or real-model work ran. Release
admission is a separate founder decision; `release_admitted` stays false in the
contract record and in both profiles until that decision is recorded.

## Consequence

WP3 must build coverage on ATOF and treat ATIF as an interchange artifact only;
must derive the denominator from declared sources before reading the stream;
must run teardown outside the subject's event loop and catch the teardown raise;
must own every size bound and every dropped-event conclusion, because Relay
reports neither; and must classify a run with no teardown record as unavailable
rather than trusting a file that happens to exist.

Two decisions belong to the founder, not to WP3. First, whether the Codex Relay
path is in scope for v0.2.0 at all, given that the locked Fabric adapter refuses
the newest stable Relay; the alternative is deferring Codex Relay evidence until
an adapter release widens the band. Second, whether Relay 0.8.2 is adopted for
the Hermes path while the Codex path, if kept, runs on 0.7.3 — two Relay
generations inside one release line. No compatibility shim may be written to
paper over either question.
