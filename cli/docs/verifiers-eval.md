# Verifiers `eval` — WP6a preflight findings

Ticket: `techtree-python-85a.1.2` (WP6a — Verifiers eval compatibility and
compiler). Spec sections §6.3–§6.9 and §6.12–§6.14.

Companion to `docs/verifiers-pin.md`, which did the same job for `validate`
during PI0. Everything below was observed against the same pinned commit and
nothing else:

```text
PrimeIntellect-ai/verifiers
7e1c47d24d055aae587ee8259f77a3e8e193513a
verifiers 0.3.1.dev21
```

Reproduce with `make verifiers-preflight`
(`tests/preflight/test_verifiers_eval_contract.py`).

**No model was called to produce any finding here.** Every observation is
either a `--dry-run` (which is model-free by construction) or a full `eval` run
driven by `tests/preflight/fixture_subject_env`, whose harness answers without
contacting a provider. A `PRIME_API_KEY` exists in this environment and was
never used to reach a provider; where it appears below it was set to the
literal string `sk-preflight-secret-value` purely to prove that no output file
ever contains it.

---

## CRITICAL — five findings that change WP6

### E0. A `subject` seat needs an environment that declares one — RESOLVED

Spec §6.5 asks for a Verifiers `Env` whose seat is literally named `subject`.
The seat name is the environment config's *field* name, and the environment
class comes from the digested bundle, so nothing in `src/techtree/verifiers/`
can produce one. Against an environment without that seat, a Techtree-compiled
config carrying an `[env.subject]` table fails **at config parse**, before
anything runs:

```text
$ <engine>/.venv/bin/eval @ compiled.toml --dry-run
EXIT=1
1 validation error for EvalConfig
--env.subject
Extra inputs are not permitted
```

This was originally raised as a STOP-AND-NOTE because the reference package
exported only `ProcedureTransferTaskset`. The bundle addendum was approved and
`procedure_transfer_v1/env.py` now ships `ProcedureTransferEnv`, so the shipped
Campaign compiles and dry-runs against the real engine. The failure above is
kept here because it is still the exact symptom a future package that forgets
to export its environment will produce, and the preflight still asserts it.

### E1. `push` defaults to **true** and uploads the participant's episodes

`EvalConfig.push` defaults to `True`, and
`verifiers.v1.utils.platform.push_traces` uploads one sample per Episode — the
complete native Episode, including prompts and the subject's replies — to
`https://api.primeintellect.ai/evaluations/`, authenticating from
`$PRIME_API_KEY` or `~/.prime/config.json`. A compiled config that merely
*omits* `push` therefore ships the participant's trajectories off the machine
the moment a Prime key is present, which is exactly what the DataPolicy
forbids.

`push` is **not** excluded from the persisted config, so the resolved
`config.toml` is a faithful audit of what was chosen. Two independent controls
were both confirmed to work, and Techtree uses both:

```text
config.toml            push = false      -> resolved config records push = false
argv                   --no-push         -> overrides push = true in the file
```

Observed: a file saying `push = true` re-run with `--no-push` persists
`push = false`; the same file with no flag persists `push = true`.

### E2. `--dry-run` writes **only** `config.toml` — no `traces.jsonl`, no `eval.log`

The spec's §6.3 sentence "Evaluation output contains `config.toml`,
`traces.jsonl`, and `eval.log`" is true of a *real* run and false of a dry run.
`verifiers.v1.cli.eval.main` takes the dry-run branch before logging is
attached to a file and before `save_config` runs, so the dry-run output
directory holds one file:

```text
$ <engine>/.venv/bin/eval @ compiled.toml --dry-run --output-dir dry/
EXIT=0
dry/config.toml
```

`verifiers/outputs.py::require_output_files` must therefore be applied to a run
directory, never to a dry-run directory, and `verify.py`'s dry-run check reads
`config.toml` alone.

One consequence is easy to miss. `--output-dir` on argv overrides the file, and
`output_dir` is *not* excluded from the persisted config, so a dry run
redirected away from the real run directory writes a resolved config recording
the **dry-run** directory. Comparing that document against the compiled one
therefore has to fold the redirection in — `verify.py` compares the compiled
config with `output_dir` set to the directory it actually passed, and checks
the real output directory separately.

### E3. Dry-run validates the *config*, not the *experiment*

Dry-run is a real gate — it imports the taskset package, narrows the env config
to the concrete Env class, and rejects unknown keys — but it stops there. Four
things Techtree cares about pass a dry run cleanly and fail later, or never:

| Config | Dry-run | Where it actually fails |
|---|---|---|
| `harness.use_bundled_skill = true` | exit 0 | never — it silently changes the experiment |
| `harness.disabled_tools = [...]` | exit 0 | mid-run, in `HermesAgentHarness.launch` |
| `harness.skills = ["/does/not/exist"]` | exit 0 | mid-run, in `Harness.install_skills` |
| no taskset id at all | exit 0 | mid-run, in `Env.__init__` |

The last one is the sharpest: with a `@ file.toml` argument the CLI's usage
gate is skipped, an empty taskset id resolves to `SingleAgentEnv`, no plugin is
imported, and the resolved config is written to
`outputs/no-taskset--<model>--bash/<uuid>/` **relative to the current working
directory**. A dry run that "passes" can therefore have proven nothing and have
written outside the run tree. Techtree always compiles an explicit taskset id
and an absolute `output_dir`, and `verifiers/config.py` — not the dry run — is
what rejects rows one to three.

An unknown top-level key and an unresolvable taskset id both exit `1`, so the
dry run is worth running; it is just not sufficient.

### E4. `traces.jsonl` line order is completion order, and the gap can be large

The same fact `docs/verifiers-pin.md` C0 recorded for `results.jsonl` holds for
`eval`, and this preflight demonstrates it directly rather than by inference.
Running four tasks at `max_concurrent = 4` against a harness whose per-task
delay decreases with task index produced:

```text
line 0 -> task idx 3
line 1 -> task idx 2
line 2 -> task idx 1
line 3 -> task idx 0
```

Exactly reversed. Pairing must join on `trace.task.hash`; §6.11's "line
position is never task position" is not a caution, it is the observed default
under any real concurrency.

---

## The `eval` contract, claim by claim

### The invocation

The conceptual form works verbatim, with `@` as its **own argv token**:

```bash
<engine>/.venv/bin/eval @ <input-config.toml> --dry-run --output-dir <dir>
```

- The console script is the bare name `eval` (`docs/verifiers-pin.md` C3), so
  it is invoked by absolute path inside the engine venv and never through
  `PATH`.
- Command-line flags override the file. `--output-dir` given on argv beats
  `output_dir` in the file, which is how a dry run is redirected away from the
  real run directory without compiling a second config.
- `--rich` defaults to **true** and paints a dashboard; every Techtree config
  sets `rich = false`.
- `--dry-run` is `exclude=True` on the config model, so it never appears in the
  persisted config and the persisted config is therefore runnable.

### The persisted `config.toml`

Written by `verifiers.v1.cli.output.write_config` as
`tomli_w.dumps(config.model_dump(mode="json", exclude_none=True))`. Field order
is model declaration order, so the bytes are deterministic for a given input.

Three fields are excluded from it and one is added to it:

```text
excluded:  uuid, dry_run, resume
filled in: client.base_url  (and client.headers, see below)
```

`BaseClientConfig.apply_prime_config` runs on every validation. When
`api_key_var == "PRIME_API_KEY"` and `base_url` was not set explicitly, it
resolves the URL from `$PRIME_INFERENCE_URL`, then `~/.prime/config.json`, then
`https://api.pinference.ai/api/v1`; and if the resolved host is a
`pinference.ai` host it copies `$PRIME_TEAM_ID` (or the Prime config's team id)
into `client.headers["X-Prime-Team-ID"]`.

Consequences for §6.14's "resolved config matches compiled experiment":

- The comparison must be a **projection**, never a byte comparison. Techtree
  omits `base_url` deliberately (§6.8) and the engine fills it in.
- `client.headers` may gain a team-id header Techtree never declared. That is a
  routing hint, not a credential, but the check must tolerate it.

Re-resolving a resolved config is a **fixed point**: dry-running a saved
`config.toml` again reproduces the same document key for key, with the single
exception of `output_dir`, which the second run's own `--output-dir` overrides.
Verified.

### The output files of a real run

`save_config` creates the directory, writes `config.toml`, and truncates
`traces.jsonl` to empty *before the first rollout*. `eval.log` is created by
`setup_logging` a moment earlier. A real run therefore ends with exactly three
files:

```text
config.toml
traces.jsonl
eval.log
```

Both `config.toml` and the empty `traces.jsonl` appear only after the taskset
package has imported and the env has been constructed — measured at roughly
1.4 s on this machine for a trivial taskset. Progress polling must treat "no
`traces.jsonl` yet" as *pending*, not as an error.

### `traces.jsonl` is append-only, one whole Episode per line

`append_episode` holds a run-wide `asyncio.Lock`, serializes the Episode with
`exclude_none=True`, and appends `bytes + b"\n"` in a worker thread under
`run_shielded`, so an in-flight cancellation still completes the write. Sampled
during a staggered four-task run, the file size went

```text
absent -> 0 -> 1842 -> 3683 -> 5518 -> 7364
```

monotonically, one whole episode at a time, and the file ends with a newline.

Episode shape (top level):

```text
id, env, ok, errors, traces[]
```

Trace shape (the fields WP6 normalization reads):

```text
id, version, verifiers{version, commit}, run{type, id}, agent{config, runtime,
name, trainable}, task{type, data, hash}, rewards{name -> {score, weight}},
metrics, usage, num_turns (derived), nodes, calls, tools, timing, errors,
stop_condition, is_completed, ok, info, extra_usage
```

Two of those are load-bearing for §6.14:

- `trace.verifiers` is literally
  `{"version": "0.3.1.dev21", "commit": "7e1c47d2…3513a"}` — the pin, recorded
  by the run itself. This is the direct source for the "Verifiers
  version/commit match engine descriptor" check; nothing has to be inferred.
- `trace.agent.config` is the fully resolved `AgentConfig` — harness (with
  `version` and `use_bundled_skill` for Hermes), runtime, model, client,
  sampling. This is the *observed* configuration the declared configuration is
  checked against.

`trace.agent.config.client` records `api_key_var` (the **name**), never a key.

### The named `subject` role — §6.5 mechanics, confirmed

`loaders.environment_class(taskset_id, env_id)` resolves the Env from the
taskset's own package when `env.id` is empty, and `_plugin_class` filters the
package's `__all__` by base type. A single `__all__` exporting a Taskset, an
Env and a Harness resolves all three unambiguously — the "exactly one" rule is
per base class, not per module. Observed against
`tests/preflight/fixture_subject_env`:

```text
taskset_class(...)      -> SubjectTaskset
environment_class(...)  -> SubjectEnv
env_config_type(...)    -> SubjectEnvConfig, fields
                           {id, interception, max_concurrent_agents, retries,
                            subject, taskset, timeout}
default_harness_id(...) -> the package itself
```

The seat name reaches the record through
`agent._EpisodeAgent._watch`, which assigns `trace.agent.name = self._name`
where `_name` is the env config's **field name**. A full four-episode run of
the fixture produced `trace.agent.name == "subject"` on every trace and no
trace named `agent` anywhere. `AgentInfo.name` defaults to `"agent"`, which is
why the built-in `SingleAgentEnv` looks nameless — its field is also called
`agent`.

### Docker runtime: the network policy Techtree must set explicitly

`DockerConfig` extends `NetworkPolicyConfig`, whose defaults are
`allow = ["*"]`, `block = []` — **unrestricted egress**. Spec §6.7's
`DockerRuntimeToml` models only `type`, `image`, `cpu` and `memory`, so a
Campaign declaring `network_policy: "restricted"` would compile to a container
with open network access.

`NetworkPolicyConfig` normalizes an empty allow-list to framework-only access:

```text
allow = []   ->   allow = [], block = ["*"]
```

`src/techtree/verifiers/config.py` therefore carries `allow`/`block` on the
Docker table and `egress_for` maps the Campaign's `network_policy` onto them.
It emits the **already-normalized** pair rather than the shorthand:

```text
restricted -> allow = [],    block = ["*"]
open       -> allow = ["*"], block = []
```

Emitting `allow = []` with `block = []` also works, but the engine rewrites it,
and then the configuration Techtree compiled and the configuration the engine
resolved disagree at `block` on every restricted run. Verified by dry run
against the real engine.

A digest-pinned image dry-runs without Docker installed and without the image
existing; provisioning is a WP6b concern.

### Credentials never appear anywhere

With `PRIME_API_KEY=sk-preflight-secret-value` exported across both a dry run
and a full run, the literal value appears in **none** of `config.toml`,
`traces.jsonl`, `eval.log`, captured stdout, or captured stderr. The config and
the trace record the variable *name* (`api_key_var = "PRIME_API_KEY"`) and
nothing else.

`clients.resolve_api_key` reads the variable at request time and falls back to
`~/.prime/config.json` for a `PRIME_API_KEY`-keyed pinference endpoint,
returning the literal string `"EMPTY"` when nothing is found. A run with no
credential therefore does not fail at startup — it fails at the first model
call. `verifiers/credentials.py` exists so that the failure is diagnosed before
Docker is provisioned rather than after.

### Standard output must never be shown to the host agent

With `rich = false` the CLI prints every trace to stdout as indented JSON after
the run:

```python
for episode in episodes:
    for trace in episode.traces:
        print(trace.model_dump_json(indent=2, exclude_none=True))
```

Four trivial traces produced 9.9 KB. Real subject traces carry the full
transcript. §6.10's rule — redirect stdout to a run-owned file, never stream it
— is not a stylistic preference; the default behaviour is a full transcript
dump.

### Cancellation

`install_interrupt()` makes the first SIGINT/SIGTERM raise `KeyboardInterrupt`
so each rollout's `finally` tears down its container, and swallows further
signals during that cleanup. The CLI then exits `130`. §6.14's "a graceful
cancellation exit code maps to cancellation rather than scientific invalidity"
has `130` as its concrete value, and §6.10's `terminate(grace_seconds)` must
send SIGTERM to the process group and wait, because killing immediately orphans
containers.

---

## What WP6 must do differently from the spec sketch

1. The reference package must export a named-subject Env (E0); without one the
   compiled configuration is rejected before anything runs.
2. `push = false` in the compiled config **and** `--no-push` on argv (E1).
3. Never apply `require_output_files` to a dry-run directory (E2).
4. `verifiers/config.py`, not the dry run, rejects `use_bundled_skill`,
   `disabled_tools`, and non-run-owned skill paths (E3).
5. Pair on `trace.task.hash`; never on line position (E4).
6. Compare the resolved config to the compiled config as a **projection**,
   tolerating `client.base_url` and an `X-Prime-Team-ID` header the engine
   adds, and folding in the `--output-dir` the dry run itself overrode.
7. Carry `allow`/`block` on the Docker table so `network_policy: "restricted"`
   means something.
8. Read `trace.verifiers.commit` for the pin check; it is recorded per trace.
9. Redirect child stdout to a file; it is a full transcript dump.
10. Treat exit `130` as cancellation, and SIGTERM the process group first.

---

## Rerunning this preflight

`tests/preflight/test_verifiers_eval_contract.py` is marked `preflight` and
excluded from the default test run. It needs network access to github.com and
PyPI on first use.

```bash
make verifiers-preflight
```

To reuse an already-built engine venv:

```bash
TECHTREE_PREFLIGHT_ENGINE_PYTHON=/path/to/engine/.venv/bin/python \
  uv run pytest -m preflight tests/preflight
```

Either way the pin is read back from the installed distribution's
`direct_url.json`, so a stale venv fails loudly rather than proving the wrong
thing.
