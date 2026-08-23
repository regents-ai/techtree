# Security, privacy and no-upload review — Techtree Climb v0.1

Ticket `techtree-python-ndq.3.7` · contract `docs/release/contracts/wp11g.md` ·
binding decisions 0014, 0015, 0023 · spec §9.12–9.13, §15.8.

Reviewed at `techtree-python` `679e8605`, `techtree-plugin` `0b0052fa`,
`techtree-ash` `32c70576`. Machine-readable form:
`release/security-review.json`.

## Verdict

**One stop condition is triggered.** Three of the contract's four are clear on
evidence gathered for this review; the fourth is not.

| Stop condition | Result |
|---|---|
| Any mutation request to techtree.sh | clear |
| Any upload path reachable | clear |
| Any permission mode looser than specified | **triggered** — the plugin state root is 0755, not 0700 |
| Any scrubber case leaking | clear — all seven redact |

The triggered condition is `techtree-python-oj8`. It exposes no content: the
directory below it is `0700` and the staged Skill inside that is `0600`. What
it exposes is that the directory exists. It is a one-line fix in a repository
this review has read-only access to, and it is the reason this ticket is not
closed as fully satisfied.

Everything else the contract asks for is either satisfied on evidence or
dispositioned in the table at the end with a risk, a reason, a scope and a
ticket.

## What is new here, and what was already true

Most of this release's security work was done before this pass. Ten SEC
findings from an internal review (`ndq.3.26` through `ndq.3.35`) are closed
with fixes and tests. The wheel has been inspected, the plugin pinned, the
scanner dossier written, the orphan bound proved by a real kill. This review's
job was to assemble that, verify it rather than transcribe it, and fill the one
hole the contract left open.

That hole was the second of the three no-upload methods. WP11e said so itself:

> This is the observation WP11e can reasonably make; the full three-method
> capture is WP11g.

Its sampler polled established TCP connections every five seconds. That yields
an address and a port. It does not yield a method, a host name, or a route —
and the claim under review is about methods and routes. **That capture now
exists** (`release/network-method-log.json`), and the destination evidence is
assembled and recounted in `release/destination-capture.json`.

Where a number appears below, it was recomputed for this review from the file
it came from, not copied from an earlier record. Two places where that
recomputation disagreed with an earlier record are named.

## Supply chain

The wheel is `sha256:5a402a43…`, built from commit `a3ea8c58…`, and
`release/wheel-inspection.json` passes 19 of 19 checks. It was rebuilt twice
from two independent fresh clones of that commit and produced the same bytes
both times. Its provenance stamp exists only inside the artifact — `git
ls-tree` returns nothing for the stamp path, and `.gitignore` keeps it out of
the tree — so the wheel names its own source without the tree being able to
lie about it.

The plugin is pinned to the exact 40-character commit
`0b0052fa68406ac4a63e4bf1fa1a6d00cf429815`. Branch names and floating versions
are refused by the install-plan validator, not only discouraged by
documentation.

Both lockfiles resolve against `https://pypi.org/simple` and nothing else. The
CLI's lock holds 37 packages and **contains no HTTP client at all**. The
engine's lock holds 110 and does contain them — `httpx`, `requests`,
`aiohttp`, the OpenAI client — which is the design and is the reason the
no-upload claim is worded the way it is. The engine's one non-registry
dependency is pinned to an exact git revision. `uv lock --check` resolves both
without change.

`shell=True` appears nowhere in `src/` or `tools/`. Every subprocess in the
package is an argv array. No auto-update or self-update path exists. The
plugin's install-plan validator rejects a plan carrying executable fields,
requires `argv` to be an array, requires the installer to be the fixed
executable, requires the argv to install exactly the pinned requirement, and
refuses `requires_confirmation: false` outright — so nothing a model writes can
become something the machine runs at install time.

ReleaseCore equality was re-verified by byte comparison rather than by
comparing digests anybody wrote down. `cmp` reports all four copies identical —
`techtree-python/release/`, the packaged copy inside `src/`,
`techtree-plugin/`, and `techtree-ash/priv/releases/climb-v0.1.0/` — at
`sha256:c037f457…`.

## Local permissions

Measured, not read out of the code. A scratch home was created under a
deliberately permissive umask and the CLI driven through it; then every file
and directory in the eleven live Techtree homes preserved in the durable
certification evidence was stat'd.

| Target | Specified | Measured | |
|---|---|---|---|
| Techtree home root, and every level above it Techtree created | 0700 | 0700 | pass |
| `cache`, `drafts`, `engines`, `identities`, `runs` | 0700 | 0700 in all eleven homes | pass |
| Private signing key | 0600 | 0600 on every one in the evidence | pass |
| Logs | 0600 | 0600 on every `worker.log` in the evidence | pass (untested — `yl8`) |
| Supervision record | 0600 | 0600 on all 18 in the evidence | pass |
| Proposal temp root | 0700 | 0700 | pass |
| Temporary proposed `SKILL.md` | 0600 | 0600 | pass |
| **Plugin state root** | **0700** | **0755 under umask 022** | **fail — `oj8`** |

The first row is the interesting one, because it is the finding `ndq.3.33`
raised: hardening only the leaf hardens the room and not the corridor. Under
umask 022 the CLI created `Library`, `Library/Application Support` and
`Library/Application Support/techtree`, and all three came out `0700`.
`src/techtree/fs.py:57-101` walks the missing ancestors and creates each one at
`0700` at creation rather than chmod'ing afterwards, so there is no instant in
which the directory exists and is readable. `tests/unit/test_fs.py:316` holds
it under a `0o000` umask fixture, so the test measures the chosen mode and not
the ambient one.

The last row is the same defect, in the plugin, unfixed.
`techtree-plugin/services/proposal.py:105` still calls
`mkdir(parents=True, exist_ok=True)` and then hardens only the leaf. Reproducing
that call sequence exactly under umask 022:

```
0755  <XDG_STATE_HOME>
0755  <XDG_STATE_HOME>/techtree-hermes      <- the contract says 0700
0700  <XDG_STATE_HOME>/techtree-hermes/proposals
0700  .../proposals/techtree-proposal-<id>
0600  .../proposals/techtree-proposal-<id>/SKILL.md
```

The test that ought to have caught it is named
`test_staging_creates_private_directories_all_the_way_down`
(`tests/plugin/unit/test_proposal_service.py:293`) and does not go all the way
down — its loop starts at `staging_root` and never looks at
`plugin_state_home()`. It also runs without a permissive-umask fixture, so it
would pass under a typical umask even if the modes were wrong.

A whole-tree census found no other Techtree-written path looser than specified.
Two things it did find are worth stating so nobody has to rediscover them.
First, the installed engine's virtual environment holds 9,195 directories at
`0755` and 72,057 group- or world-readable files (70,892 at `0644`, 1,160 at
`0755`, 5 at `0666`); those are written by `uv` under the operator's umask, and
the `engines` directory above them is `0700`, so no other user can reach any of
it. Second, fifteen engine-written files are `0644`, and
all fifteen belong to one run: the SIGKILL failure-injection run whose
evaluation children were orphaned. Every other run in the evidence, including
all four recertification runs, carries the same filenames at `0600`. The
correlation with the defect decision 0029 fixed is clear; this review did not
establish the causal chain and does not assert it. All fifteen sit inside
`0700` parents.

## Secrets — the seven adversarial cases

The contract names seven. Each was constructed and pushed through both
scrubbers on 2026-08-23, and the output checked for the secret verbatim. This
is measured behaviour, not a reading of the patterns.

| Case | Python CLI | Plugin | Test |
|---|---|---|---|
| Bearer token | redacted | redacted | both |
| Token in URL userinfo | redacted | redacted | both |
| Token in query string | redacted | redacted | **none, either side** |
| Quoted JSON API key | redacted | redacted | both |
| Private key block | redacted | redacted | **plugin only** |
| Nested list/dict | redacted | redacted | both |
| Package-manager stdout/stderr | redacted | redacted | both |

Seven of seven redact. Five of seven have a test. The two gaps are
`techtree-python-iql`, and they are worth understanding rather than just
counting: on the Python side the query-string case is caught incidentally by
the secret-assignment rule rather than by a rule written for it, and the PEM
case is caught by the opaque-run rule scanning line by line, which leaves the
`-----BEGIN-----` framing intact and would leave a final body line shorter than
forty characters with it. Both work. Neither is held by anything.

Separately: both recursive walks cover strings, mappings and lists, and a tuple
or a set passes through with its secret intact. That is unreachable through the
shapes that exist — the Python walk is typed `JsonValue` under strict mypy, and
the plugin's input is a JSON-decoded envelope, which never contains a tuple —
but it is one refactor from being reachable. `techtree-python-8yn`.

## No upload — three methods

The claim, kept narrow per decision 0028:

> Techtree does not upload local Episodes, Traces, proofs, or Skill proposals.
> Model requests are sent to the selected providers.

The second sentence is not a hedge bolted onto the first. A comparison buys
model tokens; those requests go to the provider the Campaign names, and the
claim says so rather than implying a machine that never speaks.

### Method 1 — static route and client audit

**The website is read-only.** Eleven routes, every one a `GET`
(`lib/techtree_web/router.ex:40-64`); `HEAD` is synthesized by `Plug.Head`. A
mutating method on any published address is answered `405` with an `Allow:
GET, HEAD` header and a typed non-retryable error
(`lib/techtree_web/method_surface.ex:26-47`), and the published set is derived
from the routing table itself (`:52-54`), so the two cannot drift apart. The
plug sits ahead of the router. `test/techtree_web/router_test.exs:64-91`
asserts it across eleven paths and four verbs.

The `ndq.3.34` items are all in place: no multipart parser in the endpoint's
parser list, no `Plug.MethodOverride` anywhere in the chain, and security
headers on static serving. A 9 MB body to a published address is `405` *and*
the body is never fetched (`endpoint_test.exs:76-85`).

**The CLI has exactly one outbound call site.** An AST scan of every module
under `src/` — not a grep — finds two network imports in the entire shipped
package, both `urllib`, both in `skills/starter.py:53-54`. The call site is
`_download_document` at `starter.py:367-399`, and the method is a literal:

```python
request = urllib.request.Request(
    url, method="GET", headers={"Accept": "text/markdown, text/plain, */*"}
)
```

There are zero `POST`, `PUT`, `PATCH` or `DELETE` call sites. There is no HTTP
client package in the CLI's 37-package lock to make one with. The string
`techtree.sh` does not appear in `src/` at all — the object URL comes from
ReleaseCore at runtime, and `release/models.py:99-113` constrains its shape and
rejects a `user:token@host` form so a credential cannot ride in it. The URL is
scheme-guarded before any fetcher sees it (`https`, or `http` only to this
machine), the response is size-bounded, and the bytes are verified against the
release-pinned digest afterwards — transport is not what makes them
trustworthy.

Model requests do not happen in this package. The engine is launched as a
subprocess with its own environment (`verifiers/child.py:380-391`), the
credential is handed to that child by name, and the endpoint is resolved by the
engine rather than by Techtree.

**The plugin opens no socket.** Three independent mechanisms hold this, which
matters more than one strong one. Its doctor AST-scans every runtime module
against a networking-module set and against the standard library, both blocking
checks (`doctor.py:474-568`). An independent scan in the test suite covers a
different and wider set, including `openai`, `anthropic`, `tenacity` and
`backoff` (`test_one_generation_request.py:294-309`). And the third is not
static at all: `test_no_registration_side_effects.py:50-110` replaces
`socket`, `urllib.request.urlopen`, `http.client`, `subprocess` and the `exec`
family with tripwires and requires `register()` to complete anyway. Both AST
scans read literal imports only, so a dynamic import would evade them; none
exists, and the runtime seal would catch the attempt regardless.

### Method 2 — instrumented method, host and route log

`release/network-method-log.json`, produced by `tools/network_method_probe.py`.
This is the method WP11e could not supply.

The recorder is installed as a `sitecustomize` module on the child's
`PYTHONPATH`, so it is in place before any application code imports, and it
records three layers: `http.client.HTTPConnection.putrequest` for the method,
route, host and port; `socket.getaddrinfo` for the name being resolved; and
`socket.socket.connect` for the raw destination. Every request is recorded as
it is made. Unlike a five-second poll, nothing can happen between samples.

The first step is a deliberate `GET` to a closed loopback port, and it must
appear in the recording. Without it, every zero below would be the silence of a
dead instrument rather than of a quiet product.

The CLI was then driven through its whole command surface that does not require
a paid comparison. **One request was made:**

```
GET https://techtree.sh/api/v1/objects/sha256:2aff27070177d9f37b99d5bef6fa372586887e78180005195cb808971ae55a4c
    → 2a09:8280:1::177:ed19:0 : 443
```

`--version`, `doctor`, `release info`, `release verify`, `climb list`, `climb
show` and `run status` made none. The second `skill starter` made none either:
the verified cache answers without a fetch, so materialising the Skill twice is
not reading it twice. Mutating requests: zero. All five assertions pass.

What this does not cover is stated in the record itself: the paid comparison
path, which the probe never runs because it spends money; non-Python children
such as Docker, `uv` and `git`, which a `sitecustomize` recorder cannot see
inside; and the engine's own process. Method 3 covers where those go.

### Method 3 — destination capture

`release/destination-capture.json`. Three legs of five-second `lsof` sampling
over the journey's process tree, 884 samples in total. The sample counts were
recounted from the logs for this review.

The union of every non-loopback peer across all three legs is five addresses:
`104.18.8.113` and `104.18.9.113` (the model provider, corroborated by all 117
resolved engine configurations naming
`base_url = https://api.pinference.ai/api/v1`), and three Fastly addresses
serving the package index during engine installation. **Nothing else appeared.**
Zero unexpected destinations.

Two honest qualifications. The capture ran with reverse DNS disabled, so it
recorded addresses; naming them is an attribution made from the engine
configuration and from what each process was doing, not something the capture
itself recorded. And a five-second poll supports "this peer was never observed",
never "this request was never made" — the worked example is in its own data,
because the deliberate `techtree.sh` read happened and the sampler recorded zero
connections to it. It is sub-second; the poll is five-second. That is exactly
why the contract requires three methods and not one.

One correction: the re-certification report states 375 samples where its own log
holds 378. The report was written while the sampler was still running.
`release/destination-capture.json` records the log's count and names the
discrepancy.

## Verifiers push

Off at both layers, and verified at a third.

In the compiled configuration, `push` is not a default that could be
overridden — it is `Literal[False]` (`verifiers/config.py:258`), so a
configuration that spells `push = true` is unrepresentable. On the argv, the
child is launched with `--no-push` on both the real eval and the dry run
(`verifiers/child.py:105`, `:163`, `:179`), because a flag on argv overrides
whatever the file says. And the product reads the engine's own *resolved*
configuration back and checks it (`verifiers/verify.py:255-259`).

In the durable evidence: **178 verifiers configuration files, every one of them
`push = false`.** 117 `config.toml` and 61 `input.toml`, across every run
directory. No other value appears anywhere. Read for this review, not
transcribed.

Two product-path tests hold it rather than unit tests of a helper:
`tests/integration/test_real_variant_run.py:163` asserts it through the real
compile-write-dry-run-child path, and `tests/integration/test_eval_compile.py:327`
asserts on what the installed engine itself resolved.

There is no uploader in Techtree's source at all; the uploader is upstream's.
Its non-invocation is proved behaviourally, not argued:
`tests/preflight/test_verifiers_eval_contract.py:405` asserts the module never
enters `sys.modules` on a complete run with push off and a credential present,
and `:422` is the control that proves the probe fires when push is on.

## Orphan bound

`release/orphan-bound-analysis.json`, decision 0029. The bound on one
comparison is USD 2.4152 against a declared maximum of 2.50, checked as a
run-start precondition.

The containment was proved by injection rather than argued. The run worker was
SIGKILLed mid-run (`run_ba3998e2a0d94126bc7426d0c6b32aab`, pid 77557, four
subject containers running). All four containers were gone 0.55 s later. Both
supervisors and both evaluation processes exited 1.08 s later, and both
supervision records were written at the same moment, mode `0o600`, reason
`parent_lost`, without escalating to SIGKILL. Total cleanup 1.1 s. Zero
containers never disappeared; zero leftover running containers. No report and
no proof bundle were produced, which is the point: a killed comparison yields no
result.

Containers were identified by before/after id diff with the exact ids recorded
at the moment of the kill, never by image, and no forced removal or sweep was
used — the only cleanup path exercised is the supervisor's SIGTERM to the
evaluation's own process group and the pinned engine's own teardown.

## The Skill conflict scan, and what was deleted

The contract requires this limitation to be recorded, so here it is plainly.

The plugin's envelope-conflict detection is a deterministic, statement-level
scan: conservative, affirmative-instruction-only. **A paraphrase can pass it.**
v0.1 does not add an LLM-based semantic scanner, and that is a decision rather
than an omission — an LLM scanner would put a model in the position of judging
whether another model's output is safe, which is a larger design question than
v0.1 should answer in passing.

Four things hold instead, and none of them is the scan. The founder Skills are
pinned by exact digest and are byte-identical across three repositories. There
is a manual security review — this document, and the ten closed SEC tickets.
There are negative tests for known conflicting instructions. And the safety
envelope is hardcoded: the one-turn rule, the no-upload rule and the no-auto-run
rule are not expressible in a Skill and cannot be overridden by one.

Two deterministic guards were deleted by founder ruling during this cycle, and
the review would be dishonest without them. `techtree-python-5f6`: the
numeric-claims heuristic had no left-hand boundary on its signed-number pattern,
so `modulo-97` read as the number −97 — on a task family whose entire subject is
arithmetic modulo 97. It consumed one paid revision that was otherwise perfectly
good. `techtree-python-0mx`: the generic secret-assignment heuristic flagged
`that token: no reasoning` as a credential, on a Climb about returning a token.
Both were resolved by deletion.

What that means, stated straight: the deterministic surface is smaller than it
was. What was removed was the part that guessed at meaning from surface text and
produced false positives, not the part that holds the envelope. The copy-guard
remains and was strengthened in the same cycle — `ndq.3.28` removed the
minimum-length skip that made it a no-op for short inputs, which was the entire
task family, and the regression test uses a two-character input. The paraphrase
gap is unchanged by the deletions: it was there before them and it is there now,
scoped to future untrusted operator Skills. In v0.1 the only inputs that reach
that path are two digest-pinned founder Skills and one model-authored revision
that a person sees before anything happens with it.

## Hardening adopted this cycle

Two changes came out of an independent source review by a Hermes agent
belonging to the founder, and both are in `0b0052fa`.

**The CLI child receives ten named variables and nothing else.** The bridge used
to hand it the host session's whole environment; it now builds one by exact name
from `CLI_ENVIRONMENT_ALLOWLIST` — `PATH`, `HOME`, `TMPDIR`, `XDG_DATA_HOME`,
`TECHTREE_HOME`, `TECHTREE_LOG_LEVEL`, `LANG`, `LC_ALL`, `LC_CTYPE`, `TERM`.
Provider credentials are deliberately absent; a run authenticates from
Techtree's own configuration under `HOME`. Five tests hold it, including a
canary: a wallet key planted in the host session reaches neither the child's
environment nor any envelope the plugin returns. What the platform itself adds
to any child is measured and subtracted, so an unaccounted-for variable is a
test failure rather than a shrug.

**The manifest declares what the plugin does with the machine**, and the
declaration is enforced by a closed-field grammar rather than left as a comment.
Adding `capabilities:` or `requires_env:` to `plugin.yaml` is a hard parse
failure in the plugin's own doctor.

## The scanner

`release/hermes-scanner-dossier.md` records the appeal in full. The short
version: the install-time scanner returned **DANGEROUS, 17 findings, no
override** at `880aa8a`, because a security-tested plugin structurally contains
the strings it defends against. Moving the adversarial corpus into
`techtree-python` — where the whole battery still runs, 791 tests green — took
the verdict to **CAUTION, five findings**, with the install decision `BLOCKED —
requires confirmation`. Nothing measured moved: ReleaseCore, both Skill digests
and the wheel digest are unchanged.

Two things were refused and remain refused: no fixture was disguised, renamed or
encoded to slip past a scanner, and nothing anywhere tells a user or an agent to
switch scanning off.

The residual is real and is in the table below. The install now depends on a
person reading five findings and confirming, and a reader who confirms without
reading gets the same install as a reader who reads.

## Finding disposition

Twenty findings. One is not accepted; nineteen are, each with a named risk, a
reason, a scope and — where one exists — a ticket. Six tickets were opened by
this review.

| # | Finding | Disposition | Risk | Why accepted | Scope | Ticket |
|---|---|---|---|---|---|---|
| 1 | Plugin state root is 0755, not the specified 0700 | **NOT ACCEPTED — stop condition** | Another local user sees the directory exists; no content is exposed | Not accepted. The contract names a mode; low severity is a reason to fix it cheaply, not to move the line | The plugin's state directory, on every machine that stages a proposal | `oj8` |
| 2 | Unmetered generation billing: the host can bill for an answer with no content and the user's one revision is spent | Accepted | A first-time user pays and receives nothing, twice observed in acceptance | The host owns the sampling stack, ceiling and billing; metering it would claim knowledge the product does not have. The dossier states the division rather than implying coverage | The one guided revision. Not the comparison path, whose spend is bounded and pre-checked | `bbu`, design in `cjj` |
| 3 | A stale but present Prime key passes doctor's shape check | Accepted | The exact failure the check exists to prevent — configured-looking run, nothing can answer | Validating means spending a request from a readiness check; the failure is loud, typed and lands before any episode completes | The pre-run readiness check only | `aww` |
| 4 | `uv` selects an unsupported Python and the first doctor fails | Accepted | First-run failure on an otherwise fine machine | Nothing is wrong with the product — the metadata is right and the doctor names the problem precisely. One line of published copy is wrong | Published install instructions, on machines defaulting to 3.14 | `vom` |
| 5 | Scanner install depends on a human confirming five caution findings | Accepted — and it is the outcome asked for | A reader who confirms without reading gets the same install | Both alternatives were refused and stay refused. The corpus move took DANGEROUS-no-override to CAUTION-with-confirm, and onboarding copy states the verdict in advance | Plugin installation, until trusted-source status | `llv` (closed); appeal outstanding |
| 6 | WP11f onboarding journey evidence is still pending | Accepted as an open dependency | This review does not cover the journey a community user would take | WP11f is its own ticket with its own contract, sequenced after this one. Claiming its evidence here would be padding | The community onboarding path | `ndq.3.6` |
| 7 | Skill conflict scan is deterministic; a paraphrase can pass | Accepted — recorded per contract | An operator Skill could conflict with the envelope in unmatched words | Four things hold instead, none of them the scan; the envelope is hardcoded and not overridable | Future untrusted operator Skills | `cjj` |
| 8 | Two deterministic guards deleted by founder ruling | Accepted | Less deterministic checking of model-authored text than the design carried | Both destroyed paid turns on ordinary English; neither held the envelope. Copy-guard untouched and strengthened in the same cycle | Guided-revision narrative and Skill-scan paths | `cjj` |
| 9 | Scrubber cases 3 and 5 have no test (both redact today) | Accepted | Behaviour held by nothing; both are caught by rules not written for them | No case leaks, which is the stop condition. Measured behaviour recorded here so nothing rests on an invisible assumption | Error scrubbing on both sides of the CLI boundary | `iql` |
| 10 | Recursive scrubbers do not walk tuples or sets | Accepted | An unscrubbed credential if such a shape ever arrives | Unreachable through the shapes that exist — typed `JsonValue` on one side, JSON-decoded on the other. One refactor from reachable | Error details on both sides | `8yn` |
| 11 | No test asserts the worker log is 0600 | Accepted | A future launcher change could loosen it silently | The mode is correct today and measured on every worker log in the evidence | The worker log only | `yl8` |
| 12 | Static asset paths answer 404, not 405, and are untested | Accepted | None to writability; the surface answers two ways for two kinds of read | Cosmetic. Nothing is writable and no artifact is reachable | Website static paths | `ytu` |
| 13 | Plugin AST no-socket scans read static imports only; `skills/` excluded | Accepted | A dynamic import could evade the two static scans | Three mechanisms, and the third is a runtime tripwire seal, not a scan. No dynamic import exists. The `skills/` exclusion is correct — prompts, not loaded code | The plugin runtime | none; revisit if the plugin gains its own plugin system |
| 14 | The engine's lock holds full HTTP clients | Accepted — this is the design | The claim cannot rest on "no client exists" for the engine | The engine is what talks to the provider, which the claim does not deny. Its configuration is checked, not trusted: 178 of 178 resolved configs have push off and point at the provider | The paid comparison path | none — a scope boundary of the claim |
| 15 | The sampler cannot prove absence | Accepted — why the contract requires three methods | Reading its zeros as proofs would overstate them | The three methods are complementary by design; no single one carries the claim | Method 3's evidence | none — a property of the method |
| 16 | Re-certification report says 375 samples; its log holds 378 | Accepted — corrected here | A published figure that does not match its source | Written while the sampler was still running. Nothing depends on the figure; the correction is in `destination-capture.json` | One number in one WP11e record | none |
| 17 | Fifteen engine-written files at 0644, all in the orphaned SIGKILL run | Accepted | None reachable — all fifteen sit inside 0700 parents | Every run after the 0029 fix is uniformly 0600. The correlation is recorded; the causal chain is not asserted | One historical run directory | none |
| 18 | ReleaseCore integrity is not checked on the run path | Accepted — carried from WP11e | A locally modified ReleaseCore changes which object is fetched; the digest check is self-consistent rather than independent | Anyone who can rewrite files in a 0700 home already has the account. `release verify` exists, is documented and is offline | Local tampering | none filed at WP11e |
| 19 | `uv tool install --force` can serve a stale cached wheel | Accepted | Certifying a build that is not the one under test | Not a Techtree defect, and the product caught it — `release info` reported the stamped commit actually installed. Current `dist/` wheel and sidecar agree | Release and acceptance install argv | `kml`, `oce` |
| 20 | The compiler relies on a type literal rather than passing `push` explicitly | Accepted | A reader must follow the type to see push is off | The literal is stronger than an argument: `push = true` is unrepresentable. The argv says it out loud and the resolved config is read back | Readability of one construction site | none |

## What could not be assembled

Three things, named rather than papered over.

**The paid comparison path was not instrumented.** No paid runs were authorised
for this review, so the method-2 log covers the whole non-paid command surface
and stops there. What the paid path contacts is covered by method 3 — 884
samples across three legs, five addresses, all expected — and by 178 resolved
engine configurations, but not by an in-process method log. Producing one would
cost a comparison.

**Docker, `uv` and `git` were not instrumented.** They are separate
executables, not Python, so a `sitecustomize` recorder cannot see inside them.
What they contact is registry and package-index traffic, which method 3
enumerates as expected. `github.com` is on the expected list and was not
observed in any leg; the legs reused a warm cache, and a five-second poll
cannot prove a short-lived connection did not happen. It is recorded as
expected-and-unobserved rather than as absent.

**The plugin permission defect could not be fixed here.** `techtree-plugin` is
read-only for this review and the release candidate is pinned at `0b0052fa`.
The finding is measured, reproduced, and filed as `techtree-python-oj8`.

## Outputs

| File | SHA-256 |
|---|---|
| `release/security-review.json` | `080ea86bd3033d4c3adbba7429fc0e4edd689020e7a6abb99553a7f01039641e` |
| `release/security-review.md` | this file |
| `release/network-method-log.json` | `157a5aa5597a65c1483c0e6356b143d4d1034c911c9300a8f977f9b3763547f4` |
| `release/destination-capture.json` | `7f72ac0328a3fcf94ad83c82f5fbd08ea0daef3970b96ce347353449ed35ecfd` |
| `tools/network_method_probe.py` | `cd49bb3bed479fc2de12c19d3e0133419795495f2d80021ecb449ddb0307ec2a` |

The network method log is reproducible: re-run
`uv run python tools/network_method_probe.py --home <scratch> --output <path>`.
It makes one real read of a published content-addressed object and spends
nothing.
